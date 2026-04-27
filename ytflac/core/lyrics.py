# SpotiFLAC/core/lyrics.py
"""
Multi-provider lyrics fetcher.

Ordine di tentativo (configurabile):
  1. Spotify Web  — testo sincronizzato LRC (richiede sp_dc cookie)
  2. Apple Music  — testo sincronizzato LRC via paxsenix proxy
  3. Musixmatch   — testo sincronizzato / plain via paxsenix proxy
  4. Amazon Music — testo plain via API
  5. LRCLIB       — testo sincronizzato / plain
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

_LRCLIB          = "https://lrclib.net/api"
_SPOTIFY_LYRICS  = "https://spclient.wg.spotify.com/color-lyrics/v2/track"
_PAXSENIX_APPLE  = "https://lyrics.paxsenix.org/apple-music"
_PAXSENIX_MXM    = "https://lyrics.paxsenix.org/musixmatch"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "Chrome/145.0.0.0 Safari/537.36"
)

# Aggiunto Apple Music e messo in priorità
_DEFAULT_PROVIDERS = ["spotify", "apple", "musixmatch", "amazon", "lrclib"]

# Cache settings
_CACHE_TTL_S = 24 * 60 * 60  # 24 hours
_CACHE_FILE = os.path.expanduser("~/.cache/ytflac/lyrics_cache.json")
_MAX_CACHE_ENTRIES = 5000


# --------------------------------------------------------------------------- #
# Cache Implementation                                                        #
# --------------------------------------------------------------------------- #

@dataclass
class _CacheEntry:
    lyrics: str
    provider: str
    expires_at: float

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


class _LyricsCache:
    def __init__(self):
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._load_from_disk()

    def _get_cache_key(self, track_id: str, isrc: str, track_name: str, artist_name: str) -> str:
        """Generate a cache key from available identifiers."""
        if track_id:
            return f"track_id:{track_id}"
        if isrc:
            return f"isrc:{isrc}"
        # Fallback to name-based key
        return f"name:{track_name.lower().strip()}|{artist_name.lower().strip()}"

    def get(self, track_id: str, isrc: str, track_name: str, artist_name: str) -> tuple[str, str] | None:
        key = self._get_cache_key(track_id, isrc, track_name, artist_name)
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                logger.debug("[lyrics/cache] cache hit for %s", key)
                return entry.lyrics, entry.provider
            elif entry:
                # Remove expired entry
                del self._cache[key]
                self._save_to_disk()
        return None

    def set(self, track_id: str, isrc: str, track_name: str, artist_name: str, lyrics: str, provider: str) -> None:
        if not lyrics or not lyrics.strip():
            return
        key = self._get_cache_key(track_id, isrc, track_name, artist_name)
        expires_at = time.monotonic() + _CACHE_TTL_S
        with self._lock:
            self._cache[key] = _CacheEntry(lyrics, provider, expires_at)
            # Trim cache if too large
            if len(self._cache) > _MAX_CACHE_ENTRIES:
                # Remove oldest entries (simple FIFO)
                keys_to_remove = list(self._cache.keys())[:len(self._cache) - _MAX_CACHE_ENTRIES]
                for k in keys_to_remove:
                    del self._cache[k]
            self._save_to_disk()
        logger.debug("[lyrics/cache] cached %s from %s", key, provider)

    def _load_from_disk(self) -> None:
        try:
            cache_dir = os.path.dirname(_CACHE_FILE)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            if os.path.exists(_CACHE_FILE):
                with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    now = time.monotonic()
                    for key, value in data.items():
                        expires_at = value.get("expires_at", 0)
                        if expires_at > now:
                            self._cache[key] = _CacheEntry(
                                value["lyrics"],
                                value["provider"],
                                expires_at
                            )
                logger.debug("[lyrics/cache] loaded %d entries from disk", len(self._cache))
        except Exception as exc:
            logger.warning("[lyrics/cache] failed to load from disk: %s", exc)

    def _save_to_disk(self) -> None:
        try:
            cache_dir = os.path.dirname(_CACHE_FILE)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            data = {
                key: {
                    "lyrics": entry.lyrics,
                    "provider": entry.provider,
                    "expires_at": entry.expires_at
                }
                for key, entry in self._cache.items()
                if not entry.is_expired()
            }
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.warning("[lyrics/cache] failed to save to disk: %s", exc)


# Global cache instance
_lyrics_cache = _LyricsCache()


# --------------------------------------------------------------------------- #
# Provider 1 — Spotify Web                                                     #
# --------------------------------------------------------------------------- #

def _fetch_spotify(track_id: str, sp_dc_token: str, timeout: int = 10) -> str:
    if not track_id or not sp_dc_token:
        return ""
    try:
        client_token = _spotify_client_token(sp_dc_token, timeout)
        if not client_token:
            return ""

        r = requests.get(
            f"{_SPOTIFY_LYRICS}/{track_id}",
            params={"format": "json", "market": "from_token"},
            headers={
                "Authorization": f"Bearer {client_token}",
                "App-Platform":  "WebPlayer",
                "User-Agent":    _UA,
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            return ""

        data  = r.json()
        lines = data.get("lyrics", {}).get("lines", [])
        if not lines:
            return ""

        sync_type = data.get("lyrics", {}).get("syncType", "")
        if sync_type == "LINE_SYNCED":
            lrc_lines = []
            for line in lines:
                ms   = int(line.get("startTimeMs", 0))
                m, s = divmod(ms // 1000, 60)
                cs   = (ms % 1000) // 10
                words = line.get("words", "")
                lrc_lines.append(f"[{m:02d}:{s:02d}.{cs:02d}]{words}")
            return "\n".join(lrc_lines)

        return "\n".join(line.get("words", "") for line in lines)

    except Exception as exc:
        logger.debug("[lyrics/spotify] %s", exc)
        return ""


def _spotify_client_token(sp_dc: str, timeout: int) -> str:
    totp_headers: dict[str, str] = {}
    try:
        from .spotify_totp import generate_spotify_totp
        totp_code, totp_version = generate_spotify_totp()
        if totp_code:
            totp_headers["Spotify-TOTP"]    = totp_code
            totp_headers["Spotify-TOTP-V2"] = f"{totp_code}:{totp_version}"
    except Exception:
        pass

    try:
        r = requests.get(
            "https://open.spotify.com/get_access_token",
            params={"reason": "transport", "productType": "web_player"},
            headers={
                "Cookie":     f"sp_dc={sp_dc}",
                "User-Agent": _UA,
                **totp_headers,
            },
            timeout=timeout,
        )
        if r.ok:
            return r.json().get("accessToken", "")
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- #
# Provider 2 — Apple Music (Paxsenix Proxy)                                    #
# --------------------------------------------------------------------------- #

def _score_apple_result(res: dict, t_name: str, a_name: str, duration_s: int) -> int:
    score = 0
    r_t = res.get("songName", "").lower().strip()
    r_a = res.get("artistName", "").lower().strip()
    t_t = t_name.lower().strip()
    t_a = a_name.lower().strip()

    if r_t == t_t: score += 50
    elif t_t in r_t or r_t in t_t: score += 25

    if r_a == t_a: score += 60
    elif t_a in r_a or r_a in t_a: score += 30

    r_dur = res.get("duration", 0)
    if duration_s > 0 and r_dur > 0:
        diff = abs((r_dur / 1000.0) - duration_s)
        if diff <= 5:  # Tolerance
            score += 20
    return score

def _fetch_apple(track_name: str, artist_name: str, duration_s: int, timeout: int = 15) -> str:
    query = urllib.parse.quote(f"{track_name} {artist_name}")
    search_url = f"{_PAXSENIX_APPLE}/search?q={query}"

    try:
        r = requests.get(search_url, headers={"User-Agent": _UA, "Accept": "application/json"}, timeout=timeout)
        if not r.ok: return ""
        results = r.json()
        if not results: return ""

        best = max(results, key=lambda x: _score_apple_result(x, track_name, artist_name, duration_s))
        song_id = best.get("id")
        if not song_id: return ""

        lyrics_url = f"{_PAXSENIX_APPLE}/lyrics?id={song_id}"
        r_lyr = requests.get(lyrics_url, headers={"User-Agent": _UA, "Accept": "application/json"}, timeout=timeout)
        if not r_lyr.ok: return ""

        data = r_lyr.json()
        content = data.get("content", []) if isinstance(data, dict) else data

        lrc_lines = []
        for line in content:
            ts = line.get("timestamp", 0)
            m, s = divmod(ts // 1000, 60)
            cs = (ts % 1000) // 10

            text_parts = line.get("text", [])
            line_text = ""
            for part in text_parts:
                line_text += part.get("text", "")
                if not part.get("part", False):
                    line_text += " "

            line_text = line_text.strip()
            if line_text:
                lrc_lines.append(f"[{m:02d}:{s:02d}.{cs:02d}]{line_text}")

        return "\n".join(lrc_lines)

    except Exception as exc:
        logger.debug("[lyrics/apple] %s", exc)
        return ""


# --------------------------------------------------------------------------- #
# Provider 3 — Musixmatch (Paxsenix Proxy - NO TOKEN)                          #
# --------------------------------------------------------------------------- #

def _fetch_musixmatch(track_name: str, artist_name: str, duration_s: int, timeout: int = 15) -> str:
    params = {
        "t": track_name,
        "a": artist_name,
        "type": "word",
        "format": "lrc"
    }
    if duration_s > 0:
        params["d"] = str(duration_s)

    url = f"{_PAXSENIX_MXM}/lyrics?" + urllib.parse.urlencode(params)
    try:
        r = requests.get(url, headers={"User-Agent": _UA, "Accept": "application/json"}, timeout=timeout)
        if not r.ok: return ""

        body = r.text.strip()
        import json
        try:
            parsed = json.loads(body)
            if isinstance(parsed, str):
                return parsed.strip()
        except ValueError:
            # Fallback se restituisce plain text direttamente
            if body and not body.startswith("{"):
                return body
        return ""
    except Exception as exc:
        logger.debug("[lyrics/musixmatch] %s", exc)
        return ""


# --------------------------------------------------------------------------- #
# Provider 4 — Amazon Music                                                    #
# --------------------------------------------------------------------------- #

def _fetch_amazon(isrc: str, timeout: int = 15) -> str:
    if not isrc: return ""

    from ..providers.amazon import AMAZON_API_BASE

    try:
        r = requests.get(
            f"{AMAZON_API_BASE}/lyrics/{isrc}",
            headers={"User-Agent": _UA},
            timeout=timeout,
        )
        if not r.ok: return ""
        data  = r.json()
        lines = data.get("lines") or data.get("lyrics", [])
        if not lines: return ""

        if isinstance(lines[0], dict):
            lrc = []
            for line in lines:
                ts   = int(line.get("startTime", 0))
                m    = ts // 60000
                s    = (ts % 60000) // 1000
                cs   = (ts % 1000) // 10
                text = line.get("text", "")
                lrc.append(f"[{m:02d}:{s:02d}.{cs:02d}]{text}")
            return "\n".join(lrc)

        return "\n".join(str(l) for l in lines)
    except Exception as exc:
        logger.debug("[lyrics/amazon] %s", exc)
        return ""


# --------------------------------------------------------------------------- #
# Provider 5 — LRCLIB                                                          #
# --------------------------------------------------------------------------- #

def _fetch_lrclib(track_name: str, artist_name: str, album_name: str = "", duration_s: int = 0, timeout: int = 10) -> str:
    def _lrclib_exact(t, a, al, d):
        params = {"artist_name": a, "track_name": t}
        if al: params["album_name"] = al
        if d:  params["duration"]   = d
        try:
            r = requests.get(f"{_LRCLIB}/get", params=params, timeout=timeout)
            if r.status_code == 200:
                d = r.json()
                return d.get("syncedLyrics") or d.get("plainLyrics") or ""
        except Exception: pass
        return ""

    result = _lrclib_exact(track_name, artist_name, album_name, duration_s)
    if result: return result
    if album_name:
        result = _lrclib_exact(track_name, artist_name, "", duration_s)
        if result: return result

    try:
        r = requests.get(f"{_LRCLIB}/search", params={"artist_name": artist_name, "track_name": track_name}, timeout=timeout)
        if r.status_code == 200:
            results = r.json()
            if results:
                for item in results:
                    if item.get("syncedLyrics"): return item["syncedLyrics"]
                return results[0].get("plainLyrics", "")
    except Exception: pass
    return ""


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def fetch_lyrics(
        track_name:       str,
        artist_name:      str,
        album_name:       str  = "",
        duration_s:       int  = 0,
        track_id:         str  = "",
        isrc:             str  = "",
        providers:        list[str] | None = None,
        spotify_token:    str  = "",
) -> tuple[str, str]:
    # Check cache first
    cached = _lyrics_cache.get(track_id, isrc, track_name, artist_name)
    if cached:
        logger.debug("[lyrics] cache hit for '%s' by '%s'", track_name, artist_name)
        return cached

    if providers is None:
        providers = _DEFAULT_PROVIDERS

    for provider in providers:
        result = ""
        try:
            if provider == "spotify":
                result = _fetch_spotify(track_id, spotify_token)
            elif provider == "apple":
                result = _fetch_apple(track_name, artist_name, duration_s)
            elif provider == "musixmatch":
                result = _fetch_musixmatch(track_name, artist_name, duration_s)
            elif provider == "amazon":
                result = _fetch_amazon(isrc)
            elif provider == "lrclib":
                result = _fetch_lrclib(track_name, artist_name, album_name, duration_s)
            else:
                logger.warning("[lyrics] unknown provider: %s", provider)
        except Exception as exc:
            logger.debug("[lyrics/%s] unexpected error: %s", provider, exc)

        if result and result.strip():
            logger.debug("[lyrics] found via %s (%d chars)", provider, len(result))
            # Cache the result
            _lyrics_cache.set(track_id, isrc, track_name, artist_name, result.strip(), provider)
            return result.strip(), provider

    logger.debug("[lyrics] not found for '%s' by '%s'", track_name, artist_name)
    return "", ""
"""
YouTube Music input resolver — ported from E:\\Youtubeflac\\SpotiFLAC\\backend\\youtube_music.go.

Resolves YouTube / YouTube Music URLs (single tracks and playlists) into
SpotiFLAC ``TrackMetadata`` objects by cross-referencing with the Spotify
catalogue, allowing the existing download pipeline to work unchanged.
"""
from __future__ import annotations

import html as html_mod
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import NamedTuple
from urllib.parse import urlparse, parse_qs, quote

from ..core.http import HttpClient, RetryConfig
from ..core.models import TrackMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (mirrored from Go)
# ---------------------------------------------------------------------------

MAX_PLAYLIST_TRACKS = 0  # 0 = no cap
PER_TRACK_RESOLVE_TIMEOUT = 20  # seconds
MAX_UNMATCHED_SAMPLES = 20

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Regex patterns (mirrored from Go)
# ---------------------------------------------------------------------------

_PLAYLIST_VIDEO_ID_RE = re.compile(r'"videoId":"([A-Za-z0-9_-]{11})"')
_WATCH_ENDPOINT_VIDEO_ID_RE = re.compile(r'"watchEndpoint":\{"videoId":"([A-Za-z0-9_-]{11})"')
_VIDEO_ID_PATTERN = re.compile(r'([A-Za-z0-9_-]{11})')
_HEX_ESCAPE_RE = re.compile(r'\\x([0-9A-Fa-f]{2})')
_YT_INITIAL_DATA_MARKERS = (
    "var ytInitialData = ",
    "window['ytInitialData'] = ",
    'window["ytInitialData"] = ',
    "ytInitialData = ",
)
_HTML_TITLE_RE = re.compile(r"(?is)<title>(.*?)</title>")
_NORMALIZE_TEXT_RE = re.compile(r"[^a-z0-9]+")

_PAREN_NOISE_RE = re.compile(
    r"(?i)\s*[\(\[][^\)\]]*"
    r"(official|video|audio|lyric|lyrics|mv|m/v|hd|4k|visualizer|"
    r"remaster|remastered|explicit|clean|version)"
    r"[^\)\]]*[\)\]]"
)
_FEAT_PAREN_RE = re.compile(
    r"(?i)\s*[\(\[](feat\.?|ft\.?|featuring)\s[^\)\]]*[\)\]]"
)
_TRAILING_NOISE_RE = re.compile(
    r"(?i)\s*[-|–]\s*"
    r"(official\s+(music\s+)?video|official\s+audio|lyrics?\s+video|"
    r"visualizer|hd|4k)\s*$"
)

_VARIANT_KEYWORDS = {"live", "remix", "karaoke", "instrumental", "sped up", "slowed"}

# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


class YouTubeResolveResult(NamedTuple):
    """Return type for ``resolve_youtube_input``."""
    collection_name: str
    tracks: list[TrackMetadata]
    is_playlist: bool
    unmatched_samples: list[str]


@dataclass
class _YouTubeTrackContext:
    video_id: str = ""
    raw_title: str = ""
    raw_artist: str = ""
    clean_track: str = ""
    clean_artist: str = ""


# ---------------------------------------------------------------------------
# URL detection / extraction (mirrors Go URL helpers)
# ---------------------------------------------------------------------------


def is_youtube_url(url: str) -> bool:
    """Check whether *url* is a YouTube or YouTube Music URL."""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    return host in {
        "youtube.com", "www.youtube.com",
        "music.youtube.com", "www.music.youtube.com",
        "youtu.be",
    }


def _is_playlist_url(parsed) -> bool:
    list_id = parse_qs(parsed.query).get("list", [""])[0].strip()
    if not list_id:
        return False
    path = parsed.path.lower()
    has_video = bool(parse_qs(parsed.query).get("v", [""])[0].strip())
    if "/playlist" in path:
        return True
    return not has_video


def extract_playlist_id(url: str) -> str:
    parsed = urlparse(url.strip())
    pid = parse_qs(parsed.query).get("list", [""])[0].strip()
    if not pid:
        raise ValueError("YouTube URL must include list=<playlist_id>")
    return pid


def extract_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    # Standard ?v= parameter
    vid = parse_qs(parsed.query).get("v", [""])[0].strip()
    if vid:
        return vid
    # youtu.be/<id> short URL
    if (parsed.hostname or "").lower() == "youtu.be":
        path = parsed.path.lstrip("/")
        if path and len(path) == 11:
            return path
    # /embed/<id> style
    m = re.search(r"(?:/embed/|/v/)([A-Za-z0-9_-]{11})", parsed.path)
    if m:
        return m.group(1)
    raise ValueError("YouTube URL must point to a single track (watch?v=...)")


# ---------------------------------------------------------------------------
# HTTP helpers — reuses core.http.HttpClient
# ---------------------------------------------------------------------------


def _build_http(timeout: int = 25) -> HttpClient:
    return HttpClient(
        provider="youtube_input",
        timeout_s=timeout,
        retry=RetryConfig(max_attempts=3, base_delay_s=0.4),
        headers={"User-Agent": _DEFAULT_UA},
    )


# ---------------------------------------------------------------------------
# oEmbed + playlist HTML fetchers
# ---------------------------------------------------------------------------


def fetch_oembed(video_id: str, http: HttpClient | None = None) -> dict:
    """Fetch public oEmbed JSON for a YouTube video (title + author_name)."""
    http = http or _build_http()
    target = f"https://www.youtube.com/watch?v={quote(video_id)}"
    endpoint = f"https://www.youtube.com/oembed?format=json&url={quote(target, safe='')}"
    return http.get_json(endpoint)


def fetch_playlist_html(playlist_id: str, http: HttpClient | None = None) -> str:
    """Fetch raw HTML from YT Music (fallback: youtube.com) playlist page."""
    http = http or _build_http()
    endpoints = [
        f"https://music.youtube.com/playlist?list={quote(playlist_id)}",
        f"https://www.youtube.com/playlist?list={quote(playlist_id)}",
    ]
    last_err: Exception | None = None
    for url in endpoints:
        try:
            resp = http.get(url)
            return resp.text
        except Exception as exc:
            last_err = exc
            logger.warning("[youtube_input] playlist HTML fetch failed for %s: %s", url, exc)
    raise last_err or RuntimeError("Failed to fetch YouTube playlist HTML")


def _fetch_playlist_via_ytdlp(playlist_id: str) -> tuple[str, list[tuple[str, str, str]]]:
    """
    Fetch full playlist using yt-dlp (handles pagination natively).
    Returns (title, [(video_id, title, uploader), ...]).
    """
    try:
        import yt_dlp
    except ImportError:
        logger.warning("[youtube_input] yt-dlp not installed, falling back to HTML scraping")
        return "", []

    url = f"https://music.youtube.com/playlist?list={playlist_id}"
    opts = {
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', '') or ''
            entries = info.get('entries', []) or []
            tracks = []
            for entry in entries:
                if not entry:
                    continue
                vid = entry.get('id', '')
                track_title = entry.get('title', '') or ''
                uploader = entry.get('uploader', '') or entry.get('channel', '') or ''
                if vid and len(vid) == 11:
                    tracks.append((vid, track_title, uploader))
            return title, tracks
    except Exception as exc:
        logger.warning("[youtube_input] yt-dlp playlist fetch failed: %s", exc)
        return "", []


def _fetch_playlist_via_api(playlist_id: str, http: HttpClient | None = None) -> list[str]:
    """Fetch playlist video IDs using YouTube Data API with pagination."""
    http = http or _build_http()
    video_ids: list[str] = []
    next_page_token = None
    
    while True:
        # YouTube Data API endpoint for playlist items
        api_url = f"https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if next_page_token:
            params["pageToken"] = next_page_token
        
        try:
            resp = http.get(f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
            data = resp.json()
            
            if "items" in data:
                for item in data["items"]:
                    vid = item.get("contentDetails", {}).get("videoId", "")
                    if vid and vid not in video_ids:
                        video_ids.append(vid)
            
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
                
        except Exception as exc:
            logger.warning("[youtube_input] API playlist fetch failed: %s", exc)
            break
    
    return video_ids


def _fetch_playlist_title_via_api(playlist_id: str, http: HttpClient | None = None) -> str:
    """Fetch playlist title using YouTube Data API."""
    http = http or _build_http()
    
    api_url = f"https://www.googleapis.com/youtube/v3/playlists"
    params = {
        "part": "snippet",
        "id": playlist_id,
    }
    
    try:
        resp = http.get(f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
        data = resp.json()
        
        if "items" in data and data["items"]:
            return data["items"][0].get("snippet", {}).get("title", "")
    except Exception as exc:
        logger.warning("[youtube_input] API playlist title fetch failed: %s", exc)
    
    return ""


def _extract_continuation_token(html: str) -> str | None:
    """Extract continuation token from YouTube Music HTML."""
    # Try multiple patterns for continuation token
    patterns = [
        r'"continuation":"([^"]+)"',
        r'"ctoken":"([^"]+)"',
        r'"continuationCommand":\{"token":"([^"]+)"',
        r'"nextContinuationData":\{"continuation":"([^"]+)"',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html)
        if matches:
            # Return the last continuation token (most likely to be valid)
            return matches[-1]
    
    return None


def _fetch_continuation(continuation: str, http: HttpClient | None = None) -> str:
    """Fetch continuation data from YouTube Music."""
    http = http or _build_http()
    
    # YouTube Music continuation endpoint
    endpoint = "https://music.youtube.com/youtubei/v1/browse"
    
    # Build the request body
    body = {
        "context": {
            "client": {
                "clientName": "WEB_REMIX",
                "clientVersion": "0.1",
            }
        },
        "continuation": continuation,
    }
    
    headers = {
        "Content-Type": "application/json",
    }
    
    try:
        resp = http.post(endpoint, json=body, headers=headers)
        return resp.text
    except Exception as exc:
        logger.warning("[youtube_input] Continuation request failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------


def parse_playlist_title(raw_html: str) -> str:
    m = _HTML_TITLE_RE.search(raw_html)
    if not m:
        return "YouTube Music Playlist"
    title = html_mod.unescape(m.group(1)).strip()
    title = title.removesuffix(" - YouTube Music").removesuffix(" - YouTube").strip()
    return title or "YouTube Music Playlist"


def parse_playlist_video_ids(raw_html: str, max_count: int = MAX_PLAYLIST_TRACKS) -> list[str]:
    raw_html = _decode_js_hex_escapes(raw_html)
    seen: set[str] = set()
    result: list[str] = []
    
    # Try regex patterns first
    matches = _PLAYLIST_VIDEO_ID_RE.findall(raw_html)
    matches.extend(_WATCH_ENDPOINT_VIDEO_ID_RE.findall(raw_html))
    
    for vid in matches:
        vid = vid.strip()
        if not vid or vid in seen:
            continue
        seen.add(vid)
        result.append(vid)
        if max_count and len(result) >= max_count:
            break
    
    # If regex didn't get enough, try JSON parsing
    if not result or (max_count and len(result) < max_count):
        data = _extract_yt_initial_data(raw_html)
        if data:
            for vid in _collect_video_ids_from_json(data):
                if vid in seen:
                    continue
                seen.add(vid)
                result.append(vid)
                if max_count and len(result) >= max_count:
                    break
    
    # Fallback: try to extract all 11-char video IDs from the entire HTML
    # This catches IDs in different formats/contexts
    if not result or (max_count and len(result) < max_count):
        all_ids = _VIDEO_ID_PATTERN.findall(raw_html)
        for vid in all_ids:
            vid = vid.strip()
            # Basic validation: 11 chars, alphanumeric with _ and -
            if len(vid) == 11 and vid.replace('_', '').replace('-', '').isalnum():
                if vid not in seen:
                    seen.add(vid)
                    result.append(vid)
                    if max_count and len(result) >= max_count:
                        break
    
    return result


def _decode_js_hex_escapes(text: str) -> str:
    if "\\x" not in text:
        return text
    return _HEX_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def _extract_yt_initial_data(raw_html: str) -> dict | list | None:
    for marker in _YT_INITIAL_DATA_MARKERS:
        start = raw_html.find(marker)
        if start < 0:
            continue
        start = raw_html.find("{", start)
        if start < 0:
            continue
        blob = _extract_balanced_json(raw_html, start)
        if not blob:
            continue
        try:
            return json.loads(blob)
        except Exception as exc:
            logger.debug("[youtube_input] Failed to parse ytInitialData: %s", exc)
    return None


def _extract_balanced_json(text: str, start: int) -> str:
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def _collect_video_ids_from_json(data) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    def _walk(node):
        if isinstance(node, dict):
            vid = node.get("videoId")
            if isinstance(vid, str) and len(vid) == 11 and vid not in seen:
                seen.add(vid)
                result.append(vid)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(data)
    return result


# ---------------------------------------------------------------------------
# Title / artist cleanup (mirrors cleanYouTubeMetadata)
# ---------------------------------------------------------------------------


def clean_yt_title_artist(title: str, author: str) -> tuple[str, str]:
    """Clean noisy YouTube title/author into (track, artist)."""
    track = title.strip()
    track = _PAREN_NOISE_RE.sub("", track)
    track = _FEAT_PAREN_RE.sub("", track)
    track = _TRAILING_NOISE_RE.sub("", track)
    track = track.strip()

    artist = author.strip()
    # YouTube Music auto-generated channels: "Artist - Topic"
    if artist.endswith(" - Topic"):
        artist = artist[: -len(" - Topic")].strip()

    # Many uploads use "Artist - Track" in the title itself
    for sep in (" - ", " – ", " — "):
        idx = track.find(sep)
        if idx > 0:
            candidate_artist = track[:idx].strip()
            candidate_track = track[idx + len(sep):].strip()
            if candidate_artist and candidate_track:
                if not artist or artist.lower() == "youtube":
                    artist = candidate_artist
                track = candidate_track
            break

    return track, artist


# ---------------------------------------------------------------------------
# Spotify search query generation (mirrors Go)
# ---------------------------------------------------------------------------


def _normalize_text(value: str) -> str:
    v = unicodedata.normalize("NFKC", value.lower().strip())
    v = _NORMALIZE_TEXT_RE.sub(" ", v)
    return " ".join(v.split())


def _split_primary_artist(artist: str) -> str:
    norm = artist
    for sep in (" feat. ", " ft. ", " & ", " x "):
        norm = norm.replace(sep, ",")
    parts = norm.split(",")
    return parts[0].strip() if parts else artist.strip()


def _build_field_query(track: str, artist: str) -> str:
    track = track.strip()
    artist = artist.strip()
    if not track:
        return ""
    if not artist:
        return f'track:"{track}"'
    return f'track:"{track}" artist:"{artist}"'


def _build_plain_query(track: str, artist: str) -> str:
    q = track.strip()
    if artist:
        q = f"{artist.strip()} {q}"
    return q


def build_search_queries(track: str, artist: str) -> list[str]:
    """Generate multiple Spotify search queries ordered by specificity."""
    queries: list[str] = []
    seen: set[str] = set()

    def _add(q: str) -> None:
        q = q.strip()
        if not q:
            return
        key = q.lower()
        if key in seen:
            return
        seen.add(key)
        queries.append(q)

    primary = _split_primary_artist(artist)
    # Field filters (most precise)
    _add(_build_field_query(track, primary))
    _add(_build_field_query(track, artist))
    # Plain text queries
    _add(_build_plain_query(track, primary))
    _add(_build_plain_query(track, artist))
    # Track title only (last resort)
    _add(track)
    return queries


# ---------------------------------------------------------------------------
# Best-match selection (mirrors pickBestSpotifyTrackResult)
# ---------------------------------------------------------------------------


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    curr = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        curr[0] = i
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[len(b)]


def _has_variant_keyword(value: str) -> bool:
    v = _normalize_text(value)
    return any(kw in v for kw in _VARIANT_KEYWORDS)


@dataclass
class _SearchCandidate:
    track_id: str = ""
    name: str = ""
    artists: str = ""
    album_name: str = ""
    images: str = ""
    duration_ms: int = 0
    is_explicit: bool = False
    external_url: str = ""


def _candidate_from_spotify_item(item: dict) -> _SearchCandidate:
    """Convert a Spotify /search track item dict to _SearchCandidate."""
    album = item.get("album", {})
    artists_list = item.get("artists", [])
    artist_names = ", ".join(a.get("name", "") for a in artists_list if isinstance(a, dict))
    images = album.get("images", [])
    cover = images[0].get("url", "") if images else ""
    return _SearchCandidate(
        track_id=item.get("id", ""),
        name=item.get("name", ""),
        artists=artist_names,
        album_name=album.get("name", ""),
        images=cover,
        duration_ms=item.get("duration_ms", 0),
        is_explicit=item.get("explicit", False),
        external_url=item.get("external_urls", {}).get("spotify", ""),
    )


def pick_best_match(
    candidates: list[_SearchCandidate],
    wanted_track: str,
    wanted_artist: str,
    raw_title: str,
) -> _SearchCandidate | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    track_needle = _normalize_text(wanted_track)
    artist_needle = _normalize_text(wanted_artist)

    best = candidates[0]
    best_score = -1000

    for c in candidates:
        score = 0
        name = _normalize_text(c.name)
        artists = _normalize_text(c.artists)

        if track_needle:
            if name == track_needle:
                score += 4
            elif track_needle in name:
                score += 2

        if artist_needle:
            if artist_needle in artists:
                score += 3
            elif artists in artist_needle:
                score += 1

        if _levenshtein(name, track_needle) <= 2:
            score += 2

        if _has_variant_keyword(c.name) and not _has_variant_keyword(raw_title):
            score -= 3

        if score > best_score:
            best = c
            best_score = score

    return best


# ---------------------------------------------------------------------------
# Core resolve functions
# ---------------------------------------------------------------------------


def resolve_spotify_from_yt(
    video_id: str,
    spotify_client,
    http: HttpClient | None = None,
) -> tuple[TrackMetadata | None, _YouTubeTrackContext]:
    """Resolve a single YouTube video to a Spotify TrackMetadata.

    Returns (metadata_or_None, context).
    """
    http = http or _build_http()

    # 1. Fetch oEmbed
    try:
        oembed = fetch_oembed(video_id, http)
    except Exception as exc:
        logger.warning("[youtube_input] oEmbed failed for %s: %s", video_id, exc)
        return None, _YouTubeTrackContext(video_id=video_id)

    raw_title = oembed.get("title", "")
    raw_author = oembed.get("author_name", "")

    # 2. Clean metadata
    track, artist = clean_yt_title_artist(raw_title, raw_author)
    ctx = _YouTubeTrackContext(
        video_id=video_id,
        raw_title=raw_title,
        raw_artist=raw_author,
        clean_track=track,
        clean_artist=artist,
    )
    if not track:
        return None, ctx

    # 3. Search Spotify
    queries = build_search_queries(track, artist)
    candidates: list[_SearchCandidate] = []
    seen_ids: set[str] = set()

    for query in queries:
        try:
            items = spotify_client.search_tracks(query, limit=10)
        except Exception as exc:
            logger.debug("[youtube_input] Spotify search failed for %r: %s", query, exc)
            continue

        for item in items:
            c = _candidate_from_spotify_item(item)
            if not c.track_id or c.track_id in seen_ids:
                continue
            seen_ids.add(c.track_id)
            candidates.append(c)

        if len(candidates) >= 20:
            break

    if not candidates:
        logger.info("[youtube_input] No Spotify match for %r", _build_plain_query(track, artist))
        return None, ctx

    # 4. Pick best
    best = pick_best_match(candidates, track, artist, raw_title)
    if not best or not best.track_id:
        return None, ctx

    # 5. Fetch full TrackMetadata via existing SpotifyMetadataClient
    try:
        metadata = spotify_client.get_track(best.track_id)
    except Exception as exc:
        logger.warning("[youtube_input] get_track(%s) failed: %s", best.track_id, exc)
        return None, ctx

    return metadata, ctx


def resolve_youtube_playlist(
    url: str,
    spotify_client,
    http: HttpClient | None = None,
) -> YouTubeResolveResult:
    """Resolve a YouTube Music playlist URL into a list of TrackMetadata."""
    http = http or _build_http()

    playlist_id = extract_playlist_id(url)

    # Primary: use yt-dlp for full playlist extraction with pagination
    title, ytdlp_tracks = _fetch_playlist_via_ytdlp(playlist_id)

    if ytdlp_tracks:
        # We already have title + uploader from yt-dlp, skip oEmbed per-video
        from concurrent.futures import ThreadPoolExecutor

        def _resolve_with_meta(item: tuple[str, str, str]):
            vid, raw_title, raw_uploader = item
            try:
                return _resolve_spotify_from_yt_meta(
                    vid, raw_title, raw_uploader, spotify_client
                )
            except Exception as exc:
                logger.warning("[youtube_input] Video %s resolve crashed: %s", vid, exc)
                return None, _YouTubeTrackContext(video_id=vid, raw_title=raw_title, raw_artist=raw_uploader)

        max_workers = min(8, len(ytdlp_tracks))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(_resolve_with_meta, ytdlp_tracks))

        tracks: list[TrackMetadata] = []
        unmatched: list[str] = []
        for (vid, raw_title, _), (metadata, ctx) in zip(ytdlp_tracks, results):
            if metadata is None:
                if len(unmatched) < MAX_UNMATCHED_SAMPLES:
                    unmatched.append(ctx.raw_title or raw_title or vid)
                continue
            tracks.append(metadata)

        if not tracks:
            raise ValueError("No playlist tracks could be matched on Spotify")

        return YouTubeResolveResult(
            collection_name=title or "YouTube Music Playlist",
            tracks=tracks,
            is_playlist=True,
            unmatched_samples=unmatched,
        )

    # Fallback: HTML scraping (limited to ~100 tracks)
    raw_html = fetch_playlist_html(playlist_id, http)
    title = parse_playlist_title(raw_html)
    video_ids = parse_playlist_video_ids(raw_html, MAX_PLAYLIST_TRACKS)

    if not video_ids:
        raise ValueError("No tracks found in YouTube Music playlist")

    from concurrent.futures import ThreadPoolExecutor

    def _resolve(vid: str):
        try:
            return resolve_spotify_from_yt(vid, spotify_client, http)
        except Exception as exc:
            logger.warning("[youtube_input] Video %s resolve crashed: %s", vid, exc)
            return None, _YouTubeTrackContext(video_id=vid)

    max_workers = min(8, len(video_ids))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_resolve, video_ids))

    tracks = []
    unmatched = []
    for vid, (metadata, ctx) in zip(video_ids, results):
        if metadata is None:
            if len(unmatched) < MAX_UNMATCHED_SAMPLES:
                unmatched.append(ctx.raw_title or vid)
            continue
        tracks.append(metadata)

    if not tracks:
        raise ValueError("No playlist tracks could be matched on Spotify")

    return YouTubeResolveResult(
        collection_name=title,
        tracks=tracks,
        is_playlist=True,
        unmatched_samples=unmatched,
    )


def _resolve_spotify_from_yt_meta(
    video_id: str,
    raw_title: str,
    raw_author: str,
    spotify_client,
) -> tuple[TrackMetadata | None, _YouTubeTrackContext]:
    """Resolve YouTube video to Spotify track using already-fetched title/author.
    
    Skips the oEmbed call since yt-dlp already provided this metadata.
    """
    track, artist = clean_yt_title_artist(raw_title, raw_author)
    ctx = _YouTubeTrackContext(
        video_id=video_id,
        raw_title=raw_title,
        raw_artist=raw_author,
        clean_track=track,
        clean_artist=artist,
    )
    if not track:
        return None, ctx

    queries = build_search_queries(track, artist)
    candidates: list[_SearchCandidate] = []
    seen_ids: set[str] = set()

    for query in queries:
        try:
            items = spotify_client.search_tracks(query, limit=10)
        except Exception as exc:
            logger.debug("[youtube_input] Spotify search failed for %r: %s", query, exc)
            continue

        for item in items:
            c = _candidate_from_spotify_item(item)
            if not c.track_id or c.track_id in seen_ids:
                continue
            seen_ids.add(c.track_id)
            candidates.append(c)

        if len(candidates) >= 20:
            break

    if not candidates:
        return None, ctx

    best = pick_best_match(candidates, track, artist, raw_title)
    if not best or not best.track_id:
        return None, ctx

    try:
        metadata = spotify_client.get_track(best.track_id)
    except Exception as exc:
        logger.warning("[youtube_input] get_track(%s) failed: %s", best.track_id, exc)
        return None, ctx

    return metadata, ctx


def resolve_youtube_track(
    url: str,
    spotify_client,
    http: HttpClient | None = None,
) -> YouTubeResolveResult:
    """Resolve a single YouTube watch URL into a TrackMetadata."""
    http = http or _build_http()
    video_id = extract_video_id(url)
    metadata, ctx = resolve_spotify_from_yt(video_id, spotify_client, http)
    if metadata is None:
        raise ValueError(
            f"Could not match YouTube video to Spotify: "
            f"{ctx.raw_title or ctx.video_id}"
        )
    return YouTubeResolveResult(
        collection_name=metadata.title,
        tracks=[metadata],
        is_playlist=False,
        unmatched_samples=[],
    )


def resolve_youtube_input(
    url: str,
    spotify_client,
) -> YouTubeResolveResult:
    """Top-level dispatcher — mirrors ``ResolveYouTubeMusicInput`` from Go.

    Detects whether the URL is a playlist or single track and dispatches
    to the appropriate resolver.
    """
    parsed = urlparse(url.strip())
    http = _build_http()

    if _is_playlist_url(parsed):
        return resolve_youtube_playlist(url, spotify_client, http)
    return resolve_youtube_track(url, spotify_client, http)

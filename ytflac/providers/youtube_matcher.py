"""
YouTube → Spotify match scoring and search-query building.
Extracted from ``youtube_input.py`` to keep file sizes manageable.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from ..core.models import TrackMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for title/artist cleanup
# ---------------------------------------------------------------------------

_PAREN_NOISE_RE = re.compile(
    r"(?i)\s*[\(\[][^\)\]]*"
    r"(official|video|audio|lyric|lyrics|mv|m/v|hd|4k|visualizer|"
    r"remaster|remastered|explicit|clean|version)"
    r"[^\)\]]*[\)\]]"
)
_FEAT_PAREN_RE = re.compile(r"(?i)\s*[\(\[](feat\.?|ft\.?|featuring)\s[^\)\]]*[\)\]]")
_TRAILING_NOISE_RE = re.compile(
    r"(?i)\s*[-|\-]\s*"
    r"(official\s+(music\s+)?video|official\s+audio|lyrics?\s+video|"
    r"visualizer|hd|4k)\s*$"
)

_NORMALIZE_TEXT_RE = re.compile(r"[^a-z0-9]+")
_VARIANT_KEYWORDS = {"live", "remix", "karaoke", "instrumental", "sped up", "slowed"}


# ---------------------------------------------------------------------------
# Title / artist cleanup
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
    for sep in (" - ", " - ", " - "):
        idx = track.find(sep)
        if idx > 0:
            candidate_artist = track[:idx].strip()
            candidate_track = track[idx + len(sep) :].strip()
            if candidate_artist and candidate_track:
                if not artist or artist.lower() == "youtube":
                    artist = candidate_artist
                track = candidate_track
            break

    return track, artist


# ---------------------------------------------------------------------------
# Spotify search query generation
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
# Best-match selection
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
    artist_names = ", ".join(
        a.get("name", "") for a in artists_list if isinstance(a, dict)
    )
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


def _score_candidate(
    candidate: _SearchCandidate,
    track_needle: str,
    artist_needle: str,
    raw_title: str,
) -> int:
    score = 0
    name = _normalize_text(candidate.name)
    artists = _normalize_text(candidate.artists)

    if track_needle:
        if name == track_needle:
            score += 4
        elif track_needle in name or name in track_needle:
            score += 2

    if artist_needle:
        if artist_needle in artists:
            score += 3
        elif artists in artist_needle:
            score += 1

    if track_needle and _levenshtein(name, track_needle) <= 2:
        score += 2

    if _has_variant_keyword(candidate.name) and not _has_variant_keyword(raw_title):
        score -= 3

    return score


def _score_to_confidence(raw_score: int) -> int:
    """Normalise a raw _score_candidate result to a 0-100 confidence integer."""
    low, high = 0, 12
    clamped = max(low, min(high, raw_score))
    return int((clamped / high) * 100)


def _artist_overlap_ratio(a: str, b: str) -> float:
    a_tokens = {t for t in _normalize_text(a).split() if len(t) > 1}
    b_tokens = {t for t in _normalize_text(b).split() if len(t) > 1}
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens & b_tokens)
    return inter / max(len(a_tokens), len(b_tokens))


def _is_confident_match(
    candidate: _SearchCandidate,
    wanted_track: str,
    wanted_artist: str,
    raw_title: str,
) -> bool:
    track_needle = _normalize_text(wanted_track)
    artist_needle = _normalize_text(wanted_artist)
    name = _normalize_text(candidate.name)

    score = _score_candidate(candidate, track_needle, artist_needle, raw_title)
    if score < 4:
        return False

    if track_needle:
        max_dist = max(2, len(track_needle) // 3)
        if _levenshtein(name, track_needle) > max_dist:
            return False

    if wanted_artist and _artist_overlap_ratio(candidate.artists, wanted_artist) < 0.34:
        return False

    return True


def pick_best_match(
    candidates: list[_SearchCandidate],
    wanted_track: str,
    wanted_artist: str,
    raw_title: str,
) -> tuple[_SearchCandidate | None, int]:
    """Return (best candidate, raw score). Score is 0 if no candidates."""
    if not candidates:
        return None, 0
    if len(candidates) == 1:
        track_needle = _normalize_text(wanted_track)
        artist_needle = _normalize_text(wanted_artist)
        s = _score_candidate(candidates[0], track_needle, artist_needle, raw_title)
        return candidates[0], s

    track_needle = _normalize_text(wanted_track)
    artist_needle = _normalize_text(wanted_artist)

    best = candidates[0]
    best_score = -1000

    for c in candidates:
        score = _score_candidate(c, track_needle, artist_needle, raw_title)
        if score > best_score:
            best = c
            best_score = score

    return best, best_score


def _secondary_verify_match(
    spotify_client,
    wanted_track: str,
    wanted_artist: str,
    raw_title: str,
    raw_artist: str,
) -> _SearchCandidate | None:
    queries: list[str] = []
    seen_q: set[str] = set()

    def _add_query(value: str) -> None:
        value = value.strip()
        if not value:
            return
        key = value.lower()
        if key in seen_q:
            return
        seen_q.add(key)
        queries.append(value)

    primary_artist = _split_primary_artist(wanted_artist or raw_artist)
    _add_query(_build_field_query(wanted_track, primary_artist))
    _add_query(_build_field_query(wanted_track, wanted_artist))
    _add_query(_build_plain_query(wanted_track, primary_artist))
    _add_query(_build_plain_query(wanted_track, wanted_artist))

    alt_track, alt_artist = clean_yt_title_artist(raw_title, raw_artist)
    _add_query(_build_field_query(alt_track, _split_primary_artist(alt_artist)))
    _add_query(_build_plain_query(alt_track, alt_artist))
    _add_query(raw_title)

    candidates: list[_SearchCandidate] = []
    seen_ids: set[str] = set()
    for query in queries:
        try:
            items = spotify_client.search_tracks(query, limit=12)
        except Exception as exc:
            logger.debug(
                "[youtube_input] Secondary search failed for %r: %s", query, exc
            )
            continue

        for item in items:
            c = _candidate_from_spotify_item(item)
            if not c.track_id or c.track_id in seen_ids:
                continue
            seen_ids.add(c.track_id)
            candidates.append(c)

    if not candidates:
        return None

    best, _score = pick_best_match(
        candidates, wanted_track or alt_track, wanted_artist or alt_artist, raw_title
    )
    if not best:
        return None

    if _is_confident_match(
        best, wanted_track or alt_track, wanted_artist or alt_artist, raw_title
    ):
        return best

    return None

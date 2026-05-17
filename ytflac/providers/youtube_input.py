"""
YouTube Music input resolver — ported from E:\\Youtubeflac\\SpotiFLAC\\backend\\youtube_music.go.

Resolves YouTube / YouTube Music URLs (single tracks and playlists) into
SpotiFLAC ``TrackMetadata`` objects by cross-referencing with the Spotify
catalogue, allowing the existing download pipeline to work unchanged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import NamedTuple
from urllib.parse import urlparse, parse_qs, quote

from ..core.http import HttpClient, RetryConfig
from ..core.models import TrackMetadata

from .youtube_parser import (
    parse_playlist_title,
    parse_playlist_video_ids,
    extract_continuation_token,
)
from .youtube_matcher import (
    clean_yt_title_artist,
    build_search_queries,
    _candidate_from_spotify_item,
    _is_confident_match,
    _score_to_confidence,
    _SearchCandidate,
    _secondary_verify_match,
    pick_best_match,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
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
# URL detection / extraction
# ---------------------------------------------------------------------------


def is_youtube_url(url: str) -> bool:
    """Check whether *url* is a YouTube or YouTube Music URL."""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    return host in {
        "youtube.com",
        "www.youtube.com",
        "music.youtube.com",
        "www.music.youtube.com",
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
# HTTP helpers
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
    endpoint = (
        f"https://www.youtube.com/oembed?format=json&url={quote(target, safe='')}"
    )
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
            logger.warning(
                "[youtube_input] playlist HTML fetch failed for %s: %s", url, exc
            )
    raise last_err or RuntimeError("Failed to fetch YouTube playlist HTML")


def _fetch_playlist_via_ytdlp(
    playlist_id: str,
) -> tuple[str, list[tuple[str, str, str]]]:
    """
    Fetch full playlist using yt-dlp (handles pagination natively).
    Returns (title, [(video_id, title, uploader), ...]).
    """
    try:
        import yt_dlp
    except ImportError:
        logger.warning(
            "[youtube_input] yt-dlp not installed, falling back to HTML scraping"
        )
        return "", []

    url = f"https://music.youtube.com/playlist?list={playlist_id}"
    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "") or ""
            entries = info.get("entries", []) or []
            tracks = []
            for entry in entries:
                if not entry:
                    continue
                vid = entry.get("id", "")
                track_title = entry.get("title", "") or ""
                uploader = entry.get("uploader", "") or entry.get("channel", "") or ""
                if vid and len(vid) == 11:
                    tracks.append((vid, track_title, uploader))
            return title, tracks
    except Exception as exc:
        logger.warning("[youtube_input] yt-dlp playlist fetch failed: %s", exc)
        return "", []


def _fetch_playlist_via_api(
    playlist_id: str, http: HttpClient | None = None
) -> list[str]:
    """Fetch playlist video IDs using YouTube Data API with pagination."""
    http = http or _build_http()
    video_ids: list[str] = []
    next_page_token = None

    while True:
        api_url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            resp = http.get(
                f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
            )
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


def _fetch_playlist_title_via_api(
    playlist_id: str, http: HttpClient | None = None
) -> str:
    """Fetch playlist title using YouTube Data API."""
    http = http or _build_http()

    api_url = "https://www.googleapis.com/youtube/v3/playlists"
    params = {
        "part": "snippet",
        "id": playlist_id,
    }

    try:
        resp = http.get(f"{api_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
        data = resp.json()

        if data.get("items"):
            return data["items"][0].get("snippet", {}).get("title", "")
    except Exception as exc:
        logger.warning("[youtube_input] API playlist title fetch failed: %s", exc)

    return ""


def _fetch_continuation(continuation: str, http: HttpClient | None = None) -> str:
    """Fetch continuation data from YouTube Music."""
    http = http or _build_http()

    endpoint = "https://music.youtube.com/youtubei/v1/browse"

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

    best: _SearchCandidate | None = None
    if not candidates:
        logger.info(
            "[youtube_input] No Spotify match for %r",
            f"{artist.strip()} {track.strip()}".strip(),
        )
    else:
        # 4. Pick best
        best, raw_score = pick_best_match(candidates, track, artist, raw_title)

    confidence = 0
    if (
        not best
        or not best.track_id
        or not _is_confident_match(best, track, artist, raw_title)
    ):
        verified = _secondary_verify_match(
            spotify_client,
            track,
            artist,
            raw_title,
            raw_author,
        )
        if not verified:
            return None, ctx
        best = verified
        # Secondary verification passed — treat as moderate confidence
        confidence = 55
    else:
        confidence = _score_to_confidence(raw_score)

    # 5. Fetch full TrackMetadata via existing SpotifyMetadataClient
    try:
        metadata = spotify_client.get_track(best.track_id)
        metadata = metadata.model_copy(update={
            "match_confidence": confidence,
            "match_source": "youtube",
        })
    except Exception as exc:
        logger.warning("[youtube_input] get_track(%s) failed: %s", best.track_id, exc)
        return None, ctx

    return metadata, ctx


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

    best: _SearchCandidate | None = None
    if candidates:
        best, raw_score = pick_best_match(candidates, track, artist, raw_title)

    confidence = 0
    if (
        not best
        or not best.track_id
        or not _is_confident_match(best, track, artist, raw_title)
    ):
        verified = _secondary_verify_match(
            spotify_client,
            track,
            artist,
            raw_title,
            raw_author,
        )
        if not verified:
            return None, ctx
        best = verified
        confidence = 55
    else:
        confidence = _score_to_confidence(raw_score)

    try:
        metadata = spotify_client.get_track(best.track_id)
        metadata = metadata.model_copy(update={
            "match_confidence": confidence,
            "match_source": "youtube",
        })
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
                return None, _YouTubeTrackContext(
                    video_id=vid, raw_title=raw_title, raw_artist=raw_uploader
                )

        max_workers = min(8, len(ytdlp_tracks))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            results = list(pool.map(_resolve_with_meta, ytdlp_tracks))

        tracks: list[TrackMetadata] = []
        unmatched: list[str] = []
        for (vid, raw_title, _), (metadata, ctx) in zip(ytdlp_tracks, results):
            if metadata is None:
                # Collect all unmatched — UI will display them
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
            f"Could not match YouTube video to Spotify: {ctx.raw_title or ctx.video_id}"
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

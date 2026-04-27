"""
Downloader — orchestratore principale.
"""
from __future__ import annotations
import logging
import os
import random
import re
import time

from dataclasses import dataclass, field
from pathlib import Path

from .core.models import TrackMetadata, DownloadResult
from .core.progress import DownloadManager, ProgressCallback
from .core.errors import ErrorKind, SpotiflacError, classify_error
from .core.console import print_track_header, print_source_banner, print_summary, print_api_failure, print_quality_fallback
from .core.provider_stats import (
    is_provider_open,
    prioritize,
    provider_cooldown_remaining,
    record_failure,
    record_provider_failure,
    record_provider_success,
    record_success,
)

from .core.history import HistoryManager
from .core.isrc_cache import get_cached_isrc, put_cached_isrc
from .providers.base import BaseProvider
from .providers.spotify_metadata import SpotifyMetadataClient

logger = logging.getLogger(__name__)

# Initialize debug modules
_history_manager = HistoryManager()


# ---------------------------------------------------------------------------
# Failure log — written to a separate, user-shareable file
# ---------------------------------------------------------------------------

def _failure_log_path() -> str:
    return os.path.join(os.getcwd(), "ytflac_failures.log")


def _log_failure(metadata: "TrackMetadata", per_provider_errors: dict[str, str]) -> None:
    """Append a detailed failure block to ytflac_failures.log."""
    try:
        from datetime import datetime
        path = _failure_log_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] FAILED\n")
            f.write(f"Track   : {metadata.title}\n")
            f.write(f"Artist  : {metadata.artists}\n")
            f.write(f"Album   : {metadata.album}\n")
            f.write(f"ISRC    : {metadata.isrc or '-'}\n")
            f.write(f"ID      : {metadata.id}\n")
            f.write("Providers tried:\n")
            for prov, err in per_provider_errors.items():
                kind = classify_error(err)
                f.write(f"  - {prov:<10} [{kind.name}] {err}\n")
            f.write("\n")
    except Exception:
        # Logging errors must never break the download pipeline
        pass


def _retryable_provider_failure(kind: ErrorKind) -> bool:
    return kind in {ErrorKind.NETWORK_ERROR, ErrorKind.RATE_LIMITED, ErrorKind.UNAVAILABLE}


def _provider_retry_cap(kind: ErrorKind) -> int:
    # Keep retries conservative: avoid hammering unstable endpoints.
    if kind == ErrorKind.RATE_LIMITED:
        return 3
    if kind == ErrorKind.NETWORK_ERROR:
        return 2
    if kind == ErrorKind.UNAVAILABLE:
        return 2
    return 1


def _retry_sleep_seconds(attempt: int) -> float:
    # Exponential backoff with jitter.
    base = min(6.0, 0.8 * (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, 0.6)
    return base + jitter


def _order_providers_for_track(providers: list[BaseProvider]) -> list[BaseProvider]:
    """
    Order providers by observed fallback success while honoring circuit breaker.
    Open providers are tried first; providers in cooldown are pushed to the end.
    """
    if not providers:
        return []

    by_name: dict[str, BaseProvider] = {}
    names: list[str] = []
    for p in providers:
        if p.name not in by_name:
            by_name[p.name] = p
            names.append(p.name)

    ranked_names = prioritize("provider_fallback", names)

    open_names: list[str] = []
    cooling_names: list[str] = []
    for name in ranked_names:
        if is_provider_open(name):
            open_names.append(name)
        else:
            cooling_names.append(name)

    ordered_names = open_names + cooling_names
    return [by_name[n] for n in ordered_names if n in by_name]


@dataclass
class DownloadOptions:
    output_dir:              str
    services:                list[str]       = field(default_factory=lambda: ["tidal"])
    filename_format:         str             = "{title} - {artist}"
    use_track_numbers:       bool            = False
    use_album_track_numbers: bool         = False
    use_artist_subfolders:   bool           = False
    use_album_subfolders:    bool           = False
    first_artist_only:       bool            = False
    quality:                 str             = "LOSSLESS"
    allow_fallback:          bool            = True
    inter_track_delay_s:     float           = 0.5

    embed_lyrics:            bool          = False
    lyrics_providers:        list[str]     = field(
        default_factory=lambda: ["spotify", "musixmatch", "amazon", "lrclib"]
    )
    lyrics_spotify_token:    str           = ""

    enrich_metadata:    bool           = False
    enrich_providers:   list[str]      = field(
        default_factory=lambda: ["deezer", "apple", "qobuz", "tidal"]
    )
    qobuz_token:        str | None     = None


def _build_provider(name: str, opts: DownloadOptions) -> BaseProvider | None:
    from .providers.tidal import TidalProvider
    from .providers.qobuz import QobuzProvider

    if name == "tidal":
        return TidalProvider()
    if name == "qobuz":
        return QobuzProvider(qobuz_token=opts.qobuz_token)

    adapters = {
        "amazon":  ("providers.amazon",  "AmazonProvider"),
        "deezer":  ("providers.deezer",  "DeezerProvider"),
        "youtube": ("providers.youtube", "YouTubeProvider"),
        "spoti":  ("providers.spotidownloader", "SpotiDownloaderProvider"),
    }
    if name not in adapters:
        logger.warning("Unknown provider: %s", name)
        return None

    module_path, class_name = adapters[name]
    try:
        import importlib
        pkg = __name__.rsplit(".", 1)[0]
        mod = importlib.import_module(f".{module_path}", package=pkg)
        return getattr(mod, class_name)()
    except Exception as exc:
        logger.warning("Provider %s unavailable: %s", name, exc)
        return None


def download_one(
        metadata:   TrackMetadata,
        output_dir: str,
        providers:  list[BaseProvider],
        opts:       DownloadOptions,
        position:   int = 1,
) -> DownloadResult:
    errors: dict[str, str] = {}
    manager = DownloadManager()
    
    # Add to progress queue
    manager.add_to_queue(metadata.id, metadata.title, metadata.artists, metadata.album, metadata.id)
    
    # Check ISRC cache
    cached_isrc = get_cached_isrc(metadata.id)
    if cached_isrc:
        logger.debug(f"[ISRC Cache] Hit for {metadata.id}: {cached_isrc}")
        if not metadata.isrc:
            metadata = metadata.model_copy(update={"isrc": cached_isrc})

    for provider in _order_providers_for_track(providers):
        if not is_provider_open(provider.name):
            cooldown = provider_cooldown_remaining(provider.name)
            msg = f"circuit open ({cooldown}s cooldown remaining)"
            errors[provider.name] = msg
            logger.info("[%s] Skipped for %s — %s: %s", provider.name, metadata.artists, metadata.title, msg)
            continue

        logger.info("[%s] Trying: %s — %s", provider.name, metadata.artists, metadata.title)

        cb = ProgressCallback(item_id=metadata.id)
        provider.set_progress_callback(cb)

        attempt = 1
        max_attempts = 1
        while attempt <= max_attempts:
            result = provider.download_track(
                metadata,
                output_dir,
                filename_format     = opts.filename_format,
                position            = position,
                include_track_num   = opts.use_track_numbers,
                use_album_track_num = opts.use_album_track_numbers,
                first_artist_only   = opts.first_artist_only,
                allow_fallback      = opts.allow_fallback,
                quality             = opts.quality,
                embed_lyrics            = opts.embed_lyrics,
                lyrics_providers        = opts.lyrics_providers,
                lyrics_spotify_token    = opts.lyrics_spotify_token,
                enrich_metadata         = opts.enrich_metadata,
                enrich_providers        = opts.enrich_providers,
            )

            if result.success:
                logger.info("[%s] ✓ %s — %s", provider.name, metadata.artists, metadata.title)
                record_success(provider.name, getattr(provider, "_last_api_url", "unknown"))
                record_success("provider_fallback", provider.name)
                record_provider_success(provider.name)

                _history_manager.add_download(
                    track_id=metadata.id,
                    track_name=metadata.title,
                    artist_name=metadata.artists,
                    provider=provider.name,
                    success=True,
                    file_path=result.file_path,
                )

                if metadata.isrc:
                    put_cached_isrc(metadata.id, metadata.isrc)
                return result

            err = result.error or "unknown error"
            kind = classify_error(err)
            errors[provider.name] = err
            logger.warning("[%s] ✗ %s", provider.name, err)

            record_failure(provider.name, getattr(provider, "_last_api_url", "unknown"))
            record_failure("provider_fallback", provider.name)
            record_provider_failure(provider.name, kind)

            max_attempts = _provider_retry_cap(kind)
            if _retryable_provider_failure(kind) and attempt < max_attempts:
                sleep_s = _retry_sleep_seconds(attempt)
                logger.info(
                    "[%s] retrying (%s) attempt %d/%d in %.1fs",
                    provider.name,
                    kind.name,
                    attempt + 1,
                    max_attempts,
                    sleep_s,
                )
                time.sleep(sleep_s)
                attempt += 1
                continue

            _history_manager.add_download(
                track_id=metadata.id,
                track_name=metadata.title,
                artist_name=metadata.artists,
                provider=provider.name,
                success=False,
                file_path="",
            )
            break

    summary_parts = []
    for prov, err in errors.items():
        kind = classify_error(err)
        summary_parts.append(f"{prov} [{kind.name}]: {err}")
    summary = " || ".join(summary_parts)

    # Persistent, user-shareable failure log
    _log_failure(metadata, errors)

    return DownloadResult.fail("none", f"All providers failed — {summary}")


class DownloadWorker:
    def __init__(
            self,
            tracks:   list[TrackMetadata],
            opts:     DownloadOptions,
            collection_name: str = "",
            is_album:     bool = False,
            is_playlist:  bool = False,
    ) -> None:
        self._tracks          = tracks
        self._opts            = opts
        self._collection_name = collection_name
        self._is_album        = is_album
        self._is_playlist     = is_playlist
        self._failed:  list[tuple[str, str, str]] = []
        self._providers: list[BaseProvider] = self._build_providers()

    def _build_providers(self) -> list[BaseProvider]:
        result = []
        for name in self._opts.services:
            p = _build_provider(name, self._opts)
            if p:
                result.append(p)
        if not result:
            raise ValueError(f"No valid providers found in: {self._opts.services}")
        return result

    def run(self) -> list[tuple[str, str, str]]:
        manager   = DownloadManager()
        total     = len(self._tracks)
        start     = time.perf_counter()
        base_out  = self._resolve_output_dir()

        for i, track in enumerate(self._tracks):
            position = i + 1
            print_track_header(position, total, track.title, track.artists, track.album)

            manager.start_download(track.id)

            out_dir = self._track_output_dir(base_out, track)
            result  = download_one(
                track, out_dir, self._providers, self._opts, position
            )

            if result.success:
                size_mb = (
                    os.path.getsize(result.file_path) / (1024 * 1024)
                    if result.file_path and os.path.exists(result.file_path)
                    else 0.0
                )
                manager.complete_download(track.id, result.file_path or "", size_mb)
            else:
                err = result.error or "unknown"
                self._failed.append((track.title, track.artists, err))
                logger.error("[worker] Failed: %s — %s: %s", track.title, track.artists, err)
                manager.fail_download(track.id, err)

            if i < total - 1:
                time.sleep(self._opts.inter_track_delay_s)

        elapsed = time.perf_counter() - start
        self._print_summary(elapsed)
        return self._failed

    def _resolve_output_dir(self) -> str:
        out = os.path.normpath(self._opts.output_dir)
        if (self._is_album or self._is_playlist) and self._collection_name:
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", self._collection_name.strip())
            out = os.path.join(out, safe_name)
        os.makedirs(out, exist_ok=True)
        return out

    def _track_output_dir(self, base: str, track: TrackMetadata) -> str:
        out = base
        if self._is_playlist:
            if self._opts.use_artist_subfolders:
                folder = re.sub(r'[<>:"/\\|?*]', "_", track.first_artist)
                out = os.path.join(out, folder)
            if self._opts.use_album_subfolders:
                folder = re.sub(r'[<>:"/\\|?*]', "_", track.album)
                out = os.path.join(out, folder)
        os.makedirs(out, exist_ok=True)
        return out

    def _print_summary(self, elapsed: float) -> None:
        succeeded = len(self._tracks) - len(self._failed)
        print_summary(len(self._tracks), succeeded, self._failed, elapsed)


class SpotiflacDownloader:
    def __init__(self, opts: DownloadOptions) -> None:
        self._opts   = opts
        self._client = SpotifyMetadataClient()

    def run(self, spotify_url: str, loop_minutes: int | None = None) -> None:
        while True:
            self._run_once(spotify_url)
            if not loop_minutes or loop_minutes <= 0:
                break
            print(f"\nNext run in {loop_minutes} minutes…")
            time.sleep(loop_minutes * 60)

    def _run_once(self, spotify_url: str) -> None:
        print("Fetching metadata…")

        # --- YouTube input detection ---
        from .providers.youtube_input import is_youtube_url, resolve_youtube_input

        is_album    = False
        is_playlist = False
        collection_name = ""
        tracks: list[TrackMetadata] = []
        unmatched_samples: list[str] = []

        if is_youtube_url(spotify_url):
            try:
                result = resolve_youtube_input(spotify_url, self._client)
                collection_name   = result.collection_name
                tracks            = result.tracks
                is_playlist       = result.is_playlist
                unmatched_samples = result.unmatched_samples
            except Exception as exc:
                logger.error("YouTube resolve failed: %s", exc)
                print(f"Error: {exc}")
                return

            if unmatched_samples:
                print(f"  ⚠ {len(unmatched_samples)} track(s) could not be matched on Spotify:")
                for sample in unmatched_samples[:10]:
                    print(f"    • {sample}")
        else:
            try:
                collection_name, tracks = self._client.get_url(spotify_url)
            except SpotiflacError as exc:
                logger.error("Metadata fetch failed: %s", exc)
                print(f"Error: {exc}")
                return

        if not tracks:
            print("No tracks found.")
            return

        missing_isrc = [t for t in tracks if not t.isrc]
        if missing_isrc:
            print(f"Resolving ISRC for {len(missing_isrc)} track(s)…")
            try:
                from .core.isrc_helper import IsrcHelper
                from .core.http import HttpClient
                resolver = IsrcHelper(HttpClient("isrc"))
                for i, track in enumerate(tracks):
                    if not track.isrc:
                        resolved = resolver.get_isrc(track.id)
                        if resolved:
                            tracks[i] = track.model_copy(update={"isrc": resolved})
                            logger.debug("[isrc] resolved %s → %s", track.id, resolved)
            except Exception as exc:
                logger.warning("[isrc] bulk resolution failed: %s", exc)

        print(f"Found {len(tracks)} track(s) in: {collection_name}")

        if not is_youtube_url(spotify_url):
            from .providers.spotify_metadata import parse_spotify_url
            info        = parse_spotify_url(spotify_url)
            is_album    = info["type"] == "album"
            is_playlist = info["type"] == "playlist"

        manager = DownloadManager()
        for t in tracks:
            manager.add_to_queue(t.id, t.title, t.artists, t.album, t.id)

        worker = DownloadWorker(
            tracks          = tracks,
            opts            = self._opts,
            collection_name = collection_name,
            is_album        = is_album,
            is_playlist     = is_playlist,
        )
        worker.run()


def _format_seconds(seconds: float) -> str:
    s = int(round(seconds))
    parts = []
    for unit, div in [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
        val, s = divmod(s, div)
        if val:
            parts.append(f"{val}{unit}")
    return " ".join(parts) or "0s"
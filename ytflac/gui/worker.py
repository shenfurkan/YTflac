"""
QThread workers — resolve URL + download tracks without blocking the UI.
"""
from __future__ import annotations
import os
import re
import time

from PyQt6.QtCore import QThread, pyqtSignal


class ResolveWorker(QThread):
    """Resolves a Spotify or YouTube URL to a track list."""
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, url: str, spotify_client, parent=None):
        super().__init__(parent)
        self._url    = url
        self._client = spotify_client

    def run(self):
        try:
            from ..providers.youtube_input import (
                is_youtube_url, resolve_youtube_input, YouTubeResolveResult,
            )
            from ..providers.spotify_metadata import parse_spotify_url

            if is_youtube_url(self._url):
                result = resolve_youtube_input(self._url, self._client)
            else:
                info = parse_spotify_url(self._url)
                name, tracks = self._client.get_url(self._url)
                is_pl = info["type"] in ("album", "playlist")
                result = YouTubeResolveResult(
                    collection_name   = name,
                    tracks            = tracks,
                    is_playlist       = is_pl,
                    unmatched_samples = [],
                )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class DownloadWorker(QThread):
    """
    Downloads selected tracks. Emits both per-track and aggregate signals.

    Emits:
      track_started(index, title)
      track_done(index, title)
      track_failed(index, title, error)
      progress(current, total, title)        # legacy aggregate
      progress_speed(current, total, title, speed_mbps, eta_seconds)  # new with speed
      finished(succeeded, failed)
      error(msg)                             # fatal worker error
    """
    track_started = pyqtSignal(int, str)
    track_done    = pyqtSignal(int, str)
    track_failed  = pyqtSignal(int, str, str)

    progress = pyqtSignal(int, int, str)
    progress_speed = pyqtSignal(int, int, str, float, float)  # current, total, title, speed_mbps, eta_seconds
    cooldown = pyqtSignal(int, int)   # remaining_seconds, total_seconds
    finished = pyqtSignal(int, int)
    error    = pyqtSignal(str)

    def __init__(self, tracks, opts, collection_name: str,
                 is_playlist: bool, selected_indices: list[int] | None = None,
                 cooldown_every: int = 20,
                 cooldown_seconds: int = 30,
                 parent=None):
        super().__init__(parent)
        self._tracks           = tracks
        self._opts             = opts
        self._collection_name  = collection_name
        self._is_playlist      = is_playlist
        if selected_indices is None:
            selected_indices = list(range(len(tracks)))
        self._selected = list(selected_indices)
        self._cooldown_every   = max(0, int(cooldown_every))
        self._cooldown_seconds = max(0, int(cooldown_seconds))
        self._start_time = 0.0

    def run(self):
        try:
            from ..downloader import DownloadWorker as _DW, download_one

            worker = _DW(
                tracks          = self._tracks,
                opts            = self._opts,
                collection_name = self._collection_name,
                is_playlist     = self._is_playlist,
            )
            providers = worker._providers

            base = os.path.normpath(self._opts.output_dir)
            if self._is_playlist and self._collection_name:
                safe = re.sub(r'[<>:"/\\|?*]', "_", self._collection_name.strip())
                base = os.path.join(base, safe)
            os.makedirs(base, exist_ok=True)

            total     = len(self._selected)
            succeeded = 0
            failed    = 0
            self._start_time = time.time()

            cd_every = self._cooldown_every
            cd_secs  = self._cooldown_seconds
            # Skip cooldown entirely on small batches.
            cooldown_active = cd_every > 0 and cd_secs > 0 and total > cd_every

            for done_count, idx in enumerate(self._selected, start=1):
                if self.isInterruptionRequested():
                    break

                track = self._tracks[idx]
                self.track_started.emit(idx, track.title)
                self.progress.emit(done_count, total, track.title)

                # Calculate speed and ETA
                elapsed = time.time() - self._start_time
                speed_mbps = 0.0
                eta_seconds = 0.0
                if done_count > 1 and elapsed > 0:
                    tracks_per_sec = done_count / elapsed
                    speed_mbps = 0.0  # Could be calculated if we track bytes downloaded
                    remaining = total - done_count
                    eta_seconds = remaining / tracks_per_sec if tracks_per_sec > 0 else 0.0
                self.progress_speed.emit(done_count, total, track.title, speed_mbps, eta_seconds)

                try:
                    result = download_one(track, base, providers, self._opts, idx + 1)
                except Exception as exc:
                    # Never crash the worker on a single track failure.
                    failed += 1
                    self.track_failed.emit(idx, track.title, str(exc))
                else:
                    if result.success:
                        succeeded += 1
                        self.track_done.emit(idx, track.title)
                    else:
                        failed += 1
                        self.track_failed.emit(idx, track.title, result.error or "unknown")

                # Standby cooldown to avoid provider rate limits.
                if (cooldown_active
                        and done_count < total
                        and done_count % cd_every == 0):
                    for remaining in range(cd_secs, 0, -1):
                        if self.isInterruptionRequested():
                            break
                        self.cooldown.emit(remaining, cd_secs)
                        self.msleep(1000)
                    self.cooldown.emit(0, cd_secs)

            self.finished.emit(succeeded, failed)
        except Exception as exc:
            self.error.emit(str(exc))

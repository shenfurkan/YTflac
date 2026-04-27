"""
QThread workers — resolve URL + download tracks without blocking the UI.
"""
from __future__ import annotations
import os
import re

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
      finished(succeeded, failed)
      error(msg)                             # fatal worker error
    """
    track_started = pyqtSignal(int, str)
    track_done    = pyqtSignal(int, str)
    track_failed  = pyqtSignal(int, str, str)

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int)
    error    = pyqtSignal(str)

    def __init__(self, tracks, opts, collection_name: str,
                 is_playlist: bool, selected_indices: list[int] | None = None,
                 parent=None):
        super().__init__(parent)
        self._tracks           = tracks
        self._opts             = opts
        self._collection_name  = collection_name
        self._is_playlist      = is_playlist
        if selected_indices is None:
            selected_indices = list(range(len(tracks)))
        self._selected = list(selected_indices)

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

            for done_count, idx in enumerate(self._selected, start=1):
                track = self._tracks[idx]
                self.track_started.emit(idx, track.title)
                self.progress.emit(done_count, total, track.title)

                try:
                    result = download_one(track, base, providers, self._opts, idx + 1)
                except Exception as exc:
                    failed += 1
                    self.track_failed.emit(idx, track.title, str(exc))
                    continue

                if result.success:
                    succeeded += 1
                    self.track_done.emit(idx, track.title)
                else:
                    failed += 1
                    self.track_failed.emit(idx, track.title, result.error or "unknown")

            self.finished.emit(succeeded, failed)
        except Exception as exc:
            self.error.emit(str(exc))

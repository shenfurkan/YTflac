"""
QThread workers — resolve URL + download tracks without blocking the UI.
"""
from __future__ import annotations
import contextlib
import os
import re
import time

from PyQt6.QtCore import QThread, pyqtSignal


class ResolveWorker(QThread):
    """Resolves a Spotify or YouTube URL to a track list."""
    finished    = pyqtSignal(object)
    error       = pyqtSignal(str)
    log_message = pyqtSignal(str, str)   # text, level

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
                self.log_message.emit("Resolving YouTube Music URL…", "info")
                result = resolve_youtube_input(self._url, self._client)
            else:
                self.log_message.emit("Resolving Spotify URL…", "info")
                info = parse_spotify_url(self._url)
                name, tracks = self._client.get_url(self._url)
                is_pl = info["type"] in ("album", "playlist")
                result = YouTubeResolveResult(
                    collection_name   = name,
                    tracks            = tracks,
                    is_playlist       = is_pl,
                    unmatched_samples = [],
                )
            self.log_message.emit(f"Found {len(result.tracks)} tracks", "success")
            self.finished.emit(result)
        except Exception as exc:
            self.log_message.emit(f"Resolve failed: {exc}", "error")
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
      log_message(text, level)                 # human-friendly live log
      finished(succeeded, failed)
      error(msg)                             # fatal worker error
    """
    track_started = pyqtSignal(int, str)
    track_done    = pyqtSignal(int, str)
    track_failed  = pyqtSignal(int, str, str)

    progress = pyqtSignal(int, int, str)
    progress_speed = pyqtSignal(int, int, str, float, float)  # current, total, title, speed_mbps, eta_seconds
    log_message = pyqtSignal(str, str)   # text, level
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
            from ..system_awake import keep_awake

            worker = _DW(
                tracks          = self._tracks,
                opts            = self._opts,
                collection_name = self._collection_name,
                is_playlist     = self._is_playlist,
            )
            providers = worker._providers

            base = os.path.normpath(self._opts.output_dir)
            if self._is_playlist and self._collection_name:
                safe = re.sub(r'[<>:\"/\\|?*]', "_", self._collection_name.strip())
                base = os.path.join(base, safe)
            os.makedirs(base, exist_ok=True)

            total     = len(self._selected)
            succeeded = 0
            failed    = 0
            failed_first_pass: list[tuple[int, object, str]] = []
            self._start_time = time.time()

            self.log_message.emit(f"Starting download of {total} tracks", "info")

            cd_every = self._cooldown_every
            cd_secs  = self._cooldown_seconds
            # Skip cooldown entirely on small batches.
            cooldown_active = cd_every > 0 and cd_secs > 0 and total > cd_every

            def _log_cb(msg: str, level: str) -> None:
                self.log_message.emit(msg, level)

            keep_awake_enabled = self._is_playlist or total > 1
            with keep_awake(display=True) if keep_awake_enabled else contextlib.nullcontext():
                for done_count, idx in enumerate(self._selected, start=1):
                    if self.isInterruptionRequested():
                        self.log_message.emit("Stop requested — finishing current track", "warning")
                        break

                    track = self._tracks[idx]
                    self.track_started.emit(idx, track.title)
                    self.log_message.emit(
                        f"Track {done_count}/{total}: {track.title} — {track.artists}",
                        "info",
                    )
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
                        result = download_one(
                            track, base, providers, self._opts, idx + 1,
                            log_callback=_log_cb,
                        )
                    except Exception as exc:
                        # Never crash the worker on a single track failure.
                        failed += 1
                        self.track_failed.emit(idx, track.title, str(exc))
                        self.log_message.emit(f"Failed: {exc}", "error")
                        failed_first_pass.append((idx, track, str(exc)))
                    else:
                        if result.success:
                            succeeded += 1
                            self.track_done.emit(idx, track.title)
                            short_path = result.file_path
                            if short_path:
                                short_path = os.path.basename(short_path)
                            self.log_message.emit(f"Done — saved to {short_path}", "success")
                        else:
                            failed += 1
                            self.track_failed.emit(idx, track.title, result.error or "unknown")
                            self.log_message.emit(f"Failed: {result.error or 'unknown'}", "error")
                            failed_first_pass.append((idx, track, result.error or "unknown"))

                    # Standby cooldown to avoid provider rate limits.
                    if (cooldown_active
                            and done_count < total
                            and done_count % cd_every == 0):
                        for remaining in range(cd_secs, 0, -1):
                            if self.isInterruptionRequested():
                                break
                            self.cooldown.emit(remaining, cd_secs)
                            self.log_message.emit(
                                f"Cooldown {remaining}s (rate-limit protection)",
                                "warning",
                            )
                            self.msleep(1000)
                        self.cooldown.emit(0, cd_secs)

                if failed_first_pass:
                    self.log_message.emit(
                        f"Final retry pass for {len(failed_first_pass)} failed track(s)",
                        "warning",
                    )

                for idx, track, first_err in failed_first_pass:
                    if self.isInterruptionRequested():
                        break

                    self.log_message.emit(
                        f"Retrying once: {track.title} — {track.artists}",
                        "warning",
                    )
                    try:
                        retry_result = download_one(
                            track,
                            base,
                            providers,
                            self._opts,
                            idx + 1,
                            log_callback=_log_cb,
                        )
                    except Exception as exc:
                        self.log_message.emit(f"Final retry failed: {exc}", "error")
                        continue

                    if retry_result.success:
                        succeeded += 1
                        failed = max(0, failed - 1)
                        self.track_done.emit(idx, track.title)
                        short_path = retry_result.file_path
                        if short_path:
                            short_path = os.path.basename(short_path)
                        self.log_message.emit(f"Retry success — saved to {short_path}", "success")
                    else:
                        final_err = retry_result.error or first_err
                        self.log_message.emit(f"Final retry failed: {final_err}", "error")

            elapsed = time.time() - self._start_time
            self.log_message.emit(
                f"Finished — {succeeded} ok, {failed} failed in {elapsed:.1f}s",
                "info",
            )
            self.finished.emit(succeeded, failed)
        except Exception as exc:
            self.log_message.emit(f"Worker crashed: {exc}", "error")
            self.error.emit(str(exc))

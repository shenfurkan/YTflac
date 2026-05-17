"""
QThread workers — resolve URL + download tracks without blocking the UI.
"""

from __future__ import annotations
import os
import re
import time
import contextlib
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from PyQt6.QtCore import QThread, pyqtSignal


class ResolveWorker(QThread):
    """Resolves a Spotify or YouTube URL to a track list."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    log_message = pyqtSignal(str, str)  # text, level

    def __init__(self, url: str, spotify_client, parent=None):
        super().__init__(parent)
        self._url = url
        self._client = spotify_client

    def run(self):
        try:
            from ..providers.youtube_input import (
                is_youtube_url,
                resolve_youtube_input,
                YouTubeResolveResult,
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
                    collection_name=name,
                    tracks=tracks,
                    is_playlist=is_pl,
                    unmatched_samples=[],
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
    track_done = pyqtSignal(int, str)
    track_failed = pyqtSignal(int, str, str)
    track_progress = pyqtSignal(int, int)  # index, percentage (0-100)

    progress = pyqtSignal(int, int, str)
    progress_speed = pyqtSignal(
        int, int, str, float, float
    )  # current, total, title, speed_mbps, eta_seconds
    log_message = pyqtSignal(str, str)  # text, level
    cooldown = pyqtSignal(int, int)  # remaining_seconds, total_seconds
    finished = pyqtSignal(int, int)
    error = pyqtSignal(str)

    def __init__(
        self,
        tracks,
        opts,
        collection_name: str,
        is_playlist: bool,
        selected_indices: list[int] | None = None,
        max_concurrent: int = 2,
        cooldown_every: int = 20,
        cooldown_seconds: int = 30,
        parent=None,
    ):
        super().__init__(parent)
        self._tracks = tracks
        self._opts = opts
        self._collection_name = collection_name
        self._is_playlist = is_playlist
        if selected_indices is None:
            selected_indices = list(range(len(tracks)))
        self._selected = list(selected_indices)
        self._max_concurrent = max(1, int(max_concurrent))
        self._cooldown_every = max(0, int(cooldown_every))
        self._cooldown_seconds = max(0, int(cooldown_seconds))
        self._start_time = 0.0

    def run(self):
        try:
            from ..downloader import DownloadWorker as _DW, download_one
            from ..system_awake import keep_awake

            base = os.path.normpath(self._opts.output_dir)
            if self._is_playlist and self._collection_name:
                safe = re.sub(r"[<>:\"/\\|?*]", "_", self._collection_name.strip())
                base = os.path.join(base, safe)
            os.makedirs(base, exist_ok=True)

            total = len(self._selected)
            succeeded = 0
            failed = 0
            failed_first_pass: list[tuple[int, object, str]] = []
            self._start_time = time.time()

            self.log_message.emit(f"Starting download of {total} tracks", "info")

            cd_every = self._cooldown_every
            cd_secs = self._cooldown_seconds
            # Skip cooldown entirely on small batches.
            cooldown_active = cd_every > 0 and cd_secs > 0 and total > cd_every

            max_workers = max(1, min(self._max_concurrent, 5))

            self.log_message.emit(
                f"Concurrency: {max_workers} parallel worker(s)",
                "info",
            )

            def _log_cb(msg: str, level: str) -> None:
                self.log_message.emit(msg, level)

            def _download_task(idx: int):
                local_worker = _DW(
                    tracks=self._tracks,
                    opts=self._opts,
                    collection_name=self._collection_name,
                    is_playlist=self._is_playlist,
                )
                track = self._tracks[idx]
                try:
                    def _progress_cb(percentage: int):
                        self.track_progress.emit(idx, percentage)
                    result = download_one(
                        track,
                        base,
                        local_worker._providers,
                        self._opts,
                        idx + 1,
                        log_callback=_log_cb,
                        progress_callback=_progress_cb,
                    )
                    return idx, track, result, None
                except Exception as exc:
                    return idx, track, None, exc

            def _handle_result(idx: int, track, result, exc, completed_count: int):
                nonlocal succeeded, failed

                self.progress.emit(completed_count, total, track.title)

                elapsed = time.time() - self._start_time
                speed_mbps = 0.0
                eta_seconds = 0.0
                if completed_count > 0 and elapsed > 0:
                    tracks_per_sec = completed_count / elapsed
                    remaining = total - completed_count
                    eta_seconds = remaining / tracks_per_sec if tracks_per_sec > 0 else 0.0
                self.progress_speed.emit(
                    completed_count, total, track.title, speed_mbps, eta_seconds
                )

                if exc is not None:
                    failed += 1
                    self.track_failed.emit(idx, track.title, str(exc))
                    self.log_message.emit(f"Failed: {exc}", "error")
                    failed_first_pass.append((idx, track, str(exc)))
                    return

                if result and result.success:
                    succeeded += 1
                    self.track_done.emit(idx, track.title)
                    short_path = result.file_path
                    if short_path:
                        short_path = os.path.basename(short_path)
                    self.log_message.emit(
                        f"Done — saved to {short_path}", "success"
                    )
                else:
                    failed += 1
                    err = (result.error if result else "unknown") or "unknown"
                    self.track_failed.emit(idx, track.title, err)
                    self.log_message.emit(f"Failed: {err}", "error")
                    failed_first_pass.append((idx, track, err))

            keep_awake_enabled = self._is_playlist or total > 1
            with (
                keep_awake(display=True)
                if keep_awake_enabled
                else contextlib.nullcontext()
            ):
                completed_count = 0
                next_pos = 0

                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    pending: dict = {}

                    while True:
                        if self.isInterruptionRequested():
                            self.log_message.emit(
                                "Stop requested — waiting active downloads", "warning"
                            )
                            break

                        while (
                            next_pos < total
                            and len(pending) < max_workers
                        ):
                            idx = self._selected[next_pos]
                            track = self._tracks[idx]
                            self.track_started.emit(idx, track.title)
                            self.log_message.emit(
                                f"Track {next_pos + 1}/{total}: {track.title} — {track.artists}",
                                "info",
                            )
                            fut = pool.submit(_download_task, idx)
                            pending[fut] = idx
                            next_pos += 1

                        if not pending:
                            if next_pos >= total:
                                break
                            self.msleep(50)
                            continue

                        done, _ = wait(
                            set(pending.keys()),
                            timeout=0.25,
                            return_when=FIRST_COMPLETED,
                        )
                        if not done:
                            continue

                        for fut in done:
                            pending.pop(fut, None)
                            idx, track, result, exc = fut.result()
                            completed_count += 1
                            _handle_result(idx, track, result, exc, completed_count)

                            if (
                                cooldown_active
                                and completed_count < total
                                and completed_count % cd_every == 0
                            ):
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

                    if self.isInterruptionRequested():
                        for fut in pending:
                            fut.cancel()

                if failed_first_pass:
                    self.log_message.emit(
                        f"Final retry pass for {len(failed_first_pass)} failed track(s)",
                        "warning",
                    )

                    retry_worker = _DW(
                        tracks=self._tracks,
                        opts=self._opts,
                        collection_name=self._collection_name,
                        is_playlist=self._is_playlist,
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
                            retry_worker._providers,
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
                        self.log_message.emit(
                            f"Retry success — saved to {short_path}", "success"
                        )
                    else:
                        final_err = retry_result.error or first_err
                        self.log_message.emit(
                            f"Final retry failed: {final_err}", "error"
                        )

            elapsed = time.time() - self._start_time
            self.log_message.emit(
                f"Finished — {succeeded} ok, {failed} failed in {elapsed:.1f}s",
                "info",
            )
            self.finished.emit(succeeded, failed)
        except Exception as exc:
            self.log_message.emit(f"Worker crashed: {exc}", "error")
            self.error.emit(str(exc))

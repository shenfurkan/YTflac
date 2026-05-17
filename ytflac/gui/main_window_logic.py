from __future__ import annotations

from .worker import ResolveWorker


def _on_preview(self):
    url = self._url_input.text().strip()
    if not url or (
        self._resolve_worker is not None and self._resolve_worker.isRunning()
    ):
        return
    self._set_preview_busy(True)
    self._dl_btn.setEnabled(False)
    self._clear_results()
    self._status_lbl.setText("Fetching playlist… (large playlists may take ~30s)")

    if hasattr(self, "_log_panel") and self._log_panel:
        self._log_panel.clear()

    self._resolve_worker = ResolveWorker(url, self._spotify, self)
    self._resolve_worker.finished.connect(self._on_resolve_done)
    self._resolve_worker.error.connect(self._on_resolve_error)
    self._resolve_worker.log_message.connect(self._on_log_message)
    self._resolve_worker.start()


def _on_resolve_done(self, result):
    self._resolve_worker = None
    self._set_result(result)
    self._last_url = self._url_input.text().strip()
    self._set_preview_busy(False)
    self._refresh_btn.setVisible(True)

    self._header = self._header.__class__(
        name=result.collection_name or "—",
        cover=result.tracks[0].cover_url if result.tracks else "",
        count=len(result.tracks),
        unmatched=len(result.unmatched_samples),
    ) if False else None
    # Create header via imported class from components
    from .components import PlaylistHeader, UnmatchedPanel

    youtube_confidences = [
        int(getattr(track, "match_confidence", 100) or 0)
        for track in result.tracks
        if getattr(track, "match_source", "spotify") == "youtube"
    ]
    avg_match = (
        round(sum(youtube_confidences) / len(youtube_confidences))
        if youtube_confidences
        else None
    )
    low_confidence = sum(1 for value in youtube_confidences if value < 60)

    self._header = PlaylistHeader(
        name=result.collection_name or "—",
        cover=result.tracks[0].cover_url if result.tracks else "",
        count=len(result.tracks),
        unmatched=len(result.unmatched_samples),
        avg_match=avg_match,
        low_confidence=low_confidence,
    )
    self._header_box.addWidget(self._header)

    self._unmatched_panel = None
    if result.unmatched_samples:
        self._unmatched_panel = UnmatchedPanel(result.unmatched_samples)
        self._unmatched_panel.manual_match.connect(self._on_manual_match)
        self._header_box.addWidget(self._unmatched_panel)

    downloaded_ids = self._history.get_downloaded_ids()
    failed_ids = self._history.get_failed_ids()
    new_count = 0
    retry_count = 0
    skip_count = 0

    self._track_model.reset_tracks(result.tracks)
    with self._selection_batch():
        self._set_selected_indices(set())
        for i, track in enumerate(result.tracks):
            if track.id in downloaded_ids:
                self._track_model.set_row_checked(i, False)
                skip_count += 1
            elif track.id in failed_ids:
                self._track_model.set_row_checked(i, True)
                self._selected.add(i)
                retry_count += 1
            else:
                self._track_model.set_row_checked(i, True)
                self._selected.add(i)
                new_count += 1

    parts = []
    if skip_count:
        parts.append(f"{skip_count} already downloaded")
    if retry_count:
        parts.append(f"{retry_count} will retry")
    if new_count:
        parts.append(f"{new_count} new")
    total_history = skip_count + retry_count
    if total_history > 0 and parts:
        self._status_lbl.setText("Re-import: " + "  ·  ".join(parts))
    elif new_count == len(result.tracks):
        self._status_lbl.setText(f"Ready  ·  {new_count} track" + ("s" if new_count != 1 else ""))
    else:
        self._status_lbl.setText("")

    self._search_input.clear()
    self._fade_to_page(1)
    self._update_dl_button()
    self._update_select_btn()
    self._update_header_count()


def _deselect_all(self):
    visible = self._visible_source_rows()
    if not visible:
        visible = list(range(self._track_model.rowCount()))
    with self._selection_batch():
        for i in visible:
            self._track_model.set_row_checked(i, False)
            self._selected.discard(i)
    self._update_dl_button()
    self._update_select_btn()
    self._update_header_count()


def _on_refresh(self):
    url = self._last_url or self._url_input.text().strip()
    if not url:
        return
    self._url_input.setText(url)
    self._on_preview()


def _on_manual_match(self, unmatched_idx: int, spotify_url: str):
    try:
        from ..providers.spotify_metadata import parse_spotify_url

        info = parse_spotify_url(spotify_url)
        if info.get("type") != "track":
            self.show_toast("Please paste a Spotify track URL", "warning")
            return

        track_id = info.get("id", "")
        metadata = self._spotify.get_track(track_id)
    except Exception as exc:
        self.show_toast(f"Could not fetch track from Spotify: {exc}", "error")
        return

    if self._result is not None:
        new_idx = len(self._result.tracks)
        self._result.tracks.append(metadata)
        self._track_model.append_track(metadata, checked=True)
        self._selected.add(new_idx)

        self._update_dl_button()
        self._update_header_count()

        if self._unmatched_panel:
            self._unmatched_panel.mark_fixed(
                unmatched_idx,
                f"{metadata.title} — {metadata.artists}",
            )

        self._status_lbl.setText(
            f"✓ Matched: {metadata.title} — {metadata.artists}"
        )


def _invert_selection(self):
    visible = self._visible_source_rows()
    if not visible:
        visible = list(range(self._track_model.rowCount()))
    with self._selection_batch():
        for i in visible:
            now = self._track_model.is_row_checked(i)
            self._track_model.set_row_checked(i, not now)
            if now:
                self._selected.discard(i)
            else:
                self._selected.add(i)
    self._update_dl_button()
    self._update_select_btn()
    self._update_header_count()


def _on_resolve_error(self, msg: str):
    self._resolve_worker = None
    self._set_preview_busy(False)
    self._update_dl_button()
    self._status_lbl.setText("")
    self.show_toast(f"Failed to resolve URL: {msg}", "error")


def _on_row_toggled(self, index_one_based: int, checked: bool):
    idx = index_one_based - 1
    self._track_model.set_row_checked(idx, checked)
    if checked:
        self._selected.add(idx)
    else:
        self._selected.discard(idx)
    self._update_dl_button()
    self._update_select_btn()
    self._update_header_count()


def _toggle_all(self):
    visible = self._visible_source_rows()
    if not visible:
        visible = list(range(self._track_model.rowCount()))
    all_checked = all(self._track_model.is_row_checked(i) for i in visible)
    target = not all_checked
    with self._selection_batch():
        for i in visible:
            self._track_model.set_row_checked(i, target)
            if target:
                self._selected.add(i)
            else:
                self._selected.discard(i)
    self._update_dl_button()
    self._update_select_btn()
    self._update_header_count()


def _update_select_btn(self):
    has_rows = self._track_model.rowCount() > 0
    has_selection = bool(self._selected)
    self._deselect_btn.setEnabled(has_rows and has_selection)
    self._invert_btn.setEnabled(has_rows)
    self._clear_list_btn.setEnabled(has_rows and not self._is_downloading)


def _update_dl_button(self):
    n = len(self._selected)
    if self._is_downloading:
        return
    self._dl_btn.setText(f"Download ({n})" if n else "Download")
    self._dl_btn.setEnabled(n > 0 and self._result is not None)


def _update_header_count(self):
    if self._header is not None:
        self._header.set_selection_count(len(self._selected))


def _on_search_changed(self, _text: str):
    self._search_timer.start()


def _apply_search_filter(self):
    needle = self._search_input.text().strip()
    self._set_filter_text(needle)
    self._update_select_btn()


def _clear_results(self):
    while self._header_box.count():
        it = self._header_box.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
    self._header = None
    self._unmatched_panel = None

    self._track_model.clear()
    self._set_selected_indices(set())
    self._set_result(None)
    self._set_filter_text("")
    if hasattr(self, "_search_input"):
        self._search_input.clear()
    if hasattr(self, "_refresh_btn"):
        self._refresh_btn.setVisible(False)
    self._fade_to_page(0)
    self._update_dl_button()


def _set_preview_busy(self, busy: bool):
    self._preview_btn.setEnabled(not busy)
    self._preview_btn.setText("Loading…" if busy else "Preview")

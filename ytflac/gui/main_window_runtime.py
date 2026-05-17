from __future__ import annotations

import contextlib
import logging
import os

from PyQt6.QtCore import QPropertyAnimation, QTimer, Qt
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PyQt6.QtWidgets import QDialog, QFrame, QGraphicsOpacityEffect, QLabel, QPushButton, QVBoxLayout

from ..core.errors import classify_error, friendly_label
from ..downloader import DownloadOptions
from . import fluent as F
from . import style as S
from .dialogs import AboutDialog, FailureDialog, LowConfidenceDialog, SettingsDialog, load_options_kwargs
from .worker import DownloadWorker as GUIDownloadWorker


_UI_FLUSH_INTERVAL_MS = 100
_LOG_FLUSH_INTERVAL_MS = 200
_RESIZE_DEBOUNCE_MS = 50
_SIDEBAR_COLLAPSE_WIDTH = 580
_SIDEBAR_EXPAND_WIDTH = 620


def _ensure_runtime_state(self) -> None:
    if not hasattr(self, "_pending_track_progress"):
        self._pending_track_progress: dict[int, int] = {}
    if not hasattr(self, "_pending_track_status"):
        self._pending_track_status: dict[int, tuple[str, str]] = {}
    if not hasattr(self, "_pending_overall_progress"):
        self._pending_overall_progress: tuple[int, int, str] | None = None
    if not hasattr(self, "_pending_log_messages"):
        self._pending_log_messages: list[tuple[str, str]] = []

    if not hasattr(self, "_ui_flush_timer"):
        self._ui_flush_timer = QTimer(self)
        self._ui_flush_timer.setInterval(_UI_FLUSH_INTERVAL_MS)
        self._ui_flush_timer.timeout.connect(lambda: _flush_pending_ui_updates(self))

    if not hasattr(self, "_log_flush_timer"):
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setInterval(_LOG_FLUSH_INTERVAL_MS)
        self._log_flush_timer.timeout.connect(lambda: _flush_pending_logs(self))

    if not hasattr(self, "_resize_debounce_timer"):
        self._resize_debounce_timer = QTimer(self)
        self._resize_debounce_timer.setSingleShot(True)
        self._resize_debounce_timer.setInterval(_RESIZE_DEBOUNCE_MS)
        self._resize_debounce_timer.timeout.connect(lambda: _apply_responsive_sidebar(self))

    if not hasattr(self, "_sidebar_toggling"):
        self._sidebar_toggling = False
    if not hasattr(self, "_terminal_return_page"):
        self._terminal_return_page = 1


def _flush_pending_ui_updates(self) -> None:
    pending_status = getattr(self, "_pending_track_status", {})
    pending_progress = getattr(self, "_pending_track_progress", {})

    if pending_status:
        for idx, (status, tooltip) in pending_status.items():
            self._track_model.set_row_status(idx, status, tooltip)
        pending_status.clear()

    if pending_progress:
        for idx, percentage in pending_progress.items():
            self._track_model.set_row_progress(idx, percentage)
        pending_progress.clear()

    overall = getattr(self, "_pending_overall_progress", None)
    if overall:
        current, total, title = overall
        self._progress_bar.setRange(0, total if total > 0 else 1)
        self._progress_bar.setValue(current)
        short = title if len(title) <= 36 else title[:35] + "…"
        self._status_lbl.setText(f"{current} / {total}  ·  {short}")
        self._pending_overall_progress = None


def _flush_pending_logs(self) -> None:
    has_activity = hasattr(self, "_log_panel") and self._log_panel is not None
    has_terminal = (
        hasattr(self, "_terminal_log_panel") and self._terminal_log_panel is not None
    )
    if not (has_activity or has_terminal):
        self._pending_log_messages.clear()
        return

    if not self._pending_log_messages:
        return

    for text, level in self._pending_log_messages:
        if has_activity:
            self._log_panel.append(text, level)
        if has_terminal:
            self._terminal_log_panel.append(text, level)
    self._pending_log_messages.clear()


def _create_drag_overlay(self) -> None:
    if hasattr(self, "_drag_overlay") and self._drag_overlay is not None:
        return

    overlay = QFrame(self)
    overlay.setObjectName("dragOverlay")
    overlay.setGeometry(self.rect())
    overlay.setStyleSheet(
        "QFrame#dragOverlay {"
        "background: rgba(32, 32, 32, 110);"
        "border: 2px dashed rgba(255, 255, 255, 170);"
        "border-radius: 12px;"
        "}"
        "QFrame#dragOverlay QLabel {"
        "color: white;"
        "font-size: 22px;"
        "font-weight: 600;"
        "background: transparent;"
        "}"
    )
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    layout = QVBoxLayout(overlay)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel("Drop here", overlay)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    overlay.hide()
    self._drag_overlay = overlay


def _set_drag_overlay_visible(self, visible: bool) -> None:
    _ensure_runtime_state(self)
    _create_drag_overlay(self)
    self._drag_overlay.setGeometry(self.rect())
    self._drag_overlay.setVisible(bool(visible))


def _set_sidebar_collapsed(self, collapsed: bool) -> None:
    _ensure_runtime_state(self)
    if self._sidebar_toggling or self._sidebar_collapsed == collapsed:
        return

    self._sidebar_toggling = True
    try:
        self._sidebar_collapsed = collapsed
        if collapsed:
            self._sidebar_content.hide()
            self._hamburger_btn.show()
            for child in self.centralWidget().findChildren(QFrame):
                if child.objectName() == "sidebar":
                    child.setMinimumWidth(52)
                    child.setMaximumWidth(52)
                    break
        else:
            self._sidebar_content.show()
            self._hamburger_btn.hide()
            for child in self.centralWidget().findChildren(QFrame):
                if child.objectName() == "sidebar":
                    child.setMinimumWidth(250)
                    child.setMaximumWidth(380)
                    break
    finally:
        self._sidebar_toggling = False


def _apply_responsive_sidebar(self) -> None:
    width = self.width()
    if width < _SIDEBAR_COLLAPSE_WIDTH and not self._sidebar_collapsed:
        _set_sidebar_collapsed(self, True)
    elif width > _SIDEBAR_EXPAND_WIDTH and self._sidebar_collapsed:
        _set_sidebar_collapsed(self, False)


def _on_download(self):
    _ensure_runtime_state(self)
    if self._is_downloading or not self._result or not self._selected:
        return

    services = self._enabled_services()
    if not services:
        self.show_toast("Enable at least one service in Settings", "warning")
        return

    suspicious = [
        (i, self._result.tracks[i])
        for i in self._selected
        if getattr(self._result.tracks[i], "match_confidence", 100) < 60
        and getattr(self._result.tracks[i], "match_source", "spotify") == "youtube"
    ]
    if suspicious:
        dlg = LowConfidenceDialog(suspicious, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        with self._selection_batch():
            for skip_idx in dlg.deselected_indices():
                self._selected.discard(skip_idx)
                self._track_model.set_row_checked(skip_idx, False)
        if not self._selected:
            return
        self._update_dl_button()
        self._update_header_count()

    self._set_download_busy(True)

    total = len(self._selected)
    self._progress_bar.setRange(0, total if total > 0 else 1)
    self._progress_bar.setValue(0)

    for i in range(self._track_model.rowCount()):
        self._track_model.set_row_status(
            i,
            "queued" if i in self._selected else "idle",
        )

    quality = self._qual_combo.currentText()
    kwargs = load_options_kwargs(self._settings)
    opts = DownloadOptions(
        output_dir=self._output_dir,
        services=services,
        quality=quality,
        **kwargs,
    )
    indices = sorted(self._selected)

    cd_every = self._settings.value("cooldown_every", 0, type=int)
    cd_secs = self._settings.value("cooldown_seconds", 0, type=int)
    if cd_every == 20 and cd_secs == 30:
        cd_every = 0
        cd_secs = 0

    self._dl_worker = GUIDownloadWorker(
        tracks=self._result.tracks,
        opts=opts,
        collection_name=self._result.collection_name,
        is_playlist=self._result.is_playlist,
        selected_indices=indices,
        max_concurrent=self._settings.value("concurrent_downloads", 2, type=int),
        cooldown_every=cd_every,
        cooldown_seconds=cd_secs,
        parent=self,
    )
    self._dl_worker.track_started.connect(self._on_track_started)
    self._dl_worker.track_done.connect(self._on_track_done)
    self._dl_worker.track_failed.connect(self._on_track_failed)
    self._dl_worker.track_progress.connect(self._on_track_progress)
    self._dl_worker.progress.connect(self._on_progress)
    self._dl_worker.cooldown.connect(self._on_cooldown)
    self._dl_worker.log_message.connect(self._on_log_message)
    self._dl_worker.finished.connect(self._on_dl_done)
    self._dl_worker.error.connect(self._on_dl_error)
    self._dl_worker.start()


def _on_log_message(self, text: str, level: str):
    _ensure_runtime_state(self)
    self._pending_log_messages.append((text, level))

    lvl = (level or "info").lower()
    if lvl == "error":
        logging.error("[ui] %s", text)
    elif lvl == "warning":
        logging.warning("[ui] %s", text)
    elif lvl in {"success", "api", "download", "info"}:
        logging.info("[ui] %s", text)
    else:
        logging.debug("[ui:%s] %s", lvl, text)

    if not self._log_flush_timer.isActive():
        self._log_flush_timer.start()


def _on_stop(self):
    if self._dl_worker is None:
        return
    self._stop_btn.setEnabled(False)
    self._stop_btn.setText("Stopping…")
    self._status_lbl.setText("Stopping after current track…")
    with contextlib.suppress(Exception):
        self._dl_worker.requestInterruption()


def _on_track_started(self, idx: int, _title: str):
    _ensure_runtime_state(self)
    if 0 <= idx < self._track_model.rowCount():
        self._pending_track_status[idx] = ("running", "")
        if not self._ui_flush_timer.isActive():
            self._ui_flush_timer.start()


def _on_track_progress(self, idx: int, percentage: int):
    _ensure_runtime_state(self)
    if 0 <= idx < self._track_model.rowCount():
        self._pending_track_progress[idx] = percentage
        if not self._ui_flush_timer.isActive():
            self._ui_flush_timer.start()


def _on_track_done(self, idx: int, _title: str):
    _ensure_runtime_state(self)
    if 0 <= idx < self._track_model.rowCount():
        self._pending_track_status[idx] = ("done", "")
        if not self._ui_flush_timer.isActive():
            self._ui_flush_timer.start()


def _on_track_failed(self, idx: int, _title: str, err: str):
    _ensure_runtime_state(self)
    if 0 <= idx < self._track_model.rowCount():
        self._pending_track_status[idx] = ("failed", err)
        if not self._ui_flush_timer.isActive():
            self._ui_flush_timer.start()


def _on_failure_clicked(self, index_one_based: int):
    idx = index_one_based - 1
    if not (0 <= idx < self._track_model.rowCount()):
        return
    track = self._track_model.track_at(idx)
    err = self._track_model.row_error(idx)
    title = getattr(track, "title", "Unknown")
    artist = getattr(track, "artists", "") or getattr(track, "artist", "")
    dlg = FailureDialog(title, artist, err, self)
    dlg.exec()


def _on_progress(self, current: int, total: int, title: str):
    _ensure_runtime_state(self)
    self._pending_overall_progress = (current, total, title)
    if not self._ui_flush_timer.isActive():
        self._ui_flush_timer.start()


def _on_cooldown(self, remaining: int, total: int):
    if remaining <= 0:
        self._status_lbl.setText("Resuming…")
    else:
        self._status_lbl.setText(
            f"Cooldown · {remaining}s left  (avoiding rate limits)"
        )


def _on_dl_done(self, succeeded: int, failed: int):
    _ensure_runtime_state(self)
    _flush_pending_ui_updates(self)
    _flush_pending_logs(self)
    self._ui_flush_timer.stop()
    self._log_flush_timer.stop()

    self._dl_worker = None
    self._set_download_busy(False)
    self._update_dl_button()
    msg = f"Done  ·  {succeeded} succeeded"

    if failed:
        from collections import Counter

        kinds = Counter()
        for i in range(self._track_model.rowCount()):
            err = self._track_model.row_error(i)
            if err:
                kinds[classify_error(err)] += 1
        dominant = kinds.most_common(1)[0][0] if kinds else None
        cat_text = (
            f"  (mostly {friendly_label(dominant).lower()})" if dominant else ""
        )
        msg += f"  ·  {failed} failed{cat_text}  ·  click ✗ for details"
    self._status_lbl.setText(msg)


def _on_dl_error(self, msg: str):
    _ensure_runtime_state(self)
    _flush_pending_ui_updates(self)
    _flush_pending_logs(self)
    self._ui_flush_timer.stop()
    self._log_flush_timer.stop()

    self._dl_worker = None
    self._set_download_busy(False)
    self._update_dl_button()
    self._status_lbl.setText("")
    self.show_toast(msg, "error")


def _open_settings(self):
    from .main_window_shared import SERVICES_ALL

    dlg = SettingsDialog(self._settings, SERVICES_ALL, self._output_dir, self)
    dlg.adjustSize()
    fg = dlg.frameGeometry()
    fg.moveCenter(self.geometry().center())
    dlg.move(fg.topLeft())
    if dlg.exec() == QDialog.DialogCode.Accepted:
        self._output_dir = self._settings.value(
            "output_dir", self._output_dir, type=str
        )
        self._apply_activity_visibility(
            self._settings.value("show_activity_log", False, type=bool)
        )


def _open_info(self):
    dlg = AboutDialog(self)
    dlg.exec()


def apply_theme(self, theme: str) -> None:
    S.set_theme(theme)
    F.apply_fluent_theme(theme, S.ACCENT)
    self.setStyleSheet(S.QSS)


def _toggle_sidebar(self) -> None:
    _set_sidebar_collapsed(self, not self._sidebar_collapsed)


def resizeEvent(self, event) -> None:
    super(type(self), self).resizeEvent(event)
    _ensure_runtime_state(self)
    if hasattr(self, "_drag_overlay") and self._drag_overlay is not None:
        self._drag_overlay.setGeometry(self.rect())
    self._resize_debounce_timer.start()


def dragEnterEvent(self, event: QDragEnterEvent) -> None:
    if event.mimeData().hasUrls():
        urls = event.mimeData().urls()
        if urls:
            url_str = urls[0].toString()
            if "spotify.com" in url_str or "youtube.com" in url_str or "youtu.be" in url_str:
                event.acceptProposedAction()
                _set_drag_overlay_visible(self, True)
                return
    event.ignore()


def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
    _set_drag_overlay_visible(self, False)


def dropEvent(self, event: QDropEvent) -> None:
    _set_drag_overlay_visible(self, False)

    urls = event.mimeData().urls()
    if urls:
        url_str = urls[0].toString()
        if url_str.startswith("file:///"):
            url_str = url_str[8:]
        self._url_input.setText(url_str)
        self._on_preview()


def show_toast(self, message: str, level: str = "info", duration: int = 3000) -> None:
    from .components import ToastWidget

    toast = ToastWidget(message, level, duration, self)
    toast.show_toast(self)
    self._toasts.append(toast)
    toast.destroyed.connect(lambda: self._toasts.remove(toast) if toast in self._toasts else None)


def _fade_to_page(self, page_index: int) -> None:
    if page_index == self._current_page_index:
        return

    current_widget = self._stack.widget(self._current_page_index)
    if current_widget:
        opacity_effect = current_widget.graphicsEffect()
        if opacity_effect:
            self._page_fade_out_animation = QPropertyAnimation(opacity_effect, b"opacity", self)
            self._page_fade_out_animation.setDuration(200)
            self._page_fade_out_animation.setStartValue(opacity_effect.opacity())
            self._page_fade_out_animation.setEndValue(0)
            self._page_fade_out_animation.finished.connect(lambda: self._switch_page(page_index))
            self._page_fade_out_animation.start()
        else:
            self._switch_page(page_index)
    else:
        self._switch_page(page_index)


def _switch_page(self, page_index: int) -> None:
    self._stack.setCurrentIndex(page_index)
    self._current_page_index = page_index

    new_widget = self._stack.widget(page_index)
    if new_widget:
        opacity_effect = new_widget.graphicsEffect()
        if opacity_effect:
            self._page_fade_in_animation = QPropertyAnimation(opacity_effect, b"opacity", self)
            self._page_fade_in_animation.setDuration(200)
            self._page_fade_in_animation.setStartValue(0)
            self._page_fade_in_animation.setEndValue(1)
            self._page_fade_in_animation.start()


def _open_terminal_page(self) -> None:
    _ensure_runtime_state(self)
    if self._current_page_index != 2:
        self._terminal_return_page = self._current_page_index
    self._fade_to_page(2)


def _close_terminal_page(self) -> None:
    _ensure_runtime_state(self)
    target = self._terminal_return_page
    if target == 2:
        target = 1 if self._result is not None else 0
    self._fade_to_page(target)


def _clear_terminal_logs(self) -> None:
    _ensure_runtime_state(self)
    self._pending_log_messages.clear()
    if hasattr(self, "_terminal_log_panel") and self._terminal_log_panel is not None:
        self._terminal_log_panel.clear()
    if hasattr(self, "_log_panel") and self._log_panel is not None:
        self._log_panel.clear()


def _enabled_services(self) -> list[str]:
    from .main_window_shared import SERVICES_ALL

    order = (
        self._settings.value("service_order", SERVICES_ALL, type=list)
        or SERVICES_ALL
    )
    order = [s for s in order if s in SERVICES_ALL]
    for s in SERVICES_ALL:
        if s not in order:
            order.append(s)
    enabled = self._settings.value("service_enabled", order, type=list) or order
    return [s for s in order if s in set(enabled)]


def _set_download_busy(self, busy: bool):
    _ensure_runtime_state(self)
    self._set_downloading_state(busy)
    self._dl_btn.setEnabled(not busy)
    self._dl_btn.setText("Downloading…" if busy else "Download")

    if busy:
        self._stop_btn.setVisible(True)
        effect = QGraphicsOpacityEffect(self._stop_btn)
        effect.setOpacity(0.0)
        self._stop_btn.setGraphicsEffect(effect)
        self._stop_fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self._stop_fade_anim.setDuration(180)
        self._stop_fade_anim.setStartValue(0.0)
        self._stop_fade_anim.setEndValue(1.0)
        self._stop_fade_anim.start()
    else:
        self._stop_btn.setVisible(False)
        self._stop_btn.setGraphicsEffect(None)
        self._stop_btn.setEnabled(True)
        self._stop_btn.setText("Stop")

    controls_enabled = not busy
    self._preview_btn.setEnabled(controls_enabled)
    self._url_input.setEnabled(controls_enabled)
    self._search_input.setEnabled(controls_enabled)
    self._deselect_btn.setEnabled(controls_enabled and bool(self._selected))
    self._clear_list_btn.setEnabled(controls_enabled and self._track_model.rowCount() > 0)
    self._invert_btn.setEnabled(controls_enabled)
    self._progress_bar.setVisible(busy)
    if not busy:
        self._pending_track_progress.clear()
        self._pending_track_status.clear()
        self._pending_overall_progress = None


def _apply_activity_visibility(self, visible: bool):
    if hasattr(self, "_activity_wrap") and self._activity_wrap:
        self._activity_wrap.setVisible(bool(visible))


def _set_button_icon(button: QPushButton, icon_name: str) -> None:
    try:
        import qtawesome as qta
        from .. import style as _S
        icon = qta.icon(icon_name, color=_S.TEXT_DIM)
        button.setIcon(icon)
    except Exception:
        pass


def _short_path(path: str, max_len: int = 36) -> str:
    home = os.path.expanduser("~")
    p = path.replace(home, "~")
    if len(p) > max_len:
        p = "…" + p[-(max_len - 1) :]
    return p


def _restore_geometry(self):
    geo = self._settings.value("window_geometry")
    restored = False
    if geo:
        try:
            restored = bool(self.restoreGeometry(geo))
        except Exception:
            restored = False
    if not restored:
        self.resize(820, 700)
    self.setWindowState(Qt.WindowState.WindowNoState)


def closeEvent(self, ev):
    self._settings.setValue("window_geometry", self.saveGeometry())
    for w in (self._resolve_worker, self._dl_worker):
        try:
            if w is not None and w.isRunning():
                w.requestInterruption()
                w.quit()
                if not w.wait(3000):
                    logging.warning("Worker did not stop cleanly within timeout")
        except Exception:
            pass
    super(type(self), self).closeEvent(ev)

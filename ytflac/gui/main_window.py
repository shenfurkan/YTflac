from __future__ import annotations
import os
from PyQt6.QtCore import Qt, QTimer, QSettings, QSortFilterProxyModel
from PyQt6.QtGui import QIcon, QDragEnterEvent, QDropEvent, QDragLeaveEvent
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QPushButton, QFrame
from ..core.history import HistoryManager
from ..providers.spotify_metadata import SpotifyMetadataClient
from .worker import ResolveWorker, DownloadWorker as GUIDownloadWorker
from .components import PlaylistHeader, UnmatchedPanel, ToastWidget
from .main_window_shared import _resource_path
from .delegates import TrackItemDelegate
from .models import TrackListModel, TrackListRoles
from .viewmodels import MainViewModel
from . import main_window_ui as MWUI
from . import main_window_logic as MWLOG
from . import main_window_runtime as MWR




class SpotiflacApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YtFLAC")
        self.setMinimumSize(720, 620)

        # App icon
        icon_path = _resource_path("images", "APPLOGO.ico")
        if not os.path.exists(icon_path):
            icon_path = _resource_path("images", "APPLOGO.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._settings = QSettings("YtFLAC", "Desktop")

        self._spotify = SpotifyMetadataClient()
        self._resolve_worker: ResolveWorker | None = None
        self._dl_worker: GUIDownloadWorker | None = None
        self._vm = MainViewModel(self)
        self._result = self._vm.result
        self._track_model = TrackListModel(self)
        self._track_proxy = QSortFilterProxyModel(self)
        self._track_proxy.setSourceModel(self._track_model)
        self._track_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._track_proxy.setFilterRole(TrackListRoles.SearchBlobRole)
        self._track_delegate = TrackItemDelegate(self)
        self._selected: set[int] = self._vm.selected_indices
        self._header: PlaylistHeader | None = None
        self._unmatched_panel: UnmatchedPanel | None = None
        self._is_downloading = self._vm.is_downloading
        self._last_url: str = ""
        self._history = HistoryManager()
        self._toasts: list[ToastWidget] = []
        self._current_page_index = 0

        self._vm.selectionChanged.connect(self._on_vm_selection_changed)
        self._vm.downloadStateChanged.connect(self._on_vm_download_state_changed)
        self._vm.resultChanged.connect(self._on_vm_result_changed)
        self._vm.filterChanged.connect(self._on_vm_filter_changed)

        self._track_delegate.failureClicked.connect(
            lambda row: self._on_failure_clicked(row + 1)
        )

        # Debounced search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search_filter)

        self._output_dir = self._settings.value(
            "output_dir", os.path.expanduser("~/Music/YtFLAC"), type=str
        )

        self._build_ui()
        self.setProperty("dragActive", False)
        self._restore_geometry()
        
        # Enable drag-drop for URLs
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        return MWUI._build_ui(self)

    # ------------------------------------------------------------------
    # Sidebar — left column
    # ------------------------------------------------------------------

    def _build_sidebar(self) -> QFrame:
        return MWUI._build_sidebar(self)

    def _on_format_changed(self, fmt: str):
        return MWUI._on_format_changed(self, fmt)

    # ------------------------------------------------------------------
    # Right column — preview / results
    # ------------------------------------------------------------------

    def _build_right_column(self) -> QVBoxLayout:
        return MWUI._build_right_column(self)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _on_preview(self):
        return MWLOG._on_preview(self)

    def _on_resolve_done(self, result):
        return MWLOG._on_resolve_done(self, result)

    def _deselect_all(self):
        return MWLOG._deselect_all(self)

    def _on_refresh(self):
        return MWLOG._on_refresh(self)

    def _on_manual_match(self, unmatched_idx: int, spotify_url: str):
        return MWLOG._on_manual_match(self, unmatched_idx, spotify_url)

    def _invert_selection(self):
        return MWLOG._invert_selection(self)

    def _on_resolve_error(self, msg: str):
        return MWLOG._on_resolve_error(self, msg)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_row_toggled(self, index_one_based: int, checked: bool):
        return MWLOG._on_row_toggled(self, index_one_based, checked)

    def _toggle_all(self):
        return MWLOG._toggle_all(self)

    def _update_select_btn(self):
        return MWLOG._update_select_btn(self)

    def _update_dl_button(self):
        return MWLOG._update_dl_button(self)

    def _update_header_count(self):
        return MWLOG._update_header_count(self)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self, _text: str):
        return MWLOG._on_search_changed(self, _text)

    def _apply_search_filter(self):
        return MWLOG._apply_search_filter(self)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _on_download(self):
        return MWR._on_download(self)

    def _on_log_message(self, text: str, level: str):
        return MWR._on_log_message(self, text, level)

    def _on_stop(self):
        return MWR._on_stop(self)

    def _on_track_started(self, idx: int, _title: str):
        return MWR._on_track_started(self, idx, _title)

    def _on_track_progress(self, idx: int, percentage: int):
        return MWR._on_track_progress(self, idx, percentage)

    def _on_track_done(self, idx: int, _title: str):
        return MWR._on_track_done(self, idx, _title)

    def _on_track_failed(self, idx: int, _title: str, err: str):
        return MWR._on_track_failed(self, idx, _title, err)

    def _on_failure_clicked(self, index_one_based: int):
        return MWR._on_failure_clicked(self, index_one_based)

    def _on_progress(self, current: int, total: int, title: str):
        return MWR._on_progress(self, current, total, title)

    def _on_cooldown(self, remaining: int, total: int):
        return MWR._on_cooldown(self, remaining, total)

    def _on_dl_done(self, succeeded: int, failed: int):
        return MWR._on_dl_done(self, succeeded, failed)

    def _on_dl_error(self, msg: str):
        return MWR._on_dl_error(self, msg)

    # ------------------------------------------------------------------
    # Folder / settings
    # ------------------------------------------------------------------

    def _open_settings(self):
        return MWR._open_settings(self)

    def _open_info(self):
        return MWR._open_info(self)

    def apply_theme(self, theme: str) -> None:
        return MWR.apply_theme(self, theme)

    # ------------------------------------------------------------------
    # Responsive sidebar
    # ------------------------------------------------------------------

    def _toggle_sidebar(self) -> None:
        return MWR._toggle_sidebar(self)

    def resizeEvent(self, event) -> None:
        return MWR.resizeEvent(self, event)

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        return MWR.dragEnterEvent(self, event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        return MWR.dragLeaveEvent(self, event)

    def dropEvent(self, event: QDropEvent) -> None:
        return MWR.dropEvent(self, event)

    def show_toast(self, message: str, level: str = "info", duration: int = 3000) -> None:
        return MWR.show_toast(self, message, level, duration)

    def _fade_to_page(self, page_index: int) -> None:
        return MWR._fade_to_page(self, page_index)

    def _switch_page(self, page_index: int) -> None:
        return MWR._switch_page(self, page_index)

    def _open_terminal_page(self) -> None:
        return MWR._open_terminal_page(self)

    def _close_terminal_page(self) -> None:
        return MWR._close_terminal_page(self)

    def _clear_terminal_logs(self) -> None:
        return MWR._clear_terminal_logs(self)

    def _enabled_services(self) -> list[str]:
        return MWR._enabled_services(self)

    def _selection_batch(self):
        return self._vm.selection_batch()

    def _set_selected_indices(self, indices: set[int] | list[int]) -> None:
        self._vm.set_selected_indices(indices)

    def _set_downloading_state(self, busy: bool) -> None:
        self._vm.set_is_downloading(busy)

    def _set_result(self, result) -> None:
        self._vm.set_result(result)

    def _set_filter_text(self, text: str) -> None:
        self._vm.set_filter_text(text)

    def _model_index_to_source_row(self, model_index) -> int:
        if not model_index.isValid():
            return -1
        if model_index.model() is self._track_proxy:
            src = self._track_proxy.mapToSource(model_index)
            return src.row() if src.isValid() else -1
        return model_index.row()

    def _on_track_item_clicked(self, model_index) -> None:
        row = self._model_index_to_source_row(model_index)
        if row < 0:
            return
        with self._selection_batch():
            checked = self._track_model.is_row_checked(row)
            if checked:
                self._selected.add(row)
            else:
                self._selected.discard(row)

    def _visible_source_rows(self) -> list[int]:
        rows: list[int] = []
        for proxy_row in range(self._track_proxy.rowCount()):
            proxy_idx = self._track_proxy.index(proxy_row, 0)
            src_idx = self._track_proxy.mapToSource(proxy_idx)
            if src_idx.isValid():
                rows.append(src_idx.row())
        return rows

    def _on_vm_result_changed(self, result) -> None:
        self._result = result

    def _on_vm_filter_changed(self, text: str) -> None:
        self._track_proxy.setFilterFixedString(text)
        self._update_select_btn()

    def _on_vm_selection_changed(self, _count: int) -> None:
        self._selected = self._vm.selected_indices
        self._update_dl_button()
        self._update_select_btn()
        self._update_header_count()

    def _on_vm_download_state_changed(self, busy: bool) -> None:
        self._is_downloading = busy
        if not busy:
            self._update_dl_button()
        self._update_select_btn()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_results(self):
        return MWLOG._clear_results(self)

    def _set_preview_busy(self, busy: bool):
        return MWLOG._set_preview_busy(self, busy)

    def _set_download_busy(self, busy: bool):
        return MWR._set_download_busy(self, busy)

    def _apply_activity_visibility(self, visible: bool):
        return MWR._apply_activity_visibility(self, visible)

    @staticmethod
    def _set_button_icon(button: QPushButton, icon_name: str) -> None:
        return MWR._set_button_icon(button, icon_name)

    @staticmethod
    def _short_path(path: str, max_len: int = 36) -> str:
        return MWR._short_path(path, max_len)

    # --- geometry persistence ---

    def _restore_geometry(self):
        return MWR._restore_geometry(self)

    def closeEvent(self, ev):
        return MWR.closeEvent(self, ev)

"""
YtFLAC Desktop — minimalist PyQt6 GUI.
"""
from __future__ import annotations
import os
import sys
import traceback
from datetime import datetime

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QFileDialog,
    QStackedWidget, QMessageBox, QSizePolicy, QComboBox, QDialog,
)

from ..providers.spotify_metadata import SpotifyMetadataClient
from ..downloader import DownloadOptions
from .worker import ResolveWorker, DownloadWorker as GUIDownloadWorker
from .widgets import (
    TrackRow, PlaylistHeader,
    STATUS_IDLE, STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED,
)
from .settings_dialog import SettingsDialog, load_options_kwargs
from . import style as S


SERVICES_ALL = ["tidal", "qobuz", "amazon", "deezer"]


def _resource_path(*parts: str) -> str:
    """Resolve a bundled resource path for both dev and PyInstaller onefile."""
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base, *parts)


def _log_crash(exc_type, exc_value, exc_tb):
    try:
        log_path = os.path.join(os.getcwd(), "ytflac_crash.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"[{datetime.now().isoformat()}] Unhandled exception\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass


class SpotiflacApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YtFLAC")
        self.setMinimumSize(480, 560)

        # App icon
        icon_path = _resource_path("images", "ytflaclogo.ico")
        if not os.path.exists(icon_path):
            icon_path = _resource_path("images", "ytflaclogo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._settings = QSettings("YtFLAC", "Desktop")

        self._spotify = SpotifyMetadataClient()
        self._resolve_worker: ResolveWorker | None = None
        self._dl_worker: GUIDownloadWorker | None = None
        self._result = None
        self._rows: list[TrackRow] = []
        self._selected: set[int] = set()

        self._output_dir = self._settings.value(
            "output_dir", os.path.expanduser("~/Music/YtFLAC"), type=str
        )

        self._build_ui()
        self._restore_geometry()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        # ============ HEADER STRIP ============
        # Logo
        logo_path = _resource_path("images", "ytflaclogo.png")
        logo_lbl = QLabel()
        if os.path.exists(logo_path):
            px = QPixmap(logo_path).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(px)
        logo_lbl.setFixedSize(36, 36)

        title = QLabel("YtFLAC")
        title.setObjectName("h1")
        sub = QLabel("Spotify · YouTube Music  →  FLAC / MP3")
        sub.setObjectName("muted")

        head_text = QVBoxLayout()
        head_text.setSpacing(0)
        head_text.addWidget(title)
        head_text.addWidget(sub)

        self._settings_btn = QPushButton("⚙  Settings")
        self._settings_btn.setObjectName("ghost")
        self._settings_btn.clicked.connect(self._open_settings)

        head = QHBoxLayout()
        head.addWidget(logo_lbl)
        head.addLayout(head_text, stretch=1)
        head.addWidget(self._settings_btn, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(head)

        # ============ TWO COLUMNS ============
        body = QHBoxLayout()
        body.setSpacing(18)
        outer.addLayout(body, stretch=1)

        body.addLayout(self._build_left_column(),  stretch=0)
        body.addLayout(self._build_right_column(), stretch=1)

    # ------------------------------------------------------------------
    # Left column — controls
    # ------------------------------------------------------------------

    def _build_left_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(14)
        col.setContentsMargins(0, 0, 0, 0)

        # Fixed width container for the whole left side
        # achieved via a wrapper widget
        # (we set the wrapper's max width)
        # Simpler: set max widths on individual widgets — done below.

        # --- URL ---
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Spotify or YouTube Music URL")
        self._url_input.returnPressed.connect(self._on_preview)
        self._url_input.setMinimumWidth(280)
        self._url_input.setMaximumWidth(360)

        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setFixedWidth(86)
        self._preview_btn.clicked.connect(self._on_preview)

        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        url_row.addWidget(self._url_input, stretch=1)
        url_row.addWidget(self._preview_btn)
        col.addLayout(url_row)

        # --- Format / Quality ---
        fmt_lbl = QLabel("Format")
        fmt_lbl.setObjectName("section")
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["FLAC", "MP3"])
        saved_fmt = self._settings.value("format", "FLAC", type=str)
        self._fmt_combo.setCurrentText(saved_fmt)
        self._fmt_combo.currentTextChanged.connect(
            lambda v: self._settings.setValue("format", v)
        )

        qual_lbl = QLabel("Quality")
        qual_lbl.setObjectName("section")
        self._qual_combo = QComboBox()
        self._qual_combo.addItems(["LOSSLESS", "HI_RES", "HIGH", "NORMAL"])
        saved_qual = self._settings.value("quality", "LOSSLESS", type=str)
        self._qual_combo.setCurrentText(saved_qual)
        self._qual_combo.currentTextChanged.connect(
            lambda v: self._settings.setValue("quality", v)
        )

        fq_grid = QHBoxLayout()
        fq_grid.setSpacing(8)
        fmt_box = QVBoxLayout(); fmt_box.setSpacing(4)
        fmt_box.addWidget(fmt_lbl); fmt_box.addWidget(self._fmt_combo)
        qual_box = QVBoxLayout(); qual_box.setSpacing(4)
        qual_box.addWidget(qual_lbl); qual_box.addWidget(self._qual_combo)
        fq_grid.addLayout(fmt_box, stretch=1)
        fq_grid.addLayout(qual_box, stretch=1)
        col.addLayout(fq_grid)

        col.addStretch(1)

        # --- Status + actions (bottom) ---
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("muted")
        self._status_lbl.setWordWrap(True)
        col.addWidget(self._status_lbl)

        self._dl_btn = QPushButton("Download")
        self._dl_btn.setObjectName("primary")
        self._dl_btn.setFixedHeight(42)
        self._dl_btn.setEnabled(False)
        self._dl_btn.clicked.connect(self._on_download)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addWidget(self._dl_btn, stretch=1)
        col.addLayout(action_row)

        # Lock left column width
        for w in (self._url_input,):
            pass  # handled above
        return col

    # ------------------------------------------------------------------
    # Right column — preview / results
    # ------------------------------------------------------------------

    def _build_right_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)
        col.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()

        # Page 0 — empty
        empty = QLabel("Paste a URL and click Preview.")
        empty.setObjectName("faint")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(empty)

        # Page 1 — results
        results_page = QWidget()
        rl = QVBoxLayout(results_page)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self._header_box = QVBoxLayout()
        self._header_box.setContentsMargins(0, 0, 0, 0)
        rl.addLayout(self._header_box)

        # Select-all toggle row
        self._select_btn = QPushButton("Clear All")
        self._select_btn.setObjectName("ghost")
        self._select_btn.clicked.connect(self._toggle_all)
        sel_row = QHBoxLayout()
        sel_row.addStretch()
        sel_row.addWidget(self._select_btn)
        rl.addLayout(sel_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._track_container = QWidget()
        self._track_layout = QVBoxLayout(self._track_container)
        self._track_layout.setSpacing(0)
        self._track_layout.setContentsMargins(0, 0, 0, 0)
        self._track_layout.addStretch()
        scroll.setWidget(self._track_container)
        rl.addWidget(scroll, stretch=1)

        self._stack.addWidget(results_page)
        col.addWidget(self._stack, stretch=1)

        return col

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _on_preview(self):
        url = self._url_input.text().strip()
        if not url:
            return
        self._preview_btn.setEnabled(False)
        self._preview_btn.setText("Loading…")
        self._dl_btn.setEnabled(False)
        self._clear_results()
        self._status_lbl.setText("")

        self._resolve_worker = ResolveWorker(url, self._spotify, self)
        self._resolve_worker.finished.connect(self._on_resolve_done)
        self._resolve_worker.error.connect(self._on_resolve_error)
        self._resolve_worker.start()

    def _on_resolve_done(self, result):
        self._result = result
        self._preview_btn.setEnabled(True)
        self._preview_btn.setText("Preview")

        # header
        header = PlaylistHeader(
            name      = result.collection_name or "—",
            cover     = result.tracks[0].cover_url if result.tracks else "",
            count     = len(result.tracks),
            unmatched = len(result.unmatched_samples),
        )
        self._header_box.addWidget(header)

        # rows
        for i, track in enumerate(result.tracks):
            row = TrackRow(i + 1, track, self._track_container)
            row.toggled.connect(self._on_row_toggled)
            self._track_layout.insertWidget(self._track_layout.count() - 1, row)
            self._rows.append(row)
            self._selected.add(i)

        self._stack.setCurrentIndex(1)
        self._update_dl_button()
        self._update_select_btn()

    def _on_resolve_error(self, msg: str):
        self._preview_btn.setEnabled(True)
        self._preview_btn.setText("Preview")
        QMessageBox.critical(self, "Error", f"Failed to resolve URL:\n{msg}")

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_row_toggled(self, index_one_based: int, checked: bool):
        idx = index_one_based - 1
        if checked:
            self._selected.add(idx)
        else:
            self._selected.discard(idx)
        self._update_dl_button()
        self._update_select_btn()

    def _toggle_all(self):
        all_checked = len(self._selected) == len(self._rows)
        target = not all_checked
        for row in self._rows:
            row.set_checked(target)
        if target:
            self._selected = set(range(len(self._rows)))
        else:
            self._selected.clear()
        self._update_dl_button()
        self._update_select_btn()

    def _update_select_btn(self):
        if not self._rows:
            return
        all_on = len(self._selected) == len(self._rows)
        self._select_btn.setText("Clear All" if all_on else "Select All")

    def _update_dl_button(self):
        n = len(self._selected)
        self._dl_btn.setText(f"Download ({n})" if n else "Download")
        self._dl_btn.setEnabled(n > 0 and self._result is not None)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _on_download(self):
        if not self._result or not self._selected:
            return

        services = self._enabled_services()
        if not services:
            QMessageBox.warning(self, "No service selected",
                                "Enable at least one service in Settings.")
            return

        self._dl_btn.setEnabled(False)
        self._dl_btn.setText("Downloading…")
        self._preview_btn.setEnabled(False)
        self._url_input.setEnabled(False)

        # mark selected as queued, others idle
        for i, row in enumerate(self._rows):
            row.set_status(STATUS_QUEUED if i in self._selected else STATUS_IDLE)

        quality = self._qual_combo.currentText()
        kwargs  = load_options_kwargs(self._settings)
        opts = DownloadOptions(
            output_dir = self._output_dir,
            services   = services,
            quality    = quality,
            **kwargs,
        )
        indices = sorted(self._selected)

        cd_every = self._settings.value("cooldown_every", 20, type=int)
        cd_secs  = self._settings.value("cooldown_seconds", 30, type=int)

        self._dl_worker = GUIDownloadWorker(
            tracks           = self._result.tracks,
            opts             = opts,
            collection_name  = self._result.collection_name,
            is_playlist      = self._result.is_playlist,
            selected_indices = indices,
            cooldown_every   = cd_every,
            cooldown_seconds = cd_secs,
            parent           = self,
        )
        self._dl_worker.track_started.connect(self._on_track_started)
        self._dl_worker.track_done.connect(self._on_track_done)
        self._dl_worker.track_failed.connect(self._on_track_failed)
        self._dl_worker.progress.connect(self._on_progress)
        self._dl_worker.cooldown.connect(self._on_cooldown)
        self._dl_worker.finished.connect(self._on_dl_done)
        self._dl_worker.error.connect(self._on_dl_error)
        self._dl_worker.start()

    def _on_track_started(self, idx: int, _title: str):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status(STATUS_RUNNING)

    def _on_track_done(self, idx: int, _title: str):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status(STATUS_DONE)

    def _on_track_failed(self, idx: int, _title: str, err: str):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status(STATUS_FAILED, tooltip=err)

    def _on_progress(self, current: int, total: int, _title: str):
        self._status_lbl.setText(f"{current} / {total}")

    def _on_cooldown(self, remaining: int, total: int):
        if remaining <= 0:
            self._status_lbl.setText("Resuming…")
        else:
            self._status_lbl.setText(
                f"Cooldown · {remaining}s left  (avoiding rate limits)"
            )

    def _on_dl_done(self, succeeded: int, failed: int):
        self._dl_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)
        self._url_input.setEnabled(True)
        self._update_dl_button()
        msg = f"Done  ·  {succeeded} succeeded"
        if failed:
            msg += f"  ·  {failed} failed"
        self._status_lbl.setText(msg)

    def _on_dl_error(self, msg: str):
        self._dl_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)
        self._url_input.setEnabled(True)
        self._update_dl_button()
        self._status_lbl.setText("")
        QMessageBox.critical(self, "Download Error", msg)

    # ------------------------------------------------------------------
    # Folder / settings
    # ------------------------------------------------------------------

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, SERVICES_ALL, self._output_dir, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._output_dir = self._settings.value("output_dir", self._output_dir, type=str)

    def _enabled_services(self) -> list[str]:
        order = self._settings.value("service_order", SERVICES_ALL, type=list) or SERVICES_ALL
        order = [s for s in order if s in SERVICES_ALL]
        for s in SERVICES_ALL:
            if s not in order:
                order.append(s)
        enabled = self._settings.value("service_enabled", order, type=list) or order
        return [s for s in order if s in set(enabled)]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear_results(self):
        # header
        while self._header_box.count():
            it = self._header_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        # rows
        while self._track_layout.count() > 1:
            it = self._track_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rows.clear()
        self._selected.clear()
        self._result = None
        self._stack.setCurrentIndex(0)
        self._update_dl_button()

    @staticmethod
    def _short_path(path: str, max_len: int = 36) -> str:
        home = os.path.expanduser("~")
        p = path.replace(home, "~")
        if len(p) > max_len:
            p = "…" + p[-(max_len - 1):]
        return p

    # --- geometry persistence ---

    def _restore_geometry(self):
        geo = self._settings.value("window_geometry")
        restored = False
        if geo:
            try:
                restored = bool(self.restoreGeometry(geo))
            except Exception:
                restored = False
        if not restored:
            self.resize(560, 660)
        self.setWindowState(Qt.WindowState.WindowNoState)

    def closeEvent(self, ev):
        self._settings.setValue("window_geometry", self.saveGeometry())
        # Wait for any running worker threads so the process doesn't get killed mid-IO
        for w in (self._resolve_worker, self._dl_worker):
            try:
                if w is not None and w.isRunning():
                    w.requestInterruption()
                    w.quit()
                    w.wait(3000)
            except Exception:
                pass
        super().closeEvent(ev)


# ---------------------------------------------------------------------------

def run():
    # Windows taskbar icon fix
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("YtFLAC")

    sys.excepthook = _log_crash

    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(S.QSS)

        icon_path = _resource_path("images", "ytflaclogo.ico")
        if not os.path.exists(icon_path):
            icon_path = _resource_path("images", "ytflaclogo.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        win = SpotiflacApp()
        win.show()
        win.showNormal()
        win.raise_()
        win.activateWindow()
        sys.exit(app.exec())
    except Exception:
        _log_crash(*sys.exc_info())
        raise

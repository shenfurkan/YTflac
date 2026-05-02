"""
YtFLAC Desktop — minimalist PyQt6 GUI.
"""
from __future__ import annotations
import os
import sys
import traceback
import logging
from datetime import datetime

from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QStackedWidget, QMessageBox, QComboBox, QDialog,
    QProgressBar, QFrame, QTextEdit,
)

from ..providers.spotify_metadata import SpotifyMetadataClient
from ..downloader import DownloadOptions
from ..core.errors import classify_error, friendly_label, friendly_explanation
from .worker import ResolveWorker, DownloadWorker as GUIDownloadWorker
from .widgets import (
    TrackRow, PlaylistHeader,
    STATUS_IDLE, STATUS_QUEUED, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED,
)
from .settings_dialog import SettingsDialog, load_options_kwargs
from . import style as S


SERVICES_ALL = ["tidal", "qobuz", "amazon", "deezer"]


# ---------------------------------------------------------------------------
# Live log panel — read-only, colour-coded, auto-scrolling
# ---------------------------------------------------------------------------

class LogPanel(QTextEdit):
    """Read-only, colour-coded, auto-scrolling log with a 500-line ceiling."""

    _MAX_LINES = 500

    _COLOURS = {
        "info":     S.LOG_INFO,
        "success":  S.LOG_SUCCESS,
        "error":    S.LOG_ERROR,
        "warning":  S.LOG_WARNING,
        "api":      S.LOG_API,
        "download": S.LOG_DOWNLOAD,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("logPanel")
        self.setReadOnly(True)
        self.setMinimumHeight(140)
        self.setMaximumHeight(260)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

    def append(self, text: str, level: str = "info") -> None:
        colour = self._COLOURS.get(level, S.LOG_INFO)
        ts = datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:{colour}">[{ts}] {text}</span>'
        super().append(html)
        # Trim oldest lines if ceiling exceeded
        doc = self.document()
        if doc.blockCount() > self._MAX_LINES:
            cursor = QTextCursor(doc.firstBlock())
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        # Auto-scroll
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        super().clear()


# ---------------------------------------------------------------------------
# Failure dialog — shown when user clicks a failed track row
# ---------------------------------------------------------------------------

class FailureDialog(QDialog):
    """Detailed per-track failure breakdown with copy + open-log actions."""

    def __init__(self, track_title: str, track_artist: str, raw_error: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Failed")
        self.setMinimumSize(560, 420)
        self._raw_error = raw_error

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 14)

        # Track header
        title_lbl = QLabel(f"<b>{track_title}</b>")
        title_lbl.setStyleSheet("font-size: 14px;")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel(track_artist)
        sub_lbl.setObjectName("muted")
        layout.addWidget(sub_lbl)

        # Per-provider parsed table
        per_provider = self._parse_provider_errors(raw_error)
        if per_provider:
            providers_lbl = QLabel("Providers tried:")
            providers_lbl.setObjectName("section")
            layout.addWidget(providers_lbl)

            for prov, kind, detail in per_provider:
                badge_text = friendly_label(kind)
                explanation = friendly_explanation(kind)

                row = QFrame()
                row.setStyleSheet(
                    f"background: {S.BG_ELEV}; border-radius: 8px; "
                    f"border: 1px solid {S.LINE};"
                )
                rl = QVBoxLayout(row)
                rl.setContentsMargins(12, 10, 12, 10)
                rl.setSpacing(4)

                head = QHBoxLayout()
                head.setSpacing(8)
                prov_lbl = QLabel(f"<b>{prov}</b>")
                prov_lbl.setStyleSheet("font-size: 13px;")
                head.addWidget(prov_lbl)
                head.addStretch()
                kind_badge = QLabel(badge_text)
                kind_badge.setObjectName("badge_warn")
                head.addWidget(kind_badge)
                rl.addLayout(head)

                expl_lbl = QLabel(explanation)
                expl_lbl.setObjectName("muted")
                expl_lbl.setWordWrap(True)
                rl.addWidget(expl_lbl)

                detail_lbl = QLabel(detail)
                detail_lbl.setObjectName("faint")
                detail_lbl.setWordWrap(True)
                detail_lbl.setStyleSheet(f"color: {S.TEXT_DIM}; font-size: 11px;")
                detail_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                rl.addWidget(detail_lbl)

                layout.addWidget(row)
        else:
            # Fallback: just show the raw error
            raw_view = QTextEdit()
            raw_view.setReadOnly(True)
            raw_view.setPlainText(raw_error)
            raw_view.setMinimumHeight(150)
            layout.addWidget(raw_view)

        layout.addStretch(1)

        # Action row
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        copy_btn = QPushButton("Copy details")
        copy_btn.setObjectName("ghost")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        btn_box.addWidget(copy_btn)

        open_log_btn = QPushButton("Open failure log")
        open_log_btn.setObjectName("ghost")
        open_log_btn.clicked.connect(self._open_log)
        btn_box.addWidget(open_log_btn)

        btn_box.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)

        layout.addLayout(btn_box)

    @staticmethod
    def _parse_provider_errors(raw: str) -> list[tuple[str, "ErrorKind", str]]:
        """Parse 'All providers failed — tidal [KIND]: msg || qobuz [KIND]: msg' format."""
        if not raw:
            return []
        # Strip leading prefix (handles both em-dash and -- variants)
        body = raw
        for marker in ("All providers failed —", "All providers failed --", "All providers failed -"):
            if marker in body:
                body = body.split(marker, 1)[1].strip()
                break

        out: list[tuple[str, "ErrorKind", str]] = []
        # Split by '||' (new format) or fall back to '; '
        parts = body.split(" || ") if " || " in body else body.split("; ")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Format: "provider [KIND]: detail"  (preferred)
            #     or: "provider: detail"        (legacy)
            if ":" not in part:
                continue
            head, _, detail = part.partition(":")
            head = head.strip()
            detail = detail.strip()
            kind_name = ""
            prov = head
            if "[" in head and head.endswith("]"):
                prov, kind_part = head.split("[", 1)
                kind_name = kind_part.rstrip("]").strip()
                prov = prov.strip()
            kind = classify_error(f"{kind_name} {detail}".strip())
            out.append((prov, kind, detail))
        return out

    def _copy_to_clipboard(self):
        QApplication.clipboard().setText(self._raw_error)

    def _open_log(self):
        log_path = os.path.join(os.getcwd(), "ytflac_failures.log")
        if not os.path.exists(log_path):
            QMessageBox.information(
                self, "No log yet",
                f"The failure log will be created here on the next failure:\n{log_path}"
            )
            return
        # Open with system default
        try:
            if sys.platform == "win32":
                os.startfile(log_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", log_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", log_path])
        except Exception as exc:
            QMessageBox.warning(self, "Cannot open", f"Failed to open log: {exc}")


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


def _setup_debug_logging():
    """Setup detailed debug logging on startup."""
    debug_log_path = os.path.join(os.getcwd(), "ytflac_debug.log")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # File handler for debug log
    file_handler = logging.FileHandler(debug_log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler for errors only
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup info
    logging.info("=" * 60)
    logging.info("YtFLAC GUI Starting")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Working directory: {os.getcwd()}")
    logging.info(f"Debug log: {debug_log_path}")
    logging.info("=" * 60)
    
    # Log debug module status
    try:
        from ..core.progress import DownloadManager
        dm = DownloadManager()
        logging.info("✓ DownloadManager initialized")
    except Exception as e:
        logging.warning(f"✗ DownloadManager failed: {e}")
    
    try:
        from ..core.provider_stats import ProviderScorer
        ps = ProviderScorer()
        logging.info("✓ ProviderScorer initialized")
    except Exception as e:
        logging.warning(f"✗ ProviderScorer failed: {e}")
    
    try:
        from ..core.history import HistoryManager
        hm = HistoryManager()
        stats = hm.get_stats()
        logging.info(f"✓ HistoryManager initialized (total downloads: {stats.get('total', 0)})")
    except Exception as e:
        logging.warning(f"✗ HistoryManager failed: {e}")
    
    try:
        logging.info("✓ ISRC cache functions loaded")
    except Exception as e:
        logging.warning(f"✗ ISRC cache failed: {e}")


class SpotiflacApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YtFLAC")
        self.setMinimumSize(720, 620)

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
        self._header: PlaylistHeader | None = None
        self._is_downloading = False

        # Debounced search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_search_filter)

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

        # --- URL ---
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("Spotify or YouTube Music URL")
        self._url_input.returnPressed.connect(self._on_preview)
        self._url_input.setMinimumWidth(260)
        self._url_input.setMaximumWidth(360)

        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setMinimumWidth(92)
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
        self._fmt_combo.currentTextChanged.connect(self._on_format_changed)

        qual_lbl = QLabel("Quality")
        qual_lbl.setObjectName("section")
        self._qual_combo = QComboBox()
        self._qual_combo.addItems(["LOSSLESS", "HI_RES", "HIGH", "NORMAL"])
        self._qual_combo.setItemData(0, "16-bit / 44.1 kHz FLAC", Qt.ItemDataRole.ToolTipRole)
        self._qual_combo.setItemData(1, "24-bit / up to 192 kHz", Qt.ItemDataRole.ToolTipRole)
        self._qual_combo.setItemData(2, "320 kbps lossy",          Qt.ItemDataRole.ToolTipRole)
        self._qual_combo.setItemData(3, "128 kbps lossy",          Qt.ItemDataRole.ToolTipRole)
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

        # Apply initial smart-disable for quality combo
        self._on_format_changed(saved_fmt)

        col.addStretch(1)

        # --- Progress bar (hidden until download starts) ---
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setVisible(False)
        col.addWidget(self._progress_bar)

        # --- Live log panel ---
        log_header = QHBoxLayout()
        log_lbl = QLabel("Activity")
        log_lbl.setObjectName("section")
        log_header.addWidget(log_lbl)
        log_header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("ghost")
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        log_header.addWidget(clear_btn)
        col.addLayout(log_header)

        self._log_panel = LogPanel()
        clear_btn.clicked.connect(self._log_panel.clear)
        col.addWidget(self._log_panel, stretch=1)

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

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setFixedHeight(42)
        self._stop_btn.setFixedWidth(80)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._on_stop)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addWidget(self._dl_btn, stretch=1)
        action_row.addWidget(self._stop_btn)
        col.addLayout(action_row)

        return col

    def _on_format_changed(self, fmt: str):
        self._settings.setValue("format", fmt)
        is_flac = (fmt or "").upper() == "FLAC"
        # Quality combo only meaningful for FLAC providers
        self._qual_combo.setEnabled(is_flac)
        if not is_flac:
            self._qual_combo.setToolTip("Quality is fixed for MP3 (320 kbps)")
        else:
            self._qual_combo.setToolTip("")

    # ------------------------------------------------------------------
    # Right column — preview / results
    # ------------------------------------------------------------------

    def _build_right_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)
        col.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()

        # Page 0 — empty / illustrated state
        empty_page = QWidget()
        ev = QVBoxLayout(empty_page)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.addStretch(1)

        empty_card = QFrame()
        empty_card.setObjectName("empty_card")
        empty_card.setMinimumHeight(220)
        ec = QVBoxLayout(empty_card)
        ec.setContentsMargins(24, 24, 24, 24)
        ec.setSpacing(10)
        ec.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel("Paste a URL to begin")
        title_lbl.setObjectName("h2")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ec.addWidget(title_lbl)

        hint_lbl = QLabel(
            "Spotify · YouTube Music\n"
            "track · album · playlist"
        )
        hint_lbl.setObjectName("muted")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ec.addWidget(hint_lbl)

        # Service badges
        svc_row = QHBoxLayout()
        svc_row.setSpacing(6)
        svc_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for svc in ("tidal", "qobuz", "deezer", "amazon"):
            b = QLabel(svc)
            b.setObjectName("badge")
            svc_row.addWidget(b)
        ec.addLayout(svc_row)

        ev.addWidget(empty_card)
        ev.addStretch(2)
        self._stack.addWidget(empty_page)

        # Page 1 — results
        results_page = QWidget()
        rl = QVBoxLayout(results_page)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self._header_box = QVBoxLayout()
        self._header_box.setContentsMargins(0, 0, 0, 0)
        rl.addLayout(self._header_box)

        # Search + select-all toggle row
        self._search_input = QLineEdit()
        self._search_input.setObjectName("search")
        self._search_input.setPlaceholderText("🔎  Filter tracks…")
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.setClearButtonEnabled(True)

        self._select_btn = QPushButton("Clear All")
        self._select_btn.setObjectName("ghost")
        self._select_btn.clicked.connect(self._toggle_all)

        self._invert_btn = QPushButton("Invert")
        self._invert_btn.setObjectName("ghost")
        self._invert_btn.clicked.connect(self._invert_selection)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)
        sel_row.addWidget(self._search_input, stretch=1)
        sel_row.addWidget(self._select_btn)
        sel_row.addWidget(self._invert_btn)
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
        self._status_lbl.setText("Fetching playlist… (large playlists may take ~30s)")

        if hasattr(self, "_log_panel") and self._log_panel:
            self._log_panel.clear()

        self._resolve_worker = ResolveWorker(url, self._spotify, self)
        self._resolve_worker.finished.connect(self._on_resolve_done)
        self._resolve_worker.error.connect(self._on_resolve_error)
        self._resolve_worker.log_message.connect(self._on_log_message)
        self._resolve_worker.start()

    def _on_resolve_done(self, result):
        self._result = result
        self._preview_btn.setEnabled(True)
        self._preview_btn.setText("Preview")
        self._status_lbl.setText("")

        # header
        self._header = PlaylistHeader(
            name      = result.collection_name or "—",
            cover     = result.tracks[0].cover_url if result.tracks else "",
            count     = len(result.tracks),
            unmatched = len(result.unmatched_samples),
        )
        self._header_box.addWidget(self._header)

        # rows
        for i, track in enumerate(result.tracks):
            row = TrackRow(i + 1, track, self._track_container)
            row.toggled.connect(self._on_row_toggled)
            row.failure_clicked.connect(self._on_failure_clicked)
            self._track_layout.insertWidget(self._track_layout.count() - 1, row)
            self._rows.append(row)
            self._selected.add(i)

        self._search_input.clear()
        self._stack.setCurrentIndex(1)
        self._update_dl_button()
        self._update_select_btn()
        self._update_header_count()

    def _invert_selection(self):
        # Operate only on currently visible (filtered) rows
        visible = [r for r in self._rows if r.isVisible()]
        if not visible:
            visible = self._rows
        for row in visible:
            i = row.index() - 1
            now = row.is_checked()
            row.set_checked(not now)
            if now:
                self._selected.discard(i)
            else:
                self._selected.add(i)
        self._update_dl_button()
        self._update_select_btn()
        self._update_header_count()

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
        self._update_header_count()

    def _toggle_all(self):
        # Operate only on currently visible (filtered) rows
        visible = [r for r in self._rows if r.isVisible()]
        if not visible:
            visible = self._rows
        all_checked = all(r.is_checked() for r in visible)
        target = not all_checked
        for row in visible:
            row.set_checked(target)
            i = row.index() - 1
            if target:
                self._selected.add(i)
            else:
                self._selected.discard(i)
        self._update_dl_button()
        self._update_select_btn()
        self._update_header_count()

    def _update_select_btn(self):
        if not self._rows:
            return
        visible = [r for r in self._rows if r.isVisible()]
        if not visible:
            visible = self._rows
        all_on = all(r.is_checked() for r in visible)
        self._select_btn.setText("Clear All" if all_on else "Select All")

    def _update_dl_button(self):
        n = len(self._selected)
        if self._is_downloading:
            return
        self._dl_btn.setText(f"Download ({n})" if n else "Download")
        self._dl_btn.setEnabled(n > 0 and self._result is not None)

    def _update_header_count(self):
        if self._header is not None:
            self._header.set_selection_count(len(self._selected))

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self, _text: str):
        self._search_timer.start()

    def _apply_search_filter(self):
        needle = self._search_input.text().strip().lower()
        for row in self._rows:
            row.setVisible(row.matches(needle))
        self._update_select_btn()

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

        self._is_downloading = True
        self._dl_btn.setEnabled(False)
        self._dl_btn.setText("Downloading…")
        self._stop_btn.setVisible(True)
        self._preview_btn.setEnabled(False)
        self._url_input.setEnabled(False)
        self._search_input.setEnabled(False)
        self._select_btn.setEnabled(False)
        self._invert_btn.setEnabled(False)

        # Show progress bar
        total = len(self._selected)
        self._progress_bar.setRange(0, total if total > 0 else 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

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

        cd_every = self._settings.value("cooldown_every", 0, type=int)
        cd_secs  = self._settings.value("cooldown_seconds", 0, type=int)
        # Legacy migration: historical defaults (20/30) were too slow for typical use.
        if cd_every == 20 and cd_secs == 30:
            cd_every = 0
            cd_secs = 0

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
        self._dl_worker.log_message.connect(self._on_log_message)
        self._dl_worker.finished.connect(self._on_dl_done)
        self._dl_worker.error.connect(self._on_dl_error)
        self._dl_worker.start()

    def _on_log_message(self, text: str, level: str):
        if hasattr(self, "_log_panel") and self._log_panel:
            self._log_panel.append(text, level)

    def _on_stop(self):
        if self._dl_worker is None:
            return
        self._stop_btn.setEnabled(False)
        self._stop_btn.setText("Stopping…")
        self._status_lbl.setText("Stopping after current track…")
        try:
            self._dl_worker.requestInterruption()
        except Exception:
            pass

    def _on_track_started(self, idx: int, _title: str):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status(STATUS_RUNNING)

    def _on_track_done(self, idx: int, _title: str):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status(STATUS_DONE)

    def _on_track_failed(self, idx: int, _title: str, err: str):
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_status(STATUS_FAILED, tooltip=err)

    def _on_failure_clicked(self, index_one_based: int):
        idx = index_one_based - 1
        if not (0 <= idx < len(self._rows)):
            return
        row = self._rows[idx]
        track = row._track
        err = row.error_message()
        title = getattr(track, "title", "Unknown")
        artist = getattr(track, "artists", "") or getattr(track, "artist", "")
        dlg = FailureDialog(title, artist, err, self)
        dlg.exec()

    def _on_progress(self, current: int, total: int, title: str):
        self._progress_bar.setRange(0, total if total > 0 else 1)
        self._progress_bar.setValue(current)
        # Truncate long titles for status
        short = title if len(title) <= 36 else title[:35] + "…"
        self._status_lbl.setText(f"{current} / {total}  ·  {short}")

    def _on_cooldown(self, remaining: int, total: int):
        if remaining <= 0:
            self._status_lbl.setText("Resuming…")
        else:
            self._status_lbl.setText(
                f"Cooldown · {remaining}s left  (avoiding rate limits)"
            )

    def _on_dl_done(self, succeeded: int, failed: int):
        self._is_downloading = False
        self._dl_btn.setEnabled(True)
        self._dl_btn.setText("Download")
        self._stop_btn.setVisible(False)
        self._stop_btn.setEnabled(True)
        self._stop_btn.setText("Stop")
        self._preview_btn.setEnabled(True)
        self._url_input.setEnabled(True)
        self._search_input.setEnabled(True)
        self._select_btn.setEnabled(True)
        self._invert_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._update_dl_button()
        msg = f"Done  ·  {succeeded} succeeded"
        if failed:
            # Compute dominant failure category
            from collections import Counter
            kinds = Counter()
            for row in self._rows:
                if row.error_message():
                    kinds[classify_error(row.error_message())] += 1
            dominant = kinds.most_common(1)[0][0] if kinds else None
            cat_text = f"  (mostly {friendly_label(dominant).lower()})" if dominant else ""
            msg += f"  ·  {failed} failed{cat_text}  ·  click ✗ for details"
        self._status_lbl.setText(msg)

    def _on_dl_error(self, msg: str):
        self._is_downloading = False
        self._dl_btn.setEnabled(True)
        self._dl_btn.setText("Download")
        self._stop_btn.setVisible(False)
        self._stop_btn.setEnabled(True)
        self._stop_btn.setText("Stop")
        self._preview_btn.setEnabled(True)
        self._url_input.setEnabled(True)
        self._search_input.setEnabled(True)
        self._select_btn.setEnabled(True)
        self._invert_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
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
        self._header = None
        # rows
        while self._track_layout.count() > 1:
            it = self._track_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._rows.clear()
        self._selected.clear()
        self._result = None
        if hasattr(self, "_search_input"):
            self._search_input.clear()
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
            self.resize(820, 700)
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
    # Setup debug logging on startup
    _setup_debug_logging()
    
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

        window = SpotiflacApp()
        window.show()

        ret = app.exec()
        logging.info("YtFLAC GUI exited with code %d", ret)
        return ret
    except Exception:
        _log_crash(*sys.exc_info())
        return 1

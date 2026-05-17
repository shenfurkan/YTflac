"""
Settings dialog — exposes the full DownloadOptions surface.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QStackedWidget,
    QLabel,
    QListWidget,
    QAbstractItemView,
    QFrame,
    QFileDialog,
    QSizePolicy,
)

from .. import style as S
from ..fluent import (
    CardWidget,
    ComboBox,
    FLUENT_AVAILABLE,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    TransparentPushButton,
)
from . import settings_tabs as ST


LYRICS_ALL = ST.LYRICS_ALL
ENRICH_ALL = ST.ENRICH_ALL


def _section(title: str) -> QLabel:
    return ST._section(title)


def _fluent_dialog_qss() -> str:
    return f"""
QDialog#settings_dialog {{
    background-color: {S.BG};
}}

QWidget#settings_tab_root {{
    background-color: {S.BG};
    border: none;
}}

QWidget#settings_right_panel {{
    background-color: {S.BG};
}}

QListWidget#settings_sidebar {{
    background-color: {S.BG_ELEV};
    border-right: 1px solid {S.LINE_STRONG};
    border-top: none;
    border-bottom: none;
    border-left: none;
    padding: 8px 6px;
}}

QListWidget#settings_sidebar::item {{
    color: {S.TEXT_DIM};
    border-radius: 6px;
    padding: 7px 12px;
    margin: 2px;
    font-weight: 600;
    font-size: 12px;
    background-color: transparent;
}}

QListWidget#settings_sidebar::item:hover {{
    color: {S.TEXT};
    background-color: {S.BG_HOVER};
}}

QListWidget#settings_sidebar::item:selected {{
    color: {S.TEXT};
    background-color: {S.ACCENT_SOFT};
    font-weight: 700;
}}

QFrame#dialog_footer {{
    background-color: {S.BG_ELEV};
    border-top: 1px solid {S.LINE_STRONG};
}}

QLabel#h1 {{
    font-size: 16px;
    font-weight: 800;
    color: {S.TEXT};
    padding-bottom: 0px;
    background: transparent;
}}

QLabel#h2 {{
    font-size: 12px;
    font-weight: 700;
    color: {S.TEXT};
    background: transparent;
}}

QLabel#muted {{
    color: {S.TEXT_FAINT};
    font-size: 10px;
    background: transparent;
}}

QLabel#section {{
    color: {S.TEXT_DIM};
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    background: transparent;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    min-height: 24px;
    font-size: 12px;
}}

QCheckBox {{
    font-size: 12px;
    spacing: 6px;
}}

QPushButton {{
    min-height: 26px;
    padding: 4px 10px;
    font-size: 12px;
}}
"""


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: QSettings,
        services_all: list[str],
        output_dir: str,
        parent=None,
    ):
        super().__init__(parent)
        self._settings = settings
        self._services_all = services_all
        self._output_dir = output_dir
        self.setObjectName("settings_dialog")
        self.setWindowTitle("Settings")
        self.setMinimumSize(800, 560)
        self.resize(800, 560)
        theme = self._settings.value("theme", "light", type=str)
        S.set_theme(theme)
        if FLUENT_AVAILABLE:
            self.setStyleSheet(_fluent_dialog_qss())
        else:
            self.setStyleSheet(S.QSS)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("settings_sidebar")
        self.sidebar.setFixedWidth(208)
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.sidebar.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.sidebar.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar.setSpacing(4)
        self.sidebar.addItems(["Services", "Files & Folders", "Metadata", "Lyrics", "Advanced"])
        main_layout.addWidget(self.sidebar)

        self.right_panel = QWidget()
        self.right_panel.setObjectName("settings_right_panel")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_services_tab())
        self.stack.addWidget(self._build_files_tab())
        self.stack.addWidget(self._build_metadata_tab())
        self.stack.addWidget(self._build_lyrics_tab())
        self.stack.addWidget(self._build_advanced_tab())
        right_layout.addWidget(self.stack, stretch=1)

        footer = QFrame()
        footer.setObjectName("dialog_footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 8, 16, 8)
        footer_layout.setSpacing(8)

        self.btn_restore = PushButton("Restore Defaults")
        if not FLUENT_AVAILABLE:
            self.btn_restore.setObjectName("secondary")
        self.btn_restore.clicked.connect(self._restore_defaults)

        self.btn_cancel = TransparentPushButton("Cancel")
        if not FLUENT_AVAILABLE:
            self.btn_cancel.setObjectName("ghost")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = PrimaryPushButton("Save Changes")
        if not FLUENT_AVAILABLE:
            self.btn_ok.setObjectName("primary")
        self.btn_ok.clicked.connect(self._save_and_close)

        footer_layout.addWidget(self.btn_restore)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_ok)

        right_layout.addWidget(footer)
        main_layout.addWidget(self.right_panel, stretch=1)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

    def _create_card(self) -> tuple[QFrame, QVBoxLayout]:
        card = CardWidget()
        card.setObjectName("settings_card")
        if FLUENT_AVAILABLE:
            from PyQt6.QtGui import QColor
            card.setBorderRadius(12)
            card.setBackgroundColor(QColor(S.BG_ELEV))
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        return card, layout

    def _add_setting_row(self, layout: QVBoxLayout, label_text: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        row.setSpacing(16)

        lbl = QLabel(label_text)
        lbl.setObjectName("section")

        if isinstance(widget, (ComboBox, LineEdit)):
            widget.setMinimumWidth(200)
            widget.setMaximumWidth(280)

        row.addWidget(lbl, stretch=1)
        row.addWidget(widget, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(row)


    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _build_services_tab(self) -> QWidget:
        return ST.build_services_tab(self)

    def _build_files_tab(self) -> QWidget:
        return ST.build_files_tab(self)

    def _build_metadata_tab(self) -> QWidget:
        return ST.build_metadata_tab(self)

    def _build_lyrics_tab(self) -> QWidget:
        return ST.build_lyrics_tab(self)

    def _build_advanced_tab(self) -> QWidget:
        return ST.build_advanced_tab(self)

    # ------------------------------------------------------------------
    # Save / restore
    # ------------------------------------------------------------------

    def _on_theme_changed(self, theme_name: str) -> None:
        """Handle theme change in settings."""
        theme = theme_name.lower()
        self._settings.setValue("theme", theme)
        # Notify parent to apply theme change (which updates app-level QSS)
        if self.parent():
            self.parent().apply_theme(theme)

    @staticmethod
    def _shorten(path: str, max_len: int = 36) -> str:
        import os

        home = os.path.expanduser("~")
        p = path.replace(home, "~")
        if len(p) > max_len:
            p = "…" + p[-(max_len - 1) :]
        return p

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose Folder", self._output_dir
        )
        if folder:
            self._output_dir = folder
            self._folder_btn.setText(folder)
            self._folder_btn.setToolTip(folder)

    def _save_and_close(self):
        s = self._settings
        s.setValue("output_dir", self._output_dir)
        # Services
        s.setValue("service_order", self._svc_bar.ordered_services())
        s.setValue("service_enabled", self._svc_bar.enabled_services())
        # Files
        s.setValue(
            "filename_format", self._fmt_input.text().strip() or "{title} - {artist}"
        )
        s.setValue("use_track_numbers", self._cb_track_num.isChecked())
        s.setValue("use_album_track_numbers", self._cb_album_track_num.isChecked())
        s.setValue("first_artist_only", self._cb_first_artist.isChecked())
        s.setValue("use_artist_subfolders", self._cb_artist_sub.isChecked())
        s.setValue("use_album_subfolders", self._cb_album_sub.isChecked())
        # Metadata
        s.setValue("enrich_metadata", self._cb_enrich.isChecked())
        s.setValue("enrich_providers", self._enrich_list.enabled_ordered())
        s.setValue("qobuz_token", self._qobuz_input.text().strip())
        # Lyrics
        s.setValue("embed_lyrics", self._cb_lyrics.isChecked())
        s.setValue("lyrics_providers", self._lyrics_list.enabled_ordered())
        s.setValue("lyrics_spotify_token", self._spot_token_input.text().strip())
        # Advanced
        s.setValue("allow_fallback", self._cb_fallback.isChecked())
        delay_text = self._delay_combo.currentText().replace(" s", "").strip()
        s.setValue("inter_track_delay_s", float(delay_text))
        s.setValue("log_level", self._loglevel_combo.currentText())
        s.setValue("show_activity_log", self._cb_show_log.isChecked())
        s.setValue("concurrent_downloads", int(self._concurrent_combo.currentText()))
        self.accept()

    def _restore_defaults(self):
        self._fmt_input.setText("{title} - {artist}")
        self._cb_track_num.setChecked(False)
        self._cb_album_track_num.setChecked(False)
        self._cb_first_artist.setChecked(False)
        self._cb_artist_sub.setChecked(False)
        self._cb_album_sub.setChecked(False)
        self._cb_enrich.setChecked(True)
        self._cb_lyrics.setChecked(False)
        self._cb_fallback.setChecked(True)
        self._delay_combo.setCurrentText("0.0 s")
        self._loglevel_combo.setCurrentText("WARNING")
        self._cb_show_log.setChecked(False)
        self._concurrent_combo.setCurrentText("2")
        self._qobuz_input.setText("")
        self._spot_token_input.setText("")


def load_options_kwargs(settings: QSettings) -> dict:
    """Read all settings into a kwargs dict suitable for DownloadOptions."""
    return {
        "filename_format": settings.value(
            "filename_format", "{title} - {artist}", type=str
        ),
        "use_track_numbers": settings.value("use_track_numbers", False, type=bool),
        "use_album_track_numbers": settings.value(
            "use_album_track_numbers", False, type=bool
        ),
        "use_artist_subfolders": settings.value(
            "use_artist_subfolders", False, type=bool
        ),
        "use_album_subfolders": settings.value(
            "use_album_subfolders", False, type=bool
        ),
        "first_artist_only": settings.value("first_artist_only", False, type=bool),
        "allow_fallback": settings.value("allow_fallback", True, type=bool),
        "inter_track_delay_s": settings.value("inter_track_delay_s", 0.0, type=float),
        "embed_lyrics": settings.value("embed_lyrics", False, type=bool),
        "lyrics_providers": settings.value("lyrics_providers", LYRICS_ALL, type=list)
        or LYRICS_ALL,
        "lyrics_spotify_token": settings.value("lyrics_spotify_token", "", type=str),
        "enrich_metadata": settings.value("enrich_metadata", True, type=bool),
        "enrich_providers": settings.value("enrich_providers", ENRICH_ALL, type=list)
        or ENRICH_ALL,
        "qobuz_token": settings.value("qobuz_token", "", type=str) or None,
    }

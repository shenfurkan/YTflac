"""
Settings dialog — exposes the full DownloadOptions surface.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget,
    QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox, QLabel,
    QPushButton, QDialogButtonBox, QGroupBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QFrame, QFileDialog,
)

from .widgets import ServicePriorityBar
from . import style as S


LYRICS_ALL  = ["spotify", "musixmatch", "amazon", "lrclib", "apple"]
ENRICH_ALL  = ["deezer", "apple", "qobuz", "tidal"]


def _section(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setObjectName("section")
    return lbl


class _ToggleList(QListWidget):
    """Reorderable, click-to-toggle chip list (vertical, compact)."""
    def __init__(self, all_items: list[str], enabled: list[str], parent=None):
        super().__init__(parent)
        self.setObjectName("chips")
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setSpacing(4)
        self.setFixedHeight(40)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        # de-dup + add missing
        order = [s for s in enabled if s in all_items]
        for s in all_items:
            if s not in order:
                order.append(s)
        en_set = set(enabled)
        for name in order:
            self._add(name, name in en_set)
        self.itemClicked.connect(self._toggle)

    def _add(self, name: str, on: bool):
        it = QListWidgetItem(name)
        it.setData(Qt.ItemDataRole.UserRole, on)
        self._paint(it, on)
        self.addItem(it)

    def _toggle(self, it: QListWidgetItem):
        on = not bool(it.data(Qt.ItemDataRole.UserRole))
        it.setData(Qt.ItemDataRole.UserRole, on)
        self._paint(it, on)

    @staticmethod
    def _paint(it: QListWidgetItem, on: bool):
        from PyQt6.QtGui import QColor
        it.setForeground(QColor(S.TEXT if on else S.TEXT_FAINT))

    def enabled_ordered(self) -> list[str]:
        return [
            self.item(i).text()
            for i in range(self.count())
            if bool(self.item(i).data(Qt.ItemDataRole.UserRole))
        ]


class SettingsDialog(QDialog):
    def __init__(self, settings: QSettings, services_all: list[str], current_folder: str, parent=None):
        super().__init__(parent)
        self._settings     = settings
        self._services_all = services_all
        self._current_folder = current_folder
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.setMinimumHeight(540)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("h2")
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_services_tab(), "Services")
        tabs.addTab(self._build_files_tab(),    "Files")
        tabs.addTab(self._build_metadata_tab(), "Metadata")
        tabs.addTab(self._build_lyrics_tab(),   "Lyrics")
        tabs.addTab(self._build_advanced_tab(), "Advanced")
        root.addWidget(tabs, stretch=1)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults
        )
        bb.accepted.connect(self._save_and_close)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore_defaults)
        root.addWidget(bb)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _build_services_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 8, 4, 8)
        v.setSpacing(10)

        v.addWidget(_section("Service priority"))

        info = QLabel(
            "Drag chips to reorder. Click to enable / disable. "
            "The download will try services from left to right."
        )
        info.setObjectName("faint")
        info.setWordWrap(True)
        v.addWidget(info)

        order = self._settings.value("service_order", self._services_all, type=list) or self._services_all
        order = [s for s in order if s in self._services_all]
        for s in self._services_all:
            if s not in order:
                order.append(s)
        enabled = self._settings.value("service_enabled", order, type=list) or order
        enabled = [s for s in enabled if s in order]

        self._svc_bar = ServicePriorityBar(order, enabled)
        self._svc_bar.setMinimumHeight(48)
        v.addWidget(self._svc_bar)
        v.addStretch()
        return w

    def _build_files_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setContentsMargins(4, 8, 4, 8)

        # --- Output folder ---
        folder_lbl = QLabel("Output folder")
        folder_lbl.setObjectName("section")
        form.addRow(folder_lbl)

        self._folder_btn = QPushButton(self._shorten(self._current_folder))
        self._folder_btn.setObjectName("ghost")
        self._folder_btn.setToolTip(self._current_folder)
        self._folder_btn.clicked.connect(self._choose_folder)
        form.addRow("", self._folder_btn)

        form.addRow(QLabel(" "))

        self._fmt_input = QLineEdit(
            self._settings.value("filename_format", "{title} - {artist}", type=str)
        )
        self._fmt_input.setPlaceholderText("{title} - {artist}")
        form.addRow("Filename template", self._fmt_input)

        hint = QLabel("Available: {title}, {artist}, {album}, {track_num}")
        hint.setObjectName("faint")
        form.addRow("", hint)

        self._cb_track_num = QCheckBox("Prepend track number to filename")
        self._cb_track_num.setChecked(self._settings.value("use_track_numbers", False, type=bool))
        form.addRow("", self._cb_track_num)

        self._cb_album_track_num = QCheckBox("Use the actual album track number")
        self._cb_album_track_num.setChecked(self._settings.value("use_album_track_numbers", False, type=bool))
        form.addRow("", self._cb_album_track_num)

        self._cb_first_artist = QCheckBox("Use only the first artist")
        self._cb_first_artist.setChecked(self._settings.value("first_artist_only", False, type=bool))
        form.addRow("", self._cb_first_artist)

        sep = QLabel(" ")
        form.addRow(sep)

        form.addRow(_section("Folder structure (playlists only)"))

        self._cb_artist_sub = QCheckBox("Create artist subfolder")
        self._cb_artist_sub.setChecked(self._settings.value("use_artist_subfolders", False, type=bool))
        form.addRow("", self._cb_artist_sub)

        self._cb_album_sub = QCheckBox("Create album subfolder")
        self._cb_album_sub.setChecked(self._settings.value("use_album_subfolders", False, type=bool))
        form.addRow("", self._cb_album_sub)

        return w

    def _build_metadata_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setContentsMargins(4, 8, 4, 8)

        self._cb_enrich = QCheckBox("Enrich metadata (BPM, Label, Genre, etc.)")
        self._cb_enrich.setChecked(self._settings.value("enrich_metadata", True, type=bool))
        form.addRow("", self._cb_enrich)

        form.addRow(_section("Provider order (click to toggle)"))
        enrich_default = self._settings.value("enrich_providers", ENRICH_ALL, type=list) or ENRICH_ALL
        enrich_default = [s for s in enrich_default if s in ENRICH_ALL]
        self._enrich_list = _ToggleList(ENRICH_ALL, enrich_default)
        form.addRow("", self._enrich_list)

        self._qobuz_input = QLineEdit(self._settings.value("qobuz_token", "", type=str))
        self._qobuz_input.setPlaceholderText("Optional — may be left empty")
        self._qobuz_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Qobuz token", self._qobuz_input)

        return w

    def _build_lyrics_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setContentsMargins(4, 8, 4, 8)

        self._cb_lyrics = QCheckBox("Embed lyrics into the FLAC/MP3 file")
        self._cb_lyrics.setChecked(self._settings.value("embed_lyrics", False, type=bool))
        form.addRow("", self._cb_lyrics)

        form.addRow(_section("Provider order (click to toggle)"))
        lyr_default = self._settings.value("lyrics_providers", LYRICS_ALL, type=list) or LYRICS_ALL
        lyr_default = [s for s in lyr_default if s in LYRICS_ALL]
        self._lyrics_list = _ToggleList(LYRICS_ALL, lyr_default)
        form.addRow("", self._lyrics_list)

        self._spot_token_input = QLineEdit(
            self._settings.value("lyrics_spotify_token", "", type=str)
        )
        self._spot_token_input.setPlaceholderText("Optional — sp_dc cookie for Spotify lyrics")
        self._spot_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Spotify token", self._spot_token_input)

        return w

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setContentsMargins(4, 8, 4, 8)

        self._cb_fallback = QCheckBox("Fall back to other services on failure")
        self._cb_fallback.setChecked(self._settings.value("allow_fallback", True, type=bool))
        form.addRow("", self._cb_fallback)

        self._delay_spin = QDoubleSpinBox()
        self._delay_spin.setRange(0.0, 30.0)
        self._delay_spin.setSingleStep(0.5)
        self._delay_spin.setSuffix(" s")
        self._delay_spin.setDecimals(1)
        self._delay_spin.setValue(self._settings.value("inter_track_delay_s", 0.5, type=float))
        form.addRow("Inter-track delay", self._delay_spin)

        self._loglevel_combo = QComboBox()
        self._loglevel_combo.addItems(["WARNING", "INFO", "DEBUG", "ERROR"])
        self._loglevel_combo.setCurrentText(self._settings.value("log_level", "WARNING", type=str))
        form.addRow("Log level", self._loglevel_combo)

        hint = QLabel(
            "Note: log level applies on next launch."
        )
        hint.setObjectName("faint")
        hint.setWordWrap(True)
        form.addRow("", hint)

        return w

    # ------------------------------------------------------------------
    # Save / restore
    # ------------------------------------------------------------------

    @staticmethod
    def _shorten(path: str, max_len: int = 36) -> str:
        import os
        home = os.path.expanduser("~")
        p = path.replace(home, "~")
        if len(p) > max_len:
            p = "…" + p[-(max_len - 1):]
        return p

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose Folder", self._current_folder)
        if folder:
            self._current_folder = folder
            self._folder_btn.setText(self._shorten(folder))
            self._folder_btn.setToolTip(folder)

    def _save_and_close(self):
        s = self._settings
        s.setValue("output_dir", self._current_folder)
        # Services
        s.setValue("service_order",   self._svc_bar.ordered_services())
        s.setValue("service_enabled", self._svc_bar.enabled_services())
        # Files
        s.setValue("filename_format",         self._fmt_input.text().strip() or "{title} - {artist}")
        s.setValue("use_track_numbers",       self._cb_track_num.isChecked())
        s.setValue("use_album_track_numbers", self._cb_album_track_num.isChecked())
        s.setValue("first_artist_only",       self._cb_first_artist.isChecked())
        s.setValue("use_artist_subfolders",   self._cb_artist_sub.isChecked())
        s.setValue("use_album_subfolders",    self._cb_album_sub.isChecked())
        # Metadata
        s.setValue("enrich_metadata",   self._cb_enrich.isChecked())
        s.setValue("enrich_providers",  self._enrich_list.enabled_ordered())
        s.setValue("qobuz_token",       self._qobuz_input.text().strip())
        # Lyrics
        s.setValue("embed_lyrics",          self._cb_lyrics.isChecked())
        s.setValue("lyrics_providers",      self._lyrics_list.enabled_ordered())
        s.setValue("lyrics_spotify_token",  self._spot_token_input.text().strip())
        # Advanced
        s.setValue("allow_fallback",      self._cb_fallback.isChecked())
        s.setValue("inter_track_delay_s", float(self._delay_spin.value()))
        s.setValue("log_level",           self._loglevel_combo.currentText())
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
        self._delay_spin.setValue(0.5)
        self._loglevel_combo.setCurrentText("WARNING")
        self._qobuz_input.setText("")
        self._spot_token_input.setText("")


def load_options_kwargs(settings: QSettings) -> dict:
    """Read all settings into a kwargs dict suitable for DownloadOptions."""
    return {
        "filename_format":         settings.value("filename_format", "{title} - {artist}", type=str),
        "use_track_numbers":       settings.value("use_track_numbers", False, type=bool),
        "use_album_track_numbers": settings.value("use_album_track_numbers", False, type=bool),
        "use_artist_subfolders":   settings.value("use_artist_subfolders", False, type=bool),
        "use_album_subfolders":    settings.value("use_album_subfolders", False, type=bool),
        "first_artist_only":       settings.value("first_artist_only", False, type=bool),
        "allow_fallback":          settings.value("allow_fallback", True, type=bool),
        "inter_track_delay_s":     settings.value("inter_track_delay_s", 0.5, type=float),
        "embed_lyrics":            settings.value("embed_lyrics", False, type=bool),
        "lyrics_providers":        settings.value("lyrics_providers", LYRICS_ALL, type=list) or LYRICS_ALL,
        "lyrics_spotify_token":    settings.value("lyrics_spotify_token", "", type=str),
        "enrich_metadata":         settings.value("enrich_metadata", True, type=bool),
        "enrich_providers":        settings.value("enrich_providers", ENRICH_ALL, type=list) or ENRICH_ALL,
        "qobuz_token":             settings.value("qobuz_token", "", type=str) or None,
    }

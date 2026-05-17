from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..components import ServicePriorityBar, TickCheckBox
from ..fluent import ComboBox, FLUENT_AVAILABLE, LineEdit, PushButton
from .settings_widgets import ToggleList, section_label

LYRICS_ALL = ["spotify", "musixmatch", "amazon", "lrclib", "apple"]
ENRICH_ALL = ["deezer", "apple", "qobuz", "tidal"]


def _section(title: str) -> QLabel:
    return section_label(title)


def _scroll(w: QWidget) -> QWidget:
    w.setObjectName("settings_tab_root")
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(w)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return sa


def _tighten_card(layout: QVBoxLayout) -> None:
    layout.setSpacing(4)


def build_services_tab(self) -> QWidget:
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(20, 14, 20, 14)
    v.setSpacing(10)
    v.setAlignment(Qt.AlignmentFlag.AlignTop)

    page_title = QLabel("Services")
    page_title.setObjectName("h1")
    v.addWidget(page_title)

    card, c = self._create_card()
    _tighten_card(c)

    card_title = QLabel("Service Priority")
    card_title.setObjectName("h2")
    c.addWidget(card_title)

    info = QLabel(
        "Drag chips to reorder. Click to enable / disable. "
        "The download will try services from left to right."
    )
    info.setObjectName("muted")
    info.setWordWrap(True)
    c.addWidget(info)

    order = (
        self._settings.value("service_order", self._services_all, type=list)
        or self._services_all
    )
    order = [s for s in order if s in self._services_all]
    for s in self._services_all:
        if s not in order:
            order.append(s)
    enabled = self._settings.value("service_enabled", order, type=list) or order
    enabled = [s for s in enabled if s in order]

    self._svc_bar = ServicePriorityBar(order, enabled)
    c.addWidget(self._svc_bar)

    v.addWidget(card)
    v.addStretch(1)
    return _scroll(w)


def build_files_tab(self) -> QWidget:
    w = QWidget()
    root = QVBoxLayout(w)
    root.setContentsMargins(20, 14, 20, 14)
    root.setSpacing(10)
    root.setAlignment(Qt.AlignmentFlag.AlignTop)

    page_title = QLabel("Files & Folders")
    page_title.setObjectName("h1")
    root.addWidget(page_title)

    card1, c1 = self._create_card()
    _tighten_card(c1)

    c1_title = QLabel("Output Location")
    c1_title.setObjectName("h2")
    c1.addWidget(c1_title)

    row = QHBoxLayout()
    row.setSpacing(12)
    self._folder_btn = LineEdit()
    self._folder_btn.setText(self._output_dir)
    self._folder_btn.setReadOnly(True)
    self._folder_btn.setToolTip(self._output_dir)
    btn_browse = PushButton("Browse")
    if not FLUENT_AVAILABLE:
        btn_browse.setObjectName("secondary")
    btn_browse.clicked.connect(self._choose_folder)
    row.addWidget(self._folder_btn)
    row.addWidget(btn_browse)
    c1.addLayout(row)
    root.addWidget(card1)

    card2, c2 = self._create_card()
    _tighten_card(c2)

    c2_title = QLabel("File Naming")
    c2_title.setObjectName("h2")
    c2.addWidget(c2_title)

    self._fmt_input = LineEdit()
    self._fmt_input.setText(
        self._settings.value("filename_format", "{title} - {artist}", type=str)
    )
    self._fmt_input.setPlaceholderText("{title} - {artist}")
    self._fmt_input.setToolTip(
        "Use placeholders: {title}, {artist}, {album}, {track_num}\n"
        "Example: {track_num:02d} - {title} - {artist}"
    )
    c2.addWidget(self._fmt_input)

    hint = QLabel("Available: {title}, {artist}, {album}, {track_num}")
    hint.setObjectName("muted")
    c2.addWidget(hint)

    opts_grid = QGridLayout()
    opts_grid.setHorizontalSpacing(12)
    opts_grid.setVerticalSpacing(6)

    self._cb_track_num = TickCheckBox("Prepend track number to filename")
    self._cb_track_num.setChecked(
        self._settings.value("use_track_numbers", False, type=bool)
    )
    self._cb_track_num.setToolTip(
        "Adds track number (e.g., '01') before the filename"
    )
    opts_grid.addWidget(self._cb_track_num, 0, 0)

    self._cb_album_track_num = TickCheckBox("Use the actual album track number")
    self._cb_album_track_num.setChecked(
        self._settings.value("use_album_track_numbers", False, type=bool)
    )
    self._cb_album_track_num.setToolTip(
        "Use the original track number from the album metadata"
    )
    opts_grid.addWidget(self._cb_album_track_num, 0, 1)

    self._cb_first_artist = TickCheckBox("Use only the first artist")
    self._cb_first_artist.setChecked(
        self._settings.value("first_artist_only", False, type=bool)
    )
    self._cb_first_artist.setToolTip(
        "For multi-artist tracks, only use the first artist in the filename"
    )
    opts_grid.addWidget(self._cb_first_artist, 1, 0)

    folder_title = QLabel("Folder Structure (Playlists Only)")
    folder_title.setObjectName("h2")
    c2.addWidget(folder_title)

    self._cb_artist_sub = TickCheckBox("Create artist subfolder")
    self._cb_artist_sub.setChecked(
        self._settings.value("use_artist_subfolders", False, type=bool)
    )
    self._cb_artist_sub.setToolTip(
        "Organize downloads by artist (e.g., Music/Artist/Album/)"
    )
    opts_grid.addWidget(self._cb_artist_sub, 2, 0)

    self._cb_album_sub = TickCheckBox("Create album subfolder")
    self._cb_album_sub.setChecked(
        self._settings.value("use_album_subfolders", False, type=bool)
    )
    self._cb_album_sub.setToolTip(
        "Organize downloads by album (e.g., Music/Album/)"
    )
    opts_grid.addWidget(self._cb_album_sub, 2, 1)

    c2.addLayout(opts_grid)

    root.addWidget(card2)
    root.addStretch(1)
    return _scroll(w)


def build_metadata_tab(self) -> QWidget:
    w = QWidget()
    root = QVBoxLayout(w)
    root.setContentsMargins(20, 14, 20, 14)
    root.setSpacing(10)
    root.setAlignment(Qt.AlignmentFlag.AlignTop)

    page_title = QLabel("Metadata")
    page_title.setObjectName("h1")
    root.addWidget(page_title)

    card1, c1 = self._create_card()
    _tighten_card(c1)

    self._cb_enrich = TickCheckBox("Enrich metadata (BPM, Label, Genre, etc.)")
    self._cb_enrich.setChecked(
        self._settings.value("enrich_metadata", True, type=bool)
    )
    self._cb_enrich.setToolTip("Fetch additional metadata from multiple sources")
    c1.addWidget(self._cb_enrich)

    title = QLabel("Provider Order")
    title.setObjectName("h2")
    c1.addWidget(title)
    desc = QLabel("Drag chips to reorder. Click to toggle providers.")
    desc.setObjectName("muted")
    c1.addWidget(desc)
    enrich_default = (
        self._settings.value("enrich_providers", ENRICH_ALL, type=list)
        or ENRICH_ALL
    )
    enrich_default = [s for s in enrich_default if s in ENRICH_ALL]
    self._enrich_list = ToggleList(ENRICH_ALL, enrich_default)
    c1.addWidget(self._enrich_list)

    root.addWidget(card1)

    card2, c2 = self._create_card()
    _tighten_card(c2)

    tok_title = QLabel("Qobuz Token")
    tok_title.setObjectName("h2")
    c2.addWidget(tok_title)

    self._qobuz_input = LineEdit()
    self._qobuz_input.setText(self._settings.value("qobuz_token", "", type=str))
    self._qobuz_input.setPlaceholderText("Optional — may be left empty")
    self._qobuz_input.setEchoMode(LineEdit.EchoMode.Password)
    self._qobuz_input.setToolTip(
        "Optional Qobuz authentication token for better metadata quality"
    )
    c2.addWidget(self._qobuz_input)

    root.addWidget(card2)
    root.addStretch(1)
    return _scroll(w)


def build_lyrics_tab(self) -> QWidget:
    w = QWidget()
    root = QVBoxLayout(w)
    root.setContentsMargins(20, 14, 20, 14)
    root.setSpacing(10)
    root.setAlignment(Qt.AlignmentFlag.AlignTop)

    page_title = QLabel("Lyrics")
    page_title.setObjectName("h1")
    root.addWidget(page_title)

    card1, c1 = self._create_card()
    _tighten_card(c1)

    self._cb_lyrics = TickCheckBox("Embed lyrics into the FLAC/MP3 file")
    self._cb_lyrics.setChecked(
        self._settings.value("embed_lyrics", False, type=bool)
    )
    self._cb_lyrics.setToolTip(
        "Embed synchronized lyrics (LRC) or plain lyrics into the audio file"
    )
    c1.addWidget(self._cb_lyrics)

    title = QLabel("Provider Order")
    title.setObjectName("h2")
    c1.addWidget(title)
    desc = QLabel("Drag chips to reorder. Click to toggle providers.")
    desc.setObjectName("muted")
    c1.addWidget(desc)
    lyr_default = (
        self._settings.value("lyrics_providers", LYRICS_ALL, type=list)
        or LYRICS_ALL
    )
    lyr_default = [s for s in lyr_default if s in LYRICS_ALL]
    self._lyrics_list = ToggleList(LYRICS_ALL, lyr_default)
    c1.addWidget(self._lyrics_list)

    root.addWidget(card1)

    card2, c2 = self._create_card()
    _tighten_card(c2)

    tok_title = QLabel("Spotify Token")
    tok_title.setObjectName("h2")
    c2.addWidget(tok_title)

    self._spot_token_input = LineEdit()
    self._spot_token_input.setText(
        self._settings.value("lyrics_spotify_token", "", type=str)
    )
    self._spot_token_input.setPlaceholderText(
        "Optional — sp_dc cookie for Spotify lyrics"
    )
    self._spot_token_input.setEchoMode(LineEdit.EchoMode.Password)
    self._spot_token_input.setToolTip(
        "Spotify sp_dc cookie for fetching synced lyrics from Spotify"
    )
    c2.addWidget(self._spot_token_input)

    root.addWidget(card2)
    root.addStretch(1)
    return _scroll(w)


def build_advanced_tab(self) -> QWidget:
    w = QWidget()
    root = QVBoxLayout(w)
    root.setContentsMargins(20, 14, 20, 14)
    root.setSpacing(10)
    root.setAlignment(Qt.AlignmentFlag.AlignTop)

    page_title = QLabel("Advanced Settings")
    page_title.setObjectName("h1")
    root.addWidget(page_title)

    card1, c1 = self._create_card()
    _tighten_card(c1)

    self._cb_fallback = TickCheckBox("Fall back to other services on failure")
    self._cb_fallback.setChecked(
        self._settings.value("allow_fallback", True, type=bool)
    )
    c1.addWidget(self._cb_fallback)
    c1.addSpacing(4)

    delay_value = self._settings.value("inter_track_delay_s", 0.0, type=float)
    self._delay_combo = ComboBox()
    self._delay_combo.addItems(["0.0 s", "0.5 s", "1.0 s"])
    self._delay_combo.setCurrentText(f"{delay_value:.1f} s" if delay_value in (0.0, 0.5, 1.0) else "0.0 s")
    self._add_setting_row(c1, "Inter-Track Delay", self._delay_combo)

    self._loglevel_combo = ComboBox()
    self._loglevel_combo.addItems(["WARNING", "INFO", "DEBUG"])
    self._loglevel_combo.setCurrentText(
        self._settings.value("log_level", "WARNING", type=str)
    )
    self._add_setting_row(c1, "Log Level", self._loglevel_combo)

    self._cb_show_log = TickCheckBox("Show activity log panel")
    self._cb_show_log.setChecked(
        self._settings.value("show_activity_log", True, type=bool)
    )
    self._cb_show_log.setToolTip(
        "Show the live activity/terminal-style log panel in the sidebar"
    )
    self._add_setting_row(c1, "Activity Panel", self._cb_show_log)

    root.addWidget(card1)

    card2, c2 = self._create_card()
    _tighten_card(c2)

    self._concurrent_combo = ComboBox()
    self._concurrent_combo.addItems(["1", "2", "3"])
    current_concurrent = str(self._settings.value("concurrent_downloads", 2, type=int))
    self._concurrent_combo.setCurrentText(current_concurrent if current_concurrent in {"1", "2", "3"} else "2")
    self._add_setting_row(c2, "Concurrent Downloads", self._concurrent_combo)

    hint = QLabel(
        "Cooldown pauses downloads after every N tracks to avoid rate limits.\n"
        "Default is disabled for maximum speed."
    )
    hint.setObjectName("muted")
    hint.setWordWrap(True)
    c2.addWidget(hint)

    root.addWidget(card2)
    root.addStretch(1)
    return _scroll(w)

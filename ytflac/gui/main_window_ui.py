from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListView,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .components import LogPanel
from .fluent import (
    ComboBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    TransparentPushButton,
)
from .main_window_shared import _resource_path


def _build_ui(self):
    central = QWidget()
    self.setCentralWidget(central)
    outer = QVBoxLayout(central)
    outer.setContentsMargins(24, 24, 24, 24)
    outer.setSpacing(20)

    logo_path = _resource_path("images", "APPLOGO.png")
    logo_lbl = QLabel()
    if os.path.exists(logo_path):
        px = QPixmap(logo_path).scaled(
            60,
            60,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        logo_lbl.setPixmap(px)
    logo_lbl.setFixedSize(64, 64)

    shadow = QGraphicsDropShadowEffect(logo_lbl)
    shadow.setBlurRadius(14)
    shadow.setColor(QColor(64, 62, 58, 90))
    shadow.setOffset(0, 4)
    logo_lbl.setGraphicsEffect(shadow)

    title = QLabel("YtFLAC")
    title.setObjectName("h1")

    head_text = QVBoxLayout()
    head_text.setSpacing(0)
    head_text.addWidget(title)

    self._info_btn = TransparentPushButton(" Info")
    self._info_btn.setObjectName("ghost")
    self._info_btn.clicked.connect(self._open_info)
    self._set_button_icon(self._info_btn, "fa5s.info-circle")

    self._terminal_btn = TransparentPushButton(" Terminal")
    self._terminal_btn.setObjectName("ghost")
    self._terminal_btn.clicked.connect(self._open_terminal_page)
    self._set_button_icon(self._terminal_btn, "fa5s.terminal")

    self._settings_btn = TransparentPushButton(" Settings")
    self._settings_btn.setObjectName("ghost")
    self._settings_btn.clicked.connect(self._open_settings)
    self._set_button_icon(self._settings_btn, "fa5s.cog")

    head_actions = QHBoxLayout()
    head_actions.setSpacing(8)
    head_actions.addWidget(self._info_btn)
    head_actions.addWidget(self._terminal_btn)
    head_actions.addWidget(self._settings_btn)

    head = QHBoxLayout()
    head.setSpacing(8)
    head.addWidget(logo_lbl)
    head.addLayout(head_text, stretch=1)
    head.addLayout(head_actions)
    outer.addLayout(head)

    self._activity_wrap = QFrame()
    self._activity_wrap.setObjectName("card")
    activity_col = QVBoxLayout(self._activity_wrap)
    activity_col.setContentsMargins(14, 14, 14, 14)
    activity_col.setSpacing(10)

    log_header = QHBoxLayout()
    log_header.setSpacing(8)
    log_lbl = QLabel("Activity")
    log_lbl.setObjectName("section")
    log_header.addWidget(log_lbl)
    log_header.addStretch()
    clear_btn = PushButton("Clear")
    clear_btn.setObjectName("secondary")
    clear_btn.setFixedHeight(28)
    log_header.addWidget(clear_btn)
    activity_col.addLayout(log_header)

    self._log_panel = LogPanel()
    self._log_panel.setMinimumHeight(108)
    self._log_panel.setMaximumHeight(172)
    clear_btn.clicked.connect(self._log_panel.clear)
    activity_col.addWidget(self._log_panel)

    outer.addWidget(self._activity_wrap)
    self._apply_activity_visibility(
        self._settings.value("show_activity_log", True, type=bool)
    )

    body = QHBoxLayout()
    body.setSpacing(14)
    outer.addLayout(body, stretch=1)

    body.addWidget(self._build_sidebar(), alignment=Qt.AlignmentFlag.AlignTop)
    body.addLayout(self._build_right_column(), stretch=1)


def _build_sidebar(self) -> QFrame:
    frame = QFrame()
    frame.setObjectName("sidebar")
    frame.setMinimumWidth(250)
    frame.setMaximumWidth(380)
    frame.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Expanding,
    )

    inner = QVBoxLayout(frame)
    inner.setContentsMargins(20, 20, 20, 20)
    inner.setSpacing(16)

    self._hamburger_btn = TransparentPushButton("☰")
    self._hamburger_btn.setObjectName("ghost")
    self._hamburger_btn.setFixedSize(32, 32)
    self._hamburger_btn.setToolTip("Toggle sidebar")
    self._hamburger_btn.clicked.connect(self._toggle_sidebar)
    self._hamburger_btn.hide()
    inner.addWidget(self._hamburger_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    self._sidebar_content = QWidget()
    content_layout = QVBoxLayout(self._sidebar_content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(16)

    url_lbl = QLabel("URL")
    url_lbl.setObjectName("section")
    content_layout.addWidget(url_lbl)

    self._url_input = LineEdit()
    self._url_input.setPlaceholderText("Paste Spotify or YT Music link…")
    self._url_input.returnPressed.connect(self._on_preview)
    content_layout.addWidget(self._url_input)

    btns = QHBoxLayout()
    btns.setSpacing(8)

    self._preview_btn = PushButton("Preview")
    self._preview_btn.setObjectName("secondary")
    self._preview_btn.clicked.connect(self._on_preview)
    self._set_button_icon(self._preview_btn, "fa5s.search")
    btns.addWidget(self._preview_btn, stretch=1)

    self._refresh_btn = TransparentPushButton("")
    self._refresh_btn.setObjectName("ghost")
    self._refresh_btn.setFixedSize(32, 32)
    self._refresh_btn.setToolTip("Refresh — re-resolve this playlist to find new tracks")
    self._refresh_btn.setVisible(False)
    self._refresh_btn.clicked.connect(self._on_refresh)
    self._set_button_icon(self._refresh_btn, "fa5s.sync-alt")
    btns.addWidget(self._refresh_btn)
    content_layout.addLayout(btns)

    div1 = QFrame()
    div1.setObjectName("divider")
    content_layout.addWidget(div1)

    fmt_lbl = QLabel("Format")
    fmt_lbl.setObjectName("section")
    content_layout.addWidget(fmt_lbl)

    self._fmt_combo = ComboBox()
    self._fmt_combo.addItems(["FLAC", "MP3"])
    saved_fmt = self._settings.value("format", "FLAC", type=str)
    self._fmt_combo.setCurrentText(saved_fmt)
    self._fmt_combo.currentTextChanged.connect(self._on_format_changed)
    content_layout.addWidget(self._fmt_combo)

    qual_lbl = QLabel("Quality")
    qual_lbl.setObjectName("section")
    content_layout.addWidget(qual_lbl)

    self._qual_combo = ComboBox()
    self._qual_combo.addItems(["LOSSLESS", "HI_RES", "HIGH", "NORMAL"])
    # Set tooltips - qfluentwidgets.ComboBox may have different signature than PyQt6
    try:
        self._qual_combo.setItemData(0, "16-bit / 44.1 kHz FLAC", Qt.ItemDataRole.ToolTipRole)
        self._qual_combo.setItemData(1, "24-bit / up to 192 kHz", Qt.ItemDataRole.ToolTipRole)
        self._qual_combo.setItemData(2, "320 kbps lossy", Qt.ItemDataRole.ToolTipRole)
        self._qual_combo.setItemData(3, "128 kbps lossy", Qt.ItemDataRole.ToolTipRole)
    except Exception:
        # Fallback: tooltips not set if fluent ComboBox doesn't support 3-arg setItemData
        pass
    saved_qual = self._settings.value("quality", "LOSSLESS", type=str)
    self._qual_combo.setCurrentText(saved_qual)
    self._qual_combo.currentTextChanged.connect(
        lambda v: self._settings.setValue("quality", v)
    )
    content_layout.addWidget(self._qual_combo)

    self._on_format_changed(saved_fmt)

    content_layout.addStretch(1)

    div2 = QFrame()
    div2.setObjectName("divider")
    content_layout.addWidget(div2)

    self._progress_bar = QProgressBar()
    self._progress_bar.setRange(0, 100)
    self._progress_bar.setValue(0)
    self._progress_bar.setTextVisible(False)
    self._progress_bar.setVisible(False)
    content_layout.addWidget(self._progress_bar)

    self._status_lbl = QLabel("")
    self._status_lbl.setObjectName("muted")
    self._status_lbl.setWordWrap(True)
    content_layout.addWidget(self._status_lbl)

    self._dl_btn = PrimaryPushButton("Download")
    self._dl_btn.setObjectName("primary")
    self._dl_btn.setFixedHeight(48)
    self._dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._dl_btn.setEnabled(False)
    self._dl_btn.clicked.connect(self._on_download)
    self._set_button_icon(self._dl_btn, "fa5s.download")
    content_layout.addWidget(self._dl_btn)

    self._stop_btn = PushButton("Stop")
    self._stop_btn.setObjectName("danger")
    self._stop_btn.setFixedHeight(42)
    self._stop_btn.setVisible(False)
    self._stop_btn.clicked.connect(self._on_stop)
    self._set_button_icon(self._stop_btn, "fa5s.stop")
    content_layout.addWidget(self._stop_btn)

    inner.addWidget(self._sidebar_content)

    self._sidebar_collapsed = False

    return frame


def _on_format_changed(self, fmt: str):
    self._settings.setValue("format", fmt)
    is_flac = (fmt or "").upper() == "FLAC"
    self._qual_combo.setEnabled(is_flac)
    if not is_flac:
        self._qual_combo.setToolTip("Quality is fixed for MP3 (320 kbps)")
    else:
        self._qual_combo.setToolTip("")


def _build_right_column(self) -> QVBoxLayout:
    col = QVBoxLayout()
    col.setSpacing(12)
    col.setContentsMargins(24, 0, 0, 0)

    self._stack = QStackedWidget()

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

    icon_lbl = QLabel()
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_path = _resource_path("images", "appinico2.png")
    if os.path.exists(icon_path):
        ipx = QPixmap(icon_path).scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        icon_lbl.setPixmap(ipx)
    ec.addWidget(icon_lbl)

    title_lbl = QLabel("Paste URL to begin")
    title_lbl.setObjectName("h2")
    title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ec.addWidget(title_lbl)

    ev.addWidget(empty_card)
    ev.addStretch(2)
    self._stack.addWidget(empty_page)

    self._empty_opacity = QGraphicsOpacityEffect(empty_page)
    self._empty_opacity.setOpacity(1)
    empty_page.setGraphicsEffect(self._empty_opacity)

    results_page = QWidget()
    rl = QVBoxLayout(results_page)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(8)

    self._header_box = QVBoxLayout()
    self._header_box.setContentsMargins(0, 0, 0, 0)
    rl.addLayout(self._header_box)

    self._search_input = LineEdit()
    self._search_input.setObjectName("search")
    self._search_input.setPlaceholderText("🔎  Filter tracks…")
    self._search_input.textChanged.connect(self._on_search_changed)
    self._search_input.setClearButtonEnabled(True)

    self._deselect_btn = TransparentPushButton("Deselect All")
    self._deselect_btn.setObjectName("ghost")
    self._deselect_btn.setFixedHeight(32)
    self._deselect_btn.clicked.connect(self._deselect_all)
    self._set_button_icon(self._deselect_btn, "fa5s.square")

    self._clear_list_btn = TransparentPushButton("Clear List")
    self._clear_list_btn.setObjectName("ghost")
    self._clear_list_btn.setFixedHeight(32)
    self._clear_list_btn.clicked.connect(self._clear_results)
    self._set_button_icon(self._clear_list_btn, "fa5s.trash")

    self._invert_btn = TransparentPushButton("Invert")
    self._invert_btn.setObjectName("ghost")
    self._invert_btn.setFixedHeight(32)
    self._invert_btn.clicked.connect(self._invert_selection)
    self._set_button_icon(self._invert_btn, "fa5s.exchange-alt")

    sel_row = QHBoxLayout()
    sel_row.setSpacing(8)
    sel_row.addWidget(self._search_input, stretch=1)
    sel_row.addWidget(self._deselect_btn)
    sel_row.addWidget(self._clear_list_btn)
    sel_row.addWidget(self._invert_btn)
    rl.addLayout(sel_row)

    self._track_view = QListView()
    self._track_view.setObjectName("trackListView")
    self._track_view.setUniformItemSizes(True)
    self._track_view.setAlternatingRowColors(False)
    self._track_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self._track_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
    self._track_view.setModel(self._track_proxy)
    self._track_view.setItemDelegate(self._track_delegate)
    self._track_view.clicked.connect(self._on_track_item_clicked)
    rl.addWidget(self._track_view, stretch=1)

    self._stack.addWidget(results_page)

    self._results_opacity = QGraphicsOpacityEffect(results_page)
    self._results_opacity.setOpacity(0)
    results_page.setGraphicsEffect(self._results_opacity)

    terminal_page = QWidget()
    tl = QVBoxLayout(terminal_page)
    tl.setContentsMargins(0, 0, 0, 0)
    tl.setSpacing(8)

    terminal_hdr = QHBoxLayout()
    terminal_hdr.setSpacing(8)

    terminal_title = QLabel("Terminal")
    terminal_title.setObjectName("h2")
    terminal_hdr.addWidget(terminal_title)
    terminal_hdr.addStretch(1)

    self._terminal_back_btn = TransparentPushButton("Back")
    self._terminal_back_btn.setObjectName("ghost")
    self._terminal_back_btn.setFixedHeight(32)
    self._terminal_back_btn.clicked.connect(self._close_terminal_page)
    self._set_button_icon(self._terminal_back_btn, "fa5s.arrow-left")
    terminal_hdr.addWidget(self._terminal_back_btn)

    self._terminal_clear_btn = PushButton("Clear")
    self._terminal_clear_btn.setObjectName("secondary")
    self._terminal_clear_btn.setFixedHeight(32)
    self._terminal_clear_btn.clicked.connect(self._clear_terminal_logs)
    terminal_hdr.addWidget(self._terminal_clear_btn)

    tl.addLayout(terminal_hdr)

    self._terminal_log_panel = LogPanel(max_lines=5000, compact=False)
    tl.addWidget(self._terminal_log_panel, stretch=1)

    self._stack.addWidget(terminal_page)

    self._terminal_opacity = QGraphicsOpacityEffect(terminal_page)
    self._terminal_opacity.setOpacity(0)
    terminal_page.setGraphicsEffect(self._terminal_opacity)

    col.addWidget(self._stack, stretch=1)

    return col

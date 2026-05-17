from __future__ import annotations
import os
import sys

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QWidget,
    QProgressBar,
)

from .. import style as S
from .thumbnail import load_thumbnail, rounded_pixmap
from .tick_checkbox import TickCheckBox


def _res(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "images", name)

STATUS_IDLE = "idle"
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

_STATUS_GLYPH = {
    STATUS_IDLE: ("·", S.TEXT_FAINT),
    STATUS_QUEUED: ("·", S.TEXT_DIM),
    STATUS_RUNNING: ("", S.ACCENT),
    STATUS_DONE: ("✓", S.SUCCESS),
    STATUS_FAILED: ("x", S.ERROR),
}

_STATUS_TEXT = {
    STATUS_IDLE: "",
    STATUS_QUEUED: "Queued",
    STATUS_RUNNING: "Downloading",
    STATUS_DONE: "Downloaded",
    STATUS_FAILED: "Failed",
}

class Spinner(QWidget):
    """Lightweight indeterminate spinner — small rotating arc."""
    def __init__(self, size: int = 14, color: str = S.ACCENT, parent=None):
        super().__init__(parent)
        self._size = size
        self._color = QColor(color)
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        self._timer.start(60)
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin = 2
        rect = self.rect().adjusted(margin, margin, -margin, -margin)
        pen = QPen(self._color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        start_angle = -self._angle * 16
        span_angle = -270 * 16
        p.drawArc(rect, start_angle, span_angle)
        p.end()

class TrackRow(QFrame):
    toggled = pyqtSignal(int, bool)
    failure_clicked = pyqtSignal(int)

    def __init__(self, index: int, track, parent=None):
        super().__init__(parent)
        self.setObjectName("row")
        self._index = index
        self._track = track
        self._error_msg: str = ""
        self.setFixedHeight(58)

        self._search_blob = " ".join(
            [
                getattr(track, "title", "") or "",
                getattr(track, "artists", "") or getattr(track, "artist", "") or "",
                getattr(track, "album", "") or "",
            ]
        ).lower()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 12, 6)
        layout.setSpacing(12)

        self._cb = TickCheckBox()
        self._cb.setChecked(True)
        self._cb.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self._cb)

        idx_lbl = QLabel(f"{index:02d}")
        idx_lbl.setObjectName("faint")
        idx_lbl.setFixedWidth(28)
        idx_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(idx_lbl)

        self._thumb = QLabel()
        self._thumb.setFixedSize(40, 40)
        self._thumb.setStyleSheet(f"background: {S.BG_ELEV}; border-radius: 6px; border: none;")
        layout.addWidget(self._thumb)

        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)
        self._title_lbl = QLabel(track.title)
        self._title_lbl.setStyleSheet(f"color: {S.TEXT}; font-size: 13px; font-weight: 500; background: transparent;")
        self._title_lbl.setSizePolicy(
            self._title_lbl.sizePolicy().horizontalPolicy(),
            self._title_lbl.sizePolicy().verticalPolicy(),
        )

        artist = track.artists if hasattr(track, "artists") else getattr(track, "artist", "")
        album = getattr(track, "album", "") or ""
        sub_text = artist
        if album:
            sub_text = f"{artist}  ·  {album}" if artist else album
        self._artist_lbl = QLabel(sub_text)
        self._artist_lbl.setObjectName("faint")
        col.addWidget(self._title_lbl)
        col.addWidget(self._artist_lbl)
        layout.addLayout(col, stretch=1)

        confidence = getattr(track, "match_confidence", 100)
        source = getattr(track, "match_source", "spotify")
        self._warn_lbl = QLabel("")
        self._warn_lbl.setFixedWidth(20)
        self._warn_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if source == "youtube" and confidence < 60:
            self._warn_lbl.setText("⚠")
            self._warn_lbl.setStyleSheet(f"color: {S.WARNING}; font-size: 13px; background: transparent;")
            self._warn_lbl.setToolTip(f"Low-confidence match ({confidence}%) — may be wrong track")
        layout.addWidget(self._warn_lbl)

        dur_ms = getattr(track, "duration_ms", 0) or 0
        if dur_ms > 0:
            sec = dur_ms // 1000
            dur_txt = f"{sec // 60}:{sec % 60:02d}"
        else:
            dur_txt = ""
        self._dur_lbl = QLabel(dur_txt)
        self._dur_lbl.setObjectName("faint")
        self._dur_lbl.setFixedWidth(44)
        self._dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._dur_lbl)

        self._status_wrap = QWidget()
        self._status_wrap.setFixedWidth(112)
        sw = QHBoxLayout(self._status_wrap)
        sw.setContentsMargins(0, 0, 0, 0)
        sw.setSpacing(6)
        sw.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status_lbl = QLabel("·")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner = Spinner(14, S.ACCENT)
        self._status_text_lbl = QLabel("")
        self._status_text_lbl.setStyleSheet(f"color: {S.TEXT_DIM}; font-size: 11px; background: transparent;")
        sw.addWidget(self._status_lbl)
        sw.addWidget(self._spinner)
        sw.addWidget(self._status_text_lbl)
        layout.addWidget(self._status_wrap)
        
        # Progress bar for per-track download progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: transparent;
                border: none;
                border-radius: 1px;
            }}
            QProgressBar::chunk {{
                background: {S.ACCENT};
                border-radius: 1px;
            }}
        """)
        self._progress_bar.hide()
        
        # Add progress bar below the main row
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        row_widget = QWidget()
        row_widget.setLayout(layout)
        outer_layout.addWidget(row_widget)
        outer_layout.addWidget(self._progress_bar)
        
        self.set_status(STATUS_IDLE)

        if source == "youtube" and confidence < 60:
            self.setProperty("dlState", "lowConf")
            self.style().unpolish(self)
            self.style().polish(self)

        cover = getattr(track, "cover_url", "") or ""
        if cover:
            load_thumbnail(cover, 40, self._set_cover)
        else:
            default_cover = _res("1.png")
            if os.path.exists(default_cover):
                pm = QPixmap(default_cover).scaled(
                    40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self._set_cover(pm)

    def index(self) -> int:
        return self._index

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def set_checked(self, val: bool):
        self._cb.setChecked(val)

    def _on_checkbox_changed(self, state: int):
        checked = bool(state)
        self.toggled.emit(self._index, checked)

    def matches(self, needle: str) -> bool:
        if not needle:
            return True
        return needle in self._search_blob

    def error_message(self) -> str:
        return self._error_msg

    def set_status(self, status: str, tooltip: str = ""):
        glyph, color = _STATUS_GLYPH.get(status, _STATUS_GLYPH[STATUS_IDLE])
        status_text = _STATUS_TEXT.get(status, "")

        self.setProperty("dlState", status)
        self.style().unpolish(self)
        self.style().polish(self)

        if status == STATUS_DONE:
            self._status_text_lbl.setStyleSheet(f"color: {S.SUCCESS}; font-size: 11px; font-weight: 600; background: transparent;")
        elif status == STATUS_FAILED:
            self._status_text_lbl.setStyleSheet(f"color: {S.ERROR}; font-size: 11px; font-weight: 600; background: transparent;")
        elif status == STATUS_RUNNING:
            self._status_text_lbl.setStyleSheet(f"color: {S.ACCENT}; font-size: 11px; font-weight: 600; background: transparent;")
        else:
            self._status_text_lbl.setStyleSheet(f"color: {S.TEXT_DIM}; font-size: 11px; background: transparent;")
        self._status_text_lbl.setText(status_text)

        if status == STATUS_RUNNING:
            self._status_lbl.setText("")
            self._status_lbl.hide()
            self._spinner.start()
            self._progress_bar.show()
        else:
            self._spinner.stop()
            self._status_lbl.setText(glyph)
            self._status_lbl.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent; border: none;")
            self._status_lbl.show()
            self._progress_bar.hide()
            self._progress_bar.setValue(0)

        if status == STATUS_FAILED:
            self._error_msg = tooltip or ""
            self._status_wrap.setCursor(Qt.CursorShape.PointingHandCursor)
            self._status_wrap.setToolTip("Failed — click for details")
        else:
            self._error_msg = ""
            self._status_wrap.setCursor(Qt.CursorShape.ArrowCursor)
            if tooltip:
                self._status_wrap.setToolTip(tooltip)
            elif status == STATUS_DONE:
                self._status_wrap.setToolTip("Downloaded successfully")
            elif status == STATUS_RUNNING:
                self._status_wrap.setToolTip("Downloading")
            else:
                self._status_wrap.setToolTip("")

    def set_progress(self, value: int) -> None:
        """Update the progress bar value (0-100)."""
        self._progress_bar.setValue(value)

    def mousePressEvent(self, ev):
        if self._error_msg:
            try:
                pos = ev.position().toPoint()
            except AttributeError:
                pos = ev.pos()
            if self._status_wrap.geometry().contains(pos):
                self.failure_clicked.emit(self._index)
                return
        super().mousePressEvent(ev)

    def _set_cover(self, pm: QPixmap):
        self._thumb.setPixmap(rounded_pixmap(pm, 6))

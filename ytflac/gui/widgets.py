"""
Custom widgets for the YtFLAC GUI.
"""
from __future__ import annotations
import urllib.request

from PyQt6.QtCore import (
    Qt, pyqtSignal, QObject, QRunnable, QThreadPool, QTimer,
)
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QWidget,
)

from . import style as S


# --- Thumbnail loader ------------------------------------------------------

class _ThumbSignals(QObject):
    done = pyqtSignal(str, QPixmap)


class _ThumbLoader(QRunnable):
    def __init__(self, url: str, size: int):
        super().__init__()
        self._url = url
        self._size = size
        self.signals = _ThumbSignals()

    def run(self):
        try:
            req = urllib.request.Request(
                self._url, headers={"User-Agent": "YtFLAC/1.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            pm = QPixmap()
            pm.loadFromData(data)
            if not pm.isNull():
                pm = pm.scaled(
                    self._size, self._size,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = (pm.width() - self._size) // 2
                y = (pm.height() - self._size) // 2
                pm = pm.copy(x, y, self._size, self._size)
                self.signals.done.emit(self._url, pm)
        except Exception:
            pass


_thumb_pool = QThreadPool.globalInstance()
_thumb_cache: dict[str, QPixmap] = {}


def load_thumbnail(url: str, size: int, callback):
    if not url:
        return
    key = f"{url}@{size}"
    if key in _thumb_cache:
        callback(_thumb_cache[key])
        return
    loader = _ThumbLoader(url, size)

    def _done(_u, pm):
        _thumb_cache[key] = pm
        callback(pm)

    loader.signals.done.connect(_done)
    _thumb_pool.start(loader)


def rounded_pixmap(pm: QPixmap, radius: int = 8) -> QPixmap:
    if pm.isNull():
        return pm
    out = QPixmap(pm.size())
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pm.width(), pm.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pm)
    painter.end()
    return out


# --- Track row -------------------------------------------------------------

STATUS_IDLE     = "idle"
STATUS_QUEUED   = "queued"
STATUS_RUNNING  = "running"
STATUS_DONE     = "done"
STATUS_FAILED   = "failed"

_STATUS_GLYPH = {
    STATUS_IDLE:    ("·",  S.TEXT_FAINT),
    STATUS_QUEUED:  ("·",  S.TEXT_DIM),
    STATUS_RUNNING: ("",   S.ACCENT),   # rendered as spinner
    STATUS_DONE:    ("✓",  S.SUCCESS),
    STATUS_FAILED:  ("×",  S.ERROR),
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
        # 270° arc, rotating
        start_angle = -self._angle * 16
        span_angle = -270 * 16
        p.drawArc(rect, start_angle, span_angle)
        p.end()


class TrackRow(QFrame):
    toggled = pyqtSignal(int, bool)  # index, checked
    failure_clicked = pyqtSignal(int)  # 1-based index — emitted when user clicks the failed status

    def __init__(self, index: int, track, parent=None):
        super().__init__(parent)
        self.setObjectName("row")
        self._index = index
        self._track = track
        self._error_msg: str = ""
        self.setFixedHeight(58)

        # Cached searchable text
        self._search_blob = " ".join([
            getattr(track, "title", "") or "",
            getattr(track, "artists", "") or getattr(track, "artist", "") or "",
            getattr(track, "album", "") or "",
        ]).lower()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 12, 6)
        layout.setSpacing(12)

        # Checkbox
        self._cb = QCheckBox()
        self._cb.setChecked(True)
        self._cb.stateChanged.connect(
            lambda s: self.toggled.emit(self._index, bool(s))
        )
        layout.addWidget(self._cb)

        # Index
        idx_lbl = QLabel(f"{index:02d}")
        idx_lbl.setObjectName("faint")
        idx_lbl.setFixedWidth(28)
        idx_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(idx_lbl)

        # Thumbnail
        self._thumb = QLabel()
        self._thumb.setFixedSize(40, 40)
        self._thumb.setStyleSheet(
            f"background: {S.BG_ELEV}; border-radius: 6px; border: none;"
        )
        layout.addWidget(self._thumb)

        # Title + artist · album
        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)
        self._title_lbl = QLabel(track.title)
        self._title_lbl.setStyleSheet(
            f"color: {S.TEXT}; font-size: 13px; font-weight: 500; background: transparent;"
        )
        self._title_lbl.setSizePolicy(self._title_lbl.sizePolicy().horizontalPolicy(),
                                     self._title_lbl.sizePolicy().verticalPolicy())

        artist = track.artists if hasattr(track, "artists") else getattr(track, "artist", "")
        album  = getattr(track, "album", "") or ""
        sub_text = artist
        if album:
            sub_text = f"{artist}  ·  {album}" if artist else album
        self._artist_lbl = QLabel(sub_text)
        self._artist_lbl.setObjectName("faint")
        col.addWidget(self._title_lbl)
        col.addWidget(self._artist_lbl)
        layout.addLayout(col, stretch=1)

        # Duration
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

        # Status — glyph label + spinner share the same slot
        self._status_wrap = QWidget()
        self._status_wrap.setFixedWidth(20)
        sw = QHBoxLayout(self._status_wrap)
        sw.setContentsMargins(0, 0, 0, 0)
        sw.setSpacing(0)
        sw.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._status_lbl = QLabel("·")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner = Spinner(14, S.ACCENT)
        sw.addWidget(self._status_lbl)
        sw.addWidget(self._spinner)
        layout.addWidget(self._status_wrap)
        self.set_status(STATUS_IDLE)

        # Async cover
        cover = getattr(track, "cover_url", "") or ""
        if cover:
            load_thumbnail(cover, 40, self._set_cover)

    # --- API -------------------------------------------------------------

    def index(self) -> int:
        return self._index

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def set_checked(self, val: bool):
        self._cb.setChecked(val)

    def matches(self, needle: str) -> bool:
        if not needle:
            return True
        return needle in self._search_blob

    def error_message(self) -> str:
        return self._error_msg

    def set_status(self, status: str, tooltip: str = ""):
        glyph, color = _STATUS_GLYPH.get(status, _STATUS_GLYPH[STATUS_IDLE])
        if status == STATUS_RUNNING:
            self._status_lbl.setText("")
            self._status_lbl.hide()
            self._spinner.start()
        else:
            self._spinner.stop()
            self._status_lbl.setText(glyph)
            self._status_lbl.setStyleSheet(
                f"color: {color}; font-size: 14px; background: transparent; border: none;"
            )
            self._status_lbl.show()

        # Track failure detail
        if status == STATUS_FAILED:
            self._error_msg = tooltip or ""
            self._status_wrap.setCursor(Qt.CursorShape.PointingHandCursor)
            self._status_wrap.setToolTip("Click for details")
        else:
            self._error_msg = ""
            self._status_wrap.setCursor(Qt.CursorShape.ArrowCursor)
            if tooltip:
                self._status_wrap.setToolTip(tooltip)
            else:
                self._status_wrap.setToolTip("")

    # Clicking the failed status icon → emit signal
    def mousePressEvent(self, ev):
        # Only respond when this row has a failure to show
        if self._error_msg:
            try:
                pos = ev.position().toPoint()
            except AttributeError:
                pos = ev.pos()
            if self._status_wrap.geometry().contains(pos):
                self.failure_clicked.emit(self._index)
                return
        super().mousePressEvent(ev)

    # --- Internals -------------------------------------------------------

    def _set_cover(self, pm: QPixmap):
        self._thumb.setPixmap(rounded_pixmap(pm, 6))


# --- Playlist header -------------------------------------------------------

class PlaylistHeader(QFrame):
    def __init__(self, name: str, cover: str, count: int,
                 unmatched: int, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(108)
        self._count = count

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(16)

        self._cover = QLabel()
        self._cover.setFixedSize(80, 80)
        self._cover.setStyleSheet(
            f"background: {S.BG}; border-radius: 10px; border: none;"
        )
        layout.addWidget(self._cover)

        info = QVBoxLayout()
        info.setSpacing(4)
        info.setContentsMargins(0, 4, 0, 4)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("h2")
        name_lbl.setWordWrap(False)
        info.addWidget(name_lbl)

        meta = f"{count} track" + ("" if count == 1 else "s")
        meta_lbl = QLabel(meta)
        meta_lbl.setObjectName("muted")
        info.addWidget(meta_lbl)
        info.addStretch()

        # Badge row: selection counter + unmatched warning
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        badge_row.setContentsMargins(0, 0, 0, 0)

        self._sel_badge = QLabel(f"{count} selected")
        self._sel_badge.setObjectName("badge_accent")
        badge_row.addWidget(self._sel_badge)

        if unmatched > 0:
            unm_badge = QLabel(f"{unmatched} unmatched")
            unm_badge.setObjectName("badge_warn")
            badge_row.addWidget(unm_badge)

        badge_row.addStretch()
        info.addLayout(badge_row)

        layout.addLayout(info, stretch=1)

        if cover:
            load_thumbnail(cover, 80, self._set_cover)

    def set_selection_count(self, n: int):
        self._sel_badge.setText(f"{n} selected")

    def _set_cover(self, pm: QPixmap):
        self._cover.setPixmap(rounded_pixmap(pm, 10))


# --- Service priority bar --------------------------------------------------

class ServicePriorityBar(QListWidget):
    """
    Drag-reorderable horizontal chip list.
    Click to toggle enabled / disabled (visual dim).
    """
    changed = pyqtSignal()

    def __init__(self, services: list[str],
                 enabled: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("chips")
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setMovement(QListWidget.Movement.Snap)
        self.setSpacing(4)
        self.setFixedHeight(38)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        enabled_set = set(enabled if enabled is not None else services)
        for svc in services:
            self._add_chip(svc, svc in enabled_set)

        self.itemClicked.connect(self._toggle_item)
        self.model().rowsMoved.connect(lambda *_: self.changed.emit())

    def _add_chip(self, name: str, on: bool):
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, on)
        self._apply_visual(item, on)
        self.addItem(item)

    def _toggle_item(self, item: QListWidgetItem):
        on = not bool(item.data(Qt.ItemDataRole.UserRole))
        item.setData(Qt.ItemDataRole.UserRole, on)
        self._apply_visual(item, on)
        self.changed.emit()

    @staticmethod
    def _apply_visual(item: QListWidgetItem, on: bool):
        if on:
            item.setForeground(QColor(S.TEXT))
        else:
            item.setForeground(QColor(S.TEXT_FAINT))

    def ordered_services(self) -> list[str]:
        return [self.item(i).text() for i in range(self.count())]

    def enabled_services(self) -> list[str]:
        return [
            self.item(i).text()
            for i in range(self.count())
            if bool(self.item(i).data(Qt.ItemDataRole.UserRole))
        ]

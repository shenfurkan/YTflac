from __future__ import annotations

from PyQt6.QtCore import QEvent, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate

from .. import style as S
from ..components.thumbnail import load_thumbnail
from ..models import TrackListRoles


class TrackItemDelegate(QStyledItemDelegate):
    failureClicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._covers: dict[str, QPixmap | None] = {}
        self._viewport = None

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 82)

    def _row_rect(self, rect: QRect) -> QRect:
        return rect.adjusted(6, 4, -6, -4)

    def _checkbox_rect(self, rect: QRect) -> QRect:
        row_rect = self._row_rect(rect)
        return QRect(row_rect.left() + 14, row_rect.top() + 28, 20, 20)

    def _status_rect(self, rect: QRect) -> QRect:
        row_rect = self._row_rect(rect)
        return QRect(row_rect.right() - 110, row_rect.top() + 26, 94, 26)

    def _cover_rect(self, rect: QRect) -> QRect:
        row_rect = self._row_rect(rect)
        return QRect(row_rect.left() + 82, row_rect.top() + 12, 52, 52)

    def _color(self, value: str, fallback: str = "#000000", alpha: int | None = None) -> QColor:
        color = QColor(value)
        if not color.isValid():
            color = QColor(fallback)
        if alpha is not None:
            color.setAlpha(alpha)
        return color

    def _badge_width(self, text: str, font: QFont, minimum: int = 52) -> int:
        return max(minimum, QFontMetrics(font).horizontalAdvance(text) + 18)

    def _elided(self, text: str, font: QFont, width: int) -> str:
        return QFontMetrics(font).elidedText(text or "", Qt.TextElideMode.ElideRight, max(0, width))

    def _status_data(self, status: str) -> tuple[str, str, str]:
        if status == "queued":
            return "Queued", "…", S.TEXT_DIM
        if status == "running":
            return "Downloading", "↻", S.ACCENT
        if status == "done":
            return "Done", "✓", S.SUCCESS
        if status == "failed":
            return "Failed", "✗", S.ERROR
        return "Ready", "·", S.TEXT_FAINT

    def _request_cover(self, url: str, viewport) -> None:
        if not url or url in self._covers:
            return
        self._covers[url] = None
        self._viewport = viewport

        def _done(pm: QPixmap, cover_url: str = url):
            self._covers[cover_url] = pm
            target = self._viewport
            if target is not None:
                target.update()

        load_thumbnail(url, 52, _done)

    def _draw_rounded_pixmap(self, painter: QPainter, rect: QRect, pixmap: QPixmap, radius: int) -> None:
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(rect, pixmap)
        painter.restore()

    def _draw_badge(
        self,
        painter: QPainter,
        rect: QRect,
        text: str,
        fg: str,
        bg: str,
        border: str,
        font: QFont,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._color(border, S.LINE_STRONG)))
        painter.setBrush(self._color(bg, S.BG_MID))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setFont(font)
        painter.setPen(self._color(fg, S.TEXT_DIM))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        row_rect = self._row_rect(rect)

        track = index.data(TrackListRoles.TrackRole)
        row = int(index.data(TrackListRoles.IndexRole) or 0)
        checked = bool(index.data(TrackListRoles.CheckedRole))
        status = str(index.data(TrackListRoles.StatusRole) or "idle")
        progress = int(index.data(TrackListRoles.ProgressRole) or 0)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        title = getattr(track, "title", "") if track else ""
        artists = getattr(track, "artists", "") or getattr(track, "artist", "") or "" if track else ""
        album = getattr(track, "album", "") if track else ""
        source = getattr(track, "match_source", "spotify") if track else "spotify"
        confidence = int(getattr(track, "match_confidence", 100) or 0) if track else 100
        low_confidence = source == "youtube" and confidence < 60

        bg = S.BG_ELEV
        if hovered or selected:
            bg = S.BG_HOVER
        if low_confidence:
            bg = S.WARNING

        painter.setPen(QPen(self._color(S.LINE_STRONG if checked else S.LINE, S.TEXT_FAINT, 150 if checked else 90)))
        fill = self._color(bg, S.BG_ELEV, 30 if low_confidence else None)
        if not low_confidence:
            fill = self._color(bg, S.BG_ELEV)
        painter.setBrush(fill)
        painter.drawRoundedRect(row_rect, 12, 12)

        if checked:
            stripe = QRect(row_rect.left(), row_rect.top() + 10, 3, row_rect.height() - 20)
            painter.fillRect(stripe, self._color(S.ACCENT, S.TEXT))

        cb_rect = self._checkbox_rect(rect)
        painter.setPen(QPen(self._color(S.ACCENT if checked else S.LINE_STRONG, S.TEXT_DIM)))
        painter.setBrush(self._color(S.ACCENT if checked else S.BG, S.BG))
        painter.drawRoundedRect(cb_rect, 5, 5)
        if checked:
            check_font = QFont(option.font)
            check_font.setPointSize(11)
            check_font.setBold(True)
            painter.setFont(check_font)
            painter.setPen(self._color(S.BG, "#ffffff"))
            painter.drawText(cb_rect, int(Qt.AlignmentFlag.AlignCenter), "✓")

        idx_font = QFont(option.font)
        idx_font.setPointSize(10)
        idx_font.setBold(True)
        painter.setFont(idx_font)
        painter.setPen(self._color(S.TEXT_FAINT, "#888888"))
        idx_rect = QRect(cb_rect.right() + 10, row_rect.top(), 28, row_rect.height())
        painter.drawText(idx_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), f"{row + 1:02d}")

        cover_rect = self._cover_rect(rect)
        cover_url = getattr(track, "cover_url", "") if track else ""
        if cover_url:
            self._request_cover(cover_url, option.widget)
        cover = self._covers.get(cover_url) if cover_url else None
        if cover and not cover.isNull():
            self._draw_rounded_pixmap(painter, cover_rect, cover, 9)
        else:
            painter.setPen(QPen(self._color(S.LINE, S.TEXT_FAINT, 120)))
            painter.setBrush(self._color(S.BG_MID, S.BG))
            painter.drawRoundedRect(cover_rect, 9, 9)
            cover_font = QFont(option.font)
            cover_font.setPointSize(16)
            painter.setFont(cover_font)
            painter.setPen(self._color(S.TEXT_FAINT, "#888888"))
            painter.drawText(cover_rect, int(Qt.AlignmentFlag.AlignCenter), "♪")

        status_rect = self._status_rect(rect)
        duration_ms = int(getattr(track, "duration_ms", 0) or 0) if track else 0
        duration_text = ""
        if duration_ms > 0:
            seconds = duration_ms // 1000
            duration_text = f"{seconds // 60}:{seconds % 60:02d}"
        duration_rect = QRect(status_rect.left() - 56, row_rect.top() + 29, 42, 20)

        match_text = ""
        if source == "youtube":
            match_text = f"{confidence}% match"
        elif source == "manual":
            match_text = "Manual"
        badge_font = QFont(option.font)
        badge_font.setPointSize(9)
        badge_font.setBold(True)
        match_rect = QRect()
        if match_text:
            match_w = self._badge_width(match_text, badge_font, 66)
            match_rect = QRect(duration_rect.left() - match_w - 10, row_rect.top() + 26, match_w, 24)

        text_left = cover_rect.right() + 14
        text_right = match_rect.left() - 12 if match_text else duration_rect.left() - 12
        if text_right < text_left + 120:
            text_right = status_rect.left() - 24
        text_width = max(80, text_right - text_left)

        title_font = QFont(option.font)
        title_font.setPointSize(11)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(self._color(S.TEXT, "#222222"))
        painter.drawText(
            QRect(text_left, row_rect.top() + 13, text_width, 22),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._elided(title, title_font, text_width),
        )

        artist_font = QFont(option.font)
        artist_font.setPointSize(10)
        artist_font.setBold(True)
        painter.setFont(artist_font)
        painter.setPen(self._color(S.TEXT_DIM, "#666666"))
        painter.drawText(
            QRect(text_left, row_rect.top() + 35, text_width, 18),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._elided(artists, artist_font, text_width),
        )

        album_font = QFont(option.font)
        album_font.setPointSize(9)
        painter.setFont(album_font)
        painter.setPen(self._color(S.TEXT_FAINT, "#888888"))
        painter.drawText(
            QRect(text_left, row_rect.top() + 54, text_width, 16),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._elided(album, album_font, text_width),
        )

        if match_text:
            if low_confidence:
                self._draw_badge(painter, match_rect, match_text, S.WARNING, S.BG, S.WARNING, badge_font)
            else:
                self._draw_badge(painter, match_rect, match_text, S.TEXT_DIM, S.BG_MID, S.LINE, badge_font)

        if duration_text:
            duration_font = QFont(option.font)
            duration_font.setPointSize(9)
            painter.setFont(duration_font)
            painter.setPen(self._color(S.TEXT_FAINT, "#888888"))
            painter.drawText(duration_rect, int(Qt.AlignmentFlag.AlignCenter), duration_text)

        status_text, glyph, status_color = self._status_data(status)
        status_font = QFont(option.font)
        status_font.setPointSize(9)
        status_font.setBold(True)
        chip_bg = S.BG_MID
        chip_border = S.LINE
        if status == "done":
            chip_bg = S.SUCCESS_SOFT
            chip_border = S.SUCCESS
        elif status == "failed":
            chip_bg = S.ERROR_SOFT
            chip_border = S.ERROR
        elif status == "running":
            chip_bg = S.ACCENT_SOFT
            chip_border = S.ACCENT
        self._draw_badge(painter, status_rect, f"{glyph} {status_text}", status_color, chip_bg, chip_border, status_font)

        if status == "running":
            bar_rect = QRect(text_left, row_rect.bottom() - 7, max(40, status_rect.left() - text_left - 14), 3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._color(S.LINE, S.TEXT_FAINT, 110))
            painter.drawRoundedRect(bar_rect, 2, 2)
            fill_w = int(bar_rect.width() * (max(0, min(100, progress)) / 100.0))
            if fill_w > 0:
                painter.setBrush(self._color(S.ACCENT, S.TEXT))
                painter.drawRoundedRect(QRect(bar_rect.left(), bar_rect.top(), fill_w, bar_rect.height()), 2, 2)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() != QEvent.Type.MouseButtonRelease:
            return False

        pos = event.pos()
        rect = option.rect

        cb_rect = self._checkbox_rect(rect).adjusted(-6, -6, 6, 6)
        if cb_rect.contains(pos):
            current = bool(index.data(TrackListRoles.CheckedRole))
            return model.setData(index, not current, TrackListRoles.CheckedRole)

        status = str(index.data(TrackListRoles.StatusRole) or "idle")
        if status == "failed" and self._status_rect(rect).adjusted(-4, -4, 4, 4).contains(pos):
            row = int(index.data(TrackListRoles.IndexRole) or -1)
            if row >= 0:
                self.failureClicked.emit(row)
                return True

        return False

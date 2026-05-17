from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtGui import QPixmap

from .. import style as S
from .thumbnail import load_thumbnail, rounded_pixmap

class PlaylistHeader(QFrame):
    def __init__(
        self,
        name: str,
        cover: str,
        count: int,
        unmatched: int,
        avg_match: int | None = None,
        low_confidence: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("playlistHeader")
        self.setMinimumHeight(116)
        self._count = count

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        self._cover = QLabel()
        self._cover.setFixedSize(84, 84)
        self._cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover.setStyleSheet(f"background: {S.BG_MID}; border-radius: 12px; border: 1px solid {S.LINE};")
        layout.addWidget(self._cover)

        info = QVBoxLayout()
        info.setSpacing(4)
        info.setContentsMargins(0, 2, 0, 2)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("playlistTitle")
        name_lbl.setWordWrap(False)
        name_lbl.setToolTip(name)
        info.addWidget(name_lbl)

        meta = f"{count} track" + ("" if count == 1 else "s")
        meta_lbl = QLabel(meta)
        meta_lbl.setObjectName("playlistMeta")
        info.addWidget(meta_lbl)
        info.addStretch()

        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        badge_row.setContentsMargins(0, 0, 0, 0)

        self._sel_badge = QLabel(f"{count} selected")
        self._sel_badge.setObjectName("badge_accent")
        badge_row.addWidget(self._sel_badge)

        if avg_match is not None:
            match_badge = QLabel(f"{avg_match}% avg match")
            match_badge.setObjectName("badge_neutral")
            badge_row.addWidget(match_badge)

        if low_confidence > 0:
            low_badge = QLabel(f"{low_confidence} low confidence")
            low_badge.setObjectName("badge_warn")
            badge_row.addWidget(low_badge)

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
        self._sel_badge.setText(f"{n} / {self._count} selected")

    def _set_cover(self, pm: QPixmap):
        self._cover.setPixmap(rounded_pixmap(pm, 12))

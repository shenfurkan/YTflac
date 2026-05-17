from __future__ import annotations

import importlib.metadata
import os
import sys

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap, QColor
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QGraphicsDropShadowEffect


def _res(name: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base, "images", name)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About YtFLAC")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(10)
        brand_row.addStretch(1)

        brand_lbl = QLabel()
        brand_path = _res("appinbrand.png")
        if os.path.exists(brand_path):
            px = QPixmap(brand_path).scaled(
                340, 170, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            brand_lbl.setPixmap(px)
        brand_row.addWidget(brand_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        beta_lbl = QLabel("beta")
        beta_lbl.setObjectName("muted")
        beta_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        beta_lbl.setStyleSheet(
            "font-size: 10px; letter-spacing: 2px; font-weight: 700;"
            " text-transform: uppercase; background: transparent;"
            " padding: 3px 7px; border-radius: 6px;"
        )
        brand_row.addWidget(beta_lbl, alignment=Qt.AlignmentFlag.AlignBottom)
        brand_row.addStretch(1)
        root.addLayout(brand_row)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("#card { background: #e8e6d9; border: 1px solid rgba(64, 62, 58, 0.12); border-radius: 14px; }")
        
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(64, 62, 58, 80))
        shadow.setOffset(0, 6)
        card.setGraphicsEffect(shadow)
        
        body = QVBoxLayout(card)
        body.setContentsMargins(14, 14, 14, 14)
        body.setSpacing(8)

        desc = QLabel(
            "Convert Spotify and YouTube Music links to high-quality audio files "
            "using multi-provider lossless sources."
        )
        desc.setWordWrap(True)
        body.addWidget(desc)

        badges = QHBoxLayout()
        badges.setSpacing(6)
        for txt in ("Tidal", "Qobuz", "Amazon", "Deezer"):
            b = QLabel(txt)
            b.setObjectName("badge")
            badges.addWidget(b)
        badges.addStretch(1)
        body.addLayout(badges)

        root.addWidget(card)

        links = QHBoxLayout()
        links.setSpacing(8)

        gh_btn = QPushButton("GitHub")
        gh_btn.setObjectName("ghost")
        gh_btn.clicked.connect(
            lambda: self._open_url("https://github.com/shenfurkan/YTflac")
        )
        links.addWidget(gh_btn)

        issues_btn = QPushButton("Issues")
        issues_btn.setObjectName("ghost")
        issues_btn.clicked.connect(
            lambda: self._open_url("https://github.com/shenfurkan/YTflac/issues")
        )
        links.addWidget(issues_btn)

        rel_btn = QPushButton("Releases")
        rel_btn.setObjectName("ghost")
        rel_btn.clicked.connect(
            lambda: self._open_url("https://github.com/shenfurkan/YTflac/releases")
        )
        links.addWidget(rel_btn)

        links.addStretch(1)
        root.addLayout(links)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

    @staticmethod
    def _open_url(url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    @staticmethod
    def _version_text() -> str:
        try:
            return importlib.metadata.version("ytflac")
        except Exception:
            return "dev"

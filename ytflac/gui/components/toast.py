"""
Toast notification widget for non-blocking alerts.
"""

from __future__ import annotations
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsOpacityEffect,
)
from PyQt6.QtGui import QColor

from .. import style as S


class ToastWidget(QWidget):
    """Slide-in notification widget that auto-dismisses."""

    def __init__(
        self,
        message: str,
        level: str = "info",
        duration: int = 3000,
        parent=None,
    ):
        super().__init__(parent)
        self._duration = duration
        self._level = level

        # Setup widget
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(350)

        # Background color based on level
        bg_color = self._get_bg_color(level)
        text_color = self._get_text_color(level)

        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Icon
        icon = QLabel(self._get_icon(level))
        icon.setStyleSheet(f"font-size: 20px; color: {text_color}; background: transparent;")
        layout.addWidget(icon)

        # Message
        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"color: {text_color}; font-size: 13px; background: transparent;")
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label, stretch=1)

        # Close button
        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {text_color};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.1);
            }}
        """)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        # Style the widget
        self.setStyleSheet(f"""
            ToastWidget {{
                background: {bg_color};
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }}
        """)

        # Setup opacity effect for fade animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0)

        # Auto-dismiss timer
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._fade_out)

    def _get_bg_color(self, level: str) -> str:
        """Get background color based on notification level."""
        if level == "error":
            return "#e06060"
        elif level == "warning":
            return "#d4a055"
        elif level == "success":
            return "#6dbf72"
        else:  # info
            return "#403e3a"

    def _get_text_color(self, level: str) -> str:
        """Get text color based on notification level."""
        return "#ffffff"

    def _get_icon(self, level: str) -> str:
        """Get icon emoji based on notification level."""
        if level == "error":
            return "✕"
        elif level == "warning":
            return "⚠"
        elif level == "success":
            return "✓"
        else:  # info
            return "ℹ"

    def show_toast(self, parent_widget: QWidget):
        """Show toast with slide-in animation at bottom-right of parent."""
        if not parent_widget:
            return

        # Position at bottom-right
        parent_rect = parent_widget.geometry()
        x = parent_rect.width() - self.width() - 20
        y = parent_rect.height() - self.height() - 20
        self.move(x, y)
        self.setParent(parent_widget)
        self.show()

        # Fade in
        self._fade_in()

        # Start auto-dismiss timer
        self._dismiss_timer.start(self._duration)

    def _fade_in(self):
        """Fade in animation."""
        self._animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._animation.setDuration(300)
        self._animation.setStartValue(0)
        self._animation.setEndValue(1)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()

    def _fade_out(self):
        """Fade out animation and close."""
        self._animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._animation.setDuration(300)
        self._animation.setStartValue(1)
        self._animation.setEndValue(0)
        self._animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self._animation.finished.connect(self.close)
        self._animation.start()

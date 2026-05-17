"""
Material-inspired palette + QSS for the YtFLAC GUI.
Supports light and dark themes.
"""

from __future__ import annotations

import sys

from .style_qss import build_qss

# --- Palettes ---------------------------------------------------------------

# Light theme (current)
LIGHT = {
    "BG": "#ece8dc",
    "BG_ELEV": "#f8f6ee",
    "BG_MID": "#f1eee3",
    "BG_HOVER": "#e8e3d5",
    "LINE": "rgba(64, 62, 58, 0.22)",
    "LINE_STRONG": "rgba(64, 62, 58, 0.38)",
    "LINE_FOCUS": "rgba(64, 62, 58, 0.70)",
    "TEXT": "#403e3a",
    "TEXT_DIM": "#6f6c65",
    "TEXT_FAINT": "#8c8880",
    "ACCENT": "#403e3a",
    "ACCENT_HOV": "#2a2826",
    "ACCENT_SOFT": "rgba(64, 62, 58, 0.10)",
    "SUCCESS": "#4a9650",
    "SUCCESS_SOFT": "rgba(109, 191, 114, 0.15)",
    "ERROR": "#e06060",
    "ERROR_SOFT": "rgba(224, 96, 96, 0.15)",
    "WARNING": "#b88035",
    "LOG_INFO": "#7a7872",
    "LOG_SUCCESS": "#4a7c59",
    "LOG_ERROR": "#b94040",
    "LOG_WARNING": "#9c6d28",
    "LOG_API": "#4a6c7c",
    "LOG_DOWNLOAD": "#5c7a6c",
}

# Dark theme
DARK = {
    "BG": "#1a1a1a",
    "BG_ELEV": "#242424",
    "BG_MID": "#2d2d2d",
    "BG_HOVER": "#363636",
    "LINE": "rgba(255, 255, 255, 0.08)",
    "LINE_STRONG": "rgba(255, 255, 255, 0.15)",
    "LINE_FOCUS": "rgba(255, 255, 255, 0.40)",
    "TEXT": "#e0e0e0",
    "TEXT_DIM": "#c0c0c0",
    "TEXT_FAINT": "#999999",
    "ACCENT": "#e0e0e0",
    "ACCENT_HOV": "#ffffff",
    "ACCENT_SOFT": "rgba(255, 255, 255, 0.08)",
    "SUCCESS": "#6dbf72",
    "SUCCESS_SOFT": "rgba(109, 191, 114, 0.15)",
    "ERROR": "#e06060",
    "ERROR_SOFT": "rgba(224, 96, 96, 0.15)",
    "WARNING": "#d4a055",
    "LOG_INFO": "#a0a0a0",
    "LOG_SUCCESS": "#6dbf72",
    "LOG_ERROR": "#e06060",
    "LOG_WARNING": "#d4a055",
    "LOG_API": "#7ab8c7",
    "LOG_DOWNLOAD": "#8cbfa3",
}

# Current active palette (default to light)
_current_theme = "light"


def _is_system_dark() -> bool:
    """Detect whether the OS is currently in dark mode."""
    # Try Qt first (works cross-platform when QApplication exists)
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        pass

    # Windows registry fallback
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
        except Exception:
            pass

    return False


def set_theme(theme: str) -> None:
    """Set the current theme ('light', 'dark', or 'system') and rebuild QSS + color constants."""
    global _current_theme, QSS
    _current_theme = theme

    if theme == "system":
        is_dark = _is_system_dark()
        resolved = "dark" if is_dark else "light"
    else:
        resolved = "dark" if theme == "dark" else "light"

    QSS = _build_qss(resolved)
    p = DARK.copy() if resolved == "dark" else LIGHT.copy()
    this = sys.modules[__name__]
    for key in p:
        setattr(this, key, p[key])

def get_theme() -> str:
    """Get the current theme."""
    return _current_theme

# Initialize with light theme values for backward compatibility
_p = LIGHT.copy()

BG = _p["BG"]
BG_ELEV = _p["BG_ELEV"]
BG_MID = _p["BG_MID"]
BG_HOVER = _p["BG_HOVER"]
LINE = _p["LINE"]
LINE_STRONG = _p["LINE_STRONG"]
LINE_FOCUS = _p["LINE_FOCUS"]
TEXT = _p["TEXT"]
TEXT_DIM = _p["TEXT_DIM"]
TEXT_FAINT = _p["TEXT_FAINT"]
ACCENT = _p["ACCENT"]
ACCENT_HOV = _p["ACCENT_HOV"]
ACCENT_SOFT = _p["ACCENT_SOFT"]
SUCCESS = _p["SUCCESS"]
SUCCESS_SOFT = _p["SUCCESS_SOFT"]
ERROR = _p["ERROR"]
ERROR_SOFT = _p["ERROR_SOFT"]
WARNING = _p["WARNING"]
LOG_INFO = _p["LOG_INFO"]
LOG_SUCCESS = _p["LOG_SUCCESS"]
LOG_ERROR = _p["LOG_ERROR"]
LOG_WARNING = _p["LOG_WARNING"]
LOG_API = _p["LOG_API"]
LOG_DOWNLOAD = _p["LOG_DOWNLOAD"]

FONT_STACK = "'Google Sans', 'SF Pro Display', 'SF Pro Text', 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"

# Shared border-radius tokens
R_LG = "14px"   # cards, large containers
R_MD = "12px"   # buttons, inputs, combos
R_SM = "8px"    # tooltips, badges, checkboxes
R_XS = "6px"    # scrollbar handles


# --- QSS -------------------------------------------------------------------

def _build_qss(theme: str = "light") -> str:
    """Build the QSS stylesheet for the given theme."""
    p = DARK.copy() if theme == "dark" else LIGHT.copy()
    return build_qss(p, FONT_STACK, R_LG, R_MD, R_SM, R_XS)

# Build initial QSS with light theme
QSS = _build_qss("light")

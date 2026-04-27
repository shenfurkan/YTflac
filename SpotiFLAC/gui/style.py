"""
Centralised palette + QSS for the YtFLAC GUI.
Apple-inspired, minimal, dark-only.
"""
from __future__ import annotations

# --- Palette ---------------------------------------------------------------

BG          = "#0a0a0c"
BG_ELEV     = "#101014"
BG_HOVER    = "#15151b"
LINE        = "rgba(255, 255, 255, 0.06)"
LINE_STRONG = "rgba(255, 255, 255, 0.10)"

TEXT        = "#f0f0f3"
TEXT_DIM    = "#8a8a93"
TEXT_FAINT  = "#5a5a63"

ACCENT      = "#4f8ef7"
ACCENT_HOV  = "#6ba3fa"
SUCCESS     = "#6dbf72"
ERROR       = "#e06060"
WARNING     = "#d4a055"

FONT_STACK  = "'SF Pro Display', 'SF Pro Text', 'Inter', 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"


# --- QSS -------------------------------------------------------------------

QSS = f"""
* {{
    font-family: {FONT_STACK};
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QWidget {{
    background: {BG};
}}

QLabel {{
    background: transparent;
    border: none;
}}

QLabel#h1 {{
    font-size: 22px;
    font-weight: 600;
    color: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_HOV});
    letter-spacing: -0.5px;
}}
QLabel#h2 {{
    font-size: 15px;
    font-weight: 500;
    color: {TEXT};
}}
QLabel#muted {{
    color: {TEXT_DIM};
    font-size: 12px;
    font-weight: 400;
}}
QLabel#faint {{
    color: {TEXT_FAINT};
    font-size: 11px;
    font-weight: 400;
}}
QLabel#section {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}}

/* Inputs ------------------------------------------------------------- */
QLineEdit {{
    background: {BG_ELEV};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 9px 13px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #fff;
}}
QLineEdit:focus {{
    border: 1px solid {LINE_STRONG};
    background: {BG_HOVER};
}}

/* Buttons ------------------------------------------------------------ */
QPushButton {{
    background: {BG_ELEV};
    color: {TEXT};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {BG_HOVER};
    border: 1px solid {LINE_STRONG};
}}
QPushButton:pressed {{
    background: {BG};
}}
QPushButton:disabled {{
    color: {TEXT_FAINT};
    background: {BG_ELEV};
}}

QPushButton#primary {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_HOV});
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    letter-spacing: 0.2px;
}}
QPushButton#primary:hover {{
    background: {ACCENT_HOV};
}}
QPushButton#primary:disabled {{
    background: {BG_ELEV};
    color: {TEXT_FAINT};
    border: 1px solid {LINE};
}}

QPushButton#ghost {{
    background: transparent;
    border: none;
    color: {TEXT_DIM};
    padding: 6px 10px;
}}
QPushButton#ghost:hover {{
    color: {TEXT};
    background: {BG_ELEV};
}}

/* Service chips ------------------------------------------------------ */
QListWidget#chips {{
    background: transparent;
    border: none;
    outline: 0;
}}
QListWidget#chips::item {{
    background: {BG_ELEV};
    border: 1px solid {LINE};
    border-radius: 12px;
    padding: 4px 11px;
    margin: 0 3px 0 0;
    color: {TEXT};
    font-size: 12px;
}}
QListWidget#chips::item:hover {{
    background: {BG_HOVER};
    border: 1px solid {LINE_STRONG};
}}
QListWidget#chips::item:selected {{
    background: {BG_HOVER};
    border: 1px solid {LINE_STRONG};
    color: {TEXT};
}}

/* ScrollArea --------------------------------------------------------- */
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.10);
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255, 255, 255, 0.18);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ComboBox (folder etc) --------------------------------------------- */
QComboBox {{
    background: {BG_ELEV};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 7px 12px;
    color: {TEXT};
    min-width: 90px;
}}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {BG_ELEV};
    border: 1px solid {LINE_STRONG};
    selection-background-color: {BG_HOVER};
    color: {TEXT};
    outline: 0;
}}

/* CheckBox ----------------------------------------------------------- */
QCheckBox {{
    background: transparent;
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {LINE_STRONG};
    background: {BG_ELEV};
}}
QCheckBox::indicator:hover {{
    border: 1px solid {TEXT_DIM};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    image: none;
}}

/* TrackRow frame ---------------------------------------------------- */
QFrame#row {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {LINE};
    border-radius: 0px;
}}
QFrame#row:hover {{
    background: rgba(255,255,255,0.03);
    border-radius: 6px;
}}

QFrame#card {{
    background: {BG_ELEV};
    border: 1px solid {LINE};
    border-radius: 12px;
}}

/* Tooltip ----------------------------------------------------------- */
QToolTip {{
    background: {BG_HOVER};
    color: {TEXT};
    border: 1px solid {LINE_STRONG};
    border-radius: 6px;
    padding: 4px 8px;
}}

/* Dialog ------------------------------------------------------------ */
QDialog {{ background: {BG}; }}
QListWidget {{
    background: {BG_ELEV};
    border: 1px solid {LINE};
    border-radius: 8px;
    outline: 0;
    color: {TEXT};
}}
QListWidget::item {{ padding: 6px 8px; }}
QListWidget::item:selected {{ background: {BG_HOVER}; }}
"""

from __future__ import annotations


def build_qss(
    p: dict[str, str],
    font_stack: str,
    r_lg: str,
    r_md: str,
    r_sm: str,
    r_xs: str,
) -> str:
    return f"""
* {{
    font-family: {font_stack};
    font-size: 14px;
    color: {p["TEXT"]};
    outline: none; 
}}

/* =========================================
   ANA ZEMİN VE PENCERELER 
========================================= */
QMainWindow, QDialog, QStackedWidget {{
    background-color: {p["BG"]};
    border: none;
}}

QWidget#settings_right_panel {{
    background-color: {p["BG"]};
}}

/* =========================================
   SOL MENÜ (SIDEBAR) 
========================================= */
QListWidget#settings_sidebar {{
    background-color: {p["BG_ELEV"]};
    border-right: 1px solid {p["LINE_STRONG"]};
    border-top: none; border-bottom: none; border-left: none;
    padding: 16px 8px;
}}

QListWidget#settings_sidebar::item {{
    color: {p["TEXT_DIM"]};
    border-radius: {r_sm};
    padding: 8px 12px;
    margin: 2px;
    font-weight: 600;
    font-size: 12px;
    border: none;
    background-color: transparent;
}}

QListWidget#settings_sidebar::item:hover {{
    color: {p["TEXT"]};
    background-color: {p["BG_HOVER"]};
}}

QListWidget#settings_sidebar::item:selected {{
    color: {p["TEXT"]};
    background-color: {p["ACCENT_SOFT"]};
    font-weight: 700;
}}

/* =========================================
   MODERN KART TASARIMI 
========================================= */
QFrame#settings_card, QWidget#settings_card {{
    background-color: {p["BG_ELEV"]};
    border: 1px solid {p["LINE"]};
    border-radius: {r_md};
    margin: 0px;
}}

QFrame#empty_card {{
    background-color: {p["BG"]};
    border: 1px solid {p["LINE"]};
    border-radius: {r_md};
    margin: 0px;
}}

QFrame#playlistHeader {{
    background-color: {p["BG_ELEV"]};
    border: 1px solid {p["LINE"]};
    border-radius: {r_lg};
}}

QLabel#playlistTitle {{
    color: {p["TEXT"]};
    font-size: 17px;
    font-weight: 800;
    background: transparent;
}}

QLabel#playlistMeta {{
    color: {p["TEXT_DIM"]};
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}}

QLabel#badge_accent, QLabel#badge_neutral, QLabel#badge_warn {{
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 800;
    background: transparent;
}}

QLabel#badge_accent {{
    color: {p["BG"]};
    background-color: {p["ACCENT"]};
    border: 1px solid {p["ACCENT"]};
}}

QLabel#badge_neutral {{
    color: {p["TEXT_DIM"]};
    background-color: {p["BG_MID"]};
    border: 1px solid {p["LINE"]};
}}

QLabel#badge_warn {{
    color: {p["WARNING"]};
    background-color: {p["BG"]};
    border: 1px solid {p["WARNING"]};
}}

QFrame#unmatchedPanel {{
    background-color: {p["BG_ELEV"]};
    border: 1px solid {p["WARNING"]};
    border-radius: {r_lg};
}}

QLabel#warningIcon {{
    color: {p["WARNING"]};
    font-size: 16px;
    background: transparent;
}}

QLabel#unmatchedTitle {{
    color: {p["WARNING"]};
    font-size: 13px;
    font-weight: 800;
    background: transparent;
}}

QScrollArea#unmatchedScroll {{
    border: none;
    background: transparent;
}}

QFrame#unmatchedList {{
    background-color: {p["BG"]};
    border: 1px solid {p["LINE"]};
    border-radius: {r_sm};
}}

QFrame#unmatchedRow {{
    background-color: {p["BG_MID"]};
    border-radius: {r_xs};
}}

QFrame#unmatchedRow[fixed="true"] {{
    background-color: {p["SUCCESS_SOFT"]};
}}

QLabel#unmatchedIndex {{
    color: {p["TEXT_FAINT"]};
    font-size: 12px;
    background: transparent;
}}

QLabel#unmatchedText {{
    color: {p["TEXT"]};
    font-size: 13px;
    background: transparent;
}}

/* =========================================
   SÜRÜKLE BIRAK ÇÖPLERİ 
========================================= */
QListWidget#chips {{
    background-color: transparent; 
    border: none;
    padding: 2px 0px;
}}

QListWidget#chips::item {{
    background-color: {p["BG"]};
    border: 1px solid {p["LINE_STRONG"]};
    border-radius: 12px;
    padding: 3px 10px;
    margin: 2px;
    color: {p["TEXT"]};
    font-weight: 600;
    font-size: 11px;
}}

QListWidget#chips::item:hover {{
    background-color: {p["BG_HOVER"]};
    border: 1px solid {p["TEXT_DIM"]};
}}

/* =========================================
   TYPOGRAPHY 
========================================= */
QLabel#h1 {{
    font-size: 18px;
    font-weight: 800;
    color: {p["TEXT"]};
    padding-bottom: 2px;
    background: transparent;
}}

QLabel#h2 {{
    font-size: 13px;
    font-weight: 700;
    color: {p["TEXT"]};
    background: transparent;
}}

QLabel#muted {{
    color: {p["TEXT_FAINT"]};
    font-size: 11px;
    background: transparent;
}}

QLabel#section {{
    color: {p["TEXT_DIM"]};
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    background: transparent;
}}

/* =========================================
   INPUT & COMBOBOX 
========================================= */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {p["BG"]};
    border: 1px solid {p["LINE_STRONG"]};
    border-radius: {r_sm};
    padding: 4px 8px;
    color: {p["TEXT"]};
    min-height: 20px;
}}

QComboBox {{
    background-color: {p["BG"]};
    border: 1px solid {p["LINE_STRONG"]};
    border-radius: {r_sm};
    padding: 4px 24px 4px 8px;
    color: {p["TEXT"]};
    min-height: 20px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: none;
    background: transparent;
}}

QComboBox QAbstractItemView {{
    background-color: {p["BG_ELEV"]};
    border: 1px solid {p["LINE_STRONG"]};
    border-radius: {r_sm};
    selection-background-color: {p["BG_HOVER"]};
    selection-color: {p["TEXT"]};
    outline: none;
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {p["ACCENT"]};
}}

/* =========================================
   CHECKBOX 
========================================= */
QCheckBox {{
    background: transparent;
    color: {p["TEXT"]};
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 4px;
    border: 1px solid {p["LINE_STRONG"]};
    background-color: {p["BG"]};
}}

QCheckBox::indicator:hover {{
    border: 1px solid {p["ACCENT"]};
}}

QCheckBox::indicator:checked {{
    background-color: {p["ACCENT"]};
    border: 1px solid {p["ACCENT"]};
}}

/* =========================================
   BUTONLAR & FOOTER
========================================= */
QPushButton#primary {{
    background-color: {p["TEXT"]};
    color: {p["BG"]};
    border: none;
    border-radius: {r_md};
    padding: 10px 24px;
    font-weight: 700;
}}

QPushButton#primary:hover {{
    background-color: {p["TEXT_DIM"]};
}}

QPushButton#secondary, QPushButton#ghost {{
    background-color: transparent;
    color: {p["TEXT_DIM"]};
    border: 1px solid {p["LINE_STRONG"]};
    border-radius: {r_md};
    padding: 8px 16px;
    font-weight: 600;
}}

QPushButton#ghost {{
    border: none;
}}

QPushButton#secondary:hover, QPushButton#ghost:hover {{
    background-color: {p["BG_HOVER"]};
    color: {p["TEXT"]};
}}

QFrame#dialog_footer {{
    background-color: {p["BG_ELEV"]};
    border-top: 1px solid {p["LINE_STRONG"]};
}}

/* =========================================
   TRACK LIST VIEW
========================================= */
QListView#trackListView {{
    background-color: {p["BG"]};
    border: 1px solid {p["LINE"]};
    border-radius: {r_lg};
    padding: 8px;
}}

QListView#trackListView::item {{
    background-color: transparent;
    border: none;
    border-radius: {r_sm};
    margin: 2px 0;
    padding: 2px;
    min-height: 82px; 
}}

QListView#trackListView::item:selected {{
    background-color: transparent;
}}

QListView#trackListView::item:hover {{
    background-color: transparent;
}}
"""

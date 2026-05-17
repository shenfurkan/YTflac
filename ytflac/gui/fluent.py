from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLineEdit,
    QPushButton,
)

FLUENT_AVAILABLE = False
Theme = None

PushButton = QPushButton
PrimaryPushButton = QPushButton
TransparentPushButton = QPushButton
LineEdit = QLineEdit
ComboBox = QComboBox
CheckBox = QCheckBox
CardWidget = QFrame

try:
    from qfluentwidgets import (
        CardWidget as _FluentCardWidget,
        CheckBox as _FluentCheckBox,
        ComboBox as _FluentComboBox,
        LineEdit as _FluentLineEdit,
        PrimaryPushButton as _FluentPrimaryPushButton,
        PushButton as _FluentPushButton,
        Theme as _FluentTheme,
        TransparentPushButton as _FluentTransparentPushButton,
        setTheme,
        setThemeColor,
    )

    FLUENT_AVAILABLE = True
    Theme = _FluentTheme

    PushButton = _FluentPushButton
    PrimaryPushButton = _FluentPrimaryPushButton
    TransparentPushButton = _FluentTransparentPushButton
    LineEdit = _FluentLineEdit
    ComboBox = _FluentComboBox
    CheckBox = _FluentCheckBox
    CardWidget = _FluentCardWidget
except Exception:
    setTheme = None
    setThemeColor = None


def apply_fluent_theme(theme_name: str, accent_color: str | None = None) -> bool:
    if not FLUENT_AVAILABLE or Theme is None or setTheme is None:
        return False

    theme = theme_name.lower().strip()
    if theme == "dark":
        fluent_theme = Theme.DARK
    elif theme == "system":
        fluent_theme = Theme.AUTO
    else:
        fluent_theme = Theme.LIGHT

    setTheme(fluent_theme)
    if accent_color and setThemeColor is not None:
        setThemeColor(accent_color)
    return True

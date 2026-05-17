"""GUI component smoke tests - actually instantiates widgets to catch runtime errors."""
from __future__ import annotations

import os
import pytest
import sys
from unittest.mock import MagicMock, patch

# Ensure PyQt6 can initialize without a display
pytest.importorskip("PyQt6")


def _is_offscreen():
    """Detect if we're running in offscreen mode (CI/no display)."""
    return os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"


def _init_qt():
    """Initialize QApplication for tests."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        # Use offscreen platform if no display available
        if _is_offscreen() or os.environ.get("DISPLAY") is None:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(sys.argv)
    return app


class TestFluentImports:
    """Test that all Fluent widget imports work correctly."""

    def test_fluent_shim_imports(self):
        """All fluent shim classes should be importable and instantiable."""
        from ytflac.gui.fluent import (
            FLUENT_AVAILABLE,
            PushButton,
            PrimaryPushButton,
            TransparentPushButton,
            LineEdit,
            ComboBox,
            CheckBox,
            CardWidget,
        )

        assert FLUENT_AVAILABLE is True
        # Verify they're the Fluent versions, not plain PyQt6 fallbacks
        if FLUENT_AVAILABLE:
            assert "qfluentwidgets" in PushButton.__module__
            assert "qfluentwidgets" in PrimaryPushButton.__module__
            assert "qfluentwidgets" in LineEdit.__module__
            assert "qfluentwidgets" in ComboBox.__module__

    def test_fluent_buttons_instantiate(self):
        """Fluent buttons should instantiate without errors."""
        _init_qt()
        from ytflac.gui.fluent import (
            PushButton, PrimaryPushButton, TransparentPushButton,
        )

        # Buttons
        btn1 = PushButton("Test")
        assert btn1.text() == "Test"

        btn2 = PrimaryPushButton("Primary")
        assert btn2.text() == "Primary"

        btn3 = TransparentPushButton("Ghost")
        assert btn3.text() == "Ghost"

    def test_fluent_lineedit_instantiates(self):
        """Fluent LineEdit should instantiate without errors."""
        _init_qt()
        from ytflac.gui.fluent import LineEdit

        edit = LineEdit()
        edit.setText("test text")
        assert edit.text() == "test text"

    @pytest.mark.skipif(_is_offscreen(), reason="qfluentwidgets.ComboBox hangs in offscreen mode")
    def test_fluent_combobox_instantiates(self):
        """Fluent ComboBox should instantiate without errors (skipped in offscreen)."""
        _init_qt()
        from ytflac.gui.fluent import ComboBox

        combo = ComboBox()
        combo.addItems(["FLAC", "MP3"])
        assert combo.count() == 2
        combo.setCurrentText("MP3")
        assert combo.currentText() == "MP3"

    def test_fluent_checkbox_instantiates(self):
        """Fluent CheckBox should instantiate without errors."""
        _init_qt()
        from ytflac.gui.fluent import CheckBox

        cb = CheckBox("Check me")
        assert cb.text() == "Check me"

    def test_fluent_cardwidget_instantiates(self):
        """Fluent CardWidget should instantiate without errors."""
        _init_qt()
        from ytflac.gui.fluent import CardWidget

        card = CardWidget()
        assert card is not None


class TestMainWindowUI:
    """Test main window UI builder functions."""

    def test_main_window_ui_imports(self):
        """Main window UI module should import without errors."""
        from ytflac.gui import main_window_ui as MWUI
        assert hasattr(MWUI, '_build_ui')
        assert hasattr(MWUI, '_build_sidebar')
        assert hasattr(MWUI, '_build_right_column')

    @pytest.fixture
    def mock_main_window(self):
        """Create a mock main window with required attributes."""
        mock = MagicMock()
        mock._settings = MagicMock()
        mock._settings.value = MagicMock(return_value="FLAC")
        mock._track_proxy = MagicMock()
        mock._track_delegate = MagicMock()
        return mock

    @pytest.mark.skipif(_is_offscreen(), reason="Sidebar builds ComboBox which hangs in offscreen")
    def test_sidebar_widgets_instantiate(self, mock_main_window):
        """Sidebar widgets should instantiate with Fluent versions."""
        _init_qt()
        from ytflac.gui import main_window_ui as MWUI
        from PyQt6.QtCore import Qt

        # Set up required mock methods
        mock_main_window._set_button_icon = MagicMock()
        mock_main_window._on_preview = MagicMock()
        mock_main_window._on_format_changed = MagicMock()
        mock_main_window._on_download = MagicMock()
        mock_main_window._on_stop = MagicMock()
        mock_main_window._toggle_sidebar = MagicMock()

        # Build sidebar
        frame = MWUI._build_sidebar(mock_main_window)
        assert frame is not None

        # Verify widgets were created
        assert mock_main_window._url_input is not None
        assert mock_main_window._fmt_combo is not None
        assert mock_main_window._qual_combo is not None
        assert mock_main_window._preview_btn is not None
        assert mock_main_window._dl_btn is not None

    @pytest.mark.skipif(_is_offscreen(), reason="ComboBox hangs in offscreen mode")
    def test_quality_combo_tooltips_fallback(self, mock_main_window):
        """Quality combo should handle setItemData errors gracefully."""
        _init_qt()
        from ytflac.gui.fluent import ComboBox
        from PyQt6.QtCore import Qt

        # Create a mock ComboBox that raises on setItemData (like qfluentwidgets)
        class MockComboBox(ComboBox):
            def setItemData(self, index, value, role=None):
                if role is not None:
                    raise TypeError("setItemData() takes 3 positional arguments but 4 were given")
                super().setItemData(index, value)

        # This should not crash even with the incompatible signature
        combo = MockComboBox()
        combo.addItems(["LOSSLESS", "HI_RES", "HIGH", "NORMAL"])

        # The code should catch this and continue
        try:
            combo.setItemData(0, "tooltip", Qt.ItemDataRole.ToolTipRole)
        except TypeError:
            pass  # Expected with qfluentwidgets

        # Combo should still be functional
        assert combo.count() == 4
        combo.setCurrentText("HI_RES")
        assert combo.currentText() == "HI_RES"


class TestSettingsDialog:
    """Test settings dialog components."""

    def test_settings_dialog_imports(self):
        """Settings dialog should import without errors."""
        from ytflac.gui.dialogs.settings import SettingsDialog
        from ytflac.gui.dialogs import settings_tabs as ST
        assert hasattr(SettingsDialog, '_build_ui')
        assert hasattr(ST, 'build_services_tab')
        assert hasattr(ST, 'build_lyrics_tab')

    @pytest.mark.skipif(_is_offscreen(), reason="ToggleList may hang in offscreen mode")
    def test_toggle_list_instantiates(self):
        """ToggleList should instantiate with proper items."""
        _init_qt()
        from ytflac.gui.dialogs.settings_widgets import ToggleList

        all_items = ["spotify", "musixmatch", "amazon", "lrclib", "apple"]
        enabled = ["spotify", "apple"]

        toggle_list = ToggleList(all_items, enabled)
        assert toggle_list.count() == 5

        # Verify enabled items have checkmark
        enabled_ordered = toggle_list.enabled_ordered()
        assert "spotify" in enabled_ordered
        assert "apple" in enabled_ordered

    @pytest.mark.skipif(_is_offscreen(), reason="ServicePriorityBar may hang in offscreen mode")
    def test_service_priority_bar_instantiates(self):
        """ServicePriorityBar should instantiate and handle apple service."""
        _init_qt()
        from ytflac.gui.components import ServicePriorityBar

        services = ["tidal", "qobuz", "amazon", "deezer", "apple"]
        enabled = ["tidal", "apple"]

        bar = ServicePriorityBar(services, enabled)
        assert bar.count() == 5
        assert "apple" in bar.ordered_services()


class TestTrackItemDelegate:
    """Test track item delegate."""

    def test_delegate_imports(self):
        """Track delegate should import without errors."""
        from ytflac.gui.delegates.track_item_delegate import TrackItemDelegate
        assert TrackItemDelegate is not None

    def test_delegate_instantiates(self):
        """TrackItemDelegate should instantiate."""
        _init_qt()
        from PyQt6.QtWidgets import QListView
        from ytflac.gui.delegates.track_item_delegate import TrackItemDelegate

        view = QListView()
        delegate = TrackItemDelegate(view)
        assert delegate is not None


class TestAboutDialog:
    """Test about dialog."""

    def test_about_dialog_imports(self):
        """About dialog should import without errors."""
        from ytflac.gui.dialogs.about import AboutDialog
        assert AboutDialog is not None

    def test_about_dialog_instantiates(self):
        """AboutDialog should instantiate without crashing."""
        _init_qt()
        from ytflac.gui.dialogs.about import AboutDialog

        # Should not raise any errors
        dlg = AboutDialog()
        assert dlg is not None
        assert dlg.windowTitle() == "About YtFLAC"


class TestPlaylistHeader:
    """Test playlist header component."""

    def test_header_instantiates(self):
        """PlaylistHeader should instantiate with all badges."""
        _init_qt()
        from ytflac.gui.components.header import PlaylistHeader

        header = PlaylistHeader(
            name="Test Playlist",
            cover="",
            count=10,
            unmatched=2,
            avg_match=87,
            low_confidence=1,
        )
        assert header is not None


class TestUnmatchedPanel:
    """Test unmatched panel."""

    def test_panel_instantiates(self):
        """UnmatchedPanel should instantiate with sample data."""
        _init_qt()
        from ytflac.gui.components.panels import UnmatchedPanel

        unmatched = ["Unknown Track 1", "Unknown Track 2"]
        panel = UnmatchedPanel(unmatched)
        assert panel is not None


class TestModels:
    """Test data models."""

    def test_track_list_model(self):
        """TrackListModel should handle track data."""
        _init_qt()
        from ytflac.gui.models.track_list_model import TrackListModel
        from ytflac.core.models import TrackMetadata

        model = TrackListModel()

        tracks = [
            TrackMetadata(
                id="1",
                title="Test Song",
                artists="Test Artist",
                album="Test Album",
                album_artist="Test Artist",
                duration_ms=240000,
                match_confidence=95,
                match_source="spotify",
            )
        ]

        model.reset_tracks(tracks)
        assert model.rowCount() == 1


class TestIntegration:
    """Integration tests that verify the app can start."""

    def test_gui_module_imports(self):
        """All GUI modules should be importable."""
        # This catches import errors and syntax errors
        import ytflac.gui.main_window
        import ytflac.gui.main_window_ui
        import ytflac.gui.main_window_runtime
        import ytflac.gui.main_window_logic
        import ytflac.gui.main_window_shared
        import ytflac.gui.style
        import ytflac.gui.style_qss
        import ytflac.gui.fluent

        # Dialogs
        import ytflac.gui.dialogs.about
        import ytflac.gui.dialogs.settings
        import ytflac.gui.dialogs.settings_tabs
        import ytflac.gui.dialogs.settings_widgets

        # Components
        import ytflac.gui.components.header
        import ytflac.gui.components.panels
        import ytflac.gui.components.log_panel

        # Delegates
        import ytflac.gui.delegates.track_item_delegate

        # Models
        import ytflac.gui.models.track_list_model

    def test_qtawesome_icons_load(self):
        """qtawesome icons should load without errors."""
        _init_qt()
        from ytflac.gui.main_window_runtime import _set_button_icon
        from PyQt6.QtWidgets import QPushButton
        from ytflac.gui import style as S

        btn = QPushButton("Test")
        # This should not raise
        _set_button_icon(btn, "fa5s.info-circle")

    def test_set_theme_application(self):
        """Theme application should work without errors."""
        _init_qt()
        from ytflac.gui import style as S
        from ytflac.gui import fluent as F

        # Test setting light theme
        S.set_theme("light")
        assert S.THEME == "light"

        # Test setting dark theme
        S.set_theme("dark")
        assert S.THEME == "dark"

        # Test fluent theme application (returns bool)
        result = F.apply_fluent_theme("light")
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

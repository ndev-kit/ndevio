"""Tests for PluginInstallerWidget.

This module tests:
- PluginInstallerWidget behavior (unit tests, no viewer needed)
- _open_plugin_installer integration with napari viewer (needs viewer)
"""

from pathlib import Path
from unittest.mock import patch

import pytest


class TestPluginInstallerWidget:
    """Tests for PluginInstallerWidget behavior."""

    def test_standalone_mode(self):
        """Test widget in standalone mode - no path, shows generic title."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()

        # Standalone mode: no path, generic title
        assert widget.manager.path is None
        assert 'Install BioIO Reader Plugin' in widget._title_label.value

    def test_error_mode_with_path(self):
        """Test widget in error mode - has path, preselects suggested plugin."""
        from ndevio._plugin_manager import ReaderPluginManager
        from ndevio.widgets import PluginInstallerWidget

        # Mock installed plugins to NOT include bioio-czi
        # This simulates the error case where file can't be read
        with patch(
            'ndevio._plugin_manager.get_installed_plugins',
            return_value={'bioio-ome-tiff'},
        ):
            manager = ReaderPluginManager('test.czi')
            widget = PluginInstallerWidget(plugin_manager=manager)

            # Error mode: has path, shows filename, preselects installable plugin
            assert 'test.czi' in widget._title_label.value
            assert 'bioio-czi' in manager.suggested_plugins
            # bioio-czi should be in installable since it's not installed
            assert 'bioio-czi' in manager.installable_plugins
            # Value should be set to first installable plugin
            assert widget._plugin_select.value is not None

    def test_install_button_behavior(self):
        """Test install button: queues installation and updates status."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()
        widget._plugin_select.value = 'bioio-imageio'

        with patch('ndevio._plugin_installer.install_plugin') as mock_install:
            mock_install.return_value = 123
            widget._on_install_clicked()

            mock_install.assert_called_once_with('bioio-imageio')
            assert 'Installing' in widget._status_label.value

    def test_install_without_selection_shows_error(self):
        """Test that clicking install with no selection shows error."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()
        widget._plugin_select.value = None

        widget._on_install_clicked()

        assert 'No plugin selected' in widget._status_label.value


class TestOpenPluginInstallerIntegration:
    """Integration tests for _open_plugin_installer with napari viewer."""

    @pytest.fixture
    def viewer_with_plugin_installer(self, make_napari_viewer):
        """Fixture that creates viewer and opens plugin installer for .czi."""
        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = Path('path/to/test.czi')

        reader_module._open_plugin_installer(test_path)

        # Find the widget
        widget = None
        for name, w in viewer.window.dock_widgets.items():
            if 'Install BioIO Plugin' in name:
                widget = w
                break

        return viewer, widget, test_path

    def test_docks_widget_with_correct_state(
        self, viewer_with_plugin_installer
    ):
        """Test that _open_plugin_installer docks widget with correct state."""
        viewer, widget, test_path = viewer_with_plugin_installer

        # Widget is docked
        assert len(viewer.window.dock_widgets) > 0
        assert widget is not None

        # Widget has correct path and suggestions
        assert widget.manager.path == test_path
        assert test_path.name in widget._title_label.value
        assert 'bioio-czi' in widget.manager.suggested_plugins

"""Integration tests for plugin installer with napari viewer.

These tests verify that:
- _open_plugin_installer correctly docks widgets into the viewer
- Widget integration with napari's dock system works

For widget unit tests (no viewer required), see test_plugin_installer_widget.py
For ReaderPluginManager tests, see test_plugin_manager.py
"""

from pathlib import Path
from unittest.mock import Mock, patch


class TestOpenPluginInstaller:
    """Test _open_plugin_installer function with napari viewer."""

    def test_opens_widget_in_viewer(self, make_napari_viewer):
        """Test that _open_plugin_installer docks widget into viewer."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = 'test.czi'
        error = UnsupportedFileFormatError(
            reader_name='test', path=test_path, msg_extra=''
        )

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {
                'bioio-ome-tiff': Mock(supported=False),
                'ArrayLike': Mock(supported=False),
            }
            reader_module._open_plugin_installer(test_path, error)

        # Widget should be docked in viewer
        assert len(viewer.window.dock_widgets) > 0

        # Find the plugin installer widget
        widget = self._find_plugin_installer_widget(viewer)
        assert widget is not None

    def test_widget_receives_correct_path(self, make_napari_viewer):
        """Test that docked widget has the correct path set."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = Path('path/to/test.czi')
        error = UnsupportedFileFormatError(
            reader_name='test', path=str(test_path), msg_extra=''
        )

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {}
            reader_module._open_plugin_installer(test_path, error)

        widget = self._find_plugin_installer_widget(viewer)
        assert widget is not None
        assert widget.manager.path == test_path
        assert test_path.name in widget._title_label.value

    def test_suggests_correct_plugins_for_extension(self, make_napari_viewer):
        """Test that widget suggests correct plugins based on file extension."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = 'test.lif'
        error = UnsupportedFileFormatError(
            reader_name='test', path=test_path, msg_extra=''
        )

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {
                'bioio-ome-tiff': Mock(supported=False),
                'ArrayLike': Mock(supported=False),
            }
            reader_module._open_plugin_installer(test_path, error)

        widget = self._find_plugin_installer_widget(viewer)
        assert widget is not None
        assert 'bioio-lif' in widget.manager.installable_plugins

    @staticmethod
    def _find_plugin_installer_widget(viewer):
        """Helper to find PluginInstallerWidget in viewer dock widgets."""
        for name, widget in viewer.window.dock_widgets.items():
            if 'Install BioIO Plugin' in name:
                return widget
        return None

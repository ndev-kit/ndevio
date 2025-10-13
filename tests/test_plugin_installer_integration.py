"""Tests for _open_plugin_installer function and widget integration."""

from pathlib import Path
from unittest.mock import Mock, patch


class TestOpenPluginInstaller:
    """Test _open_plugin_installer function."""

    def test_opens_widget_with_viewer(self, make_napari_viewer):
        """Test that widget is opened when viewer exists."""
        # Import the private function directly from the module
        from bioio_base.exceptions import UnsupportedFileFormatError

        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = "test.czi"
        error = UnsupportedFileFormatError(
            reader_name="test", path=test_path, msg_extra=""
        )

        # Mock plugin_feasibility_report to avoid needing real file
        with patch(
            "ndevio._napari_reader.plugin_feasibility_report"
        ) as mock_report:
            mock_report.return_value = {
                "bioio-ome-tiff": Mock(supported=False),
                "ArrayLike": Mock(supported=False),
            }

            # Call the function
            reader_module._open_plugin_installer(test_path, error)

        # Check that widget was added to viewer
        assert len(viewer.window._dock_widgets) > 0

        # Find the plugin installer widget
        plugin_widget = None
        for name, widget in viewer.window._dock_widgets.items():
            if "Install BioIO Plugin" in name:
                plugin_widget = widget
                break

        assert plugin_widget is not None

    def test_widget_has_correct_path(self, make_napari_viewer):
        """Test that widget receives the correct path."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = Path("path/to/test.czi")
        error = UnsupportedFileFormatError(
            reader_name="test", path=str(test_path), msg_extra=""
        )

        with patch(
            "ndevio._napari_reader.plugin_feasibility_report"
        ) as mock_report:
            mock_report.return_value = {}

            reader_module._open_plugin_installer(test_path, error)

        # Get the widget
        widget_data = list(viewer.window._dock_widgets.values())[0]
        widget = (
            widget_data.widget()._widget
        )  # Get the actual Container widget

        # Check path was passed correctly
        assert widget.path == test_path
        assert test_path.name in widget._title_label.value

    def test_filters_installed_plugins(self, make_napari_viewer):
        """Test that installed plugins are filtered from suggestions."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = "test.czi"
        error = UnsupportedFileFormatError(
            reader_name="test", path=test_path, msg_extra=""
        )

        # Mock feasibility report showing bioio-czi as installed
        with patch(
            "ndevio._napari_reader.plugin_feasibility_report"
        ) as mock_report:
            mock_report.return_value = {
                "bioio-czi": Mock(
                    supported=False
                ),  # Installed but can't read this file
                "ArrayLike": Mock(supported=False),
            }

            reader_module._open_plugin_installer(test_path, error)

        # Get the widget
        widget_data = list(viewer.window._dock_widgets.values())[0]
        widget = widget_data.widget()._widget

        # bioio-czi should be filtered out from suggested_plugins
        if widget.suggested_plugins:
            plugin_names = [p["name"] for p in widget.suggested_plugins]
            assert "bioio-czi" not in plugin_names

    def test_suggests_uninstalled_plugins(self, make_napari_viewer):
        """Test that uninstalled plugins are suggested."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        import ndevio._napari_reader as reader_module

        viewer = make_napari_viewer()
        test_path = "test.lif"  # LIF files need bioio-lif
        error = UnsupportedFileFormatError(
            reader_name="test", path=test_path, msg_extra=""
        )

        # Mock feasibility report with no bioio-lif installed
        with patch(
            "ndevio._napari_reader.plugin_feasibility_report"
        ) as mock_report:
            mock_report.return_value = {
                "bioio-ome-tiff": Mock(supported=False),
                "ArrayLike": Mock(supported=False),
            }

            reader_module._open_plugin_installer(test_path, error)

        # Get the widget
        widget_data = list(viewer.window._dock_widgets.values())[0]
        widget = widget_data.widget()._widget

        # bioio-lif should be in suggested_plugins
        assert widget.suggested_plugins is not None
        plugin_names = [p["name"] for p in widget.suggested_plugins]
        assert "bioio-lif" in plugin_names


class TestPluginInstallerWidgetIntegration:
    """Integration tests for PluginInstallerWidget with viewer."""

    def test_widget_created_in_error_mode(self, make_napari_viewer):
        """Test widget creation in error mode with viewer."""
        from ndevio.widgets import PluginInstallerWidget

        make_napari_viewer()  # Create viewer context

        suggested = [
            {"name": "bioio-czi", "description": "Zeiss CZI files"},
        ]

        widget = PluginInstallerWidget(
            path="test.czi",
            suggested_plugins=suggested,
        )

        # Verify widget state
        assert widget.path == "test.czi"
        assert widget.suggested_plugins == suggested
        assert "test.czi" in widget._title_label.value
        assert widget._plugin_select.value == "bioio-czi"

    def test_install_button_queues_installation(self, make_napari_viewer):
        """Test that clicking install button queues installation."""
        from ndevio.widgets import PluginInstallerWidget

        make_napari_viewer()

        widget = PluginInstallerWidget()

        # Select a plugin
        widget._plugin_select.value = "bioio-imageio"

        # Mock the install_plugin function at the point of import
        with patch("ndevio._plugin_installer.install_plugin") as mock_install:
            mock_install.return_value = 123  # Mock job ID

            # Click install button
            widget._on_install_clicked()

            # Verify install was called with correct plugin
            mock_install.assert_called_once_with("bioio-imageio")

    def test_widget_shows_all_plugins(self, make_napari_viewer):
        """Test that widget shows all available plugins."""
        from ndevio._bioio_plugin_utils import BIOIO_PLUGINS
        from ndevio.widgets import PluginInstallerWidget

        make_napari_viewer()

        widget = PluginInstallerWidget()

        # Should have all plugins from BIOIO_PLUGINS
        plugin_names = [p["name"] for p in widget.plugins]
        expected_names = list(BIOIO_PLUGINS.keys())

        assert set(plugin_names) == set(expected_names)

    def test_widget_preselects_first_suggestion(self, make_napari_viewer):
        """Test that first suggested plugin is pre-selected."""
        from ndevio.widgets import PluginInstallerWidget

        make_napari_viewer()

        suggested = [
            {"name": "bioio-lif", "description": "Leica LIF files"},
            {"name": "bioio-czi", "description": "Zeiss CZI files"},
        ]

        widget = PluginInstallerWidget(
            path="test.lif",
            suggested_plugins=suggested,
        )

        # First suggestion should be selected
        assert widget._plugin_select.value == "bioio-lif"

    def test_install_updates_status_label(self, make_napari_viewer):
        """Test that status label updates during installation."""
        from ndevio.widgets import PluginInstallerWidget

        make_napari_viewer()

        widget = PluginInstallerWidget()
        widget._plugin_select.value = "bioio-imageio"

        with patch("ndevio._plugin_installer.install_plugin") as mock_install:
            mock_install.return_value = 123

            # Status should update to "Installing..."
            widget._on_install_clicked()
            assert "Installing" in widget._status_label.value

    def test_no_plugin_selected_shows_error(self, make_napari_viewer):
        """Test that clicking install with no selection shows error."""
        from ndevio.widgets import PluginInstallerWidget

        make_napari_viewer()

        widget = PluginInstallerWidget()
        widget._plugin_select.value = None

        widget._on_install_clicked()

        assert "No plugin selected" in widget._status_label.value

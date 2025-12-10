"""Tests for PluginInstallerWidget.

This module tests the PluginInstallerWidget in _plugin_installer.py.
Widget unit tests do NOT require make_napari_viewer.

For napari integration tests (docking widgets into viewer),
see test_plugin_installer_integration.py
"""

from unittest.mock import Mock, patch


class TestPluginInstallerWidgetUnit:
    """Unit tests for PluginInstallerWidget - no napari viewer required."""

    def test_standalone_mode_default_state(self):
        """Test widget creation in standalone mode (no path)."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()

        # Should have plugins available via manager
        assert len(widget.manager.known_plugins) > 0
        assert widget.manager.path is None
        assert 'Install BioIO Reader Plugin' in widget._title_label.value

    def test_error_mode_with_manager(self):
        """Test widget creation with a manager (error mode)."""
        from ndevio._plugin_manager import ReaderPluginManager
        from ndevio.widgets import PluginInstallerWidget

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager('test.czi')
            widget = PluginInstallerWidget(plugin_manager=manager)

        # Should show filename in title
        assert 'test.czi' in widget._title_label.value
        # Should have installable plugins
        assert 'bioio-czi' in widget.manager.installable_plugins
        # First installable should be pre-selected
        assert widget._plugin_select.value == 'bioio-czi'

    def test_preselects_first_installable_plugin(self):
        """Test that first installable plugin is pre-selected."""
        from ndevio._plugin_manager import ReaderPluginManager
        from ndevio.widgets import PluginInstallerWidget

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager('test.lif')
            widget = PluginInstallerWidget(plugin_manager=manager)

        installable = widget.manager.installable_plugins
        assert len(installable) > 0
        assert widget._plugin_select.value == installable[0]

    def test_shows_all_known_plugins(self):
        """Test that all known plugins are available for selection."""
        from ndevio._bioio_plugin_utils import BIOIO_PLUGINS
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()

        assert set(widget.manager.known_plugins) == set(BIOIO_PLUGINS.keys())

    def test_no_plugin_selected_shows_error(self):
        """Test clicking install with no selection shows error."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()
        widget._plugin_select.value = None

        widget._on_install_clicked()

        assert 'No plugin selected' in widget._status_label.value

    def test_install_button_queues_installation(self):
        """Test that install button triggers installation."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()
        widget._plugin_select.value = 'bioio-imageio'

        with patch('ndevio._plugin_installer.install_plugin') as mock_install:
            mock_install.return_value = 123

            widget._on_install_clicked()

            mock_install.assert_called_once_with('bioio-imageio')

    def test_install_updates_status_label(self):
        """Test that status label updates during installation."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()
        widget._plugin_select.value = 'bioio-imageio'

        with patch('ndevio._plugin_installer.install_plugin') as mock_install:
            mock_install.return_value = 123

            widget._on_install_clicked()

            assert 'Installing' in widget._status_label.value

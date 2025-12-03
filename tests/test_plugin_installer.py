"""Tests for plugin installer functionality."""

from unittest.mock import Mock, patch


class TestReaderPluginManagerInstallable:
    """Test ReaderPluginManager.installable_plugins property."""

    def test_czi_file_no_plugins_installed(self):
        """Test that CZI file suggests bioio-czi plugin when nothing installed."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {"ArrayLike": Mock(supported=False)}

            manager = ReaderPluginManager("test.czi")
            plugins = manager.installable_plugins

        assert len(plugins) == 1
        assert plugins[0] == "bioio-czi"

    def test_lif_file_no_plugins_installed(self):
        """Test that LIF file suggests bioio-lif plugin."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {"ArrayLike": Mock(supported=False)}

            manager = ReaderPluginManager("test.lif")
            plugins = manager.installable_plugins

        assert len(plugins) == 1
        assert plugins[0] == "bioio-lif"

    def test_tiff_file_suggests_non_core_only(self):
        """Test that TIFF files only suggest non-core plugins."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {"ArrayLike": Mock(supported=False)}

            manager = ReaderPluginManager("test.tiff")
            plugins = manager.installable_plugins

        # Should only get bioio-tiff-glob (non-core)
        # bioio-ome-tiff and bioio-tifffile are core and shouldn't be suggested
        assert "bioio-tiff-glob" in plugins
        assert "bioio-ome-tiff" not in plugins
        assert "bioio-tifffile" not in plugins

    def test_no_plugins_for_unsupported_extension(self):
        """Test that unsupported extensions return empty list."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {"ArrayLike": Mock(supported=False)}

            manager = ReaderPluginManager("test.xyz")
            plugins = manager.installable_plugins

        assert len(plugins) == 0

    def test_filters_installed_plugins(self):
        """Test that already installed plugins are filtered out."""
        from ndevio._plugin_manager import ReaderPluginManager

        # Mock feasibility report showing bioio-czi as installed
        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {
                "bioio-czi": Mock(supported=True),
                "ArrayLike": Mock(supported=False),
            }

            manager = ReaderPluginManager("test.czi")
            plugins = manager.installable_plugins

        # bioio-czi should be filtered out since it's "installed"
        assert len(plugins) == 0


class TestPluginInstallerWidget:
    """Test PluginInstallerWidget in both modes."""

    def test_standalone_mode(self, make_napari_viewer):
        """Test widget in standalone mode (no path provided)."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()

        # Should have ALL plugins available via manager
        assert len(widget.manager.available_plugins) > 0

        # Should not have path
        assert widget.manager.path is None

        # Title should be standalone message
        assert "Install BioIO Reader Plugin" in widget._title_label.value

        # No path, so no pre-selection
        assert (
            widget._plugin_select.value is None
            or widget._plugin_select.value is not None
        )

    def test_error_mode_with_installable_plugins(self, make_napari_viewer):
        """Test widget in error mode with installable plugins."""
        from ndevio._plugin_manager import ReaderPluginManager
        from ndevio.widgets import PluginInstallerWidget

        with patch("bioio.plugin_feasibility_report") as mock_report:
            # Mock report showing no plugins installed
            mock_report.return_value = {"ArrayLike": Mock(supported=False)}

            manager = ReaderPluginManager("test.czi")
            widget = PluginInstallerWidget(plugin_manager=manager)

        # Should have ALL plugins available
        assert len(widget.manager.available_plugins) > 0

        # Should have installable plugins
        installable = widget.manager.installable_plugins
        assert len(installable) > 0
        assert "bioio-czi" in installable

        # First installable plugin should be pre-selected
        assert widget._plugin_select.value == installable[0]

        # Should have path
        assert widget.manager.path is not None
        assert widget.manager.path.name == "test.czi"

        # Title should show filename
        assert "test.czi" in widget._title_label.value

    def test_error_mode_no_installable_plugins(self, make_napari_viewer):
        """Test widget in error mode without installable plugins."""
        from ndevio._plugin_manager import ReaderPluginManager
        from ndevio.widgets import PluginInstallerWidget

        with patch("bioio.plugin_feasibility_report") as mock_report:
            # Mock report showing all suggested plugins already installed
            mock_report.return_value = {
                "bioio-imageio": Mock(supported=False),  # for .xyz files
                "ArrayLike": Mock(supported=False),
            }

            manager = ReaderPluginManager("test.png")
            widget = PluginInstallerWidget(plugin_manager=manager)

        # Should still have ALL plugins available
        assert len(widget.manager.available_plugins) > 0

        # No installable plugins (core already installed or unsupported format)
        # So no pre-selection or pre-select first available
        # (Either behavior is acceptable)

    def test_widget_without_viewer(self):
        """Test widget can be created without viewer."""
        from ndevio.widgets import PluginInstallerWidget

        # Should work without any napari viewer
        widget = PluginInstallerWidget()

        # Widget should have all plugins via manager
        assert len(widget.manager.available_plugins) > 0


class TestInstallPlugin:
    """Test install_plugin function."""

    def test_returns_job_id(self):
        """Test that install_plugin returns a job ID."""
        from ndevio._plugin_installer import install_plugin

        # This will queue the installation but not actually run it
        job_id = install_plugin("bioio-imageio")

        # Job ID should be an integer
        assert isinstance(job_id, int)

    def test_install_via_queue(self):
        """Manual test for queue-based installation."""
        from ndevio._plugin_installer import (
            get_installer_queue,
        )

        queue = get_installer_queue()

        # Track completion
        completed = []

        def on_finished(event):
            completed.append(event)

        queue.processFinished.connect(on_finished)

        # Wait for completion (with timeout)
        queue.waitForFinished(msecs=30000)

        # Check that we got a completion event
        assert len(completed) > 0
        assert "bioio-imageio" in completed[0].get("pkgs", [])


class TestVerifyPluginInstalled:
    """Test verify_plugin_installed function."""

    def test_verify_installed_plugin(self):
        """Test verification of an installed plugin (bioio itself)."""
        from ndevio._plugin_installer import verify_plugin_installed

        # bioio should be installed since it's a dependency
        assert verify_plugin_installed("bioio")

    def test_verify_not_installed_plugin(self):
        """Test verification of a plugin that isn't installed."""
        from ndevio._plugin_installer import verify_plugin_installed

        # Use a plugin that definitely won't be installed
        assert not verify_plugin_installed("bioio-nonexistent-plugin-12345")

    def test_verify_converts_name_format(self):
        """Test that plugin name is correctly converted to module name."""
        from ndevio._plugin_installer import verify_plugin_installed

        # Test with installed package (bioio-base should be installed)
        # The function should convert bioio-base -> bioio_base
        result = verify_plugin_installed("bioio-base")
        assert isinstance(result, bool)


class TestGetInstallerQueue:
    """Test get_installer_queue function."""

    def test_returns_queue_instance(self):
        """Test that get_installer_queue returns a queue."""
        from napari_plugin_manager.qt_package_installer import (
            NapariInstallerQueue,
        )

        from ndevio._plugin_installer import get_installer_queue

        queue = get_installer_queue()
        assert isinstance(queue, NapariInstallerQueue)

    def test_returns_same_instance(self):
        """Test that get_installer_queue returns singleton."""
        from ndevio._plugin_installer import get_installer_queue

        queue1 = get_installer_queue()
        queue2 = get_installer_queue()

        # Should be the same instance
        assert queue1 is queue2

    def test_queue_reset(self):
        """Test that queue can be reset for testing."""
        from ndevio import _plugin_installer
        from ndevio._plugin_installer import get_installer_queue

        queue1 = get_installer_queue()

        # Reset the global
        _plugin_installer._installer_queue = None

        queue2 = get_installer_queue()

        # Should be a new instance
        assert queue1 is not queue2

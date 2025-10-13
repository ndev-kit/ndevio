"""Tests for plugin installer functionality."""

import pytest


class TestGetInstallablePlugins:
    """Test get_installable_plugins function."""

    def test_czi_file_no_feasibility_report(self):
        """Test that CZI file suggests bioio-czi plugin."""
        from ndevio._bioio_plugin_utils import get_installable_plugins

        plugins = get_installable_plugins("test.czi")

        assert len(plugins) == 1
        assert plugins[0]["name"] == "bioio-czi"
        assert "Zeiss CZI" in plugins[0]["description"]

    def test_lif_file_no_feasibility_report(self):
        """Test that LIF file suggests bioio-lif plugin."""
        from ndevio._bioio_plugin_utils import get_installable_plugins

        plugins = get_installable_plugins("test.lif")

        assert len(plugins) == 1
        assert plugins[0]["name"] == "bioio-lif"

    def test_tiff_file_suggests_non_core_only(self):
        """Test that TIFF files only suggest non-core plugins."""
        from ndevio._bioio_plugin_utils import get_installable_plugins

        plugins = get_installable_plugins("test.tiff")

        # Should only get bioio-tifffile (non-core)
        # bioio-ome-tiff is core and shouldn't be suggested
        plugin_names = [p["name"] for p in plugins]
        assert "bioio-tifffile" in plugin_names
        assert "bioio-ome-tiff" not in plugin_names

    def test_no_plugins_for_unsupported_extension(self):
        """Test that unsupported extensions return empty list."""
        from ndevio._bioio_plugin_utils import get_installable_plugins

        plugins = get_installable_plugins("test.xyz")

        assert len(plugins) == 0

    def test_filters_installed_plugins(self):
        """Test that already installed plugins are filtered out."""
        from ndevio._bioio_plugin_utils import get_installable_plugins

        # Mock feasibility report showing bioio-czi as installed
        mock_report = {
            "bioio-czi": type(
                "MockSupport", (), {"supported": True, "priority": 1}
            )(),
            "ArrayLike": type(
                "MockSupport", (), {"supported": True, "priority": 0}
            )(),
        }

        plugins = get_installable_plugins("test.czi", mock_report)

        # bioio-czi should be filtered out since it's "installed"
        assert len(plugins) == 0


class TestPluginInstallerWidget:
    """Test PluginInstallerWidget in both modes."""

    def test_standalone_mode(self, make_napari_viewer):
        """Test widget in standalone mode (no path provided)."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget()

        # Should have ALL plugins available from BIOIO_PLUGINS
        assert len(widget.plugins) > 0

        # Should not have path
        assert widget.path is None

        # Should not have suggested plugins
        assert widget.suggested_plugins is None

        # Title should be standalone message
        assert "Install BioIO Reader Plugin" in widget._title_label.value

        assert widget._plugin_select.value is None

    def test_error_mode_with_suggestions(self, make_napari_viewer):
        """Test widget in error mode with suggested plugins."""
        from ndevio.widgets import PluginInstallerWidget

        suggested = [
            {"name": "bioio-czi", "description": "Zeiss CZI files"},
            {"name": "bioio-lif", "description": "Leica LIF files"},
        ]

        widget = PluginInstallerWidget(
            path="test.czi",
            suggested_plugins=suggested,
        )

        # Should have ALL plugins (not just suggested)
        assert len(widget.plugins) > len(suggested)

        # Should have suggested plugins stored
        assert widget.suggested_plugins == suggested

        # First suggested plugin should be pre-selected
        assert widget._plugin_select.value == "bioio-czi"

        # Should have path
        assert widget.path == "test.czi"

        # Title should show filename
        assert "test.czi" in widget._title_label.value

    def test_error_mode_no_suggestions(self, make_napari_viewer):
        """Test widget in error mode without suggestions."""
        from ndevio.widgets import PluginInstallerWidget

        widget = PluginInstallerWidget(
            path="test.xyz",
            suggested_plugins=None,
        )

        # Should still have ALL plugins
        assert len(widget.plugins) > 0

        assert widget._plugin_select.value is None

    def test_widget_without_viewer(self):
        """Test widget can be created without viewer."""
        from ndevio.widgets import PluginInstallerWidget

        # Should work without any napari viewer
        widget = PluginInstallerWidget()

        # Widget should have all plugins
        assert len(widget.plugins) > 0


class TestInstallPlugin:
    """Test install_plugin function."""

    def test_returns_job_id(self):
        """Test that install_plugin returns a job ID."""
        from ndevio._plugin_installer import install_plugin

        # This will queue the installation but not actually run it
        job_id = install_plugin("bioio-imageio")

        # Job ID should be an integer
        assert isinstance(job_id, int)

    @pytest.mark.skip(
        reason="Requires napari and actual installation - run manually"
    )
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

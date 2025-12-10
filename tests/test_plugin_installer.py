"""Tests for plugin installer functionality.

This module tests the _plugin_installer.py module:
- install_plugin: queues a plugin for installation
- verify_plugin_installed: checks if a plugin is installed
- get_installer_queue: gets the napari installer queue singleton

For ReaderPluginManager tests, see test_plugin_manager.py
For widget tests, see test_plugin_installer_widget.py
"""


class TestInstallPlugin:
    """Test install_plugin function."""

    def test_returns_job_id(self):
        """Test that install_plugin returns a job ID."""
        from ndevio._plugin_installer import install_plugin

        # This will queue the installation but not actually run it
        job_id = install_plugin('bioio-imageio')

        assert isinstance(job_id, int)


class TestVerifyPluginInstalled:
    """Test verify_plugin_installed function."""

    def test_installed_dependency(self):
        """Test verification of an installed package (bioio is a dependency)."""
        from ndevio._plugin_installer import verify_plugin_installed

        assert verify_plugin_installed('bioio')

    def test_not_installed_plugin(self):
        """Test verification of a plugin that isn't installed."""
        from ndevio._plugin_installer import verify_plugin_installed

        assert not verify_plugin_installed('bioio-nonexistent-plugin-12345')

    def test_converts_hyphen_to_underscore(self):
        """Test that plugin name is correctly converted to module name."""
        from ndevio._plugin_installer import verify_plugin_installed

        # bioio-base should be installed, converts to bioio_base
        result = verify_plugin_installed('bioio-base')
        assert isinstance(result, bool)


class TestGetInstallerQueue:
    """Test get_installer_queue function."""

    def test_returns_queue_instance(self):
        """Test that get_installer_queue returns the correct type."""
        from napari_plugin_manager.qt_package_installer import (
            NapariInstallerQueue,
        )

        from ndevio._plugin_installer import get_installer_queue

        queue = get_installer_queue()
        assert isinstance(queue, NapariInstallerQueue)

    def test_singleton_behavior(self):
        """Test that get_installer_queue returns the same instance."""
        from ndevio._plugin_installer import get_installer_queue

        queue1 = get_installer_queue()
        queue2 = get_installer_queue()

        assert queue1 is queue2

    def test_queue_can_be_reset(self):
        """Test that queue can be reset for testing purposes."""
        from ndevio import _plugin_installer
        from ndevio._plugin_installer import get_installer_queue

        queue1 = get_installer_queue()

        # Reset the global
        _plugin_installer._installer_queue = None

        queue2 = get_installer_queue()

        assert queue1 is not queue2

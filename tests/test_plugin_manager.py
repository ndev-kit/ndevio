"""Tests for ReaderPluginManager class from _plugin_manager module.

Note: Extension-to-plugin mapping is tested in test_bioio_plugin_utils.py
via TestSuggestPluginsForPath. We trust those unit tests and don't duplicate here.
"""

from unittest.mock import patch

import pytest
from bioio_base.exceptions import UnsupportedFileFormatError


class TestRaiseWithSuggestions:
    """Tests for raise_unsupported_with_suggestions function."""

    def test_raises_with_suggestions_enabled(self):
        """Test error message includes suggestions when enabled."""
        from ndevio._plugin_manager import raise_unsupported_with_suggestions

        with patch('ndev_settings.get_settings') as mock_settings:
            mock_settings.return_value.ndevio_reader.suggest_reader_plugins = (
                True
            )

            with pytest.raises(UnsupportedFileFormatError) as exc_info:
                raise_unsupported_with_suggestions('test.czi')

            error_msg = str(exc_info.value)
            assert 'bioio-czi' in error_msg

    def test_raises_without_suggestions_when_disabled(self):
        """Test error message has no suggestions when disabled."""
        from ndevio._plugin_manager import raise_unsupported_with_suggestions

        with patch('ndev_settings.get_settings') as mock_settings:
            mock_settings.return_value.ndevio_reader.suggest_reader_plugins = (
                False
            )

            with pytest.raises(UnsupportedFileFormatError) as exc_info:
                raise_unsupported_with_suggestions('test.czi')

            error_msg = str(exc_info.value)
            # Should still mention the file but not include installation message
            assert 'test.czi' in error_msg


class TestGetInstalledPlugins:
    """Tests for get_installed_plugins module-level function."""

    def test_returns_set_of_strings(self):
        """Test that get_installed_plugins returns a set of strings."""
        from ndevio._bioio_plugin_utils import get_installed_plugins

        result = get_installed_plugins()

        assert isinstance(result, set)
        for item in result:
            assert isinstance(item, str)

    def test_includes_core_plugins(self):
        """Test that installed plugins include core bioio plugins."""
        from ndevio._bioio_plugin_utils import get_installed_plugins

        result = get_installed_plugins()

        # At minimum, one core plugin should be present
        core_plugins = {'bioio-ome-tiff', 'bioio-ome-zarr', 'bioio-tifffile'}
        assert len(result & core_plugins) > 0


class TestReaderPluginManager:
    """Tests for ReaderPluginManager properties and methods."""

    def test_installed_plugins_returns_set(self):
        """Test that installed_plugins returns a set of plugin names."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager('test.tiff')

        assert isinstance(manager.installed_plugins, set)
        assert len(manager.installed_plugins) > 0

    def test_installed_plugins_matches_module_function(self):
        """Test installed_plugins matches get_installed_plugins()."""
        from ndevio._bioio_plugin_utils import get_installed_plugins
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager('test.tiff')

        assert manager.installed_plugins == get_installed_plugins()

    def test_suggested_plugins_for_tiff(self):
        """Test suggested_plugins returns relevant plugins for tiff."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager('test.tiff')
        suggested = manager.suggested_plugins

        assert 'bioio-ome-tiff' in suggested
        assert 'bioio-tifffile' in suggested

    def test_suggested_plugins_for_czi(self):
        """Test suggested_plugins returns bioio-czi for .czi files."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager('test.czi')
        suggested = manager.suggested_plugins

        assert 'bioio-czi' in suggested

    def test_installable_excludes_installed_and_core(self):
        """Test installable_plugins excludes installed and core plugins."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager('test.tiff')
        installable = manager.installable_plugins

        # Core plugins never in installable
        assert 'bioio-ome-tiff' not in installable
        assert 'bioio-tifffile' not in installable
        assert 'bioio-imageio' not in installable
        assert 'bioio-tiff-glob' in installable

        # Already installed plugins should not be in installable
        installed = manager.installed_plugins
        for plugin in installable:
            assert plugin not in installed

    def test_get_installation_message_with_installable(self):
        """Test installation message is generated for installable plugins."""
        from ndevio._plugin_manager import ReaderPluginManager

        # Mock installed plugins to NOT include bioio-nd2
        with patch(
            'ndevio._plugin_manager.get_installed_plugins',
            return_value={'bioio-ome-tiff', 'bioio-tifffile'},
        ):
            manager = ReaderPluginManager('test.nd2')
            message = manager.get_installation_message()

            assert 'bioio-nd2' in message
            assert 'pip install' in message


class TestReaderPluginManagerNoPath:
    """Tests for ReaderPluginManager edge cases when no path provided."""

    def test_suggested_plugins_empty_without_path(self):
        """Test suggested_plugins returns [] without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        assert manager.suggested_plugins == []

    def test_installable_plugins_empty_without_path(self):
        """Test installable_plugins returns [] without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        assert manager.installable_plugins == []

    def test_get_installation_message_returns_empty(self):
        """Test get_installation_message returns '' without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        assert manager.get_installation_message() == ''


class TestReaderPluginManagerWithRealFiles:
    """Tests using real files to verify end-to-end behavior."""

    def test_suggested_plugins_for_real_tiff(self, resources_dir):
        """Test suggested_plugins with a real TIFF file."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')
        suggested = manager.suggested_plugins

        assert 'bioio-ome-tiff' in suggested
        assert 'bioio-tifffile' in suggested

    def test_installed_plugins_includes_core(self, resources_dir):
        """Test installed_plugins includes core plugins."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')
        installed = manager.installed_plugins

        # At least one core plugin should be installed
        core_plugins = {'bioio-ome-tiff', 'bioio-ome-zarr', 'bioio-tifffile'}
        assert len(installed & core_plugins) > 2

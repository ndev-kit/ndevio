"""Tests for ReaderPluginManager class from _plugin_manager module."""

import logging
from unittest.mock import Mock, patch

import pytest


class TestReaderPluginManagerProperties:
    """Test ReaderPluginManager properties (known_plugins, installed, etc.)."""

    def test_known_plugins_returns_all_bioio_plugins(self):
        """Test that known_plugins returns all plugins from BIOIO_PLUGINS."""
        from ndevio._bioio_plugin_utils import BIOIO_PLUGINS
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()

        assert set(manager.known_plugins) == set(BIOIO_PLUGINS.keys())

    def test_installed_plugins_from_feasibility_report(self):
        """Test that installed_plugins comes from bioio feasibility report."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {
                'bioio-czi': Mock(supported=False),
                'bioio-ome-tiff': Mock(supported=True),
                'ArrayLike': Mock(supported=False),
            }

            manager = ReaderPluginManager('test.czi')

            assert 'bioio-czi' in manager.installed_plugins
            assert 'bioio-ome-tiff' in manager.installed_plugins
            assert (
                'ArrayLike' not in manager.installed_plugins
            )  # Not a bioio plugin

    def test_suggested_plugins_based_on_extension(self):
        """Test that suggested_plugins are determined by file extension."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager('test.czi')

            assert 'bioio-czi' in manager.suggested_plugins

    def test_installable_plugins_excludes_installed(self):
        """Test that installable_plugins excludes already installed plugins."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            # bioio-czi shows as installed
            mock_report.return_value = {
                'bioio-czi': Mock(supported=False),
                'ArrayLike': Mock(supported=False),
            }

            manager = ReaderPluginManager('test.czi')

            # bioio-czi should NOT be in installable (it's installed)
            assert 'bioio-czi' not in manager.installable_plugins

    def test_installable_plugins_excludes_core_plugins(self):
        """Test that core plugins are excluded from installable list."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager('test.tiff')
            installable = manager.installable_plugins

            # Core plugins should never be in installable
            core_plugins = [
                'bioio-ome-tiff',
                'bioio-imageio',
                'bioio-ome-zarr',
                'bioio-tifffile',
            ]
            for core in core_plugins:
                assert core not in installable

            # Non-core tiff plugin should be installable
            assert 'bioio-tiff-glob' in installable


class TestReaderPluginManagerInstallable:
    """Test ReaderPluginManager.installable_plugins for various file types."""

    @pytest.mark.parametrize(
        ('filename', 'expected_plugin'),
        [
            ('test.czi', 'bioio-czi'),
            ('test.lif', 'bioio-lif'),
            ('test.nd2', 'bioio-nd2'),
            ('test.dv', 'bioio-dv'),
        ],
    )
    def test_proprietary_formats_suggest_correct_plugin(
        self, filename, expected_plugin
    ):
        """Test that proprietary formats suggest the correct plugin."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager(filename)
            plugins = manager.installable_plugins

        assert expected_plugin in plugins

    def test_unsupported_extension_returns_empty(self):
        """Test that unsupported extensions return empty installable list."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager('test.xyz')
            plugins = manager.installable_plugins

        assert len(plugins) == 0


class TestReaderPluginManagerGetWorkingReader:
    """Test ReaderPluginManager.get_working_reader method."""

    def test_no_path_returns_none(self, caplog):
        """Test that get_working_reader returns None without a path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()  # No path

        with caplog.at_level(logging.WARNING):
            result = manager.get_working_reader()

        assert result is None
        assert 'Cannot get working reader without a path' in caplog.text

    def test_returns_working_reader_when_available(self, resources_dir):
        """Test that get_working_reader returns a reader for supported files."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')
        reader = manager.get_working_reader()

        assert reader is not None
        # bioio-ome-tiff is preferred for OME-TIFF files
        assert 'ome_tiff' in reader.__module__


class TestReaderPluginManagerGetInstallationMessage:
    """Test ReaderPluginManager.get_installation_message method."""

    def test_no_path_returns_empty(self):
        """Test that get_installation_message returns empty without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()  # No path

        assert manager.get_installation_message() == ''

    def test_with_installable_plugins_returns_message(self):
        """Test that message is generated when plugins are installable."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager('test.czi')
            message = manager.get_installation_message()

        assert 'bioio-czi' in message
        assert 'pip install' in message or 'install' in message.lower()


class TestReaderPluginManagerFeasibilityReport:
    """Test feasibility_report caching behavior."""

    def test_feasibility_report_cached(self):
        """Test that feasibility_report is cached."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}

            manager = ReaderPluginManager('test.czi')

            # Access multiple times
            _ = manager.feasibility_report
            _ = manager.feasibility_report
            _ = manager.feasibility_report

            # Should only be called once due to @cached_property
            assert mock_report.call_count == 1

    def test_no_path_returns_empty_report(self):
        """Test that feasibility_report returns empty dict without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()  # No path

        assert manager.feasibility_report == {}

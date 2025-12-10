"""Tests for ReaderPluginManager class from _plugin_manager module.

Note: Extension-to-plugin mapping is tested in test_bioio_plugin_utils.py
via TestSuggestPluginsForPath. We trust those unit tests and don't duplicate here.
"""

import logging
from unittest.mock import Mock, patch


class TestReaderPluginManager:
    """Tests for ReaderPluginManager properties and methods."""

    def test_known_plugins_matches_bioio_plugins_registry(self):
        """Test that known_plugins returns all plugins from BIOIO_PLUGINS."""
        from ndevio._bioio_plugin_utils import BIOIO_PLUGINS
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()

        assert set(manager.known_plugins) == set(BIOIO_PLUGINS.keys())

    def test_installed_plugins_from_feasibility_report(self):
        """Test that installed_plugins filters to bioio plugins from report."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {
                'bioio-czi': Mock(supported=False),
                'bioio-ome-tiff': Mock(supported=True),
                'ArrayLike': Mock(supported=False),  # Not a bioio plugin
            }
            manager = ReaderPluginManager('test.czi')

            # Only bioio-* plugins should be included
            assert 'bioio-czi' in manager.installed_plugins
            assert 'bioio-ome-tiff' in manager.installed_plugins
            assert 'ArrayLike' not in manager.installed_plugins

    def test_installable_excludes_installed_and_core(self):
        """Test installable_plugins excludes installed and core plugins."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            # Simulate: bioio-ome-tiff installed, nothing else
            mock_report.return_value = {
                'bioio-ome-tiff': Mock(supported=True),
                'ArrayLike': Mock(supported=False),
            }
            manager = ReaderPluginManager('test.tiff')
            installable = manager.installable_plugins

            # Core plugins never in installable (even if "suggested" by extension)
            assert 'bioio-ome-tiff' not in installable
            assert 'bioio-tifffile' not in installable
            # Non-core tiff plugin should be installable
            assert 'bioio-tiff-glob' in installable

    def test_feasibility_report_cached(self):
        """Test that feasibility_report is cached via @cached_property."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            mock_report.return_value = {'ArrayLike': Mock(supported=False)}
            manager = ReaderPluginManager('test.czi')

            # Access multiple times
            _ = manager.feasibility_report
            _ = manager.feasibility_report
            _ = manager.installed_plugins  # Also uses feasibility_report

            # Should only call bioio once
            assert mock_report.call_count == 1


class TestReaderPluginManagerNoPath:
    """Tests for ReaderPluginManager edge cases when no path provided."""

    def test_feasibility_report_empty_without_path(self):
        """Test that feasibility_report returns {} without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        assert manager.feasibility_report == {}

    def test_get_working_reader_returns_none_with_warning(self, caplog):
        """Test get_working_reader returns None and logs warning without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()

        with caplog.at_level(logging.WARNING):
            result = manager.get_working_reader()

        assert result is None
        assert 'Cannot get working reader without a path' in caplog.text

    def test_get_installation_message_returns_empty(self):
        """Test get_installation_message returns '' without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        assert manager.get_installation_message() == ''


class TestReaderPluginManagerWithRealFiles:
    """Tests using real files to verify end-to-end behavior."""

    def test_get_working_reader_for_ome_tiff(self, resources_dir):
        """Test get_working_reader returns correct reader for OME-TIFF."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')
        reader = manager.get_working_reader()

        assert reader is not None
        assert 'ome_tiff' in reader.__module__

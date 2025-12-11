"""Tests for ReaderPluginManager class from _plugin_manager module.

Note: Extension-to-plugin mapping is tested in test_bioio_plugin_utils.py
via TestSuggestPluginsForPath. We trust those unit tests and don't duplicate here.
"""

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


class TestGetPriorityList:
    """Tests for get_priority_list method."""

    def test_priority_list_contains_reader_classes(self, resources_dir):
        """Test that priority list contains actual Reader classes."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')
        priority = manager.get_priority_list()

        assert len(priority) > 0
        # Each item should be a Reader class (has 'Reader' in name or is subclass)
        for reader_class in priority:
            assert hasattr(reader_class, '__name__')

    def test_preferred_reader_comes_first(self, resources_dir):
        """Test that preferred reader is first in priority list."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')

        # Without preferred reader
        _default_priority = manager.get_priority_list()

        # With preferred reader
        priority_with_pref = manager.get_priority_list(
            preferred_reader='bioio-tifffile'
        )

        # bioio-tifffile should be first when preferred
        assert 'tifffile' in priority_with_pref[0].__module__

    def test_preferred_reader_not_installed_is_skipped(self):
        """Test that non-installed preferred reader is skipped."""
        from ndevio._plugin_manager import ReaderPluginManager

        with patch('bioio.plugin_feasibility_report') as mock_report:
            # Only bioio-ome-tiff installed
            mock_report.return_value = {
                'bioio-ome-tiff': Mock(supported=True),
            }
            manager = ReaderPluginManager('test.tiff')

            # Request non-installed reader as preferred
            priority = manager.get_priority_list(preferred_reader='bioio-czi')

            # Should not crash, czi should not be in list
            assert len(priority) > 0
            for reader_class in priority:
                assert 'czi' not in reader_class.__module__


class TestReaderPluginManagerNoPath:
    """Tests for ReaderPluginManager edge cases when no path provided."""

    def test_feasibility_report_empty_without_path(self):
        """Test that feasibility_report returns {} without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        assert manager.feasibility_report == {}

    def test_get_priority_list_returns_empty_without_path(self):
        """Test get_priority_list returns empty list without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        result = manager.get_priority_list()

        assert result == []

    def test_get_installation_message_returns_empty(self):
        """Test get_installation_message returns '' without path."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager()
        assert manager.get_installation_message() == ''


class TestReaderPluginManagerWithRealFiles:
    """Tests using real files to verify end-to-end behavior."""

    def test_get_priority_list_returns_installed_readers(self, resources_dir):
        """Test get_priority_list returns installed readers in BIOIO_PLUGINS order."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')
        priority = manager.get_priority_list()

        # Should have at least one reader (core plugins are always installed)
        assert len(priority) > 0
        # Each item should be a Reader class
        for reader_class in priority:
            assert hasattr(reader_class, '__name__')

    def test_get_priority_list_with_preferred_reader(self, resources_dir):
        """Test get_priority_list respects preferred_reader."""
        from ndevio._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(resources_dir / 'cells3d2ch_legacy.tiff')
        priority = manager.get_priority_list(preferred_reader='bioio-tifffile')

        assert len(priority) > 0
        # bioio-tifffile should be first when preferred
        assert 'tifffile' in priority[0].__module__

"""Tests for _bioio_plugin_utils module.

This module tests the utility functions in _bioio_plugin_utils.py:
- suggest_plugins_for_path: suggests plugins based on file extension
- format_plugin_installation_message: formats installation instructions
- BIOIO_PLUGINS: the plugin metadata registry

For ReaderPluginManager tests, see test_plugin_manager.py
"""

import pytest


class TestSuggestPluginsForPath:
    """Test suggest_plugins_for_path function."""

    @pytest.mark.parametrize(
        ('filename', 'expected_plugins'),
        [
            ('test.czi', ['bioio-czi']),
            ('test.lif', ['bioio-lif']),
            ('test.nd2', ['bioio-nd2']),
            ('test.dv', ['bioio-dv']),
        ],
    )
    def test_proprietary_formats(self, filename, expected_plugins):
        """Test that proprietary formats suggest correct plugins."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path(filename)

        assert plugins == expected_plugins

    def test_tiff_suggests_all_tiff_plugins(self):
        """Test that TIFF files suggest all TIFF-compatible plugins."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path('test.tiff')

        assert 'bioio-ome-tiff' in plugins
        assert 'bioio-tifffile' in plugins
        assert 'bioio-tiff-glob' in plugins

    def test_unsupported_extension_returns_empty(self):
        """Test that unsupported extensions return empty list."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path('test.xyz')

        assert plugins == []


class TestFormatPluginInstallationMessage:
    """Test format_plugin_installation_message function."""

    def test_czi_message_basic(self):
        """Test message generation for CZI file."""
        from ndevio._bioio_plugin_utils import (
            format_plugin_installation_message,
            suggest_plugins_for_path,
        )

        suggested = suggest_plugins_for_path('test.czi')
        message = format_plugin_installation_message(
            filename='test.czi',
            suggested_plugins=suggested,
            installed_plugins=set(),
            installable_plugins=suggested,
        )

        assert 'bioio-czi' in message
        assert 'pip install' in message or 'conda install' in message

    def test_unsupported_extension_message(self):
        """Test message for completely unsupported extension."""
        from ndevio._bioio_plugin_utils import (
            format_plugin_installation_message,
        )

        message = format_plugin_installation_message(
            filename='test.xyz',
            suggested_plugins=[],
            installed_plugins=set(),
            installable_plugins=[],
        )

        assert 'No bioio plugins found' in message or '.xyz' in message

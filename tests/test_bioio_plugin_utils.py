"""Tests for _bioio_plugin_utils module.

This module tests:
- suggest_plugins_for_path: maps file extensions to bioio plugin names
- format_plugin_installation_message: formats installation instructions
- BIOIO_PLUGINS: the plugin metadata registry
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
            ('test.xyz', []),  # Unsupported returns empty
        ],
    )
    def test_extension_to_plugin_mapping(self, filename, expected_plugins):
        """Test that file extensions map to correct plugin suggestions."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path(filename)
        assert plugins == expected_plugins

    def test_tiff_suggests_multiple_plugins(self):
        """Test that TIFF files suggest all TIFF-compatible plugins."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path('test.tiff')

        # TIFF has multiple compatible readers
        assert 'bioio-ome-tiff' in plugins
        assert 'bioio-tifffile' in plugins
        assert 'bioio-tiff-glob' in plugins


class TestFormatPluginInstallationMessage:
    """Test format_plugin_installation_message function."""

    def test_message_with_installable_plugins(self):
        """Test message includes plugin name and install command."""
        from ndevio._bioio_plugin_utils import (
            format_plugin_installation_message,
        )

        message = format_plugin_installation_message(
            filename='test.czi',
            suggested_plugins=['bioio-czi'],
            installed_plugins=set(),  # Not installed
            installable_plugins=['bioio-czi'],
        )

        assert 'bioio-czi' in message
        assert 'pip install' in message or 'conda install' in message

    def test_message_for_unsupported_extension(self):
        """Test message for extension with no known plugins."""
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

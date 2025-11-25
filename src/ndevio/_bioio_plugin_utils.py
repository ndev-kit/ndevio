"""Bioio plugin metadata and extension mapping.

This module contains the BIOIO_PLUGINS registry and low-level utilities for
plugin discovery. The ReaderPluginManager uses these utilities internally.

Public API:
    BIOIO_PLUGINS - Dict of all bioio plugins and their file extensions
    suggest_plugins_for_path() - Get list of suggested plugins by file extension
    get_reader_priority() - Get reader priority list from BIOIO_PLUGINS order

Internal API (used by ReaderPluginManager):
    format_plugin_installation_message() - Generate installation message

Note:
    For plugin detection, installation recommendations, and reader selection,
    use ReaderPluginManager from ndevio._plugin_manager. Don't call these
    utilities directly unless you're implementing low-level plugin logic.

Example:
    >>> # Recommended: Use ReaderPluginManager
    >>> from ndevio._plugin_manager import ReaderPluginManager
    >>> manager = ReaderPluginManager("image.czi")
    >>> print(manager.installable_plugins)
    >>> print(manager.get_installation_message())
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Bioio plugins and their supported extensions
# Source: https://github.com/bioio-devs/bioio
#
# ORDERING MATTERS: Plugins are listed in priority order (highest priority first).
# This order is used by ReaderPluginManager when selecting readers.
# Priority is based on:
# 1. Metadata preservation quality (OME formats preserve most metadata)
# 2. Reliability and performance for specific formats
# 3. Known issues or limitations
BIOIO_PLUGINS = {
    # Highest priority: OME formats with excellent metadata preservation
    "bioio-ome-zarr": {
        "extensions": [".zarr"],
        "description": "OME-Zarr files",
        "repository": "https://github.com/bioio-devs/bioio-ome-zarr",
        "core": True,
    },
    "bioio-ome-tiff": {
        "extensions": [".ome.tif", ".ome.tiff", ".tif", ".tiff"],
        "description": "OME-TIFF files with valid OME-XML metadata",
        "repository": "https://github.com/bioio-devs/bioio-ome-tiff",
        "core": True,
    },
    "bioio-ome-tiled-tiff": {
        "extensions": [".tiles.ome.tif"],
        "description": "Tiled OME-TIFF files",
        "repository": "https://github.com/bioio-devs/bioio-ome-tiled-tiff",
    },
    # High priority: Format-specific readers with good metadata support
    "bioio-tifffile": {
        "extensions": [".tif", ".tiff"],
        "description": "TIFF files (including those without OME metadata)",
        "repository": "https://github.com/bioio-devs/bioio-tifffile",
        "core": True,
    },
    "bioio-nd2": {
        "extensions": [".nd2"],
        "description": "Nikon ND2 files",
        "repository": "https://github.com/bioio-devs/bioio-nd2",
    },
    "bioio-czi": {
        "extensions": [".czi"],
        "description": "Zeiss CZI files",
        "repository": "https://github.com/bioio-devs/bioio-czi",
    },
    "bioio-lif": {
        "extensions": [".lif"],
        "description": "Leica LIF files",
        "repository": "https://github.com/bioio-devs/bioio-lif",
    },
    "bioio-dv": {
        "extensions": [".dv", ".r3d"],
        "description": "DeltaVision files",
        "repository": "https://github.com/bioio-devs/bioio-dv",
    },
    "bioio-sldy": {
        "extensions": [".sldy", ".dir"],
        "description": "3i SlideBook files",
        "repository": "https://github.com/bioio-devs/bioio-sldy",
    },
    # Lower priority: Generic/fallback readers
    "bioio-imageio": {
        "extensions": [".bmp", ".gif", ".jpg", ".jpeg", ".png"],
        "description": "Generic image formats (PNG, JPG, etc.)",
        "repository": "https://github.com/bioio-devs/bioio-imageio",
        "core": True,
    },
    "bioio-tiff-glob": {
        "extensions": [".tiff"],
        "description": "TIFF sequences (glob patterns)",
        "repository": "https://github.com/bioio-devs/bioio-tiff-glob",
    },
    # Lowest priority: Requires external dependencies (Java)
    "bioio-bioformats": {
        "extensions": [".oib", ".oif", ".vsi", ".ims", ".lsm", ".stk"],
        "description": "Proprietary microscopy formats (requires Java)",
        "repository": "https://github.com/bioio-devs/bioio-bioformats",
        "note": "Requires Java Runtime Environment",
    },
}

# Map extensions to plugin names for quick lookup
_EXTENSION_TO_PLUGIN = {}
for plugin_name, info in BIOIO_PLUGINS.items():
    for ext in info["extensions"]:
        if ext not in _EXTENSION_TO_PLUGIN:
            _EXTENSION_TO_PLUGIN[ext] = []
        _EXTENSION_TO_PLUGIN[ext].append(plugin_name)


def get_reader_priority() -> list[str]:
    """Get reader priority list from BIOIO_PLUGINS dictionary order.

    Returns plugin names in priority order (highest priority first).
    This order is used by ReaderPluginManager when selecting readers.

    Returns
    -------
    list of str
        Plugin names in priority order

    Examples
    --------
    >>> from ndevio._bioio_plugin_utils import get_reader_priority
    >>> priority = get_reader_priority()
    >>> print(priority[0])  # Highest priority reader
    'bioio-ome-zarr'
    """
    return list(BIOIO_PLUGINS.keys())


def format_plugin_installation_message(
    filename: str,
    suggested_plugins: list[str],
    installed_plugins: set[str],
    installable_plugins: list[str],
) -> str:
    """Generate installation message for bioio plugins.

    This function formats a helpful error message based on the plugin state.
    Used internally by ReaderPluginManager.get_installation_message().

    Parameters
    ----------
    filename : str
        Name of the file that couldn't be read
    suggested_plugins : list of str
        Names of all plugins that could read this file type
    installed_plugins : set of str
        Names of plugins that are already installed
    installable_plugins : list of str
        Names of non-core plugins that aren't installed but could read the file

    Returns
    -------
    str
        Formatted installation instructions

    Notes
    -----
    This is a helper function used by ReaderPluginManager. Use the manager's
    get_installation_message() method instead of calling this directly.
    """
    # No plugins found for this extension
    if not suggested_plugins:
        return (
            f"\n\nNo bioio plugins found for '{filename}'.\n"
            "See https://github.com/bioio-devs/bioio for available plugins."
        )

    # Format the plugin list (filters out core plugins automatically)
    plugin_list = _format_plugin_list(installable_plugins)

    # Build appropriate message based on what's installed/missing
    if installed_plugins and installable_plugins and plugin_list:
        # Case 1: Some plugins installed but failed, suggest alternatives
        installed_str = ", ".join(sorted(installed_plugins))
        return (
            f"\n\nInstalled plugin '{installed_str}' failed to read '{filename}'.\n"
            "Try one of these alternatives:\n\n"
            f"{plugin_list}"
            "\nRestart napari/Python after installing."
        )

    if installed_plugins and not installable_plugins:
        # Case 2: All suggested plugins already installed but still failed
        installed_str = ", ".join(sorted(installed_plugins))
        return (
            f"\nFile '{filename}' is supported by: {installed_str}\n"
            "However, the plugin failed to read it.\n"
            "This may indicate a corrupt file or incompatible format variant."
        )

    if plugin_list:
        # Case 3: No installed plugins, suggest installing
        return (
            f"\n\nTo read '{filename}', install one of:\n\n"
            f"{plugin_list}"
            "\nRestart napari/Python after installing."
        )

    # Case 4: All suggested plugins are core plugins (already should be installed)
    return (
        f"\n\nRequired plugins for '{filename}' should already be installed.\n"
        "If you're still having issues, check your installation or "
        "open an issue at https://github.com/ndev-kit/ndevio."
    )


def suggest_plugins_for_path(path: Path | str) -> list[str]:
    """Get list of bioio plugin names that could read the given file.

    Returns all plugin names that support the file's extension, regardless of
    whether they're installed or core plugins.

    Parameters
    ----------
    path : Path or str
        File path to check

    Returns
    -------
    list of str
        List of plugin names (e.g., 'bioio-czi', 'bioio-ome-tiff') that
        could read this file. Empty list if no plugins support the extension.

    Examples
    --------
    >>> from ndevio._bioio_plugin_utils import suggest_plugins_for_path
    >>> plugins = suggest_plugins_for_path("image.czi")
    >>> print(plugins[0])
    'bioio-czi'
    """
    from pathlib import Path

    path = Path(path)
    filename = path.name.lower()

    # Check compound extensions first (.ome.tiff, .tiles.ome.tif, etc.)
    for plugin_name, info in BIOIO_PLUGINS.items():
        for ext in info["extensions"]:
            # Compound extension: multiple dots and matches filename
            if (
                ext.startswith(".")
                and len(ext.split(".")) > 2
                and filename.endswith(ext)
            ):
                return [plugin_name]

    # Fall back to simple extension matching
    file_ext = path.suffix.lower()

    if file_ext in _EXTENSION_TO_PLUGIN:
        return _EXTENSION_TO_PLUGIN[file_ext].copy()

    return []


def _format_plugin_list(plugin_names: list[str]) -> str:
    """Format a list of plugin names with installation instructions.

    Parameters
    ----------
    plugin_names : list of str
        Plugin names to format (e.g., ['bioio-czi', 'bioio-lif'])

    Returns
    -------
    str
        Formatted installation instructions
    """
    if not plugin_names:
        return ""

    lines = []
    for plugin_name in plugin_names:
        # Look up plugin info from registry
        info = BIOIO_PLUGINS.get(plugin_name)
        if not info:
            continue

        # Skip core plugins (already installed with ndevio)
        if info.get("core", False):
            continue

        lines.append(f"  • {plugin_name}")
        lines.append(f"    {info['description']}")
        if info.get("note"):
            lines.append(f"    Note: {info['note']}")
        lines.append(f"    Install: pip install {plugin_name}\n")

    return "\n".join(lines)

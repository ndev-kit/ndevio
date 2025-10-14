"""Bioio plugin metadata and extension mapping.

This module contains the BIOIO_PLUGINS registry and low-level utilities for
plugin discovery. The ReaderPluginManager uses these utilities internally.

Public API:
    BIOIO_PLUGINS - Dict of all bioio plugins and their file extensions
    suggest_plugins_for_path() - Get list of suggested plugins by file extension

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
BIOIO_PLUGINS = {
    "bioio-czi": {
        "extensions": [".czi"],
        "description": "Zeiss CZI files",
        "repository": "https://github.com/bioio-devs/bioio-czi",
    },
    "bioio-dv": {
        "extensions": [".dv", ".r3d"],
        "description": "DeltaVision files",
        "repository": "https://github.com/bioio-devs/bioio-dv",
    },
    "bioio-imageio": {
        "extensions": [".bmp", ".gif", ".jpg", ".jpeg", ".png"],
        "description": "Generic image formats (PNG, JPG, etc.)",
        "repository": "https://github.com/bioio-devs/bioio-imageio",
        "core": True,
    },
    "bioio-lif": {
        "extensions": [".lif"],
        "description": "Leica LIF files",
        "repository": "https://github.com/bioio-devs/bioio-lif",
    },
    "bioio-nd2": {
        "extensions": [".nd2"],
        "description": "Nikon ND2 files",
        "repository": "https://github.com/bioio-devs/bioio-nd2",
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
    "bioio-ome-zarr": {
        "extensions": [".zarr"],
        "description": "OME-Zarr files",
        "repository": "https://github.com/bioio-devs/bioio-ome-zarr",
        "core": True,
    },
    "bioio-sldy": {
        "extensions": [".sldy", ".dir"],
        "description": "3i SlideBook files",
        "repository": "https://github.com/bioio-devs/bioio-sldy",
    },
    "bioio-tifffile": {
        "extensions": [".tif", ".tiff"],
        "description": "TIFF files (including those without OME metadata)",
        "repository": "https://github.com/bioio-devs/bioio-tifffile",
    },
    "bioio-tiff-glob": {
        "extensions": [".tiff"],
        "description": "TIFF sequences (glob patterns)",
        "repository": "https://github.com/bioio-devs/bioio-tiff-glob",
    },
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


def format_plugin_installation_message(
    filename: str,
    suggested_plugins: list[dict[str, str]],
    installed_plugins: set[str],
    installable_plugins: list[dict[str, str]],
) -> str:
    """Generate installation message for bioio plugins.

    This function formats a helpful error message based on the plugin state.
    Used internally by ReaderPluginManager.get_installation_message().

    Parameters
    ----------
    filename : str
        Name of the file that couldn't be read
    suggested_plugins : list of dict
        All plugins that could read this file type
    installed_plugins : set of str
        Names of plugins that are already installed
    installable_plugins : list of dict
        Non-core plugins that aren't installed but could read the file

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


def suggest_plugins_for_path(path: Path | str) -> list[dict[str, str]]:
    """Get list of bioio plugins that could read the given file.

    Returns all plugins that support the file's extension, regardless of
    whether they're installed or core plugins.

    Parameters
    ----------
    path : Path or str
        File path to check

    Returns
    -------
    list of dict
        List of plugin info dicts with keys: name, description, repository,
        extensions, and optionally 'core' and 'note'.
        Each dict represents a bioio plugin that could read this file.

    Examples
    --------
    >>> from ndevio._bioio_plugin_utils import suggest_plugins_for_path
    >>> plugins = suggest_plugins_for_path("image.czi")
    >>> print(plugins[0]["name"])
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
                result = info.copy()
                result["name"] = plugin_name
                return [result]

    # Fall back to simple extension matching
    file_ext = path.suffix.lower()
    suggestions = []

    if file_ext in _EXTENSION_TO_PLUGIN:
        for plugin_name in _EXTENSION_TO_PLUGIN[file_ext]:
            info = BIOIO_PLUGINS[plugin_name].copy()
            info["name"] = plugin_name
            suggestions.append(info)

    return suggestions


def _format_plugin_list(plugins: list[dict[str, str]]) -> str:
    """Format a list of plugins with installation instructions."""
    # Filter out core plugins (already installed with ndevio)
    non_core = [p for p in plugins if not p.get("core", False)]

    if not non_core:
        return ""

    lines = []
    for plugin in non_core:
        lines.append(f"  • {plugin['name']}")
        lines.append(f"    {plugin['description']}")
        if plugin.get("note"):
            lines.append(f"    Note: {plugin['note']}")
        lines.append(f"    Install: pip install {plugin['name']}\n")

    return "\n".join(lines)

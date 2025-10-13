"""Bioio plugin utilities and metadata.

This module provides low-level utilities for bioio plugin discovery and messaging.
Most users should use ReaderPluginManager for a higher-level API.

Public API:
    BIOIO_PLUGINS - Dict of all bioio plugins and their file extensions
    suggest_plugins_for_path() - Get list of suggested plugins for a file (low-level)
    get_missing_plugins_message() - Generate installation message (used internally)

Note:
    For plugin detection, installation recommendations, and reader selection,
    use ReaderPluginManager from ndevio._plugin_manager instead of calling
    these functions directly.

Example:
    >>> # Recommended: Use ReaderPluginManager
    >>> from ndevio._plugin_manager import ReaderPluginManager
    >>> manager = ReaderPluginManager("image.czi")
    >>> print(manager.installable_plugins)
    >>> print(manager.get_installation_message())
    >>>
    >>> # Low-level: Direct use of utilities (not recommended)
    >>> from ndevio._bioio_plugin_utils import suggest_plugins_for_path
    >>> plugins = suggest_plugins_for_path("image.czi")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from bioio.plugins import PluginSupport

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


def get_missing_plugins_message(
    path: Path | str,
    feasibility_report: dict[str, PluginSupport] | None = None,
) -> str:
    """Generate installation message for missing bioio plugins.

    This function suggests which plugins to install based on file extension.
    If a feasibility report is provided, it will filter out already-installed
    plugins from the suggestions.

    Parameters
    ----------
    path : Path or str
        File path that couldn't be read
    feasibility_report : dict, optional
        Report from bioio.plugin_feasibility_report() showing installed plugins

    Returns
    -------
    str
        Installation instructions for missing plugins
    """
    from pathlib import Path

    path = Path(path)
    suggested_plugins = suggest_plugins_for_path(path)

    # No plugins found for this extension
    if not suggested_plugins:
        return (
            f"\n\nNo bioio plugins found for '{path.name}' (extension: {path.suffix}).\n"
            "See https://github.com/bioio-devs/bioio for available plugins."
        )

    # Determine which plugins are already installed
    installed_plugins = _get_installed_plugins(feasibility_report)

    # Filter to get only plugins that aren't installed
    if feasibility_report:
        missing_plugins = _filter_installed_plugins(
            suggested_plugins, feasibility_report
        )
    else:
        missing_plugins = suggested_plugins

    # Format the plugin list (filters out core plugins)
    plugin_list = _format_plugin_list(missing_plugins)

    # Build appropriate message based on what's installed/missing
    if installed_plugins and missing_plugins and plugin_list:
        # Case 1: Some plugins installed but failed, suggest alternatives
        installed_str = ", ".join(sorted(installed_plugins))
        return (
            f"\n\nInstalled plugin '{installed_str}' failed to read '{path.name}'.\n"
            "Try one of these alternatives:\n\n"
            f"{plugin_list}"
            "\nRestart napari/Python after installing."
        )

    if installed_plugins and not missing_plugins:
        # Case 2: All suggested plugins already installed but still failed
        installed_str = ", ".join(sorted(installed_plugins))
        return (
            f"\nFile '{path.name}' is supported by: {installed_str}\n"
            "However, the plugin failed to read it.\n"
            "This may indicate a corrupt file or incompatible format variant."
        )

    if plugin_list:
        # Case 3: No installed plugins, suggest installing
        return (
            f"\n\nTo read '{path.name}', install one of:\n\n"
            f"{plugin_list}"
            "\nRestart napari/Python after installing."
        )

    # Case 4: All suggested plugins are core plugins (already should be installed)
    return (
        f"\n\nRequired plugins for '{path.name}' should already be installed.\n"
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


def _get_installed_plugins(
    feasibility_report: dict[str, PluginSupport] | None,
) -> set[str]:
    """Extract installed plugin names from feasibility report.

    The feasibility report from bioio.plugin_feasibility_report() includes
    all installed plugins. The 'supported' field indicates whether each
    plugin can read the specific file, but the presence of a plugin in the
    report means it's installed.

    Parameters
    ----------
    feasibility_report : dict, optional
        Report from bioio.plugin_feasibility_report()

    Returns
    -------
    set of str
        Set of installed plugin names (excludes "ArrayLike")

    Notes
    -----
    This is a helper function used internally by get_missing_plugins_message().
    For plugin detection, use ReaderPluginManager.installed_plugins instead.
    """
    if not feasibility_report:
        return set()

    # If a plugin appears in the report, it's installed
    return {name for name in feasibility_report if name != "ArrayLike"}


def _filter_installed_plugins(
    suggested_plugins: list[dict[str, str]],
    feasibility_report: dict[str, PluginSupport] | None = None,
) -> list[dict[str, str]]:
    """Filter out already-installed plugins from a list of suggested plugins.

    Parameters
    ----------
    suggested_plugins : list of dict
        List of plugin info dicts from suggest_plugins_for_path()
    feasibility_report : dict, optional
        Report from bioio.plugin_feasibility_report() showing installed plugins.
        If None, returns all suggested plugins unchanged.

    Returns
    -------
    list of dict
        List of plugins that are not already installed

    Notes
    -----
    This is a helper function used internally by get_missing_plugins_message().
    For plugin detection, use ReaderPluginManager.installable_plugins instead.
    """
    if not feasibility_report:
        # No feasibility report, can't filter - return all
        return suggested_plugins

    # Determine which plugins are already installed
    installed_plugins = _get_installed_plugins(feasibility_report)

    # Filter to get plugins that aren't installed
    return [p for p in suggested_plugins if p["name"] not in installed_plugins]


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

"""Bioio plugin installation suggestions for unsupported file formats.

This module suggests missing bioio plugins to install when a file can't be read.
The suggestions are based on file extensions and installed plugin detection.

Public API:
    get_missing_plugins_message() - Generate installation message for missing plugins
    BIOIO_PLUGINS - Dict of all bioio plugins and their file extensions

Example:
    >>> from ndevio._bioio_plugin_utils import get_missing_plugins_message
    >>>
    >>> # Simple usage - just provide the path
    >>> message = get_missing_plugins_message("image.czi")
    >>> print(message)
    >>>
    >>> # With feasibility report to detect what's already installed
    >>> from bioio import plugin_feasibility_report
    >>> report = plugin_feasibility_report("image.czi")
    >>> message = get_missing_plugins_message("image.czi", report)
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

    # Get all plugins that support this file extension
    suggested_plugins = _suggest_plugins_for_path(path)

    if feasibility_report:
        # Find plugins that claim to support the file (are installed)
        installed_plugins = {
            name
            for name, support in feasibility_report.items()
            if name != "ArrayLike" and support.supported
        }

        if installed_plugins:
            # Filter out plugins that are already installed
            missing_plugins = [
                p
                for p in suggested_plugins
                if p["name"] not in installed_plugins
            ]

            if missing_plugins:
                # Some plugins installed but failed, suggest others
                installed_str = ", ".join(sorted(installed_plugins))
                msg_parts = [
                    f"\nInstalled plugin '{installed_str}' failed to read '{path.name}'.",
                    "Try one of these alternatives:\n",
                ]
                msg_parts.append(
                    _format_installation_message(missing_plugins, path.name)
                )
                msg_parts.append("Restart napari/Python after installing.")
                return "\n".join(msg_parts)
            else:
                # All suggested plugins already installed but still failed
                installed_str = ", ".join(sorted(installed_plugins))
                return (
                    f"File '{path.name}' is supported by: {installed_str}\n"
                    f"However, the plugin failed to read it.\n"
                    "This may indicate a corrupt file or incompatible format variant."
                )

    # No feasibility report or no installed plugins - suggest all
    return _format_installation_message(suggested_plugins, path.name)


def _suggest_plugins_for_extension(file_ext: str) -> list[dict[str, str]]:
    """Suggest bioio plugins based on file extension."""
    file_ext = file_ext.lower()
    suggestions = []

    if file_ext in _EXTENSION_TO_PLUGIN:
        for plugin_name in _EXTENSION_TO_PLUGIN[file_ext]:
            info = BIOIO_PLUGINS[plugin_name].copy()
            info["name"] = plugin_name
            suggestions.append(info)

    return suggestions


def _suggest_plugins_for_path(path: Path | str) -> list[dict[str, str]]:
    """Suggest bioio plugins based on file path (handles compound extensions)."""
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
    return _suggest_plugins_for_extension(path.suffix)


def _format_installation_message(
    plugins: list[dict[str, str]], file_name: str
) -> str:
    """Format installation instructions for missing plugins."""
    if not plugins:
        return (
            f"No bioio plugins found for '{file_name}'.\n"
            "See https://github.com/bioio-devs/bioio for available plugins."
        )

    # Filter out core plugins (already installed with ndevio)
    non_core = [p for p in plugins if not p.get("core", False)]

    if not non_core:
        return (
            f"Required plugins for '{file_name}' should already be installed.\n"
            "If you're still having issues, check your installation or "
            "open an issue at https://github.com/ndev-kit/ndevio."
        )

    msg = []

    for plugin in non_core:
        msg.append(f"  • {plugin['name']}")
        msg.append(f"    {plugin['description']}")
        if plugin.get("note"):
            msg.append(f"    Note: {plugin['note']}")
        msg.append(f"    Install: pip install {plugin['name']}\n")

    return "\n".join(msg)

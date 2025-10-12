"""Bioio plugin compatibility checking and installation suggestions.

This module analyzes which bioio plugins can read a file and generates
helpful error messages with installation instructions when files can't be read.

Public API:
    get_missing_plugins_message() - Generate error message with plugin suggestions
    BIOIO_PLUGINS - Dict of all bioio plugins and their file extensions

Example:
    >>> from bioio import plugin_feasibility_report
    >>> from ndevio._bioio_plugin_utils import get_missing_plugins_message
    >>>
    >>> path = "image.czi"
    >>> report = plugin_feasibility_report(path)
    >>> message = get_missing_plugins_message(path, report)
    >>> print(message)
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


def _analyze_feasibility_report(
    feasibility_report: dict[str, PluginSupport],
) -> dict:
    """Analyze bioio feasibility report to find supported readers."""
    available_readers = []
    errors = {}

    for reader_name, support in feasibility_report.items():
        if reader_name == "ArrayLike":
            continue

        if support.supported:
            available_readers.append(reader_name)
        elif support.error:
            errors[reader_name] = support.error

    return {
        "supported": len(available_readers) > 0,
        "available_readers": available_readers,
        "errors": errors,
    }


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
    """Suggest bioio plugins for a file path, handling compound extensions."""
    from pathlib import Path

    path = Path(path)
    filename = path.name.lower()

    # Check compound extensions first (.ome.tiff, .tiles.ome.tif, etc.)
    for plugin_name, info in BIOIO_PLUGINS.items():
        for ext in info["extensions"]:
            if (
                ext.startswith(".")
                and len(ext.split(".")) > 2
                and filename.endswith(ext)
            ):
                result = info.copy()
                result["name"] = plugin_name
                return [result]

    return _suggest_plugins_for_extension(path.suffix)


def _format_plugin_suggestion(
    plugins: list[dict[str, str]], context: str = "this file"
) -> str:
    """Format installation message for suggested plugins."""
    if not plugins:
        return (
            f"No bioio plugins found for {context}.\n"
            "See https://github.com/bioio-devs/bioio for available plugins."
        )

    # Filter out core plugins (already installed)
    non_core = [p for p in plugins if not p.get("core", False)]

    if not non_core:
        return (
            f"The required plugins for {context} should already be installed.\n"
            "If you're still having issues, check your installation.\n"
            "Otherwise, open an issue at https://github.com/ndev-kit/ndevio."
        )

    msg = [f"To read {context}, you may need to install:\n"]

    for plugin in non_core:
        msg.append(f"\n  {plugin['name']}")
        msg.append(f"  {plugin['description']}")
        if plugin.get("note"):
            msg.append(f"  Note: {plugin['note']}")
        msg.append(f"\n  pip install {plugin['name']}")
        msg.append(f"  or: uv pip install {plugin['name']}")

    msg.append("\n\nRestart napari/Python after installing.")
    return "\n".join(msg)


def get_missing_plugins_message(
    path: Path | str,
    feasibility_report: dict[str, PluginSupport] | None = None,
) -> str:
    """Generate helpful error message when a file cannot be read.

    Parameters
    ----------
    path : Path or str
        File path that couldn't be read
    feasibility_report : dict, optional
        Report from bioio.plugin_feasibility_report()

    Returns
    -------
    str
        Human-readable error message with installation suggestions
    """
    from pathlib import Path

    path = Path(path)
    suggested_plugins = _suggest_plugins_for_path(path)

    if feasibility_report:
        analysis = _analyze_feasibility_report(feasibility_report)

        if analysis["supported"]:
            available_readers = analysis["available_readers"]
            assert isinstance(available_readers, list)
            installed_readers = set(available_readers)

            # Find suggested plugins that aren't installed
            missing_plugins = [
                p
                for p in suggested_plugins
                if p["name"] not in installed_readers
            ]

            if missing_plugins:
                msg = (
                    f"Installed plugin(s) {', '.join(sorted(installed_readers))} "
                    f"failed to read the file.\n"
                    "Try installing:\n"
                )
                msg += _format_plugin_suggestion(
                    missing_plugins, f"'{path.name}'"
                )
                return msg
            else:
                return (
                    f"File supported by: {', '.join(sorted(installed_readers))}\n"
                    "But the installed plugin(s) failed to read it.\n"
                    "Check the error logs for details."
                )

    # No installed plugins support this file
    if suggested_plugins:
        return _format_plugin_suggestion(suggested_plugins, f"'{path.name}'")
    else:
        return (
            f"No bioio plugins found for extension '{path.suffix}'.\n"
            "See https://github.com/bioio-devs/bioio for available plugins."
        )

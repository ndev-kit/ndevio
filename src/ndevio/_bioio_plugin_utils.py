"""Utilities for analyzing bioio reader feasibility and suggesting installations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from bioio.plugins import PluginSupport

logger = logging.getLogger(__name__)

# Complete map of bioio plugins and their supported extensions
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
        "extensions": [
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tif",
            ".tiff",
            ".webp",
            ".avif",
            ".svg",
        ],
        "description": "Generic image formats (PNG, JPG, etc.)",
        "repository": "https://github.com/bioio-devs/bioio-imageio",
        "core": True,  # Part of ndevio core dependencies
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
        "core": True,  # Part of ndevio core dependencies
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
        "core": True,  # Part of ndevio core dependencies
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
        "description": "TIFF sequences/stacks (glob patterns)",
        "repository": "https://github.com/bioio-devs/bioio-tiff-glob",
    },
    "bioio-bioformats": {
        "extensions": [
            # Many proprietary formats
            ".oib",
            ".oif",
            ".vsi",
            ".ims",
            ".lsm",
            ".stk",
            # Add more as needed
        ],
        "description": "Many proprietary microscopy formats (requires Java)",
        "repository": "https://github.com/bioio-devs/bioio-bioformats",
        "note": "Requires Java Runtime Environment (JRE)",
    },
}

# Map extensions to plugin names for quick lookup
EXTENSION_TO_PLUGIN = {}
for plugin_name, info in BIOIO_PLUGINS.items():
    for ext in info["extensions"]:
        if ext not in EXTENSION_TO_PLUGIN:
            EXTENSION_TO_PLUGIN[ext] = []
        EXTENSION_TO_PLUGIN[ext].append(plugin_name)


def analyze_feasibility_report(
    feasibility_report: dict[str, PluginSupport],
) -> dict[str, str | list[str] | bool]:
    """
    Analyze a bioio feasibility report and provide recommendations.

    Parameters
    ----------
    feasibility_report : dict[str, PluginSupport]
        Report from bioio.plugin_feasibility_report()

    Returns
    -------
    dict
        Analysis with keys:
        - "supported": bool - Whether any reader supports the file
        - "available_readers": list[str] - Readers that support the file
        - "errors": dict - Error messages from readers that don't support
    """
    available_readers = []
    errors = {}

    for reader_name, support in feasibility_report.items():
        if reader_name == "ArrayLike":
            continue  # Skip ArrayLike, not a real reader

        if support.supported:
            available_readers.append(reader_name)
        elif support.error:
            errors[reader_name] = support.error

    # Build analysis
    analysis = {
        "supported": len(available_readers) > 0,
        "available_readers": available_readers,
        "errors": errors,
    }

    return analysis


def suggest_plugins_for_extension(file_ext: str) -> list[dict[str, str]]:
    """
    Suggest bioio plugin packages based on file extension.

    Parameters
    ----------
    file_ext : str
        File extension (e.g., ".czi", ".tiff")

    Returns
    -------
    list[dict]
        List of plugin info dicts with keys: name, description, repository, note (optional)
    """
    file_ext = file_ext.lower()

    # Handle compound extensions like .ome.tiff
    suggestions = []

    # Check for exact matches
    if file_ext in EXTENSION_TO_PLUGIN:
        for plugin_name in EXTENSION_TO_PLUGIN[file_ext]:
            info = BIOIO_PLUGINS[plugin_name].copy()
            info["name"] = plugin_name
            suggestions.append(info)

    return suggestions


def suggest_plugins_for_path(path: Path | str) -> list[dict[str, str]]:
    """
    Suggest bioio plugin packages based on file path.

    Handles compound extensions like .ome.tiff correctly.

    Parameters
    ----------
    path : Path or str
        File path to analyze

    Returns
    -------
    list[dict]
        List of plugin info dicts with keys: name, description, repository, note (optional)
    """
    from pathlib import Path

    path = Path(path)
    filename = path.name.lower()

    # Check for compound extensions first (e.g., .ome.tiff, .tiles.ome.tif)
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
                return [result]  # Return first match for compound extensions

    # Fall back to simple extension matching
    return suggest_plugins_for_extension(path.suffix)


def format_plugin_suggestion(
    plugins: list[dict[str, str]], context: str = "this file"
) -> str:
    """
    Format a helpful message suggesting plugin installation.

    Parameters
    ----------
    plugins : list[dict]
        List of plugin info dicts from suggest_plugins_for_path/extension
    context : str
        Context for why plugins are needed

    Returns
    -------
    str
        Formatted suggestion message
    """
    if not plugins:
        return (
            f"No bioio plugins found for {context}.\n"
            "See https://github.com/bioio-devs/bioio for available plugins."
        )

    # Filter out core plugins that should already be installed
    non_core = [p for p in plugins if not p.get("core", False)]

    if not non_core:
        return (
            f"The required plugins for {context} should already be installed.\n"
            "If you're still having issues, check your installation."
        )

    msg_parts = [f"To read {context}, you may need to install:\n"]

    for plugin in non_core:
        msg_parts.append(f"\n  📦 {plugin['name']}")
        msg_parts.append(f"     {plugin['description']}")
        if plugin.get("note"):
            msg_parts.append(f"     ⚠️  {plugin['note']}")
        msg_parts.append(f"\n     Install: uv pip install {plugin['name']}")
        msg_parts.append(f"          or: pip install {plugin['name']}")

    msg_parts.append(
        "\n\nThen restart napari/Python to make the plugin available."
    )

    return "".join(msg_parts)


def get_missing_plugins_message(
    path: Path | str,
    feasibility_report: dict[str, PluginSupport] | None = None,
) -> str:
    """
    Generate a helpful error message when a file cannot be read.

    Combines feasibility report analysis with extension-based plugin suggestions.

    Parameters
    ----------
    path : Path or str
        File path that couldn't be read
    feasibility_report : dict, optional
        Report from bioio.plugin_feasibility_report(), if available

    Returns
    -------
    str
        Human-readable error message with installation suggestions
    """
    from pathlib import Path

    path = Path(path)

    # Get extension-based suggestions
    suggested_plugins = suggest_plugins_for_path(path)

    if feasibility_report:
        analysis = analyze_feasibility_report(feasibility_report)

        if analysis["supported"]:
            # File format claims to be supported but failed to read
            # Check if there are additional plugins to suggest
            available_readers = analysis["available_readers"]
            assert isinstance(available_readers, list)  # Type narrowing
            installed_readers = set(available_readers)

            # Find plugins that are suggested but not installed
            missing_plugins = [
                p
                for p in suggested_plugins
                if p["name"] not in installed_readers
            ]

            if missing_plugins:
                # Suggest additional plugins that might work better
                msg = (
                    f"Installed plugin(s) {', '.join(sorted(installed_readers))} "
                    f"could not read the file.\n"
                    f"You may need a different plugin:\n"
                )
                msg += format_plugin_suggestion(
                    missing_plugins, f"'{path.name}'"
                )
                return msg
            else:
                # All suggested plugins are installed but still failed
                return (
                    f"File format is supported by: {', '.join(sorted(installed_readers))}\n"
                    "But the installed plugin(s) failed to read the file.\n"
                    "Check the error logs for more details."
                )

    # File is not supported - suggest plugins
    if suggested_plugins:
        return format_plugin_suggestion(suggested_plugins, f"'{path.name}'")
    else:
        return (
            f"No bioio plugins found for files with extension '{path.suffix}'.\n"
            "See https://github.com/bioio-devs/bioio for available plugins."
        )

"""Test script for reader feasibility analysis and plugin suggestions."""

from pathlib import Path

import bioio

from ndevio._reader_utils import (
    BIOIO_PLUGINS,
    get_missing_plugins_message,
    suggest_plugins_for_path,
)

# Get the resources directory relative to this script
script_dir = Path(__file__).parent
resources_dir = script_dir.parent / "tests" / "resources"

images = [
    "0T-4C-0Z-7pos.czi",
    "cells3d2ch_legacy.tiff",
    "RGB_bad_metadata.tiff",
    "nDev-logo-small.png",
]

print("=" * 80)
print("NDEVIO BIOIO PLUGIN SUGGESTION TOOL")
print("=" * 80)
print(f"\n📚 Total bioio plugins in database: {len(BIOIO_PLUGINS)}")
print(f"📁 Resources directory: {resources_dir}")
print(f"   (exists: {resources_dir.exists()})")
print()

for image in images:
    image_path = resources_dir / image
    print(f"\n{'=' * 80}")
    print(f"📄 File: {image_path.name}")
    print(f"   Path: {image_path}")
    print(f"   Exists: {image_path.exists()}")
    print("=" * 80)

    # Get feasibility report from bioio
    fr = bioio.plugin_feasibility_report(image_path)

    # Show what plugins COULD support this file (based on extension)
    suggested_plugins = suggest_plugins_for_path(image_path)

    print(f"\n� Extension-based suggestions ({image_path.suffix}):")
    if suggested_plugins:
        for plugin in suggested_plugins:
            core_marker = " [CORE]" if plugin.get("core", False) else ""
            print(f"  • {plugin['name']}{core_marker}")
            print(f"    {plugin['description']}")
            if plugin.get("note"):
                print(f"    ⚠️  {plugin['note']}")
    else:
        print("  No plugins found for this extension")

    # Show what's actually installed and supports it
    supported_by = [
        name
        for name, support in fr.items()
        if support.supported and name != "ArrayLike"
    ]

    print("\n✅ Actually supported by (installed):")
    if supported_by:
        for reader in supported_by:
            print(f"  • {reader}")
    else:
        print("  ❌ No installed readers support this file")

        # Show installation suggestion
        message = get_missing_plugins_message(image_path, fr)
        print("\n💡 Installation suggestion:")
        for line in message.split("\n"):
            print(f"  {line}")

    print()

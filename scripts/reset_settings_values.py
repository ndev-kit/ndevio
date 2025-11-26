#!/usr/bin/env python
"""Pre-commit hook to reset settings values to their defaults.

This ensures that the committed settings file always has value == default,
preventing accidental commits of local user preferences.
"""
import sys
from pathlib import Path

import yaml


def reset_settings_to_defaults(settings_file: Path) -> bool:
    """Reset all 'value' fields to match 'default' fields.

    Returns True if file was modified, False otherwise.
    """
    with open(settings_file) as f:
        settings = yaml.safe_load(f)

    if not settings:
        return False

    modified = False

    for group_name, group_settings in settings.items():
        for setting_name, setting_data in group_settings.items():
            if (
                isinstance(setting_data, dict)
                and "default" in setting_data
                and "value" in setting_data
                and setting_data["value"] != setting_data["default"]
            ):
                print(
                    f"Resetting {group_name}.{setting_name}: "
                    f"{setting_data['value']} -> {setting_data['default']}"
                )
                setting_data["value"] = setting_data["default"]
                modified = True

    if modified:
        with open(settings_file, "w") as f:
            yaml.dump(settings, f, default_flow_style=False, sort_keys=False)

    return modified


def main():
    """Main entry point for pre-commit hook."""
    settings_file = (
        Path(__file__).parent.parent / "src" / "ndevio" / "ndev_settings.yaml"
    )

    if not settings_file.exists():
        print(f"Settings file not found: {settings_file}")
        return 1

    if reset_settings_to_defaults(settings_file):
        print(
            "\nWARNING: Settings file was modified to reset values to defaults."
        )
        print("Please review and re-stage the changes.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

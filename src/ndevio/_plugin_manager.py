"""Centralized manager for bioio reader plugin detection and recommendations.

This module provides a unified interface for:
1. Suggesting plugins based on file extension
2. Detecting which plugins are installed vs need to be installed
3. Generating helpful installation messages

bioio handles reader priority and fallback internally (bioio#162).
This module focuses on user-friendly installation suggestions.

Public API:
    ReaderPluginManager - Main class for plugin management
    get_installed_plugins - Fast detection of installed bioio plugins

Example:
    >>> from ndevio._plugin_manager import ReaderPluginManager
    >>>
    >>> # Create manager for a specific file
    >>> manager = ReaderPluginManager("image.czi")
    >>>
    >>> # Check what plugins could be installed
    >>> print(manager.installable_plugins)
    >>> print(manager.get_installation_message())
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ._bioio_plugin_utils import get_installed_plugins

if TYPE_CHECKING:
    from napari.types import PathLike

logger = logging.getLogger(__name__)


class ReaderPluginManager:
    """Manager for bioio reader plugin detection and installation suggestions.

    bioio handles reader priority and fallback internally (see bioio#162).
    This class focuses on:
    - Detecting which plugins are installed
    - Suggesting plugins to install based on file extension
    - Generating helpful installation messages

    Parameters
    ----------
    path : PathLike, optional
        Path to the file for which to manage plugins. If None, manager
        operates in standalone mode.

    Examples
    --------
    >>> manager = ReaderPluginManager("image.czi")
    >>> if manager.installable_plugins:
    ...     print(manager.get_installation_message())
    """

    def __init__(self, path: PathLike | None = None):
        self.path = Path(path) if path is not None else None

    @property
    def installed_plugins(self) -> set[str]:
        """Get names of installed bioio plugins.

        Uses entry_points for fast lookup without loading plugins.

        Returns
        -------
        set of str
            Set of installed plugin names.
        """
        return get_installed_plugins()

    @property
    def suggested_plugins(self) -> list[str]:
        """Get plugin names that could read the current file (installed or not).

        Based on file extension, returns all plugin names that declare support
        for this file type, regardless of installation status.

        Returns
        -------
        list of str
            List of plugin names (e.g., ['bioio-czi']).
        """
        if not self.path:
            return []

        from ._bioio_plugin_utils import suggest_plugins_for_path

        return suggest_plugins_for_path(self.path)

    @property
    def installable_plugins(self) -> list[str]:
        """Get non-core plugin names that aren't installed but could read the file.

        This is the key property for suggesting plugins to install. It filters
        out core plugins (bundled with bioio) and already-installed plugins.

        Returns
        -------
        list of str
            List of plugin names that should be installed.
            Empty list if no path is set or all suitable plugins are installed.
        """
        from ._bioio_plugin_utils import BIOIO_PLUGINS

        suggested = self.suggested_plugins
        installed = self.installed_plugins

        # Filter out core plugins and installed plugins
        return [
            plugin_name
            for plugin_name in suggested
            if not BIOIO_PLUGINS.get(plugin_name, {}).get('core', False)
            and plugin_name not in installed
        ]

    def get_installation_message(self) -> str:
        """Generate helpful message for missing plugins.

        Creates a user-friendly message suggesting which plugins to install,
        with installation instructions.

        Returns
        -------
        str
            Formatted message with installation suggestions.
        """
        if not self.path:
            return ''

        from ._bioio_plugin_utils import format_plugin_installation_message

        return format_plugin_installation_message(
            filename=self.path.name,
            suggested_plugins=self.suggested_plugins,
            installed_plugins=self.installed_plugins,
            installable_plugins=self.installable_plugins,
        )

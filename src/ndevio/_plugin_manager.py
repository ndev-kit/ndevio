"""Centralized manager for bioio reader plugin detection and recommendations.

This module provides a unified interface for managing bioio reader plugins:
1. Known plugins - All bioio plugins defined in BIOIO_PLUGINS (priority order)
2. Installed plugins - Plugins currently installed in the environment
3. Installable plugins - Plugins that could read a file but aren't installed

The ReaderPluginManager builds a priority list from BIOIO_PLUGINS that can be
passed directly to BioImage(reader=[...]) for priority-based reader selection.

Public API:
    ReaderPluginManager - Main class for plugin management

Example:
    >>> from ndevio._plugin_manager import ReaderPluginManager
    >>>
    >>> # Create manager for a specific file
    >>> manager = ReaderPluginManager("image.czi")
    >>>
    >>> # Get priority list of Reader classes to pass to BioImage
    >>> priority = manager.get_priority_list()
    >>> img = BioImage("image.czi", reader=priority)
    >>>
    >>> # Check what plugins could be installed
    >>> print(manager.installable_plugins)
    >>> print(manager.get_installation_message())
"""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bioio.plugins import PluginSupport
    from bioio_base.reader import Reader
    from napari.types import PathLike

logger = logging.getLogger(__name__)


class ReaderPluginManager:
    """Centralized manager for bioio reader plugin detection and recommendations.

    This class builds a priority list from BIOIO_PLUGINS that can be passed
    directly to BioImage(reader=[...]) for priority-based reader selection.
    It also provides installation suggestions for missing plugins.

    Parameters
    ----------
    path : PathLike, optional
        Path to the file for which to manage plugins. If None, manager
        operates in standalone mode (e.g., for browsing all available plugins).

    Attributes
    ----------
    path : Path or None
        Path to the file being managed

    Examples
    --------
    >>> # For a specific file
    >>> manager = ReaderPluginManager("image.czi")
    >>> priority = manager.get_priority_list()
    >>> if priority:
    ...     img = BioImage("image.czi", reader=priority)
    ... else:
    ...     print(manager.get_installation_message())
    """

    def __init__(self, path: PathLike | None = None):
        """Initialize manager, optionally for a specific file path.

        Parameters
        ----------
        path : PathLike, optional
            Path to the file for plugin detection. If None, operates in
            standalone mode.
        """
        self.path = Path(path) if path is not None else None

    @property
    def known_plugins(self) -> list[str]:
        """Get all known bioio plugin names from BIOIO_PLUGINS.

        Returns
        -------
        list of str
            List of plugin names (e.g., ['bioio-czi', 'bioio-ome-tiff', ...]).
        """
        from ._bioio_plugin_utils import BIOIO_PLUGINS

        return list(BIOIO_PLUGINS.keys())

    @cached_property
    def feasibility_report(self) -> dict[str, PluginSupport]:
        """Get cached feasibility report for current path.

        The feasibility report from bioio.plugin_feasibility_report() shows
        which installed plugins can read the file. This property caches the
        result to avoid expensive repeated calls.

        Returns
        -------
        dict
            Mapping of plugin names to PluginSupport objects. Empty dict if
            no path is set.
        """
        if not self.path:
            return {}

        from bioio import plugin_feasibility_report

        return plugin_feasibility_report(self.path)

    @property
    def installed_plugins(self) -> set[str]:
        """Get names of installed bioio plugins.

        Returns
        -------
        set of str
            Set of installed plugin names (excludes "ArrayLike").
        """
        report = self.feasibility_report
        return {name for name in report if name != 'ArrayLike'}

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

    def get_priority_list(
        self, preferred_reader: str | None = None
    ) -> list[type[Reader]]:
        """Build priority list of installed Reader classes for bioio.

        Creates an ordered list of Reader classes based on:
        1. Preferred reader (if specified and installed)
        2. BIOIO_PLUGINS order (filtered to installed plugins)

        bioio will try each reader in order until one works. We don't
        pre-filter to "supported" readers - that's bioio's job.

        Parameters
        ----------
        preferred_reader : str, optional
            Name of preferred reader to place first (e.g., "bioio-ome-tiff").
            If not installed, it's skipped.

        Returns
        -------
        list of Reader classes
            Ordered list of installed Reader classes.
            Empty if no plugins installed.

        Examples
        --------
        >>> manager = ReaderPluginManager("image.tiff")
        >>> priority = manager.get_priority_list(preferred_reader="bioio-ome-tiff")
        >>> img = BioImage("image.tiff", reader=priority)
        """
        from ._bioio_plugin_utils import get_reader_by_name

        installed = self.installed_plugins
        priority: list[type[Reader]] = []

        # Add preferred reader first if installed
        if preferred_reader and preferred_reader in installed:
            try:
                priority.append(get_reader_by_name(preferred_reader))
            except ImportError:
                logger.warning(
                    'Preferred reader %s not importable', preferred_reader
                )

        # Add remaining plugins in BIOIO_PLUGINS order
        for plugin_name in self.known_plugins:
            if plugin_name in installed and plugin_name != preferred_reader:
                try:
                    priority.append(get_reader_by_name(plugin_name))
                except ImportError:
                    # Plugin listed in feasibility report but not importable
                    logger.debug('Plugin %s not importable', plugin_name)

        return priority

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

"""Centralized manager for bioio reader plugin detection and recommendations.

This module provides a unified interface for managing three categories of plugins:
1. Available plugins - All known bioio plugins (from BIOIO_PLUGINS)
2. Installed plugins - Plugins currently installed in the environment
3. Suggested/installable plugins - Plugins that could read a specific file

The ReaderPluginManager class eliminates code duplication and provides a clean
API for both core functionality and widgets.

Public API:
    ReaderPluginManager - Main class for plugin management

Example:
    >>> from ndevio._plugin_manager import ReaderPluginManager
    >>>
    >>> # Create manager for a specific file
    >>> manager = ReaderPluginManager("image.czi")
    >>>
    >>> # Check what plugins could read this file
    >>> print(manager.suggested_plugins)
    >>>
    >>> # Check what's installed
    >>> print(manager.installed_plugins)
    >>>
    >>> # Get plugins that need to be installed
    >>> print(manager.installable_plugins)
    >>>
    >>> # Try to get a working reader
    >>> reader = manager.get_working_reader(preferred_reader="bioio-czi")
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

    This class handles three plugin categories:
    1. Available plugins - All known bioio plugins (from BIOIO_PLUGINS)
    2. Installed plugins - Plugins currently installed in environment
    3. Suggested plugins - Plugins that could read a specific file

    The manager caches expensive operations (like plugin_feasibility_report)
    and provides a clean API for widgets and core logic.

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
    >>> if manager.installed_plugins:
    ...     reader = manager.get_working_reader()
    >>> else:
    ...     print(manager.get_installation_message())
    >>>
    >>> # Standalone mode (no file)
    >>> manager = ReaderPluginManager()
    >>> all_plugins = manager.available_plugins
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

    def get_working_reader(
        self, preferred_reader: str | None = None
    ) -> Reader | None:
        """Get a reader that can actually read this file.

        Tries readers in priority order:
        1. Preferred reader if it's installed and supported
        2. Readers from BIOIO_PLUGINS dict order (highest priority first)
        3. Any other installed reader that supports the file
        4. None if no working reader found

        Parameters
        ----------
        preferred_reader : str, optional
            Name of preferred reader to try first (e.g., "bioio-ome-tiff")

        Returns
        -------
        Reader or None
            Reader class that can read the file, or None if no suitable
            reader is installed.

        Notes
        -----
        The priority order is determined by the ordering of BIOIO_PLUGINS
        in _bioio_plugin_utils.py, which prioritizes readers based on
        metadata preservation quality, reliability, and known issues.
        """
        from ._bioio_plugin_utils import get_reader_by_name

        if not self.path:
            logger.warning(
                'Cannot get working reader without a path. '
                'Initialize ReaderPluginManager with a file path.'
            )
            return None

        report = self.feasibility_report

        # Try preferred reader first
        if (
            preferred_reader
            and preferred_reader in report
            and report[preferred_reader].supported
        ):
            logger.info(
                'Using preferred reader: %s for %s',
                preferred_reader,
                self.path,
            )
            return get_reader_by_name(preferred_reader)

        # Try readers in priority order from BIOIO_PLUGINS
        for reader_name in self.known_plugins:
            if reader_name in report and report[reader_name].supported:
                logger.info(
                    'Using reader: %s for %s (from priority list)',
                    reader_name,
                    self.path,
                )
                return get_reader_by_name(reader_name)

        # Try any other installed reader that supports the file
        for name, support in report.items():
            if name != 'ArrayLike' and support.supported:
                logger.info(
                    'Using reader: %s for %s (from installed plugins)',
                    name,
                    self.path,
                )
                return get_reader_by_name(name)

        logger.warning('No working reader found for: %s', self.path)
        return None

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

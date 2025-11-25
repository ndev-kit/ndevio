"""Core plugin installation logic for bioio readers.

This module provides pure Python functions for installing bioio reader plugins.
No napari or Qt dependencies - this is business logic only.

Uses napari-plugin-manager's InstallerQueue for actual installation,
supporting both pip and conda backends.

Public API:
    install_plugin() - Install a bioio plugin using napari-plugin-manager
    get_installer_queue() - Get the global InstallerQueue instance
    verify_plugin_installed() - Check if a plugin is installed

Note:
    For plugin discovery and suggestions, see _bioio_plugin_utils module.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Module-level singleton for the installer queue
_installer_queue = None


def install_plugin(plugin_name: str) -> int:
    """Install a bioio plugin using napari-plugin-manager.

    This function queues an installation job using napari's InstallerQueue,
    which handles both pip and conda environments appropriately.

    Parameters
    ----------
    plugin_name : str
        Name of the bioio plugin to install (e.g., 'bioio-czi')

    Returns
    -------
    int
        Job ID from the InstallerQueue. Can be used to track the installation.
        The actual installation happens asynchronously.

    Notes
    -----
    The installation is asynchronous - this function returns immediately
    with a job ID. Connect to the queue's signals to monitor progress.

    Examples
    --------
    >>> from ndevio._plugin_installer import install_plugin, get_installer_queue
    >>> queue = get_installer_queue()
    >>> job_id = install_plugin("bioio-czi")
    >>> # Monitor via queue.processFinished signal
    """
    from napari_plugin_manager.base_qt_package_installer import (
        InstallerTools,
    )

    logger.info("Queueing installation for: %s", plugin_name)

    queue = get_installer_queue()

    # Determine which tool to use (pip vs conda)
    # napari-plugin-manager handles this automatically based on environment
    tool = InstallerTools.PYPI  # Default to PYPI for bioio packages

    # Queue the installation
    job_id = queue.install(tool=tool, pkgs=[plugin_name])

    logger.info("Installation queued with job ID: %s", job_id)
    return job_id


def get_installer_queue():
    """Get or create the global InstallerQueue instance.

    Returns
    -------
    NapariInstallerQueue
        The global installer queue instance.
    """
    from napari_plugin_manager.qt_package_installer import (
        NapariInstallerQueue,
    )

    global _installer_queue
    if _installer_queue is None:
        _installer_queue = NapariInstallerQueue()

    return _installer_queue


def verify_plugin_installed(plugin_name: str) -> bool:
    """Verify that a plugin was successfully installed.

    Parameters
    ----------
    plugin_name : str
        Name of the plugin to verify

    Returns
    -------
    bool
        True if plugin can be imported, False otherwise
    """
    try:
        # Convert plugin name to module name (bioio-czi -> bioio_czi)
        module_name = plugin_name.replace("-", "_")
        __import__(module_name)
        return True
    except ImportError:
        return False

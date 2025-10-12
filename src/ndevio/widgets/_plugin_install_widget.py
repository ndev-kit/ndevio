"""Widget for installing missing bioio reader plugins.

This widget can be used in two modes:
1. Standalone: Open from napari menu to browse and install any bioio plugin
2. Error-triggered: Automatically opens when a file can't be read, with
   suggested plugin pre-selected
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from magicgui.widgets import ComboBox, Container, Label, PushButton

from .._bioio_plugin_utils import BIOIO_PLUGINS

if TYPE_CHECKING:
    from napari.types import PathLike

logger = logging.getLogger(__name__)


class PluginInstallerWidget(Container):
    """Widget to install missing bioio reader plugins.

    Can be used standalone or triggered by file read errors.

    The widget always shows all available bioio plugins from BIOIO_PLUGINS.

    In standalone mode:
    - First plugin in alphabetical order is pre-selected
    - No file path shown

    In error mode:
    - First suggested plugin is pre-selected (if provided)
    - Shows the file path that failed to read
    - User can still select any other plugin from the full list

    Parameters
    ----------
    path : PathLike, optional
        Path to the file that couldn't be read. If None, runs in standalone mode.
    suggested_plugins : list of dict, optional
        List of plugin info dicts from get_installable_plugins().
        If provided, the first plugin will be pre-selected.

    Attributes
    ----------
    path : PathLike or None
        Path to the file (None in standalone mode)
    suggested_plugins : list of dict or None
        Suggested plugins for error mode
    plugins : list of dict
        All available plugins from BIOIO_PLUGINS
    """

    def __init__(
        self,
        path: PathLike | None = None,
        suggested_plugins: list[dict[str, Any]] | None = None,
    ):
        """Initialize the PluginInstallerWidget.

        Parameters
        ----------
        path : PathLike, optional
            Path to the file that couldn't be read. If None, runs in standalone mode.
        suggested_plugins : list of dict, optional
            List of suggested plugin info dicts. In error mode, the first
            suggested plugin will be pre-selected in the dropdown.
        """
        super().__init__(labels=False)

        self.path = path
        self.suggested_plugins = suggested_plugins

        # Always get all plugins
        self.plugins = list(BIOIO_PLUGINS.keys())

        self._init_widgets()
        self._connect_events()

    def _init_widgets(self):
        """Initialize all widget components."""
        from pathlib import Path

        # Title - conditional based on mode
        if self.path is not None:
            # Error mode: show file that failed
            file_name = Path(self.path).name
            self._title_label = Label(
                value=f"<b>Cannot read file:</b> {file_name}"
            )
        else:
            # Standalone mode: general title
            self._title_label = Label(
                value="<b>Install BioIO Reader Plugin</b>"
            )
        self.append(self._title_label)

        self._info_label = Label(value="Select a plugin to install:")
        self.append(self._info_label)

        self._plugin_select = ComboBox(
            label="Plugin",
            choices=self.plugins,
            value=None,
            nullable=True,
        )
        # If suggested plugins provided, pre-select the first one
        if self.suggested_plugins and len(self.suggested_plugins) > 0:
            self._plugin_select.value = self.suggested_plugins[0]["name"]
        self.append(self._plugin_select)

        # Install button
        self._install_button = PushButton(text="Install Plugin")
        self.append(self._install_button)

        # Status label
        self._status_label = Label(value="")
        self.append(self._status_label)

    def _connect_events(self):
        """Connect widget events to handlers."""
        self._install_button.clicked.connect(self._on_install_clicked)

    def _on_install_clicked(self):
        """Handle install button click."""
        self._status_label.value = "Installing..."

        # Get selected plugin name
        plugin_name = self._plugin_select.value

        if not plugin_name:
            self._status_label.value = "No plugin selected"
            return

        logger.info("User requested install of: %s", plugin_name)

        # Use napari-plugin-manager's InstallerQueue
        from .._plugin_installer import get_installer_queue, install_plugin

        # Get the global installer queue
        queue = get_installer_queue()

        # Connect to the queue's signals to monitor progress
        def on_process_finished(event):
            """Handle installation completion."""
            exit_code = event.get("exit_code", 1)
            pkgs = event.get("pkgs", [])

            # Check if this event is for our package
            if plugin_name not in pkgs:
                return

            if exit_code == 0:
                self._status_label.value = (
                    f"✓ Successfully installed {plugin_name}!\n\n"
                    "⚠ It is recommended to restart napari."
                )
                logger.info("Plugin installed successfully: %s", plugin_name)
                # Disconnect after success
                queue.processFinished.disconnect(on_process_finished)
            else:
                self._status_label.value = (
                    f"✗ Installation failed for {plugin_name}\n"
                    f"Exit code: {exit_code}\n"
                    "Check the console for details."
                )
                logger.error("Plugin installation failed: %s", plugin_name)
                # Disconnect after failure
                queue.processFinished.disconnect(on_process_finished)

        # Connect to the signal
        queue.processFinished.connect(on_process_finished)

        # Queue the installation (returns job ID)
        job_id = install_plugin(plugin_name)
        logger.info("Installation job %s queued for %s", job_id, plugin_name)

    def close(self):
        """Clean up resources when widget is closed."""
        # Disconnect from installer queue if connected
        from .._plugin_installer import get_installer_queue

        try:
            queue = get_installer_queue()
            # Try to disconnect all our connections
            # (will silently fail if not connected, which is fine)
            queue.processFinished.disconnect()
        except (RuntimeError, TypeError):
            # Already disconnected or queue doesn't exist
            pass

        super().close()

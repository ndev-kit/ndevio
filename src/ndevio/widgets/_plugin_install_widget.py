"""Widget for installing missing bioio reader plugins.

This widget appears when a file cannot be read due to missing reader plugins.
It allows users to interactively install the necessary plugins using
napari-plugin-manager's InstallerQueue.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from magicgui.widgets import ComboBox, Container, Label, PushButton

if TYPE_CHECKING:
    import napari
    from napari.types import PathLike

logger = logging.getLogger(__name__)


class PluginInstallerWidget(Container):
    """Widget to install missing bioio reader plugins.

    This widget displays when a file cannot be read, showing:
    - The file path that failed
    - Dropdown of available plugins that could read it
    - Install button to install the selected plugin
    - Status messages and installation progress

    Parameters
    ----------
    viewer : napari.viewer.Viewer
        The napari viewer instance
    path : PathLike
        Path to the file that couldn't be read
    installable_plugins : list of dict
        List of plugin info dicts from get_installable_plugins()

    Attributes
    ----------
    viewer : napari.viewer.Viewer
        The napari viewer instance
    path : PathLike
        Path to the file
    plugins : list of dict
        Available plugins to install
    """

    def __init__(
        self,
        viewer: napari.viewer.Viewer,
        path: PathLike,
        installable_plugins: list[dict],
    ):
        """Initialize the PluginInstallerWidget.

        Parameters
        ----------
        viewer : napari.viewer.Viewer
            The napari viewer instance
        path : PathLike
            Path to the file that couldn't be read
        installable_plugins : list of dict
            List of plugin info dicts
        """
        super().__init__(labels=False)
        self.viewer = viewer
        self.path = path
        self.plugins = installable_plugins

        self._init_widgets()
        self._connect_events()

    def _init_widgets(self):
        """Initialize all widget components."""
        from pathlib import Path

        # Title
        self._title_label = Label(
            value=f"<b>Cannot read file:</b> {Path(self.path).name}"
        )
        self.append(self._title_label)

        # Info message
        if not self.plugins:
            self._info_label = Label(
                value="No installable plugins found for this file type."
            )
            self.append(self._info_label)
            return

        self._info_label = Label(
            value="Install a reader plugin to open this file:"
        )
        self.append(self._info_label)

        # Plugin dropdown (ComboBox for single selection)
        plugin_choices = [p["name"] for p in self.plugins]

        self._plugin_select = ComboBox(
            label="Plugin",
            choices=plugin_choices,
            value=plugin_choices[0] if plugin_choices else None,
            nullable=False,
        )
        self.append(self._plugin_select)

        # Install button
        self._install_button = PushButton(text="Install Plugin")
        self.append(self._install_button)

        # Status label
        self._status_label = Label(value="")
        self.append(self._status_label)

    def _connect_events(self):
        """Connect widget events to handlers."""
        if hasattr(self, "_install_button"):
            self._install_button.clicked.connect(self._on_install_clicked)

    def _on_install_clicked(self):
        """Handle install button click."""
        # Disable button during installation
        self._install_button.enabled = False
        self._status_label.value = "Installing..."

        # Get selected plugin name
        plugin_name = self._plugin_select.value

        if not plugin_name:
            self._status_label.value = "No plugin selected"
            self._install_button.enabled = True
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
                # Re-enable button to allow retry
                self._install_button.enabled = True
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

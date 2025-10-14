"""Widget for installing missing bioio reader plugins.

This widget can be used in two modes:
1. Standalone: Open from napari menu to browse and install any bioio plugin
2. Error-triggered: Automatically opens when a file can't be read, with
   suggested plugin pre-selected
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from magicgui.widgets import ComboBox, Container, Label, PushButton

if TYPE_CHECKING:
    from .._plugin_manager import ReaderPluginManager

logger = logging.getLogger(__name__)


class PluginInstallerWidget(Container):
    """Widget to install missing bioio reader plugins.

    Can be used standalone or triggered by file read errors.

    The widget always shows all available bioio plugins.

    In standalone mode:
    - Create without a plugin_manager or with one without a path
    - First plugin in alphabetical order is pre-selected
    - No file path shown

    In error mode:
    - Provide a plugin_manager initialized with the file path
    - First installable plugin is pre-selected (if any)
    - Shows the file path that failed to read
    - User can still select any other plugin from the full list

    Parameters
    ----------
    plugin_manager : ReaderPluginManager, optional
        Plugin manager instance. If None, creates a new one in standalone mode.

    Attributes
    ----------
    manager : ReaderPluginManager
        Plugin manager for detection and recommendations
    """

    def __init__(
        self,
        plugin_manager: ReaderPluginManager | None = None,
    ):
        """Initialize the PluginInstallerWidget.

        Parameters
        ----------
        plugin_manager : ReaderPluginManager, optional
            Plugin manager instance. If None, creates a new one in standalone mode
            (no file path, just shows all available plugins).
        """
        super().__init__(labels=False)

        # Import here to avoid circular imports
        from .._plugin_manager import ReaderPluginManager

        # Create or use provided manager
        self.manager = plugin_manager or ReaderPluginManager()

        # Store connection for cleanup
        self._queue_connection = None

        self._init_widgets()
        self._connect_events()

    def _init_widgets(self):
        """Initialize all widget components."""
        # Title - conditional based on mode
        if self.manager.path is not None:
            # Error mode: show file that failed
            file_name = self.manager.path.name
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

        # Get all available plugin names from manager
        plugin_names = self.manager.available_plugins

        self._plugin_select = ComboBox(
            label="Plugin",
            choices=plugin_names,
            value=None,
            nullable=True,
        )

        # If there are installable plugins, pre-select the first one
        installable = self.manager.installable_plugins
        if installable:
            self._plugin_select.value = installable[0]

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
            else:
                self._status_label.value = (
                    f"✗ Installation failed for {plugin_name}\n"
                    f"Exit code: {exit_code}\n"
                    "Check the console for details."
                )
                logger.error("Plugin installation failed: %s", plugin_name)

            # Disconnect after completion (success or failure)
            if self._queue_connection is not None:
                try:
                    queue.processFinished.disconnect(self._queue_connection)
                    self._queue_connection = None
                except (RuntimeError, TypeError):
                    # Already disconnected
                    pass

        # Store the connection so we can disconnect it later
        self._queue_connection = on_process_finished
        queue.processFinished.connect(self._queue_connection)

        # Queue the installation (returns job ID)
        job_id = install_plugin(plugin_name)
        logger.info("Installation job %s queued for %s", job_id, plugin_name)

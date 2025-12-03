"""Widget for selecting scenes from multi-scene image files.

This widget is used when opening files that contain multiple scenes/series.
It allows users to select which scene(s) to open in the viewer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from magicgui.widgets import Container, Select
from ndev_settings import get_settings

if TYPE_CHECKING:
    import napari
    from napari.types import PathLike

    from ..nimage import nImage

logger = logging.getLogger(__name__)

DELIMITER = " :: "


class nImageSceneWidget(Container):
    """
    Widget to select a scene from a multi-scene file.

    Parameters
    ----------
    viewer : napari.viewer.Viewer
        The napari viewer instance.
    path : PathLike
        Path to the file.
    img : nImage
        The nImage instance.
    in_memory : bool
        Whether the image should be added in memory.

    Attributes
    ----------
    viewer : napari.viewer.Viewer
        The napari viewer instance.
    path : PathLike
        Path to the file.
    img : nImage
        The nImage instance.
    in_memory : bool
        Whether the image should be added in memory.
    settings : Settings
        The settings instance.
    scenes : list
        List of scenes in the image.
    _scene_list_widget : magicgui.widgets.Select
        Widget to select a scene from a multi-scene file.

    Methods
    -------
    open_scene
        Opens the selected scene(s) in the viewer.

    """

    def __init__(
        self,
        viewer: napari.viewer.Viewer,
        path: PathLike,
        img: nImage,
        in_memory: bool,
    ):
        """
        Initialize the nImageSceneWidget.

        Parameters
        ----------
        viewer : napari.viewer.Viewer
            The napari viewer instance.
        path : PathLike
            Path to the file.
        img : nImage
            The nImage instance.
        in_memory : bool
            Whether the image should be added in memory.

        """
        super().__init__(labels=False)
        self.max_height = 200
        self.viewer = viewer
        self.path = path
        self.img = img
        self.in_memory = in_memory
        self.settings = get_settings()
        self.scenes = [
            f"{idx}{DELIMITER}{scene}"
            for idx, scene in enumerate(self.img.scenes)
        ]

        self._init_widgets()
        self._connect_events()

    def _init_widgets(self):
        self._scene_list_widget = Select(
            value=None,
            nullable=True,
            choices=self.scenes,
        )
        self.append(self._scene_list_widget)

    def _connect_events(self):
        self._scene_list_widget.changed.connect(self.open_scene)

    def open_scene(self) -> None:
        """Open the selected scene(s) in the viewer."""
        if self.settings.ndevio_reader.clear_layers_on_new_scene:
            self.viewer.layers.clear()

        for scene in self._scene_list_widget.value:
            if scene is None:
                continue
            # Use scene indexes to cover for duplicate names
            scene_index = int(scene.split(DELIMITER)[0])
            self.img.set_scene(scene_index)
            img_data = self.img.get_napari_image_data(in_memory=self.in_memory)
            img_meta = self.img.get_napari_metadata()

            self.viewer.add_image(img_data.data, **img_meta)

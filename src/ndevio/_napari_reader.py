from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from bioio_base.exceptions import UnsupportedFileFormatError
from ndev_settings import get_settings

from .nimage import determine_reader_plugin, nImage

if TYPE_CHECKING:
    from napari.types import LayerData, PathLike, ReaderFunction

logger = logging.getLogger(__name__)


def napari_get_reader(
    path: PathLike,
    in_memory: bool | None = None,
    open_first_scene_only: bool | None = None,
    open_all_scenes: bool | None = None,
) -> ReaderFunction | None:
    """
    Get the appropriate reader function for a single given path.

    Parameters
    ----------
    path : PathLike
        Path to the file to be read
    in_memory : bool, optional
        Whether to read the file in memory, by default None
    open_first_scene_only : bool, optional
        Whether to ignore multi-scene files and just open the first scene,
        by default None, which uses the setting
    open_all_scenes : bool, optional
        Whether to open all scenes in a multi-scene file, by default None
        which uses the setting
        Ignored if open_first_scene_only is True


    Returns
    -------
    ReaderFunction
        The reader function for the given path

    """
    settings = get_settings()

    open_first_scene_only = (
        open_first_scene_only
        if open_first_scene_only is not None
        else settings.ndevio_reader.scene_handling == "View First Scene Only"  # type: ignore
    ) or False

    open_all_scenes = (
        open_all_scenes
        if open_all_scenes is not None
        else settings.ndevio_reader.scene_handling == "View All Scenes"  # type: ignore
    ) or False

    if isinstance(path, list):
        logger.info("Bioio: Expected a single path, got a list of paths.")
        return None

    try:
        reader = determine_reader_plugin(path)
        return partial(
            napari_reader_function,
            reader=reader,  # type: ignore
            in_memory=in_memory,
            open_first_scene_only=open_first_scene_only,
            open_all_scenes=open_all_scenes,
        )

    except UnsupportedFileFormatError as e:
        # determine_reader_plugin() already enhanced the error message
        logger.error("ndevio: Unsupported file format: %s", path)
        # Show plugin installer widget if enabled in settings
        if settings.ndevio_reader.suggest_reader_plugins:  # type: ignore
            _open_plugin_installer(path, e)

        # Return None per napari reader spec - don't raise exception
        return None

    except Exception as e:  # noqa: BLE001
        logger.warning("ndevio: Error reading file: %s", e)
        return None


def napari_reader_function(
    path: PathLike,
    reader: Callable,
    in_memory: bool | None = None,
    open_first_scene_only: bool = False,
    open_all_scenes: bool = False,
    layer_type: str = "image",
) -> list[LayerData] | None:
    """
    Read a file using the given reader function.

    Parameters
    ----------
    path : PathLike
        Path to the file to be read
    reader : None
        Bioio Reader function to be used to read the file, by default None.
    in_memory : bool, optional
        Whether to read the file in memory, by default None.
    layer_type : str, optional
        Type of layer to be created in napari, by default 'image'.
    open_first_scene_only : bool, optional
        Whether to ignore multi-scene files and just open the first scene,
        by default False.
    open_all_scenes : bool, optional
        Whether to open all scenes in a multi-scene file, by default False.
        Ignored if open_first_scene_only is True.

    Returns
    -------
    list
        List containing image data, metadata, and layer type

    """
    if isinstance(path, list):
        logger.info("Bioio: Expected a single path, got a list of paths.")
        return None

    img = nImage(path, reader=reader)
    in_memory = (
        img._determine_in_memory(path) if in_memory is None else in_memory
    )
    # TODO: Guess layer type here (check channel names for labels?)
    logger.info("Bioio: Reading in-memory: %s", in_memory)

    # open first scene only
    if len(img.scenes) == 1 or open_first_scene_only:
        img_data = img.get_napari_image_data(in_memory=in_memory)
        img_meta = img.get_napari_metadata(path)
        return [(img_data.data, img_meta, layer_type)]

    # TODO: USE settings for open first or all scenes to set the nubmer of iterations of a for loop
    # check napari reader settings stuff
    # open all scenes as layers
    if len(img.scenes) > 1 and open_all_scenes:
        layer_list = []
        for scene in img.scenes:
            img.set_scene(scene)
            img_data = img.get_napari_image_data(in_memory=in_memory)
            img_meta = img.get_napari_metadata(path)
            layer_list.append((img_data.data, img_meta, layer_type))
        return layer_list

    # open scene widget
    if len(img.scenes) > 1 and not open_all_scenes:
        _open_scene_container(path=path, img=img, in_memory=in_memory)
        return [(None,)]

    logger.warning("Bioio: Error reading file")
    return [(None,)]


def _open_scene_container(
    path: PathLike, img: nImage, in_memory: bool
) -> None:
    from pathlib import Path

    import napari

    from .widgets import DELIMITER, nImageSceneWidget

    viewer = napari.current_viewer()
    viewer.window.add_dock_widget(
        nImageSceneWidget(viewer, path, img, in_memory),
        area="right",
        name=f"{Path(path).stem}{DELIMITER}Scenes",
    )


def _open_plugin_installer(
    path: PathLike, error: UnsupportedFileFormatError
) -> None:
    """Open the plugin installer widget for an unsupported file.

    Parameters
    ----------
    path : PathLike
        Path to the file that couldn't be read
    error : UnsupportedFileFormatError
        The error that was raised
    """

    import napari

    from ._plugin_manager import ReaderPluginManager
    from .widgets import PluginInstallerWidget

    # Get viewer, handle case where no viewer available
    viewer = napari.current_viewer()

    # Don't try to open widget if no viewer available (e.g., in tests)
    if viewer is None:
        logger.warning(
            "Cannot open plugin installer widget: No napari viewer available"
        )
        return

    # Create plugin manager for this file
    manager = ReaderPluginManager(path)

    widget = PluginInstallerWidget(plugin_manager=manager)
    viewer.window.add_dock_widget(
        widget,
        area="right",
        name="Install BioIO Plugin",
    )

from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

from ndev_settings import get_settings

from .nimage import nImage

if TYPE_CHECKING:
    from napari.types import LayerDataTuple, PathLike, ReaderFunction

logger = logging.getLogger(__name__)


def napari_get_reader(
    path: PathLike,
    in_memory: bool | None = None,
    open_first_scene_only: bool | None = None,
    open_all_scenes: bool | None = None,
) -> ReaderFunction | None:
    """
    Get the appropriate reader function for a single given path.

    Uses a quick extension check to determine if any bioio plugin might
    support this file. If so, returns a reader function that will use
    bioio's priority system to try each installed reader.

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
    ReaderFunction or None
        The reader function for the given path, or None if extension
        is not recognized by any bioio plugin.

    """
    from ._bioio_plugin_utils import suggest_plugins_for_path

    if isinstance(path, list):
        logger.info('Bioio: Expected a single path, got a list of paths.')
        return None

    # Quick extension check - if no plugins recognize this extension, return None
    # This allows other napari readers to try the file
    # TODO: This is probably legacy cruft before starting to autopopulate the filename_patterns in napari.yaml
    suggested = suggest_plugins_for_path(path)
    if not suggested:
        logger.debug('ndevio: No bioio plugins for extension: %s', path)
        return None

    settings = get_settings()

    open_first_scene_only = (
        open_first_scene_only
        if open_first_scene_only is not None
        else settings.ndevio_reader.scene_handling == 'View First Scene Only'  # type: ignore
    ) or False

    open_all_scenes = (
        open_all_scenes
        if open_all_scenes is not None
        else settings.ndevio_reader.scene_handling == 'View All Scenes'  # type: ignore
    ) or False

    # Extension is recognized - return a reader function
    # The actual reading happens in napari_reader_function
    return partial(
        napari_reader_function,
        in_memory=in_memory,
        open_first_scene_only=open_first_scene_only,
        open_all_scenes=open_all_scenes,
    )


def napari_reader_function(
    path: PathLike,
    in_memory: bool | None = None,
    open_first_scene_only: bool = False,
    open_all_scenes: bool = False,
) -> list[LayerDataTuple] | None:
    """
    Read a file using bioio.

    nImage handles reader selection: if a preferred_reader is set in settings,
    it's tried first with automatic fallback to bioio's default plugin ordering.

    Parameters
    ----------
    path : PathLike
        Path to the file to be read
    in_memory : bool, optional
        Whether to read the file in memory, by default None.
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
    from bioio_base.exceptions import UnsupportedFileFormatError

    try:
        img = nImage(path)  # nImage handles preferred reader and fallback
    except UnsupportedFileFormatError:
        # Try to open plugin installer widget
        # If no viewer available, this will re-raise
        _open_plugin_installer(path)
        return None

    logger.info('Bioio: Reading file with %d scenes', len(img.scenes))

    # open first scene only
    if len(img.scenes) == 1 or open_first_scene_only:
        return img.get_layer_data_tuples(in_memory=in_memory)

    # open all scenes as layers
    if open_all_scenes:
        layer_list = []
        for scene in img.scenes:
            img.set_scene(scene)
            layer_list.extend(img.get_layer_data_tuples(in_memory=in_memory))
        return layer_list

    # else: open scene widget
    _open_scene_container(path=path, img=img, in_memory=in_memory)
    return [(None,)]  # type: ignore[return-value]


def _open_scene_container(
    path: PathLike, img: nImage, in_memory: bool | None
) -> None:
    from pathlib import Path

    import napari

    from .widgets import DELIMITER, nImageSceneWidget

    viewer = napari.current_viewer()
    viewer.window.add_dock_widget(
        nImageSceneWidget(viewer, path, img, in_memory),
        area='right',
        name=f'{Path(path).stem}{DELIMITER}Scenes',
    )


def _open_plugin_installer(path: PathLike) -> None:
    """Open the plugin installer widget for an unsupported file.

    If no napari viewer is available, re-raises the UnsupportedFileFormatError
    with installation suggestions so programmatic users get a helpful message.

    Parameters
    ----------
    path : PathLike
        Path to the file that couldn't be read

    Raises
    ------
    UnsupportedFileFormatError
        If no napari viewer is available (programmatic usage)
    """
    import napari
    from bioio_base.exceptions import UnsupportedFileFormatError

    from ._plugin_manager import ReaderPluginManager
    from .widgets import PluginInstallerWidget

    # Get viewer, handle case where no viewer available
    viewer = napari.current_viewer()

    # If no viewer, re-raise with helpful message for programmatic users
    if viewer is None:
        logger.debug(
            'No napari viewer available, raising exception with suggestions'
        )
        manager = ReaderPluginManager(path)
        raise UnsupportedFileFormatError(
            reader_name='ndevio',
            path=str(path),
            msg_extra=manager.get_installation_message(),
        )

    # Create plugin manager for this file
    manager = ReaderPluginManager(path)

    widget = PluginInstallerWidget(plugin_manager=manager)
    viewer.window.add_dock_widget(
        widget,
        area='right',
        name='Install BioIO Plugin',
    )

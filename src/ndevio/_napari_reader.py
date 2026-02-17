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
    open_first_scene_only: bool | None = None,
    open_all_scenes: bool | None = None,
) -> ReaderFunction | None:
    """Get the appropriate reader function for a single given path.

    Parameters
    ----------
    path : PathLike
        Path to the file to be read
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
        else settings.ndevio_reader.scene_handling == 'View First Scene Only'  # type: ignore
    ) or False

    open_all_scenes = (
        open_all_scenes
        if open_all_scenes is not None
        else settings.ndevio_reader.scene_handling == 'View All Scenes'  # type: ignore
    ) or False

    # Return reader function; actual format validation happens in
    # napari_reader_function via nImage initialization.
    return partial(
        napari_reader_function,
        open_first_scene_only=open_first_scene_only,
        open_all_scenes=open_all_scenes,
    )


def napari_reader_function(
    path: PathLike,
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
        return img.get_layer_data_tuples()

    # open all scenes as layers
    if open_all_scenes:
        layer_list = []
        for scene in img.scenes:
            img.set_scene(scene)
            layer_list.extend(img.get_layer_data_tuples())
        return layer_list

    # else: open scene widget
    _open_scene_container(path=path, img=img)
    return [(None,)]  # type: ignore[return-value]


def _open_scene_container(path: PathLike, img: nImage) -> None:
    from pathlib import Path

    import napari

    from .widgets import DELIMITER, nImageSceneWidget

    viewer = napari.current_viewer()
    viewer.window.add_dock_widget(
        nImageSceneWidget(viewer, path, img),
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

    from .bioio_plugins._manager import ReaderPluginManager
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

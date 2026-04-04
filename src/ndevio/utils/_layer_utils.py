"""Utilities for building napari layer data from BioImage objects."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bioio_base.types import ArrayLike
    from napari.types import LayerDataTuple

logger = logging.getLogger(__name__)

# Keywords that indicate a channel contains labels/segmentation data
CHANNEL_LABEL_KEYWORDS = frozenset(
    {
        'label',
        'mask',
        'seg',
        'segmentation',
        'annotation',
        'roi',
        'region',
        'instance',
        'objects',
    }
)
FILE_LABEL_KEYWORDS = frozenset(
    {
        'label',
        'mask',
        'segmentation',
        'instance',
        'objects',
    }
)


def infer_channel_layer_type(channel_name: str) -> str:
    """Infer layer type from channel name keywords.

    Parameters
    ----------
    channel_name : str
        The channel name to check.

    Returns
    -------
    str
        'labels' if channel_name contains a label keyword, else 'image'.

    Examples
    --------
    >>> infer_channel_layer_type('nuclei_mask')
    'labels'
    >>> infer_channel_layer_type('DAPI')
    'image'

    """
    name_lower = channel_name.lower()
    return (
        'labels'
        if any(kw in name_lower for kw in CHANNEL_LABEL_KEYWORDS)
        else 'image'
    )


def infer_file_label_type(path_stem: str) -> str:
    """Infer layer type from filename stem keywords.

    Parameters
    ----------
    path_stem : str
        The filename stem (no extension) to check.

    Returns
    -------
    str
        'labels' if path_stem contains a label keyword, else 'image'.
    Examples
    --------
    >>> infer_file_label_type('cells_segmentation')
    'labels'
    >>> infer_file_label_type('experiment1')
    'image'

    """
    name_lower = path_stem.lower()
    return (
        'labels'
        if any(kw in name_lower for kw in FILE_LABEL_KEYWORDS)
        else 'image'
    )


def resolve_layer_type(
    channel_name: str,
    global_override: str | None,
    channel_types: dict[str, str] | None,
    path_stem: str | None = None,
) -> str:
    """Resolve layer type: global override > per-channel > auto-detect.

    Auto-detection checks the channel name first, then falls back to the
    filename stem so that files named e.g. ``cells_mask.tif`` are detected
    as ``'labels'`` even when the channel name is a generic ``'0'``.

    Parameters
    ----------
    channel_name : str
        Name of the channel.
    global_override : str | None
        If set, this layer type is used for all channels.
    channel_types : dict[str, str] | None
        Per-channel layer type mapping.
    path_stem : str | None
        Filename stem (no extension) used as a fallback when the channel
        name does not contain label keywords.

    Returns
    -------
    str
        The resolved layer type.

    """
    if global_override is not None:
        return global_override
    if channel_types and channel_name in channel_types:
        return channel_types[channel_name]
    if infer_channel_layer_type(channel_name) == 'labels':
        return 'labels'
    if path_stem is not None:
        return infer_file_label_type(path_stem)
    return 'image'


def determine_in_memory(
    path: str | None,
    uncompressed_bytes: int | None = None,
    max_in_mem_bytes: float | None = None,
    max_in_mem_percent: float = 0.3,
) -> bool:
    """Determine whether to load image data in memory or as dask array.

    Parameters
    ----------
    path : str | None
        Path to the image file as a string. If None (array data), returns True.
    uncompressed_bytes : int | None
        Expected in-memory size in bytes (``shape.prod() * dtype.itemsize``).
        When provided this is used instead of the on-disk file size, which
        can be far smaller for compressed formats (e.g. LZW-compressed int32
        TIFF).  When None the on-disk size reported by the filesystem is used.
    max_in_mem_bytes : float | None
        Maximum size in bytes for in-memory loading.
        If None (default), reads from the ``ndevio_reader.max_in_mem_gb``
        setting, falling back to 8 GB (8e9 bytes).
    max_in_mem_percent : float
        Maximum fraction of available memory for in-memory loading.
        Default is 30%.

    Returns
    -------
    bool
        True if image should be loaded in memory, False for dask array.

    """
    # No file path means array data - always in memory
    if path is None:
        return True

    if max_in_mem_bytes is None:
        from ndev_settings import get_settings

        max_in_mem_bytes = get_settings().ndevio_reader.max_in_mem_gb * 1e9

    from psutil import virtual_memory

    available_mem = virtual_memory().available

    if uncompressed_bytes is not None:
        check_bytes = uncompressed_bytes
    else:
        from bioio_base.io import pathlike_to_fs

        fs, path_str = pathlike_to_fs(path)
        check_bytes = fs.size(path_str)  # type: ignore[assignment]

    return (
        check_bytes <= max_in_mem_bytes
        and check_bytes < max_in_mem_percent * available_mem
    )


def build_layer_tuple(
    data: ArrayLike | list[ArrayLike],
    *,
    layer_type: str,
    name: str,
    metadata: dict,
    scale: tuple[float, ...],
    axis_labels: tuple[str, ...],
    units: tuple[str | None, ...],
    channel_idx: int = 0,
    total_channels: int = 1,
    rgb: bool = False,
    extra_kwargs: dict | None = None,
) -> LayerDataTuple:
    """Build a single LayerDataTuple for napari.

    Parameters
    ----------
    data : ArrayLike | list[ArrayLike]
        Image data for this layer. A list of arrays is interpreted by
        napari as multiscale data (highest to lowest resolution).
    layer_type : str
        Layer type ('image', 'labels', etc.).
    name : str
        Layer name.
    metadata : dict
        Base metadata dict (bioimage, raw_metadata, etc.).
    scale : tuple[float, ...]
        Scale for each dimension.
    axis_labels : tuple[str, ...]
        Dimension labels.
    units : tuple[str | None, ...]
        Physical units for each dimension.
    channel_idx : int
        Channel index (for colormap/blending selection). Default 0.
    total_channels : int
        Total channels (for colormap selection). Default 1.
    rgb : bool
        Whether this is an RGB image.
    extra_kwargs : dict, optional
        Additional napari layer kwargs to merge (overrides defaults).

    Returns
    -------
    LayerDataTuple
        (data, metadata, layer_type) tuple.

    """
    from ._colormap_utils import get_colormap_for_channel

    layer_kwargs: dict = {
        'name': name,
        'metadata': metadata,
        'scale': scale,
        'axis_labels': axis_labels,
        'units': units,
    }

    if rgb:
        layer_kwargs['rgb'] = True
    elif layer_type == 'image':
        # Add colormap/blending for non-RGB images
        layer_kwargs['colormap'] = get_colormap_for_channel(
            channel_idx, total_channels
        )
        layer_kwargs['blending'] = (
            'additive'
            if channel_idx > 0 and total_channels > 1
            else 'translucent_no_depth'
        )

    # Apply extra overrides last
    if extra_kwargs:
        layer_kwargs.update(extra_kwargs)

    return (data, layer_kwargs, layer_type)  # type: ignore[return-value]

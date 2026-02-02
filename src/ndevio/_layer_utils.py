"""Utilities for building napari layer data from BioImage objects."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xarray as xr
    from bioio_base.types import ArrayLike
    from napari.types import LayerDataTuple

logger = logging.getLogger(__name__)

# Keywords that indicate a channel contains labels/segmentation data
LABEL_KEYWORDS = frozenset({'label', 'mask', 'segmentation', 'seg', 'roi'})


def get_single_channel_name(
    layer_data: xr.DataArray,
    channel_dim: str,
) -> str | None:
    """Extract channel name from coords for single-channel image.

    When an image has been squeezed and no longer has a Channel dimension,
    the channel name may still be available in the coordinates.

    Parameters
    ----------
    layer_data : xr.DataArray
        The image data array.
    channel_dim : str
        Name of the channel dimension (e.g., 'C').

    Returns
    -------
    str | None
        The channel name if found, else None.

    Examples
    --------
    >>> # For a squeezed single-channel image with coords
    >>> get_single_channel_name(data, 'C')
    'DAPI'

    """
    if channel_dim in layer_data.coords:
        coord = layer_data.coords[channel_dim]
        if coord.size == 1:
            return str(coord.item())
    return None


def infer_layer_type(channel_name: str) -> str:
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
    >>> infer_layer_type('nuclei_mask')
    'labels'
    >>> infer_layer_type('DAPI')
    'image'

    """
    name_lower = channel_name.lower()
    return (
        'labels' if any(kw in name_lower for kw in LABEL_KEYWORDS) else 'image'
    )


def resolve_layer_type(
    channel_name: str,
    global_override: str | None,
    channel_types: dict[str, str] | None,
) -> str:
    """Resolve layer type: global override > per-channel > auto-detect.

    Parameters
    ----------
    channel_name : str
        Name of the channel.
    global_override : str | None
        If set, this layer type is used for all channels.
    channel_types : dict[str, str] | None
        Per-channel layer type mapping.

    Returns
    -------
    str
        The resolved layer type.

    """
    if global_override is not None:
        return global_override
    if channel_types and channel_name in channel_types:
        return channel_types[channel_name]
    return infer_layer_type(channel_name)


def determine_in_memory(
    path: Path | None,
    max_in_mem_bytes: float = 4e9,
    max_in_mem_percent: float = 0.3,
) -> bool:
    """Determine whether to load image data in memory or as dask array.

    Parameters
    ----------
    path : Path | None
        Path to the image file. If None (array data), returns True.
    max_in_mem_bytes : float
        Maximum file size in bytes for in-memory loading.
        Default is 4 GB (4e9 bytes).
    max_in_mem_percent : float
        Maximum percentage of available memory for in-memory loading.
        Default is 30%.

    Returns
    -------
    bool
        True if image should be loaded in memory, False for dask array.

    """
    from bioio_base.io import pathlike_to_fs
    from psutil import virtual_memory

    # No file path means array data - always in memory
    if path is None:
        return True

    fs, path_str = pathlike_to_fs(path)
    filesize: int = fs.size(path_str)  # type: ignore[assignment]
    available_mem = virtual_memory().available

    return (
        filesize <= max_in_mem_bytes
        and filesize < max_in_mem_percent * available_mem
    )


def build_layer_tuple(
    data: ArrayLike,
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
    data : ArrayLike
        Image data for this layer.
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

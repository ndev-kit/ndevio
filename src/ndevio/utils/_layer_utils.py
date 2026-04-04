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


def _contains_label_keyword(value: str, keywords: frozenset[str]) -> bool:
    """Return whether a string contains any keyword in a keyword set."""
    value_lower = value.lower()
    return any(keyword in value_lower for keyword in keywords)


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
    if _contains_label_keyword(channel_name, CHANNEL_LABEL_KEYWORDS):
        return 'labels'
    if path_stem and _contains_label_keyword(path_stem, FILE_LABEL_KEYWORDS):
        return 'labels'
    return 'image'


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

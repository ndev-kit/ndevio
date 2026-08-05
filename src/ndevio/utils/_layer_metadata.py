"""Translate physical metadata from a BioImage for napari layers.

This module owns the OME-Zarr spec-version quirks and fallback behaviour that
previously lived scattered across ``nImage``'s ``layer_*`` properties.  Its
interface is deliberately small: given a ``BioImage`` (or any object exposing
the same ``scale``, ``dimension_properties``, ``metadata`` and ``ome_metadata``
accessors) plus the squeezed dimension names, it returns a fully-resolved
:class:`LayerMetadata`.

Tests pass a lightweight stand-in for ``BioImage`` — no real files or BioImage
instances required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bioio import BioImage

logger = logging.getLogger(__name__)

# Dimensions that are not exposed as napari layer axes (handled separately via
# channel splitting / RGB handling).
_EXCLUDED_DIMS = frozenset({'C', 'S'})

# Exceptions raised by BioImage readers when physical metadata is missing or
# stored in an old OME-Zarr format:
# - array-like inputs lack physical_pixel_sizes -> AttributeError
# - OME-Zarr v0.1/v0.2 lack 'coordinateTransformations' -> KeyError
# - v0.3 string-axes aren't normalised -> TypeError
_METADATA_UNAVAILABLE = (AttributeError, KeyError, TypeError)


@dataclass(frozen=True)
class LayerMetadata:
    """Resolved physical metadata for a napari layer.

    The tuples are aligned 1:1 with the (squeezed) layer data dimensions —
    napari requires ``axis_labels`` and ``units`` to have exactly ``ndim``
    entries.
    """

    axis_labels: tuple[str, ...]
    scale: tuple[float, ...]
    units: tuple[str | None, ...]
    metadata: dict


def build_layer_metadata(
    image: BioImage, dims: Sequence[str]
) -> LayerMetadata:
    """Resolve napari layer metadata from a BioImage.

    Parameters
    ----------
    image : BioImage
        The image to read physical metadata from (e.g. an ``nImage``).
    dims : Sequence[str]
        The squeezed dimension names of the layer data (e.g. from the
        reference xarray).  Channel and Samples dims are excluded here.

    Returns
    -------
    LayerMetadata
        Axis labels, scale, units, and the layer metadata dict.  Physical
        metadata that cannot be read falls back to ``scale=1.0`` / ``units=None``
        rather than raising.
    """
    axis_labels = tuple(str(d) for d in dims if d not in _EXCLUDED_DIMS)
    return LayerMetadata(
        axis_labels=axis_labels,
        scale=_resolve_scale(image, axis_labels),
        units=_resolve_units(image, axis_labels),
        metadata=_resolve_metadata(image),
    )


def _resolve_scale(
    image: BioImage, axis_labels: tuple[str, ...]
) -> tuple[float, ...]:
    """Read per-axis scale from *image*, defaulting each axis to 1.0."""
    try:
        bio_scale = image.scale
    except _METADATA_UNAVAILABLE:
        return tuple(1.0 for _ in axis_labels)
    return tuple(getattr(bio_scale, dim, None) or 1.0 for dim in axis_labels)


def _resolve_units(
    image: BioImage, axis_labels: tuple[str, ...]
) -> tuple[str | None, ...]:
    """Read per-axis units from *image*, defaulting each axis to None."""
    try:
        dim_props = image.dimension_properties
    except _METADATA_UNAVAILABLE:
        return tuple(None for _ in axis_labels)

    def _get_unit(dim: str) -> str | None:
        prop = getattr(dim_props, dim, None)
        return prop.unit if prop else None

    return tuple(_get_unit(dim) for dim in axis_labels)


def _resolve_metadata(image: BioImage) -> dict:
    """Build the layer metadata dict, tolerating unparseable OME metadata."""
    meta: dict = {
        'bioimage': image,
        'raw_image_metadata': image.metadata,
    }

    try:
        meta['ome_metadata'] = image.ome_metadata
    except NotImplementedError:
        pass  # Reader doesn't support OME metadata
    except (ValueError, TypeError, KeyError) as e:
        # Some files have metadata that doesn't conform to OME schema, despite
        # bioio attempting to parse it (e.g. CZI files with LatticeLightsheet
        # acquisition mode).  Log a warning but keep the raw metadata.
        logger.warning(
            'Could not parse OME metadata: %s. '
            "Raw metadata is still available in 'raw_image_metadata'.",
            e,
        )
    return meta


__all__ = ['LayerMetadata', 'build_layer_metadata']

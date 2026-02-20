"""Compatibility checks for known bioio reader format limitations.

These functions inspect reader state after initialisation and emit a single
consolidated warning when a known incompatibility is detected, so that
downstream property accessors can fail silently without repeating noisy
messages.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from bioio_ome_zarr import Reader as OmeZarrReader


def warn_if_old_zarr_format(reader: OmeZarrReader) -> None:
    """Emit one warning if *reader* is a ``bioio_ome_zarr.Reader`` for a v0.1/v0.2 store.

    ``bioio_ome_zarr.Reader`` unconditionally accesses ``coordinateTransformations``
    inside each ``datasets`` entry — a key introduced in OME-Zarr v0.3.  Any call
    to ``reader.scale`` or ``reader.dimension_properties`` therefore raises
    ``KeyError`` for v0.1/v0.2 stores.

    ``nImage`` silently falls back to ``scale=1.0`` / ``units=None`` in those
    paths, but this warning gives users a single, clear explanation upfront via
    the napari activity log.

    Parameters
    ----------
    reader : OmeZarrReader
    """
    multiscales = reader._multiscales_metadata
    datasets = multiscales[0].get('datasets', []) if multiscales else []
    if datasets and 'coordinateTransformations' not in datasets[0]:
        version = multiscales[0].get('version', 'unknown (likely 0.1 or 0.2)')
        logger.warning(
            'OME-Zarr compatibility warning: this store appears to be '
            'OME-Zarr spec version %s, which pre-dates '
            "'coordinateTransformations' in dataset entries (introduced "
            'in v0.3). Physical scale and unit metadata cannot be read. '
            'ndevio will open the image with scale=1.0 and no units. '
            'Consider converting the file to OME-Zarr >=v0.4.',
            version,
        )

"""Compatibility checks for known bioio reader format limitations.

These functions inspect reader state after initialisation and emit a single
consolidated warning when a known incompatibility is detected, so that
downstream property accessors can fail silently without repeating noisy
messages.

OME-Zarr spec version differences handled here:

- **v0.1/v0.2**: No ``axes`` field, no ``coordinateTransformations`` in
  ``datasets`` entries. ``bioio_ome_zarr`` falls back to guessing dims
  from shape, but ``scale``/``dimension_properties`` raise ``KeyError``.
  We warn and let nImage fall back to ``scale=1.0`` / ``units=None``.

- **v0.3**: ``axes`` is a **list of strings** (e.g. ``["t", "c", "z", "y", "x"]``),
  but ``bioio_ome_zarr`` assumes v0.4 dict-axes (``[{"name": "z", ...}]``).
  Attempting ``ax["name"]`` on a string raises ``TypeError``.
  We normalise string-axes to dict-axes **in-place** on the reader metadata
  so all downstream code works transparently.

- **v0.4+**: ``axes`` is a list of dicts — no patching needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Dimension name → OME-Zarr axis type mapping (v0.4 spec).
_AXIS_TYPE_MAP: dict[str, str] = {
    't': 'time',
    'c': 'channel',
    'z': 'space',
    'y': 'space',
    'x': 'space',
}

if TYPE_CHECKING:
    from bioio_ome_zarr import Reader as OmeZarrReader


def apply_ome_zarr_compat_patches(reader: OmeZarrReader) -> None:
    """Apply all OME-Zarr compatibility patches to *reader*.

    Currently handles:
    - v0.1/v0.2 stores (warning only — no ``coordinateTransformations``)
    - v0.3 stores (normalise string-axes to dict-axes in-place)

    Parameters
    ----------
    reader : OmeZarrReader
    """
    _normalize_v03_string_axes(reader)
    _warn_if_no_coordinate_transforms(reader)


def _normalize_v03_string_axes(reader: OmeZarrReader) -> None:
    """Convert v0.3 string-axes to v0.4 dict-axes in-place.

    OME-Zarr v0.3 stores ``axes`` as ``["t", "c", "z", "y", "x"]``.
    ``bioio_ome_zarr`` expects v0.4 format: ``[{"name": "z", "type": "space"}, ...]``.

    This function mutates ``reader._multiscales_metadata`` so that all
    downstream code in ``bioio_ome_zarr`` works without modification.
    If the axes are already dicts (v0.4+) or absent (v0.1/v0.2), this
    is a no-op.

    Parameters
    ----------
    reader : OmeZarrReader
    """
    multiscales = reader._multiscales_metadata
    if not multiscales:
        return

    patched = False
    for scene_meta in multiscales:
        axes = scene_meta.get('axes', [])
        if not axes:
            continue
        # v0.3: axes are strings; v0.4+: axes are dicts
        if isinstance(axes[0], str):
            scene_meta['axes'] = [
                {
                    'name': name,
                    'type': _AXIS_TYPE_MAP.get(name.lower(), 'space'),
                }
                for name in axes
            ]
            patched = True

    if patched:
        version = multiscales[0].get('version', 'unknown (likely 0.3)')
        logger.info(
            'OME-Zarr compatibility: normalised v0.3 string-axes to '
            'v0.4 dict-axes for spec version %s. Image will open '
            'normally but axis units are unavailable in this format.',
            version,
        )


def _warn_if_no_coordinate_transforms(reader: OmeZarrReader) -> None:
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

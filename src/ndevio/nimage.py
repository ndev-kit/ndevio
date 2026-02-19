"""Additional functionality for BioImage objects to be used in napari-ndev."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from bioio import BioImage
from bioio_base.reader import Reader
from bioio_base.types import ImageLike

from .bioio_plugins._manager import raise_unsupported_with_suggestions
from .utils._layer_utils import (
    build_layer_tuple,
    determine_in_memory,
    get_single_channel_name,
    resolve_layer_type,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    import xarray as xr
    from bioio_base.reader import Reader
    from bioio_base.types import ImageLike
    from napari.types import LayerDataTuple

logger = logging.getLogger(__name__)


def _resolve_reader(
    image: ImageLike,
    explicit_reader: type[Reader] | Sequence[type[Reader]] | None,
) -> type[Reader] | Sequence[type[Reader]] | None:
    """Resolve the reader to use for an image.

    Priority:
    1. Explicit reader (passed to __init__)
    2. Preferred reader from settings (if file path and installed)
    3. None (let bioio determine)

    Parameters
    ----------
    image : ImageLike
        The image to resolve a reader for.
    explicit_reader : type[Reader] | Sequence[type[Reader]] | None
        Explicit reader class(es) passed by user.

    Returns
    -------
    type[Reader] | Sequence[type[Reader]] | None
        The reader to use, or None to let bioio choose.

    """
    if explicit_reader is not None:
        return explicit_reader

    # Only check preferred reader for file paths
    if not isinstance(image, str | Path):
        return None

    # Get preferred reader from settings
    from ndev_settings import get_settings

    from .bioio_plugins._utils import get_installed_plugins, get_reader_by_name

    settings = get_settings()
    preferred = settings.ndevio_reader.preferred_reader  # type: ignore

    if not preferred:
        return None

    if preferred not in get_installed_plugins():
        logger.debug('Preferred reader %s not installed', preferred)
        return None

    return get_reader_by_name(preferred)


class nImage(BioImage):
    """
    An nImage is a BioImage with additional functionality for napari.

    Extends BioImage to provide napari-ready layer data with proper scale,
    axis labels, and units derived from bioimaging metadata.

    Parameters
    ----------
    image : ImageLike
        Image to be loaded. Can be a path to an image file, a numpy array,
        or an xarray DataArray.
    reader : type[Reader] | Sequence[type[Reader]], optional
        Reader class or priority list of readers. If not provided, checks
        settings for preferred_reader and tries that first, then falls back
        to bioio's default deterministic priority.
    **kwargs
        Additional arguments passed to BioImage.

    Attributes
    ----------
    path : str | None
        Path or URI to the source file, or None if created from array data.
        Always a plain string — local paths are stored as-is, ``file://`` URIs
        are normalised to their path component, and remote URIs (``s3://``,
        ``https://``, …) are kept verbatim.  Use ``_is_remote`` to distinguish
        local from remote.

    Examples
    --------
    Basic usage with file path:

    >>> img = nImage("path/to/image.tiff")
    >>> for layer_tuple in img.get_layer_data_tuples():
    ...     layer = Layer.create(*layer_tuple)
    ...     viewer.add_layer(layer)

    Access layer properties:

    >>> img.layer_scale       # (1.0, 0.2, 0.2) - physical scale per dim
    >>> img.layer_axis_labels # ('Z', 'Y', 'X')
    >>> img.layer_units       # ('µm', 'µm', 'µm')

    """

    # Class-level type hints for instance attributes
    path: str | None
    _is_remote: bool
    _layer_data: xr.DataArray | None

    def __init__(
        self,
        image: ImageLike,
        reader: type[Reader] | Sequence[type[Reader]] | None = None,
        **kwargs,
    ) -> None:
        """Initialize an nImage with an image, and optionally a reader."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        resolved_reader = _resolve_reader(image, reader)

        # Try preferred/explicit reader first, fall back to bioio default
        if resolved_reader is not None:
            try:
                super().__init__(image=image, reader=resolved_reader, **kwargs)
            except UnsupportedFileFormatError:
                # Preferred reader failed, fall back to bioio's default
                try:
                    super().__init__(image=image, reader=None, **kwargs)
                except UnsupportedFileFormatError:
                    if isinstance(image, str | Path):
                        raise_unsupported_with_suggestions(image)
                    raise
        else:
            try:
                super().__init__(image=image, reader=None, **kwargs)
            except UnsupportedFileFormatError:
                if isinstance(image, str | Path):
                    raise_unsupported_with_suggestions(image)
                raise

        # Instance state
        self._layer_data = None
        if isinstance(image, str | Path):
            import fsspec
            from fsspec.implementations.local import LocalFileSystem

            s = str(image)
            fs, resolved = fsspec.url_to_fs(s)
            if isinstance(fs, LocalFileSystem):
                # Normalise file:// URIs and any platform variations to an
                # OS-native path string so Path(self.path) always round-trips.
                self.path = str(Path(resolved))
                self._is_remote = False
            else:
                # Remote URI (s3://, https://, gc://, …) — keep verbatim.
                self.path = s
                self._is_remote = True
        else:
            self.path = None
            self._is_remote = False

    @property
    def layer_data(self) -> xr.DataArray:
        """
        Image data as xarray DataArray for napari layer creation.

        Lazily loads data on first access. Uses in-memory or dask array
        based on file size (determined automatically).

        Returns
        -------
        xr.DataArray
            Squeezed image data.

        Notes
        -----
        BioImage.xarray_data and BioImage.xarray_dask_data automatically
        handle mosaic tile reconstruction when reconstruct_mosaic=True
        (the default). No special mosaic handling needed here.

        """
        if self._layer_data is None:
            if self._is_remote or not determine_in_memory(self.path):
                self._layer_data = self.xarray_dask_data.squeeze()
            else:
                self._layer_data = self.xarray_data.squeeze()
        return self._layer_data

    @property
    def path_stem(self) -> str:
        """Filename stem derived from path or URI, used in layer names.

        Returns
        -------
        str
            The stem of the filename (no extension, no parent path), or
            ``'unknown'`` when the image was created from array data.

        Examples
        --------
        >>> nImage("/data/cells.ome.tiff").path_stem
        'cells.ome'
        >>> nImage("s3://bucket/experiment/image.zarr").path_stem
        'image'

        """
        if self.path is None:
            return 'unknown'
        if self._is_remote:
            from pathlib import PurePosixPath
            from urllib.parse import urlparse

            return PurePosixPath(urlparse(self.path).path).stem
        return Path(self.path).stem

    @property
    def layer_names(self) -> list[str]:
        """Per-channel layer names for napari.

        Returns one name per output layer — the same count as
        :meth:`get_layer_data_tuples` returns tuples. The base name is the
        scene-qualified :attr:`path_stem`; channel names are prepended using
        ``' :: '`` as a delimiter when present.

        Returns
        -------
        list[str]
            e.g. ``['membrane :: cells.ome', 'nuclei :: cells.ome']``
            for a 2-channel file, or ``['0 :: cells.ome']`` for a
            single-channel OME image with a default ``C`` coordinate.
            Only when no ``C`` dimension is present at all will the name
            be just ``['cells.ome']``.

        Examples
        --------
        >>> nImage("cells.ome.tiff").layer_names
        ['0 :: cells.ome']

        """
        # Build scene-qualified base name (pure metadata, no data load)
        delim = ' :: '
        parts: list[str] = []
        if len(self.scenes) > 1 or self.current_scene != 'Image:0':
            parts.extend([str(self.current_scene_index), self.current_scene])
        parts.append(self.path_stem)
        base_name = delim.join(parts)

        # RGB (Samples dim): single layer, no channel prefix
        if 'S' in self.dims.order:
            return [base_name]

        # No channel dimension at all (pure spatial image)
        if 'C' not in self.dims.order:
            return [base_name]

        # Use BioImage channel_names — metadata only, no data load
        channel_names = self.channel_names

        # Single channel (C=1 is squeezed out of layer_data)
        if self.dims.C == 1:
            ch_name = channel_names[0] if channel_names else None
            return [f'{ch_name} :: {base_name}' if ch_name else base_name]

        # Multichannel
        return [f'{ch} :: {base_name}' for ch in channel_names]

    @property
    def layer_scale(self) -> tuple[float, ...]:
        """Physical scale for dimensions in layer data.

        Uses layer_axis_labels to determine which dimensions are present,
        then extracts scale values from BioImage.scale.
        Defaults to 1.0 for dimensions without scale metadata.

        Returns
        -------
        tuple[float, ...]
            Scale tuple matching layer_axis_labels.

        Examples
        --------
        >>> img = nImage("timelapse.tiff")  # T=3, Z=1, Y=10, X=10
        >>> img.layer_axis_labels
        ('T', 'Y', 'X')
        >>> img.layer_scale
        (2.0, 0.2, 0.2)

        """
        axis_labels = self.layer_axis_labels

        # Try to get scale from BioImage - may fail for array-like inputs
        # where physical_pixel_sizes is None
        try:
            bio_scale = self.scale
        except AttributeError:
            return tuple(1.0 for _ in axis_labels)

        return tuple(
            getattr(bio_scale, dim, None) or 1.0 for dim in axis_labels
        )

    @property
    def layer_axis_labels(self) -> tuple[str, ...]:
        """Dimension names for napari layers (excludes Channel and Samples).

        Returns
        -------
        tuple[str, ...]
            Dimension names (e.g., ('Z', 'Y', 'X')).

        Examples
        --------
        >>> img = nImage("multichannel.tiff")  # Shape (C=2, Z=10, Y=100, X=100)
        >>> img.layer_axis_labels
        ('Z', 'Y', 'X')

        """
        layer_data = self.layer_data

        # Exclude Channel and Samples dimensions (RGB/multichannel handled separately)
        return tuple(
            str(dim) for dim in layer_data.dims if dim not in ('C', 'S')
        )

    @property
    def layer_units(self) -> tuple[str | None, ...]:
        """Physical units for dimensions in layer data.

        Returns
        -------
        tuple[str | None, ...]
            Unit strings matching layer_axis_labels. None for dims without units.

        Examples
        --------
        >>> img = nImage("timelapse.tiff")  # T=3, Z=1, Y=10, X=10
        >>> # After squeezing, Z is removed
        >>> img.layer_axis_labels
        ('T', 'Y', 'X')
        >>> img.layer_units
        ('s', 'µm', 'µm')

        """
        axis_labels = self.layer_axis_labels

        try:
            dim_props = self.dimension_properties
        except AttributeError:
            return tuple(None for _ in axis_labels)

        def _get_unit(dim: str) -> str | None:
            prop = getattr(dim_props, dim, None)
            return prop.unit if prop else None

        return tuple(_get_unit(dim) for dim in axis_labels)

    @property
    def layer_metadata(self) -> dict:
        """Base metadata dict for napari layers.

        Contains bioimage reference, raw metadata, and OME metadata if available.

        Returns
        -------
        dict
            Keys: 'bioimage', 'raw_image_metadata', and optionally 'ome_metadata'.

        """
        meta: dict = {
            'bioimage': self,
            'raw_image_metadata': self.metadata,
        }

        try:
            meta['ome_metadata'] = self.ome_metadata
        except NotImplementedError:
            pass  # Reader doesn't support OME metadata
        except (ValueError, TypeError, KeyError) as e:
            # Some files have metadata that doesn't conform to OME schema, despite bioio attempting to parse it
            # (e.g., CZI files with LatticeLightsheet acquisition mode)
            # As such, when accessing ome_metadata, we may get various exceptions
            # Log warning but continue - raw metadata is still available
            logger.warning(
                'Could not parse OME metadata: %s. '
                "Raw metadata is still available in 'raw_image_metadata'.",
                e,
            )

        return meta

    def get_layer_data_tuples(
        self,
        layer_type: str | None = None,
        channel_types: dict[str, str] | None = None,
        channel_kwargs: dict[str, dict] | None = None,
    ) -> list[LayerDataTuple]:
        """Build layer data tuples for napari.

        Splits multichannel data into separate layers, each with appropriate
        metadata. Automatically detects label layers from channel names
        containing keywords like 'label', 'mask', 'segmentation'.

        Parameters
        ----------
        layer_type : str, optional
            Override layer type for ALL channels. Valid values: 'image',
            'labels', 'shapes', 'points', 'surface', 'tracks', 'vectors'.
            If None, auto-detection is used (based on channel names).
            Takes precedence over channel_types.
        channel_types : dict[str, str], optional
            Per-channel layer type overrides.
            e.g., {"DAPI": "image", "nuclei_mask": "labels"}
            Ignored if layer_type is set.
        channel_kwargs : dict[str, dict], optional
            Per-channel napari kwargs overrides.
            e.g., {"DAPI": {"colormap": "blue", "contrast_limits": (0, 1000)}}
            These override the automatically generated metadata.

        Returns
        -------
        list[LayerDataTuple]
            List of (data, metadata, layer_type) tuples.

        Examples
        --------
        Add layers to napari:

        >>> from napari.layers import Layer
        >>> img = nImage("path/to/image.tiff")
        >>> for ldt in img.get_layer_data_tuples():
        ...     viewer.add_layer(Layer.create(*ldt))

        Mixed image/labels:

        >>> img.get_layer_data_tuples(
        ...     channel_types={"DAPI": "image", "nuclei_mask": "labels"}
        ... )

        See Also
        --------
        napari.layers.Layer.create : Creates a layer from a LayerDataTuple.
        https://napari.org/dev/plugins/building_a_plugin/guides.html

        """
        layer_data = self.layer_data
        if layer_type is not None:
            channel_types = None  # Global override ignores per-channel
        names = self.layer_names
        base_metadata = self.layer_metadata
        scale = self.layer_scale
        axis_labels = self.layer_axis_labels
        units = self.layer_units

        # Handle RGB images (Samples dimension 'S')
        if 'S' in self.dims.order:
            return [
                build_layer_tuple(
                    layer_data.data,
                    layer_type='image',
                    name=names[0],
                    metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    units=units,
                    rgb=True,
                )
            ]

        channel_dim = 'C'

        # Single channel (no C dimension to split)
        if channel_dim not in layer_data.dims:
            channel_name = get_single_channel_name(layer_data, channel_dim)
            effective_type = resolve_layer_type(
                channel_name or '', layer_type, channel_types
            )
            extra_kwargs = (
                channel_kwargs.get(channel_name)
                if channel_kwargs and channel_name
                else None
            )
            return [
                build_layer_tuple(
                    layer_data.data,
                    layer_type=effective_type,
                    name=names[0],
                    metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    units=units,
                    extra_kwargs=extra_kwargs,
                )
            ]

        # Multichannel - split into separate layers
        channel_names = [
            str(c) for c in layer_data.coords[channel_dim].data.tolist()
        ]
        channel_axis = layer_data.dims.index(channel_dim)
        total_channels = layer_data.shape[channel_axis]

        tuples: list[LayerDataTuple] = []
        for i in range(total_channels):
            channel_name = (
                channel_names[i] if i < len(channel_names) else f'channel_{i}'
            )
            effective_type = resolve_layer_type(
                channel_name, layer_type, channel_types
            )

            # Slice along channel axis
            slices: list[slice | int] = [slice(None)] * layer_data.ndim
            slices[channel_axis] = i
            channel_data = layer_data.data[tuple(slices)]

            extra_kwargs = (
                channel_kwargs.get(channel_name) if channel_kwargs else None
            )

            tuples.append(
                build_layer_tuple(
                    channel_data,
                    layer_type=effective_type,
                    name=names[i],
                    metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    units=units,
                    channel_idx=i,
                    total_channels=total_channels,
                    extra_kwargs=extra_kwargs,
                )
            )

        return tuples

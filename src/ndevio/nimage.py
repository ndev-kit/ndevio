"""Additional functionality for BioImage objects to be used in napari-ndev."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import xarray as xr
from bioio import BioImage
from bioio_base.dimensions import DimensionNames
from bioio_base.reader import Reader
from bioio_base.types import ImageLike, PathLike

if TYPE_CHECKING:
    from napari.types import LayerDataTuple

logger = logging.getLogger(__name__)

DELIM = ' :: '

# Keywords that indicate a channel contains labels/segmentation data
LABEL_KEYWORDS = frozenset({'label', 'mask', 'segmentation', 'seg', 'roi'})


def _get_preferred_reader_for_path(
    path: str | Path,
) -> type[Reader] | None:
    """Get preferred reader for a file path from settings.

    Parameters
    ----------
    path : str | Path
        Path to check preferred reader for.

    Returns
    -------
    type[Reader] | None
        Reader class if preferred is set and installed, else None.

    """
    from ndev_settings import get_settings

    from ._bioio_plugin_utils import get_installed_plugins, get_reader_by_name

    settings = get_settings()
    preferred = settings.ndevio_reader.preferred_reader  # type: ignore

    if not preferred:
        return None

    if preferred not in get_installed_plugins():
        logger.debug('Preferred reader %s not installed', preferred)
        return None

    return get_reader_by_name(preferred)


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

    return _get_preferred_reader_for_path(image)


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
    path : Path | None
        Path to the source file, or None if created from array data.

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
    path: Path | None
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
                        self._raise_with_suggestions(image)
                    raise
        else:
            try:
                super().__init__(image=image, reader=None, **kwargs)
            except UnsupportedFileFormatError:
                if isinstance(image, str | Path):
                    self._raise_with_suggestions(image)
                raise

        # Instance state
        self._layer_data = None
        self.path = Path(image) if isinstance(image, str | Path) else None

    def _raise_with_suggestions(self, path: PathLike) -> None:
        """Raise UnsupportedFileFormatError with installation suggestions."""
        from bioio_base.exceptions import UnsupportedFileFormatError
        from ndev_settings import get_settings

        from ._plugin_manager import ReaderPluginManager

        settings = get_settings()
        manager = ReaderPluginManager(path)
        msg_extra = (
            manager.get_installation_message()
            if settings.ndevio_reader.suggest_reader_plugins  # type: ignore
            else None
        )

        raise UnsupportedFileFormatError(
            reader_name='ndevio',
            path=str(path),
            msg_extra=msg_extra,
        ) from None

    # -------------------------------------------------------------------------
    # Memory Management
    # -------------------------------------------------------------------------

    def _determine_in_memory(
        self,
        max_in_mem_bytes: float = 4e9,
        max_in_mem_percent: float = 0.3,
    ) -> bool:
        """Determine whether to load image data in memory or as dask array.

        Parameters
        ----------
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
        if self.path is None:
            return True

        fs, path_str = pathlike_to_fs(self.path)
        filesize: int = fs.size(path_str)  # type: ignore[assignment]
        available_mem = virtual_memory().available

        return (
            filesize <= max_in_mem_bytes
            and filesize < max_in_mem_percent * available_mem
        )

    # -------------------------------------------------------------------------
    # Layer Data (cached)
    # -------------------------------------------------------------------------

    @property
    def layer_data(self) -> xr.DataArray | None:
        """
        Image data as xarray DataArray for napari layer creation.

        Lazily loads data on first access. Uses in-memory or dask array
        based on file size (determined automatically).

        Returns
        -------
        xr.DataArray
            Squeezed image data.

        """
        if self._layer_data is None:
            self._load_layer_data(in_memory=None)
        return self._layer_data

    def _load_layer_data(self, in_memory: bool | None = None) -> None:
        """
        Load and cache the image data as an xarray DataArray.

        Parameters
        ----------
        in_memory : bool, optional
            Whether to load the image in memory or as dask array.
            If None, determined automatically based on file size.

        """
        if in_memory is None:
            in_memory = self._determine_in_memory()

        if DimensionNames.MosaicTile in self.reader.dims.order:
            try:
                if in_memory:
                    self._layer_data = self.reader.mosaic_xarray_data.squeeze()
                else:
                    self._layer_data = (
                        self.reader.mosaic_xarray_dask_data.squeeze()
                    )

            except NotImplementedError:
                logger.warning(
                    'Bioio: Mosaic tile switching not supported for this reader'
                )
                self._layer_data = None
        else:
            if in_memory:
                self._layer_data = self.reader.xarray_data.squeeze()
            else:
                self._layer_data = self.reader.xarray_dask_data.squeeze()

    # -------------------------------------------------------------------------
    # Layer Properties (derived from layer_data)
    # -------------------------------------------------------------------------

    def _infer_layer_type(self, channel_name: str) -> str:
        """Infer layer type from channel name keywords."""
        name_lower = channel_name.lower()
        return (
            'labels'
            if any(kw in name_lower for kw in LABEL_KEYWORDS)
            else 'image'
        )

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

        return tuple(
            str(dim)
            for dim in layer_data.dims
            if dim not in (DimensionNames.Channel, DimensionNames.Samples)
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

    # -------------------------------------------------------------------------
    # Layer Tuple Building
    # -------------------------------------------------------------------------

    def _build_layer_name(
        self,
        channel_name: str | None = None,
        include_scene: bool = True,
    ) -> str:
        """Build layer name from channel, scene, and file path."""
        path_stem = self.path.stem if self.path is not None else 'unknown path'

        # Skip scene info if only one scene with default name
        no_scene = len(self.scenes) == 1 and self.current_scene == 'Image:0'

        parts: list[str] = []
        if channel_name:
            parts.append(channel_name)
        if include_scene and not no_scene:
            parts.extend([str(self.current_scene_index), self.current_scene])
        parts.append(path_stem)

        return DELIM.join(parts)

    def _build_single_layer_tuple(
        self,
        data,
        layer_type: str,
        base_metadata: dict,
        scale: tuple[float, ...],
        axis_labels: tuple[str, ...],
        units: tuple[str | None, ...] | None = None,
        channel_name: str | None = None,
        channel_idx: int = 0,
        total_channels: int = 1,
        channel_kwargs: dict[str, dict] | None = None,
        rgb: bool = False,
    ) -> LayerDataTuple:
        """Build a single LayerDataTuple for napari.

        Parameters
        ----------
        data : ArrayLike
            Image data for this layer.
        layer_type : str
            Layer type ('image', 'labels', etc.).
        base_metadata : dict
            Base metadata dict (bioimage, raw_metadata, etc.).
        scale : tuple[float, ...]
            Scale for each dimension.
        axis_labels : tuple[str, ...]
            Dimension labels.
        units : tuple[str | None, ...], optional
            Physical units for each dimension.
        channel_name : str, optional
            Channel name for layer naming.
        channel_idx : int
            Channel index (for colormap/blending selection). Default 0.
        total_channels : int
            Total channels (for colormap selection). Default 1.
        channel_kwargs : dict[str, dict], optional
            Per-channel metadata overrides. Maps channel name to dict of
            napari layer kwargs to override defaults.
        rgb : bool
            Whether this is an RGB image (sets rgb=True in metadata).

        Returns
        -------
        LayerDataTuple
            (data, metadata, layer_type) tuple.

        """
        meta: dict = {
            'name': self._build_layer_name(channel_name),
            'metadata': base_metadata,
            'scale': scale,
            'axis_labels': axis_labels,
        }

        if units:
            meta['units'] = units

        if rgb:
            meta['rgb'] = True
        elif layer_type == 'image':
            # Add colormap/blending for non-RGB images
            from ._colormap_utils import get_colormap_for_channel

            meta['colormap'] = get_colormap_for_channel(
                channel_idx, total_channels
            )
            meta['blending'] = (
                'additive'
                if channel_idx > 0 and total_channels > 1
                else 'translucent_no_depth'
            )

        # Apply per-channel overrides
        if channel_kwargs and channel_name and channel_name in channel_kwargs:
            meta.update(channel_kwargs[channel_name])

        return (data, meta, layer_type)  # type: ignore[return-value]

    def _resolve_layer_type(
        self,
        channel_name: str,
        layer_type_override: str | None,
        channel_types: dict[str, str] | None,
    ) -> str:
        """Resolve layer type: global override > per-channel > auto-detect."""
        if layer_type_override is not None:
            return layer_type_override
        if channel_types and channel_name in channel_types:
            return channel_types[channel_name]
        return self._infer_layer_type(channel_name)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_layer_data_tuples(
        self,
        in_memory: bool | None = None,
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
        in_memory : bool, optional
            Load in memory (True) or as dask array (False).
            If None, determined by file size.
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
        # Load image data if not already loaded
        # or reload if in_memory explicitly specified
        if self._layer_data is None or in_memory is not None:
            self._load_layer_data(in_memory=in_memory)
        layer_data = self.layer_data

        if layer_type is not None:
            channel_types = None  # Global override ignores per-channel

        base_metadata = self.layer_metadata
        scale = self.layer_scale
        axis_labels = self.layer_axis_labels
        units = self.layer_units

        # Handle RGB images (Samples dimension)
        if DimensionNames.Samples in self.reader.dims.order:
            return [
                self._build_single_layer_tuple(
                    data=layer_data.data,
                    layer_type='image',
                    base_metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    units=units,
                    channel_kwargs=channel_kwargs,
                    rgb=True,
                )
            ]

        channel_dim = DimensionNames.Channel

        # Single channel (no C dimension to split)
        if channel_dim not in layer_data.dims:
            channel_name = self._get_single_channel_name(
                layer_data, channel_dim
            )
            effective_type = self._resolve_layer_type(
                channel_name or '', layer_type, channel_types
            )
            return [
                self._build_single_layer_tuple(
                    data=layer_data.data,
                    layer_type=effective_type,
                    base_metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    units=units,
                    channel_name=channel_name,
                    channel_kwargs=channel_kwargs,
                )
            ]

        # Multichannel - split into separate layers
        return self._build_multichannel_tuples(
            layer_data=layer_data,
            channel_dim=channel_dim,
            layer_type=layer_type,
            channel_types=channel_types,
            channel_kwargs=channel_kwargs,
            base_metadata=base_metadata,
            scale=scale,
            axis_labels=axis_labels,
            units=units,
        )

    def _get_single_channel_name(
        self, layer_data: xr.DataArray, channel_dim: str
    ) -> str | None:
        """Extract channel name from coords for single-channel image."""
        if channel_dim in layer_data.coords:
            coord = layer_data.coords[channel_dim]
            if coord.size == 1:
                return str(coord.item())
        return None

    def _build_multichannel_tuples(
        self,
        layer_data: xr.DataArray,
        channel_dim: str,
        layer_type: str | None,
        channel_types: dict[str, str] | None,
        channel_kwargs: dict[str, dict] | None,
        base_metadata: dict,
        scale: tuple[float, ...],
        axis_labels: tuple[str, ...],
        units: tuple[str | None, ...],
    ) -> list[LayerDataTuple]:
        """Build layer tuples for each channel in a multichannel image."""
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
            effective_type = self._resolve_layer_type(
                channel_name, layer_type, channel_types
            )

            # Slice along channel axis
            slices: list[slice | int] = [slice(None)] * layer_data.ndim
            slices[channel_axis] = i
            channel_data = layer_data.data[tuple(slices)]

            tuples.append(
                self._build_single_layer_tuple(
                    data=channel_data,
                    layer_type=effective_type,
                    base_metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    units=units,
                    channel_name=channel_name,
                    channel_idx=i,
                    total_channels=total_channels,
                    channel_kwargs=channel_kwargs,
                )
            )

        return tuples

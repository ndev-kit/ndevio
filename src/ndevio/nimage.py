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
LABEL_KEYWORDS = ['label', 'mask', 'segmentation', 'seg', 'roi']


class nImage(BioImage):
    """
    An nImage is a BioImage with additional functionality for napari.

    Parameters
    ----------
    image : ImageLike
        Image to be loaded. Can be a path to an image file, a numpy array,
        or an xarray DataArray.
    reader : type[Reader] or Sequence[type[Reader]], optional
        Reader class or priority list of readers. If not provided, checks
        settings for preferred_reader and tries that first. If the preferred
        reader fails, falls back to bioio's default priority. If no preferred
        reader is set, uses bioio's deterministic plugin ordering directly.
    **kwargs
        Additional arguments passed to BioImage.

    Attributes
    ----------
    See BioImage for inherited attributes.
    """

    def __init__(
        self,
        image: ImageLike,
        reader: type[Reader] | Sequence[type[Reader]] | None = None,
        **kwargs,
    ) -> None:
        """Initialize an nImage with an image, and optionally a reader."""
        from bioio_base.exceptions import UnsupportedFileFormatError
        from ndev_settings import get_settings

        self.settings = get_settings()

        # If no explicit reader and we have a file path, check for preferred
        if reader is None and isinstance(image, (str | Path)):
            reader = self._get_preferred_reader_list()

        try:
            if reader is not None:
                # Try preferred/explicit reader first
                try:
                    super().__init__(image=image, reader=reader, **kwargs)
                except UnsupportedFileFormatError:
                    # Preferred reader failed, fall back to bioio's default
                    # errors in this will propagate to outer except, bubbling
                    # up the suggestion error message
                    super().__init__(image=image, reader=None, **kwargs)
            else:
                # No preferred reader, use bioio's default priority
                super().__init__(image=image, reader=None, **kwargs)
        except UnsupportedFileFormatError:
            # Only add installation suggestions for file paths
            # For arrays/other types, just let bioio's error propagate
            if isinstance(image, (str | Path)):
                self._raise_with_suggestions(image)
            raise

        # Private cache attributes (accessed via properties)
        self._layer_data: xr.DataArray | None = None
        self.path = image if isinstance(image, (str | Path)) else None

    def _get_preferred_reader_list(self) -> list[type[Reader]] | None:
        """Get preferred reader as a list (for fallback) or None.

        Returns the Reader class if set and installed, else None.
        When returned, __init__ will try this reader first and fall back
        to bioio's default priority if it fails.
        """
        from ._bioio_plugin_utils import (
            get_installed_plugins,
            get_reader_by_name,
        )

        pref = self.settings.ndevio_reader.preferred_reader  # type: ignore
        if not pref:
            return None

        # in case a legacy settings file exists with a plugin that is not present in a new environment
        if pref not in get_installed_plugins():
            logger.debug('Preferred reader %s not installed', pref)
            return None

        return [get_reader_by_name(pref)]

    def _raise_with_suggestions(self, path: PathLike) -> None:
        """Raise UnsupportedFileFormatError with installation suggestions."""
        from bioio_base.exceptions import UnsupportedFileFormatError

        from ._plugin_manager import ReaderPluginManager

        manager = ReaderPluginManager(path)
        if self.settings.ndevio_reader.suggest_reader_plugins:  # type: ignore
            msg_extra = manager.get_installation_message()
        else:
            msg_extra = None

        raise UnsupportedFileFormatError(
            reader_name='ndevio',
            path=str(path),
            msg_extra=msg_extra,
        ) from None

    def _determine_in_memory(
        self,
        path=None,
        max_in_mem_bytes: float = 4e9,
        max_in_mem_percent: float = 0.3,
    ) -> bool:
        """
        Determine whether the image should be loaded into memory or not.

        If the image is smaller than the maximum filesize or percentage of the
        available memory, this will determine to load image in memory.
        Otherwise, suggest to load as a dask array.

        Parameters
        ----------
        path : str or Path
            Path to the image file.
        max_in_mem_bytes : int
            Maximum number of bytes that can be loaded into memory.
            Default is 4 GB (4e9 bytes)
        max_in_mem_percent : float
            Maximum percentage of memory that can be loaded into memory.
            Default is 30% of available memory (0.3)

        Returns
        -------
        bool
            True if image should be loaded in memory, False otherwise.

        """
        from bioio_base.io import pathlike_to_fs
        from psutil import virtual_memory

        if path is None:
            path = self.path

        # If still None (created from array data), default to in-memory
        if path is None:
            return True

        fs, path = pathlike_to_fs(path)
        filesize = fs.size(path)
        available_mem = virtual_memory().available
        return (
            filesize <= max_in_mem_bytes
            and filesize < max_in_mem_percent * available_mem
        )

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

    def _infer_layer_type(self, channel_name: str) -> str:
        """Infer layer type from channel name."""
        name_lower = channel_name.lower()
        if any(keyword in name_lower for keyword in LABEL_KEYWORDS):
            return 'labels'
        return 'image'

    @property
    def layer_scale(self) -> tuple[float, ...]:
        """
        Physical scale for dimensions present in napari layer data.

        Uses layer_axis_labels to determine which dimensions are actually
        present after squeezing, then extracts scale values from BioImage.scale.
        Defaults to 1.0 for dimensions without scale metadata.

        Returns
        -------
        tuple[float, ...]
            Scale tuple matching dimensions in layer_axis_labels. Each value
            is either the physical scale or 1.0 if scale metadata is unavailable.

        Examples
        --------
        >>> img = nImage("timelapse.tiff")  # T=3, Z=1, Y=10, X=10
        >>> # After squeezing, Z is removed
        >>> img.layer_axis_labels
        ('T', 'Y', 'X')
        >>> img.layer_scale
        (2.0, 0.2, 0.2)  # T in seconds, Y/X in microns

        Notes
        -----
        Uses layer_axis_labels as source of truth - only returns scale for
        dimensions actually present in the squeezed layer_data.

        """
        axis_labels = self.layer_axis_labels

        # Try to get scale from BioImage - may fail for array-like inputs
        # where physical_pixel_sizes is None
        try:
            bio_scale = self.scale
        except AttributeError:
            # No scale metadata available, default to 1.0 for all dimensions
            return tuple(1.0 for _ in axis_labels)

        # From BioImage.scale get the value for each dim present, default to 1.0 if None
        return tuple(
            getattr(bio_scale, dim, None) or 1.0 for dim in axis_labels
        )

    @property
    def layer_axis_labels(self) -> tuple[str, ...]:
        """
        Axis labels for napari layers (dims without Channel).

        Returns the dimension names from layer_data, excluding
        the Channel dimension since channels are split into separate layers.
        Also excludes Samples dimension (for RGB images).

        Returns
        -------
        tuple[str, ...]
            Tuple of dimension names (e.g., ('Z', 'Y', 'X') for 3D image).

        Examples
        --------
        >>> img = nImage("multichannel.tiff")  # Shape (C=2, Z=10, Y=100, X=100)
        >>> img.layer_axis_labels
        ('Z', 'Y', 'X')  # Channel excluded

        """
        return tuple(
            str(dim)
            for dim in self.layer_data.dims
            if dim not in (DimensionNames.Channel, DimensionNames.Samples)
        )

    @property
    def layer_units(self) -> tuple[str | None, ...]:
        """
        Physical units for dimensions present in napari layer data.

        Uses layer_axis_labels to determine which dimensions are present,
        then extracts units from dimension_properties.

        Returns
        -------
        tuple[str | None, ...]
            Unit strings matching layer_axis_labels order. Elements can be
            None for dimensions without unit metadata.

        Examples
        --------
        >>> img = nImage("timelapse.tiff")  # T=3, Z=1, Y=10, X=10
        >>> # After squeezing, Z is removed
        >>> img.layer_axis_labels
        ('T', 'Y', 'X')
        >>> img.layer_units
        ('s', 'µm', 'µm')  # seconds for T, microns for spatial

        Notes
        -----
        Uses layer_axis_labels as source of truth - only returns units for
        dimensions actually present in the squeezed layer_data.

        """
        axis_labels = self.layer_axis_labels

        try:
            dim_props = self.dimension_properties
        except AttributeError:
            # No dimension_properties available, return None for each dimension
            return tuple(None for _ in axis_labels)

        # Get unit for each dimension present
        return tuple(
            getattr(dim_props, dim, None).unit
            if getattr(dim_props, dim, None)
            else None
            for dim in axis_labels
        )

    @property
    def layer_metadata(self) -> dict:
        """
        Base metadata dict for napari layers.

        Contains bioimage reference, raw metadata, and OME metadata (if available).

        Returns
        -------
        dict
            Metadata dict with 'bioimage', 'raw_image_metadata', and optionally
            'ome_metadata'.

        """
        img_meta = {'bioimage': self, 'raw_image_metadata': self.metadata}

        try:
            img_meta['ome_metadata'] = self.ome_metadata
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

        return img_meta

    def _build_layer_name(
        self, channel_name: str | None = None, include_scene: bool = True
    ) -> str:
        """
        Build layer name from channel name, scene info, and file path.

        Parameters
        ----------
        channel_name : str, optional
            Name of the channel. If None, omitted from name.
        include_scene : bool, optional
            Whether to include scene info. Default True.

        Returns
        -------
        str
            Formatted layer name.

        """
        path_stem = (
            Path(self.path).stem if self.path is not None else 'unknown path'
        )

        # Check if scene info is meaningful
        no_scene = len(self.scenes) == 1 and self.current_scene == 'Image:0'

        parts = []
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
        scale: tuple | None,
        axis_labels: tuple[str, ...],
        channel_name: str | None = None,
        channel_idx: int | None = None,
        total_channels: int = 1,
        channel_kwargs: dict[str, dict] | None = None,
    ) -> tuple:
        """
        Build a single layer tuple with appropriate metadata.

        Parameters
        ----------
        data : array-like
            Image data for this layer.
        layer_type : str
            Type of layer ('image', 'labels', etc.).
        base_metadata : dict
            Base metadata dict with bioimage reference.
        scale : tuple | None
            Physical pixel scale, or None.
        axis_labels : tuple[str, ...]
            Dimension labels for this layer (e.g., ('Z', 'Y', 'X')).
        channel_name : str, optional
            Channel name for layer naming.
        channel_idx : int, optional
            Index of this channel (for colormap/blending selection).
            If None, assumes single channel.
        total_channels : int
            Total number of channels in the original image.
        channel_kwargs : dict[str, dict], optional
            Per-channel metadata overrides. Maps channel name to dict of
            napari layer kwargs to override defaults.

        Returns
        -------
        tuple
            (data, metadata, layer_type) tuple for napari.

        """
        meta = {
            'name': self._build_layer_name(channel_name),
            'metadata': base_metadata,
        }

        if scale:
            meta['scale'] = scale

        if axis_labels:
            meta['axis_labels'] = axis_labels

        # Add image-specific metadata
        if layer_type == 'image':
            from ._colormap_utils import get_colormap_for_channel

            # Use channel_idx if provided, otherwise default to 0
            idx = channel_idx if channel_idx is not None else 0
            meta['colormap'] = get_colormap_for_channel(idx, total_channels)
            meta['blending'] = (
                'additive'
                if idx > 0 and total_channels > 1
                else 'translucent_no_depth'
            )

        # Apply per-channel overrides
        if channel_kwargs and channel_name and channel_name in channel_kwargs:
            meta.update(channel_kwargs[channel_name])

        return (data, meta, layer_type)

    def _resolve_layer_type(
        self,
        channel_name: str,
        layer_type_override: str | None,
        channel_types: dict[str, str] | None,
    ) -> str:
        """
        Resolve the layer type for a channel.

        Priority: global override > per-channel override > auto-detect.

        """
        if layer_type_override is not None:
            return layer_type_override
        if channel_types and channel_name in channel_types:
            return channel_types[channel_name]
        return self._infer_layer_type(channel_name)

    def get_layer_data_tuples(
        self,
        in_memory: bool | None = None,
        layer_type: str | None = None,
        channel_types: dict[str, str] | None = None,
        channel_kwargs: dict[str, dict] | None = None,
    ) -> list[LayerDataTuple]:
        """
        Build layer data tuples for napari.

        Always splits multichannel data into separate layers, allowing
        different layer types per channel. Automatically detects label
        layers from channel names containing keywords like 'label', 'mask',
        'segmentation'.

        Parameters
        ----------
        in_memory : bool, optional
            Load data in memory or as dask array. If None, determined
            automatically based on file size.
        layer_type : str, optional
            Override layer type for ALL channels. Valid values: 'image',
            'labels', 'shapes', 'points', 'surface', 'tracks', 'vectors'.
            If None, auto-detection is used (based on channel names).
            Takes precedence over channel_types.
        channel_types : dict[str, str], optional
            Override automatic layer type detection per-channel. Maps channel
            name to layer type ('image' or 'labels').
            e.g., {"DAPI": "image", "nuclei_mask": "labels"}
            Ignored if layer_type is provided.
        channel_kwargs : dict[str, dict], optional
            Per-channel metadata overrides. Maps channel name to dict of
            napari layer kwargs (colormap, contrast_limits, opacity, etc.).
            e.g., {"DAPI": {"colormap": "blue", "contrast_limits": (0, 1000)}}
            These override the automatically generated metadata.

        Returns
        -------
        list[LayerDataTuple]
            List of (data, metadata, layer_type) tuples ready for napari.

        Examples
        --------
        Add layers to a napari viewer using `Layer.create()`:

        >>> from napari.layers import Layer
        >>> img = nImage("path/to/image.tiff")
        >>> for ldt in img.get_layer_data_tuples():
        ...     layer = Layer.create(*ldt)
        ...     viewer.add_layer(layer)

        Override layer types for mixed image/labels files:

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

        if layer_type is not None:
            channel_types = None  # Global override ignores per-channel

        base_metadata = self.layer_metadata
        scale = self.layer_scale
        axis_labels = self.layer_axis_labels
        units = self.layer_units
        channel_dim = DimensionNames.Channel

        # Handle RGB images specially (no axis_labels, uses 'rgb' flag)
        if DimensionNames.Samples in self.reader.dims.order:
            meta = {
                'name': self._build_layer_name(),
                'rgb': True,
                'metadata': base_metadata,
            }
            if scale:
                meta['scale'] = scale
            if axis_labels:
                meta['axis_labels'] = axis_labels
            if units:
                meta['units'] = units
            return [(self.layer_data.data, meta, 'image')]

        # Single channel image (no channel dimension to split)
        if channel_dim not in self.layer_data.dims:
            # Try to get channel name from coords for label detection
            channel_name = None
            if channel_dim in self.layer_data.coords:
                coord = self.layer_data.coords[channel_dim]
                if coord.size == 1:
                    channel_name = str(coord.item())

            effective_type = self._resolve_layer_type(
                channel_name or '', layer_type, channel_types
            )
            return [
                self._build_single_layer_tuple(
                    data=self.layer_data.data,
                    layer_type=effective_type,
                    base_metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    channel_kwargs=channel_kwargs,
                )
            ]

        # Multichannel image - always split into separate layers
        channel_names = [
            str(c) for c in self.layer_data.coords[channel_dim].data.tolist()
        ]
        channel_axis = self.layer_data.dims.index(channel_dim)
        total_channels = self.layer_data.shape[channel_axis]

        layer_tuples = []
        for i in range(total_channels):
            channel_name = (
                channel_names[i] if i < len(channel_names) else f'channel_{i}'
            )
            effective_type = self._resolve_layer_type(
                channel_name, layer_type, channel_types
            )

            # Slice data along channel axis to extract single channel
            slices = [slice(None)] * self.layer_data.ndim
            slices[channel_axis] = i
            channel_data = self.layer_data.data[tuple(slices)]

            layer_tuples.append(
                self._build_single_layer_tuple(
                    data=channel_data,
                    layer_type=effective_type,
                    base_metadata=base_metadata,
                    scale=scale,
                    axis_labels=axis_labels,
                    channel_name=channel_name,
                    channel_idx=i,
                    total_channels=total_channels,
                    channel_kwargs=channel_kwargs,
                )
            )

        return layer_tuples

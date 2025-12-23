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
    layer_data_tuples : list[tuple] | None
        Cached layer data tuples from get_layer_data_tuples().
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
        if reader is None and isinstance(image, PathLike):
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
            if isinstance(image, PathLike):
                self._raise_with_suggestions(image)
            raise

        self.napari_layer_data: xr.DataArray | None = None
        self.layer_data_tuples: list[tuple] | None = None
        self.path = image if isinstance(image, PathLike) else None

    def _get_preferred_reader_list(self) -> list[type[Reader]] | None:
        """Get preferred reader as a list (for fallback) or None.

        Returns the Reader class if set and installed, else None.
        When returned, __init__ will try this reader first and fall back
        to bioio's default priority if it fails.
        """
        from ._bioio_plugin_utils import get_reader_by_name
        from ._plugin_manager import get_installed_plugins

        pref = self.settings.ndevio_reader.preferred_reader  # type: ignore
        if not pref:
            return None

        if pref not in get_installed_plugins():
            logger.debug('Preferred reader %s not installed', pref)
            return None

        try:
            return [get_reader_by_name(pref)]
        except ImportError:
            logger.warning('Preferred reader %s not importable', pref)
            return None

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

        fs, path = pathlike_to_fs(path)
        filesize = fs.size(path)
        available_mem = virtual_memory().available
        return (
            filesize <= max_in_mem_bytes
            and filesize < max_in_mem_percent * available_mem
        )

    def _get_layer_data(self, in_memory: bool | None = None) -> xr.DataArray:
        """
        Load and cache the image data as an xarray DataArray.

        Parameters
        ----------
        in_memory : bool, optional
            Whether to load the image in memory or as dask array.
            If None, determined automatically based on file size.

        Returns
        -------
        xr.DataArray
            Image data as a xarray DataArray.

        """
        if in_memory is None:
            in_memory = self._determine_in_memory()

        if DimensionNames.MosaicTile in self.reader.dims.order:
            try:
                if in_memory:
                    self.napari_layer_data = (
                        self.reader.mosaic_xarray_data.squeeze()
                    )
                else:
                    self.napari_layer_data = (
                        self.reader.mosaic_xarray_dask_data.squeeze()
                    )

            except NotImplementedError:
                logger.warning(
                    'Bioio: Mosaic tile switching not supported for this reader'
                )
                return None
        else:
            if in_memory:
                self.napari_layer_data = self.reader.xarray_data.squeeze()
            else:
                self.napari_layer_data = self.reader.xarray_dask_data.squeeze()

        return self.napari_layer_data

    def _infer_layer_type(self, channel_name: str) -> str:
        """Infer layer type from channel name."""
        name_lower = channel_name.lower()
        if any(keyword in name_lower for keyword in LABEL_KEYWORDS):
            return 'labels'
        return 'image'

    def _get_scale(self) -> tuple | None:
        """Extract physical pixel scale from image metadata according to number of napari dims."""
        if self.napari_layer_data is None:
            return None

        scale = [
            getattr(self.physical_pixel_sizes, dim)
            for dim in self.napari_layer_data.dims
            if dim
            in {
                DimensionNames.SpatialX,
                DimensionNames.SpatialY,
                DimensionNames.SpatialZ,
            }
            and getattr(self.physical_pixel_sizes, dim) is not None
        ]

        return tuple(scale) if scale else None

    def _build_metadata(self) -> dict:
        """
        Build base metadata dict with bioimage reference and raw metadata.

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
        channel_name: str | None = None,
        channel_idx: int = 0,
        n_channels: int = 1,
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
        channel_name : str, optional
            Channel name for layer naming.
        channel_idx : int
            Index of this channel (for colormap selection).
        n_channels : int
            Total number of channels (for colormap selection).
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

        # Add image-specific metadata
        if layer_type == 'image':
            from ._colormap_utils import get_colormap_for_channel

            meta['colormap'] = get_colormap_for_channel(
                channel_idx, n_channels
            )
            meta['blending'] = (
                'additive'
                if channel_idx > 0 and n_channels > 1
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

    # =========================================================================
    # Public API
    # =========================================================================

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
        if self.napari_layer_data is None:
            self._get_layer_data(in_memory=in_memory)

        if layer_type is not None:
            channel_types = None  # Global override ignores per-channel

        base_metadata = self._build_metadata()
        scale = self._get_scale()
        channel_dim = DimensionNames.Channel

        # Handle RGB images specially
        if DimensionNames.Samples in self.reader.dims.order:
            meta = {
                'name': self._build_layer_name(),
                'rgb': True,
                'metadata': base_metadata,
            }
            if scale:
                meta['scale'] = scale
            self.layer_data_tuples = [
                (self.napari_layer_data.data, meta, 'image')
            ]
            return self.layer_data_tuples

        # Single channel image (no channel dimension)
        if channel_dim not in self.napari_layer_data.dims:
            effective_type = layer_type or 'image'
            self.layer_data_tuples = [
                self._build_single_layer_tuple(
                    data=self.napari_layer_data.data,
                    layer_type=effective_type,
                    base_metadata=base_metadata,
                    scale=scale,
                    n_channels=1,
                    channel_kwargs=channel_kwargs,
                )
            ]
            return self.layer_data_tuples

        # Multichannel image - split into separate layers
        channel_names = [
            str(c)
            for c in self.napari_layer_data.coords[channel_dim].data.tolist()
        ]
        channel_axis = self.napari_layer_data.dims.index(channel_dim)
        n_channels = self.napari_layer_data.shape[channel_axis]

        layer_tuples = []
        for i in range(n_channels):
            channel_name = (
                channel_names[i] if i < len(channel_names) else f'channel_{i}'
            )
            effective_type = self._resolve_layer_type(
                channel_name, layer_type, channel_types
            )

            # Slice data along channel axis
            slices = [slice(None)] * self.napari_layer_data.ndim
            slices[channel_axis] = i
            channel_data = self.napari_layer_data.data[tuple(slices)]

            layer_tuples.append(
                self._build_single_layer_tuple(
                    data=channel_data,
                    layer_type=effective_type,
                    base_metadata=base_metadata,
                    scale=scale,
                    channel_name=channel_name,
                    channel_idx=i,
                    n_channels=n_channels,
                    channel_kwargs=channel_kwargs,
                )
            )

        self.layer_data_tuples = layer_tuples
        return self.layer_data_tuples

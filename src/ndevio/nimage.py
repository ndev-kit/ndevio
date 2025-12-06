"""Additional functionality for BioImage objects to be used in napari-ndev."""

from __future__ import annotations

import logging
from pathlib import Path

import xarray as xr
from bioio import BioImage
from bioio_base.dimensions import DimensionNames
from bioio_base.reader import Reader
from bioio_base.types import ImageLike, PathLike

logger = logging.getLogger(__name__)

DELIM = " :: "


def determine_reader_plugin(
    image: ImageLike, preferred_reader: str | None = None
) -> Reader:
    """
    Determine the reader plugin to use for loading an image.

    Convenience wrapper that integrates ReaderPluginManager with ndevio settings.
    For file paths, uses the priority system (DEFAULT_READER_PRIORITY).
    For arrays, uses bioio's default plugin detection.

    Parameters
    ----------
    image : ImageLike
        Image to be loaded (file path, numpy array, or xarray DataArray).
    preferred_reader : str, optional
        Preferred reader name. If None, uses ndevio_reader.preferred_reader
        from settings.

    Returns
    -------
    Reader
        Reader class to use for loading the image.

    Raises
    ------
    UnsupportedFileFormatError
        If no suitable reader can be found. Error message includes
        installation suggestions for missing plugins.

    """
    from bioio_base.exceptions import UnsupportedFileFormatError
    from ndev_settings import get_settings

    from ._plugin_manager import ReaderPluginManager

    # For file paths: use ReaderPluginManager
    if isinstance(image, str | Path):
        settings = get_settings()

        # Get preferred reader from settings if not provided
        if preferred_reader is None:
            preferred_reader = settings.ndevio_reader.preferred_reader  # type: ignore

        manager = ReaderPluginManager(image)
        reader = manager.get_working_reader(preferred_reader)

        if reader:
            return reader

        # No reader found - raise error with installation suggestions
        if settings.ndevio_reader.suggest_reader_plugins:  # type: ignore
            msg_extra = manager.get_installation_message()
        else:
            msg_extra = None

        raise UnsupportedFileFormatError(
            reader_name="ndevio",
            path=str(image),
            msg_extra=msg_extra,
        )

    # For arrays: use bioio's built-in plugin determination
    return nImage.determine_plugin(image).metadata.get_reader()


class nImage(BioImage):
    """
    An nImage is a BioImage with additional functionality for napari-ndev.

    Parameters
    ----------
    image : ImageLike
        Image to be loaded. Can be a path to an image file, a numpy array,
        or an xarray DataArray.
    reader : Reader, optional
        Reader to be used to load the image. If not provided, a reader will be
        determined based on the image type.

    Attributes
    ----------
    See BioImage for inherited attributes.

    Methods
    -------
    get_napari_image_data(in_memory=None)
        Get the image data as a xarray, optionally loading it into memory.


    """

    def __init__(self, image: ImageLike, reader: Reader | None = None) -> None:
        """
        Initialize an nImage with an image, and optionally a reader.

        If a reader is not provided, a reader will be determined by bioio.
        However, if the image is supported by the preferred reader, the reader
        will be set to preferred_reader.Reader to override the softer decision
        made by bioio.BioImage.determine_plugin().

        Note: The issue here is that bioio.BioImage.determine_plugin() will
        sort by install time and choose the first plugin that supports the
        image. This is not always the desired behavior, because bioio-tifffile
        can take precedence over bioio-ome-tiff, even if the image was saved
        as an OME-TIFF via bioio.writers.OmeTiffWriter (which is the case
        for napari-ndev).

        Note: If no suitable reader can be found, an UnsupportedFileFormatError
        will be raised, with installation suggestions for missing plugins.
        """
        from ndev_settings import get_settings

        self.settings = get_settings()

        if reader is None:
            reader = determine_reader_plugin(image)

        super().__init__(image=image, reader=reader)  # type: ignore
        self.napari_data = None
        self.napari_metadata = {}
        self.path = image if isinstance(image, str | Path) else None

    def _determine_in_memory(
        self,
        path=None,
        max_in_mem_bytes: int = 4e9,
        max_in_mem_percent: int = 0.3,
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

    def get_napari_image_data(
        self, in_memory: bool | None = None
    ) -> xr.DataArray:
        """
        Get the image data as a xarray DataArray.

        From BioImage documentation:
        If you do not want the image pre-stitched together, you can use the base reader
        by either instantiating the reader independently or using the `.reader` property.

        Parameters
        ----------
        in_memory : bool, optional
            Whether to load the image in memory or not.
            If None, will determine whether to load in memory based on the image size.

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
                    self.napari_data = self.reader.mosaic_xarray_data.squeeze()
                else:
                    self.napari_data = (
                        self.reader.mosaic_xarray_dask_data.squeeze()
                    )

            except NotImplementedError:
                logger.warning(
                    "Bioio: Mosaic tile switching not supported for this reader"
                )
                return None
        else:
            if in_memory:
                self.napari_data = self.reader.xarray_data.squeeze()
            else:
                self.napari_data = self.reader.xarray_dask_data.squeeze()

        return self.napari_data

    # Metadata keys that are only valid for image layers, not labels/other layers
    # Note: channel_axis is NOT included here because the reader function needs it
    # to split multichannel data for non-image layers, then removes it before
    # passing to napari
    _IMAGE_ONLY_METADATA_KEYS = {"rgb", "colormap", "contrast_limits"}

    def get_napari_metadata(
        self,
        path: PathLike | None = None,
        layer_type: str = "image",
    ) -> dict:
        """
        Get the metadata for the image to be displayed in napari.

        Parameters
        ----------
        path : PathLike, optional
            Path to the image file.
        layer_type : str, optional
            The napari layer type ('image', 'labels', etc.). Default is 'image'.
            Some metadata keys (like 'channel_axis', 'rgb') are only valid for
            image layers and will be filtered out for other layer types.

        Returns
        -------
        dict
            Metadata for the image to be displayed in napari.

        """
        if self.napari_data is None:
            self.get_napari_image_data()  # this also sets self.path
        # override the nImage path only if provided
        path = self.path if path is None else path

        # Determine available metadata information
        meta = {}
        scene = self.current_scene
        scene_idx = self.current_scene_index
        path_stem = (
            Path(self.path).stem if self.path is not None else "unknown path"
        )

        NO_SCENE = (
            len(self.scenes) == 1 and self.current_scene == "Image:0"
        )  # Image:0 is the default scene name, suggesting there is no information
        CHANNEL_DIM = DimensionNames.Channel
        IS_MULTICHANNEL = CHANNEL_DIM in self.napari_data.dims

        # Build metadata under various condition
        # add channel_axis if unpacking channels as layers
        if IS_MULTICHANNEL:
            # Convert to plain Python strings to avoid numpy string types (NumPy 2.0+)
            channel_names = [
                str(c)
                for c in self.napari_data.coords[CHANNEL_DIM].data.tolist()
            ]

            if self.settings.ndevio_reader.unpack_channels_as_layers:
                meta["channel_axis"] = self.napari_data.dims.index(CHANNEL_DIM)

                if NO_SCENE:
                    meta["name"] = [
                        f"{C}{DELIM}{path_stem}" for C in channel_names
                    ]
                else:
                    meta["name"] = [
                        f"{C}{DELIM}{scene_idx}{DELIM}{scene}{DELIM}{path_stem}"
                        for C in channel_names
                    ]

            if not self.settings.ndevio_reader.unpack_channels_as_layers:
                meta["name"] = (
                    f"{DELIM}".join(channel_names)
                    + f"{DELIM}{scene_idx}{DELIM}{scene}{DELIM}{path_stem}"
                )

        if not IS_MULTICHANNEL:
            if NO_SCENE:
                meta["name"] = path_stem
            else:
                meta["name"] = f"{scene_idx}{DELIM}{scene}{DELIM}{path_stem}"

        # Handle if RGB
        if DimensionNames.Samples in self.reader.dims.order:
            meta["rgb"] = True

        # Handle scales
        scale = [
            getattr(self.physical_pixel_sizes, dim)
            for dim in self.napari_data.dims
            if dim
            in {
                DimensionNames.SpatialX,
                DimensionNames.SpatialY,
                DimensionNames.SpatialZ,
            }
            and getattr(self.physical_pixel_sizes, dim) is not None
        ]

        if scale:
            meta["scale"] = tuple(scale)

        # get all other metadata
        img_meta = {"bioimage": self, "raw_image_metadata": self.metadata}

        try:
            img_meta["ome_metadata"] = self.ome_metadata
        except NotImplementedError:
            pass  # Reader doesn't support OME metadata, so we don't attach it to napari metadata
        except (ValueError, TypeError, KeyError) as e:
            # Some files have metadata that doesn't conform to OME schema, despite bioio attempting to parse it
            # (e.g., CZI files with LatticeLightsheet acquisition mode)
            # As such, when accessing ome_metadata, we may get various exceptions
            # Log warning but continue - raw metadata is still available
            logger.warning(
                "Could not parse OME metadata: %s. "
                "Raw metadata is still available in 'raw_image_metadata'.",
                e,
            )

        meta["metadata"] = img_meta

        # Filter out image-only metadata keys for non-image layer types
        if layer_type != "image":
            meta = {
                k: v
                for k, v in meta.items()
                if k not in self._IMAGE_ONLY_METADATA_KEYS
            }

        self.napari_metadata = meta
        return self.napari_metadata

    def build_napari_layer_tuples(
        self,
        path: PathLike | None = None,
        layer_type: str = "image",
        in_memory: bool | None = None,
    ) -> list[tuple]:
        """
        Build napari layer data tuples, handling channel splitting for non-image layers.

        For image layers, napari handles channel_axis splitting automatically
        with conveniences like cycling colormaps and additive blending.
        For other layer types (labels, etc.), we manually split the data
        along the channel axis since only add_image() supports channel_axis.

        Parameters
        ----------
        path : PathLike, optional
            Path to the image file. If None, uses self.path.
        layer_type : str, optional
            The napari layer type ('image', 'labels', etc.). Default is 'image'.
        in_memory : bool, optional
            Whether to load the image in memory. If None, determined automatically.

        Returns
        -------
        list[tuple]
            List of (data, metadata, layer_type) tuples ready for napari.

        Examples
        --------
        >>> img = nImage("path/to/image.tiff")
        >>> layer_tuples = img.build_napari_layer_tuples(layer_type="labels")
        >>> for data, meta, ltype in layer_tuples:
        ...     viewer.add_layer(Layer.create(data, meta, ltype))

        """
        # Ensure data and metadata are loaded
        if self.napari_data is None:
            self.get_napari_image_data(in_memory=in_memory)

        img_data = self.napari_data
        img_meta = self.get_napari_metadata(path=path, layer_type=layer_type)

        # For image layers, napari handles channel_axis - return as single tuple
        if layer_type == "image" or "channel_axis" not in img_meta:
            return [(img_data.data, img_meta, layer_type)]

        # For non-image layers, check if we need to split channels manually
        channel_axis = img_meta.pop("channel_axis", None)

        if channel_axis is not None:
            # We have multichannel data that needs manual splitting
            names = img_meta.get("name", [])
            if not isinstance(names, list):
                names = [names]

            layer_tuples = []
            n_channels = img_data.shape[channel_axis]

            for i in range(n_channels):
                # Slice the data along channel axis
                slices = [slice(None)] * img_data.ndim
                slices[channel_axis] = i
                channel_data = img_data.data[tuple(slices)]

                # Build per-channel metadata
                channel_meta = img_meta.copy()
                if i < len(names):
                    channel_meta["name"] = names[i]
                # Handle case where name is still a list
                if "name" in channel_meta and isinstance(
                    channel_meta["name"], list
                ):
                    channel_meta["name"] = (
                        names[i] if i < len(names) else f"channel_{i}"
                    )

                layer_tuples.append((channel_data, channel_meta, layer_type))

            return layer_tuples

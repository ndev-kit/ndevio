"""Tests for ndevio.nImage class."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import bioio_tifffile
import pytest

from ndevio import nImage

RGB_TIFF = (
    "RGB_bad_metadata.tiff"  # has two scenes, with really difficult metadata
)
CELLS3D2CH_OME_TIFF = "cells3d2ch_legacy.tiff"  # 2 channel, 3D OME-TIFF, from old napari-ndev saving
LOGO_PNG = "nDev-logo.small.png"  # small PNG file


def test_nImage_init(resources_dir: Path):
    """Test nImage initialization."""
    img = nImage(resources_dir / RGB_TIFF)
    assert img.path == resources_dir / RGB_TIFF
    assert img.reader is not None
    assert img.data.shape == (1, 1, 1, 1440, 1920, 3)
    assert img.napari_data is None


def test_nImage_ome_reader(resources_dir: Path):
    """
    Test that the OME-TIFF reader is used for OME-TIFF files.

    This test is in response to https://github.com/bioio-devs/bioio/issues/79
    whereby images saved with bioio.writers.OmeTiffWriter are not being read with
    bioio_ome_tiff.Reader, but instead with bioio_tifffile.Reader.

    The example here was saved with aicsimageio.writers.OmeTiffWriter. nImage
    has an __init__ function that should override the reader determined by
    bioio.BioImage.determine_plugin() with bioio_ome_tiff if the image is an
    OME-TIFF.
    """

    img_path = resources_dir / CELLS3D2CH_OME_TIFF

    nimg = nImage(img_path)
    assert nimg.settings.ndevio_Reader.preferred_reader == "bioio-ome-tiff"
    # the below only exists if 'bioio-ome-tiff' is used
    assert hasattr(nimg, "ome_metadata")
    assert nimg.channel_names == ["membrane", "nuclei"]

    nimg = nImage(img_path, reader=bioio_tifffile.Reader)

    # check that despite preferred reader, the reader is still bioio_tifffile
    # because there is no ome_metadata
    assert nimg.settings.ndevio_Reader.preferred_reader == "bioio-ome-tiff"
    # check that calling nimg.ome_metadata raises NotImplementedError
    with pytest.raises(NotImplementedError):
        _ = nimg.ome_metadata


@pytest.mark.skip(
    reason="OmeTiffWriter removed in bioio 3.0+, will implement in _writer.py"
)
def test_nImage_save_read(resources_dir: Path, tmp_path: Path):
    """
    Test saving and reading an image with OmeTiffWriter and nImage.

    Confirm that the image is saved with the correct physical pixel sizes and
    channel names, and that it is read back with the same physical pixel sizes
    and channel names because it is an OME-TIFF. See the above test for
    the need of this and to ensure not being read by bioio_tifffile.Reader.

    TODO: Re-enable this test once we implement write_ome_tiff in _writer.py

    Expected behavior:
    - Load test image with known physical pixel sizes
    - Save with new physical pixel sizes and channel names
    - Re-load and verify metadata is preserved correctly
    - Confirm it's read as OME-TIFF (not via bioio_tifffile)
    """


def test_determine_in_memory(resources_dir: Path):
    """Test in-memory determination for small files."""
    img = nImage(resources_dir / RGB_TIFF)
    assert img._determine_in_memory() is True


def test_nImage_determine_in_memory_large_file(resources_dir: Path):
    """Test in-memory determination for large files."""
    img = nImage(resources_dir / RGB_TIFF)
    with (
        mock.patch(
            "psutil.virtual_memory", return_value=mock.Mock(available=1e9)
        ),
        mock.patch(
            "bioio_base.io.pathlike_to_fs",
            return_value=(mock.Mock(size=lambda x: 5e9), ""),
        ),
    ):
        assert img._determine_in_memory() is False


def test_get_napari_image_data(resources_dir: Path):
    """Test getting napari image data in memory."""
    img = nImage(resources_dir / RGB_TIFF)
    img.get_napari_image_data()
    assert img.napari_data.shape == (1440, 1920, 3)
    assert img.napari_data.dims == ("Y", "X", "S")


def test_get_napari_image_data_not_in_memory(resources_dir: Path):
    """Test getting napari image data as dask array."""
    import dask

    img = nImage(resources_dir / RGB_TIFF)
    img.get_napari_image_data(in_memory=False)
    assert img.napari_data is not None
    # check that the data is a dask array
    assert isinstance(img.napari_data.data, dask.array.core.Array)


def test_get_napari_metadata(resources_dir: Path):
    """Test napari metadata generation."""
    img = nImage(resources_dir / RGB_TIFF)
    img.get_napari_metadata(path=img.path)
    assert img.napari_metadata["name"] == "0 :: Image:0 :: RGB_bad_metadata"
    assert img.napari_metadata["scale"] == (
        264.5833333333333,
        264.5833333333333,
    )
    assert img.napari_metadata["rgb"] is True


def test_get_napari_image_data_mosaic_tile_in_memory(resources_dir: Path):
    """Test mosaic tile image data in memory."""
    import xarray as xr
    from bioio_base.dimensions import DimensionNames

    with mock.patch.object(nImage, "reader", create=True) as mock_reader:
        mock_reader.dims.order = [DimensionNames.MosaicTile]
        mock_reader.mosaic_xarray_data.squeeze.return_value = xr.DataArray(
            [1, 2, 3]
        )
        img = nImage(resources_dir / RGB_TIFF)
        data = img.get_napari_image_data(in_memory=True)
        assert data is not None
        assert data.shape == (3,)
        assert img.napari_data is not None


def test_get_napari_image_data_mosaic_tile_not_in_memory(
    resources_dir: Path,
):
    """Test mosaic tile image data as dask array."""
    import xarray as xr
    from bioio_base.dimensions import DimensionNames

    with mock.patch.object(nImage, "reader", create=True) as mock_reader:
        mock_reader.dims.order = [DimensionNames.MosaicTile]
        mock_reader.mosaic_xarray_dask_data.squeeze.return_value = (
            xr.DataArray([1, 2, 3])
        )
        img = nImage(resources_dir / RGB_TIFF)
        data = img.get_napari_image_data(in_memory=False)
        assert data is not None
        assert data.shape == (3,)
        assert img.napari_data is not None

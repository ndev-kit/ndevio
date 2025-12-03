"""Tests for ndevio.nImage class."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

try:
    import bioio_tifffile
except ImportError:  # pragma: no cover - optional test dependency
    bioio_tifffile = None

import pytest
from bioio_base.exceptions import UnsupportedFileFormatError

from ndevio import nImage
from ndevio.nimage import determine_reader_plugin

RGB_TIFF = (
    "RGB_bad_metadata.tiff"  # has two scenes, with really difficult metadata
)
CELLS3D2CH_OME_TIFF = "cells3d2ch_legacy.tiff"  # 2 channel, 3D OME-TIFF, from old napari-ndev saving
LOGO_PNG = "nDev-logo-small.png"  # small PNG file (fix typo)
CZI_FILE = "0T-4C-0Z-7pos.czi"  # multi-scene CZI file
ND2_FILE = "ND2_dims_rgb.nd2"  # ND2 file requiring bioio-nd2


def test_nImage_init(resources_dir: Path):
    """Test nImage initialization with a file that should work."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    assert img.path == resources_dir / CELLS3D2CH_OME_TIFF
    assert img.reader is not None
    # Shape is (T, C, Z, Y, X) = (1, 2, 60, 66, 85)
    assert img.data.shape == (1, 2, 60, 66, 85)
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
    assert nimg.settings.ndevio_reader.preferred_reader == "bioio-ome-tiff"
    # the below only exists if 'bioio-ome-tiff' is used
    assert hasattr(nimg, "ome_metadata")
    assert nimg.channel_names == ["membrane", "nuclei"]

    # Additional check that the reader override works when bioio_tifffile is
    # available. The project does not require bioio_tifffile as a test
    # dependency, so skip this part when it's missing.
    if bioio_tifffile is None:  # pragma: no cover - optional
        pytest.skip(
            "bioio_tifffile not installed; skipping reader-override checks"
        )

    nimg = nImage(img_path, reader=bioio_tifffile.Reader)

    # check that despite preferred reader, the reader is still bioio_tifffile
    # because there is no ome_metadata
    assert nimg.settings.ndevio_reader.preferred_reader == "bioio-ome-tiff"
    # check that calling nimg.ome_metadata raises NotImplementedError
    with pytest.raises(NotImplementedError):
        _ = nimg.ome_metadata


def test_nImage_save_read(resources_dir: Path, tmp_path: Path):
    """
    Test saving and reading an image with OmeTiffWriter and nImage.

    Confirm that the image is saved with the correct physical pixel sizes and
    channel names, and that it is read back with the same physical pixel sizes
    and channel names because it is an OME-TIFF. See the above test for
    the need of this and to ensure not being read by bioio_tifffile.Reader.
    """
    from bioio_base.types import PhysicalPixelSizes
    from bioio_ome_tiff.writers import OmeTiffWriter

    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    assert img.physical_pixel_sizes.X == 1

    img_data = img.get_image_data("CZYX")
    OmeTiffWriter.save(
        img_data,
        tmp_path / "test_save_read.tiff",
        dim_order="CZYX",
        physical_pixel_sizes=PhysicalPixelSizes(1, 2, 3),  # ZYX
        channel_names=["test1", "test2"],
    )
    assert (tmp_path / "test_save_read.tiff").exists()

    new_img = nImage(tmp_path / "test_save_read.tiff")

    # having the below features means it is properly read as OME-TIFF
    assert new_img.physical_pixel_sizes.Z == 1
    assert new_img.physical_pixel_sizes.Y == 2
    assert new_img.physical_pixel_sizes.X == 3
    assert new_img.channel_names == ["test1", "test2"]


def test_determine_in_memory(resources_dir: Path):
    """Test in-memory determination for small files."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    assert img._determine_in_memory() is True


def test_nImage_determine_in_memory_large_file(resources_dir: Path):
    """Test in-memory determination for large files."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
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
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    img.get_napari_image_data()
    # napari_data will be squeezed and first channel selected by default
    # Original shape (1, 2, 60, 66, 85) -> first channel (60, 66, 85)
    assert img.napari_data.shape == (2, 60, 66, 85)
    assert img.napari_data.dims == ("C", "Z", "Y", "X")


def test_get_napari_image_data_not_in_memory(resources_dir: Path):
    """Test getting napari image data as dask array."""
    import dask

    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    img.get_napari_image_data(in_memory=False)
    assert img.napari_data is not None
    # check that the data is a dask array
    assert isinstance(img.napari_data.data, dask.array.core.Array)


def test_get_napari_metadata(resources_dir: Path):
    """Test napari metadata generation."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    img.get_napari_metadata(path=img.path)
    # With channels, the name will be a list of channel names
    assert any(
        "cells3d2ch_legacy" in name for name in img.napari_metadata["name"]
    )
    assert img.napari_metadata["scale"] is not None


def test_get_napari_image_data_mosaic_tile_in_memory(resources_dir: Path):
    """Test mosaic tile image data in memory."""
    import xarray as xr
    from bioio_base.dimensions import DimensionNames

    with mock.patch.object(nImage, "reader", create=True) as mock_reader:
        mock_reader.dims.order = [DimensionNames.MosaicTile]
        mock_reader.mosaic_xarray_data.squeeze.return_value = xr.DataArray(
            [1, 2, 3]
        )
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
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
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        data = img.get_napari_image_data(in_memory=False)
        assert data is not None
        assert data.shape == (3,)
        assert img.napari_data is not None


@pytest.mark.parametrize(
    ("filename", "should_work", "expected_plugin_suggestion"),
    [
        (LOGO_PNG, True, None),  # PNG works with bioio-imageio (core)
        (
            CELLS3D2CH_OME_TIFF,
            True,
            None,
        ),  # OME-TIFF works with bioio-ome-tiff (core)
        (CZI_FILE, True, None),
        (ND2_FILE, False, "bioio-nd2"),  # ND2 needs bioio-nd2
        (RGB_TIFF, True, None),
    ],
)
def test_determine_reader_plugin_behavior(
    resources_dir: Path,
    filename: str,
    should_work: bool | str,
    expected_plugin_suggestion: str | None,
):
    """Test determine_reader_plugin with various file formats.

    Parameters
    ----------
    filename : str
        Test file name
    should_work : bool | "maybe"
        True = must succeed, False = must fail, "maybe" = can succeed or fail
    expected_plugin_suggestion : str | None
        If failure expected, the plugin name that should be suggested
    """
    if should_work is True:
        # Must successfully determine a reader
        reader = determine_reader_plugin(resources_dir / filename)
        assert reader is not None
    elif should_work is False:
        # Must fail with helpful error message
        with pytest.raises(UnsupportedFileFormatError) as exc_info:
            determine_reader_plugin(resources_dir / filename)

        error_msg = str(exc_info.value)
        assert filename in error_msg
        if expected_plugin_suggestion:
            assert expected_plugin_suggestion in error_msg
        assert "pip install" in error_msg
    else:  # "maybe"
        # Can succeed or fail; if fails, check for helpful message
        try:
            reader = determine_reader_plugin(resources_dir / filename)
            assert reader is not None
        except UnsupportedFileFormatError as e:
            error_msg = str(e)
            if expected_plugin_suggestion:
                assert expected_plugin_suggestion in error_msg
            assert "pip install" in error_msg


@pytest.mark.parametrize(
    ("filename", "should_work", "expected_error_contains"),
    [
        (LOGO_PNG, True, None),
        (CELLS3D2CH_OME_TIFF, True, None),
        (CZI_FILE, True, None),
        (ND2_FILE, False, ["bioio-nd2", "pip install"]),
        (RGB_TIFF, True, None),
    ],
)
def test_nimage_init_with_various_formats(
    resources_dir: Path,
    filename: str,
    should_work: bool | str,
    expected_error_contains: list[str] | None,
):
    """Test nImage initialization with various file formats.

    This tests the complete workflow: file → determine_reader_plugin → nImage init
    """
    if should_work is True:
        # Must successfully initialize
        img = nImage(resources_dir / filename)
        assert img.data is not None
        assert img.path == resources_dir / filename
    elif should_work is False:
        # Must fail with helpful error
        with pytest.raises(UnsupportedFileFormatError) as exc_info:
            nImage(resources_dir / filename)

        error_msg = str(exc_info.value)
        if expected_error_contains:
            for expected_text in expected_error_contains:
                assert expected_text in error_msg
    else:  # "maybe"
        # Can succeed or fail
        try:
            img = nImage(resources_dir / filename)
            assert img.data is not None
        except UnsupportedFileFormatError as e:
            error_msg = str(e)
            # Should contain at least one of the expected error texts
            if expected_error_contains:
                assert any(
                    text in error_msg for text in expected_error_contains
                )

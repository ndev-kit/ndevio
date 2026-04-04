"""Tests for ndevio.nImage class."""

from __future__ import annotations

from pathlib import Path
from unittest import mock
from unittest.mock import patch

import pytest
from bioio_base.exceptions import UnsupportedFileFormatError

from ndevio import nImage

RGB_TIFF = (
    'RGB_bad_metadata.tiff'  # has two scenes, with really difficult metadata
)
CELLS3D2CH_OME_TIFF = 'cells3d2ch_legacy.tiff'  # 2 channel, 3D OME-TIFF, from old napari-ndev saving
LOGO_PNG = 'nDev-logo-small.png'  # small PNG file (fix typo)
CZI_FILE = '0T-4C-0Z-7pos.czi'  # multi-scene CZI file
ND2_FILE = 'ND2_dims_rgb.nd2'  # ND2 file requiring bioio-nd2
ZARR = 'dimension_handling_zyx_V3.zarr'


def test_nImage_init(resources_dir: Path):
    """Test nImage initialization with a file that should work."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    assert img.path == str(resources_dir / CELLS3D2CH_OME_TIFF)
    assert img.reader is not None
    # Shape is (T, C, Z, Y, X) = (1, 2, 60, 66, 85)
    assert img.data.shape == (1, 2, 60, 66, 85)
    # layer_data should not be loaded until accessed
    assert img._reference_xarray is None
    # Accessing the property triggers lazy loading
    assert img.reference_xarray is not None


def test_nImage_zarr(resources_dir: Path):
    """Test that nImage can read a Zarr file."""
    img = nImage(resources_dir / ZARR)
    assert img.data is not None
    assert img.path == str(resources_dir / ZARR)
    assert img.data.shape == (1, 1, 2, 4, 4)


def test_nImage_zarr_trailing_slash(resources_dir: Path):
    """Test that a string path with a trailing slash is handled correctly.

    Regression test: bioio's extension-based reader detection fails when the
    path ends with '/', e.g. 'store.zarr/'. nImage strips the slash on init.
    See https://github.com/ndev-kit/ndevio/issues/XX
    """
    path_with_slash = str(resources_dir / ZARR) + '/'
    img = nImage(path_with_slash)
    assert img.data is not None
    # path stored without the trailing slash
    assert not img.path.endswith('/')
    assert img.path == str(resources_dir / ZARR)
    assert img.data.shape == (1, 1, 2, 4, 4)


@pytest.mark.network
def test_nImage_remote_zarr_trailing_slash():
    """Test that a remote Zarr URL with a trailing slash is read correctly.

    Regression test: 'https://...9846152.zarr/' crashed with
    'Reader ndevio returned no data' because the trailing slash prevented
    bioio from matching the '*.zarr' extension pattern.
    """
    remote_zarr = (
        'https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0048A/9846152.zarr/'
    )
    img = nImage(remote_zarr)
    assert img._is_remote
    assert not img.path.endswith('/')
    assert img.path == remote_zarr.rstrip('/')
    assert img.xarray_dask_data is not None


@pytest.mark.network
def test_nImage_remote_zarr():
    """Test that nImage can read a remote Zarr file."""
    remote_zarr = 'https://uk1s3.embassy.ebi.ac.uk/ebi-ngff-challenge-2024/4ffaeed2-fa70-4907-820f-8a96ef683095.zarr'  # from https://github.com/bioio-devs/bioio-ome-zarr/blob/main/bioio_ome_zarr/tests/test_remote_read_zarrV3.py
    img = nImage(remote_zarr)
    assert img.path == remote_zarr
    assert img._is_remote
    # original shape is (1, 2, 1, 512, 512) but layer_data is squeezed
    assert img.reference_xarray.shape == (2, 512, 512)


@pytest.mark.network
def test_nImage_remote_zarr_v01v02_format(caplog):
    """Test that nImage emits a warning for old OME-Zarr formats when reading remotely."""
    remote_zarr = 'https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.1/9836841.zarr'  # from https://github.com/ndev-kit/ndevio/issues/50
    with caplog.at_level(
        'WARNING', logger='ndevio.bioio_plugins._compatibility'
    ):
        img = nImage(remote_zarr)
    assert img.path == remote_zarr
    # should catch a key error due to old format
    # but still quietly create a scale with no units
    assert img.layer_scale == (1.0, 1.0)
    assert img.layer_units == (None, None)


@pytest.mark.network
def test_nimage_remote_v03_zarr():
    """Test that nImage can read a real remote OME-Zarr v0.3 store."""
    remote_zarr = 'https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.3/9836842.zarr'
    img = nImage(remote_zarr)
    assert img.path == remote_zarr
    assert img._is_remote
    assert img.reference_xarray is not None
    tuples = img.get_layer_data_tuples()
    assert len(tuples) > 0


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
    # assert nimg.settings.ndevio_reader.preferred_reader == 'bioio-ome-tiff'  # this was the old methodology before bioio#162
    assert nimg.reader.name == 'bioio_ome_tiff'
    # the below only exists if 'bioio-ome-tiff' is used
    assert hasattr(nimg, 'ome_metadata')
    assert nimg.channel_names == ['membrane', 'nuclei']


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

    img_data = img.get_image_data('CZYX')
    OmeTiffWriter.save(
        img_data,
        tmp_path / 'test_save_read.tiff',
        dim_order='CZYX',
        physical_pixel_sizes=PhysicalPixelSizes(1, 2, 3),  # ZYX
        channel_names=['test1', 'test2'],
    )
    assert (tmp_path / 'test_save_read.tiff').exists()

    new_img = nImage(tmp_path / 'test_save_read.tiff')

    # having the below features means it is properly read as OME-TIFF
    assert new_img.physical_pixel_sizes.Z == 1
    assert new_img.physical_pixel_sizes.Y == 2
    assert new_img.physical_pixel_sizes.X == 3
    assert new_img.channel_names == ['test1', 'test2']


def test_get_layer_data(resources_dir: Path):
    """Test loading napari layer data in memory."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    # Access layer_data property to trigger loading
    data = img.reference_xarray
    # layer_data will be squeezed
    # Original shape (1, 2, 60, 66, 85) -> (2, 60, 66, 85)
    assert data.shape == (2, 60, 66, 85)
    assert data.dims == ('C', 'Z', 'Y', 'X')


def test_get_layer_data_tuples_basic(resources_dir: Path):
    """Test layer data tuple generation."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    layer_tuples = img.get_layer_data_tuples()
    # With 2 channels, should get 2 tuples (one per channel)
    assert len(layer_tuples) == 2
    for _data, meta, layer_type in layer_tuples:
        assert 'cells3d2ch_legacy' in meta['name']
        assert meta['scale'] is not None
        assert layer_type == 'image'  # default layer type


def test_get_layer_data_tuples_ome_validation_error_logged(
    resources_dir: Path,
    caplog: pytest.LogCaptureFixture,
):
    """Test that OME metadata validation errors are logged but don't crash.

    Some files (e.g., CZI files with LatticeLightsheet acquisition mode) have
    metadata that doesn't conform to the OME schema, causing ValidationError
    when accessing ome_metadata. This should be logged as a warning but not
    prevent the image from loading.
    """
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)

    # Mock ome_metadata to raise a ValidationError (which inherits from ValueError)
    with mock.patch.object(
        type(img),
        'ome_metadata',
        new_callable=mock.PropertyMock,
        side_effect=ValueError('Invalid acquisition_mode: LatticeLightsheet'),
    ):
        caplog.clear()
        layer_tuples = img.get_layer_data_tuples()

        # Should still return valid layer tuples
        assert layer_tuples is not None
        assert len(layer_tuples) > 0

        # Check that metadata dict exists in each tuple
        for _, meta, _ in layer_tuples:
            assert 'name' in meta
            assert 'metadata' in meta
            # ome_metadata should NOT be in the nested metadata dict
            assert 'ome_metadata' not in meta['metadata']
            # raw_image_metadata should still be available
            assert 'raw_image_metadata' in meta['metadata']

        # Warning should be logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == 'WARNING'
        assert 'Could not parse OME metadata' in caplog.records[0].message
        assert 'LatticeLightsheet' in caplog.records[0].message


def test_get_layer_data_tuples_ome_not_implemented_silent(
    resources_dir: Path,
    caplog: pytest.LogCaptureFixture,
):
    """Test that NotImplementedError for ome_metadata is silently ignored.

    Some readers don't support OME metadata at all. This should be silently
    ignored without logging.
    """
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)

    # Mock ome_metadata to raise NotImplementedError
    with mock.patch.object(
        type(img),
        'ome_metadata',
        new_callable=mock.PropertyMock,
        side_effect=NotImplementedError(
            'Reader does not support OME metadata'
        ),
    ):
        caplog.clear()
        layer_tuples = img.get_layer_data_tuples()

        # Should still return valid layer tuples
        assert layer_tuples is not None
        assert len(layer_tuples) > 0

        for _, meta, _ in layer_tuples:
            assert 'ome_metadata' not in meta['metadata']

        # No warning should be logged for NotImplementedError
        assert len(caplog.records) == 0


@pytest.mark.parametrize(
    ('filename', 'should_work', 'expected_error_contains'),
    [
        (LOGO_PNG, True, None),
        (CELLS3D2CH_OME_TIFF, True, None),
        (CZI_FILE, True, None),
        (ND2_FILE, False, ['bioio-nd2', 'pip install']),
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

    This tests the complete workflow: file → get_reader_priority → nImage init
    """
    if should_work is True:
        # Must successfully initialize
        img = nImage(resources_dir / filename)
        assert img.data is not None
        assert img.path == str(resources_dir / filename)
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


# =============================================================================
# Tests for get_layer_data_tuples
# =============================================================================


class TestGetLayerDataTuples:
    """Tests for nImage.get_layer_data_tuples method."""

    def test_multichannel_returns_tuple_per_channel(self, resources_dir: Path):
        """Test that multichannel images return one tuple per channel.

        The new API always splits channels, returning separate tuples for each.
        """
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        layer_tuples = img.get_layer_data_tuples()

        # Should return one tuple per channel (2 channels)
        assert len(layer_tuples) == 2

        for data, meta, layer_type in layer_tuples:
            # channel_axis should NOT be in metadata (we split ourselves)
            assert 'channel_axis' not in meta

            # name should be a string (not a list)
            assert isinstance(meta['name'], str)

            # Data should be a list of arrays (multiscale-ready)
            assert isinstance(data, list)
            assert len(data) == 1  # single resolution level
            # Shape should NOT include channel dimension
            assert data[0].shape == (60, 66, 85)  # ZYX only

            # Default layer type is "image" (channel names don't match label keywords)
            assert layer_type == 'image'

    def test_layer_names_include_channel_names(self, resources_dir: Path):
        """Test that layer names include channel names from the file."""
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        layer_tuples = img.get_layer_data_tuples()

        # Extract names from the tuples
        names = [meta['name'] for _, meta, _ in layer_tuples]

        # Channel names from the file are "membrane" and "nuclei"
        assert 'membrane' in names[0]
        assert 'nuclei' in names[1]

    def test_layer_names_matches_tuple_names(self, resources_dir: Path):
        """Test that layer_names property matches names in get_layer_data_tuples."""
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        layer_tuples = img.get_layer_data_tuples()

        # layer_names should match names baked into the tuples
        assert img.layer_names == [meta['name'] for _, meta, _ in layer_tuples]
        assert len(img.layer_names) == 2
        assert 'membrane' in img.layer_names[0]
        assert 'nuclei' in img.layer_names[1]

    def test_layer_names_single_channel(self, resources_dir: Path):
        """Test layer_names for a single-channel image."""
        img = nImage(resources_dir / LOGO_PNG)
        assert len(img.layer_names) == 1
        assert img.layer_names[0].endswith(img.path_stem)

    def test_single_channel_image_returns_single_tuple(
        self, resources_dir: Path
    ):
        """Test that single channel images return single tuple."""
        # PNG is single channel (or RGB treated as single layer)
        img = nImage(resources_dir / LOGO_PNG)
        layer_tuples = img.get_layer_data_tuples()

        # Single channel should return single tuple
        assert len(layer_tuples) == 1

        data, meta, layer_type = layer_tuples[0]
        assert 'channel_axis' not in meta
        assert layer_type == 'image'

    def test_scale_preserved_in_tuples(self, resources_dir: Path):
        """Test that scale metadata is preserved in each tuple."""
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        layer_tuples = img.get_layer_data_tuples()

        for _, meta, _ in layer_tuples:
            # Scale should be preserved in each layer
            assert 'scale' in meta
            # Original has physical pixel sizes, so scale should have values
            assert len(meta['scale']) > 0

    def test_colormap_cycling_for_images(self, resources_dir: Path):
        """Test that image layers get colormaps based on napari's defaults.

        - 1 channel → gray
        - 2 channels → magenta, green (MAGENTA_GREEN)
        - 3+ channels → cycles through CYMRGB
        """
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        layer_tuples = img.get_layer_data_tuples()

        # Extract colormaps from the tuples
        colormaps = [meta.get('colormap') for _, meta, _ in layer_tuples]

        # 2 channels should use MAGENTA_GREEN
        assert colormaps[0] == 'magenta'
        assert colormaps[1] == 'green'

    def test_colormap_single_channel_is_gray(self, resources_dir: Path):
        """Test that single channel images get gray colormap."""
        import numpy as np
        import xarray as xr

        # Create nImage directly with single channel data (no Channel dimension)
        mock_data = xr.DataArray(
            np.zeros((10, 10)),
            dims=['Y', 'X'],
        )
        img = nImage(mock_data)

        layer_tuples = img.get_layer_data_tuples()
        assert len(layer_tuples) == 1
        assert layer_tuples[0][1]['colormap'] == 'gray'

    def test_colormap_three_plus_channels_uses_multi_channel_cycle(
        self, resources_dir: Path
    ):
        """Test that 3+ channel images cycle through MULTI_CHANNEL_CYCLE."""
        import numpy as np
        import xarray as xr
        from bioio_base.dimensions import DimensionNames

        from ndevio.utils._colormap_utils import MULTI_CHANNEL_CYCLE

        # Create nImage directly with 4 channel data
        mock_data = xr.DataArray(
            np.zeros((4, 10, 10)),
            dims=[DimensionNames.Channel, 'Y', 'X'],
            coords={DimensionNames.Channel: ['ch0', 'ch1', 'ch2', 'ch3']},
        )
        img = nImage(mock_data)

        layer_tuples = img.get_layer_data_tuples()
        colormaps = [meta.get('colormap') for _, meta, _ in layer_tuples]

        # Should cycle through MULTI_CHANNEL_CYCLE (CMYBGR)
        assert colormaps[0] == MULTI_CHANNEL_CYCLE[0]  # cyan
        assert colormaps[1] == MULTI_CHANNEL_CYCLE[1]  # magenta
        assert colormaps[2] == MULTI_CHANNEL_CYCLE[2]  # yellow
        assert colormaps[3] == MULTI_CHANNEL_CYCLE[3]  # blue

    def test_auto_detect_labels_from_channel_name(self, resources_dir: Path):
        """Test that channels with label-like names are detected as labels."""
        import numpy as np
        import xarray as xr
        from bioio_base.dimensions import DimensionNames

        # Create nImage directly with a channel named "mask"
        mock_data = xr.DataArray(
            np.zeros((2, 10, 10)),
            dims=[DimensionNames.Channel, 'Y', 'X'],
            coords={DimensionNames.Channel: ['intensity', 'mask']},
        )
        img = nImage(mock_data)

        layer_tuples = img.get_layer_data_tuples()

        # First channel "intensity" should be image
        assert layer_tuples[0][2] == 'image'
        # Second channel "mask" should be labels (keyword match)
        assert layer_tuples[1][2] == 'labels'

    def test_channel_types_override_auto_detection(self, resources_dir: Path):
        """Test that channel_types parameter overrides auto-detection."""
        import numpy as np
        import xarray as xr
        from bioio_base.dimensions import DimensionNames

        # Create nImage directly with mock data
        mock_data = xr.DataArray(
            np.zeros((2, 10, 10)),
            dims=[DimensionNames.Channel, 'Y', 'X'],
            coords={DimensionNames.Channel: ['intensity', 'mask']},
        )
        img = nImage(mock_data)

        # Override: set both channels to labels
        layer_tuples = img.get_layer_data_tuples(
            channel_types={'intensity': 'labels', 'mask': 'labels'}
        )

        # Both should be labels due to override
        assert layer_tuples[0][2] == 'labels'
        assert layer_tuples[1][2] == 'labels'

    def test_labels_do_not_get_colormap(self, resources_dir: Path):
        """Test that labels layers don't get colormap metadata."""
        import numpy as np
        import xarray as xr
        from bioio_base.dimensions import DimensionNames

        # Create nImage directly with a labels channel
        mock_data = xr.DataArray(
            np.zeros((1, 10, 10)),
            dims=[DimensionNames.Channel, 'Y', 'X'],
            coords={DimensionNames.Channel: ['segmentation']},
        )
        img = nImage(mock_data)

        layer_tuples = img.get_layer_data_tuples()

        # "segmentation" matches label keyword
        assert layer_tuples[0][2] == 'labels'
        # Labels should not have colormap
        assert 'colormap' not in layer_tuples[0][1]

    def test_layer_type_override_all_channels(self, resources_dir: Path):
        """Test that layer_type parameter overrides all channels."""
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        layer_tuples = img.get_layer_data_tuples(layer_type='labels')

        # All channels should be labels due to override
        assert len(layer_tuples) == 2
        for _, meta, layer_type in layer_tuples:
            assert layer_type == 'labels'
            # Labels should not have colormap
            assert 'colormap' not in meta

    def test_layer_type_overrides_channel_types(self, resources_dir: Path):
        """Test that layer_type takes precedence over channel_types."""
        import numpy as np
        import xarray as xr
        from bioio_base.dimensions import DimensionNames

        # Create nImage directly with mock data
        mock_data = xr.DataArray(
            np.zeros((2, 10, 10)),
            dims=[DimensionNames.Channel, 'Y', 'X'],
            coords={DimensionNames.Channel: ['intensity', 'mask']},
        )
        img = nImage(mock_data)

        # Even though channel_types says "intensity" should be image,
        # layer_type="labels" should override everything
        layer_tuples = img.get_layer_data_tuples(
            layer_type='labels',
            channel_types={'intensity': 'image', 'mask': 'image'},
        )

        # Both should be labels due to layer_type override
        assert layer_tuples[0][2] == 'labels'

    def test_channel_kwargs_override_metadata(self, resources_dir: Path):
        """Test that channel_kwargs overrides default metadata."""
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        layer_tuples = img.get_layer_data_tuples(
            channel_kwargs={
                img.channel_names[0]: {
                    'colormap': 'blue',
                    'contrast_limits': (0, 1000),
                },
                img.channel_names[1]: {
                    'opacity': 0.5,
                },
            }
        )

        assert len(layer_tuples) == 2
        # First channel should have overridden colormap and contrast_limits
        assert layer_tuples[0][1]['colormap'] == 'blue'
        assert layer_tuples[0][1]['contrast_limits'] == (0, 1000)
        # Second channel should have opacity override but default colormap
        assert layer_tuples[1][1]['opacity'] == 0.5
        assert (
            layer_tuples[1][1]['colormap'] == 'green'
        )  # default for 2-channel


class TestPreferredReaderFallback:
    """Tests for preferred reader fallback logic in nImage.__init__."""

    def test_preferred_reader_success(self, resources_dir: Path):
        """Test that preferred reader is used when it works."""
        with patch('ndevio.nimage._resolve_reader') as mock_resolve:
            # Mock returning a valid reader
            from bioio_tifffile import Reader

            mock_resolve.return_value = Reader

            img = nImage(str(resources_dir / 'cells3d2ch_legacy.tiff'))

            # Verify _resolve_reader was called
            mock_resolve.assert_called_once()
            assert img is not None
            assert img.reader.name == 'bioio_tifffile'

    def test_preferred_reader_fallback(self, resources_dir: Path):
        """Test that failed preferred reader will fallback"""
        with patch('ndevio.nimage._resolve_reader') as mock_resolve:
            # Mock returning a reader that won't work for this file
            from bioio_czi import Reader

            mock_resolve.return_value = Reader

            img = nImage(str(resources_dir / 'cells3d2ch_legacy.tiff'))

            # Verify _resolve_reader was called
            mock_resolve.assert_called_once()
            assert img is not None
            # Should have fallen back to bioio's default (ome-tiff)
            assert img.reader.name == 'bioio_ome_tiff'

    def test_no_preferred_reader_uses_default(self, resources_dir: Path):
        """Test that no preferred reader uses bioio's default priority."""
        with patch('ndevio.nimage._resolve_reader') as mock_resolve:
            mock_resolve.return_value = None  # No preferred reader

            img = nImage(str(resources_dir / 'cells3d2ch_legacy.tiff'))
            assert img is not None
            mock_resolve.assert_called_once()
            assert img.reader.name == 'bioio_ome_tiff'


class TestResolveReaderFunction:
    """Tests for _resolve_reader function."""

    def test_returns_none_when_no_preferred_reader(self):
        """Test returns None when preferred_reader is not set."""
        from ndevio.nimage import _resolve_reader

        with patch('ndev_settings.get_settings') as mock_get_settings:
            mock_get_settings.return_value.ndevio_reader.preferred_reader = (
                None
            )

            result = _resolve_reader('test.tiff', None)
            assert result is None

    def test_returns_none_when_preferred_not_installed(self):
        """Test returns None when preferred reader is not installed."""
        from ndevio.nimage import _resolve_reader

        with (
            patch('ndev_settings.get_settings') as mock_get_settings,
            patch(
                'ndevio.bioio_plugins._utils.get_installed_plugins',
                return_value={'bioio-ome-tiff', 'bioio-tifffile'},
            ),
        ):
            mock_get_settings.return_value.ndevio_reader.preferred_reader = (
                'bioio-czi'
            )

            result = _resolve_reader('test.tiff', None)
            assert result is None

    def test_returns_reader_when_preferred_installed(self):
        """Test returns reader class when preferred reader is installed."""
        from ndevio.nimage import _resolve_reader

        with (
            patch('ndev_settings.get_settings') as mock_get_settings,
            patch(
                'ndevio.bioio_plugins._utils.get_installed_plugins',
                return_value={'bioio-ome-tiff'},
            ),
            patch(
                'ndevio.bioio_plugins._utils.get_reader_by_name'
            ) as mock_get_reader,
        ):
            from bioio_ome_tiff import Reader as OmeTiffReader

            mock_get_reader.return_value = OmeTiffReader
            mock_get_settings.return_value.ndevio_reader.preferred_reader = (
                'bioio-ome-tiff'
            )

            result = _resolve_reader('test.tiff', None)
            assert result == OmeTiffReader
            mock_get_reader.assert_called_once_with('bioio-ome-tiff')

    def test_explicit_reader_bypasses_settings(self):
        """Test that explicit reader bypasses settings lookup."""
        from bioio_tifffile import Reader as TifffileReader

        from ndevio.nimage import _resolve_reader

        with patch('ndev_settings.get_settings') as mock_get_settings:
            result = _resolve_reader('test.tiff', TifffileReader)

            # Should return explicit reader without checking settings
            assert result == TifffileReader
            mock_get_settings.assert_not_called()

    def test_array_input_returns_none(self):
        """Test that array inputs don't trigger preferred reader lookup."""
        import numpy as np

        from ndevio.nimage import _resolve_reader

        with patch('ndev_settings.get_settings') as mock_get_settings:
            arr = np.zeros((10, 10), dtype=np.uint8)
            result = _resolve_reader(arr, None)

            # Should return None without checking settings for arrays
            assert result is None
            mock_get_settings.assert_not_called()


class TestNonPathImageHandling:
    """Tests for handling non-path inputs (arrays)."""

    def test_array_input_no_preferred_reader_check(self):
        """Test that arrays don't trigger preferred reader logic."""
        import numpy as np

        with patch('ndevio.nimage._resolve_reader') as mock_resolve:
            # Create a simple array
            arr = np.zeros((10, 10), dtype=np.uint8)

            # This should work
            img = nImage(arr)
            assert img is not None

            # _resolve_reader should have been called but returned None
            mock_resolve.assert_called_once()
            # First arg is the image, second is explicit_reader (None)
            call_args = mock_resolve.call_args
            assert call_args[0][1] is None  # explicit_reader is None

    def test_unsupported_array_raises_without_suggestions(self):
        """Test that unsupported arrays raise error without plugin suggestions."""
        # Create something that will fail
        with pytest.raises(UnsupportedFileFormatError) as exc_info:
            # Pass an invalid object
            nImage('this_is_not_a_valid_input.fake')

        # Error should be raised but without custom suggestions since it's not a path
        error_msg = str(exc_info.value)
        assert (
            'fake' in error_msg.lower() or 'unsupported' in error_msg.lower()
        )


class TestExplicitReaderParameter:
    """Tests for when reader is explicitly provided."""

    def test_explicit_reader_bypasses_preferred(self, resources_dir: Path):
        """Test that explicit reader parameter bypasses preferred reader."""
        from bioio_tifffile import Reader as TifffileReader

        with patch('ndevio.nimage._resolve_reader') as mock_resolve:
            mock_resolve.return_value = TifffileReader

            # Explicit reader should be used directly
            img = nImage(
                str(resources_dir / 'cells3d2ch_legacy.tiff'),
                reader=TifffileReader,
            )

            assert img is not None
            # _resolve_reader should return the explicit reader
            mock_resolve.assert_called_once()
            call_args = mock_resolve.call_args
            assert call_args[0][1] == TifffileReader  # explicit_reader

    def test_explicit_reader_fails_falls_back(self, resources_dir: Path):
        """Test explicit reader that fails falls back to default."""
        from bioio_czi import Reader as CziReader

        # Use CZI reader on a TIFF file - it should fail and fall back
        img = nImage(
            str(resources_dir / 'cells3d2ch_legacy.tiff'),
            reader=CziReader,
        )

        assert img is not None
        # Should have fallen back to bioio's default
        assert img.reader.name == 'bioio_ome_tiff'


class TestDetermineInMemory:
    """Tests for nImage memory-loading policy."""

    @staticmethod
    def _make_image(path):
        img = object.__new__(nImage)
        img.path = None if path is None else str(path)
        img._is_remote = False
        return img

    def test_none_path_returns_true(self):
        """Array-backed inputs should stay in memory."""
        assert self._make_image(None)._fits_in_memory() is True

    def test_small_file_returns_true(self, tmp_path):
        """Small files should be loaded eagerly."""
        small_file = tmp_path / 'small.txt'
        small_file.write_text('x' * 100)

        with mock.patch(
            'psutil.virtual_memory', return_value=mock.Mock(available=1e10)
        ):
            assert self._make_image(small_file)._fits_in_memory() is True

    def test_large_file_returns_false(self, tmp_path):
        """Large files should stay dask-backed."""
        large_file = tmp_path / 'large.txt'
        large_file.write_text('x')

        with (
            mock.patch(
                'psutil.virtual_memory', return_value=mock.Mock(available=1e9)
            ),
            mock.patch(
                'bioio_base.io.pathlike_to_fs',
                return_value=(mock.Mock(size=lambda x: 5e9), ''),
            ),
        ):
            assert self._make_image(large_file)._fits_in_memory() is False

    def test_uncompressed_bytes_large_overrides_small_disk_size(
        self, tmp_path
    ):
        """Compressed files should be judged by RAM footprint when known."""
        small_file = tmp_path / 'labels.tif'
        small_file.write_bytes(b'\x00' * 100)

        with mock.patch(
            'psutil.virtual_memory', return_value=mock.Mock(available=1e10)
        ):
            assert (
                self._make_image(small_file)._fits_in_memory(
                    uncompressed_bytes=int(5e9)
                )
                is False
            )
            assert (
                self._make_image(small_file)._fits_in_memory(
                    uncompressed_bytes=1000
                )
                is True
            )

    def test_missing_max_in_mem_setting_falls_back_to_default(self, tmp_path):
        """Older persisted settings may not yet contain max_in_mem_gb."""
        from types import SimpleNamespace

        small_file = tmp_path / 'small.txt'
        small_file.write_text('x' * 100)

        with (
            mock.patch(
                'ndev_settings.get_settings',
                return_value=SimpleNamespace(
                    ndevio_reader=SimpleNamespace(),
                ),
            ),
            mock.patch(
                'psutil.virtual_memory',
                return_value=mock.Mock(available=1e10),
            ),
        ):
            assert self._make_image(small_file)._fits_in_memory() is True


# =============================================================================
# Regression tests: compressed files and filename-based label detection
# =============================================================================


def test_compressed_int32_tiff_uses_dask(tmp_path: Path):
    """Regression: a compressed int32 TIFF must be loaded as dask even when
    its on-disk size is well below the in-memory threshold.

    An 18.9 MB LZW-compressed int32 file expands to ~3 GB in RAM.
    The old code compared the compressed *filesystem* size against the
    threshold; a 19 MB file would always pass and be loaded eagerly.
    The fix computes uncompressed_bytes = prod(shape) * dtype.itemsize and
    uses that instead.
    """
    import math

    import numpy as np
    import tifffile

    # All-zeros data compresses to near-nothing with LZW: small, quick write.
    # Shape gives ~288 MB uncompressed. We mock available RAM to 500 MB so
    # that 30% = 150 MB < 288 MB, which forces dask regardless of threshold.
    # Without the uncompressed_bytes fix, disk_size (~KB) would be used and
    # the tiny file would be loaded eagerly.
    shape = (200, 600, 600)

    path = tmp_path / 'big_uncompressed.tif'
    tifffile.imwrite(
        str(path), np.zeros(shape, dtype=np.int32), compression='lzw'
    )

    disk_size = path.stat().st_size
    uncompressed = math.prod(shape) * np.dtype(np.int32).itemsize
    assert disk_size < uncompressed // 100, (
        'test precondition: compressed file must be tiny vs uncompressed'
    )

    import dask.array as da

    # Mock RAM so the memory-fraction check forces dask (288 MB > 30% of 500 MB).
    # This isolates the test from machine memory and makes it deterministic.
    with mock.patch(
        'psutil.virtual_memory', return_value=mock.Mock(available=int(500e6))
    ):
        img = nImage(path)

        assert isinstance(img.reference_xarray.data, da.Array), (
            f'Expected dask array, got {type(img.reference_xarray.data)}'
        )

        tuples = img.get_layer_data_tuples()
        assert len(tuples) == 1
        data_out, _, _ = tuples[0]
        assert isinstance(data_out, list)
        assert isinstance(data_out[0], da.Array), (
            f'Expected dask array in layer tuple, got {type(data_out[0])}'
        )


def test_labels_detected_from_filename(tmp_path: Path):
    """Regression: a TIFF file whose channel name is a generic '0' but whose
    filename contains a label keyword (e.g. 'cells_mask.tif') should be
    returned as a 'labels' layer, not 'image'.

    Previously only the channel name was checked; now the filename stem is
    used as a fallback when the channel name provides no signal.
    """
    import numpy as np
    import tifffile

    # Single-channel int32 TIFF — channel name will be '0' (no label keyword)
    data = np.random.randint(0, 10, (10, 10), dtype=np.int32)
    path = tmp_path / 'cells_mask.tif'
    tifffile.imwrite(str(path), data)

    img = nImage(path)
    # Verify the channel name is generic (no label keyword)
    channel_name = img.channel_names[0]
    from ndevio.utils._layer_utils import CHANNEL_LABEL_KEYWORDS

    assert not any(
        kw in channel_name.lower() for kw in CHANNEL_LABEL_KEYWORDS
    ), f'Channel name {channel_name!r} unexpectedly contains a label keyword'

    tuples = img.get_layer_data_tuples()
    assert len(tuples) == 1
    _, _, layer_type = tuples[0]
    assert layer_type == 'labels', (
        f"Expected 'labels' from filename 'cells_mask.tif', got {layer_type!r}"
    )


def test_non_label_filename_stays_image(tmp_path: Path):
    """Counter-test: a TIFF named 'raw_image.tif' with generic channel name
    should remain an 'image' layer, not be promoted to 'labels'.
    """
    import numpy as np
    import tifffile

    data = np.zeros((10, 10), dtype=np.uint16)
    path = tmp_path / 'raw_image.tif'
    tifffile.imwrite(str(path), data)

    img = nImage(path)
    tuples = img.get_layer_data_tuples()
    assert len(tuples) == 1
    _, _, layer_type = tuples[0]
    assert layer_type == 'image'


def test_dask_chunks_are_per_plane(tmp_path: Path):
    """Verify that dask-loaded TIFFs have per-Z-plane chunks (not the whole volume).

    bioio-base's DEFAULT_CHUNK_DIMS = ["Z","Y","X"] creates one dask task per
    (T,C) pair — every Z-slice decompresses the full ZYX volume.  nImage
    overrides this with chunk_dims=["Y","X"] so each task is a single page.

    For a (Z=8, Y=64, X=64) file the resulting dask array should have chunks
    (1, 64, 64), not (8, 64, 64).
    """
    import dask.array as da
    import numpy as np
    import tifffile

    # 100 planes × 64 × 64 × uint16 = 800 KB uncompressed.
    # With 1 MB available, 30 % = 300 KB < 800 KB → forced to dask.
    shape = (100, 64, 64)  # Z, Y, X
    path = tmp_path / 'zyx_chunk_test.tiff'
    tifffile.imwrite(str(path), np.zeros(shape, dtype=np.uint16))

    # Force dask: mock available RAM so the memory-fraction check triggers.
    with mock.patch(
        'psutil.virtual_memory', return_value=mock.Mock(available=int(1e6))
    ):
        img = nImage(path)
        tuples = img.get_layer_data_tuples()

    data_out, _, _ = tuples[0]
    # layer_data is always a list (multiscale-compatible); [0] is level 0.
    arr = data_out[0]
    assert isinstance(arr, da.Array), f'Expected dask array, got {type(arr)}'

    z_chunk, y_chunk, x_chunk = arr.chunksize
    assert z_chunk == 1, (
        f'Expected Z-chunk=1 (per-plane), got {z_chunk}. '
        'chunk_dims override to ["Y","X"] may not be working.'
    )
    assert y_chunk == 64
    assert x_chunk == 64

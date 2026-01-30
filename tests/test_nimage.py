"""Tests for ndevio.nImage class."""

from __future__ import annotations

from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

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


def test_nImage_init(resources_dir: Path):
    """Test nImage initialization with a file that should work."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    assert img.path == resources_dir / CELLS3D2CH_OME_TIFF
    assert img.reader is not None
    # Shape is (T, C, Z, Y, X) = (1, 2, 60, 66, 85)
    assert img.data.shape == (1, 2, 60, 66, 85)
    # napari_layer_data should not be loaded until accessed
    assert img._napari_layer_data is None
    # Accessing the property triggers lazy loading
    assert img.napari_layer_data is not None


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


def test_determine_in_memory(resources_dir: Path):
    """Test in-memory determination for small files."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    assert img._determine_in_memory() is True


def test_nImage_determine_in_memory_large_file(resources_dir: Path):
    """Test in-memory determination for large files."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    with (
        mock.patch(
            'psutil.virtual_memory', return_value=mock.Mock(available=1e9)
        ),
        mock.patch(
            'bioio_base.io.pathlike_to_fs',
            return_value=(mock.Mock(size=lambda x: 5e9), ''),
        ),
    ):
        assert img._determine_in_memory() is False


def test_get_layer_data(resources_dir: Path):
    """Test loading napari layer data in memory."""
    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    img._load_napari_layer_data()
    # napari_layer_data will be squeezed
    # Original shape (1, 2, 60, 66, 85) -> (2, 60, 66, 85)
    assert img.napari_layer_data.shape == (2, 60, 66, 85)
    assert img.napari_layer_data.dims == ('C', 'Z', 'Y', 'X')


def test_get_layer_data_not_in_memory(resources_dir: Path):
    """Test loading napari layer data as dask array."""
    import dask

    img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
    img._load_napari_layer_data(in_memory=False)
    assert img.napari_layer_data is not None
    # check that the data is a dask array
    assert isinstance(img.napari_layer_data.data, dask.array.core.Array)


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


def test_get_layer_data_mosaic_tile_in_memory(resources_dir: Path):
    """Test mosaic tile image data in memory."""
    import xarray as xr
    from bioio_base.dimensions import DimensionNames

    with mock.patch.object(nImage, 'reader', create=True) as mock_reader:
        mock_reader.dims.order = [DimensionNames.MosaicTile]
        mock_reader.mosaic_xarray_data.squeeze.return_value = xr.DataArray(
            [1, 2, 3]
        )
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        img._load_napari_layer_data(in_memory=True)
        assert img.napari_layer_data is not None
        assert img.napari_layer_data.shape == (3,)


def test_get_layer_data_mosaic_tile_not_in_memory(
    resources_dir: Path,
):
    """Test mosaic tile image data as dask array."""
    import xarray as xr
    from bioio_base.dimensions import DimensionNames

    with mock.patch.object(nImage, 'reader', create=True) as mock_reader:
        mock_reader.dims.order = [DimensionNames.MosaicTile]
        mock_reader.mosaic_xarray_dask_data.squeeze.return_value = (
            xr.DataArray([1, 2, 3])
        )
        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)
        img._load_napari_layer_data(in_memory=False)
        assert img.napari_layer_data is not None
        assert img.napari_layer_data.shape == (3,)


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

            # Data shape should NOT include channel dimension
            assert data.shape == (60, 66, 85)  # ZYX only

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

    def test_in_memory_parameter_respected(self, resources_dir: Path):
        """Test that in_memory parameter is passed through correctly."""

        img = nImage(resources_dir / CELLS3D2CH_OME_TIFF)

        # Test with in_memory=True (numpy array)
        layer_tuples = img.get_layer_data_tuples(in_memory=True)

        import numpy as np

        for data, _, _ in layer_tuples:
            # Data should be numpy array when in_memory=True
            assert isinstance(data, np.ndarray)

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

        from ndevio._colormap_utils import MULTI_CHANNEL_CYCLE

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
        with patch(
            'ndevio.nimage.nImage._get_preferred_reader_list'
        ) as mock_get:
            # Mock returning a valid reader
            from bioio_tifffile import Reader

            mock_get.return_value = [Reader]

            img = nImage(str(resources_dir / 'cells3d2ch_legacy.tiff'))

            # Verify preferred reader was attempted
            mock_get.assert_called_once()
            assert img is not None
            assert img.reader.name == 'bioio_tifffile'

    def test_preferred_reader_fallback(self, resources_dir: Path):
        """Test that failed preferred reader will fallback"""
        with patch(
            'ndevio.nimage.nImage._get_preferred_reader_list'
        ) as mock_get:
            # Mock returning a valid reader
            from bioio_czi import Reader

            mock_get.return_value = [Reader]

            img = nImage(str(resources_dir / 'cells3d2ch_legacy.tiff'))

            # Verify preferred reader was attempted
            mock_get.assert_called_once()
            assert img is not None
            assert img.reader.name == 'bioio_ome_tiff'

    def test_no_preferred_reader_uses_default(self, resources_dir: Path):
        """Test that no preferred reader uses bioio's default priority."""
        with patch(
            'ndevio.nimage.nImage._get_preferred_reader_list'
        ) as mock_get:
            mock_get.return_value = None  # No preferred reader

            img = nImage(str(resources_dir / 'cells3d2ch_legacy.tiff'))
            assert img is not None
            mock_get.assert_called_once()
            assert img.reader.name == 'bioio_ome_tiff'


class TestGetPreferredReaderList:
    """Tests for _get_preferred_reader_list method."""

    def test_returns_none_when_no_preferred_reader(self, resources_dir: Path):
        """Test returns None when preferred_reader is not set."""
        with patch('ndev_settings.get_settings') as mock_settings:
            mock_settings.return_value.ndevio_reader.preferred_reader = None

            img = nImage.__new__(nImage)
            img.settings = mock_settings.return_value

            result = img._get_preferred_reader_list()
            assert result is None

    def test_returns_none_when_preferred_not_installed(
        self, resources_dir: Path
    ):
        """Test returns None when preferred reader is not installed."""
        with (
            patch('ndev_settings.get_settings') as mock_settings,
            patch(
                'ndevio._bioio_plugin_utils.get_installed_plugins',
                return_value={'bioio-ome-tiff', 'bioio-tifffile'},
            ),
        ):
            mock_settings.return_value.ndevio_reader.preferred_reader = (
                'bioio-czi'
            )

            img = nImage.__new__(nImage)
            img.settings = mock_settings.return_value

            result = img._get_preferred_reader_list()
            assert result is None

    def test_returns_reader_when_preferred_installed(
        self, resources_dir: Path
    ):
        """Test returns reader class when preferred reader is installed."""
        with (
            patch('ndev_settings.get_settings') as mock_settings,
            patch(
                'ndevio._bioio_plugin_utils.get_installed_plugins',
                return_value={'bioio-ome-tiff'},
            ),
            patch(
                'ndevio._bioio_plugin_utils.get_reader_by_name'
            ) as mock_get_reader,
        ):
            from bioio_ome_tiff import Reader as OmeTiffReader

            mock_get_reader.return_value = OmeTiffReader
            mock_settings.return_value.ndevio_reader.preferred_reader = (
                'bioio-ome-tiff'
            )

            img = nImage.__new__(nImage)
            img.settings = mock_settings.return_value

            result = img._get_preferred_reader_list()
            assert result == [OmeTiffReader]
            mock_get_reader.assert_called_once_with('bioio-ome-tiff')


class TestRaiseWithSuggestions:
    """Tests for _raise_with_suggestions method."""

    def test_raises_with_suggestions_enabled(self):
        """Test error message includes suggestions when enabled."""
        with patch('ndev_settings.get_settings') as mock_settings:
            mock_settings.return_value.ndevio_reader.suggest_reader_plugins = (
                True
            )

            img = nImage.__new__(nImage)
            img.settings = mock_settings.return_value

            with pytest.raises(UnsupportedFileFormatError) as exc_info:
                img._raise_with_suggestions('test.czi')

            error_msg = str(exc_info.value)
            assert 'bioio-czi' in error_msg

    def test_raises_without_suggestions_when_disabled(self):
        """Test error message has no suggestions when disabled."""
        with patch('ndev_settings.get_settings') as mock_settings:
            mock_settings.return_value.ndevio_reader.suggest_reader_plugins = (
                False
            )

            img = nImage.__new__(nImage)
            img.settings = mock_settings.return_value

            with pytest.raises(UnsupportedFileFormatError) as exc_info:
                img._raise_with_suggestions('test.czi')

            error_msg = str(exc_info.value)
            # Should still mention the file but not include installation message
            assert 'test.czi' in error_msg


class TestNonPathImageHandling:
    """Tests for handling non-path inputs (arrays)."""

    def test_array_input_no_preferred_reader_check(self):
        """Test that arrays don't trigger preferred reader logic."""
        import numpy as np

        with patch(
            'ndevio.nimage.nImage._get_preferred_reader_list'
        ) as mock_get:
            # Create a simple array
            arr = np.zeros((10, 10), dtype=np.uint8)

            # This should work without calling _get_preferred_reader_list
            img = nImage(arr)
            assert img is not None
            # Should not call _get_preferred_reader_list for arrays
            mock_get.assert_not_called()

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

        with patch(
            'ndevio.nimage.nImage._get_preferred_reader_list'
        ) as mock_get:
            # Explicit reader should bypass preferred
            img = nImage(
                str(resources_dir / 'cells3d2ch_legacy.tiff'),
                reader=TifffileReader,
            )

            assert img is not None
            # Should not check for preferred reader when explicit reader provided
            mock_get.assert_not_called()

    def test_explicit_reader_fails_falls_back(self, resources_dir: Path):
        """Test explicit reader that fails falls back to default."""
        mock_reader = MagicMock()
        mock_reader.side_effect = UnsupportedFileFormatError(
            reader_name='mock', path='test'
        )

        with patch(
            'ndevio.nimage.nImage._get_preferred_reader_list'
        ) as mock_get:
            # Even with explicit reader that fails, should fall back
            img = nImage(
                str(resources_dir / 'cells3d2ch_legacy.tiff'),
                reader=mock_reader,
            )

            assert img is not None
            # Should not check preferred when explicit reader provided
            mock_get.assert_not_called()

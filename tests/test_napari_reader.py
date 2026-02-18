from __future__ import annotations

from pathlib import Path

# import npe2
import pytest

from ndevio._napari_reader import napari_get_reader

###############################################################################

RGB_TIFF = 'RGB_bad_metadata.tiff'  # has two scenes
MULTISCENE_CZI = r'0T-4C-0Z-7pos.czi'
PNG_FILE = 'nDev-logo-small.png'
ND2_FILE = 'ND2_dims_rgb.nd2'
OME_TIFF = 'cells3d2ch_legacy.tiff'
REMOTE_ZARR = 'https://uk1s3.embassy.ebi.ac.uk/ebi-ngff-challenge-2024/4ffaeed2-fa70-4907-820f-8a96ef683095.zarr'  # from https://github.com/bioio-devs/bioio-ome-zarr/blob/main/bioio_ome_zarr/tests/test_remote_read_zarrV3.py

###############################################################################


def test_napari_viewer_open(resources_dir: Path, make_napari_viewer) -> None:
    """
    Test that the napari viewer can open a file with the ndevio plugin.

    In zarr>=3.0, the FSStore was removed and replaced with DirectoryStore.
    This test checks that the napari viewer can open any file because BioImage
    (nImage) would try to import the wrong FSStore from zarr. Now, the FSStore
    is shimmed to DirectoryStore with a compatibility patch in nImage.
    """
    viewer = make_napari_viewer()
    viewer.open(str(resources_dir / OME_TIFF), plugin='ndevio')

    # Now channels are split into separate layers, so we should have 2 layers
    assert len(viewer.layers) == 2
    # Each layer is a single channel with shape (60, 66, 85)
    assert viewer.layers[0].data.shape == (60, 66, 85)


def test_napari_viewer_open_directory(
    resources_dir: Path, make_napari_viewer
) -> None:
    viewer = make_napari_viewer()
    viewer.open(
        str(resources_dir / 'dimension_handling_zyx_V3.zarr/'), plugin='ndevio'
    )

    assert len(viewer.layers) == 1
    assert viewer.layers[0].data.shape == (2, 4, 4)


def test_napari_viewer_open_remote(make_napari_viewer) -> None:
    viewer = make_napari_viewer()
    viewer.open(REMOTE_ZARR, plugin='ndevio')

    assert len(viewer.layers) == 2
    assert viewer.layers[0].data.shape == (512, 512)


@pytest.mark.parametrize(
    (
        'filename',
        'expected_shape',
        'expected_has_scale',
        'expected_num_layers',
    ),
    [
        # PNG shape is (106, 243, 4) - actual dimensions of nDev-logo-small.png
        # PNG files from bioio-imageio don't include scale metadata
        (PNG_FILE, (106, 243, 4), False, 1),
        # OME-TIFF has 2 channels that are now split into separate layers
        # Each layer shape is (60, 66, 85) - ZYX
        (OME_TIFF, (60, 66, 85), True, 2),
    ],
)
def test_reader_supported_formats(
    resources_dir: Path,
    filename: str,
    expected_shape: tuple[int, ...],
    expected_has_scale: bool,
    expected_num_layers: int,
) -> None:
    """Test reader with formats that should work with core dependencies."""

    # Resolve filename to filepath
    if isinstance(filename, str):
        path = str(resources_dir / filename)

    # Get reader
    partial_napari_reader_function = napari_get_reader(
        path, open_first_scene_only=True
    )
    # Check callable
    assert callable(partial_napari_reader_function)

    # Get data
    layer_data = partial_napari_reader_function(path)

    # We should return expected number of layers
    assert layer_data is not None
    assert len(layer_data) == expected_num_layers

    data, meta, _ = layer_data[0]

    # Check layer data shape
    assert data.shape == expected_shape

    # Check meta has expected keys
    assert 'name' in meta
    if expected_has_scale:
        assert 'scale' in meta


@pytest.mark.parametrize(
    ('filename', 'expected_shape', 'should_work'),
    [
        # RGB_TIFF should work now that bioio-tifffile is a core dependency
        (RGB_TIFF, (1440, 1920, 3), True),
        # MULTISCENE_CZI still requires bioio-czi which is optional
        pytest.param(
            MULTISCENE_CZI,
            (32, 32),
            False,
        ),
    ],
)
def test_for_multiscene_widget(
    make_napari_viewer,
    resources_dir: Path,
    filename: str,
    expected_shape: tuple[int, ...],
    should_work: bool,
) -> None:
    """Test multiscene widget functionality.

    Note: This test is currently skipped for files that require optional plugins.
    """
    # Make a viewer
    viewer = make_napari_viewer()
    assert len(viewer.layers) == 0
    assert len(viewer.window._dock_widgets) == 0

    # Resolve filename to filepath
    if isinstance(filename, str):
        path = str(resources_dir / filename)

    # Get reader
    reader = napari_get_reader(path)

    if reader is not None:
        # Call reader on path
        reader(path)

        if len(viewer.window._dock_widgets) != 0:
            # Get the second scene
            scene_widget = (
                viewer.window._dock_widgets[f'{Path(filename).stem} :: Scenes']
                .widget()
                ._magic_widget
            )
            assert scene_widget is not None
            assert scene_widget.viewer == viewer

            scenes = scene_widget._scene_list_widget.choices

            # Set to the first scene (0th choice is none)
            scene_widget._scene_list_widget.value = scenes[1]

            data = viewer.layers[0].data

            assert data.shape == expected_shape
        else:
            data, _, _ = reader(path)[0]
            assert data.shape == expected_shape


def test_napari_get_reader_supported_formats_work(resources_dir: Path):
    """Test that supported formats return valid readers."""
    # PNG should work (bioio-imageio is core)
    reader_png = napari_get_reader(str(resources_dir / PNG_FILE))
    assert callable(reader_png)

    # OME-TIFF should work (bioio-ome-tiff is core)
    reader_tiff = napari_get_reader(str(resources_dir / OME_TIFF))
    assert callable(reader_tiff)

    # Can actually read the files
    layer_data_png = reader_png(str(resources_dir / PNG_FILE))
    assert layer_data_png is not None
    assert len(layer_data_png) > 0

    layer_data_tiff = reader_tiff(str(resources_dir / OME_TIFF))
    assert layer_data_tiff is not None
    assert len(layer_data_tiff) > 0


@pytest.mark.parametrize(
    ('filename', 'expected_plugin_in_error'),
    [
        (ND2_FILE, 'bioio-nd2'),  # ND2 needs bioio-nd2
    ],
)
def test_napari_reader_missing_plugin_error(
    resources_dir: Path, filename: str, expected_plugin_in_error: str
):
    """Test that reading a file without the required plugin raises helpful error.

    When extension is recognized but required plugin isn't installed,
    nImage raises UnsupportedFileFormatError with installation suggestions.
    """
    from bioio_base.exceptions import UnsupportedFileFormatError

    # napari_get_reader returns a reader function since extension is known
    reader = napari_get_reader(str(resources_dir / filename))
    assert callable(reader)

    # But actually reading fails with helpful error message
    with pytest.raises(UnsupportedFileFormatError) as exc_info:
        reader(str(resources_dir / filename))

    error_msg = str(exc_info.value)
    assert expected_plugin_in_error in error_msg
    assert 'pip install' in error_msg or 'conda install' in error_msg

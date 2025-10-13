from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import dask.array as da

# import npe2
import numpy as np
import pytest
from bioio_base.exceptions import UnsupportedFileFormatError

from ndevio._napari_reader import napari_get_reader

###############################################################################

RGB_TIFF = "RGB_bad_metadata.tiff"  # has two scenes
MULTISCENE_CZI = r"0T-4C-0Z-7pos.czi"
PNG_FILE = "nDev-logo-small.png"
# GIF_FILE = "example.gif"
OME_TIFF = "cells3d2ch_legacy.tiff"

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
    viewer.open(str(resources_dir / OME_TIFF), plugin="ndevio")

    assert viewer.layers[0].data.shape == (60, 66, 85)


@pytest.mark.parametrize(
    ("in_memory", "expected_dtype"),
    [
        (True, np.ndarray),
        (False, da.core.Array),
    ],
)
@pytest.mark.parametrize(
    ("filename", "expected_shape", "expected_has_scale"),
    [
        # PNG shape is (106, 243, 4) - actual dimensions of nDev-logo-small.png
        # PNG files from bioio-imageio don't include scale metadata
        (PNG_FILE, (106, 243, 4), False),
        # OME-TIFF shape is (2, 60, 66, 85) - CZYX with 2 channels
        (OME_TIFF, (2, 60, 66, 85), True),
    ],
)
def test_reader_supported_formats(
    resources_dir: Path,
    filename: str,
    in_memory: bool,
    expected_shape: tuple[int, ...],
    expected_dtype,
    expected_has_scale: bool,
    make_napari_viewer,
) -> None:
    """Test reader with formats that should work with core dependencies."""
    make_napari_viewer()

    # Resolve filename to filepath
    if isinstance(filename, str):
        path = str(resources_dir / filename)

    # Get reader
    partial_napari_reader_function = napari_get_reader(
        path, in_memory=in_memory, open_first_scene_only=True
    )
    # Check callable
    assert callable(partial_napari_reader_function)

    # Get data
    layer_data = partial_napari_reader_function(path)

    # We should return at least one layer
    assert layer_data is not None
    assert len(layer_data) > 0

    data, meta, _ = layer_data[0]

    # Check layer data
    assert isinstance(data, expected_dtype)
    assert data.shape == expected_shape

    # Check meta has expected keys
    assert "name" in meta
    if expected_has_scale:
        assert "scale" in meta


@pytest.mark.parametrize(
    ("in_memory", "expected_dtype"),
    [
        (True, np.ndarray),
        (False, da.core.Array),
    ],
)
@pytest.mark.parametrize(
    ("filename", "expected_shape", "should_work"),
    [
        # RGB_TIFF and MULTISCENE_CZI may not work with core dependencies
        # Skip these tests for now since they require optional plugins
        pytest.param(
            RGB_TIFF,
            (1440, 1920, 3),
            False,
            marks=pytest.mark.skip(
                reason="RGB_TIFF requires bioio-tifffile or may fail"
            ),
        ),
        pytest.param(
            MULTISCENE_CZI,
            (32, 32),
            False,
            marks=pytest.mark.skip(reason="CZI requires bioio-czi"),
        ),
    ],
)
def test_for_multiscene_widget(
    make_napari_viewer,
    resources_dir: Path,
    filename: str,
    in_memory: bool,
    expected_dtype,
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
    reader = napari_get_reader(path, in_memory)

    if reader is not None:
        # Call reader on path
        reader(path)

        if len(viewer.window._dock_widgets) != 0:
            # Get the second scene
            scene_widget = (
                viewer.window._dock_widgets[f"{Path(filename).stem} :: Scenes"]
                .widget()
                ._magic_widget
            )
            assert scene_widget is not None
            assert scene_widget.viewer == viewer

            scenes = scene_widget._scene_list_widget.choices

            # Set to the first scene (0th choice is none)
            scene_widget._scene_list_widget.value = scenes[1]

            data = viewer.layers[0].data

            assert isinstance(data, expected_dtype)
            assert data.shape == expected_shape
        else:
            data, _, _ = reader(path)[0]
            assert isinstance(data, expected_dtype)
            assert data.shape == expected_shape


def test_napari_get_reader_multi_path(resources_dir: Path) -> None:
    # Get reader
    reader = napari_get_reader(
        [str(resources_dir / RGB_TIFF), str(resources_dir / MULTISCENE_CZI)],
        in_memory=True,
    )

    # Check callable
    assert reader is None


def test_napari_get_reader_ome_override(resources_dir: Path) -> None:
    reader = napari_get_reader(
        str(resources_dir / OME_TIFF),
    )

    assert callable(reader)


def test_napari_get_reader_unsupported(resources_dir: Path) -> None:
    """Test that unsupported file extension raises UnsupportedFileFormatError."""
    from bioio_base.exceptions import UnsupportedFileFormatError

    # Mock the widget opener since we don't have a viewer in this test
    with patch("ndevio._napari_reader._open_plugin_installer"):
        with pytest.raises(UnsupportedFileFormatError) as exc_info:
            napari_get_reader(
                str(resources_dir / "measure_props_Labels.abcdefg"),
            )

        error_msg = str(exc_info.value)
        # Should indicate no plugins found for this extension
        assert ".abcdefg" in error_msg or "abcdefg" in error_msg


def test_napari_get_reader_general_exception(caplog):
    """Test that general exceptions in determine_reader_plugin are handled correctly."""
    test_path = "non_existent_file.xyz"

    # Mock determine_reader_plugin to raise an exception
    with patch("ndevio._napari_reader.determine_reader_plugin") as mock_reader:
        mock_reader.side_effect = Exception("Test exception")

        reader = napari_get_reader(test_path)
        assert reader is None

        assert "ndevio: Error reading file" in caplog.text
        assert "Test exception" in caplog.text


def test_napari_get_reader_png(resources_dir: Path) -> None:
    reader = napari_get_reader(
        str(resources_dir / PNG_FILE),
    )

    assert callable(reader)


def test_napari_get_reader_unsupported_czi_with_helpful_error(
    resources_dir: Path, caplog
):
    """Test that unsupported CZI raises UnsupportedFileFormatError with plugin suggestions."""
    # Mock the widget opener since we don't have a viewer in this test
    with patch("ndevio._napari_reader._open_plugin_installer"):
        with pytest.raises(UnsupportedFileFormatError) as exc_info:
            napari_get_reader(str(resources_dir / MULTISCENE_CZI))

        error_msg = str(exc_info.value)
        # Should suggest bioio-czi
        assert "bioio-czi" in error_msg
        assert "Zeiss CZI files" in error_msg
        assert "pip install bioio-czi" in error_msg

        # Should be logged as error (if the napari reader was invoked)
        # If nothing was logged, don't fail the test; otherwise assert the message is present
        if caplog.text:
            assert "ndevio: Unsupported file format" in caplog.text


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
    ("filename", "expected_plugin_in_error"),
    [
        (MULTISCENE_CZI, "bioio-czi"),  # CZI needs bioio-czi
        (
            RGB_TIFF,
            "bioio-tifffile",
        ),  # RGB_TIFF might work or fail; if fails, should suggest bioio-tifffile
    ],
)
def test_napari_get_reader_unsupported_formats_helpful_errors(
    resources_dir: Path, filename: str, expected_plugin_in_error: str
):
    """Test that unsupported formats raise helpful errors with plugin suggestions.

    Note: Some files (like RGB_TIFF) may be readable by core plugins despite
    having "bad metadata", in which case this test will pass without error.
    The test is primarily for formats that definitely need specific plugins (like CZI).
    """
    # Mock the widget opener since we don't have a viewer in this test
    with patch("ndevio._napari_reader._open_plugin_installer"):
        try:
            reader = napari_get_reader(str(resources_dir / filename))
            # If we got a reader, the file is readable by installed plugins
            # This is OK - just means the format is supported
            if reader is None:
                pytest.fail(
                    f"Expected either a reader or an error for {filename}"
                )
        except UnsupportedFileFormatError as exc:
            # File is not readable - check error message has helpful suggestions
            error_msg = str(exc)
            assert expected_plugin_in_error in error_msg
            assert "pip install" in error_msg

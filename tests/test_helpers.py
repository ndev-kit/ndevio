"""Tests for ndevio.helpers module."""

import numpy as np
import pytest
from bioio.writers import OmeTiffWriter

from ndevio import nImage
from ndevio.helpers import (
    check_for_missing_files,
    create_id_string,
    elide_string,
    get_channel_names,
    get_directory_and_files,
    get_squeezed_dim_order,
)


class TestCheckForMissingFiles:
    """Tests for check_for_missing_files function."""

    def test_no_missing_files_path(self, tmp_path):
        """Test when all files exist using Path objects."""
        directory = tmp_path / "test_dir"
        directory.mkdir()
        file1 = directory / "file1.txt"
        file1.write_text("Test file 1")
        file2 = directory / "file2.txt"
        file2.write_text("Test file 2")

        missing = check_for_missing_files([file1, file2], directory)
        assert missing == []

    def test_missing_file_path(self, tmp_path):
        """Test detecting missing files using Path objects."""
        directory = tmp_path / "test_dir"
        directory.mkdir()
        file1 = directory / "file1.txt"
        file1.write_text("Test file 1")
        file3 = directory / "file3.txt"  # Does not exist

        missing = check_for_missing_files([file1, file3], directory)
        assert missing == [("file3.txt", "test_dir")]

    def test_missing_file_str(self, tmp_path):
        """Test with string file names."""
        directory = tmp_path / "test_dir"
        directory.mkdir()
        file1 = directory / "file1.txt"
        file1.write_text("Test file 1")

        missing = check_for_missing_files(
            ["file1.txt", "file3.txt"], directory
        )
        assert missing == [("file3.txt", "test_dir")]


class TestCreateIdString:
    """Tests for create_id_string function."""

    def test_basic_id_string(self):
        """Test basic ID string creation from numpy array."""
        img = nImage(np.random.random((2, 2)))
        id_string = create_id_string(img, "test_id")
        assert id_string == "test_id__0__Image:0"

    def test_none_identifier(self):
        """Test with None identifier."""
        img = nImage(np.random.random((2, 2)))
        id_string = create_id_string(img, None)
        assert id_string == "None__0__Image:0"

    def test_with_ome_metadata_name(self, tmp_path):
        """Test that OmeTiffWriter image_name is used in ID string."""
        OmeTiffWriter.save(
            data=np.random.random((2, 2)),
            uri=tmp_path / "test.tiff",
            image_name="test_image",
        )

        img = nImage(tmp_path / "test.tiff")
        id_string = create_id_string(img, "test_id")

        assert img.current_scene == "Image:0"
        assert id_string == "test_id__0__test_image"


class TestGetChannelNames:
    """Tests for get_channel_names function."""

    def test_multichannel_image(self, resources_dir):
        """Test getting channel names from multichannel image."""
        # Use the legacy tiff which has channel names
        file = resources_dir / "cells3d2ch_legacy.tiff"
        if file.exists():
            img = nImage(file)
            names = get_channel_names(img)
            assert isinstance(names, list)
            assert all(isinstance(n, str) for n in names)

    def test_rgb_image(self, resources_dir):
        """Test that RGB images return red, green, blue."""
        file = resources_dir / "RGB_bad_metadata.tiff"
        if file.exists():
            img = nImage(file)
            if "S" in img.dims.order:
                names = get_channel_names(img)
                assert names == ["red", "green", "blue"]


class TestGetDirectoryAndFiles:
    """Tests for get_directory_and_files function."""

    def test_default_pattern(self, tmp_path):
        """Test with default pattern finding image files."""
        # Create test files
        (tmp_path / "image1.tif").write_bytes(b"fake")
        (tmp_path / "image2.tiff").write_bytes(b"fake")
        (tmp_path / "data.csv").write_text("a,b,c")

        directory, files = get_directory_and_files(tmp_path)
        assert directory == tmp_path
        # Should find tif/tiff but not csv
        file_names = [f.name for f in files]
        assert "image1.tif" in file_names
        assert "image2.tiff" in file_names
        assert "data.csv" not in file_names

    def test_custom_pattern(self, tmp_path):
        """Test with custom file pattern."""
        (tmp_path / "data1.csv").write_text("a,b")
        (tmp_path / "data2.csv").write_text("c,d")
        (tmp_path / "image.tif").write_bytes(b"fake")

        directory, files = get_directory_and_files(tmp_path, pattern="csv")
        assert directory == tmp_path
        assert len(files) == 2
        assert all(f.suffix == ".csv" for f in files)

    def test_none_directory(self):
        """Test with None directory returns empty results."""
        directory, files = get_directory_and_files(None)
        assert directory is None
        assert files == []

    def test_nonexistent_directory(self, tmp_path):
        """Test that nonexistent directory raises FileNotFoundError."""
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(FileNotFoundError):
            get_directory_and_files(nonexistent)


class TestGetSqueezedDimOrder:
    """Tests for get_squeezed_dim_order function."""

    def test_3d_image(self):
        """Test squeezed dims for 3D image."""
        # Create a TCZYX image with Z > 1
        data = np.random.random((1, 2, 5, 10, 10))  # T=1, C=2, Z=5, Y=10, X=10
        img = nImage(data)
        dims = get_squeezed_dim_order(img)
        # Should return ZYX (C is skipped by default, T=1 is squeezed)
        assert "Z" in dims
        assert "Y" in dims
        assert "X" in dims
        assert "C" not in dims
        assert "T" not in dims

    def test_2d_image(self):
        """Test squeezed dims for 2D image."""
        data = np.random.random((10, 10))
        img = nImage(data)
        dims = get_squeezed_dim_order(img)
        assert "Y" in dims
        assert "X" in dims


class TestElideString:
    """Tests for elide_string function."""

    def test_short_string_unchanged(self):
        """Test that short strings are not modified."""
        assert elide_string("short", 10) == "short"
        assert elide_string("short", 6) == "short"

    def test_exact_length_unchanged(self):
        """Test that strings at max length are not modified."""
        assert elide_string("exactly15chars", 15) == "exactly15chars"

    def test_middle_elision(self):
        """Test middle elision (default)."""
        assert elide_string("thisisaverylongstring", 10) == "thi...ing"
        assert elide_string("thisisaverylongstring", 15) == "thisis...string"

    def test_start_elision(self):
        """Test start elision."""
        assert (
            elide_string("thisisaverylongstring", 10, "start") == "...gstring"
        )

    def test_end_elision(self):
        """Test end elision."""
        assert elide_string("thisisaverylongstring", 10, "end") == "thisisa..."

    def test_very_small_max_length(self):
        """Test with max_length <= 5 truncates without ellipsis."""
        assert elide_string("thisisaverylongstring", 3) == "thi"
        assert elide_string("thisisaverylongstring", 5) == "thisi"

    def test_invalid_location(self):
        """Test that invalid location raises ValueError."""
        with pytest.raises(
            ValueError,
            match='Invalid location. Must be "start", "middle", or "end".',
        ):
            elide_string("thisisaverylongstring", 10, "invalid")

    def test_edge_cases(self):
        """Test edge cases."""
        assert elide_string("", 10) == ""
        assert elide_string("a", 1) == "a"
        assert elide_string("ab", 1) == "a"

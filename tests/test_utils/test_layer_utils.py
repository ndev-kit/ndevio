"""Tests for _layer_utils module."""

from __future__ import annotations

from unittest import mock


class TestInferLayerType:
    """Tests for infer_layer_type function."""

    def test_label_keyword_returns_labels(self):
        """Test that label keywords are detected."""
        from ndevio.utils._layer_utils import infer_layer_type

        assert infer_layer_type('nuclei_mask') == 'labels'
        assert infer_layer_type('cell_labels') == 'labels'
        assert infer_layer_type('segmentation') == 'labels'
        assert infer_layer_type('SEG_channel') == 'labels'
        assert infer_layer_type('roi_data') == 'labels'

    def test_non_label_returns_image(self):
        """Test that non-label names return image."""
        from ndevio.utils._layer_utils import infer_layer_type

        assert infer_layer_type('DAPI') == 'image'
        assert infer_layer_type('GFP') == 'image'
        assert infer_layer_type('membrane') == 'image'

    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        from ndevio.utils._layer_utils import infer_layer_type

        assert infer_layer_type('MASK') == 'labels'
        assert infer_layer_type('Label') == 'labels'
        assert infer_layer_type('SEGMENTATION') == 'labels'


class TestResolveLayerType:
    """Tests for resolve_layer_type function."""

    def test_global_override_takes_precedence(self):
        """Test that global override is used first."""
        from ndevio.utils._layer_utils import resolve_layer_type

        result = resolve_layer_type(
            'nuclei_mask',  # Would auto-detect to labels
            global_override='surface',
            channel_types={'nuclei_mask': 'image'},
        )
        assert result == 'surface'

    def test_channel_types_used_when_no_global(self):
        """Test that channel_types is used when no global override."""
        from ndevio.utils._layer_utils import resolve_layer_type

        result = resolve_layer_type(
            'nuclei_mask',
            global_override=None,
            channel_types={'nuclei_mask': 'points'},
        )
        assert result == 'points'

    def test_auto_detect_when_no_overrides(self):
        """Test auto-detection when no overrides provided."""
        from ndevio.utils._layer_utils import resolve_layer_type

        assert (
            resolve_layer_type('nuclei_mask', None, None) == 'labels'
        )  # Auto-detect
        assert resolve_layer_type('DAPI', None, None) == 'image'  # Auto-detect


class TestDetermineInMemory:
    """Tests for determine_in_memory function."""

    def test_none_path_returns_true(self):
        """Test that None path (array data) returns True."""
        from ndevio.utils._layer_utils import determine_in_memory

        assert determine_in_memory(None) is True

    def test_small_file_returns_true(self, tmp_path):
        """Test that small files are loaded in memory."""
        from ndevio.utils._layer_utils import determine_in_memory

        small_file = tmp_path / 'small.txt'
        small_file.write_text('x' * 100)

        with mock.patch(
            'psutil.virtual_memory', return_value=mock.Mock(available=1e10)
        ):
            assert determine_in_memory(small_file) is True

    def test_large_file_returns_false(self, tmp_path):
        """Test that large files are loaded as dask."""
        from ndevio.utils._layer_utils import determine_in_memory

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
            assert determine_in_memory(large_file) is False


class TestBuildLayerTuple:
    """Tests for build_layer_tuple function."""

    def test_basic_structure(self):
        """Test basic layer tuple structure."""
        import numpy as np

        from ndevio.utils._layer_utils import build_layer_tuple

        data = np.zeros((10, 10))
        result = build_layer_tuple(
            data,
            layer_type='image',
            name='test_layer',
            metadata={'key': 'value'},
            scale=(1.0, 1.0),
            axis_labels=('Y', 'X'),
            units=(None, None),
        )

        assert len(result) == 3
        assert result[2] == 'image'
        assert result[1]['name'] == 'test_layer'
        assert result[1]['scale'] == (1.0, 1.0)
        assert result[1]['axis_labels'] == ('Y', 'X')
        assert result[1]['units'] == (None, None)
        assert result[1]['metadata'] == {'key': 'value'}

    def test_includes_units_when_provided(self):
        """Test that units are included in metadata."""
        import numpy as np

        from ndevio.utils._layer_utils import build_layer_tuple

        data = np.zeros((10, 10))
        result = build_layer_tuple(
            data,
            layer_type='image',
            name='test',
            metadata={},
            scale=(1.0, 1.0),
            axis_labels=('Y', 'X'),
            units=('µm', 'µm'),
        )

        assert result[1]['units'] == ('µm', 'µm')

    def test_rgb_flag_set(self):
        """Test that RGB flag is set correctly."""
        import numpy as np

        from ndevio.utils._layer_utils import build_layer_tuple

        data = np.zeros((10, 10, 3))
        result = build_layer_tuple(
            data,
            layer_type='image',
            name='rgb_image',
            metadata={},
            scale=(1.0, 1.0),
            axis_labels=('Y', 'X'),
            units=(None, None),
            rgb=True,
        )

        assert result[1]['rgb'] is True
        assert (
            'colormap' not in result[1]
        )  # RGB images shouldn't have colormap

    def test_image_gets_colormap(self):
        """Test that non-RGB images get colormap."""
        import numpy as np

        from ndevio.utils._layer_utils import build_layer_tuple

        data = np.zeros((10, 10))
        result = build_layer_tuple(
            data,
            layer_type='image',
            name='test',
            metadata={},
            scale=(1.0, 1.0),
            axis_labels=('Y', 'X'),
            units=(None, None),
        )

        assert 'colormap' in result[1]
        assert 'blending' in result[1]

    def test_labels_no_colormap(self):
        """Test that labels don't get colormap."""
        import numpy as np

        from ndevio.utils._layer_utils import build_layer_tuple

        data = np.zeros((10, 10), dtype=np.int32)
        result = build_layer_tuple(
            data,
            layer_type='labels',
            name='test',
            metadata={},
            scale=(1.0, 1.0),
            axis_labels=('Y', 'X'),
            units=(None, None),
        )

        assert 'colormap' not in result[1]

    def test_extra_kwargs_override(self):
        """Test that extra_kwargs override defaults."""
        import numpy as np

        from ndevio.utils._layer_utils import build_layer_tuple

        data = np.zeros((10, 10))
        result = build_layer_tuple(
            data,
            layer_type='image',
            name='test',
            metadata={},
            scale=(1.0, 1.0),
            axis_labels=('Y', 'X'),
            units=(None, None),
            extra_kwargs={'colormap': 'custom', 'visible': False},
        )

        assert result[1]['colormap'] == 'custom'
        assert result[1]['visible'] is False

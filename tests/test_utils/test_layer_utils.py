"""Tests for _layer_utils module."""

from __future__ import annotations


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

    def test_auto_detect_is_case_insensitive(self):
        """Channel-name keyword matching should ignore case."""
        from ndevio.utils._layer_utils import resolve_layer_type

        assert resolve_layer_type('MASK', None, None) == 'labels'
        assert resolve_layer_type('Label', None, None) == 'labels'
        assert resolve_layer_type('SEGMENTATION', None, None) == 'labels'

    def test_path_stem_fallback_detects_labels(self):
        """Regression: file named 'cells_mask.tif' with generic channel name
        '0' should be detected as 'labels' via the path_stem fallback.
        """
        from ndevio.utils._layer_utils import resolve_layer_type

        assert (
            resolve_layer_type('0', None, None, path_stem='cells_mask')
            == 'labels'
        )
        assert (
            resolve_layer_type(
                'Channel 0', None, None, path_stem='nuclei_labels'
            )
            == 'labels'
        )
        assert (
            resolve_layer_type('', None, None, path_stem='segmentation_output')
            == 'labels'
        )
        assert resolve_layer_type('', None, None, path_stem='raw') == 'image'

    def test_path_stem_not_checked_when_channel_triggers_detection(self):
        """Channel-name detection is unaffected by a non-label path_stem."""
        from ndevio.utils._layer_utils import resolve_layer_type

        assert (
            resolve_layer_type('nuclei_mask', None, None, path_stem='raw')
            == 'labels'
        )

    def test_path_stem_nonlabel_image_result(self):
        """Neither channel nor path_stem contains label keyword → 'image'."""
        from ndevio.utils._layer_utils import resolve_layer_type

        assert (
            resolve_layer_type('DAPI', None, None, path_stem='raw_image')
            == 'image'
        )

    def test_path_stem_none_channel_nonlabel_returns_image(self):
        """path_stem=None with non-label channel should still return 'image'."""
        from ndevio.utils._layer_utils import resolve_layer_type

        assert (
            resolve_layer_type('DAPI', None, None, path_stem=None) == 'image'
        )


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

"""Tests for bioio_plugins._compatibility module."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch


def _make_zarr_reader(multiscales: list) -> MagicMock:
    """Return a mock that looks like a ``bioio_ome_zarr.Reader`` instance."""
    reader = MagicMock()
    reader.__module__ = 'bioio_ome_zarr.reader'
    reader._multiscales_metadata = multiscales
    return reader


def _make_v01_multiscales(version: str = '0.1') -> list:
    """Minimal OME-Zarr v0.1/v0.2 multiscales — no coordinateTransformations."""
    return [{'version': version, 'datasets': [{'path': '0'}, {'path': '1'}]}]


def _make_v03_string_axes_multiscales() -> list:
    """OME-Zarr v0.3 multiscales — axes are strings, has coordinateTransformations."""
    return [
        {
            'version': '0.3',
            'axes': ['z', 'y', 'x'],
            'datasets': [
                {
                    'path': '0',
                    'coordinateTransformations': [
                        {'type': 'scale', 'scale': [1.0, 0.5, 0.5]}
                    ],
                }
            ],
        }
    ]


def _make_v04_multiscales() -> list:
    """Minimal OME-Zarr >=v0.4 multiscales — dict-axes and coordinateTransformations."""
    return [
        {
            'version': '0.4',
            'axes': [
                {'name': 'z', 'type': 'space'},
                {'name': 'y', 'type': 'space'},
                {'name': 'x', 'type': 'space'},
            ],
            'datasets': [
                {
                    'path': '0',
                    'coordinateTransformations': [
                        {'type': 'scale', 'scale': [1.0, 0.5, 0.5]}
                    ],
                }
            ],
        }
    ]


class TestWarnIfNoCoordinateTransforms:
    """Unit tests for _warn_if_no_coordinate_transforms."""

    def test_v01_emits_warning(self, caplog):
        """v0.1 metadata (no coordinateTransformations) triggers a warning."""
        from ndevio.bioio_plugins._compatibility import (
            _warn_if_no_coordinate_transforms,
        )

        reader = _make_zarr_reader(_make_v01_multiscales('0.1'))

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            _warn_if_no_coordinate_transforms(reader)

        assert len(caplog.records) == 1
        assert '0.1' in caplog.records[0].message
        assert 'coordinateTransformations' in caplog.records[0].message
        assert 'scale=1.0' in caplog.records[0].message

    def test_v02_emits_warning(self, caplog):
        """v0.2 metadata also triggers a warning."""
        from ndevio.bioio_plugins._compatibility import (
            _warn_if_no_coordinate_transforms,
        )

        reader = _make_zarr_reader(_make_v01_multiscales('0.2'))

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            _warn_if_no_coordinate_transforms(reader)

        assert len(caplog.records) == 1
        assert '0.2' in caplog.records[0].message

    def test_v03_with_transforms_no_warning(self, caplog):
        """v0.3 metadata (has coordinateTransformations) emits no warning."""
        from ndevio.bioio_plugins._compatibility import (
            _warn_if_no_coordinate_transforms,
        )

        reader = _make_zarr_reader(_make_v03_string_axes_multiscales())

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            _warn_if_no_coordinate_transforms(reader)

        assert len(caplog.records) == 0

    def test_v04_no_warning(self, caplog):
        """v0.4 metadata emits no warning."""
        from ndevio.bioio_plugins._compatibility import (
            _warn_if_no_coordinate_transforms,
        )

        reader = _make_zarr_reader(_make_v04_multiscales())

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            _warn_if_no_coordinate_transforms(reader)

        assert len(caplog.records) == 0

    def test_empty_multiscales_no_warning(self, caplog):
        """Empty multiscales list does not raise and emits no warning."""
        from ndevio.bioio_plugins._compatibility import (
            _warn_if_no_coordinate_transforms,
        )

        reader = _make_zarr_reader([])

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            _warn_if_no_coordinate_transforms(reader)

        assert len(caplog.records) == 0

    def test_unknown_version_in_warning(self, caplog):
        """When version key is missing the warning still fires with a fallback string."""
        from ndevio.bioio_plugins._compatibility import (
            _warn_if_no_coordinate_transforms,
        )

        # No 'version' key, no 'coordinateTransformations'
        multiscales = [{'datasets': [{'path': '0'}]}]
        reader = _make_zarr_reader(multiscales)

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            _warn_if_no_coordinate_transforms(reader)

        assert len(caplog.records) == 1
        assert 'unknown' in caplog.records[0].message.lower()


class TestNormalizeV03StringAxes:
    """Unit tests for _normalize_v03_string_axes."""

    def test_string_axes_normalized(self):
        """v0.3 string-axes are converted to v0.4 dict-axes."""
        from ndevio.bioio_plugins._compatibility import (
            _normalize_v03_string_axes,
        )

        reader = _make_zarr_reader(_make_v03_string_axes_multiscales())
        _normalize_v03_string_axes(reader)

        axes = reader._multiscales_metadata[0]['axes']
        assert all(isinstance(ax, dict) for ax in axes)
        assert axes[0] == {'name': 'z', 'type': 'space'}
        assert axes[1] == {'name': 'y', 'type': 'space'}
        assert axes[2] == {'name': 'x', 'type': 'space'}

    def test_dict_axes_untouched(self):
        """v0.4 dict-axes are not modified."""
        from ndevio.bioio_plugins._compatibility import (
            _normalize_v03_string_axes,
        )

        reader = _make_zarr_reader(_make_v04_multiscales())
        import copy

        original = copy.deepcopy(reader._multiscales_metadata[0]['axes'])
        _normalize_v03_string_axes(reader)

        assert reader._multiscales_metadata[0]['axes'] == original

    def test_empty_multiscales(self):
        """No crash on empty multiscales."""
        from ndevio.bioio_plugins._compatibility import (
            _normalize_v03_string_axes,
        )

        reader = _make_zarr_reader([])
        _normalize_v03_string_axes(reader)  # should not raise


class TestNImageCompatibilityGuard:
    """Integration tests: nImage.__init__ calls apply_ome_zarr_compat_patches for zarr readers."""

    def test_non_zarr_reader_skips_check(self, resources_dir):
        """A TIFF-backed nImage never calls apply_ome_zarr_compat_patches."""
        from ndevio import nImage

        with patch(
            'ndevio.bioio_plugins._compatibility.apply_ome_zarr_compat_patches'
        ) as mock_check:
            nImage(resources_dir / 'cells3d2ch_legacy.tiff')

        mock_check.assert_not_called()

    def test_zarr_reader_calls_check(self, resources_dir):
        """A zarr-backed nImage calls apply_ome_zarr_compat_patches exactly once."""
        from ndevio import nImage

        with patch(
            'ndevio.bioio_plugins._compatibility.apply_ome_zarr_compat_patches'
        ) as mock_check:
            nImage(resources_dir / 'dimension_handling_zyx_V3.zarr')

        mock_check.assert_called_once()

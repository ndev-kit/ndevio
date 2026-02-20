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


def _make_v03_multiscales() -> list:
    """Minimal OME-Zarr >=v0.3 multiscales — has coordinateTransformations."""
    return [
        {
            'version': '0.3',
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


class TestWarnIfOldZarrFormat:
    """Unit tests for warn_if_old_zarr_format."""

    def test_v01_emits_warning(self, caplog):
        """v0.1 metadata (no coordinateTransformations) triggers a warning."""
        from ndevio.bioio_plugins._compatibility import warn_if_old_zarr_format

        reader = _make_zarr_reader(_make_v01_multiscales('0.1'))

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            warn_if_old_zarr_format(reader)

        assert len(caplog.records) == 1
        assert '0.1' in caplog.records[0].message
        assert 'coordinateTransformations' in caplog.records[0].message
        assert 'scale=1.0' in caplog.records[0].message

    def test_v02_emits_warning(self, caplog):
        """v0.2 metadata also triggers a warning."""
        from ndevio.bioio_plugins._compatibility import warn_if_old_zarr_format

        reader = _make_zarr_reader(_make_v01_multiscales('0.2'))

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            warn_if_old_zarr_format(reader)

        assert len(caplog.records) == 1
        assert '0.2' in caplog.records[0].message

    def test_v03_no_warning(self, caplog):
        """v0.3+ metadata (has coordinateTransformations) emits no warning."""
        from ndevio.bioio_plugins._compatibility import warn_if_old_zarr_format

        reader = _make_zarr_reader(_make_v03_multiscales())

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            warn_if_old_zarr_format(reader)

        assert len(caplog.records) == 0

    def test_empty_multiscales_no_warning(self, caplog):
        """Empty multiscales list does not raise and emits no warning."""
        from ndevio.bioio_plugins._compatibility import warn_if_old_zarr_format

        reader = _make_zarr_reader([])

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            warn_if_old_zarr_format(reader)

        assert len(caplog.records) == 0

    def test_unknown_version_in_warning(self, caplog):
        """When version key is missing the warning still fires with a fallback string."""
        from ndevio.bioio_plugins._compatibility import warn_if_old_zarr_format

        # No 'version' key, no 'coordinateTransformations'
        multiscales = [{'datasets': [{'path': '0'}]}]
        reader = _make_zarr_reader(multiscales)

        with caplog.at_level(
            logging.WARNING, logger='ndevio.bioio_plugins._compatibility'
        ):
            warn_if_old_zarr_format(reader)

        assert len(caplog.records) == 1
        assert 'unknown' in caplog.records[0].message.lower()


class TestNImageCompatibilityGuard:
    """Integration tests: nImage.__init__ only calls warn_if_old_zarr_format for zarr readers."""

    def test_non_zarr_reader_skips_check(self, resources_dir):
        """A TIFF-backed nImage never calls warn_if_old_zarr_format."""
        from ndevio import nImage

        with patch(
            'ndevio.bioio_plugins._compatibility.warn_if_old_zarr_format'
        ) as mock_check:
            nImage(resources_dir / 'cells3d2ch_legacy.tiff')

        mock_check.assert_not_called()

    def test_zarr_reader_calls_check(self, resources_dir):
        """A zarr-backed nImage calls warn_if_old_zarr_format exactly once."""
        from ndevio import nImage

        with patch(
            'ndevio.bioio_plugins._compatibility.warn_if_old_zarr_format'
        ) as mock_check:
            nImage(resources_dir / 'dimension_handling_zyx_V3.zarr')

        mock_check.assert_called_once()

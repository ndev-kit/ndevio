"""Tests for the ndevio layer metadata translator.

The translator is exercised through a lightweight stand-in for ``BioImage``,
so the whole OME-Zarr / array-input quirk matrix is covered without real
files.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from ndevio.utils._layer_metadata import LayerMetadata, build_layer_metadata

# Squeezed dims may still include C (multichannel) and S (RGB); the translator
# must exclude both from the exposed axis labels.
DIMS = ('T', 'C', 'Z', 'Y', 'X')
DIMS_WITH_SAMPLES = ('T', 'C', 'Z', 'Y', 'X', 'S')


class FakeBioImage:
    """Lightweight stand-in for BioImage's metadata accessors.

    ``scale``, ``dimension_properties`` and ``ome_metadata`` behave like the
    real BioImage properties: passing an exception *class* makes the property
    raise it, mirroring the OME-Zarr / array-input quirks.
    """

    def __init__(
        self,
        *,
        scale,
        dimension_properties,
        metadata=None,
        ome_metadata=None,
    ):
        self._scale = scale
        self._dimension_properties = dimension_properties
        self._metadata = metadata if metadata is not None else {'raw': True}
        self._ome_metadata = ome_metadata

    @property
    def scale(self):
        return self._raise_if_needed(self._scale)

    @property
    def dimension_properties(self):
        return self._raise_if_needed(self._dimension_properties)

    @property
    def metadata(self):
        return self._metadata

    @property
    def ome_metadata(self):
        return self._raise_if_needed(self._ome_metadata)

    @staticmethod
    def _raise_if_needed(value):
        if isinstance(value, type) and issubclass(value, Exception):
            raise value()
        return value


def make_fake_image(
    *,
    scale=None,
    dimension_properties=None,
    metadata=None,
    ome_metadata=None,
):
    """Build a FakeBioImage, defaulting absent accessors to empty objects."""
    return FakeBioImage(
        scale=scale if scale is not None else SimpleNamespace(),
        dimension_properties=(
            dimension_properties
            if dimension_properties is not None
            else SimpleNamespace()
        ),
        metadata=metadata,
        ome_metadata=ome_metadata,
    )


@pytest.fixture
def image():
    """An image with full physical metadata for the DIMS dimensions."""
    scale = SimpleNamespace(T=2.0, Z=0.5, Y=0.2, X=0.2)
    dim_props = SimpleNamespace(
        T=SimpleNamespace(unit='s'),
        Z=SimpleNamespace(unit='µm'),
        Y=SimpleNamespace(unit='µm'),
        X=SimpleNamespace(unit='µm'),
    )
    return make_fake_image(
        scale=scale,
        dimension_properties=dim_props,
        metadata={'source': 'fake'},
        ome_metadata={'version': '0.4'},
    )


class TestAxisLabels:
    def test_returns_typed_result(self, image):
        meta = build_layer_metadata(image, DIMS)
        assert isinstance(meta, LayerMetadata)

    def test_excludes_channel_and_samples(self, image):
        meta = build_layer_metadata(image, DIMS_WITH_SAMPLES)
        assert meta.axis_labels == ('T', 'Z', 'Y', 'X')

    def test_preserves_dims_order(self, image):
        meta = build_layer_metadata(image, ('Y', 'X'))
        assert meta.axis_labels == ('Y', 'X')


class TestScale:
    def test_resolved_per_axis(self, image):
        meta = build_layer_metadata(image, DIMS)
        assert meta.scale == (2.0, 0.5, 0.2, 0.2)

    def test_defaults_to_one_for_missing_axis(self, image):
        image._scale = SimpleNamespace(T=2.0)  # only T is known
        meta = build_layer_metadata(image, DIMS)
        assert meta.scale == (2.0, 1.0, 1.0, 1.0)

    @pytest.mark.parametrize('exc', [AttributeError, KeyError, TypeError])
    def test_falls_back_to_ones_when_scale_unavailable(self, image, exc):
        image._scale = exc
        meta = build_layer_metadata(image, DIMS)
        assert meta.scale == (1.0, 1.0, 1.0, 1.0)


class TestUnits:
    def test_resolved_per_axis(self, image):
        meta = build_layer_metadata(image, DIMS)
        assert meta.units == ('s', 'µm', 'µm', 'µm')

    def test_none_for_axis_without_prop(self, image):
        image._dimension_properties = SimpleNamespace(
            T=SimpleNamespace(unit='s')
        )
        meta = build_layer_metadata(image, DIMS)
        assert meta.units == ('s', None, None, None)

    @pytest.mark.parametrize('exc', [AttributeError, KeyError, TypeError])
    def test_falls_back_to_nones_when_properties_unavailable(self, image, exc):
        image._dimension_properties = exc
        meta = build_layer_metadata(image, DIMS)
        assert meta.units == (None, None, None, None)


class TestMetadata:
    def test_contains_image_and_raw_metadata(self, image):
        meta = build_layer_metadata(image, DIMS)
        assert meta.metadata['bioimage'] is image
        assert meta.metadata['raw_image_metadata'] == {'source': 'fake'}

    def test_includes_ome_metadata_when_available(self, image):
        meta = build_layer_metadata(image, DIMS)
        assert meta.metadata['ome_metadata'] == {'version': '0.4'}

    def test_omits_ome_metadata_on_notimplemented(self, image):
        image._ome_metadata = NotImplementedError
        meta = build_layer_metadata(image, DIMS)
        assert 'ome_metadata' not in meta.metadata
        assert 'raw_image_metadata' in meta.metadata

    @pytest.mark.parametrize('exc', [ValueError, TypeError, KeyError])
    def test_warns_but_keeps_raw_on_unparseable_ome(self, image, exc, caplog):
        image._ome_metadata = exc
        with caplog.at_level(
            logging.WARNING, logger='ndevio.utils._layer_metadata'
        ):
            meta = build_layer_metadata(image, DIMS)
        assert 'raw_image_metadata' in meta.metadata
        assert 'ome_metadata' not in meta.metadata
        assert any(
            'Could not parse OME metadata' in r.message for r in caplog.records
        )


class TestAlignment:
    def test_scale_units_aligned_with_axis_labels(self, image):
        meta = build_layer_metadata(image, DIMS)
        assert len(meta.scale) == len(meta.axis_labels)
        assert len(meta.units) == len(meta.axis_labels)

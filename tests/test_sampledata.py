"""Tests for ndevio.sampledata module."""

from __future__ import annotations

import pytest

from ndevio.sampledata import (
    ndev_logo,
    neocortex,
    neuron_labels,
    neuron_labels_processed,
    neuron_raw,
    scratch_assay,
)


def _validate_layer_data_tuples(result: list, expected_layer_type: str | None = None):
    """Helper to validate LayerDataTuple structure.

    Parameters
    ----------
    result : list
        List of LayerDataTuple from sample data function
    expected_layer_type : str, optional
        If provided, assert all layers are this type
    """
    assert isinstance(result, list)
    assert len(result) > 0

    for layer_tuple in result:
        # LayerDataTuple is (data, kwargs, layer_type)
        assert isinstance(layer_tuple, tuple)
        assert len(layer_tuple) == 3

        data, kwargs, layer_type = layer_tuple

        # Data should be array-like with shape
        assert hasattr(data, "shape")
        assert len(data.shape) >= 2  # At minimum 2D

        # kwargs should be a dict
        assert isinstance(kwargs, dict)

        # layer_type should be a string
        assert isinstance(layer_type, str)
        assert layer_type in ("image", "labels")

        if expected_layer_type:
            assert layer_type == expected_layer_type


class TestLocalSampleData:
    """Tests for sample data that loads from local files (no network)."""

    def test_ndev_logo(self):
        """Test loading ndev logo returns valid LayerDataTuples."""
        result = ndev_logo()
        _validate_layer_data_tuples(result, expected_layer_type="image")
        # Logo should be a single image layer
        assert len(result) == 1

    def test_neuron_labels(self):
        """Test loading neuron labels returns valid LayerDataTuples."""
        result = neuron_labels()
        _validate_layer_data_tuples(result, expected_layer_type="labels")
        # Should have 4 channels as separate label layers
        assert len(result) == 4

    def test_neuron_labels_processed(self):
        """Test loading processed neuron labels returns valid LayerDataTuples."""
        result = neuron_labels_processed()
        _validate_layer_data_tuples(result, expected_layer_type="labels")
        # Should have 4 channels as separate label layers
        assert len(result) == 4


@pytest.mark.network
class TestNetworkSampleData:
    """Tests for sample data that requires network download via pooch.

    These tests are marked with @pytest.mark.network and can be skipped
    in CI environments without network access using:
        pytest -m "not network"
    """

    def test_scratch_assay(self):
        """Test loading scratch assay returns valid LayerDataTuples."""
        result = scratch_assay()
        _validate_layer_data_tuples(result)
        # Should have 4 layers: 2 images + 2 labels
        assert len(result) == 4
        # Check we have both image and labels types
        layer_types = [t[2] for t in result]
        assert "image" in layer_types
        assert "labels" in layer_types

    def test_neocortex(self):
        """Test loading neocortex returns valid LayerDataTuples."""
        result = neocortex()
        _validate_layer_data_tuples(result, expected_layer_type="image")
        # Should have 3 channels as separate image layers
        assert len(result) == 3

    def test_neuron_raw(self):
        """Test loading neuron raw returns valid LayerDataTuples."""
        result = neuron_raw()
        _validate_layer_data_tuples(result, expected_layer_type="image")
        # Should have 4 channels as separate image layers
        assert len(result) == 4

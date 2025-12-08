"""
Sample data providers for napari.

This module implements the "sample data" specification.
see: https://napari.org/stable/plugins/building_a_plugin/guides.html#sample-data
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pooch
from bioio_imageio import Reader as ImageIOReader
from bioio_ome_tiff import Reader as OmeTiffReader

from ndevio import nImage

if TYPE_CHECKING:
    from napari.types import LayerDataTuple

SAMPLE_DIR = Path(__file__).parent / 'data'


def ndev_logo() -> list[LayerDataTuple]:
    """Load the ndev logo image."""
    return nImage(
        SAMPLE_DIR / 'ndev-logo.png',
        reader=ImageIOReader,
    ).get_layer_data_tuples()


def scratch_assay() -> list[LayerDataTuple]:
    """Load scratch assay data with labeled nuclei and cytoplasm."""
    scratch_assay_raw_path = pooch.retrieve(
        url='doi:10.5281/zenodo.17845346/scratch-assay-labeled-10T-2Ch.tiff',
        known_hash='md5:2b98c4ea18cd741a1545e59855348a2f',
        fname='scratch-assay-labeled-10T-2Ch.tiff',
        path=SAMPLE_DIR,
    )
    img = nImage(
        scratch_assay_raw_path,
        reader=OmeTiffReader,
    )
    return img.get_layer_data_tuples(
        in_memory=True,
        channel_types={
            'H3342': 'image',
            'oblique': 'image',
            'nuclei': 'labels',
            'cyto': 'labels',
        },
        channel_kwargs={
            'H3342': {'colormap': 'cyan'},
            'oblique': {'colormap': 'gray'},
        },
    )


def neocortex() -> list[LayerDataTuple]:
    """Load neocortex 3-channel image data."""
    neocortex_raw_path = pooch.retrieve(
        url='doi:10.5281/zenodo.17845346/neocortex-3Ch.tiff',
        known_hash='md5:eadc3fac751052461fb2e5f3c6716afa',
        fname='neocortex-3Ch.tiff',
        path=SAMPLE_DIR,
    )
    return nImage(
        neocortex_raw_path,
        reader=OmeTiffReader,
    ).get_layer_data_tuples(in_memory=True)


def neuron_raw() -> list[LayerDataTuple]:
    """Load raw neuron 4-channel image data.

    This sample is downloaded from Zenodo if not present locally.
    """
    neuron_raw_path = pooch.retrieve(
        url='doi:10.5281/zenodo.17845346/neuron-4Ch_raw.tiff',
        known_hash='md5:5d3e42bca2085e8588b6f23cf89ba87c',
        fname='neuron-4Ch_raw.tiff',
        path=SAMPLE_DIR,
    )
    return nImage(
        neuron_raw_path,
        reader=OmeTiffReader,
    ).get_layer_data_tuples(
        in_memory=True,
        layer_type='image',
        channel_kwargs={
            'PHALL': {'colormap': 'gray'},
        },
    )


def neuron_labels() -> list[LayerDataTuple]:
    """Load neuron labels data."""
    return nImage(
        SAMPLE_DIR / 'neuron-4Ch_labels.tiff',
        reader=OmeTiffReader,
    ).get_layer_data_tuples(
        in_memory=True,
        layer_type='labels',
    )


def neuron_labels_processed() -> list[LayerDataTuple]:
    """Load processed neuron labels data."""
    return nImage(
        SAMPLE_DIR / 'neuron-4Ch_labels_processed.tiff',
        reader=OmeTiffReader,
    ).get_layer_data_tuples(
        in_memory=True,
        layer_type='labels',
    )

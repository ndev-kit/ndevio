# ndevio

[![License BSD-3](https://img.shields.io/pypi/l/ndevio.svg?color=green)](https://github.com/ndev-kit/ndevio/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/ndevio.svg?color=green)](https://pypi.org/project/ndevio)
[![Python Version](https://img.shields.io/pypi/pyversions/ndevio.svg?color=green)](https://python.org)
[![tests](https://github.com/ndev-kit/ndevio/workflows/tests/badge.svg)](https://github.com/ndev-kit/ndevio/actions)
[![codecov](https://codecov.io/gh/ndev-kit/ndevio/branch/main/graph/badge.svg)](https://codecov.io/gh/ndev-kit/ndevio)
[![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/ndevio)](https://napari-hub.org/plugins/ndevio)
[![npe2](https://img.shields.io/badge/plugin-npe2-blue?link=https://napari.org/stable/plugins/index.html)](https://napari.org/stable/plugins/index.html)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-purple.json)](https://github.com/copier-org/copier)

**A generalized image format reader for napari built on top of [bioio]**

`ndevio` provides flexible, metadata-aware image I/O for images in napari.
Originally developed as part of napari-ndev, `ndevio` has since been separated into its own plugin as part of the [ndev-kit] and is intended to be a feature-rich and easier to maintain spiritual successor to [napari-aicsimageio].

----------------------------------

## Features

- **Extensive format support** via [bioio] and its plugin system — read OME-TIFF, OME-Zarr, common image and movie formats, proprietary formats (CZI, LIF, ND2), and many more (with bioformats)!
- **Multi-scene handling** — interactive widget for selecting between scenes/positions in multi-scene files
- **Configurable behavior** via [ndev-settings] — customize reader priority, multi-scene handling, and more
- **Smart plugin installation** — automatic suggestions to install missing bioio reader plugins
- **Programmatic API** — `nImage` class for napari-ready metadata extraction
- **Batch utilities** — legacy widget for batch concatenation (with [nbatch]) and metadata management, with features being superseded by [napari-metadata]
- **Sample data** — demonstrates ndevio metadata handling and capabilities

![napari viewer showing scene selection widget and napari-metadata widget displaying the metadata provided by ndevio a .czi file](https://github.com/ndev-kit/ndevio/blob/main/resources/ndevio-scene-and-metadata.png?raw=true)

## Installation

You can install `ndevio` from [PyPI] or via the napari plugin manager:

```bash
pip install ndevio
```

If you would like to try out ndevio, you can run napari in a temporary environment with [uv]:

```bash
uvx --with ndevio -p 3.13 "napari[all]"
```

To contibute to ndevio or experiment with the latest features, see [Contributing.md](CONTRIBUTING.md) for development setup instructions. Conda-forge availability is coming soon!

### Additional Image Format Support

**ndevio** uses [bioio](https://github.com/bioio-devs/bioio) for flexible image reading. Basic formats (TIFF, OME-TIFF, OME-Zarr, PNG, etc.) are supported out of the box via:

- `bioio-ome-tiff` - OME-TIFF files
- `bioio-ome-zarr` - OME-Zarr files
- `bioio-tifffile` - General TIFF files
- `bioio-imageio` - PNG, JPEG, and other common formats

If your image format is not supported by the default readers, then you will get a warning and (by default in napari) a widget to install the suggested reader.
If you know of your additional proprietary formats, install the appropriate bioio reader.
See the [bioio documentation](https://bioio-devs.github.io/bioio/) for the full list of available readers.
**Note**: The use of `bioio-bioformats` has not been fully tested and may have issues. Please [file an issue] if you encounter problems.

## Usage

### In napari

Simply drag and drop image files into napari. `ndevio` handles the rest! To learn more about the decisions that ndevio (and its settings) makes when loading images, see [How ndevio Handles Images](#how-ndevio-handles-images) below.

#### Multi-scene Images

When opening multi-scene files (e.g., multi-position acquisitions, mosaics), a **Scene Widget** appears in the viewer, allowing you to select which scene to display. Configure default behavior via the Settings widget.

#### Bioio Reader Plugin Installation Widget

If you open a file that requires a bioio reader not currently installed, ndevio will display a **BioIO Plugin Installation widget** in napari suggesting the appropriate plugin to install.

![bioio plugin installation suggestion widget](https://github.com/ndev-kit/ndevio/blob/main/resources/bioio-plugin-install-widget.png?raw=true)

This widget taps into the `napari-plugin-manager` to install the bioio reader plugin from PyPI via a GUI. You may invoke this widget manually at any time via `Plugins > ndevio > Install BioIO Reader Plugins` to install any additional bioio reader plugin *and* update any currently installed plugins.

#### Settings Widget

Access **ndevio settings** via `Plugins > ndev-settings > Settings` to customize:

- **Preferred reader**: Override bioio's default plugin selection priority (useful for formats with multiple compatible readers)
- **Multi-scene handling**: Choose whether to show the scene widget, view all scenes as a stack, or view only the first scene
- **Plugin suggestions**: Enable/disable automatic plugin installation prompts for unsupported formats

![ndevio settings via the ndev-settings widget in napari](https://github.com/ndev-kit/ndevio/blob/main/resources/ndev-settings.png?raw=true)

These settings are managed by [ndev-settings] and persist across napari sessions.

#### Utilities Widget

Access via `Plugins > ndevio > Utilities` for:

- **Batch concatenation** of images
- **Metadata management**
- **Export** as OME-TIFF or figure (PNG)

**Note**: Elements of this widget are being superseded by [napari-metadata] for more comprehensive metadata handling.
**Note 2:** This widget was built during napari-ndev mono-repo development and does not fully reflect the design goals of ndevio. It will remain functional, but expect future versions to look different.

### Programmatic Usage with `nImage`

The `nImage` class extends [bioio]'s `BioImage` with napari-specific functionality:

```python
from ndevio import nImage
from napari import Viewer

# Load image with automatic metadata extraction
img = nImage("path/to/image.czi")

# Because nImage subclasses BioImage, all BioImage methods are available
img.dims)             # e.g., <Dimensions [T: 15, C: 4, Z: 1, Y: 256, X: 256]>

# Access napari-ready properties, note that channel and singleton dimensions are dropped
img.layer_data.shape)   # e.g. (15, 4, 256, 256) - still includes channel dimbecause it has not yet been converted to a list of LayerDataTuples
img.layer_scale)        # e.g., (1.0, 0.2, 0.2) - time interval + physical scale per dimension, napari ready
img.layer_axis_labels)  # e.g., ('T', 'Y', 'X')
img.layer_units)        # e.g., ('s', 'µm', 'µm')
img.layer_metadata)     # e.g., a dictionary containing the 1) full BioImage object, 2) raw_image metadata and 3) OME metadata (if parsed) - accessible via `viewer.layers[n].metadata`

# A convenience method to get napari LayerDataTuples with nImage metadata for napari
viewer = Viewer()
for ldt in img.get_layer_data_tuples():
    viewer.add_layer(ldt)
```

### Sample Data

ndevio includes sample datasets accessible via `File > Open Sample > ndevio`.
These samples use the `nImage` API to demonstrate the metadata handling.

![4 Channel 2D neural cells with segmentation labels](https://github.com/ndev-kit/ndevio/blob/main/resources/neuron-sampledata.png?raw=true)

- 2D neural cells in a dish imaged with 4 channels, with corresponding segmentation labels
- 2D brain slice with 3 different transcription factor antibody stains
- A single 2D+Time sample from a scratched retinal epithelial cell culture, including auto-detected labels in the same file.
- the napari-ndev logo as a .png

## How ndevio Handles Images

### Metadata

Image metadata is extracted from bioio and converted to napari layer metadata based on the current napari convention to squeeze out singleton dimensions (i.e. drop dimensions of size 1):

- **Full metadata** available at `viewer.layers[n].metadata`
- **Time and physical scale** automatically applied to layers from OME metadata or file headers
- **Dimension labels** (T, C, Z, Y, X) preserved in `axis_labels`
- **Physical units** (µm, nm, etc.) stored in layer metadata

### Memory Management

Images are loaded **in-memory** or **lazily** (via dask) automatically based on:

- File size < 4 GB **AND**
- File size < 30% of available RAM

### Multi-channel Images

Multi-channel images are **always split** into individual layers (one per channel), using channel names from metadata when available. Images are added with colorblind-friendly colormaps.

### Mosaic/Tiled Images

Images with tiles (e.g., stitched acquisitions) are **automatically stitched together** if the reader supports this behavior.

### RGB Images

RGB(A) images are currently added to the viewer as a single RGB(A) layer, according to napari conventions.
RGB(A) images are identified by containing the Samples ('S') dimension by bioio, which nominally exists for images with the last (`-1`) dimension being of size 3 or 4.

### Detection of Labels/Segmentation Layers

If an image contains a channel name or file name suggestive of a labels layer, ndevio will add that channel as a labels layer in napari. Mixed image and label files are possible by having information in the channel names (e.g., `["DAPI", "DAPI-labels"]`).

### Customization

If you need different behavior for any of these automated handling rules, please [file an issue] — we may be able to add settings to configure them!

## Coming Soon

**Writers for OME-TIFF and OME-Zarr** with round-trip napari metadata support!

## Contributing

Contributions are very welcome! Please see [Contributing.md](CONTRIBUTING.md) for development setup and guidelines.

## License

Distributed under the terms of the [BSD-3] license,
"ndevio" is free and open source software

## Issues

If you encounter any problems, please [file an issue] along with a detailed description.

[file an issue]: https://github.com/ndev-kit/ndevio/issues
[napari]: https://github.com/napari/napari
[copier]: https://copier.readthedocs.io/en/stable/
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[napari-plugin-template]: https://github.com/napari/napari-plugin-template
[PyPI]: https://pypi.org/project/ndevio/
[tox]: https://tox.readthedocs.io/en/latest/
[bioio]: https://github.com/bioio-devs/bioio
[napari-aicsimageio]: https://github.com/AllenCellModeling/napari-aicsimageio
[ndev-settings]: https://github.com/ndev-kit/ndev-settings
[napari-metadata]: https://github.com/napari/napari-metadata
[nbatch]: https://github.com/ndev-kit/nbatch
[uv]: https://docs.astral.sh/uv/
[ndev-kit]: https://github.com/ndev-kit

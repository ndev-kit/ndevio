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
Originally developed as part of [napari-ndev], `ndevio` has since been separated into its own plugin and is intended to be a feature-rich and easier to maintain spiritual successor to [napari-aicsimageio].

----------------------------------

## Features

- **Extensive format support** via [bioio] and its plugin system — read OME-TIFF, OME-Zarr, common image and movie formats, proprietary formats (CZI, LIF, ND2), and many more (with bioformats)!
- **Multi-scene handling** — interactive widget for selecting between scenes/positions in multi-scene files
- **Configurable behavior** via [ndev-settings] — customize reader priority, multi-scene handling, and more
- **Smart plugin installation** — automatic suggestions to install missing bioio reader plugins
- **Programmatic API** — `nImage` class for napari-ready metadata extraction
- **Batch utilities** — legacy widget for batch concatenation (with [nbatch]) and metadata management, with features being superseded by [napari-metadata]
- **Sample data** — demonstrates ndevio capabilities

## Installation

You can install `ndevio` via [pip]:

```bash
pip install ndevio
```

or search for it in the napari plugin manager. Conda-forge installation is coming soon!

If you would like to try out ndevio, you can run napari in a temporary environment with [uv]:

```bash
uvx --with ndevio -p 3.13 "napari[all]"
```

To contibute to ndevio or experiment with the latest features, see [Contributing.md](Contributing.md) for development setup instructions.

### Additional Image Format Support

**ndevio** uses [bioio](https://github.com/bioio-devs/bioio) for flexible image reading. Basic formats (TIFF, OME-TIFF, OME-Zarr, PNG, etc.) are supported out of the box via:

- `bioio-ome-tiff` - OME-TIFF files
- `bioio-ome-zarr` - OME-Zarr files
- `bioio-tifffile` - General TIFF files
- `bioio-imageio` - PNG, JPEG, and other common formats

If your image format is not supported by the default readers, then you will get a warning and (by default in napari) a widget to install the suggested reader.
If you know of your additional proprietary formats, install the appropriate bioio reader.

```bash
# CZI files (GPL-3 licensed)
pip install bioio-czi

# LIF files (GPL-3 licensed)
pip install bioio-lif

# Bio-Formats for many formats (behavior not guaranteed)
pip install bioio-bioformats
```

See the [bioio documentation](https://bioio-devs.github.io/bioio/) for the full list of available readers.

### Pixi Usage

You can use [Pixi](https://pixi.sh) for reproducible development environments:

```bash
git clone https://github.com/ndev-kit/ndevio.git
cd ndevio
pixi install -e dev
pixi run -e dev test
```

Or activate the environment and run commands directly:

```bash
pixi shell -e dev
pytest -v
```

### Development

For development, clone the repository and install with the dev dependency group:

```bash
git clone https://github.com/ndev-kit/ndevio.git
cd ndevio
pip install -e . --group dev
```

This includes pytest, pytest-cov, pytest-qt, tox-uv, napari, and pyqt6.

Run tests with:

```bash
pytest -v --cov=ndevio --cov-report=html
```

## Contributing

Contributions are very welcome. Tests can be run with [tox], please ensure
the coverage at least stays the same before you submit a pull request.

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
[tox]: https://tox.readthedocs.io/en/latest/
[pip]: https://pypi.org/project/pip/

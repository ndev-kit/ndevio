# AGENTS.md - ndevio

**Read, write, and manage images in napari**

This document provides guidance for AI assistants and developers working on the `ndevio` package. For workspace-level guidance, see the root `AGENTS.md`.

---

## Quick Start for Development

**Setting up the development environment**:

```powershell
# Navigate to ndevio directory
cd C:\Users\timmo\ndev-kit\ndevio

# Create and activate virtual environment (using uv)
uv venv
.venv\Scripts\activate

# Install in editable mode with testing dependencies
uv pip install -e . --group dev

# Run tests to verify setup
pytest -v
```

**IMPORTANT**: Always activate the virtual environment (`.venv\Scripts\activate`) before running tests or development commands!

---

## Package Purpose

`ndevio` is the I/O backbone of the ndev-kit ecosystem. It provides:

1. **Robust image reading** using bioio with intelligent reader selection
2. **napari metadata handling** for proper layer display and management
3. **Scene management** for multi-scene image files
4. **Simple writers** for OME-TIFF and OME-Zarr formats enabling roundtrip I/O
5. **Settings-driven configuration** for user preferences and reader selection
6. **Extensible reader discovery** via bioio's plugin system

This package is a **spiritual successor to napari-aicsimageio** but must be independently implemented without borrowing code due to licensing considerations.

---

## Project Goals & Status

### Current Migration Goals

1. ✅ **Replicate napari-ndev reading logic** - Core functionality migrated
2. 🔄 **Refactor metadata handling** - Improve napari metadata generation and standardization
3. 🔄 **Replace napari-ndev with ndevio** - Deprecate old code, point to ndevio
4. ⏳ **Expand test coverage** - Especially for Zarr files and edge cases
5. ⏳ **Implement simple writers** - OME-TIFF and OME-Zarr roundtrip capability
6. ⏳ **Plugin manager integration** - UI for installing bioio readers (e.g., bioio-czi, bioio-lif)
7. ⏳ **Modern metadata support** - Handle metadata patterns from napari-aicsimageio era forward

**Status Key**: ✅ Complete | 🔄 In Progress | ⏳ Planned

---

## Architecture & Design Principles

### Separation of Concerns

**Core functionality** (`nimage.py`):

- `nImage` class extends `bioio.BioImage` with napari-specific methods
- Pure Python logic for image loading, metadata extraction
- No Qt dependencies in core modules
- Settings accessed via `ndev-settings`

**napari integration** (`_napari_reader.py`):

- `napari_get_reader()` - Reader discovery function (napari plugin hook)
- `napari_reader_function()` - Actual reading implementation
- `SceneSelector` widget - UI for multi-scene files
- Thin wrappers around core `nImage` functionality

**Writers** (`_writer.py`):

- Simple, focused implementations for OME-TIFF and OME-Zarr
- Roundtrip capability with readers
- Preserve critical metadata

**Widgets** (`_widget.py`):

- Reader settings and configuration UI
- Plugin manager integration (future)
- Export/screenshot utilities

### Reader Selection Strategy

The reader selection follows a priority hierarchy:

1. **Explicit reader parameter** - If passed directly to function
2. **User preference from settings** - `ndev_settings.ndevio_reader.preferred_reader`
3. **bioio feasibility check** - Verify preferred reader supports the file
4. **bioio auto-detection** - Fallback to bioio's plugin determination

**Key function**: `get_preferred_reader(image, preferred_reader=None)`

This approach gives users control while providing intelligent fallbacks.

### Metadata Philosophy

napari layers require specific metadata for proper display. The `get_napari_metadata()` method generates:

**Essential metadata**:

- `name` - Layer name (includes scene, channel, path information)
- `scale` - Physical pixel sizes for proper spatial rendering
- `rgb` - Flag for RGB images
- `channel_axis` - When unpacking multichannel images as separate layers
- `metadata` - Nested dict with bioimage object, raw metadata, OME metadata

**Naming convention**:

```raw
<channel> :: <scene_idx> :: <scene_name> :: <filename>
```

Delimiter: ` :: ` (space-colon-colon-space)

**Design goals**:

- Preserve traceability to source file
- Support multi-scene and multichannel workflows
- Enable programmatic parsing of layer names
- Maintain compatibility with napari-ndev patterns

---

## Key Components

### nImage Class

Extends `bioio.BioImage` with napari-specific functionality.

**Key methods**:

```python
def get_napari_image_data(in_memory: bool | None = None) -> xr.DataArray:
    """
    Get image data as xarray, optionally in memory.

    Respects user settings for in_memory threshold.
    Returns dask array or numpy array based on file size.
    """

def get_napari_metadata(path: PathLike | None = None) -> dict:
    """
    Generate napari layer metadata.

    Handles:
    - Scene naming
    - Channel unpacking
    - Physical scales
    - RGB detection
    - Nested metadata preservation
    """
```

**Attributes**:

- `napari_data` - Cached xarray of image data
- `napari_metadata` - Cached metadata dict
- `path` - Path to source file (if applicable)
- `settings` - Reference to ndev-settings

### Reader Function

**Entry point**: `napari_get_reader(path, **kwargs) -> ReaderFunction | None`

Returns a reader function if the file is supported, otherwise `None`.

**Actual reader**: `napari_reader_function(path, reader, **kwargs) -> list[LayerData]`

Handles:

- Single scene files → returns one layer (or multiple if unpacking channels)
- Multi-scene files → returns all scenes or shows `SceneSelector` widget
- In-memory vs dask array decisions
- Error handling and logging

### Scene Management

**Three modes** (configurable in settings):

1. **Open Scene Widget** (default) - Show `SceneSelector` for multi-scene files
2. **View All Scenes** - Load all scenes automatically
3. **View First Scene Only** - Ignore additional scenes

The `SceneSelector` widget:

- Lists available scenes
- Allows scene selection
- Optionally clears viewer when switching scenes
- Integrates with napari viewer

---

## Development Guidelines

### Testing Strategy

**Priority areas** (in order):

1. **Core nImage functionality** (90%+ coverage target)
   - Reader selection logic
   - Metadata generation
   - In-memory determination
   - Scene handling

2. **napari reader integration** (80%+ coverage)
   - File format support
   - Multi-scene workflows
   - Channel unpacking
   - Error handling

3. **Zarr support** (Critical - needs expansion)
   - OME-Zarr reading
   - Zarr v3 compatibility
   - Zarr writing (roundtrip)
   - Large dataset handling

4. **Writers** (Future - roundtrip tests)
   - OME-TIFF write/read cycle
   - OME-Zarr write/read cycle
   - Metadata preservation

**Test data strategy**:

- Small synthetic images in `tests/test_data/`
- Use `ndev-sampledata` for realistic examples
- Mock large files, use small Zarr stores for testing

**Running tests**:

```powershell
# IMPORTANT: Activate the virtual environment first (using uv)
.venv\Scripts\activate

# From ndevio root
pytest --cov=src/ndevio --cov-report=html

# Test specific functionality
pytest tests/test_reader.py -k "scene"
pytest tests/test_writer.py -v
```

### Code Organization

```raw
ndevio/
├── src/ndevio/
│   ├── __init__.py          # Public API exports
│   ├── nimage.py            # Core nImage class (NO napari/Qt deps)
│   ├── _napari_reader.py    # napari reader plugin
│   ├── _writer.py           # Writer implementations
│   ├── _widget.py           # napari widgets (Qt allowed here)
│   ├── napari.yaml          # napari plugin manifest
│   └── ndev_settings.yaml   # Settings schema
└── tests/
    ├── conftest.py          # Shared fixtures
    ├── test_reader.py       # Reader tests
    ├── test_writer.py       # Writer tests
    ├── test_widget.py       # Widget tests
    └── test_data/           # Small test files
```

**Import rules**:

- `nimage.py` - NO napari, NO Qt imports
- `_napari_reader.py` - napari types OK, Qt via lazy import only
- `_widget.py` - Full Qt/magicgui allowed
- All modules can use `ndev_settings`

### Settings Integration

Settings defined in `ndev_settings.yaml`:

```yaml
ndevio_reader:
  preferred_reader:
    default: bioio-ome-tiff
    dynamic_choices:
      provider: bioio.readers
    tooltip: Preferred reader to use when opening images

  scene_handling:
    choices: [Open Scene Widget, View All Scenes, View First Scene Only]
    default: Open Scene Widget

  unpack_channels_as_layers:
    default: true
    tooltip: Whether to unpack multichannel images as separate layers

  clear_layers_on_new_scene:
    default: false
    tooltip: Whether to clear viewer when selecting new scene
```

**Access pattern**:

```python
from ndev_settings import get_settings

settings = get_settings()
preferred = settings.ndevio_reader.preferred_reader
```

---

## Implementation Priorities

### Phase 1: Core Refactoring (Current)

- [ ] Improve `get_napari_metadata()` for clarity and maintainability
- [ ] Standardize metadata structure for downstream consumers
- [ ] Enhance docstrings with examples
- [ ] Add type hints throughout
- [ ] Separate metadata generation into composable functions

**Anti-pattern to avoid**:

```python
# Don't: One giant function with deeply nested conditionals
def get_napari_metadata(self):
    meta = {}
    if IS_MULTICHANNEL:
        if self.settings.unpack:
            if NO_SCENE:
                meta["name"] = [...]
            else:
                meta["name"] = [...]
        else:
            # ...more nesting...
```

**Better pattern**:

```python
# Do: Composable helper functions
def _build_layer_name(self, channel=None, scene_info=None) -> str:
    """Build standardized layer name."""
    parts = []
    if channel:
        parts.append(channel)
    if scene_info and not scene_info.is_default:
        parts.extend([scene_info.index, scene_info.name])
    parts.append(self.path_stem)
    return DELIM.join(parts)

def get_napari_metadata(self):
    """Generate napari metadata using helper functions."""
    meta = {}
    meta["name"] = self._build_layer_name(...)
    meta["scale"] = self._extract_physical_scales()
    meta["metadata"] = self._build_nested_metadata()
    return meta
```

### Phase 2: Writer Implementation

**Goal**: Simple, reliable writers for roundtrip I/O

**OME-TIFF Writer**:

```python
def write_ome_tiff(
    path: str,
    data: np.ndarray | xr.DataArray,
    metadata: dict | None = None,
    **kwargs
) -> str:
    """
    Write data as OME-TIFF using bioio.

    Preserves critical metadata for roundtrip compatibility.
    """
    # Use bioio's OmeTiffWriter
    # Extract and preserve physical scales, channel names
    # Return path to written file
```

**OME-Zarr Writer**:

```python
def write_ome_zarr(
    path: str,
    data: np.ndarray | xr.DataArray,
    metadata: dict | None = None,
    **kwargs
) -> str:
    """
    Write data as OME-Zarr using bioio.

    Supports lazy writing for large datasets.
    """
    # Use bioio's OmeZarrWriter
    # Handle chunking appropriately
    # Preserve multiscale if appropriate
```

**Testing**:

- Roundtrip tests: write → read → compare
- Metadata preservation tests
- Large file handling (use small test cases with chunking)

### Phase 3: Enhanced Test Coverage

**Critical Zarr tests**:

```python
def test_read_ome_zarr(sample_ome_zarr):
    """Test reading OME-Zarr with metadata."""
    img = nImage(sample_ome_zarr)
    assert img.reader_name == "bioio-ome-zarr"
    # Test metadata preservation

def test_zarr_v3_compatibility():
    """Ensure zarr v3 compatibility patch works."""
    # Test the _apply_zarr_compat_patch() function

def test_zarr_roundtrip(tmp_path):
    """Write and read back Zarr."""
    # Create data → write → read → compare
```

**Multi-scene tests**:

```python
def test_scene_selector_widget(make_napari_viewer, multi_scene_file):
    """Test SceneSelector widget interaction."""
    viewer = make_napari_viewer()
    # Test widget creation, scene selection, layer updates

def test_view_all_scenes(multi_scene_file):
    """Test automatic loading of all scenes."""
    # Set scene_handling = "View All Scenes"
    # Verify all scenes loaded as separate layers
```

### Phase 4: Plugin Manager Integration

**Goal**: Allow users to install additional bioio readers from napari

**Concept**:

- Widget lists available bioio readers (via entry points)
- Shows installed vs available
- Allows installation via pip (subprocess or napari's plugin manager)
- Updates dynamic choices in settings

**Implementation sketch**:

```python
# In _widget.py
from magicgui.widgets import Container, PushButton, Table

class ReaderManagerWidget(Container):
    """Manage bioio reader plugins."""

    def __init__(self):
        self.reader_table = Table()
        self.install_button = PushButton(text="Install Selected")
        # List available readers from PyPI or entry points
        # Show installation status
        # Handle installation
```

**Entry points to query**:

```python
from importlib.metadata import entry_points

bioio_readers = entry_points(group="bioio.readers")
# Shows all installed bioio readers
```

**Installation**:

- Use `subprocess` to call `pip install bioio-czi`
- Or integrate with napari's plugin manager API
- Update settings' dynamic_choices after install

### Phase 5: Modern Metadata Support

**Context**: napari-aicsimageio introduced patterns for metadata handling that users may expect.

**Goals**:

- Support common metadata patterns from napari-aicsimageio
- Maintain backward compatibility where possible
- Document differences clearly

**Key considerations**:

- napari's `Layer.metadata` structure
- OME metadata handling
- Physical units and scales
- Channel names and colors

**Research needed**:

- Review napari-aicsimageio metadata structure
- Identify commonly used metadata fields
- Design compatible structure (without copying code)

---

## Common Pitfalls

### ❌ Don't: Import Qt in nimage.py

```python
# nimage.py - WRONG
from qtpy.QtWidgets import QMessageBox

class nImage(BioImage):
    def load(self):
        if error:
            QMessageBox.warning(...)  # Breaks headless usage
```

### ✅ Do: Raise exceptions in core, handle in UI

```python
# nimage.py - CORRECT
class nImage(BioImage):
    def load(self):
        if error:
            raise ValueError("Invalid image format")

# _widget.py or _napari_reader.py
try:
    img = nImage(path)
except ValueError as e:
    # Handle in UI layer
    show_warning(str(e))
```

---

### ❌ Don't: Hardcode reader preferences

```python
# WRONG
def get_reader(path):
    if path.endswith('.tiff'):
        return bioio_ome_tiff.Reader
    elif path.endswith('.zarr'):
        return bioio_ome_zarr.Reader
```

### ✅ Do: Use settings and bioio's discovery

```python
# CORRECT
def get_preferred_reader(image, preferred_reader=None):
    settings = get_settings()
    preferred = preferred_reader or settings.ndevio_reader.preferred_reader

    # Use bioio's feasibility check
    fr = bioio.plugin_feasibility_report(image)
    if preferred in fr and fr[preferred].supported:
        return import_reader(preferred)

    # Fallback to bioio auto-detection
    return nImage.determine_plugin(image).metadata.get_reader()
```

---

### ❌ Don't: Create monolithic metadata functions

```python
# WRONG - Hard to test, maintain, extend
def get_napari_metadata(self):
    meta = {}
    # 150 lines of nested conditionals
    # Impossible to test individual pieces
    return meta
```

### ✅ Do: Decompose into testable helpers

```python
# CORRECT
def _extract_channel_names(self) -> list[str]:
    """Extract channel names from xarray coords."""
    if DimensionNames.Channel not in self.napari_data.dims:
        return []
    return self.napari_data.coords[DimensionNames.Channel].data.tolist()

def _extract_physical_scales(self) -> tuple | None:
    """Extract physical pixel sizes as scale tuple."""
    # Focused, testable function

def get_napari_metadata(self):
    """Compose metadata from helper functions."""
    meta = {}
    meta["channel_names"] = self._extract_channel_names()
    meta["scale"] = self._extract_physical_scales()
    # ...
    return meta
```

---

### ❌ Don't: Mix reader logic with napari integration

```python
# WRONG
def napari_get_reader(path):
    img = nImage(path)  # Heavy operation in discovery function
    return lambda p: [(img.data, {"name": "image"})]
```

### ✅ Do: Defer expensive operations

```python
# CORRECT
def napari_get_reader(path):
    try:
        reader = get_preferred_reader(path)  # Fast check
        return partial(napari_reader_function, reader=reader)
    except UnsupportedFileFormatError:
        return None

def napari_reader_function(path, reader, **kwargs):
    img = nImage(path, reader=reader)  # Heavy operation deferred
    # ...
```

---

## Migration from napari-ndev

When migrating functionality:

1. **Identify the feature** in napari-ndev
2. **Extract core logic** to ndevio (refactor as needed)
3. **Add comprehensive tests** to ndevio
4. **Update napari-ndev** to import from ndevio
5. **Deprecate old code** with clear warnings
6. **Document migration** in both packages

**Example deprecation**:

```python
# In napari-ndev after migration
import warnings
from ndevio import nImage

warnings.warn(
    "napari_ndev.nImage is deprecated. Use ndevio.nImage instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["nImage"]
```

---

## Resources & References

### bioio Ecosystem

- [bioio Documentation](https://bioio-devs.github.io/bioio/)
- [bioio Readers](https://github.com/bioio-devs/bioio#supported-file-formats)
- [bioio-ome-tiff](https://github.com/bioio-devs/bioio-ome-tiff)
- [bioio-ome-zarr](https://github.com/bioio-devs/bioio-ome-zarr)

### napari Integration

- [napari Reader Plugin Guide](https://napari.org/stable/plugins/guides.html#readers)
- [napari Layer Metadata](https://napari.org/stable/howtos/layers/index.html)
- [napari-plugin-engine (npe2)](https://napari.org/npe2/)

### Relevant Standards

- [OME-TIFF Specification](https://docs.openmicroscopy.org/ome-model/latest/)
- [OME-Zarr (NGFF)](https://ngff.openmicroscopy.org/latest/)
- [Zarr Specification](https://zarr.readthedocs.io/)

### Related Projects

- [napari-aicsimageio](https://github.com/AllenCellModeling/napari-aicsimageio) - Inspiration (do NOT copy code)
- [napari-bioio](https://github.com/bioio-devs/napari-bioio) - Reference implementation

---

## AI Assistant Checklist

Before making changes to ndevio:

- [ ] Read this AGENTS.md and root AGENTS.md
- [ ] Understand the separation between core (nimage.py) and UI layers
- [ ] Check if changes belong in ndevio or should go elsewhere
- [ ] Review existing tests for patterns
- [ ] Verify no Qt imports in core modules
- [ ] Run tests before and after changes
- [ ] Update docstrings and type hints
- [ ] Consider impact on napari-ndev migration

When implementing features:

- [ ] Core functionality first (pure Python in nimage.py)
- [ ] Tests for core functionality
- [ ] napari integration layer (if needed)
- [ ] Widget/UI layer (if needed)
- [ ] Integration tests
- [ ] Update ndev_settings.yaml (if adding settings)
- [ ] Update README with usage examples

---

## Changelog

- **2025-10-11**: Initial ndevio AGENTS.md created
  - Documented package purpose and goals
  - Outlined migration strategy from napari-ndev
  - Established architecture principles and testing strategy
  - Defined implementation phases and priorities
  - Added common pitfalls and best practices

---

## Contact

**Package Maintainer**: Tim Monko (timmonko@gmail.com)

**Issues**: [ndevio GitHub Issues](https://github.com/ndev-kit/ndevio/issues)

For general ndev-kit questions, see the root AGENTS.md contact section.

---

*This is living documentation. Update as the package evolves and new patterns emerge.*

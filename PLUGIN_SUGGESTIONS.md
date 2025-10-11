# Bioio Plugin Installation Suggestion System

## Overview

This implements an intelligent system for suggesting bioio plugin installations when users try to open unsupported file formats in ndevio/napari.

## How It Works

### 1. Static Plugin Database (`_reader_utils.py`)

We maintain a complete map of bioio plugins from the official bioio repository:

```python
BIOIO_PLUGINS = {
    "bioio-czi": {
        "extensions": [".czi"],
        "description": "Zeiss CZI files",
        "repository": "https://github.com/bioio-devs/bioio-czi",
    },
    # ... more plugins
}
```

This database includes:
- All known bioio plugins and their supported extensions
- Descriptions for each plugin
- Which plugins are part of ndevio's "core" dependencies
- Special notes (e.g., bioio-bioformats requires Java)

### 2. Extension-Based Suggestions

When a file can't be opened, we:
1. Extract the file extension (handling compound extensions like `.ome.tiff`)
2. Look up which bioio plugins support that extension
3. Filter out "core" plugins (already installed)
4. Return installation suggestions for optional plugins

### 3. Integration with napari Reader

In `napari_get_reader()`:
- When `UnsupportedFileFormatError` is raised
- We call `get_missing_plugins_message(path, feasibility_report)`
- This provides a helpful error message with installation instructions
- Users see this in napari's console/logs

## Example Output

For a `.czi` file without `bioio-czi` installed:

```
ndevio: Unsupported file format
To read 'example.czi', you may need to install:

  📦 bioio-czi
     Zeiss CZI files

     Install: uv pip install bioio-czi
          or: pip install bioio-czi

Then restart napari/Python to make the plugin available.
```

## API Functions

### `suggest_plugins_for_path(path)`
Returns list of plugin info dicts that might support the file based on extension.

### `get_missing_plugins_message(path, feasibility_report=None)`
Generates complete error message with installation instructions.

### `format_plugin_suggestion(plugins, context)`
Formats the installation message from plugin info dicts.

## Future Enhancements

### Phase 2: napari-plugin-manager Integration

For a GUI-based installer widget:

1. **Use napari-plugin-manager's machinery**:
   - Respect user's environment (venv, conda, etc.)
   - Handle subprocess installation safely
   - Provide installation status feedback

2. **Widget Design**:
   - Show current file's supported plugins vs. installed plugins
   - One-click install button for missing plugins
   - Status indicator during installation
   - Success/failure feedback

3. **Implementation Approach**:
```python
from napari_plugin_manager.qt_plugin_dialog import QtPluginDialog

class BioioPluginInstaller(QWidget):
    def __init__(self):
        # Use napari-plugin-manager's installation logic
        # to ensure environment-aware installation
        pass

    def show_missing_for_file(self, path):
        # Show which plugins would help read this file
        # Provide install buttons
        pass
```

### Phase 3: Settings Integration

Add to `ndev_settings.yaml`:
```yaml
ndevio_Reader:
  auto_suggest_plugins:
    default: true
    tooltip: "Show plugin installation suggestions for unsupported files"

  prompt_installation:
    default: false
    tooltip: "Prompt to install missing plugins automatically"
```

## Testing

Run `troubleshooting.py` to see the system in action:

```powershell
cd C:\Users\timmo\ndev-kit\ndevio
.venv\Scripts\python.exe troubleshooting.py
```

This will analyze test files and show:
- Extension-based plugin suggestions
- What's actually installed
- Installation messages for missing plugins

## Dependencies

This implementation requires NO additional dependencies beyond existing ndevio requirements:
- Uses standard library for extension matching
- `bioio.plugin_feasibility_report()` already available
- No Qt/napari dependencies in core suggestion logic

## Maintenance

When new bioio plugins are released:
1. Update `BIOIO_PLUGINS` dict in `_reader_utils.py`
2. Add extensions and descriptions
3. Mark if it should be a "core" dependency

The database is based on: https://github.com/bioio-devs/bioio#bioio-readers

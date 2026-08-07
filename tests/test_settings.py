"""Tests for ndevio's plugin settings.

ndevio's user-configurable settings are declared in ``napari.yaml`` under
``contributions.configuration`` and exposed to napari through
``napari.settings.get_plugin_settings('ndevio')``.  These tests check that:

* the manifest declares the expected configuration contributions,
* ``ndevio._settings.get_ndevio_settings`` returns napari's settings when
  available and falls back to the manifest defaults otherwise.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ndevio._settings import (
    ExportDefaults,
    ReaderDefaults,
    _DefaultSettings,
    get_ndevio_settings,
)

MANIFEST = Path(__file__).parent.parent / 'src' / 'ndevio' / 'napari.yaml'


@pytest.fixture
def manifest():
    """Parse the ndevio npe2 manifest once per test."""
    from npe2 import PluginManifest

    return PluginManifest.from_file(MANIFEST)


def test_manifest_declares_configuration_categories(manifest):
    """The manifest contributes a 'Reader' and an 'Export' category."""
    configs = manifest.contributions.configuration
    assert [c.title for c in configs] == ['Reader', 'Export']

    reader = configs[0]
    assert set(reader.properties) == {
        'ndevio.suggest_reader_plugins',
        'ndevio.scene_handling',
        'ndevio.clear_layers_on_new_scene',
        'ndevio.max_in_mem_gb',
    }

    export = configs[1]
    assert set(export.properties) == {
        'ndevio.canvas_scale',
        'ndevio.override_canvas_size',
        'ndevio.canvas_width',
        'ndevio.canvas_height',
    }


def test_manifest_reader_property_defaults(manifest):
    """Reader properties carry the same defaults as the old ndev-settings."""
    reader = manifest.contributions.configuration[0]
    props = reader.properties

    assert props['ndevio.suggest_reader_plugins'].default is True
    assert props['ndevio.scene_handling'].default == 'Open Scene Widget'
    assert props['ndevio.scene_handling'].enum == [
        'Open Scene Widget',
        'View All Scenes',
        'View First Scene Only',
    ]
    assert props['ndevio.clear_layers_on_new_scene'].default is False
    assert props['ndevio.max_in_mem_gb'].default == 8.0
    assert props['ndevio.max_in_mem_gb'].minimum == 0.5
    assert props['ndevio.max_in_mem_gb'].maximum == 128.0


def test_manifest_export_property_defaults(manifest):
    """Export properties carry the same defaults as the old ndev-settings."""
    export = manifest.contributions.configuration[1]
    props = export.properties

    assert props['ndevio.canvas_scale'].default == 1.0
    assert props['ndevio.canvas_scale'].minimum == 0.01
    assert props['ndevio.canvas_scale'].maximum == 100.0
    assert props['ndevio.override_canvas_size'].default is False
    assert props['ndevio.canvas_width'].default == 1024
    assert props['ndevio.canvas_height'].default == 1024


def test_manifest_has_no_dynamic_preferred_reader(manifest):
    """The dynamic 'preferred_reader' setting is not representable and dropped."""
    for config in manifest.contributions.configuration:
        for key in config.properties:
            assert 'preferred' not in key.lower()


def test_default_settings_shape():
    """The fallback settings object mirrors the manifest defaults."""
    defaults = _DefaultSettings()
    assert isinstance(defaults.reader, ReaderDefaults)
    assert isinstance(defaults.export, ExportDefaults)

    assert defaults.reader.suggest_reader_plugins is True
    assert defaults.reader.scene_handling == 'Open Scene Widget'
    assert defaults.reader.clear_layers_on_new_scene is False
    assert defaults.reader.max_in_mem_gb == 8.0

    assert defaults.export.canvas_scale == 1.0
    assert defaults.export.override_canvas_size is False
    assert defaults.export.canvas_width == 1024
    assert defaults.export.canvas_height == 1024


def test_get_ndevio_settings_uses_napari(monkeypatch):
    """When napari provides plugin settings, they are returned as-is."""
    import napari.settings as napari_settings

    mock = SimpleNamespace(
        reader=SimpleNamespace(scene_handling='View All Scenes'),
    )
    monkeypatch.setattr(
        napari_settings,
        'get_plugin_settings',
        lambda plugin: mock,
        raising=False,
    )

    assert get_ndevio_settings() is mock


def test_get_ndevio_settings_falls_back_when_plugin_missing(monkeypatch):
    """napari raising KeyError for an undiscovered plugin -> defaults."""
    import napari.settings as napari_settings

    def _raise(_plugin: str):
        raise KeyError('ndevio')

    monkeypatch.setattr(
        napari_settings, 'get_plugin_settings', _raise, raising=False
    )

    settings = get_ndevio_settings()
    assert isinstance(settings, _DefaultSettings)
    assert settings.reader.scene_handling == 'Open Scene Widget'


def test_get_ndevio_settings_falls_back_when_feature_missing(monkeypatch):
    """Older napari without get_plugin_settings -> defaults."""
    import napari.settings as napari_settings

    monkeypatch.delattr(napari_settings, 'get_plugin_settings', raising=False)

    settings = get_ndevio_settings()
    assert isinstance(settings, _DefaultSettings)
    assert settings.reader.max_in_mem_gb == 8.0


def test_real_get_plugin_settings(tmp_path):
    """End-to-end: napari builds ndevio's preferences from the manifest."""
    from napari import settings as napari_settings

    if not hasattr(napari_settings, 'get_plugin_settings'):
        pytest.skip(
            'installed napari lacks plugin settings (need napari>=0.9.0)'
        )

    from npe2 import PluginManager, PluginManifest

    # pytest blocks discovery, so register the (always installed) manifest.
    pm = PluginManager.instance()
    if 'ndevio' not in pm:
        pm.register(PluginManifest.from_distribution('ndevio'))
    # Reset the in-memory cache so the registered plugin is included (saved
    # values are re-read from disk; this also allows path_dir=tmp_path).
    napari_settings._PLUGIN_PREFERENCES.clear()

    settings = napari_settings.get_plugin_settings('ndevio', path_dir=tmp_path)

    assert settings.reader.suggest_reader_plugins is True
    assert settings.reader.scene_handling == 'Open Scene Widget'
    assert settings.reader.clear_layers_on_new_scene is False
    assert settings.reader.max_in_mem_gb == 8.0

    assert settings.export.canvas_scale == 1.0
    assert settings.export.override_canvas_size is False
    assert settings.export.canvas_width == 1024
    assert settings.export.canvas_height == 1024

    # Settings are persisted to a per-plugin yaml, and changes auto-save.
    assert settings.config_path == tmp_path / 'ndevio.yaml'
    settings.reader.max_in_mem_gb = 4.0
    assert 'max_in_mem_gb: 4.0' in (tmp_path / 'ndevio.yaml').read_text()

    # The accessor used by ndevio's code paths returns this same model.
    assert get_ndevio_settings() is settings
    assert not isinstance(get_ndevio_settings(), _DefaultSettings)

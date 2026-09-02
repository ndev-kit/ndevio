"""Tests for ndevio's plugin settings.

ndevio's user-configurable settings are declared in ``napari.yaml`` under
``contributions.configurations`` and exposed to napari through
``napari.settings.get_plugin_settings('ndevio')``.  These tests check that:

* the manifest declares the expected configuration contributions,
* ``ndevio._settings.get_ndevio_settings`` returns napari's settings when
  available and falls back to the manifest defaults otherwise,
* napari's ``plugin_settings`` pytest fixture drives the real manifest
  end-to-end (napari >= 0.9.0).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from ndevio._settings import get_ndevio_settings

MANIFEST = Path(__file__).parent.parent / 'src' / 'ndevio' / 'napari.yaml'


@pytest.fixture
def manifest():
    """Parse the ndevio npe2 manifest once per test."""
    from npe2 import PluginManifest

    return PluginManifest.from_file(MANIFEST)


def test_manifest_declares_configuration_categories(manifest):
    """The manifest contributes reader / export categories."""
    configs = manifest.contributions.configurations
    assert list(configs) == ['reader', 'export']
    assert [c.title for c in configs.values()] == [
        'Reader',
        'Export',
    ]

    reader = configs['reader']
    assert set(reader.properties) == {
        'suggest_reader_plugins',
        'scene_handling',
        'clear_layers_on_new_scene',
        'max_in_mem_gb',
    }

    export = configs['export']
    assert set(export.properties) == {
        'canvas_scale',
        'override_canvas_size',
        'canvas_width',
        'canvas_height',
    }


def test_manifest_reader_property_defaults(manifest):
    """Reader properties carry the same defaults as the old ndev-settings."""
    reader = manifest.contributions.configurations['reader']
    props = reader.properties

    assert props['suggest_reader_plugins'].default is True
    assert props['scene_handling'].default == 'Open Scene Widget'
    assert props['scene_handling'].enum == [
        'Open Scene Widget',
        'View All Scenes',
        'View First Scene Only',
    ]
    assert props['clear_layers_on_new_scene'].default is False
    assert props['max_in_mem_gb'].default == 8.0
    assert props['max_in_mem_gb'].minimum == 0.5
    assert props['max_in_mem_gb'].maximum == 128.0


def test_manifest_export_property_defaults(manifest):
    """Export properties carry the same defaults as the old ndev-settings."""
    export = manifest.contributions.configurations['export']
    props = export.properties

    assert props['canvas_scale'].default == 1.0
    assert props['canvas_scale'].minimum == 0.01
    assert props['canvas_scale'].maximum == 100.0
    assert props['override_canvas_size'].default is False
    assert props['canvas_width'].default == 1024
    assert props['canvas_height'].default == 1024


def test_manifest_has_no_dynamic_preferred_reader(manifest):
    """The dynamic 'preferred_reader' setting is not representable and dropped."""
    for config in manifest.contributions.configurations.values():
        for key in config.properties:
            assert 'preferred' not in key.lower()


def test_fallback_defaults_shape():
    """The fallback defaults mirror the manifest defaults."""
    from ndevio._settings import _DEFAULTS

    assert _DEFAULTS.reader.suggest_reader_plugins is True
    assert _DEFAULTS.reader.scene_handling == 'Open Scene Widget'
    assert _DEFAULTS.reader.clear_layers_on_new_scene is False
    assert _DEFAULTS.reader.max_in_mem_gb == 8.0

    assert _DEFAULTS.export.canvas_scale == 1.0
    assert _DEFAULTS.export.override_canvas_size is False
    assert _DEFAULTS.export.canvas_width == 1024
    assert _DEFAULTS.export.canvas_height == 1024


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


def test_get_ndevio_settings_falls_back_when_feature_missing(monkeypatch):
    """Older napari without get_plugin_settings -> defaults."""
    import napari.settings as napari_settings

    monkeypatch.delattr(napari_settings, 'get_plugin_settings', raising=False)

    settings = get_ndevio_settings()
    assert isinstance(settings, SimpleNamespace)
    assert settings.reader.max_in_mem_gb == 8.0


def test_plugin_settings_fixture_end_to_end(plugin_settings, npe2pm):
    """End-to-end via napari's `plugin_settings` fixture + the real manifest.

    Requires napari >= 0.9.0, which ships the `plugin_settings` pytest
    fixture; on older napari the fixture simply doesn't exist and the test
    errors at setup (it is not silently skipped).
    """
    # register ndevio's *real* manifest, loaded from its file, scoped to this
    # test by the npe2pm fixture
    with npe2pm.tmp_plugin(manifest=MANIFEST):
        from napari.settings import get_plugin_settings

        settings = get_plugin_settings('ndevio')

        assert settings.reader.suggest_reader_plugins is True
        assert settings.reader.scene_handling == 'Open Scene Widget'
        assert settings.reader.clear_layers_on_new_scene is False
        assert settings.reader.max_in_mem_gb == 8.0

        assert settings.export.canvas_scale == 1.0
        assert settings.export.override_canvas_size is False
        assert settings.export.canvas_width == 1024
        assert settings.export.canvas_height == 1024

        # changes auto-save under the fixture's per-test tmp_path
        settings.reader.max_in_mem_gb = 4.0
        assert 'max_in_mem_gb: 4.0' in settings.config_path.read_text()

        # the accessor used by ndevio's code paths returns this same model
        assert get_ndevio_settings() is settings
        assert not isinstance(get_ndevio_settings(), SimpleNamespace)


def test_plugin_settings_from_installed_package(plugin_settings, npe2pm):
    """Same end-to-end, but register ndevio from its installed distribution.

    ``npe2pm.tmp_plugin(package='ndevio')`` loads the manifest via
    ``PluginManifest.from_distribution`` — the natural mode when the plugin
    under test is installed in the test environment.
    """
    with npe2pm.tmp_plugin(package='ndevio'):
        from napari.settings import get_plugin_settings

        settings = get_plugin_settings('ndevio')
        assert settings.reader.max_in_mem_gb == 8.0

        settings.reader.max_in_mem_gb = 4.0
        assert 'max_in_mem_gb: 4.0' in settings.config_path.read_text()

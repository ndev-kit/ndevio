"""Access to ndevio's plugin settings.

ndevio's user-configurable behavior is declared in ``napari.yaml`` under
``contributions.configuration`` (two categories: ``reader`` and ``export``)
and surfaces in napari's **Preferences** dialog.  At runtime the values are
read through ``napari.settings.get_plugin_settings('ndevio')``.

When napari is too old to expose plugin settings (i.e. it predates the
``get_plugin_settings`` API), or when the ndevio plugin has not been
discovered yet, :func:`get_ndevio_settings` falls back to the same defaults
declared in the manifest so ndevio keeps working everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from napari.settings import PluginPreferences

_PLUGIN_NAME = 'ndevio'

# The defaults below mirror the ``contributions.configuration`` block in
# ``napari.yaml``.  They are only used as a fallback when napari's plugin
# settings are unavailable (old napari, or plugin not discovered yet).


@dataclass(frozen=True)
class ReaderDefaults:
    """Default values for the ``reader`` configuration category."""

    suggest_reader_plugins: bool = True
    scene_handling: str = 'Open Scene Widget'
    clear_layers_on_new_scene: bool = False
    max_in_mem_gb: float = 8.0


@dataclass(frozen=True)
class ExportDefaults:
    """Default values for the ``export`` configuration category."""

    canvas_scale: float = 1.0
    override_canvas_size: bool = False
    canvas_width: int = 1024
    canvas_height: int = 1024


@dataclass(frozen=True)
class _DefaultSettings:
    """Fallback settings object exposing the same shape as napari's model.

    Attributes are named to match the generated napari plugin preferences
    (``.reader`` and ``.export``), so callers can use the fallback
    interchangeably with the napari-managed model.
    """

    reader: ReaderDefaults = field(default_factory=ReaderDefaults)
    export: ExportDefaults = field(default_factory=ExportDefaults)


def get_ndevio_settings() -> PluginPreferences | _DefaultSettings:
    """Return ndevio's plugin settings, falling back to defaults.

    Returns
    -------
    PluginPreferences | _DefaultSettings
        The napari-managed plugin preferences for ``ndevio`` when available,
        otherwise a frozen dataclass carrying the manifest defaults.  Both
        expose the same ``.reader`` and ``.export`` attributes.

    """
    try:
        from napari.settings import get_plugin_settings
    except ImportError:  # pragma: no cover - pre-plugin-settings napari
        return _DefaultSettings()

    try:
        return get_plugin_settings(_PLUGIN_NAME)
    except KeyError:
        # ndevio is not registered/discovered (yet) -> manifest defaults
        return _DefaultSettings()

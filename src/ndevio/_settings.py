"""Access to ndevio's plugin settings.

ndevio's user-configurable behavior is declared in ``napari.yaml`` under
``contributions.configuration`` (two categories: ``Reader`` and ``Export``)
and surfaces in napari's **Preferences** dialog.  At runtime the values are
read through ``napari.settings.get_plugin_settings('ndevio')``.

On napari versions too old to expose plugin settings (i.e. it predates the
``get_plugin_settings`` API, released in 0.9.0), :func:`get_ndevio_settings`
falls back to the defaults declared in ``napari.yaml`` so ndevio keeps working
everywhere.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from napari.settings import PluginPreferences

_PLUGIN_NAME = 'ndevio'

# Defaults mirroring the ``contributions.configuration`` block in
# ``napari.yaml`` — only the values ndevio's code reads.  Used as a fallback
# when napari is too old to expose plugin settings; the settings are not
# user-configurable in that case.
_DEFAULTS = SimpleNamespace(
    reader=SimpleNamespace(
        suggest_reader_plugins=True,
        scene_handling='Open Scene Widget',
        clear_layers_on_new_scene=False,
        max_in_mem_gb=8.0,
    ),
    export=SimpleNamespace(
        canvas_scale=1.0,
        override_canvas_size=False,
        canvas_width=1024,
        canvas_height=1024,
    ),
)


def get_ndevio_settings() -> PluginPreferences | SimpleNamespace:
    """Return ndevio's plugin settings, falling back to manifest defaults.

    Returns the napari-managed plugin preferences for ``ndevio`` when
    available; otherwise a ``SimpleNamespace`` carrying the manifest defaults
    (used when napari is too old for ``get_plugin_settings``).  Both expose
    the same ``.reader`` and ``.export`` attributes.
    """
    try:
        from napari.settings import get_plugin_settings

        return get_plugin_settings(_PLUGIN_NAME)
    except ImportError:  # pragma: no cover - napari < 0.9.0
        return _DEFAULTS

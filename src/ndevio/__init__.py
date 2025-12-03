try:  # noqa: D104
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from . import helpers
from ._napari_reader import napari_get_reader
from ._plugin_manager import ReaderPluginManager
from .nimage import nImage

__all__ = [
    "__version__",
    "helpers",
    "nImage",
    "napari_get_reader",
    "ReaderPluginManager",
]

try:  # noqa: D104
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from ._napari_reader import napari_get_reader
from .nimage import nImage

__all__ = ["__version__", "nImage", "napari_get_reader"]

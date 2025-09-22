try:  # noqa: D104
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from .nimage import nImage

__all__ = ["__version__", "nImage"]


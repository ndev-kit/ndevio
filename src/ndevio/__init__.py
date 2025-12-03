from typing import TYPE_CHECKING

try:  # noqa: D104
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from . import helpers

# Type stub for lazy import - lets type checkers know nImage exists
if TYPE_CHECKING:
    from .nimage import nImage as nImage


def __getattr__(name: str):
    """Lazily import nImage to speed up package import."""
    if name == "nImage":
        from .nimage import nImage

        return nImage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    "helpers",
    "nImage",
]

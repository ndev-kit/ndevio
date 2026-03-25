from typing import TYPE_CHECKING

try:  # noqa: D104
    from ._version import version as __version__
except ImportError:
    __version__ = 'unknown'

if TYPE_CHECKING:
    from .nimage import nImage as nImage
    from .utils import helpers as helpers


def __getattr__(name: str) -> object:
    """Lazily import heavy submodules to speed up package import."""
    if name == 'nImage':
        from .nimage import nImage

        return nImage
    if name == 'helpers':
        from .utils import helpers

        return helpers
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


__all__ = [
    '__version__',
    'helpers',
    'nImage',
]

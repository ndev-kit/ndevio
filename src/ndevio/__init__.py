try:  # noqa: D104
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

# Lazy imports for performance - heavy modules loaded on first access
_lazy_imports = {
    "helpers": ".helpers",
    "nImage": ".nimage",
    "napari_get_reader": "._napari_reader",
    "ReaderPluginManager": "._plugin_manager",
}


def __getattr__(name: str):
    """Lazily import modules/objects to speed up package import."""
    if name in _lazy_imports:
        import importlib

        module_path = _lazy_imports[name]
        module = importlib.import_module(module_path, __name__)
        # For module imports (helpers), return the module
        if name == "helpers":
            return module
        # For class/function imports, get the attribute from the module
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    "helpers",
    "nImage",
    "napari_get_reader",
    "ReaderPluginManager",
]

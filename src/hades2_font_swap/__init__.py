"""Replace Hades II's in-game fonts with any TrueType or OpenType font."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hades2-font-swap")
except PackageNotFoundError:  # running from a source checkout without installing
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]

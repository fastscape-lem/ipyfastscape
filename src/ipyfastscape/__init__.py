from importlib.metadata import PackageNotFoundError, version

from .common import AppLinker
from .topoviz3d import TopoViz3d

try:
    __version__ = version("ipyfastscape")
except PackageNotFoundError:  # noqa
    # package is not installed
    pass


__all__ = ("AppLinker", "TopoViz3d", "__version__")

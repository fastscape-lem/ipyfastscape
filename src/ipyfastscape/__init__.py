from pkg_resources import DistributionNotFound, get_distribution

from .common import AppLinker  # noqa: F401
from .topoviz3d import TopoViz3d  # noqa: F401

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:  # noqa: F401; pragma: no cover
    # package is not installed
    pass

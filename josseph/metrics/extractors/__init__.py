"""Metric extractor registrations."""

from importlib import import_module
from pkgutil import iter_modules

_PACKAGE_NAME = __name__

for _module in iter_modules(__path__):
    if _module.ispkg:
        continue
    import_module(f"{_PACKAGE_NAME}.{_module.name}")

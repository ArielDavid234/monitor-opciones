"""Backward-compat shim — la implementación vive en live_scanning/."""
from page_modules.live_scanning import render  # noqa: F401
__all__ = ["render"]

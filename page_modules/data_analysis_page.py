"""Backward-compat shim — la implementación vive en data_analysis/."""
from page_modules.data_analysis import render  # noqa: F401
__all__ = ["render"]

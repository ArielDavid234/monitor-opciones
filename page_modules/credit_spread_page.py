"""Backward-compat shim — la implementación vive en credit_spread/."""
from page_modules.credit_spread import render  # noqa: F401
__all__ = ["render"]

# -*- coding: utf-8 -*-
"""
Backward-compatibility shim — entities live in `domain.entities` now.

Any code that still does `from core.entities import X` will continue
to work, but new code should import directly from `domain.entities`.
"""
from domain.entities import *  # noqa: F401,F403
from domain.entities import __all__  # noqa: F401

# -*- coding: utf-8 -*-
"""infrastructure/caching package — gestión de caché (Redis + memory fallback)."""
from infrastructure.caching.cache_manager import CacheManager, get_cache

__all__ = ["CacheManager", "get_cache"]

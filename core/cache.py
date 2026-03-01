# -*- coding: utf-8 -*-
"""
core/cache — Shim de compatibilidad.

**DEPRECATED**:  Usar ``infrastructure.caching.CacheManager`` directamente.

Este módulo mantiene las funciones ``get_cached_chain`` y ``cache_chain``
que usa ``core.scanner`` y ``core.credit_spread_scanner``.  Internamente
delega al ``CacheManager`` unificado para evitar duplicar la lógica de
Redis / memory fallback.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from infrastructure.caching import get_cache

logger = logging.getLogger(__name__)

_cache = get_cache()


def get_cached_chain(ticker: str, expiration: str) -> Optional[Any]:
    """Devuelve el chain cacheado o None si no existe / expiró.

    Delegación directa al CacheManager singleton.
    """
    return _cache.get(f"chain:{ticker}:{expiration}")


def cache_chain(ticker: str, expiration: str, chain_df: Any, ttl_seconds: int = 720) -> None:
    """Guarda el chain en caché. No hace nada si no hay backend disponible.

    Delegación directa al CacheManager singleton.
    """
    _cache.set(f"chain:{ticker}:{expiration}", chain_df, ttl=ttl_seconds)

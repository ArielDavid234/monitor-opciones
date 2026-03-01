# -*- coding: utf-8 -*-
"""
CacheManager — gestión unificada de caché con Redis (preferido) y
memory fallback transparente.

La capa de dominio/servicios sólo conoce el protocolo ``CacheProvider``
(definido en ``core.protocols``); nunca toca Redis ni pickle directamente.
Esta clase es la implementación concreta que vive en infraestructura.

Cumple el contrato de ``core.protocols.CacheProvider``.
"""
from __future__ import annotations

import logging
import pickle
import time
from functools import lru_cache
from typing import Any, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Caché unificada: Redis si disponible, dict en memoria como fallback.

    Implementa el protocolo ``CacheProvider`` de ``core.protocols``.

    Uso::

        cache = CacheManager()
        cache.set("chain:SPY:2026-03-21", df, ttl=600)
        result = cache.get("chain:SPY:2026-03-21")
        cache.delete("chain:SPY:2026-03-21")
        cache.clear_prefix("chain:SPY:")

    El backend se elige automáticamente:
        - Si ``REDIS_URL`` está configurado y se puede conectar → Redis.
        - Si no → dict en memoria con TTL y eviction LRU.
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        """
        Args:
            redis_url: URL de Redis (p.ej. "redis://localhost:6379"). Si es None,
                       se lee de ``config.settings`` o de la variable de entorno
                       ``REDIS_URL``.  Si Redis no está disponible, se usa caché
                       en memoria.
        """
        cfg = get_settings()
        self._default_ttl: int = cfg.cache_ttl_seconds
        self._max_memory: int = cfg.cache_max_memory_entries
        self._redis = self._connect_redis(redis_url or cfg.redis_url)
        self._memory: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._hits: int = 0
        self._misses: int = 0

    # ── Conexión ───────────────────────────────────────────────────────────

    @staticmethod
    def _connect_redis(redis_url: Optional[str]) -> Optional[Any]:
        """Intenta conectar a Redis; silencia errores y devuelve None si falla."""
        import os
        url = redis_url or os.getenv("REDIS_URL")
        if not url:
            logger.info("CacheManager: REDIS_URL no configurado — usando memory cache")
            return None
        try:
            import redis
            client = redis.from_url(
                url,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=10,
            )
            client.ping()
            logger.info("CacheManager: Redis conectado en %s", url)
            return client
        except Exception as exc:
            logger.warning("CacheManager: Redis no disponible (%s) — usando memory cache", exc)
            return None

    @property
    def backend(self) -> str:
        """Devuelve 'redis' o 'memory' según el backend activo."""
        return "redis" if self._redis is not None else "memory"

    @property
    def stats(self) -> dict[str, int]:
        """Estadísticas de hits/misses para diagnóstico."""
        return {"hits": self._hits, "misses": self._misses}

    # ── Operaciones públicas ───────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Lee un valor del caché. Devuelve None si no existe o expiró."""
        if self._redis is not None:
            result = self._redis_get(key)
        else:
            result = self._memory_get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Almacena un valor en caché con TTL en segundos.

        Args:
            key: clave del caché.
            value: cualquier valor serializable (pickle).
            ttl: tiempo de vida en segundos. Si None, usa el default de settings.
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        if self._redis is not None:
            self._redis_set(key, value, effective_ttl)
        else:
            self._memory_set(key, value, effective_ttl)

    def delete(self, key: str) -> None:
        """Elimina una entrada del caché."""
        if self._redis is not None:
            try:
                self._redis.delete(key)
            except Exception as exc:
                logger.debug("Redis delete error: %s", exc)
        else:
            self._memory.pop(key, None)

    def clear_prefix(self, prefix: str) -> None:
        """Elimina todas las entradas cuya clave empieza con ``prefix``."""
        if self._redis is not None:
            try:
                keys = self._redis.keys(f"{prefix}*")
                if keys:
                    self._redis.delete(*keys)
            except Exception as exc:
                logger.debug("Redis clear_prefix error: %s", exc)
        else:
            to_delete = [k for k in self._memory if k.startswith(prefix)]
            for k in to_delete:
                del self._memory[k]

    def clear_all(self) -> None:
        """Limpia todo el caché (útil para tests)."""
        if self._redis is not None:
            try:
                self._redis.flushdb()
            except Exception as exc:
                logger.debug("Redis flushdb error: %s", exc)
        else:
            self._memory.clear()

    # ── Redis internals ────────────────────────────────────────────────────

    def _redis_get(self, key: str) -> Optional[Any]:
        """Lee un valor de Redis y lo deserializa con pickle."""
        try:
            data = self._redis.get(key)
            return pickle.loads(data) if data else None
        except Exception as exc:
            logger.debug("Redis get error (%s): %s", key, exc)
            return None

    def _redis_set(self, key: str, value: Any, ttl: int) -> None:
        """Serializa con pickle y guarda en Redis con TTL."""
        try:
            self._redis.setex(key, ttl, pickle.dumps(value))
        except Exception as exc:
            logger.debug("Redis set error (%s): %s", key, exc)

    # ── Memory internals ───────────────────────────────────────────────────

    def _memory_get(self, key: str) -> Optional[Any]:
        """Lee un valor del dict en memoria, verificando expiración."""
        entry = self._memory.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._memory[key]
            return None
        return value

    def _memory_set(self, key: str, value: Any, ttl: int) -> None:
        """Guarda en el dict en memoria con eviction LRU si supera el límite."""
        if len(self._memory) >= self._max_memory:
            # Evict la entrada más antigua
            oldest = min(self._memory, key=lambda k: self._memory[k][1])
            del self._memory[oldest]
        self._memory[key] = (value, time.time() + ttl)


@lru_cache(maxsize=1)
def get_cache() -> CacheManager:
    """Instancia singleton del CacheManager (thread-safe via lru_cache).

    Usar esta función en vez de instanciar CacheManager() directamente
    para garantizar un solo backend compartido.
    """
    return CacheManager()

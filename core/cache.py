import os
import pickle
import logging

logger = logging.getLogger(__name__)

# Conexión Redis opcional (se lee del secret REDIS_URL de Streamlit Cloud)
# Si no está configurado o falla, todas las funciones son no-op y el scanner
# funciona exactamente igual que antes (escaneo síncrono normal).
_r = None

try:
    import redis as _redis_lib
    _redis_url = os.getenv("REDIS_URL")
    if _redis_url:
        _r = _redis_lib.from_url(
            _redis_url,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=10,
        )
        _r.ping()  # verifica conexión real al arrancar
        logger.info("Redis conectado — caché compartida activa")
    else:
        logger.info("REDIS_URL no configurado — caché Redis desactivada (modo local)")
except Exception as e:
    _r = None
    logger.warning("Redis no disponible, caché desactivada: %s", e)


def get_cached_chain(ticker: str, expiration: str):
    """Devuelve el chain cacheado en Redis o None si no existe / Redis no disponible."""
    if _r is None:
        return None
    try:
        key = f"chain:{ticker}:{expiration}"
        data = _r.get(key)
        if data:
            return pickle.loads(data)
    except Exception as e:
        logger.debug("Redis get error: %s", e)
    return None


def cache_chain(ticker: str, expiration: str, chain_df, ttl_seconds: int = 720):
    """Guarda el chain en Redis por 12 minutos. No hace nada si Redis no disponible."""
    if _r is None:
        return
    try:
        key = f"chain:{ticker}:{expiration}"
        _r.setex(key, ttl_seconds, pickle.dumps(chain_df))
    except Exception as e:
        logger.debug("Redis set error: %s", e)

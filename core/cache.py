import os
import pickle
import redis
from datetime import timedelta

# Conexión Redis (se lee del secret REDIS_URL de Streamlit Cloud)
redis_url = os.getenv("REDIS_URL")
if not redis_url:
    raise RuntimeError("REDIS_URL no encontrado en variables de entorno")

r = redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=5, socket_timeout=10)

def get_cached_chain(ticker: str, expiration: str):
    """Devuelve el DataFrame cacheado o None si no existe o expiró."""
    key = f"chain:{ticker}:{expiration}"
    data = r.get(key)
    if data:
        return pickle.loads(data)
    return None

def cache_chain(ticker: str, expiration: str, chain_df, ttl_seconds: int = 720):
    """Guarda el chain en Redis por 12 minutos (720 segundos)."""
    key = f"chain:{ticker}:{expiration}"
    r.setex(key, ttl_seconds, pickle.dumps(chain_df))

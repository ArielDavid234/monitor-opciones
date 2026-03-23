from __future__ import annotations

import os
import time
import uuid

from infrastructure.caching import get_cache
from infrastructure.data.env_resolver import get_env_value
from infrastructure.data.provider_runtime import get_provider_circuit
from infrastructure.data.yahoo_finance_client import get_active_provider


def _ok(name: str, details: dict | None = None) -> dict:
    return {"name": name, "status": "ok", "details": details or {}}


def _degraded(name: str, details: dict | None = None) -> dict:
    return {"name": name, "status": "degraded", "details": details or {}}


def _down(name: str, details: dict | None = None) -> dict:
    return {"name": name, "status": "down", "details": details or {}}


def provider_healthcheck() -> dict:
    provider = get_active_provider()
    circuit = get_provider_circuit().snapshot()
    if str(circuit.get("state", "closed")) == "open":
        return _degraded("provider", {"provider": provider, "circuit": circuit})

    if provider == "databento":
        if not get_env_value("DATABENTO_API_KEY", ""):
            return _down("provider", {"provider": provider, "reason": "missing DATABENTO_API_KEY"})
        return _ok("provider", {"provider": provider, "circuit": circuit})

    return _down("provider", {"provider": provider, "reason": "invalid provider"})


def cache_healthcheck() -> dict:
    cache = get_cache()
    key = f"health:cache:{uuid.uuid4().hex}"
    payload = {"ts": time.time()}
    try:
        cache.set(key, payload, ttl=20)
        out = cache.get(key)
        cache.delete(key)
        if not isinstance(out, dict):
            return _degraded("cache", {"backend": cache.backend, "reason": "unexpected payload"})
        return _ok("cache", {"backend": cache.backend, "stats": cache.stats})
    except Exception as exc:
        return _down("cache", {"backend": cache.backend, "error": str(exc)})


def repository_healthcheck() -> dict:
    has_url = bool(get_env_value("SUPABASE_URL", ""))
    has_key = bool(get_env_value("SUPABASE_ANON_KEY", ""))
    if has_url and has_key:
        return _ok("repository", {"backend": "supabase"})
    return _down("repository", {"backend": "supabase", "reason": "missing SUPABASE_URL/SUPABASE_ANON_KEY"})


def global_health_status() -> dict:
    checks = [provider_healthcheck(), cache_healthcheck(), repository_healthcheck()]
    statuses = [c["status"] for c in checks]
    if any(s == "down" for s in statuses):
        overall = "down"
    elif any(s == "degraded" for s in statuses):
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "timestamp": int(time.time()),
        "overall": overall,
        "checks": checks,
    }

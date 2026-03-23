from __future__ import annotations

import json
import logging
import time
from typing import Any

from infrastructure.caching import get_cache

logger = logging.getLogger(__name__)

_AUDIT_KEY = "platform:audit:events"
_AUDIT_MAX = 5000


def _safe_log_payload(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, sort_keys=True)
    for token in ("api_key", "token", "password", "secret", "authorization"):
        text = text.replace(token, "redacted")
    return text


def _append_event(event: dict[str, Any]) -> None:
    cache = get_cache()
    rows = cache.get(_AUDIT_KEY)
    if not isinstance(rows, list):
        rows = []
    rows.append(event)
    if len(rows) > _AUDIT_MAX:
        rows = rows[-_AUDIT_MAX:]
    cache.set(_AUDIT_KEY, rows, ttl=7 * 24 * 3600)


def record_audit_event(
    action: str,
    *,
    user_id: str | None,
    tenant_id: str | None,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = {
        "ts": int(time.time()),
        "action": str(action or "unknown"),
        "user_id": str(user_id or "unknown"),
        "tenant_id": str(tenant_id or "default"),
        "status": str(status or "ok"),
        "metadata": metadata or {},
    }
    _append_event(payload)
    logger.info("audit_event | %s", _safe_log_payload(payload))


def recent_audit_events(limit: int = 100) -> list[dict[str, Any]]:
    cache = get_cache()
    rows = cache.get(_AUDIT_KEY)
    if not isinstance(rows, list):
        return []
    return rows[-max(1, int(limit)):]

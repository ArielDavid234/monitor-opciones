from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any


_tenant_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_context", default=None)


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str
    plan: str
    role: str


def normalize_tenant_id(tenant_id: str | None) -> str:
    cleaned = str(tenant_id or "").strip().lower()
    if not cleaned:
        raise ValueError("tenant_id is required")
    return cleaned


def set_tenant_context(tenant_id: str) -> contextvars.Token:
    return _tenant_ctx.set(normalize_tenant_id(tenant_id))


def reset_tenant_context(token: contextvars.Token) -> None:
    _tenant_ctx.reset(token)


def get_tenant_context(default: str | None = None) -> str | None:
    current = _tenant_ctx.get()
    if current:
        return current
    if default:
        return normalize_tenant_id(default)
    return None


def require_tenant_id(tenant_id: str | None = None) -> str:
    if tenant_id:
        return normalize_tenant_id(tenant_id)
    current = get_tenant_context()
    if current:
        return current
    raise ValueError("tenant_id is required")


def tenant_key(tenant_id: str, key: str) -> str:
    safe_tenant = normalize_tenant_id(tenant_id)
    safe_key = str(key or "").strip()
    if not safe_key:
        raise ValueError("storage key is required")
    return f"tenant:{safe_tenant}:{safe_key}"


def resolve_user_tenant(user: dict[str, Any] | None) -> str:
    if isinstance(user, dict):
        return normalize_tenant_id(str(user.get("tenant_id") or "default"))
    return "default"


def assert_tenant_access(*, actor_tenant_id: str, requested_tenant_id: str) -> None:
    actor = normalize_tenant_id(actor_tenant_id)
    requested = normalize_tenant_id(requested_tenant_id)
    if actor != requested:
        raise PermissionError("cross-tenant access denied")

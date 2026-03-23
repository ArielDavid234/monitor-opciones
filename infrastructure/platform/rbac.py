from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrastructure.platform.audit import record_audit_event
from infrastructure.platform.tenant import resolve_user_tenant


ROLE_VIEWER = "viewer"
ROLE_ANALYST = "analyst"
ROLE_ADMIN = "admin"
ROLE_OWNER = "owner"

CAP_SCAN_EXECUTE = "scan_execute"
CAP_REPORT_VIEW = "report_view"
CAP_CONFIG_UPDATE = "config_update"
CAP_MODEL_PROMOTE = "model_promote"
CAP_PROVIDER_SWITCH = "provider_switch"

_ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    ROLE_VIEWER: frozenset({CAP_REPORT_VIEW}),
    ROLE_ANALYST: frozenset({CAP_REPORT_VIEW, CAP_SCAN_EXECUTE}),
    ROLE_ADMIN: frozenset({CAP_REPORT_VIEW, CAP_SCAN_EXECUTE, CAP_CONFIG_UPDATE, CAP_PROVIDER_SWITCH}),
    ROLE_OWNER: frozenset({CAP_REPORT_VIEW, CAP_SCAN_EXECUTE, CAP_CONFIG_UPDATE, CAP_MODEL_PROMOTE, CAP_PROVIDER_SWITCH}),
}


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    role: str
    capability: str


def normalize_role(raw_role: str | None) -> str:
    role = str(raw_role or "").strip().lower()
    if role in _ROLE_CAPABILITIES:
        return role
    if role in {"enterprise", "owner"}:
        return ROLE_OWNER
    if role in {"admin"}:
        return ROLE_ADMIN
    if role in {"pro", "analyst"}:
        return ROLE_ANALYST
    return ROLE_VIEWER


def has_capability(role: str, capability: str) -> bool:
    normalized = normalize_role(role)
    return str(capability) in _ROLE_CAPABILITIES.get(normalized, frozenset())


def authorize(
    *,
    user: dict[str, Any] | None,
    capability: str,
    tenant_id: str,
) -> AuthorizationDecision:
    role = normalize_role((user or {}).get("role") if isinstance(user, dict) else None)
    allowed = has_capability(role, capability)
    reason = "ok" if allowed else "capability_denied"

    record_audit_event(
        "rbac_check",
        user_id=(user or {}).get("id") if isinstance(user, dict) else None,
        tenant_id=tenant_id or resolve_user_tenant(user if isinstance(user, dict) else None),
        status="allow" if allowed else "deny",
        metadata={"role": role, "capability": capability, "reason": reason},
    )

    return AuthorizationDecision(allowed=allowed, reason=reason, role=role, capability=str(capability))

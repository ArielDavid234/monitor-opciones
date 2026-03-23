from __future__ import annotations

import time
from typing import Any

from infrastructure.platform.audit import record_audit_event
from infrastructure.platform.event_bus import get_event_bus


def record_provider_switch(*, user_id: str, tenant_id: str, old_provider: str, new_provider: str) -> None:
    record_audit_event(
        "provider_switch",
        user_id=user_id,
        tenant_id=tenant_id,
        status="success",
        metadata={"old_provider": old_provider, "new_provider": new_provider, "timestamp": int(time.time())},
    )


def record_model_promoted(*, user_id: str, tenant_id: str, version: str) -> None:
    get_event_bus().publish(
        "model_promoted",
        {
            "event_id": f"model-promoted-{version}",
            "version": version,
            "status": "prod",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        schema_name="model_event",
    )
    record_audit_event(
        "model_promoted",
        user_id=user_id,
        tenant_id=tenant_id,
        status="success",
        metadata={"version": version},
    )


def record_config_update(*, user_id: str, tenant_id: str, changes: dict[str, Any]) -> None:
    record_audit_event(
        "config_update",
        user_id=user_id,
        tenant_id=tenant_id,
        status="success",
        metadata={"changes": changes},
    )

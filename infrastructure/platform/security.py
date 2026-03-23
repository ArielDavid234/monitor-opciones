from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

from config.settings import get_settings
from infrastructure.data.env_resolver import get_env_value
from infrastructure.platform.audit import record_audit_event

logger = logging.getLogger(__name__)


_REDACTION_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(token\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(authorization\s*[=:]\s*bearer\s+)([^\s,;]+)"),
    re.compile(r"(?i)(password\s*[=:]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(secret\s*[=:]\s*)([^\s,;]+)"),
]


class SensitiveLogFilter(logging.Filter):
    """Log filter that redacts secret-like tokens from emitted messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = str(record.getMessage())
        redacted = redact_sensitive_text(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_secure_logging() -> None:
    root = logging.getLogger()
    for h in root.handlers:
        if not any(isinstance(f, SensitiveLogFilter) for f in h.filters):
            h.addFilter(SensitiveLogFilter())


def redact_sensitive_text(text: str) -> str:
    out = str(text or "")
    for pattern in _REDACTION_PATTERNS:
        out = pattern.sub(r"\1***REDACTED***", out)
    return out


def sanitize_error_for_user(raw_error: Any) -> str:
    text = redact_sensitive_text(str(raw_error or "")).lower()
    if any(tok in text for tok in ("429", "rate limit", "quota", "too many", "limit")):
        return "datos parciales: cuota temporal alta del proveedor; reintentar en 60 segundos"
    if any(tok in text for tok in ("timeout", "timed out", "temporarily unavailable", "connection")):
        return "datos parciales: servicio temporalmente no disponible; reintentar en 30 segundos"
    if "circuitopen" in text or "circuit open" in text:
        return "datos parciales: protección temporal activa por fallos de proveedor; reintentar en 60 segundos"
    return "datos parciales: error operativo temporal; reintentar en 30 segundos"


def anonymize_user_id(value: str | None) -> str:
    if not value:
        return "anon:unknown"
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()
    return f"anon:{digest[:12]}"


def _critical_config_snapshot() -> dict[str, str]:
    cfg = get_settings()
    return {
        "data_provider": str(getattr(cfg, "data_provider", "")),
        "market_cache_version": str(getattr(cfg, "market_cache_version", "")),
        "market_schema_version": str(getattr(cfg, "market_schema_version", "")),
        "snapshot_schema_version": str(getattr(cfg, "snapshot_schema_version", "")),
        "quota_total": str(getattr(cfg, "databento_quota_total_per_min", "")),
        "quota_background": str(getattr(cfg, "databento_quota_background", "")),
        "quota_live": str(getattr(cfg, "databento_quota_reserved_live_scanning", "")),
    }


def audit_critical_config_change() -> None:
    """Emits an audit event whenever critical runtime config changes across restarts."""
    from infrastructure.caching import get_cache

    cache = get_cache()
    key = "audit:critical_config:last"
    current = _critical_config_snapshot()
    previous = cache.get(key)

    if not isinstance(previous, dict):
        cache.set(key, current, ttl=7 * 24 * 3600)
        logger.info("config audit init | config=%s", json.dumps(current, sort_keys=True))
        record_audit_event(
            "critical_config_change",
            user_id="system",
            tenant_id="platform",
            status="init",
            metadata={"config": current},
        )
        return

    changed = [k for k, v in current.items() if str(previous.get(k)) != str(v)]
    if not changed:
        return

    event = {
        "changed_keys": changed,
        "new": {k: current[k] for k in changed},
        "old": {k: previous.get(k) for k in changed},
    }
    logger.warning("config audit change | %s", json.dumps(event, sort_keys=True))
    record_audit_event(
        "critical_config_change",
        user_id="system",
        tenant_id="platform",
        status="changed",
        metadata=event,
    )
    cache.set(key, current, ttl=7 * 24 * 3600)


def validate_startup_secrets() -> list[str]:
    cfg = get_settings()
    provider = get_env_value("DATA_PROVIDER", str(getattr(cfg, "data_provider", "databento"))).lower()
    errors: list[str] = []

    databento_key = get_env_value("DATABENTO_API_KEY", str(getattr(cfg, "databento_api_key", "")))
    polygon_key = get_env_value("POLYGON_API_KEY", str(getattr(cfg, "polygon_api_key", "")))
    supabase_url = get_env_value("SUPABASE_URL", str(getattr(cfg, "supabase_url", "")))
    supabase_key = get_env_value("SUPABASE_ANON_KEY", str(getattr(cfg, "supabase_anon_key", "")))

    if provider == "databento" and not databento_key:
        errors.append("DATABENTO_API_KEY ausente para DATA_PROVIDER=databento")
    if provider == "polygon" and not polygon_key:
        errors.append("POLYGON_API_KEY ausente para DATA_PROVIDER=polygon")

    if not supabase_url:
        errors.append("SUPABASE_URL ausente")
    if not supabase_key:
        errors.append("SUPABASE_ANON_KEY ausente")

    return errors


def fail_fast_if_missing_secrets() -> None:
    errors = validate_startup_secrets()
    if not errors:
        return

    msg = "Configuracion invalida: secretos criticos faltantes -> " + "; ".join(errors)
    logger.critical(msg)
    raise RuntimeError(msg)


def env_by_stage(stage: str) -> dict[str, str]:
    """Expose required variable names by environment stage."""
    stage_key = (stage or "dev").lower().strip()
    common = {
        "DATA_PROVIDER": "databento|polygon",
        "SUPABASE_URL": "required",
        "SUPABASE_ANON_KEY": "required",
        "REDIS_URL": "optional",
        "MARKET_CACHE_VERSION": "required",
        "MARKET_SCHEMA_VERSION": "required",
        "SNAPSHOT_SCHEMA_VERSION": "required",
    }
    if stage_key == "prod":
        common["SNAPSHOT_WARM_START_ENABLED"] = "true|false"
        common["CHANGE_FREEZE_ENABLED"] = "true|false"
    return common

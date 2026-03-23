from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str


class SchemaRegistry:
    """Versioned data contract registry with lightweight runtime validation."""

    def __init__(self) -> None:
        self._schemas: dict[tuple[str, str], dict[str, Any]] = {
            ("market_snapshot", "v1"): {
                "required": {
                    "ticker": str,
                    "spot": (int, float),
                    "timestamp": str,
                    "provider": str,
                }
            },
            ("scoring_output", "v1"): {
                "required": {
                    "ticker": str,
                    "score_unificado": (int, float),
                    "perfil_riesgo": str,
                    "timestamp": str,
                }
            },
            ("alert_event", "v1"): {
                "required": {
                    "event_id": str,
                    "ticker": str,
                    "score_unificado": (int, float),
                    "severity": str,
                    "timestamp": str,
                }
            },
            ("model_event", "v1"): {
                "required": {
                    "event_id": str,
                    "version": str,
                    "status": str,
                    "timestamp": str,
                }
            },
        }

    def available(self) -> list[dict[str, str]]:
        return [{"schema": k[0], "version": k[1]} for k in sorted(self._schemas.keys())]

    def validate(self, schema_name: str, version: str, payload: dict[str, Any]) -> ValidationResult:
        key = (str(schema_name), str(version))
        schema = self._schemas.get(key)
        if not schema:
            return ValidationResult(False, f"unknown_schema:{schema_name}:{version}")

        required = schema.get("required", {})
        if not isinstance(payload, dict):
            return ValidationResult(False, "payload_must_be_object")

        for field, expected_type in required.items():
            if field not in payload:
                return ValidationResult(False, f"missing_field:{field}")
            value = payload.get(field)
            if value is None or not isinstance(value, expected_type):
                return ValidationResult(False, f"invalid_type:{field}")

        return ValidationResult(True, "ok")

    def validate_before_publish(self, schema_name: str, version: str, payload: dict[str, Any]) -> ValidationResult:
        result = self.validate(schema_name, version, payload)
        if not result.ok:
            logger.warning(
                "schema_validation_failed | schema=%s | version=%s | reason=%s",
                schema_name,
                version,
                result.message,
            )
        return result

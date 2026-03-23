from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ModelVersion:
    version: str
    created_at: str
    dataset_ref: str
    validation_metrics: dict[str, Any]
    status: str
    params: dict[str, Any]


class ModelRegistry:
    """File-based model registry with rollback support."""

    def __init__(self, registry_path: str = "reports/model_registry.json") -> None:
        self._path = Path(registry_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"active_version": None, "versions": []}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {"active_version": None, "versions": []}

    def _save(self, payload: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def register(self, *, version: str, dataset_ref: str, validation_metrics: dict[str, Any], status: str, params: dict[str, Any]) -> ModelVersion:
        registry = self._load()
        mv = ModelVersion(
            version=version,
            created_at=_utc_now_iso(),
            dataset_ref=dataset_ref,
            validation_metrics=validation_metrics,
            status=status,
            params=params,
        )
        versions = registry.get("versions", [])
        versions = [v for v in versions if v.get("version") != version]
        versions.append(asdict(mv))
        registry["versions"] = versions

        if status in {"prod", "canary"}:
            registry["active_version"] = version
        self._save(registry)
        return mv

    def set_status(self, version: str, status: str) -> bool:
        registry = self._load()
        changed = False
        for row in registry.get("versions", []):
            if row.get("version") == version:
                row["status"] = status
                changed = True
        if changed and status in {"prod", "canary"}:
            registry["active_version"] = version
        self._save(registry)
        return changed

    def rollback(self, target_version: str) -> bool:
        registry = self._load()
        has_target = any(v.get("version") == target_version for v in registry.get("versions", []))
        if not has_target:
            return False

        for row in registry.get("versions", []):
            if row.get("version") == target_version:
                row["status"] = "prod"
            elif row.get("status") == "prod":
                row["status"] = "retired"
        registry["active_version"] = target_version
        self._save(registry)
        return True

    def active_version(self) -> str | None:
        return self._load().get("active_version")

    def all_versions(self) -> list[dict[str, Any]]:
        return self._load().get("versions", [])

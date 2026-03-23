from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from infrastructure.platform.schema_registry import SchemaRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventPublishResult:
    accepted: bool
    event_id: str
    reason: str


class InternalEventBus:
    """In-process event bus with pub/sub, idempotency and structured logging."""

    def __init__(self, schema_registry: SchemaRegistry | None = None, dedupe_size: int = 20000) -> None:
        self._schema_registry = schema_registry or SchemaRegistry()
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._seen_ids: set[str] = set()
        self._order = deque(maxlen=dedupe_size)

    def subscribe(self, event_name: str, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(str(event_name), []).append(callback)

    def publish(
        self,
        event_name: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        schema_name: str | None = None,
        schema_version: str = "v1",
    ) -> EventPublishResult:
        eid = str(event_id or uuid.uuid4().hex)
        with self._lock:
            if eid in self._seen_ids:
                logger.info("event_duplicate_ignored | event_name=%s | event_id=%s", event_name, eid)
                return EventPublishResult(False, eid, "duplicate")

        if schema_name:
            validation = self._schema_registry.validate_before_publish(schema_name, schema_version, payload)
            if not validation.ok:
                logger.warning(
                    "event_rejected_contract | event_name=%s | event_id=%s | reason=%s",
                    event_name,
                    eid,
                    validation.message,
                )
                return EventPublishResult(False, eid, "contract_validation_failed")

        envelope = {
            "event_id": eid,
            "event_name": str(event_name),
            "timestamp": int(time.time()),
            "payload": payload,
            "schema": schema_name,
            "schema_version": schema_version,
        }

        with self._lock:
            self._seen_ids.add(eid)
            self._order.append(eid)
            while len(self._order) > self._order.maxlen:
                old = self._order.popleft()
                self._seen_ids.discard(old)
            callbacks = list(self._subscribers.get(str(event_name), []))

        logger.info(
            "event_published | event_name=%s | event_id=%s | schema=%s | version=%s",
            event_name,
            eid,
            schema_name,
            schema_version,
        )

        for callback in callbacks:
            try:
                callback(envelope)
            except Exception as exc:
                logger.exception("event_subscriber_failed | event_name=%s | event_id=%s | error=%s", event_name, eid, exc)

        return EventPublishResult(True, eid, "ok")


_GLOBAL_EVENT_BUS = InternalEventBus()


def get_event_bus() -> InternalEventBus:
    return _GLOBAL_EVENT_BUS

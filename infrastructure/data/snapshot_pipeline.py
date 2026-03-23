from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable

from infrastructure.data.provider_runtime import (
    get_budget_manager,
    get_provider_metrics,
    get_refresh_priority_registry,
)

logger = logging.getLogger(__name__)


def _now() -> float:
    return time.time()


def _interval_seconds(priority: str) -> int:
    if priority == "hot":
        return int(os.getenv("SNAPSHOT_HOT_INTERVAL_SEC", "45"))
    if priority == "inactive":
        return int(os.getenv("SNAPSHOT_INACTIVE_INTERVAL_SEC", "600"))
    return int(os.getenv("SNAPSHOT_NORMAL_INTERVAL_SEC", "180"))


@dataclass
class SnapshotTask:
    ticker: str
    priority: str = "normal"
    next_run_ts: float = 0.0
    last_access_ts: float = 0.0


class SnapshotScheduler:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, SnapshotTask] = {}
        self._refresh_handler: Callable[[str, str], bool] | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._degrade_threshold = float(os.getenv("SNAPSHOT_DEGRADE_USAGE_RATIO", "0.9"))
        self._inactive_after_sec = int(os.getenv("SNAPSHOT_INACTIVE_AFTER_SEC", "1800"))
        self._batch_size = max(1, int(os.getenv("SNAPSHOT_BATCH_SIZE", "2")))

    def set_refresh_handler(self, handler: Callable[[str, str], bool]) -> None:
        self._refresh_handler = handler

    def start(self) -> None:
        if not self._is_enabled():
            return
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, name="snapshot-scheduler", daemon=True)
            self._thread.start()
            logger.info("Snapshot scheduler started")

    def register_tickers(self, tickers: list[str], priority: str = "normal", immediate: bool = True) -> None:
        now_ts = _now()
        with self._lock:
            for raw in tickers:
                ticker = str(raw or "").strip().upper()
                if not ticker:
                    continue
                interval = _interval_seconds(priority)
                task = self._tasks.get(ticker) or SnapshotTask(ticker=ticker)
                task.priority = priority
                task.last_access_ts = now_ts
                task.next_run_ts = now_ts if immediate else now_ts + interval
                self._tasks[ticker] = task

    def mark_access(self, ticker: str, priority: str = "normal") -> None:
        ticker = str(ticker or "").strip().upper()
        if not ticker:
            return
        now_ts = _now()
        with self._lock:
            task = self._tasks.get(ticker) or SnapshotTask(ticker=ticker)
            if priority == "hot" or task.priority != "hot":
                task.priority = priority
            task.last_access_ts = now_ts
            if task.next_run_ts <= 0:
                task.next_run_ts = now_ts + _interval_seconds(task.priority)
            self._tasks[ticker] = task

    def request_revalidate(self, ticker: str, reason: str, priority: str = "normal", immediate: bool = False) -> None:
        ticker = str(ticker or "").strip().upper()
        if not ticker:
            return
        self.mark_access(ticker, priority=priority)
        if immediate:
            with self._lock:
                task = self._tasks.get(ticker)
                if task is not None:
                    task.next_run_ts = _now()
                    self._tasks[ticker] = task
        logger.info(
            "snapshot revalidate requested | ticker=%s | priority=%s | immediate=%s | reason=%s",
            ticker,
            priority,
            immediate,
            reason,
        )

    @staticmethod
    def _is_enabled() -> bool:
        return os.getenv("SNAPSHOT_PIPELINE_ENABLED", "1").strip().lower() not in {"0", "false", "no"}

    def _run_loop(self) -> None:
        while True:
            if not self._running:
                return

            handler = self._refresh_handler
            if handler is None:
                time.sleep(1.0)
                continue

            budget = get_budget_manager().snapshot()
            if float(budget.get("usage_ratio", 0.0)) >= self._degrade_threshold:
                get_provider_metrics().record_degraded_mode()
                logger.warning(
                    "snapshot scheduler degraded | usage_ratio=%.3f | threshold=%.3f",
                    float(budget.get("usage_ratio", 0.0)),
                    self._degrade_threshold,
                )
                time.sleep(2.0)
                continue

            due = self._pop_due_tasks()
            if not due:
                time.sleep(0.75)
                continue

            for task in due:
                try:
                    ok = handler(task.ticker, "scheduled_refresh")
                    logger.info(
                        "snapshot refresh %s | ticker=%s | priority=%s",
                        "ok" if ok else "failed",
                        task.ticker,
                        task.priority,
                    )
                except Exception as exc:  # pragma: no cover - defensive for daemon thread
                    logger.warning("snapshot refresh exception | ticker=%s | error=%s", task.ticker, exc)
                finally:
                    self._reschedule(task)

    def _pop_due_tasks(self) -> list[SnapshotTask]:
        now_ts = _now()
        out: list[SnapshotTask] = []
        with self._lock:
            for task in self._tasks.values():
                if now_ts - task.last_access_ts > self._inactive_after_sec:
                    task.priority = "inactive"
                elif task.priority == "inactive":
                    task.priority = "normal"

            prio = get_refresh_priority_registry()
            ordered = sorted(
                self._tasks.values(),
                key=lambda t: (
                    t.next_run_ts,
                    -prio.score_for_ticker(t.ticker),
                ),
            )
            for task in ordered:
                if len(out) >= self._batch_size:
                    break
                if task.next_run_ts <= now_ts:
                    out.append(task)
        return out

    def _reschedule(self, task: SnapshotTask) -> None:
        interval = _interval_seconds(task.priority)
        jitter_max = max(3, int(interval * 0.2))
        jitter = (hash(f"{task.ticker}:{int(_now())}") % jitter_max)
        task.next_run_ts = _now() + interval + jitter
        with self._lock:
            self._tasks[task.ticker] = task


_SCHEDULER = SnapshotScheduler()


def get_snapshot_scheduler() -> SnapshotScheduler:
    return _SCHEDULER

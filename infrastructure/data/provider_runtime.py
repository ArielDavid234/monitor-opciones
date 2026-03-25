from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable

from infrastructure.platform.business_value import estimate_refresh_priority_score, get_plan_policy

from config.settings import get_settings

logger = logging.getLogger(__name__)

_REQUEST_CHANNEL: ContextVar[str] = ContextVar("provider_request_channel", default="background")


class CircuitOpenError(RuntimeError):
    """Raised when provider circuit breaker is open and blocks provider calls."""


@contextmanager
def request_channel(channel: str):
    """Scope para clasificar requests de proveedor (live_scanning/background)."""
    token = _REQUEST_CHANNEL.set(channel or "background")
    try:
        yield
    finally:
        _REQUEST_CHANNEL.reset(token)


def get_request_channel() -> str:
    return _REQUEST_CHANNEL.get()


@dataclass
class BudgetDecision:
    allowed: bool
    reason: str | None = None
    retry_in_seconds: int = 0


class BudgetManager:
    """Budget manager por minuto para controlar consumo de cuota del proveedor de datos."""

    def __init__(
        self,
        total_per_minute: int | None = None,
        reserved_live_scanning: int | None = None,
        background_quota: int | None = None,
        high_watermark: float | None = None,
    ) -> None:
        cfg = get_settings()
        _total_default = int(getattr(cfg, "provider_quota_total_per_min", 240))
        _live_default = int(getattr(cfg, "provider_quota_reserved_live_scanning", 160))
        _bg_default = int(getattr(cfg, "provider_quota_background", max(_total_default - _live_default, 1)))
        _wm_default = float(getattr(cfg, "provider_quota_high_watermark", 0.85))

        self.total_per_minute = total_per_minute or int(os.getenv("PROVIDER_QUOTA_TOTAL_PER_MIN", str(_total_default)))
        self.reserved_live_scanning = reserved_live_scanning or int(
            os.getenv("PROVIDER_QUOTA_RESERVED_LIVE_SCANNING", str(_live_default))
        )
        self.background_quota = background_quota or int(
            os.getenv("PROVIDER_QUOTA_BACKGROUND", str(_bg_default))
        )
        self.high_watermark = high_watermark or float(os.getenv("PROVIDER_QUOTA_HIGH_WATERMARK", str(_wm_default)))

        self._lock = threading.Lock()
        self._minute_bucket = int(time.time() // 60)
        self._total_used = 0
        self._live_used = 0
        self._background_used = 0
        self._blocked = 0

    def _rotate_if_needed(self) -> None:
        current_bucket = int(time.time() // 60)
        if current_bucket != self._minute_bucket:
            self._minute_bucket = current_bucket
            self._total_used = 0
            self._live_used = 0
            self._background_used = 0
            self._blocked = 0

    def acquire(self, endpoint: str, ticker: str, critical: bool = False, channel: str | None = None) -> BudgetDecision:
        req_channel = channel or get_request_channel()
        with self._lock:
            self._rotate_if_needed()
            usage_ratio = self._total_used / max(self.total_per_minute, 1)
            sec_to_next_min = max(1, 60 - (int(time.time()) % 60))

            if self._total_used >= self.total_per_minute:
                self._blocked += 1
                logger.warning(
                    "budget deny | provider=yfinance | endpoint=%s | ticker=%s | channel=%s | reason=quota_total | retry_in=%ds",
                    endpoint,
                    ticker,
                    req_channel,
                    sec_to_next_min,
                )
                return BudgetDecision(False, "quota_total", sec_to_next_min)

            if not critical and usage_ratio >= self.high_watermark:
                self._blocked += 1
                logger.warning(
                    "budget deny | provider=yfinance | endpoint=%s | ticker=%s | channel=%s | reason=high_watermark | retry_in=%ds",
                    endpoint,
                    ticker,
                    req_channel,
                    sec_to_next_min,
                )
                return BudgetDecision(False, "high_watermark", sec_to_next_min)

            if req_channel != "live_scanning" and self._background_used >= self.background_quota and not critical:
                self._blocked += 1
                logger.warning(
                    "budget deny | provider=yfinance | endpoint=%s | ticker=%s | channel=%s | reason=background_quota | retry_in=%ds",
                    endpoint,
                    ticker,
                    req_channel,
                    sec_to_next_min,
                )
                return BudgetDecision(False, "background_quota", sec_to_next_min)

            self._total_used += 1
            if req_channel == "live_scanning":
                self._live_used += 1
            else:
                self._background_used += 1

            logger.info(
                "budget consume | provider=yfinance | endpoint=%s | ticker=%s | channel=%s | total=%d/%d | live=%d/%d | background=%d/%d",
                endpoint,
                ticker,
                req_channel,
                self._total_used,
                self.total_per_minute,
                self._live_used,
                self.reserved_live_scanning,
                self._background_used,
                self.background_quota,
            )
            return BudgetDecision(True)

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            self._rotate_if_needed()
            return {
                "quota_total_minute": self.total_per_minute,
                "quota_reserved_live_scanning": self.reserved_live_scanning,
                "quota_background": self.background_quota,
                "used_total": self._total_used,
                "used_live": self._live_used,
                "used_background": self._background_used,
                "blocked": self._blocked,
                "usage_ratio": round(self._total_used / max(self.total_per_minute, 1), 4),
            }


class ProviderMetrics:
    """Métricas runtime para observabilidad de proveedor y scanner."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._provider_request_count = 0
        self._provider_429_count = 0
        self._chain_fetch_failures = 0
        self._provider_request_denied_count = 0
        self._degraded_mode_activations = 0
        self._snapshot_hits = 0
        self._snapshot_misses = 0
        self._429_timestamps = deque(maxlen=10000)

    def record_request(self, status: str) -> None:
        with self._lock:
            self._provider_request_count += 1
            if status == "429":
                self._provider_429_count += 1
                self._429_timestamps.append(time.time())
            elif status == "denied":
                self._provider_request_denied_count += 1

    def record_chain_failure(self) -> None:
        with self._lock:
            self._chain_fetch_failures += 1

    def record_degraded_mode(self) -> None:
        with self._lock:
            self._degraded_mode_activations += 1

    def record_snapshot_access(self, hit: bool) -> None:
        with self._lock:
            if hit:
                self._snapshot_hits += 1
            else:
                self._snapshot_misses += 1

    def get_429_last_5m(self) -> int:
        with self._lock:
            now_ts = time.time()
            while self._429_timestamps and now_ts - self._429_timestamps[0] > 300:
                self._429_timestamps.popleft()
            return len(self._429_timestamps)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            total_snapshot = self._snapshot_hits + self._snapshot_misses
            ratio = float(self._snapshot_hits / total_snapshot) if total_snapshot else 0.0
            return {
                "provider_request_count": self._provider_request_count,
                "provider_429_count": self._provider_429_count,
                "provider_request_denied_count": self._provider_request_denied_count,
                "chain_fetch_failures": self._chain_fetch_failures,
                "degraded_mode_activations": self._degraded_mode_activations,
                "snapshot_hits": self._snapshot_hits,
                "snapshot_misses": self._snapshot_misses,
                "snapshot_hit_ratio": round(ratio, 4),
            }


class ProviderCircuitBreaker:
    """Circuit breaker simple para evitar cascadas de error al proveedor."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._failure_threshold = int(
            os.getenv(
                "PROVIDER_CIRCUIT_FAILURE_THRESHOLD",
                str(getattr(cfg, "provider_circuit_failure_threshold", 5)),
            )
        )
        self._recovery_timeout_sec = int(
            os.getenv(
                "PROVIDER_CIRCUIT_RECOVERY_TIMEOUT_SEC",
                str(getattr(cfg, "provider_circuit_recovery_timeout_sec", 90)),
            )
        )
        self._half_open_max_probe = int(
            os.getenv(
                "PROVIDER_CIRCUIT_HALF_OPEN_MAX_PROBE",
                str(getattr(cfg, "provider_circuit_half_open_max_probe", 2)),
            )
        )

        self._lock = threading.Lock()
        self._state = "closed"
        self._consecutive_failures = 0
        self._opened_at_ts = 0.0
        self._half_open_probes = 0

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == "closed":
                return True

            if self._state == "open":
                if time.time() - self._opened_at_ts >= self._recovery_timeout_sec:
                    self._state = "half_open"
                    self._half_open_probes = 0
                    logger.warning("provider circuit transition | state=half_open")
                else:
                    return False

            if self._state == "half_open":
                if self._half_open_probes >= self._half_open_max_probe:
                    return False
                self._half_open_probes += 1
                return True

            return True

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._half_open_probes = 0
            if self._state != "closed":
                logger.info("provider circuit transition | state=closed")
            self._state = "closed"

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == "half_open":
                self._state = "open"
                self._opened_at_ts = time.time()
                self._half_open_probes = 0
                logger.error("provider circuit transition | state=open | reason=half_open_failure")
                return

            if self._consecutive_failures >= self._failure_threshold:
                self._state = "open"
                self._opened_at_ts = time.time()
                self._half_open_probes = 0
                logger.error(
                    "provider circuit transition | state=open | failures=%d | threshold=%d",
                    self._consecutive_failures,
                    self._failure_threshold,
                )

    def snapshot(self) -> dict[str, int | float | str]:
        with self._lock:
            remaining = 0
            if self._state == "open":
                remaining = max(0, self._recovery_timeout_sec - int(time.time() - self._opened_at_ts))
            return {
                "state": self._state,
                "consecutive_failures": self._consecutive_failures,
                "recovery_timeout_sec": self._recovery_timeout_sec,
                "retry_after_sec": remaining,
                "half_open_probes": self._half_open_probes,
            }


class ScanMetadataRegistry:
    """Registro en memoria de metadata de escaneos para trazabilidad/auditoria."""

    def __init__(self, max_items: int = 2000) -> None:
        self._lock = threading.Lock()
        self._items = deque(maxlen=max_items)

    def record(
        self,
        *,
        ticker: str,
        provider: str,
        market_schema_version: str,
        snapshot_schema_version: str,
        source: str,
        latency_ms: float,
    ) -> None:
        row = {
            "ts": int(time.time()),
            "ticker": str(ticker or "").upper(),
            "provider": provider,
            "market_schema_version": market_schema_version,
            "snapshot_schema_version": snapshot_schema_version,
            "source": source,
            "latency_ms": round(float(latency_ms), 2),
        }
        with self._lock:
            self._items.append(row)

    def recent(self, limit: int = 100) -> list[dict]:
        with self._lock:
            items = list(self._items)
        return items[-max(1, limit):]


class CrossUserTickerDedupe:
    """Track repeated ticker demand to reduce duplicated live fetches across users."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._window_sec = int(
            os.getenv(
                "CROSS_USER_DEDUPE_WINDOW_SEC",
                str(getattr(cfg, "cross_user_dedupe_window_sec", 45)),
            )
        )
        self._lock = threading.Lock()
        self._ticker_hits: dict[str, deque[float]] = {}
        self._ticker_last_seen: dict[str, float] = {}

    def register_request(self, ticker: str) -> dict[str, Any]:
        now_ts = time.time()
        tk = str(ticker or "").upper()
        if not tk:
            return {"dedupe_candidate": False, "recent_hits": 0}

        with self._lock:
            q = self._ticker_hits.get(tk)
            if q is None:
                q = deque(maxlen=500)
                self._ticker_hits[tk] = q

            q.append(now_ts)
            while q and now_ts - q[0] > self._window_sec:
                q.popleft()

            self._ticker_last_seen[tk] = now_ts
            recent_hits = len(q)

        return {
            "dedupe_candidate": recent_hits > 1,
            "recent_hits": recent_hits,
            "window_sec": self._window_sec,
        }

    def should_defer_live_fetch(self, ticker: str) -> bool:
        tk = str(ticker or "").upper()
        if not tk:
            return False
        now_ts = time.time()
        with self._lock:
            q = self._ticker_hits.get(tk)
            if not q:
                return False
            while q and now_ts - q[0] > self._window_sec:
                q.popleft()
            return len(q) >= 2


@dataclass
class _InFlightCall:
    event: threading.Event
    done: bool = False
    result: Any = None
    error: BaseException | None = None


class SingleFlightGroup:
    """Coalesce concurrent requests for the same key into a single execution."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inflight: dict[str, _InFlightCall] = {}

    def do(self, key: str, fn: Callable[[], Any]) -> Any:
        wait_call: _InFlightCall | None = None
        with self._lock:
            existing = self._inflight.get(key)
            if existing is not None:
                wait_call = existing
            else:
                call = _InFlightCall(event=threading.Event())
                self._inflight[key] = call

        if wait_call is not None:
            wait_call.event.wait(timeout=30)
            if wait_call.error is not None:
                raise wait_call.error
            return wait_call.result

        with self._lock:
            leader_call = self._inflight[key]

        try:
            leader_call.result = fn()
            return leader_call.result
        except BaseException as exc:
            leader_call.error = exc
            raise
        finally:
            leader_call.done = True
            leader_call.event.set()
            with self._lock:
                self._inflight.pop(key, None)


class RefreshPriorityRegistry:
    """Commercial-aware refresh priority score per ticker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, dict[str, Any]] = {}

    def register_demand(self, ticker: str, user_plan: str) -> dict[str, Any]:
        now_ts = time.time()
        tk = str(ticker or "").upper()
        if not tk:
            return {"score": 0.0, "ticker": ""}

        plan_weight = get_plan_policy(user_plan).commercial_weight
        with self._lock:
            row = self._rows.get(tk) or {
                "demand_users": 0,
                "activity_5m": deque(maxlen=1000),
                "last_activity_ts": now_ts,
                "commercial_weight_sum": 0.0,
            }

            row["demand_users"] = int(row.get("demand_users", 0)) + 1
            row["last_activity_ts"] = now_ts
            row["commercial_weight_sum"] = float(row.get("commercial_weight_sum", 0.0)) + plan_weight
            activity_5m = row.get("activity_5m")
            if not isinstance(activity_5m, deque):
                activity_5m = deque(maxlen=1000)
            activity_5m.append(now_ts)
            while activity_5m and now_ts - activity_5m[0] > 300:
                activity_5m.popleft()
            row["activity_5m"] = activity_5m
            self._rows[tk] = row

            demand_users = int(row.get("demand_users", 0))
            recent_activity_seconds = max(0.0, now_ts - float(row.get("last_activity_ts", now_ts)))
            activity_count_5m = len(activity_5m)

        score = estimate_refresh_priority_score(
            user_plan=user_plan,
            demand_users=demand_users,
            recent_activity_seconds=recent_activity_seconds,
            activity_count_5m=activity_count_5m,
        )
        return {
            "ticker": tk,
            "score": score,
            "demand_users": demand_users,
            "activity_count_5m": activity_count_5m,
        }

    def score_for_ticker(self, ticker: str) -> float:
        tk = str(ticker or "").upper()
        if not tk:
            return 0.0

        now_ts = time.time()
        with self._lock:
            row = self._rows.get(tk)
            if not row:
                return 0.0
            activity_5m = row.get("activity_5m")
            if not isinstance(activity_5m, deque):
                return 0.0
            while activity_5m and now_ts - activity_5m[0] > 300:
                activity_5m.popleft()
            demand_users = int(row.get("demand_users", 0))
            activity_count_5m = len(activity_5m)
            recent_activity_seconds = max(0.0, now_ts - float(row.get("last_activity_ts", now_ts)))
            avg_weight = float(row.get("commercial_weight_sum", 0.0)) / max(demand_users, 1)

        implied_plan = "enterprise" if avg_weight >= 2.7 else ("pro" if avg_weight >= 1.7 else "free")
        return estimate_refresh_priority_score(
            user_plan=implied_plan,
            demand_users=demand_users,
            recent_activity_seconds=recent_activity_seconds,
            activity_count_5m=activity_count_5m,
        )


_BUDGET = BudgetManager()
_METRICS = ProviderMetrics()
_CIRCUIT = ProviderCircuitBreaker()
_SCAN_META = ScanMetadataRegistry()
_CROSS_USER_DEDUPE = CrossUserTickerDedupe()
_SINGLE_FLIGHT = SingleFlightGroup()
_REFRESH_PRIORITY = RefreshPriorityRegistry()


def get_budget_manager() -> BudgetManager:
    return _BUDGET


def get_provider_metrics() -> ProviderMetrics:
    return _METRICS


def get_provider_circuit() -> ProviderCircuitBreaker:
    return _CIRCUIT


def record_scan_metadata(
    *,
    ticker: str,
    provider: str,
    market_schema_version: str,
    snapshot_schema_version: str,
    source: str,
    latency_ms: float,
) -> None:
    _SCAN_META.record(
        ticker=ticker,
        provider=provider,
        market_schema_version=market_schema_version,
        snapshot_schema_version=snapshot_schema_version,
        source=source,
        latency_ms=latency_ms,
    )


def get_recent_scan_metadata(limit: int = 100) -> list[dict]:
    return _SCAN_META.recent(limit=limit)


def get_cross_user_dedupe() -> CrossUserTickerDedupe:
    return _CROSS_USER_DEDUPE


def get_single_flight_group() -> SingleFlightGroup:
    return _SINGLE_FLIGHT


def get_refresh_priority_registry() -> RefreshPriorityRegistry:
    return _REFRESH_PRIORITY

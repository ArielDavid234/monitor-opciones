from __future__ import annotations

import os
import sys


def _fenv(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def main() -> int:
    canary_error_rate = _fenv("CANARY_ERROR_RATE_PCT", 0.0)
    canary_p90_ms = _fenv("CANARY_P90_MS", 0.0)

    max_error_rate = _fenv("CANARY_MAX_ERROR_RATE_PCT", 2.0)
    max_p90_ms = _fenv("CANARY_MAX_P90_MS", 60000)

    print(
        {
            "error_rate_pct": canary_error_rate,
            "p90_ms": canary_p90_ms,
            "max_error_rate_pct": max_error_rate,
            "max_p90_ms": max_p90_ms,
        }
    )

    if canary_error_rate > max_error_rate:
        print("Canary failed: error rate above threshold")
        return 2
    if canary_p90_ms > max_p90_ms:
        print("Canary failed: p90 latency above threshold")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

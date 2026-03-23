from __future__ import annotations

import os
import sys


def main() -> int:
    freeze_enabled = os.getenv("CHANGE_FREEZE_ENABLED", "true").strip().lower() in {"1", "true", "yes"}
    if not freeze_enabled:
        print("Change freeze disabled")
        return 0

    try:
        burn_7d = float(os.getenv("ERROR_RATE_7D_PCT", "0"))
    except ValueError:
        burn_7d = 0.0

    try:
        max_allowed = float(os.getenv("ERROR_BUDGET_MAX_ERROR_RATE_PCT_7D", "2.0"))
    except ValueError:
        max_allowed = 2.0

    print({"error_rate_7d_pct": burn_7d, "max_allowed_pct": max_allowed})
    if burn_7d > max_allowed:
        print("Error budget exhausted: change freeze active")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

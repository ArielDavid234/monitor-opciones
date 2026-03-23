from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.auth import SupabaseAuth
from infrastructure.platform.business_value import export_daily_business_summary


def main() -> int:
    auth = SupabaseAuth()
    out = export_daily_business_summary(auth)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

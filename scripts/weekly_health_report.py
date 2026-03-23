from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.data.provider_runtime import get_provider_metrics, get_recent_scan_metadata
from infrastructure.platform.business_value import aggregate_business_metrics
from infrastructure.platform.health import global_health_status
from core.auth import SupabaseAuth


def main() -> int:
    now = datetime.now(timezone.utc)
    out_dir = Path("reports") / "weekly_health"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"weekly_health_{now.strftime('%Y%m%d_%H%M%S')}.md"

    health = global_health_status()
    metrics = get_provider_metrics().snapshot()
    scan_meta = get_recent_scan_metadata(limit=200)
    business = aggregate_business_metrics(SupabaseAuth(), lookback_days=7)

    content = [
        "# Weekly Health Report",
        "",
        f"- generated_at_utc: {now.isoformat()}",
        f"- overall_health: {health.get('overall')}",
        "",
        "## Provider Metrics",
        "```json",
        json.dumps(metrics, indent=2, sort_keys=True),
        "```",
        "",
        "## Health Checks",
        "```json",
        json.dumps(health, indent=2, sort_keys=True),
        "```",
        "",
        "## Recent Scan Metadata",
        "```json",
        json.dumps(scan_meta[-25:], indent=2, sort_keys=True),
        "```",
        "",
        "## Business Metrics",
        "```json",
        json.dumps(business, indent=2, sort_keys=True),
        "```",
    ]

    out_path.write_text("\n".join(content), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

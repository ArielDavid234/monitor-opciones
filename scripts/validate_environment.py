from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.platform.security import env_by_stage, validate_startup_secrets


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate environment and critical secrets")
    parser.add_argument("--stage", default="dev", choices=["dev", "staging", "prod"], help="Environment stage")
    args = parser.parse_args()

    required = env_by_stage(args.stage)
    errors = validate_startup_secrets()

    print(json.dumps({"stage": args.stage, "required_keys": required, "errors": errors}, indent=2, sort_keys=True))
    if errors:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

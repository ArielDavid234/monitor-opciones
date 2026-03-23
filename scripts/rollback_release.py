from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback release to previous stable version")
    parser.add_argument("--environment", required=True, choices=["staging", "production"])
    parser.add_argument("--target", required=True, help="Target stable version/tag")
    args = parser.parse_args()

    cmd = os.getenv("ROLLBACK_CMD", "").strip()
    if not cmd:
        print(f"[DRY-RUN] rollback environment={args.environment} target={args.target} (ROLLBACK_CMD not configured)")
        return 0

    cmd_full = cmd.replace("{environment}", args.environment).replace("{target}", args.target)
    proc = subprocess.run(cmd_full, shell=True)
    return int(proc.returncode)


if __name__ == "__main__":
    sys.exit(main())

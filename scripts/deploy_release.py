from __future__ import annotations

import argparse
import os
import subprocess
import sys


def run_cmd(cmd: str) -> int:
    if not cmd.strip():
        return 0
    proc = subprocess.run(cmd, shell=True)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy release by environment")
    parser.add_argument("--environment", required=True, choices=["staging", "production"])
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    env_key = "DEPLOY_CMD_STAGING" if args.environment == "staging" else "DEPLOY_CMD_PRODUCTION"
    cmd = os.getenv(env_key, "").strip()

    if not cmd:
        print(f"[DRY-RUN] {args.environment} deploy version={args.version} (no {env_key} configured)")
        return 0

    cmd_full = cmd.replace("{version}", args.version)
    print(f"Executing deploy command for {args.environment}")
    return run_cmd(cmd_full)


if __name__ == "__main__":
    sys.exit(main())

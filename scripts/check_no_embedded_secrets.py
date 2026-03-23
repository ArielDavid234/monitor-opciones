from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INCLUDE_SUFFIXES = {".py", ".md", ".txt", ".yml", ".yaml", ".toml"}
EXCLUDE_PARTS = {".git", ".venv", "__pycache__", ".app_cache"}

PATTERNS = [
    re.compile(r"(?i)(api[_-]?key\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"])") ,
    re.compile(r"(?i)(token\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"])") ,
    re.compile(r"(?i)(secret\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"])") ,
    re.compile(r"AKIA[0-9A-Z]{16}"),
]

ALLOWLIST = (
    "<tu_api_key>",
    "example",
    "dummy",
    "placeholder",
)


def should_scan(path: pathlib.Path) -> bool:
    if path.suffix.lower() not in INCLUDE_SUFFIXES:
        return False
    p = str(path)
    return not any(part in p for part in EXCLUDE_PARTS)


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_scan(path):
            continue
        if path.name in {".env.example"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for idx, line in enumerate(text.splitlines(), start=1):
            line_lower = line.lower()
            if any(tok in line_lower for tok in ALLOWLIST):
                continue
            if any(p.search(line) for p in PATTERNS):
                findings.append(f"{path.relative_to(ROOT)}:{idx}")

    if findings:
        print("Embedded secret-like values detected:")
        for f in findings:
            print(f" - {f}")
        return 2

    print("No embedded secrets detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

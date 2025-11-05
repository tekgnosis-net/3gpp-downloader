#!/usr/bin/env python3
"""Update project version markers for semantic-release."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def update_pyproject(version: str) -> None:
    target = Path("pyproject.toml")
    text = target.read_text(encoding="utf-8")
    pattern = re.compile(r'^(version\s*=\s*")[^"]+("\s*)$', re.MULTILINE)
    replaced, count = pattern.subn(lambda m: f"{m.group(1)}{version}{m.group(2)}", text, count=1)
    if count == 0:
        raise RuntimeError("Failed to locate version field in pyproject.toml")
    target.write_text(replaced, encoding="utf-8")


def update_frontend_package(version: str) -> None:
    target = Path("frontend/package.json")
    data = json.loads(target.read_text(encoding="utf-8"))
    data["version"] = version
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: update_version.py <version>")
    version = sys.argv[1]
    update_pyproject(version)
    update_frontend_package(version)


if __name__ == "__main__":
    main()

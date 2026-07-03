#!/usr/bin/env python3
"""Verify all committed test fixtures exist on disk."""

from __future__ import annotations

import json
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def iter_expected_fixture_paths() -> list[Path]:
    with open(FIXTURES_DIR / "fixtures.json") as f:
        fixtures_data = json.load(f)

    paths: list[Path] = []
    for endpoint, fixtures in fixtures_data.items():
        if endpoint == "$schema":
            continue
        for fixture_name in fixtures:
            paths.append(FIXTURES_DIR / endpoint / f"{fixture_name}.jkr")

    paths.append(FIXTURES_DIR / "load" / "corrupted.jkr")
    return paths


def main() -> int:
    missing = [path for path in iter_expected_fixture_paths() if not path.exists()]
    if not missing:
        print(f"All {len(iter_expected_fixture_paths())} fixtures present.")
        return 0

    print(f"Missing {len(missing)} fixture(s):", file=sys.stderr)
    for path in missing:
        print(f"  - {path.relative_to(FIXTURES_DIR.parent)}", file=sys.stderr)
    print(
        "\nGenerate with: balatrobot serve --fast --debug  "
        "then  python tests/fixtures/generate.py",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

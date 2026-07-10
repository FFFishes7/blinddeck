"""Read and format the native Balatro challenge catalog."""

from __future__ import annotations

import json
import sys
from typing import Any

from bot_client import APIError, rpc
from envelope import CHALLENGES_FORMAT, build_challenges_envelope, build_error_envelope

JSON_FLAG = "--json"


def _parse_argv(argv: list[str]) -> bool:
    if not argv:
        return False
    if argv == [JSON_FLAG]:
        return True
    raise ValueError("usage: challenges [--json]")


def format_challenges(catalog: list[dict[str, Any]]) -> str:
    unlocked = sum(entry.get("unlocked") is True for entry in catalog)
    completed = sum(entry.get("completed") is True for entry in catalog)
    lines = [
        f"challenges: {unlocked}/{len(catalog)} unlocked · {completed}/{len(catalog)} completed"
    ]
    for entry in catalog:
        status = "unlocked" if entry.get("unlocked") else "locked"
        if entry.get("completed"):
            status += ", completed"
        index = entry.get("index", "?")
        challenge_id = entry.get("id", "?")
        name = entry.get("name") or challenge_id
        lines.append(f"[{index}] {challenge_id} — {name} ({status})")
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        json_out = _parse_argv(sys.argv[1:])
        result = rpc("challenges")
        catalog = result.get("challenges") if isinstance(result, dict) else None
        if not isinstance(catalog, list):
            raise ValueError("challenges response did not contain a challenge list")
        envelope = build_challenges_envelope(catalog)
        if json_out:
            print(json.dumps(envelope, ensure_ascii=False))
        else:
            print(format_challenges(catalog), end="")
        return 0
    except APIError as e:
        print(
            json.dumps(
                build_error_envelope(e.name, e.message, fmt=CHALLENGES_FORMAT),
                ensure_ascii=False,
            )
        )
        return 1
    except ValueError as e:
        print(
            json.dumps(
                build_error_envelope("BAD_REQUEST", str(e), fmt=CHALLENGES_FORMAT),
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

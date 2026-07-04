"""Detail query commands (`query hands`, `query deck`, …).

Default output is a compact table for common queries; `--json` returns structured data.
User docs: detail queries — see PLAY.md § Command reference.
"""

from __future__ import annotations

import json
import sys

from bot_client import APIError, rpc
from envelope import QUERY_FORMAT, build_error_envelope, build_query_envelope
from layers import QUERY_EXTRACTORS, available_queries, extract_query, poll_until_stable

JSON_FLAG = "--json"


def _parse_argv(argv: list[str]) -> tuple[list[str], bool]:
    json_out = False
    rest: list[str] = []
    for arg in argv:
        if arg == JSON_FLAG:
            json_out = True
        else:
            rest.append(arg)
    return rest, json_out


def _format_hands(data: dict) -> str:
    rows = sorted(data.items(), key=lambda kv: kv[1].get("order", 99))
    lines = ["hand                lvl  chips  mult  played"]
    for name, info in rows:
        lines.append(
            f"{name:<20s}{info.get('level', 0):>3d}{info.get('chips', 0):>7d}"
            f"{info.get('mult', 0):>6d}{info.get('played', 0):>8d}"
        )
    return "\n".join(lines)


def _format_blinds(data: dict) -> str:
    order = ["small", "big", "boss"]
    lines = ["blind        target  status      effect"]
    for key in order:
        b = data.get(key)
        if not b:
            continue
        name = b.get("name", key)
        score = b.get("score", "?")
        status = b.get("status", "?")
        effect = b.get("effect") or ""
        tag = b.get("tag_name") or ""
        suffix = f" [skip: {tag} — {b.get('tag_effect', '')}]" if tag else ""
        lines.append(f"{name:<13s}{str(score):>7s}  {status:<11s} {effect}{suffix}")
    return "\n".join(lines)


def _format(name: str, data: dict) -> str | None:
    if name == "hands":
        return _format_hands(data)
    if name == "blinds":
        return _format_blinds(data)
    return None


def main() -> int:
    args, json_out = _parse_argv(sys.argv[1:])
    if not args:
        print(
            json.dumps(
                build_error_envelope(
                    "BAD_REQUEST",
                    "usage: query.py deck|hands|blinds|used_vouchers|seed [--json]",
                    fmt=QUERY_FORMAT,
                ),
                ensure_ascii=False,
            )
        )
        return 2

    name = args[0].lower()
    if name not in QUERY_EXTRACTORS:
        print(
            json.dumps(
                build_error_envelope(
                    "BAD_REQUEST", f"unknown query: {name}", fmt=QUERY_FORMAT
                ),
                ensure_ascii=False,
            )
        )
        return 2

    try:
        raw = poll_until_stable(lambda: rpc("gamestate"))
        state = raw.get("state", "UNKNOWN")
        allowed = {q["name"] for q in available_queries(state)}
        if name not in allowed:
            print(
                json.dumps(
                    build_error_envelope(
                        "INVALID_STATE",
                        f"query {name!r} not available in state {state!r}",
                        fmt=QUERY_FORMAT,
                    ),
                    ensure_ascii=False,
                )
            )
            return 1
        data = extract_query(raw, name)
        envelope = build_query_envelope(name, data)
        formatted = None if json_out else _format(name, data)
        if formatted:
            print(formatted)
        else:
            print(json.dumps(envelope, ensure_ascii=False))
        return 0
    except APIError as e:
        print(
            json.dumps(
                build_error_envelope(e.name, e.message, fmt=QUERY_FORMAT),
                ensure_ascii=False,
            )
        )
        return 1
    except TimeoutError as e:
        print(
            json.dumps(
                build_error_envelope("TIMEOUT", str(e), fmt=QUERY_FORMAT),
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

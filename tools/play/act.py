"""Friendly action dispatcher: `act.py METHOD [args...]` → execute → compact summary.

Replaces the old act.py that required a JSON string argument. Positional
args are parsed by ``commands.build_params`` so callers never have to quote
JSON on the PowerShell command line.

Examples (via bot.ps1, which forwards unknown subcommands here):
    bot.ps1 start RED WHITE
    bot.ps1 play 0 1 2 3 4
    bot.ps1 buy card 0
    bot.ps1 pack 0
    bot.ps1 pack skip

Pass ``--json`` to print the raw play envelope instead of the compact summary.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from actions import build_actions
from bot_client import APIError, rpc
from commands import build_params
from envelope import build_error_envelope, build_play_envelope
from exec import execute
from layers import normalize_play_state
from view import print_summary

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


def main() -> int:
    args, json_out = _parse_argv(sys.argv[1:])
    if not args:
        print(
            json.dumps(
                build_error_envelope(
                    "BAD_REQUEST",
                    "usage: act.py METHOD [args...] [--json]",
                ),
                ensure_ascii=False,
            )
        )
        return 2

    method, rest = args[0], args[1:]
    try:
        params: dict[str, Any] = build_params(method, rest)
        if method == "health":
            result = rpc("health", params)
            if json_out:
                print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
            else:
                status = result.get("status") if isinstance(result, dict) else None
                print(f"health: {status or 'ok'}")
            return 0
        if method == "save" and not json_out:
            result = rpc("save", params)
            path = result.get("path") if isinstance(result, dict) else None
            print(f"save success: {path or params['path']}")
            return 0
        raw = execute(method, params)
        normalized = normalize_play_state(raw)
        envelope = build_play_envelope(normalized, build_actions(normalized))
        if json_out:
            print(json.dumps(envelope, ensure_ascii=False))
        else:
            print_summary(envelope)
        return 0
    except APIError as e:
        print(json.dumps(build_error_envelope(e.name, e.message), ensure_ascii=False))
        return 1
    except ValueError as e:
        print(
            json.dumps(build_error_envelope("BAD_REQUEST", str(e)), ensure_ascii=False)
        )
        return 2
    except TimeoutError as e:
        print(json.dumps(build_error_envelope("TIMEOUT", str(e)), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

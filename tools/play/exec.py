"""Execute a JSON-RPC command and return a play envelope."""

from __future__ import annotations

import json
import sys
from typing import Any

from actions import build_actions
from bot_client import APIError, rpc
from commands import normalize_sort_mode
from envelope import build_error_envelope, build_play_envelope
from layers import normalize_play_state
from state import fetch_stable_gamestate


def parse_exec_payload(raw: str) -> tuple[str, dict[str, Any]]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("exec payload must be a JSON object")
    command = data.get("command")
    if not command or not isinstance(command, str):
        raise ValueError("exec payload requires string field 'command'")
    params = data.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("exec payload field 'params' must be an object")
    return command, params


def execute(command: str, params: dict[str, Any]) -> dict[str, Any]:
    if command == "sort":
        mode = normalize_sort_mode(str(params.get("mode", "rank")))
        rpc("sort", {"mode": mode})
        return fetch_stable_gamestate()
    rpc(command, params)
    return fetch_stable_gamestate()


def main() -> int:
    if len(sys.argv) < 2:
        print(
            json.dumps(
                build_error_envelope(
                    "BAD_REQUEST",
                    'usage: exec.py \'{"command":"play","params":{"cards":[0,1,2,3,4]}}\'',
                ),
                ensure_ascii=False,
            )
        )
        return 2

    try:
        command, params = parse_exec_payload(sys.argv[1])
        raw = execute(command, params)
        normalized = normalize_play_state(raw)
        envelope = build_play_envelope(normalized, build_actions(normalized))
        print(json.dumps(envelope, ensure_ascii=False))
        return 0
    except json.JSONDecodeError as e:
        print(
            json.dumps(build_error_envelope("BAD_REQUEST", str(e)), ensure_ascii=False)
        )
        return 2
    except APIError as e:
        print(json.dumps(build_error_envelope(e.name, e.message), ensure_ascii=False))
        return 1
    except (ValueError, TimeoutError) as e:
        print(
            json.dumps(build_error_envelope("BAD_REQUEST", str(e)), ensure_ascii=False)
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

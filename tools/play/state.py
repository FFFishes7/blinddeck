"""Fetch full JSON gamestate for the `state` command (user docs: full JSON state)."""

from __future__ import annotations

import json

from actions import build_actions
from bot_client import APIError, rpc
from envelope import build_error_envelope, build_play_envelope
from layers import poll_until_stable


def fetch_stable_gamestate() -> dict:
    return poll_until_stable(lambda: rpc("gamestate"))


def main() -> int:
    try:
        raw = fetch_stable_gamestate()
        envelope = build_play_envelope(raw, build_actions(raw))
        print(json.dumps(envelope, ensure_ascii=False))
        return 0
    except APIError as e:
        print(json.dumps(build_error_envelope(e.name, e.message), ensure_ascii=False))
        return 1
    except TimeoutError as e:
        print(json.dumps(build_error_envelope("TIMEOUT", str(e)), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

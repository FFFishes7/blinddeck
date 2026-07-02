"""Generic BalatroBot RPC helper.

Usage:
    echo '{"deck":"BLACK"}' | python rpc.py start
    python rpc.py gamestate
Reads JSON params from stdin (empty stdin => {}).
"""

import json
import sys

from bot_client import APIError
from bot_client import rpc as bot_rpc


def main() -> int:
    method = sys.argv[1]
    raw = sys.stdin.buffer.read().decode("utf-8-sig").strip()
    params = json.loads(raw) if raw else {}
    try:
        result = bot_rpc(method, params)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except APIError as e:
        print(f"APIError: {e.name} - {e.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

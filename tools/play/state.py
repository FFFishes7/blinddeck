"""Print a compact summary of the current Balatro gamestate."""

import sys

from bot_client import APIError, rpc
from view import print_summary


def main():
    try:
        print_summary(rpc("gamestate"))
    except APIError as e:
        print(f"RPC error (gamestate): {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

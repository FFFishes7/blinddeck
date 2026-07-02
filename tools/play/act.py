"""Run one BalatroBot action and print a compact summary.

Examples:
    python act.py select
    python act.py skip
    python act.py play 0 1 2 3 4
    python act.py discard 0 1
    python act.py buy card 0
    python act.py buy pack 0
    python act.py pack 0
    python act.py pack 0 1 2      # choose pack card 0, target hand cards 1 and 2
    python act.py pack skip
    python act.py use 0 1 2       # use consumable 0 on hand cards 1 and 2
    python act.py death 0 4 3     # consumable 0: convert source card 4 into target card 3
    python act.py rearrange hand 0 2 1 3 4 5 6 7
    python act.py sort rank       # use Balatro's native rank sort button logic
    python act.py sort suit       # use Balatro's native suit sort button logic
    python act.py start RED WHITE
    python act.py cash_out
    python act.py next_round
"""

from __future__ import annotations

import sys

from bot_client import APIError, rpc
from view import print_summary

NO_PARAMS = frozenset(
    {"select", "skip", "next_round", "cash_out", "reroll", "gamestate", "menu"}
)

ALIASES = {
    "gs": "gamestate",
    "state": "gamestate",
    "nr": "next_round",
    "cash": "cash_out",
}


def build_params(method: str, args: list[str]) -> dict:
    if method in NO_PARAMS:
        return {}
    if method in ("play", "discard"):
        if not args:
            raise ValueError(f"{method} needs card indices, e.g. play 0 1 2 3 4")
        return {"cards": [int(x) for x in args]}
    if method == "buy":
        if len(args) != 2:
            raise ValueError("buy needs: card|voucher|pack INDEX")
        kind, idx = args
        if kind not in ("card", "voucher", "pack"):
            raise ValueError("buy kind must be card, voucher, or pack")
        return {kind: int(idx)}
    if method == "pack":
        if not args:
            raise ValueError("pack needs card index or skip, e.g. pack 0 or pack skip")
        if args[0].lower() in ("skip", "s"):
            return {"skip": True}
        params = {"card": int(args[0])}
        if len(args) > 1:
            params["targets"] = [int(x) for x in args[1:]]
        return params
    if method == "use":
        if not args:
            raise ValueError("use needs consumable index, e.g. use 0 or use 0 1 2")
        params = {"consumable": int(args[0])}
        if len(args) > 1:
            params["cards"] = [int(x) for x in args[1:]]
        return params
    if method == "rearrange":
        return build_rearrange_params(args)
    if method == "sort":
        return {"mode": args[0] if args else "rank"}
    if method == "sell":
        if len(args) != 2:
            raise ValueError("sell needs: joker|consumable INDEX")
        kind, idx = args
        if kind not in ("joker", "consumable"):
            raise ValueError("sell kind must be joker or consumable")
        return {kind: int(idx)}
    if method == "start":
        if len(args) < 2:
            raise ValueError("start needs: DECK STAKE [seed]")
        params = {"deck": args[0].upper(), "stake": args[1].upper()}
        if len(args) > 2:
            params["seed"] = args[2]
        return params
    raise ValueError(f"unknown method: {method}")


def normalize_sort_mode(mode: str = "rank") -> str:
    aliases = {
        "r": "rank",
        "rd": "rank-desc",
        "ra": "rank-asc",
        "value": "rank",
        "value-desc": "rank-desc",
        "value-asc": "rank-asc",
        "s": "suit",
        "sd": "suit-desc",
        "sa": "suit-asc",
    }
    normalized = aliases.get(mode, mode)
    if normalized not in (
        "rank",
        "rank-desc",
        "rank-asc",
        "suit",
        "suit-desc",
        "suit-asc",
    ):
        raise ValueError(
            "sort mode must be rank|rank-desc|rank-asc|suit|suit-desc|suit-asc"
        )
    return normalized


def sort_hand(mode: str = "rank") -> dict:
    return rpc("sort", {"mode": normalize_sort_mode(mode)})


def build_rearrange_params(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("rearrange needs: hand|jokers|consumables FULL_INDEX_ORDER")
    area = args[0]
    if area not in ("hand", "jokers", "consumables"):
        raise ValueError("rearrange area must be hand, jokers, or consumables")
    return {area: [int(x) for x in args[1:]]}


def move_before(order: list[int], source: int, target: int) -> list[int]:
    order.remove(source)
    order.insert(order.index(target), source)
    return order


def use_death(consumable: int, source: int, target: int) -> dict:
    """Use Death as source -> target, preserving Balatro's left-to-right rule.

    Balatro Death converts the left selected card into the right selected card.
    This helper always moves the source card immediately to the left of the
    target first, so a request like "turn Q into 2" cannot accidentally turn the
    2 into the Q because of visual hand order.
    """
    state = rpc("gamestate")
    hand = state.get("hand", {}).get("cards", [])
    if source < 0 or source >= len(hand) or target < 0 or target >= len(hand):
        raise ValueError(f"death source/target out of range for hand size {len(hand)}")
    if source == target:
        raise ValueError("death source and target must be different cards")

    order = move_before(list(range(len(hand))), source, target)
    if order != list(range(len(hand))):
        rpc("rearrange", {"hand": order})
    source = order.index(source)
    target = order.index(target)

    return rpc("use", {"consumable": consumable, "cards": [source, target]})


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    method = ALIASES.get(sys.argv[1], sys.argv[1])
    args = sys.argv[2:]
    try:
        if method == "death":
            if len(args) != 3:
                raise ValueError(
                    "death needs: CONSUMABLE_INDEX SOURCE_CARD_INDEX TARGET_CARD_INDEX"
                )
            state = use_death(int(args[0]), int(args[1]), int(args[2]))
            print_summary(state)
            return 0
        if method == "sort":
            state = sort_hand(args[0] if args else "rank")
            print_summary(state)
            return 0
        params = build_params(method, args)
        state = rpc(method, params)
    except (APIError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print_summary(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

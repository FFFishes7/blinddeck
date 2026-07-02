"""Run one BalatroBot action and print a compact summary.

Run `python act.py help` for a full, state-aware command reference.
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


# (category, syntax, description, applicable_states or None for "any state")
COMMANDS = [
    ("query", "state", "current gamestate summary", None),
    ("query", "hand", "alias for state", None),
    ("query", "rpc METHOD [json-stdin]", "send any JSON-RPC call", None),
    (
        "query",
        "know preflight",
        "verify stake/jokers/boss/tags vs knowledge base",
        None,
    ),
    (
        "query",
        'know check joker|boss|tag|stake|planet|tarot|voucher|spectral|rule "Name"',
        "look up one verified entry",
        None,
    ),
    ("query", "know list jokers|bosses|tags|...", "list all entries of a kind", None),
    ("query", "know stats", "knowledge library counts", None),
    ("run flow", "start DECK STAKE [seed]", "start a new run", {"MENU"}),
    ("run flow", "menu", "return to main menu", None),
    ("run flow", "select", "select the current blind", {"BLIND_SELECT"}),
    ("run flow", "skip", "skip the current blind (small/big only)", {"BLIND_SELECT"}),
    ("run flow", "cash_out", "cash out round rewards", {"ROUND_EVAL"}),
    ("run flow", "next_round", "leave shop -> next blind select", {"SHOP"}),
    ("hand", "play i [j ...]", "play hand cards at given indices", {"SELECTING_HAND"}),
    (
        "hand",
        "discard i [j ...]",
        "discard hand cards at given indices",
        {"SELECTING_HAND"},
    ),
    (
        "hand",
        "sort rank|rank-desc|rank-asc|suit|suit-desc|suit-asc",
        "Balatro's native sort",
        {"SELECTING_HAND", "SMODS_BOOSTER_OPENED"},
    ),
    (
        "hand",
        "rearrange hand|jokers|consumables i j k ...",
        "custom ordering by full index order",
        {"SELECTING_HAND", "SHOP", "SMODS_BOOSTER_OPENED"},
    ),
    ("shop", "buy card|voucher|pack N", "buy a shop card/voucher/pack", {"SHOP"}),
    ("shop", "reroll", "reroll the shop", {"SHOP"}),
    (
        "shop",
        "sell joker|consumable N",
        "sell a joker or consumable",
        {"SELECTING_HAND", "SHOP", "SMODS_BOOSTER_OPENED"},
    ),
    (
        "pack",
        "pack N [targets...]",
        "pick pack card N, optionally target hand cards",
        {"SMODS_BOOSTER_OPENED"},
    ),
    ("pack", "pack skip", "skip the opened booster pack", {"SMODS_BOOSTER_OPENED"}),
    (
        "consumable",
        "use N [cards...]",
        "use consumable N, optionally on hand cards",
        {"SELECTING_HAND", "SHOP"},
    ),
    (
        "consumable",
        "death CONSUMABLE SRC TGT",
        "Death: turn source card SRC into target TGT (auto-orders)",
        {"SELECTING_HAND"},
    ),
    ("help", "help [all|STATE]", "show commands (filtered by state)", None),
]

_HELP_CATEGORIES = ["query", "run flow", "hand", "shop", "pack", "consumable", "help"]


def print_help(filter_state: str | None = None) -> None:
    """Print the command reference.

    If ``filter_state`` is a concrete state name, only commands valid in that
    state (plus always-available ones) are shown. ``"all"`` or ``None`` shows
    everything.
    """
    if filter_state and filter_state != "all":
        print(f"BalatroBot commands (state={filter_state}):")
    else:
        print("BalatroBot commands (all):")
    by_cat: dict[str, list[tuple[str, str, set[str] | None]]] = {}
    for cat, syntax, desc, states in COMMANDS:
        by_cat.setdefault(cat, []).append((syntax, desc, states))
    for cat in _HELP_CATEGORIES:
        rows = by_cat.get(cat, [])
        if filter_state and filter_state != "all":
            rows = [r for r in rows if r[2] is None or filter_state in r[2]]
        if not rows:
            continue
        print(f"  [{cat}]")
        for syntax, desc, states in rows:
            tag = " (any state)" if states is None else ""
            print(f"    {syntax:<52} {desc}{tag}")
    print(
        "notes: indices are 0-based; server is single-connection/serial; "
        "each action prints state after."
    )
    print(
        "tip: run `python act.py help` for state-aware help, `help all` for full list."
    )


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
        print("Run `python act.py help` for the command reference.", file=sys.stderr)
        return 2
    method = ALIASES.get(sys.argv[1], sys.argv[1])
    args = sys.argv[2:]
    if method in ("help", "-h", "--help"):
        arg = args[0] if args else None
        if arg is None:
            # State-aware: probe the server, fall back to full list if down.
            try:
                filter_state = rpc("gamestate").get("state")
            except Exception:
                filter_state = "all"
        elif arg == "all":
            filter_state = "all"
        else:
            filter_state = arg
        print_help(filter_state)
        return 0
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

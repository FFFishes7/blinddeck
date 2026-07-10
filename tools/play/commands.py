"""RPC command parameter builders (migrated from act.py)."""

from __future__ import annotations

from cheats import build_add_params, build_debuff_params, build_set_params

NO_PARAMS = frozenset(
    {
        "select",
        "skip",
        "next_round",
        "cash_out",
        "endless",
        "reroll",
        "reroll_boss",
        "gamestate",
        "menu",
        "health",
    }
)

SORT_MODES = frozenset(
    {"rank", "rank-desc", "rank-asc", "suit", "suit-desc", "suit-asc"}
)

SORT_ALIASES = {
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


def normalize_sort_mode(mode: str = "rank") -> str:
    normalized = SORT_ALIASES.get(mode, mode)
    if normalized not in SORT_MODES:
        raise ValueError(
            "sort mode must be rank|rank-desc|rank-asc|suit|suit-desc|suit-asc"
        )
    return normalized


def build_rearrange_params(args: list[str]) -> dict:
    if len(args) < 2:
        raise ValueError("rearrange needs: jokers FULL_INDEX_ORDER")
    area = args[0]
    if area != "jokers":
        raise ValueError("rearrange area must be jokers")
    return {"jokers": [int(x) for x in args[1:]]}


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
        params: dict = {"card": int(args[0])}
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
        return {"mode": normalize_sort_mode(args[0] if args else "rank")}
    if method == "sell":
        if len(args) != 2:
            raise ValueError("sell needs: joker|consumable INDEX")
        kind, idx = args
        if kind not in ("joker", "consumable"):
            raise ValueError("sell kind must be joker or consumable")
        return {kind: int(idx)}
    if method == "challenge":
        if len(args) != 1:
            raise ValueError(
                "challenge needs: CHALLENGE_ID (run challenges to list IDs)"
            )
        return {"id": args[0]}
    if method == "start":
        if len(args) < 2:
            raise ValueError("start needs: DECK STAKE [seed]")
        params = {"deck": args[0].upper(), "stake": args[1].upper()}
        if len(args) > 2:
            params["seed"] = args[2]
        return params
    if method == "load":
        if len(args) != 1:
            raise ValueError("load needs: PATH")
        return {"path": args[0]}
    if method == "save":
        if len(args) != 1:
            raise ValueError("save needs: PATH")
        return {"path": args[0]}
    if method == "screenshot":
        if len(args) != 1:
            raise ValueError("screenshot needs: PATH")
        return {"path": args[0]}
    if method == "add":
        return build_add_params(args)
    if method == "set":
        return build_set_params(args)
    if method == "debuff":
        return build_debuff_params(args)
    raise ValueError(f"unknown method: {method}")


def move_before(order: list[int], source: int, target: int) -> list[int]:
    order.remove(source)
    order.insert(order.index(target), source)
    return order


def format_friendly_action(action: dict) -> str | None:
    """Render an envelope action's ``example`` as a ``bot.ps1`` friendly subcommand."""
    cmd = action.get("command")
    if not cmd:
        return None
    example = action.get("example") or {}
    params = example.get("params") or {}

    if cmd in NO_PARAMS:
        return cmd
    if cmd in ("play", "discard"):
        cards = params.get("cards") or []
        return f"{cmd} " + " ".join(str(c) for c in cards)
    if cmd == "buy":
        for kind in ("card", "voucher", "pack"):
            if kind in params:
                return f"buy {kind} {params[kind]}"
        return "buy card|voucher|pack IDX"
    if cmd == "pack":
        if params.get("skip"):
            return "pack skip"
        card = params.get("card")
        if card is None:
            return "pack IDX"
        targets = params.get("targets") or []
        parts = ["pack", str(card), *[str(t) for t in targets]]
        return " ".join(parts)
    if cmd == "use":
        idx = params.get("consumable")
        if idx is None:
            return "use CONSUMABLE_IDX"
        cards = params.get("cards") or []
        if cards:
            return "use " + " ".join(str(x) for x in [idx, *cards])
        return f"use {idx}"
    if cmd == "rearrange":
        order = params.get("jokers")
        if order is not None:
            return "rearrange jokers " + " ".join(str(i) for i in order)
        return "rearrange jokers ORDER"
    if cmd == "sort":
        return f"sort {params.get('mode', 'rank')}"
    if cmd == "sell":
        for kind in ("joker", "consumable"):
            if kind in params:
                return f"sell {kind} {params[kind]}"
        return "sell joker|consumable IDX"
    if cmd == "challenges":
        return "challenges"
    if cmd == "challenge":
        return f"challenge {params.get('id', 'CHALLENGE_ID')}"
    if cmd == "start":
        deck = params.get("deck", "DECK")
        stake = params.get("stake", "STAKE")
        seed = params.get("seed")
        if seed:
            return f"start {deck} {stake} {seed}"
        return f"start {deck} {stake}"
    if cmd in ("load", "save", "screenshot"):
        path = params.get("path", "PATH")
        return f"{cmd} {path}"
    if cmd == "add":
        key = params.get("key", "KEY")
        return f"add {key}"
    if cmd == "set":
        pairs = [f"{k}={v}" for k, v in params.items()]
        return "set " + " ".join(pairs) if pairs else "set"
    if cmd == "debuff":
        cards = params.get("cards") or []
        if not params.get("debuff", True):
            return "debuff clear " + " ".join(str(c) for c in cards)
        return "debuff " + " ".join(str(c) for c in cards)
    return cmd

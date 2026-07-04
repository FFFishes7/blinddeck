"""State filtering, detail-query registry, and transition polling for play helpers.

User-facing docs call these: compact summary (filtered gamestate), detail queries,
full JSON state. Internal names: filter_layer1, RUN_QUERIES.
"""

from __future__ import annotations

import copy
import os
import time
from typing import Any, Callable

TRANSITION_STATES = frozenset(
    {"HAND_PLAYED", "DRAW_TO_HAND", "NEW_ROUND", "PLAY_TAROT"}
)

LAYER1_KEYS_BY_STATE: dict[str, frozenset[str]] = {
    "MENU": frozenset({"state"}),
    "BLIND_SELECT": frozenset(
        {
            "state",
            "money",
            "bankrupt_at",
            "round_num",
            "ante_num",
            "deck",
            "stake",
            "round",
            "blinds",
            "jokers",
            "consumables",
            "cards",
        }
    ),
    "SELECTING_HAND": frozenset(
        {
            "state",
            "money",
            "bankrupt_at",
            "round_num",
            "ante_num",
            "deck",
            "stake",
            "round",
            "blinds",
            "jokers",
            "consumables",
            "cards",
            "hand",
        }
    ),
    "ROUND_EVAL": frozenset(
        {
            "state",
            "money",
            "bankrupt_at",
            "round_num",
            "ante_num",
            "deck",
            "stake",
            "round",
            "blinds",
            "jokers",
            "consumables",
            "cards",
            "won",
            "victory_overlay",
        }
    ),
    "SHOP": frozenset(
        {
            "state",
            "money",
            "bankrupt_at",
            "round_num",
            "ante_num",
            "deck",
            "stake",
            "round",
            "cards",
            "jokers",
            "consumables",
            "shop",
            "vouchers",
            "packs",
        }
    ),
    "SMODS_BOOSTER_OPENED": frozenset(
        {
            "state",
            "money",
            "round_num",
            "ante_num",
            "deck",
            "stake",
            "round",
            "cards",
            "jokers",
            "consumables",
            "pack",
            "hand",
        }
    ),
    "GAME_OVER": frozenset(
        {
            "state",
            "won",
            "seed",
            "ante_num",
            "round_num",
            "deck",
            "stake",
            "run_summary",
        }
    ),
}

RUN_QUERIES = [
    {
        "name": "deck",
        "description": "Full remaining draw pile",
        "command": "query deck",
    },
    {
        "name": "hands",
        "description": "Poker hand level table",
        "command": "query hands",
    },
    {
        "name": "blinds",
        "description": "All three blinds with full detail",
        "command": "query blinds",
    },
    {
        "name": "used_vouchers",
        "description": "Vouchers owned this run",
        "command": "query used_vouchers",
    },
]

QUERY_REGISTRY: dict[str, list[dict[str, str]]] = {
    "BLIND_SELECT": list(RUN_QUERIES),
    "SELECTING_HAND": list(RUN_QUERIES)
    + [
        {
            "name": "seed",
            "description": "Run seed for debug/replay",
            "command": "query seed",
        }
    ],
    "ROUND_EVAL": list(RUN_QUERIES)
    + [
        {
            "name": "seed",
            "description": "Run seed for debug/replay",
            "command": "query seed",
        }
    ],
    "SHOP": list(RUN_QUERIES),
    "SMODS_BOOSTER_OPENED": list(RUN_QUERIES),
}

QUERY_EXTRACTORS: dict[str, str] = {
    "deck": "cards",
    "hands": "hands",
    "blinds": "blinds",
    "used_vouchers": "used_vouchers",
    "seed": "seed",
}

POLL_INTERVAL_SEC = 0.05
POLL_TIMEOUT_SEC = float(os.getenv("BALATROBOT_POLL_TIMEOUT", "30"))


def pack_has_hand(raw: dict[str, Any]) -> bool:
    hand = raw.get("hand") or {}
    return bool(hand.get("cards"))


def filter_blinds_current(blinds: dict[str, Any]) -> dict[str, Any]:
    for key, blind in blinds.items():
        if blind.get("status") == "CURRENT":
            return {key: copy.deepcopy(blind)}
    return copy.deepcopy(blinds)


def strip_cards_count_only(cards: dict[str, Any]) -> dict[str, Any]:
    return {"count": cards.get("count", 0), "limit": cards.get("limit", 0)}


def filter_layer1(raw: dict[str, Any]) -> dict[str, Any]:
    state = raw.get("state", "UNKNOWN")
    allowed = LAYER1_KEYS_BY_STATE.get(state)
    if allowed is None:
        return {"state": state}

    out: dict[str, Any] = {}
    for key in allowed:
        if key not in raw:
            continue
        value = raw[key]
        if value is None:
            continue

        if key == "cards" and isinstance(value, dict):
            out[key] = strip_cards_count_only(value)
            continue

        if key == "blinds" and state in ("SELECTING_HAND", "ROUND_EVAL"):
            out[key] = filter_blinds_current(value)
            continue

        if key == "won":
            if state == "GAME_OVER" or value is True:
                out[key] = value
            continue

        if key == "victory_overlay":
            if value is True:
                out[key] = value
            continue

        if key == "hand" and state == "SMODS_BOOSTER_OPENED" and not pack_has_hand(raw):
            continue

        out[key] = copy.deepcopy(value)

    return out


def available_queries(state: str) -> list[dict[str, str]]:
    return copy.deepcopy(QUERY_REGISTRY.get(state, []))


def extract_query(raw: dict[str, Any], name: str) -> dict[str, Any]:
    field = QUERY_EXTRACTORS.get(name)
    if field is None:
        raise ValueError(f"unknown query: {name}")
    if field not in raw:
        return {}
    data = copy.deepcopy(raw[field])
    if name == "seed":
        return {"seed": data}
    return data


def poll_until_stable(
    fetch: Callable[[], dict[str, Any]],
    *,
    timeout: float = POLL_TIMEOUT_SEC,
    interval: float = POLL_INTERVAL_SEC,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last = fetch()
    while True:
        state = last.get("state", "UNKNOWN")
        if state not in TRANSITION_STATES:
            return last
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"game state stuck in transition {state!r} after {timeout}s"
            )
        time.sleep(interval)
        last = fetch()

"""Compact gamestate display for manual play."""

from __future__ import annotations

from typing import Any

RANK_LABEL = {"T": "10", "J": "J", "Q": "Q", "K": "K", "A": "A"}
SUIT_LABEL = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def card_label(card: dict[str, Any]) -> str:
    key = card.get("key", "")
    if "_" in key:
        suit, rank = key.split("_", 1)
        rank = RANK_LABEL.get(rank, rank)
        return f"{rank}{SUIT_LABEL.get(suit, suit)}"
    val = card.get("value", {})
    rank = RANK_LABEL.get(str(val.get("rank", "?")), str(val.get("rank", "?")))
    suit = SUIT_LABEL.get(str(val.get("suit", "?")), str(val.get("suit", "?")))
    return f"{rank}{suit}"


def card_debuffed(card: dict[str, Any]) -> bool:
    st = card.get("state")
    if isinstance(st, dict):
        return bool(st.get("debuff"))
    if isinstance(st, list):
        return any(isinstance(x, dict) and x.get("debuff") for x in st)
    return False


def active_blind(state: dict[str, Any]) -> dict[str, Any] | None:
    if state.get("blind"):
        return state["blind"]
    for blind in state.get("blinds", {}).values():
        if blind.get("status") in ("CURRENT", "SELECT"):
            return blind
    return None


def card_cost(card: dict[str, Any], show_cost: bool = True) -> str:
    if not show_cost:
        return ""
    cost = card.get("cost", {})
    if isinstance(cost, dict) and cost.get("free"):
        return " free"
    if isinstance(cost, dict) and "buy" in cost:
        return f" ${cost['buy']}"
    return ""


EDITION_LABEL = {
    "FOIL": "FOIL +50c",
    "HOLO": "HOLO +10m",
    "HOLOGRAPHIC": "HOLO +10m",
    "POLYCHROME": "POLY x1.5",
    "NEGATIVE": "NEG +slot",
}


def card_tags(card: dict[str, Any]) -> list[str]:
    modifier = card.get("modifier", {}) or {}
    tags = []
    edition = modifier.get("edition")
    if edition:
        tags.append(EDITION_LABEL.get(str(edition), str(edition)))
    enhancement = modifier.get("enhancement")
    if enhancement and card.get("set") in ("DEFAULT", "ENHANCED"):
        tags.append(str(enhancement))
    if modifier.get("seal"):
        tags.append(f"{modifier['seal']} SEAL")
    if modifier.get("eternal"):
        tags.append("ETERNAL")
    if modifier.get("rental"):
        tags.append("RENTAL")
    if modifier.get("perishable"):
        tags.append(f"PERISH {modifier['perishable']}")
    return tags


def compact_effect(card: dict[str, Any]) -> str:
    effect = ((card.get("value") or {}).get("effect") or "").strip()
    return " ".join(effect.split())


def is_playing_card(card: dict[str, Any]) -> bool:
    value = card.get("value") or {}
    if value.get("rank") and value.get("suit"):
        return True
    key = card.get("key", "")
    if "_" not in key:
        return False
    suit, rank = key.split("_", 1)
    return suit in SUIT_LABEL and (
        rank in RANK_LABEL or rank in {str(n) for n in range(2, 10)}
    )


def display_name(
    card: dict[str, Any],
    include_effect: bool = False,
    include_card_face: bool = True,
    show_cost: bool = True,
) -> str:
    label = card.get("label", card.get("key", "?"))
    if include_card_face and is_playing_card(card):
        label = f"{card_label(card)} {label}"
    name = f"{label}{card_cost(card, show_cost=show_cost)}"
    value = card.get("value") or {}
    if card.get("key") == "c_fool":
        copy_label = value.get("copy_label") or value.get("copy_key")
        if copy_label and copy_label != "c_fool":
            name += f" -> {copy_label}"
    tags = card_tags(card)
    if tags:
        name += " [" + ", ".join(tags) + "]"
    if include_effect:
        effect = compact_effect(card)
        if effect:
            name += f" — {effect}"
    return name


def named_area(
    cards: list[dict[str, Any]],
    include_effect: bool = False,
    show_cost: bool = True,
) -> list[tuple[int, str]]:
    return [
        (i, display_name(c, include_effect=include_effect, show_cost=show_cost))
        for i, c in enumerate(cards)
    ]


def print_hint(state_name: str) -> None:
    hints = {
        "MENU": "hint: python act.py start RED WHITE",
        "BLIND_SELECT": "hint: python act.py select  |  python act.py skip",
        "SELECTING_HAND": "hint: python act.py play 0 1 2 3 4  |  python act.py discard 0 1",
        "ROUND_EVAL": "hint: python act.py cash_out",
        "SHOP": "hint: python act.py buy card 0  |  python act.py buy pack 0  |  python act.py reroll  |  python act.py next_round",
        "SMODS_BOOSTER_OPENED": "hint: python act.py pack 0 [target...]  |  python act.py pack skip",
        "GAME_OVER": "hint: python act.py menu",
    }
    if state_name in hints:
        print(hints[state_name])


def print_summary(state: dict[str, Any]) -> None:
    rnd = state.get("round", {})
    blind = active_blind(state)
    state_name = state["state"]
    print(
        f"state={state_name} ante={state['ante_num']} round={state.get('round_num')} "
        f"money={state['money']} deck={state.get('deck')} stake={state.get('stake')}"
    )
    if blind:
        print(
            f"blind={blind['name']} type={blind.get('type')} status={blind['status']} "
            f"target={blind['score']} effect={blind.get('effect', '')}"
        )
    if rnd:
        print(
            f"round: chips={rnd.get('chips', 0)} "
            f"hands={rnd.get('hands_left')} discards={rnd.get('discards_left')} "
            f"reroll=${rnd.get('reroll_cost')}"
        )
    jokers = state.get("jokers", {}).get("cards", [])
    if jokers:
        limit = state.get("jokers", {}).get("limit", 5)
        empty = limit - len(jokers)
        print("jokers:")
        for i, desc in named_area(jokers, include_effect=True):
            print(f"  [{i}] {desc}")
        if empty:
            print(f"  (+{empty} empty slots)")
    consumables = state.get("consumables", {}).get("cards", [])
    if consumables:
        print("consumables:", named_area(consumables))
    if state_name == "SHOP":
        print("shop:", named_area(state.get("shop", {}).get("cards", [])))
        print("packs:", named_area(state.get("packs", {}).get("cards", [])))
        print("vouchers:", named_area(state.get("vouchers", {}).get("cards", [])))
        print(
            "blinds:",
            {
                k: (
                    v["name"],
                    v.get("tag_name", ""),
                    v.get("tag_effect", ""),
                    v["score"],
                )
                for k, v in state.get("blinds", {}).items()
            },
        )
    if state_name == "BLIND_SELECT":
        print(
            "blinds:",
            {
                k: (v["name"], v.get("tag_name", ""), v["status"])
                for k, v in state.get("blinds", {}).items()
            },
        )
    hand = state.get("hand", {}).get("cards", [])
    if hand:
        print("hand:")
        for i, c in enumerate(hand):
            state_info = c.get("state") if isinstance(c.get("state"), dict) else {}
            hidden = " HIDDEN" if state_info.get("hidden") else ""
            debuff = " DEBUFF" if card_debuffed(c) else ""
            mod = c.get("value", {}).get("effect", "")
            extra = f" +{mod}" if mod else ""
            print(f"  [{i}] {card_label(c)} ({c['key']}){extra}{hidden}{debuff}")
    pack = state.get("pack", {}).get("cards", [])
    if pack:
        print(
            "pack_open (free pick):",
            named_area(pack, include_effect=True, show_cost=False),
        )
    leveled = {
        h: (d["level"], d["chips"], d["mult"])
        for h, d in state.get("hands", {}).items()
        if d["level"] > 1
    }
    if leveled:
        print("leveled_hands:", leveled)
    print_hint(state_name)

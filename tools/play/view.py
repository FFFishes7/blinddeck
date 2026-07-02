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


def base_chips(card: dict[str, Any]) -> int | None:
    """Base chip value of a playing card from its rank, with no edition or
    enhancement bonuses baked in. 2-9 = face value, T/J/Q/K = 10, A = 11.

    Returns None for cards without a rank (e.g. Stone), so the caller can
    fall back to the raw effect text.
    """
    val = card.get("value") or {}
    rank = str(val.get("rank") or "")
    mapping = {"T": 10, "J": 10, "Q": 10, "K": 10, "A": 11}
    if rank.isdigit():
        return int(rank)
    if rank in mapping:
        return mapping[rank]
    key = card.get("key", "")
    if "_" in key:
        _, r = key.split("_", 1)
        if r.isdigit():
            return int(r)
        if r in mapping:
            return mapping[r]
    return None


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
    "FOIL": "箔片:+50筹码",
    "HOLO": "全息:+10倍率",
    "HOLOGRAPHIC": "全息:+10倍率",
    "POLYCHROME": "多彩:×1.5",
    "NEGATIVE": "负片:+槽位",
}

ENHANCEMENT_LABEL = {
    "BONUS": "奖励:+30筹码",
    "MULT": "倍率:+4倍率",
    "GLASS": "玻璃:×2倍率 1/4碎裂",
    "STEEL": "钢铁:留在手牌×1.5",
    "GOLD": "金币:留在手牌+$3",
    "LUCKY": "幸运:1/5 +20倍率 1/15 +$20",
    "STONE": "石头:+50筹码 无花色点数",
    "WILD": "万能:任意花色点数",
}

SEAL_LABEL = {
    "RED": "红色蜡封:计分时再次触发",
    "BLUE": "蓝色蜡封:留至回合末生成星球牌",
    "PURPLE": "紫色蜡封:弃牌时生成随机塔罗牌",
    "GOLD": "金色蜡封:计分时+$3",
}


def card_tags(card: dict[str, Any]) -> list[str]:
    modifier = card.get("modifier", {}) or {}
    tags = []
    edition = modifier.get("edition")
    if edition:
        tags.append(EDITION_LABEL.get(str(edition), str(edition)))
    enhancement = modifier.get("enhancement")
    if enhancement and card.get("set") in ("DEFAULT", "ENHANCED"):
        tags.append(ENHANCEMENT_LABEL.get(str(enhancement), str(enhancement)))
    seal = modifier.get("seal")
    if seal:
        tags.append(SEAL_LABEL.get(str(seal), f"{seal}蜡封"))
    if modifier.get("eternal"):
        tags.append("永恒")
    if modifier.get("rental"):
        tags.append("租赁")
    if modifier.get("perishable"):
        tags.append(f"消逝{modifier['perishable']}")
    return tags


def compact_effect(card: dict[str, Any]) -> str:
    effect = ((card.get("value") or {}).get("effect") or "").strip()
    return " ".join(effect.split())


# Fallback descriptions when a card's value.effect is empty. Keyed by tokens
# that appear in the card label, so it works regardless of exact card key.
STATIC_EFFECT_TOKENS: list[tuple[str, str]] = [
    ("Buffoon", "补充包内含小丑牌"),
    ("Arcana", "补充包内含塔罗牌"),
    ("Celestial", "补充包内含星球牌"),
    ("Spectral", "补充包内含幻灵牌"),
    ("Standard", "补充包内含增强手牌"),
]


def static_effect(card: dict[str, Any]) -> str:
    label = card.get("label", "") or ""
    for token, desc in STATIC_EFFECT_TOKENS:
        if token in label:
            return desc
    return ""


SET_LABEL: dict[str, str] = {
    "JOKER": "小丑",
    "TAROT": "塔罗",
    "PLANET": "星球",
    "SPECTRAL": "幻灵",
    "VOUCHER": "凭证",
    "DEFAULT": "手牌",
    "ENHANCED": "手牌",
    "BOOSTER": "补充包",
}


def type_tag(card: dict[str, Any]) -> str:
    """Short Chinese label for the card's set, e.g. 小丑/塔罗/星球.

    Falls back to the raw uppercased set so an unknown set still surfaces.
    """
    s = str(card.get("set") or "").strip().upper()
    if not s:
        return ""
    return SET_LABEL.get(s, s)


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
    include_type: bool = False,
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
    if include_type:
        t = type_tag(card)
        if t:
            tags.insert(0, t)
    if tags:
        name += " [" + ", ".join(tags) + "]"
    if include_effect:
        if is_playing_card(card):
            # Playing cards: show only base-rank chips here. Edition and
            # enhancement bonuses are already conveyed by card_tags, so
            # reusing the baked-in effect string would double-count (e.g.
            # "++60筹码" next to "[箔片:+50筹码]").
            bc = base_chips(card)
            if bc is not None:
                name += f" — ++{bc}筹码"
        else:
            effect = compact_effect(card)
            if not effect:
                effect = static_effect(card)
            if effect:
                name += f" — {effect}"
    return name


def named_area(
    cards: list[dict[str, Any]],
    include_effect: bool = False,
    show_cost: bool = True,
    include_type: bool = False,
) -> list[tuple[int, str]]:
    return [
        (
            i,
            display_name(
                c,
                include_effect=include_effect,
                show_cost=show_cost,
                include_type=include_type,
            ),
        )
        for i, c in enumerate(cards)
    ]


def print_hand_levels(state: dict[str, Any]) -> None:
    """Print every poker hand type with its level, chips, and mult.

    Sorted by Balatro's hand ``order`` so the layout is stable. Unlike the
    old leveled-only highlight, this shows base (L1) hands too, which lets the
    AI weigh played hands against current scoring values.
    """
    hands = state.get("hands") or {}
    if not hands:
        return
    ordered = sorted(hands.items(), key=lambda kv: kv[1].get("order", 0))
    parts = [
        f"{name}[L{d.get('level', 1)} {d.get('chips', 0)}\u00d7{d.get('mult', 0)}]"
        for name, d in ordered
    ]
    print("hands: " + ", ".join(parts))


def print_round_start_rules(state: dict[str, Any]) -> None:
    if state.get("state") != "SELECTING_HAND":
        return
    rnd = state.get("round") or {}
    # Only show at the very start of the round: no chips banked and no action
    # (play or discard) taken yet, so it doesn't repeat after every discard.
    if rnd.get("chips", 0) != 0:
        return
    if (rnd.get("hands_played") or 0) != 0:
        return
    if (rnd.get("discards_used") or 0) != 0:
        return
    print("round_rules:")
    print(
        "  scoring: "
        "只有组成当前牌型的计分牌会结算；未计分的踢脚牌通常不触发牌面增强/计分效果。"
    )
    print("  order: 计分牌按当前出牌顺序从左到右触发；小丑按小丑栏从左到右触发。")
    print(
        "  order_tools: "
        "可先用 rearrange hand/jokers 或 sort rank/suit 调整顺序，再出牌或使用 Death。"
    )


def print_hint(state_name: str) -> None:
    # Concise, high-signal cues for the primary actions of each state. Niche
    # commands (sell / rearrange / death / all sort modes) live in `help` --
    # the pointer below already directs there -- so the hint stays readable.
    hints = {
        "MENU": "hint: python act.py start RED WHITE",
        "BLIND_SELECT": "hint: python act.py select  |  python act.py skip  (skip 拿上方 tag=)",
        "SELECTING_HAND": "hint: python act.py play 0 1 2 3 4  |  discard 0 1  |  use 0 [cards...]  |  sort rank|suit",
        "ROUND_EVAL": "hint: python act.py cash_out",
        "SHOP": "hint: python act.py buy card 0  |  buy pack 0  |  buy voucher 0  |  reroll  |  next_round  |  use 0",
        "SMODS_BOOSTER_OPENED": "hint: python act.py pack 0 [targets...]  |  pack skip",
        "GAME_OVER": "hint: python act.py menu",
    }
    if state_name in hints:
        print(hints[state_name])
    print("? .\\bot.ps1 help  — full command list (state-aware)")


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
        print("consumables:")
        for i, desc in named_area(consumables, include_effect=True, include_type=True):
            print(f"  [{i}] {desc}")
    if state_name == "SHOP":
        shop_cards = state.get("shop", {}).get("cards", [])
        if shop_cards:
            print("shop:")
            for i, desc in named_area(
                shop_cards, include_effect=True, include_type=True
            ):
                print(f"  [{i}] {desc}")
        pack_cards = state.get("packs", {}).get("cards", [])
        if pack_cards:
            print("packs:")
            for i, desc in named_area(
                pack_cards, include_effect=True, include_type=True
            ):
                print(f"  [{i}] {desc}")
        voucher_cards = state.get("vouchers", {}).get("cards", [])
        if voucher_cards:
            print("vouchers:")
            for i, desc in named_area(
                voucher_cards, include_effect=True, include_type=True
            ):
                print(f"  [{i}] {desc}")
        print(
            "blinds:",
            {
                k: (v["name"], v.get("tag_name", ""), v["score"])
                for k, v in state.get("blinds", {}).items()
            },
        )
    if state_name == "BLIND_SELECT":
        print("blinds:")
        for k, v in state.get("blinds", {}).items():
            line = f"  {k}: {v['name']} [{v['status']}] target={v['score']}"
            if v.get("effect"):
                line += f" effect={v['effect']}"
            if v.get("tag_name"):
                line += f" tag={v['tag_name']}"
            if v.get("tag_effect"):
                line += f" ({v['tag_effect']})"
            print(line)
    hand = state.get("hand", {}).get("cards", [])
    if hand:
        print("hand:")
        for i, c in enumerate(hand):
            state_info = c.get("state") if isinstance(c.get("state"), dict) else {}
            if state_info.get("hidden"):
                print(f"  [{i}] ?? HIDDEN")
                continue
            debuff = " DEBUFF" if card_debuffed(c) else ""
            bc = base_chips(c)
            extra = f" ++{bc}筹码" if bc is not None else ""
            tags = card_tags(c)
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            print(f"  [{i}] {card_label(c)} ({c['key']}){extra}{tag_str}{debuff}")
    pack = state.get("pack", {}).get("cards", [])
    if pack:
        print(
            "pack_open (free pick):",
            named_area(pack, include_effect=True, show_cost=False, include_type=True),
        )
    if state_name in ("SELECTING_HAND", "ROUND_EVAL"):
        print_hand_levels(state)
    print_round_start_rules(state)
    print_hint(state_name)

"""Compact human/AI-readable state summary (glance command).

Formats the play envelope into a short multi-line string so the AI can read
the current state at a glance instead of scanning the full JSON envelope.
"""

from __future__ import annotations

import json
from typing import Any

from actions import (
    build_actions,
    buy_blocked_by_slots,
    buy_power,
    consumable_target_hint,
)
from bot_client import APIError
from envelope import build_error_envelope, build_play_envelope
from layers import TRANSITION_STATES, normalize_play_state
from start_options import build_decks, build_stakes
from state import fetch_stable_gamestate

SUIT_SYMBOL = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}

# Modifier tag maps. The Lua layer emits these uppercased codes from
# src/lua/utils/gamestate.lua (extract_card_modifier). Tags use a one-letter
# category prefix so they never collide: e:* enhancement, d:* edition, s:* seal.
ENHANCEMENT_TAGS = {
    "MULT": "e:Mult",
    "BONUS": "e:Bonus",
    "GLASS": "e:Glass",
    "STONE": "e:Stone",
    "WILD": "e:Wild",
    "LUCKY": "e:Lucky",
    "GOLD": "e:Gold",
    "STEEL": "e:Steel",
}
EDITION_TAGS = {
    "FOIL": "d:Foil",
    "HOLO": "d:Holo",
    "HOLOGRAPHIC": "d:Holo",
    "POLYCHROME": "d:Poly",
    "NEGATIVE": "d:Neg",
}
SEAL_TAGS = {
    "RED": "s:Red",
    "BLUE": "s:Blue",
    "GOLD": "s:Gold",
    "PURPLE": "s:Purple",
}


def _modifier_tags(card: dict[str, Any]) -> list[str]:
    """Build ordered modifier tags [enhancement, edition, seal] for a card."""
    mod = card.get("modifier") or {}
    if not isinstance(mod, dict):
        return []
    tags: list[str] = []
    enh = mod.get("enhancement")
    if isinstance(enh, str) and enh in ENHANCEMENT_TAGS:
        tags.append(ENHANCEMENT_TAGS[enh])
    elif isinstance(enh, str) and enh:
        tags.append(f"e:{enh}")
    ed = mod.get("edition")
    if isinstance(ed, str) and ed in EDITION_TAGS:
        tags.append(EDITION_TAGS[ed])
    elif isinstance(ed, str) and ed:
        tags.append(f"d:{ed}")
    seal = mod.get("seal")
    if isinstance(seal, str) and seal in SEAL_TAGS:
        tags.append(SEAL_TAGS[seal])
    elif isinstance(seal, str) and seal:
        tags.append(f"s:{seal}")
    if mod.get("eternal"):
        tags.append("eternal")
    return tags


def card_label(card: dict[str, Any]) -> str:
    """Format a playing card as e.g. ``K♠`` / ``T♥`` / ``A♦``.

    Hidden cards (boss blinds) return ``??``. Cards missing rank/suit
    (jokers, consumables) fall back to their ``label`` field. When the card
    carries an enhancement/edition/seal, a bracketed tag list is appended
    (e.g. ``4♦[e:Mult,s:Red]``) so the AI can see buffs without a separate
    query. Debuffed cards are wrapped in parentheses.
    """
    if card.get("state", {}).get("hidden"):
        return "??"
    value = card.get("value") or {}
    rank = value.get("rank")
    suit = value.get("suit")
    if not rank or not suit:
        return str(card.get("label") or "?")
    base = f"{rank}{SUIT_SYMBOL.get(suit, suit)}"
    tags = _modifier_tags(card)
    if tags:
        base += "[" + ",".join(tags) + "]"
    if card.get("state", {}).get("debuff"):
        base = f"({base})"
    return base


JOKER_EDITION_LABEL = {
    "FOIL": "+50 chips",
    "HOLO": "+10 mult",
    "HOLOGRAPHIC": "+10 mult",
    "POLYCHROME": "x1.5 mult",
    "NEGATIVE": "+1 slot",
}


def _sticker_prefix(mod: dict[str, Any]) -> str:
    """Edition + sticker tags for jokers/consumables/shop cards."""
    parts: list[str] = []
    perishable = mod.get("perishable")
    if isinstance(perishable, int) and perishable > 0:
        parts.append(f"(perishable {perishable}r)")
    if mod.get("rental"):
        parts.append("(rental -$1/round)")
    ed = mod.get("edition")
    if isinstance(ed, str):
        parts.append(f"({JOKER_EDITION_LABEL.get(ed, ed)})")
    if mod.get("eternal"):
        parts.append("(eternal)")
    return " ".join(parts)


def _joker_line(idx: int, card: dict[str, Any]) -> str:
    name = card.get("label") or "?"
    effect = (card.get("value") or {}).get("effect") or ""
    prefix = f"[{idx}]"
    mod = card.get("modifier") or {}
    if isinstance(mod, dict):
        sticker = _sticker_prefix(mod)
        if sticker:
            prefix += f" {sticker}"
        # Joker-internal enhancement codes (e.g. "SUIT MULT", "DISCARD DOLLARS")
        # are categories already conveyed by the effect text — dropped to avoid
        # leaking raw enum keys.
    return f"{prefix} {name} — {effect}" if effect else f"{prefix} {name}"


def _blind_line(blind: dict[str, Any], *, show_skip_tag: bool = True) -> str:
    name = blind.get("name") or "?"
    status = blind.get("status") or "?"
    score = blind.get("score")
    effect = blind.get("effect") or ""
    tag_name = blind.get("tag_name") or ""
    tag_effect = blind.get("tag_effect") or ""
    parts = [f"blind={name}", f"target={score}", f"status={status}"]
    if effect:
        parts.append(f"effect={effect}")
    line = " ".join(parts)
    if show_skip_tag and (tag_name or tag_effect):
        line += f"\n  tag={tag_name} ({tag_effect}) [skip reward: only triggers if you skip this blind]"
    return line


def _show_blind_skip_tag(status: str) -> bool:
    normalized = (status or "").upper()
    if normalized == "DEFEATED":
        return False
    return normalized in ("CURRENT", "SELECT", "UPCOMING")


def _blinds_block(state: dict[str, Any]) -> str:
    """Compact one-line-per-blind summary for BLIND_SELECT.

    Shows all three blinds (small/big/boss) with target, status, effect, and
    any skip-reward tag, marking the selectable one as ``(current)``. Replaces
    the need to call ``query blinds`` for planning.
    """
    blinds = state.get("blinds") or {}
    order = [("small", "Small"), ("big", "Big"), ("boss", "Boss")]
    lines: list[str] = []
    for key, label in order:
        blind = blinds.get(key)
        if not blind:
            continue
        name = blind.get("name") or f"{label} Blind"
        score = blind.get("score")
        status = blind.get("status") or "?"
        effect = blind.get("effect") or ""
        tag_name = blind.get("tag_name") or ""
        tag_effect = blind.get("tag_effect") or ""
        parts = [f"{label.lower()}: {name}"]
        if score is not None:
            parts.append(f"target={score}")
        if status in ("CURRENT", "SELECT"):
            parts.append("(current, select)")
        else:
            parts.append(f"[{status.lower()}]")
        if effect:
            parts.append(f"— {effect}")
        line = " ".join(parts)
        if _show_blind_skip_tag(status) and (tag_name or tag_effect):
            line += f" [skip reward: {tag_name}"
            if tag_effect:
                line += f" — {tag_effect}"
            line += "]"
        lines.append(line)
    rnd = state.get("round") or {}
    boss_cost = rnd.get("boss_reroll_cost", 10)
    if rnd.get("boss_reroll_available"):
        lines.append(f"  reroll_boss=${boss_cost}{_afford_suffix(boss_cost, state)}")
    elif rnd.get("boss_rerolled") and (state.get("used_vouchers") or {}).get(
        "v_directors_cut"
    ):
        lines.append("  reroll_boss=[used this ante]")
    return "\n".join(lines) if lines else "blinds: (none)"


def _held_tags_line(state: dict[str, Any]) -> str | None:
    """Pending held tags (stable snapshot); oldest first."""
    tags = state.get("held_tags") or []
    if not tags:
        return None
    names = [str(t.get("name") or "?") for t in tags]
    return "held tags (pending): " + " → ".join(names)


def _append_summary_footer(
    lines: list[str], envelope: dict[str, Any], state: dict[str, Any]
) -> None:
    held = _held_tags_line(state)
    if held:
        lines.append(held)
    lines.append(_actions_line(envelope))


def _current_blind(state: dict[str, Any]) -> dict[str, Any] | None:
    for blind in (state.get("blinds") or {}).values():
        if blind.get("status") in ("CURRENT", "SELECT"):
            return blind
    return None


def _header(state: dict[str, Any]) -> str:
    fields = [f"state={state.get('state', 'UNKNOWN')}"]
    if state.get("ante_num") is not None:
        fields.append(f"ante={state['ante_num']}")
    if state.get("round_num") is not None:
        fields.append(f"round={state['round_num']}")
    if state.get("money") is not None:
        fields.append(f"money={state['money']}")
    if state.get("state") == "SHOP" and state.get("bankrupt_at", 0) != 0:
        fields.append(f"buy_power={buy_power(state)}")
    if state.get("deck"):
        fields.append(f"deck={state['deck']}")
    if state.get("stake"):
        fields.append(f"stake={state['stake']}")
    return " ".join(fields)


def _round_line(state: dict[str, Any], target: int | None = None) -> str:
    r = state.get("round") or {}
    chips = r.get("chips", 0)
    hands = r.get("hands_left", 0)
    discards = r.get("discards_left", 0)
    if target is not None:
        score_part = f"score={chips}/{target}"
        if chips < target:
            score_part += f" need={target - chips}"
        else:
            score_part += " beaten"
    else:
        score_part = f"score={chips}"
    return f"round: hands_left={hands} discards_left={discards} {score_part}"


INTEREST_CAP_DEFAULT = 5
INTEREST_PER = 5  # $1 per $5 held, capped


def _economy_parts(state: dict[str, Any], *, include_hands: bool = False) -> list[str]:
    """Pending round-end economy fragments (interest, DG, rental, unused hands)."""
    parts: list[str] = []
    money = state.get("money", 0)
    if money > 0:
        interest = min(money // INTEREST_PER, INTEREST_CAP_DEFAULT)
        if interest > 0:
            parts.append(f"+${interest} interest (cap ${INTEREST_CAP_DEFAULT})")
    jokers = (state.get("jokers") or {}).get("cards") or []
    has_dg = any((j.get("key") or "") == "j_delayed_grat" for j in jokers)
    if has_dg:
        r = state.get("round") or {}
        discards_left = r.get("discards_left", 0)
        discards_used_total = r.get("discards_used", 0)
        if discards_used_total == 0 and discards_left > 0:
            parts.append(f"+${2 * discards_left} delayed_grat if 0 discards used")
    if include_hands:
        r = state.get("round") or {}
        hands_left = r.get("hands_left", 0)
        if hands_left > 0:
            parts.append(f"+${hands_left} unused hands")
    rental_count = sum(
        1
        for j in jokers
        if isinstance((j.get("modifier") or {}), dict)
        and (j.get("modifier") or {}).get("rental")
    )
    if rental_count > 0:
        parts.append(f"-${rental_count}/round rental")
    return parts


def _economy_line(state: dict[str, Any]) -> str | None:
    """Pending interest + Delayed Gratification bonus, if any info to show."""
    parts: list[str] = []
    money = state.get("money", 0)
    if money > 0:
        interest = min(money // INTEREST_PER, INTEREST_CAP_DEFAULT)
        if interest > 0:
            parts.append(f"interest=+${interest} (cap ${INTEREST_CAP_DEFAULT})")
    jokers = (state.get("jokers") or {}).get("cards") or []
    has_dg = any((j.get("key") or "") == "j_delayed_grat" for j in jokers)
    if has_dg:
        r = state.get("round") or {}
        discards_left = r.get("discards_left", 0)
        discards_used_total = r.get("discards_used", 0)
        if discards_used_total == 0 and discards_left > 0:
            parts.append(f"delayed_grat=+${2 * discards_left} if 0 discards used")
    rental_count = sum(
        1
        for j in jokers
        if isinstance((j.get("modifier") or {}), dict)
        and (j.get("modifier") or {}).get("rental")
    )
    if rental_count > 0:
        parts.append(f"rental_due=-${rental_count}/round")
    return "economy: " + " ".join(parts) if parts else None


def _round_eval_block(state: dict[str, Any]) -> list[str]:
    r = state.get("round") or {}
    chips = r.get("chips", 0)
    lines = [f"round won, score={chips}"]
    pending = _economy_parts(state, include_hands=True)
    if pending:
        lines.append("  pending: " + " · ".join(pending))
    if state.get("won") and state.get("victory_overlay"):
        lines.append("→ endless")
    lines.append("→ cash_out")
    return lines


def _afford_suffix(cost: int | str, state: dict[str, Any]) -> str:
    if not isinstance(cost, int):
        return ""
    power = buy_power(state)
    if cost <= power:
        return " [ok]"
    return f" [need ${cost - power}]"


def _shop_buy_suffix(
    card: dict[str, Any], cost: int | str, state: dict[str, Any]
) -> str:
    if buy_blocked_by_slots(card, state):
        return " [slots full]"
    return _afford_suffix(cost, state)


def _hand_line(state: dict[str, Any]) -> str:
    cards = (state.get("hand") or {}).get("cards") or []
    if not cards:
        return "hand: (empty)"
    return "hand: " + " ".join(f"[{i}] {card_label(c)}" for i, c in enumerate(cards))


def _actions_line(envelope: dict[str, Any]) -> str:
    seen: list[str] = []
    for a in envelope.get("actions") or []:
        cmd = a.get("command")
        if cmd and cmd not in seen:
            seen.append(cmd)
    return "actions: " + (" ".join(seen) if seen else "(none)")


def _option_ids(envelope: dict[str, Any], key: str, fallback_fn) -> list[str]:
    items = envelope.get(key)
    if items:
        return [item["id"] for item in items if item.get("id")]
    return [item["id"] for item in fallback_fn()]


def _game_over_hint(state: dict[str, Any]) -> str:
    deck = state.get("deck") or "DECK"
    stake = state.get("stake") or "STAKE"
    return f"→ menu  then  start {deck} {stake} [SEED]"


def _menu_hint(envelope: dict[str, Any]) -> list[str]:
    lines = ["→ start DECK STAKE [SEED]"]
    deck_ids = _option_ids(envelope, "decks", build_decks)
    stake_ids = _option_ids(envelope, "stakes", build_stakes)
    if deck_ids:
        lines.append(f"  decks: {' '.join(deck_ids)} ({len(deck_ids)} total)")
    if stake_ids:
        lines.append(f"  stakes: {' '.join(stake_ids)} ({len(stake_ids)} total)")
    for a in envelope.get("actions") or []:
        if a.get("command") == "load":
            example = (a.get("example") or {}).get("params") or {}
            path = example.get("path")
            if path:
                lines.append(f"→ load {path}")
            break
    return lines


def print_summary(envelope: dict[str, Any]) -> None:
    """Print a compact multi-line summary of a play envelope to stdout."""
    if not envelope.get("ok"):
        err = envelope.get("error") or {}
        print(f"ERROR: {err.get('name', '?')} - {err.get('message', '')}")
        return

    state = envelope.get("gamestate") or {}
    name = state.get("state", "UNKNOWN")
    lines: list[str] = [_header(state)]

    if name == "MENU":
        lines.extend(_menu_hint(envelope))
        lines.append(_actions_line(envelope))
    elif name == "BLIND_SELECT":
        lines.append(_blinds_block(state))
        lines.extend(_joker_lines(state))
        _append_summary_footer(lines, envelope, state)
    elif name == "SELECTING_HAND":
        blind = _current_blind(state)
        target = blind.get("score") if blind else None
        lines.append(_round_line(state, target))
        if blind:
            lines.append(_blind_line(blind, show_skip_tag=False))
        lines.extend(_joker_lines(state))
        lines.append(_hand_line(state))
        econ = _economy_line(state)
        if econ:
            lines.append(econ)
        _append_summary_footer(lines, envelope, state)
    elif name == "ROUND_EVAL":
        lines.extend(_round_eval_block(state))
        _append_summary_footer(lines, envelope, state)
    elif name == "SHOP":
        lines.append(_shop_block(state))
        lines.extend(_joker_lines(state))
        _append_summary_footer(lines, envelope, state)
    elif name == "SMODS_BOOSTER_OPENED":
        lines.append(_pack_block(state))
        if (state.get("hand") or {}).get("cards"):
            lines.append(_hand_line(state))
        lines.extend(_joker_lines(state))
        _append_summary_footer(lines, envelope, state)
    elif name == "GAME_OVER":
        summary = state.get("run_summary") or {}
        result = summary.get("result") or "Lost"
        lines.append(f"GAME_OVER: {result}")
        if summary.get("most_played_hand"):
            mp = summary["most_played_hand"]
            lines.append(f"  most_played: {mp.get('name')} x{mp.get('count')}")
        lines.append(_game_over_hint(state))
        _append_summary_footer(lines, envelope, state)
    elif name in TRANSITION_STATES:
        lines.append("→ transient: wait for stable state, then glance again")
        lines.append(_actions_line(envelope))
    else:
        _append_summary_footer(lines, envelope, state)

    print("\n".join(lines))


def _joker_lines(state: dict[str, Any]) -> list[str]:
    jokers_area = state.get("jokers") or {}
    jokers = jokers_area.get("cards") or []
    if not jokers:
        return []
    jcount = jokers_area.get("count", len(jokers))
    jlimit = jokers_area.get("limit")
    slot = f" ({jcount}/{jlimit})" if jlimit is not None else ""
    out = [
        "jokers"
        + slot
        + ": "
        + "  ".join(_joker_line(i, c) for i, c in enumerate(jokers))
    ]
    cons_area = state.get("consumables") or {}
    consumables = cons_area.get("cards") or []
    if consumables:
        ccount = cons_area.get("count", len(consumables))
        climit = cons_area.get("limit")
        cslot = f" ({ccount}/{climit})" if climit is not None else ""
        out.append(
            "consumables"
            + cslot
            + ": "
            + "  ".join(_joker_line(i, c) for i, c in enumerate(consumables))
        )
    return out


def _shop_card_line(slot: str, card: dict[str, Any], state: dict[str, Any]) -> str:
    """Shop row with modifier stickers when present."""
    label = card.get("label") or "?"
    cost = (card.get("cost") or {}).get("buy", "?")
    effect = (card.get("value") or {}).get("effect") or ""
    mod = card.get("modifier") or {}
    sticker = _sticker_prefix(mod) if isinstance(mod, dict) else ""
    name_part = f"{sticker} {label}".strip() if sticker else label
    afford = _shop_buy_suffix(card, cost, state)
    if effect:
        return f"  {slot} {name_part} ${cost}{afford} — {effect}"
    return f"  {slot} {name_part} ${cost}{afford}"


def _shop_block(state: dict[str, Any]) -> str:
    parts: list[str] = []
    shop = (state.get("shop") or {}).get("cards") or []
    for i, c in enumerate(shop):
        parts.append(_shop_card_line(f"shop[{i}]", c, state))
    vouchers = (state.get("vouchers") or {}).get("cards") or []
    for i, c in enumerate(vouchers):
        label = c.get("label") or "?"
        cost = (c.get("cost") or {}).get("buy", "?")
        effect = (c.get("value") or {}).get("effect") or ""
        afford = _afford_suffix(cost, state)
        parts.append(f"  voucher[{i}] {label} ${cost}{afford} — {effect}")
    packs = (state.get("packs") or {}).get("cards") or []
    for i, c in enumerate(packs):
        label = c.get("label") or "?"
        cost = (c.get("cost") or {}).get("buy", "?")
        effect = (c.get("value") or {}).get("effect") or ""
        afford = _afford_suffix(cost, state)
        parts.append(f"  pack[{i}] {label} ${cost}{afford} — {effect}")
    reroll = (state.get("round") or {}).get("reroll_cost", "?")
    parts.append(f"  reroll=${reroll}{_afford_suffix(reroll, state)}")
    return "shop:\n" + "\n".join(parts) if parts else "shop: (empty)"


def _pack_block(state: dict[str, Any]) -> str:
    cards = (state.get("pack") or {}).get("cards") or []
    parts: list[str] = []
    for i, c in enumerate(cards):
        label = card_label(c)
        effect = (c.get("value") or {}).get("effect", "")
        hint = consumable_target_hint(c)
        hint_suffix = f" ({hint})" if hint else ""
        parts.append(f"  pack[{i}] {label} — {effect}{hint_suffix}")
    return "pack:\n" + "\n".join(parts) if parts else "pack: (empty)"


def main() -> int:
    try:
        raw = fetch_stable_gamestate()
        normalized = normalize_play_state(raw)
        envelope = build_play_envelope(normalized, build_actions(normalized))
        print_summary(envelope)
        return 0
    except APIError as e:
        print(json.dumps(build_error_envelope(e.name, e.message), ensure_ascii=False))
        return 1
    except TimeoutError as e:
        print(json.dumps(build_error_envelope("TIMEOUT", str(e)), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

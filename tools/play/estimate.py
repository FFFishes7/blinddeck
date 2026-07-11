"""Score estimator: `bot.ps1 estimate` — top playable hands + estimated score.

Read-only local computation over the current gamestate. Enumerates ordered 1–5
card plays from the hand, classifies each poker hand, and scores with hand levels + card
buffs + retriggers + modeled jokers + boss debuff + Plasma balancing.

Deterministic-only principle
----------------------------
Only model effects whose outcome is **fixed** once you choose which cards to play.
RNG jokers (Misprint, 8 Ball, Bloodstone, …) stay `unmodeled`. Do not guess random
procs or expected values.

Mechanics should be verified against Balatro source when adding jokers:
  ``%APPDATA%\\Balatro\\Mods\\lovely\\game-dump\\card.lua``
  ``…/functions/state_events.lua``

Registry (modeled / no-op / never-RNG / TODO): ``tools/play/estimate_registry.md``

**Modeling new jokers:** follow the required checklist in that file (gate →
source → implement in ``estimate_jokers.py`` → test → document). See also ``AGENTS.md`` § Estimate modeling.

Output
------
- ``indices`` — ordered list to pass unchanged to ``bot.ps1 play`` (includes kickers
  when they change held-card jokers such as Blackboard).
- ``scoring_indices`` — scoring cards in actual trigger order.
- ``unmodeled_jokers`` — present but not modeled; treat score as lower bound only.

Usage:
    bot.ps1 estimate          # compact top-3 summary
    bot.ps1 estimate --json   # raw envelope
"""

from __future__ import annotations

import json
import sys
from itertools import combinations, permutations
from math import perm

from bot_client import APIError
from envelope import build_error_envelope
from estimate_constants import LOW_RANKS, RANK_CHIPS, RANK_ORDER
from estimate_jokers import (
    NO_SCORE_JOKERS,
    PER_CARD_JOKERS,
    RETRIGGER_ONLY_JOKERS,
    _apply_joker_edition_after,
    _apply_joker_edition_before,
    _baseball_react_xmult,
    _card_is_face,
    _card_is_wild,
    _effective_joker_at,
    _enhancement_scores_on_play,
    _global_joker_bonus,
    _joker_edition_from,
    _modeled,
    _per_card_joker_bonus,
    _retrigger_config,
)
from state import fetch_stable_gamestate
from view import card_label

ESTIMATE_FORMAT = "balatrobot-estimate-v1"
JSON_FLAG = "--json"
MAX_ORDERED_CANDIDATES = 250_000


class InvalidEstimateState(Exception):
    """Raised when estimate is requested outside SELECTING_HAND."""

    def __init__(self, state: str):
        super().__init__(
            f"estimate is only available in SELECTING_HAND, current state is {state}"
        )
        self.state = state


class EstimateCandidateLimitError(Exception):
    """Raised when exhaustive ordered-play search would be unexpectedly large."""

    def __init__(self, hand_size: int, candidate_count: int):
        super().__init__(
            f"ordered estimate search for {hand_size} visible cards would evaluate "
            f"{candidate_count} candidates (limit {MAX_ORDERED_CANDIDATES})"
        )
        self.hand_size = hand_size
        self.candidate_count = candidate_count


# --- card parsing -----------------------------------------------------------


def _parse_card(card: dict) -> dict | None:
    """Parse a gamestate hand card into a flat dict. None if hidden/unknown."""
    if card.get("state", {}).get("hidden"):
        return None
    value = card.get("value") or {}
    rank = value.get("rank")
    suit = value.get("suit")
    if not rank or not suit:
        return None
    mod = card.get("modifier") or {}
    return {
        "rank": rank,
        "suit": suit,
        "enhancement": (mod.get("enhancement") or "") if isinstance(mod, dict) else "",
        "edition": (mod.get("edition") or "") if isinstance(mod, dict) else "",
        "seal": (mod.get("seal") or "") if isinstance(mod, dict) else "",
        "debuff": bool(card.get("state", {}).get("debuff")),
        "label": card_label(card),
    }


# --- poker hand classification ---------------------------------------------


def _consecutive_values(vals: list[int], shortcut: bool) -> bool:
    """True when sorted unique values form a straight (Shortcut allows one gap)."""
    if len(vals) < 2:
        return len(vals) >= 1
    gaps = 0
    for i in range(1, len(vals)):
        diff = vals[i] - vals[i - 1]
        if diff == 1:
            continue
        if shortcut and diff == 2 and gaps == 0:
            gaps = 1
            continue
        return False
    return True


def _straight_indices(
    cards: list[dict],
    idx_with_rank: list[int],
    *,
    min_len: int,
    shortcut: bool,
) -> list[int] | None:
    """Indices of one best straight of at least ``min_len`` cards, if any."""

    rank_groups: dict[str, list[int]] = {}
    for i in idx_with_rank:
        rank_groups.setdefault(cards[i]["rank"], []).append(i)

    def pick_straight(rank_keys: list[str]) -> list[int] | None:
        if len(rank_keys) < min_len:
            return None
        for combo in combinations(rank_keys, min_len):
            vals = sorted(RANK_ORDER[r] for r in combo)
            if _consecutive_values(vals, shortcut):
                return [rank_groups[r][0] for r in combo]
        return None

    normal = pick_straight(list(rank_groups))
    if normal:
        return normal
    wheel = ["A", "2", "3", "4", "5"]
    wheel_present = [r for r in wheel if r in rank_groups]
    if len(wheel_present) >= min_len:
        wheel_vals = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5}
        for combo in combinations(wheel_present, min_len):
            vals = sorted(wheel_vals[r] for r in combo)
            if _consecutive_values(vals, shortcut):
                return [rank_groups[r][0] for r in combo]
    return None


def _flush_indices(
    cards: list[dict], idx_with_rank: list[int], *, min_len: int
) -> list[int] | None:
    """Best flush subset; Wild cards fill any suit (_card_is_wild excludes debuffed)."""
    wild_idx = [i for i in idx_with_rank if _card_is_wild(cards[i])]
    non_wild = [i for i in idx_with_rank if i not in wild_idx]

    from collections import Counter

    suit_count = Counter(cards[i]["suit"] for i in non_wild)
    best: list[int] | None = None
    for suit in "HDSC":
        total = suit_count.get(suit, 0) + len(wild_idx)
        if total >= min_len:
            indices = [i for i in non_wild if cards[i]["suit"] == suit] + wild_idx
            if best is None or len(indices) > len(best):
                best = indices
    return best


def _classify(
    cards: list[dict],
    *,
    four_fingers: bool = False,
    shortcut: bool = False,
) -> tuple[str, list[int]]:
    """Classify 1-5 played cards. Returns (hand_type, scoring_indices_into_played)."""
    # Separate stones (no rank/suit) — they never help form a hand but score.
    idx_with_rank = [i for i, c in enumerate(cards) if c["rank"]]
    ranks = [cards[i]["rank"] for i in idx_with_rank]
    min_run = 4 if four_fingers else 5

    from collections import Counter

    rank_count = Counter(ranks)

    flush_idx = _flush_indices(cards, idx_with_rank, min_len=min_run)
    straight_idx = _straight_indices(
        cards, idx_with_rank, min_len=min_run, shortcut=shortcut
    )
    is_flush = flush_idx is not None
    is_straight = straight_idx is not None
    sf_idx: list[int] | None = None
    if is_flush and is_straight:
        overlap = sorted(set(flush_idx or []) & set(straight_idx or []))
        if len(overlap) >= min_run:
            sf_idx = overlap

    counts = sorted(rank_count.values(), reverse=True)
    # Groups: list of (rank, count) sorted by count desc then rank desc.
    groups = sorted(
        rank_count.items(), key=lambda kv: (-kv[1], -RANK_ORDER.get(kv[0], 0))
    )

    def idx_of_group(count_wanted: int, n: int = 1) -> list[int]:
        out: list[int] = []
        for r, cnt in groups:
            if cnt == count_wanted and len(out) < n * count_wanted:
                for i in idx_with_rank:
                    if cards[i]["rank"] == r and i not in out:
                        out.append(i)
                        if len(out) == n * count_wanted:
                            break
        return out

    # Flush Five before Five of a Kind: five Wilds can satisfy both flush and 5oak.
    if is_flush and len(flush_idx or []) == 5 and counts == [5]:
        return "Flush Five", list(range(5))
    # Flush House: flush + full house (3+2)
    if is_flush and len(flush_idx or []) == 5 and counts == [3, 2]:
        return "Flush House", list(range(5))
    # Five of a Kind
    if counts == [5]:
        return "Five of a Kind", list(range(5))
    # Straight Flush
    if sf_idx:
        return "Straight Flush", sf_idx
    # Four of a Kind
    if counts in ([4, 1], [4]):
        return "Four of a Kind", idx_of_group(4, 1)
    # Full House
    if counts == [3, 2]:
        return "Full House", list(range(5))
    # Flush
    if is_flush and flush_idx:
        return "Flush", flush_idx
    # Straight
    if is_straight and straight_idx:
        return "Straight", straight_idx
    # Three of a Kind
    if counts in ([3, 1, 1], [3, 1], [3]):
        return "Three of a Kind", idx_of_group(3, 1)
    # Two Pair
    if counts in ([2, 2, 1], [2, 2]):
        return "Two Pair", idx_of_group(2, 2)
    # Pair
    if counts in ([2, 1, 1, 1], [2, 1, 1], [2, 1], [2]):
        return "Pair", idx_of_group(2, 1)
    # High Card: single highest-rank card
    best = max(idx_with_rank, key=lambda i: RANK_ORDER.get(cards[i]["rank"], 0))
    return "High Card", [best]


def _classify_flags(jokers: list[dict]) -> tuple[bool, bool, bool]:
    keys = {j.get("key") for j in jokers}
    return ("j_four_fingers" in keys, "j_shortcut" in keys, "j_smeared" in keys)


# --- scoring ----------------------------------------------------------------


def _apply_card_trigger(
    chips: float,
    mult: float,
    card: dict,
    ctx: dict,
    jokers: list[dict],
    *,
    photograph_active: bool = False,
) -> tuple[float, float]:
    """Apply one scoring-card trigger in game order to running totals."""
    if card["debuff"]:
        return chips, mult

    add_chips = 0
    add_mult = 0
    card_xmult = 1.0
    if card["enhancement"] == "STONE":
        add_chips += 50
    else:
        add_chips += RANK_CHIPS.get(card["rank"], 0)
        enh = card["enhancement"]
        if _enhancement_scores_on_play(card, ctx):
            if enh == "BONUS":
                add_chips += 30
            elif enh == "MULT":
                add_mult += 4
            elif enh == "GLASS":
                card_xmult *= 2
            # LUCKY: 1-in-5 +20 Mult proc — unknown at glance; not modeled
            # WILD / GOLD / STEEL: no on-score chip/mult when played
    ed = card["edition"]
    if ed == "FOIL":
        add_chips += 50
    elif ed in ("HOLO", "HOLOGRAPHIC"):
        add_mult += 10
    elif ed == "POLYCHROME":
        card_xmult *= 1.5

    chips += add_chips
    mult += add_mult
    mult *= card_xmult

    # Per-card Joker effects fire left-to-right after the playing card's own
    # enhancement/edition. Copycats occupy their physical slot in this order.
    for i in range(len(jokers)):
        _eff, jkey = _effective_joker_at(i, jokers)
        c_add = 0
        m_add = 0
        xmult = 1.0
        if jkey in PER_CARD_JOKERS or jkey in {"j_ancient", "j_idol"}:
            c_add, m_add, xmult = _per_card_joker_bonus(card, jkey, ctx)
        elif jkey == "j_scary_face" and _card_is_face(card, ctx):
            c_add = 30
        elif jkey == "j_smiley" and _card_is_face(card, ctx):
            m_add = 5
        elif jkey == "j_photograph" and photograph_active:
            xmult = 2
        chips += c_add
        mult += m_add
        mult *= xmult
    return chips, mult


def _score_combo(
    cards: list[dict],
    scoring_idx: list[int],
    hand_type: str,
    hand_level: dict,
    jokers: list[dict],
    cfg: dict,
    ctx: dict,
    dusk_active: bool,
) -> tuple[float, float, int]:
    """Return (chips, mult, score) for one combo."""
    base_chips = hand_level.get("chips", 0)
    base_mult = hand_level.get("mult", 0)
    if ctx.get("flint"):
        base_chips = base_chips // 2
        base_mult = base_mult // 2

    chips = base_chips
    mult = base_mult

    retrigger_all = cfg.get("retrigger_all", 0)
    retrigger_leftmost = cfg.get("retrigger_leftmost", 0)
    if dusk_active and cfg.get("dusk_owned"):
        # Dusk: "triggers all played cards in the final hand twice" => +1 retrigger.
        retrigger_all += 1

    eff_scoring = _ordered_scoring_indices(
        scoring_idx, len(cards), splash=bool(cfg.get("splash"))
    )
    # Leftmost scoring card = first scored in play order (Hanging Chad).
    leftmost = eff_scoring[0] if eff_scoring else -1
    photograph_owned = any(
        _effective_joker_at(i, jokers)[1] == "j_photograph" for i in range(len(jokers))
    )
    first_face_scoring_idx = -1
    if photograph_owned:
        if ctx.get("pareidolia") and eff_scoring:
            first_face_scoring_idx = eff_scoring[0]
        else:
            for i in eff_scoring:
                if _card_is_face(cards[i], ctx):
                    first_face_scoring_idx = i
                    break

    for i in eff_scoring:
        card = cards[i]
        triggers = 1 + retrigger_all
        if card["seal"] == "RED":
            triggers += 1
        if cfg.get("hack_owned") and card["rank"] in LOW_RANKS:
            triggers += 1
        if cfg.get("retrigger_face") and _card_is_face(card, ctx):
            triggers += cfg["retrigger_face"]
        if i == leftmost:
            triggers += retrigger_leftmost
        for _ in range(triggers):
            chips, mult = _apply_card_trigger(
                chips,
                mult,
                card,
                ctx,
                jokers,
                photograph_active=i == first_face_scoring_idx,
            )

    # Held-card phase runs before joker_main. This includes held playing-card
    # effects (Steel) and jokers reacting to held cards (Baron, Shoot the Moon,
    # Raised Fist); physical Joker editions still fire later in their own slot.
    held = ctx.get("held_cards") or []
    ranked_held = [c for c in held if c.get("rank")]
    lowest_held = None
    if ranked_held:
        lowest_value = min(RANK_ORDER.get(c["rank"], 99) for c in ranked_held)
        # Game uses <= while scanning left-to-right, so the last tied low card wins.
        lowest_held = next(
            c
            for c in reversed(ranked_held)
            if RANK_ORDER.get(c["rank"], 99) == lowest_value
        )
    for card in held:
        if card.get("debuff"):
            continue
        triggers = 1 + cfg.get("retrigger_held", 0)
        if card.get("seal") == "RED":
            triggers += 1
        for _ in range(triggers):
            if card.get("enhancement") == "STEEL":
                mult *= 1.5
            for i in range(len(jokers)):
                _eff, key = _effective_joker_at(i, jokers)
                if key == "j_shoot_the_moon" and card.get("rank") == "Q":
                    mult += 13
                elif key == "j_baron" and card.get("rank") == "K":
                    mult *= 1.5
                elif key == "j_raised_fist" and card is lowest_held:
                    mult += 2 * RANK_CHIPS.get(card["rank"], 0)

    # Joker phase (global), left to right. Every physical slot applies its
    # edition here even when its ability fired earlier in the held phase or is
    # repetition-only.
    ctx2 = {
        **ctx,
        "hand_type": hand_type,
        "scoring_cards": [cards[i] for i in eff_scoring],
        "held_cards": ctx.get("held_cards", []),
        "joker_count": ctx.get("joker_count", len(jokers)),
        "joker_limit": ctx.get("joker_limit", 0),
        "stencil_count": ctx.get("stencil_count", 0),
        "cards_played": len(cards),
    }
    for i, j in enumerate(jokers):
        physical = j
        eff, key = _effective_joker_at(i, jokers)
        edition = _joker_edition_from(physical)
        chips, mult = _apply_joker_edition_before(edition, chips, mult)
        if (
            eff
            and key not in NO_SCORE_JOKERS
            and key not in PER_CARD_JOKERS
            and key not in RETRIGGER_ONLY_JOKERS
        ):
            add_c, add_m, xm = _global_joker_bonus(eff, ctx2)
            chips += add_c
            mult += add_m
            mult *= xm
        # Baseball's other_joker reaction fires unconditionally for every
        # physical joker in the joker_main loop, even retrigger-only /
        # no-score jokers whose own ability doesn't fire in joker_main.
        mult *= _baseball_react_xmult(jokers, physical)
        mult = _apply_joker_edition_after(edition, mult)

    if ctx.get("plasma"):
        balanced = (chips + mult) // 2
        chips = balanced
        mult = balanced

    return chips, mult, int(round(chips * mult))


def _ordered_scoring_indices(
    scoring_idx: list[int], card_count: int, *, splash: bool
) -> list[int]:
    """Return scoring-card positions in the same order Balatro will trigger them."""
    if splash:
        return list(range(card_count))
    scoring_set = set(scoring_idx)
    return [i for i in range(card_count) if i in scoring_set]


def _ordered_play_candidate_count(hand_size: int) -> int:
    """Number of exhaustive ordered plays of one through five visible cards."""
    return sum(perm(hand_size, n) for n in range(1, min(5, hand_size) + 1))


def _hand_levels(state: dict) -> dict:
    """Map hand_type -> {chips, mult, level} from gamestate.hands."""
    out = {}
    for name, info in (state.get("hands") or {}).items():
        out[name] = {
            "chips": info.get("chips", 0),
            "mult": info.get("mult", 0),
            "level": info.get("level", 1),
        }
    return out


def _current_blind(state: dict) -> dict | None:
    for blind in (state.get("blinds") or {}).values():
        if blind.get("status") in ("CURRENT", "SELECT"):
            return blind
    return None


def _hands_meta(state: dict) -> dict[str, dict]:
    """Per hand-type counters from gamestate (e.g. Card Sharp)."""
    out: dict[str, dict] = {}
    for name, info in (state.get("hands") or {}).items():
        out[name] = {
            "played_this_round": info.get("played_this_round", 0),
            "played": info.get("played", 0),
        }
        if info.get("visible") is not None:
            out[name]["visible"] = info.get("visible")
    return out


def _ctx(state: dict) -> dict:
    blind = _current_blind(state) or {}
    flint = blind.get("name") == "The Flint"
    plasma = state.get("deck") == "PLASMA"
    r = state.get("round") or {}
    cards = state.get("cards") or {}
    return {
        "flint": flint,
        "plasma": plasma,
        "discards_left": r.get("discards_left", 0),
        "hands_left": r.get("hands_left", 0),
        "deck_remaining": cards.get("count", 0),
        "money": state.get("money", 0),
        "joker_limit": (state.get("jokers") or {}).get("limit", 0),
        "target": blind.get("score"),
        "boss_name": blind.get("name") or "",
        "boss_effect": blind.get("effect") or "",
        "hands_meta": _hands_meta(state),
        "run": state.get("run") or {},
        "ancient_suit": r.get("ancient_suit"),
        "idol_rank": r.get("idol_rank"),
        "idol_suit": r.get("idol_suit"),
    }


# --- top-level estimate -----------------------------------------------------


def score_hand_indices(state: dict, hand_indices: list[int]) -> dict:
    """Score one explicit play (indices into ``state.hand.cards``). For tests/tools."""
    if state.get("state") != "SELECTING_HAND":
        raise InvalidEstimateState(state.get("state") or "UNKNOWN")
    hand_cards = (state.get("hand") or {}).get("cards") or []
    parsed = []
    for i, c in enumerate(hand_cards):
        p = _parse_card(c)
        if p is not None:
            p["hand_index"] = i
            parsed.append(p)
    index_to_local = {p["hand_index"]: i for i, p in enumerate(parsed)}
    combo_local = [index_to_local[hi] for hi in hand_indices]
    if len(combo_local) != len(hand_indices):
        raise ValueError(f"invalid or hidden hand indices: {hand_indices}")

    jokers = (state.get("jokers") or {}).get("cards") or []
    cfg = _retrigger_config(jokers)
    four_fingers, shortcut, smeared = _classify_flags(jokers)
    ctx_base = {
        **_ctx(state),
        "joker_count": len(jokers),
        "stencil_count": sum(1 for j in jokers if j.get("key") == "j_stencil"),
        "pareidolia": any(j.get("key") == "j_pareidolia" for j in jokers),
        "vampire_owned": any(j.get("key") == "j_vampire" for j in jokers),
        "smeared": smeared,
    }
    levels = _hand_levels(state)
    dusk_now = cfg.get("dusk_owned", False) and ctx_base.get("hands_left") == 1

    cards = [parsed[i] for i in combo_local]
    hand_type, scoring_idx = _classify(
        cards, four_fingers=four_fingers, shortcut=shortcut
    )
    level = levels.get(hand_type, {"chips": 0, "mult": 0, "level": 1})
    combo_set = set(combo_local)
    combo_ctx = {
        **ctx_base,
        "held_cards": [parsed[i] for i in range(len(parsed)) if i not in combo_set],
    }
    chips, mult, score = _score_combo(
        cards,
        scoring_idx,
        hand_type,
        level,
        jokers,
        cfg,
        combo_ctx,
        dusk_active=dusk_now,
    )
    return {
        "hand_type": hand_type,
        "indices": hand_indices,
        "scoring_indices": [parsed[combo_local[i]]["hand_index"] for i in scoring_idx],
        "chips": chips,
        "mult": mult,
        "score": score,
        "level": level.get("level", 1),
    }


def estimate(state: dict) -> dict:
    """Compute the estimate envelope from a raw gamestate dict."""
    if state.get("state") != "SELECTING_HAND":
        raise InvalidEstimateState(state.get("state") or "UNKNOWN")
    hand_cards = (state.get("hand") or {}).get("cards") or []
    parsed = []
    for i, c in enumerate(hand_cards):
        p = _parse_card(c)
        if p is not None:
            p["hand_index"] = i
            parsed.append(p)
    jokers = (state.get("jokers") or {}).get("cards") or []
    cfg = _retrigger_config(jokers)
    four_fingers, shortcut, smeared = _classify_flags(jokers)
    ctx = {
        **_ctx(state),
        "joker_count": len(jokers),
        "stencil_count": sum(1 for j in jokers if j.get("key") == "j_stencil"),
        "pareidolia": any(j.get("key") == "j_pareidolia" for j in jokers),
        "vampire_owned": any(j.get("key") == "j_vampire" for j in jokers),
        "smeared": smeared,
    }
    levels = _hand_levels(state)
    _, unmodeled = _modeled(jokers)

    max_play = min(5, len(parsed))
    candidate_count = _ordered_play_candidate_count(len(parsed))
    if candidate_count > MAX_ORDERED_CANDIDATES:
        raise EstimateCandidateLimitError(len(parsed), candidate_count)

    results: list[dict] = []
    # Dusk: game checks hands_left == 0 during evaluate_play (after
    # ease_hands_played(-1)); API still shows hands_left == 1 before you play.
    dusk_now = cfg.get("dusk_owned", False) and ctx.get("hands_left") == 1
    for n in range(1, max_play + 1):
        for combo in permutations(range(len(parsed)), n):
            cards = [parsed[i] for i in combo]
            hand_type, scoring_idx = _classify(
                cards, four_fingers=four_fingers, shortcut=shortcut
            )
            level = levels.get(hand_type, {"chips": 0, "mult": 0, "level": 1})
            combo_set = set(combo)
            combo_ctx = {
                **ctx,
                "held_cards": [
                    parsed[i] for i in range(len(parsed)) if i not in combo_set
                ],
            }
            chips, mult, score = _score_combo(
                cards,
                scoring_idx,
                hand_type,
                level,
                jokers,
                cfg,
                combo_ctx,
                dusk_active=dusk_now,
            )
            ordered_scoring_idx = _ordered_scoring_indices(
                scoring_idx, len(cards), splash=bool(cfg.get("splash"))
            )
            scoring_play_indices = [
                parsed[combo[i]]["hand_index"] for i in ordered_scoring_idx
            ]
            play_indices = [parsed[i]["hand_index"] for i in combo]
            scoring_labels = [parsed[combo[i]]["label"] for i in ordered_scoring_idx]
            play_labels = [parsed[i]["label"] for i in combo]
            results.append(
                {
                    "hand_type": hand_type,
                    "indices": play_indices,
                    "cards": play_labels,
                    "scoring_indices": scoring_play_indices,
                    "scoring_cards": scoring_labels,
                    "chips": chips,
                    "mult": mult,
                    "score": score,
                    "level": level.get("level", 1),
                }
            )

    # Drop duplicate scoring sets from different kicker/order choices. Prefer
    # higher score, then fewer cards, then natural left-to-right order, then a
    # stable lexicographic order.
    deduped: dict[tuple[str, tuple[int, ...]], dict] = {}
    for r in results:
        key = (r["hand_type"], tuple(sorted(r["scoring_indices"])))
        prev = deduped.get(key)
        r_natural = r["indices"] == sorted(r["indices"])
        prev_natural = prev is not None and prev["indices"] == sorted(prev["indices"])
        if (
            prev is None
            or r["score"] > prev["score"]
            or (
                r["score"] == prev["score"] and len(r["indices"]) < len(prev["indices"])
            )
            or (
                r["score"] == prev["score"]
                and len(r["indices"]) == len(prev["indices"])
                and r_natural
                and not prev_natural
            )
            or (
                r["score"] == prev["score"]
                and len(r["indices"]) == len(prev["indices"])
                and r_natural == prev_natural
                and tuple(r["indices"]) < tuple(prev["indices"])
            )
        ):
            deduped[key] = r
    results = list(deduped.values())

    results.sort(key=lambda r: (r["score"], -len(r["indices"])), reverse=True)
    top = results[:3]

    return {
        "ok": True,
        "format": ESTIMATE_FORMAT,
        "estimate": {
            "target": ctx["target"],
            "beats_target": [r for r in top if r["score"] >= (ctx["target"] or 0)],
            "top": top,
            "unmodeled_jokers": unmodeled,
        },
    }


def _format(est: dict) -> str:
    e = est["estimate"]
    lines: list[str] = []
    target = e["target"]
    for k, r in enumerate(e["top"]):
        beat = "BEATS" if r["score"] >= (target or 0) else "short"
        score_part = ""
        if r.get("scoring_indices") and r["scoring_indices"] != r["indices"]:
            score_part = f" scoring={r['scoring_indices']}"
        lines.append(
            f"  #{k + 1} {r['hand_type']} (lvl {r['level']}) "
            f"idx={r['indices']} {r['cards']}{score_part}  "
            f"chips={r['chips']} mult={r['mult']} score={r['score']} [{beat}]"
        )
    if e["unmodeled_jokers"]:
        lines.append(
            "  unmodeled: "
            + ", ".join(e["unmodeled_jokers"])
            + " (base-only; treat effects as unknown)"
        )
    return "\n".join(lines)


def _parse_argv(argv: list[str]) -> tuple[list[str], bool]:
    json_out = False
    rest: list[str] = []
    for arg in argv:
        if arg == JSON_FLAG:
            json_out = True
        else:
            rest.append(arg)
    return rest, json_out


def main() -> int:
    _, json_out = _parse_argv(sys.argv[1:])
    try:
        raw = fetch_stable_gamestate()
        est = estimate(raw)
        print(json.dumps(est, ensure_ascii=False) if json_out else _format(est))
        return 0
    except InvalidEstimateState as e:
        print(
            json.dumps(
                build_error_envelope("INVALID_STATE", str(e), fmt=ESTIMATE_FORMAT),
                ensure_ascii=False,
            )
        )
        return 1
    except EstimateCandidateLimitError as e:
        print(
            json.dumps(
                build_error_envelope("BAD_REQUEST", str(e), fmt=ESTIMATE_FORMAT),
                ensure_ascii=False,
            )
        )
        return 1
    except APIError as e:
        print(json.dumps(build_error_envelope(e.name, e.message), ensure_ascii=False))
        return 1
    except TimeoutError as e:
        print(json.dumps(build_error_envelope("TIMEOUT", str(e)), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

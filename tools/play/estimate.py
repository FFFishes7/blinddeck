"""Score estimator: `bot.ps1 estimate` — top playable hands + estimated score.

Read-only local computation over the current gamestate. Enumerates 1–5 card plays
from the hand, classifies each poker hand, and scores with hand levels + card
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
source → implement → test → document). See also ``AGENTS.md`` § Estimate modeling.

Output
------
- ``indices`` — pass directly to ``bot.ps1 play`` (includes kickers when they change
  held-card jokers such as Blackboard).
- ``scoring_indices`` — cards that contribute to the poker hand type only.
- ``unmodeled_jokers`` — present but not modeled; treat score as lower bound only.

Usage:
    bot.ps1 estimate          # compact top-3 summary
    bot.ps1 estimate --json   # raw envelope
"""

from __future__ import annotations

import json
import re
import sys
from itertools import combinations

from bot_client import APIError
from envelope import build_error_envelope
from state import fetch_stable_gamestate
from view import card_label

ESTIMATE_FORMAT = "balatrobot-estimate-v1"
JSON_FLAG = "--json"

class InvalidEstimateState(Exception):
    """Raised when estimate is requested outside SELECTING_HAND."""

    def __init__(self, state: str):
        super().__init__(f"estimate is only available in SELECTING_HAND, current state is {state}")
        self.state = state

# --- card value tables ------------------------------------------------------

RANK_CHIPS = {
    "A": 11,
    "K": 10,
    "Q": 10,
    "J": 10,
    "T": 10,
    "9": 9,
    "8": 8,
    "7": 7,
    "6": 6,
    "5": 5,
    "4": 4,
    "3": 3,
    "2": 2,
}
RANK_ORDER = {
    "A": 14,
    "K": 13,
    "Q": 12,
    "J": 11,
    "T": 10,
    "9": 9,
    "8": 8,
    "7": 7,
    "6": 6,
    "5": 5,
    "4": 4,
    "3": 3,
    "2": 2,
}
EVEN_RANKS = {"2", "4", "6", "8", "10", "T"}
ODD_RANKS = {"A", "3", "5", "7", "9"}
FIBONACCI_RANKS = {"A", "2", "3", "5", "8"}
FACE_RANKS = {"J", "Q", "K"}
LOW_RANKS = {"2", "3", "4", "5"}

# Type jokers: bonus when played hand matches poker type (card.lua joker_main).
TYPE_MULT_JOKERS: dict[str, tuple[str, int]] = {
    "j_jolly": ("Pair", 8),
    "j_zany": ("Three of a Kind", 12),
    "j_mad": ("Two Pair", 10),
    "j_crazy": ("Straight", 12),
    "j_droll": ("Flush", 10),
}
TYPE_CHIPS_JOKERS: dict[str, tuple[str, int]] = {
    "j_sly": ("Pair", 50),
    "j_wily": ("Three of a Kind", 100),
    "j_clever": ("Two Pair", 80),
    "j_devious": ("Straight", 100),
    "j_crafty": ("Flush", 80),
}
# Planets: ×Mult when played hand matches poker type (card.lua joker_main x_mult).
TYPE_XMULT_JOKERS: dict[str, tuple[str, float]] = {
    "j_duo": ("Pair", 2),
    "j_trio": ("Three of a Kind", 3),
    "j_order": ("Straight", 3),
    "j_tribe": ("Flush", 2),
}

# Poker hand type -> Balatro order (lower = better). Matches `query hands`.
HAND_ORDER = {
    "Flush Five": 1,
    "Flush House": 2,
    "Five of a Kind": 3,
    "Straight Flush": 4,
    "Four of a Kind": 5,
    "Full House": 6,
    "Flush": 7,
    "Straight": 8,
    "Three of a Kind": 9,
    "Two Pair": 10,
    "Pair": 11,
    "High Card": 12,
}

# Jokers Blueprint / Brainstorm cannot copy (game.lua blueprint_compat = false).
BLUEPRINT_INCOMPATIBLE = frozenset(
    {
        "j_four_fingers",
        "j_credit_card",
        "j_chaos",
        "j_delayed_grat",
        "j_pareidolia",
        "j_egg",
        "j_splash",
        "j_sixth_sense",
        "j_shortcut",
        "j_cloud_9",
        "j_rocket",
        "j_midas_mask",
        "j_gift",
        "j_turtle_bean",
        "j_to_the_moon",
        "j_juggler",
        "j_drunkard",
        "j_golden",
        "j_trading",
        "j_mr_bones",
        "j_troubadour",
        "j_smeared",
        "j_ring_master",
        "j_merry_andy",
        "j_oops",
        "j_invisible",
        "j_satellite",
        "j_astronomer",
        "j_chicot",
    }
)


def _blueprint_compatible(key: str) -> bool:
    return bool(key) and key not in BLUEPRINT_INCOMPATIBLE


def _resolve_chain_from(index: int, jokers: list[dict], depth: int = 0) -> dict | None:
    """Resolve copy-chain from joker slot ``index`` (Blueprint/Brainstorm recursion)."""
    if depth > len(jokers) or index < 0 or index >= len(jokers):
        return None
    j = jokers[index]
    key = j.get("key") or ""
    if not _blueprint_compatible(key):
        return None
    if key == "j_blueprint":
        if index + 1 >= len(jokers):
            return None
        return _resolve_chain_from(index + 1, jokers, depth + 1)
    if key == "j_brainstorm":
        if not jokers or jokers[0].get("key") == "j_brainstorm":
            return None
        return _resolve_chain_from(0, jokers, depth + 1)
    return j


def _resolve_copy_target(index: int, jokers: list[dict]) -> dict | None:
    """Joker whose scoring effect Blueprint/Brainstorm applies at ``index``."""
    if index >= len(jokers):
        return None
    key = jokers[index].get("key") or ""
    if key == "j_brainstorm":
        return _resolve_chain_from(0, jokers)
    if key == "j_blueprint":
        if index + 1 >= len(jokers):
            return None
        return _resolve_chain_from(index + 1, jokers)
    return None


def _effective_joker_at(index: int, jokers: list[dict]) -> tuple[dict | None, str]:
    """Return (joker, key) used for scoring at slot ``index`` (copycats delegate)."""
    j = jokers[index]
    key = j.get("key") or ""
    if key in ("j_blueprint", "j_brainstorm"):
        target = _resolve_copy_target(index, jokers)
        if not target:
            return None, key
        return target, target.get("key") or ""
    return j, key


# --- joker registry ---------------------------------------------------------
# New joker? Mandatory checklist: tools/play/estimate_registry.md
# (gate → source in card.lua → implement → test → update registry tables).

# Jokers with no direct score impact (economy / utility) — modeled as no-op so
# they do NOT trigger an unmodeled warning.
NO_SCORE_JOKERS = {
    "j_midas_mask",
    "j_delayed_grat",
    "j_egg",
    "j_gift",
    "j_golden",
    "j_faceless",
    "j_cartomancer",
    "j_certificate",
    "j_mail",
    "j_ripple",
    "j_trading",
    "j_riff_raff",
    "j_drunkard",
    "j_matador",
    "j_cloud_9",
    "j_hiker",
    "j_rough_gem",
    "j_golden_ticket",
    "j_business",
    "j_reserved_parking",
}

# Per-card joker bonus for ONE trigger of a scoring card.
# Returns (add_chips, add_mult, xmult). xmult from cards is applied per-trigger.
PER_CARD_JOKERS = {
    "j_greedy_joker": lambda c: (0, 3 if c["suit"] == "D" else 0, 1),
    "j_lusty_joker": lambda c: (0, 3 if c["suit"] == "H" else 0, 1),
    "j_wrathful_joker": lambda c: (0, 3 if c["suit"] == "S" else 0, 1),
    "j_gluttenous_joker": lambda c: (0, 3 if c["suit"] == "C" else 0, 1),
    "j_walkie_talkie": lambda c: (
        (10 if c["rank"] in ("T", "10", "4") else 0),
        (4 if c["rank"] in ("T", "10", "4") else 0),
        1,
    ),
    "j_fibonacci": lambda c: (0, 8 if c["rank"] in FIBONACCI_RANKS else 0, 1),
    "j_even_steven": lambda c: (0, 4 if c["rank"] in EVEN_RANKS else 0, 1),
    "j_odd_todd": lambda c: (31 if c["rank"] in ODD_RANKS else 0, 0, 1),
    "j_onyx_agate": lambda c: (0, 7 if c["suit"] == "C" else 0, 1),  # +7 M per club
    "j_scholar": lambda c: (
        (20 if c["rank"] == "A" else 0),
        (4 if c["rank"] == "A" else 0),
        1,
    ),
    "j_arrowhead": lambda c: (50 if c["suit"] == "S" else 0, 0, 1),
    "j_triboulet": lambda c: (0, 0, 2 if c["rank"] in ("K", "Q") else 1),
}

_RED_SUITS = frozenset({"H", "D"})
_BLACK_SUITS = frozenset({"S", "C"})


def _card_is_suit(card: dict, suit: str, ctx: dict) -> bool:
    """Mirror ``Card:is_suit`` including Smeared Joker (Hearts≈Diamonds, Spades≈Clubs)."""
    cs = card.get("suit")
    if not cs:
        return False
    if cs == suit:
        return True
    if not ctx.get("smeared"):
        return False
    if suit in _RED_SUITS and cs in _RED_SUITS:
        return True
    return suit in _BLACK_SUITS and cs in _BLACK_SUITS


def _per_card_joker_bonus(card: dict, key: str, ctx: dict) -> tuple[int, int, float]:
    """Per-card joker bonus for one scoring-card trigger."""
    if key == "j_greedy_joker":
        return (0, 3 if _card_is_suit(card, "D", ctx) else 0, 1)
    if key == "j_lusty_joker":
        return (0, 3 if _card_is_suit(card, "H", ctx) else 0, 1)
    if key == "j_wrathful_joker":
        return (0, 3 if _card_is_suit(card, "S", ctx) else 0, 1)
    if key == "j_gluttenous_joker":
        return (0, 3 if _card_is_suit(card, "C", ctx) else 0, 1)
    if key == "j_onyx_agate":
        return (0, 7 if _card_is_suit(card, "C", ctx) else 0, 1)
    if key == "j_arrowhead":
        return (50 if _card_is_suit(card, "S", ctx) else 0, 0, 1)
    fn = PER_CARD_JOKERS.get(key)
    if fn:
        return fn(card)
    return (0, 0, 1)


def _flower_pot_active(scoring_cards: list[dict], ctx: dict) -> bool:
    tallies = {"H": 0, "D": 0, "S": 0, "C": 0}
    for card in scoring_cards:
        if _card_is_suit(card, "H", ctx):
            if tallies["H"] == 0:
                tallies["H"] = 1
        elif _card_is_suit(card, "D", ctx):
            if tallies["D"] == 0:
                tallies["D"] = 1
        elif _card_is_suit(card, "S", ctx):
            if tallies["S"] == 0:
                tallies["S"] = 1
        elif _card_is_suit(card, "C", ctx):
            if tallies["C"] == 0:
                tallies["C"] = 1
    return all(tallies[s] > 0 for s in "HDSC")


def _seeing_double_active(scoring_cards: list[dict], ctx: dict) -> bool:
    tallies = {s: 0 for s in "HDSC"}
    for card in scoring_cards:
        for s in "HDSC":
            if tallies[s] == 0 and _card_is_suit(card, s, ctx):
                tallies[s] = 1
    return tallies["C"] > 0 and any(tallies[s] > 0 for s in "HDS")


def _parse_effect_bonus(joker: dict, stat: str) -> int:
    """Parse current +Mult or +Chips from localized joker `value.effect` UI text.

    Effect strings come from the game's locale (en-us, zh_CN, de, …). We match
    numeric patterns tied to stat type markers, not a single language prefix.
    """
    effect = (joker.get("value") or {}).get("effect") or ""
    if not effect:
        return 0

    if stat == "mult":
        type_markers = r"(?:Mult|倍率|Extra[-\s]*Mult|extra\s*Mult)\b"
        zh_compact = r"当前为\+(\d+)(?:倍率)?"
    else:
        type_markers = r"(?:Chips|筹码|Extra[-\s]*Chips|extra\s*chips)\b"
        zh_compact = r"当前为\+(\d+)(?:筹码)?"

    m = re.search(rf"\+(\d+(?:\.\d+)?)\s*{type_markers}", effect, re.I)
    if m:
        return int(float(m.group(1)))

    m = re.search(zh_compact, effect)
    if m:
        return int(m.group(1))

    # Parenthetical runtime value, e.g. "(Currently +21 Mult )" or "(Currently +0 )".
    m = re.search(
        rf"\([^)]*?\+(\d+(?:\.\d+)?)\s*(?:{type_markers}|\))",
        effect,
        re.I,
    )
    if m:
        return int(float(m.group(1)))

    return 0


def _parse_effect_mult(joker: dict) -> int:
    return _parse_effect_bonus(joker, "mult")


def _parse_effect_chips(joker: dict) -> int:
    return _parse_effect_bonus(joker, "chips")


def _parse_effect_xmult(joker: dict) -> float:
    """Parse current XMult from localized joker `value.effect` UI text (fallback)."""
    effect = (joker.get("value") or {}).get("effect") or ""
    if not effect:
        return 1.0
    type_markers = r"(?:Mult|倍率)\b"
    for pat in (
        rf"X(\d+(?:\.\d+)?)\s*{type_markers}",
        r"当前为X(\d+(?:\.\d+)?)倍率",
        rf"\([^)]*?X(\d+(?:\.\d+)?)\s*(?:{type_markers}|\))",
    ):
        m = re.search(pat, effect, re.I)
        if m:
            return float(m.group(1))
    return 1.0


def _joker_stats(joker: dict) -> dict:
    """Structured scoring snapshot from gamestate (`value.stats`), if present."""
    raw = (joker.get("value") or {}).get("stats")
    return raw if isinstance(raw, dict) else {}


def _stat_mult(joker: dict) -> int:
    stats = _joker_stats(joker)
    key = joker.get("key") or ""
    if key in STAT_ONLY_MULT_JOKERS:
        if "mult" in stats:
            return int(stats["mult"])
        return 0
    if "mult" in stats:
        return int(stats["mult"])
    return _parse_effect_mult(joker)


def _stat_chips(joker: dict) -> int:
    stats = _joker_stats(joker)
    if "chips" in stats:
        return int(stats["chips"])
    key = joker.get("key") or ""
    # Growth jokers embed "+15" / "+8" in static descriptions — never parse those.
    if key in EFFECT_CHIPS_JOKERS:
        return 0
    return _parse_effect_chips(joker)


def _stat_xmult(joker: dict) -> float:
    stats = _joker_stats(joker)
    if "x_mult" in stats:
        return float(stats["x_mult"])
    return _parse_effect_xmult(joker)


# Jokers whose +Mult is read from effect text (dynamic run state, deterministic at glance time).
EFFECT_MULT_JOKERS = frozenset(
    {
        "j_swashbuckler",
        "j_ceremonial",
        "j_flash",
        "j_popcorn",
        "j_green_joker",
        "j_red_card",
        "j_fortune_teller",
        "j_ride_the_bus",
        "j_trousers",
    }
)

# Growth jokers: never parse static +N from localized effect text; use stats only.
STAT_ONLY_MULT_JOKERS = frozenset(
    {
        "j_ride_the_bus",
        "j_green_joker",
        "j_ceremonial",
        "j_red_card",
        "j_popcorn",
        "j_flash",
    }
)

BASEBALL_UNCOMMON_XMULT = 1.5

# Jokers whose +chips is read from effect text (Ice Cream, Castle, Runner, …).
EFFECT_CHIPS_JOKERS = frozenset(
    {
        "j_ice_cream",
        "j_castle",
        "j_square",
        "j_runner",
        "j_wee",
        "j_stone",
    }
)

# Jokers whose ×Mult is read from effect text (Steel Joker, Throwback, …).
EFFECT_XMULT_JOKERS = frozenset(
    {
        "j_steel_joker",
        "j_throwback",
        "j_constellation",
        "j_obelisk",
        "j_campfire",
        "j_glass",
        "j_lucky_cat",
        "j_hologram",
        "j_ramen",
        "j_madness",
        "j_vampire",
        "j_hit_the_road",
    }
)

# Hand types that satisfy growth conditions (game uses poker_hands flags; we mirror).
_RUNNER_HAND_TYPES = frozenset({"Straight", "Straight Flush"})
_TROUSERS_HAND_TYPES = frozenset({"Two Pair", "Full House", "Flush House"})


def _blackboard_held_ok(card: dict) -> bool:
    """Held card counts for Blackboard (Wild satisfies Spade/Club-only rule)."""
    if card.get("enhancement") == "WILD":
        return True
    return card.get("suit") in {"S", "C"}


def _scoring_enhanced_count(scoring_cards: list[dict]) -> int:
    return sum(
        1
        for c in scoring_cards
        if c.get("enhancement") not in (None, "", "BASE")
    )


def _project_chips_joker(joker: dict, key: str, ctx: dict) -> int:
    """Chips from stats plus in-hand growth for Square / Runner / Wee."""
    chips = _stat_chips(joker)
    cards_played = ctx.get("cards_played", 5)
    hand_type = ctx.get("hand_type") or ""
    scoring = ctx.get("scoring_cards") or []
    if key == "j_square" and cards_played == 4:
        chips += 4
    elif key == "j_runner" and hand_type in _RUNNER_HAND_TYPES:
        chips += 15
    elif key == "j_wee":
        chips += 8 * sum(1 for c in scoring if c.get("rank") == "2")
    return chips


def _round_aware_card_xmult(card: dict, jokers: list[dict], ctx: dict) -> float:
    """Per-card ×Mult from jokers that depend on round scoring targets."""
    xmult = 1.0
    for j in jokers:
        key = j.get("key") or ""
        if key == "j_ancient" and ctx.get("ancient_suit") and _card_is_suit(card, ctx["ancient_suit"], ctx):
            xmult *= 1.5
        if (
            key == "j_idol"
            and ctx.get("idol_rank")
            and ctx.get("idol_suit")
            and card.get("rank") == ctx["idol_rank"]
            and _card_is_suit(card, ctx["idol_suit"], ctx)
        ):
            xmult *= 2
    return xmult


def _card_is_face(card: dict, ctx: dict) -> bool:
    """Face check mirroring ``Card:is_face`` (Pareidolia makes every card a face)."""
    if ctx.get("pareidolia"):
        return True
    return card.get("rank") in FACE_RANKS


def _ride_the_bus_step(joker: dict) -> int:
    stats = _joker_stats(joker)
    if "ride_the_bus_step" in stats:
        return int(stats["ride_the_bus_step"])
    return 1


def _project_ride_the_bus_mult(joker: dict, ctx: dict) -> int:
    """+Mult from stats; +step when no scoring face; reset to 0 if any scoring face."""
    scoring = ctx.get("scoring_cards") or []
    if any(_card_is_face(c, ctx) for c in scoring):
        return 0
    return _stat_mult(joker) + _ride_the_bus_step(joker)


def _green_hand_add(joker: dict) -> int:
    stats = _joker_stats(joker)
    if "green_hand_add" in stats:
        return int(stats["green_hand_add"])
    return 1


def _project_green_joker_mult(joker: dict, ctx: dict) -> int:
    """+Mult after context.before increment (hand_add per hand played)."""
    _ = ctx
    return _stat_mult(joker) + _green_hand_add(joker)


def _obelisk_step(joker: dict) -> float:
    stats = _joker_stats(joker)
    if "obelisk_step" in stats:
        return float(stats["obelisk_step"])
    return 0.2


def _obelisk_resets(hand_type: str, hands_meta: dict[str, dict]) -> bool:
    """True when playing *hand_type* resets Obelisk (sole most-played after increment).

    Game increments ``hands[scoring_name].played`` before ``context.before``; only
    visible poker hand types participate (``SMODS.is_poker_hand_visible``).
    """
    played_after = hands_meta.get(hand_type, {}).get("played", 0) + 1
    for name, meta in hands_meta.items():
        if name == hand_type:
            continue
        if meta.get("visible") is False:
            continue
        if meta.get("played", 0) >= played_after:
            return False
    return True


def _project_obelisk_xmult(joker: dict, ctx: dict) -> float:
    """Project Obelisk ×Mult after context.before for this hand type."""
    hand_type = ctx.get("hand_type") or ""
    hands_meta = ctx.get("hands_meta") or {}
    if _obelisk_resets(hand_type, hands_meta):
        return 1.0
    base = _stat_xmult(joker)
    return (base if base > 1.0 else 1.0) + _obelisk_step(joker)


def _global_joker_bonus(joker: dict, ctx: dict) -> tuple[int, int, float]:
    """Global (hand-level) joker contribution: (add_chips, add_mult, xmult)."""
    key = joker.get("key") or ""
    hand_type = ctx.get("hand_type") or ""
    if key in TYPE_MULT_JOKERS:
        need, bonus = TYPE_MULT_JOKERS[key]
        return (0, bonus, 1) if hand_type == need else (0, 0, 1)
    if key in TYPE_CHIPS_JOKERS:
        need, bonus = TYPE_CHIPS_JOKERS[key]
        return (bonus, 0, 1) if hand_type == need else (0, 0, 1)
    if key in TYPE_XMULT_JOKERS:
        need, bonus = TYPE_XMULT_JOKERS[key]
        return (0, 0, bonus) if hand_type == need else (0, 0, 1)
    if key == "j_joker":
        return (0, 4, 1)
    if key == "j_abstract":
        return (0, 3 * ctx.get("joker_count", 0), 1)
    if key == "j_mystic_summit":
        return (0, 15 if ctx["discards_left"] == 0 else 0, 1)
    if key == "j_trousers":
        mult = _stat_mult(joker)
        if hand_type in _TROUSERS_HAND_TYPES:
            mult += 2
        return (0, mult, 1) if mult > 0 else (0, 0, 1)
    if key == "j_ride_the_bus":
        mult = _project_ride_the_bus_mult(joker, ctx)
        return (0, mult, 1) if mult > 0 else (0, 0, 1)
    if key == "j_green_joker":
        mult = _project_green_joker_mult(joker, ctx)
        return (0, mult, 1) if mult > 0 else (0, 0, 1)
    if key == "j_swashbuckler" or key in EFFECT_MULT_JOKERS:
        return (0, _stat_mult(joker), 1)
    if key == "j_blackboard":
        held_cards = ctx.get("held_cards") or []
        if held_cards and all(_blackboard_held_ok(c) for c in held_cards):
            return (0, 0, 3)
        return (0, 0, 1)
    if key == "j_flower_pot":
        scoring = ctx.get("scoring_cards") or []
        return (0, 0, 3) if _flower_pot_active(scoring, ctx) else (0, 0, 1)
    if key == "j_family":  # The Family: X4 if hand contains a 4oak
        return (0, 0, 4) if ctx["hand_type"] == "Four of a Kind" else (0, 0, 1)
    if key in EFFECT_XMULT_JOKERS:
        xm = _stat_xmult(joker)
        if key == "j_vampire":
            base = xm if xm > 1.0 else 1.0
            xm = base + 0.1 * _scoring_enhanced_count(ctx.get("scoring_cards") or [])
            return (0, 0, xm) if xm > 1.0 else (0, 0, 1)
        if key == "j_madness":
            return (0, 0, xm) if xm > 1.0 else (0, 0, 1)
        if key == "j_obelisk":
            xm = _project_obelisk_xmult(joker, ctx)
            return (0, 0, xm) if xm > 1.0 else (0, 0, 1)
        if key == "j_steel_joker" and xm <= 1.0:
            return (0, 0, 1)
        if key == "j_throwback" and xm <= 1.0:
            skips = (ctx.get("run") or {}).get("skips", 0)
            if skips > 0:
                xm = 1.0 + 0.25 * skips
        return (0, 0, xm) if xm > 1.0 else (0, 0, 1)
    if key == "j_blue_joker":
        return (ctx.get("deck_remaining", 0) * 2, 0, 1)
    if key == "j_half":
        return (0, 20, 1) if ctx.get("cards_played", 5) <= 3 else (0, 0, 1)
    if key == "j_banner":
        dl = ctx.get("discards_left", 0)
        return (30 * dl, 0, 1) if dl > 0 else (0, 0, 1)
    if key == "j_gros_michel":
        return (0, 15, 1)
    if key == "j_acrobat":
        return (0, 0, 3) if ctx.get("hands_left") == 1 else (0, 0, 1)
    if key == "j_card_sharp":
        ptr = (ctx.get("hands_meta") or {}).get(hand_type, {}).get("played_this_round", 0)
        # Game increments played_this_round before scoring; estimate from pre-play state.
        return (0, 0, 3) if ptr >= 1 else (0, 0, 1)
    if key == "j_stuntman":
        return (250, 0, 1)
    if key == "j_bootstraps":
        tiers = ctx.get("money", 0) // 5
        return (0, 2 * tiers, 1) if tiers >= 1 else (0, 0, 1)
    if key == "j_supernova":
        played = (ctx.get("hands_meta") or {}).get(hand_type, {}).get("played", 0)
        return (0, played, 1)
    if key == "j_seeing_double":
        scoring = ctx.get("scoring_cards") or []
        return (0, 0, 2) if _seeing_double_active(scoring, ctx) else (0, 0, 1)
    if key == "j_cavendish":
        return (0, 0, 3)
    if key == "j_bull":
        return (max(0, ctx.get("money", 0)) * 2, 0, 1)
    if key in EFFECT_CHIPS_JOKERS:
        chips = _project_chips_joker(joker, key, ctx)
        return (chips, 0, 1) if chips > 0 else (0, 0, 1)
    if key == "j_stencil":
        limit = ctx.get("joker_limit", 0)
        count = ctx.get("joker_count", 0)
        stencils = ctx.get("stencil_count", 0)
        empty = limit - count
        if empty > 0:
            return (0, 0, empty + stencils)
        return (0, 0, 1)
    if key == "j_erosion":
        run = ctx.get("run") or {}
        missing = max(
            0,
            int(run.get("starting_deck_size", 52)) - int(run.get("deck_size", 52)),
        )
        return (0, 4 * missing, 1) if missing > 0 else (0, 0, 1)
    if key == "j_drivers_license":
        xm = _stat_xmult(joker)
        return (0, 0, xm) if xm > 1.0 else (0, 0, 1)
    if key == "j_loyalty_card":
        stats = _joker_stats(joker)
        every = int(stats.get("loyalty_every", 5))
        remaining = stats.get("loyalty_remaining")
        if remaining is not None and int(remaining) == every:
            return (0, 0, float(stats.get("loyalty_x_mult", 4)))
        return (0, 0, 1)
    return (0, 0, 1)


def _joker_rarity(joker: dict) -> str | None:
    raw = (joker.get("value") or {}).get("rarity")
    return raw if isinstance(raw, str) else None


def _mime_owned(jokers: list[dict]) -> bool:
    for i in range(len(jokers)):
        _eff, key = _effective_joker_at(i, jokers)
        if key == "j_mime":
            return True
    return False


def _baseball_react_xmult(jokers: list[dict], triggered_joker: dict) -> float:
    """×Mult from Baseball Card when an Uncommon joker fires joker_main."""
    if _joker_rarity(triggered_joker) != "UNCOMMON":
        return 1.0
    count = sum(1 for j in jokers if j.get("key") == "j_baseball")
    return BASEBALL_UNCOMMON_XMULT**count if count else 1.0


def _held_joker_bonus_once(held_cards: list[dict], jokers: list[dict]) -> tuple[int, float]:
    """One pass of held-in-hand joker effects (Baron, Shoot the Moon, Raised Fist)."""
    add_mult = 0
    xmult = 1.0
    for i in range(len(jokers)):
        _eff, key = _effective_joker_at(i, jokers)
        if key == "j_shoot_the_moon":
            add_mult += 13 * sum(1 for c in held_cards if c.get("rank") == "Q")
        elif key == "j_baron":
            kings = sum(1 for c in held_cards if c.get("rank") == "K")
            if kings:
                xmult *= 1.5**kings
        elif key == "j_raised_fist" and held_cards:
            ranked = [c for c in held_cards if c.get("rank")]
            if ranked:
                lowest = min(ranked, key=lambda c: RANK_ORDER.get(c["rank"], 99))
                add_mult += 2 * RANK_CHIPS.get(lowest["rank"], 0)
    return add_mult, xmult


def _held_playing_card_bonus(held_cards: list[dict], mime: bool) -> float:
    """×Mult from held Steel cards (Mime retriggers once)."""
    xmult = 1.0
    triggers = 2 if mime else 1
    for card in held_cards:
        if card.get("debuff"):
            continue
        if card.get("enhancement") != "STEEL":
            continue
        for _ in range(triggers):
            xmult *= 1.5
    return xmult


def _held_joker_bonus(held_cards: list[dict], jokers: list[dict]) -> tuple[int, float]:
    """Held-in-hand joker phase: (add_mult, xmult). Mime retriggers once."""
    mime = _mime_owned(jokers)
    add_mult, xmult = _held_joker_bonus_once(held_cards, jokers)
    if mime:
        add_m2, x_m2 = _held_joker_bonus_once(held_cards, jokers)
        add_mult += add_m2
        xmult *= x_m2
    return add_mult, xmult


def _seltzer_active(joker: dict) -> int:
    """Return extra all-card retriggers if Seltzer countdown > 0."""
    stats = _joker_stats(joker)
    if "seltzer_remaining" in stats:
        return 1 if int(stats["seltzer_remaining"]) > 0 else 0
    effect = (joker.get("value") or {}).get("effect") or ""
    m = re.search(r"(\d+)", effect)
    if not m:
        return 0
    n = int(m.group(1))
    return 1 if n > 0 else 0


def _retrigger_config(jokers: list[dict]) -> dict:
    """Build retrigger config from owned jokers."""
    cfg = {"retrigger_all": 0, "retrigger_leftmost": 0, "retrigger_face": 0, "dusk_owned": False, "hack_owned": False}
    for i, _j in enumerate(jokers):
        j, key = _effective_joker_at(i, jokers)
        if not j:
            continue
        if key == "j_selzer":
            cfg["retrigger_all"] += _seltzer_active(j)
        elif key == "j_hanging_chad":
            cfg["retrigger_leftmost"] += 2  # "2 additional times"
        elif key == "j_dusk":
            cfg["dusk_owned"] = True
        elif key == "j_splash":
            cfg["splash"] = True
        elif key == "j_hack":
            cfg["hack_owned"] = True
        elif key == "j_sock_and_buskin":
            cfg["retrigger_face"] += 1
    return cfg


def _modeled(jokers: list[dict]) -> tuple[list[str], list[str]]:
    """Split jokers into (modeled_keys, unmodeled_names)."""
    modeled_keys = (
        set(NO_SCORE_JOKERS)
        | set(PER_CARD_JOKERS)
        | set(TYPE_MULT_JOKERS)
        | set(TYPE_CHIPS_JOKERS)
        | set(TYPE_XMULT_JOKERS)
        | {
            "j_joker",
            "j_abstract",
            "j_mystic_summit",
            "j_blackboard",
            "j_swashbuckler",
            "j_flower_pot",
            "j_family",
            "j_selzer",
            "j_hanging_chad",
            "j_dusk",
            "j_splash",
            "j_hack",
            "j_sock_and_buskin",
            "j_blue_joker",
            "j_half",
            "j_banner",
            "j_gros_michel",
            "j_acrobat",
            "j_card_sharp",
            "j_stuntman",
            "j_bootstraps",
            "j_supernova",
            "j_seeing_double",
            "j_cavendish",
            "j_bull",
            "j_photograph",
            "j_shoot_the_moon",
            "j_baron",
            "j_raised_fist",
            "j_stencil",
            "j_erosion",
            "j_ancient",
            "j_idol",
            "j_drivers_license",
            "j_loyalty_card",
            "j_pareidolia",
            "j_scary_face",
            "j_smiley",
            "j_blueprint",
            "j_brainstorm",
            "j_four_fingers",
            "j_shortcut",
            "j_mime",
            "j_baseball",
            "j_smeared",
        }
        | EFFECT_MULT_JOKERS
        | EFFECT_CHIPS_JOKERS
        | EFFECT_XMULT_JOKERS
    )
    unmodeled: list[str] = []
    for j in jokers:
        key = j.get("key") or ""
        if key and key not in modeled_keys:
            unmodeled.append(j.get("label") or key)
    return list(modeled_keys), unmodeled


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
    from itertools import combinations

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


def _flush_indices(cards: list[dict], idx_with_rank: list[int], *, min_len: int) -> list[int] | None:
    from collections import Counter

    suit_count = Counter(cards[i]["suit"] for i in idx_with_rank)
    for suit, cnt in suit_count.items():
        if cnt >= min_len:
            return [i for i in idx_with_rank if cards[i]["suit"] == suit]
    return None


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
    suits = [cards[i]["suit"] for i in idx_with_rank]
    n_ranked = len(idx_with_rank)
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

    # Flush Five: flush + 5 of a kind
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


def _card_trigger_chips_mult(
    card: dict,
    per_card_keys: list[str],
    ctx: dict,
    jokers: list[dict],
    *,
    photograph_x2: bool = False,
) -> tuple[int, int, float]:
    """One trigger of a scoring card: (add_chips, add_mult, xmult)."""
    chips = 0
    mult = 0
    xmult = 1.0
    if card["enhancement"] == "STONE":
        chips += 50
    else:
        chips += RANK_CHIPS.get(card["rank"], 0)
        enh = card["enhancement"]
        if enh == "BONUS":
            chips += 30
        elif enh == "MULT":
            mult += 4
        elif enh == "GLASS":
            xmult *= 2
        elif enh == "LUCKY":
            mult += 4  # expected ~+4 (1/5 of +20); probabilistic
        # WILD / GOLD / STEEL: no on-score chip/mult when played
    ed = card["edition"]
    if ed == "FOIL":
        chips += 50
    elif ed in ("HOLO", "HOLOGRAPHIC"):
        mult += 10
    elif ed == "POLYCHROME":
        xmult *= 1.5
    # per-card joker bonuses (fire once per trigger)
    for key in per_card_keys:
        c_add, m_add, x = _per_card_joker_bonus(card, key, ctx)
        chips += c_add
        mult += m_add
        xmult *= x
    for i in range(len(jokers)):
        _eff, jkey = _effective_joker_at(i, jokers)
        if jkey == "j_scary_face" and _card_is_face(card, ctx):
            chips += 30
        elif jkey == "j_smiley" and _card_is_face(card, ctx):
            mult += 5
    xmult *= _round_aware_card_xmult(card, jokers, ctx)
    if photograph_x2:
        xmult *= 2
    if card["debuff"]:
        # Debuffed cards score 0 chips/mult and don't trigger effects.
        return 0, 0, 1
    return chips, mult, xmult


def _score_combo(
    cards: list[dict],
    scoring_idx: list[int],
    hand_type: str,
    hand_level: dict,
    jokers: list[dict],
    cfg: dict,
    ctx: dict,
    dusk_active: bool,
) -> tuple[int, int, int]:
    """Return (chips, mult, score) for one combo."""
    base_chips = hand_level.get("chips", 0)
    base_mult = hand_level.get("mult", 0)
    if ctx.get("flint"):
        base_chips = base_chips // 2
        base_mult = base_mult // 2

    chips = base_chips
    mult = base_mult

    per_card_keys: list[str] = []
    for i, _j in enumerate(jokers):
        _eff, key = _effective_joker_at(i, jokers)
        if key in PER_CARD_JOKERS:
            per_card_keys.append(key)
    retrigger_all = cfg.get("retrigger_all", 0)
    retrigger_leftmost = cfg.get("retrigger_leftmost", 0)
    if dusk_active and cfg.get("dusk_owned"):
        # Dusk: "triggers all played cards in the final hand twice" => +1 retrigger.
        retrigger_all += 1

    # Splash: every played card scores (scoring_idx becomes all 5).
    eff_scoring = list(range(5)) if cfg.get("splash") else scoring_idx
    # Leftmost scoring card index (for Hanging Chad).
    leftmost = min(eff_scoring) if eff_scoring else -1
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

    for pos, i in enumerate(eff_scoring):
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
            c_add, m_add, x = _card_trigger_chips_mult(
                card,
                per_card_keys,
                ctx,
                jokers,
                photograph_x2=photograph_owned and i == first_face_scoring_idx,
            )
            chips += c_add
            mult += m_add
            mult *= x

    # Joker phase (global), left to right.
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
        j, key = _effective_joker_at(i, jokers)
        if not j:
            continue
        if key in NO_SCORE_JOKERS or key in PER_CARD_JOKERS:
            continue
        if key in {"j_selzer", "j_hanging_chad", "j_dusk", "j_splash", "j_hack", "j_sock_and_buskin"}:
            continue
        add_c, add_m, xm = _global_joker_bonus(j, ctx2)
        chips += add_c
        mult += add_m
        mult *= xm
        mult *= _baseball_react_xmult(jokers, j)

    held = ctx.get("held_cards") or []
    mime = _mime_owned(jokers)
    h_add_m, h_xm = _held_joker_bonus(held, jokers)
    mult += h_add_m
    mult *= h_xm
    mult *= _held_playing_card_bonus(held, mime)

    if ctx.get("plasma"):
        balanced = (chips + mult) // 2
        chips = balanced
        mult = balanced

    return chips, mult, chips * mult


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
    want = set(hand_indices)
    combo_local = [i for i, p in enumerate(parsed) if p["hand_index"] in want]
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
        "smeared": smeared,
    }
    levels = _hand_levels(state)
    dusk_now = cfg.get("dusk_owned", False) and ctx_base.get("hands_left") == 1

    cards = [parsed[i] for i in combo_local]
    hand_type, scoring_idx = _classify(cards, four_fingers=four_fingers, shortcut=shortcut)
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
        "smeared": smeared,
    }
    levels = _hand_levels(state)
    _, unmodeled = _modeled(jokers)

    max_play = min(5, len(parsed))
    combos = [
        combo
        for n in range(1, max_play + 1)
        for combo in combinations(range(len(parsed)), n)
    ]

    results: list[dict] = []
    # Dusk: game checks hands_left == 0 during evaluate_play (after
    # ease_hands_played(-1)); API still shows hands_left == 1 before you play.
    dusk_now = cfg.get("dusk_owned", False) and ctx.get("hands_left") == 1
    for combo in combos:
        cards = [parsed[i] for i in combo]
        hand_type, scoring_idx = _classify(cards, four_fingers=four_fingers, shortcut=shortcut)
        level = levels.get(hand_type, {"chips": 0, "mult": 0, "level": 1})
        combo_set = set(combo)
        combo_ctx = {
            **ctx,
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
        scoring_play_indices = [parsed[combo[i]]["hand_index"] for i in scoring_idx]
        play_indices = [parsed[i]["hand_index"] for i in combo]
        scoring_labels = [parsed[combo[i]]["label"] for i in scoring_idx]
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

    # Drop duplicate scoring sets from different kicker choices. Prefer the
    # higher-scoring play; on ties, prefer playing fewer cards.
    deduped: dict[tuple[str, tuple[int, ...]], dict] = {}
    for r in results:
        key = (r["hand_type"], tuple(sorted(r["scoring_indices"])))
        prev = deduped.get(key)
        if (
            prev is None
            or r["score"] > prev["score"]
            or (
                r["score"] == prev["score"]
                and len(r["indices"]) < len(prev["indices"])
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
        print(json.dumps(build_error_envelope("INVALID_STATE", str(e), fmt=ESTIMATE_FORMAT), ensure_ascii=False))
        return 1
    except APIError as e:
        print(json.dumps(build_error_envelope(e.name, e.message), ensure_ascii=False))
        return 1
    except TimeoutError as e:
        print(json.dumps(build_error_envelope("TIMEOUT", str(e)), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())



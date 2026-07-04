"""Joker registry and scoring effects for the Balatro score estimator.

New joker? Mandatory checklist: tools/play/estimate_registry.md
"""

from __future__ import annotations

import re

from estimate_constants import (
    EVEN_RANKS,
    FACE_RANKS,
    FIBONACCI_RANKS,
    ODD_RANKS,
    RANK_CHIPS,
    RANK_ORDER,
    TYPE_CHIPS_JOKERS,
    TYPE_MULT_JOKERS,
    TYPE_XMULT_JOKERS,
)

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


# Jokers whose score effect lives outside joker_main (retriggers / held / splash).
RETRIGGER_ONLY_JOKERS = frozenset(
    {
        "j_selzer",
        "j_hanging_chad",
        "j_dusk",
        "j_splash",
        "j_hack",
        "j_sock_and_buskin",
        "j_mime",
    }
)

# Jokers whose score effect runs in the held-in-hand phase (not joker_main).
HELD_PHASE_JOKERS = frozenset(
    {
        "j_baron",
        "j_shoot_the_moon",
        "j_raised_fist",
    }
)

# Physical jokers whose edition bonus applies after the held stack (add-only),
# not during joker_main where it would be multiplied by held ×Mult.
EDITION_AFTER_HELD_PHYSICAL = RETRIGGER_ONLY_JOKERS | HELD_PHASE_JOKERS


def _joker_edition_from(card: dict) -> str:
    """Edition on the physical joker at this slot (Blueprint uses its own edition)."""
    mod = card.get("modifier") or {}
    if not isinstance(mod, dict):
        return ""
    ed = mod.get("edition")
    return ed if isinstance(ed, str) else ""


def _apply_joker_edition_before(
    edition: str, chips: float, mult: float
) -> tuple[float, float]:
    """Foil/Holo apply before the joker's own effect during joker_main."""
    if edition == "FOIL":
        chips += 50
    elif edition in ("HOLO", "HOLOGRAPHIC"):
        mult += 10
    return chips, mult


def _apply_joker_edition_after(edition: str, mult: float) -> float:
    """Polychrome applies after the joker's own effect during joker_main."""
    if edition == "POLYCHROME":
        mult *= 1.5
    return mult


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
    "j_trading",
    "j_riff_raff",
    "j_drunkard",
    "j_matador",
    "j_cloud_9",
    "j_hiker",
    "j_rough_gem",
    "j_business",
    "j_reserved_parking",
    # Economy / utility / non-score RNG (no play-time score impact)
    "j_8_ball",
    "j_astronomer",
    "j_burglar",
    "j_burnt",
    "j_chaos",
    "j_chicot",
    "j_credit_card",
    "j_diet_cola",
    "j_dna",
    "j_hallucination",
    "j_invisible",
    "j_juggler",
    "j_luchador",
    "j_marble",
    "j_merry_andy",
    "j_mr_bones",
    "j_oops",
    "j_perkeo",
    "j_ring_master",
    "j_rocket",
    "j_satellite",
    "j_seance",
    "j_sixth_sense",
    "j_space",
    "j_superposition",
    "j_ticket",
    "j_to_the_moon",
    "j_todo_list",
    "j_troubadour",
    "j_turtle_bean",
    "j_vagabond",
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
    key = joker.get("key") or ""
    if key in STAT_ONLY_XMULT_JOKERS:
        if "x_mult" in stats:
            return float(stats["x_mult"])
        return 1.0
    if "x_mult" in stats:
        return float(stats["x_mult"])
    return _parse_effect_xmult(joker)


def _fortune_teller_mult(joker: dict, ctx: dict) -> int:
    stats = _joker_stats(joker)
    if "mult" in stats:
        return int(stats["mult"])
    run = ctx.get("run") or {}
    return int(run.get("tarot_used", 0))


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
        "j_swashbuckler",
    }
)

# Growth ×Mult jokers: never parse static X1 from localized effect text; use stats only.
STAT_ONLY_XMULT_JOKERS = frozenset(
    {
        "j_constellation",
        "j_campfire",
        "j_glass",
        "j_madness",
        "j_vampire",
        "j_hologram",
        "j_ramen",
        "j_hit_the_road",
        "j_caino",
        "j_yorick",
        "j_drivers_license",
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
        "j_caino",
        "j_yorick",
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


def _enhancement_scores_on_play(card: dict, ctx: dict) -> bool:
    """Vampire strips enhancements from scoring cards before they score."""
    if not ctx.get("vampire_owned"):
        return True
    return card.get("enhancement") in (None, "", "BASE")


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


def _caino_xmult(joker: dict) -> float:
    stats = _joker_stats(joker)
    if "caino_xmult" in stats:
        return float(stats["caino_xmult"])
    if "x_mult" in stats:
        return float(stats["x_mult"])
    return 1.0


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
    if key == "j_fortune_teller":
        mult = _fortune_teller_mult(joker, ctx)
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
        if key == "j_caino":
            xm = _caino_xmult(joker)
            return (0, 0, xm) if xm > 1.0 else (0, 0, 1)
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
        # Game increments `played` before joker_main on this hand.
        return (0, played + 1, 1)
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
        stats = _joker_stats(joker)
        tally = int(stats.get("driver_tally", 0))
        if tally >= 16:
            xm = _stat_xmult(joker)
            return (0, 0, xm) if xm > 1.0 else (0, 0, 1)
        return (0, 0, 1)
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
            for c in held_cards:
                if c.get("rank") == "K":
                    xmult *= 1.5
        elif key == "j_raised_fist" and held_cards:
            ranked = [c for c in held_cards if c.get("rank")]
            if ranked:
                lowest = min(ranked, key=lambda c: RANK_ORDER.get(c["rank"], 99))
                add_mult += 2 * RANK_CHIPS.get(lowest["rank"], 0)
    return add_mult, xmult


def _held_playing_card_bonus(held_cards: list[dict], mime: bool) -> float:
    """×Mult from held Steel cards (Mime retriggers held abilities once)."""
    xmult = 1.0
    for card in held_cards:
        if card.get("debuff"):
            continue
        if card.get("enhancement") != "STEEL":
            continue
        triggers = 1 + (1 if card.get("seal") == "RED" else 0)
        if mime:
            triggers *= 2
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

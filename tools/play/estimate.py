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
    "j_flash",
    "j_faceless",
    "j_cartomancer",
    "j_certificate",
    "j_mail",
    "j_ramen",
    "j_ripple",
    "j_hologram",
    "j_trading",
    "j_riff_raff",
    "j_drunkard",
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
    "j_scary_face": lambda c: (30 if c["rank"] in FACE_RANKS else 0, 0, 1),
    "j_smiley": lambda c: (0, 5 if c["rank"] in FACE_RANKS else 0, 1),
    "j_scholar": lambda c: (
        (20 if c["rank"] == "A" else 0),
        (4 if c["rank"] == "A" else 0),
        1,
    ),
}


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
    if key == "j_joker":
        return (0, 4, 1)
    if key == "j_abstract":
        return (0, 3 * ctx.get("joker_count", 0), 1)
    if key == "j_mystic_summit":
        return (0, 15 if ctx["discards_left"] == 0 else 0, 1)
    if key == "j_swashbuckler":
        effect = (joker.get("value") or {}).get("effect") or ""
        m = re.search(r"当前为\+(\d+)倍率", effect)
        return (0, int(m.group(1)) if m else 0, 1)
    if key == "j_blackboard":
        held_cards = ctx.get("held_cards") or []
        if held_cards and all(c.get("suit") in {"S", "C"} for c in held_cards):
            return (0, 0, 3)
        return (0, 0, 1)
    if key == "j_flower_pot":
        suits = {c["suit"] for c in ctx["scoring_cards"] if c["suit"]}
        return (0, 0, 3) if {"D", "C", "H", "S"} <= suits else (0, 0, 1)
    if key == "j_family":  # The Family: X4 if hand contains a 4oak
        return (0, 0, 4) if ctx["hand_type"] == "Four of a Kind" else (0, 0, 1)
    if key == "j_steel_joker":  # +chips scaling — needs run state; approximate 0
        return (0, 0, 1)
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
    return (0, 0, 1)


def _seltzer_active(joker: dict) -> int:
    """Return extra all-card retriggers if Seltzer countdown > 0."""
    effect = (joker.get("value") or {}).get("effect") or ""
    m = re.search(r"(\d+)", effect)
    if not m:
        return 0
    n = int(m.group(1))
    return 1 if n > 0 else 0


def _retrigger_config(jokers: list[dict]) -> dict:
    """Build retrigger config from owned jokers."""
    cfg = {"retrigger_all": 0, "retrigger_leftmost": 0, "dusk_owned": False, "hack_owned": False}
    for j in jokers:
        key = j.get("key") or ""
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
    return cfg


def _modeled(jokers: list[dict]) -> tuple[list[str], list[str]]:
    """Split jokers into (modeled_keys, unmodeled_names)."""
    modeled_keys = (
        set(NO_SCORE_JOKERS)
        | set(PER_CARD_JOKERS)
        | set(TYPE_MULT_JOKERS)
        | set(TYPE_CHIPS_JOKERS)
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
            "j_steel_joker",
            "j_blue_joker",
            "j_half",
            "j_banner",
            "j_gros_michel",
            "j_acrobat",
            "j_card_sharp",
        }
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


def _classify(cards: list[dict]) -> tuple[str, list[int]]:
    """Classify 1-5 played cards. Returns (hand_type, scoring_indices_into_played)."""
    # Separate stones (no rank/suit) — they never help form a hand but score.
    idx_with_rank = [i for i, c in enumerate(cards) if c["rank"]]
    ranks = [cards[i]["rank"] for i in idx_with_rank]
    suits = [cards[i]["suit"] for i in idx_with_rank]
    n_ranked = len(idx_with_rank)

    from collections import Counter

    rank_count = Counter(ranks)

    is_flush = n_ranked == 5 and len(set(suits)) == 1
    # Straight: 5 distinct consecutive ranks (A can be low).
    is_straight = False
    if n_ranked == 5 and len(set(ranks)) == 5:
        vals = sorted(RANK_ORDER[r] for r in ranks)
        if vals == list(range(vals[0], vals[0] + 5)):
            is_straight = True
        # A-low wheel: A,2,3,4,5 -> vals [2,3,4,5,14]
        elif sorted(ranks) == ["A", "2", "3", "4", "5"]:
            is_straight = True

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
    if is_flush and counts == [5]:
        return "Flush Five", list(range(5))
    # Flush House: flush + full house (3+2)
    if is_flush and counts == [3, 2]:
        return "Flush House", list(range(5))
    # Five of a Kind
    if counts == [5]:
        return "Five of a Kind", list(range(5))
    # Straight Flush
    if is_flush and is_straight:
        return "Straight Flush", list(range(5))
    # Four of a Kind
    if counts in ([4, 1], [4]):
        return "Four of a Kind", idx_of_group(4, 1)
    # Full House
    if counts == [3, 2]:
        return "Full House", list(range(5))
    # Flush
    if is_flush:
        return "Flush", list(range(5))
    # Straight
    if is_straight:
        return "Straight", list(range(5))
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


# --- scoring ----------------------------------------------------------------


def _card_trigger_chips_mult(
    card: dict, per_card_jokers: list, ctx: dict
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
    for fn in per_card_jokers:
        c_add, m_add, x = fn(card)
        chips += c_add
        mult += m_add
        xmult *= x
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

    per_card_fns = [
        PER_CARD_JOKERS[j["key"]] for j in jokers if j.get("key") in PER_CARD_JOKERS
    ]
    retrigger_all = cfg.get("retrigger_all", 0)
    retrigger_leftmost = cfg.get("retrigger_leftmost", 0)
    if dusk_active and cfg.get("dusk_owned"):
        # Dusk: "triggers all played cards in the final hand twice" => +1 retrigger.
        retrigger_all += 1

    # Splash: every played card scores (scoring_idx becomes all 5).
    eff_scoring = list(range(5)) if cfg.get("splash") else scoring_idx
    # Leftmost scoring card index (for Hanging Chad).
    leftmost = min(eff_scoring) if eff_scoring else -1

    for pos, i in enumerate(eff_scoring):
        card = cards[i]
        triggers = 1 + retrigger_all
        if card["seal"] == "RED":
            triggers += 1
        if cfg.get("hack_owned") and card["rank"] in LOW_RANKS:
            triggers += 1
        if i == leftmost:
            triggers += retrigger_leftmost
        for _ in range(triggers):
            c_add, m_add, x = _card_trigger_chips_mult(card, per_card_fns, ctx)
            chips += c_add
            mult += m_add
            mult *= x

    # Joker phase (global), left to right.
    ctx2 = {
        **ctx,
        "hand_type": hand_type,
        "scoring_cards": [cards[i] for i in eff_scoring],
        "held_cards": ctx.get("held_cards", []),
        "joker_count": len(jokers),
        "cards_played": len(cards),
    }
    for j in jokers:
        key = j.get("key") or ""
        if key in NO_SCORE_JOKERS or key in PER_CARD_JOKERS:
            continue
        if key in {"j_selzer", "j_hanging_chad", "j_dusk", "j_splash", "j_hack"}:
            continue
        add_c, add_m, xm = _global_joker_bonus(j, ctx2)
        chips += add_c
        mult += add_m
        mult *= xm

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
        out[name] = {"played_this_round": info.get("played_this_round", 0)}
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
        "target": blind.get("score"),
        "boss_name": blind.get("name") or "",
        "boss_effect": blind.get("effect") or "",
        "hands_meta": _hands_meta(state),
    }


# --- top-level estimate -----------------------------------------------------


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
    ctx = _ctx(state)
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
        hand_type, scoring_idx = _classify(cards)
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



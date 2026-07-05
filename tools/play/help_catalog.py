"""Static command catalog for ``bot.ps1 help`` (examples + descriptions)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CatalogCategory = Literal["play", "read", "know", "advanced", "hidden"]

CATEGORY_TITLES: dict[CatalogCategory, str] = {
    "play": "Play",
    "read": "Read state",
    "know": "Know",
    "advanced": "Advanced",
    "hidden": "Hidden / debug",
}


@dataclass(frozen=True)
class CatalogEntry:
    example: str
    description: str
    category: CatalogCategory


def catalog_entries() -> list[CatalogEntry]:
    return [
        # play
        CatalogEntry(
            "start RED WHITE",
            "Start a new run; optional SEED. Deck/stake lists appear in glance at MENU.",
            "play",
        ),
        CatalogEntry(
            "start RED WHITE ABC123",
            "Start with a specific seed (restart hint on GAME_OVER uses this form).",
            "play",
        ),
        CatalogEntry("select", "Select the current blind at BLIND_SELECT.", "play"),
        CatalogEntry(
            "skip",
            "Skip Small/Big blind only — collects the skip-reward tag on that blind.",
            "play",
        ),
        CatalogEntry(
            "reroll_boss",
            "Reroll Boss blind for $10 (Director's Cut / Retcon at Boss BLIND_SELECT).",
            "play",
        ),
        CatalogEntry(
            "play 0 1 2 3 4",
            "Play 1-5 cards; [N] from hand: line (0-based).",
            "play",
        ),
        CatalogEntry(
            "discard 0 1",
            "Discard hand cards by [N] from hand: line.",
            "play",
        ),
        CatalogEntry(
            "sort rank",
            "Sort hand by rank (also: rank-desc, suit, suit-asc, aliases r/s/rd/…).",
            "play",
        ),
        CatalogEntry(
            "sell joker 0",
            "Sell joker at [N] on jokers: line — not the consumable slot.",
            "play",
        ),
        CatalogEntry(
            "sell consumable 1",
            "Sell consumable at [N] on consumables: line — separate index list.",
            "play",
        ),
        CatalogEntry(
            "use 0",
            "Use consumable [0] with no hand targets (when the card allows).",
            "play",
        ),
        CatalogEntry(
            "use 0 1 2",
            "Use consumable [0] targeting hand cards [1] [2] (Tarot/Spectral/Death).",
            "play",
        ),
        CatalogEntry(
            "rearrange jokers 1 0",
            "Reorder jokers left-to-right (scoring order); 2+ jokers required.",
            "play",
        ),
        CatalogEntry(
            "rearrange consumables 1 0",
            "Reorder consumable slots; 2+ consumables required.",
            "play",
        ),
        CatalogEntry(
            "rearrange hand 2 0 1 3",
            "Reorder hand cards; 2+ hand cards required.",
            "play",
        ),
        CatalogEntry(
            "buy card 0",
            "Buy shop row [0] (card/voucher rows use buy card / buy voucher).",
            "play",
        ),
        CatalogEntry("buy voucher 0", "Buy voucher at shop index [0].", "play"),
        CatalogEntry("buy pack 0", "Buy booster pack at shop index [0].", "play"),
        CatalogEntry(
            "reroll", "Reroll shop offers (affordability check only).", "play"
        ),
        CatalogEntry("next_round", "Leave shop for blind selection.", "play"),
        CatalogEntry(
            "cash_out",
            "Collect ROUND_EVAL rewards after reading pending: rows.",
            "play",
        ),
        CatalogEntry(
            "endless",
            "Dismiss victory overlay after Ante 8 win; then cash_out / shop.",
            "play",
        ),
        CatalogEntry("menu", "Return to main menu from any state.", "play"),
        CatalogEntry(
            "pack 0",
            "Take pack choice [0] with no hand targets (when allowed).",
            "play",
        ),
        CatalogEntry(
            "pack 0 1 2",
            "Take pack choice [0] with hand targets [1] [2] from hand: line.",
            "play",
        ),
        CatalogEntry(
            "pack skip",
            "Forfeit all remaining picks in the open booster (not next blind).",
            "play",
        ),
        # read
        CatalogEntry(
            "glance",
            "Compact summary + actions: line (command names only; see help for syntax).",
            "read",
        ),
        CatalogEntry(
            "estimate",
            "Optional score estimator (dev only; not recommended for normal play).",
            "read",
        ),
        CatalogEntry(
            "state",
            "Full JSON gamestate + actions[] with examples (scripting).",
            "read",
        ),
        CatalogEntry(
            "query hands",
            "Hand-type level chips/mult table (scoring math).",
            "read",
        ),
        CatalogEntry("query deck", "Detail query: deck composition.", "read"),
        CatalogEntry("query blinds", "Detail query: three-blind summary.", "read"),
        CatalogEntry(
            "query used_vouchers", "Detail query: vouchers bought this run.", "read"
        ),
        CatalogEntry("query seed", "Detail query: current run seed.", "read"),
        # know
        CatalogEntry(
            "know preflight",
            "Phase-aware verified facts (BLIND_SELECT / skip; optional).",
            "know",
        ),
        CatalogEntry(
            'know check joker "Baron"',
            "Lookup one joker/boss/tag/stake/deck/rule (JSON).",
            "know",
        ),
        CatalogEntry(
            "know check rule scoring_formula",
            "Lookup a curated mechanics rule (JSON).",
            "know",
        ),
        CatalogEntry(
            "know list jokers",
            "List names in a library (aliases: joker, rules → rule).",
            "know",
        ),
        CatalogEntry(
            "know stats",
            "Knowledge library file counts and directory (JSON).",
            "know",
        ),
        # advanced
        CatalogEntry(
            'exec "{\\"command\\":\\"play\\",\\"params\\":{\\"cards\\":[0,1,2,3,4]}}"',
            "Raw JSON-RPC envelope; escape quotes in PowerShell — prefer friendly subcommands.",
            "advanced",
        ),
        # hidden
        CatalogEntry("save run.jkr", "Save current run to a file.", "hidden"),
        CatalogEntry("load run.jkr", "Load a saved run from a file.", "hidden"),
        CatalogEntry(
            "screenshot shot.png",
            "Save a screenshot to disk (absolute path recommended).",
            "hidden",
        ),
        CatalogEntry(
            "add joker j_dusk",
            "Debug: add joker/card/consumable (requires BALATROBOT_ALLOW_CHEATS=1).",
            "hidden",
        ),
        CatalogEntry(
            "set hands 1 chips 0",
            "Debug: set hands/discards/chips (requires BALATROBOT_ALLOW_CHEATS=1).",
            "hidden",
        ),
        CatalogEntry(
            "debuff 0",
            "Debug: debuff hand card [N] (requires BALATROBOT_ALLOW_CHEATS=1).",
            "hidden",
        ),
    ]

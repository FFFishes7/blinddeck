"""Shared knowledge library helpers for know.py."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from layers import TRANSITION_STATES, effective_state

_DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "balatro"


def knowledge_dir() -> Path:
    override = os.environ.get("BALATROBOT_KNOWLEDGE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _DEFAULT_KNOWLEDGE_DIR


LIBRARIES = {
    "joker": "balatro-jokers-verified.json",
    "boss": "balatro-bosses-verified.json",
    "tag": "balatro-tags-verified.json",
    "stake": "balatro-stakes-verified.json",
    "deck": "balatro-decks-verified.json",
    "planet": "balatro-planets-verified.json",
    "tarot": "balatro-tarots-verified.json",
    "voucher": "balatro-vouchers-verified.json",
    "spectral": "balatro-spectrals-verified.json",
    "rule": "balatro-rules-verified.json",
}

ALIASES = {
    "jokers": "joker",
    "bosses": "boss",
    "tags": "tag",
    "stakes": "stake",
    "decks": "deck",
    "planets": "planet",
    "tarots": "tarot",
    "vouchers": "voucher",
    "spectrals": "spectral",
    "rules": "rule",
}

CONSUMABLE_SET_TO_KIND = {
    "TAROT": "tarot",
    "PLANET": "planet",
    "SPECTRAL": "spectral",
}

PREFLIGHT_FIELDS_BY_PHASE: dict[str, frozenset[str]] = {
    "MENU": frozenset(),
    "TRANSIENT": frozenset(),
    "BLIND_SELECT": frozenset({"deck", "stake", "joker", "consumable", "boss", "tag"}),
    "SELECTING_HAND": frozenset({"deck", "stake", "joker", "consumable", "boss"}),
    "SHOP": frozenset({"deck", "stake", "joker", "consumable", "boss"}),
    "SMODS_BOOSTER_OPENED": frozenset({"deck", "stake", "joker", "consumable", "boss"}),
    "ROUND_EVAL": frozenset({"deck", "stake", "joker", "consumable", "boss"}),
    "GAME_OVER": frozenset({"deck", "stake"}),
}


def resolve_kind(name: str) -> str:
    kind = ALIASES.get(name.lower(), name.lower())
    if kind not in LIBRARIES:
        raise ValueError(f"unknown library: {name}")
    return kind


def load_library(kind: str) -> dict:
    path = knowledge_dir() / LIBRARIES[kind]
    if not path.is_file():
        raise FileNotFoundError(f"Missing library: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_name(
    kind: str, name: str, library: dict, quiet: bool = False
) -> str | None:
    key = name.strip()
    if key in library:
        return key
    lower_map = {k.lower(): k for k in library}
    if key.lower() in lower_map:
        return lower_map[key.lower()]
    matches = get_close_matches(key, library.keys(), n=3, cutoff=0.6)
    if len(matches) == 1:
        if not quiet:
            print(f"  (matched '{matches[0]}')", file=sys.stderr)
        return matches[0]
    if matches and not quiet:
        print(f"  ambiguous — did you mean: {', '.join(matches)}?", file=sys.stderr)
    return None


def relevant_boss(state: dict) -> str | None:
    for blind in state.get("blinds", {}).values():
        if blind.get("type") == "BOSS" and blind.get("status") in (
            "CURRENT",
            "SELECT",
            "UPCOMING",
        ):
            return blind.get("name")
    return None


def upcoming_tags(state: dict) -> list[tuple[str, str]]:
    out = []
    for slot, blind in state.get("blinds", {}).items():
        tag = blind.get("tag_name") or ""
        if tag and blind.get("status") in ("SELECT", "UPCOMING"):
            out.append((slot, tag))
    return out


def preflight_phase(state: dict) -> str:
    raw = state.get("state", "UNKNOWN")
    if raw in TRANSITION_STATES:
        return "TRANSIENT"
    phase = effective_state(state)
    if phase in PREFLIGHT_FIELDS_BY_PHASE:
        return phase
    return "TRANSIENT"


def _append_check(
    checks: list[dict[str, Any]],
    *,
    kind: str,
    name: str,
    library: dict | None = None,
    extra: dict[str, Any] | None = None,
) -> bool:
    lib = library if library is not None else load_library(kind)
    resolved = resolve_name(kind, name, lib, quiet=True)
    row: dict[str, Any] = {"kind": kind, "name": name, "passed": False, "entry": None}
    if extra:
        row.update(extra)
    if resolved:
        row["passed"] = True
        row["entry"] = {"name": resolved, **lib[resolved]}
    checks.append(row)
    return bool(row["passed"])


def collect_preflight_checks(
    state: dict,
    *,
    check_kind: Callable[[str, str, dict | None], tuple[bool, dict | None]]
    | None = None,
) -> tuple[list[dict[str, Any]], bool, str]:
    """Return checks list, aggregate passed, and resolved play phase."""
    phase = preflight_phase(state)
    fields = PREFLIGHT_FIELDS_BY_PHASE.get(phase, frozenset())
    checks: list[dict[str, Any]] = []
    passed = True

    if not fields:
        return checks, True, phase

    if check_kind is not None:

        def add(
            kind: str, name: str, library: dict | None = None, **extra: Any
        ) -> None:
            nonlocal passed
            ok, entry = check_kind(kind, name, library)
            row: dict[str, Any] = {
                "kind": kind,
                "name": name,
                "passed": ok,
                "entry": entry,
                **extra,
            }
            checks.append(row)
            passed = passed and ok

    else:

        def add(
            kind: str, name: str, library: dict | None = None, **extra: Any
        ) -> None:
            nonlocal passed
            ok = _append_check(
                checks, kind=kind, name=name, library=library, extra=extra or None
            )
            passed = passed and ok

    if "deck" in fields:
        deck = (state.get("deck") or "RED").upper()
        add("deck", deck)

    if "stake" in fields:
        stake = (state.get("stake") or "WHITE").upper()
        add("stake", stake)

    if "joker" in fields:
        joker_lib = load_library("joker")
        for card in state.get("jokers", {}).get("cards", []):
            label = card.get("label") or ""
            if label:
                add("joker", label, joker_lib)

    if "consumable" in fields:
        libs: dict[str, dict] = {}
        for card in state.get("consumables", {}).get("cards", []):
            label = card.get("label") or ""
            card_set = (card.get("set") or "").upper()
            kind = CONSUMABLE_SET_TO_KIND.get(card_set)
            if not label or not kind:
                continue
            if kind not in libs:
                libs[kind] = load_library(kind)
            add(kind, label, libs[kind])

    if "boss" in fields:
        boss = relevant_boss(state)
        if boss:
            add("boss", boss)

    if "tag" in fields:
        tag_lib = load_library("tag")
        for slot, tag in upcoming_tags(state):
            add("tag", tag, tag_lib, slot=slot)

    return checks, passed, phase

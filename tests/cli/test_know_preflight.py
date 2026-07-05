"""Tests for phase-aware know preflight."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLAY_ROOT = Path(__file__).resolve().parents[2] / "tools" / "play"
sys.path.insert(0, str(PLAY_ROOT))

from know import (  # noqa: E402  # type: ignore[unresolved-import]
    _format_preflight,
    check_kind,
)
from know_lib import (  # noqa: E402  # type: ignore[unresolved-import]
    collect_preflight_checks,
    preflight_phase,
)


def _boss_blinds(name: str = "The Eye", status: str = "UPCOMING") -> dict:
    return {
        "small": {"type": "SMALL", "status": "SELECT", "tag_name": "Economy Tag"},
        "big": {"type": "BIG", "status": "UPCOMING", "tag_name": ""},
        "boss": {"type": "BOSS", "name": name, "status": status},
    }


def _owned_joker(label: str = "Baron") -> dict:
    return {"cards": [{"label": label, "set": "JOKER"}]}


def _owned_consumable(label: str, card_set: str) -> dict:
    return {"cards": [{"label": label, "set": card_set}]}


@pytest.mark.parametrize(
    ("state", "expected_kinds"),
    [
        ({"state": "MENU"}, []),
        ({"state": "HAND_PLAYED", "deck": "RED", "stake": "WHITE"}, []),
        (
            {
                "state": "BLIND_SELECT",
                "deck": "RED",
                "stake": "RED",
                "ante_num": 2,
                "money": 8,
                "jokers": _owned_joker("Baron"),
                "consumables": _owned_consumable("The Hermit", "TAROT"),
                "blinds": _boss_blinds(),
            },
            ["deck", "stake", "joker", "tarot", "boss", "tag"],
        ),
        (
            {
                "state": "SELECTING_HAND",
                "deck": "PLASMA",
                "stake": "RED",
                "jokers": _owned_joker(),
                "consumables": _owned_consumable("Pluto", "PLANET"),
                "blinds": _boss_blinds(status="CURRENT"),
            },
            ["deck", "stake", "joker", "planet", "boss"],
        ),
        (
            {
                "state": "SHOP",
                "deck": "RED",
                "stake": "RED",
                "jokers": _owned_joker(),
                "consumables": {"cards": []},
                "blinds": _boss_blinds(),
            },
            ["deck", "stake", "joker", "boss"],
        ),
        (
            {
                "state": "SMODS_BOOSTER_OPENED",
                "deck": "RED",
                "stake": "RED",
                "jokers": _owned_joker(),
                "consumables": {"cards": []},
                "blinds": _boss_blinds(),
            },
            ["deck", "stake", "joker", "boss"],
        ),
        (
            {
                "state": "ROUND_EVAL",
                "deck": "BLUE",
                "stake": "WHITE",
                "jokers": _owned_joker(),
                "consumables": _owned_consumable("Ankh", "SPECTRAL"),
                "blinds": _boss_blinds(),
            },
            ["deck", "stake", "joker", "spectral", "boss"],
        ),
        (
            {
                "state": "GAME_OVER",
                "deck": "RED",
                "stake": "RED",
                "jokers": _owned_joker(),
            },
            ["deck", "stake"],
        ),
    ],
)
def test_preflight_checks_by_phase(state: dict, expected_kinds: list[str]) -> None:
    checks, passed, phase = collect_preflight_checks(state, check_kind=check_kind)
    assert [c["kind"] for c in checks] == expected_kinds
    assert passed is True
    if expected_kinds:
        assert phase == preflight_phase(state)
    text = _format_preflight(
        {
            "preflight": {
                "passed": passed,
                "context": {
                    "state": state.get("state"),
                    "ante_num": state.get("ante_num"),
                    "deck": (state.get("deck") or "RED").upper(),
                    "stake": (state.get("stake") or "WHITE").upper(),
                    "money": state.get("money"),
                },
                "checks": checks,
            }
        }
    )
    if not expected_kinds:
        assert text == ""
    else:
        assert "kind     name" in text
        assert checks[0]["kind"] == "deck"


def test_preflight_unknown_joker_fails() -> None:
    state = {
        "state": "SELECTING_HAND",
        "deck": "RED",
        "stake": "RED",
        "jokers": _owned_joker("Totally Fake Joker"),
        "consumables": {"cards": []},
        "blinds": _boss_blinds(),
    }
    checks, passed, _ = collect_preflight_checks(state, check_kind=check_kind)
    assert passed is False
    joker_row = next(c for c in checks if c["kind"] == "joker")
    assert joker_row["passed"] is False
    assert joker_row["entry"] is None


def test_preflight_header_and_full_effect() -> None:
    checks, passed, _ = collect_preflight_checks(
        {
            "state": "GAME_OVER",
            "deck": "RED",
            "stake": "RED",
        },
        check_kind=check_kind,
    )
    text = _format_preflight(
        {
            "preflight": {
                "passed": passed,
                "context": {
                    "state": "GAME_OVER",
                    "ante_num": 5,
                    "deck": "RED",
                    "stake": "RED",
                    "money": 0,
                },
                "checks": checks,
            }
        }
    )
    assert "passed=" not in text.splitlines()[0]
    assert "ante=5 deck=RED stake=RED" in text.splitlines()[0]
    stake_row = next(c for c in checks if c["kind"] == "stake")
    assert stake_row["entry"]["effect"] in text
    assert "still pay." in text

    ok, entry = check_kind("deck", "RED")
    assert ok is True
    assert entry is not None
    assert "+1 discard" in entry["effect"]


def test_list_deck_alias() -> None:
    from know import cmd_list  # type: ignore[unresolved-import]

    names = cmd_list("deck")["names"]
    assert "RED" in names
    assert "PLASMA" in names


def test_knowledge_dir_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from know import cmd_stats  # type: ignore[unresolved-import]
    from know_lib import LIBRARIES, load_library  # type: ignore[unresolved-import]

    deck_data = {"RED": {"effect": "+1 discard each round", "source": []}}
    (tmp_path / LIBRARIES["deck"]).write_text(json.dumps(deck_data), encoding="utf-8")
    monkeypatch.setenv("BALATROBOT_KNOWLEDGE_DIR", str(tmp_path))

    loaded = load_library("deck")
    assert loaded == deck_data

    stats = cmd_stats()
    assert stats["dir"] == str(tmp_path.resolve())
    assert stats["libraries"]["deck"]["count"] == 1

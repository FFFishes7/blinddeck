"""Tests for bot.ps1 help output."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PLAY_ROOT = Path(__file__).resolve().parents[2] / "tools" / "play"
sys.path.insert(0, str(PLAY_ROOT))

from bot_client import APIError  # noqa: E402  # type: ignore[unresolved-import]
from help import format_help_text, main  # noqa: E402  # type: ignore[unresolved-import]


def test_help_default_text_includes_sell_explanation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch.object(sys, "argv", ["help.py"]):
        assert main() == 0
    out = capsys.readouterr().out
    assert "sell joker 0" in out
    assert "jokers: line" in out
    assert "== Play ==" in out
    assert "death 0" not in out


def test_help_json_v2_structure(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(sys, "argv", ["help.py", "--json"]):
        assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "balatrobot-help-v2"
    assert payload["ok"] is True
    assert any(e["example"] == "sell joker 0" for e in payload["catalog"])
    assert "hidden_actions" not in payload


def test_help_now_with_mock_gamestate(capsys: pytest.CaptureFixture[str]) -> None:
    shop_state = {
        "state": "SHOP",
        "money": 10,
        "deck": "RED",
        "stake": "WHITE",
        "bankrupt_at": 0,
        "shop": {
            "cards": [{"label": "Jolly Joker", "set": "JOKER", "cost": 2}],
        },
        "vouchers": {"cards": []},
        "packs": {"cards": []},
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "round": {"reroll_cost": 5},
    }
    with (
        patch.object(sys, "argv", ["help.py", "--now"]),
        patch("help.fetch_stable_gamestate", return_value=shop_state),
    ):
        assert main() == 0
    out = capsys.readouterr().out
    assert "== Valid now (SHOP) ==" in out
    assert "buy card 0" in out


def test_help_now_api_error_still_prints_catalog(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch.object(sys, "argv", ["help.py", "--now"]),
        patch(
            "help.fetch_stable_gamestate",
            side_effect=APIError("INTERNAL_ERROR", "connection refused"),
        ),
    ):
        assert main() == 0
    out = capsys.readouterr().out
    assert "sell joker 0" in out
    assert "valid_now: unavailable" in out


def test_format_help_text_valid_now_section() -> None:
    text = format_help_text(
        valid_now={
            "state": "MENU",
            "actions": [{"example": "start RED WHITE", "description": "Start run"}],
        }
    )
    assert "== Valid now (MENU) ==" in text
    assert "start RED WHITE" in text

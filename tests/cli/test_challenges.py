"""Unit tests for native challenge play helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

PLAY_ROOT = Path(__file__).resolve().parents[2] / "tools" / "play"
sys.path.insert(0, str(PLAY_ROOT))

import challenges  # type: ignore[unresolved-import]  # noqa: E402
from actions import build_actions  # type: ignore[unresolved-import]  # noqa: E402
from commands import (  # type: ignore[unresolved-import]  # noqa: E402
    build_params,
    format_friendly_action,
)
from envelope import (  # type: ignore[unresolved-import]  # noqa: E402
    build_play_envelope,
)
from layers import filter_layer1  # type: ignore[unresolved-import]  # noqa: E402

CATALOG = [
    {
        "id": "c_omelette",
        "index": 1,
        "name": "The Omelette",
        "unlocked": True,
        "completed": False,
    },
    {
        "id": "c_city",
        "index": 2,
        "name": "15 Minute City",
        "unlocked": False,
        "completed": True,
    },
]


def test_format_challenges_includes_ids_and_status() -> None:
    text = challenges.format_challenges(CATALOG)
    assert "1/2 unlocked" in text
    assert "1/2 completed" in text
    assert "c_omelette — The Omelette (unlocked)" in text
    assert "c_city — 15 Minute City (locked, completed)" in text


def test_challenges_json_command(capsys) -> None:
    with (
        patch.object(sys, "argv", ["challenges.py", "--json"]),
        patch("challenges.rpc", return_value={"challenges": CATALOG}),
    ):
        assert challenges.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "ok": True,
        "format": "balatrobot-challenges-v1",
        "challenges": CATALOG,
    }


def test_challenge_command_params_and_friendly_format() -> None:
    assert build_params("challenge", ["c_omelette"]) == {"id": "c_omelette"}
    assert (
        format_friendly_action(
            {"command": "challenge", "example": {"params": {"id": "c_omelette"}}}
        )
        == "challenge c_omelette"
    )
    assert (
        format_friendly_action({"command": "challenges", "example": {"params": {}}})
        == "challenges"
    )


def test_challenge_command_requires_exactly_one_id() -> None:
    try:
        build_params("challenge", [])
    except ValueError as error:
        assert "challenge needs" in str(error)
    else:
        raise AssertionError("missing challenge ID should fail")


def test_menu_actions_and_active_challenge_are_exposed() -> None:
    menu = {"state": "MENU"}
    commands = {action["command"] for action in build_actions(menu)}
    assert {"start", "challenges", "challenge"}.issubset(commands)

    running = {
        "state": "BLIND_SELECT",
        "challenge": {"id": "c_omelette", "name": "The Omelette"},
    }
    assert filter_layer1(running)["challenge"]["id"] == "c_omelette"
    assert (
        build_play_envelope(running, build_actions(running))["gamestate"]["challenge"][
            "name"
        ]
        == "The Omelette"
    )

"""Tests for src/lua/endpoints/endless.lua"""

import time

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


def _wait_for_victory_overlay(client: httpx.Client, *, attempts: int = 100) -> dict:
    """Poll gamestate until the post-win overlay is visible."""
    for _ in range(attempts):
        gamestate = api(client, "gamestate", {})["result"]
        if gamestate.get("victory_overlay"):
            return gamestate
        time.sleep(0.1)
    raise AssertionError("victory_overlay never appeared after winning the run")


class TestEndlessEndpoint:
    """Test basic endless endpoint functionality."""

    def test_endless_after_game_won(self, client: httpx.Client) -> None:
        """Victory overlay dismisses and cash_out reaches shop."""
        gamestate = load_fixture(
            client,
            "play",
            "state-SELECTING_HAND--ante_num-8--blinds.boss.status-CURRENT--round.chips-1000000",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        play_response = api(client, "play", {"cards": [0, 3, 4, 5, 6]})
        assert_gamestate_response(play_response, won=True)
        won_state = _wait_for_victory_overlay(client)
        assert won_state.get("won") is True
        assert won_state.get("victory_overlay") is True
        assert won_state.get("state") == "ROUND_EVAL"

        assert_error_response(
            api(client, "cash_out", {}),
            "NOT_ALLOWED",
            "Victory overlay is showing",
        )
        assert_error_response(
            api(client, "sell", {"joker": 0}),
            "NOT_ALLOWED",
            "Victory overlay is showing",
        )
        assert_error_response(
            api(client, "use", {"consumable": 0}),
            "NOT_ALLOWED",
            "Victory overlay is showing",
        )
        assert_error_response(
            api(client, "save", {"path": "balatrobot_victory_overlay_test.jkr"}),
            "NOT_ALLOWED",
            "Victory overlay is showing",
        )

        endless_response = api(client, "endless", {})
        after_endless = assert_gamestate_response(
            endless_response, state="ROUND_EVAL", won=True
        )
        assert not after_endless.get("victory_overlay")

        cash_out_response = api(client, "cash_out", {})
        assert_gamestate_response(cash_out_response, state="SHOP")

    def test_endless_game_over_result_is_loss(self, client: httpx.Client) -> None:
        """After endless continues, GAME_OVER shows loss even though won stays true."""
        load_fixture(
            client,
            "play",
            "state-SELECTING_HAND--ante_num-8--blinds.boss.status-CURRENT--round.chips-1000000",
        )
        play_response = api(client, "play", {"cards": [0, 3, 4, 5, 6]})
        assert_gamestate_response(play_response, won=True)
        _wait_for_victory_overlay(client)

        assert_gamestate_response(
            api(client, "endless", {}), state="ROUND_EVAL", won=True
        )
        assert_gamestate_response(api(client, "cash_out", {}), state="SHOP")
        assert_gamestate_response(api(client, "next_round", {}), state="BLIND_SELECT")
        assert_gamestate_response(api(client, "select", {}), state="SELECTING_HAND")

        api(client, "set", {"hands": 1})
        loss_response = api(client, "play", {"cards": [0]}, timeout=60)
        gamestate = assert_gamestate_response(loss_response, state="GAME_OVER")
        assert gamestate.get("won") is True
        result = gamestate["run_summary"]["result"]
        assert result != "Victory"
        assert result == "Lost" or result.startswith("Lost to ")


class TestEndlessEndpointValidation:
    """Test endless endpoint guards."""

    def test_endless_not_allowed_without_overlay(self, client: httpx.Client) -> None:
        """Normal ROUND_EVAL has no victory overlay."""
        gamestate = load_fixture(client, "cash_out", "state-ROUND_EVAL")
        assert gamestate["state"] == "ROUND_EVAL"
        assert_error_response(
            api(client, "endless", {}),
            "NOT_ALLOWED",
            "Run has not been won yet",
        )

    def test_endless_invalid_state(self, client: httpx.Client) -> None:
        """endless requires ROUND_EVAL."""
        gamestate = load_fixture(client, "cash_out", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "endless", {}),
            "INVALID_STATE",
            "Method 'endless' requires one of these states: ROUND_EVAL",
        )

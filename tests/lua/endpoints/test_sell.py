"""Tests for src/lua/endpoints/sell.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestSellEndpoint:
    """Test basic sell endpoint functionality."""

    def test_sell_no_args(self, client: httpx.Client) -> None:
        """Test sell endpoint with no arguments."""
        gamestate = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "sell", {}),
            "BAD_REQUEST",
            "Must provide exactly one of: joker or consumable",
        )

    def test_sell_multi_args(self, client: httpx.Client) -> None:
        """Test sell endpoint with multiple arguments."""
        gamestate = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "sell", {"joker": 0, "consumable": 0}),
            "BAD_REQUEST",
            "Can only sell one item at a time",
        )

    def test_sell_no_jokers(self, client: httpx.Client) -> None:
        """Test sell endpoint when player has no jokers."""
        gamestate = load_fixture(
            client, "sell", "state-SELECTING_HAND--jokers.count-0--consumables.count-0"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["jokers"]["count"] == 0
        assert_error_response(
            api(client, "sell", {"joker": 0}),
            "NOT_ALLOWED",
            "No jokers available to sell",
        )

    def test_sell_no_consumables(self, client: httpx.Client) -> None:
        """Test sell endpoint when player has no consumables."""
        gamestate = load_fixture(
            client, "sell", "state-SELECTING_HAND--jokers.count-0--consumables.count-0"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["count"] == 0
        assert_error_response(
            api(client, "sell", {"consumable": 0}),
            "NOT_ALLOWED",
            "No consumables available to sell",
        )

    def test_sell_joker_invalid_index(self, client: httpx.Client) -> None:
        """Test sell endpoint with invalid joker index."""
        gamestate = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["jokers"]["count"] == 1
        assert_error_response(
            api(client, "sell", {"joker": 1}),
            "BAD_REQUEST",
            "Index out of range for joker: 1",
        )

    def test_sell_consumable_invalid_index(self, client: httpx.Client) -> None:
        """Test sell endpoint with invalid consumable index."""
        gamestate = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["count"] == 1
        assert_error_response(
            api(client, "sell", {"consumable": 1}),
            "BAD_REQUEST",
            "Index out of range for consumable: 1",
        )

    def test_sell_joker_in_SELECTING_HAND(self, client: httpx.Client) -> None:
        """Test selling a joker in SELECTING_HAND state."""
        before = load_fixture(
            client,
            "sell",
            "state-SELECTING_HAND--jokers.count-1--consumables.count-1",
        )
        assert before["state"] == "SELECTING_HAND"
        assert before["jokers"]["count"] == 1
        response = api(client, "sell", {"joker": 0})
        after = assert_gamestate_response(response)
        assert after["jokers"]["count"] == 0
        assert before["money"] < after["money"]

    def test_sell_consumable_in_SELECTING_HAND(self, client: httpx.Client) -> None:
        """Test selling a consumable in SELECTING_HAND state."""
        before = load_fixture(
            client, "sell", "state-SELECTING_HAND--jokers.count-1--consumables.count-1"
        )
        assert before["state"] == "SELECTING_HAND"
        assert before["consumables"]["count"] == 1
        response = api(client, "sell", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["consumables"]["count"] == 0
        assert before["money"] < after["money"]

    def test_sell_joker_in_SHOP(self, client: httpx.Client) -> None:
        """Test selling a joker in SHOP state."""
        before = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert before["state"] == "SHOP"
        assert before["jokers"]["count"] == 1
        response = api(client, "sell", {"joker": 0})
        after = assert_gamestate_response(response)
        assert after["jokers"]["count"] == 0
        assert before["money"] < after["money"]

    def test_sell_consumable_in_SHOP(self, client: httpx.Client) -> None:
        """Test selling a consumable in SHOP state."""
        before = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert before["state"] == "SHOP"
        assert before["consumables"]["count"] == 1
        response = api(client, "sell", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["consumables"]["count"] == 0
        assert before["money"] < after["money"]

    def test_sell_joker_exact_money_delta(self, client: httpx.Client) -> None:
        """Test selling a joker increases money by the card sell cost."""
        before = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        sell_cost = before["jokers"]["cards"][0]["cost"]["sell"]
        response = api(client, "sell", {"joker": 0})
        after = assert_gamestate_response(response)
        assert after["money"] == before["money"] + sell_cost

    def test_sell_from_SMODS_BOOSTER_OPENED(self, client: httpx.Client) -> None:
        """Test selling a joker while a booster pack is open."""
        before = load_fixture(
            client,
            "pack",
            "state-SMODS_BOOSTER_OPENED--pack.type-buffoon--jokers.count-4",
        )
        assert before["state"] == "SMODS_BOOSTER_OPENED"
        assert before["jokers"]["count"] >= 1
        sell_cost = before["jokers"]["cards"][0]["cost"]["sell"]
        response = api(client, "sell", {"joker": 0})
        after = assert_gamestate_response(response, state="SMODS_BOOSTER_OPENED")
        assert after["jokers"]["count"] == before["jokers"]["count"] - 1
        assert after["money"] == before["money"] + sell_cost


class TestSellEndpointValidation:
    """Test sell endpoint parameter validation."""

    def test_invalid_joker_type_string(self, client: httpx.Client) -> None:
        """Test that sell fails when joker parameter is a string."""
        gamestate = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["jokers"]["count"] == 1
        assert_error_response(
            api(client, "sell", {"joker": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'joker' must be an integer",
        )

    def test_invalid_consumable_type_string(self, client: httpx.Client) -> None:
        """Test that sell fails when consumable parameter is a string."""
        gamestate = load_fixture(
            client, "sell", "state-SHOP--jokers.count-1--consumables.count-1"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["count"] == 1
        assert_error_response(
            api(client, "sell", {"consumable": "INVALID_STRING"}),
            "BAD_REQUEST",
            "Field 'consumable' must be an integer",
        )


class TestSellEndpointStateRequirements:
    """Test sell endpoint state requirements."""

    def test_sell_from_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test selling a joker from BLIND_SELECT state."""
        before = load_fixture(
            client,
            "sell",
            "state-BLIND_SELECT--jokers.count-1--consumables.count-0",
        )
        assert before["state"] == "BLIND_SELECT"
        response = api(client, "sell", {"joker": 0})
        after = assert_gamestate_response(response, state="BLIND_SELECT")
        assert after["jokers"]["count"] == 0
        assert before["money"] < after["money"]

    def test_sell_from_ROUND_EVAL(self, client: httpx.Client) -> None:
        """Test selling is disallowed from ROUND_EVAL state."""
        before = load_fixture(
            client,
            "sell",
            "state-ROUND_EVAL--jokers.count-1--consumables.count-0",
        )
        assert before["state"] == "ROUND_EVAL"
        assert_error_response(
            api(client, "sell", {"joker": 0}),
            "INVALID_STATE",
            "Method 'sell' requires one of these states:",
        )

    def test_sell_from_MENU(self, client: httpx.Client) -> None:
        """Test that sell fails from the main menu."""
        api(client, "menu", {})
        assert_error_response(
            api(client, "sell", {"joker": 0}),
            "INVALID_STATE",
            "Method 'sell' requires one of these states:",
        )

    def test_sell_eternal_joker(self, client: httpx.Client) -> None:
        """Test that eternal jokers cannot be sold."""
        load_fixture(
            client, "sell", "state-SELECTING_HAND--jokers.count-0--consumables.count-0"
        )
        response = api(client, "add", {"key": "j_joker", "eternal": True})
        gamestate = assert_gamestate_response(response)
        assert gamestate["jokers"]["cards"][0]["modifier"]["eternal"] is True
        assert_error_response(
            api(client, "sell", {"joker": 0}),
            "NOT_ALLOWED",
            "Cannot sell eternal joker",
        )

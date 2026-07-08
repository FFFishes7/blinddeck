"""Tests for src/lua/endpoints/rearrange.lua"""

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestRearrangeInShopState:
    """Test rearranging cards in SHOP state."""

    def test_rearrange_jokers(self, client: httpx.Client) -> None:
        """Test rearranging jokers in shop."""
        before = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert before["state"] == "SHOP"
        assert before["jokers"]["count"] == 4
        prev_ids = [card["id"] for card in before["jokers"]["cards"]]
        permutation = [2, 0, 1, 3]
        response = api(
            client,
            "rearrange",
            {"jokers": permutation},
        )
        after = assert_gamestate_response(response)
        ids = [card["id"] for card in after["jokers"]["cards"]]
        assert ids == [prev_ids[i] for i in permutation]


class TestRearrangeEndpointValidation:
    """Test rearrange endpoint parameter validation."""

    def test_no_parameters_provided(self, client: httpx.Client) -> None:
        """Test error when no rearrange type specified."""
        gamestate = load_fixture(
            client, "rearrange", "state-SELECTING_HAND--hand.count-8"
        )
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(client, "rearrange", {})
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Must provide jokers",
        )

    def test_wrong_array_length_jokers(self, client: httpx.Client) -> None:
        """Test error when jokers array wrong length."""
        gamestate = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["jokers"]["count"] == 4
        response = api(
            client,
            "rearrange",
            {"jokers": [0, 1, 2]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Must provide exactly 4 indices for jokers",
        )

    def test_invalid_card_index(self, client: httpx.Client) -> None:
        """Test error when card index out of range."""
        gamestate = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["jokers"]["count"] == 4
        response = api(
            client,
            "rearrange",
            {"jokers": [-1, 1, 2, 3]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Index out of range for jokers: -1",
        )

    def test_duplicate_indices(self, client: httpx.Client) -> None:
        """Test error when indices contain duplicates."""
        gamestate = load_fixture(
            client, "rearrange", "state-SHOP--jokers.count-4--consumables.count-2"
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["jokers"]["count"] == 4
        response = api(
            client,
            "rearrange",
            {"jokers": [1, 1, 2, 3]},
        )
        assert_error_response(
            response,
            "BAD_REQUEST",
            "Duplicate index in jokers: 1",
        )


class TestRearrangeEndpointStateRequirements:
    """Test rearrange endpoint state requirements."""

    def test_rearrange_jokers_from_wrong_state(self, client: httpx.Client) -> None:
        """Test that rearranging jokers fails from wrong state."""
        gamestate = load_fixture(client, "rearrange", "state-BLIND_SELECT")
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "rearrange", {"jokers": [0, 1, 2, 3, 4]}),
            "INVALID_STATE",
            "Method 'rearrange' requires one of these states: SELECTING_HAND, SHOP",
        )

"""Tests for src/lua/endpoints/use.lua"""

import httpx
import pytest

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


class TestUseEndpoint:
    """Test basic use endpoint functionality."""

    def test_use_hermit_no_cards(self, client: httpx.Client) -> None:
        """Test using The Hermit (no card selection) in SHOP state."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SHOP--money-12--consumables.cards[0]-key-c_hermit",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["money"] == 12
        assert gamestate["consumables"]["cards"][0]["key"] == "c_hermit"
        response = api(client, "use", {"consumable": 0})
        assert_gamestate_response(response, money=24)

    def test_use_hermit_in_selecting_hand(self, client: httpx.Client) -> None:
        """Test using The Hermit in SELECTING_HAND state."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--money-12--consumables.cards[0]-key-c_hermit",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["money"] == 12
        assert gamestate["consumables"]["cards"][0]["key"] == "c_hermit"
        response = api(client, "use", {"consumable": 0})
        assert_gamestate_response(response, money=24)

    def test_use_hermit_consumable_count_decrements(self, client: httpx.Client) -> None:
        """Test that using a consumable decreases consumables count."""
        before = load_fixture(
            client,
            "use",
            "state-SHOP--money-12--consumables.cards[0]-key-c_hermit",
        )
        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response, money=24)
        assert after["consumables"]["count"] == before["consumables"]["count"] - 1

    def test_use_death_success(self, client: httpx.Client) -> None:
        """Test using Death with exactly 2 cards transforms the hand."""
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_death",
        )
        before_keys = [card["key"] for card in before["hand"]["cards"]]
        response = api(client, "use", {"consumable": 0, "cards": [0, 1]})
        after = assert_gamestate_response(response)
        assert after["consumables"]["count"] == before["consumables"]["count"] - 1
        after_keys = [card["key"] for card in after["hand"]["cards"]]
        assert after_keys != before_keys

    def test_use_from_SMODS_BOOSTER_OPENED_arcana(self, client: httpx.Client) -> None:
        """Test using a hand-targeting consumable while an Arcana pack is open."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SHOP--consumables.cards[0].key-c_magician",
        )
        assert gamestate["state"] == "SHOP"
        pack_index = next(
            (
                index
                for index, card in enumerate(gamestate["packs"]["cards"])
                if "arcana" in card["key"]
            ),
            None,
        )
        if pack_index is None:
            response = api(client, "reroll", {})
            gamestate = assert_gamestate_response(response, state="SHOP")
            pack_index = next(
                (
                    index
                    for index, card in enumerate(gamestate["packs"]["cards"])
                    if "arcana" in card["key"]
                ),
                None,
            )
        if pack_index is None:
            pytest.skip("Shop did not offer an Arcana pack to open")
        response = api(client, "buy", {"pack": pack_index})
        before = assert_gamestate_response(response, state="SMODS_BOOSTER_OPENED")
        if before["hand"]["count"] == 0:
            pytest.skip("Arcana pack opened without a visible hand in this setup")
        response = api(client, "use", {"consumable": 0, "cards": [0]})
        after = assert_gamestate_response(response, state="SMODS_BOOSTER_OPENED")
        assert after["consumables"]["count"] == before["consumables"]["count"] - 1
        assert after["hand"]["cards"][0]["modifier"]["enhancement"] == "LUCKY"

    def test_use_insufficient_space(self, client: httpx.Client) -> None:
        """Test that Judgement is blocked when joker slots are full."""
        load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--jokers.count-0--consumables.count-0",
        )
        for _ in range(5):
            response = api(client, "add", {"key": "j_joker"})
            assert_gamestate_response(response)
        response = api(client, "add", {"key": "c_judgement"})
        gamestate = assert_gamestate_response(response)
        consumable_index = gamestate["consumables"]["count"] - 1
        assert (
            gamestate["consumables"]["cards"][consumable_index]["key"] == "c_judgement"
        )
        assert gamestate["jokers"]["count"] == 5
        assert_error_response(
            api(client, "use", {"consumable": consumable_index}),
            "NOT_ALLOWED",
            "cannot be used at this time",
        )

    def test_use_temperance_no_cards(self, client: httpx.Client) -> None:
        """Test using Temperance (no card selection)."""
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0]-key-c_temperance--jokers.count-0",
        )
        assert before["state"] == "SELECTING_HAND"
        assert before["jokers"]["count"] == 0  # no jokers => no money increase
        assert before["consumables"]["cards"][0]["key"] == "c_temperance"
        response = api(client, "use", {"consumable": 0})
        assert_gamestate_response(response, money=before["money"])

    def test_use_planet_no_cards(self, client: httpx.Client) -> None:
        """Test using a Planet card (no card selection)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["hands"]["High Card"]["level"] == 1
        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["hands"]["High Card"]["level"] == 2

    def test_use_magician_with_one_card(self, client: httpx.Client) -> None:
        """Test using The Magician with 1 card (min=1, max=2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(client, "use", {"consumable": 1, "cards": [0]})
        after = assert_gamestate_response(response)
        assert after["hand"]["cards"][0]["modifier"]["enhancement"] == "LUCKY"

    def test_use_magician_with_two_cards(self, client: httpx.Client) -> None:
        """Test using The Magician with 2 cards."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        response = api(client, "use", {"consumable": 1, "cards": [7, 5]})
        after = assert_gamestate_response(response)
        assert after["hand"]["cards"][5]["modifier"]["enhancement"] == "LUCKY"
        assert after["hand"]["cards"][7]["modifier"]["enhancement"] == "LUCKY"

    def test_use_familiar_all_hand(self, client: httpx.Client) -> None:
        """Test using Familiar (destroys cards, #G.hand.cards > 1)."""
        before = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0]-key-c_familiar",
        )
        assert before["state"] == "SELECTING_HAND"
        response = api(client, "use", {"consumable": 0})
        after = assert_gamestate_response(response)
        assert after["hand"]["count"] == before["hand"]["count"] - 1 + 3
        assert after["hand"]["cards"][7]["set"] == "ENHANCED"
        assert after["hand"]["cards"][8]["set"] == "ENHANCED"
        assert after["hand"]["cards"][9]["set"] == "ENHANCED"


class TestUseEndpointValidation:
    """Test use endpoint parameter validation."""

    def test_use_no_consumable_provided(self, client: httpx.Client) -> None:
        """Test that use fails when consumable parameter is missing."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {}),
            "BAD_REQUEST",
            "Missing required field 'consumable'",
        )

    def test_use_invalid_consumable_type(self, client: httpx.Client) -> None:
        """Test that use fails when consumable is not an integer."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": "NOT_AN_INTEGER"}),
            "BAD_REQUEST",
            "Field 'consumable' must be an integer",
        )

    def test_use_invalid_consumable_index_negative(self, client: httpx.Client) -> None:
        """Test that use fails when consumable index is negative."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": -1}),
            "BAD_REQUEST",
            "Consumable index out of range: -1",
        )

    def test_use_invalid_consumable_index_too_high(self, client: httpx.Client) -> None:
        """Test that use fails when consumable index >= count."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 999}),
            "BAD_REQUEST",
            "Consumable index out of range: 999",
        )

    def test_use_invalid_cards_type(self, client: httpx.Client) -> None:
        """Test that use fails when cards is not an array."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": "NOT_AN_ARRAY_OF_INTEGERS"}),
            "BAD_REQUEST",
            "Field 'cards' must be an array",
        )

    def test_use_invalid_cards_item_type(self, client: httpx.Client) -> None:
        """Test that use fails when cards array contains non-integer."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": ["NOT_INT_1", "NOT_INT_2"]}),
            "BAD_REQUEST",
            "Field 'cards' array item at index 0 must be of type integer",
        )

    def test_use_invalid_card_index_negative(self, client: httpx.Client) -> None:
        """Test that use fails when a card index is negative."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": [-1]}),
            "BAD_REQUEST",
            "Card index out of range: -1",
        )

    def test_use_invalid_card_index_too_high(self, client: httpx.Client) -> None:
        """Test that use fails when a card index >= hand count."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": [999]}),
            "BAD_REQUEST",
            "Card index out of range: 999",
        )

    def test_use_magician_without_cards(self, client: httpx.Client) -> None:
        """Test that using The Magician without cards parameter fails."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][1]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 1}),
            "BAD_REQUEST",
            "Consumable 'The Magician' requires card selection",
        )

    def test_use_magician_with_empty_cards(self, client: httpx.Client) -> None:
        """Test that using The Magician with empty cards array fails."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][1]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": []}),
            "BAD_REQUEST",
            "Consumable 'The Magician' requires card selection",
        )

    def test_use_magician_too_many_cards(self, client: httpx.Client) -> None:
        """Test that using The Magician with 3 cards fails (max=2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][1]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 1, "cards": [0, 1, 2]}),
            "BAD_REQUEST",
            "Consumable 'The Magician' requires at most 2 cards (provided: 3)",
        )

    def test_use_death_too_few_cards(self, client: httpx.Client) -> None:
        """Test that using Death with 1 card fails (requires exactly 2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_death",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_death"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0]}),
            "BAD_REQUEST",
            "Consumable 'Death' requires exactly 2 cards (provided: 1)",
        )

    def test_use_death_too_many_cards(self, client: httpx.Client) -> None:
        """Test that using Death with 3 cards fails (requires exactly 2)."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_death",
        )
        assert gamestate["state"] == "SELECTING_HAND"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_death"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0, 1, 2]}),
            "BAD_REQUEST",
            "Consumable 'Death' requires exactly 2 cards (provided: 3)",
        )

    def test_use_death_arg_order_invariant(self, client: httpx.Client) -> None:
        """Death converts the lower-index card into a copy of the higher-index one,
        regardless of arg order. `use 0 [0,1]` and `use 0 [1,0]` produce the same hand."""

        def _use_and_snapshot(order: list[int]) -> tuple[dict, list[dict]]:
            before = load_fixture(
                client, "use", "state-SELECTING_HAND--consumables.cards[0].key-c_death"
            )
            orig_right = before["hand"]["cards"][1]["value"]
            after = assert_gamestate_response(
                api(client, "use", {"consumable": 0, "cards": order}),
                state="SELECTING_HAND",
            )
            return orig_right, after["hand"]["cards"]

        orig_right_fwd, hand_fwd = _use_and_snapshot([0, 1])
        orig_right_rev, hand_rev = _use_and_snapshot([1, 0])

        for hand, orig_right in [
            (hand_fwd, orig_right_fwd),
            (hand_rev, orig_right_rev),
        ]:
            assert hand[0]["value"]["rank"] == orig_right["rank"]
            assert hand[0]["value"]["suit"] == orig_right["suit"]
        assert [c["value"] for c in hand_fwd] == [c["value"] for c in hand_rev]


class TestUseEndpointStateRequirements:
    """Test use endpoint state requirements."""

    def test_use_from_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Hand-target consumables fail from BLIND_SELECT when no hand is visible."""
        gamestate = load_fixture(
            client,
            "use",
            "state-BLIND_SELECT--consumables.cards[0].key-c_magician",
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0]}),
            "INVALID_STATE",
            "Consumable 'The Magician' requires card selection and a visible hand",
        )

    def test_use_from_ROUND_EVAL(self, client: httpx.Client) -> None:
        """Hand-target consumables fail from ROUND_EVAL when no hand is visible."""
        gamestate = load_fixture(
            client,
            "use",
            "state-ROUND_EVAL--consumables.cards[0].key-c_magician",
        )
        assert gamestate["state"] == "ROUND_EVAL"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0]}),
            "INVALID_STATE",
            "Consumable 'The Magician' requires card selection and a visible hand",
        )

    def test_use_magician_from_SHOP(self, client: httpx.Client) -> None:
        """Test that The Magician fails from SHOP when no hand is visible."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SHOP--consumables.cards[0].key-c_magician",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_magician"
        assert_error_response(
            api(client, "use", {"consumable": 0, "cards": [0]}),
            "INVALID_STATE",
            "Consumable 'The Magician' requires card selection and a visible hand",
        )

    def test_use_familiar_from_SHOP(self, client: httpx.Client) -> None:
        """Test that The Familiar fails from SHOP when no hand is visible."""
        gamestate = load_fixture(
            client,
            "use",
            "state-SHOP--consumables.cards[0]-key-c_familiar",
        )
        assert gamestate["state"] == "SHOP"
        assert gamestate["consumables"]["cards"][0]["key"] == "c_familiar"
        assert_error_response(
            api(client, "use", {"consumable": 0}),
            "NOT_ALLOWED",
            "Consumable 'Familiar' cannot be used at this time",
        )

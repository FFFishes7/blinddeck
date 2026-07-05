"""Tests for src/lua/endpoints/sort.lua"""

import httpx
import pytest

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["D", "C", "H", "S"]


def _hand_ranks(gamestate: dict) -> list[str]:
    return [card["value"]["rank"] for card in gamestate["hand"]["cards"]]


def _hand_suits(gamestate: dict) -> list[str]:
    return [card["value"]["suit"] for card in gamestate["hand"]["cards"]]


def _assert_rank_order(ranks: list[str], *, descending: bool) -> None:
    indices = [RANKS.index(rank) for rank in ranks]
    expected = sorted(indices, reverse=descending)
    assert indices == expected


def _assert_suit_order(suits: list[str], *, descending: bool) -> None:
    indices = [SUITS.index(suit) for suit in suits]
    expected = sorted(indices, reverse=descending)
    assert indices == expected


class TestSortEndpoint:
    """Test basic sort endpoint functionality."""

    def test_sort_default_rank(self, client: httpx.Client) -> None:
        """Test sort endpoint with default rank descending mode."""
        before = load_fixture(client, "sort", "state-SELECTING_HAND")
        assert before["state"] == "SELECTING_HAND"
        response = api(client, "sort", {})
        after = assert_gamestate_response(response, state="SELECTING_HAND")
        _assert_rank_order(_hand_ranks(after), descending=True)

    @pytest.mark.parametrize(
        "mode,check",
        [
            ("rank", lambda gs: _assert_rank_order(_hand_ranks(gs), descending=True)),
            (
                "rank-desc",
                lambda gs: _assert_rank_order(_hand_ranks(gs), descending=True),
            ),
            (
                "rank-asc",
                lambda gs: _assert_rank_order(_hand_ranks(gs), descending=False),
            ),
            ("suit", lambda gs: _assert_suit_order(_hand_suits(gs), descending=True)),
            (
                "suit-desc",
                lambda gs: _assert_suit_order(_hand_suits(gs), descending=True),
            ),
            (
                "suit-asc",
                lambda gs: _assert_suit_order(_hand_suits(gs), descending=False),
            ),
        ],
    )
    def test_sort_modes(self, client: httpx.Client, mode: str, check: object) -> None:
        """Test sort endpoint with supported sort modes."""
        load_fixture(client, "sort", "state-SELECTING_HAND")
        response = api(client, "sort", {"mode": mode})
        after = assert_gamestate_response(response, state="SELECTING_HAND")
        check(after)  # type: ignore[operator]


class TestSortEndpointValidation:
    """Test sort endpoint parameter validation."""

    def test_invalid_sort_mode(self, client: httpx.Client) -> None:
        """Test that sort fails with an unsupported mode."""
        load_fixture(client, "sort", "state-SELECTING_HAND")
        assert_error_response(
            api(client, "sort", {"mode": "INVALID_MODE"}),
            "BAD_REQUEST",
            "Sort mode must be one of: rank, rank-desc, rank-asc, suit, suit-desc, suit-asc",
        )


class TestSortEndpointStateRequirements:
    """Test sort endpoint state requirements."""

    def test_sort_from_SHOP(self, client: httpx.Client) -> None:
        """Test that sort fails when not in SELECTING_HAND state."""
        load_fixture(client, "sort", "state-SHOP")
        assert_error_response(
            api(client, "sort", {}),
            "INVALID_STATE",
            "Method 'sort' requires one of these states: SELECTING_HAND",
        )

    def test_sort_from_MENU(self, client: httpx.Client) -> None:
        """Test that sort fails from the main menu."""
        api(client, "menu", {})
        assert_error_response(
            api(client, "sort", {}),
            "INVALID_STATE",
            "Method 'sort' requires one of these states: SELECTING_HAND",
        )

    def test_sort_in_SMODS_BOOSTER_OPENED_arcana(self, client: httpx.Client) -> None:
        """sort is rejected while a booster pack is open, even Arcana/Spectral.

        Balatro's Rank/Suit hand-sort buttons are hidden by the pack overlay
        (even when hand cards are visible for Tarot/Spectral targeting). The
        API matches the UI: sort is SELECTING_HAND-only.
        """
        load_fixture(
            client,
            "pack",
            "seed-VEBROR8--state-SMODS_BOOSTER_OPENED--pack.key-p_arcana_mega_1",
        )
        assert_error_response(
            api(client, "sort", {"mode": "rank-asc"}),
            "INVALID_STATE",
            "Method 'sort' requires one of these states: SELECTING_HAND",
        )

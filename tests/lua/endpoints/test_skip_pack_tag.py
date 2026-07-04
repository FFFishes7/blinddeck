"""Integration tests for skip tags that open a booster pack immediately."""

import httpx

from tests.lua.conftest import api, assert_gamestate_response
from tests.lua.tag_seeds import (
    BOSS_SMALL,
    CHARM_SMALL,
    DOUBLE_THEN_FOIL,
    ECONOMY_SMALL,
    FOIL_SMALL,
)

# Only Charm Tag can appear on ante 1; other pack tags need ante 2+ (game.lua min_ante).
CHARM_TAG = "Charm Tag"
FOIL_TAG = "Foil Tag"
ECONOMY_TAG = "Economy Tag"
DOUBLE_TAG = "Double Tag"
BOSS_TAG = "Boss Tag"


def _pending_tag_names(gamestate: dict) -> list[str]:
    return [t["name"] for t in gamestate.get("held_tags") or []]


def _assert_held_tags_ready(gamestate: dict) -> None:
    assert gamestate.get("held_tags_ready") is True, (
        "expected stable held_tags snapshot"
    )


def _assert_foil_held(gamestate: dict, *, seed: str) -> None:
    _assert_held_tags_ready(gamestate)
    assert FOIL_TAG in _pending_tag_names(gamestate), (
        f"expected Foil in held_tags (seed={seed!r})"
    )


def _assert_foil_not_held(gamestate: dict, *, seed: str) -> None:
    _assert_held_tags_ready(gamestate)
    assert FOIL_TAG not in _pending_tag_names(gamestate), (
        f"expected Foil consumed from held_tags (seed={seed!r})"
    )


def _start_blind_select(client: httpx.Client, seed: str) -> dict:
    api(client, "menu", {})
    return assert_gamestate_response(
        api(
            client,
            "start",
            {"deck": "RED", "stake": "WHITE", "seed": seed},
        ),
        state="BLIND_SELECT",
    )


def _assert_small_tag(gamestate: dict, *, seed: str, tag_name: str) -> None:
    actual = gamestate["blinds"]["small"]["tag_name"]
    assert actual == tag_name, (
        f"seed {seed!r} drifted: expected {tag_name!r} on small, got {actual!r}"
    )


class TestSkipPackTag:
    """Skip a blind with a pack-granting tag → reported pack-open state."""

    def test_skip_charm_tag_reports_booster_opened(self, client: httpx.Client) -> None:
        seed = CHARM_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_name=CHARM_TAG)

        response = api(client, "skip", {}, timeout=60)
        gamestate = assert_gamestate_response(response, state="SMODS_BOOSTER_OPENED")
        _assert_held_tags_ready(gamestate)
        assert CHARM_TAG not in _pending_tag_names(gamestate)
        pack_cards = (gamestate.get("pack") or {}).get("cards") or []
        assert pack_cards, f"expected open pack cards after Charm skip (seed={seed!r})"


class TestSkipHeldTags:
    """Stable held_tags snapshot after skip settle."""

    def test_skip_foil_tag_adds_pending_held_tag(self, client: httpx.Client) -> None:
        seed = FOIL_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_name=FOIL_TAG)

        response = api(client, "skip", {}, timeout=60)
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        _assert_held_tags_ready(gamestate)
        pending = _pending_tag_names(gamestate)
        assert FOIL_TAG in pending, f"expected Foil in held_tags (seed={seed!r})"
        foil_entries = [
            t for t in gamestate.get("held_tags") or [] if t.get("name") == FOIL_TAG
        ]
        assert len(foil_entries) == 1
        assert foil_entries[0].get("effect"), "expected non-empty tag effect"
        assert not (gamestate.get("pack") or {}).get("cards"), (
            "Foil skip should not open a pack"
        )

    def test_foil_tag_persists_through_round_and_consumed_in_shop(
        self, client: httpx.Client
    ) -> None:
        """Foil stays held through SELECTING_HAND/ROUND_EVAL; consumed on SHOP entry."""
        seed = FOIL_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_name=FOIL_TAG)

        gamestate = assert_gamestate_response(
            api(client, "skip", {}, timeout=60),
            state="BLIND_SELECT",
        )
        _assert_foil_held(gamestate, seed=seed)

        gamestate = assert_gamestate_response(
            api(client, "select", {}, timeout=60),
            state="SELECTING_HAND",
        )
        _assert_foil_held(gamestate, seed=seed)

        assert_gamestate_response(api(client, "set", {"chips": 1_000_000}))
        gamestate = assert_gamestate_response(
            api(client, "play", {"cards": [0, 1, 2, 3, 4]}, timeout=60),
            state="ROUND_EVAL",
        )
        _assert_foil_held(gamestate, seed=seed)

        gamestate = assert_gamestate_response(
            api(client, "cash_out", {}, timeout=60),
            state="SHOP",
        )
        _assert_foil_not_held(gamestate, seed=seed)

    def test_skip_economy_tag_consumed_not_held(self, client: httpx.Client) -> None:
        seed = ECONOMY_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_name=ECONOMY_TAG)

        money_before = gamestate["money"]
        response = api(client, "skip", {}, timeout=60)
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        _assert_held_tags_ready(gamestate)
        assert ECONOMY_TAG not in _pending_tag_names(gamestate)
        assert gamestate["money"] == min(money_before * 2, 40), (
            f"Economy Tag should double money up to $40 "
            f"(before={money_before}, after={gamestate['money']}, seed={seed!r})"
        )


class TestDoubleTagStack:
    """Double Tag copies the next tag obtained (oldest-first stack order)."""

    def test_double_tag_copies_foil_on_second_skip(self, client: httpx.Client) -> None:
        seed = DOUBLE_THEN_FOIL
        gamestate = _start_blind_select(client, seed)
        assert gamestate["blinds"]["small"]["tag_name"] == DOUBLE_TAG, (
            f"seed {seed!r} drifted: expected Double on small, "
            f"got {gamestate['blinds']['small']['tag_name']!r}"
        )
        assert gamestate["blinds"]["big"]["tag_name"] == FOIL_TAG, (
            f"seed {seed!r} drifted: expected Foil on big, "
            f"got {gamestate['blinds']['big']['tag_name']!r}"
        )

        gamestate = assert_gamestate_response(
            api(client, "skip", {}, timeout=60),
            state="BLIND_SELECT",
        )
        _assert_held_tags_ready(gamestate)
        assert DOUBLE_TAG in _pending_tag_names(gamestate)

        gamestate = assert_gamestate_response(
            api(client, "skip", {}, timeout=60),
            state="BLIND_SELECT",
        )
        _assert_held_tags_ready(gamestate)
        pending = _pending_tag_names(gamestate)
        assert pending == [FOIL_TAG, FOIL_TAG], (
            f"expected [Foil, Foil] oldest-first after Double copies Foil "
            f"(seed={seed!r}, got={pending!r})"
        )


class TestSkipNonPackTag:
    """Non-pack skip tags must settle on BLIND_SELECT without waiting for a pack."""

    def test_skip_non_pack_tag_stays_blind_select(self, client: httpx.Client) -> None:
        seed = BOSS_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_name=BOSS_TAG)

        response = api(client, "skip", {}, timeout=15)
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        _assert_held_tags_ready(gamestate)
        assert gamestate["blinds"]["small"]["status"] == "SKIPPED"
        pack_cards = (gamestate.get("pack") or {}).get("cards") or []
        assert not pack_cards, f"Boss Tag skip should not open a pack (seed={seed!r})"

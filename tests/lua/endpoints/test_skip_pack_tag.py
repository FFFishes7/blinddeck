"""Integration tests for skip tags that open a booster pack immediately."""

import time

import httpx

from tests.lua.conftest import api, assert_gamestate_response
from tests.lua.tag_seeds import (
    BOSS_SMALL,
    CHARM_SMALL,
    DOUBLE_THEN_CHARM,
    DOUBLE_THEN_FOIL,
    ECONOMY_SMALL,
    FOIL_SMALL,
)

# Locale-independent tag keys (Balatro G.P_TAGS ids)
CHARM_TAG_KEY = "tag_charm"
FOIL_TAG_KEY = "tag_foil"
ECONOMY_TAG_KEY = "tag_economy"
DOUBLE_TAG_KEY = "tag_double"
BOSS_TAG_KEY = "tag_boss"

# Display names (English install; tag_key assertions are locale-safe)
CHARM_TAG = "Charm Tag"
FOIL_TAG = "Foil Tag"
ECONOMY_TAG = "Economy Tag"
DOUBLE_TAG = "Double Tag"
BOSS_TAG = "Boss Tag"


def _pending_tag_keys(gamestate: dict) -> list[str]:
    return [t["key"] for t in gamestate.get("held_tags") or []]


def _pending_tag_names(gamestate: dict) -> list[str]:
    return [t["name"] for t in gamestate.get("held_tags") or []]


def _assert_held_tags_ready(gamestate: dict) -> None:
    assert gamestate.get("held_tags_ready") is True, (
        "expected stable held_tags snapshot"
    )


def _assert_foil_held(gamestate: dict, *, seed: str) -> None:
    _assert_held_tags_ready(gamestate)
    assert FOIL_TAG_KEY in _pending_tag_keys(gamestate), (
        f"expected Foil in held_tags (seed={seed!r})"
    )


def _assert_foil_not_held(gamestate: dict, *, seed: str) -> None:
    _assert_held_tags_ready(gamestate)
    assert FOIL_TAG_KEY not in _pending_tag_keys(gamestate), (
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


def _assert_small_tag(gamestate: dict, *, seed: str, tag_key: str) -> None:
    actual = gamestate["blinds"]["small"]["tag_key"]
    assert actual == tag_key, (
        f"seed {seed!r} drifted: expected {tag_key!r} on small, got {actual!r}"
    )


def _pack_pick_params(gamestate: dict, card_idx: int) -> dict:
    """Build pack params; include hand targets when the card requires them."""
    card = gamestate["pack"]["cards"][card_idx]
    params: dict = {"card": card_idx}
    value = card.get("value") or {}
    tmin = value.get("target_min")
    if isinstance(tmin, int):
        params["targets"] = list(range(tmin))
    return params


def _wait_for_open_pack(client: httpx.Client, *, timeout: float = 60) -> dict:
    """Poll gamestate until a booster pack is open and ready to snapshot."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        gamestate = assert_gamestate_response(api(client, "gamestate", {}))
        pack = gamestate.get("pack") or {}
        if (
            gamestate.get("pack_ready")
            and pack.get("cards")
            and pack.get("choices_remaining")
        ):
            if gamestate.get("pack_hand_ready") is False:
                continue
            return gamestate
    raise AssertionError(
        "timed out waiting for pack_ready open pack with choices_remaining"
    )


class TestSkipPackTag:
    """Skip a blind with a pack-granting tag → reported pack-open state."""

    def test_skip_charm_tag_reports_booster_opened(self, client: httpx.Client) -> None:
        seed = CHARM_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_key=CHARM_TAG_KEY)

        response = api(client, "skip", {}, timeout=60)
        gamestate = assert_gamestate_response(response, state="SMODS_BOOSTER_OPENED")
        _assert_held_tags_ready(gamestate)
        assert CHARM_TAG_KEY not in _pending_tag_keys(gamestate)
        pack_cards = (gamestate.get("pack") or {}).get("cards") or []
        assert pack_cards, f"expected open pack cards after Charm skip (seed={seed!r})"
        # Charm Tag opens Mega Arcana (choose=2)
        assert gamestate["pack"]["choices_remaining"] == 2


class TestSkipHeldTags:
    """Stable held_tags snapshot after skip settle."""

    def test_skip_foil_tag_adds_pending_held_tag(self, client: httpx.Client) -> None:
        seed = FOIL_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_key=FOIL_TAG_KEY)

        response = api(client, "skip", {}, timeout=60)
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        _assert_held_tags_ready(gamestate)
        pending = _pending_tag_keys(gamestate)
        assert FOIL_TAG_KEY in pending, f"expected Foil in held_tags (seed={seed!r})"
        foil_entries = [
            t for t in gamestate.get("held_tags") or [] if t.get("key") == FOIL_TAG_KEY
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
        _assert_small_tag(gamestate, seed=seed, tag_key=FOIL_TAG_KEY)

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
        _assert_small_tag(gamestate, seed=seed, tag_key=ECONOMY_TAG_KEY)

        money_before = gamestate["money"]
        response = api(client, "skip", {}, timeout=60)
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        _assert_held_tags_ready(gamestate)
        assert ECONOMY_TAG_KEY not in _pending_tag_keys(gamestate)
        assert gamestate["money"] == min(money_before * 2, 40), (
            f"Economy Tag should double money up to $40 "
            f"(before={money_before}, after={gamestate['money']}, seed={seed!r})"
        )


class TestDoubleTagStack:
    """Double Tag copies the next tag obtained (oldest-first stack order)."""

    def test_double_tag_copies_foil_on_second_skip(self, client: httpx.Client) -> None:
        seed = DOUBLE_THEN_FOIL
        gamestate = _start_blind_select(client, seed)
        assert gamestate["blinds"]["small"]["tag_key"] == DOUBLE_TAG_KEY, (
            f"seed {seed!r} drifted: expected Double on small, "
            f"got {gamestate['blinds']['small']['tag_key']!r}"
        )
        assert gamestate["blinds"]["big"]["tag_key"] == FOIL_TAG_KEY, (
            f"seed {seed!r} drifted: expected Foil on big, "
            f"got {gamestate['blinds']['big']['tag_key']!r}"
        )

        gamestate = assert_gamestate_response(
            api(client, "skip", {}, timeout=60),
            state="BLIND_SELECT",
        )
        _assert_held_tags_ready(gamestate)
        assert DOUBLE_TAG_KEY in _pending_tag_keys(gamestate)

        gamestate = assert_gamestate_response(
            api(client, "skip", {}, timeout=60),
            state="BLIND_SELECT",
        )
        _assert_held_tags_ready(gamestate)
        pending = _pending_tag_keys(gamestate)
        assert pending == [FOIL_TAG_KEY, FOIL_TAG_KEY], (
            f"expected [tag_foil, tag_foil] oldest-first after Double copies Foil "
            f"(seed={seed!r}, got={pending!r})"
        )

    def test_double_charm_opens_two_packs_with_choices_remaining(
        self, client: httpx.Client
    ) -> None:
        """Double Tag copies Charm → two consecutive Mega Arcana packs."""
        seed = DOUBLE_THEN_CHARM
        gamestate = _start_blind_select(client, seed)
        assert gamestate["blinds"]["small"]["tag_key"] == DOUBLE_TAG_KEY, (
            f"seed {seed!r} drifted: expected Double on small, "
            f"got {gamestate['blinds']['small']['tag_key']!r}"
        )
        assert gamestate["blinds"]["big"]["tag_key"] == CHARM_TAG_KEY, (
            f"seed {seed!r} drifted: expected Charm on big, "
            f"got {gamestate['blinds']['big']['tag_key']!r}"
        )

        gamestate = assert_gamestate_response(
            api(client, "skip", {}, timeout=60),
            state="BLIND_SELECT",
        )
        _assert_held_tags_ready(gamestate)
        assert DOUBLE_TAG_KEY in _pending_tag_keys(gamestate)

        gamestate = assert_gamestate_response(
            api(client, "skip", {}, timeout=60),
            state="SMODS_BOOSTER_OPENED",
        )
        assert gamestate["pack"]["choices_remaining"] == 2

        gamestate = assert_gamestate_response(
            api(client, "pack", _pack_pick_params(gamestate, 0), timeout=60),
            state="SMODS_BOOSTER_OPENED",
        )
        assert gamestate["pack"]["choices_remaining"] == 1

        assert_gamestate_response(
            api(client, "pack", _pack_pick_params(gamestate, 0), timeout=60),
        )
        gamestate = _wait_for_open_pack(client)
        assert gamestate.get("pack_ready") is True
        pack_cards = (gamestate.get("pack") or {}).get("cards") or []
        assert pack_cards, "second pack must have cards when pack_ready"
        assert gamestate["pack"]["choices_remaining"] == 2


class TestSkipNonPackTag:
    """Non-pack skip tags must settle on BLIND_SELECT without waiting for a pack."""

    def test_skip_non_pack_tag_stays_blind_select(self, client: httpx.Client) -> None:
        seed = BOSS_SMALL
        gamestate = _start_blind_select(client, seed)
        _assert_small_tag(gamestate, seed=seed, tag_key=BOSS_TAG_KEY)

        response = api(client, "skip", {}, timeout=15)
        gamestate = assert_gamestate_response(response, state="BLIND_SELECT")
        _assert_held_tags_ready(gamestate)
        assert gamestate["blinds"]["small"]["status"] == "SKIPPED"
        pack_cards = (gamestate.get("pack") or {}).get("cards") or []
        assert not pack_cards, f"Boss Tag skip should not open a pack (seed={seed!r})"

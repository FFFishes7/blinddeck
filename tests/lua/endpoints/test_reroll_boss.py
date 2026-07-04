"""Tests for src/lua/endpoints/reroll_boss.lua"""

from __future__ import annotations

import httpx

from tests.lua.conftest import (
    api,
    assert_error_response,
    assert_gamestate_response,
    load_fixture,
)


def _setup_boss_with_directors_cut(client: httpx.Client, *, money: int = 20) -> dict:
    load_fixture(client, "skip", "state-BLIND_SELECT--blinds.boss.status-SELECT")
    gs = api(
        client,
        "set",
        {
            "grant_voucher": "v_directors_cut",
            "money": money,
            "boss_rerolled": False,
        },
    )["result"]
    assert gs["state"] == "BLIND_SELECT"
    assert gs["blinds"]["boss"]["status"] in ("SELECT", "CURRENT")
    assert gs.get("used_vouchers", {}).get("v_directors_cut") is not None
    assert gs.get("round", {}).get("boss_reroll_available") is True
    return gs


class TestRerollBossEndpoint:
    """Reroll Boss blind with Director's Cut / Retcon."""

    def test_reroll_boss_success(self, client: httpx.Client) -> None:
        gs = _setup_boss_with_directors_cut(client)
        old_name = gs["blinds"]["boss"]["name"]
        money_before = gs["money"]
        response = api(client, "reroll_boss", {}, timeout=60)
        gs = assert_gamestate_response(response, state="BLIND_SELECT")
        assert gs["blinds"]["boss"]["name"] != old_name
        assert gs["money"] == money_before - 10
        assert gs.get("round", {}).get("boss_rerolled") is True
        assert gs.get("round", {}).get("boss_reroll_available") is False

    def test_reroll_boss_twice_directors_cut(self, client: httpx.Client) -> None:
        _setup_boss_with_directors_cut(client)
        assert_gamestate_response(api(client, "reroll_boss", {}, timeout=60))
        assert_error_response(
            api(client, "reroll_boss", {}, timeout=60),
            "NOT_ALLOWED",
            "Director's Cut or Retcon",
        )

    def test_reroll_boss_retcon_unlimited(self, client: httpx.Client) -> None:
        load_fixture(client, "skip", "state-BLIND_SELECT--blinds.boss.status-SELECT")
        gs = api(
            client,
            "set",
            {
                "grant_voucher": "v_retcon",
                "money": 30,
                "boss_rerolled": True,
            },
        )["result"]
        assert gs.get("round", {}).get("boss_reroll_available") is True
        old_name = gs["blinds"]["boss"]["name"]
        money_before = gs["money"]
        gs = assert_gamestate_response(
            api(client, "reroll_boss", {}, timeout=60), state="BLIND_SELECT"
        )
        assert gs["blinds"]["boss"]["name"] != old_name
        assert gs["money"] == money_before - 10
        assert gs.get("round", {}).get("boss_reroll_available") is True

    def test_reroll_boss_insufficient_funds(self, client: httpx.Client) -> None:
        load_fixture(client, "skip", "state-BLIND_SELECT--blinds.boss.status-SELECT")
        gs = api(
            client,
            "set",
            {
                "grant_voucher": "v_directors_cut",
                "money": 5,
                "boss_rerolled": False,
            },
        )["result"]
        assert gs.get("round", {}).get("boss_reroll_available") is False
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "Not enough dollars",
        )

    def test_reroll_boss_not_boss_phase(self, client: httpx.Client) -> None:
        gamestate = load_fixture(
            client, "select", "state-BLIND_SELECT--blinds.small.status-SELECT"
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "Boss blind is on deck",
        )

    def test_reroll_boss_without_voucher(self, client: httpx.Client) -> None:
        gamestate = load_fixture(
            client, "skip", "state-BLIND_SELECT--blinds.boss.status-SELECT"
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert not (gamestate.get("used_vouchers") or {}).get("v_directors_cut")
        assert_error_response(
            api(client, "reroll_boss", {}),
            "NOT_ALLOWED",
            "Director's Cut or Retcon",
        )


class TestRerollBossEndpointStateRequirements:
    """State requirements for reroll_boss."""

    def test_reroll_boss_from_SHOP(self, client: httpx.Client) -> None:
        gamestate = load_fixture(client, "reroll", "state-SHOP")
        assert gamestate["state"] == "SHOP"
        assert_error_response(
            api(client, "reroll_boss", {}),
            "INVALID_STATE",
            "Method 'reroll_boss' requires one of these states: BLIND_SELECT",
        )

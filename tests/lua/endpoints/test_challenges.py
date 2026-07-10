"""Live coverage for native Challenge Mode endpoints."""

from __future__ import annotations

import httpx

from tests.lua.conftest import api, assert_error_response, assert_gamestate_response


def _catalog(client: httpx.Client) -> list[dict]:
    response = api(client, "challenges", {})
    assert "result" in response
    catalog = response["result"]["challenges"]
    assert isinstance(catalog, list) and catalog
    return catalog


def _set_profile(client: httpx.Client, mode: str) -> None:
    response = api(client, "test_challenge_profile", {"mode": mode})
    assert response["result"] == {"success": True}


def test_challenges_catalog_is_native_ordered_and_serialized(
    client: httpx.Client,
) -> None:
    api(client, "menu", {})
    catalog = _catalog(client)
    assert [entry["index"] for entry in catalog] == list(range(1, len(catalog) + 1))
    for entry in catalog:
        assert isinstance(entry["id"], str) and entry["id"]
        assert isinstance(entry["name"], str) and entry["name"]
        assert isinstance(entry["unlocked"], bool)
        assert isinstance(entry["completed"], bool)
        assert {"jokers", "consumables", "vouchers", "rules", "restrictions"}.issubset(
            entry
        )


def test_challenge_rejects_unknown_and_locked_ids(client: httpx.Client) -> None:
    api(client, "menu", {})
    assert_error_response(
        api(client, "challenge", {"id": "not_a_real_challenge"}),
        "BAD_REQUEST",
        "Unknown challenge ID",
    )

    try:
        _set_profile(client, "lock_all")
        entry = _catalog(client)[0]
        assert entry["unlocked"] is False
        assert_error_response(
            api(client, "challenge", {"id": entry["id"]}),
            "NOT_ALLOWED",
            "Challenge is locked",
        )
        assert_gamestate_response(api(client, "gamestate", {}), state="MENU")
    finally:
        _set_profile(client, "restore")


def test_challenge_starts_unlocked_native_setup(client: httpx.Client) -> None:
    api(client, "menu", {})
    try:
        _set_profile(client, "unlock_all")
        entry = _catalog(client)[0]
        response = api(client, "challenge", {"id": entry["id"]})
        state = response["result"]
        assert_gamestate_response(response, state="BLIND_SELECT", stake="WHITE")
        assert state["challenge"] == {"id": entry["id"], "name": entry["name"]}
        assert state["jokers"]["count"] >= len(entry["jokers"])
    finally:
        api(client, "menu", {})
        _set_profile(client, "restore")

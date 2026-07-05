"""Live and fixture tests for round.cashout_preview."""

from __future__ import annotations

import httpx
import pytest

from tests.lua.conftest import api, assert_gamestate_response, load_fixture


def _preview_lines(gamestate: dict) -> list[dict]:
    preview = (gamestate.get("round") or {}).get("cashout_preview")
    assert preview is not None, "expected round.cashout_preview"
    lines = preview.get("lines")
    assert isinstance(lines, list)
    return lines


def _line_by_kind(gamestate: dict, kind: str) -> list[dict]:
    return [line for line in _preview_lines(gamestate) if line.get("kind") == kind]


def _win_from_selecting_hand(client: httpx.Client) -> dict:
    api(client, "set", {"chips": 10000})
    return assert_gamestate_response(
        api(client, "play", {"cards": [0]}),
        state="ROUND_EVAL",
    )


class TestCashoutPreviewFixture:
    """Fixture-based cashout preview on ROUND_EVAL."""

    def test_round_eval_fixture_has_cashout_preview(self, client: httpx.Client) -> None:
        gamestate = load_fixture(client, "cash_out", "state-ROUND_EVAL")
        assert gamestate["state"] == "ROUND_EVAL"
        preview = gamestate["round"]["cashout_preview"]
        assert isinstance(preview, dict)
        assert isinstance(preview["lines"], list)
        assert preview["lines"], "expected at least one cashout line"
        assert isinstance(preview["total"], int)
        assert preview["total"] > 0
        kinds = {line["kind"] for line in preview["lines"]}
        assert "hands" in kinds


class TestCashoutPreviewLive:
    """Live cashout preview vs actual cash_out."""

    def test_golden_joker_row(self, client: httpx.Client) -> None:
        load_fixture(client, "play", "state-SELECTING_HAND")
        api(client, "add", {"key": "j_golden"})
        gamestate = _win_from_selecting_hand(client)
        joker_lines = [
            line
            for line in _preview_lines(gamestate)
            if line.get("kind") == "joker" and line.get("key") == "j_golden"
        ]
        assert len(joker_lines) == 1
        assert joker_lines[0]["dollars"] == 4

    def test_to_the_moon_interest(self, client: httpx.Client) -> None:
        gamestate = load_fixture(client, "play", "state-SELECTING_HAND")
        api(client, "add", {"key": "j_to_the_moon"})
        api(client, "set", {"chips": 10000, "money": 10})
        gamestate = assert_gamestate_response(
            api(client, "play", {"cards": [0]}),
            state="ROUND_EVAL",
        )
        interest_lines = _line_by_kind(gamestate, "interest")
        assert len(interest_lines) == 1
        # interest_amount=2 (base 1 + To the Moon 1), floor(10/5)=2 → $4
        assert interest_lines[0]["dollars"] == 4

    def test_total_matches_cash_out(self, client: httpx.Client) -> None:
        gamestate = load_fixture(client, "cash_out", "state-ROUND_EVAL")
        money_before = gamestate["money"]
        total = gamestate["round"]["cashout_preview"]["total"]
        after = assert_gamestate_response(api(client, "cash_out", {}), state="SHOP")
        assert after["money"] == money_before + total

    def test_investment_tag_on_boss_round(self, client: httpx.Client) -> None:
        """Boss win with Investment Tag held adds a tag eval row."""
        gamestate = load_fixture(
            client,
            "play",
            "state-SELECTING_HAND--ante_num-8--blinds.boss.status-CURRENT--round.chips-1000000",
        )
        assert gamestate["blinds"]["boss"]["status"] == "CURRENT"
        held = [t.get("name") for t in gamestate.get("held_tags") or []]
        if "Investment Tag" not in held:
            pytest.skip("Investment Tag not held on this boss fixture path")
        gamestate = assert_gamestate_response(
            api(client, "play", {"cards": [0]}),
            state="ROUND_EVAL",
        )
        tag_lines = _line_by_kind(gamestate, "tag")
        assert any(line.get("dollars") == 25 for line in tag_lines)

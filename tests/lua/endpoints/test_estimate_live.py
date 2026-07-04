"""Live estimate vs play scoring — validates estimate.py against real Balatro."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

PLAY_ROOT = Path(__file__).resolve().parents[3] / "tools" / "play"
sys.path.insert(0, str(PLAY_ROOT))

import estimate  # noqa: E402  # type: ignore[unresolved-import]

from tests.lua.conftest import api, load_fixture


def _hand_rank(gs: dict, idx: int) -> str | None:
    cards = (gs.get("hand") or {}).get("cards") or []
    if idx >= len(cards):
        return None
    return (cards[idx].get("value") or {}).get("rank")


def _play_delta(client: httpx.Client, gs: dict, indices: list[int]) -> int:
    chips_before = gs["round"]["chips"]
    gs_after = api(client, "play", {"cards": indices})["result"]
    return gs_after["round"]["chips"] - chips_before


class TestEstimateLiveScoring:
    """Estimate top play must match incremental round.chips from play."""

    def test_gros_michel_top_matches_play(self, client: httpx.Client) -> None:
        gs = load_fixture(client, "gamestate", "state-SELECTING_HAND")
        gs = api(client, "add", {"key": "j_gros_michel"})["result"]
        est = estimate.estimate(gs)
        assert not est["estimate"]["unmodeled_jokers"]
        top = est["estimate"]["top"][0]
        delta = _play_delta(client, gs, top["indices"])
        assert delta == top["score"], (
            f"estimate={top['score']} actual={delta} "
            f"hand={top['hand_type']} idx={top['indices']}"
        )

    def test_jolly_pair_matches_play_when_top_is_pair(self, client: httpx.Client) -> None:
        gs = load_fixture(client, "gamestate", "state-SELECTING_HAND")
        gs = api(client, "add", {"key": "j_jolly"})["result"]
        est = estimate.estimate(gs)
        assert not est["estimate"]["unmodeled_jokers"]
        pair_plays = [r for r in est["estimate"]["top"] if r["hand_type"] == "Pair"]
        assert pair_plays, "fixture hand should offer a Pair line with j_jolly"
        pick = pair_plays[0]
        delta = _play_delta(client, gs, pick["indices"])
        assert delta == pick["score"], (
            f"estimate={pick['score']} actual={delta} idx={pick['indices']}"
        )

    def test_runner_top_matches_play(self, client: httpx.Client) -> None:
        gs = load_fixture(client, "gamestate", "state-SELECTING_HAND")
        gs = api(client, "add", {"key": "j_runner"})["result"]
        est = estimate.estimate(gs)
        assert not est["estimate"]["unmodeled_jokers"]
        top = est["estimate"]["top"][0]
        delta = _play_delta(client, gs, top["indices"])
        assert delta == top["score"], (
            f"estimate={top['score']} actual={delta} "
            f"hand={top['hand_type']} idx={top['indices']}"
        )

    def test_wee_joker_pair_of_twos_matches_play(self, client: httpx.Client) -> None:
        gs = load_fixture(client, "gamestate", "state-SELECTING_HAND")
        gs = api(client, "add", {"key": "j_wee"})["result"]
        twos = [i for i in range((gs.get("hand") or {}).get("count", 0)) if _hand_rank(gs, i) == "2"]
        assert len(twos) >= 2, "fixture hand needs at least two 2s for wee joker live test"
        indices = twos[:2]
        est_line = estimate.score_hand_indices(gs, indices)
        delta = _play_delta(client, gs, indices)
        assert delta == est_line["score"], (
            f"estimate={est_line['score']} actual={delta} idx={indices}"
        )

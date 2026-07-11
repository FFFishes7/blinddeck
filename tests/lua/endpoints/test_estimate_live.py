"""Live estimate vs play scoring — validates estimate.py against real Balatro."""

from __future__ import annotations

import httpx
import pytest

from tests.lua.endpoints.estimate_live_recipes import all_live_recipes
from tests.lua.endpoints.estimate_live_runner import run_live_recipe, run_scenario
from tests.lua.endpoints.estimate_live_scenarios import all_scenarios, get_scenario

_ALL_RECIPES = all_live_recipes()
_SCORING_IDS = [r.recipe_id for r in _ALL_RECIPES if r.check_unmodeled]
_BUFF_IDS = [r.recipe_id for r in _ALL_RECIPES if not r.check_unmodeled]
_ALL_SCENARIOS = all_scenarios()
_SCENARIO_IDS = [s.scenario_id for s in _ALL_SCENARIOS]


class TestEstimateLiveScoring:
    """Each deterministic scoring joker: estimate must match play delta."""

    @pytest.mark.parametrize(
        "recipe_id",
        _SCORING_IDS,
        ids=_SCORING_IDS,
    )
    def test_scoring_joker_matches_play(
        self, client: httpx.Client, recipe_id: str
    ) -> None:
        recipe = next(r for r in _ALL_RECIPES if r.recipe_id == recipe_id)
        run_live_recipe(client, recipe)


class TestEstimateLiveCardBuffs:
    """Deterministic card buffs: estimate must match play delta."""

    @pytest.mark.parametrize(
        "recipe_id",
        _BUFF_IDS,
        ids=_BUFF_IDS,
    )
    def test_card_buff_matches_play(self, client: httpx.Client, recipe_id: str) -> None:
        recipe = next(r for r in _ALL_RECIPES if r.recipe_id == recipe_id)
        run_live_recipe(client, recipe)

    def test_scoring_joker_count(self) -> None:
        assert len(_SCORING_IDS) == 99

    def test_buff_recipe_count(self) -> None:
        assert len(_BUFF_IDS) == 15


class TestEstimateLiveScenarios:
    """Multi-joker + buff interaction scenarios with order-sensitive scoring."""

    @pytest.mark.parametrize(
        "scenario_id",
        _SCENARIO_IDS,
        ids=_SCENARIO_IDS,
    )
    def test_scenario_order_sensitive(
        self, client: httpx.Client, scenario_id: str
    ) -> None:
        run_scenario(client, get_scenario(scenario_id))

    def test_scenario_count(self) -> None:
        assert len(_SCENARIO_IDS) == 36

"""Run live estimate recipes against Balatro."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

PLAY_ROOT = Path(__file__).resolve().parents[3] / "tools" / "play"
sys.path.insert(0, str(PLAY_ROOT))

import estimate  # noqa: E402  # type: ignore[unresolved-import]

from tests.lua.conftest import api, load_fixture  # noqa: E402
from tests.lua.endpoints.estimate_live_recipes import (  # noqa: E402
    PAIR_5,
    CardAdd,
    JokerAdd,
    LiveRecipe,
)
from tests.lua.endpoints.estimate_live_scenarios import (  # noqa: E402
    ScenarioLine,
    ScenarioRecipe,
)


def _ranks_equal(a: str | None, b: str) -> bool:
    if a is None:
        return False
    if a == b:
        return True
    return {a, b} == {"T", "10"}


def _card_key_parts(key: str) -> tuple[str, str]:
    suit, rank = key.split("_", 1)
    return suit, rank


def _hand_rank(gs: dict, idx: int) -> str | None:
    cards = (gs.get("hand") or {}).get("cards") or []
    if idx >= len(cards):
        return None
    return (cards[idx].get("value") or {}).get("rank")


def _hand_suit(gs: dict, idx: int) -> str | None:
    cards = (gs.get("hand") or {}).get("cards") or []
    if idx >= len(cards):
        return None
    return (cards[idx].get("value") or {}).get("suit")


def _card_matches_add(gs: dict, idx: int, want: CardAdd) -> bool:
    cards = (gs.get("hand") or {}).get("cards") or []
    if idx >= len(cards):
        return False
    c = cards[idx]
    val = c.get("value") or {}
    mod = c.get("modifier") or {}
    ws, wr = _card_key_parts(want.key)
    if not _ranks_equal(val.get("rank"), wr) or val.get("suit") != ws:
        return False
    if want.enhancement and mod.get("enhancement") != want.enhancement:
        return False
    if want.edition and mod.get("edition") != want.edition:
        return False
    if want.seal and mod.get("seal") != want.seal:
        return False
    return True


def _indices_for_cards(gs: dict, wants: tuple[CardAdd, ...]) -> list[int]:
    used: set[int] = set()
    indices: list[int] = []
    for want in wants:
        found = False
        for i in range((gs.get("hand") or {}).get("count", 0)):
            if i in used:
                continue
            if _card_matches_add(gs, i, want):
                indices.append(i)
                used.add(i)
                found = True
                break
        if not found:
            raise AssertionError(
                f"card not found in hand: {want.key} enh={want.enhancement}"
            )
    return indices


def _indices_for_rank(gs: dict, rank: str, count: int = 2) -> list[int]:
    found = [
        i
        for i in range((gs.get("hand") or {}).get("count", 0))
        if _hand_rank(gs, i) == rank
    ]
    if len(found) < count:
        raise AssertionError(f"need {count} cards rank {rank}, found {len(found)}")
    return found[:count]


def _play_delta(client: httpx.Client, gs: dict, indices: list[int]) -> int:
    chips_before = gs["round"]["chips"]
    resp = api(client, "play", {"cards": indices})
    if "error" in resp:
        raise RuntimeError(f"Play API error: {resp['error']}")
    gs_after = resp["result"]
    return gs_after["round"]["chips"] - chips_before


def _add_cards(client: httpx.Client, gs: dict, cards: tuple[CardAdd, ...]) -> dict:
    for card in cards:
        gs = api(client, "add", card.to_add_params())["result"]
    return gs


def _debuff_cards(client: httpx.Client, gs: dict, cards: tuple[CardAdd, ...]) -> dict:
    indices = _indices_for_cards(gs, cards)
    return api(client, "debuff", {"cards": indices, "debuff": True})["result"]


def setup_recipe(client: httpx.Client, recipe: LiveRecipe) -> dict:
    gs = load_fixture(client, "gamestate", "state-SELECTING_HAND")
    if recipe.jokers:
        for joker in recipe.jokers:
            gs = api(client, "add", joker.to_add_params())["result"]
    else:
        for key in recipe.joker_keys:
            gs = api(client, "add", {"key": key})["result"]
    gs = _add_cards(client, gs, recipe.cards)
    if recipe.set_state:
        gs = api(client, "set", recipe.set_state)["result"]
    if recipe.debuff:
        gs = _debuff_cards(client, gs, recipe.debuff)
    if recipe.require_loyalty_active:
        loyalty_ok = False
        for j in (gs.get("jokers") or {}).get("cards") or []:
            if j.get("key") != "j_loyalty_card":
                continue
            stats = (j.get("value") or {}).get("stats") or {}
            every = stats.get("loyalty_every")
            remaining = stats.get("loyalty_remaining")
            if (
                every is not None
                and remaining is not None
                and int(remaining) == int(every)
            ):
                loyalty_ok = True
                break
        if not loyalty_ok:
            pytest.skip("Loyalty Card countdown not active for ×Mult proc")
    if recipe.pre_play_pair:
        idx = _indices_for_rank(gs, "5", 2)
        api(client, "play", {"cards": idx})
        gs = api(client, "gamestate")["result"]
        gs = _add_cards(client, gs, PAIR_5)
    gs = _maybe_add_round_target_cards(client, gs, recipe)
    return gs


def _maybe_add_round_target_cards(
    client: httpx.Client, gs: dict, recipe: LiveRecipe
) -> dict:
    if recipe.pick == "ancient":
        suit = (gs.get("round") or {}).get("ancient_suit")
        if not suit:
            pytest.skip("round.ancient_suit not set in fixture")
        have = sum(
            1
            for i in range((gs.get("hand") or {}).get("count", 0))
            if _hand_suit(gs, i) == suit
        )
        if have < 2:
            gs = _add_cards(client, gs, (CardAdd(f"{suit}_5"), CardAdd(f"{suit}_6")))
        return gs
    if recipe.pick == "idol":
        rnd = gs.get("round") or {}
        rank = rnd.get("idol_rank")
        suit = rnd.get("idol_suit")
        if not rank or not suit:
            pytest.skip("round.idol_rank/idol_suit not set in fixture")
        have_idol = any(
            _hand_rank(gs, i) == rank and _hand_suit(gs, i) == suit
            for i in range((gs.get("hand") or {}).get("count", 0))
        )
        if not have_idol:
            gs = api(client, "add", {"key": f"{suit}_{rank}"})["result"]
        have_five = _indices_for_rank(gs, "5", 1)
        if not have_five:
            gs = api(client, "add", {"key": "S_5"})["result"]
        return gs
    return gs


def pick_indices(gs: dict, recipe: LiveRecipe) -> list[int]:
    pick = recipe.pick
    if pick == "top":
        est = estimate.estimate(gs)
        return est["estimate"]["top"][0]["indices"]
    if pick == "play_added":
        return _indices_for_cards(gs, recipe.cards)
    if pick == "pair_5s":
        return _indices_for_rank(gs, "5", 2)
    if pick == "pair_rank":
        rank = _card_key_parts(recipe.cards[0].key)[1]
        return _indices_for_rank(gs, rank, 2)
    if pick == "pair_suit":
        suit = _card_key_parts(recipe.cards[0].key)[0]
        found = [
            i
            for i in range((gs.get("hand") or {}).get("count", 0))
            if _hand_suit(gs, i) == suit
        ][:2]
        if len(found) < 2:
            raise AssertionError(f"need 2 cards suit {suit}, found {len(found)}")
        return found
    if pick == "three_k":
        return _indices_for_rank(gs, "K", 3)
    if pick == "two_pair":
        return _indices_for_rank(gs, "K", 2) + _indices_for_rank(gs, "5", 2)
    if pick == "straight_5":
        return _indices_for_cards(gs, recipe.cards)
    if pick == "flush_5d":
        return _indices_for_cards(gs, recipe.cards)
    if pick == "four_k":
        return _indices_for_cards(gs, recipe.cards[:4])
    if pick == "four_flush":
        return _indices_for_cards(gs, recipe.cards)
    if pick == "flower_pot":
        return _indices_for_cards(gs, recipe.cards)
    if pick == "seeing_double":
        return _indices_for_cards(gs, recipe.cards)
    if pick == "blackboard":
        return _indices_for_cards(gs, recipe.cards[:2])
    if pick == "baron_hold":
        return _indices_for_rank(gs, "5", 2)
    if pick == "shoot_hold":
        return _indices_for_rank(gs, "5", 2)
    if pick == "raised_fist_hold":
        return _indices_for_rank(gs, "5", 2)
    if pick == "mime_steel":
        return _indices_for_rank(gs, "5", 2)
    if pick == "high_stone":
        return _indices_for_cards(gs, recipe.cards)
    if pick == "ancient":
        suit = (gs.get("round") or {}).get("ancient_suit")
        if not suit:
            pytest.skip("round.ancient_suit not set")
        found = [
            i
            for i in range((gs.get("hand") or {}).get("count", 0))
            if _hand_suit(gs, i) == suit
        ]
        if len(found) < 2:
            raise AssertionError(f"need 2 cards suit {suit}")
        return found[:2]
    if pick == "idol":
        rnd = gs.get("round") or {}
        rank = rnd.get("idol_rank")
        suit = rnd.get("idol_suit")
        if not rank or not suit:
            pytest.skip("round.idol_rank/idol_suit not set")
        idol_idx = next(
            i
            for i in range((gs.get("hand") or {}).get("count", 0))
            if _hand_rank(gs, i) == rank and _hand_suit(gs, i) == suit
        )
        five_idx = _indices_for_rank(gs, "5", 1)[0]
        if five_idx == idol_idx:
            five_idx = _indices_for_rank(gs, "5", 2)[1]
        return [idol_idx, five_idx]
    raise ValueError(f"unknown pick strategy: {pick}")


def assert_estimate_matches_play(
    client: httpx.Client,
    gs: dict,
    indices: list[int],
    *,
    check_unmodeled: bool = True,
) -> int:
    est_full = estimate.estimate(gs)
    if check_unmodeled:
        assert not est_full["estimate"]["unmodeled_jokers"], (
            f"unexpected unmodeled: {est_full['estimate']['unmodeled_jokers']}"
        )
    est_line = estimate.score_hand_indices(gs, indices)
    delta = _play_delta(client, gs, indices)
    expected = est_line["score"]
    if isinstance(expected, float):
        expected = int(round(expected))
    assert abs(delta - expected) <= 1, (
        f"estimate={expected} actual={delta} hand={est_line['hand_type']} "
        f"chips={est_line['chips']} mult={est_line['mult']} idx={indices}"
    )
    return delta


def run_live_recipe(client: httpx.Client, recipe: LiveRecipe) -> None:
    gs = setup_recipe(client, recipe)
    indices = pick_indices(gs, recipe)
    assert_estimate_matches_play(
        client, gs, indices, check_unmodeled=recipe.check_unmodeled
    )


def _joker_count(gs: dict) -> int:
    return (gs.get("jokers") or {}).get("count", 0)


def _hand_count(gs: dict) -> int:
    return (gs.get("hand") or {}).get("count", 0)


def _rearrange_jokers(client: httpx.Client, order: tuple[int, ...]) -> dict:
    return api(client, "rearrange", {"jokers": list(order)})["result"]


def _rearrange_hand_for_play_order(
    client: httpx.Client,
    gs: dict,
    play_order_cards: tuple[CardAdd, ...],
) -> tuple[dict, list[int]]:
    """Return indices matching ``play_order_cards`` (arg order = score order)."""
    want_indices = _indices_for_cards(gs, play_order_cards)
    return gs, want_indices


def _find_card_index(
    gs: dict,
    *,
    rank: str | None = None,
    enhancement: str | None = None,
    used: set[int] | None = None,
) -> int:
    used = used or set()
    for i in range(_hand_count(gs)):
        if i in used:
            continue
        if rank is not None and _hand_rank(gs, i) != rank:
            continue
        cards = (gs.get("hand") or {}).get("cards") or []
        mod = (cards[i].get("modifier") or {}) if i < len(cards) else {}
        if enhancement is not None and mod.get("enhancement") != enhancement:
            continue
        return i
    raise AssertionError(f"card not found rank={rank} enh={enhancement}")


def _add_jokers(client: httpx.Client, jokers: tuple[JokerAdd, ...]) -> dict:
    gs = None
    for joker in jokers:
        gs = api(client, "add", joker.to_add_params())["result"]
    assert gs is not None
    area = gs.get("jokers") or {}
    assert area.get("count", 0) <= area.get("limit", 0), (
        f"joker capacity exceeded: count={area.get('count')} limit={area.get('limit')}"
    )
    return gs


def _joker_order_for_specs(
    added: tuple[JokerAdd, ...], desired: tuple[JokerAdd, ...]
) -> tuple[int, ...]:
    """Map key/edition specs to stable indices in the add sequence."""
    if len(added) != len(desired):
        raise AssertionError(
            f"joker order length mismatch: added={len(added)} desired={len(desired)}"
        )
    used: set[int] = set()
    order: list[int] = []
    for want in desired:
        for i, have in enumerate(added):
            if i not in used and have == want:
                used.add(i)
                order.append(i)
                break
        else:
            raise AssertionError(f"joker order spec not added: {want}")
    return tuple(order)


def setup_scenario(
    client: httpx.Client,
    recipe: ScenarioRecipe,
    line: ScenarioLine,
) -> dict:
    gs = load_fixture(client, "gamestate", "state-SELECTING_HAND")
    added_jokers: tuple[JokerAdd, ...] = ()
    if line.jokers is not None:
        added_jokers = line.jokers
        gs = _add_jokers(client, added_jokers)
    elif recipe.jokers:
        added_jokers = recipe.jokers
        gs = _add_jokers(client, added_jokers)
    else:
        joker_keys = (
            line.joker_keys if line.joker_keys is not None else recipe.joker_keys
        )
        for key in joker_keys:
            gs = api(client, "add", {"key": key})["result"]
    cards = line.cards if line.cards is not None else recipe.cards
    gs = _add_cards(client, gs, cards)
    merged_set = {**recipe.set_state, **line.set_state}
    if merged_set:
        gs = api(client, "set", merged_set)["result"]
    debuff = line.debuff if line.debuff else recipe.debuff
    if debuff:
        gs = _debuff_cards(client, gs, debuff)
    if line.joker_order is not None:
        gs = _rearrange_jokers(client, line.joker_order)
    if line.joker_order_specs is not None:
        if line.joker_order is not None:
            raise ValueError("use joker_order or joker_order_specs, not both")
        gs = _rearrange_jokers(
            client,
            _joker_order_for_specs(added_jokers, line.joker_order_specs),
        )
    if line.hand_order:
        raise ValueError(
            "hand_order is no longer supported because rearrange hand was removed"
        )
    return gs


def resolve_line_play_indices(
    gs: dict,
    recipe: ScenarioRecipe,
    line: ScenarioLine,
) -> list[int]:
    if line.play_order_cards:
        return _indices_for_cards(gs, line.play_order_cards)
    pick = line.pick
    cards = line.cards if line.cards is not None else recipe.cards
    if pick == "estimate_top" or pick == "top":
        return estimate.estimate(gs)["estimate"]["top"][0]["indices"]
    if pick == "pair_5s":
        return _indices_for_rank(gs, "5", 2)
    if pick == "pair_j":
        return _indices_for_rank(gs, "J", 2)
    if pick == "straight_5":
        return _indices_for_cards(gs, cards)
    if pick == "play_added":
        return _indices_for_cards(gs, cards)
    if pick == "play_all":
        return list(range(_hand_count(gs)))
    raise ValueError(
        f"unknown line pick: {pick!r} for {recipe.scenario_id}/{line.line_id}"
    )


def run_scenario(client: httpx.Client, recipe: ScenarioRecipe) -> None:
    optimal_delta: int | None = None
    for line in recipe.lines:
        gs = setup_scenario(client, recipe, line)
        if line.play_order_cards:
            gs, indices = _rearrange_hand_for_play_order(
                client, gs, line.play_order_cards
            )
        else:
            indices = resolve_line_play_indices(gs, recipe, line)
        delta = assert_estimate_matches_play(
            client, gs, indices, check_unmodeled=recipe.check_unmodeled
        )
        if line.expect_lower_than_optimal:
            assert optimal_delta is not None, (
                f"missing optimal line before {line.line_id}"
            )
            assert delta < optimal_delta, (
                f"{recipe.scenario_id}/{line.line_id}: expected lower than optimal "
                f"({delta} >= {optimal_delta})"
            )
        else:
            optimal_delta = delta

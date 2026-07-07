"""Unit tests for Play Helper JSON layer (no Balatro required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PLAY_ROOT = Path(__file__).resolve().parents[2] / "tools" / "play"
import sys  # noqa: E402

sys.path.insert(0, str(PLAY_ROOT))

import act  # noqa: E402  # type: ignore[unresolved-import]
from actions import (  # noqa: E402  # type: ignore[unresolved-import]
    build_actions,
    buy_blocked_by_slots,
    consumable_target_hint,
)
from commands import (  # noqa: E402  # type: ignore[unresolved-import]
    build_params,
    format_friendly_action,
    normalize_sort_mode,
)
from envelope import (  # noqa: E402  # type: ignore[unresolved-import]
    build_play_envelope,
)
from layers import (  # noqa: E402  # type: ignore[unresolved-import]
    effective_state,
    extract_query,
    filter_layer1,
    is_gamestate_stable,
    normalize_play_state,
    poll_until_stable,
)
from start_options import (  # noqa: E402  # type: ignore[unresolved-import]
    build_decks,
    build_stakes,
)
from view import (  # noqa: E402  # type: ignore[unresolved-import]
    _blind_line,
    _blinds_block,
    _consumable_line,
    _header,
    _joker_line,
    _round_line,
    card_label,
    print_summary,
)


@pytest.fixture
def selecting_hand_state() -> dict:
    return {
        "state": "SELECTING_HAND",
        "money": 10,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "won": False,
        "seed": "ABC123",
        "round": {"hands_left": 4, "discards_left": 3, "chips": 100, "reroll_cost": 5},
        "blinds": {
            "small": {"status": "DEFEATED", "name": "Small Blind"},
            "big": {"status": "CURRENT", "name": "Big Blind", "type": "BIG"},
            "boss": {"status": "UPCOMING", "name": "The Hook", "type": "BOSS"},
        },
        "hands": {"Pair": {"level": 1, "chips": 10, "mult": 2}},
        "used_vouchers": {"v_overstock": "Shop has more cards"},
        "jokers": {
            "count": 1,
            "limit": 5,
            "cards": [{"label": "Joker", "key": "j_joker"}],
        },
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52, "cards": ["hidden"]},
        "hand": {"count": 8, "limit": 8, "cards": [{"label": "Ace of Spades"}]},
        "shop": {"count": 0, "limit": 0, "cards": []},
    }


def test_filter_layer1_selecting_hand_strips_l3(selecting_hand_state: dict) -> None:
    filtered = filter_layer1(selecting_hand_state)
    assert filtered["state"] == "SELECTING_HAND"
    assert "hand" in filtered
    assert "shop" not in filtered
    assert "hands" not in filtered
    assert "seed" not in filtered
    assert filtered["cards"] == {"count": 44, "limit": 52}
    assert list(filtered["blinds"]) == ["big"]


def test_query_deck_extracts_full_cards(selecting_hand_state: dict) -> None:
    data = extract_query(selecting_hand_state, "deck")
    assert data["count"] == 44
    assert data["cards"] == ["hidden"]


def test_menu_envelope_has_decks_stakes() -> None:
    raw = {"state": "MENU", "money": 0, "round_num": 0, "ante_num": 0}
    envelope = build_play_envelope(raw, build_actions(raw))
    assert envelope["format"] == "balatrobot-play-v1"
    assert envelope["gamestate"] == {"state": "MENU"}
    assert "queries" not in envelope
    assert len(envelope["decks"]) == len(build_decks())
    assert len(envelope["stakes"]) == len(build_stakes())
    assert envelope["actions"][0]["command"] == "start"


def test_game_over_envelope(selecting_hand_state: dict) -> None:
    raw = {
        "state": "GAME_OVER",
        "won": False,
        "seed": "3ZF4YT86",
        "ante_num": 5,
        "round_num": 11,
        "run_summary": {
            "best_hand": 11446,
            "result": "Lost to Big Blind",
        },
        "money": 32,
        "jokers": selecting_hand_state["jokers"],
    }
    envelope = build_play_envelope(raw, build_actions(raw))
    gs = envelope["gamestate"]
    assert gs["seed"] == "3ZF4YT86"
    assert gs["run_summary"]["best_hand"] == 11446
    assert "money" not in gs
    assert "queries" not in envelope
    commands = {a["command"] for a in envelope["actions"]}
    assert commands == {"menu"}


def test_build_actions_selecting_hand(selecting_hand_state: dict) -> None:
    actions = build_actions(selecting_hand_state)
    commands = {a["command"] for a in actions}
    assert {"play", "discard", "sort"}.issubset(commands)


def test_start_options_descriptions() -> None:
    decks = build_decks()
    assert any(d["id"] == "RED" and d["description"] for d in decks)
    stakes = build_stakes()
    assert any(s["id"] == "WHITE" and s["description"] for s in stakes)


def test_build_params_sell() -> None:
    assert build_params("sell", ["joker", "0"]) == {"joker": 0}
    assert build_params("sell", ["consumable", "2"]) == {"consumable": 2}


def test_build_params_use() -> None:
    assert build_params("use", ["0"]) == {"consumable": 0}
    assert build_params("use", ["0", "1", "2"]) == {"consumable": 0, "cards": [1, 2]}


def test_build_params_sort() -> None:
    assert build_params("sort", []) == {"mode": "rank"}
    assert build_params("sort", ["suit-desc"]) == {"mode": "suit-desc"}


def test_normalize_sort_mode_aliases() -> None:
    assert normalize_sort_mode("r") == "rank"
    assert normalize_sort_mode("value-desc") == "rank-desc"
    assert normalize_sort_mode("sa") == "suit-asc"


def test_build_params_sell_errors() -> None:
    with pytest.raises(ValueError, match="sell needs"):
        build_params("sell", ["joker"])
    with pytest.raises(ValueError, match="sell kind must be"):
        build_params("sell", ["card", "0"])


def test_build_params_use_errors() -> None:
    with pytest.raises(ValueError, match="use needs"):
        build_params("use", [])


def test_build_params_sort_errors() -> None:
    with pytest.raises(ValueError, match="sort mode must be"):
        normalize_sort_mode("invalid")


def test_build_actions_shop(selecting_hand_state: dict) -> None:
    shop_state = {
        **selecting_hand_state,
        "state": "SHOP",
        "shop": {
            "count": 1,
            "limit": 2,
            "cards": [{"label": "Joker", "key": "j_joker"}],
        },
        "vouchers": {"count": 0, "limit": 1, "cards": []},
        "packs": {"count": 0, "limit": 2, "cards": []},
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [{"label": "The Hermit", "key": "c_hermit"}],
        },
        "jokers": {
            "count": 2,
            "limit": 5,
            "cards": [
                {"label": "Joker", "key": "j_joker"},
                {"label": "Jolly Joker", "key": "j_jolly"},
            ],
        },
    }
    commands = {a["command"] for a in build_actions(shop_state)}
    assert {"buy", "reroll", "next_round", "sell", "use", "rearrange"}.issubset(
        commands
    )


def test_build_actions_pack_open_rearrange_random_joker(
    selecting_hand_state: dict,
) -> None:
    pack_state = {
        **selecting_hand_state,
        "state": "SMODS_BOOSTER_OPENED",
        "pack": {
            "count": 2,
            "limit": 2,
            "cards": [
                {
                    "label": "Ankh",
                    "key": "c_ankh",
                    "value": {"effect": "Create a copy of a random Joker"},
                },
                {
                    "label": "Ectoplasm",
                    "key": "c_ectoplasm",
                    "value": {"effect": "..."},
                },
            ],
        },
        "jokers": {
            "count": 2,
            "limit": 5,
            "cards": [
                {"label": "Joker", "key": "j_joker"},
                {"label": "Jolly Joker", "key": "j_jolly"},
            ],
        },
    }
    commands = {a["command"] for a in build_actions(pack_state)}
    assert "rearrange" in commands
    pack_actions = [a for a in build_actions(pack_state) if a["command"] == "pack"]
    assert any("random joker" in a["description"].lower() for a in pack_actions)


def test_build_actions_blind_select(selecting_hand_state: dict) -> None:
    blind_state = {
        **selecting_hand_state,
        "state": "BLIND_SELECT",
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "The Hermit",
                    "key": "c_hermit",
                    "value": {"target_min": 1, "target_max": 1},
                }
            ],
        },
    }
    commands = {a["command"] for a in build_actions(blind_state)}
    assert {"select", "sell", "use"}.issubset(commands)


def test_build_actions_use_hidden_without_hand(selecting_hand_state: dict) -> None:
    """Hand-target consumables omit use when hand is missing or too small."""
    base = {
        **selecting_hand_state,
        "hand": {"count": 0, "limit": 8, "cards": []},
    }
    blind_magician = {
        **base,
        "state": "BLIND_SELECT",
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "The Magician",
                    "key": "c_magician",
                    "value": {"target_min": 1, "target_max": 2},
                }
            ],
        },
    }
    assert "use" not in {a["command"] for a in build_actions(blind_magician)}

    blind_fool = {
        **base,
        "state": "BLIND_SELECT",
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [
                {"label": "The Fool", "key": "c_fool", "value": {"effect": "..."}}
            ],
        },
    }
    assert "use" in {a["command"] for a in build_actions(blind_fool)}

    blind_ankh = {
        **base,
        "state": "BLIND_SELECT",
        "jokers": {
            "count": 1,
            "limit": 5,
            "cards": [{"label": "Joker", "key": "j_joker"}],
        },
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "Ankh",
                    "key": "c_ankh",
                    "value": {"random_joker_effect": True},
                }
            ],
        },
    }
    assert "use" in {a["command"] for a in build_actions(blind_ankh)}

    death_one_card = {
        **selecting_hand_state,
        "state": "SELECTING_HAND",
        "hand": {
            "count": 1,
            "limit": 8,
            "cards": [{"label": "7♣", "value": {"rank": "7", "suit": "C"}}],
        },
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [{"label": "Death", "key": "c_death", "value": {"effect": "..."}}],
        },
    }
    assert "use" not in {a["command"] for a in build_actions(death_one_card)}

    death_two_cards = {
        **death_one_card,
        "hand": {
            "count": 2,
            "limit": 8,
            "cards": [
                {"label": "7♣", "value": {"rank": "7", "suit": "C"}},
                {"label": "K♠", "value": {"rank": "K", "suit": "S"}},
            ],
        },
    }
    assert "use" in {a["command"] for a in build_actions(death_two_cards)}


def test_build_actions_round_eval(selecting_hand_state: dict) -> None:
    round_eval_state = {
        **selecting_hand_state,
        "state": "ROUND_EVAL",
        "hand": {"count": 0, "limit": 8, "cards": []},
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "The Hermit",
                    "key": "c_hermit",
                    "value": {"target_min": 1, "target_max": 1},
                }
            ],
        },
    }
    commands = {a["command"] for a in build_actions(round_eval_state)}
    assert {"cash_out", "sell"}.issubset(commands)
    assert "use" not in commands


def test_build_actions_round_eval_victory_overlay(selecting_hand_state: dict) -> None:
    round_eval_state = {
        **selecting_hand_state,
        "state": "ROUND_EVAL",
        "won": True,
        "victory_overlay": True,
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [{"label": "The Hermit", "key": "c_hermit"}],
        },
    }
    actions = build_actions(round_eval_state)
    commands = [a["command"] for a in actions]
    assert commands == ["endless", "menu"]


def test_build_actions_pack_open(selecting_hand_state: dict) -> None:
    pack_state = {
        **selecting_hand_state,
        "state": "SMODS_BOOSTER_OPENED",
        "pack": {
            "count": 3,
            "limit": 3,
            "cards": [{"label": "The Magician", "key": "c_magician"}],
        },
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "The Magician",
                    "key": "c_magician",
                    "value": {"effect": "Select 1-2 cards in hand"},
                }
            ],
        },
    }
    commands = {a["command"] for a in build_actions(pack_state)}
    assert {"pack", "sell", "use"}.issubset(commands)
    pick = next(
        a
        for a in build_actions(pack_state)
        if a["command"] == "pack"
        and not (a.get("example") or {}).get("params", {}).get("skip")
    )
    assert pick["example"]["params"] == {"card": 0}


def test_effective_state_blind_select_with_open_pack() -> None:
    raw = {
        "state": "BLIND_SELECT",
        "pack": {
            "count": 2,
            "limit": 2,
            "cards": [{"label": "Joker", "key": "j_joker"}],
        },
    }
    assert effective_state(raw) == "SMODS_BOOSTER_OPENED"


def test_effective_state_vanilla_buffoon_pack() -> None:
    raw = {"state": "BUFFOON_PACK", "pack": {"count": 0, "limit": 0, "cards": []}}
    assert effective_state(raw) == "SMODS_BOOSTER_OPENED"


def test_build_actions_blind_select_with_open_pack(selecting_hand_state: dict) -> None:
    """Tag-skip can leave pack data while engine state was BLIND_SELECT."""
    raw = {
        **selecting_hand_state,
        "state": "BLIND_SELECT",
        "blinds": {
            "small": {"status": "SKIPPED", "name": "Small Blind", "type": "SMALL"},
            "big": {
                "status": "SELECT",
                "name": "Big Blind",
                "type": "BIG",
                "score": 450,
            },
            "boss": {
                "status": "UPCOMING",
                "name": "The Hook",
                "type": "BOSS",
                "score": 600,
            },
        },
        "pack": {
            "count": 2,
            "limit": 2,
            "cards": [{"label": "Joker", "key": "j_joker", "value": {"effect": "x"}}],
        },
    }
    normalized = normalize_play_state(raw)
    commands = {a["command"] for a in build_actions(normalized)}
    assert "pack" in commands
    assert "select" not in commands
    assert "skip" not in commands


def test_print_summary_tag_skip_pack_open(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "BLIND_SELECT",
        "money": 4,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "blinds": {
            "small": {"status": "SKIPPED", "name": "Small Blind", "type": "SMALL"},
            "big": {
                "status": "SELECT",
                "name": "Big Blind",
                "type": "BIG",
                "score": 450,
            },
            "boss": {
                "status": "UPCOMING",
                "name": "The Hook",
                "type": "BOSS",
                "score": 600,
            },
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 52, "limit": 52},
        "pack": {
            "count": 2,
            "limit": 2,
            "cards": [
                {"label": "Joker", "key": "j_joker", "value": {"effect": "+4 Mult"}}
            ],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "state=SMODS_BOOSTER_OPENED" in out
    assert "pack:" in out
    assert "actions: pack" in out
    assert "select" not in out.split("actions:")[-1]


def test_is_gamestate_stable_requires_held_tags_ready() -> None:
    assert not is_gamestate_stable({"state": "BLIND_SELECT", "held_tags_ready": False})
    assert is_gamestate_stable({"state": "BLIND_SELECT", "held_tags_ready": True})
    assert is_gamestate_stable({"state": "BLIND_SELECT"})
    assert not is_gamestate_stable({"state": "HAND_PLAYED", "held_tags_ready": True})
    assert is_gamestate_stable({"state": "MENU", "held_tags_ready": False})
    assert is_gamestate_stable({"state": "GAME_OVER", "held_tags_ready": False})


def test_is_gamestate_stable_requires_pack_ready() -> None:
    base = {"state": "SMODS_BOOSTER_OPENED", "held_tags_ready": True}
    assert not is_gamestate_stable({**base, "pack_ready": False})
    assert is_gamestate_stable({**base, "pack_ready": True})
    assert not is_gamestate_stable(
        {**base, "pack_ready": True, "pack_hand_ready": False}
    )
    assert is_gamestate_stable({**base, "pack_ready": True, "pack_hand_ready": True})
    assert is_gamestate_stable({**base, "pack_ready": True, "pack_hand_ready": None})


def test_consumable_target_hint_death() -> None:
    card = {"key": "c_death", "value": {"effect": "copy left card into right"}}
    hint = consumable_target_hint(card)
    assert hint is not None
    assert "arg order irrelevant" in hint
    assert "lower-index" in hint


def test_build_actions_pack_death_includes_targets(selecting_hand_state: dict) -> None:
    pack_state = {
        **selecting_hand_state,
        "state": "SMODS_BOOSTER_OPENED",
        "pack": {
            "count": 1,
            "limit": 1,
            "choices_remaining": 1,
            "cards": [
                {
                    "label": "Death",
                    "key": "c_death",
                    "value": {"effect": "copy left card into right"},
                }
            ],
        },
        "hand": {
            "count": 3,
            "limit": 8,
            "cards": [
                {"label": "2♠", "value": {"rank": "2", "suit": "S"}},
                {"label": "3♠", "value": {"rank": "3", "suit": "S"}},
                {"label": "4♠", "value": {"rank": "4", "suit": "S"}},
            ],
        },
    }
    pack_actions = [a for a in build_actions(pack_state) if a["command"] == "pack"]
    assert pack_actions
    example = pack_actions[0]["example"]["params"]
    assert example["card"] == 0
    assert example["targets"] == [0, 1]


def test_build_actions_pack_never_offers_sort(
    selecting_hand_state: dict,
) -> None:
    """sort is SELECTING_HAND-only (matches Balatro UI); never in pack actions,
    even when an Arcana/Spectral pack has hand cards visible for targeting."""
    pack_state = {
        **selecting_hand_state,
        "state": "SMODS_BOOSTER_OPENED",
        "pack": {
            "count": 1,
            "limit": 1,
            "cards": [{"label": "The Magician", "key": "c_magician"}],
        },
    }
    commands = {a["command"] for a in build_actions(pack_state)}
    assert "sort" not in commands


def test_poll_until_stable_waits_for_held_tags() -> None:
    calls = iter(
        [
            {"state": "BLIND_SELECT", "held_tags_ready": False},
            {"state": "BLIND_SELECT", "held_tags_ready": True},
        ]
    )
    result = poll_until_stable(lambda: next(calls), timeout=1.0, interval=0)
    assert result["held_tags_ready"] is True


def _held_tags_fixture_state(state: str) -> dict:
    """Minimal gamestate dict with held_tags for filter_layer1 / print_summary tests."""
    held = [{"name": "Foil Tag", "effect": "Next base edition shop Joker is free"}]
    base: dict = {
        "state": state,
        "money": 4,
        "round_num": 0,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "held_tags": held,
        "held_tags_ready": True,
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 52, "limit": 52},
    }
    if state in ("BLIND_SELECT", "SELECTING_HAND", "ROUND_EVAL"):
        base["blinds"] = {
            "small": {"status": "SKIPPED", "name": "Small Blind", "type": "SMALL"},
            "big": {
                "status": "SELECT",
                "name": "Big Blind",
                "type": "BIG",
                "score": 450,
            },
            "boss": {
                "status": "UPCOMING",
                "name": "The Hook",
                "type": "BOSS",
                "score": 600,
            },
        }
    if state == "SELECTING_HAND":
        base["round"] = {"hands_left": 4, "discards_left": 3, "chips": 0}
        base["hand"] = {"count": 8, "limit": 8, "cards": [{"label": "Ace of Spades"}]}
    if state == "ROUND_EVAL":
        base["round"] = {"hands_left": 3, "discards_left": 3, "chips": 500}
        base["won"] = False
    if state == "SHOP":
        base["round"] = {"reroll_cost": 5}
        base["shop"] = {"count": 2, "limit": 2, "cards": []}
        base["vouchers"] = {"count": 1, "limit": 1, "cards": []}
        base["packs"] = {"count": 2, "limit": 2, "cards": []}
    if state == "SMODS_BOOSTER_OPENED":
        base["round"] = {"hands_left": 4, "discards_left": 3, "chips": 0}
        base["pack"] = {"count": 3, "limit": 3, "cards": [{"label": "The Fool"}]}
        base["hand"] = {"count": 8, "limit": 8, "cards": [{"label": "Ace of Spades"}]}
    return base


HELD_TAGS_LAYER1_STATES = (
    "BLIND_SELECT",
    "SELECTING_HAND",
    "ROUND_EVAL",
    "SHOP",
    "SMODS_BOOSTER_OPENED",
)


@pytest.mark.parametrize("state", HELD_TAGS_LAYER1_STATES)
def test_filter_layer1_includes_held_tags_by_state(state: str) -> None:
    raw = _held_tags_fixture_state(state)
    filtered = filter_layer1(raw)
    assert filtered.get("held_tags") == raw["held_tags"]


@pytest.mark.parametrize("state", ("MENU", "GAME_OVER"))
def test_filter_layer1_excludes_held_tags_outside_layer1(state: str) -> None:
    raw = _held_tags_fixture_state("BLIND_SELECT")
    raw["state"] = state
    if state == "GAME_OVER":
        raw["won"] = False
        raw["run_summary"] = {"result": "Defeat"}
    filtered = filter_layer1(raw)
    assert "held_tags" not in filtered


@pytest.mark.parametrize("state", HELD_TAGS_LAYER1_STATES)
def test_print_summary_held_tags_line_by_state(
    state: str, capsys: pytest.CaptureFixture[str]
) -> None:
    print_summary(_envelope(_held_tags_fixture_state(state)))
    out = capsys.readouterr().out
    assert "held tags (pending): Foil Tag" in out


def test_filter_layer1_includes_held_tags() -> None:
    raw = {
        "state": "BLIND_SELECT",
        "money": 4,
        "held_tags": [{"name": "Foil Tag", "effect": "..."}],
        "held_tags_ready": True,
        "blinds": {"small": {"status": "SKIPPED"}},
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 52, "limit": 52},
    }
    filtered = filter_layer1(raw)
    assert filtered.get("held_tags") == [{"name": "Foil Tag", "effect": "..."}]


# --- view.card_label ---------------------------------------------------------


def test_card_label_visible() -> None:
    assert (
        card_label({"label": "K of Spades", "value": {"rank": "K", "suit": "S"}})
        == "K♠"
    )
    assert card_label({"value": {"rank": "T", "suit": "H"}}) == "T♥"
    assert card_label({"value": {"rank": "A", "suit": "D"}}) == "A♦"
    assert card_label({"value": {"rank": "2", "suit": "C"}}) == "2♣"


def test_card_label_hidden() -> None:
    assert card_label({"label": "?", "state": {"hidden": True}}) == "??"
    assert (
        card_label(
            {
                "label": "?",
                "value": {"rank": "K", "suit": "S"},
                "state": {"hidden": True},
            }
        )
        == "??"
    )


def test_card_label_fallback() -> None:
    assert card_label({"label": "Joker"}) == "Joker"
    assert card_label({}) == "?"


def test_card_label_enhancement_tag() -> None:
    assert (
        card_label(
            {"value": {"rank": "4", "suit": "D"}, "modifier": {"enhancement": "MULT"}}
        )
        == "4♦[e:Mult]"
    )


def test_card_label_edition_and_seal_tags() -> None:
    assert (
        card_label(
            {
                "value": {"rank": "K", "suit": "H"},
                "modifier": {"edition": "FOIL", "seal": "RED"},
            }
        )
        == "K♥[d:Foil,s:Red]"
    )


def test_card_label_debuff_wraps() -> None:
    assert (
        card_label({"value": {"rank": "7", "suit": "C"}, "state": {"debuff": True}})
        == "(7♣)"
    )


def test_card_label_hidden_still_returns_qq() -> None:
    assert (
        card_label({"state": {"hidden": True}, "modifier": {"enhancement": "MULT"}})
        == "??"
    )


def test_joker_line_perishable_rental() -> None:
    line = _joker_line(
        1,
        {
            "label": "Jolly Joker",
            "value": {"effect": "+8 Mult if played hand contains a Pair"},
            "cost": {"sell": 99},
            "modifier": {
                "edition": "HOLO",
                "perishable": 3,
                "rental": True,
                "eternal": True,
            },
        },
    )
    assert "(+$99 sell)" not in line
    assert "(perishable 3r)" in line
    assert "(rental -$1/round)" in line
    assert "(+10 mult)" in line
    assert "(eternal)" in line
    assert "Jolly Joker" in line
    assert " — +8 Mult if played hand contains a Pair" in line
    _, desc = line.split(" — ", 1)
    assert "+10 Mult" not in desc


def test_joker_line_effect_excludes_edition_in_description() -> None:
    """Effect after em dash is main ability only; edition stays in prefix tags."""
    line = _joker_line(
        0,
        {
            "label": "Jolly Joker",
            "value": {"effect": "+8 Mult if played hand contains a Pair"},
            "modifier": {"edition": "HOLO"},
        },
    )
    assert "(+10 mult)" in line.split(" — ", 1)[0]
    desc = line.split(" — ", 1)[1]
    assert "+8 Mult" in desc
    assert "+10 Mult" not in desc


def test_joker_line_sell_price_before_stickers() -> None:
    line = _joker_line(
        0,
        {
            "label": "Jolly Joker",
            "value": {"effect": "+8 Mult"},
            "cost": {"sell": 3, "buy": 5},
            "modifier": {"edition": "HOLO", "rental": True},
        },
    )
    assert line.startswith("[0] (+$3 sell) (rental -$1/round) (+10 mult) Jolly Joker")


def test_joker_line_sell_price_omitted_when_zero() -> None:
    line = _joker_line(0, {"label": "Joker", "cost": {"sell": 0}})
    assert "(+$" not in line
    assert "sell)" not in line


def test_consumable_line_includes_sell_price() -> None:
    line = _consumable_line(
        0,
        {
            "label": "The Hermit",
            "cost": {"sell": 1},
            "value": {"effect": "Doubles money"},
        },
    )
    assert "(+$1 sell)" in line
    assert "The Hermit" in line


# --- view.print_summary (one per state) -------------------------------------


def _envelope(raw: dict) -> dict:
    normalized = normalize_play_state(raw)
    return build_play_envelope(normalized, build_actions(normalized))


def test_print_summary_menu(capsys: pytest.CaptureFixture[str]) -> None:
    print_summary(
        _envelope({"state": "MENU", "money": 0, "round_num": 0, "ante_num": 0})
    )
    out = capsys.readouterr().out
    assert "state=MENU" in out
    assert "→ start DECK STAKE [SEED]" in out
    assert "decks:" in out
    assert "stakes:" in out
    assert "actions:" in out
    assert "→ start RED WHITE" not in out.split("actions:")[0]


def test_format_friendly_action_buy() -> None:
    action = {
        "command": "buy",
        "example": {"command": "buy", "params": {"card": 0}},
    }
    assert format_friendly_action(action) == "buy card 0"


def test_format_friendly_action_play() -> None:
    action = {
        "command": "play",
        "example": {"command": "play", "params": {"cards": [0, 1, 2, 3, 4]}},
    }
    assert format_friendly_action(action) == "play 0 1 2 3 4"


def test_blind_line_no_skip_tag_in_hand() -> None:
    blind = {
        "name": "Small Blind",
        "status": "CURRENT",
        "score": 300,
        "tag_name": "Investment Tag",
        "tag_effect": "gain $25",
    }
    line = _blind_line(blind, show_skip_tag=False)
    assert "skip reward" not in line
    assert "blind=Small Blind" in line


def test_blinds_block_defeated_no_skip_tag() -> None:
    raw = {
        "state": "BLIND_SELECT",
        "blinds": {
            "small": {
                "status": "DEFEATED",
                "name": "Small Blind",
                "score": 300,
                "tag_name": "Investment Tag",
                "tag_effect": "gain $25",
            },
            "big": {"status": "CURRENT", "name": "Big Blind", "score": 450},
            "boss": {"status": "UPCOMING", "name": "The Hook", "score": 600},
        },
    }
    out = _blinds_block(raw)
    assert "small:" in out
    assert "skip reward" not in out.split("big:")[0]
    assert "skip reward" not in out.split("boss:")[0]


def test_round_line_need() -> None:
    state = {"round": {"hands_left": 1, "discards_left": 0, "chips": 406}}
    assert "need=194" in _round_line(state, target=600)
    state2 = {"round": {"hands_left": 0, "discards_left": 0, "chips": 650}}
    assert "beaten" in _round_line(state2, target=600)


def test_shop_affordability(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "SHOP",
        "money": 3,
        "bankrupt_at": 0,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "cards": {"count": 44, "limit": 52},
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "shop": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "Cheap",
                    "key": "j_joker",
                    "set": "JOKER",
                    "cost": {"buy": 2},
                    "value": {"effect": "cheap"},
                },
                {
                    "label": "Pricey",
                    "key": "j_jolly",
                    "set": "JOKER",
                    "cost": {"buy": 6},
                    "value": {"effect": "pricey"},
                },
            ],
        },
        "vouchers": {"count": 0, "limit": 1, "cards": []},
        "packs": {"count": 0, "limit": 2, "cards": []},
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "shop[0]" in out and "[ok]" in out
    assert "shop[1]" in out and "[need $3]" in out
    assert "reroll=$5 [need $2]" in out


def test_shop_slots_full_joker(capsys: pytest.CaptureFixture[str]) -> None:
    jokers = [
        {"label": f"J{i}", "key": f"j_j{i}", "value": {"effect": ""}} for i in range(5)
    ]
    raw = {
        "state": "SHOP",
        "money": 20,
        "bankrupt_at": 0,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "jokers": {"count": 5, "limit": 5, "cards": jokers},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "shop": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "New Joker",
                    "key": "j_greedy",
                    "set": "JOKER",
                    "cost": {"buy": 4},
                    "value": {"effect": "full slots"},
                },
            ],
        },
        "vouchers": {"count": 0, "limit": 1, "cards": []},
        "packs": {"count": 0, "limit": 2, "cards": []},
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "jokers (5/5)" in out
    assert "shop[0]" in out and "[slots full]" in out
    assert "actions: buy" in out and "reroll" in out and "next_round" in out


def test_header_buy_power() -> None:
    state = {
        "state": "SHOP",
        "money": 8,
        "bankrupt_at": -5,
        "ante_num": 2,
        "round_num": 5,
        "deck": "RED",
        "stake": "WHITE",
    }
    header = _header(state)
    assert "buy_power=13" in header
    assert _header({**state, "bankrupt_at": 0, "state": "SHOP"}) == (
        "state=SHOP ante=2 round=5 money=8 deck=RED stake=WHITE"
    )


def test_pack_target_hint_range() -> None:
    card = {
        "key": "c_magician",
        "value": {"target_min": 1, "target_max": 2, "effect": ""},
    }
    assert consumable_target_hint(card) == "needs 1-2 targets"
    assert (
        consumable_target_hint({"value": {"target_min": 1, "target_max": 1}})
        == "needs 1 target"
    )
    assert (
        consumable_target_hint(
            {"key": "c_ankh", "value": {"random_joker_effect": True}}
        )
        == "random joker — pack targets ignored"
    )
    assert (
        consumable_target_hint(
            {"key": "c_ectoplasm", "value": {"random_joker_effect": True}}
        )
        == "random joker Negative — pack targets ignored"
    )


def test_print_summary_transient(capsys: pytest.CaptureFixture[str]) -> None:
    print_summary(_envelope({"state": "HAND_PLAYED"}))
    out = capsys.readouterr().out
    assert "transient" in out
    assert "glance again" in out


def test_print_summary_blind_select(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "BLIND_SELECT",
        "money": 8,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 0},
        "blinds": {
            "small": {
                "status": "UPCOMING",
                "name": "Small Blind",
                "type": "SMALL",
                "score": 300,
                "tag_name": "Foil Tag",
                "tag_effect": "free foil joker",
            },
            "big": {
                "status": "CURRENT",
                "name": "Big Blind",
                "type": "BIG",
                "score": 450,
            },
            "boss": {"status": "UPCOMING", "name": "The Hook", "type": "BOSS"},
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 52, "limit": 52},
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "state=BLIND_SELECT" in out
    assert "big: Big Blind target=450 (current, select)" in out
    assert "boss: The Hook" in out
    assert "skip reward: Foil Tag" in out
    assert "actions:" in out


def test_print_summary_blind_select_select_status_shows_blind_and_skip(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Live BLIND_SELECT uses status 'SELECT' (not CURRENT) for the selectable
    blind — glance must still show it and offer skip on Small/Big."""
    raw = {
        "state": "BLIND_SELECT",
        "money": 4,
        "round_num": 2,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "blinds": {
            "small": {
                "status": "SELECT",
                "name": "Small Blind",
                "type": "SMALL",
                "score": 300,
            },
            "big": {
                "status": "UPCOMING",
                "name": "Big Blind",
                "type": "BIG",
                "score": 450,
            },
            "boss": {
                "status": "UPCOMING",
                "name": "The Flint",
                "type": "BOSS",
                "score": 1600,
                "effect": "base halved",
            },
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 52, "limit": 52},
    }
    envelope = _envelope(raw)
    print_summary(envelope)
    out = capsys.readouterr().out
    assert "small: Small Blind target=300 (current, select)" in out
    assert "boss: The Flint" in out
    commands = {a["command"] for a in envelope["actions"]}
    assert "skip" in commands


def test_print_summary_selecting_hand(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "SELECTING_HAND",
        "money": 4,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"hands_left": 3, "discards_left": 4, "chips": 180, "reroll_cost": 5},
        "blinds": {
            "big": {
                "status": "CURRENT",
                "name": "Big Blind",
                "type": "BIG",
                "score": 300,
            },
        },
        "jokers": {
            "count": 1,
            "limit": 5,
            "cards": [
                {
                    "label": "Seltzer",
                    "key": "j_seltzer",
                    "value": {"effect": "retrigger"},
                }
            ],
        },
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52},
        "hand": {
            "count": 8,
            "limit": 8,
            "cards": [
                {"label": "K of S", "value": {"rank": "K", "suit": "S"}},
                {"label": "K of H", "value": {"rank": "K", "suit": "H"}},
                {
                    "label": "?",
                    "value": {"rank": "Q", "suit": "C"},
                    "state": {"hidden": True},
                },
            ],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "state=SELECTING_HAND" in out
    assert "hands_left=3" in out
    assert "discards_left=4" in out
    assert "score=180/300 need=120" in out
    assert "K♠" in out
    assert "??" in out
    assert "jokers (1/5)" in out
    assert "Seltzer" in out
    assert "actions: play discard sort rearrange" in out


def test_print_summary_consumables_without_jokers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Consumables line must appear even when the joker slot is empty."""
    raw = {
        "state": "SELECTING_HAND",
        "money": 4,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"hands_left": 3, "discards_left": 4, "chips": 0, "reroll_cost": 5},
        "blinds": {
            "small": {
                "status": "CURRENT",
                "name": "Small Blind",
                "type": "SMALL",
                "score": 300,
            },
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "Death",
                    "key": "c_death",
                    "value": {
                        "effect": "Select 2 cards, convert the left card into the right card"
                    },
                }
            ],
        },
        "cards": {"count": 44, "limit": 52},
        "hand": {
            "count": 2,
            "limit": 8,
            "cards": [
                {"label": "7♣", "value": {"rank": "7", "suit": "C"}},
                {"label": "K♠", "value": {"rank": "K", "suit": "S"}},
            ],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "jokers" not in out
    assert "consumables (1/2):" in out
    assert "[0] Death" in out
    assert "arg order irrelevant" in out
    assert "use" in out


def test_print_summary_selecting_hand_no_passive_economy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = {
        "state": "SELECTING_HAND",
        "money": 4,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"hands_left": 3, "discards_left": 4, "chips": 180, "reroll_cost": 5},
        "blinds": {
            "big": {
                "status": "CURRENT",
                "name": "Big Blind",
                "type": "BIG",
                "score": 300,
            },
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52},
        "hand": {
            "count": 2,
            "limit": 8,
            "cards": [
                {"label": "K of S", "value": {"rank": "K", "suit": "S"}},
                {"label": "K of H", "value": {"rank": "K", "suit": "H"}},
            ],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "state=SELECTING_HAND" in out
    assert "economy:" not in out


def test_print_summary_selecting_hand_delayed_grat_economy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = {
        "state": "SELECTING_HAND",
        "money": 4,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {
            "hands_left": 3,
            "discards_left": 4,
            "discards_used": 0,
            "chips": 180,
            "reroll_cost": 5,
        },
        "blinds": {
            "big": {
                "status": "CURRENT",
                "name": "Big Blind",
                "type": "BIG",
                "score": 300,
            },
        },
        "jokers": {
            "count": 1,
            "limit": 5,
            "cards": [
                {
                    "label": "Delayed Gratification",
                    "key": "j_delayed_grat",
                    "value": {"effect": "earn $2 per discard if none used"},
                }
            ],
        },
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52},
        "hand": {
            "count": 2,
            "limit": 8,
            "cards": [
                {"label": "K of S", "value": {"rank": "K", "suit": "S"}},
                {"label": "K of H", "value": {"rank": "K", "suit": "H"}},
            ],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "economy:" in out
    assert "delayed_grat=" in out


def test_print_summary_round_eval(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "ROUND_EVAL",
        "money": 12,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {
            "hands_left": 2,
            "discards_left": 3,
            "chips": 500,
            "reroll_cost": 5,
            "cashout_preview": {
                "lines": [
                    {"kind": "blind", "label": "blind", "dollars": 3},
                    {"kind": "hands", "label": "hands", "dollars": 2},
                    {
                        "kind": "joker",
                        "label": "Golden Joker",
                        "dollars": 4,
                        "key": "j_golden",
                    },
                    {"kind": "interest", "label": "interest", "dollars": 2},
                ],
                "total": 11,
            },
        },
        "blinds": {
            "big": {
                "status": "DEFEATED",
                "name": "Big Blind",
                "type": "BIG",
                "score": 300,
            }
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52},
        "won": True,
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "state=ROUND_EVAL" in out
    assert "pending:" in out
    assert "Golden Joker" in out
    assert "total +$11" in out
    assert "→ cash_out" in out
    assert "cash_out" in out


def test_print_summary_round_eval_total_matches_line_sum(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pending total equals sum of line dollars (including interest)."""
    raw = {
        "state": "ROUND_EVAL",
        "money": 15,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {
            "hands_left": 0,
            "discards_left": 0,
            "chips": 500,
            "cashout_preview": {
                "lines": [
                    {"kind": "blind", "label": "blind", "dollars": 5},
                    {"kind": "hands", "label": "hands", "dollars": 3},
                    {"kind": "interest", "label": "interest", "dollars": 3},
                ],
                "total": 11,
            },
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52},
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "total +$11" in out
    assert "+$5 blind" in out
    assert "+$3 interest" in out


def test_print_summary_round_eval_blind_and_hands_total_equals_sum(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Red Stake no-reward Small Blind does not show stale blind dollars."""
    raw = {
        "state": "ROUND_EVAL",
        "money": 0,
        "round_num": 13,
        "ante_num": 6,
        "deck": "RED",
        "stake": "RED",
        "round": {
            "hands_left": 2,
            "discards_left": 0,
            "chips": 21790,
            "cashout_preview": {
                "lines": [
                    {"kind": "hands", "label": "hands", "dollars": 2},
                ],
                "total": 2,
            },
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52},
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "+$3 blind" not in out
    assert "+$2 hands" in out
    assert "total +$2" in out
    pending_block = out.split("pending:", 1)[1].split("\n", 1)[0]
    assert pending_block.count("total") == 1


def test_print_summary_round_eval_victory_overlay(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = {
        "state": "ROUND_EVAL",
        "money": 12,
        "round_num": 24,
        "ante_num": 8,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"hands_left": 0, "discards_left": 0, "chips": 1000000},
        "jokers": {
            "count": 1,
            "limit": 5,
            "cards": [{"label": "Joker", "key": "j_joker"}],
        },
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [{"label": "The Hermit", "key": "c_hermit"}],
        },
        "cards": {"count": 44, "limit": 52},
        "won": True,
        "victory_overlay": True,
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "→ endless" in out
    assert "→ menu" in out
    assert "→ cash_out" not in out
    assert "actions: endless menu" in out
    actions_line = out.split("actions:", 1)[1].strip()
    assert "sell" not in actions_line
    assert "use" not in actions_line
    assert "cash_out" not in actions_line


def test_print_summary_round_eval_investment_tag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = {
        "state": "ROUND_EVAL",
        "money": 12,
        "round_num": 24,
        "ante_num": 8,
        "deck": "RED",
        "stake": "WHITE",
        "round": {
            "hands_left": 0,
            "discards_left": 0,
            "chips": 500,
            "cashout_preview": {
                "lines": [
                    {"kind": "blind", "label": "blind", "dollars": 3},
                    {"kind": "interest", "label": "interest", "dollars": 1},
                ],
                "total": 4,
                "investment_received": 25,
            },
        },
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "cards": {"count": 44, "limit": 52},
        "won": True,
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "received:" in out
    assert "Investment Tag (boss defeat)" in out
    assert "+$25" in out
    assert "total +$4" in out
    assert "pending:" in out
    pending_block = out.split("pending:", 1)[1].split("\n", 1)[0]
    assert "Investment Tag" not in pending_block


def test_print_summary_pack_death_hint(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "SMODS_BOOSTER_OPENED",
        "money": 6,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "cards": {"count": 44, "limit": 52},
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "pack": {
            "count": 1,
            "limit": 1,
            "choices_remaining": 1,
            "cards": [
                {
                    "label": "Death",
                    "key": "c_death",
                    "value": {"effect": "copy left card into right"},
                }
            ],
        },
        "hand": {
            "count": 2,
            "limit": 8,
            "cards": [
                {"label": "7♣", "value": {"rank": "7", "suit": "C"}},
                {"label": "K♠", "value": {"rank": "K", "suit": "S"}},
            ],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "Death" in out
    assert "arg order irrelevant" in out
    assert "note: Death" not in out


def test_print_summary_shop(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "SHOP",
        "money": 10,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "cards": {"count": 44, "limit": 52},
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "shop": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "Joker",
                    "key": "j_joker",
                    "cost": {"buy": 4},
                    "value": {"effect": "+4 Mult"},
                }
            ],
        },
        "vouchers": {"count": 0, "limit": 1, "cards": []},
        "packs": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "Arcana Pack",
                    "key": "p_arcana",
                    "cost": {"buy": 4},
                    "value": {"effect": "Tarot cards"},
                }
            ],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "state=SHOP" in out
    assert "shop[0] Joker" in out
    assert "[ok]" in out
    assert "actions: buy" in out and "reroll" in out and "next_round" in out
    raw = {
        "state": "SHOP",
        "money": 10,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "cards": {"count": 44, "limit": 52},
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "shop": {
            "count": 1,
            "limit": 2,
            "cards": [
                {
                    "label": "Jolly Joker",
                    "key": "j_jolly",
                    "cost": {"buy": 6},
                    "value": {"effect": "+8 Mult if played hand contains a Pair"},
                    "modifier": {"edition": "FOIL", "perishable": 5, "rental": True},
                }
            ],
        },
        "vouchers": {"count": 0, "limit": 1, "cards": []},
        "packs": {"count": 0, "limit": 2, "cards": []},
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "(+50 chips)" in out
    assert "(perishable 5r)" in out
    assert "(rental -$1/round)" in out
    assert "Jolly Joker" in out


def test_print_summary_pack_opened(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "SMODS_BOOSTER_OPENED",
        "money": 6,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"reroll_cost": 5},
        "cards": {"count": 44, "limit": 52},
        "jokers": {"count": 0, "limit": 5, "cards": []},
        "consumables": {"count": 0, "limit": 2, "cards": []},
        "pack": {
            "count": 2,
            "limit": 2,
            "choices_remaining": 1,
            "cards": [
                {
                    "label": "The Magician",
                    "key": "c_magician",
                    "value": {
                        "effect": "convert 2 cards",
                        "target_min": 1,
                        "target_max": 2,
                    },
                },
                {
                    "label": "The Fool",
                    "key": "c_fool",
                    "value": {"effect": "copy last Tarot"},
                },
            ],
        },
        "hand": {
            "count": 8,
            "limit": 8,
            "cards": [{"label": "K of S", "value": {"rank": "K", "suit": "S"}}],
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "state=SMODS_BOOSTER_OPENED" in out
    assert "The Magician" in out
    assert "needs 1-2 targets" in out
    assert "choices remaining: 1" in out
    assert "actions: pack" in out
    assert "pack skip" not in out or "actions: pack" in out


def test_print_summary_game_over(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "GAME_OVER",
        "won": False,
        "deck": "RED",
        "stake": "WHITE",
        "seed": "ABC",
        "ante_num": 3,
        "round_num": 7,
        "run_summary": {
            "best_hand": 1200,
            "result": "Lost to Big Blind",
            "most_played_hand": {"name": "Pair", "count": 5},
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "GAME_OVER" in out
    assert "money=None" not in out
    assert "→ menu  then  start RED WHITE ABC" in out
    assert "actions: menu" in out


def test_print_summary_game_over_endless_loss(
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw = {
        "state": "GAME_OVER",
        "won": True,
        "deck": "RED",
        "stake": "WHITE",
        "seed": "ABC",
        "ante_num": 9,
        "round_num": 25,
        "run_summary": {
            "best_hand": 50000,
            "result": "Lost to Small Blind",
        },
    }
    print_summary(_envelope(raw))
    out = capsys.readouterr().out
    assert "GAME_OVER: Lost to Small Blind" in out
    assert "→ menu  then  start RED WHITE ABC" in out
    assert "Victory" not in out


def test_print_summary_error_envelope(capsys: pytest.CaptureFixture[str]) -> None:
    print_summary(
        {
            "ok": False,
            "format": "balatrobot-play-v1",
            "error": {"name": "BAD_REQUEST", "message": "nope"},
        }
    )
    out = capsys.readouterr().out
    assert "ERROR: BAD_REQUEST - nope" in out


# --- act.main ---------------------------------------------------------------


def test_act_main_routes_to_execute(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_execute(method: str, params: dict) -> dict:
        calls.append((method, params))
        return {"state": "MENU", "money": 0, "round_num": 0, "ante_num": 0}

    monkeypatch.setattr(act, "execute", fake_execute)
    monkeypatch.setattr(act.sys, "argv", ["act.py", "play", "0", "1"])
    rc = act.main()
    assert rc == 0
    assert calls == [("play", {"cards": [0, 1]})]
    out = capsys.readouterr().out
    assert "state=MENU" in out


def test_act_main_json_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_execute(method: str, params: dict) -> dict:
        return {"state": "MENU", "money": 0, "round_num": 0, "ante_num": 0}

    monkeypatch.setattr(act, "execute", fake_execute)
    monkeypatch.setattr(act.sys, "argv", ["act.py", "select", "--json"])
    rc = act.main()
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["gamestate"] == {"state": "MENU"}


def test_act_main_save_prints_success_without_state_refresh(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_rpc(method: str, params: dict) -> dict:
        calls.append((method, params))
        return {"success": True, "path": "run.jkr"}

    def fail_execute(method: str, params: dict) -> dict:
        raise AssertionError("save should not refresh gamestate")

    monkeypatch.setattr(act, "rpc", fake_rpc)
    monkeypatch.setattr(act, "execute", fail_execute)
    monkeypatch.setattr(act.sys, "argv", ["act.py", "save", "run.jkr"])
    rc = act.main()
    assert rc == 0
    assert calls == [("save", {"path": "run.jkr"})]
    out = capsys.readouterr().out
    assert "save success: run.jkr" in out
    assert "state=" not in out
    assert "actions:" not in out
    assert "hand:" not in out


def test_act_main_save_json_flag_keeps_play_envelope(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_rpc(method: str, params: dict) -> dict:
        raise AssertionError("save --json should keep execute path")

    def fake_execute(method: str, params: dict) -> dict:
        assert (method, params) == ("save", {"path": "run.jkr"})
        return {"state": "MENU", "money": 0, "round_num": 0, "ante_num": 0}

    monkeypatch.setattr(act, "rpc", fail_rpc)
    monkeypatch.setattr(act, "execute", fake_execute)
    monkeypatch.setattr(act.sys, "argv", ["act.py", "save", "run.jkr", "--json"])
    rc = act.main()
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["gamestate"] == {"state": "MENU"}


def test_act_main_unknown_method_returns_bad_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(act.sys, "argv", ["act.py", "frobnicate"])
    rc = act.main()
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False
    assert data["error"]["name"] == "BAD_REQUEST"


def test_act_main_no_args_returns_usage(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(act.sys, "argv", ["act.py"])
    rc = act.main()
    assert rc == 2
    data = json.loads(capsys.readouterr().out)
    assert data["error"]["name"] == "BAD_REQUEST"
    assert "usage" in data["error"]["message"]


def test_buy_blocked_by_slots_allows_negative_joker_when_slots_full() -> None:
    state = {
        "jokers": {"count": 5, "limit": 5},
        "consumables": {"count": 0, "limit": 2},
    }
    base_joker = {"set": "JOKER", "modifier": {}}
    negative_joker = {"set": "JOKER", "modifier": {"edition": "NEGATIVE"}}

    assert buy_blocked_by_slots(base_joker, state) is True
    assert buy_blocked_by_slots(negative_joker, state) is False


# --- estimate.estimate ------------------------------------------------------

import estimate  # noqa: E402  # type: ignore[unresolved-import]


def _hand_cards(*ranks_suits: tuple[str, str, dict]) -> list[dict]:
    out = []
    for rank, suit, mod in ranks_suits:
        mod = dict(mod)
        debuffed = mod.pop("debuff", False)
        card = {
            "label": f"{rank} of {suit}",
            "value": {"rank": rank, "suit": suit},
            "modifier": mod,
        }
        if debuffed:
            card["state"] = {"debuff": True}
        out.append(card)
    return out


def _est_state(
    hand: list[dict],
    jokers: list[dict] | None = None,
    hands_levels: dict | None = None,
    deck: str = "RED",
    blind_name: str = "Small Blind",
    blind_score: int = 300,
    discards_left: int = 3,
    hands_left: int = 4,
    deck_remaining: int = 44,
    money: int = 0,
) -> dict:
    return {
        "state": "SELECTING_HAND",
        "deck": deck,
        "money": money,
        "cards": {"count": deck_remaining, "limit": 52},
        "round": {"hands_left": hands_left, "discards_left": discards_left, "chips": 0},
        "blinds": {
            "small": {
                "status": "CURRENT",
                "name": blind_name,
                "type": "SMALL",
                "score": blind_score,
            }
        },
        "hands": hands_levels
        or {
            "High Card": {"order": 12, "chips": 5, "mult": 1, "level": 1},
            "Pair": {"order": 11, "chips": 10, "mult": 2, "level": 1},
            "Two Pair": {"order": 10, "chips": 20, "mult": 2, "level": 1},
            "Three of a Kind": {"order": 9, "chips": 30, "mult": 3, "level": 1},
            "Straight": {"order": 8, "chips": 30, "mult": 4, "level": 1},
            "Flush": {"order": 7, "chips": 35, "mult": 4, "level": 1},
            "Full House": {"order": 6, "chips": 40, "mult": 4, "level": 1},
            "Four of a Kind": {"order": 5, "chips": 60, "mult": 7, "level": 1},
            "Straight Flush": {"order": 4, "chips": 100, "mult": 8, "level": 1},
            "Five of a Kind": {"order": 3, "chips": 120, "mult": 12, "level": 1},
            "Flush House": {"order": 2, "chips": 140, "mult": 14, "level": 1},
            "Flush Five": {"order": 1, "chips": 160, "mult": 16, "level": 1},
        },
        "jokers": {"count": len(jokers or []), "limit": 5, "cards": jokers or []},
        "hand": {"count": len(hand), "limit": 8, "cards": hand},
    }


def test_estimate_three_of_a_kind_kings_no_jokers() -> None:
    # 3 Kings + 2 kickers -> Three of a Kind: base 30/3 + 3*10 chips = 60*3 = 180
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("K", "D", {}),
        ("5", "C", {}),
        ("2", "S", {}),
    )
    est = estimate.estimate(_est_state(hand))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Three of a Kind"
    assert top[0]["score"] == 180
    assert top[0]["chips"] == 60
    assert top[0]["mult"] == 3


def test_estimate_pair_with_mult_enhancement_and_seltzer() -> None:
    # Pair of 4s, one is a Mult card (+4 mult), Seltzer active (retrigger x2).
    # base 10/2, scoring 4+4=8 chips. Per trigger: +4 mult (Mult card).
    # Seltzer retrigger -> 2 triggers: chips 8*2=16, mult add 4*2=8.
    # mult = 2 + 8 = 10; chips = 10 + 16 = 26; score = 260.
    hand = _hand_cards(
        ("4", "D", {"enhancement": "MULT"}),
        ("4", "C", {}),
        ("7", "H", {}),
        ("9", "S", {}),
        ("2", "D", {}),
    )
    jokers = [
        {
            "label": "Seltzer",
            "key": "j_selzer",
            "value": {"effect": "在接下来的8次出牌中 重新触发所有 打出的卡牌"},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["score"] == 260


def test_estimate_diamond_flush_with_greedy_joker() -> None:
    # 5-diamond flush, base 35/4. Greedy: +3 mult per diamond (5 -> +15).
    # No retrigger. chips = 35 + (A+J+T+9+4)=11+10+10+9+4=44 -> 79.
    # mult = 4 + 15 = 19. score = 79 * 19 = 1501.
    hand = _hand_cards(
        ("A", "D", {}),
        ("J", "D", {}),
        ("T", "D", {}),
        ("9", "D", {}),
        ("4", "D", {}),
    )
    jokers = [
        {
            "label": "Greedy Joker",
            "key": "j_greedy_joker",
            "value": {"effect": "+3 Mult per diamond"},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Flush"
    assert top[0]["score"] == 1501


def test_estimate_unmodeled_joker_warned() -> None:
    hand = _hand_cards(
        ("K", "S", {}), ("K", "H", {}), ("3", "D", {}), ("5", "C", {}), ("2", "S", {})
    )
    jokers = [
        {
            "label": "Some Unknown Joker",
            "key": "j_unknown_xyz",
            "value": {"effect": "weird"},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    assert est["estimate"]["unmodeled_jokers"] == ["Some Unknown Joker"]


def test_estimate_flint_halves_base() -> None:
    # Pair of 5s, base 10/2. Flint halves base -> 5/1. chips 5+5+5=15, mult 1.
    # score = 15 * 1 = 15.
    hand = _hand_cards(
        ("5", "S", {}), ("5", "H", {}), ("7", "D", {}), ("9", "C", {}), ("2", "S", {})
    )
    est = estimate.estimate(_est_state(hand, blind_name="The Flint", blind_score=1600))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["score"] == 15


def test_estimate_dusk_inactive_when_not_last_hand() -> None:
    # Pair of 4s, one Mult card (+4 mult/trigger), Dusk owned but hands_left=4
    # => NOT the last hand => Dusk does not trigger.
    # base 10/2, chips 4+4=8, +4 mult/trigger, 1 trigger => chips 18, mult 6 => 108.
    hand = _hand_cards(
        ("4", "D", {"enhancement": "MULT"}),
        ("4", "C", {}),
        ("7", "H", {}),
        ("9", "S", {}),
        ("2", "D", {}),
    )
    jokers = [
        {"label": "Dusk", "key": "j_dusk", "value": {"effect": "retrigger final hand"}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers, hands_left=4))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["score"] == 108  # no Dusk


def test_estimate_dusk_active_on_last_hand() -> None:
    # Same hand, but hands_left=1 => Dusk triggers (+1 retrigger).
    # 2 triggers: chips 8*2=16, mult add 4*2=8 => chips 26, mult 10 => 260.
    hand = _hand_cards(
        ("4", "D", {"enhancement": "MULT"}),
        ("4", "C", {}),
        ("7", "H", {}),
        ("9", "S", {}),
        ("2", "D", {}),
    )
    jokers = [
        {"label": "Dusk", "key": "j_dusk", "value": {"effect": "retrigger final hand"}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers, hands_left=1))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["score"] == 260  # Dusk active


def test_estimate_pair_play_indices_match_scoring_without_kickers() -> None:
    # Pair of Kings + 3 kickers: play only the two Kings (indices 0,1).
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    est = estimate.estimate(_est_state(hand))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["indices"] == [0, 1]
    assert top[0]["scoring_indices"] == [0, 1]
    assert len(top[0]["cards"]) == 2


def test_estimate_three_of_a_kind_play_indices_match_scoring() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("K", "D", {}),
        ("5", "C", {}),
        ("2", "S", {}),
    )
    est = estimate.estimate(_est_state(hand))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Three of a Kind"
    assert top[0]["indices"] == [0, 1, 2]
    assert top[0]["scoring_indices"] == [0, 1, 2]
    assert len(top[0]["cards"]) == 3


def test_estimate_blackboard_includes_kicker_in_play_indices() -> None:
    # Two Pair with J♥ held blocks Blackboard; playing J♥ as kicker leaves only black cards held.
    hand = _hand_cards(
        ("K", "S", {}),
        ("Q", "C", {}),
        ("J", "H", {}),
        ("T", "S", {}),
        ("8", "S", {}),
        ("8", "D", {}),
        ("5", "H", {}),
        ("5", "C", {}),
    )
    jokers = [
        {"label": "Abstract Joker", "key": "j_abstract", "value": {"effect": "+18"}},
        {"label": "Blackboard", "key": "j_blackboard", "value": {}},
        {"label": "Riff-raff", "key": "j_riff_raff", "value": {}},
        {"label": "Mystic Summit", "key": "j_mystic_summit", "value": {}},
        {
            "label": "Swashbuckler",
            "key": "j_swashbuckler",
            "value": {"stats": {"mult": 12}},
        },
        {"label": "Dusk", "key": "j_dusk", "value": {}},
    ]
    est = estimate.estimate(
        _est_state(
            hand,
            jokers=jokers,
            hands_levels={
                "Two Pair": {"chips": 40, "mult": 3, "level": 2},
                "Pair": {"chips": 10, "mult": 2, "level": 1},
            },
        )
    )
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Two Pair"
    assert top[0]["indices"] == [2, 4, 5, 6, 7]
    assert top[0]["scoring_indices"] == [4, 5, 6, 7]
    assert top[0]["score"] == 4950.0


def test_estimate_blue_joker_adds_deck_remaining_chips() -> None:
    # Pair of Kings: base 10/2 + 20 card chips = 30 chips, mult 2 => 60.
    # Blue Joker with 52 cards left: +104 chips => (30+104)*2 = 268.
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Blue Joker",
            "key": "j_blue_joker",
            "value": {"effect": "+104 chips"},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers, deck_remaining=52))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["score"] == 268
    assert est["estimate"]["unmodeled_jokers"] == []


@pytest.fixture
def cheats_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BALATROBOT_ALLOW_CHEATS", "1")


def test_add_requires_cheats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BALATROBOT_ALLOW_CHEATS", raising=False)
    with pytest.raises(ValueError, match="BALATROBOT_ALLOW_CHEATS"):
        build_params("add", ["joker", "j_dusk"])


def test_set_requires_cheats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BALATROBOT_ALLOW_CHEATS", raising=False)
    with pytest.raises(ValueError, match="BALATROBOT_ALLOW_CHEATS"):
        build_params("set", ["hands", "1"])


def test_build_params_add_joker(cheats_on: None) -> None:
    assert build_params("add", ["joker", "j_dusk"]) == {"key": "j_dusk"}


def test_build_params_add_card_with_flags(cheats_on: None) -> None:
    assert build_params("add", ["card", "D_4", "enhancement=MULT", "seal=RED"]) == {
        "key": "D_4",
        "enhancement": "MULT",
        "seal": "RED",
    }


def test_build_params_add_rejects_voucher_kind(cheats_on: None) -> None:
    with pytest.raises(ValueError, match="joker, card, or consumable"):
        build_params("add", ["voucher", "v_overstock_norm"])


def test_build_params_set_round_fields(cheats_on: None) -> None:
    assert build_params("set", ["hands_left", "1", "chips", "0"]) == {
        "hands": 1,
        "chips": 0,
    }


def test_build_params_set_rejects_money(cheats_on: None) -> None:
    with pytest.raises(ValueError, match="not allowed"):
        build_params("set", ["money", "100"])


def test_build_params_debuff(cheats_on: None) -> None:
    assert build_params("debuff", ["0", "2"]) == {"cards": [0, 2], "debuff": True}
    assert build_params("debuff", ["clear", "1"]) == {"cards": [1], "debuff": False}


def test_debuff_requires_cheats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BALATROBOT_ALLOW_CHEATS", raising=False)
    with pytest.raises(ValueError, match="BALATROBOT_ALLOW_CHEATS"):
        build_params("debuff", ["0"])


def test_build_params_reroll_boss(cheats_on: None) -> None:
    assert build_params("reroll_boss", []) == {}


def test_estimate_wily_joker_three_of_a_kind_chips() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("K", "D", {}),
        ("5", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Wily Joker", "key": "j_wily", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Three of a Kind"
    # base 60 chips + 100 wily = 160, mult 3 => 480
    assert top[0]["chips"] == 160
    assert top[0]["score"] == 480


def test_estimate_jolly_joker_pair_mult() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Jolly Joker", "key": "j_jolly", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # chips 30, mult 2+8=10 => 300
    assert top[0]["mult"] == 10
    assert top[0]["score"] == 300


def test_estimate_banner_adds_discards_times_thirty() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Banner", "key": "j_banner", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers, discards_left=3))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # chips 30 + 90 banner = 120, mult 2 => 240
    assert top[0]["chips"] == 120
    assert top[0]["score"] == 240


def test_estimate_card_sharp_on_second_pair_of_round() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Card Sharp", "key": "j_card_sharp", "value": {}}]
    hands = {
        "Pair": {
            "order": 11,
            "chips": 10,
            "mult": 2,
            "level": 1,
            "played_this_round": 1,
        },
        "High Card": {
            "order": 12,
            "chips": 5,
            "mult": 1,
            "level": 1,
            "played_this_round": 0,
        },
    }
    est = estimate.estimate(_est_state(hand, jokers=jokers, hands_levels=hands))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # chips 30, mult 2*3=6 => 180
    assert top[0]["mult"] == 6
    assert top[0]["score"] == 180


def test_estimate_half_joker_small_play() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
    )
    jokers = [{"label": "Half Joker", "key": "j_half", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["indices"] == [0, 1]
    assert top[0]["mult"] == 22
    assert top[0]["score"] == 660


def test_estimate_raised_fist_excludes_played_kicker_from_held_cards() -> None:
    hand = _hand_cards(
        ("A", "S", {}),
        ("K", "H", {}),
        ("9", "D", {}),
        ("2", "C", {}),
        ("3", "S", {}),
    )
    jokers = [{"label": "Raised Fist", "key": "j_raised_fist", "value": {}}]

    ace_only = estimate.score_hand_indices(_est_state(hand, jokers=jokers), [0])
    with_low_kicker = estimate.score_hand_indices(
        _est_state(hand, jokers=jokers), [0, 3]
    )

    assert ace_only["hand_type"] == "High Card"
    assert ace_only["scoring_indices"] == [0]
    assert ace_only["mult"] == 5  # base 1 + lowest held 2 doubled => +4
    assert with_low_kicker["hand_type"] == "High Card"
    assert with_low_kicker["scoring_indices"] == [0]
    assert (
        with_low_kicker["mult"] == 7
    )  # played 2 is no longer held; lowest held 3 => +6
    assert with_low_kicker["score"] > ace_only["score"]


def test_estimate_hack_retriggers_low_ranks() -> None:
    # Pair of 5s: each 5 scores 5 chips; hack doubles triggers => 5+5 twice = 20 card chips.
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("K", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Hack", "key": "j_hack", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # base 10 + 20 card = 30 chips, mult 2 => 60
    assert top[0]["chips"] == 30
    assert top[0]["score"] == 60


def test_estimate_stuntman_adds_two_fifty_chips() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Stuntman", "key": "j_stuntman", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 280
    assert top[0]["score"] == 560


def test_estimate_bootstraps_mult_from_money() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Bootstraps", "key": "j_bootstraps", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers, money=14))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # floor(14/5)=2 tiers, +4 mult => mult 6, chips 30 => 180
    assert top[0]["mult"] == 6
    assert top[0]["score"] == 180


def test_estimate_supernova_uses_lifetime_hand_count() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Supernova", "key": "j_supernova", "value": {}}]
    hands = {
        "Pair": {"order": 11, "chips": 10, "mult": 2, "level": 1, "played": 6},
        "High Card": {"order": 12, "chips": 5, "mult": 1, "level": 1, "played": 0},
    }
    est = estimate.estimate(_est_state(hand, jokers=jokers, hands_levels=hands))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 9
    assert top[0]["score"] == 270


def test_estimate_seeing_double_x2_with_club_and_other_suit() -> None:
    hand = _hand_cards(
        ("K", "C", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "S", {}),
        ("2", "C", {}),
    )
    jokers = [{"label": "Seeing Double", "key": "j_seeing_double", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 4
    assert top[0]["score"] == 120


def test_estimate_ceremonial_parses_effect_mult() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Ceremonial Dagger",
            "key": "j_ceremonial",
            "value": {"stats": {"mult": 21}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 23
    assert top[0]["score"] == 690


def test_estimate_ceremonial_parses_effect_mult_english() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Ceremonial Dagger",
            "key": "j_ceremonial",
            "value": {"stats": {"mult": 21}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 23
    assert top[0]["score"] == 690


def test_estimate_ice_cream_parses_effect_chips_english() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Ice Cream",
            "key": "j_ice_cream",
            "value": {
                "effect": "(Currently +85 Chips )",
                "stats": {"chips": 85},
            },
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["chips"] == 115
    assert top[0]["score"] == 230


def test_estimate_duo_x2_on_pair() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "The Duo", "key": "j_duo", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 4
    assert top[0]["score"] == 120


def test_estimate_cavendish_x3_on_pair() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Cavendish", "key": "j_cavendish", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 6
    assert top[0]["score"] == 180


def test_estimate_bull_chips_from_money() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Bull", "key": "j_bull", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers, money=10))
    top = est["estimate"]["top"]
    assert top[0]["chips"] == 50
    assert top[0]["score"] == 100


def test_estimate_baron_x15_per_held_king() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("K", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Baron", "key": "j_baron", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 3
    assert top[0]["score"] == 60


def test_estimate_shoot_the_moon_held_queen() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("Q", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Shoot the Moon", "key": "j_shoot_the_moon", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 15
    assert top[0]["score"] == 300


def test_estimate_photograph_first_face_x2() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Photograph", "key": "j_photograph", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 4
    assert top[0]["score"] == 120


def test_estimate_photochad_glass_red_leftmost() -> None:
    hand = _hand_cards(
        ("J", "H", {"enhancement": "GLASS", "seal": "RED"}),
        ("J", "S", {}),
        ("5", "H", {}),
        ("3", "C", {}),
        ("2", "D", {}),
    )
    jokers = [
        {"label": "Photograph", "key": "j_photograph", "value": {}},
        {"label": "Hanging Chad", "key": "j_hanging_chad", "value": {}},
    ]
    est = estimate.score_hand_indices(_est_state(hand, jokers=jokers), [0, 1])
    assert est["hand_type"] == "Pair"
    assert est["chips"] == 60
    assert est["mult"] == 512
    assert est["score"] == 30720


def test_estimate_photochad_glass_red_no_red_lower() -> None:
    jokers = [
        {"label": "Photograph", "key": "j_photograph", "value": {}},
        {"label": "Hanging Chad", "key": "j_hanging_chad", "value": {}},
    ]
    hand_red = _hand_cards(
        ("J", "H", {"enhancement": "GLASS", "seal": "RED"}),
        ("J", "S", {}),
        ("5", "H", {}),
        ("3", "C", {}),
        ("2", "D", {}),
    )
    hand_plain = _hand_cards(
        ("J", "H", {"enhancement": "GLASS"}),
        ("J", "S", {}),
        ("5", "H", {}),
        ("3", "C", {}),
        ("2", "D", {}),
    )
    optimal = estimate.score_hand_indices(_est_state(hand_red, jokers=jokers), [0, 1])
    suboptimal = estimate.score_hand_indices(
        _est_state(hand_plain, jokers=jokers), [0, 1]
    )
    assert suboptimal["score"] < optimal["score"]
    assert optimal["score"] == 30720
    assert suboptimal["score"] == 6400


def test_estimate_mime_holo_adds_joker_main_mult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    with_holo = [
        {"label": "Jolly Joker", "key": "j_jolly", "value": {}},
        {
            "label": "Mime",
            "key": "j_mime",
            "value": {},
            "modifier": {"edition": "HOLO"},
        },
    ]
    plain = [
        {"label": "Jolly Joker", "key": "j_jolly", "value": {}},
        {"label": "Mime", "key": "j_mime", "value": {}},
    ]
    holo_score = estimate.score_hand_indices(
        _est_state(hand, jokers=with_holo), [0, 1]
    )["score"]
    plain_score = estimate.score_hand_indices(_est_state(hand, jokers=plain), [0, 1])[
        "score"
    ]
    assert holo_score > plain_score
    assert holo_score - plain_score == 200  # +10 mult on mime slot * 20 chips


def test_estimate_mime_holo_held_steel_not_multiplied() -> None:
    """Holo on held/retrigger jokers applies after held ×Mult stack (S31)."""
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "D", {}),
        ("3", "H", {}),
        ("7", "C", {}),
        ("2", "S", {}),
        ("K", "H", {"enhancement": "STEEL", "seal": "RED"}),
    )
    with_holo = [
        {"label": "Baron", "key": "j_baron", "value": {}},
        {
            "label": "Mime",
            "key": "j_mime",
            "value": {},
            "modifier": {"edition": "HOLO"},
        },
    ]
    plain = [
        {"label": "Baron", "key": "j_baron", "value": {}},
        {"label": "Mime", "key": "j_mime", "value": {}},
    ]
    holo = estimate.score_hand_indices(_est_state(hand, jokers=with_holo), [0, 1])
    base = estimate.score_hand_indices(_est_state(hand, jokers=plain), [0, 1])
    assert holo["score"] > base["score"]
    assert holo["score"] - base["score"] == 200  # flat +10 mult, not × held stack
    assert holo["score"] == 656  # (22.78125 + 10) * 20 rounded


def test_estimate_stencil_xmult_from_empty_slots() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Joker Stencil", "key": "j_stencil", "value": {}}]
    state = _est_state(hand, jokers=jokers)
    state["jokers"]["limit"] = 5
    est = estimate.estimate(state)
    top = est["estimate"]["top"]
    # empty=5-1=4, +1 stencil => x5 on pair mult 2 => 10
    assert top[0]["mult"] == 10
    assert top[0]["score"] == 300


def test_estimate_arrowhead_adds_fifty_per_spade() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Arrowhead", "key": "j_arrowhead", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 80
    assert top[0]["score"] == 160


def test_estimate_sock_and_buskin_retriggers_face_cards() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Sock and Buskin", "key": "j_sock_and_buskin", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["chips"] == 50
    assert top[0]["score"] == 100


def test_estimate_triboulet_x2_on_kings_and_queens() -> None:
    hand = _hand_cards(
        ("Q", "S", {}),
        ("Q", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Triboulet", "key": "j_triboulet", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 8
    assert top[0]["score"] == 240


def test_estimate_ride_the_bus_parses_effect_mult() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Ride the Bus",
            "key": "j_ride_the_bus",
            "value": {
                "effect": "(Currently +5 Mult )",
                "stats": {"mult": 5, "ride_the_bus_step": 1},
            },
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    # No scoring face → +5 stored +1 step; High Card on 5 beats face Pair for this joker.
    assert top[0]["hand_type"] == "High Card"
    assert top[0]["indices"] == [2]
    assert top[0]["mult"] == 7
    assert top[0]["score"] == 70


def test_estimate_throwback_parses_effect_xmult() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Throwback",
            "key": "j_throwback",
            "value": {"effect": "(Currently X1.5 Mult )"},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 3
    assert top[0]["score"] == 90


def test_estimate_steel_joker_parses_effect_xmult() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Steel Joker",
            "key": "j_steel_joker",
            "value": {"effect": "(Currently X1.4 Mult )"},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 2.8
    assert top[0]["score"] == 84


def test_estimate_raised_fist_lowest_held_rank() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("2", "D", {}),
    )
    jokers = [{"label": "Raised Fist", "key": "j_raised_fist", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["indices"] == [0, 1]
    assert top[0]["mult"] == 6
    assert top[0]["score"] == 120


def test_estimate_uses_joker_stats_without_effect_text() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Ride the Bus",
            "key": "j_ride_the_bus",
            "value": {"stats": {"mult": 4, "ride_the_bus_step": 1}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 7
    assert top[0]["score"] == 140


def test_estimate_erosion_from_run_counters() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Erosion", "key": "j_erosion", "value": {}}]
    state = _est_state(hand, jokers=jokers)
    state["run"] = {"starting_deck_size": 52, "deck_size": 42, "skips": 0}
    est = estimate.estimate(state)
    top = est["estimate"]["top"]
    assert top[0]["mult"] == 42
    assert top[0]["score"] == 1260


def test_estimate_ancient_xmult_on_matching_suit() -> None:
    hand = _hand_cards(
        ("K", "D", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Ancient Joker", "key": "j_ancient", "value": {}}]
    state = _est_state(hand, jokers=jokers)
    state["round"]["ancient_suit"] = "D"
    est = estimate.estimate(state)
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # base 10 + 20 card chips = 30; mult 2 * 1.5 on one king = 3 => 90
    assert top[0]["score"] == 90


def test_estimate_idol_xmult_on_matching_card() -> None:
    hand = _hand_cards(
        ("K", "D", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "The Idol", "key": "j_idol", "value": {}}]
    state = _est_state(hand, jokers=jokers)
    state["round"]["idol_rank"] = "K"
    state["round"]["idol_suit"] = "D"
    est = estimate.estimate(state)
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # one king matches idol => mult 2 * 2 = 4 on that trigger only => total mult 4
    assert top[0]["mult"] == 4
    assert top[0]["score"] == 120


def test_estimate_loyalty_card_active_from_stats() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Loyalty Card",
            "key": "j_loyalty_card",
            "value": {
                "stats": {
                    "loyalty_every": 5,
                    "loyalty_remaining": 5,
                    "loyalty_x_mult": 4,
                }
            },
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # chips 30, mult 2 * 4 = 8 => 240
    assert top[0]["mult"] == 8
    assert top[0]["score"] == 240


def test_estimate_square_joker_four_card_play() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
    )
    jokers = [
        {"label": "Square Joker", "key": "j_square", "value": {"stats": {"chips": 8}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert len(top[0]["indices"]) == 4
    # base 10 + 20 card + 8 stats + 4 growth = 42 chips, mult 2 => 84
    assert top[0]["chips"] == 42
    assert top[0]["score"] == 84


def test_estimate_runner_straight_growth() -> None:
    hand = _hand_cards(
        ("9", "S", {}),
        ("T", "D", {}),
        ("J", "H", {}),
        ("Q", "C", {}),
        ("K", "S", {}),
    )
    jokers = [{"label": "Runner", "key": "j_runner", "value": {"stats": {"chips": 30}}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Straight"
    assert top[0]["chips"] == 124
    assert top[0]["score"] == 496


def test_estimate_wee_joker_twos_scored() -> None:
    hand = _hand_cards(
        ("2", "S", {}),
        ("2", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("K", "S", {}),
    )
    jokers = [{"label": "Wee Joker", "key": "j_wee", "value": {"stats": {"chips": 0}}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 30
    assert top[0]["score"] == 60


def test_estimate_trousers_two_pair_growth() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("5", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Spare Trousers",
            "key": "j_trousers",
            "value": {"stats": {"mult": 4}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Two Pair"
    assert top[0]["mult"] == 8
    assert top[0]["score"] == 400


def test_estimate_vampire_enhanced_scoring_cards() -> None:
    hand = _hand_cards(
        ("K", "S", {"enhancement": "BONUS"}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Vampire", "key": "j_vampire", "value": {"stats": {"x_mult": 1.2}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 2.6
    assert top[0]["score"] == 78


def test_estimate_vampire_strips_enhancement_chips() -> None:
    hand = _hand_cards(
        ("5", "S", {"enhancement": "BONUS"}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Vampire", "key": "j_vampire", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 20
    assert top[0]["mult"] == 2.2
    assert top[0]["score"] == 44


def test_estimate_blackboard_wild_held_counts() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "H", {"enhancement": "WILD"}),
    )
    jokers = [{"label": "Blackboard", "key": "j_blackboard", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 6


def test_estimate_wild_flush_with_four_same_suit() -> None:
    hand = _hand_cards(
        ("K", "H", {}),
        ("Q", "H", {}),
        ("J", "H", {}),
        ("T", "H", {}),
        ("9", "D", {"enhancement": "WILD"}),
    )
    est = estimate.estimate(_est_state(hand))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Straight Flush"


def test_estimate_lusty_joker_wild_heart_scores() -> None:
    hand = _hand_cards(
        ("K", "H", {}),
        ("Q", "H", {}),
        ("J", "H", {}),
        ("T", "H", {}),
        ("9", "C", {"enhancement": "WILD"}),
    )
    jokers = [{"label": "Lusty Joker", "key": "j_lusty_joker", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Straight Flush"
    assert top[0]["mult"] == 23


def test_estimate_ace_and_queen_wild_not_pair() -> None:
    hand = _hand_cards(
        ("A", "S", {"enhancement": "MULT"}),
        ("Q", "D", {"enhancement": "WILD"}),
        ("5", "C", {}),
        ("3", "H", {}),
        ("2", "S", {}),
    )
    est = estimate.estimate(_est_state(hand))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "High Card"
    assert top[0]["indices"] == [0]


def test_flower_pot_wild_suit_assignment() -> None:
    import estimate_jokers as ej  # type: ignore[unresolved-import]

    three_hearts = [
        {"rank": "K", "suit": "H", "enhancement": "WILD"},
        {"rank": "Q", "suit": "H", "enhancement": ""},
        {"rank": "J", "suit": "H", "enhancement": ""},
    ]
    assert not ej._flower_pot_active(three_hearts, {})

    four_wilds = [
        {"rank": "K", "suit": "H", "enhancement": "WILD"},
        {"rank": "Q", "suit": "D", "enhancement": "WILD"},
        {"rank": "J", "suit": "S", "enhancement": "WILD"},
        {"rank": "T", "suit": "C", "enhancement": "WILD"},
    ]
    assert ej._flower_pot_active(four_wilds, {})


def test_seeing_double_wild_assigns_club_and_other() -> None:
    import estimate_jokers as ej  # type: ignore[unresolved-import]

    wild_plus_club = [
        {"rank": "K", "suit": "H", "enhancement": "WILD"},
        {"rank": "Q", "suit": "C", "enhancement": ""},
    ]
    assert ej._seeing_double_active(wild_plus_club, {})


def test_wild_debuffed_no_flush_help() -> None:
    hand = _hand_cards(
        ("K", "H", {"enhancement": "WILD", "debuff": True}),
        ("5", "D", {}),
        ("7", "D", {}),
        ("9", "D", {}),
        ("J", "D", {}),
    )
    est = estimate.estimate(_est_state(hand))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] != "Flush"
    assert top[0]["hand_type"] == "High Card"


def test_wild_debuffed_lusty_no_bonus() -> None:
    hand = _hand_cards(
        ("K", "H", {"enhancement": "WILD", "debuff": True}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
        ("6", "D", {}),
    )
    jokers = [{"label": "Lusty Joker", "key": "j_lusty_joker", "value": {}}]
    line = estimate.score_hand_indices(_est_state(hand, jokers=jokers), [0])
    assert line["hand_type"] == "High Card"
    assert line["mult"] == 1


def test_flush_five_five_wild_kings() -> None:
    hand = _hand_cards(
        ("K", "H", {"enhancement": "WILD"}),
        ("K", "D", {"enhancement": "WILD"}),
        ("K", "S", {"enhancement": "WILD"}),
        ("K", "C", {"enhancement": "WILD"}),
        ("K", "H", {"enhancement": "WILD"}),
    )
    est = estimate.estimate(_est_state(hand))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Flush Five"
    assert top[0]["mult"] == 16


def test_estimate_obelisk_grows_off_most_played_hand() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Obelisk",
            "key": "j_obelisk",
            "value": {"stats": {"x_mult": 1.4, "obelisk_step": 0.2}},
        }
    ]
    hands = {
        "Pair": {
            "order": 11,
            "chips": 10,
            "mult": 2,
            "level": 1,
            "played": 4,
            "played_this_round": 0,
            "visible": True,
        },
        "Flush": {
            "order": 7,
            "chips": 35,
            "mult": 4,
            "level": 1,
            "played": 5,
            "played_this_round": 0,
            "visible": True,
        },
        "High Card": {
            "order": 12,
            "chips": 5,
            "mult": 1,
            "level": 1,
            "played": 2,
            "played_this_round": 0,
            "visible": True,
        },
    }
    state = _est_state(hand, jokers=jokers, hands_levels=hands)
    est = estimate.estimate(state)
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    # Pair 4->5 after inc; Flush still at 5 >= 5 => grow: 1.4 + 0.2 = 1.6
    assert top[0]["mult"] == pytest.approx(3.2)
    assert top[0]["score"] == pytest.approx(96)


def test_estimate_obelisk_resets_on_most_played_hand() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Obelisk",
            "key": "j_obelisk",
            "value": {"stats": {"x_mult": 1.8, "obelisk_step": 0.2}},
        }
    ]
    hands = {
        "Pair": {
            "order": 11,
            "chips": 10,
            "mult": 2,
            "level": 1,
            "played": 10,
            "played_this_round": 0,
        },
        "Flush": {
            "order": 7,
            "chips": 35,
            "mult": 4,
            "level": 1,
            "played": 3,
            "played_this_round": 0,
        },
        "High Card": {
            "order": 12,
            "chips": 5,
            "mult": 1,
            "level": 1,
            "played": 2,
            "played_this_round": 0,
        },
    }
    state = _est_state(hand, jokers=jokers, hands_levels=hands)
    est = estimate.estimate(state)
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 2
    assert top[0]["score"] == 60


def test_estimate_obelisk_first_play_resets() -> None:
    """First play of a hand type increments to 1 with no other hand at >=1 -> reset."""
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Obelisk",
            "key": "j_obelisk",
            "value": {"stats": {"obelisk_step": 0.2}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 2
    assert top[0]["score"] == 60


def test_estimate_ride_the_bus_grows_without_scoring_face() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Ride the Bus",
            "key": "j_ride_the_bus",
            "value": {"stats": {"mult": 2, "ride_the_bus_step": 1}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 5
    assert top[0]["score"] == 100


def test_estimate_ride_the_bus_resets_on_scoring_face() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Ride the Bus",
            "key": "j_ride_the_bus",
            "value": {"stats": {"mult": 5, "ride_the_bus_step": 1}},
        }
    ]
    line = estimate.score_hand_indices(_est_state(hand, jokers=jokers), [0, 1])
    assert line["hand_type"] == "Pair"
    assert line["mult"] == 2
    assert line["score"] == 60


def test_estimate_pareidolia_makes_all_cards_face_for_scary() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
    )
    jokers = [
        {"label": "Pareidolia", "key": "j_pareidolia", "value": {}},
        {"label": "Scary Face", "key": "j_scary_face", "value": {}},
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 80
    assert top[0]["score"] == 160


def test_estimate_hit_the_road_uses_stats_xmult() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Hit the Road",
            "key": "j_hit_the_road",
            "value": {"stats": {"x_mult": 2.0}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 4
    assert top[0]["score"] == 120


def test_estimate_brainstorm_doubles_jolly_pair() -> None:
    hand = _hand_cards(
        ("J", "S", {}),
        ("J", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Jolly Joker", "key": "j_jolly", "value": {}},
        {"label": "Brainstorm", "key": "j_brainstorm", "value": {}},
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 18
    assert top[0]["score"] == 540


def test_estimate_blueprint_copies_right_joker() -> None:
    hand = _hand_cards(
        ("J", "S", {}),
        ("J", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Blueprint", "key": "j_blueprint", "value": {}},
        {"label": "Jolly Joker", "key": "j_jolly", "value": {}},
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 18
    assert top[0]["score"] == 540


def test_estimate_hologram_uses_stats_xmult() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Hologram", "key": "j_hologram", "value": {"stats": {"x_mult": 2.0}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 4
    assert top[0]["score"] == 120


def test_estimate_four_fingers_four_card_straight() -> None:
    hand = _hand_cards(
        ("2", "S", {}),
        ("3", "H", {}),
        ("4", "D", {}),
        ("5", "C", {}),
        ("9", "S", {}),
    )
    jokers = [{"label": "Four Fingers", "key": "j_four_fingers", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Straight"
    assert top[0]["score"] == 176


def test_estimate_shortcut_allows_rank_gap() -> None:
    hand = _hand_cards(
        ("2", "S", {}),
        ("3", "H", {}),
        ("5", "D", {}),
        ("6", "C", {}),
        ("7", "S", {}),
    )
    jokers = [{"label": "Shortcut", "key": "j_shortcut", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Straight"
    assert top[0]["score"] == 212


def test_estimate_green_joker_first_hand() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Green Joker",
            "key": "j_green_joker",
            "value": {"stats": {"mult": 0, "green_hand_add": 1}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 3
    assert top[0]["score"] == 60


def test_estimate_mime_doubles_held_steel() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("K", "D", {"enhancement": "STEEL"}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Mime", "key": "j_mime", "value": {"rarity": "UNCOMMON"}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 4.5
    assert top[0]["score"] == 90


def test_estimate_baseball_reacts_to_uncommon_joker() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Cavendish", "key": "j_cavendish", "value": {"rarity": "UNCOMMON"}},
        {"label": "Baseball Card", "key": "j_baseball", "value": {}},
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 9
    assert top[0]["score"] == 180


def test_estimate_joker_foil_before_effect() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Jolly Joker",
            "key": "j_jolly",
            "value": {},
            "modifier": {"edition": "FOIL"},
        },
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 70
    assert top[0]["mult"] == 10
    assert top[0]["score"] == 700


def test_estimate_joker_holo_before_effect() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Jolly Joker",
            "key": "j_jolly",
            "value": {},
            "modifier": {"edition": "HOLO"},
        },
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 20
    assert top[0]["score"] == 400


def test_estimate_joker_poly_after_xmult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Cavendish",
            "key": "j_cavendish",
            "value": {"rarity": "UNCOMMON"},
            "modifier": {"edition": "POLYCHROME"},
        },
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 9
    assert top[0]["score"] == 180


def test_estimate_joker_edition_on_per_card_joker() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Greedy Joker",
            "key": "j_greedy_joker",
            "value": {},
            "modifier": {"edition": "HOLO"},
        },
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 12
    assert top[0]["score"] == 240


def test_estimate_blueprint_edition_copies_effect() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Blueprint",
            "key": "j_blueprint",
            "value": {},
            "modifier": {"edition": "FOIL"},
        },
        {"label": "Jolly Joker", "key": "j_jolly", "value": {}},
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 70
    assert top[0]["mult"] == 18
    assert top[0]["score"] == 1260


def test_estimate_ice_cream_uses_stats_chips() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Ice Cream", "key": "j_ice_cream", "value": {"stats": {"chips": 100}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 120
    assert top[0]["score"] == 240


def test_estimate_popcorn_uses_stats_mult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Popcorn", "key": "j_popcorn", "value": {"stats": {"mult": 20}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 22
    assert top[0]["score"] == 440


def test_estimate_castle_uses_stats_chips() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Castle", "key": "j_castle", "value": {"stats": {"chips": 45}}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["chips"] == 65
    assert top[0]["score"] == 130


def test_estimate_red_card_uses_stats_mult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Red Card", "key": "j_red_card", "value": {"stats": {"mult": 9}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 11
    assert top[0]["score"] == 220


def test_estimate_trousers_zero_stats_grows_on_two_pair() -> None:
    hand = _hand_cards(
        ("K", "S", {}),
        ("K", "H", {}),
        ("5", "D", {}),
        ("5", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {
            "label": "Spare Trousers",
            "key": "j_trousers",
            "value": {"stats": {"mult": 0}},
        }
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Two Pair"
    assert top[0]["mult"] == 4
    assert top[0]["score"] == 200


def test_estimate_fortune_teller_uses_run_tarot_used() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Fortune Teller", "key": "j_fortune_teller", "value": {}}]
    state = _est_state(hand, jokers=jokers)
    state["run"] = {"tarot_used": 7}
    est = estimate.estimate(state)
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 9
    assert top[0]["score"] == 180


def test_estimate_swashbuckler_uses_stats_mult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Gros Michel", "key": "j_gros_michel", "value": {}},
        {
            "label": "Swashbuckler",
            "key": "j_swashbuckler",
            "value": {"stats": {"mult": 2}},
        },
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 19
    assert top[0]["score"] == 380


def test_estimate_madness_uses_stats_xmult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Madness", "key": "j_madness", "value": {"stats": {"x_mult": 1.5}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 3.0
    assert top[0]["score"] == 60


def test_estimate_smeared_greedy_counts_hearts_as_diamonds() -> None:
    hand = _hand_cards(
        ("K", "H", {}),
        ("K", "D", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Smeared Joker", "key": "j_smeared", "value": {}},
        {"label": "Greedy Joker", "key": "j_greedy_joker", "value": {}},
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 8
    assert top[0]["score"] == 240


def test_all_joker_keys_modeled() -> None:
    """Every OpenRPC / enums.lua joker key is registered in the estimate registry."""
    import re

    import estimate_jokers as ej  # type: ignore[unresolved-import]

    modeled_set, _ = ej._modeled([])
    root = Path(__file__).resolve().parents[2]
    rpc = json.loads((root / "src/lua/utils/openrpc.json").read_text())
    all_keys: set[str] = set()
    for comp in rpc.get("components", {}).get("schemas", {}).values():
        if isinstance(comp, dict) and comp.get("enum"):
            for v in comp["enum"]:
                if isinstance(v, str) and v.startswith("j_"):
                    all_keys.add(v)
    enum = set(
        re.findall(r'"(j_[a-z0-9_]+)"', (root / "src/lua/utils/enums.lua").read_text())
    )
    # Glance-time RNG score jokers — see estimate_registry.md § Player-uncertain
    score_rng = frozenset({"j_misprint", "j_bloodstone"})
    allowed_unmodeled = ej.NO_SCORE_JOKERS | score_rng
    missing = sorted((all_keys | enum) - set(modeled_set) - allowed_unmodeled)
    assert missing == []


def test_estimate_misprint_is_unmodeled() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Misprint", "key": "j_misprint", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    assert est["estimate"]["unmodeled_jokers"] == ["Misprint"]
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 2
    assert top[0]["score"] == 40


def test_estimate_bloodstone_is_unmodeled() -> None:
    hand = _hand_cards(
        ("5", "H", {}),
        ("5", "D", {}),
        ("3", "C", {}),
        ("7", "S", {}),
        ("2", "S", {}),
    )
    jokers = [{"label": "Bloodstone", "key": "j_bloodstone", "value": {}}]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    assert est["estimate"]["unmodeled_jokers"] == ["Bloodstone"]
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["score"] == 40


def test_estimate_caino_uses_stats_caino_xmult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Caino", "key": "j_caino", "value": {"stats": {"caino_xmult": 2.0}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 4.0
    assert top[0]["score"] == 80


def test_estimate_yorick_uses_stats_xmult() -> None:
    hand = _hand_cards(
        ("5", "S", {}),
        ("5", "H", {}),
        ("3", "D", {}),
        ("7", "C", {}),
        ("2", "S", {}),
    )
    jokers = [
        {"label": "Yorick", "key": "j_yorick", "value": {"stats": {"x_mult": 3.0}}}
    ]
    est = estimate.estimate(_est_state(hand, jokers=jokers))
    top = est["estimate"]["top"]
    assert top[0]["hand_type"] == "Pair"
    assert top[0]["mult"] == 6.0
    assert top[0]["score"] == 120

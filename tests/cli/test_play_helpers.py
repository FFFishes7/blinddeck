"""Unit tests for Play Helper JSON layer (no Balatro required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PLAY_ROOT = Path(__file__).resolve().parents[2] / "tools" / "play"
import sys  # noqa: E402

sys.path.insert(0, str(PLAY_ROOT))

import act  # noqa: E402  # type: ignore[unresolved-import]
from actions import build_actions  # noqa: E402  # type: ignore[unresolved-import]
from commands import (  # noqa: E402  # type: ignore[unresolved-import]
    build_params,
    normalize_sort_mode,
)
from envelope import (  # noqa: E402  # type: ignore[unresolved-import]
    build_play_envelope,
)
from layers import (  # noqa: E402  # type: ignore[unresolved-import]
    extract_query,
    filter_layer1,
)
from start_options import (  # noqa: E402  # type: ignore[unresolved-import]
    build_decks,
    build_stakes,
)
from view import (  # noqa: E402  # type: ignore[unresolved-import]
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
    }
    commands = {a["command"] for a in build_actions(shop_state)}
    assert {"buy", "reroll", "next_round", "sell", "use"}.issubset(commands)


def test_build_actions_blind_select(selecting_hand_state: dict) -> None:
    blind_state = {
        **selecting_hand_state,
        "state": "BLIND_SELECT",
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [{"label": "The Hermit", "key": "c_hermit"}],
        },
    }
    commands = {a["command"] for a in build_actions(blind_state)}
    assert {"select", "sell", "use"}.issubset(commands)


def test_build_actions_round_eval(selecting_hand_state: dict) -> None:
    round_eval_state = {
        **selecting_hand_state,
        "state": "ROUND_EVAL",
        "consumables": {
            "count": 1,
            "limit": 2,
            "cards": [{"label": "The Hermit", "key": "c_hermit"}],
        },
    }
    commands = {a["command"] for a in build_actions(round_eval_state)}
    assert {"cash_out", "sell", "use"}.issubset(commands)


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


# --- view.print_summary (one per state) -------------------------------------


def _envelope(raw: dict) -> dict:
    return build_play_envelope(raw, build_actions(raw))


def test_print_summary_menu(capsys: pytest.CaptureFixture[str]) -> None:
    print_summary(
        _envelope({"state": "MENU", "money": 0, "round_num": 0, "ante_num": 0})
    )
    out = capsys.readouterr().out
    assert "state=MENU" in out
    assert "start RED WHITE" in out


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
    assert "score=180/300" in out
    assert "K♠" in out
    assert "??" in out
    assert "jokers (1/5)" in out
    assert "Seltzer" in out
    assert "actions: play discard sort" in out


def test_print_summary_round_eval(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "ROUND_EVAL",
        "money": 12,
        "round_num": 1,
        "ante_num": 1,
        "deck": "RED",
        "stake": "WHITE",
        "round": {"hands_left": 2, "discards_left": 3, "chips": 500, "reroll_cost": 5},
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
    assert "cash_out" in out


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
    assert "pack[0] Arcana Pack" in out
    assert "actions:" in out


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
            "cards": [
                {
                    "label": "The Magician",
                    "key": "c_magician",
                    "value": {"effect": "convert 2 cards"},
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
    assert "actions: pack" in out


def test_print_summary_game_over(capsys: pytest.CaptureFixture[str]) -> None:
    raw = {
        "state": "GAME_OVER",
        "won": False,
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
    assert "menu" in out


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


# --- estimate.estimate ------------------------------------------------------

import estimate  # noqa: E402  # type: ignore[unresolved-import]


def _hand_cards(*ranks_suits: tuple[str, str, dict]) -> list[dict]:
    out = []
    for rank, suit, mod in ranks_suits:
        out.append(
            {
                "label": f"{rank} of {suit}",
                "value": {"rank": rank, "suit": suit},
                "modifier": mod,
            }
        )
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
) -> dict:
    return {
        "state": "SELECTING_HAND",
        "deck": deck,
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
    assert est["estimate"]["boss"]["flint_modeled"] is True


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
    assert top[0]["dusk_now"] is False
    assert est["estimate"]["dusk_now"] is False


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
    assert top[0]["dusk_now"] is True
    assert est["estimate"]["dusk_now"] is True

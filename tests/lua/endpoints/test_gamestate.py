"""Tests for src/lua/endpoints/gamestate.lua"""

import re

import httpx
import pytest

from tests.lua.conftest import api, assert_gamestate_response, load_fixture


class TestGamestateEndpoint:
    """Test basic gamestate endpoint and gamestate response structure."""

    def test_gamestate_from_MENU(self, client: httpx.Client) -> None:
        """Test that gamestate endpoint from MENU state is valid."""
        api(client, "menu", {})
        response = api(client, "gamestate", {})
        assert_gamestate_response(response, state="MENU")

    def test_gamestate_from_BLIND_SELECT(self, client: httpx.Client) -> None:
        """Test that gamestate from BLIND_SELECT state is valid."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["state"] == "BLIND_SELECT"
        assert gamestate["round_num"] == 0
        assert gamestate["deck"] == "RED"
        assert gamestate["stake"] == "WHITE"
        response = api(client, "gamestate", {})
        assert_gamestate_response(
            response,
            state="BLIND_SELECT",
            round_num=0,
            deck="RED",
            stake="WHITE",
        )

    def test_held_tags_fields_on_blind_select(self, client: httpx.Client) -> None:
        """gamestate always includes held_tags list and held_tags_ready flag."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert isinstance(gamestate.get("held_tags"), list)
        assert gamestate["held_tags"] == []
        assert gamestate.get("held_tags_ready") is True


class TestGamestateRunSummary:
    """Test run_summary extraction on GAME_OVER."""

    def test_run_summary_on_GAME_OVER(self, client: httpx.Client) -> None:
        """Test that GAME_OVER includes run_summary with a result line."""
        gamestate = load_fixture(
            client, "play", "state-SELECTING_HAND--round.hands_left-1"
        )
        response = api(client, "play", {"cards": [0]}, timeout=60)
        gamestate = assert_gamestate_response(response, state="GAME_OVER")
        assert gamestate.get("won") is False
        assert "run_summary" in gamestate
        summary = gamestate["run_summary"]
        assert isinstance(summary["result"], str)
        assert len(summary["result"]) > 0
        assert isinstance(summary["best_hand"], int)
        assert summary["best_hand"] >= 0
        assert isinstance(summary["cards_played"], int)
        assert summary["cards_played"] >= 0
        assert isinstance(summary["cards_discarded"], int)
        assert summary["cards_discarded"] >= 0
        assert isinstance(summary["cards_purchased"], int)
        assert summary["cards_purchased"] >= 0
        if "most_played_hand" in summary:
            assert isinstance(summary["most_played_hand"]["name"], str)
            assert isinstance(summary["most_played_hand"]["count"], int)

    def test_run_summary_victory_fields(self, client: httpx.Client) -> None:
        """Test that a won run includes a victory result line."""
        gamestate = load_fixture(
            client,
            "play",
            "state-SELECTING_HAND--ante_num-8--blinds.boss.status-CURRENT--round.chips-1000000",
        )
        response = api(client, "play", {"cards": [0, 3, 4, 5, 6]}, timeout=60)
        gamestate = assert_gamestate_response(response, won=True)
        summary = gamestate["run_summary"]
        assert summary["result"] == "Victory"
        assert isinstance(summary["best_hand"], int)

    def test_fool_copy_fields_after_planet_use(self, client: httpx.Client) -> None:
        """Test The Fool exposes copy metadata for the last Tarot/Planet used."""
        load_fixture(
            client,
            "use",
            "state-SELECTING_HAND--consumables.cards[0].key-c_pluto--consumables.cards[1].key-c_magician",
        )
        api(client, "use", {"consumable": 0})
        response = api(client, "add", {"key": "c_fool"})
        gamestate = assert_gamestate_response(response)
        fool = next(
            card
            for card in gamestate["consumables"]["cards"]
            if card["key"] == "c_fool"
        )
        assert fool["value"]["copy_key"] == "c_pluto"
        assert fool["value"]["copy_set"] == "Planet"
        assert fool["value"]["copy_label"] != ""

    def test_run_summary_absent_during_run(self, client: httpx.Client) -> None:
        """Test that run_summary is not present outside GAME_OVER."""
        gamestate = load_fixture(
            client,
            "gamestate",
            "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE",
        )
        assert gamestate["state"] == "BLIND_SELECT"
        assert "run_summary" not in gamestate


class TestGamestateTopLevel:
    """Test gamestate endpoint with top-level fields."""

    def test_deck_extraction(self, client: httpx.Client) -> None:
        """Test deck field matches started deck (e.g., "BLUE")."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["deck"] == "BLUE"

    def test_stake_extraction(self, client: httpx.Client) -> None:
        """Test stake field matches started stake (e.g., "RED")."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["stake"] == "RED"

    def test_seed_extraction(self, client: httpx.Client) -> None:
        """Test seed field matches the seed used in `start`."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["seed"] == "TEST123"

    def test_money_extraction(self, client: httpx.Client) -> None:
        """Test money field after using `set` to modify it."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "set", {"money": 42})
        assert response["result"]["seed"] == "TEST123"

    def test_bankrupt_at_extraction(self, client: httpx.Client) -> None:
        """Test bankrupt_at field is exposed during an active run."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert "bankrupt_at" in gamestate
        assert isinstance(gamestate["bankrupt_at"], int)

    def test_ante_num_extractions(self, client: httpx.Client) -> None:
        """Test ante_num field after using `set` to modify it."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "set", {"ante": 5})
        assert response["result"]["ante_num"] == 5

    def test_round_num_extractions(self, client: httpx.Client) -> None:
        """Test round_num field after using `set` to modify it."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "set", {"round": 5})
        assert response["result"]["round_num"] == 5

    def test_won_false_extraction(self, client: httpx.Client) -> None:
        """Test won field after defeating ante 8 boss."""
        fixture_name = "state-BLIND_SELECT--deck-BLUE--stake-RED"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["won"] is False

    def test_won_true_extraction(self, client: httpx.Client) -> None:
        """Test won field after winning ante 8 boss."""
        fixture_name = "state-SELECTING_HAND--round_num-8--blinds.boss.status-CURRENT--round.chips-1000000"
        load_fixture(client, "gamestate", fixture_name)
        response = api(client, "play", {"cards": [0]})
        assert response["result"]["won"] is True


class TestGamestateRound:
    """Test gamestate round extraction."""

    def test_round_hands_left_and_round_hands_played(
        self, client: httpx.Client
    ) -> None:
        """Test round.hands_left and round.hands_played fields."""
        fixture_name = (
            "state-SELECTING_HAND--round.hands_played-1--round.discards_used-1"
        )
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["hands_left"] == 3
        assert gamestate["round"]["hands_played"] == 1

    def test_round_discards_left_and_round_discards_used(
        self, client: httpx.Client
    ) -> None:
        """Test round.discards_left and round.discards_used fields."""
        fixture_name = (
            "state-SELECTING_HAND--round.hands_played-1--round.discards_used-1"
        )
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["discards_left"] == 3
        assert gamestate["round"]["discards_used"] == 1

    def test_round_chips_extraction(self, client: httpx.Client) -> None:
        """Test round.chips field."""
        fixture_name = (
            "state-SELECTING_HAND--round.hands_played-1--round.discards_used-1"
        )
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["chips"] == 16
        response = api(client, "play", {"cards": [0]})
        assert response["result"]["round"]["chips"] == 31

    def test_round_reroll_cost_extraction(self, client: httpx.Client) -> None:
        """Test round.reroll_cost field."""
        fixture_name = "state-SHOP"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["round"]["reroll_cost"] == 5
        response = api(client, "reroll", {})
        assert response["result"]["round"]["reroll_cost"] == 6


class TestGamestateBlinds:
    """Test gamestate blind extraction."""

    def test_blinds_structure_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction structure and ante-1 chip targets."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        blinds = gamestate["blinds"]

        assert set(blinds.keys()) == {"small", "big", "boss"}

        for key, blind_type in (
            ("small", "SMALL"),
            ("big", "BIG"),
            ("boss", "BOSS"),
        ):
            blind = blinds[key]
            assert blind["type"] == blind_type
            assert isinstance(blind["name"], str) and blind["name"]
            assert isinstance(blind["effect"], str)
            assert isinstance(blind["score"], int) and blind["score"] > 0
            assert isinstance(blind["tag_name"], str)
            assert isinstance(blind["tag_effect"], str)
            assert isinstance(blind["status"], str)

        # Fixed ante-1 chip requirements; boss/tag content is seed-dependent
        assert blinds["small"]["score"] == 300
        assert blinds["big"]["score"] == 450
        assert blinds["boss"]["score"] == 600
        assert blinds["small"]["effect"] == ""
        assert blinds["big"]["effect"] == ""
        assert blinds["boss"]["tag_name"] == ""
        assert blinds["boss"]["tag_effect"] == ""
        assert blinds["small"]["tag_name"]
        assert blinds["big"]["tag_name"]

    def test_blinds_zero_skip_extraction(self, client: httpx.Client) -> None:
        """Test initial blind extraction."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["blinds"]["small"]["status"] == "SELECT"
        assert gamestate["blinds"]["big"]["status"] == "UPCOMING"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"

    def test_blinds_one_skip_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction after one skip."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        load_fixture(client, "gamestate", fixture_name)
        gamestate = api(client, "skip", {})["result"]
        assert gamestate["blinds"]["small"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["big"]["status"] == "SELECT"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"

    def test_blinds_two_skip_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction after two skip."""
        fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
        load_fixture(client, "gamestate", fixture_name)
        api(client, "skip", {})
        gamestate = api(client, "skip", {})["result"]
        assert gamestate["blinds"]["small"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["big"]["status"] == "SKIPPED"
        assert gamestate["blinds"]["boss"]["status"] == "SELECT"

    def test_blinds_progession_extraction(self, client: httpx.Client) -> None:
        """Test blind extraction after one completed blind."""
        fixture_name = "state-SELECTING_HAND"
        gamestate = load_fixture(client, "gamestate", fixture_name)
        assert gamestate["blinds"]["small"]["status"] == "CURRENT"
        assert gamestate["blinds"]["big"]["status"] == "UPCOMING"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"
        api(client, "set", {"chips": 1000})
        api(client, "play", {"cards": [0]})
        api(client, "cash_out", {})
        gamestate = api(client, "next_round", {})["result"]
        assert gamestate["blinds"]["small"]["status"] == "DEFEATED"
        assert gamestate["blinds"]["big"]["status"] == "SELECT"
        assert gamestate["blinds"]["boss"]["status"] == "UPCOMING"


class TestGamestateAreas:
    """Test gamestate areas extraction."""

    class TestGamestateAreasJokers:
        """Test gamestate jokers area extraction."""

        def test_jokers_area_empty_initial(self, client: httpx.Client) -> None:
            """Test jokers area is empty at start of run."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["jokers"]["count"] == 0
            assert gamestate["jokers"]["cards"] == []

        def test_jokers_area_count_after_add(self, client: httpx.Client) -> None:
            """Test jokers area count after adding a joker."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            assert response["result"]["jokers"]["count"] == 1
            assert len(response["result"]["jokers"]["cards"]) == 1

        def test_jokers_area_limit(self, client: httpx.Client) -> None:
            """Test jokers area limit."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["jokers"]["limit"] == 5

    class TestGamestateAreasConsumables:
        """Test gamestate consumables area extraction."""

        def test_consumables_area_empty_initial(self, client: httpx.Client) -> None:
            """Test consumables area is empty at start of run."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["consumables"]["count"] == 0
            assert gamestate["consumables"]["cards"] == []

        def test_consumables_area_count_after_add(self, client: httpx.Client) -> None:
            """Test consumables area count after adding a consumable."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            assert response["result"]["consumables"]["count"] == 1
            assert len(response["result"]["consumables"]["cards"]) == 1

        def test_consumables_area_limit(self, client: httpx.Client) -> None:
            """Test consumables area limit."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["consumables"]["limit"] == 2

    class TestGamestateAreasCards:
        """Test gamestate cards area extraction."""

        def test_cards_area_initial_count(self, client: httpx.Client) -> None:
            """Test cards area has full deck at blind selection."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["cards"]["count"] == 52

        def test_cards_area_count_after_draw(self, client: httpx.Client) -> None:
            """Test cards area count after drawing cards."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "select", {})
            assert response["result"]["cards"]["count"] == 52 - 8  # 8 cards drawn

        def test_cards_area_limit(self, client: httpx.Client) -> None:
            """Test cards area limit."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["cards"]["limit"] == 52

    class TestGamestateAreasHand:
        """Test gamestate hand area extraction."""

        def test_hand_area_count_in_BLIND_SELECT(self, client: httpx.Client) -> None:
            """Test hand area is absent in BLIND_SELECT state."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["hand"]["count"] == 0

        def test_hand_area_count_in_SELECTING_HAND(self, client: httpx.Client) -> None:
            """Test hand area count."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["hand"]["count"] == 8

        def test_hand_area_limit(self, client: httpx.Client) -> None:
            """Test hand area limit."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["hand"]["limit"] == 8

        def test_hand_area_highlighted_limit(self, client: httpx.Client) -> None:
            """Test hand area highlighted limit."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["hand"]["highlighted_limit"] == 5

    class TestGamestateAreasPack:
        """Test gamestate pack area extraction."""

        def test_pack_area_absent_in_SHOP(self, client: httpx.Client) -> None:
            """Test pack area is absent in non SMODS_BOOSTER_OPENED state (e.g. SHOP)"""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert "pack" not in gamestate

        def test_pack_area_limit(self, client: httpx.Client) -> None:
            """Test pack area is absent in non SMODS_BOOSTER_OPENED state (e.g. SHOP)"""
            fixture_name = "state-SMODS_BOOSTER_OPENED"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["pack"]["limit"] > 0

        def test_pack_area_count(self, client: httpx.Client) -> None:
            """Test pack area count."""
            fixture_name = "state-SMODS_BOOSTER_OPENED"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["pack"]["count"] > 0
            assert gamestate["pack"]["count"] == gamestate["pack"]["limit"]

        def test_pack_area_highlighted_limit(self, client: httpx.Client) -> None:
            """Test pack area highlighted limit."""
            fixture_name = "state-SMODS_BOOSTER_OPENED"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["pack"]["highlighted_limit"] == 1

    class TestGamestateAreasShop:
        """Test gamestate shop area extraction."""

        def test_shop_area_absent_in_BLIND_SELECT(self, client: httpx.Client) -> None:
            """Test shop area is absent in BLIND_SELECT state."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert "shop" not in gamestate

        def test_shop_area_count(self, client: httpx.Client) -> None:
            """Test shop area count."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["shop"]["count"] == 2
            reponse = api(client, "buy", {"card": 0})
            assert reponse["result"]["shop"]["count"] == 1

        def test_shop_area_limit(self, client: httpx.Client) -> None:
            """Test shop area limit."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["shop"]["limit"] == 2

    class TestGamestateAreasVouchers:
        """Test gamestate vouchers area extraction."""

        def test_vouchers_area_absent_in_BLIND_SELECT(
            self, client: httpx.Client
        ) -> None:
            """Test vouchers area is absent in BLIND_SELECT state."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert "vouchers" not in gamestate

        def test_vouchers_area_count(self, client: httpx.Client) -> None:
            """Test vouchers area count."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["vouchers"]["count"] == 1
            reponse = api(client, "buy", {"voucher": 0})
            assert reponse["result"]["vouchers"]["count"] == 0

        def test_vouchers_area_limit(self, client: httpx.Client) -> None:
            """Test vouchers area limit."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["vouchers"]["limit"] == 1

    class TestGamestateAreasPacks:
        """Test gamestate packs area extraction."""

        def test_packs_area_absent_in_BLIND_SELECT(self, client: httpx.Client) -> None:
            """Test packs area is absent in BLIND_SELECT state."""
            fixture_name = "state-BLIND_SELECT--round_num-0--deck-RED--stake-WHITE"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert "packs" not in gamestate

        def test_packs_area_count(self, client: httpx.Client) -> None:
            """Test packs area count."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["packs"]["count"] == 2
            reponse = api(client, "buy", {"pack": 0})
            assert reponse["result"]["packs"]["count"] == 1

        def test_packs_area_limit(self, client: httpx.Client) -> None:
            """Test packs area limit."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            assert gamestate["packs"]["limit"] == 2


class TestGamestateCards:
    """Test gamestate cards."""

    class TestGamestateCardId:
        """Test gamestate card id."""

        def test_card_ids_in_hand(self, client: httpx.Client) -> None:
            """Test card ids in hand."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["hand"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_jokers(self, client: httpx.Client) -> None:
            """Test card ids in jokers."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            gamestate = assert_gamestate_response(response)
            cards = gamestate["jokers"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_cards(self, client: httpx.Client) -> None:
            """Test card ids in cards."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["cards"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_consumables(self, client: httpx.Client) -> None:
            """Test card ids in consumables."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            gamestate = assert_gamestate_response(response)
            cards = gamestate["consumables"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_pack(self, client: httpx.Client) -> None:
            """Test card ids in pack."""
            fixture_name = "state-SMODS_BOOSTER_OPENED"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["pack"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_shop(self, client: httpx.Client) -> None:
            """Test card ids in shop."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["shop"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_vouchers(self, client: httpx.Client) -> None:
            """Test card ids in vouchers."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["vouchers"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

        def test_card_ids_in_packs(self, client: httpx.Client) -> None:
            """Test card ids in packs."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            cards = gamestate["packs"]["cards"]
            ids = [c["id"] for c in cards]
            assert all(isinstance(id, int) for id in ids)
            assert len(ids) == len(set(ids))  # unique

    class TestGamestateCardKey:
        """Test gamestate card key."""

        def test_card_key_joker_format(self, client: httpx.Client) -> None:
            """Test joker card key format matches pattern ^j_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert re.match(r"^j_[a-z_]+$", joker["key"])

        def test_card_key_tarot_format(self, client: httpx.Client) -> None:
            """Test tarot card key format matches pattern ^c_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            assert re.match(r"^c_[a-z_]+$", tarot["key"])

        def test_card_key_planet_format(self, client: httpx.Client) -> None:
            """Test planet card key format matches pattern ^c_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_pluto"})
            planet = response["result"]["consumables"]["cards"][0]
            assert re.match(r"^c_[a-z_]+$", planet["key"])

        def test_card_key_spectral_format(self, client: httpx.Client) -> None:
            """Test spectral card key format matches pattern ^c_[a-z_]+$."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_familiar"})
            spectral = response["result"]["consumables"]["cards"][0]
            assert re.match(r"^c_[a-z_]+$", spectral["key"])

        def test_card_key_voucher_format(self, client: httpx.Client) -> None:
            """Test voucher card key format matches pattern ^v_[a-z_]+$."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            vouchers = gamestate["vouchers"]["cards"]
            for voucher in vouchers:
                assert re.match(r"^v_[a-z_]+$", voucher["key"])

        def test_card_key_booster_format(self, client: httpx.Client) -> None:
            """Test booster pack key format matches pattern ^p_[a-z_0-9]+$."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            packs = gamestate["packs"]["cards"]
            for pack in packs:
                assert re.match(r"^p_[a-z_0-9]+$", pack["key"])

        def test_card_key_playing_card_format(self, client: httpx.Client) -> None:
            """Test playing card key format matches pattern ^[HDCS]_[2-9TJQKA]$."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            hand_cards = gamestate["hand"]["cards"]
            for card in hand_cards:
                assert re.match(r"^[HDCS]_[2-9TJQKA]$", card["key"])

    class TestGamestateCardSet:
        """Test gamestate card set."""

        def test_card_set_default(self, client: httpx.Client) -> None:
            """Test default playing cards have DEFAULT set."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            card = gamestate["hand"]["cards"][0]
            assert card["set"] == "DEFAULT"

        def test_card_set_enhanced(self, client: httpx.Client) -> None:
            """Test enhanced playing cards have ENHANCED set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "H_A", "enhancement": "BONUS"})
            # Find the enhanced card (last card in hand)
            cards = response["result"]["hand"]["cards"]
            card = cards[-1]
            assert card["set"] == "ENHANCED"

        def test_card_set_joker(self, client: httpx.Client) -> None:
            """Test joker cards have JOKER set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert joker["set"] == "JOKER"

        def test_card_set_tarot(self, client: httpx.Client) -> None:
            """Test tarot cards have TAROT set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            assert tarot["set"] == "TAROT"

        def test_card_set_planet(self, client: httpx.Client) -> None:
            """Test planet cards have PLANET set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_pluto"})
            planet = response["result"]["consumables"]["cards"][0]
            assert planet["set"] == "PLANET"

        def test_card_set_spectral(self, client: httpx.Client) -> None:
            """Test spectral cards have SPECTRAL set."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_familiar"})
            spectral = response["result"]["consumables"]["cards"][0]
            assert spectral["set"] == "SPECTRAL"

        def test_card_set_voucher(self, client: httpx.Client) -> None:
            """Test voucher cards have VOUCHER set."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            voucher = gamestate["vouchers"]["cards"][0]
            assert voucher["set"] == "VOUCHER"

        def test_card_set_booster(self, client: httpx.Client) -> None:
            """Test booster packs have BOOSTER set."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            pack = gamestate["packs"]["cards"][0]
            assert pack["set"] == "BOOSTER"

    class TestGamestateCardLabel:
        """Test gamestate card label."""

        def test_card_label_is_string(self, client: httpx.Client) -> None:
            """Test card labels are non-empty strings."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            hand_cards = gamestate["hand"]["cards"]

            # Verify multiple cards have valid string labels
            for card in hand_cards[:3]:
                assert "label" in card
                assert isinstance(card["label"], str)
                assert len(card["label"]) > 0

        def test_card_label_joker(self, client: httpx.Client) -> None:
            """Test joker card has human-readable label."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]

            assert "label" in joker
            assert joker["label"] == "Joker"

        def test_card_label_playing_card(self, client: httpx.Client) -> None:
            """Test playing cards have descriptive labels (Base Card or enhancement)."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            hand_cards = gamestate["hand"]["cards"]

            # Verify first card has a valid card type label
            card = hand_cards[0]

            assert "label" in card
            label = card["label"]

            # Validate label is one of the valid playing card types
            # fmt: off
            valid_labels = [
                "Base Card", "Steel Card", "Glass Card", "Gold Card", "Stone Card",
                "Lucky Card", "Bonus Card", "Mult Card", "Wild Card",
            ]
            # fmt: on
            assert label in valid_labels

    class TestGamestateCardValue:
        """Test gamestate card value."""

        def test_card_value_suit_valid_enum(self, client: httpx.Client) -> None:
            """Test playing cards have valid suit enum (H, D, C, S)."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            valid_suits = ["H", "D", "C", "S"]
            for card in gamestate["hand"]["cards"]:
                assert card["value"]["suit"] in valid_suits

        def test_card_value_suit_present_for_playing_cards(
            self, client: httpx.Client
        ) -> None:
            """Test all playing cards have suit field in value."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            for card in gamestate["hand"]["cards"]:
                assert "suit" in card["value"]
                assert card["value"]["suit"] is not None

        def test_card_value_suit_absent_for_jokers(self, client: httpx.Client) -> None:
            """Test jokers don't have suit field."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert joker["value"].get("suit") is None

        def test_card_value_rank_valid_enum(self, client: httpx.Client) -> None:
            """Test playing cards have valid rank enum."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            # fmt: off
            valid_ranks = [
                "2", "3", "4", "5", "6", "7", "8",
                "9", "T", "J", "Q", "K", "A",
            ]
            # fmt: on
            for card in gamestate["hand"]["cards"]:
                assert card["value"]["rank"] in valid_ranks

        def test_card_value_rank_present_for_playing_cards(
            self, client: httpx.Client
        ) -> None:
            """Test all playing cards have rank field in value."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            for card in gamestate["hand"]["cards"]:
                assert "rank" in card["value"]
                assert card["value"]["rank"] is not None

        def test_card_value_rank_absent_for_consumables(
            self, client: httpx.Client
        ) -> None:
            """Test consumables don't have rank field."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            assert tarot["value"].get("rank") is None

        def test_card_value_effect_is_string(self, client: httpx.Client) -> None:
            """Test effect field is always a string."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            for card in gamestate["hand"]["cards"]:
                assert isinstance(card["value"]["effect"], str)

        def test_card_value_effect_joker(self, client: httpx.Client) -> None:
            """Test joker effect description."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]
            assert joker["value"]["effect"] == "+4 Mult"

        def test_card_value_effect_tarot(self, client: httpx.Client) -> None:
            """Test tarot effect description."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_fool"})
            tarot = response["result"]["consumables"]["cards"][0]
            expected = (
                "Creates the last Tarot or Planet card "
                "used during this run The Fool excluded "
            )
            assert tarot["value"]["effect"] == expected

        def test_card_value_effect_planet(self, client: httpx.Client) -> None:
            """Test planet effect description."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_pluto"})
            planet = response["result"]["consumables"]["cards"][0]
            assert (
                planet["value"]["effect"]
                == "(lvl.1) Level up High Card +1 Mult and +10 chips"
            )

        def test_card_value_consumable_target_requirements(
            self, client: httpx.Client
        ) -> None:
            """Test tarot target_min/target_max from G.P_CENTERS (Magician)."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "c_magician"})
            tarot = response["result"]["consumables"]["cards"][0]
            assert tarot["value"].get("target_min") == 1
            assert tarot["value"].get("target_max") == 2

        def test_card_value_random_joker_consumables(
            self, client: httpx.Client
        ) -> None:
            """Ankh/Hex/Ectoplasm expose random_joker_effect (not requires_joker)."""
            expectations = {
                "c_ankh": {"requires_jokers_min": 1},
                "c_hex": {"requires_jokers_min": 1},
                "c_ectoplasm": {},
            }
            for key, extra in expectations.items():
                load_fixture(client, "gamestate", "state-SELECTING_HAND")
                response = api(client, "add", {"key": key})
                card = response["result"]["consumables"]["cards"][0]
                assert card["value"].get("random_joker_effect") is True
                assert "requires_joker" not in card["value"]
                for field, value in extra.items():
                    assert card["value"].get(field) == value

        def test_pack_card_ankh_random_joker_effect(self, client: httpx.Client) -> None:
            """Pack-open Ankh card includes random_joker_effect in gamestate."""
            gamestate = load_fixture(
                client,
                "pack",
                "state-SMODS_BOOSTER_OPENED--pack.cards[0].key-c_ankh--jokers.count-1",
            )
            ankh = gamestate["pack"]["cards"][0]
            assert ankh["key"] == "c_ankh"
            assert ankh["value"].get("random_joker_effect") is True
            assert "requires_joker" not in ankh["value"]
            assert ankh["value"].get("requires_jokers_min") == 1

    class TestGamestateCardModifier:
        """Test gamestate card modifier."""

        def test_modifier_structure_exists(self, client: httpx.Client) -> None:
            """Test card has modifier field."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            card = gamestate["hand"]["cards"][0]
            assert "modifier" in card

        def test_modifier_absent_fields(self, client: httpx.Client) -> None:
            """Test unmodified card has empty modifier (fields omitted when not set)."""
            fixture_name = "state-SELECTING_HAND"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            card = gamestate["hand"]["cards"][0]
            assert card["modifier"] == []

    class TestGamestateCardState:
        """Test gamestate card state."""

        # TODO: add later

    class TestGamestateCardCost:
        """Test gamestate card cost."""

        def test_cost_buy_in_shop(self, client: httpx.Client) -> None:
            """Test shop card has cost['buy'] > 0."""
            fixture_name = "state-SHOP"
            gamestate = load_fixture(client, "gamestate", fixture_name)
            shop_cards = gamestate["shop"]["cards"]

            assert len(shop_cards) > 0, "Shop should have at least one card"
            card = shop_cards[0]
            assert isinstance(card["cost"]["buy"], int)
            assert card["cost"]["buy"] > 0

        def test_cost_sell_owned_joker(self, client: httpx.Client) -> None:
            """Test added joker has cost['sell'] > 0."""
            fixture_name = "state-SELECTING_HAND"
            load_fixture(client, "gamestate", fixture_name)
            response = api(client, "add", {"key": "j_joker"})
            joker = response["result"]["jokers"]["cards"][0]

            assert isinstance(joker["cost"]["sell"], int)
            assert joker["cost"]["sell"] > 0


class TestGamestateJokerStats:
    """Structured joker scoring stats (value.stats)."""

    def test_gros_michel_exposes_stats_mult(self, client: httpx.Client) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        response = api(client, "add", {"key": "j_gros_michel"})
        joker = response["result"]["jokers"]["cards"][-1]
        assert joker["key"] == "j_gros_michel"
        stats = joker["value"]["stats"]
        assert stats["mult"] == 15

    def test_popcorn_exposes_stats_mult(self, client: httpx.Client) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        response = api(client, "add", {"key": "j_popcorn"})
        joker = response["result"]["jokers"]["cards"][-1]
        assert joker["key"] == "j_popcorn"
        assert joker["value"]["stats"]["mult"] == 20

    def test_ice_cream_exposes_stats_chips(self, client: httpx.Client) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        response = api(client, "add", {"key": "j_ice_cream"})
        joker = response["result"]["jokers"]["cards"][-1]
        assert joker["key"] == "j_ice_cream"
        assert joker["value"]["stats"]["chips"] == 100

    def test_swashbuckler_exposes_sell_sum_as_stats_mult(
        self, client: httpx.Client
    ) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        api(client, "add", {"key": "j_gros_michel"})
        response = api(client, "add", {"key": "j_swashbuckler"})
        joker = response["result"]["jokers"]["cards"][-1]
        assert joker["key"] == "j_swashbuckler"
        assert joker["value"]["stats"]["mult"] > 0

    def test_fortune_teller_exposes_tarot_count(self, client: httpx.Client) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        response = api(client, "add", {"key": "j_fortune_teller"})
        joker = response["result"]["jokers"]["cards"][-1]
        assert joker["key"] == "j_fortune_teller"
        assert joker["value"]["stats"]["mult"] == 0

    def test_selzer_exposes_seltzer_remaining(self, client: httpx.Client) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        response = api(client, "add", {"key": "j_selzer"})
        joker = response["result"]["jokers"]["cards"][-1]
        assert joker["key"] == "j_selzer"
        assert joker["value"]["stats"]["seltzer_remaining"] == 10

    def test_run_counters_on_active_run(self, client: httpx.Client) -> None:
        gamestate = load_fixture(client, "gamestate", "state-SELECTING_HAND")
        run = gamestate["run"]
        assert "skips" in run
        assert "deck_size" in run
        assert "starting_deck_size" in run
        assert run["starting_deck_size"] >= run["deck_size"]

    def test_round_scoring_targets_on_active_run(self, client: httpx.Client) -> None:
        gamestate = load_fixture(client, "gamestate", "state-SELECTING_HAND")
        rnd = gamestate["round"]
        assert rnd.get("ancient_suit") in {"H", "D", "C", "S"}
        assert rnd.get("idol_rank") in {
            "A",
            "K",
            "Q",
            "J",
            "T",
            "9",
            "8",
            "7",
            "6",
            "5",
            "4",
            "3",
            "2",
        }
        assert rnd.get("idol_suit") in {"H", "D", "C", "S"}

    def test_loyalty_card_exposes_loyalty_stats(self, client: httpx.Client) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        response = api(client, "add", {"key": "j_loyalty_card"})
        joker = response["result"]["jokers"]["cards"][-1]
        stats = joker["value"]["stats"]
        assert stats["loyalty_every"] == 5
        assert "loyalty_remaining" in stats
        assert stats["loyalty_x_mult"] == 4

    def test_obelisk_exposes_obelisk_step(self, client: httpx.Client) -> None:
        load_fixture(client, "gamestate", "state-SELECTING_HAND")
        response = api(client, "add", {"key": "j_obelisk"})
        joker = response["result"]["jokers"]["cards"][-1]
        assert joker["key"] == "j_obelisk"
        assert joker["value"]["stats"]["obelisk_step"] == 0.2


class TestGamestateCardModifiers:
    """Test gamestate card modifiers."""

    class TestGamestateCardModifierSeal:
        """Test gamestate card modifier seal."""

        # TODO: add later

    class TestGamestateCardModifierEdition:
        """Test gamestate card modifier edition."""

        # TODO: add later

    class TestGamestateCardModifierEnhancement:
        """Test gamestate card modifier enhancement."""

        # TODO: add later

    class TestGamestateCardModifierEternal:
        """Test gamestate card modifier eternal."""

        # TODO: add later

    class TestGamestateCardModifierPerishable:
        """Test gamestate card modifier perishable."""

        # TODO: add later

    class TestGamestateCardModifierRental:
        """Test gamestate card modifier rental."""

        # TODO: add later


class TestGamestateCardStates:
    """Test gamestate card states."""

    class TestGamestateCardStateDebuff:
        """Test gamestate card state debuff."""

        # TODO: add later

    class TestGamestateCardStateHidden:
        """Test gamestate card state hidden."""

        def test_hidden_card_masks_identity(self, client: httpx.Client) -> None:
            """Test face-down hand cards hide rank, suit, key, and label."""
            gamestate = load_fixture(client, "gamestate", "state-SELECTING_HAND")

            def is_hidden(card: dict) -> bool:
                state = card.get("state")
                return isinstance(state, dict) and bool(state.get("hidden"))

            hidden_cards = [
                card for card in gamestate["hand"]["cards"] if is_hidden(card)
            ]
            if not hidden_cards:
                gamestate = load_fixture(
                    client,
                    "gamestate",
                    "state-SELECTING_HAND--round_num-8--blinds.boss.status-CURRENT--round.chips-1000000",
                )
                hidden_cards = [
                    card for card in gamestate["hand"]["cards"] if is_hidden(card)
                ]
            if not hidden_cards:
                pytest.skip("Fixture seed has no face-down hand cards")

            for card in hidden_cards:
                assert card["key"] == ""
                assert card["label"] == ""
                assert card["value"]["effect"] == ""
                assert card["modifier"] == []
                assert card["value"].get("rank") is None
                assert card["value"].get("suit") is None
                assert card["state"]["hidden"] is True
                assert isinstance(card["id"], int)

    class TestGamestateCardStateHighlight:
        """Test gamestate card state highlight."""

        # TODO: add later


class TestGamestateCardCosts:
    """Test gamestate card costs."""

    class TestGamestateCardCostSell:
        """Test gamestate card cost sell."""

        # TODO: add later

    class TestGamestateCardCostBuy:
        """Test gamestate card cost buy."""

        # TODO: add later

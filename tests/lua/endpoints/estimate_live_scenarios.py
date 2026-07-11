"""Multi-joker interaction live scenarios: order-sensitive estimate == play."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.lua.endpoints.estimate_live_recipes import (
    FIVE_WILD_KINGS,
    PAIR_5,
    PAIR_J,
    STRAIGHT_5,
    WILD_DEBUFF_FLUSH,
    CardAdd,
    JokerAdd,
)

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioLine:
    line_id: str
    play_order_cards: tuple[CardAdd, ...] | None = None
    pick: str = ""
    joker_order: tuple[int, ...] | None = None
    joker_order_specs: tuple[JokerAdd, ...] | None = None
    hand_order: str = ""  # "", "queen_left", "queen_right", "two_left", "two_right"
    cards: tuple[CardAdd, ...] | None = None
    joker_keys: tuple[str, ...] | None = None
    jokers: tuple[JokerAdd, ...] | None = None
    set_state: dict[str, Any] = field(default_factory=dict)
    debuff: tuple[CardAdd, ...] = ()
    expect_lower_than_optimal: bool = False


@dataclass(frozen=True)
class ScenarioRecipe:
    scenario_id: str
    description: str
    category: str
    joker_keys: tuple[str, ...] = ()
    jokers: tuple[JokerAdd, ...] = ()
    cards: tuple[CardAdd, ...] = ()
    set_state: dict[str, Any] = field(default_factory=dict)
    debuff: tuple[CardAdd, ...] = ()
    lines: tuple[ScenarioLine, ...] = ()
    check_unmodeled: bool = True


# Shared card bundles
STEEL_RED_K = CardAdd("H_K", enhancement="STEEL", seal="RED")
STEEL_K = CardAdd("D_K", enhancement="STEEL")
PLAIN_K = CardAdd("H_K")
GLASS_J = CardAdd("H_J", enhancement="GLASS")
GLASS_RED_J = CardAdd("H_J", enhancement="GLASS", seal="RED")
POLY_J = CardAdd("H_J", edition="POLYCHROME")
MULT_5 = CardAdd("S_5", enhancement="MULT")
GLASS_5 = CardAdd("D_5", enhancement="GLASS")
BONUS_FOIL_5 = CardAdd("S_5", enhancement="BONUS", edition="FOIL")
MULT_HOLO_J = CardAdd("H_J", enhancement="MULT", edition="HOLO")
STONE_CARD = CardAdd("S_2", enhancement="STONE")
RETRIGGER_BUFF = CardAdd("S_4", enhancement="GLASS", seal="RED")
BLACKBOARD_HAND = (
    CardAdd("S_K"),
    CardAdd("C_Q"),
    CardAdd("H_J"),
    CardAdd("S_T"),
    CardAdd("S_8"),
    CardAdd("D_8"),
    CardAdd("H_5"),
    CardAdd("C_5"),
)

FACE_LINE = (
    CardAdd("H_J"),
    CardAdd("S_Q"),
    CardAdd("D_K"),
    CardAdd("C_K"),
    CardAdd("S_2"),
)


def _negative_first(jokers: tuple[JokerAdd, ...]) -> tuple[JokerAdd, ...]:
    """Add Negative jokers first so every later physical card fits legally."""
    return tuple(j for j in jokers if j.edition == "NEGATIVE") + tuple(
        j for j in jokers if j.edition != "NEGATIVE"
    )


MEGA_FACE_CARDS = (
    CardAdd("S_J", edition="FOIL"),
    GLASS_RED_J,
    MULT_HOLO_J,
    CardAdd("D_J", enhancement="BONUS", edition="FOIL"),
    CardAdd("C_J", enhancement="WILD", edition="POLYCHROME"),
)
MEGA_FACE_NO_RED = (
    CardAdd("S_J", edition="FOIL"),
    GLASS_J,
    MULT_HOLO_J,
    CardAdd("D_J", enhancement="BONUS", edition="FOIL"),
    CardAdd("C_J", enhancement="WILD", edition="POLYCHROME"),
)
MEGA_FACE_JOKERS = (
    JokerAdd("j_photograph", edition="HOLO"),
    JokerAdd("j_brainstorm", edition="NEGATIVE"),
    JokerAdd("j_blueprint", edition="NEGATIVE"),
    JokerAdd("j_hanging_chad", edition="FOIL"),
    JokerAdd("j_sock_and_buskin", edition="POLYCHROME"),
    JokerAdd("j_smiley", edition="NEGATIVE"),
    JokerAdd("j_scary_face", edition="NEGATIVE"),
    JokerAdd("j_dusk", edition="NEGATIVE"),
    JokerAdd("j_selzer", edition="NEGATIVE"),
    JokerAdd("j_jolly", edition="FOIL"),
    JokerAdd("j_crafty", edition="NEGATIVE"),
    JokerAdd("j_cavendish", edition="POLYCHROME"),
)

MEGA_HELD_CARDS = (
    CardAdd("H_5", enhancement="GLASS"),
    CardAdd("D_5", enhancement="MULT"),
    CardAdd("S_K", enhancement="STEEL", seal="RED"),
    CardAdd("C_K", enhancement="STEEL"),
    CardAdd("S_Q", enhancement="STEEL"),
)
MEGA_HELD_PLAIN_KINGS = (
    CardAdd("H_5", enhancement="GLASS"),
    CardAdd("D_5", enhancement="MULT"),
    CardAdd("S_K"),
    CardAdd("C_K"),
    CardAdd("S_Q", enhancement="STEEL"),
)
MEGA_HELD_JOKERS = (
    JokerAdd("j_baron", edition="POLYCHROME"),
    JokerAdd("j_brainstorm", edition="HOLO"),
    JokerAdd("j_mime", edition="HOLO"),
    JokerAdd("j_blueprint", edition="FOIL"),
    JokerAdd("j_shoot_the_moon", edition="NEGATIVE"),
    JokerAdd("j_raised_fist", edition="NEGATIVE"),
    JokerAdd("j_steel_joker", edition="NEGATIVE"),
    JokerAdd("j_abstract", edition="NEGATIVE"),
    JokerAdd("j_jolly", edition="NEGATIVE"),
    JokerAdd("j_cavendish", edition="POLYCHROME"),
    JokerAdd("j_baseball", edition="NEGATIVE"),
    JokerAdd("j_stuntman", edition="NEGATIVE"),
)
MEGA_HELD_NO_MIME = tuple(j for j in MEGA_HELD_JOKERS if j.key != "j_mime")
MEGA_HELD_NO_SCORE_EDITIONS = tuple(
    JokerAdd(j.key, edition="NEGATIVE") for j in MEGA_HELD_JOKERS
)

MEGA_GLOBAL_CARDS = (
    CardAdd("H_K", enhancement="GLASS", seal="RED"),
    CardAdd("H_K", enhancement="MULT", edition="HOLO"),
    CardAdd("H_K", enhancement="BONUS", edition="FOIL"),
    CardAdd("H_5", edition="POLYCHROME"),
    CardAdd("C_5", enhancement="WILD"),
)
MEGA_GLOBAL_JOKERS = (
    JokerAdd("j_jolly", edition="FOIL"),
    JokerAdd("j_brainstorm", edition="HOLO"),
    JokerAdd("j_abstract", edition="NEGATIVE"),
    JokerAdd("j_swashbuckler", edition="NEGATIVE"),
    JokerAdd("j_bull", edition="NEGATIVE"),
    JokerAdd("j_bootstraps", edition="NEGATIVE"),
    JokerAdd("j_stuntman", edition="FOIL"),
    JokerAdd("j_crafty", edition="NEGATIVE"),
    JokerAdd("j_acrobat", edition="NEGATIVE"),
    JokerAdd("j_tribe", edition="NEGATIVE"),
    JokerAdd("j_seeing_double", edition="NEGATIVE"),
    JokerAdd("j_blueprint", edition="HOLO"),
    JokerAdd("j_cavendish", edition="POLYCHROME"),
    JokerAdd("j_baseball", edition="NEGATIVE"),
)
MEGA_GLOBAL_XMULT_EARLY = (
    MEGA_GLOBAL_JOKERS[0],
    MEGA_GLOBAL_JOKERS[1],
    MEGA_GLOBAL_JOKERS[11],
    MEGA_GLOBAL_JOKERS[12],
    MEGA_GLOBAL_JOKERS[8],
    MEGA_GLOBAL_JOKERS[9],
    MEGA_GLOBAL_JOKERS[10],
    *MEGA_GLOBAL_JOKERS[2:8],
    MEGA_GLOBAL_JOKERS[13],
)
MEGA_GLOBAL_NO_BASEBALL = tuple(j for j in MEGA_GLOBAL_JOKERS if j.key != "j_baseball")
MEGA_GLOBAL_NO_SCORE_EDITIONS = tuple(
    JokerAdd(j.key, edition="NEGATIVE") for j in MEGA_GLOBAL_JOKERS
)


def _line(
    line_id: str,
    *,
    play_order_cards: tuple[CardAdd, ...] | None = None,
    pick: str = "",
    joker_order: tuple[int, ...] | None = None,
    joker_order_specs: tuple[JokerAdd, ...] | None = None,
    hand_order: str = "",
    cards: tuple[CardAdd, ...] | None = None,
    joker_keys: tuple[str, ...] | None = None,
    jokers: tuple[JokerAdd, ...] | None = None,
    set_state: dict[str, Any] | None = None,
    debuff: tuple[CardAdd, ...] = (),
    expect_lower: bool = False,
) -> ScenarioLine:
    return ScenarioLine(
        line_id=line_id,
        play_order_cards=play_order_cards,
        pick=pick,
        joker_order=joker_order,
        joker_order_specs=joker_order_specs,
        hand_order=hand_order,
        debuff=debuff,
        cards=cards,
        joker_keys=joker_keys,
        jokers=jokers,
        set_state=set_state or {},
        expect_lower_than_optimal=expect_lower,
    )


def build_scenarios() -> list[ScenarioRecipe]:
    """All order-sensitive multi-joker scenarios (24 base + 7 buffed joker)."""
    return [
        # --- A. Steel K / held buff ---
        ScenarioRecipe(
            scenario_id="S04",
            description="Steel K Baron+Mime base",
            category="steel_held",
            joker_keys=("j_baron", "j_mime"),
            cards=(*PAIR_5, STEEL_RED_K),
            lines=(
                _line("optimal", pick="pair_5s"),
                _line(
                    "no_steel_red",
                    cards=(*PAIR_5, PLAIN_K),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S13",
            description="Steel K Baron+Mime two kings",
            category="steel_held",
            joker_keys=("j_baron", "j_mime"),
            cards=(
                *PAIR_5,
                STEEL_RED_K,
                CardAdd("D_K", enhancement="STEEL", seal="RED"),
            ),
            lines=(
                _line("optimal", pick="pair_5s"),
                _line(
                    "one_king",
                    cards=(*PAIR_5, STEEL_RED_K, PLAIN_K),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S14",
            description="Steel K High Card vs pair",
            category="steel_held",
            joker_keys=("j_baron", "j_mime"),
            cards=(
                CardAdd("S_5"),
                CardAdd("D_5"),
                CardAdd("S_2"),
                STEEL_K,
                CardAdd("H_K", enhancement="STEEL"),
            ),
            lines=(
                _line("optimal", pick="pair_5s"),
                _line(
                    "high_card", play_order_cards=(CardAdd("S_2"),), expect_lower=True
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S15",
            description="Shoot the Moon + Steel held",
            category="steel_held",
            joker_keys=("j_shoot_the_moon", "j_mime"),
            cards=(*PAIR_5, CardAdd("H_Q"), STEEL_K),
            lines=(
                _line("with_steel", pick="pair_5s"),
                _line(
                    "no_steel",
                    cards=(*PAIR_5, CardAdd("H_Q"), PLAIN_K),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S16",
            description="Raised Fist + Steel held",
            category="steel_held",
            joker_keys=("j_raised_fist", "j_mime"),
            cards=(*PAIR_5, CardAdd("S_2"), CardAdd("S_3", enhancement="STEEL")),
            lines=(
                _line("with_steel", pick="pair_5s"),
                _line(
                    "no_steel",
                    cards=(*PAIR_5, CardAdd("S_2"), CardAdd("S_3")),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S17",
            description="Steel Joker deck scale + held steel",
            category="steel_held",
            joker_keys=("j_steel_joker", "j_mime"),
            cards=(*PAIR_5, STEEL_K, CardAdd("C_K", enhancement="STEEL")),
            lines=(
                _line("optimal", pick="pair_5s"),
                _line(
                    "no_held_steel",
                    cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        # --- B. Scored buff stacks ---
        ScenarioRecipe(
            scenario_id="S20",
            description="MULT then GLASS play order",
            category="scored_buff",
            joker_keys=("j_jolly",),
            cards=(MULT_5, GLASS_5, CardAdd("S_3"), CardAdd("H_7"), CardAdd("C_2")),
            lines=(
                _line("mult_left", play_order_cards=(MULT_5, GLASS_5)),
                _line(
                    "glass_left", play_order_cards=(GLASS_5, MULT_5), expect_lower=True
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S21",
            description="BONUS+FOIL pair",
            category="scored_buff",
            joker_keys=("j_abstract",),
            cards=(
                BONUS_FOIL_5,
                CardAdd("D_5"),
                CardAdd("S_3"),
                CardAdd("H_7"),
                CardAdd("C_2"),
            ),
            lines=(
                _line("optimal", play_order_cards=(BONUS_FOIL_5, CardAdd("D_5"))),
                _line(
                    "plain_pair",
                    cards=(
                        CardAdd("S_5"),
                        CardAdd("D_5"),
                        CardAdd("H_3"),
                        CardAdd("C_7"),
                        CardAdd("S_2"),
                    ),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S22",
            description="Stone+Splash all score",
            category="scored_buff",
            joker_keys=("j_stone", "j_splash"),
            cards=(
                STONE_CARD,
                CardAdd("S_3"),
                CardAdd("H_7"),
                CardAdd("C_4"),
                CardAdd("D_9"),
            ),
            lines=(
                _line(
                    "optimal",
                    play_order_cards=(
                        STONE_CARD,
                        CardAdd("S_3"),
                        CardAdd("H_7"),
                        CardAdd("C_4"),
                        CardAdd("D_9"),
                    ),
                ),
                _line(
                    "pair_only",
                    play_order_cards=(CardAdd("S_3"), CardAdd("H_7")),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S23",
            description="Vampire strips BONUS chips",
            category="scored_buff",
            joker_keys=("j_vampire",),
            lines=(
                _line(
                    "bonus_pair",
                    cards=(
                        CardAdd("S_5", enhancement="BONUS"),
                        CardAdd("D_5"),
                        CardAdd("H_3"),
                        CardAdd("C_7"),
                        CardAdd("S_2"),
                    ),
                    pick="pair_5s",
                ),
                _line(
                    "plain_pair",
                    cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S24",
            description="POLY+GLASS pair with Jolly",
            category="scored_buff",
            joker_keys=("j_jolly",),
            cards=(
                CardAdd("S_5", enhancement="GLASS"),
                CardAdd("D_5", edition="POLYCHROME"),
                CardAdd("H_3"),
                CardAdd("C_7"),
                CardAdd("S_2"),
            ),
            lines=(
                _line(
                    "optimal",
                    play_order_cards=(
                        CardAdd("S_5", enhancement="GLASS"),
                        CardAdd("D_5", edition="POLYCHROME"),
                        CardAdd("H_3"),
                    ),
                ),
                _line(
                    "plain_pair",
                    cards=(
                        CardAdd("S_5"),
                        CardAdd("D_5"),
                        CardAdd("H_3"),
                        CardAdd("C_7"),
                        CardAdd("S_2"),
                    ),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S26",
            description="MULT+HOLO Jack pair",
            category="scored_buff",
            joker_keys=("j_smiley",),
            cards=(
                MULT_HOLO_J,
                CardAdd("S_J"),
                CardAdd("H_5"),
                CardAdd("C_3"),
                CardAdd("D_2"),
            ),
            lines=(
                _line("optimal", pick="pair_j"),
                _line(
                    "no_face",
                    cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        # --- C. Joker combo / copy / order ---
        ScenarioRecipe(
            scenario_id="S01",
            description="+Mult before xMult joker order",
            category="joker_combo",
            joker_keys=("j_jolly", "j_cavendish"),
            cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
            lines=(
                _line("optimal", joker_order=(0, 1), pick="pair_5s"),
                _line(
                    "reversed", joker_order=(1, 0), pick="pair_5s", expect_lower=True
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S05",
            description="Brainstorm copies leftmost Jolly",
            category="joker_combo",
            joker_keys=("j_brainstorm", "j_jolly", "j_abstract"),
            cards=(*PAIR_J, CardAdd("H_5"), CardAdd("C_3"), CardAdd("D_2")),
            lines=(
                _line("optimal", joker_order=(1, 0, 2), pick="pair_j"),
                _line(
                    "wrong_left",
                    joker_order=(0, 1, 2),
                    pick="pair_j",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S06",
            description="Blueprint trap Cavendish vs Jolly",
            category="joker_combo",
            joker_keys=("j_blueprint", "j_jolly", "j_cavendish"),
            cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
            lines=(
                _line("optimal", joker_order=(1, 0, 2), pick="pair_5s"),
                _line("trap", joker_order=(0, 1, 2), pick="pair_5s", expect_lower=True),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S08",
            description="Blackboard kicker two pair",
            category="joker_combo",
            joker_keys=("j_blackboard", "j_abstract"),
            cards=BLACKBOARD_HAND,
            lines=(
                _line(
                    "kicker",
                    play_order_cards=(
                        CardAdd("H_J"),
                        CardAdd("S_8"),
                        CardAdd("D_8"),
                        CardAdd("H_5"),
                        CardAdd("C_5"),
                    ),
                ),
                _line(
                    "no_blackboard",
                    joker_keys=("j_abstract",),
                    play_order_cards=(
                        CardAdd("H_J"),
                        CardAdd("S_8"),
                        CardAdd("D_8"),
                        CardAdd("H_5"),
                        CardAdd("C_5"),
                    ),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S10",
            description="Flower Pot Splash straight",
            category="joker_combo",
            joker_keys=("j_flower_pot", "j_splash", "j_seeing_double"),
            cards=STRAIGHT_5,
            lines=(
                _line("optimal", pick="straight_5"),
                _line(
                    "two_card",
                    play_order_cards=(CardAdd("S_9"), CardAdd("D_T")),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S12",
            description="Baseball on Cavendish xMult order",
            category="joker_combo",
            joker_keys=("j_jolly", "j_cavendish", "j_baseball"),
            cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
            lines=(
                _line("optimal", joker_order=(0, 1, 2), pick="pair_5s"),
                _line(
                    "reversed", joker_order=(1, 0, 2), pick="pair_5s", expect_lower=True
                ),
            ),
        ),
        # --- D. Retrigger + buff ---
        ScenarioRecipe(
            scenario_id="S02",
            description="Estimator reorders PhotoChad POLY face leftmost",
            category="retrigger",
            joker_keys=("j_photograph", "j_hanging_chad"),
            cards=(
                CardAdd("S_J"),
                POLY_J,
                CardAdd("H_5"),
                CardAdd("C_3"),
                CardAdd("D_2"),
            ),
            lines=(
                _line("optimized", pick="estimate_top"),
                _line(
                    "face_not_left",
                    play_order_cards=(CardAdd("S_J"), POLY_J),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S03",
            description="PhotoChad face slot with kicker",
            category="retrigger",
            joker_keys=("j_photograph", "j_hanging_chad"),
            cards=(
                GLASS_J,
                CardAdd("S_J"),
                CardAdd("H_5"),
                CardAdd("C_3"),
                CardAdd("D_2"),
                CardAdd("S_7"),
            ),
            lines=(
                _line(
                    "face_right",
                    play_order_cards=(CardAdd("H_5"), GLASS_J, CardAdd("S_J")),
                ),
                _line(
                    "no_chad",
                    joker_keys=("j_photograph",),
                    play_order_cards=(CardAdd("H_5"), GLASS_J, CardAdd("S_J")),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S07",
            description="Dusk Seltzer Hanging Chad retrigger stack",
            category="retrigger",
            joker_keys=("j_dusk", "j_selzer", "j_hanging_chad"),
            cards=(
                RETRIGGER_BUFF,
                CardAdd("D_4"),
                CardAdd("H_3"),
                CardAdd("C_7"),
                CardAdd("S_2"),
            ),
            lines=(
                _line(
                    "optimal",
                    set_state={"hands": 1},
                    play_order_cards=(RETRIGGER_BUFF, CardAdd("D_4")),
                ),
                _line(
                    "no_dusk",
                    set_state={"hands": 2},
                    play_order_cards=(RETRIGGER_BUFF, CardAdd("D_4")),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S09",
            description="Sock and Buskin face retrigger",
            category="retrigger",
            joker_keys=("j_sock_and_buskin", "j_smiley", "j_scary_face"),
            cards=FACE_LINE,
            lines=(
                _line(
                    "all_faces",
                    play_order_cards=(
                        CardAdd("H_J"),
                        CardAdd("S_Q"),
                        CardAdd("D_K"),
                        CardAdd("C_K"),
                    ),
                ),
                _line(
                    "one_less",
                    play_order_cards=(CardAdd("H_J"), CardAdd("S_Q"), CardAdd("D_K")),
                    expect_lower=True,
                ),
            ),
        ),
        # --- E. Hand type ---
        ScenarioRecipe(
            scenario_id="S11",
            description="Estimator reorders flush MULT before GLASS",
            category="hand_type",
            joker_keys=("j_crafty",),
            cards=(
                CardAdd("D_7", enhancement="GLASS"),
                CardAdd("D_5", enhancement="MULT"),
                CardAdd("D_9"),
                CardAdd("D_J"),
                CardAdd("D_K"),
            ),
            lines=(
                _line("optimized", pick="estimate_top"),
                _line(
                    "glass_left",
                    play_order_cards=(
                        CardAdd("D_7", enhancement="GLASS"),
                        CardAdd("D_5", enhancement="MULT"),
                        CardAdd("D_9"),
                        CardAdd("D_J"),
                        CardAdd("D_K"),
                    ),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S18",
            description="PhotoChad POLY face leftmost",
            category="hand_type",
            joker_keys=("j_photograph", "j_hanging_chad"),
            cards=(
                POLY_J,
                CardAdd("S_J"),
                CardAdd("H_5"),
                CardAdd("C_3"),
                CardAdd("D_2"),
            ),
            lines=(
                _line("optimal", play_order_cards=(POLY_J, CardAdd("S_J"))),
                _line(
                    "face_not_left",
                    play_order_cards=(CardAdd("S_J"), POLY_J),
                    expect_lower=True,
                ),
            ),
        ),
        # --- F. Buffed joker + hand buff combos ---
        ScenarioRecipe(
            scenario_id="S27",
            description="Blueprint Holo copies Cavendish",
            category="buffed_joker",
            jokers=(JokerAdd("j_blueprint", edition="HOLO"), JokerAdd("j_cavendish")),
            cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
            lines=(
                _line("optimal", pick="pair_5s"),
                _line(
                    "no_holo",
                    jokers=(JokerAdd("j_blueprint"), JokerAdd("j_cavendish")),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S28",
            description="Jolly Foil before Cavendish",
            category="buffed_joker",
            jokers=(JokerAdd("j_jolly", edition="FOIL"), JokerAdd("j_cavendish")),
            cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
            lines=(
                _line("optimal", joker_order=(0, 1), pick="pair_5s"),
                _line(
                    "reversed", joker_order=(1, 0), pick="pair_5s", expect_lower=True
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S29",
            description="Cavendish Poly after Jolly",
            category="buffed_joker",
            jokers=(JokerAdd("j_jolly"), JokerAdd("j_cavendish", edition="POLYCHROME")),
            cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
            lines=(
                _line("optimal", joker_order=(0, 1), pick="pair_5s"),
                _line(
                    "no_poly",
                    jokers=(JokerAdd("j_jolly"), JokerAdd("j_cavendish")),
                    joker_order=(0, 1),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S30",
            description="PhotoChad Holo joker slot",
            category="buffed_joker",
            jokers=(
                JokerAdd("j_photograph", edition="HOLO"),
                JokerAdd("j_hanging_chad"),
            ),
            cards=(
                POLY_J,
                CardAdd("S_J"),
                CardAdd("H_5"),
                CardAdd("C_3"),
                CardAdd("D_2"),
            ),
            lines=(
                _line("optimal", play_order_cards=(POLY_J, CardAdd("S_J"))),
                _line(
                    "face_not_left",
                    play_order_cards=(CardAdd("S_J"), POLY_J),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S31",
            description="Mime Holo + held steel",
            category="buffed_joker",
            jokers=(JokerAdd("j_baron"), JokerAdd("j_mime", edition="HOLO")),
            cards=(*PAIR_5, STEEL_RED_K),
            lines=(
                _line("optimal", pick="pair_5s"),
                _line(
                    "no_holo",
                    jokers=(JokerAdd("j_baron"), JokerAdd("j_mime")),
                    pick="pair_5s",
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S32",
            description="Baseball Poly Cavendish order",
            category="buffed_joker",
            jokers=(
                JokerAdd("j_jolly"),
                JokerAdd("j_cavendish", edition="POLYCHROME"),
                JokerAdd("j_baseball"),
            ),
            cards=(*PAIR_5, CardAdd("H_3"), CardAdd("C_7"), CardAdd("S_2")),
            lines=(
                _line("optimal", joker_order=(0, 1, 2), pick="pair_5s"),
                _line(
                    "reversed", joker_order=(1, 0, 2), pick="pair_5s", expect_lower=True
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S33",
            description="Estimator reorders PhotoChad GLASS+RED top tier",
            category="buffed_joker",
            joker_keys=("j_photograph", "j_hanging_chad"),
            cards=(
                CardAdd("S_J"),
                GLASS_RED_J,
                CardAdd("H_5"),
                CardAdd("C_3"),
                CardAdd("D_2"),
            ),
            lines=(
                _line("optimized", pick="estimate_top"),
                _line(
                    "no_red",
                    cards=(
                        GLASS_J,
                        CardAdd("S_J"),
                        CardAdd("H_5"),
                        CardAdd("C_3"),
                        CardAdd("D_2"),
                    ),
                    play_order_cards=(GLASS_J, CardAdd("S_J")),
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S34",
            description="Five Wild Kings classify as Flush Five",
            category="wild",
            cards=FIVE_WILD_KINGS,
            lines=(_line("optimal", pick="play_added"),),
            check_unmodeled=False,
        ),
        ScenarioRecipe(
            scenario_id="S35",
            description="Debuffed Wild reverts to printed suit (no diamond flush)",
            category="wild",
            cards=WILD_DEBUFF_FLUSH,
            debuff=(CardAdd("H_K", enhancement="WILD"),),
            lines=(_line("optimal", pick="play_added"),),
            check_unmodeled=False,
        ),
        # --- H. Mega stress: many jokers + buffs + phase interactions ---
        ScenarioRecipe(
            scenario_id="S36",
            description="Mega scored-card order/retrigger/copy stress",
            category="mega",
            jokers=_negative_first(MEGA_FACE_JOKERS),
            cards=MEGA_FACE_CARDS,
            set_state={"hands": 1},
            lines=(
                _line(
                    "optimized",
                    pick="estimate_top",
                    joker_order_specs=MEGA_FACE_JOKERS,
                ),
                _line(
                    "reverse_play",
                    play_order_cards=tuple(reversed(MEGA_FACE_CARDS)),
                    joker_order_specs=MEGA_FACE_JOKERS,
                    expect_lower=True,
                ),
                _line(
                    "no_dusk",
                    pick="estimate_top",
                    joker_order_specs=MEGA_FACE_JOKERS,
                    set_state={"hands": 2},
                    expect_lower=True,
                ),
                _line(
                    "no_red",
                    cards=MEGA_FACE_NO_RED,
                    pick="estimate_top",
                    joker_order_specs=MEGA_FACE_JOKERS,
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S37",
            description="Mega held-card Mime/copy/Baseball stress",
            category="mega",
            jokers=_negative_first(MEGA_HELD_JOKERS),
            cards=MEGA_HELD_CARDS,
            lines=(
                _line(
                    "optimized",
                    pick="estimate_top",
                    joker_order_specs=MEGA_HELD_JOKERS,
                ),
                _line(
                    "no_mime",
                    jokers=_negative_first(MEGA_HELD_NO_MIME),
                    pick="estimate_top",
                    joker_order_specs=MEGA_HELD_NO_MIME,
                    expect_lower=True,
                ),
                _line(
                    "plain_kings",
                    cards=MEGA_HELD_PLAIN_KINGS,
                    pick="estimate_top",
                    joker_order_specs=MEGA_HELD_JOKERS,
                    expect_lower=True,
                ),
                _line(
                    "no_score_editions",
                    jokers=_negative_first(MEGA_HELD_NO_SCORE_EDITIONS),
                    pick="estimate_top",
                    joker_order_specs=MEGA_HELD_NO_SCORE_EDITIONS,
                    expect_lower=True,
                ),
            ),
        ),
        ScenarioRecipe(
            scenario_id="S38",
            description="Mega global joker order/edition/Baseball stress",
            category="mega",
            jokers=_negative_first(MEGA_GLOBAL_JOKERS),
            cards=MEGA_GLOBAL_CARDS,
            set_state={"money": 25, "hands": 1},
            lines=(
                _line(
                    "optimized",
                    pick="estimate_top",
                    joker_order_specs=MEGA_GLOBAL_JOKERS,
                ),
                _line(
                    "xmult_early",
                    pick="estimate_top",
                    joker_order_specs=MEGA_GLOBAL_XMULT_EARLY,
                    expect_lower=True,
                ),
                _line(
                    "no_baseball",
                    jokers=_negative_first(MEGA_GLOBAL_NO_BASEBALL),
                    pick="estimate_top",
                    joker_order_specs=MEGA_GLOBAL_NO_BASEBALL,
                    expect_lower=True,
                ),
                _line(
                    "no_score_editions",
                    jokers=_negative_first(MEGA_GLOBAL_NO_SCORE_EDITIONS),
                    pick="estimate_top",
                    joker_order_specs=MEGA_GLOBAL_NO_SCORE_EDITIONS,
                    expect_lower=True,
                ),
            ),
        ),
    ]


_SCENARIOS: list[ScenarioRecipe] | None = None


def all_scenarios() -> list[ScenarioRecipe]:
    global _SCENARIOS
    if _SCENARIOS is None:
        _SCENARIOS = build_scenarios()
    return _SCENARIOS


def get_scenario(scenario_id: str) -> ScenarioRecipe:
    for s in all_scenarios():
        if s.scenario_id == scenario_id:
            return s
    raise KeyError(scenario_id)

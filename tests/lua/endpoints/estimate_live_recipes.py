"""Live estimate recipes: one scenario per scoring joker + card buff matrix."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Card / recipe types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CardAdd:
    key: str
    enhancement: str | None = None
    edition: str | None = None
    seal: str | None = None

    def to_add_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"key": self.key}
        if self.enhancement:
            params["enhancement"] = self.enhancement
        if self.edition:
            params["edition"] = self.edition
        if self.seal:
            params["seal"] = self.seal
        return params


@dataclass(frozen=True)
class JokerAdd:
    key: str
    edition: str | None = None

    def to_add_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"key": self.key}
        if self.edition:
            params["edition"] = self.edition
        return params


@dataclass(frozen=True)
class LiveRecipe:
    """One live estimate == play validation scenario."""

    recipe_id: str
    joker_keys: tuple[str, ...] = ()
    jokers: tuple[JokerAdd, ...] = ()
    cards: tuple[CardAdd, ...] = ()
    set_state: dict[str, Any] = field(default_factory=dict)
    pick: str = "pair_5s"
    check_unmodeled: bool = True
    pre_play_pair: bool = False
    require_loyalty_active: bool = False


# Standard card bundles
PAIR_5 = (CardAdd("S_5"), CardAdd("D_5"))
PAIR_4 = (CardAdd("S_4"), CardAdd("D_4"))
PAIR_3 = (CardAdd("S_3"), CardAdd("D_3"))
PAIR_J = (CardAdd("H_J"), CardAdd("S_J"))
PAIR_A = (CardAdd("S_A"), CardAdd("D_A"))
PAIR_D = (CardAdd("D_5"), CardAdd("D_6"))
PAIR_H = (CardAdd("H_5"), CardAdd("H_6"))
PAIR_S = (CardAdd("S_5"), CardAdd("S_6"))
PAIR_C = (CardAdd("C_5"), CardAdd("C_6"))
THREE_K = (CardAdd("S_K"), CardAdd("D_K"), CardAdd("H_K"))
TWO_PAIR = (CardAdd("S_K"), CardAdd("D_K"), CardAdd("S_5"), CardAdd("D_5"))
STRAIGHT_5 = (
    CardAdd("S_9"),
    CardAdd("D_T"),
    CardAdd("H_J"),
    CardAdd("C_Q"),
    CardAdd("S_K"),
)
FLUSH_D5 = (
    CardAdd("D_5"),
    CardAdd("D_7"),
    CardAdd("D_9"),
    CardAdd("D_J"),
    CardAdd("D_K"),
)
FOUR_K = (
    CardAdd("S_K"),
    CardAdd("D_K"),
    CardAdd("H_K"),
    CardAdd("C_K"),
    CardAdd("S_2"),
)
FOUR_HEART_FLUSH = (
    CardAdd("H_5"),
    CardAdd("H_7"),
    CardAdd("H_9"),
    CardAdd("H_J"),
)
FOUR_STRAIGHT = (
    CardAdd("S_9"),
    CardAdd("D_T"),
    CardAdd("H_J"),
    CardAdd("C_Q"),
)
SHORTCUT_STRAIGHT = (
    CardAdd("S_T"),
    CardAdd("H_9"),
    CardAdd("D_7"),
    CardAdd("C_6"),
    CardAdd("S_5"),
)
SPLASH_5 = (
    CardAdd("S_5"),
    CardAdd("D_5"),
    CardAdd("S_2"),
    CardAdd("C_3"),
    CardAdd("H_7"),
)
FLOWER_POT = (
    CardAdd("H_5"),
    CardAdd("D_6"),
    CardAdd("S_7"),
    CardAdd("C_8"),
    CardAdd("S_2"),
)
SEEING_DOUBLE = (
    CardAdd("S_K"),
    CardAdd("C_K"),
    CardAdd("H_5"),
    CardAdd("D_5"),
)
BLACKBOARD = (
    CardAdd("S_5"),
    CardAdd("C_5"),
    CardAdd("S_3"),
    CardAdd("C_7"),
)
BARON_HOLD = (
    CardAdd("S_5"),
    CardAdd("D_5"),
    CardAdd("S_K"),
)
SHOOT_MOON_HOLD = (
    CardAdd("S_5"),
    CardAdd("D_5"),
    CardAdd("H_Q"),
)
RAISED_FIST_HOLD = (
    CardAdd("S_2"),
    CardAdd("S_5"),
    CardAdd("D_5"),
)
MIME_STEEL = (
    CardAdd("S_5"),
    CardAdd("D_5"),
    CardAdd("H_K", enhancement="STEEL"),
)
PAIR_2 = (CardAdd("S_2"), CardAdd("D_2"))


def _r(
    recipe_id: str,
    *jokers: str,
    cards: tuple[CardAdd, ...] = PAIR_5,
    pick: str = "pair_5s",
    set_state: dict[str, Any] | None = None,
    **kwargs: Any,
) -> LiveRecipe:
    return LiveRecipe(
        recipe_id=recipe_id,
        joker_keys=jokers,
        cards=cards,
        pick=pick,
        set_state=set_state or {},
        **kwargs,
    )


def build_scoring_joker_recipes() -> list[LiveRecipe]:
    """One recipe per deterministic scoring joker (99 keys)."""
    recipes: list[LiveRecipe] = []

    pair_5s = [
        "j_joker",
        "j_gros_michel",
        "j_popcorn",
        "j_ice_cream",
        "j_ceremonial",
        "j_flash",
        "j_red_card",
        "j_fortune_teller",
        "j_castle",
        "j_cavendish",
        "j_stuntman",
        "j_green_joker",
        "j_ride_the_bus",
        "j_obelisk",
        "j_madness",
        "j_constellation",
        "j_campfire",
        "j_glass",
        "j_hologram",
        "j_ramen",
        "j_hit_the_road",
        "j_throwback",
        "j_lucky_cat",
        "j_yorick",
        "j_caino",
        "j_drivers_license",
        "j_steel_joker",
        "j_stone",
        "j_supernova",
        "j_erosion",
        "j_blue_joker",
        "j_abstract",
        "j_selzer",
        "j_hanging_chad",
        "j_hack",
        "j_duo",
        "j_sly",
        "j_half",
        "j_stencil",
        "j_pareidolia",
        "j_fibonacci",
    ]
    for key in pair_5s:
        recipes.append(_r(key, key))

    recipes.extend(
        [
            _r("j_jolly", "j_jolly"),
            _r("j_zany", "j_zany", cards=THREE_K, pick="three_k"),
            _r("j_mad", "j_mad", cards=TWO_PAIR, pick="two_pair"),
            _r("j_crazy", "j_crazy", cards=STRAIGHT_5, pick="straight_5"),
            _r("j_droll", "j_droll", cards=FLUSH_D5, pick="flush_5d"),
            _r("j_wily", "j_wily", cards=THREE_K, pick="three_k"),
            _r("j_clever", "j_clever", cards=TWO_PAIR, pick="two_pair"),
            _r("j_devious", "j_devious", cards=STRAIGHT_5, pick="straight_5"),
            _r("j_crafty", "j_crafty", cards=FLUSH_D5, pick="flush_5d"),
            _r("j_trio", "j_trio", cards=THREE_K, pick="three_k"),
            _r("j_order", "j_order", cards=STRAIGHT_5, pick="straight_5"),
            _r("j_tribe", "j_tribe", cards=FLUSH_D5, pick="flush_5d"),
            _r("j_family", "j_family", cards=FOUR_K, pick="four_k"),
            _r("j_greedy_joker", "j_greedy_joker", cards=PAIR_D, pick="pair_suit"),
            _r("j_lusty_joker", "j_lusty_joker", cards=PAIR_H, pick="pair_suit"),
            _r("j_wrathful_joker", "j_wrathful_joker", cards=PAIR_S, pick="pair_suit"),
            _r("j_gluttenous_joker", "j_gluttenous_joker", cards=PAIR_C, pick="pair_suit"),
            _r("j_onyx_agate", "j_onyx_agate", cards=PAIR_C, pick="pair_suit"),
            _r("j_arrowhead", "j_arrowhead", cards=PAIR_S, pick="pair_suit"),
            _r("j_walkie_talkie", "j_walkie_talkie", cards=PAIR_4, pick="pair_rank"),
            _r("j_even_steven", "j_even_steven", cards=PAIR_4, pick="pair_rank"),
            _r("j_odd_todd", "j_odd_todd", cards=PAIR_3, pick="pair_rank"),
            _r("j_scholar", "j_scholar", cards=PAIR_A, pick="pair_rank"),
            _r("j_triboulet", "j_triboulet", cards=PAIR_J, pick="pair_rank"),
            _r("j_scary_face", "j_scary_face", cards=PAIR_J, pick="pair_rank"),
            _r("j_smiley", "j_smiley", cards=PAIR_J, pick="pair_rank"),
            _r("j_photograph", "j_photograph", cards=PAIR_J, pick="pair_rank"),
            _r("j_sock_and_buskin", "j_sock_and_buskin", cards=PAIR_J, pick="pair_rank"),
            _r("j_runner", "j_runner", pick="top"),
            _r("j_wee", "j_wee", cards=PAIR_2, pick="pair_rank"),
            _r("j_square", "j_square", cards=TWO_PAIR, pick="two_pair"),
            _r("j_trousers", "j_trousers", cards=TWO_PAIR, pick="two_pair"),
            _r("j_vampire", "j_vampire", cards=(CardAdd("S_5", enhancement="BONUS"), CardAdd("D_5"))),
            _r("j_splash", "j_splash", cards=SPLASH_5, pick="straight_5"),
            _r("j_four_fingers", "j_four_fingers", cards=FOUR_HEART_FLUSH, pick="four_flush"),
            _r("j_shortcut", "j_shortcut", cards=SHORTCUT_STRAIGHT, pick="straight_5"),
            _r("j_flower_pot", "j_flower_pot", cards=FLOWER_POT, pick="flower_pot"),
            _r("j_seeing_double", "j_seeing_double", cards=SEEING_DOUBLE, pick="seeing_double"),
            _r(
                "j_blackboard",
                "j_blackboard",
                cards=BLACKBOARD,
                pick="blackboard",
            ),
            _r("j_baron", "j_baron", cards=BARON_HOLD, pick="baron_hold"),
            _r("j_shoot_the_moon", "j_shoot_the_moon", cards=SHOOT_MOON_HOLD, pick="shoot_hold"),
            _r("j_raised_fist", "j_raised_fist", cards=RAISED_FIST_HOLD, pick="raised_fist_hold"),
            _r("j_mime", "j_mime", cards=MIME_STEEL, pick="mime_steel"),
            _r("j_smeared", "j_smeared", "j_greedy_joker", cards=PAIR_H, pick="pair_suit"),
            _r("j_blueprint", "j_blueprint", "j_jolly", cards=PAIR_J, pick="pair_rank"),
            _r("j_brainstorm", "j_jolly", "j_brainstorm", cards=PAIR_J, pick="pair_rank"),
            _r("j_swashbuckler", "j_gros_michel", "j_swashbuckler"),
            _r("j_baseball", "j_baseball", "j_popcorn"),
            _r("j_bull", "j_bull"),
            _r("j_bootstraps", "j_bootstraps"),
            _r("j_acrobat", "j_acrobat", set_state={"hands": 1}, pick="pair_5s"),
            _r("j_dusk", "j_dusk", set_state={"hands": 1}, pick="pair_5s"),
            _r("j_mystic_summit", "j_mystic_summit", set_state={"discards": 0}, pick="pair_5s"),
            _r("j_banner", "j_banner", pick="pair_5s"),
            _r("j_ancient", "j_ancient", pick="ancient"),
            _r("j_idol", "j_idol", pick="idol"),
            LiveRecipe(
                recipe_id="j_loyalty_card",
                joker_keys=("j_loyalty_card",),
                cards=PAIR_5,
                pick="pair_5s",
                require_loyalty_active=True,
            ),
            LiveRecipe(
                recipe_id="j_card_sharp",
                joker_keys=("j_card_sharp",),
                cards=PAIR_5,
                pick="pair_5s",
                pre_play_pair=True,
            ),
        ]
    )

    ids = {r.recipe_id for r in recipes}
    expected = _all_scoring_joker_keys()
    missing = sorted(set(expected) - ids)
    extra = sorted(ids - set(expected))
    if missing or extra:
        raise RuntimeError(f"Recipe coverage mismatch: missing={missing} extra={extra}")
    return recipes


def build_buff_recipes() -> list[LiveRecipe]:
    """Deterministic card buff live matrix (no joker unless noted)."""
    return [
        LiveRecipe(
            recipe_id="buff_bonus",
            cards=(CardAdd("S_5", enhancement="BONUS"), CardAdd("D_5")),
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_mult",
            cards=(CardAdd("S_5", enhancement="MULT"), CardAdd("D_5")),
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_glass",
            cards=(CardAdd("S_5", enhancement="GLASS"), CardAdd("D_5")),
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_stone",
            cards=(CardAdd("S_5", enhancement="STONE"),),
            pick="high_stone",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_foil",
            cards=(CardAdd("S_5", edition="FOIL"), CardAdd("D_5")),
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_holo",
            cards=(CardAdd("S_5", edition="HOLO"), CardAdd("D_5")),
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_polychrome",
            cards=(CardAdd("S_5", edition="POLYCHROME"), CardAdd("D_5")),
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_red_seal",
            cards=(CardAdd("S_5", seal="RED"), CardAdd("D_5")),
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="buff_steel_held",
            joker_keys=("j_mime",),
            cards=MIME_STEEL,
            pick="mime_steel",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="joker_edition_foil",
            jokers=(JokerAdd("j_jolly", edition="FOIL"),),
            cards=PAIR_5,
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="joker_edition_holo",
            jokers=(JokerAdd("j_jolly", edition="HOLO"),),
            cards=PAIR_5,
            pick="pair_5s",
            check_unmodeled=False,
        ),
        LiveRecipe(
            recipe_id="joker_edition_poly",
            jokers=(JokerAdd("j_cavendish", edition="POLYCHROME"),),
            cards=PAIR_5,
            pick="pair_5s",
            check_unmodeled=False,
        ),
    ]


def all_live_recipes() -> list[LiveRecipe]:
    return build_scoring_joker_recipes() + build_buff_recipes()


def _all_scoring_joker_keys() -> list[str]:
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / "tools" / "play"))
    import estimate_jokers as ej  # noqa: WPS433

    modeled, _ = ej._modeled([])
    return sorted(set(modeled) - ej.NO_SCORE_JOKERS - {"j_misprint", "j_bloodstone"})

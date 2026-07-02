"""Regenerate Balatro verified JSON libraries from docs/api.md.

Usage (from repo root or knowledge/balatro/):
    python build_knowledge.py

Reads overrides from balatro-*-overrides.json for factual corrections only.
Writes balatro-*-verified.json used by know.py preflight.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_MD = Path(__file__).resolve().parents[2] / "docs" / "api.md"

TABLE_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|\s*$")

# The knowledge library is fact-only. Do not publish strategic recommendations
# in generated lookup tables; keep those in play policy/code, not rule data.
FACT_ONLY_DROP_FIELDS = {
    "strategy",
    "implication",
    "decision",
    "synergy",
    "anti",
    "misconception",
}
TAG_SKIP_TRIGGER = "Obtained by skipping the shown Blind."

# Game display labels (API gamestate uses these, not raw keys).
JOKER_LABELS: dict[str, str] = {
    "j_joker": "Joker",
    "j_greedy_joker": "Greedy Joker",
    "j_lusty_joker": "Lusty Joker",
    "j_wrathful_joker": "Wrathful Joker",
    "j_gluttenous_joker": "Gluttonous Joker",
    "j_jolly": "Jolly Joker",
    "j_zany": "Zany Joker",
    "j_mad": "Mad Joker",
    "j_crazy": "Crazy Joker",
    "j_droll": "Droll Joker",
    "j_sly": "Sly Joker",
    "j_wily": "Wily Joker",
    "j_clever": "Clever Joker",
    "j_devious": "Devious Joker",
    "j_crafty": "Crafty Joker",
    "j_half": "Half Joker",
    "j_stencil": "Joker Stencil",
    "j_four_fingers": "Four Fingers",
    "j_mime": "Mime",
    "j_credit_card": "Credit Card",
    "j_ceremonial": "Ceremonial Dagger",
    "j_banner": "Banner",
    "j_mystic_summit": "Mystic Summit",
    "j_marble": "Marble Joker",
    "j_loyalty_card": "Loyalty Card",
    "j_8_ball": "8 Ball",
    "j_misprint": "Misprint",
    "j_dusk": "Dusk",
    "j_raised_fist": "Raised Fist",
    "j_chaos": "Chaos the Clown",
    "j_fibonacci": "Fibonacci",
    "j_steel_joker": "Steel Joker",
    "j_scary_face": "Scary Face",
    "j_abstract": "Abstract Joker",
    "j_delayed_grat": "Delayed Gratification",
    "j_hack": "Hack",
    "j_pareidolia": "Pareidolia",
    "j_gros_michel": "Gros Michel",
    "j_even_steven": "Even Steven",
    "j_odd_todd": "Odd Todd",
    "j_scholar": "Scholar",
    "j_business": "Business Card",
    "j_supernova": "Supernova",
    "j_ride_the_bus": "Ride the Bus",
    "j_space": "Space Joker",
    "j_egg": "Egg",
    "j_burglar": "Burglar",
    "j_blackboard": "Blackboard",
    "j_runner": "Runner",
    "j_ice_cream": "Ice Cream",
    "j_dna": "DNA",
    "j_splash": "Splash",
    "j_blue_joker": "Blue Joker",
    "j_sixth_sense": "Sixth Sense",
    "j_constellation": "Constellation",
    "j_hiker": "Hiker",
    "j_faceless": "Faceless Joker",
    "j_green_joker": "Green Joker",
    "j_superposition": "Superposition",
    "j_todo_list": "To Do List",
    "j_cavendish": "Cavendish",
    "j_card_sharp": "Card Sharp",
    "j_red_card": "Red Card",
    "j_madness": "Madness",
    "j_square": "Square Joker",
    "j_seance": "Séance",
    "j_riff_raff": "Riff-Raff",
    "j_vampire": "Vampire",
    "j_shortcut": "Shortcut",
    "j_hologram": "Hologram",
    "j_vagabond": "Vagabond",
    "j_baron": "Baron",
    "j_cloud_9": "Cloud 9",
    "j_rocket": "Rocket",
    "j_obelisk": "Obelisk",
    "j_midas_mask": "Midas Mask",
    "j_luchador": "Luchador",
    "j_photograph": "Photograph",
    "j_gift": "Gift Card",
    "j_turtle_bean": "Turtle Bean",
    "j_erosion": "Erosion",
    "j_reserved_parking": "Reserved Parking",
    "j_mail": "Mail-In Rebate",
    "j_to_the_moon": "To the Moon",
    "j_hallucination": "Hallucination",
    "j_fortune_teller": "Fortune Teller",
    "j_juggler": "Juggler",
    "j_drunkard": "Drunkard",
    "j_stone": "Stone Joker",
    "j_golden": "Golden Joker",
    "j_lucky_cat": "Lucky Cat",
    "j_baseball": "Baseball Card",
    "j_bull": "Bull",
    "j_diet_cola": "Diet Cola",
    "j_trading": "Trading Card",
    "j_flash": "Flash Card",
    "j_popcorn": "Popcorn",
    "j_trousers": "Spare Trousers",
    "j_ancient": "Ancient Joker",
    "j_ramen": "Ramen",
    "j_walkie_talkie": "Walkie Talkie",
    "j_selzer": "Seltzer",
    "j_castle": "Castle",
    "j_smiley": "Smiley Face",
    "j_campfire": "Campfire",
    "j_ticket": "Golden Ticket",
    "j_mr_bones": "Mr. Bones",
    "j_acrobat": "Acrobat",
    "j_sock_and_buskin": "Sock and Buskin",
    "j_swashbuckler": "Swashbuckler",
    "j_troubadour": "Troubadour",
    "j_certificate": "Certificate",
    "j_smeared": "Smeared Joker",
    "j_throwback": "Throwback",
    "j_hanging_chad": "Hanging Chad",
    "j_rough_gem": "Rough Gem",
    "j_bloodstone": "Bloodstone",
    "j_arrowhead": "Arrowhead",
    "j_onyx_agate": "Onyx Agate",
    "j_glass": "Glass Joker",
    "j_ring_master": "Showman",
    "j_flower_pot": "Flower Pot",
    "j_blueprint": "Blueprint",
    "j_wee": "Wee Joker",
    "j_merry_andy": "Merry Andy",
    "j_oops": "Oops! All 6s",
    "j_idol": "The Idol",
    "j_seeing_double": "Seeing Double",
    "j_matador": "Matador",
    "j_hit_the_road": "Hit the Road",
    "j_duo": "The Duo",
    "j_trio": "The Trio",
    "j_family": "The Family",
    "j_order": "The Order",
    "j_tribe": "The Tribe",
    "j_stuntman": "Stuntman",
    "j_invisible": "Invisible Joker",
    "j_brainstorm": "Brainstorm",
    "j_satellite": "Satellite",
    "j_shoot_the_moon": "Shoot the Moon",
    "j_drivers_license": "Driver's License",
    "j_cartomancer": "Cartomancer",
    "j_astronomer": "Astronomer",
    "j_burnt": "Burnt Joker",
    "j_bootstraps": "Bootstraps",
    "j_caino": "Canio",
    "j_triboulet": "Triboulet",
    "j_yorick": "Yorick",
    "j_chicot": "Chicot",
    "j_perkeo": "Perkeo",
}

TAROT_LABELS: dict[str, str] = {
    "c_fool": "The Fool",
    "c_magician": "The Magician",
    "c_high_priestess": "The High Priestess",
    "c_empress": "The Empress",
    "c_emperor": "The Emperor",
    "c_heirophant": "The Hierophant",
    "c_lovers": "The Lovers",
    "c_chariot": "The Chariot",
    "c_justice": "Justice",
    "c_hermit": "The Hermit",
    "c_wheel_of_fortune": "The Wheel of Fortune",
    "c_strength": "Strength",
    "c_hanged_man": "The Hanged Man",
    "c_death": "Death",
    "c_temperance": "Temperance",
    "c_devil": "The Devil",
    "c_tower": "The Tower",
    "c_star": "The Star",
    "c_moon": "The Moon",
    "c_sun": "The Sun",
    "c_judgement": "Judgement",
    "c_world": "The World",
}

PLANET_LABELS: dict[str, str] = {
    "c_mercury": "Mercury",
    "c_venus": "Venus",
    "c_earth": "Earth",
    "c_mars": "Mars",
    "c_jupiter": "Jupiter",
    "c_saturn": "Saturn",
    "c_uranus": "Uranus",
    "c_neptune": "Neptune",
    "c_pluto": "Pluto",
    "c_planet_x": "Planet X",
    "c_ceres": "Ceres",
    "c_eris": "Eris",
}

SPECTRAL_LABELS: dict[str, str] = {
    "c_familiar": "Familiar",
    "c_grim": "Grim",
    "c_incantation": "Incantation",
    "c_talisman": "Talisman",
    "c_aura": "Aura",
    "c_wraith": "Wraith",
    "c_sigil": "Sigil",
    "c_ouija": "Ouija",
    "c_ectoplasm": "Ectoplasm",
    "c_immolate": "Immolate",
    "c_ankh": "Ankh",
    "c_deja_vu": "Deja Vu",
    "c_hex": "Hex",
    "c_trance": "Trance",
    "c_medium": "Medium",
    "c_cryptid": "Cryptid",
    "c_soul": "The Soul",
    "c_black_hole": "Black Hole",
}

VOUCHER_LABELS: dict[str, str] = {
    "v_overstock_norm": "Overstock",
    "v_clearance_sale": "Clearance Sale",
    "v_hone": "Hone",
    "v_reroll_surplus": "Reroll Surplus",
    "v_crystal_ball": "Crystal Ball",
    "v_telescope": "Telescope",
    "v_grabber": "Grabber",
    "v_wasteful": "Wasteful",
    "v_tarot_merchant": "Tarot Merchant",
    "v_planet_merchant": "Planet Merchant",
    "v_seed_money": "Seed Money",
    "v_blank": "Blank",
    "v_magic_trick": "Magic Trick",
    "v_hieroglyph": "Hieroglyph",
    "v_directors_cut": "Director's Cut",
    "v_paint_brush": "Paint Brush",
    "v_overstock_plus": "Overstock Plus",
    "v_liquidation": "Liquidation",
    "v_glow_up": "Glow Up",
    "v_reroll_glut": "Reroll Glut",
    "v_omen_globe": "Omen Globe",
    "v_observatory": "Observatory",
    "v_nacho_tong": "Nacho Tong",
    "v_recyclomancy": "Recyclomancy",
    "v_tarot_tycoon": "Tarot Tycoon",
    "v_planet_tycoon": "Planet Tycoon",
    "v_money_tree": "Money Tree",
    "v_antimatter": "Antimatter",
    "v_illusion": "Illusion",
    "v_petroglyph": "Petroglyph",
    "v_retcon": "Retcon",
    "v_palette": "Palette",
}

BOSSES: dict[str, dict] = {
    "The Hook": {
        "effect": "After each hand played, 2 random unplayed cards are discarded from hand.",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Hook",
    },
    "The Ox": {
        "effect": "Playing the most-played hand type this run sets money to $0.",
        "score_mult": "2x",
        "min_ante": 6,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Ox",
    },
    "The House": {
        "effect": "The first drawn hand is all face-down.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_House",
    },
    "The Wall": {
        "effect": "Extra large blind: requires 4× base score. Luchador or Chicot can reduce it to 2×.",
        "score_mult": "4x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Wall",
    },
    "The Wheel": {
        "effect": "Each drawn card has a 1 in 7 chance of being face-down.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Wheel",
    },
    "The Arm": {
        "effect": "Permanently reduces the level of the played hand type by 1 (minimum level 1). Applied before scoring.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Arm",
    },
    "The Club": {
        "effect": "All Club cards are debuffed and cannot be scoring cards.",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Club",
    },
    "The Fish": {
        "effect": "After each hand played, newly drawn cards are face-down.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Fish",
    },
    "The Psychic": {
        "effect": "Must play exactly 5 cards each hand (not all need to score).",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Psychic",
    },
    "The Goad": {
        "effect": "All Spade cards are debuffed and cannot be scoring cards.",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Goad",
    },
    "The Water": {
        "effect": "0 discards available this blind.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Water",
    },
    "The Window": {
        "effect": "All Diamond cards are debuffed and cannot be scoring cards.",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Window",
    },
    "The Manacle": {
        "effect": "-1 hand size.",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Manacle",
    },
    "The Eye": {
        "effect": "Each hand type can only be played once per blind.",
        "score_mult": "2x",
        "min_ante": 3,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Eye",
    },
    "The Mouth": {
        "effect": "Can only play one hand type this blind. After the first hand, must repeat that same type.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Mouth",
    },
    "The Plant": {
        "effect": "All face cards (J, Q, K) are debuffed.",
        "score_mult": "2x",
        "min_ante": 4,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Plant",
    },
    "The Serpent": {
        "effect": "After each play or discard, always draw exactly 3 cards regardless of hand size limit.",
        "score_mult": "2x",
        "min_ante": 5,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Serpent",
    },
    "The Pillar": {
        "effect": "Cards played during Small and Big blinds this Ante are debuffed.",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Pillar",
    },
    "The Needle": {
        "effect": "Only 1 hand allowed per round. Discards are still available.",
        "score_mult": "1x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Needle",
    },
    "The Head": {
        "effect": "All Heart cards are debuffed and cannot be scoring cards.",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Head",
    },
    "The Tooth": {
        "effect": "-$1 for each card played.",
        "score_mult": "2x",
        "min_ante": 3,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Tooth",
    },
    "The Flint": {
        "effect": "Base chips and mult of all hand types are halved this blind.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Flint",
    },
    "The Mark": {
        "effect": "All face cards are drawn face-down.",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Mark",
    },
    "Amber Acorn": {
        "effect": "Flips and shuffles all Jokers.",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Amber_Acorn",
    },
    "Verdant Leaf": {
        "effect": "All cards are debuffed until 1 Joker is sold.",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/Verdant_Leaf",
    },
    "Violet Vessel": {
        "effect": "Extra large blind: requires 6× base score. Luchador or Chicot can reduce it to 2×.",
        "score_mult": "6x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Violet_Vessel",
    },
    "Crimson Heart": {
        "effect": "Each hand, one random Joker is debuffed. The debuffed Joker changes each hand.",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Crimson_Heart",
    },
    "Cerulean Bell": {
        "effect": "One card is always forced into the selection.",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Cerulean_Bell",
    },
}

TAGS: dict[str, dict] = {
    "Boss Tag": {
        "effect": "Rerolls the next Boss Blind.",
        "wiki": "https://balatrowiki.org/w/Boss_Tag",
    },
    "Buffoon Tag": {
        "effect": "Free Mega Buffoon Pack.",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Buffoon_Tag",
    },
    "Charm Tag": {
        "effect": "Free Mega Arcana Pack.",
        "wiki": "https://balatrowiki.org/w/Charm_Tag",
    },
    "Coupon Tag": {
        "effect": "On first entry to the next shop, all initial Jokers, consumables, and packs are free.",
        "limits": "Vouchers are not included. Items added after a reroll are not included.",
        "wiki": "https://balatrowiki.org/w/Coupon_Tag",
    },
    "D6 Tag": {
        "effect": "Reroll cost starts at $0 in the next shop.",
        "wiki": "https://balatrowiki.org/w/D6_Tag",
    },
    "Double Tag": {
        "effect": "Copies the next Tag obtained (cannot copy itself).",
        "wiki": "https://balatrowiki.org/w/Double_Tag",
    },
    "Economy Tag": {
        "effect": "After skipping, doubles current money up to a maximum of $40.",
        "wiki": "https://balatrowiki.org/w/Economy_Tag",
    },
    "Ethereal Tag": {
        "effect": "Free Spectral Pack.",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Ethereal_Tag",
    },
    "Foil Tag": {
        "effect": "A random base Joker in the next shop is free with Foil edition.",
        "wiki": "https://balatrowiki.org/w/Foil_Tag",
    },
    "Garbage Tag": {
        "effect": "Earn $1 for each unused discard this round (paid at skip time based on remaining discards).",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Garbage_Tag",
    },
    "Handy Tag": {
        "effect": "Earn $1 for each hand played this round (paid at skip time based on hands played so far).",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Handy_Tag",
    },
    "Holographic Tag": {
        "effect": "A random base Joker in the next shop is free with Holographic edition.",
        "wiki": "https://balatrowiki.org/w/Holographic_Tag",
    },
    "Investment Tag": {
        "effect": "Earn +$25 after defeating the next Boss Blind. Stackable.",
        "wiki": "https://balatrowiki.org/w/Investment_Tag",
    },
    "Juggle Tag": {
        "effect": "+3 hand size for the next round.",
        "wiki": "https://balatrowiki.org/w/Juggle_Tag",
    },
    "Meteor Tag": {
        "effect": "Free Mega Celestial Pack.",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Meteor_Tag",
    },
    "Negative Tag": {
        "effect": "A random base Joker in the next shop is free with Negative edition.",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Negative_Tag",
    },
    "Orbital Tag": {
        "effect": "Upgrade one selected hand type by 3 levels.",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Orbital_Tag",
    },
    "Polychrome Tag": {
        "effect": "A random base Joker in the next shop is free with Polychrome edition.",
        "wiki": "https://balatrowiki.org/w/Polychrome_Tag",
    },
    "Rare Tag": {
        "effect": "A free Rare Joker appears in the next shop (occupies a shop slot).",
        "wiki": "https://balatrowiki.org/w/Rare_Tag",
    },
    "Speed Tag": {
        "effect": "Earn $5 for each Blind skipped this run (at least $5 when obtained).",
        "wiki": "https://balatrowiki.org/w/Speed_Tag",
    },
    "Standard Tag": {
        "effect": "Free Mega Standard Pack.",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Standard_Tag",
    },
    "Top-up Tag": {
        "effect": "Generates up to 2 Common Jokers (requires available Joker slots).",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Top-up_Tag",
    },
    "Uncommon Tag": {
        "effect": "A free Uncommon Joker appears in the next shop (occupies a shop slot).",
        "wiki": "https://balatrowiki.org/w/Uncommon_Tag",
    },
    "Voucher Tag": {
        "effect": "An additional Voucher appears in the next shop.",
        "wiki": "https://balatrowiki.org/w/Voucher_Tag",
    },
}

JOKER_OVERRIDES: dict[str, dict] = {
    "Oops! All 6s": {
        "effect": "Doubles all X-in-Y probabilities (e.g. 1/3→2/3, 1/5→2/5), including negative ones such as Glass shattering, Gros Michel extinction, and Wheel of Fortune dark card.",
    },
    "Wee Joker": {
        "effect": "Starts at +0 Chips; gains +8 Chips permanently each time a 2 is scored in the scoring hand. Each retrigger (Hack, Dusk, Red Seal, etc.) counts as a separate scoring event and adds another +8.",
    },
    "To Do List": {
        "effect": "Each round randomly targets one poker hand type; scores +$4 when that exact hand type is played and scored. Target changes at end of round. Multiple copies have independent random targets.",
        "notes": "Gives money, not Mult. Must match the hand type exactly — Full House does not satisfy a Two Pair target.",
    },
    "Dusk": {
        "effect": "On the final hand of a blind, all played cards retrigger twice.",
        "notes": "Retriggers apply to individual card scoring (chips, enhancements, editions), not to the total hand multiplier. When Needle forces exactly 1 hand per round, that hand is always the final hand.",
    },
    "Joker Stencil": {
        "effect": "Each empty Joker slot, including the slot occupied by Stencil itself, contributes ×1 Mult. Multiple Stencils multiply together.",
        "notes": "This is an XMult effect, not flat +Mult.",
    },
    "Misprint": {
        "effect": "Adds a random +0 to +23 flat Mult each hand (uniform distribution, expected ~+11.5).",
        "notes": "High variance: can roll 0.",
    },
    "Blueprint": {
        "notes": "Copies the Joker immediately to its right. Incompatible with Oops! All 6s.",
    },
    "Brainstorm": {
        "notes": "Copies the leftmost Joker. Incompatible with Oops! All 6s.",
    },
}

PLANET_OVERRIDES: dict[str, dict] = {
    "Mars": {
        "notes": "Upgrades Four of a Kind, not Three of a Kind.",
    },
}

STAKES: dict[str, dict] = {
    "WHITE": {
        "effect": "Base difficulty, no additional modifiers.",
        "wiki": "https://balatrowiki.org/w/Stakes#White_Stake",
    },
    "RED": {
        "effect": "Winning the Small Blind gives no money. Big and Boss Blinds still pay.",
        "wiki": "https://balatrowiki.org/w/Stakes#Red_Stake",
    },
    "GREEN": {
        "effect": "Required score scales faster with Ante (stacks with Red Stake).",
        "wiki": "https://balatrowiki.org/w/Stakes#Green_Stake",
    },
    "BLACK": {
        "effect": "Shop Jokers have a 30% chance of having an Eternal sticker (cannot be sold or destroyed).",
        "wiki": "https://balatrowiki.org/w/Stakes#Black_Stake",
    },
    "BLUE": {
        "effect": "-1 discard per round (stacks with previous stakes).",
        "wiki": "https://balatrowiki.org/w/Stakes#Blue_Stake",
    },
    "PURPLE": {
        "effect": "Required score scales faster (stacks with previous stakes).",
        "wiki": "https://balatrowiki.org/w/Stakes#Purple_Stake",
    },
    "ORANGE": {
        "effect": "Perishable Jokers can appear in the shop (self-destruct after a set number of rounds).",
        "wiki": "https://balatrowiki.org/w/Stakes#Orange_Stake",
    },
    "GOLD": {
        "effect": "Rental Jokers can appear in the shop (costs $1 per round).",
        "wiki": "https://balatrowiki.org/w/Stakes#Gold_Stake",
    },
}


def parse_api_section(text: str, prefix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = TABLE_ROW.match(line)
        if not m:
            continue
        key, effect = m.group(1), m.group(2).strip()
        if key.startswith(prefix):
            out[key] = effect
    return out


def fact_only(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k not in FACT_ONLY_DROP_FIELDS}


def fact_only_table(table: dict[str, dict]) -> dict[str, dict]:
    return {label: fact_only(entry) for label, entry in table.items()}


def merge_entries(base: dict[str, dict], overrides: dict) -> dict[str, dict]:
    merged = dict(base)
    for label, extra in overrides.items():
        if label in merged:
            merged[label] = {**merged[label], **extra}
        else:
            merged[label] = extra
    return fact_only_table(merged)


def wiki_slug(label: str) -> str:
    return label.replace(" ", "_").replace("!", "%21").replace("'", "%27")


def build_cards(
    keys: dict[str, str], labels: dict[str, str], kind: str
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for key, effect in sorted(keys.items()):
        label = labels.get(key, key)
        out[label] = {
            "key": key,
            "effect": effect,
            "wiki": f"https://balatrowiki.org/w/{wiki_slug(label)}",
        }
    return out


def main() -> None:
    if not API_MD.is_file():
        raise SystemExit(f"Missing {API_MD}")

    api_text = API_MD.read_text(encoding="utf-8")
    joker_keys = parse_api_section(api_text, "j_")
    tarot_keys = parse_api_section(api_text, "c_fool") | parse_api_section(
        api_text, "c_magician"
    )
    # tarot/planet/spectral share c_ prefix — split by known label sets
    all_c = parse_api_section(api_text, "c_")
    tarot_keys = {k: v for k, v in all_c.items() if k in TAROT_LABELS}
    planet_keys = {k: v for k, v in all_c.items() if k in PLANET_LABELS}
    spectral_keys = {k: v for k, v in all_c.items() if k in SPECTRAL_LABELS}
    voucher_keys = parse_api_section(api_text, "v_")

    jokers = merge_entries(
        build_cards(joker_keys, JOKER_LABELS, "joker"), JOKER_OVERRIDES
    )
    planets = merge_entries(
        build_cards(planet_keys, PLANET_LABELS, "planet"), PLANET_OVERRIDES
    )

    tags = fact_only_table(TAGS)
    for tag in tags.values():
        tag["trigger"] = TAG_SKIP_TRIGGER

    outputs = {
        "balatro-jokers-verified.json": jokers,
        "balatro-bosses-verified.json": fact_only_table(BOSSES),
        "balatro-tags-verified.json": tags,
        "balatro-stakes-verified.json": fact_only_table(STAKES),
        "balatro-tarots-verified.json": fact_only_table(
            build_cards(tarot_keys, TAROT_LABELS, "tarot")
        ),
        "balatro-planets-verified.json": planets,
        "balatro-spectrals-verified.json": fact_only_table(
            build_cards(spectral_keys, SPECTRAL_LABELS, "spectral")
        ),
        "balatro-vouchers-verified.json": fact_only_table(
            build_cards(voucher_keys, VOUCHER_LABELS, "voucher")
        ),
    }

    for fname, data in outputs.items():
        path = ROOT / fname
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Wrote {path.name}: {len(data)} entries")

    if len(joker_keys) != 150:
        print(f"WARNING: expected 150 jokers, got {len(joker_keys)}")
    if len(BOSSES) != 28:
        print(f"WARNING: expected 28 bosses, got {len(BOSSES)}")
    if len(TAGS) != 24:
        print(f"WARNING: expected 24 tags, got {len(TAGS)}")


if __name__ == "__main__":
    main()

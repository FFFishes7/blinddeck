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
TAG_SKIP_TRIGGER = "跳过当前 Blind 时获得该 Tag；打过该 Blind 不会获得。"

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
        "effect": "每打出一手后，随机弃掉手中 2 张未打出的牌。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Hook",
    },
    "The Ox": {
        "effect": "打出本 run 最常打的牌型 → 资金归 $0。",
        "score_mult": "2x",
        "min_ante": 6,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Ox",
    },
    "The House": {
        "effect": "第一手抽牌全部面朝下。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_House",
    },
    "The Wall": {
        "effect": "超大盲注：需 4× base 分（Luchador/Chicot 可降回 2×）。",
        "score_mult": "4x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Wall",
    },
    "The Wheel": {
        "effect": "1/7 概率抽到的牌面朝下。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Wheel",
    },
    "The Arm": {
        "effect": "打出的牌型等级永久 -1（最低 1 级，在计分前生效）。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Arm",
    },
    "The Club": {
        "effect": "梅花 debuff：不能当计分牌。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Club",
    },
    "The Fish": {
        "effect": "每手打出后新抽的牌面朝下。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Fish",
    },
    "The Psychic": {
        "effect": "每手必须打出恰好 5 张牌（不必全部计分）。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "strategy": "Four Fingers 4 张成顺/花 + 1 废牌；减手牌构筑极危险。",
        "wiki": "https://balatrowiki.org/w/The_Psychic",
    },
    "The Goad": {
        "effect": "黑桃 debuff：不能当计分牌。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Goad",
    },
    "The Water": {
        "effect": "本盲注 0 discard。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Water",
    },
    "The Window": {
        "effect": "方块 debuff：不能当计分牌。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Window",
    },
    "The Manacle": {
        "effect": "手牌上限 -1。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": False,
        "strategy": "Juggler/Troubadour/Turtle Bean/Juggle Tag 抵消。",
        "wiki": "https://balatrowiki.org/w/The_Manacle",
    },
    "The Eye": {
        "effect": "本盲注每种牌型只能打一次。",
        "score_mult": "2x",
        "min_ante": 3,
        "matador": True,
        "strategy": "最后一手留爆发；勿弱牌收尾。",
        "wiki": "https://balatrowiki.org/w/The_Eye",
    },
    "The Mouth": {
        "effect": "本盲注只能打一种牌型（之后只能重复该型）。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Mouth",
    },
    "The Plant": {
        "effect": "所有人头牌 debuff。",
        "score_mult": "2x",
        "min_ante": 4,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Plant",
    },
    "The Serpent": {
        "effect": "每次 play 或 discard 后固定抽 3 张（无视手牌上限）。",
        "score_mult": "2x",
        "min_ante": 5,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Serpent",
    },
    "The Pillar": {
        "effect": "本 Ante 之前在 Small/Big 打过的牌 debuff。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Pillar",
    },
    "The Needle": {
        "effect": "整轮仅 1 hand；discard 仍可用。",
        "score_mult": "1x",
        "min_ante": 2,
        "matador": False,
        "strategy": "Boss 前须 Planet/构筑到位；Dusk/Acrobat 仍吃「最后一手」。",
        "wiki": "https://balatrowiki.org/w/The_Needle",
    },
    "The Head": {
        "effect": "红心 debuff：不能当计分牌。",
        "score_mult": "2x",
        "min_ante": 1,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Head",
    },
    "The Tooth": {
        "effect": "每打出一张牌 -$1。",
        "score_mult": "2x",
        "min_ante": 3,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/The_Tooth",
    },
    "The Flint": {
        "effect": "本盲注所有牌型的 base chips 和 mult 减半。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/The_Flint",
    },
    "The Mark": {
        "effect": "所有人头牌抽牌时面朝下。",
        "score_mult": "2x",
        "min_ante": 2,
        "matador": False,
        "strategy": "1 张高牌 + 人头构筑。",
        "wiki": "https://balatrowiki.org/w/The_Mark",
    },
    "Amber Acorn": {
        "effect": "翻转并洗牌所有小丑。",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Amber_Acorn",
    },
    "Verdant Leaf": {
        "effect": "所有牌 debuff，直到卖掉 1 张小丑。",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": True,
        "wiki": "https://balatrowiki.org/w/Verdant_Leaf",
    },
    "Violet Vessel": {
        "effect": "超大盲注：需 6× base 分（Luchador/Chicot 可降回 2×）。",
        "score_mult": "6x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Violet_Vessel",
    },
    "Crimson Heart": {
        "effect": "每手随机 debuff 一张小丑（每手换一张）。",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Crimson_Heart",
    },
    "Cerulean Bell": {
        "effect": "强制始终选中 1 张牌。",
        "score_mult": "2x",
        "min_ante": 8,
        "showdown": True,
        "matador": False,
        "wiki": "https://balatrowiki.org/w/Cerulean_Bell",
    },
}

TAGS: dict[str, dict] = {
    "Boss Tag": {
        "effect": "重 roll 下一个 Boss Blind。",
        "wiki": "https://balatrowiki.org/w/Boss_Tag",
    },
    "Buffoon Tag": {
        "effect": "免费 Mega Buffoon Pack。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Buffoon_Tag",
    },
    "Charm Tag": {
        "effect": "免费 Mega Arcana Pack。",
        "wiki": "https://balatrowiki.org/w/Charm_Tag",
    },
    "Coupon Tag": {
        "effect": "下一家店首次进店时，初始小丑/消耗品/补充包免费。",
        "limits": "券不含；reroll 后新商品不含。",
        "wiki": "https://balatrowiki.org/w/Coupon_Tag",
    },
    "D6 Tag": {
        "effect": "下一家店 reroll 起始 $0。",
        "wiki": "https://balatrowiki.org/w/D6_Tag",
    },
    "Double Tag": {
        "effect": "复制「下一个」获得的 Tag（不能复制自身）。",
        "wiki": "https://balatrowiki.org/w/Double_Tag",
    },
    "Economy Tag": {
        "effect": "skip 后按当前资金翻倍，上限 $40。",
        "wiki": "https://balatrowiki.org/w/Economy_Tag",
    },
    "Ethereal Tag": {
        "effect": "免费 Spectral Pack。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Ethereal_Tag",
    },
    "Foil Tag": {
        "effect": "下一家店某初始 base 小丑免费且带 Foil。",
        "wiki": "https://balatrowiki.org/w/Foil_Tag",
    },
    "Garbage Tag": {
        "effect": "本局每次未使用的 discard 得 $1（skip 时按当前剩余 discard 结算）。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Garbage_Tag",
    },
    "Handy Tag": {
        "effect": "本局每打出过一次 hand 得 $1（skip 时按已打 hand 数结算）。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Handy_Tag",
    },
    "Holographic Tag": {
        "effect": "下一家店某初始 base 小丑免费且带 Holographic。",
        "wiki": "https://balatrowiki.org/w/Holographic_Tag",
    },
    "Investment Tag": {
        "effect": "击败下一个 Boss 后 +$25；可叠加。",
        "wiki": "https://balatrowiki.org/w/Investment_Tag",
    },
    "Juggle Tag": {
        "effect": "下一轮 +3 手牌上限。",
        "wiki": "https://balatrowiki.org/w/Juggle_Tag",
    },
    "Meteor Tag": {
        "effect": "免费 Mega Celestial Pack。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Meteor_Tag",
    },
    "Negative Tag": {
        "effect": "下一家店某初始 base 小丑免费且带 Negative。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Negative_Tag",
    },
    "Orbital Tag": {
        "effect": "选一个牌型 +3 级。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Orbital_Tag",
    },
    "Polychrome Tag": {
        "effect": "下一家店某初始 base 小丑免费且带 Polychrome。",
        "wiki": "https://balatrowiki.org/w/Polychrome_Tag",
    },
    "Rare Tag": {
        "effect": "下一家店生成一张免费 Rare 小丑（占 shop 槽）。",
        "notes": "需已解锁 Blueprint 才出现。",
        "wiki": "https://balatrowiki.org/w/Rare_Tag",
    },
    "Speed Tag": {
        "effect": "本 run 每 skip 过一个 Blind 得 $5（skip 时至少 $5）。",
        "wiki": "https://balatrowiki.org/w/Speed_Tag",
    },
    "Standard Tag": {
        "effect": "免费 Mega Standard Pack。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Standard_Tag",
    },
    "Top-up Tag": {
        "effect": "生成最多 2 张 Common 小丑（需有空槽）。",
        "min_ante": 2,
        "wiki": "https://balatrowiki.org/w/Top-up_Tag",
    },
    "Uncommon Tag": {
        "effect": "下一家店生成一张免费 Uncommon 小丑（占 shop 槽）。",
        "wiki": "https://balatrowiki.org/w/Uncommon_Tag",
    },
    "Voucher Tag": {
        "effect": "下一家店额外出现一张券。",
        "wiki": "https://balatrowiki.org/w/Voucher_Tag",
    },
}

STAKES: dict[str, dict] = {
    "WHITE": {
        "effect": "基础难度，无额外 modifier。",
        "wiki": "https://balatrowiki.org/w/Stakes#White_Stake",
    },
    "RED": {
        "effect": "Small Blind 打赢不给钱（Big/Boss 仍给）。",
        "wiki": "https://balatrowiki.org/w/Stakes#Red_Stake",
    },
    "GREEN": {
        "effect": "需求分随 Ante 涨得更快（叠在 Red 上）。",
        "wiki": "https://balatrowiki.org/w/Stakes#Green_Stake",
    },
    "BLACK": {
        "effect": "商店 30% Eternal 贴纸（不可卖/毁）。",
        "wiki": "https://balatrowiki.org/w/Stakes#Black_Stake",
    },
    "BLUE": {
        "effect": "-1 discard（叠在前序 stake 上）。",
        "wiki": "https://balatrowiki.org/w/Stakes#Blue_Stake",
    },
    "PURPLE": {
        "effect": "需求分涨得更快（叠在前序 stake 上）。",
        "wiki": "https://balatrowiki.org/w/Stakes#Purple_Stake",
    },
    "ORANGE": {
        "effect": "商店可出现 Perishable 小丑（N 回合后自毁）。",
        "wiki": "https://balatrowiki.org/w/Stakes#Orange_Stake",
    },
    "GOLD": {
        "effect": "商店可出现 Rental 小丑（每回合 -$1）。",
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


def load_overrides(name: str) -> dict:
    path = ROOT / f"balatro-{name}-overrides.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


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

    jokers = build_cards(joker_keys, JOKER_LABELS, "joker")
    jokers = merge_entries(jokers, load_overrides("jokers"))

    planets = build_cards(planet_keys, PLANET_LABELS, "planet")
    planets = merge_entries(planets, load_overrides("planets"))

    tags = merge_entries(TAGS, load_overrides("tags"))
    for tag in tags.values():
        tag["trigger"] = TAG_SKIP_TRIGGER

    outputs = {
        "balatro-jokers-verified.json": fact_only_table(jokers),
        "balatro-bosses-verified.json": merge_entries(BOSSES, load_overrides("bosses")),
        "balatro-tags-verified.json": tags,
        "balatro-stakes-verified.json": merge_entries(STAKES, load_overrides("stakes")),
        "balatro-tarots-verified.json": fact_only_table(
            build_cards(tarot_keys, TAROT_LABELS, "tarot")
        ),
        "balatro-planets-verified.json": fact_only_table(planets),
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

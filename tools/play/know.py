"""Look up wiki-verified Balatro facts before deciding.

Usage:
    python know.py preflight          # fact gate: jokers + boss + stake + tags + core rules
    python know.py run                # jokers only
    python know.py check joker "Name"
    python know.py check boss "The Psychic"
    python know.py check tag "Coupon Tag"
    python know.py check stake RED
    python know.py check planet Mars
    python know.py check rule scoring_hand_only
    python know.py list jokers|bosses|tags|stakes|planets|tarots|vouchers|spectrals|rules
    python know.py stats              # library counts
"""

from __future__ import annotations

import json
import os
import sys
from difflib import get_close_matches
from pathlib import Path

from bot_client import APIError, rpc

KNOWLEDGE_DIR = Path(
    os.getenv(
        "BALATROBOT_KNOWLEDGE_DIR",
        Path(__file__).resolve().parents[2] / "knowledge" / "balatro",
    )
)

LIBRARIES = {
    "joker": "balatro-jokers-verified.json",
    "boss": "balatro-bosses-verified.json",
    "tag": "balatro-tags-verified.json",
    "stake": "balatro-stakes-verified.json",
    "planet": "balatro-planets-verified.json",
    "tarot": "balatro-tarots-verified.json",
    "voucher": "balatro-vouchers-verified.json",
    "spectral": "balatro-spectrals-verified.json",
    "rule": "balatro-rules-verified.json",
}

ALIASES = {
    "jokers": "joker",
    "bosses": "boss",
    "tags": "tag",
    "stakes": "stake",
    "planets": "planet",
    "tarots": "tarot",
    "vouchers": "voucher",
    "spectrals": "spectral",
    "rules": "rule",
}


def load_library(kind: str) -> dict:
    path = KNOWLEDGE_DIR / LIBRARIES[kind]
    if not path.is_file():
        print(f"Missing library: {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_name(kind: str, name: str, library: dict) -> str | None:
    key = name.strip()
    if key in library:
        return key
    lower_map = {k.lower(): k for k in library}
    if key.lower() in lower_map:
        return lower_map[key.lower()]
    matches = get_close_matches(key, library.keys(), n=3, cutoff=0.6)
    if len(matches) == 1:
        print(f"  (matched '{matches[0]}')")
        return matches[0]
    if matches:
        print(f"  ambiguous — did you mean: {', '.join(matches)}?")
    return None


def print_entry(label: str, entry: dict) -> None:
    print(f"VERIFIED: {label}")
    for key in (
        "key",
        "trigger",
        "effect",
        "limits",
        "notes",
        "score_mult",
        "min_ante",
        "title",
        "category",
        "rule",
        "source",
    ):
        if entry.get(key) is not None and entry.get(key) != "":
            title = {
                "key": "API key",
                "limits": "限制",
                "trigger": "触发",
                "notes": "备注",
                "score_mult": "分数倍率",
                "min_ante": "最早 Ante",
                "title": "标题",
                "category": "类别",
                "rule": "规则",
                "source": "来源",
            }.get(key, key)
            value = entry[key]
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            print(f"  {title}: {value}")
    if entry.get("wiki"):
        print(f"  wiki: {entry['wiki']}")


def check_kind(kind: str, name: str, library: dict | None = None) -> int:
    library = library or load_library(kind)
    resolved = resolve_name(kind, name, library)
    if not resolved:
        print(f"UNKNOWN {kind.upper()}: {name.strip()}")
        print(
            "  → 查 https://balatrowiki.org/ 后写入 overrides 并运行 build_knowledge.py"
        )
        print("  → 入库前禁止基于该项做决策")
        return 1
    print_entry(resolved, library[resolved])
    return 0


def cmd_list(kind: str) -> int:
    library = load_library(kind)
    for name in sorted(library):
        print(name)
    return 0


def cmd_stats() -> int:
    print("=== knowledge library stats ===")
    print(f"dir: {KNOWLEDGE_DIR}")
    for kind, fname in LIBRARIES.items():
        path = KNOWLEDGE_DIR / fname
        if path.is_file():
            n = len(json.loads(path.read_text(encoding="utf-8")))
            print(f"  {kind:10} {n:4}  {fname}")
        else:
            print(f"  {kind:10} MISS  {fname}")
    return 0


def cmd_run() -> int:
    try:
        state = rpc("gamestate")
    except APIError as e:
        print(f"RPC error: {e}", file=sys.stderr)
        return 1
    jokers = [c["label"] for c in state.get("jokers", {}).get("cards", [])]
    if not jokers:
        print("No jokers in current run.")
        return 0
    library = load_library("joker")
    failed = False
    for label in jokers:
        print("---")
        if check_kind("joker", label, library) != 0:
            failed = True
    if failed:
        print("\nGATE FAIL: 存在未验证小丑。")
        return 1
    print("\nGATE OK: 当前小丑均已验证。")
    return 0


def relevant_boss(state: dict) -> str | None:
    if state.get("blind", {}).get("type") == "BOSS":
        return state["blind"].get("name")
    for blind in state.get("blinds", {}).values():
        if blind.get("status") in ("CURRENT", "SELECT") and blind.get("type") == "BOSS":
            return blind.get("name")
        if blind.get("status") == "UPCOMING" and blind.get("type") == "BOSS":
            return blind.get("name")
    return None


def upcoming_tags(state: dict) -> list[tuple[str, str]]:
    out = []
    for slot, blind in state.get("blinds", {}).items():
        tag = blind.get("tag_name") or ""
        if tag and blind.get("status") in ("SELECT", "UPCOMING"):
            out.append((slot, tag))
    return out


def cmd_preflight() -> int:
    try:
        state = rpc("gamestate")
    except APIError as e:
        print(f"RPC error: {e}", file=sys.stderr)
        return 1

    failed = False
    print(
        f"=== preflight ante={state.get('ante_num')} state={state.get('state')} "
        f"stake={state.get('stake')} money={state.get('money')} ==="
    )

    stake = (state.get("stake") or "WHITE").upper()
    print("--- stake ---")
    if check_kind("stake", stake) != 0:
        failed = True

    print("--- jokers ---")
    joker_lib = load_library("joker")
    jokers = [c["label"] for c in state.get("jokers", {}).get("cards", [])]
    if not jokers:
        print("(none)")
    for label in jokers:
        print("---")
        if check_kind("joker", label, joker_lib) != 0:
            failed = True

    boss = relevant_boss(state)
    print("--- boss ---")
    if boss:
        if check_kind("boss", boss) != 0:
            failed = True
    else:
        print("(no boss targeted)")

    tags = upcoming_tags(state)
    if tags:
        print("--- tags (available only if that blind is skipped) ---")
        tag_lib = load_library("tag")
        for slot, tag in tags:
            print(f"[{slot}] {tag}")
            if check_kind("tag", tag, tag_lib) != 0:
                failed = True

    print("--- core rules ---")
    rule_lib = load_library("rule")
    for rule_key in (
        "scoring_hand_only",
        "held_in_hand_effects",
        "the_fool_copies_last_tarot_or_planet",
        "death_uses_rightmost_selected_card_as_target",
        "cartomancer_needs_consumable_space",
    ):
        if rule_key in rule_lib:
            print(f"  {rule_key}: {rule_lib[rule_key].get('rule', '')}")
        else:
            print(f"  missing rule: {rule_key}")
            failed = True

    if failed:
        print("\nPREFLIGHT FAIL")
        return 1
    print("\nPREFLIGHT OK")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "preflight":
        return cmd_preflight()
    if cmd == "run":
        return cmd_run()
    if cmd == "stats":
        return cmd_stats()
    if cmd == "list":
        if len(sys.argv) < 3:
            print(
                "Usage: python know.py list jokers|bosses|tags|stakes|planets|tarots|vouchers|spectrals|rules",
                file=sys.stderr,
            )
            return 2
        kind = ALIASES.get(sys.argv[2].lower())
        if not kind:
            print(f"Unknown library: {sys.argv[2]}", file=sys.stderr)
            return 2
        return cmd_list(kind)
    if cmd == "check":
        if len(sys.argv) < 4:
            print(
                'Usage: python know.py check joker|boss|tag|stake|planet|tarot|voucher|spectral|rule "Name"',
                file=sys.stderr,
            )
            return 2
        kind = ALIASES.get(sys.argv[2].lower(), sys.argv[2].lower())
        if kind not in LIBRARIES:
            print(f"Unknown kind: {sys.argv[2]}", file=sys.stderr)
            return 2
        name = " ".join(sys.argv[3:])
        return check_kind(kind, name)
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

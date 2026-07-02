"""Look up wiki-verified Balatro facts before deciding.

Usage:
    python know.py preflight          # fact gate: stake + jokers + boss + tags
    python know.py check joker "Name"
    python know.py check boss "The Psychic"
    python know.py check tag "Coupon Tag"
    python know.py check stake RED
    python know.py check planet Mars
    python know.py check rule scoring_hand_only
    python know.py list jokers|bosses|tags|stakes|planets|tarots|vouchers|spectrals|rules
    python know.py list jokers wrap   # substring filter (case-insensitive)
    python know.py check joker "Mad Joker" --json   # JSON output (null if unknown)
    python know.py list jokers --json              # JSON array of names
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


def resolve_name(
    kind: str, name: str, library: dict, quiet: bool = False
) -> str | None:
    key = name.strip()
    if key in library:
        return key
    lower_map = {k.lower(): k for k in library}
    if key.lower() in lower_map:
        return lower_map[key.lower()]
    matches = get_close_matches(key, library.keys(), n=3, cutoff=0.6)
    if len(matches) == 1:
        if not quiet:
            print(f"  (matched '{matches[0]}')")
        return matches[0]
    if matches and not quiet:
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
        value = entry.get(key)
        if value is not None and value != "":
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            print(f"  {key}: {value}")
    if entry.get("wiki"):
        print(f"  wiki: {entry['wiki']}")


def check_kind(
    kind: str, name: str, library: dict | None = None, json_mode: bool = False
) -> int:
    library = library or load_library(kind)
    resolved = resolve_name(kind, name, library, quiet=json_mode)
    if not resolved:
        if json_mode:
            print("null")
        else:
            print(f"UNKNOWN {kind.upper()}: {name.strip()}")
        return 1
    entry = library[resolved]
    if json_mode:
        out = {"name": resolved, **entry}
        print(json.dumps(out, ensure_ascii=False))
    else:
        print_entry(resolved, entry)
    return 0


def cmd_list(kind: str, substring: str | None = None, json_mode: bool = False) -> int:
    library = load_library(kind)
    names = sorted(library)
    if substring:
        sub = substring.lower()
        names = [n for n in names if sub in n.lower()]
    if json_mode:
        print(json.dumps(names, ensure_ascii=False))
    else:
        for n in names:
            print(n)
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


def relevant_boss(state: dict) -> str | None:
    for blind in state.get("blinds", {}).values():
        if blind.get("type") == "BOSS" and blind.get("status") in (
            "CURRENT",
            "SELECT",
            "UPCOMING",
        ):
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

    if failed:
        print("\nPREFLIGHT FAIL")
        return 1
    print("\nPREFLIGHT OK")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    argv = sys.argv[1:]
    json_mode = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    cmd = argv[0]
    if cmd == "preflight":
        return cmd_preflight()
    if cmd == "stats":
        return cmd_stats()
    if cmd == "list":
        if len(argv) < 2:
            print(
                "Usage: python know.py list jokers|bosses|tags|stakes|planets|tarots|vouchers|spectrals|rules [substring] [--json]",
                file=sys.stderr,
            )
            return 2
        kind = ALIASES.get(argv[1].lower())
        if not kind:
            print(f"Unknown library: {argv[1]}", file=sys.stderr)
            return 2
        substring = argv[2] if len(argv) > 2 else None
        return cmd_list(kind, substring=substring, json_mode=json_mode)
    if cmd == "check":
        if len(argv) < 3:
            print(
                'Usage: python know.py check joker|boss|tag|stake|planet|tarot|voucher|spectral|rule "Name" [--json]',
                file=sys.stderr,
            )
            return 2
        kind = ALIASES.get(argv[1].lower(), argv[1].lower())
        if kind not in LIBRARIES:
            print(f"Unknown kind: {argv[1]}", file=sys.stderr)
            return 2
        name = " ".join(argv[2:])
        return check_kind(kind, name, json_mode=json_mode)
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

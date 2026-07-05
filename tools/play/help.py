"""Formatted command help for ``bot.ps1 help``."""

from __future__ import annotations

import json
import sys
from typing import Any

from actions import build_actions
from bot_client import APIError
from commands import format_friendly_action
from envelope import HELP_FORMAT, build_error_envelope, build_help_envelope
from help_catalog import CATEGORY_TITLES, CatalogCategory, catalog_entries
from layers import normalize_play_state
from state import fetch_stable_gamestate

JSON_FLAG = "--json"
NOW_FLAG = "--now"

_CATEGORY_ORDER: tuple[CatalogCategory, ...] = (
    "play",
    "read",
    "know",
    "advanced",
    "hidden",
)


def _parse_argv(argv: list[str]) -> tuple[bool, bool]:
    json_out = False
    now = False
    for arg in argv:
        if arg == JSON_FLAG:
            json_out = True
        elif arg == NOW_FLAG:
            now = True
        else:
            raise ValueError(f"unknown help flag: {arg}")
    return json_out, now


def _catalog_payload() -> list[dict[str, str]]:
    return [
        {
            "example": e.example,
            "description": e.description,
            "category": e.category,
        }
        for e in catalog_entries()
    ]


def _valid_now_payload(state: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_play_state(state)
    play_state = normalized.get("state", "UNKNOWN")
    actions: list[dict[str, str]] = []
    for action in build_actions(normalized):
        example = format_friendly_action(action)
        if not example:
            continue
        actions.append(
            {
                "example": example,
                "description": action.get("description") or "",
            }
        )
    return {"state": play_state, "actions": actions}


def format_help_text(
    *,
    valid_now: dict[str, Any] | None = None,
    valid_now_error: str | None = None,
) -> str:
    lines = ["BlindDeck commands (.\\tools\\play\\bot.ps1 <example>)", ""]
    by_category: dict[CatalogCategory, list] = {c: [] for c in _CATEGORY_ORDER}
    for entry in catalog_entries():
        by_category[entry.category].append(entry)

    for category in _CATEGORY_ORDER:
        entries = by_category[category]
        if not entries:
            continue
        lines.append(f"== {CATEGORY_TITLES[category]} ==")
        for entry in entries:
            lines.append(f"  {entry.example}")
            lines.append(f"    {entry.description}")
        lines.append("")

    if valid_now:
        lines.append(f"== Valid now ({valid_now['state']}) ==")
        for row in valid_now.get("actions") or []:
            lines.append(f"  {row['example']}")
            if row.get("description"):
                lines.append(f"    {row['description']}")
        lines.append("")

    if valid_now_error:
        lines.append(f"valid_now: unavailable ({valid_now_error})")
        lines.append("")

    lines.append(
        "Run `bot.ps1 help --now` when the game is up for commands valid in the current state."
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    try:
        json_out, now = _parse_argv(sys.argv[1:])
    except ValueError as e:
        print(
            json.dumps(
                build_error_envelope("BAD_REQUEST", str(e), fmt=HELP_FORMAT),
                ensure_ascii=False,
            )
        )
        return 2

    catalog = _catalog_payload()
    valid_now: dict[str, Any] | None = None
    valid_now_error: str | None = None

    if now:
        try:
            raw = fetch_stable_gamestate()
            valid_now = _valid_now_payload(raw)
        except APIError as e:
            valid_now_error = f"{e.name}: {e.message}"
        except TimeoutError as e:
            valid_now_error = str(e)

    if json_out:
        print(
            json.dumps(
                build_help_envelope(
                    catalog, valid_now=valid_now, error=valid_now_error
                ),
                ensure_ascii=False,
            )
        )
        return 0

    print(
        format_help_text(valid_now=valid_now, valid_now_error=valid_now_error),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

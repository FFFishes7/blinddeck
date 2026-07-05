"""Play Helper JSON envelope builders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from layers import available_queries, filter_layer1, normalize_play_state
from start_options import build_decks, build_stakes

PLAY_FORMAT = "balatrobot-play-v1"
QUERY_FORMAT = "balatrobot-query-v1"
KNOW_FORMAT = "balatrobot-know-v1"
HELP_FORMAT = "balatrobot-help-v2"


def detect_save_path() -> str | None:
    for key in ("BALATROBOT_SAVE_PATH", "BALATROBOT_LOAD_PATH"):
        value = os.getenv(key)
        if value and Path(value).is_file():
            return value
    return None


def build_play_envelope(
    raw: dict[str, Any], actions: list[dict[str, Any]]
) -> dict[str, Any]:
    normalized = normalize_play_state(raw)
    state = normalized.get("state", "UNKNOWN")
    envelope: dict[str, Any] = {
        "ok": True,
        "format": PLAY_FORMAT,
        "gamestate": filter_layer1(normalized),
        "actions": actions,
    }
    queries = available_queries(state)
    if queries:
        envelope["queries"] = queries
    if state == "MENU":
        envelope["decks"] = build_decks()
        envelope["stakes"] = build_stakes()
    return envelope


def build_error_envelope(
    name: str, message: str, *, fmt: str = PLAY_FORMAT
) -> dict[str, Any]:
    return {
        "ok": False,
        "format": fmt,
        "error": {"name": name, "message": message},
    }


def build_query_envelope(name: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "format": QUERY_FORMAT,
        "query": name,
        "data": data,
    }


def build_know_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "format": KNOW_FORMAT, **payload}


def build_help_envelope(
    catalog: list[dict[str, Any]],
    *,
    valid_now: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "format": HELP_FORMAT,
        "catalog": catalog,
    }
    if valid_now is not None:
        payload["valid_now"] = valid_now
    if error:
        payload["valid_now_error"] = error
    return payload

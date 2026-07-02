"""Shared fast HTTP client for BalatroBot JSON-RPC API.

All play/helper scripts should import ``rpc`` from here instead of spawning
subprocesses or duplicating httpx calls. The server accepts one request at a
time, so calls are serialized with a lock.
"""

from __future__ import annotations

import os
import threading
from typing import Any

import httpx

DEFAULT_URL = os.getenv("BALATROBOT_URL", "http://127.0.0.1:12346")
DEFAULT_TIMEOUT = float(os.getenv("BALATROBOT_TIMEOUT", "120"))

_lock = threading.Lock()


class APIError(RuntimeError):
    def __init__(self, name: str, message: str, code: int = 0):
        self.name = name
        self.message = message
        self.code = code
        super().__init__(f"{name}: {message}")


class BotClient:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = DEFAULT_TIMEOUT):
        self.url = url
        self._timeout = timeout
        self._id = 0
        self._http = httpx.Client(timeout=timeout)

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with _lock:
            self._id += 1
            response = self._http.post(
                self.url,
                json={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or {},
                    "id": self._id,
                },
            )
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            err = data["error"]
            name = err.get("data", {}).get("name", "RPC_ERROR")
            raise APIError(name, err.get("message", ""), err.get("code", 0))
        return data["result"]

    def close(self) -> None:
        self._http.close()


_client: BotClient | None = None


def get_client() -> BotClient:
    global _client
    if _client is None:
        _client = BotClient()
    return _client


def rpc(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_client().call(method, params)


def current_blind(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("blind"):
        return state["blind"]
    for blind in state.get("blinds", {}).values():
        if blind.get("status") == "CURRENT":
            return blind
    raise KeyError("No current blind in gamestate")

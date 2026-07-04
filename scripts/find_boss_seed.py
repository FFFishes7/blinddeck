"""One-off: find RED/WHITE seed with Boss Tag on small blind (ante 1).

Used by non-pack skip live test. Record in tests/lua/tag_seeds.py as BOSS_SMALL.

    python scripts/find_boss_seed.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import replace

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from balatrobot.config import Config  # noqa: E402
from balatrobot.manager import BalatroInstance  # noqa: E402

BOSS_TAG = "Boss Tag"
DECK = "RED"
STAKE = "WHITE"
MAX = int(os.environ.get("TAG_SEED_SEARCH_MAX", "12000"))


def api(client: httpx.Client, method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    response = client.post("/", json=payload)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data["result"]


def small_tag_for_seed(client: httpx.Client, seed: str) -> str:
    api(client, "menu", {})
    gs = api(client, "start", {"deck": DECK, "stake": STAKE, "seed": seed})
    return gs["blinds"]["small"]["tag_name"]


async def main() -> None:
    config = replace(Config.from_env(), debug=True, fast=True)
    port = 12351
    instance = BalatroInstance(config, port=port)
    await instance.start()
    url = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=url, timeout=60.0) as client:
            for i in range(MAX):
                seed = f"S{i:05d}"
                if small_tag_for_seed(client, seed) == BOSS_TAG:
                    print(f"FOUND seed={seed!r} small={BOSS_TAG!r}")
                    return
                if i and i % 1000 == 0:
                    print(f"checked {i}")
            print("NOT FOUND")
    finally:
        await instance.stop()


if __name__ == "__main__":
    asyncio.run(main())

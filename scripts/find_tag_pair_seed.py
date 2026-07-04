"""One-off: find RED/WHITE seed with Double Tag (small) + Foil Tag (big) on ante 1.

Record the result in tests/lua/tag_seeds.py as DOUBLE_THEN_FOIL.

    python scripts/find_tag_pair_seed.py
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

SMALL_TAG = "Double Tag"
BIG_TAG = "Foil Tag"
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


def tags_for_seed(client: httpx.Client, seed: str) -> tuple[str, str]:
    api(client, "menu", {})
    gs = api(client, "start", {"deck": DECK, "stake": STAKE, "seed": seed})
    return gs["blinds"]["small"]["tag_name"], gs["blinds"]["big"]["tag_name"]


async def main() -> None:
    config = replace(Config.from_env(), debug=True, fast=True)
    port = 12347
    instance = BalatroInstance(config, port=port)
    await instance.start()
    url = f"http://127.0.0.1:{port}"
    try:
        with httpx.Client(base_url=url, timeout=60.0) as client:
            hits: list[tuple[str, str]] = []
            for i in range(MAX):
                seed = f"S{i:05d}"
                small, big = tags_for_seed(client, seed)
                if small == SMALL_TAG:
                    hits.append((seed, big))
                    if big == BIG_TAG:
                        print(f"FOUND seed={seed!r} small={small!r} big={big!r}")
                        return
                if i and i % 1000 == 0:
                    print(f"checked {i}, double_hits={len(hits)}")
            print("NOT FOUND")
            for seed, big in hits[:20]:
                print(f"  {seed!r} -> big={big!r}")
    finally:
        await instance.stop()


if __name__ == "__main__":
    asyncio.run(main())

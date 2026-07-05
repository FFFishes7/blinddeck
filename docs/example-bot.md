# Example Bot

A minimal Python example that plays Balatro using the local JSON-RPC API.

## The Bot

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
# ]
# ///

import requests

# BlindDeck API endpoint
URL = "http://127.0.0.1:12346"

def rpc(method: str, params: dict = {}) -> dict:
    """Send a JSON-RPC 2.0 request to the BlindDeck API."""
    response = requests.post(URL, json={
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    })
    data = response.json()
    # Raise if error, otherwise return result (contains game state)
    if "error" in data:
        raise Exception(data["error"]["message"])
    return data["result"]


def play_game():
    """Play a complete game of Balatro."""
    # Return to menu and start a new game
    rpc("menu")
    state = rpc("start", {"deck": "RED", "stake": "WHITE"})
    print(f"Started game with seed: {state['seed']}")

    # Main game loop
    while state["state"] != "GAME_OVER":
        match state["state"]:
            case "BLIND_SELECT":
                state = rpc("select")

            case "SELECTING_HAND":
                num_cards = min(5, len(state["hand"]["cards"]))
                cards = list(range(num_cards))
                state = rpc("play", {"cards": cards})

            case "ROUND_EVAL":
                if state.get("victory_overlay"):
                    state = rpc("endless")
                else:
                    state = rpc("cash_out")

            case "SHOP":
                state = rpc("next_round")

            case "SMODS_BOOSTER_OPENED":
                # Simplest path: forfeit remaining pack picks
                state = rpc("pack", {"skip": True})

            case _:
                # Transient states (HAND_PLAYED, DRAW_TO_HAND, …)
                state = rpc("gamestate")

    # Game ended — use run_summary.result when present (won alone can stay
    # true after an endless-mode death; see docs/api.md).
    summary = state.get("run_summary") or {}
    result = summary.get("result")
    if result:
        print(result)
    elif state.get("won"):
        print(f"Victory! Final ante: {state['ante_num']}")
    else:
        print(f"Game over at ante {state['ante_num']}, round {state['round_num']}")

    return bool(result and "Victory" in result) if result else state.get("won", False)


if __name__ == "__main__":
    play_game()
```

## Running the Bot

1. Start Balatro with the mod (from the repository root):

    **Windows (recommended):**

    ```powershell
    .\tools\play\serve.ps1 --fast
    ```

    **Cross-platform:**

    ```bash
    balatrobot serve --fast
    ```

2. In another terminal, run the bot:

    ```bash
    uv run bot.py
    ```

The bot will automatically start a new game and play until it wins or loses.

For local manual or LLM-assisted play, see [Play Helpers](../tools/play/README.md) and [PLAY.md](../PLAY.md).

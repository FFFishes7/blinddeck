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
                # Always select the current blind
                state = rpc("select")

            case "SELECTING_HAND":
                # Play the first 5 cards (simple strategy)
                num_cards = min(5, len(state["hand"]["cards"]))
                cards = list(range(num_cards))
                state = rpc("play", {"cards": cards})

            case "ROUND_EVAL":
                # Collect rewards and go to shop
                state = rpc("cash_out")

            case "SHOP":
                # Skip the shop and proceed to next round
                state = rpc("next_round")

            case _:
                # Handle any transitional states
                state = rpc("gamestate")

    # Game ended
    if state["won"]:
        print(f"Victory! Final ante: {state['ante_num']}")
    else:
        print(f"Game over at ante {state['ante_num']}, round {state['round_num']}")

    return state["won"]


if __name__ == "__main__":
    play_game()
```

## Running the Bot

1. Start Balatro with the mod:

    ```bash
    uvx balatrobot serve
    ```

2. In another terminal, run the bot:

    ```bash
    uv run bot.py
    ```

The bot will automatically start a new game and play until it wins or loses.

For local manual or LLM-assisted play, see [Play Helpers](../tools/play/README.md).

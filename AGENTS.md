# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

**Project**: **BlindDeck** — Balatro play desk (mod + API + play helpers).\
**GitHub Repository**: [`FFFishes7/blinddeck`](https://github.com/FFFishes7/blinddeck)

**Play Balatro with your agent — glance, then act.** If the user asks you to **play** (not develop), read [`PLAY.md`](./PLAY.md) first.

## Playing Balatro (read this first if asked to play)

If the user asks you to **play** Balatro (not develop this repo), read [`PLAY.md`](./PLAY.md) for the full guide. The essentials:

- The game serves JSON-RPC 2.0 on `http://127.0.0.1:12346`. Health-check first.
- **Loop:** `bot.ps1 glance` → (`bot.ps1 know preflight`) → one friendly action → read printed summary. Repeat until `GAME_OVER`, then `bot.ps1 menu` + `bot.ps1 start DECK STAKE` (e.g. `start RED WHITE`). **`estimate` is optional / not recommended** — see `PLAY.md`.
- **All indices are 0-based.** One request at a time (server is single-client).
- **Use friendly subcommands, never `exec '{...}'`** — PowerShell strips unescaped double quotes from JSON args.
- State → command:

| State                  | Command                                                                                                          |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `MENU`                 | `bot.ps1 start DECK STAKE [SEED]` (e.g. `start RED WHITE`; `glance` lists decks/stakes)                          |
| `BLIND_SELECT`         | `bot.ps1 select` · `bot.ps1 skip` (Small/Big only) · `bot.ps1 reroll_boss` (Boss + Director's Cut / Retcon, $10) |
| `SELECTING_HAND`       | `bot.ps1 play 0 1 2 3 4` · `discard 0 1` · `use 0 [1 2]` · `sort rank` · *(optional)* `estimate`                 |
| `ROUND_EVAL`           | `bot.ps1 cash_out` · after Ante 8 win with victory overlay: `bot.ps1 endless` first                              |
| `SHOP`                 | `bot.ps1 buy card 0` · `buy pack 0` · `reroll` · `sell joker 0` · `next_round`                                   |
| `SMODS_BOOSTER_OPENED` | `bot.ps1 pack 0 [1 2]` · `pack skip`                                                                             |
| `GAME_OVER`            | `bot.ps1 menu` then `start`                                                                                      |

Each `glance`/action output ends with an `actions:` line listing valid next commands. For scoring, use `query hands` + `know check rule scoring_formula`; `bot.ps1 estimate` is an incomplete optional helper (not recommended for normal play). Common pitfalls (full list in `PLAY.md`): boss blinds hide card faces (`??`), `pack` targets only for Tarot/Spectral, `buy` checks `dollars - bankrupt_at`, tags are skip rewards not defeat rewards, zombie `balatrobot serve` processes need `Stop-Process` before restarting `serve.ps1`.

## Overview

This repository is **BlindDeck** — a Balatro play desk built on [BalatroBot](https://github.com/coder/balatrobot). It consists of two main parts:

1. **Python Package** (`src/balatrobot/`): A CLI and library to manage the Balatro game process, inject the mod, and handle communication.
2. **Lua API** (`src/lua/`): The mod code running inside Balatro (Love2D) that exposes a HTTP JSON-RPC 2.0 API.

### Live scenario policy

When an estimate live scenario fails (`estimate != play`, setup error, flaky assertion):

1. **Fix the root cause** — estimate logic, runner setup, fixture, or game alignment.
2. **Do not** replace the scenario with a simpler variant to make tests pass.
3. **Do not** skip, weaken assertions, or delete planned coverage without explicit user approval.
4. **Do not** mark plan todos complete while known deviations remain undocumented.

Keep the original scenario intent (IDs, jokers, buffs, optimal/suboptimal lines). Debug with unit tests + targeted live runs (e.g. `pytest … -k S31`).

**Forbidden:** S31 Baron + Mime HOLO + STEEL+RED K fails → swap to Jolly + Mime HOLO. **Required:** fix edition timing for held/retrigger jokers; restore S31 as planned.

Applies to `tests/lua/endpoints/estimate_live_scenarios.py`, `estimate_live_recipes.py`, and estimate modeling in `tools/play/`.

### Testing

Integration tests (`tests/lua`) automatically start and stop Balatro instances on random ports.

```bash
# Run all tests (CLI and Lua suites)
make test

# Run Lua integration tests in parallel
pytest -n 6 tests/lua

# Run CLI tests
pytest tests/cli

# Run specific tests
pytest tests/lua/endpoints/test_health.py -v
pytest tests/lua/endpoints/test_health.py::TestHealthEndpoint::test_health_from_MENU -v

# Run only integration tests
pytest tests/cli -m integration

# Run non-integration tests (no Balatro instance required)
pytest tests/cli -m "not integration"

# Manual launch for dev/debugging
balatrobot --fast --debug
```

### Live test seeds

Lua tests that require a specific run setup (e.g. a blind skip tag) must use **fixed seeds** from [`tests/lua/tag_seeds.py`](tests/lua/tag_seeds.py), not random search loops at pytest time.

1. Discover: `python scripts/find_<scenario>_seed.py` (one script per scenario; pair combos use `find_tag_pair_seed.py`).
2. Record the constant in `tests/lua/tag_seeds.py`.
3. In the test, assert the seed still produces the expected blinds/tags (`seed drifted` if the game RNG changes).

See [`docs/contributing.md`](docs/contributing.md) for the finder table.

### Make Commands

Available make targets:

| Target           | Description                                                                                        |
| ---------------- | -------------------------------------------------------------------------------------------------- |
| `make help`      | Show all available targets                                                                         |
| `make lint`      | Run ruff linter (check only)                                                                       |
| `make format`    | Run ruff format `.`, **mdformat `.`**, and stylua (same markdown scope as CI `mdformat --check .`) |
| `make typecheck` | Run type checker (Python and Lua)                                                                  |
| `make quality`   | Run all code quality checks (lint + typecheck + format)                                            |
| `make test`      | Run all tests                                                                                      |
| `make all`       | Run all quality checks and tests                                                                   |
| `make fixtures`  | Generate test fixtures                                                                             |
| `make install`   | Install dependencies                                                                               |

**Important rules:**

1. **Only run make commands when explicitly asked.** Do not proactively run `make test`, `make quality`, etc.
2. **Never run bare linting/formatting/typechecking tools.** Always use make targets instead:
    - Use `make lint` instead of `ruff check`
    - Use `make format` instead of `ruff format`
    - Use `make typecheck` instead of `ty check`
    - Use `make quality` for all checks combined

## Architecture

### 1. Python Layer (`src/balatrobot/`)

Controls the game lifecycle and provides the CLI.

- **CLI** (`cli.py`): Entry point (`balatrobot`). Handles arguments like `--fast`, `--debug`, `--headless`.
- **Manager** (`manager.py`): `BalatroInstance` context manager. Starts the game process, handles logging, and waits for the API to be healthy.
- **Config** (`config.py`): Configuration management using `dataclasses` and environment variables.
- **Platform Abstraction** (`platforms/`): Cross-platform game launcher system with platform-specific implementations for macOS, Windows, Linux (Proton), and native Love2D.

### 2. Lua Layer (`src/lua/`)

Runs inside the game engine and exposes an API.

- **HTTP Server** (`src/lua/core/server.lua`)

    - Single-client HTTP/1.1 server on port 12346 (default)
    - **Protocol**: JSON-RPC 2.0 over HTTP POST to `/`
    - **Request**: `{"jsonrpc": "2.0", "method": "endpoint", "params": {...}, "id": 1}`
    - **Response**: `{"jsonrpc": "2.0", "result": {...}, "id": 1}`
    - Max body size: 64KB

- **Dispatcher** (`src/lua/core/dispatcher.lua`)

    - Routes requests based on the `method` field.
    - Validates:
        1. Protocol (JSON-RPC 2.0, valid ID)
        2. Schema (via `validator.lua`)
        3. Game State (`requires_state`)
        4. Endpoint execution

- **Endpoints** (`src/lua/endpoints/*.lua`)

    - Stateless modules defining `schema` and `execute` functions.
    - 0-based indexing in API vs 1-based in Lua.
    - OpenRPC Specification (`src/lua/utils/openrpc.json`): Machine-readable API documentation describing all endpoints.

    **Core Endpoints:**

    - `add.lua`: Add a new card (joker, consumable, voucher, playing card, or booster pack).
    - `debuff.lua`: Set or clear debuff on hand cards (debug / estimate testing).
    - `buy.lua`: Buy a card or booster pack from the shop.
    - `cash_out.lua`: Cash out and collect round rewards.
    - `endless.lua`: Dismiss victory overlay to continue in endless mode.
    - `discard.lua`: Discard cards from the hand.
    - `gamestate.lua`: Get current game state.
    - `health.lua`: Health check endpoint for connection testing.
    - `load.lua`: Load a saved run state from a file.
    - `menu.lua`: Return to the main menu from any game state.
    - `next_round.lua`: Leave the shop and advance to blind selection.
    - `pack.lua`: Select or skip a card from an opened booster pack.
    - `play.lua`: Play a card from the hand.
    - `rearrange.lua`: Rearrange cards in hand, jokers, or consumables.
    - `reroll.lua`: Reroll to update the cards in the shop area.
    - `reroll_boss.lua`: Reroll the Boss blind for $10 (Director's Cut / Retcon).
    - `save.lua`: Save the current run state to a file.
    - `screenshot.lua`: Take a screenshot of the current game state.
    - `select.lua`: Select the current blind.
    - `sell.lua`: Sell a joker or consumable from player inventory.
    - `set.lua`: Set a in-game value (money, chips, ante, etc.).
    - `skip.lua`: Skip the current blind (Small or Big only).
    - `sort.lua`: Sort hand cards using Balatro's native rank or suit sort.
    - `start.lua`: Start a new game run with specified deck and stake.
    - `use.lua`: Use a consumable card with optional target cards.

    **Test Endpoints (`src/lua/endpoints/tests/*.lua`):**

    - `echo.lua`: Test endpoint for dispatcher testing.
    - `endpoint.lua`: Test endpoint with schema for dispatcher testing.
    - `error.lua`: Test endpoint that throws runtime errors.
    - `state.lua`: Test endpoint that requires specific game states.
    - `validation.lua`: Comprehensive validation test endpoint.

## Estimate modeling (required workflow)

`bot.ps1 estimate` models **deterministic** scoring only. Before changing `tools/play/estimate.py` or `estimate_jokers.py`:

1. **Gate** — read the joker in Balatro source (`%APPDATA%\Balatro\Mods\lovely\game-dump\card.lua`). If it uses RNG or unread state → **Never model**; leave `unmodeled`.
2. **Trace** — find context (`joker_main` / per-card / `repetition`) via `state_events.lua` → `evaluate_play` and `smods/src/utils.lua` (`SMODS.calculate_main_scoring`, `trigger_effects`).
3. **Implement** — port to `tools/play/estimate_jokers.py`; register in `_modeled()`; pipeline glue stays in `estimate.py`. `indices` = full `bot.ps1 play` args (kickers included when they change held-card effects).
4. **Test** — unit: `pytest tests/cli/test_play_helpers.py -k estimate`; integration (required for new/changed jokers): `pytest tests/lua/endpoints/test_estimate_live.py` — add a recipe in `estimate_live_recipes.py` or scenario in `estimate_live_scenarios.py`. Manual fallback: `estimate` then `play` same `idx` with `BALATROBOT_ALLOW_CHEATS=1`.
5. **Document** — update [`tools/play/estimate_registry.md`](tools/play/estimate_registry.md) (checklist + Verified/Never tables + live log); update `docs/api.md` if gamestate fields changed.

Full checklist and scoring pipeline map: **`tools/play/estimate_registry.md`**. Do not use wiki guesses when source is available.

## Key Files

- **Python**:
    - `src/balatrobot/cli.py`: Main entry point.
    - `src/balatrobot/manager.py`: Game process logic.
- **Lua**:
    - `balatrobot.lua`: Mod entry point.
    - `src/lua/core/server.lua`: HTTP/TCP handling.
    - `src/lua/endpoints/`: All API commands.
- **Configuration**:
    - `pyproject.toml`: Python dependencies and tools config.
    - `balatrobot.json` / `balatrobot.lua`: SMODS mod metadata.

### Error Handling

Error codes are mapped to JSON-RPC standard and custom ranges:

- `INTERNAL_ERROR` (-32000): Runtime errors
- `BAD_REQUEST` (-32001): Invalid schema or parameters
- `INVALID_STATE` (-32002): Action not allowed in current game state
- `NOT_ALLOWED` (-32003): Action prevented by game rules

Error responses follow JSON-RPC 2.0 format:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Human readable error",
    "data": { "name": "BAD_REQUEST" }
  },
  "id": 1
}
```

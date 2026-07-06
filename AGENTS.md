# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

**Project**: **BlindDeck** — Balatro play desk (mod + API + play helpers).\
**GitHub Repository**: [`FFFishes7/blinddeck`](https://github.com/FFFishes7/blinddeck)

**Play Balatro with your agent — glance, then act.** If the user asks you to **play** (not develop), read [`PLAY.md` §1–§6](./PLAY.md#1-what-you-are-doing) top to bottom before the first move; [Appendix](./PLAY.md#appendix-on-demand) only when stuck.

## Playing Balatro (read this first if asked to play)

- The game serves JSON-RPC 2.0 on `http://127.0.0.1:12346`. Health-check first.
- **Loop:** `bot.ps1 glance` → (optional `bot.ps1 know preflight` at blind/skip — see PLAY.md §2) → one friendly action → read printed summary. Repeat until `GAME_OVER`, then `bot.ps1 menu` + `bot.ps1 start DECK STAKE SEED` (seed from summary restart hint; e.g. `start RED WHITE ABC123`). **`estimate` is optional / not recommended** — see `PLAY.md`.
- **Scoring:** read [PLAY.md §3 Scoring essentials](./PLAY.md#3-scoring-essentials); use `query hands` + §3 for hand math (not `estimate`).
- **All indices are 0-based.** One request at a time (server is single-client).
- **Use friendly subcommands, never `exec '{...}'`** — PowerShell strips unescaped double quotes from JSON args.
- **Command syntax:** `bot.ps1 help` (formatted catalog + descriptions); `bot.ps1 help --now` when the game is running; `state --json` → `actions[].example` for scripting.
- State → command:

| State                  | Command                                                                                                                                        |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `MENU`                 | `bot.ps1 start DECK STAKE [SEED]` (e.g. `start RED WHITE`; `glance` lists decks/stakes)                                                        |
| `BLIND_SELECT`         | `bot.ps1 select` · `bot.ps1 skip` (Small/Big only) · `bot.ps1 reroll_boss` (Boss + Director's Cut / Retcon, $10)                               |
| `SELECTING_HAND`       | `bot.ps1 play 0 1 2 3 4` (1-5 cards) · `discard 0 1` · `use 0 [1 2]` · `sort rank` · *(optional)* `estimate`                                   |
| `ROUND_EVAL`           | `bot.ps1 cash_out` · after Ante 8 win with victory overlay: `bot.ps1 endless` first                                                            |
| `SHOP`                 | `bot.ps1 buy card 0` · `buy pack 0` · `reroll` · `sell joker 0` · `rearrange jokers 1 0` · `next_round`                                        |
| `SMODS_BOOSTER_OPENED` | `bot.ps1 pack 0 [1 2]` while glance shows **`choices remaining: N`** · `pack skip` only to forfeit picks · `rearrange jokers …` when 2+ jokers |
| `GAME_OVER`            | `bot.ps1 menu` then `start DECK STAKE SEED` (from summary restart hint)                                                                        |

Each `glance`/action output ends with an `actions:` line listing valid next commands. **Pitfalls and API gotchas:** [PLAY.md §6](./PLAY.md#6-pitfalls). State→command table and glance abbreviations: [PLAY.md §4–§5](./PLAY.md#4-state--command).

### Windows play helpers

- Launch with `.\tools\play\serve.ps1 --fast` or `--fast --debug`; there is no `bot.ps1 serve`. Leave it running and health-check `http://127.0.0.1:12346`.
- `tools/play/serve.ps1` is machine-local and gitignored because it contains the correct local Steam/Balatro path.
- Use the deliberate loop: `glance` → optional `know preflight` → think → one friendly action → read the new summary.
- Do **not** write or run automated strategy scripts, batch play loops, or bots that pick actions without per-turn reasoning.
- Do **not** use `estimate` as the default play loop step; it is optional and incomplete. Prefer `query hands` plus the scoring rules in `PLAY.md`.
- If `estimate` is used: `idx` / `indices` means the full `bot.ps1 play` list, including kickers when they matter; `scoring=` / `scoring_indices` means only poker-scoring cards.
- Never use bare JSON through `bot.ps1 exec` in PowerShell; use friendly subcommands. If raw `exec` is unavoidable, escape quotes as `\"`.

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
3. On Windows, if `make` is unavailable, run the equivalent commands from `.venv` using the same flags and scope as the Makefile. For markdown checks, use repo-wide `mdformat --check .`, matching CI scope.

### Change delivery checklist

When a **feature, fix, or refactor** changes user-visible or agent-visible behavior, complete this before marking the task done:

1. **Unit tests** — CLI (`tests/cli/`) and/or pure logic; no Balatro required.
2. **Live tests** — required when touching gamestate, glance output, Lua endpoints, tag/pack/cashout timing, or OpenRPC fields. Run targeted `pytest tests/lua/...`; skip only with an explicit reason in the completion summary.
3. **Docs** — update affected docs in the same working tree change.
4. **Manual smoke** — when glance, CLI, polling, or play-helper UX changed, use `serve.ps1` + `bot.ps1 glance` on the affected state if practical.

Live tests are expected for changes under `src/lua/**`, `tools/play/view.py`, `tools/play/layers.py`, `tools/play/actions.py`, tag skip/pack sequences, cashout preview, and victory overlay handling.

When summarizing a behavior change, include what was run or why it was skipped:

- **Unit:** `pytest ...` (pass)
- **Live:** `pytest tests/lua/...` (pass) or reason skipped
- **Docs:** files updated, or why none
- **Smoke:** manual step if applicable

Do not mark todos complete while a required live scenario fails or docs are stale.

### Git boundaries

- **Do not** `git commit`, `git push`, amend, or force-push unless the user explicitly asks for that git action.
- Task done, tests passing, docs updated, or a user saying “可以” for a feature is not permission to commit unless they clearly mean git.
- If unclear, ask whether they want a commit or push.
- Never commit local or machine-specific paths:
    - `.cursor/` — local Cursor rules
    - `CLAUDE.md` — local Claude copy; repo uses `AGENTS.md`
    - `tools/play/serve.ps1` — machine-specific Balatro path
    - `saves/`, `*.jkr` outside fixtures — runtime saves
- `AGENTS.md` is the tracked canonical agent guidance for this repo.

When the user explicitly asks to commit or push, first run pre-push checks: `make quality`, relevant tests, docs review, `git status` / `git diff`, and confirm no secrets or ignored/local files are staged. Commit messages should follow conventional commits (`feat:`, `fix:`, `docs:`, ...).

### Keep docs in sync

After code changes, check whether related documentation is still accurate and update it unless the change is purely internal or the user explicitly requested code-only work.

| Area changed                    | Likely docs                                                                |
| ------------------------------- | -------------------------------------------------------------------------- |
| Play helper / bot UX            | `PLAY.md`, `tools/play/README.md`                                          |
| Estimate / joker modeling       | `tools/play/estimate_registry.md`, `AGENTS.md` § Estimate modeling         |
| Agent entry points              | `AGENTS.md`                                                                |
| Lua API / endpoints             | `src/lua/utils/openrpc.json`, endpoint docstrings, `AGENTS.md`             |
| Architecture / setup            | `docs/OVERVIEW.md`, `README.md`                                            |
| Knowledge / rules               | `knowledge/balatro/README.md`, verified JSON under `knowledge/`            |
| Live Lua tests / scenario setup | `tests/lua/tag_seeds.py`, `docs/contributing.md`, `scripts/find_*_seed.py` |

If intentionally skipping a docs update, mention why in the summary.

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

### Estimate hard rules and invariants

- Deterministic only: no RNG, probability, or expected-value guesses. RNG jokers stay `unmodeled` and belong in the registry's Never table.
- Prefer structured API fields (`value.stats`, `gamestate.round`, `gamestate.run`); parse `value.effect` only as a fallback.
- Dusk: API `hands_left == 1` (= game internal `0` after `ease_hands_played(-1)`); +1 retrigger per played scoring card.
- Blue Joker: +2 chips × `state.cards.count` in global joker phase.
- Blackboard: all **unplayed** cards (`G.hand.cards`) must be Spades or Clubs.
- Mystic Summit: only active when `discards_left == 0`.
- Dedupe estimate candidates by `(hand_type, sorted scoring_indices)`; keep the highest score and prefer fewer cards on tie.

Unit tests prove the Python model matches itself; they do not prove Balatro agrees. For modeled joker changes, add or update live coverage using real gamestate: `load_fixture` → add joker(s) → `estimate(state)` → `play` the same `indices` → assert chip delta equals the estimate score. Run:

```powershell
python -m pytest tests/cli/test_play_helpers.py -k estimate -v
python -m pytest tests/lua/endpoints/test_estimate_live.py -v
```

Manual fallback when a fixture cannot hit the joker: with `$env:BALATROBOT_ALLOW_CHEATS=1`, run `estimate`, then `play` the same indices, compare against actual score, and log it in `tools/play/estimate_registry.md`.

## Key Files

- **Python**:
    - `src/balatrobot/cli.py`: Main entry point.
    - `src/balatrobot/manager.py`: Game process logic.
- **Play helpers** (`tools/play/`):
    - `know.py` / `know_lib.py`: Knowledge lookups and phase-aware preflight.
    - `view.py`: Compact `glance` summary.
    - `act.py`: Friendly action dispatcher.
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

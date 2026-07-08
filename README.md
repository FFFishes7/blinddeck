<div align="center">
  <h1>BlindDeck</h1>
  <div><img src="./docs/assets/blinddeck.svg" alt="BlindDeck" width="170" height="170"></div>
  <p><em>Play Balatro with your agent — glance, then act.</em></p>
</div>

---

**BlindDeck** is a Balatro play desk for humans and AI agents: a Steamodded mod, JSON-RPC HTTP API, and command-line helpers so you (or your agent in Cursor, Codex, Claude, etc.) can read run state with `glance` and take one deliberate action per turn.

BlindDeck extends the [BalatroBot](https://github.com/coder/balatrobot) mod (game-state API and launcher) with play helpers, a verified knowledge library, and additional API surface (e.g. `sort`, hidden-card masking, `reroll_boss`).

## Documentation

| Document                                         | Audience              | Contents                                    |
| ------------------------------------------------ | --------------------- | ------------------------------------------- |
| [**PLAY.md**](PLAY.md)                           | Players and AI agents | Play sheet (§1–§6): loop, scoring, pitfalls |
| [**tools/play/README.md**](tools/play/README.md) | Play-helper users     | `bot.ps1` commands, glance output, `--json` |
| [**docs/api.md**](docs/api.md)                   | Integrators           | JSON-RPC methods, schemas, errors           |
| [**docs/OVERVIEW.md**](docs/OVERVIEW.md)         | Developers            | Architecture map and doc index              |
| [**docs/cli.md**](docs/cli.md)                   | Operators             | `balatrobot serve` / `api`, env vars, paths |

## Features

- **`bot.ps1 glance`** — compact multi-line state summary, **`choices remaining: N`** on open packs, and an `actions:` line for valid next commands
- **`bot.ps1 know`** — wiki-backed lookups (joker, boss, tag, stake, deck, planet, tarot, voucher, spectral, rules); **`know preflight`** prints a phase-aware verified-facts table at blind/skip
- **`bot.ps1 query`** — detail queries (hand levels, deck, blinds, vouchers, seed) as tables or JSON
- **Friendly actions** — `play`, `select`, `buy`, `pack`, … without PowerShell JSON quoting
- **JSON-RPC API** — full game control for scripts; OpenRPC spec in `src/lua/utils/openrpc.json`

## Quick start (Windows)

Two steps: install the mod once, then launch the game and use the helpers.

### 1. One-time setup

**In Balatro**

1. Install [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) — copy `version.dll` into your Balatro game folder (same directory as `Balatro.exe`).

2. Install [Steamodded](https://github.com/Steamodded/smods/wiki) — put `smods` under `%AppData%\Balatro\Mods\`.

3. Put this repository under `%AppData%\Balatro\Mods\balatrobot\`. For development, a symlink works well:

    ```powershell
    New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Balatro\Mods\balatrobot" -Target (Get-Location)
    ```

    (Run PowerShell as Administrator if the symlink command fails.)

    The mod directory name remains `balatrobot` (SMODS mod id); the in-game mod title is **BlindDeck**.

**In this repository**

1. Install dependencies — creates `.venv` with the `balatrobot` CLI and play-helper packages:

    ```powershell
    make install
    ```

    If `make` is unavailable, run `uv sync --group dev --group test` instead.

2. Copy `tools/play/serve.example.ps1` to `tools/play/serve.ps1` and set `$BalatroDir` to your Steam Balatro folder if it is not the default:

    ```powershell
    Copy-Item tools\play\serve.example.ps1 tools\play\serve.ps1
    ```

    `serve.ps1` stays untracked (machine-specific). You can also set the user env var `BALATROBOT_GAME_DIR` instead of editing the file.

For platform-specific paths (macOS / Linux Proton / native Love) and CLI flags, see the [CLI Reference](docs/cli.md).

### 2. Launch Balatro (GUI + API)

From the repository root:

```powershell
.\tools\play\serve.ps1
```

This sets session env vars for Balatro paths, runs `balatrobot serve` to start the game with the mod, and exposes JSON-RPC on `http://127.0.0.1:12346` (default).

Useful flags: `.\tools\play\serve.ps1 --fast --debug`

Leave this terminal open while you play.

### 3. Play

In a **second terminal**, with the game running:

```powershell
.\tools\play\bot.ps1 glance              # compact state summary (use every turn)
.\tools\play\bot.ps1 query hands         # hand-type chips/mult for scoring
.\tools\play\bot.ps1 select              # friendly actions (no JSON quoting)
.\tools\play\bot.ps1 play 0 1 2 3 4
.\tools\play\bot.ps1 save saves\myrun.jkr
.\tools\play\bot.ps1 help
```

Relative `save` paths are resolved by Balatro/LÖVE on Windows, so `save run.jkr` writes under `C:\Users\<username>\AppData\Roaming\Balatro\`. Use an absolute path if you want the `.jkr` file inside this repo.

`bot.ps1` calls the API via `.venv\Scripts\python.exe`. Prefer **friendly subcommands** (`glance`, `play`, `select`, `buy`, …). `estimate` is optional and not recommended for normal play — see [PLAY.md](PLAY.md). Use `state` / `exec` for scripting.

**AI agents:** read [PLAY.md §1–§6](PLAY.md#1-what-you-are-doing) before the first move; [tools/play/README.md](tools/play/README.md) for glance field details.

If connection fails, confirm `serve.ps1` is still running and the game finished loading.

## Acknowledgments

BlindDeck is a fork of [BalatroBot](https://github.com/coder/balatrobot). The mod, JSON-RPC API, and Python launcher were created by the BalatroBot authors; this repo adds play helpers, knowledge lookups, and extensions.

Thanks to:

- [coder/balatrobot](https://github.com/coder/balatrobot) — [@S1M0N38](https://github.com/S1M0N38), [@stirby](https://github.com/stirby), and contributors
- [besteon/balatrobot](https://github.com/besteon/balatrobot) — [@phughesion](https://github.com/phughesion), [@besteon](https://github.com/besteon), [@giewev](https://github.com/giewev)

BlindDeck is maintained by [@FFFishes7](https://github.com/FFFishes7).

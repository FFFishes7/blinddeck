# BalatroBot

![balatrobot](./docs/assets/balatrobot.svg)

*Personal Balatro play setup with API and helpers*

---

This repository is my personal setup for playing Balatro locally. It builds on [BalatroBot](https://github.com/coder/balatrobot)—a mod that exposes game state and controls through a JSON-RPC HTTP API—and adds a few things I wanted for everyday play: helper scripts, a knowledge library, and some small API tweaks.

## About This Fork

The core of this repo—the Lua mod, Python CLI, API, and tests—comes from the BalatroBot projects linked below. I forked [`coder/balatrobot`](https://github.com/coder/balatrobot) (MIT) for my own games and kept the original history and credit in place.

On top of that foundation, my changes are mostly personal:

- `tools/play/` — wrappers, compact state view, and RPC helpers for manual / LLM-assisted play
- `knowledge/balatro/` — source-backed fact tables for `know.py`
- a handful of API and gamestate improvements I hit while playing (e.g. `sort`, hidden-card masking)
- docs and CI trimmed to match how I actually use the repo

If you are looking for the main BalatroBot project, releases, or the wider community, [`coder/balatrobot`](https://github.com/coder/balatrobot) is the place to start. This copy is just my working tree.

## Local Play

This is the workflow I use on Windows. Two parts: get the mod into Balatro once, then launch the game and talk to it with the helper scripts.

### 1. One-time setup

**In Balatro**

1. Install [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector) — copy `version.dll` into your Balatro game folder (same directory as `Balatro.exe`).

2. Install [Steamodded](https://github.com/Steamodded/smods/wiki) — put `smods` under `%AppData%\Balatro\Mods\`.

3. Put this repo under `%AppData%\Balatro\Mods\balatrobot\`. For development, a symlink works well:

    ```powershell
    New-Item -ItemType SymbolicLink -Path "$env:APPDATA\Balatro\Mods\balatrobot" -Target (Get-Location)
    ```

    (Run PowerShell as Administrator if the symlink command fails.)

**In this repo**

1. Install dependencies — creates `.venv` with the `balatrobot` CLI and play-helper Python packages:

    ```powershell
    make install
    ```

    If `make` is unavailable, run `uv sync --group dev --group test` instead.

2. Copy `tools/play/serve.example.ps1` to `tools/play/serve.ps1` and set `$BalatroDir` to your Steam Balatro folder if it is not the default:

    ```powershell
    Copy-Item tools\play\serve.example.ps1 tools\play\serve.ps1
    ```

    `serve.ps1` stays untracked (machine-specific). You can also set the user env var `BALATROBOT_GAME_DIR` instead of editing the file.

More detail: [Installation](docs/installation.md).

### 2. Launch Balatro (GUI + API)

From the repo root:

```powershell
.\tools\play\serve.ps1
```

What this does:

- Sets `BALATROBOT_BALATRO_PATH`, `BALATROBOT_LOVE_PATH`, and `BALATROBOT_LOVELY_PATH` for the current terminal session from your Balatro install directory.
- Runs `.venv\Scripts\balatrobot.exe serve`, which starts `Balatro.exe` with the mod loaded.
- Starts the JSON-RPC HTTP server on `http://127.0.0.1:12346` (default).

Useful flags: `.\tools\play\serve.ps1 --fast --debug`

Leave this terminal open while you play. You do not need to set those env vars in Windows system settings — `serve.ps1` handles them each time.

### 3. Use the play helpers

In a **second terminal**, with the game still running:

```powershell
.\tools\play\bot.ps1 state
.\tools\play\bot.ps1 know preflight
.\tools\play\bot.ps1 play 0 1 2 3 4
.\tools\play\bot.ps1 pack skip
.\tools\play\bot.ps1 sort rank
```

`bot.ps1` calls the running API through `.venv\Scripts\python.exe`. If you see connection errors, check that `serve.ps1` is still running and the game finished loading.

## Acknowledgments

Thanks to everyone who built BalatroBot before this fork:

- [coder/balatrobot](https://github.com/coder/balatrobot) — [@S1M0N38](https://github.com/S1M0N38), [@stirby](https://github.com/stirby), and contributors
- [besteon/balatrobot](https://github.com/besteon/balatrobot) — [@phughesion](https://github.com/phughesion), [@besteon](https://github.com/besteon), [@giewev](https://github.com/giewev)

Their work on the mod, API, and botting framework is what makes this repo possible.

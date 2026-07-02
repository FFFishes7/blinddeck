<div align="center">
  <h1>BalatroBot</h1>
  <div><img src="./docs/assets/balatrobot.svg" alt="balatrobot" width="170" height="170"></div>
  <p><em>Personal Balatro play setup with API and helpers</em></p>
</div>

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

```powershell
.\tools\play\bot.ps1 state
.\tools\play\bot.ps1 know preflight
```

To launch a local GUI session, copy `tools/play/serve.example.ps1` to `tools/play/serve.ps1`, adjust the Balatro install path, then run it from the repository root or via the script path.

## Acknowledgments

Thanks to everyone who built BalatroBot before this fork:

- [coder/balatrobot](https://github.com/coder/balatrobot) — [@S1M0N38](https://github.com/S1M0N38), [@stirby](https://github.com/stirby), and contributors
- [besteon/balatrobot](https://github.com/besteon/balatrobot) — [@phughesion](https://github.com/phughesion), [@besteon](https://github.com/besteon), [@giewev](https://github.com/giewev)

Their work on the mod, API, and botting framework is what makes this repo possible.

<div align="center">
  <h1>BalatroBot</h1>
  <div><img src="./docs/assets/balatrobot.svg" alt="balatrobot" width="170" height="170"></div>
  <p><em>Personal Balatro play setup with API and helpers</em></p>
</div>

---

This repository is my personal setup for playing Balatro locally. It uses BalatroBot, a mod that serves a JSON-RPC 2.0 HTTP API to expose game state and controls for external programs. On top of that, this fork adds play helpers and a source-backed knowledge library for manual and LLM-assisted play.

## Fork Notice

This repository is a personal fork of [`coder/balatrobot`](https://github.com/coder/balatrobot), which is distributed under the MIT License. The original project history, license, and attribution are preserved. Changes in this fork focus on local play helpers, API improvements discovered during manual play, and a source-backed Balatro knowledge library for safer decision support.

## Local Play Helpers and Knowledge Library

- `tools/play/`: command wrappers, compact state display, and JSON-RPC helper scripts.
- `knowledge/balatro/`: source-backed Balatro fact tables used by `tools/play/know.py`.

Example:

```powershell
.\tools\play\bot.ps1 state
.\tools\play\bot.ps1 know preflight
```

To launch a local GUI session, copy `tools/play/serve.example.ps1` to `tools/play/serve.ps1`, adjust the Balatro install path, then run it from the repository root or via the script path.

## 🙏 Acknowledgments

This project is a fork of the original [balatrobot](https://github.com/besteon/balatrobot) repository. We would like to acknowledge and thank the original contributors who laid the foundation for this framework:

- [@phughesion](https://github.com/phughesion)
- [@besteon](https://github.com/besteon)
- [@giewev](https://github.com/giewev)

The original repository provided the initial API and botting framework that this project has evolved from. We appreciate their work in creating the foundation for Balatro bot development.

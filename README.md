<div align="center">
  <h1>BalatroBot</h1>
  <p align="center">
    <a href="https://github.com/coder/balatrobot/releases">
      <img alt="GitHub release" src="https://img.shields.io/github/v/release/coder/balatrobot?include_prereleases&sort=semver&style=for-the-badge&logo=github"/>
    </a>
    <a href="https://discord.gg/TPn6FYgGPv">
      <img alt="Discord" src="https://img.shields.io/badge/discord-server?style=for-the-badge&logo=discord&logoColor=%23FFFFFF&color=%235865F2"/>
    </a>
  </p>
  <div><img src="./docs/assets/balatrobot.svg" alt="balatrobot" width="170" height="170"></div>
  <p><em>API for developing Balatro bots</em></p>
</div>

---

BalatroBot is a mod for Balatro that serves a JSON-RPC 2.0 HTTP API, exposing game state and controls for external program interaction. The API provides endpoints for complete game control, including card selection, shop transactions, blind selection, and state management. External clients connect via HTTP POST to execute game actions programmatically.

## Fork Notice

This repository is a personal fork of [`coder/balatrobot`](https://github.com/coder/balatrobot), which is distributed under the MIT License. The original project history, license, and attribution are preserved. Changes in this fork focus on local play helpers, API improvements discovered during manual play, and a source-backed Balatro knowledge library for safer decision support.

## Local Play Helpers and Knowledge Library

This fork includes an optional helper layer for manual/LLM-assisted Balatro play:

- `tools/play/`: command wrappers, compact state display, and JSON-RPC helper scripts.
- `knowledge/balatro/`: verified Balatro lookup tables and strategy notes used by `tools/play/know.py`.

Example:

```powershell
.\tools\play\bot.ps1 state
.\tools\play\bot.ps1 know preflight
```

To launch a local GUI session, copy `tools/play/serve.example.ps1` to `tools/play/serve.ps1`, adjust the Balatro install path, then run it from the repository root or via the script path.

## 📚 Documentation

https://coder.github.io/balatrobot/

## 🚀 Related Projects

- [**BalatroBot**](https://github.com/coder/balatrobot): API for developing Balatro bots
- [**BalatroLLM**](https://github.com/coder/balatrollm): Play Balatro with LLMs
- [**BalatroBench**](https://github.com/coder/balatrobench): Benchmark LLMs playing Balatro

## 🙏 Acknowledgments

This project is a fork of the original [balatrobot](https://github.com/besteon/balatrobot) repository. We would like to acknowledge and thank the original contributors who laid the foundation for this framework:

- [@phughesion](https://github.com/phughesion)
- [@besteon](https://github.com/besteon)
- [@giewev](https://github.com/giewev)

The original repository provided the initial API and botting framework that this project has evolved from. We appreciate their work in creating the foundation for Balatro bot development.

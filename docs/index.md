<style>
  .project-logos img {
    transition: transform 0.3s ease;
  }
  .project-logos img:hover {
    transform: scale(1.1);
  }
</style>

<div class="project-logos" style="display: flex; justify-content: center; align-items: flex-end; gap: 2rem; flex-wrap: wrap;">
  <figure style="text-align: center; margin: 0;">
    <a href="https://github.com/FFFishes7/balatrobot">
      <img src="assets/balatrobot.svg" alt="BalatroBot" width="120">
    </a>
    <figcaption>
      <a href="https://github.com/FFFishes7/balatrobot"><span style="text-decoration: underline; text-underline-offset: 8px;">BalatroBot</span></a><br>
      <small>Personal Balatro play setup with API and helpers</small>
    </figcaption>
  </figure>
</div>

---

This repository is a personal Balatro play setup built on BalatroBot. The mod serves a JSON-RPC 2.0 HTTP API for game state and controls, and this fork adds local play helpers plus a source-backed knowledge library for manual and LLM-assisted play.

<div class="grid cards" markdown>

- :material-download:{ .lg .middle } __Installation__

    ---

    Setup guide covering prerequisites and BalatroBot installation.

    [:octicons-arrow-right-24: Installation](installation.md)

- :material-robot:{ .lg .middle } __Example Bot__

    ---

    A minimal Python bot example to get started with BalatroBot.

    [:octicons-arrow-right-24: Example Bot](example-bot.md)

- :material-console:{ .lg .middle } __CLI Reference__

    ---

    Command-line interface for launching Balatro with BalatroBot.

    [:octicons-arrow-right-24: CLI Reference](cli.md)

- :material-gamepad-variant:{ .lg .middle } __Play Helpers__

    ---

    PowerShell wrappers, compact state display, and knowledge lookups for local play.

    [:octicons-arrow-right-24: Play Helpers](../tools/play/README.md)

- :material-file-document:{ .lg .middle } __BalatroBot API__

    ---

    Message formats, game states, methods, schema, enums and errors

    [:octicons-arrow-right-24: API Reference](api.md)

- :octicons-people-24:{ .lg .middle } __Contributing__

    ---

    Setup guide for developers, test suite, and contributing guidelines.

    [:octicons-arrow-right-24: Contributing](contributing.md)

</div>

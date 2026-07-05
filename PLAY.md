# Playing Balatro with BlindDeck — Quick Guide for AI Agents

You are the player. **Play Balatro with your human:** read state, reason each turn, and act through the API — one command at a time. The game runs on `127.0.0.1:12346` (JSON-RPC 2.0).

**North star:** PLAY.md is the **operation contract** — loop, `glance`, pitfalls. Balatro facts: **live summary + `know` / `query`**.

**Each session:** read **[Quick start](#quick-start-play-sheet)** below, then **`glance` → one action → read summary**. Everything after [Reference (on demand)](#reference-on-demand) is for troubleshooting and edge cases — **do not read it before your first move**.

| If you are…           | Start here                                                   |
| --------------------- | ------------------------------------------------------------ |
| **Playing a run**     | [Quick start](#quick-start-play-sheet)                       |
| **Scripting the API** | [docs/api.md](docs/api.md), `bot.ps1 state --json`           |
| **Changing the mod**  | [AGENTS.md](AGENTS.md), [docs/OVERVIEW.md](docs/OVERVIEW.md) |

Install / launch: [README.md](README.md). **Glance field details:** [tools/play/README.md](tools/play/README.md#what-glance-shows).

---

## Quick start (play sheet)

**Loop** — one request at a time; indices **0-based**; never `bot.ps1 exec '{"…"}'` (PowerShell strips quotes — use friendly subcommands).

```
repeat:
  bot.ps1 glance              → read summary + actions:
  (optional) know preflight   → boss / unfamiliar joker / skip tag
  bot.ps1 <one action>        → read new summary (includes next actions:)
until GAME_OVER → menu → start DECK STAKE SEED   # SEED from summary restart hint
```

**`estimate` is optional and not recommended** for normal play.

| State                  | Command                                                                                                                 |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `MENU`                 | `start DECK STAKE [SEED]`                                                                                               |
| `BLIND_SELECT`         | `select` · `skip` (Small/Big) · `reroll_boss` (Boss, $10)                                                               |
| `SELECTING_HAND`       | `play …` · `discard …` · `use …` · `sort rank` — repeat until **`beaten`**, then `glance`                               |
| `ROUND_EVAL`           | read **`pending:` `total +$N`**; if **`victory_overlay`**: **`endless`** or **`menu`** (not `cash_out` until dismissed) |
| `SHOP`                 | `buy card\|pack …` · `reroll` · `sell …` · `next_round`                                                                 |
| `SMODS_BOOSTER_OPENED` | `pack IDX [hand indices…]` while **`choices remaining: N` > 0**; targets = **`hand:` `[N]`**, not ranks                 |
| `GAME_OVER`            | `menu` then `start DECK STAKE SEED` (seed shown in summary restart hint)                                              |

**Pitfalls (top hits)** — extras in [§4 Pitfalls](#4-pitfalls):

- Read **`actions:`** when unsure what to do next.
- Boss hides card faces (`??`). **`buy` / shop** use `money - bankrupt_at` (`[ok]` / `[need $N]` on rows).
- **`pack skip`** is not “next blind”; **`pack` targets** are **hand `[N]` indices** from the `hand:` line (not rank values); Ankh/Hex/Ectoplasm = random joker.
- **Tags on blinds** = skip rewards only (not defeat rewards). **`held tags (pending):`** = already earned, not yet triggered.
- **`ROUND_EVAL`:** use **`pending:` `total +$N`** before `cash_out`.
- Transient states (`HAND_PLAYED`, …): **`glance`** again until stable.

**Card modifiers in `glance`** — `hand:` lists **`[N] rank+suit[tags]`**; **`[N]`** is the 0-based index for `play`, `discard`, `use`, and pack targets (e.g. `[0] 4♦[e:Mult,s:Red]`):

| Prefix | Meaning                                                                    |
| ------ | -------------------------------------------------------------------------- |
| `e:`   | Enhancement — `Mult` `Bonus` `Glass` `Stone` `Wild` `Lucky` `Gold` `Steel` |
| `d:`   | Edition — `Foil` `Holo` `Poly` `Neg`                                       |
| `s:`   | Seal — `Red` `Blue` `Gold` `Purple`                                        |

`e:Wild` = all **suits**, rank unchanged (not all ranks). Debuffed cards: `(7♣)`. Joker stickers `(rental …)` / `(perishable …)` are on joker lines, not hand cards. Enhancement **scoring** → `know check rule enhancement_scoring`.

**When to use `know` / `query`:**

- **Score a hand:** `query hands` + `know check rule scoring_formula` (kickers, wild, editions → `know list rule`).
- **Boss blind:** `know preflight` or `know check boss "Name"` before `select`.
- **Unfamiliar joker in shop or hand:** `know check joker "Name"`.
- **Skip / held tag:** read `tag_effect` on the blind or `know check tag "Name"`.
- **Scripting / machine-readable state:** `state --json` or `query … --json` — see [tools/play/README.md](tools/play/README.md).

**When to open Reference:** connection errors → [§0](#0-prerequisites); summary line unclear → [tools/play/README.md](tools/play/README.md#what-glance-shows); Double Tag + pack skip → [Tag edge cases](#tag-edge-cases); command args → [§2](#2-command-cheatsheet).

---

## Reference (on demand)

Sections below are **reference only** — open the one you need; do not read end-to-end each turn.

| Section                                        | Open when…                                         |
| ---------------------------------------------- | -------------------------------------------------- |
| [§0 Prerequisites](#0-prerequisites)           | Health check fails, port/zombie serve              |
| [§1 Reading state](#1-reading-state)           | `query` / `know` / `--json` modes                  |
| [§2 Command cheatsheet](#2-command-cheatsheet) | Arg syntax, sort modes, debug cheats               |
| [Tag edge cases](#tag-edge-cases)              | Double Tag + consecutive packs, held vs blind tags |
| [§3 Trace](#3-minimal-trace)                   | Example command sequence, `exec` quoting           |
| [§4 Pitfalls](#4-pitfalls)                     | Errors, GAME_OVER `won`, `reroll_boss` detail      |
| [§5 Decision assist](#5-decision-assist)       | Scoring, jokers, tags → `know`                     |
| [§6 Further commands](#6-further-commands)     | Full `query` / `know` / `state` table              |

---

## 0. Prerequisites

- A Balatro instance with this mod loaded is already running and serving HTTP on `127.0.0.1:12346`.
- If unsure, health-check first:

```powershell
.\.venv\Scripts\python.exe -c "import httpx;print(httpx.post('http://127.0.0.1:12346/',json={'jsonrpc':'2.0','method':'health','params':{},'id':1},timeout=3).text)"
```

- All indices in this API are **0-based** (first card is `0`).
- The server handles **one request at a time**. Never send two commands in parallel.
- Every state-changing action returns the new state (compact summary by default, or JSON with `--json`).

### If the health check fails

1. **Wait first.** Balatro takes ~30–60s to load after `serve.ps1` launches. Retry health a few times before assuming it's dead.

2. **Check for zombie serve processes.** Leftover `balatrobot serve` processes (e.g. from `pytest -n 6`) can linger with no game child and no listening port:

    ```powershell
    Get-Process balatrobot -ErrorAction SilentlyContinue        # list
    Get-Process balatrobot -ErrorAction SilentlyContinue | Stop-Process -Force
    ```

3. **Restart the server:**

    ```powershell
    .\tools\play\serve.ps1 --fast --debug
    ```

    Leave it running in its own terminal; poll health until `status: ok`.

4. **Port busy?** Use `.\tools\play\serve.ps1 --port 12347` and pass `--port 12347` (or `$env:BALATROBOT_URL`) to the play helpers.

Do not try to "fix" the running game state — only restart the server process.

## 1. Reading state

| Kind                | Commands                                                                         | When                        |
| ------------------- | -------------------------------------------------------------------------------- | --------------------------- |
| **Compact summary** | `glance`, any action (default)                                                   | Every turn                  |
| **Detail queries**  | `query hands`, `query deck`, `query blinds`, `query used_vouchers`, `query seed` | Scoring, deck, blind detail |
| **Knowledge**       | `know preflight`, `know check …`                                                 | Boss, jokers, tags, rules   |
| **Full JSON**       | `state`, any action with `--json`                                                | Scripting                   |

Every summary ends with **`actions:`** — valid command names for the current state. Per-state line meanings (BLIND_SELECT, SHOP, pack, ROUND_EVAL, …): **[tools/play/README.md § What glance shows](tools/play/README.md#what-glance-shows)**. Modifier abbreviations: [Quick start](#quick-start-play-sheet).

JSON `actions[]` entries include `example` payloads — see [tools/play/README.md](tools/play/README.md).

## 2. Command cheatsheet

- `start DECK STAKE [SEED]` — deck/stake lists appear in `glance` at MENU.
- `play` / `discard` — card indices, max 5 for `play`.
- `buy card|voucher|pack IDX` — 0-based shop index.
- `pack IDX [TARGETS...]` — hand targets for Tarot/Spectral only; not Ankh/Hex/Ectoplasm.
- `use CONSUMABLE [CARDS...]` — target hand cards when required.
- `sort MODE` — `rank` / `rank-desc` / `suit` / … (aliases `r`, `s`, `rd`, …).
- `sell joker|consumable IDX` · `rearrange hand|jokers|consumables ORDER`.

**Debug (not for normal play;** `$env:BALATROBOT_ALLOW_CHEATS=1` **):** `add joker …` · `set hands|discards|chips …` · `debuff`. See [tools/play/README.md](tools/play/README.md#debug-add--set-estimate-testing-only).

### Tag edge cases

- **`blinds.{small,big}.tag_name`** = skip reward if you **`skip`** that blind (not if you defeat it). Boss has no tag.
- **`held tags (pending):`** = already earned, not yet triggered. Upcoming skip rewards stay on the blind line.
- **Pack on skip:** some tags open a booster immediately → `SMODS_BOOSTER_OPENED` and `actions: pack`. Tag details → `know check tag "…"`.
- **Double Tag + pack tag:** can open **two packs back-to-back** — after each `pack`, read summary again; check **`choices remaining: N`**; see [tools/play/README.md](tools/play/README.md#what-glance-shows) pack example.

## 3. Minimal trace

```powershell
.\tools\play\bot.ps1 glance
.\tools\play\bot.ps1 start RED WHITE
.\tools\play\bot.ps1 select
.\tools\play\bot.ps1 play 0 1 2 3 4
.\tools\play\bot.ps1 cash_out
.\tools\play\bot.ps1 buy card 0
.\tools\play\bot.ps1 next_round
# ... until GAME_OVER → menu → start DECK STAKE SEED
```

Each action prints the new summary + `actions:` — you rarely need a separate `glance` between actions.

> **Do not use `bot.ps1 exec '{"command":...}'`.** PowerShell strips unescaped `"`. Use friendly subcommands, or escape as `\"`. Raw JSON-RPC fallback: [tools/play/README.md](tools/play/README.md#json--advanced) or [AGENTS.md](AGENTS.md).

## 4. Pitfalls

Extra items not repeated in Quick start:

- **`pack` target count** must match the card's requirement or you get `BAD_REQUEST`.
- **`rearrange jokers`** is scoring order only — not consumable/pack targeting.
- **Joker/consumable slots full** → `sell` first; shop rows may show `[slots full]`.
- **`skip` only on Small/Big** — collects tag; pack tags should show `pack` actions after skip. Charm skip with no pack after mod update → restart game (stale Lua).
- **`reroll_boss`:** Boss `BLIND_SELECT` only; $10; Director's Cut (once/ante) or Retcon; `money - bankrupt_at >= 10`. Unrelated to shop `reroll`.
- **`won` on `GAME_OVER`** means you beat Ante 8 Boss (stays true in endless). Read **`run_summary.result`** for the actual outcome. Summary shows **`→ menu  then  start DECK STAKE SEED`** with the ended run's seed for replay.
- **Connection blip** during transitions → retry `glance` once.
- **Errors:** `BAD_REQUEST` (bad params), `INVALID_STATE` (wrong state), `NOT_ALLOWED` (game rules), `INTERNAL_ERROR` (Lua crash). Read `error.message`.

## 5. Decision assist

Balatro strategy and scoring formulas: **`know`** CLI and knowledge JSON.

- **`glance` first** — never assume state.
- **Score math:** `query hands` + `know check rule scoring_formula`; wild/kickers/editions → `know list rule`.
- **Boss / joker / tag:** `know preflight` or targeted `know check …` (see Quick start).
- **`estimate`:** dev/regression only — [tools/play/estimate_registry.md](tools/play/estimate_registry.md).

## 6. Further commands

Full **`query` / `know` / `state`** table and friendly subcommand notes: [tools/play/README.md](tools/play/README.md) (Commands, Friendly action subcommands, JSON / advanced).

# Play Helpers

Two interfaces on top of the BalatroBot JSON-RPC API:

- **Friendly subcommands** (default) — positional args, no JSON to quote.
- **JSON envelope** (`state` / `exec` / `query` / `know`) — machine-readable, for advanced use.

## Workflow

1. **One-time:** install Lovely + Steamodded, link this repo into `%AppData%\Balatro\Mods\balatrobot\`, run `make install`, copy `serve.example.ps1` → `serve.ps1`.
2. **Launch:** `.\tools\play\serve.ps1` — starts Balatro with the mod and the API on port 12346.
3. **Play:** in another terminal, use `.\tools\play\bot.ps1 ...`.

See the root [README](../../README.md#local-play) and [`PLAY.md`](../../PLAY.md) for the full play guide.

## Commands

```powershell
.\tools\play\bot.ps1 glance              # compact multi-line state summary
.\tools\play\bot.ps1 estimate            # top playable hands + score estimate
.\tools\play\bot.ps1 state               # full JSON envelope
.\tools\play\bot.ps1 know preflight      # verified joker/boss/stake/tag facts (table; --json for raw)
.\tools\play\bot.ps1 query hands         # poker hand level table (base chips/mult)
.\tools\play\bot.ps1 query blinds        # three-blind summary (table; --json for raw)
.\tools\play\bot.ps1 help                # state-aware command list
```

### What `glance` shows

- **Header:** `state`, `ante`, `round`, `money`, `deck`, `stake`.
- **BLIND_SELECT:** all three blinds (small/big/boss) with target, status, boss
    effect, and any skip-reward tag; the selectable blind is marked `(current, select)`.
- **SELECTING_HAND:** `hands_left` / `discards_left` / `score=X/target`, the
    current blind, jokers and consumables with slot count `jokers (N/5)`, the hand
    (with modifier tags — see below), an `economy:` line when interest / Delayed
    Gratification pending, and the `actions:` line.
- **Card modifier tags** (so buffs are visible without a separate query):
    `e:Mult`, `e:Bonus`, `e:Glass`, `e:Stone`, `e:Wild`, `e:Lucky`, `e:Gold`,
    `e:Steel` (enhancement); `d:Foil`, `d:Holo`, `d:Poly`, `d:Neg` (edition);
    `s:Red`, `s:Blue`, `s:Gold`, `s:Purple` (seal). Example: `4♦[e:Mult,s:Red]`.
    Debuffed cards are wrapped in parentheses: `(7♣)`.
- **Joker editions** are decoded inline: `[0] (+10 mult) Holographic Joker — ...`.
    Joker-internal category codes (e.g. `SUIT MULT`) are dropped; the effect text
    carries that meaning.

### Friendly action subcommands

No JSON, no quoting — `bot.ps1` forwards these to `act.py`, which parses positional args via `commands.build_params` and prints the new state as a compact summary. Append `--json` to any of them to print the raw envelope instead.

| Command                        | Args                                   | Notes                                                                                             |
| ------------------------------ | -------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `start`                        | `DECK STAKE [SEED]`                    | e.g. `start RED WHITE`                                                                            |
| `select`                       | —                                      | select current blind                                                                              |
| `skip`                         | —                                      | skip current blind (Small/Big only) — collects the skip tag                                       |
| `play`                         | `CARD_IDX...`                          | e.g. `play 0 1 2 3 4` (max 5, 0-based)                                                            |
| `discard`                      | `CARD_IDX...`                          | e.g. `discard 0 1`                                                                                |
| `sort`                         | `MODE`                                 | `rank` / `rank-desc` / `rank-asc` / `suit` / `suit-desc` / `suit-asc` (aliases: `r`,`s`,`rd`,...) |
| `rearrange`                    | `hand\|jokers\|consumables FULL_ORDER` | e.g. `rearrange hand 2 0 1 3`                                                                     |
| `buy`                          | `card\|voucher\|pack IDX`              | e.g. `buy card 0`, `buy pack 0`                                                                   |
| `sell`                         | `joker\|consumable IDX`                | e.g. `sell joker 0`                                                                               |
| `reroll`                       | —                                      | reroll shop                                                                                       |
| `cash_out`                     | —                                      | collect round rewards                                                                             |
| `next_round`                   | —                                      | leave shop for blind select                                                                       |
| `pack`                         | `IDX [TARGET_IDX...]` or `skip`        | e.g. `pack 0`, `pack 0 1 2` (targets for Tarot/Spectral), `pack skip`                             |
| `use`                          | `CONSUMABLE_IDX [CARD_IDX...]`         | e.g. `use 0`, `use 0 1 2`                                                                         |
| `death`                        | `CONSUMABLE SOURCE TARGET`             | special: reorders hand then uses Death                                                            |
| `menu`                         | —                                      | return to main menu                                                                               |
| `save` / `load` / `screenshot` | `PATH`                                 |                                                                                                   |

### Debug: `add` / `set` (estimate testing only)

Gated by **`BALATROBOT_ALLOW_CHEATS=1`**. Not listed in normal `actions:` during play. Do not use in normal runs.

```powershell
$env:BALATROBOT_ALLOW_CHEATS = "1"
.\tools\play\bot.ps1 add joker j_dusk
.\tools\play\bot.ps1 add card D_4 enhancement=MULT seal=RED
.\tools\play\bot.ps1 add consumable c_fool
.\tools\play\bot.ps1 set hands 1 discards 0 chips 0
```

Restrictions:

- **`add`**: `joker` / `card` / `consumable` only (no voucher/pack — use `exec` for those).
- **`add card`**: only in `SELECTING_HAND` (API rule); key format `D_4`, `H_A`, …
- Optional flags: `enhancement=`, `seal=`, `edition=`, `eternal=`, `perishable=`, `rental=`
- **`set`**: `hands`, `discards`, `chips` only (aliases: `hands_left`, `discards_left`, `score`)

Typical estimate lab: `select` → `add`/`set` → `estimate` → `play` → compare score.

### `estimate` — score estimator *(optional, not recommended for play)*

**Do not rely on this for normal AI play.** It models only a subset of deterministic
jokers, parses dynamic values from localized UI effect text, and can encourage
over-trusting `[BEATS]`. Prefer `query hands` + `know check rule scoring_formula`.
Use `estimate` for dev/regression and joker modeling (`estimate_registry.md`).

**Deterministic only:** models effects fixed by current state + your card choice.
RNG jokers (Misprint, 8 Ball, Bloodstone, …) stay `unmodeled`. Full registry +
**mandatory modeling checklist**: [`estimate_registry.md`](estimate_registry.md).
Verify new jokers in `%APPDATA%\Balatro\Mods\lovely\game-dump\card.lua` before porting.

`bot.ps1 estimate` is only available in `SELECTING_HAND`. It enumerates 1–5 card
plays, classifies each poker hand, and scores: hand level + scoring-card chips +
enhancement/edition/seal + retriggers + modeled jokers (+Mult before ×Mult) +
boss debuff (The Flint) + Plasma balancing.

Prints top-3 lines with **`idx`** = full `bot.ps1 play` indices (includes kickers
when they change held-card jokers like Blackboard); optional **`scoring=`** when
kickers differ from scorers; `[BEATS]` / `[short]` vs blind target. Dusk uses API
`hands_left == 1` (= game's internal `0` after decrement). `--json` adds
`scoring_indices`, `scoring_cards`, `unmodeled_jokers`.

Modeled jokers: see registry. Economy jokers (Riff-raff, Egg, …) are no-ops.
Anything else → `unmodeled` (treat score as lower bound only).

### JSON / advanced

```powershell
.\tools\play\bot.ps1 state                       # full play envelope (gamestate + actions + queries)
.\tools\play\bot.ps1 exec '{\"command\":\"play\",\"params\":{\"cards\":[0,1,2,3,4]}}'
.\tools\play\bot.ps1 query deck | query hands | query blinds | query used_vouchers | query seed
```

> **PowerShell quoting:** `exec` takes a JSON string argument. PowerShell strips
> unescaped double quotes when passing to native exes, so you must escape them
> as `\"` (as shown above). Prefer the friendly subcommands — they avoid this
> entirely.

## AI loop

1. `glance` → compact state + `actions:` line (valid next commands)
2. `know preflight` → verified joker/boss/stake/tag effects (before non-trivial decisions)
3. (optional) `query hands` / `query deck` / … — **use `query hands` for scoring math**
4. friendly action subcommand → prints the new compact state automatically
5. Repeat until `state == GAME_OVER`, then `menu` + `start`

*(Optional, not recommended: `estimate` — partial score model for dev/regression only.)*

Every `glance` / action output ends with an `actions:` line listing the
commands valid in the current state. The full envelope (from `state` /
`exec` / `<action> --json`) includes an `actions[]` array with `example`
payloads for each.

## Files

- `bot.ps1` — entry point (`glance` / `estimate` / `state` / `query` / `know` / `exec` / `help` + friendly action subcommands)
- `view.py` — compact summary formatter + `glance` command (`card_label`, `print_summary`)
- `act.py` — friendly action dispatcher (`build_params` → `execute` → compact summary, `--json` for envelope)
- `estimate.py` — score estimator (`estimate` command, top playable hands + modeled-joker scoring)
- `estimate_registry.md` — modeled / no-op / never-RNG joker list + source refs
- `state.py` — full JSON gamestate envelope
- `query.py` — Layer 2 queries (table output by default; `--json` for raw)
- `exec.py` — raw JSON-RPC action, returns envelope
- `know.py` — knowledge base lookups (preflight table by default; `--json` for raw)
- `commands.py` — friendly-command → RPC params parser
- `cheats.py` — gated `add`/`set` parsers (requires `BALATROBOT_ALLOW_CHEATS=1`)
- `actions.py` — state-aware action list builder
- `layers.py`, `envelope.py`, `start_options.py`, `bot_client.py` — core logic
- `serve.example.ps1` — copy to `serve.ps1` and set your Balatro Steam path (`serve.ps1` is gitignored)


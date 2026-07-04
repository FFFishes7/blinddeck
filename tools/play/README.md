# Play Helpers

Command-line helpers on top of the BlindDeck JSON-RPC API.

## Two command styles

- **Compact commands** (default) — positional args (`glance`, `play 0 1 2 3 4`, `select`). No JSON quoting.
- **JSON commands** — `state`, `exec`, `query … --json`, `know … --json` for structured output and scripting.

See [PLAY.md](../../PLAY.md#three-ways-to-read-state) for when to use compact summaries, detail queries, full JSON state, and knowledge lookups.

## Workflow

1. **One-time:** install Lovely + Steamodded, link this repo into `%AppData%\Balatro\Mods\balatrobot\`, run `make install`, copy `serve.example.ps1` → `serve.ps1`.
2. **Launch:** `.\tools\play\serve.ps1` — starts Balatro with the mod and the API on port 12346.
3. **Play:** in another terminal, use `.\tools\play\bot.ps1 ...`.

See the root [README](../../README.md#quick-start-windows) and [`PLAY.md`](../../PLAY.md) for the full play guide.

## Commands

```powershell
.\tools\play\bot.ps1 glance              # compact summary (default state read)
.\tools\play\bot.ps1 estimate            # top playable hands + score estimate
.\tools\play\bot.ps1 state               # full JSON state + actions + queries
.\tools\play\bot.ps1 know preflight      # verified joker/boss/stake/tag facts (table; --json for raw)
.\tools\play\bot.ps1 query hands         # detail query: poker hand level table
.\tools\play\bot.ps1 query blinds        # detail query: three-blind summary
.\tools\play\bot.ps1 help                # state-aware command list
```

### What `glance` shows

- **Header:** `state`, `ante`, `round`, `money`, `deck`, `stake`. In **SHOP** with
    Credit Card (`bankrupt_at != 0`), also **`buy_power=`** (`money - bankrupt_at`).
- **MENU:** `→ start DECK STAKE [SEED]` plus compact `decks:` / `stakes:` lists; `actions:` lists valid command names (e.g. `start load`).
- **BLIND_SELECT:** all three blinds (small/big/boss) with target, status, boss
    effect, and any skip-reward tag; the selectable blind is marked `(current, select)`.
    When the tag stack is stable, **`held tags (pending): …`** lists untriggered
    tags already earned from earlier skips (oldest → newest) — not the skip reward
    on upcoming blinds (`blinds.*.tag_name`). `glance` waits for `held_tags_ready`
    before returning (same idea as transient state polling).
    With Director's Cut or Retcon at Boss selection, **`reroll_boss=$10 [ok]`** /
    **`[need $N]`** / **`[used this ante]`** may appear; `actions:` includes
    `reroll_boss` when `round.boss_reroll_available`.
- **SELECTING_HAND:** `hands_left` / `discards_left` / `score=X/target` with
    **`need=N`** when below the blind target or **`beaten`** when at/above it; the
    current blind (boss `effect=` only — no skip-reward tag while playing), jokers
    and consumables with slot count `jokers (N/5)`, the hand (with modifier tags —
    see below), an `economy:` line when interest / Delayed Gratification /
    **rental** pending, and the `actions:` line.
- **SHOP:** each shop row shows price plus **`[ok]`**, **`[need $N]`**, or
    **`[slots full]`** (joker/consumable slots full — same check as `buy.lua`).
    Reroll uses affordability only. Header may include **`buy_power=`** when
    `bankrupt_at != 0`. Slot/full-price hints are on shop rows, not duplicated in
    `actions:`.
- **SMODS_BOOSTER_OPENED:** pack rows show target hints such as **`(needs 1-2 targets)`**
    from API `target_min`/`target_max` (Tarot/Spectral).
- **GAME_OVER:** restart hint uses the ended run's deck/stake, e.g.
    **`→ menu  then  start RED WHITE [SEED]`**.
- **ROUND_EVAL:** `round won, score=…` plus a **`pending:`** line (hands-left $,
    interest, Delayed Gratification). When **`victory_overlay`** is set after
    winning the run, **`→ endless`** then **`→ cash_out`**; otherwise **`→ cash_out`** only.
- **Transient states** (`HAND_PLAYED`, `DRAW_TO_HAND`, `NEW_ROUND`, `PLAY_TAROT`):
    **`→ transient: wait for stable state, then glance again`** and `actions: (none)`.
- **Card modifier tags** (so buffs are visible without a separate query):
    `e:Mult`, `e:Bonus`, `e:Glass`, `e:Stone`, `e:Wild`, `e:Lucky`, `e:Gold`,
    `e:Steel` (enhancement); `d:Foil`, `d:Holo`, `d:Poly`, `d:Neg` (edition);
    `s:Red`, `s:Blue`, `s:Gold`, `s:Purple` (seal). Example: `4♦[e:Mult,s:Red]`.
    Debuffed cards are wrapped in parentheses: `(7♣)`.
- **Joker / consumable stickers** inline: `[0] (perishable 3r) (rental -$1/round)   (+10 mult) Holographic Jolly Joker — ...`. Shop rows use the same sticker
    prefix when a card has edition/perishable/rental.
- **Joker editions** are decoded inline: `[0] (+10 mult) Holographic Joker — ...`.
    Joker-internal category codes (e.g. `SUIT MULT`) are dropped; the effect text
    carries that meaning.

### Friendly action subcommands

No JSON, no quoting — `bot.ps1` forwards these to `act.py`, which parses positional args via `commands.build_params` and prints a compact summary. Append `--json` for full JSON state instead.

| Command                        | Args                                   | Notes                                                                                             |
| ------------------------------ | -------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `start`                        | `DECK STAKE [SEED]`                    | e.g. `start RED WHITE`                                                                            |
| `select`                       | —                                      | select current blind                                                                              |
| `reroll_boss`                  | —                                      | reroll Boss blind ($10; Director's Cut / Retcon)                                                  |
| `skip`                         | —                                      | skip current blind (Small/Big only) — collects the skip tag                                       |
| `play`                         | `CARD_IDX...`                          | e.g. `play 0 1 2 3 4` (max 5, 0-based)                                                            |
| `discard`                      | `CARD_IDX...`                          | e.g. `discard 0 1`                                                                                |
| `sort`                         | `MODE`                                 | `rank` / `rank-desc` / `rank-asc` / `suit` / `suit-desc` / `suit-asc` (aliases: `r`,`s`,`rd`,...) |
| `rearrange`                    | `hand\|jokers\|consumables FULL_ORDER` | e.g. `rearrange hand 2 0 1 3`                                                                     |
| `buy`                          | `card\|voucher\|pack IDX`              | e.g. `buy card 0`, `buy pack 0`                                                                   |
| `sell`                         | `joker\|consumable IDX`                | e.g. `sell joker 0`                                                                               |
| `reroll`                       | —                                      | reroll shop                                                                                       |
| `cash_out`                     | —                                      | collect round rewards                                                                             |
| `endless`                      | —                                      | dismiss victory overlay to continue in endless mode (after Ante 8 win)                            |
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
.\tools\play\bot.ps1 debuff 0          # debuff hand card at index 0
.\tools\play\bot.ps1 debuff clear 0    # clear debuff
```

Restrictions:

- **`add`**: `joker` / `card` / `consumable` only (no voucher/pack — use `exec` for those).
- **`add card`**: only in `SELECTING_HAND` (API rule); key format `D_4`, `H_A`, …
- Optional flags: `enhancement=`, `seal=`, `edition=`, `eternal=`, `perishable=`, `rental=`
- **`set`**: friendly `bot.ps1 set` accepts `hands`, `discards`, `chips` only (aliases: `hands_left`, `discards_left`, `score`). For `money`, `ante`, `grant_voucher`, `boss_rerolled`, or `shop`, use `exec` or `balatrobot api set` (JSON-RPC always accepts full params).
- **`debuff`**: `SELECTING_HAND` only; 0-based hand indices; `debuff clear IDX …` to undo

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
**joker-slot Foil/Holo/Poly** (Foil/Holo before effect, Poly after; Blueprint uses
its own slot edition) + boss debuff (The Flint) + Plasma balancing.

Prints top-3 lines with **`idx`** = full `bot.ps1 play` indices (includes kickers
when they change held-card jokers like Blackboard); optional **`scoring=`** when
kickers differ from scorers; `[BEATS]` / `[short]` vs blind target. Dusk uses API
`hands_left == 1` (= game's internal `0` after decrement). `--json` adds
`scoring_indices`, `scoring_cards`, `unmodeled_jokers`.

Modeled jokers: see registry. Economy jokers (Riff-raff, Egg, …) are no-ops.
Anything else → `unmodeled` (treat score as lower bound only).

### JSON / advanced

```powershell
.\tools\play\bot.ps1 state                       # full JSON state (gamestate + actions + queries)
.\tools\play\bot.ps1 exec '{\"command\":\"play\",\"params\":{\"cards\":[0,1,2,3,4]}}'
.\tools\play\bot.ps1 query deck | query hands | query blinds | query used_vouchers | query seed
```

> **PowerShell quoting:** `exec` takes a JSON string argument. PowerShell strips
> unescaped double quotes when passing to native exes, so you must escape them
> as `\"` (as shown above). Prefer the friendly subcommands — they avoid this
> entirely.

## AI loop

1. `glance` → compact summary + `actions:` line (valid next commands)
2. `know preflight` → verified joker/boss/stake/tag effects (before non-trivial decisions)
3. (optional) `query hands` / `query deck` / … — **use `query hands` for scoring math**
4. friendly action subcommand → prints the new compact summary automatically
5. Repeat until `state == GAME_OVER`, then `menu` + `start`

*(Optional, not recommended: `estimate` — partial score model for dev/regression only.)*

Every `glance` / action output ends with an `actions:` line listing **command
names** valid in the current state (deduplicated, e.g. `actions: play discard sort buy reroll next_round`). Use `bot.ps1 help` or [PLAY.md](../../PLAY.md) for argument syntax.

For full JSON state (`state`, `exec`, or `<action> --json`), the same commands appear in an `actions[]` array with `example` payloads for each.

## Files

- `bot.ps1` — entry point (`glance` / `estimate` / `state` / `query` / `know` / `exec` / `help` + friendly action subcommands)
- `view.py` — compact summary formatter + `glance` command (`card_label`, `print_summary`)
- `act.py` — friendly action dispatcher (`build_params` → `execute` → compact summary, `--json` for full state)
- `estimate.py` — score estimator CLI + pipeline (`estimate` command)
- `estimate_jokers.py` — joker registry and scoring effects (add new jokers here)
- `estimate_constants.py` — rank/chip tables shared by classifier and jokers
- `estimate_registry.md` — modeled / no-op / never-RNG joker list + source refs
- `state.py` — full JSON gamestate for `state` command
- `query.py` — detail queries (table by default; `--json` for raw)
- `exec.py` — raw JSON-RPC action, returns full state envelope
- `know.py` — knowledge base lookups (preflight table by default; `--json` for raw)
- `commands.py` — friendly-command → RPC params parser
- `cheats.py` — gated `add`/`set`/`debuff` parsers (requires `BALATROBOT_ALLOW_CHEATS=1`)
- `actions.py` — state-aware action list builder
- `layers.py`, `envelope.py`, `start_options.py`, `bot_client.py` — core logic (internal; user docs say compact summary / detail queries)
- `serve.example.ps1` — copy to `serve.ps1` and set your Balatro Steam path (`serve.ps1` is gitignored)

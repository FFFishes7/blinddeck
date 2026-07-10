# Play Helpers

Command-line helpers on top of the BlindDeck JSON-RPC API.

## Two command styles

- **Compact commands** (default) — positional args (`glance`, `play 0 1 2 3 4`, `select`). No JSON quoting.
- **JSON commands** — `state`, `exec`, `query … --json`, `know … --json` for structured output and scripting.

See [PLAY.md §1–§6](../../PLAY.md#1-what-you-are-doing) for the play loop, scoring essentials, and pitfalls; this file for glance field details and command args.

## Workflow

1. **One-time:** install Lovely + Steamodded, link this repo into `%AppData%\Balatro\Mods\balatrobot\`, run `make install`, copy `serve.example.ps1` → `serve.ps1`.
2. **Launch:** `.\tools\play\serve.ps1` — starts Balatro with the mod and the API on port 12346.
3. **Play:** in another terminal, use `.\tools\play\bot.ps1 ...`.

See the root [README](../../README.md#quick-start-windows) and [PLAY.md](../../PLAY.md#1-what-you-are-doing) for the play guide.

## Commands

```powershell
.\tools\play\bot.ps1 glance              # compact summary (default state read)
.\tools\play\bot.ps1 estimate            # top playable hands + score estimate
.\tools\play\bot.ps1 state               # full JSON state + actions + queries
.\tools\play\bot.ps1 know preflight      # phase-aware verified facts table (deck/stake/jokers/…; --json for raw)
.\tools\play\bot.ps1 know check joker "Baron"
.\tools\play\bot.ps1 know check rule scoring_formula
.\tools\play\bot.ps1 know list jokers    # aliases: joker, rules → rule
.\tools\play\bot.ps1 know stats
.\tools\play\bot.ps1 query hands         # detail query: poker hand level table
.\tools\play\bot.ps1 query blinds        # detail query: three-blind summary
.\tools\play\bot.ps1 challenges          # native IDs, unlock/completion status, and setup
.\tools\play\bot.ps1 challenge c_omelette # start an unlocked native challenge by ID
.\tools\play\bot.ps1 help                # formatted command catalog + descriptions
.\tools\play\bot.ps1 help --now          # + valid-now examples when game is running
.\tools\play\bot.ps1 help --json         # machine-readable help-v2 envelope
```

`know check`, `know list`, and `know stats` always print JSON. `know preflight` prints a compact table by default; add `--json` for the raw envelope.

**Environment:** `BALATROBOT_KNOWLEDGE_DIR` overrides the default `knowledge/balatro/` lookup path (see [knowledge/balatro/README.md](../../knowledge/balatro/README.md)).

### What `glance` shows

- **Header:** `state`, `ante`, `round`, `money`, `deck`, `stake`, and active `challenge` when applicable. In **SHOP** with
    Credit Card (`bankrupt_at != 0`), also **`buy_power=`** (`money - bankrupt_at`).

- **MENU:** `→ start DECK STAKE [SEED]` plus compact `decks:` / `stakes:` lists and `→ challenges then challenge CHALLENGE_ID`. `challenges` prints native IDs, profile unlock/completion state, and setup details; `challenge ID` starts only an unlocked challenge at its built-in White Stake.

- **BLIND_SELECT:** all three blinds (small/big/boss) with target, status, boss
    effect, and any skip-reward tag; the selectable blind is marked `(current, select)`.
    When the tag stack is stable, **`held tags (pending): …`** lists untriggered
    tags already earned from earlier skips (oldest → newest) — not the skip reward
    on upcoming blinds (`blinds.*.tag_name`). During in-run states only
    (`BLIND_SELECT`, `SELECTING_HAND`, `ROUND_EVAL`, `SHOP`, `SMODS_BOOSTER_OPENED`),
    `glance` waits for `held_tags_ready` before returning — not at **`MENU`** or
    **`GAME_OVER`** (same idea as transient state polling).
    With Director's Cut or Retcon at Boss selection, **`reroll_boss=$10 [ok]`** /
    **`[need $N]`** / **`[used this ante]`** may appear; `actions:` includes
    `reroll_boss` when `round.boss_reroll_available`.

- **SELECTING_HAND:** `hands_left` / `discards_left` / `score=X/target` with
    **`need=N`** when below the blind target or **`beaten`** when at/above it; the
    current blind (boss `effect=` only — no skip-reward tag while playing), jokers
    and consumables with slot count `jokers (N/5)`, the hand (with modifier tags —
    see below), an `economy:` line when relevant (**SELECTING_HAND only** — Delayed
    Gratification / rental hints, not passive interest) and the `actions:` line.

- **SHOP:** each shop row shows price plus **`[ok]`**, **`[need $N]`**, or
    **`[slots full]`** (joker/consumable slots full — same check as `buy.lua`).
    Reroll uses affordability only. Header may include **`buy_power=`** when
    `bankrupt_at != 0`. With 2+ jokers, `actions:` includes
    **`rearrange jokers`**.

- **SMODS_BOOSTER_OPENED:** first line under `pack:` is **`choices remaining: N`** — picks still required from **this** open booster (from `G.GAME.pack_choices`). **Charm Tag** skip opens **Mega Arcana** (**2**, then **1** after the first pick); shop normal Arcana is **1**; mega packs from shop are **2** → **1**. Pack rows show target hints such as **`(needs 1-2 targets)`**
    from API `target_min`/`target_max` (hand cards). **`pack IDX [hand indices…]`** — targets are **0-based hand positions** from the `hand:` line, not rank values. Death: **`pack 0 I J`** — first target I is the source (transformed), second target J is the template (copied). Random-joker Spectrals (Ankh, Hex,
    Ectoplasm) show **`(random joker — pack targets ignored)`** plus a one-line note when any
    pack card has `random_joker_effect`. Example:

    ```text
    pack:
      choices remaining: 2
      pack[0] The Magician — convert 2 cards (needs 1-2 targets)
      pack[1] The Fool — copy last Tarot
    actions: pack sell use
    ```

    While **`choices remaining` > 0**, use **`pack 0`** / **`pack 1`** (with hand targets when shown). **`pack skip`** forfeits all remaining picks in the current pack — not “advance to the next blind”. **`sort`** is not available while a pack is open (Balatro's Rank/Suit buttons are hidden by the pack overlay, even in Arcana/Spectral packs where hand cards are visible for targeting).
    `glance` waits for **`pack_ready`** and **`pack_hand_ready`** (Arcana/Spectral deal animation) before snapshotting — avoids empty `pack:` rows between consecutive pack tags.

- **GAME_OVER:** restart hint uses the ended run's deck/stake/seed, e.g.
    **`→ menu  then  start RED WHITE ABC123`**.

- **ROUND_EVAL:** `round won, score=…` plus **`pending:`** (income rows + **`total +$N`** for remaining **`cash_out`** bundle).
    In normal **`ROUND_EVAL`**, **`actions:`** offers **`cash_out`** only; inventory **`sell`** and **`use`** are disabled until the next state.
    **Investment Tag** on boss defeat: **`received: +$N Investment Tag (boss defeat)`** — already in **`money=`**; not listed under **`pending:`**.
    If **`victory_overlay`**, **`→ endless`** then **`→ menu`** only — **`actions:`** and API allow **`endless`** / **`menu`** only (no **`cash_out`**, **`sell`**, **`use`**, or **`save`** until overlay dismissed). Example:

    ```text
    round won, score=500
      pending: +$3 blind · +$3 hands · +$4 Golden Joker · +$2 interest · total +$12
    → cash_out
    ```

- **Transient states** (`HAND_PLAYED`, `DRAW_TO_HAND`, `NEW_ROUND`, `PLAY_TAROT`):
    **`→ transient: wait for stable state, then glance again`** and `actions: (none)`.

- **Card modifier tags** on hand cards and pack rows — abbreviations in [PLAY.md §5](../../PLAY.md#5-read-glance) (`e:`/`d:`/`s:`). Example: `4♦[e:Mult,s:Red]`. Debuffed cards: `(7♣)`. Cerulean Bell forced hand cards show `[forced]`; ordinary highlighted cards show `[selected]`.

- **Joker / consumable stickers** inline: `[0] (+$3 sell) (perishable 3r) (rental -$1/round) (+10 mult) Holographic Jolly Joker — ...`. **`(+$N sell)`** is sell value when you **`sell joker|consumable`** (omitted for **eternal**). Shop rows use the same sticker
    prefix when a card has edition/perishable/rental (shop buy price stays **`$N`** on the row).

- **Joker editions** are decoded inline: `[0] (+$2 sell) (+10 mult) Holographic Joker — ...`.
    Joker-internal category codes (e.g. `SUIT MULT`) are dropped; the effect text
    carries that meaning. The `— effect` suffix is **mechanism description only** —
    profile stake win sticker sentences (e.g. “win on White Stake”) are omitted from
    `value.effect` / glance.

### Friendly action subcommands

No JSON, no quoting — `bot.ps1` forwards these to `act.py`, which parses positional args via `commands.build_params` and prints a compact summary. Append `--json` for full JSON state instead.

| Command                        | Args                            | Notes                                                                                                                                                                                                                                                                                              |
| ------------------------------ | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `start`                        | `DECK STAKE [SEED]`             | e.g. `start RED WHITE`                                                                                                                                                                                                                                                                             |
| `select`                       | —                               | select current blind                                                                                                                                                                                                                                                                               |
| `reroll_boss`                  | —                               | reroll Boss blind ($10; Director's Cut / Retcon)                                                                                                                                                                                                                                                   |
| `skip`                         | —                               | skip current blind (Small/Big only) — collects the skip tag                                                                                                                                                                                                                                        |
| `play`                         | `CARD_IDX...`                   | e.g. `play 0 1 2 3 4` (1-5 cards, 0-based)                                                                                                                                                                                                                                                         |
| `discard`                      | `CARD_IDX...`                   | e.g. `discard 0 1`                                                                                                                                                                                                                                                                                 |
| `sort`                         | `MODE`                          | `rank` / `rank-desc` / `rank-asc` / `suit` / `suit-desc` / `suit-asc` (aliases: `r`,`s`,`rd`,...)                                                                                                                                                                                                  |
| `rearrange`                    | `jokers FULL_ORDER`             | e.g. `rearrange jokers 1 0`                                                                                                                                                                                                                                                                        |
| `buy`                          | `card\|voucher\|pack IDX`       | e.g. `buy card 0`, `buy pack 0`                                                                                                                                                                                                                                                                    |
| `sell`                         | `joker\|consumable IDX`         | e.g. `sell joker 0`                                                                                                                                                                                                                                                                                |
| `reroll`                       | —                               | reroll shop                                                                                                                                                                                                                                                                                        |
| `cash_out`                     | —                               | collect round rewards                                                                                                                                                                                                                                                                              |
| `endless`                      | —                               | dismiss victory overlay to continue in endless mode (after Ante 8 win)                                                                                                                                                                                                                             |
| `next_round`                   | —                               | leave shop for blind select                                                                                                                                                                                                                                                                        |
| `pack`                         | `IDX [TARGET_IDX...]` or `skip` | e.g. `pack 0`, `pack 0 1 2` — **hand [N] indices** from `hand:` line (not ranks); Death: `pack 0 I J` (first target I = source, second J = template); Ankh/Hex/Ectoplasm ignore targets (`random_joker_effect`); **`pack skip`** forfeits all remaining picks (see `choices remaining:` in glance) |
| `use`                          | `CONSUMABLE_IDX [CARD_IDX...]`  | e.g. `use 0`, `use 0 1 2` — Death (Tarot): `use 0 I J` (first target I = source (transformed), second J = template (copied))                                                                                                                                                                       |
| `menu`                         | —                               | return to main menu                                                                                                                                                                                                                                                                                |
| `save` / `load` / `screenshot` | `PATH`                          | Normal `save PATH` prints `save success: PATH` instead of a state summary. For `save`/`load`, relative paths are automatically resolved into this project's `saves/` folder. Use an absolute path if you want to save elsewhere.                                                                   |

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

Follow [PLAY.md §2 Loop and hard rules](../../PLAY.md#2-loop-and-hard-rules). Scoring math: [PLAY.md §3 Scoring essentials](../../PLAY.md#3-scoring-essentials) + `query hands` — not `estimate`.

1. `glance` → compact summary + `actions:` line (valid next commands)
2. `know preflight` at blind select / skip decision (phase-aware table — see PLAY.md §2)
3. `query hands` when estimating a play in `SELECTING_HAND`
4. friendly action subcommand → prints the new compact summary automatically
5. Repeat until `state == GAME_OVER`, then `menu` + `start DECK STAKE SEED` (seed from summary restart hint)

Every `glance` / action output ends with an `actions:` line listing **command
names** valid in the current state (deduplicated, e.g. `actions: play discard sort buy reroll next_round`). **`use`** appears only when each owned consumable can actually be used: Tarot/Spectral cards that need hand targets require enough **visible** hand cards (`target_min`, or 2 for Death); random-joker Spectrals (Ankh/Hex/Ectoplasm) and no-target cards (Planet, Fool, …) may still show `use` without a hand. Use `bot.ps1 help` (catalog + descriptions), `bot.ps1 help --now` (valid now), or [PLAY.md §4–§5](../../PLAY.md#4-state--command) for argument syntax.

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
- `help.py` / `help_catalog.py` — formatted command catalog (`help`, `help --now`, `help --json`)
- `commands.py` — friendly-command → RPC params parser
- `cheats.py` — gated `add`/`set`/`debuff` parsers (requires `BALATROBOT_ALLOW_CHEATS=1`)
- `actions.py` — state-aware action list builder
- `layers.py`, `envelope.py`, `start_options.py`, `bot_client.py` — core logic (internal; user docs say compact summary / detail queries)
- `serve.example.ps1` — copy to `serve.ps1` and set your Balatro Steam path (`serve.ps1` is gitignored)

# Playing Balatro with BlindDeck — Quick Guide for AI Agents

You are the player. **Play Balatro with your human:** read state, reason each turn, and act through the API — one command at a time. The game runs on `127.0.0.1:12346` and exposes a JSON-RPC 2.0 API. You call endpoints; the game responds with the new state. This file tells you everything you need to run a full game without reading any source.

**Read this if…**

- **Playing a run** (human or agent) — follow the core loop and [Command reference](#6-command-reference) below.
- **Writing a script** against the API — use `bot.ps1 state` or `--json`; see [docs/api.md](docs/api.md).
- **Changing the mod or helpers** — see [AGENTS.md](AGENTS.md) and [docs/OVERVIEW.md](docs/OVERVIEW.md).

For installation and launch, see [README.md](README.md). Command details: [tools/play/README.md](tools/play/README.md).

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

## 1. The Core Loop

```
repeat:
  1. bot.ps1 glance                    ← compact state summary (state, blinds, hand, jokers, actions)
  2. (optional, not recommended) bot.ps1 estimate  ← score helper; incomplete joker model — prefer reasoning + query hands
  3. (optional) bot.ps1 know preflight ← verify joker/boss/tag effects before deciding
  4. bot.ps1 <action> [args]           ← see [State → command table](#2-state--friendly-command-table)
  5. read the printed compact summary  ← the action prints the new state automatically
until state == GAME_OVER
```

After `GAME_OVER`: `bot.ps1 menu`, then `bot.ps1 start DECK STAKE` (e.g. `start RED WHITE`).

### Three ways to read state

| Kind                  | Commands                                                                         | Output                                           | When to use                                             |
| --------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------- |
| **Compact summary**   | `glance`, any action (default)                                                   | Multi-line text + `actions:`                     | Every turn — default                                    |
| **Detail queries**    | `query hands`, `query deck`, `query blinds`, `query used_vouchers`, `query seed` | Table (default) or JSON (`--json`)               | Scoring math, deck tracking, extra blind/voucher detail |
| **Full state (JSON)** | `state`, any action with `--json`                                                | JSON: `gamestate`, `actions`, optional `queries` | Scripting / structured parsing                          |
| **Knowledge lookups** | `know preflight`, `know check …`                                                 | Verified joker/boss/tag/rule tables              | Before non-trivial decisions                            |

**Rule of thumb:** `glance` first; use `query hands` for score math; use `state --json` only when you need machine-readable structure.

### The `actions:` line is your navigation

Every `glance` and action output ends with an `actions:` line listing valid
command names for the current state (deduplicated, e.g. `actions: play discard sort buy reroll next_round`).

For full JSON state (`bot.ps1 state`, `bot.ps1 exec ...`, or any action with `--json`), the same commands appear in an `actions[]` array; each entry includes a ready-to-use `example` payload with concrete indices when applicable.

When you don't know what to do, read `actions:`.

### What `glance` shows you (so you rarely need `state`)

- **BLIND_SELECT:** all three blinds (small/big/boss) with target, status, boss
    effect, and skip-reward tag; the selectable blind is marked `(current, select)`.
    When the tag stack is stable, **`held tags (pending): …`** lists tags already
    earned from earlier skips (oldest → newest) — not skip rewards on upcoming
    blinds. See [Tag semantics](#tag-semantics-skip-rewards). Defeated blinds omit
    skip-reward text. When Boss is on deck and you own Director's Cut or Retcon, a
    **`reroll_boss=$10 [ok]`** / **`[need $N]`** / **`[used this ante]`** line
    appears; `actions:` may include `reroll_boss`.
- **SELECTING_HAND:** `score=X/target` includes **`need=N`** until you beat the
    blind, then **`beaten`**. Skip-reward tags are not repeated on the current blind
    line (you already chose to play).
- **SHOP:** prices show **`[ok]`**, **`[need $N]`**, or **`[slots full]`**; header
    adds **`buy_power=`** when Credit Card raises `bankrupt_at`.
- **Pack open:** Tarot/Spectral candidates show **`(needs 1-2 targets)`** etc.
- **GAME_OVER:** **`→ menu  then  start RED WHITE [SEED]`** uses the run's deck/stake.
- **ROUND_EVAL:** pending round-end money (hands left, interest, Delayed
    Gratification) before **`→ cash_out`**. After beating Ante 8 Boss, if
    **`victory_overlay`** is set, **`→ endless`** appears first — dismiss the
    win screen, then **`cash_out`** → shop → **`next_round`** for Ante 9+.
- **Transient states** (`HAND_PLAYED`, etc.): wait and **`glance`** again — no
    actions until stable.
- **Hand cards and eligible pack candidates carry modifier tags:** `4♦[e:Mult,s:Red]` = Mult enhancement + Red
    seal. Legend: enhancement `e:Mult/Bonus/Glass/Stone/Wild/Lucky/Gold/Steel`
    (`e:Wild` = all suits, **rank unchanged** — `know check rule wild_card_enhancement`),
    edition `d:Foil/Holo/Poly/Neg`, seal `s:Red/Blue/Gold/Purple`. Debuffed cards
    are wrapped `(7♣)`. So you can see buffs without a separate query.
- **Joker & consumable slots:** `jokers (5/5)` / `consumables (1/2)`.
- **Economy:** an `economy:` line shows pending interest, Delayed Gratification
    bonus, and rental joker upkeep (`rental_due=-$N/round`) when relevant.

## 2. State → Friendly Command Table

| State                  | What to do                                      | Command                                                                                                                          |
| ---------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `MENU`                 | Start a run                                     | `bot.ps1 start DECK STAKE` (e.g. `start RED WHITE`; optional seed: `start DECK STAKE SEED`)                                      |
| `BLIND_SELECT`         | Play or skip the blind                          | `bot.ps1 select` · `bot.ps1 skip` (Small/Big only) · `bot.ps1 reroll_boss` (Boss + Director's Cut / Retcon, $10)                 |
| `SELECTING_HAND`       | Play / discard / use / sort (estimate optional) | `bot.ps1 play 0 1 2 3 4` · `bot.ps1 discard 0 1` · `bot.ps1 use 0 [1 2]` · `bot.ps1 sort rank` · *(optional)* `bot.ps1 estimate` |
| `HAND_PLAYED`          | Transient — just poll                           | `bot.ps1 glance`                                                                                                                 |
| `ROUND_EVAL`           | Collect rewards                                 | `bot.ps1 cash_out` · if `victory_overlay`: `bot.ps1 endless` first, then `cash_out`                                              |
| `SHOP`                 | Buy / reroll / sell / leave                     | `bot.ps1 buy card 0` · `bot.ps1 buy pack 0` · `bot.ps1 reroll` · `bot.ps1 sell joker 0` · `bot.ps1 next_round`                   |
| `SMODS_BOOSTER_OPENED` | Pick or skip                                    | `bot.ps1 pack 0` (or `pack 0 1 2` with targets) · `bot.ps1 pack skip`                                                            |
| `GAME_OVER`            | Run ended                                       | `bot.ps1 menu` then `start`                                                                                                      |

Command arg cheatsheet:

- `start DECK STAKE [SEED]` — `DECK` ∈ {RED, BLUE, YELLOW, GREEN, BLACK, MAGIC, NEBULA, GHOST, ABANDONED, CHECKERED, ZODIAC, PAINTED, ANAGLYPH, PLASMA, ERRATIC}; `STAKE` ∈ {WHITE, RED, GREEN, BLACK, BLUE, PURPLE, ORANGE, GOLD}.
- `play` / `discard` — card indices, max 5 for `play`.
- `buy card|voucher|pack IDX` — 0-based index into the shop / vouchers / packs area.
- `pack IDX [TARGETS...]` — `TARGETS` only for Tarot/Spectral-style cards acting on hand cards. `pack skip` closes the pack.
- `use CONSUMABLE [CARDS...]` — `CARDS` only for consumables that target hand cards.
- `sort MODE` — `rank` / `rank-desc` / `rank-asc` / `suit` / `suit-desc` / `suit-asc` (aliases `r`,`s`,`rd`...).
- `sell joker|consumable IDX` · `rearrange hand|jokers|consumables FULL_ORDER` (e.g. `rearrange hand 2 0 1 3`).

Debug (estimate testing only — not for normal play; requires `$env:BALATROBOT_ALLOW_CHEATS=1`):

- `add joker j_dusk` · `add card D_4 enhancement=MULT seal=RED` · `add consumable c_fool`
- `set hands 1 discards 0 chips 0` — friendly `set` only accepts `hands` / `discards` / `chips` (money/ante/voucher debug via raw `exec` or API `set`)
- `debuff 0` · `debuff clear 0` — debuff or clear hand cards (`SELECTING_HAND` only)
- Not listed in normal `actions:`; see `tools/play/README.md` for restrictions

### Tag semantics (skip rewards)

`blinds.{small,big}.tag_name` / `tag_effect` are **skip rewards** — they only trigger
if you `skip` that blind, not if you defeat it. The boss blind has no tag. Read
`tag_effect` before deciding to skip (e.g. a Foil Tag gives a free foil joker next
shop; an Investment Tag gives money per skip this round). `know preflight` also
lists pending tags with verified effects.

**Five tags open a booster immediately on skip** (Charm / Meteor / Ethereal /
Standard / Buffoon — see `know check tag "Charm Tag"` and `opens_pack_on_skip` in
the tag library). After skip, `glance` should show `SMODS_BOOSTER_OPENED` and
`actions: pack …`. Most other tags (Foil, Economy, Boss, …) stay on
`BLIND_SELECT`. Buffoon/Meteor/Ethereal/Standard only appear from ante 2+; Charm
is the only pack tag on ante 1. Tags stack oldest-first — an older Charm Tag can
still open a pack when you skip a later blind with a non-pack tag.

**Held tags (pending stack):** After tag animations settle, `glance` / action
summaries may show `held tags (pending): …` — tags you already earned by
skipping earlier blinds but have **not triggered yet** (oldest → newest). This
is a **stable snapshot** only: `glance` waits for `held_tags_ready` (like
transition states). It does **not** predict Double Tag copies or shop trigger
order. For skip rewards on blinds you have **not** skipped yet, use
`blinds.{small,big}.tag_name` instead.

## 3. Minimal Full-Game Trace

```powershell
.\tools\play\bot.ps1 glance              # see current state
.\tools\play\bot.ps1 start RED WHITE     # example: start DECK STAKE (see glance for deck/stake list)
.\tools\play\bot.ps1 select              # select current blind
# optional: .\tools\play\bot.ps1 estimate   # score helper (incomplete; not recommended for normal play)
.\tools\play\bot.ps1 sort rank           # sort hand for easier reading
.\tools\play\bot.ps1 play 0 1 2 3 4      # play cards at hand indices 0-4
.\tools\play\bot.ps1 discard 0 1         # or discard to draw replacements
.\tools\play\bot.ps1 cash_out            # collect round rewards → shop
.\tools\play\bot.ps1 buy card 0          # buy joker/consumable from shop
.\tools\play\bot.ps1 buy pack 0          # buy a booster pack
.\tools\play\bot.ps1 pack 0              # take card 0 from the open pack
.\tools\play\bot.ps1 next_round          # leave shop → next blind select
# ... repeat until GAME_OVER
.\tools\play\bot.ps1 menu                # return to main menu
```

Each command prints the new compact state automatically, including the next
`actions:` line — you rarely need a separate `glance` between actions.

> **Do not use `bot.ps1 exec '{"command":...}'`.** PowerShell strips unescaped
> double quotes when passing JSON strings to native exes, so the JSON arrives
> malformed and you get `Expecting property name enclosed in double quotes`.
> The friendly subcommands above avoid quoting entirely. `exec` is only for
> advanced use; if you must, escape quotes as `\"`:
> `bot.ps1 exec '{\"command\":\"play\",\"params\":{\"cards\":[0,1,2,3,4]}}'`.

Equivalent raw JSON-RPC (fallback when `bot.ps1` isn't available):

```powershell
.\.venv\Scripts\python.exe -c "import httpx,json;print(httpx.post('http://127.0.0.1:12346/',json={'jsonrpc':'2.0','method':'start','params':{'deck':'RED','stake':'WHITE'},'id':1}).json())"
```

## 4. Pitfalls

- **0-based indices.** First hand card is `0`. `play 0 1 2 3 4` plays the first five.
- **One request at a time.** The server is single-client, serial. Wait for each response before sending the next.
- **PowerShell eats JSON quotes.** Never call `bot.ps1 exec '{"command":...}'` with bare `"` — PowerShell strips them. Use the friendly subcommands ([State → command table](#2-state--friendly-command-table), [Minimal trace](#3-minimal-full-game-trace)), or escape as `\"` if you must use `exec`.
- **`pack` `targets` only for Tarot/Spectral.** Buffoon/Celestial/Standard packs don't need targets. The endpoint validates target count against the card's requirement and returns `BAD_REQUEST` if wrong.
- **Boss blinds hide card faces.** Cards with `state.hidden == true` return no rank/suit (shown as `??` in `glance`) — do not try to "read" them; decide based on what's visible.
- **`buy` / `reroll` affordability is `money - bankrupt_at`**, not raw `money` (Credit Card raises `bankrupt_at`). `glance` shows `[ok]` / `[need $N]` on shop rows; if a buy still fails with `BAD_REQUEST`, slots may be full or cost changed after reroll.
- **Joker/consumable slots can be full.** `buy` returns `BAD_REQUEST` when slots are full — `sell` something first or skip.
- **`skip` only works on Small/Big blinds**, not boss. Skip collects a tag reward (see [Tag semantics](#tag-semantics-skip-rewards)). Only five tags open a pack on skip; `glance` after skip should show `pack` actions when one fires. If skip with **Charm Tag** leaves blind select with the tag in the HUD but no pack, restart the game (Lua mod reload) — a prior API bug blocked tag apply; use a fresh run after updating.
- \*\*`reroll_boss` is Boss-only and costs $10.** Only in `BLIND_SELECT` when the Boss blind is on deck, you own **Director's Cut** (once per ante) or **Retcon** (unlimited), and `money - bankrupt_at >= 10`. `glance` shows `reroll_boss=$10 [ok]`/`[need $N]`/`[used this ante]`; then`select`the new boss. Shop`reroll\` is unrelated.
- **`won` ≠ current outcome on `GAME_OVER`.** `won: true` means you beat Ante 8 Boss (stays true in endless). Read **`run_summary.result`** for the actual line (`Lost to …`, `Victory`, etc.) — especially after endless-mode death.
- **Connection failure ≠ bug.** During state transitions the server may briefly not respond. Retry `glance` once before investigating.
- **Error names:** `INTERNAL_ERROR` (Lua crash), `BAD_REQUEST` (bad params), `INVALID_STATE` (wrong state), `NOT_ALLOWED` (game rules blocked it). Read `error.message` — it's specific.

## 5. Decision Principles

- **Always `glance` (and ideally `know preflight`) before deciding.** Never assume the state.
- **`bot.ps1 estimate` is optional and not recommended for normal play.** It only models a subset of jokers, may miss locale-specific effect text, and can make agents over-trust a number. Prefer reading the hand + `query hands` + `know check rule scoring_formula` when you need score math. Use `estimate` mainly for dev/regression (`tools/play/estimate_registry.md`), not as the default decision loop.
- **If you do run `estimate`, only in `SELECTING_HAND`.** It returns `INVALID_STATE` elsewhere. Output is a hint only: **`idx`** = full `bot.ps1 play` list when kickers matter (e.g. Blackboard); **`scoring=`** = poker scorers only. **`unmodeled`** jokers mean the true score can be higher — never treat `[BEATS]` as guaranteed.
- **Scoring math (default path):** Run `bot.ps1 query hands` for real base `chips`/`mult`. Apply `bot.ps1 know check rule scoring_formula`: score = Chips × Mult, built in phases (hand base → scoring-card chips → jokers left-to-right, +Mult before ×Mult). **Only the cards forming the poker hand type score — kickers add no chips** (`know check rule kickers_do_not_score`); card chips are A=11, 2-10=face, J/Q/K=10 (`know check rule card_chip_values`). (Example: Three of a Kind is base 30/3 + 3×scoring rank chips, not all five cards.) `know list rule` lists all rules; relevant ones: `scoring_formula`, `kickers_do_not_score`, `card_chip_values`, `hand_base_values_level_1`, `additive_before_multiplicative_mult`, `edition_values`, `enhancement_scoring`, `wild_card_enhancement`, `seal_effects`, `plasma_deck_balances_chips_and_mult`.
- **Wild cards:** Wild counts as every **suit**, not every **rank** — pair Wild only with matching rank (`know check rule wild_card_enhancement`). Do not play Ace + Queen Wild expecting an Ace pair.
- **Beat the blind target, not maximize score.** `round.chips` is your current score; the current blind's `score` is the target. Once you've passed it, you can stop playing hands to bank unused hands ($1 each) and discards.
- **Don't burn discards for no reason.** Each unused hand pays $1 interest at round end (interest capped at $5). Discard only to improve a hand you intend to play.
- **Economy early, scaling late.** In early antes, money compounds. Don't reroll aggressively. Buy jokers that scale (Mult+) or generate economy.
- **Joker order matters.** Put chips and `+Mult` jokers before `×Mult` jokers when possible; after buying Hologram, Polychrome, Card Sharp, etc., consider `bot.ps1 rearrange jokers ...` so multiplicative effects fire late.
- **Boss-blind awareness.** Before `select`ing a boss, run `know preflight` and check the boss effect — some bosses invalidate strategies (e.g. "The Flint" halves base chips/mult, "The Psychic" forces 5-card plays and hides cards). Adjust which cards you play.
- **Vouchers persist for the run.** Buying a voucher is usually higher value than a single joker if it matches your direction.
- **When in doubt in shop:** buy a pack > reroll > skip to next round. Packs give selection among multiple cards.
- **Losing is fine.** If `hands_left` hits 0 and chips < target, the run ends (`GAME_OVER`). Call `menu` and start fresh.

### When to run `know preflight`

Run it before any non-trivial decision:

- **BLIND_SELECT** before `select`ing a **boss** blind (verify the boss effect).
- **SHOP** before buying a joker whose effect you're unsure about (verify with `know check joker "Name"`).
- **SELECTING_HAND** when you own jokers and aren't sure what triggers them.

Output is a `checks[]` array (stake / each joker / boss / pending tags), each with
`passed` and a verified `entry`:

```json
{"ok": true, "format": "balatrobot-know-v1", "preflight": {
  "passed": true,
  "context": {"state": "BLIND_SELECT", "ante_num": 1, "stake": "WHITE", "money": 8},
  "checks": [
    {"kind": "stake", "name": "WHITE", "passed": true, "entry": {...}},
    {"kind": "joker", "name": "Seltzer", "passed": true, "entry": {...}},
    {"kind": "boss", "name": "The Psychic", "passed": true, "entry": {...}},
    {"kind": "tag", "name": "Foil Tag", "slot": "big", "passed": true, "entry": {...}}
  ]
}}
```

`passed: false` means a fact wasn't found in the knowledge library — treat the
effect as unknown and fall back to the in-game `effect`/`tag_effect` text.

## 6. Command reference

| Command                                                                                 | Output                                            | When to use                                                                       |
| --------------------------------------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------- |
| `glance`                                                                                | Compact summary + `actions:`                      | Every turn — primary state read                                                   |
| `query hands`                                                                           | Hand-type level / chips / mult table              | **Scoring math** (preferred over `estimate`)                                      |
| `query deck`                                                                            | Remaining draw pile                               | Deck composition / draw tracking                                                  |
| `query blinds`                                                                          | All three blinds (full detail)                    | When the glance blind block is not enough                                         |
| `query used_vouchers`                                                                   | Vouchers owned this run                           | Shop planning, `reroll_boss` eligibility                                          |
| `query seed`                                                                            | Run seed                                          | Debug / replay                                                                    |
| `state`                                                                                 | Full JSON state + `actions` + available `queries` | Scripting; append `--json` to actions for the same shape                          |
| `know preflight`                                                                        | Verified joker / boss / tag / stake checks        | Before boss select, shop buys, tricky joker lines                                 |
| `know check joker "Name"` / `check boss "Name"` / `check tag "Name"` / `check rule "…"` | Single knowledge entry                            | One-off lookup                                                                    |
| `estimate`                                                                              | Top playable hands + partial score model          | Dev/regression only — [not recommended for play](tools/play/estimate_registry.md) |
| `screenshot PATH` / `save PATH` / `load PATH`                                           | File I/O                                          | Checkpoints and visual debug                                                      |

Append `--json` to `query` or `know` for raw JSON instead of tables.

See also [Three ways to read state](#three-ways-to-read-state) and [tools/play/README.md](tools/play/README.md).

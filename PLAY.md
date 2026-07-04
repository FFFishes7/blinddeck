# Playing Balatro — Quick Guide for AI Agents

You are the player. The game runs on `127.0.0.1:12346` and exposes a JSON-RPC 2.0 API. You call endpoints; the game responds with the new state. This file tells you everything you need to run a full game without reading any source.

For the repo overview and development workflow, see `AGENTS.md` and `docs/OVERVIEW.md`.

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
  4. bot.ps1 <action> [args]           ← see §2 friendly-command table
  5. read the printed compact summary  ← the action prints the new state automatically
until state == GAME_OVER
```

After `GAME_OVER`: `bot.ps1 menu`, then `bot.ps1 start DECK STAKE` (e.g. `start RED WHITE`).

### The `actions:` line is your navigation

Every `glance` and action output ends with an `actions:` line listing valid
command names for the current state (deduplicated, e.g. `actions: play discard sort buy reroll next_round`). The full JSON envelope (from `bot.ps1 state`, `bot.ps1 exec ...`, or any action with `--json`) includes an `actions[]` array where each entry
has a ready-to-use `example` payload with concrete indices when applicable.
When you don't know what to do, read `actions:`.

### What `glance` shows you (so you rarely need `state`)

- **BLIND_SELECT:** all three blinds (small/big/boss) with target, status, boss
    effect, and skip-reward tag; the selectable blind is marked `(current, select)`.
    Defeated blinds omit skip-reward text.
- **SELECTING_HAND:** `score=X/target` includes **`need=N`** until you beat the
    blind, then **`beaten`**. Skip-reward tags are not repeated on the current blind
    line (you already chose to play).
- **SHOP:** prices show **`[ok]`**, **`[need $N]`**, or **`[slots full]`**; header
    adds **`buy_power=`** when Credit Card raises `bankrupt_at`.
- **Pack open:** Tarot/Spectral candidates show **`(needs 1-2 targets)`** etc.
- **GAME_OVER:** **`→ menu  then  start RED WHITE [SEED]`** uses the run's deck/stake.
- **ROUND_EVAL:** pending round-end money (hands left, interest, Delayed
    Gratification) before **`→ cash_out`**.
- **Transient states** (`HAND_PLAYED`, etc.): wait and **`glance`** again — no
    actions until stable.
- **Hand cards and eligible pack candidates carry modifier tags:** `4♦[e:Mult,s:Red]` = Mult enhancement + Red
    seal. Legend: enhancement `e:Mult/Bonus/Glass/Stone/Wild/Lucky/Gold/Steel`,
    edition `d:Foil/Holo/Poly/Neg`, seal `s:Red/Blue/Gold/Purple`. Debuffed cards
    are wrapped `(7♣)`. So you can see buffs without a separate query.
- **Joker & consumable slots:** `jokers (5/5)` / `consumables (1/2)`.
- **Economy:** an `economy:` line shows pending interest, Delayed Gratification
    bonus, and rental joker upkeep (`rental_due=-$N/round`) when relevant.

## 2. State → Friendly Command Table

| State                  | What to do                                      | Command                                                                                                                          |
| ---------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `MENU`                 | Start a run                                     | `bot.ps1 start DECK STAKE` (e.g. `start RED WHITE`; optional seed: `start DECK STAKE SEED`)                                      |
| `BLIND_SELECT`         | Play or skip the blind                          | `bot.ps1 select` · or `bot.ps1 skip` (Small/Big only)                                                                            |
| `SELECTING_HAND`       | Play / discard / use / sort (estimate optional) | `bot.ps1 play 0 1 2 3 4` · `bot.ps1 discard 0 1` · `bot.ps1 use 0 [1 2]` · `bot.ps1 sort rank` · *(optional)* `bot.ps1 estimate` |
| `HAND_PLAYED`          | Transient — just poll                           | `bot.ps1 glance`                                                                                                                 |
| `ROUND_EVAL`           | Collect rewards                                 | `bot.ps1 cash_out`                                                                                                               |
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
- `set hands 1 discards 0 chips 0` — only `hands` / `discards` / `chips` (no money/ante)
- Not listed in normal `actions:`; see `tools/play/README.md` for restrictions

### Tag semantics (skip rewards)

`blinds.{small,big}.tag_name` / `tag_effect` are **skip rewards** — they only trigger
if you `skip` that blind, not if you defeat it. The boss blind has no tag. Read
`tag_effect` before deciding to skip (e.g. a Foil Tag gives a free foil joker next
shop; an Investment Tag gives money per skip this round). `know preflight` also
lists pending tags with verified effects.

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
- **PowerShell eats JSON quotes.** Never call `bot.ps1 exec '{"command":...}'` with bare `"` — PowerShell strips them. Use the friendly subcommands (§2/§3), or escape as `\"` if you must use `exec`.
- **`pack` `targets` only for Tarot/Spectral.** Buffoon/Celestial/Standard packs don't need targets. The endpoint validates target count against the card's requirement and returns `BAD_REQUEST` if wrong.
- **Boss blinds hide card faces.** Cards with `state.hidden == true` return no rank/suit (shown as `??` in `glance`) — do not try to "read" them; decide based on what's visible.
- **`buy` / `reroll` affordability is `money - bankrupt_at`**, not raw `money` (Credit Card raises `bankrupt_at`). `glance` shows `[ok]` / `[need $N]` on shop rows; if a buy still fails with `BAD_REQUEST`, slots may be full or cost changed after reroll.
- **Joker/consumable slots can be full.** `buy` returns `BAD_REQUEST` when slots are full — `sell` something first or skip.
- **`skip` only works on Small/Big blinds**, not boss. Skip collects a tag reward (see §2 tag semantics).
- **Connection failure ≠ bug.** During state transitions the server may briefly not respond. Retry `glance` once before investigating.
- **Error names:** `INTERNAL_ERROR` (Lua crash), `BAD_REQUEST` (bad params), `INVALID_STATE` (wrong state), `NOT_ALLOWED` (game rules blocked it). Read `error.message` — it's specific.

## 5. Decision Principles

- **Always `glance` (and ideally `know preflight`) before deciding.** Never assume the state.
- **`bot.ps1 estimate` is optional and not recommended for normal play.** It only models a subset of jokers, may miss locale-specific effect text, and can make agents over-trust a number. Prefer reading the hand + `query hands` + `know check rule scoring_formula` when you need score math. Use `estimate` mainly for dev/regression (`tools/play/estimate_registry.md`), not as the default decision loop.
- **If you do run `estimate`, only in `SELECTING_HAND`.** It returns `INVALID_STATE` elsewhere. Output is a hint only: **`idx`** = full `bot.ps1 play` list when kickers matter (e.g. Blackboard); **`scoring=`** = poker scorers only. **`unmodeled`** jokers mean the true score can be higher — never treat `[BEATS]` as guaranteed.
- **Scoring math (default path):** Run `bot.ps1 query hands` for real base `chips`/`mult`. Apply `bot.ps1 know check rule scoring_formula`: score = Chips × Mult, built in phases (hand base → scoring-card chips → jokers left-to-right, +Mult before ×Mult). **Only the cards forming the poker hand type score — kickers add no chips** (`know check rule kickers_do_not_score`); card chips are A=11, 2-10=face, J/Q/K=10 (`know check rule card_chip_values`). (Example: Three of a Kind is base 30/3 + 3×scoring rank chips, not all five cards.) `know list rule` lists all rules; relevant ones: `scoring_formula`, `kickers_do_not_score`, `card_chip_values`, `hand_base_values_level_1`, `additive_before_multiplicative_mult`, `edition_values`, `enhancement_scoring`, `seal_effects`, `plasma_deck_balances_chips_and_mult`.
- **Beat the blind target, not maximize score.** `round.chips` is your current score; the current blind's `score` is the target. Once you've passed it, you can stop playing hands to bank unused hands ($1 each) and discards.
- **Don't burn discards for no reason.** Each unused hand pays $1 interest at round end (interest capped at $5). Discard only to improve a hand you intend to play.
- **Economy early, scaling late.** In early antes, money compounds. Don't reroll aggressively. Buy jokers that scale (Mult+) or generate economy.
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

## 6. Useful Queries

- `bot.ps1 glance` — compact state summary (state, blinds, round, hand with modifier tags, jokers w/ slot count, `actions:` line). Use this constantly.
- `bot.ps1 query hands` — poker hand level table with real `chips`/`mult` per hand type (table by default; `--json` for raw). **Primary tool for scoring math.**
- `bot.ps1 estimate` — *(optional, not recommended)* top playable hands + partial score model. Dev/regression helper only; see `tools/play/estimate_registry.md`.
- `bot.ps1 state` — full JSON envelope (gamestate + actions + queries).
- `bot.ps1 query deck` / `query blinds` / `query used_vouchers` / `query seed` — other Layer-2 queries.
- `bot.ps1 know preflight` — verified effects of all active jokers + current boss + pending tags (table by default; `--json` for raw).
- `bot.ps1 know check joker "Name"` / `check boss "Name"` / `check tag "Name"` — look up one entry.
- `screenshot PATH` / `save PATH` / `load PATH` — visual debug and run checkpoints (`bot.ps1 screenshot C:\tmp\ss.png`).

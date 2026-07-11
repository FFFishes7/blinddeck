# Playing Balatro with BlindDeck — Play Sheet for AI Agents

You are the player. Read **§1–§6** top to bottom before your first move, then **`glance` → one action → read summary** each turn. The game serves JSON-RPC 2.0 on `http://127.0.0.1:12346`.

| If you are…           | Start here                                                   |
| --------------------- | ------------------------------------------------------------ |
| **Playing a run**     | **§1–§6 below** (Appendix only when stuck)                   |
| **Scripting the API** | [docs/api.md](docs/api.md), `bot.ps1 state --json`           |
| **Changing the mod**  | [AGENTS.md](AGENTS.md), [docs/OVERVIEW.md](docs/OVERVIEW.md) |

Install / launch: [README.md](README.md). Recommended: `serve.ps1 --fast --audio` (sound on). Glance field details: [tools/play/README.md](tools/play/README.md#what-glance-shows).

---

## 1. What you are doing

- Read live state from **`bot.ps1 glance`** (compact summary + **`actions:`** line).
- Reason each turn; send **one friendly subcommand** per request.
- Card facts: **`know`** / **`query`** — or the scoring rules in **§3** for hand math.
- **`estimate` is optional and not recommended** for normal play (dev/regression only).

---

## 2. Loop and hard rules

```
repeat:
  bot.ps1 glance
  # optional: know preflight @ BLIND_SELECT / skip
  bot.ps1 <one action>        → read new summary (includes next actions:)
until GAME_OVER → menu → start DECK STAKE SEED   # SEED from summary restart hint
```

**Hard rules**

- Indices are **0-based** (first card is `0`).
- **One request at a time** — the server is single-client.
- Read **`actions:`** when unsure what to do next.
- **Never** `bot.ps1 exec '{"command":...}'` — PowerShell strips quotes; use friendly subcommands.
- Transient states (`HAND_PLAYED`, …): **`glance`** again until stable.

**Before `SELECTING_HAND` decisions, read §3.**

**Optional — `know preflight` (not every hand):** at **`BLIND_SELECT`**, or when weighing **`skip`**. Prints a verified-facts table (wiki JSON); **`glance` already has game effect text** on joker/blind lines — preflight batches the knowledge-base lookup.

| Phase                                           | Rows in preflight table                                            |
| ----------------------------------------------- | ------------------------------------------------------------------ |
| `MENU` / transient (`HAND_PLAYED`, …)           | *(empty — no output)*                                              |
| `BLIND_SELECT`                                  | deck · stake · owned jokers · owned consumables · boss · skip tags |
| `SELECTING_HAND` / `SHOP` / pack / `ROUND_EVAL` | deck · stake · owned jokers · owned consumables · boss             |
| `GAME_OVER`                                     | deck · stake only                                                  |

In Challenge Mode, preflight identifies and verifies the active challenge, then omits the normal deck/stake context and rows; at `GAME_OVER` it remains empty because no other facts apply. Use `know challenge ID_OR_NAME` for its full static setup, rules, restrictions, and Wiki link.

---

## 3. Scoring essentials

Final score = **Chips × Mult**, built **left to right**:

1. **Hand type base** — from the hand’s current level (`bot.ps1 query hands`; level-1 examples: Pair 10/2, Three of a Kind 30/3, Flush 35/4).
2. **Scoring cards only** — Balatro picks the best poker hand among played cards; **kickers add nothing** (no chips, no on-score effects). Exception: **Splash**.
3. **Per scoring card** — rank chips (**A=11**, **2–10 face**, **J/Q/K=10**) + enhancement / edition / seal when that card scores.
4. **Jokers left → right** — each adds +Chips, +Mult, or **×Mult** to the running totals.

**Played-card order:** the indices in `play I J K …` are both the selected
cards and their left-to-right scoring order. For example, `play 4 1 3` scores
hand cards `[4]` → `[1]` → `[3]`. Put an earlier trigger first by ordering the
arguments; `rearrange` cannot rearrange hand cards. Kickers do not score, so
their position normally has no scoring effect (except with Splash or another
effect that makes them score).

Played-card order matters for effects such as Photograph (the first scoring
face card), Hanging Chad (the first scoring card), and each scoring card's
enhancement, edition, and seal. With base Mult 4, a Mult Card before a Glass
Card gives `(4+4)×2=16` Mult; Glass before Mult gives `4×2+4=12`.

When using the optional `estimate` helper, treat its `idx=[…]` result as an
ordered command, not a set: pass the indices to `play` unchanged. The estimator
searches card order and may intentionally recommend a non-sorted sequence such
as `play 0 3 2 1 4`.

**Order rule:** stack **+Mult before ×Mult** — put +Mult jokers (and +Mult cards/editions) **left** of ×Mult jokers and ×Mult editions (Ramen, Polychrome, …). Joker slot order matters (`rearrange jokers`).

Example (40 chips, base mult 4, +4 Mult joker + ×2 Ramen): joker **left** of Ramen → 40×((4+4)×2)=**640**; reversed → 40×((4×2)+4)=**480**.

**Kicker trap (#1 estimate mistake):** Three Kings + two kickers scores **only the three Kings’ chips** plus the Three-of-a-Kind base — **not** all five cards.

**Held in hand:** **Steel** = ×1.5 Mult while held — **do not play** Steel for scoring. Baron, Raised Fist, and Gold enhancement also use cards left in hand. (Glass cards, by contrast, score when **played** — they are not held-mult.)

More rules: `know check rule scoring_formula` · `know list rules`

---

## 4. State → command

### Quick reference

The primary command for each state. Full syntax and index rules below.

| State                  | Primary command                                                            |
| ---------------------- | -------------------------------------------------------------------------- |
| `MENU`                 | `start DECK STAKE [SEED]` · `challenges` → `challenge ID` (or `load PATH`) |
| `BLIND_SELECT`         | `select` · `skip` (Small/Big) · `reroll_boss` (Boss, $10)                  |
| `SELECTING_HAND`       | `play N…` · `discard N…` · `use 0 [1 2]` · `sort rank`                     |
| `ROUND_EVAL`           | `cash_out` (or `endless` / `menu` if `victory_overlay`)                    |
| `SHOP`                 | `buy card\|voucher\|pack N` · `reroll` · `next_round`                      |
| `SMODS_BOOSTER_OPENED` | `pack N [hand…]` while `choices remaining: N > 0` · `pack skip`            |
| `GAME_OVER`            | `menu` → then `start DECK STAKE SEED`                                      |

### Common syntax (wherever the items exist)

**Indices are 0-based and per-area.** `hand:`, `jokers:`, `consumables:` each have their own `[N]` lists. `hand [N]` is for `play` / `discard` / `use` targets / `pack` targets. `jokers [N]` is for `sell` / `rearrange`. `consumables [N]` is for `sell` only. They do **not** cross over (`sell joker 0` ≠ `sell consumable 0`).

| Action    | Syntax                               | Notes                                                                                                                                                                              |
| --------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Play      | `play I J K …`                       | Hand indices are also the left-to-right scoring order: `play 4 1 3` scores `[4]` → `[1]` → `[3]`.                                                                                  |
| Sell      | `sell joker N` / `sell consumable N` | Type keyword required (not `sell 0` alone).                                                                                                                                        |
| Use       | `use 0 1 2`                          | Consumable `[0]` from `consumables:` + hand targets `[1]` `[2]` from `hand:`. Death same form (2 targets; first target = source (transformed), second target = template (copied)). |
| Rearrange | `rearrange jokers I J K …`           | Jokers only: **full** new left-to-right order, every index once. e.g. `rearrange jokers 1 0` puts former `[1]` left of former `[0]`. Cannot rearrange hand cards. Needs ≥2 jokers. |
| Sort      | `sort rank`                          | Changes hand display order for reading/selecting indices; it does not set play order. Modes: `rank` / `rank-desc` / `rank-asc` / `suit` / `suit-desc` / `suit-asc`.                |
| Save      | `save PATH`                          | Any in-run state (not `MENU`). e.g. `save run.jkr`. Prints `save success: PATH`; relative paths are automatically resolved into this project's `saves/` folder.                    |

**Where each inventory action is allowed:**

| Action      | Allowed states                                                      |
| ----------- | ------------------------------------------------------------------- |
| `sell`      | `BLIND_SELECT` · `SELECTING_HAND` · `SHOP` · `SMODS_BOOSTER_OPENED` |
| `use`       | `BLIND_SELECT` · `SELECTING_HAND` · `SHOP` · `SMODS_BOOSTER_OPENED` |
| `rearrange` | `SELECTING_HAND` · `SHOP` · `SMODS_BOOSTER_OPENED`                  |
| `sort`      | `SELECTING_HAND`                                                    |

### Per-state details

- **`MENU`** — start a normal run with `start DECK STAKE [SEED]`. For Challenge
    Mode, run `challenges`, then `challenge ID`; its deck, rules, and White Stake
    are fixed. Use `load PATH` only when offered in `actions:`.
- **`BLIND_SELECT`** — `select`, `skip` (Small/Big only), or `reroll_boss`
    (eligible Boss, $10). Inventory permits `sell` and `use`; saving is allowed.
- **`SELECTING_HAND`** — `play N…`, `discard N…`, `sort rank`, or
    `use 0 [targets…]`. Use `query hands` plus §3 for scoring; `estimate` is
    development-only.
- **`ROUND_EVAL`** — normally `cash_out` after reading `pending:`. With
    `victory_overlay`, only `endless` or `menu` is allowed.
- **`SHOP`** — buy, reroll, manage inventory, or `next_round`; saving is
    allowed.
- **`SMODS_BOOSTER_OPENED`** — use `pack N [targets…]` while
    `choices remaining > 0`; `pack skip` forfeits all remaining picks. Targets
    are `hand:` indices. Ankh, Hex, and Ectoplasm ignore targets.
- **`GAME_OVER`** — `menu`, then restart from the summary hint. Saving is
    allowed.
- **Transient states** (`HAND_PLAYED`, `DRAW_TO_HAND`, `NEW_ROUND`, …) — no
    play commands; `glance` until stable.

### Save / load / screenshot (not in `actions:`)

| Command           | When                                                | Notes                                                                                                                            |
| ----------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `save PATH`       | Active run (rows above; not `MENU`)                 | e.g. `save run.jkr`; prints `save success: PATH`; relative paths are automatically resolved into this project's `saves/` folder. |
| `load PATH`       | `MENU` (also in `actions:` when a save is detected) | Continue instead of `start`                                                                                                      |
| `screenshot PATH` | When the API allows                                 | Utility; e.g. `screenshot shot.png`                                                                                              |

---

## 5. Read glance

Every summary ends with **`actions:`** containing command names, not complete
arguments. Use §4 or `bot.ps1 help --now` for valid examples; scripting clients
can read `state --json` → `actions[].example`.

Per-state line meanings: [tools/play/README.md § What glance shows](tools/play/README.md#what-glance-shows).

**Hand line:** `[N] rank+suit[tags]` — **`[N]`** is the index for `play`, `discard`, `use` targets, and pack targets. Cerulean Bell forced cards show `[forced]`; ordinary highlighted cards show `[selected]`.

**Jokers / consumables:** each has its own **0-based `[N]`**, separate from `hand:`.

**Modifier tags on hand cards:**

| Prefix | Meaning                                                                    |
| ------ | -------------------------------------------------------------------------- |
| `e:`   | Enhancement — `Mult` `Bonus` `Glass` `Stone` `Wild` `Lucky` `Gold` `Steel` |
| `d:`   | Edition — `Foil` `Holo` `Poly` `Neg`                                       |
| `s:`   | Seal — `Red` `Blue` `Gold` `Purple`                                        |

**Enhancements:**

| Tag       | Effect                                 | Trigger / decision rule                        |
| --------- | -------------------------------------- | ---------------------------------------------- |
| `e:Mult`  | +4 Mult                                | When this card scores                          |
| `e:Bonus` | +30 Chips                              | When this card scores                          |
| `e:Glass` | ×2 Mult; 1 in 4 chance to be destroyed | When this card scores                          |
| `e:Stone` | +50 Chips; no rank or suit             | Always scores when played                      |
| `e:Wild`  | Counts as every suit                   | Rank is unchanged                              |
| `e:Lucky` | 1 in 5: +20 Mult; 1 in 15: +$20        | Independent random rolls when this card scores |
| `e:Gold`  | +$3                                    | Keep in hand through the end of the round      |
| `e:Steel` | ×1.5 Mult                              | Keep in hand while another card/hand scores    |

**Editions:** playing-card editions apply when that card scores; Joker editions
apply during the Joker phase.

| Tag      | Effect    | Note                                       |
| -------- | --------- | ------------------------------------------ |
| `d:Foil` | +50 Chips | Additive Chips                             |
| `d:Holo` | +10 Mult  | Additive Mult                              |
| `d:Poly` | ×1.5 Mult | Multiplicative; order matters              |
| `d:Neg`  | +1 slot   | Passive capacity, not a scoring multiplier |

**Seals:**

| Tag        | Effect                                       | Trigger / requirement                     |
| ---------- | -------------------------------------------- | ----------------------------------------- |
| `s:Red`    | Retriggers the card once                     | When its scoring or held effect triggers  |
| `s:Blue`   | Creates the Planet for the final played hand | Held at round end; needs consumable space |
| `s:Gold`   | +$3                                          | When this card scores                     |
| `s:Purple` | Creates a Tarot                              | When discarded; needs consumable space    |

**Joker stickers / state:**

| Glance text        | Meaning                                               |
| ------------------ | ----------------------------------------------------- |
| `rental -$N/round` | Pay the displayed fee at the end of every round       |
| `perishable Nr`    | Becomes debuffed after the displayed number of rounds |
| `eternal`          | Cannot be sold or destroyed                           |
| `pinned leftmost`  | Forced to remain in the leftmost Joker position       |

Debuffed cards are shown in parentheses, such as `(7♣)`: their enhancement,
edition, seal, and most other abilities do not trigger; debuffed Wild cards use
their printed suit. Source-backed lifecycle warnings such as Mr. Bones
`(self-destructs on save)` appear with the Joker stickers.

**Shop / buy:** rows show `[ok]` / `[need $N]` / `[slots full]` from `money - bankrupt_at`.

**When to use `know` / `query`**

| Need                            | Command                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------- |
| Hand levels / base chips & mult | `query hands`                                                                   |
| Boss blind                      | `know preflight` or `know check boss "Name"`                                    |
| Unfamiliar joker                | `know check joker "Name"`                                                       |
| Skip or held tag                | `tag_effect` on blind line, or `know check tag "Name"`                          |
| Full rule list                  | `know list rules`                                                               |
| Scripting / JSON                | `state --json`, `query … --json` — [tools/play/README.md](tools/play/README.md) |

---

## 6. Pitfalls

- **Played-card order comes from `play` arguments:** `play 4 1 3` scores
    `[4]` → `[1]` → `[3]`. `rearrange` is jokers-only, and `sort` only changes
    the displayed hand order; neither is an arbitrary hand-rearrangement command.
- Boss blinds hide card faces (`??`).
- **Tags on blind lines** = reward for **`skip`** only (not defeating the blind). **`held tags (pending):`** = already earned, not yet triggered.
- **`pack skip`** is not “advance to next blind”.
- **Ankh / Hex / Ectoplasm:** random joker — to keep one joker, **sell every other joker first** (`sell joker N` per slot) so only the keeper remains.
- Joker/consumable slots full → **`sell joker|consumable`** first
- **`pack` target count** must match the card or you get `BAD_REQUEST`.
- **`reroll_boss`:** Boss `BLIND_SELECT` only; $10; unrelated to shop `reroll`.
- **`won` on `GAME_OVER`** means you beat Ante 8 Boss (can stay true in endless). Read **`run_summary.result`** for the actual outcome.
- Connection blip during transitions → retry `glance` once.
- Errors: `BAD_REQUEST`, `INVALID_STATE`, `NOT_ALLOWED`, `INTERNAL_ERROR` — read `error.message`.

---

## Appendix (on demand)

Open only when the play sheet is not enough.

### Prerequisites

- Balatro with this mod on `http://127.0.0.1:12346`. Health-check:

```powershell
.\tools\play\bot.ps1 health
```

**If health fails:** wait 30–60s after launch; kill zombie `balatrobot` processes; restart `.\tools\play\serve.ps1 --fast --audio`; try `--port 12347` if busy. Do not “fix” game state — restart the server only. Details: [README.md](README.md).

### Minimal trace

```powershell
.\tools\play\bot.ps1 glance
.\tools\play\bot.ps1 start RED WHITE
.\tools\play\bot.ps1 select
.\tools\play\bot.ps1 play 0 1 2 3 4
.\tools\play\bot.ps1 cash_out
.\tools\play\bot.ps1 buy card 0
.\tools\play\bot.ps1 next_round
```

Each action prints the new summary + `actions:` — you rarely need a separate `glance` between actions.

### Further commands

Full **`query` / `know` / `state`** table, friendly subcommand notes, and debug `add` / `set` / `debuff` (`BALATROBOT_ALLOW_CHEATS=1`): [tools/play/README.md](tools/play/README.md).

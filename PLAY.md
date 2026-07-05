# Playing Balatro with BlindDeck — Play Sheet for AI Agents

You are the player. Read **§1–§6** top to bottom before your first move, then **`glance` → one action → read summary** each turn. The game serves JSON-RPC 2.0 on `http://127.0.0.1:12346`.

| If you are…           | Start here                                                   |
| --------------------- | ------------------------------------------------------------ |
| **Playing a run**     | **§1–§6 below** (Appendix only when stuck)                   |
| **Scripting the API** | [docs/api.md](docs/api.md), `bot.ps1 state --json`           |
| **Changing the mod**  | [AGENTS.md](AGENTS.md), [docs/OVERVIEW.md](docs/OVERVIEW.md) |

Install / launch: [README.md](README.md). **Glance field details:** [tools/play/README.md](tools/play/README.md#what-glance-shows).

---

## 1. What you are doing

- Read live state from **`bot.ps1 glance`** (compact summary + **`actions:`** line).
- Reason each turn; send **one friendly subcommand** per request.
- Balatro card facts: **`know`** / **`query`** — or the scoring rules in **§3** for hand math.
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

Does **not** include shop cards or `held tags` — read **`glance`** for those.

---

## 3. Scoring essentials

Final score = **Chips × Mult**, built **left to right**:

1. **Hand type base** — from the hand’s current level (`bot.ps1 query hands`; level-1 examples: Pair 10/2, Three of a Kind 30/3, Flush 35/4).
2. **Scoring cards only** — Balatro picks the best poker hand among played cards; **kickers add nothing** (no chips, no on-score effects). Exception: **Splash**.
3. **Per scoring card** — rank chips (**A=11**, **2–10 face**, **J/Q/K=10**) + enhancement / edition / seal when that card scores.
4. **Jokers left → right** — each adds +Chips, +Mult, or **×Mult** to the running totals.

**Order rule:** stack **+Mult before ×Mult** — put +Mult jokers (and +Mult cards) **left** of ×Mult jokers (Ramen, Polychrome, Glass, …). Joker slot order matters (`rearrange jokers`).

Example (40 chips, base mult 4, +4 Mult joker + ×2 Ramen): joker **left** of Ramen → 40×((4+4)×2)=**640**; reversed → 40×((4×2)+4)=**480**.

**Kicker trap (#1 estimate mistake):** Three Kings + two kickers scores **only the three Kings’ chips** plus the Three-of-a-Kind base — **not** all five cards.

**Held in hand:** **Steel** = ×1.5 Mult while held — **do not play** Steel for scoring. Baron, Raised Fist, and Gold enhancement also use cards left in hand.

More rules: `know check rule scoring_formula` · `know list rules`

---

## 4. State → command

| State                  | Command                                                                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `MENU`                 | `start DECK STAKE [SEED]` — deck/stake lists in `glance`                                                            |
| `BLIND_SELECT`         | `select` · `skip` (Small/Big only) · `reroll_boss` (Boss, $10, Director's Cut / Retcon)                             |
| `SELECTING_HAND`       | `play …` · `discard …` · `use …` · `death …` · `sort rank` — repeat until summary shows **`beaten`**, then `glance` |
| `ROUND_EVAL`           | See bullets below                                                                                                   |
| `SHOP`                 | `buy card\|pack …` · `reroll` · `sell …` · `rearrange jokers\|consumables …` · `next_round`                         |
| `SMODS_BOOSTER_OPENED` | See bullets below                                                                                                   |
| `GAME_OVER`            | `menu` then `start DECK STAKE SEED` (seed in summary restart hint)                                                  |

**`ROUND_EVAL`**

- Read **`pending:`** rows and **`total +$N`** before cashing out.
- If **`victory_overlay`**: `endless` or `menu` first — **not** `cash_out` until dismissed.
- Otherwise: `cash_out`.

**`SMODS_BOOSTER_OPENED`**

- While **`choices remaining: N` > 0**: `pack IDX [hand indices…]` or `pack skip` (forfeit remaining picks — not “next blind”).
- **`pack` targets** = **0-based hand `[N]`** from the `hand:` line (not rank values).
- Tarot/Spectral only for targets; **Ankh / Hex / Ectoplasm** = random joker (targets ignored).
- Booster choices are **free picks** — not shop prices.

**Scoring a hand:** `query hands` + mental math from **§3**.

---

## 5. Read glance

Every summary ends with **`actions:`**. Per-state line meanings: [tools/play/README.md § What glance shows](tools/play/README.md#what-glance-shows).

**Hand line:** `[N] rank+suit[tags]` — **`[N]`** is the index for `play`, `discard`, `use`, and pack targets.

| Prefix | Meaning                                                                    |
| ------ | -------------------------------------------------------------------------- |
| `e:`   | Enhancement — `Mult` `Bonus` `Glass` `Stone` `Wild` `Lucky` `Gold` `Steel` |
| `d:`   | Edition — `Foil` `Holo` `Poly` `Neg`                                       |
| `s:`   | Seal — `Red` `Blue` `Gold` `Purple`                                        |

`e:Wild` = all **suits**, rank unchanged (not all ranks). Debuffed cards: `(7♣)`. Joker stickers `(rental …)` / `(perishable …)` are on joker lines, not hand cards.

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

- Boss blinds hide card faces (`??`).
- **Tags on blind lines** = reward for **`skip`** only (not defeating the blind). **`held tags (pending):`** = already earned, not yet triggered.
- **`pack skip`** is not “advance to next blind”.
- **Ankh / Hex / Ectoplasm:** random joker — to keep one joker, **sell every other joker first** so only the keeper remains.
- **`rearrange jokers`** changes scoring order only — not consumable/pack targeting.
- Joker/consumable slots full → **`sell`** first; **`pack` target count** must match the card or you get `BAD_REQUEST`.
- **`skip` only on Small/Big.** Some tags open a pack immediately after skip → `SMODS_BOOSTER_OPENED`; Double Tag can mean **two packs back-to-back** — read summary after each `pack`.
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
.\.venv\Scripts\python.exe -c "import httpx;print(httpx.post('http://127.0.0.1:12346/',json={'jsonrpc':'2.0','method':'health','params':{},'id':1},timeout=3).text)"
```

**If health fails:** wait 30–60s after launch; kill zombie `balatrobot` processes; restart `.\tools\play\serve.ps1 --fast --debug`; try `--port 12347` if busy. Do not “fix” game state — restart the server only. Details: [README.md](README.md).

### Command cheatsheet

- `start DECK STAKE [SEED]` · `play` / `discard` (max 5) · `buy card|voucher|pack IDX`
- `pack IDX [TARGETS…]` · `use CONSUMABLE [CARDS…]` · `death CONSUMABLE SOURCE TARGET` (Spectral Death) · `sort rank` / `suit` / …
- `sell joker|consumable IDX` · `rearrange hand|jokers|consumables ORDER`
- Debug (not normal play; `$env:BALATROBOT_ALLOW_CHEATS=1`): `add` · `set` · `debuff` — [tools/play/README.md](tools/play/README.md#debug-add--set-estimate-testing-only)

### Tag edge cases

- **`blinds.{small,big}.tag_name`** = skip reward if you **`skip`** that blind. Boss has no tag.
- Pack-on-skip tags → `SMODS_BOOSTER_OPENED` immediately; check **`choices remaining: N`** after each pick.

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

Full **`query` / `know` / `state`** table and friendly subcommand notes: [tools/play/README.md](tools/play/README.md).

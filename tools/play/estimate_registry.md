# Estimate joker registry

`bot.ps1 estimate` only models **deterministic** scoring: given the cards you choose to
play, the result must be uniquely fixed by the current gamestate. Anything involving
RNG, hidden future state, or unread dynamic values stays **`unmodeled`**.

**Source of truth for mechanics:** Balatro decompiled Lua under  
`%APPDATA%\Balatro\Mods\lovely\game-dump\` (vanilla + lovely patches) and SMODS under  
`%APPDATA%\Balatro\Mods\smods\src\`.

When adding a joker, read its `eval_card` branch in `card.lua` first, then port only if
the condition uses state we already expose in `gamestate`.

**Agents:** follow [Modeling checklist (required)](#modeling-checklist-required) below —
no ad-hoc ports. Cursor rule: `.cursor/rules/estimate-maintenance.mdc` (local).

---

## Modeling checklist (required)

Use this checklist for **every** new or changed joker in `estimate.py`. Do not skip steps.

### 0. Gate — deterministic only?

- [ ] Read the joker in `%APPDATA%\Balatro\Mods\lovely\game-dump\card.lua` (`eval_card`).
- [ ] Confirm **no** `pseudorandom`, `pseudorandom_probability`, or hidden proc.
- [ ] Confirm all inputs exist in our `gamestate` (or derived from visible hand + round counters).

If any check fails → add to **Never model** below; leave `unmodeled`; **stop** (no estimate code).

### 1. Source — where does it fire?

- [ ] Note **context**: `main_scoring` (per scoring card), `joker_main` (global phase), or `repetition` (Dusk/Seltzer/…).
- [ ] Trace call path: `state_events.lua` `evaluate_play` → `SMODS.calculate_main_scoring` / joker loop (`smods/src/utils.lua`).
- [ ] Note **phase**: +Mult vs ×Mult; held-card jokers use **`G.hand.cards`** (unplayed cards only).

### 2. Implement

- [ ] Add logic in `tools/play/estimate.py` (`PER_CARD_JOKERS`, `_global_joker_bonus`, `_retrigger_config`, or `NO_SCORE_JOKERS`).
- [ ] Register key in `_modeled()` or it stays `unmodeled`.
- [ ] If kicker choice matters (Blackboard): enumerate play sizes; **`indices`** = full `bot.ps1 play` list.

### 3. Test

- [ ] Unit test in `tests/cli/test_play_helpers.py` (`pytest tests/cli/test_play_helpers.py -k estimate`).
- [ ] Live check when possible: `$env:BALATROBOT_ALLOW_CHEATS=1` → `estimate` → `play` **same `idx`** → score must match.

### 4. Document (same change set)

- [ ] Move joker to **Verified & modeled** (or **Never model**) in this file.
- [ ] Append row to **Live validation log** if live-tested.
- [ ] Update `tools/play/README.md` / `PLAY.md` only if CLI output or user workflow changed.

---

## Scoring architecture (where the algorithm lives)

There is no single `score.lua`. Scoring is a **pipeline** split across vanilla + SMODS:

| Layer | File | Role |
| --- | --- | --- |
| **Orchestrator** | `game-dump/functions/state_events.lua` | `G.FUNCS.evaluate_play` — full hand scoring sequence; calls everything below |
| **Play trigger** | same file (~L491) | `ease_hands_played(-1)` then move cards to `G.play`, then `evaluate_play()` |
| **Hand type** | `smods/src/overrides.lua` | `G.FUNCS.get_poker_hand_info`, `evaluate_poker_hand` — which cards score |
| **Effect dispatch** | `game-dump/functions/common_events.lua` | `eval_card(card, context)` — routes to joker/enhancement/seal/edition logic |
| **Joker rules** | `game-dump/card.lua` | Per-joker `if self.ability.name == …` returning `mult_mod`, `Xmult_mod`, `repetitions` |
| **Scoring engine** | `smods/src/utils.lua` | **`SMODS.calculate_main_scoring`** → **`SMODS.score_card`** (per card + retriggers) → **`SMODS.trigger_effects`** (apply mods to running totals) |
| **Running totals** | `smods/src/game_object.lua` | **`SMODS.Scoring_Parameters`** — accumulators for `chips` and `mult` (`modify()`) |
| **Final formula** | same file | **`SMODS.Scoring_Calculation`**: default `multiply` → `chips * mult`; Plasma uses `add` |
| **Hand score readout** | `smods/src/utils.lua` | **`SMODS.calculate_round_score()`** — applies current `Scoring_Calculation:func(chips, mult)` |
| **Boss debuff** | `game-dump/blind.lua` | `Blind:modify_hand` (e.g. The Flint halves base before card phase) |
| **Clamp helpers** | `game-dump/functions/misc_functions.lua` | `mod_chips`, `mod_mult` |

**Typical `evaluate_play` order** (see `state_events.lua` ~L586–790):

1. Classify hand → set base `hand_chips` / `mult` from `G.GAME.hands[handname]`
2. `Blind:modify_hand` (Flint, etc.)
3. **`SMODS.calculate_main_scoring`** — loop **scoring** cards in `G.play`; each card via `score_card` → `eval_card` → per-card jokers → **`SMODS.calculate_repetitions`** (Dusk, Seltzer, Red Seal, Hanging Chad)
4. **Joker main phase** — loop jokers with `joker_main` context (Blackboard reads **`G.hand.cards`**, not played cards)
5. `final_scoring_step` (deck back, e.g. Plasma balance)
6. **`SMODS.calculate_round_score()`** → add to `G.GAME.chips`

Our `estimate.py` mirrors steps 1–5 in simplified closed form; step 6 is the printed `score`.

---

## Deterministic principle

| Include | Exclude |
| --- | --- |
| Hand levels, card rank chips, enhancement / edition / seal | `pseudorandom` / probability procs |
| Jokers whose effect depends only on visible hand, jokers, round counters | Effects that depend on cards not yet drawn |
| Boss debuffs when blind name is known (e.g. The Flint) | Jokers whose runtime value is missing from API |
| Kickers that change **held** cards (e.g. Blackboard) — search all play sizes | “Expected value” of random outcomes |

If a modeled joker is present but its dynamic value cannot be read (e.g. Swashbuckler
without `当前为+Nm` in effect text), treat as **unmodeled** for that run.

---

## Verified & modeled

Cross-checked against `game-dump/card.lua` and/or live `play` validation.

| Key | Effect (summary) | Source notes |
| --- | --- | --- |
| `j_joker` | +4 Mult | `joker_main` |
| `j_abstract` | +3 Mult per Joker (`#G.jokers.cards` with `set == 'Joker'`) | Counts all jokers in slots |
| `j_mystic_summit` | +15 Mult when `discards_left == 0` | `d_remaining = 0` in config |
| `j_blackboard` | ×3 Mult when **all cards in `G.hand`** are Spades or Clubs | Unplayed cards only; kicker plays matter |
| `j_swashbuckler` | +Mult = sum of other jokers' sell values | Uses `value.effect` `当前为+Nm` from gamestate |
| `j_blue_joker` | +2 chips × deck remaining | Uses `cards.count` |
| `j_dusk` | +1 retrigger on every **played** card when last hand | Game checks `hands_left == 0` **during** scoring (after `ease_hands_played(-1)`); API shows `hands_left == 1` before you play → same hand |
| `j_seltzer` | +1 retrigger all played cards while countdown > 0 | Parsed from effect digits |
| `j_hanging_chad` | +2 retriggers on leftmost scoring card | |
| `j_splash` | All played cards score | |
| `j_greedy_joker` / `j_lusty_joker` / `j_wrathful_joker` / `j_gluttenous_joker` | +3 Mult per matching suit in scoring cards | Per-card |
| `j_walkie_talkie` | +10 chips, +4 Mult on 10/4 | Per-card |
| `j_fibonacci` | +8 Mult on A/2/3/5/8 | Per-card |
| `j_even_steven` / `j_odd_todd` | +4 Mult on even / +31 chips on odd ranks | Per-card |
| `j_onyx_agate` | +7 Mult per club scored | Per-card |
| `j_flower_pot` | ×3 Mult if scoring hand has all four suits | Global |
| `j_family` | ×4 Mult on Four of a Kind | Global |

**Output fields**

- `indices` — full list for `bot.ps1 play` (includes kickers when they improve a modeled effect).
- `scoring_indices` / `scoring_cards` — poker hand scorers only (kickers do not add chip value).

---

## Verified no-op (economy / utility)

Modeled as zero score impact so they do **not** appear in `unmodeled_jokers`:

`j_midas_mask`, `j_delayed_grat`, `j_egg`, `j_gift`, `j_golden`, `j_flash`, `j_faceless`,
`j_cartomancer`, `j_certificate`, `j_mail`, `j_ramen`, `j_ripple`, `j_hologram`,
`j_trading`, `j_riff_raff`, …

---

## Never model (RNG / hidden)

Do not add closed-form estimates — keep **`unmodeled`**:

| Key / name | Why |
| --- | --- |
| `j_misprint` | Random Mult each hand (`pseudorandom('misprint', min, max)`) |
| `j_8_ball` | Probability spawn Tarot |
| `j_bloodstone` | Probability ×Mult |
| `j_lucky_cat`, Lucky Card enhancements | Probability money / Mult |
| `j_wheel_of_fortune` | Random edition on joker |
| `j_space` | Chance to level up hand |
| `j_hack` | Retrigger 2–5 (deterministic per card rank — *could* be modeled later) |
| `j_cavendish`, `j_gros_michel` | Destruction RNG |
| Most “1 in N chance” jokers | Any `SMODS.pseudorandom_probability` path |

---

## TODO (deterministic, not yet ported)

Candidates worth adding when needed — all are deterministic once conditions are read from state:

| Key | Blocker / notes |
| --- | --- |
| `j_steel_joker` | Needs steel-card tally from gamestate |
| `j_ceremonial` | Depends on blind-select sacrifice (past state) |
| `j_blackboard` wild cards | `is_suit(..., true)` — Wild counts as both; need wild flag in API |
| `j_driver's_license` | Needs modified-card count ≥ 16 |
| `j_campfire` | Scales on sold cards this run |
| `j_fortune_teller` | +Mult per Tarot used (`G.GAME.consumeable_usage`) |

---

## Scoring order (pipeline summary)

See **Scoring architecture** for file paths. Runtime order:

1. `ease_hands_played(-1)` — **before** `evaluate_play()`
2. Move highlighted cards `G.hand` → `G.play`
3. Hand base chips/mult (+ Flint debuff)
4. Per **scoring** card triggers (`SMODS.calculate_main_scoring` / `score_card`; retriggers via `calculate_repetitions`)
5. Joker main phase left-to-right (`joker_main`) — Blackboard reads **`G.hand.cards`**
6. Final scoring step / deck back effects / Plasma balance → **`SMODS.calculate_round_score()`**

Retriggers (Dusk, Seltzer, Red Seal, Hanging Chad) apply to **scoring** card loops in
game code; Dusk condition is `hands_left == 0` at evaluation time (= last hand from API).

---

## Live validation log

| Date | Scenario | Estimate | Actual | Notes |
| --- | --- | --- | --- | --- |
| 2026-07-04 | Straight + Abstract/Swashbuckler | 2618 | 2618 | ✓ |
| 2026-07-04 | Two Pair, play `[4,5,6,7]` only | 4950 (wrong idx) | 2178 | Fixed: need `[2,4,5,6,7]` for Blackboard kicker |
| 2026-07-04 | Two Pair, correct idx | 2442 | +2442 incremental | ✓ |
| 2026-07-04 | Needle, High Card `[0,5,7]` | 1863 `[short]` | Lost | Estimate correct; target 2000, need better line |

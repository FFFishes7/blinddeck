# Estimate joker registry

`bot.ps1 estimate` is an **optional, not recommended** play helper — incomplete joker
coverage; normal agents should use `query hands` + `know check rule scoring_formula`.
This file documents the **dev/regression** scoring model only.

**Source of truth for mechanics:** Balatro decompiled Lua under\
`%APPDATA%\Balatro\Mods\lovely\game-dump\` (vanilla + lovely patches) and SMODS under\
`%APPDATA%\Balatro\Mods\smods\src\`.

When adding a joker, read its `eval_card` branch in `card.lua` first, then port only if
the condition uses state we already expose in `gamestate`.

**Agents:** follow [Modeling checklist (required)](#modeling-checklist-required) below —
no ad-hoc ports. Cursor rule: `.cursor/rules/estimate-maintenance.mdc` (local).

---

## Modeling checklist (required)

Use this checklist for **every** new or changed joker in `estimate_jokers.py`. Do not skip steps.

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

- [ ] Add logic in `tools/play/estimate_jokers.py` (`PER_CARD_JOKERS`, `_global_joker_bonus`, `_retrigger_config`, or `NO_SCORE_JOKERS`).
- [ ] Register key in `_modeled()` or it stays `unmodeled`.
- [ ] If kicker choice matters (Blackboard): enumerate play sizes; **`indices`** = full `bot.ps1 play` list.

### 3. Test

- [ ] Unit test in `tests/cli/test_play_helpers.py` (`python -m pytest tests/cli/test_play_helpers.py -k estimate`).
- [ ] **Integration test** in `tests/lua/endpoints/test_estimate_live.py` — add a row to `tests/lua/endpoints/estimate_live_recipes.py` (`build_scoring_joker_recipes()`). Parametrized run: real gamestate → `estimate(state)` → `play` same `indices` → `round.chips` delta must equal `score`. Unit tests alone are self-referential and do not count as verification.
- [ ] Manual fallback when fixture cannot trigger the joker: `$env:BALATROBOT_ALLOW_CHEATS=1` → `estimate` → `play` **same `idx`** → log in live validation table.

### 4. Document (working tree)

- [ ] Move joker to **Verified & modeled** (or **Never model**) in this file.
- [ ] Append row to **Live validation log** if live-tested.
- [ ] Update `tools/play/README.md` / `PLAY.md` if CLI output or workflow changed.

Do **not** `git commit` / `git push` unless the user explicitly asks.

---

## Scoring architecture (where the algorithm lives)

There is no single `score.lua`. Scoring is a **pipeline** split across vanilla + SMODS:

| Layer                  | File                                     | Role                                                                                                                                             |
| ---------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Orchestrator**       | `game-dump/functions/state_events.lua`   | `G.FUNCS.evaluate_play` — full hand scoring sequence; calls everything below                                                                     |
| **Play trigger**       | same file (~L491)                        | `ease_hands_played(-1)` then move cards to `G.play`, then `evaluate_play()`                                                                      |
| **Hand type**          | `smods/src/overrides.lua`                | `G.FUNCS.get_poker_hand_info`, `evaluate_poker_hand` — which cards score                                                                         |
| **Effect dispatch**    | `game-dump/functions/common_events.lua`  | `eval_card(card, context)` — routes to joker/enhancement/seal/edition logic                                                                      |
| **Joker rules**        | `game-dump/card.lua`                     | Per-joker `if self.ability.name == …` returning `mult_mod`, `Xmult_mod`, `repetitions`                                                           |
| **Scoring engine**     | `smods/src/utils.lua`                    | **`SMODS.calculate_main_scoring`** → **`SMODS.score_card`** (per card + retriggers) → **`SMODS.trigger_effects`** (apply mods to running totals) |
| **Running totals**     | `smods/src/game_object.lua`              | **`SMODS.Scoring_Parameters`** — accumulators for `chips` and `mult` (`modify()`)                                                                |
| **Final formula**      | same file                                | **`SMODS.Scoring_Calculation`**: default `multiply` → `chips * mult`; Plasma uses `add`                                                          |
| **Hand score readout** | `smods/src/utils.lua`                    | **`SMODS.calculate_round_score()`** — applies current `Scoring_Calculation:func(chips, mult)`                                                    |
| **Boss debuff**        | `game-dump/blind.lua`                    | `Blind:modify_hand` (e.g. The Flint halves base before card phase)                                                                               |
| **Clamp helpers**      | `game-dump/functions/misc_functions.lua` | `mod_chips`, `mod_mult`                                                                                                                          |

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

| Include                                                                      | Exclude                                        |
| ---------------------------------------------------------------------------- | ---------------------------------------------- |
| Hand levels, card rank chips, enhancement / edition / seal                   | `pseudorandom` / probability procs             |
| Jokers whose effect depends only on visible hand, jokers, round counters     | Effects that depend on cards not yet drawn     |
| Boss debuffs when blind name is known (e.g. The Flint)                       | Jokers whose runtime value is missing from API |
| Kickers that change **held** cards (e.g. Blackboard) — search all play sizes | “Expected value” of random outcomes            |

If a modeled joker is present but its dynamic value cannot be read from
`value.stats` (preferred) or parseable `value.effect`, treat as **unmodeled** for
that run.

### API: `value.stats` on jokers (preferred)

`gamestate` jokers may include structured scoring fields under `value.stats`
(locale-independent, from `card.ability`):

| Field                                                    | Meaning                                          |
| -------------------------------------------------------- | ------------------------------------------------ |
| `mult`                                                   | Additive Mult in joker_main                      |
| `chips`                                                  | Additive chips in joker_main                     |
| `x_mult`                                                 | Multiplicative Mult in joker_main                |
| `seltzer_remaining`                                      | Seltzer countdown                                |
| `steel_tally` / `stone_tally` / `driver_tally`           | Deck tallies                                     |
| `loyalty_every` / `loyalty_remaining` / `loyalty_x_mult` | Loyalty Card countdown                           |
| `obelisk_step`                                           | Obelisk ×Mult increment per non-dominant hand    |
| `ride_the_bus_step`                                      | Ride the Bus +Mult per hand without scoring face |
| `green_hand_add`                                         | Green Joker +Mult increment per hand played      |
| `caino_xmult`                                            | Caino ×Mult (when > 1)                           |

Run-level counters live on `gamestate.run`: `skips`, `deck_size`,
`starting_deck_size`, `tarot_used`.

Round scoring targets on `gamestate.round`: `ancient_suit`, `idol_rank`, `idol_suit`, `castle_suit`.

`estimate.py` reads `stats` first; `value.effect` text parsing is fallback only.

---

## Verified & modeled

Cross-checked against `game-dump/card.lua` and/or live `play` validation.

| Key                                                                                                                                     | Effect (summary)                                                                                                                 | Source notes                                                                                                                              |
| --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `j_joker`                                                                                                                               | +4 Mult                                                                                                                          | `joker_main`                                                                                                                              |
| `j_abstract`                                                                                                                            | +3 Mult per Joker (`#G.jokers.cards` with `set == 'Joker'`)                                                                      | Counts all jokers in slots                                                                                                                |
| `j_mystic_summit`                                                                                                                       | +15 Mult when `discards_left == 0`                                                                                               | `d_remaining = 0` in config                                                                                                               |
| `j_blackboard`                                                                                                                          | ×3 Mult when **all cards in `G.hand`** are Spades or Clubs                                                                       | Unplayed cards only; Wild counts as ♠/♣; kicker plays matter                                                                              |
| `j_swashbuckler`                                                                                                                        | +Mult = sum of other jokers' sell values (`value.stats.mult`)                                                                    | Global; live `play` validated                                                                                                             |
| `j_blue_joker`                                                                                                                          | +2 chips × deck remaining                                                                                                        | Uses `cards.count`                                                                                                                        |
| `j_dusk`                                                                                                                                | +1 retrigger on every **played** card when last hand                                                                             | Game checks `hands_left == 0` **during** scoring (after `ease_hands_played(-1)`); API shows `hands_left == 1` before you play → same hand |
| `j_seltzer`                                                                                                                             | +1 retrigger all played cards while countdown > 0                                                                                | Parsed from effect digits                                                                                                                 |
| `j_hanging_chad`                                                                                                                        | +2 retriggers on leftmost scoring card                                                                                           |                                                                                                                                           |
| `j_splash`                                                                                                                              | All played cards score                                                                                                           |                                                                                                                                           |
| `j_greedy_joker` / `j_lusty_joker` / `j_wrathful_joker` / `j_gluttenous_joker`                                                          | +3 Mult per matching suit in scoring cards                                                                                       | Per-card                                                                                                                                  |
| `j_walkie_talkie`                                                                                                                       | +10 chips, +4 Mult on 10/4                                                                                                       | Per-card                                                                                                                                  |
| `j_fibonacci`                                                                                                                           | +8 Mult on A/2/3/5/8                                                                                                             | Per-card                                                                                                                                  |
| `j_even_steven` / `j_odd_todd`                                                                                                          | +4 Mult on even / +31 chips on odd ranks                                                                                         | Per-card                                                                                                                                  |
| `j_onyx_agate`                                                                                                                          | +7 Mult per club scored                                                                                                          | Per-card                                                                                                                                  |
| `j_flower_pot`                                                                                                                          | ×3 Mult if scoring hand has all four suits                                                                                       | Global                                                                                                                                    |
| `j_family`                                                                                                                              | ×4 Mult on Four of a Kind                                                                                                        | Global                                                                                                                                    |
| `j_jolly` / `j_zany` / `j_mad` / `j_crazy` / `j_droll`                                                                                  | +Mult when hand type matches (`t_mult`)                                                                                          | Global                                                                                                                                    |
| `j_sly` / `j_wily` / `j_clever` / `j_devious` / `j_crafty`                                                                              | +chips when hand type matches (`t_chips`)                                                                                        | Global                                                                                                                                    |
| `j_half`                                                                                                                                | +20 Mult when ≤3 cards played                                                                                                    | Global                                                                                                                                    |
| `j_banner`                                                                                                                              | +30 chips × `discards_left` (if > 0)                                                                                             | Global                                                                                                                                    |
| `j_gros_michel`                                                                                                                         | +15 Mult                                                                                                                         | Global (destruction is RNG — mult while alive is fixed)                                                                                   |
| `j_acrobat`                                                                                                                             | ×3 Mult on last hand (`hands_left == 1` API)                                                                                     | Global                                                                                                                                    |
| `j_card_sharp`                                                                                                                          | ×3 Mult when hand type already played this round                                                                                 | Uses `hands.*.played_this_round`                                                                                                          |
| `j_hack`                                                                                                                                | +1 retrigger per scoring 2–5                                                                                                     | Per scoring card                                                                                                                          |
| `j_scary_face`                                                                                                                          | +30 chips per face card scored                                                                                                   | Per-card                                                                                                                                  |
| `j_smiley`                                                                                                                              | +5 Mult per face card scored                                                                                                     | Per-card                                                                                                                                  |
| `j_scholar`                                                                                                                             | +20 chips, +4 Mult per Ace scored                                                                                                | Per-card                                                                                                                                  |
| `j_stuntman`                                                                                                                            | +250 chips                                                                                                                       | Global                                                                                                                                    |
| `j_bootstraps`                                                                                                                          | +2 Mult per $5 (`state.money // 5`)                                                                                              | Global                                                                                                                                    |
| `j_supernova`                                                                                                                           | +Mult = lifetime `hands.*.played` for scoring hand type                                                                          | Global                                                                                                                                    |
| `j_seeing_double`                                                                                                                       | ×2 Mult if scoring cards include ♣ + another suit                                                                                | Global                                                                                                                                    |
| `j_ceremonial` / `j_flash` / `j_popcorn` / `j_green_joker` / `j_red_card` / `j_fortune_teller` / `j_ride_the_bus` / `j_trousers`        | +Mult from `value.stats.mult` (fallback: effect text)                                                                            | Global                                                                                                                                    |
| `j_duo` / `j_trio` / `j_order` / `j_tribe`                                                                                              | ×Mult when hand type matches (Pair / 3oak / Straight / Flush)                                                                    | Global                                                                                                                                    |
| `j_cavendish`                                                                                                                           | ×3 Mult while alive                                                                                                              | Global (destruction is RNG)                                                                                                               |
| `j_bull`                                                                                                                                | +2 chips × `state.money`                                                                                                         | Global                                                                                                                                    |
| `j_photograph`                                                                                                                          | ×2 Mult on first face card scored                                                                                                | Per scoring card                                                                                                                          |
| `j_baron`                                                                                                                               | ×1.5 Mult per King **held**                                                                                                      | Held-in-hand                                                                                                                              |
| `j_shoot_the_moon`                                                                                                                      | +13 Mult per Queen **held**                                                                                                      | Held-in-hand                                                                                                                              |
| `j_raised_fist`                                                                                                                         | +2× nominal chips of lowest **held** rank                                                                                        | Held-in-hand                                                                                                                              |
| `j_stencil`                                                                                                                             | ×Mult = empty joker slots + stencil count                                                                                        | Global                                                                                                                                    |
| `j_steel_joker` / `j_throwback` / `j_constellation` / `j_obelisk` / `j_campfire` / `j_glass` / `j_lucky_cat` / `j_hologram` / `j_ramen` | ×Mult from `value.stats.x_mult` (Throwback also uses `run.skips`)                                                                | Global                                                                                                                                    |
| `j_erosion`                                                                                                                             | +4 Mult per card below starting deck size (`run.deck_size`)                                                                      | Global                                                                                                                                    |
| `j_arrowhead`                                                                                                                           | +50 chips per Spade scored                                                                                                       | Per-card                                                                                                                                  |
| `j_triboulet`                                                                                                                           | ×2 Mult per King or Queen scored                                                                                                 | Per-card                                                                                                                                  |
| `j_sock_and_buskin`                                                                                                                     | +1 retrigger per face card scored                                                                                                | Retrigger                                                                                                                                 |
| `j_ancient`                                                                                                                             | ×1.5 Mult per played card matching `round.ancient_suit`                                                                          | Per-card; needs `round.ancient_suit`                                                                                                      |
| `j_idol`                                                                                                                                | ×2 Mult on played card matching `round.idol_rank` + `round.idol_suit`                                                            | Per-card                                                                                                                                  |
| `j_loyalty_card`                                                                                                                        | ×4 Mult when `value.stats.loyalty_remaining == loyalty_every`                                                                    | Global                                                                                                                                    |
| `j_drivers_license`                                                                                                                     | ×Mult from `value.stats.x_mult` when tally ≥ 16                                                                                  | Global                                                                                                                                    |
| `j_square` / `j_runner` / `j_wee`                                                                                                       | +chips from `stats` + in-hand growth (4 cards / Straight / each 2 scored)                                                        | Global                                                                                                                                    |
| `j_madness` / `j_vampire`                                                                                                               | ×Mult from `stats` (+0.1 per enhanced scoring card for Vampire; strips enhancement chips)                                        | Global                                                                                                                                    |
| `j_obelisk`                                                                                                                             | ×Mult from `stats` + `obelisk_step` when playing a non-dominant visible hand; resets to ×1 when sole most-played after increment | Global; uses `hands.*.played` + `visible`                                                                                                 |
| `j_ride_the_bus`                                                                                                                        | +Mult from `stats` + `ride_the_bus_step` when no scoring face; resets to 0 if any                                                | Global                                                                                                                                    |
| `j_pareidolia`                                                                                                                          | All cards count as face (Scary/Smiley/Photograph/Sock and Buskin/Ride the Bus)                                                   | Modifier                                                                                                                                  |
| `j_hit_the_road`                                                                                                                        | ×Mult from `value.stats.x_mult` (Jacks discarded this round)                                                                     | Global                                                                                                                                    |
| `j_flash`                                                                                                                               | +Mult from `value.stats.mult` (shop reroll growth)                                                                               | Global                                                                                                                                    |
| `j_blueprint`                                                                                                                           | Copies scoring effect of joker to the right (when blueprint-compatible)                                                          | Copycat                                                                                                                                   |
| `j_brainstorm`                                                                                                                          | Copies scoring effect of leftmost joker (when blueprint-compatible)                                                              | Copycat                                                                                                                                   |
| `j_hologram` / `j_ramen`                                                                                                                | ×Mult from `value.stats.x_mult` (cards added / consumables used)                                                                 | Global                                                                                                                                    |
| `j_green_joker`                                                                                                                         | +Mult from `stats` + `green_hand_add` per hand (context.before)                                                                  | Global                                                                                                                                    |
| `j_four_fingers`                                                                                                                        | Straights/flushes need 4 cards (not 5)                                                                                           | Hand classifier                                                                                                                           |
| `j_shortcut`                                                                                                                            | Straights may contain one rank gap                                                                                               | Hand classifier                                                                                                                           |
| `j_mime`                                                                                                                                | Retriggers held card/joker effects once (Steel ×1.5, Baron, …)                                                                   | Held phase                                                                                                                                |
| `j_baseball`                                                                                                                            | ×1.5 Mult per Baseball when an Uncommon joker fires joker_main                                                                   | Global; needs `value.rarity`                                                                                                              |
| `j_smeared`                                                                                                                             | Hearts≈Diamonds, Spades≈Clubs for suit jokers / Flower Pot / Seeing Double                                                       | Modifier                                                                                                                                  |
| `j_popcorn`                                                                                                                             | +Mult from `value.stats.mult` (starts 20, −4/round)                                                                              | Global; live `play` validated                                                                                                             |
| `j_ice_cream`                                                                                                                           | +chips from `value.stats.chips` (starts 100, −5/hand)                                                                            | Global; live `play` validated                                                                                                             |
| `j_castle`                                                                                                                              | +chips from `value.stats.chips` when > 0 (discarded `round.castle_suit`)                                                         | Global                                                                                                                                    |
| `j_red_card`                                                                                                                            | +Mult from `value.stats.mult` (+3 per blind skip)                                                                                | Global; stats-only (no effect parse)                                                                                                      |
| `j_fortune_teller`                                                                                                                      | +Mult = tarot used this run (`stats.mult` or `run.tarot_used`)                                                                   | Global                                                                                                                                    |
| `j_trousers`                                                                                                                            | +Mult from `stats` + 2 when playing Two Pair / Full House / Flush House                                                          | Global; live `play` validated                                                                                                             |
| `j_vampire`                                                                                                                             | ×Mult from `stats` + 0.1 per enhanced scoring card; strips enhancement chip bonuses                                              | Global; live `play` validated                                                                                                             |
| `j_madness` / `j_constellation` / `j_campfire` / `j_glass`                                                                              | ×Mult from `value.stats.x_mult` when > 1                                                                                         | Global; stats-only                                                                                                                        |
| `j_caino`                                                                                                                               | ×Mult from `value.stats.caino_xmult` when > 1                                                                                    | Global; stats-only                                                                                                                        |
| `j_yorick`                                                                                                                              | ×Mult from `value.stats.x_mult` when > 1                                                                                         | Global; stats-only (grows on discards)                                                                                                    |

**Output fields**

- `indices` — full list for `bot.ps1 play` (includes kickers when they improve a modeled effect).
- `scoring_indices` / `scoring_cards` — poker hand scorers only (kickers do not add chip value).

---

## Verified no-op (economy / utility)

Modeled as zero **score** impact so they do **not** appear in `unmodeled_jokers`.
Round-end **dollar** jokers (Golden, Rocket, Cloud 9, Satellite, Delayed Gratification)
are **not** in `estimate` — see **`round.cashout_preview`** / `glance` **`pending:`**
at **`ROUND_EVAL`** instead.

`j_midas_mask`, `j_delayed_grat`, `j_egg`, `j_gift`, `j_golden`, `j_faceless`,
`j_cartomancer`, `j_certificate`, `j_mail`,
`j_trading`, `j_riff_raff`, `j_drunkard` (+discard slot only), `j_matador`, `j_cloud_9`,
`j_hiker`, `j_rough_gem`, `j_business`, `j_reserved_parking`,
`j_8_ball`, `j_astronomer`, `j_burglar`, `j_burnt`, `j_chaos`, `j_chicot`,
`j_credit_card`, `j_diet_cola`, `j_dna`, `j_hallucination`, `j_invisible`,
`j_juggler`, `j_luchador`, `j_marble`, `j_merry_andy`, `j_mr_bones`, `j_oops`,
`j_perkeo`, `j_ring_master`, `j_rocket`, `j_satellite`, `j_seance`, `j_sixth_sense`,
`j_space`, `j_superposition`, `j_ticket`, `j_to_the_moon`, `j_todo_list`,
`j_troubadour`, `j_turtle_bean`, `j_vagabond`

---

## Player-uncertain (stay `unmodeled`)

Score impact exists but the value is **unknown at glance** (RNG when cards score).
Do **not** use expected-value approximations — list in `unmodeled_jokers` so agents
know the estimate is incomplete:

| Key            | Why                               |
| -------------- | --------------------------------- |
| `j_misprint`   | Random +0–23 Mult each hand       |
| `j_bloodstone` | 1-in-2 ×1.5 Mult per scored Heart |

Lucky card enhancement (+20 Mult proc) is likewise not modeled on scoring cards.

### Wild Card enhancement (`WILD`)

| Modeled                    | Detail                                                                              |
| -------------------------- | ----------------------------------------------------------------------------------- |
| Flush / SF detection       | Wild fills any suit in `_flush_indices` (`estimate.py`)                             |
| Rank unchanged             | Pair/ToK use printed rank only — Wild Q does not match Ace                          |
| Suit Jokers                | `_card_is_suit` returns true for any suit when Wild (Lusty, Greedy, …)              |
| Flower Pot / Seeing Double | Backtracking: each Wild assigned **one** suit per card                              |
| Blackboard (held)          | Wild counts as Spade or Club while held                                             |
| On-score bonus             | None (Wild has no +chips/+mult when scored — correct)                               |
| Debuffed Wild              | `_card_is_wild` false when `state.debuff`; printed suit only (`estimate_jokers.py`) |
| Flush Five tier            | `_classify` checks flush+5oak before Five of a Kind (`estimate.py`)                 |

| Not modeled         | Why                                             |
| ------------------- | ----------------------------------------------- |
| Deck unlock tallies | Wild does not count toward “30 of suit in deck” |

Rule reference: `bot.ps1 know check rule wild_card_enhancement`.

---

## Never model (RNG / hidden)

Do not add closed-form estimates — keep **`unmodeled`**:

| Key / name                             | Why                                                          |
| -------------------------------------- | ------------------------------------------------------------ |
| `j_misprint`                           | Random Mult each hand (see **Player-uncertain** above)       |
| `j_bloodstone`                         | Probability ×Mult on Hearts (see **Player-uncertain** above) |
| `j_8_ball`                             | Probability spawn Tarot (no score — also in no-op list)      |
| `j_lucky_cat`, Lucky Card enhancements | Probability money / Mult                                     |
| `j_wheel_of_fortune`                   | Random edition on joker                                      |
| `j_space`                              | Chance to level up hand (no score — also in no-op list)      |
| `j_cavendish`, `j_gros_michel`         | Destruction RNG (mult while alive is modeled)                |
| Most other “1 in N chance” jokers      | Any `SMODS.pseudorandom_probability` path                    |

Economy/utility keys with no play-time score are in **Verified no-op** above
(`j_8_ball`, `j_space`, …) so they do not spam `unmodeled_jokers`.

---

## TODO (deterministic, not yet ported)

*(none — add rows here when a joker needs new API fields)*

Integration tests: `tests/lua/endpoints/test_estimate_live.py` — parametrized recipes in
`tests/lua/endpoints/estimate_live_recipes.py` → `add joker` / card buffs →
`estimate(state)` → `play` same `indices` → `round.chips` delta must match.

Multi-joker **interaction scenarios** live in `tests/lua/endpoints/estimate_live_scenarios.py`
and run via `TestEstimateLiveScenarios` (31 scenarios × 2 lines ≈ 62 plays).

**Live coverage (2026-07-04):**

| Suite                 |  Count | Notes                                                                                            |
| --------------------- | -----: | ------------------------------------------------------------------------------------------------ |
| Scoring jokers        |     99 | One recipe per deterministic scoring key (`NO_SCORE` and `j_misprint` / `j_bloodstone` excluded) |
| Card buffs            |     12 | Playing-card buffs (9) + joker edition foil/holo/poly live (3)                                   |
| Interaction scenarios |     31 | Order-sensitive multi-joker combos; each has optimal + suboptimal line                           |
| Runtime               | ~6 min | Single Balatro instance; do not parallelize with other lua suites (OOM)                          |

`j_loyalty_card` skips when countdown is not active at glance time.

### Live interaction scenarios (31)

**Division of labor:** single-joker matrix = full smoke coverage; scenarios = order / held /
retrigger / combo regression with **contrast assertions** (optimal line: `estimate == play`;
suboptimal line: same match **and** score strictly lower).

Runner: `estimate_live_runner.run_scenario` — each line reloads the fixture independently;
optional `rearrange` jokers/hand; play order follows **hand slot order** (leftmost scoring card first).
Scenarios may use [`JokerAdd`](tests/lua/endpoints/estimate_live_recipes.py) for joker editions.

| Cat            | ID  | Description                    | Jokers                                | Contrast                              |
| -------------- | --- | ------------------------------ | ------------------------------------- | ------------------------------------- |
| A steel/held   | S04 | Steel K Baron+Mime base        | Baron, Mime                           | STEEL+RED K held vs plain K           |
| A              | S13 | Two steel kings held           | Baron, Mime                           | 2× STEEL+RED K vs 1 steel + plain K   |
| A              | S14 | High Card vs pair              | Baron, Mime                           | Pair vs 1-card High Card              |
| A              | S15 | Shoot the Moon + Steel         | Shoot, Mime                           | Steel K held vs plain K               |
| A              | S16 | Raised Fist + Steel            | Raised Fist, Mime                     | Steel 3 held vs plain 3               |
| A              | S17 | Steel Joker deck scale         | Steel Joker, Mime                     | Held steel vs no held steel           |
| B scored buff  | S20 | MULT→GLASS play order          | Jolly                                 | MULT left vs GLASS left               |
| B              | S21 | BONUS+FOIL pair                | Abstract                              | Enhanced pair vs plain pair           |
| B              | S22 | Stone+Splash                   | Stone, Splash                         | 5-card all-score vs 2-card pair       |
| B              | S23 | Vampire strips BONUS           | Vampire                               | BONUS pair vs plain pair              |
| B              | S24 | POLY+GLASS pair                | Jolly                                 | GLASS+POLY pair vs plain pair         |
| B              | S26 | MULT+HOLO Jack                 | Smiley                                | Face pair vs non-face pair            |
| C joker combo  | S01 | +Mult→×Mult order              | Jolly, Cavendish                      | Jolly left vs reversed                |
| C              | S05 | Brainstorm copy                | Brainstorm, Jolly, Abstract           | Jolly leftmost vs wrong slot          |
| C              | S06 | Blueprint trap                 | Blueprint, Jolly, Cavendish           | Copy Cavendish vs copy Jolly          |
| C              | S08 | Blackboard kicker              | Blackboard, Abstract                  | With Blackboard vs Abstract only      |
| C              | S10 | Flower Pot Splash              | Flower Pot, Splash, Seeing Double     | Full straight vs 2 cards              |
| C              | S12 | Baseball ×Mult order           | Jolly, Cavendish, Baseball            | Cavendish before Baseball vs reversed |
| D retrigger    | S02 | PhotoChad POLY                 | Photograph, Hanging Chad              | Face leftmost vs not                  |
| D              | S03 | PhotoChad + kicker             | Photograph, Hanging Chad              | With Chad vs Photograph only          |
| D              | S07 | Dusk+Seltzer+Chad              | Dusk, Seltzer, Hanging Chad           | `hands=1` vs `hands=2`                |
| D              | S09 | Face retrigger                 | Sock, Smiley, Scary Face              | 4 faces vs 3 faces                    |
| E hand type    | S11 | Flush MULT/GLASS               | Crafty                                | GLASS right vs GLASS left             |
| E              | S18 | PhotoChad POLY (dup archetype) | Photograph, Hanging Chad              | Face leftmost vs not                  |
| F buffed joker | S27 | Blueprint Holo + Cavendish     | Blueprint **HOLO** + Cavendish        | With Holo vs plain Blueprint          |
| F              | S28 | Jolly Foil + Cavendish         | Jolly **FOIL** + Cavendish            | Order (0,1) vs reversed               |
| F              | S29 | Cavendish Poly                 | Jolly + Cavendish **POLY**            | Poly vs plain Cavendish               |
| F              | S30 | PhotoChad Holo joker           | Photograph **HOLO** + Chad            | POLY face left vs not                 |
| F              | S31 | Mime Holo + held steel         | Baron + Mime **HOLO** + STEEL+RED K   | Holo vs plain Mime                    |
| F              | S32 | Baseball + Poly Cavendish      | Jolly + Cavendish **POLY** + Baseball | Order vs reversed                     |
| F              | S33 | **PhotoChad GLASS+RED 顶配**   | Photograph + Chad                     | GLASS+RED J left vs GLASS only        |

**PhotoChad + GLASS + RED (S33):** leftmost scoring face with GLASS (×2/trigger) + RED (+1 retrigger)

- Hanging Chad (+2 on `scoring_hand[1]`) + Photograph (×2 on first face each trigger). Live-validated;
    unit tests `test_estimate_photochad_glass_red_*`.

**Buff coverage in scenarios (each ≥ 2 appearances):**

| Buff         | Scenario IDs                 |
| ------------ | ---------------------------- |
| BONUS        | S21, S23                     |
| MULT         | S20, S26                     |
| GLASS        | S02, S03, S07, S11, S24      |
| STONE        | S22                          |
| STEEL (held) | S04, S13, S14, S15, S16, S17 |
| FOIL         | S21                          |
| HOLO         | S26                          |
| POLYCHROME   | S02, S09, S18, S24           |
| RED seal     | S04, S07, S13                |

## Run one scenario: `pytest tests/lua/endpoints/test_estimate_live.py -k S04 -v`

## Scoring order (pipeline summary)

See **Scoring architecture** for file paths. Runtime order:

1. `ease_hands_played(-1)` — **before** `evaluate_play()`
2. Move highlighted cards `G.hand` → `G.play`
3. Hand base chips/mult (+ Flint debuff)
4. Per **scoring** card triggers (`SMODS.calculate_main_scoring` / `score_card`; retriggers via `calculate_repetitions`)
5. Joker main phase left-to-right (`joker_main`) — per slot: **Foil +50 chips /
    Holo +10 mult before** the joker effect, **Poly ×1.5 mult after** (edition read
    from the physical card at that slot, including Blueprint/Brainstorm); then held
    jokers (Baron, Mime, …). **Held/retrigger jokers** (Mime, Baron, Shoot the Moon,
    Raised Fist, Dusk, …) apply edition **after** the held ×Mult stack so Holo is
    add-only, not re-multiplied. Blackboard reads **`G.hand.cards`**
6. Final scoring step / deck back effects / Plasma balance → **`SMODS.calculate_round_score()`**

Retriggers (Dusk, Seltzer, Red Seal, Hanging Chad) apply to **scoring** card loops in
game code; Dusk condition is `hands_left == 0` at evaluation time (= last hand from API).

---

## Live validation log

| Date       | Scenario                         | Estimate         | Actual            | Notes                                           |
| ---------- | -------------------------------- | ---------------- | ----------------- | ----------------------------------------------- |
| 2026-07-04 | Straight + Abstract/Swashbuckler | 2618             | 2618              | ✓                                               |
| 2026-07-04 | Two Pair, play `[4,5,6,7]` only  | 4950 (wrong idx) | 2178              | Fixed: need `[2,4,5,6,7]` for Blackboard kicker |
| 2026-07-04 | Two Pair, correct idx            | 2442             | +2442 incremental | ✓                                               |
| 2026-07-04 | Needle, High Card `[0,5,7]`      | 1863 `[short]`   | Lost              | Estimate correct; target 2000, need better line |
| 2026-07-04 | Jolly + Pair of Jacks            | 300              | 300               | ✓ live (ante 1 small blind)                     |

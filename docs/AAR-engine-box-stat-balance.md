# AAR — Box-stat balance: winners, aces, double faults, UE variety

## Segment summary

Playing the full engine surfaced four box-score complaints (owner, 2026-07):
1. **Not enough winners.**
2. **Aces too rare.**
3. **Double faults too infrequent.**
4. **Not enough variety in unforced-error totals** — every player's UE count
   looked the same regardless of who they were.

All four are point-resolution calibration, so the fix lives entirely in
`engine/rally.py:TUNE` and the winner/error split logic. Nothing about outcomes
changed: the season runs the **fast** model for scorelines, and `boxstats.py`
replays each recorded game through this same rally engine (rejection-sampled to
the persisted winner). So retuning the rally tables moves the box stats every
match shows — singles and doubles both, since `doubles.py` imports the serve/ace
helpers — without touching a single scoreline. `skill_slope`, the fast hold
curve, and the talent distribution were left alone.

Work is on `claude/tennis-engine-balance-igv65n`. Engine/box-stat/dual/doubles
suites (34) plus honors/individuals/ita/bracketing (28) all green.

## Root cause of #4 (the interesting one)

The winner-vs-error split was two **flat constants** — `winner_share = 0.42`,
`unforced_share = 0.55` — applied identically to every player. Aces already
varied by `serve_power − return_game` and double faults by `serve_placement`,
but *whether a lost rally became an unforced error* was talent-blind. So UE
totals only varied by match length and the binomial residual; a metronome and a
sprayer produced statistically identical error counts. That's the "no variety"
the owner saw. The engine's own design philosophy — *talent shifts the
distribution* — was simply not wired into the error split.

## What changed (`engine/rally.py`)

### Levels (issues 1–3) — TUNE nudges
| Tune | Before | After | Effect |
|---|---|---|---|
| `ace_first_base` | 0.16 | 0.185 | more aces |
| `ace_second_base` | 0.04 | 0.05 | more aces |
| `ace_swing` | 0.18 | 0.24 | big servers separate further |
| `second_in_base` | 0.90 | 0.855 | more double faults |
| `second_in_swing` | 0.08 | 0.10 | placement protects steady servers |
| `winner_share` (baseline) | 0.42 | 0.47 | more winners |
| `unforced_share` (baseline) | 0.55 | 0.52 | fewer cheap server UEs |

### Variety (issue 4) — the split now flexes per point
`winner_share` and `unforced_share` became **baselines**; two small helpers
(`_winner_share`, `_unforced_share`) swing the actual split by player attribute,
with three new coefficients:

- `winner_power` (0.34) — the ballstriker's groundstroke weapon (`_offense` =
  ½(forehand+backhand)) → more clean winners.
- `winner_steady` (0.34) — a steadier *opponent* gifts fewer forced errors, so
  more points must be earned with a real winner.
- `unforced_steady` (0.62) — a low-consistency *server* sprays more unforced
  errors; a metronome rarely misses.

Because a flaky player's UE now rises through **both** error branches (as the
misser when the server wins, and as the server when they lose the rally), a
player's `consistency` becomes the dominant driver of their UE total — which is
exactly the between-player spread that was missing. Wind's error contribution
was folded into `_unforced_share` (previously inline), no behavior change at
calm default.

## Measured before → after (400–600 full-fidelity matches, base 0.5)

| Stat | Before | After | Target |
|---|---|---|---|
| Ace rate / serve pt | 11.4% | 13.2% | up |
| DF rate / serve pt | 3.9% | 5.6% | up |
| Winners mean (per player/match) | 29.5 | 31.6 | up |
| Winners : UE ratio | 1.01 | 1.20 | winners lead |
| UE mean | 29.3 | 26.3 | ~steady |
| UE CV (std/mean) | 0.36 | 0.46 | more spread |
| UE/pt: low-consistency (<0.42) | — | 28.8% | — |
| UE/pt: high-consistency (>0.58) | — | 15.1% | ~2× spread |

The last two rows are the point of #4: identical-length matches now yield very
different error counts depending on who's hitting.

## Pass 2 — "it still feels random" (talent fingerprints)

Owner follow-up: the levels were right but stats still read as luck. Root cause
was structural: **each box stat keyed off a single driver** (aces = serve−return,
DF = placement, winners = forehand+backhand, UE = consistency), and `stamina`
touched the full point engine not at all. Over ~60 points a one-driver signal is
swamped by binomial noise, and a cannon server facing a good returner posted few
aces — which reads as random.

Fix: give each stat a **basket** of drivers and raise the signal.

- **Aces** now lead on *absolute* serve power, with the return only partly
  offsetting (`ace_return_weight` 0.55, `ace_swing` 0.24→0.30) — a true cannon
  stays an ace machine regardless of opponent.
- **Double faults** read placement **and** composure (`second_in_nerve` 0.10,
  `second_in_swing` 0.10→0.14) — nervy servers dump seconds in normal play, not
  only on break points.
- **Winners** read a shot-maker basket — weapons + court coverage + nerve
  (`winner_power` 0.34→0.46, `winner_move` 0.24, `winner_nerve` 0.16).
- **Unforced errors** stay consistency-led but a good mover retrieves would-be
  errors (`unforced_move` 0.24).

Correlation of each stat with the talent that should drive it (single match,
2,400 player-lines):

| Stat vs its talent | Pass 1 | Pass 2 |
|---|---|---|
| Ace vs raw serve_power | 0.54 | **0.67** |
| DF vs placement | −0.41 | **−0.50** |
| Winners vs shot-maker composite | ~0.40 | **0.53** (and 0.51 vs `overall`) |
| UE vs defensive composite | — | **−0.72** |

These are strong for one match; they rise further over a season as noise
averages out. We deliberately stop here rather than chase r→1 — a deterministic
box score is exactly what the owner does *not* want (talent shifts the
distribution; it doesn't script the line).

## Pass 3 — the engine now SEES the rich attributes (owner directive)

Owner: *"the engine should be seeing the rich attributes!"* Correct — passes 1–2
tuned the split but still fed on the **9 collapsed drivers**. A player's 49 rich
attributes (`app/player_attributes.py:RICH_ATTRS`) were averaged into 9 drivers
at `Prospect.engine_player()` and the texture was gone before a point was played.
So a big *first* serve was invisible if `strength` dragged the `serve_power`
driver down; `court_vision`, `passing_precision`, `discipline`, `rally_patience`
never touched a stat.

Fix — carry the rich table onto the engine and read it directly:

1. **`engine.state.Player` gained `rich: dict | None`** — the 49 attrs as [0,1]
   units. `Prospect.engine_player()` now populates it; synthetic `random_player()`
   leaves it `None`.
2. **Per-role baskets on `Player`** (`ace_power_first`, `return_solidity`,
   `second_serve_in_skill`, `serve_composure`, `attack`, `steadiness`,
   `court_cover`, `go_for_it`). Each reads the *specific* attributes that produce
   that outcome, and **falls back to the matching driver when `rich` is None** —
   so synthetic players (and every existing test) behave exactly as before.
3. **`rally.py` reads the baskets** instead of drivers: aces ← first-serve
   power + variety; DF ← second-serve quality + composure; winners ← weapons +
   passing + approach + vision + court coverage + nerve; UE ← consistency +
   tolerance + discipline + patience + coverage.

### The distribution trap this exposed (important)

Passes 1–2 were calibrated on synthetic `base=0.5` players. **Real rosters don't
sit at 0.5** — measured basket centers: **D1 ≈ 0.68, D2 ≈ 0.49, D3 ≈ 0.42**. With
the swings anchored at 0.5, every D1 player got a large positive winner swing and
negative error swing → **W:UE 3.2, aces 16%, DF 2%** on real rosters. The whole
prior calibration had been measuring the wrong population.

Fix: a **`swing_ref` (0.60)** anchor — the talent level the winner/error/ace
swings are measured against — and re-tuned bases/coeffs against **real rosters**.
A player at the reference gets the baseline; stronger bends toward winners/aces,
weaker toward errors. This also produces sensible **cross-division texture** for
free.

### Realized on real rosters (single match, ~1,600 duals/division)

| | ace% | DF%/pt | winners | UE | W:UE | UE CV |
|---|---|---|---|---|---|---|
| D1 | 11.3 | 2.7 | 31.4 | 20.1 | 1.56 | 0.55 |
| D2 | 8.3 | 6.6 | 17.9 | 32.9 | 0.54 | 0.43 |
| D3 | 7.5 | 8.2 | 12.9 | 34.4 | 0.38 | 0.45 |

D1 hits winners and aces, lower divisions grind and spray — emergent from the
attribute distribution, not hand-set per division.

### Correlation of each stat with its driving attributes (real rosters, ONE match)

| Stat vs its rich basket | drivers (pass 2) | rich (pass 3) |
|---|---|---|
| Aces vs serve power+variety | ~0.54 | **0.60** |
| Double faults vs 2nd-serve quality | ~−0.50 | **−0.60** |
| Winners vs weapons basket | ~0.40 | **0.84** |
| Unforced errors vs steadiness basket | ~−0.72 | **−0.88** |

Winners and UE now track the *actual* rich profile at r≈0.85 in a **single**
match — the strongest lever against "it feels random," and it climbs further over
a season.

### Notes
- **Determinism / outcomes unchanged.** Reading different attribute *values* does
  not change the rng draw sequence; the fast model still decides every scoreline,
  the overlay is still rejection-sampled to it. Box-stat identity + determinism
  tests pass.
- **Doubles** serve/DF read rich via the shared serve-in helpers, and **aces now
  route through the shared `rally._ace_prob`** (damped by a single
  `doubles.TUNE["ace_scale"]` 0.60 for the crowded net) — previously doubles had
  its own stale ace constants on raw drivers and never called the helper it
  imported (caught in review). Doubles ace rate ≈ 6.6% (vs singles 11.3%).

## Pass 4 — doubles fully on rich (owner directive)

Owner: *"I do want doubles fully on rich too."* The four doubles skill ratings
(`serve_rating`, `return_rating`, `net_rating`, `poach_rating`) still read the 9
drivers, so the specifically-doubles attributes — `net_play`, `volley_touch`,
`poaching`, `overhead`, `doubles_chemistry` — never touched a doubles point.

- **The four ratings now read rich baskets** (with driver fallback for synthetic
  players). `net_rating` ← net_play/volley_touch/overhead/agility/composure;
  `poach_rating` ← poaching/speed/agility/court_vision/doubles_chemistry;
  `serve_rating` ← first-serve power+accuracy/second-serve quality/variety;
  `return_rating` ← return quality/depth/aggression/passing/consistency. Each
  basket is centered like the driver form it replaced, so the fast-model / seeding
  calibration (`fast_skill_slope`) is preserved on average. These feed the point
  model AND `doubles_rating` (seeding + fast outcomes), so doubles outcomes now
  flow from the rich doubles attributes. `net_rating` tracks `net_play` at r=0.92.
- **The net-exchange winner/error split now flexes with talent** (it was a flat
  0.58, the singles pass-2 problem in miniature): `_net_winner_share` bends on the
  finisher's weapon + net game and the losing pair's steadiness, and the error is
  attributed to the **less-steady** partner. Doubles box winners now track a
  net/weapon basket at r=0.48 and UE track steadiness at −0.38 (were ~0.24/~0,
  lower than singles only because a pro set has ~⅓ the points per player).
- Seeding/outcomes shift (intended — the rich doubles profile now matters); the
  bracketing/ITA/honors/individuals suites stay green.
- Still driver-based: `_net_presence`'s small back-player term (0.26 weight) —
  immaterial, left for clarity.
- Four divisions exist (D4 is the academic tier); it sits between D2/D3 in
  strength and falls in line without separate tuning.
- `tests/test_doubles_lineup.py::test_pinned_doubles_uses_a_non_singles_specialist`
  fails on a dense roster (the 8th player slips into the coached six under lineup
  noise) — **pre-existing**, reproduces on the parent commit, unrelated to this
  work.

## Pass 5 — playing-style profiles so doubles specialists EXIST (owner directive)

After pass 4, doubles read the right attributes but `doubles_rating` still
correlated with singles `overall` at **0.99** — not an engine fault: the
**generator** (`development.generate_prospect`) drew all 49 attributes as
*independent* noise around one talent mean (`gauss(talent, 6)` per attr), so
every player was a clone of their own average — no shape, no net specialist.
`play_style` was drawn but never used.

Fix (`app/development.py`): `_apply_style_profile` shifts correlated attribute
**clusters** (serve / return / baseline / net / movement) by the player's
`play_style` plus a **net-specialist roll** (`NET_SPECIALIST_RATE` 0.18). The
shifts are **weight-normalized** — a uniform offset is removed so the player's
overall grade (Σ weight·grade) is preserved. So a player TRADES strengths (more
net, less baseline) at the **same overall level**: their net-weighted
`doubles_rating` rises above their all-around singles level, which is exactly a
doubles specialist.

Crucially this keeps the talent distribution intact — measured STR over 2,880
roster players, with vs without profiles:

| | mean | sd | p50 |
|---|---|---|---|
| baseline (no profiles) | 44.797 | 4.152 | 44.43 |
| with profiles | 44.801 | 4.131 | 44.43 |

Identical — only the *shape* moved. Realized:
- `doubles_rating` vs singles `overall` corr **0.99 → 0.956**.
- At roster scale, the team's **best doubles player is the singles #1 in only
  66%** of programs (#2 23%, #3 9%, #4 1%) — meaningful reshuffle, not chaos.
- **56% of programs** field a non-top-6-singles player in their doubles six.

Deliberately not pushed to extremes (an 8th-string singles player as doubles #1
is rare in real college tennis; the serve/return terms in `doubles_rating`
anchor a specialist so net alone can't vault them to the very top). Levers if
more divergence is wanted: `NET_SPECIALIST_RATE`, `_NET_SPECIALIST_BIAS`,
`_STYLE_BIAS`. Note: this adds RNG draws in `generate_prospect`, so the world's
player *identities* shift vs the old seed (determinism holds; the STR
*distribution* is unchanged as shown).

## Pass 6 — calibrate to real NCAA data + add forced errors (owner directive)

The owner pasted live box scores and three real data sources (VS Sports ATP-vs-NCAA,
Berkeley Sports Analytics, O'Shannessy "First 4 Shots"). Measured against them the
engine was off, badly at D1:

| Stat | Engine (D1) | Real NCAA-M |
|---|---|---|
| Aces | 12.4% | ~7% |
| Double faults | 1.8% | ~5% |
| 1st serve in | 68% | ~62% |
| Winners/match | 37 | far lower |
| W:UE | 2.2 | — |

Three fixes:

1. **Serve levels to the article.** `ace_first_base` 0.135→0.085, `ace_swing`
   0.30→0.20 (aces 12%→~7%); `first_in_base` 0.62→0.60 (68%→62%);
   `second_in_base`/swings retuned so DFs rise to ~5% and zero-DF players fell from
   54% to ~8%. All serve anchors moved onto `swing_ref` (the first/second serve-in
   swings were still anchored at 0.5, which pushed strong servers' second serves
   near 100% and killed their faults). `swing_ref` 0.60→0.68 (the real D1 center),
   so D1 sits at baseline and lower divisions bend down.

2. **Aces and double faults now positively correlate** (real pro men r≈0.93 —
   Berkeley). Added `second_in_aggression`: the same `ace_power_first` that earns
   aces also costs second serves, so a big server posts more of both (visible in
   the sample box: A9/DF8), while a big *and accurate* server keeps faults down.

3. **Forced errors are now their own category** (the big structural gap). The
   engine only had winners and unforced errors, so it charged every point that
   wasn't a winner as *unforced* — but O'Shannessy's men's college data is **~32%
   winners / ~41% forced / ~27% unforced**, with forced the largest bucket. Added
   `forced_errors` to `PlayerStats` (+ `STAT_KEYS` "fe", persistence, aggregation),
   and the "server won the rally, returner missed" branch now records a **forced**
   error instead of an unforced one. `winner_share`/`unforced_share` retuned to hit
   the 32/41/27 split. Surfaced on the box score (`season_dual`, `gtt_dual`,
   `player`, `render.py`) as `W · FE · UE`. Also fixed a doubles double-count (the
   return-missed branch incremented UE both inline and via `award`).

Realized D1 men: aces 6.7%, DF 5.6%, 1st serve 62%, split **W 32% / F 38% / UE
24%**, ~18 winners/match. Lower divisions grind harder (more errors, fewer aces),
which the data supports. Women aren't separately tuned; their lower talent scale
places them below `swing_ref`, so they naturally land more error-heavy (the real
WTA/NCAA-W pattern).

Note: adding `forced_errors` extends the persisted stat wire format. Old saves
lack "fe"; `from_dict` defaults it to 0, so they read back cleanly.

## Pass 7 — gender difference is EMERGENT (validation, no code change)

Owner supplied the StatsOnTheT ace-to-double-fault history + the r/tennis
discussion: **ATP ace:DF ≈ 2.2 (aces exceed faults), WTA ≈ 0.8 (faults exceed
aces)**, driven by both fewer aces AND more double faults for women. The rally
engine has ONE gender-agnostic table; women differ only by sitting lower on the
talent scale (below `swing_ref` 0.68). Measured, the pattern falls out on its
own:

| D1 | aces | DF | ace:DF | W / F / UE |
|---|---|---|---|---|
| men | 6.7% | 5.6% | **1.20** | 32 / 38 / 24 |
| women | 5.4% | 6.5% | **0.84** | 20 / 43 / 30 |

Women land at ace:DF 0.84 (real WTA ≈ 0.8) with more errors / fewer winners
(O'Shannessy: men 30% winners, women 26%). No gender lever was added; the single
talent scale plus one reference point reproduces the ATP/WTA divergence. This is
the whole design thesis working end to end: get the talent distribution right and
the stat texture emerges, rather than hand-setting per-gender dials. (College men
at ace:DF 1.20 also match the O'Shannessy "college men serve closer to WTA-pro
ace:DF than ATP-pro" finding — pro ATP is ~2.2, college men far below it.)

## Pass 8 — outcomes now come from the rich point engine (owner directive)

The prior passes all improved the box STATS, but the season still decided WHO WON
with the fast game-level model (`engine/fast.py`) on a single `overall` gap; the
rich point engine only ran as an overlay reconstructing stats to match the winner
the fast model already picked. The owner: *"we did all that work so outcomes are
based on real talent and match constants, not dice rolls… there's no reason the
game shouldn't pit players against what they have."* The fast model was a
speed-through scaffold from before the attribute set existed.

**Change: the full point engine now decides every season dual** (`worldconfig.
match_fidelity` default "fast" → "full"; `season.py` fallback likewise; env
override is now `TTM_FIDELITY=fast` to opt back to legacy). Consequences:

- Outcomes are driven by serve/return/rally/net talent and the rich attributes,
  and the box stats come from the SAME sim (no more overlay reconstruction), so
  stats and scoreline are one consistent object by construction.
- **It's faster, not slower** (the documented fear): full = ~14 ms/dual vs
  fast+box-stats ~36 ms/dual, because the overlay rejection-samples games to
  rebuild stats while full simulates once. The old "never on the request thread"
  warning applied to full *without* the overlay already running; with box stats on
  (default) the heavy point sim was already being paid.

**Competitiveness recalibrated.** The raw point engine was far chalkier than the
fast model (favorite 88% overall vs 66%, and ~92% at a 1-1.5 UTR gap — nearly
deterministic). The owner chose a ~75-80% target (better players win clearly more,
upsets still live at close gaps). Lowered the outcome dials
(`rally_slope` 3.2→0.9, `serve_plus_first` 0.55→0.36, `serve_plus_second`
0.20→0.10). Realized full-fidelity favorite curve on real D1 rosters:

| UTR gap | 0-0.5 | 0.5-1 | 1-1.5 | 1.5-2 | 2-3 | 3+ | overall |
|---|---|---|---|---|---|---|---|
| favorite win % | 53 | 65 | 73 | 80 | 90 | 96 | **77** |

Dense talent (tight roster spread) is what keeps most duals close: the majority of
matchups sit inside ~1.5 UTR, so the overall rate stays ~77% even though a real 3+
gap is ~96%. The box-stat calibration (aces 7% / DF 5% / 32-41-27 split) still
holds under the new dials — verified after the change.

## Appendix — reference data used for calibration (ground truth)

Preserved verbatim so future retuning has the targets without re-finding sources.

**VS Sports / Tennis Analytics — ATP vs NCAA-M serve (388k points, 2022-23):**
- 1st serve %: college ≈ ATP (~60-64%).
- 1st serve points won: pros 71%, **college men 66%**.
- Aces: pros 12%, **college men 7%**.
- Double faults: pros ~3% fewer than college; **college men ≈ 5-6%** of service points.
- 2nd serve points won: pros 3% higher than college.

**O'Shannessy / "First 4 Shots" & "Num3ers" — men's college + Grand Slam men:**
- Rally length: **0-4 shots = 70%**, 5-8 = 20%, 9+ = 10% (points are front-loaded).
- Point ending (GS men): **Winners 32% / Forcing errors 41% / Unforced 27%**
  (women 29 / 37 / 34).
- Building Blocks (AO): **men 70% errors / 30% winners; women 74% / 26%**.
- Net vs baseline win %: baseline 46%, **net 66%**.
- College men ace:DF ratio ≈ women's-pro range (low), not ATP-pro's high range.

**Berkeley Sports Analytics (Jake Lamb) — ATP men, 300 players:**
- **Ace-rate and DF-rate correlate at r = 0.93** (bigger serve → both rise).
- Only ~9% of players clear above-median aces AND below-median DFs.
- Break-points-saved % correlates with ace:DF ratio (r = 0.87).

**StatsOnTheT — ace:DF ratio through time:**
- **ATP ≈ 1.35 (1991) rising to ~2.2 (2019); WTA ≈ 0.8** and flat.
- Top-server spread is huge (Isner ace:DF 12.5; median tour player ~2).

**Engine targets locked from the above (D1 men):** aces 7%, DF ~5%, 1st serve
62%, 1st serve won ~66%, point split 32/41/27, ace:DF > 1, ace/DF positively
correlated. Realized: 6.7% / 5.6% / 62% / 32-38-24 / 1.20, r(ace,DF) positive.

## Guardrails / gotchas for the next agent

- **Do not push these back to flat constants.** The per-player winner/error
  split is the whole fix for #4. If a future test wants a fixed UE rate, the
  test is the stale side — assert an *identity* (UE ≤ points lost), not a level.
- **Outcomes are the fast model's job, not this file.** These tables only feed
  the box-stat overlay + exhibition full-fidelity matches. If chalkiness needs
  tuning, that's `fast.py`/`skill_slope`, not here (see
  `docs/match-engine-and-ratings.md` §1, §4).
- Ace and second-serve tunes are **shared with doubles** (`doubles.py` imports
  `_ace_prob`, `_second_serve_in_prob`), so those two propagate automatically;
  the winner/UE split does not (doubles keeps its own `winner_share`).
- Re-measure with a full-fidelity harness (not fast) — the fast model records no
  per-player stats. Reuse the throwaway in scratchpad or `render.py`'s box.

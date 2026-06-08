# AAR — Junior Ranking Points Ledger & Doubles

## Segment summary

This segment gave the junior circuit a **ranking system that matches how real
tennis actually ranks juniors**, and then added **doubles** to it. Two real-world
references drove it: the ITA college rankings (a Points ledger shown beside a WTN
rating) and the ITF/USTA junior points tables. The throughline is a deliberate
separation the sim previously collapsed: **ranking ≠ rating ≠ evaluation**.

- **Junior points ledger** — an accomplishment ledger on **ITF World Tennis Tour
  Junior** scaling: points by round reached × event grade (Major→Grand Slam …
  State→Grade 5), best-6 results, ranked-win bonuses, no ability prior, no recency.
- **Doubles** — folded into the *same* ledger the ITF way (Combined Junior Ranking:
  `best-6 singles + ¼ × best-6 doubles`), with a **doubles STR** that diverges from
  singles STR so a doubles specialist becomes a recruitable identity.
- **Teams** got a small ITA borrow: a **+10% road-win bonus** in the Power Index.

Shipped on `claude/junior-circuit-spec-i5QGW` (PR #26); 165 tests green.

## The design intent (why three numbers, not one)

The sim already had two recruit numbers — the **recruiting board** (consensus
ability + scouting) and **STR** (results-based strength). The national junior
ranking was just sorting on STR. That conflates two different questions, and real
tennis never does: the ITF/USTA junior boards rank on *points you earned this
season*, with a rating (WTN/UTR) sitting beside them. So this segment made the
junior ranking a genuine **points ledger** and kept STR as the rating column —
three honest numbers:

| Number | Question | Source |
| --- | --- | --- |
| Ranking points | What did you *earn* on the circuit? | best-6 results + ranked wins |
| STR | How *good* are you? | results-based rating (WTN analogue) |
| Recruiting board | What's your *ceiling* worth? | consensus ability + scouting |

Their **divergence is the gameplay** — a kid high on points but buried on the board
is a riser who earned it; the reverse is an over-scouted name. The user named this
explicitly as the gem-hunting hook, so both ranks are surfaced side by side on the
profile.

## What was built

### Points ledger (`app/junior_circuit.py` → `JUNIOR_POINTS`, `_freeze_points`)
`JUNIOR_POINTS[finish][grade]` is the ITF singles table; our five calendar tiers map
to ITF grades via `_LEVEL_TO_GRADE`. Each recruit's frozen `junior_points` is their
**best six** event results plus their best six **ranked-win bonuses** (beating a
higher-ranked junior, resolved off a *provisional* combined order — two-pass, like
the real algorithms iterate off the prior ranking). `tournaments_played` rides
along. Ranking surfaces (`app/juniors.py`): `points_rankings` (whole pool),
`us_points_rankings` (Top 100), `nation_points_top` (Top 10 per talent-dense nation).

### Doubles (the centerpiece)
The user's spec was specific and I built to it exactly:

- **One ledger, no separate doubles ranking.** `combined = best-6 singles + ¼ ×
  best-6 doubles`. `junior_points` is now that combined total; `singles_points` /
  `doubles_points` are kept for the breakdown.
- **Grit decides participation.** `_plays_doubles` rolls on stamina + resilience +
  competitiveness, so grinders play doubles more (~58% of the pool plays). Not
  everyone does — that's the point.
- **On-the-fly partners.** Drawn per event from that event's doubles entrants
  (`rng.shuffle` then pair), not season-long partnerships.
- **Full match engine, not the 8-game pro set.** `JUNIOR_DOUBLES_FMT` is best-of-3,
  no-ad, 10-point match tiebreak in lieu of the third set — ITF junior doubles
  rules, which the user supplied.
- **A doubles STR that actually differs from singles.** This was the crux. A naïve
  pair-collapse (flat attribute mean, the college-dual trick) makes doubles ability
  a pure function of singles ability — so doubles STR ≈ singles STR for everyone and
  the feature delivers nothing. `_pair_engine` instead builds a **doubles-tilted**
  synthetic team (`_DOUBLES_TILT`): serve / movement / net instincts up, long-rally
  baseline down. A net player then rates *above* their singles level in doubles and a
  baseline grinder below, so specialists surface (observed spread ≈ −2.9 … +1.9 STR).
  Doubles STR is solved over a per-partner corpus (each partner credited vs both
  opponents) seeded from singles ability.

### Web
Recruit profile gained a **Doubles STR** row (green when it beats singles STR) and a
separate **Junior Doubles** results table with partner names; a new **Junior
Rankings** page (International / US Top 100 / per-nation Top 10) ranks on the combined
points with STR as the WTN-style column. The recruiting board is untouched.

### Teams (`app/rating.py`)
`ROAD_WIN_BONUS` = 0.10: an away win counts 1.10× toward APR. The Power Index is
otherwise unchanged — it was already a season-only, no-prior, iterated-SOS rating,
and richer than the ITA team algorithm via flight/game data, so wholesale-copying
the ITA Points formula would have been a downgrade.

## Decisions & tradeoffs (owning them)

- **ITF scaling over USTA.** I first built the ledger on the USTA table (titles worth
  3000); the user preferred ITF magnitudes, so I rescaled. Judgment call inside that:
  **Major→Grand Slam** (title = 1000) puts the board top ~4k, close to the ITF
  screenshots. If our "Majors" should read as Grade A instead, dropping them a notch
  compresses the whole board toward ITF's ~3.2k top — a one-line table edit, flagged
  to the user.
- **Doubles STR tilt is deliberately modest** (±2–3 STR). Doubles isn't a different
  sport, so I didn't want a wild second rating; the tradeoff is that specialists are a
  real but subtle signal rather than a dramatic one. Tunable via `_DOUBLES_TILT`.
- **No real doubles *skill* attribute.** The tilt re-weights the existing nine engine
  drivers rather than adding a true serve-volley/net model (the engine itself flags
  that as a later build). Good enough to create the archetype; not a physically
  faithful doubles engine.
- **The unhashable-Prospect bug.** First pass keyed `teams`/`played` dicts on pair
  *tuples of Prospects* — `Prospect` is an unmutable-unfriendly dataclass and
  unhashable, so it blew up. Fixed by keying on pid-tuples. `run_tournament` itself
  was fine (it indexes entrants by position, never hashes them), which is why singles
  always worked with unhashable entrants.

## Determinism & calibration safety

All of it is seed-deterministic (verified: a re-run reproduces the board), since
participation, pairing and matches draw from the circuit's seeded RNG. Calibration
risk is low by construction: doubles only *adds* a points stream and a separate STR;
it never mutates the recruiting-board ability or the singles pipeline. The points
ledger likewise reads off the existing `finishes` data without touching ability.

## Tests

`tests/test_junior_circuit.py` and `tests/test_rating.py`:
- ITF event-points values + combined ledger identity (`combined == singles + ¼·doubles`).
- Points rank diverges from the recruiting board (the gem signal), best-6 bounded.
- Doubles participation is **grit-correlated** (high-grit cohort plays more), folds
  in at ¼ weight, and yields a doubles STR that diverges from singles STR in *both*
  directions (specialists and singles-only types).
- Road-win bonus rates an away win above an identical home record.

Full suite: **165 passed**.

## Handoff — what's left

- **Movement arrows** (the ↑/↓ in the ITF screenshots) need a prior points snapshot
  to diff against — natural to wire on the first board recompute after a rollover.
- **Singles / Doubles / Combined toggle** on the rankings page (mirrors the ITF
  dropdown); combined is the only view today.
- **Grade-mapping and tilt-strength** are both single-constant tunes if the user wants
  the board compressed or specialists louder.
- A **true doubles model** (serve-volley/net/poaching) would replace the driver tilt
  if doubles ever deserves first-class fidelity.

## Addendum — Grand Slams / Masters / Majors separated (correction)

The first cut **conflated "Major" with "Grand Slam"** — the calendar's top tier was
literally commented "the junior equivalent of the four Grand Slams" and was paying
Grand-Slam points. That was wrong: in real tennis the four slams sit *above* the
marquee events, and a slam — especially a slam *doubles* title — should dwarf
everything else. I built it the wrong way and the user caught it; it took two passes
to land the hierarchy the user actually wanted.

Final structure — a pro-tour ladder, with three distinct elite tiers so the genuine
top players have many high-value venues to separate themselves on the board:

| Tier | Events | Champion (singles / doubles) |
| --- | --- | --- |
| **Grand Slam** | 4 junior slams (Australian / Roland-Garros / Wimbledon / US Open) | 2000 / 1500 |
| **Masters** | 4 marquee city Opens | 1000 / 750 |
| **Major** | 5 classic international juniors (Easter/Orange Bowl, Bonfiglio, …) | 500 / 375 |
| National | 5 | 250 / 188 |
| Development | 4 | 125 / 94 |
| State | 1 | 50 / 38 |

Rounds decay in ATP-style ratios (F .6, SF .36, QF .18, R16 .09, R32 .045 of the
champion value). Only the international elite (Tier 1) enter Grand Slam / Masters /
Major draws. Points are now keyed directly by tier name (the intermediate ITF-grade
lookup was removed). Net: a slam title (2000) is double a Masters and quadruple a
Major; a Grand Slam doubles title (1500, ¼ → 375 into the combined ledger) is the
single biggest doubles prize. Board top ~10k on the elite résumés. Tests updated;
junior suite green.

## Addendum 2 — fixed calendar → rank-gated weekly pyramid

The original circuit was a **fixed calendar** of ~23 hand-named events at fixed
months, with tier-eligibility deciding who entered. That doesn't scale or convince:
with 1000 players you need *many* events at every level each week, and hand-coding
them is brittle. The user redirected (and a quick read of the real ITF tour — >1,000
graded tournaments a year, small draws, **ranking-gated acceptance lists**, hundreds
running in parallel weekly — confirmed it). Rebuilt the scheduler:

- **Abstract weeks, not a calendar.** `SEASON_WEEKS` (14) speedy weeks; after the
  last, recruits graduate to college. "Weeks" are just enough tournaments to give
  everyone matches and data.
- **Rank-gated parallel draws.** Each week the whole field is ranked by *running*
  points (ability seeds week 1), then sliced into tier **bands** and split into
  32-player draws (`_schedule_week`). The elite get the Grand Slam (top 32 on slam
  weeks) / Masters; everyone else plays down their level — so all ~1000 play every
  week, and **only winners climb into the big events** (the filter the user wanted).
- **Generated tournament names.** `_gen_tournament_name` rolls a real city from the
  hometowns DB + a tier-appropriate suffix ("Užice Masters Cup", "Florence Open"),
  deduped per season. Only the four slams are fixed.
- **Seven tiers** (Premier restored): Grand Slam 2000 > Masters 1000 > Major 500 >
  Premier 250 > National 125 > Developmental 60 > State 30, ATP-ratio rounds.
- **Development pulses + STR snapshots** moved from months to weeks; the old
  fixed-calendar constants, fallback-coverage hack, and tier-eligibility table were
  deleted (everyone now plays by construction).

Result: every recruit plays exactly `SEASON_WEEKS` events with generated names at
their level; a 1000-player class builds in ~10s (cached once). Tests that asserted
the old closed calendar were updated; full suite green (165).

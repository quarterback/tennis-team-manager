# Development Model — the tennis adaptation

This is how the O27 baseball prospect-development model ("How I Fixed Baseball Sim
Prospect Development Breaks") was ported into the tennis sim, what was kept
verbatim, what changed for tennis, and the one genuinely new mechanic the tennis
version adds: **staggered** development.

It's written as source material for a write-up, so it leads with the design intent
and points at the code (`app/development.py`, `app/world.py`,
`app/junior_circuit.py`) as it goes.

---

## What carried over verbatim

The baseball model's spine is intact, because it was right:

**Interest-rate development.** Every player draws one `interest_rate` at generation
and keeps it for life. The tier structure is identical to baseball:

| Interest tier | Share | Multiplier |
| --- | --- | --- |
| ordinary | 75% | 1.0× |
| late bloomer | 20% | 1.3× |
| super-bloomer | 5% | 1.6× |

(`app/development.py` → `TIERS`). Growth is deterministic: each development year
closes a fraction of the gap to the (hidden, slowly-rising) potential ceiling, and
the fraction is `interest_rate × GROWTH_K × tier_multiplier`. A super-bloomer traces
a dramatic arc; an ordinary developer barely moves. **The variation is character,
not a dice roll** — when a player surprises you, it's because you never saw their
rate, not because the universe rerolled them.

**Nobody regresses; everybody develops.** This is the load-bearing idea and tennis
keeps it exactly. "Regression" in this model is purely *relative*: a low-interest
player's ratings stay flat while higher-interest peers keep climbing past them. The
kid who was the best 14-year-old in the room — already accessing most of his
potential — looks elite, then stops looking elite at 16 because his stats didn't
move while everyone else's did. No one's rating actually went down. He stagnated and
the field grew. That *feels* like regression from the outside, which is the point.

**The scouting fog.** Tennis keeps the two-report structure: a shared consensus
service read and your own department's read, each an independent blur of the hidden
ceiling by a per-player fog magnitude (Uniform 7–31). See
`Prospect.scouting_report()`; it drives the recruit profile's "two independent
ceiling reads (±fog)" and the consensus recruiting board. The decision triangle —
stats vs. consensus vs. your department — survives intact.

---

## What changed for tennis: converging access, not a static lens

The baseball model splits each attribute into **potential** (hidden ceiling, grows)
× a **static access** lens (fixed 0.40–0.95) → **displayed**. The crucial move there
is that access never changes: a hidden gem with low access looks like a fringe
contributor his entire college career and only reveals his true ceiling on pro
signing.

Tennis deliberately does **not** freeze access. It uses **converging maturity**:

- At generation a recruit's *current* grades are `potential × maturity`
  (`maturity` ∈ 0.45–0.95 — the access lens at that moment).
- But maturity is not static. Development *raises* it: `current` closes the gap
  toward `potential` every year (`Prospect.develop`). Access rises over a career.

Why the divergence from baseball:

1. **Tennis STR is results-based and public.** A player's on-court STR
   (`app/str_rating.py`) is computed from what they actually did, opponent-relative
   and recency-weighted. You can't hide current ability behind a static lens when
   the rating *is* the results — the court reveals it. So tennis makes **current
   ability visible** and hides **trajectory** instead. The mystery isn't "how good
   is he really" (the matches answer that); it's "how much more is coming."
2. **The reveal is continuous, not a single pro-signing drop.** A late bloomer's
   ceiling expresses gradually across college as maturity converges, rather than
   snapping into view on draft day. Tennis careers are about thin margins widening
   slowly, so a smooth convergence models the sport better than a one-time lens
   lift.

So the three layers in tennis read: **potential** (hidden ceiling) → **maturity**
(access, *rising*) → **current** (visible, drives STR and the engine). The star
rating still tracks *current*, so gems are underrated and busts overrated exactly as
in baseball (`Prospect.star_rating`) — the difference is only that the lens opens
over time instead of staying shut until the pros.

---

## The new mechanic: staggered development

Baseball develops the whole class once a year, all at once. Tennis develops over the
**course of a season**, and the new idea is that it does **not** happen to everyone
simultaneously — **think staggered senate terms.**

`app/development.py` → `stagger_scale(key, tick, ticks)`:

- Each player banks a full year of growth, but only inside a contiguous **window**
  of the season's ticks (default ~45% of them), and the window's *start* is
  phase-shifted by a stable per-player key.
- The per-tick slices in a player's window sum to the same total for everyone, and
  every window finishes by the final tick — so the **season-end state is identical**
  to developing all at once. Only the *timing* differs.

The payoff is what you see **mid-season**: at any week, some players have already
made their jump, some are mid-climb, and some haven't moved yet. Development arrives
in waves across the roster instead of as one synchronized year-end step. It's
deterministic (no RNG — a stable hash of the player id picks the phase), so any
week's snapshot is reproducible.

Applied in two places:

- **College in-season drip** (`app/world.py` → `developed_rosters`). The world
  advances week by week; each week pulses the staggered slice. By the end of the
  season every roster has banked its full year (so the year-over-year rollover is
  unchanged), but the in-season ranking movement now ripples instead of stepping.
- **The junior circuit** (below), where the stagger is what makes the bloom/plateau
  arc legible.

---

## The showcase: the junior circuit replays the climb

The junior circuit (`app/junior_circuit.py`) runs once per recruiting class, before
recruiting opens, and plays a full junior season with the match engine. It's the
natural stage for the development model because the junior years are exactly where
the "great at 14, ordinary at 16" story happens.

The trick: a recruit's **current** (generated) ability is treated as the *end* of
the junior climb — their recruiting-time level. The circuit replays how they got
there:

1. **Roll back to a younger self.** `Prospect.regress_to_younger(years)` is the exact
   inverse of `develop`: it backs `current` toward where the player was ~a year ago,
   *scaled by their own interest rate*. A super-bloomer was far weaker at the start
   of the season; an early bloomer was always near where they are now. (Nothing
   actually regresses — this only *replays* a climb that already happened.)
2. **Develop back up, in staggered waves.** As the calendar advances month by month,
   each junior self pulses a `stagger_scale` slice of development, climbing back
   toward their current ability by season's end.
3. **The matches use the developing self.** Early-season matches are played by the
   younger, weaker self; late-season matches by the nearly-grown one. The
   results-based STR (seeded with the *younger* ability as its prior) therefore
   starts low for a fast developer and rises with results across the four ranking
   snapshots.

What you get is the arc, visible in a recruit's ranking history:

```
Super-bloomer (interest 1.99)      Early bloomer (interest 0.09)
  Jan  National #89  STR 39.2        Jan  National #29  STR 44.4
  Apr  National #90  STR 39.2        Apr  National #32  STR 44.4
  Aug  National #78  STR 40.2        Aug  National #37  STR 44.0
  Dec  National #66  STR 41.1        Dec  National #39  STR 44.0
```

The super-bloomer surges up the national board as he grows into his ceiling; the
early bloomer holds flat and *slides* as the field climbs past him — without his
rating ever dropping. That's the model's whole thesis rendered in one table.

Crucially, all of this runs on **throwaway copies**. The recruit object's
recruiting-time ability and star rating are never mutated, so the recruiting board
stays calibrated; only the junior STR, results, and ranking history reflect the
climb. (`test_recruiting_ability_is_not_mutated_by_the_circuit`.)

---

## Why this works (the tennis version)

The baseball framing was: *display decouples from potential; nobody regresses;
everybody develops; the mystery is who develops fast and how well they hide it.*

Tennis keeps the engine of that — deterministic interest-rate development, the
75/20/5 tiers, the scouting fog, no true regression — and adapts three things to the
sport:

- **Current ability is visible** (the court reveals it via results-based STR); the
  hidden thing is the *slope*. Maturity converges instead of a static lens hiding
  the ceiling until the pros.
- **Development is a season-long, staggered process**, so a roster's growth ripples
  across the year in senate-style waves rather than landing as one annual step.
- **The junior circuit replays the climb**, turning "great at 14, ordinary at 16"
  from a description into something you can watch happen in a recruit's ranking
  history — because tennis, more than team sports, is a game of thin margins
  widening slowly, and the development model should let you *see* them widen.

---

## Code map

| Piece | Where |
| --- | --- |
| Interest tiers, `develop`, `regress_to_younger`, `stagger_scale` | `app/development.py` |
| Results-based STR (the public rating) | `app/str_rating.py` |
| Staggered college in-season drip | `app/world.py` → `developed_rosters` |
| Junior-circuit climb replay + bloom/plateau | `app/junior_circuit.py` |
| Scouting fog (consensus + your department) | `app/development.py` → `scouting_report` |
| Tests | `tests/test_development.py`, `tests/test_junior_circuit.py` |

---

## Rankings vs. ratings vs. evaluation (three honest numbers)

Real tennis keeps the *ranking* (what you earned) separate from the *rating* (how
good you are) — the ITA college table shows Points **and** WTN; the ITF/USTA junior
tours rank on a points ledger while WTN/UTR sits beside it. The sim mirrors that
split instead of collapsing everything into one number.

**Junior ranking points (`app/junior_circuit.py` → `JUNIOR_POINTS`, `_freeze_points`).**
An accomplishment ledger modelled on the USTA Junior Tournaments points table. Each
event awards points by **round reached × level** (our calendar tiers Major / Premier
/ National / Development / State map onto USTA Levels 1–5 — a Major title is 3000, a
State quarterfinal 105). Only a player's **best six** results count, plus their best
six **ranked-win bonuses** (beating a Top-10 junior is +225, USTA-style, resolved
off a provisional points order). It is deliberately *not* a rating: it rewards deep
runs at strong events and rewards activity, with no ability prior and no recency
weighting — start-from-scratch, like the real tours.

**The three numbers, and why they differ:**

| Number | Question it answers | Source |
| --- | --- | --- |
| Ranking points | What did you *earn* on the junior circuit? | best-6 results + ranked wins |
| STR | How *good* are you (strength/form)? | results-based rating (WTN analogue) |
| Recruiting board | What's your *ceiling* worth to a coach? | consensus ability + scouting |

Their **divergence is the gameplay**. A recruit ranked high on points but buried on
the board is a riser who earned it on court; a board darling with thin points is an
over-scouted name; a high-STR kid ranked low on points skipped events. The junior
rankings pages (International / US Top 100 / per-nation Top 10) rank on points and
show STR as the WTN-style column, and the recruit profile lays all three side by
side so the gaps pop.

**Teams (`app/rating.py`).** The college Power Index is already a season-only,
no-prior, iterated-strength-of-schedule rating — the same family as the ITA Points
algorithm, but richer (it sees flight and game data the ITA team algorithm can't).
The one ITA borrow is the **+10% road-win bonus**: an away win counts 1.10× toward
APR, so a team that won on the road rates a hair above an identical home record.

| Piece | Where |
| --- | --- |
| Junior points ledger + ranked-win bonus | `app/junior_circuit.py` |
| Points ranking surfaces (intl / US / by-nation) | `app/juniors.py` |
| ITA road-win bonus | `app/rating.py` |

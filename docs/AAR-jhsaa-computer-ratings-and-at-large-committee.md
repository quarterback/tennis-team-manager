# AAR — JHSAA computer ratings and the at-large selection committee

Owner spec 2026-09. Two deliverables: a **computer-ratings layer** (nine
independent systems + composite, every championship group and gender, every
season) and an **at-large selection committee** on top of it for **7A and
Group 1**, which move to a **48-team State field**. The structure is ported
from viperball's `engine/ranking_composite.py` — the owner's other sim already
runs this kind of composite — adapted to tennis.

## What was reused (the report the spec required)

1. **Dual/line ingestion** — `TeamSeason.schedule` rows from `jhsaa.play_dual`
   (varsity structural: JV is `JVTeam`); set/game parsing reads the home-first
   score convention `jhsaa._games` reads.
2. **Group scoping** — `run_season`'s `by_group` on `School.group` (the
   championship group, so play-up is already right), per gender.
3. **TOSS / seeding ATR** — `power_index(prestate=True)`, `seed_atr`,
   `_seed_atr_key`, `atr` reused READ-ONLY. Nothing modified; nothing here
   feeds them.
4. **Bracket machinery** — the Parastate is played by hand (pinned pairings)
   via `play_dual(phase="state")`; the Round of 32 onward is the existing
   `run_state(survivors, champions=16)`; rendering rides `_jh_split_state`'s
   generic named-prelim split (the "Parastate" round draws as its own tree).
5. **Archiving** — `ratings` and `committee` keys on `out["groups"][group]`,
   flowed into `world.run_jhsaa`'s summary blob, `.get` on read — the
   `epiregional` pattern. Computed once on the pre-State graph, never refit on
   a page request (`pi`'s rule).

## The ratings layer (`app/jhsaa_ratings.py`)

Nine systems: Colley · Bradley-Terry (pure W/L, per spec — viperball's MOV
weighting deliberately not ported) · Win% · Massey (dual) · SRS · Massey
(game) · Set share (fractional-win Colley) · SOR · Elo. Composite = mean /
median / σ of the nine ranks; σ is the disagreement measure and the page's
point.

Owner refinements, all applied:

- **‼️ MARGINS ARE FORMAT-NORMALISED.** A season mixes 5-, 7- and 9-flight
  duals, so raw margins are not one currency: Massey-dual/SRS use
  `(flights won − lost) / flights played`, Massey-game uses the normalised
  game margin per dual (raw games would hand long three-set duals more
  statistical mass for merely lasting longer). A 5-0, 7-0 and 9-0 are all
  +1.0 — format length is never a rating input.
- **Same-group input only** — `dual_rows` keeps duals where BOTH sides are in
  the group; cross-group showcases stay on the résumé but never enter the fit,
  or the independence premise dies.
- **‼️ SOR's benchmark is DEFINED and PUBLISHED**: the median Bradley-Terry
  rating of the group's teams ranked 9-16 ("a normal bye-caliber team"),
  frozen per run and archived as `sor_bench`. "Average top-16 team" without a
  mathematical identity is recursive. SOR itself is an exact Poisson-binomial
  DP with the mid-P convention (P(W<w) + P(W=w)/2) — plain P(W≤w) hands every
  undefeated team exactly 1.0 whatever it played.
- **Determinism** — Gaussian elimination for the least-squares family, damped
  SRS iteration (the plain form oscillates forever on a two-team graph), no
  rng anywhere.
- **A disconnected group is REPORTED** (`disconnected`), and the least-squares
  family withheld — never silently fit per component.
- **Retirement guard** — a single-set line is a retirement/default and never
  reaches set/game share.
- Ratings are computed and archived for ALL twelve groups (the historical
  dataset for any future group that adds at-larges), in `run_season` beside
  `final_power`, on the same pre-State posture.

## The committee (`app/jhsaa_committee.py`)

Five members, CONCENTRATED published weights (owner numbers — a member reads
only the systems their philosophy names; forcing all nine on everyone
collapses the ballots toward the mean): Traditionalist (Colley .30 / BT .30 /
Win% .25 / SOR .15) · Quant (Massey-G .35 / SetShare .30 / Massey-D .20 /
SRS .15) · Schedule Hawk (SOR .40 / Colley .20 / Massey-D .20 / BT .20) · Eye
Test (Elo .40 / SRS .25 / Win% .20 / BT .15) · Balancer (1/9 each).

Procedure: automatic bids (a district champion who missed the road) → locks
(unanimous across the five at-large ranges, each range = a member's top
`16 − automatics` candidates) → the bubble, **Borda over the FULL ordering of
the bubble population** (so No. 17 and No. 50 on a ballot stay
distinguishable) → seeding 33-48 by Borda over the selected sixteen with the
owner's tie ladder (ballots-selecting count → median ballot rank → composite
mean → seeding ATR; the head-to-head rung sits before ATR in the owner's
wording but a played pairing between two at-larges is rarely defined, so the
ATR rung carries it).

**‼️ The candidate pool is EVERY team outside the road field** — including
teams the systems rank above road qualifiers (owner correction mid-build; the
first spec draft read as bottom-only). And **‼️ an at-large is ALWAYS seeded
33-48** — structural, not a sort key: the at-larges arrive after the 32 road
seeds in `run_state_48`'s field.

> **2026-09 resize.** 8A and 9A adopted this structure (48 = 32 + 16); 7A moved
> to 40 = 32 + 8 keeping Parastate (25v40 … 32v33, seeds 1-24 bye). Bids are
> per group in `jhsaa.AT_LARGE_BIDS`; `run_state_48` is now `run_state_parastate`
> at `byes=16`; `select` takes `seats`. See
> `docs/AAR-jhsaa-group2-3s3d-postseason-deciders.md` §1.

## The 48-team field (`jhsaa.run_state_48`, `ATLARGE_GROUPS`)

Road unchanged (still exactly 32 by the existing ladder). Seeds all earned:
1-4 Epiregional winners, 5-8 Epiregional losers, 9-16 the best eight
non-champion road qualifiers, 17-32 the rest — all on the EXISTING `seed_atr`.
Parastate pins 17v48 … 32v33, higher seed hosts, winners retain their seed;
byes 1-16 first play in the Round of 32 (`run_state` on the surviving 32,
`champions=16` → the plain single-draw branch). Group 1 joined `WIDE_GROUPS`,
so both groups play 4S/5D in every State round, Parastate included.

## Surfaces

`/jhsaa/computer-ratings` (all groups; sortable composite + nine systems +
glossary; the disconnected banner) and `/jhsaa/committee` (7A/Group 1;
selection board with statuses Qualified/Lock/In/Bubble/Out, per-member ballot
positions, Borda; a Ballots tab showing the five orderings side by side).
Both read the ARCHIVE only. The spec's third "résumé" view is the existing
school page (schedule, opponents, results, district finish) — not rebuilt.

## Tests

`tests/test_jhsaa_ratings.py` (hand-checked Colley/Massey/SRS answers,
normalisation, chain ordering, retirement guard, SOR benchmark + mid-P,
disconnected report, engineered-σ composite, State/TOC exclusion) and
`tests/test_jhsaa_committee.py` (32+16 assembly, open pool, the 33-48 floor
under a top-ranked at-large, automatic bids, ballot independence,
full-ordering bubble Borda, Parastate pairings + seed retention + 48→32→…→2).
Plus the two routes in the empty-state route sweep.

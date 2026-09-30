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
- **‼️ SRS CAPS ITS MARGIN, AND UNCAPPED IT WAS NOT A SYSTEM AT ALL (owner rule
  2026-09, `SRS_MARGIN_CAP` 0.5).** `srs` and `massey_dual` were the SAME RATING,
  and not approximately: divide Massey's normal equations by a team's dual count
  and you get exactly SRS's fixed point (`r = avg margin + mean opponent
  rating`), with the same zero-centring, off the same `_flight_margin`. Measured:
  agreement to 1.7e-10 and an identical rank order on a 400-dual synthetic
  schedule, and on the owner's real 2029 pages the two columns matched in **all
  57 rows of 10B and all 55 of 11B**. Two costs, both invisible on a page that
  looked tidy: the composite counted margin-plus-schedule in **two of nine**
  columns, and **σ — sold on the page as the disagreement measure — averaged in a
  pair that can never disagree**, so every team's σ read low, worst where margin
  was the outlier view. Capping answers the weakness the glossary already names
  in `massey_dual` (running up flight margins), so the two now differ exactly
  where that is what separated them: 13 of 24 teams move rank on the synthetic
  schedule, largest move 4 places. ‼️ **A DUPLICATE SYSTEM IS THE ONE DEFECT THIS
  PAGE CANNOT SHOW YOU** — nine columns of plausible numbers, a composite, and a
  σ that is confidently wrong; it was found by reading two columns down, not by
  any check. Pinned three ways: a capped known answer, an UNDER-the-cap case
  where the two must still agree exactly (so the cap is provably the only
  difference), and a ranking-inequality test that fails if SRS is ever un-capped.
  ‼️ Ratings are ARCHIVED and never refit on read (the `pi` rule), so seasons
  played before this keep identical columns — the honest record of what the
  association published, not a migration.
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
>
> **2026-09 expansion.** 6A, 5A, 4A, 3A, 2A **and 1A** joined on 7A's shape —
> **eight bids each**, over the road each already had. That is a 40-team
> structure for the five 32-road classes and a **32** for 1A, whose road is 24:
> the bid count is the decision and the field size is the consequence (the
> owner refused the sixteen bids a 40 would have cost 1A). The dual formats did
> NOT move with it: `WIDE_GROUPS` is a separate axis and the new classes are not
> in it. See `docs/AAR-jhsaa-playoff-expansion-parastate.md`.

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
glossary; the disconnected banner) and `/jhsaa/committee` (every Parastate class;
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

---

## Addendum — Colley out, Markov in, and a 24-outlet electorate (owner rules 2026-09)

Two changes in one pass, and they belong together: adding a tenth measurement
while leaving five voters in place would only have nudged one Balancer's average.

### 1. The Markov chain replaced Colley

Surveyed the field first rather than answering from memory (an earlier draft of
this answer did, and the owner caught it). Massey's own comparison roster —
Dickinson, Houlgate, Dunkel, Boand, Williamson, Litkenhous, Poling, Berryman,
Billingsley, Anderson-Hester, Wolfe, Sagarin, Congrove, ARGH — is almost entirely
*parameterisations*, not new mathematics; Wikipedia's survey collapses the whole
field into three families (permutation of standings, trading skill points,
solving equations) and the nine already covered all three. Four families were
genuinely absent:

| Family | Representative | Verdict |
|---|---|---|
| Markov / random walk | Callaghan-Mucha-Porter; LRMC; GeM | **Added** |
| Offence-defence | Govan-Langville-Meyer (Sinkhorn-Knopp) | Best second candidate — the only family returning TWO numbers per team, and tennis supplies the currency natively (flights taken vs conceded). Not built: a team that wins no flight all season is an all-zero row needing smoothing, and the flight-efficiency page answers part of it. |
| Keener eigenvector | Keener, *SIAM Review* 35 (1993) | Rejected — the preference matrix must be irreducible, so it fails exactly on the thin pod graphs where it would be wanted. |
| Rating uncertainty | Glicko, TrueSkill, WHR | Rejected — Elo plus a variance term, and a rating archived and never refit has nowhere to use the variance. |

Also rejected: **KRACH** (an alias of Bradley-Terry — adding it would reinstate
exactly the duplication the SRS cap had just removed), **Billingsley-style
recency** (a weighting of a model already present, and Elo is the system where
*when* you won counts), and **minimum-violations / retrodictive** ranking
(distinctive output, but exactly NP-hard, so it ships as a heuristic whose answer
depends on the heuristic — wrong for a determinism-first module).

Colley was the column dropped because the layer carried three record-only
systems and Colley's reading is Bradley-Terry's near neighbour. **The Colley
MATRIX did not leave**: `set_share` *is* a fractional-win Colley (`_colley_frac`),
which is where the method earns its place. A column went, not a technique —
pinned by `test_the_colley_matrix_survives_as_the_set_share_adjustment`.

**Measured** on a pod-shaped 80-team, 415-dual schedule: Markov moved 73 of 80
teams' ranks against the Colley column (mean 5.1 places, max 19) at a rank
correlation of +0.96 — a different ordering, not a third view of the record.
Correlation with the generator's own skill: BT +0.92, Colley +0.90, **Markov
+0.88**, Win% +0.87, so on a connected graph it is marginally the weakest of the
four at recovering strength. That is not a defect. The page exists to publish
nine honest disagreements, and what Markov contributes is transitivity: two teams
with identical records separate when one's win came over the chain's best team
(`test_markov_carries_a_win_transitively_where_bradley_terry_cannot`).

> ‼️ **A CLAIM WRITTEN INTO A DOCSTRING BEFORE IT WAS MEASURED, AND IT WAS
> WRONG.** The first draft said Markov made a disconnected class comparable —
> "the schedule-adjusted column that survives" — and the template said so on the
> page. It is defined on a broken graph (no singular matrix, no withheld column),
> but that is a different statement. Measured on two isolated pods, one built far
> stronger: strong pod 0.025-0.153, weak pod 0.032-0.139, overlapping. The
> damping carries MASS between components and no EVIDENCE, and nothing can do
> better — with no dual between two groups of teams there is nothing in the
> results to order them by. Colley answered on a broken graph too, per component.
> `test_markov_is_defined_on_a_broken_schedule_but_cannot_bridge_it` exists so
> the stronger claim cannot creep back.

### 2. Five voters became twenty-four

Owner rule 2026-09, separating two questions that had been conflated: how many
PHILOSOPHIES the committee needs, and how big the ELECTORATE is. It needs enough
philosophies not to be a few formulas wearing human names — seven — and an
electorate big enough to be a state.

Why five was too small, arithmetically: one voter *was* 20% of the electorate, a
3-2 split was the narrowest possible majority, a "unanimous lock" meant five
perspectives agreeing, the entire look-at-everything position was one member, and
a new rating could only reach the committee through whichever member read it. At
twenty-four a team appears on 21 ballots or 14 or 8 — granularity 5/5, 4/5, 3/5
cannot express — and one idiosyncratic ballot can no longer throw a team ten seed
lines through the Borda count.

- **The 24 outlets are the OWNER'S OWN LIST** — call signs, mastheads, types and
  markets exactly as handed over. An agent drafted a roster of its own first and
  it was discarded: names are the owner's to pick, and that holds for a TV station
  as firmly as for a school. What this module chose is only which philosophy each
  outlet votes on, and its weights.
- **Seats per tendency** follow the owner's own shape (`TENDENCY_SEATS`): four
  voters each for the three frames a selection argument is actually fought over —
  record, schedule, margin — and three each for resume, network, form and
  consensus. 24 in all.
- **A market never casts one opinion twice.** Three outlets share Port Veles and
  two share four other markets; a city's paper, station and radio sit in three
  different tendencies, asserted at import. Ten of the twenty areas carry an
  outlet, weighted to the populous ones, which is how media markets fall.
- **Every market is a real Jefferson city**, verified against
  `data/jhsaa/schools.json` with its area recorded on the voter and pinned by
  `test_every_market_is_a_real_jefferson_city`.
- **A LOCK IS A SHARE, NEVER A COUNT** (`LOCK_SHARE` = 6/7 → **21 of 24**). At
  five voters a lock was literal unanimity, a fair reading of "every reasonable
  interpretation thinks this team belongs". With seven deliberately divergent
  philosophies unanimity is brittle — one specialist erases almost every lock —
  and 21 of 24 is stronger evidence in absolute terms than the old 5 of 5 while
  allowing three principled dissents. Written as the fraction so the bar tracks
  the roster: `lock_threshold(7) == 6`, `lock_threshold(5) == 5`.
- **A `Fringe` band** under the bubble (`bubble_threshold()`, 12 of 24 — the
  owner's "serious consideration" line). ‼️ It is a LABEL and never a cut: the
  spec's rule is that nothing pre-cuts the pool, so a team on one ballot is still
  scored by the Borda count. Pinned.
- **The `consensus` vector is DERIVED from `jhsaa_ratings.SYSTEMS`** (`_consensus`),
  so dropping Colley could not leave a stale hand-typed nine-tuple behind — which
  is exactly what the old Balancer was.
- **Thresholds are provisional.** The owner's own note: calibrate them from real
  seasons rather than choosing them now. They are two named constants.

### 3. What the page does with two dozen voters

- **The board reports a COUNT, not a column per voter.** Five member columns fitted
  beside nine system columns; twenty-four do not — 33 columns is the
  horizontal-scroll table this section's layout rules exist to prevent, and "on 21
  of 24 ballots" is the number the larger electorate was grown to produce anyway.
- **The ballots tab is grouped by tendency**, seven blocks of three or four
  columns, each column naming its outlet, market and beat, with the published
  weights in the tooltip. Seven arguments, not twenty-four parallel lists.
- ‼️ **THE ELECTORATE AND THE SYSTEM COLUMNS ARE THE ARCHIVED SEASON'S** (the `pi`
  rule, the same reason the seat count already was). A season selected by the
  original five renders with those five and their weights; a season rated with
  Colley renders a Colley column and a pre-Markov season renders none. Reading
  the module here would blank a retired column and print an empty new one across
  every season ever played, so `select` archives `voters`/`weights`/`lock_at` and
  `group_ratings` archives `systems`, and both views read from there.

### 4. Two readers the first pass missed, and why each failed silently

Both are the same rule — *the columns and the electorate are the archived
season's, never today's module* — and both were caught in review rather than by a
test, because neither raises.

**‼️ THE RESEARCH EXPORT IS A THIRD READER OF `SYSTEMS`.** The two web views were
fixed to read `ratings["systems"]`; `research_export.build_jhsaa` still iterated
`jhsaa_ratings.SYSTEMS`, so exporting any pre-Markov season **dropped its
`rank_colley` / `value_colley` and emitted empty `rank_markov` / `value_markov`
in their place**. The table stays exactly the right shape with the historical
data gone, which is the worst possible outcome for a file whose whole purpose is
analysis. Fixed by taking the union of the season's own layers' `systems` (module
order first, so a current season's header is byte-identical, then any retired
system the archive still carries) — a union, not a per-layer list, because `_csv`
derives its header from `rows[0]` and every row must carry every key. The
manifest sentence names the season's columns from that list instead of a typed
"(Colley, Bradley-Terry, …)". A layer with no `systems` key at all falls back to
the keys its own `ranks` carry — the same fact read off the data rather than the
header.
> **The lesson is the sweep, not the site.** When a module-level list becomes
> per-season, `grep` every importer of it. Three readers existed; the first pass
> found two, and the one it missed is the only one that writes a file the owner
> keeps.

**‼️ AN INTERSECTION WITH TODAY'S ROSTER IS NOT A FILTER, IT IS A DELETION.** The
committee view resolved its identities as *"the archived `voters`, else today's
`VOTERS`, then keep only those in `members`"*. On a selection archived before
`voters` existed, `members` holds the five ORIGINAL member names and the fallback
holds the twenty-four outlets — the intersection is **empty**, which emptied the
tendency list, and the ballots tab renders BY tendency, so the entire historical
tab went blank while the archive still held every ballot and every weight.
- Identities are now built **one row per archived member**, in `members` order:
  the archive's row if it has one, else `_voter_identity(name)` (today's roster
  when the name is still on it, otherwise the name alone with no tendency).
  Nothing is ever intersected away.
- The blocks are built in `_jh_ballot_groups`, not filtered in the template, and
  it emits **one trailing block for ballots whose tendency this build does not
  know**, labelled "The committee". A pre-outlets season therefore renders its
  five ballots in one group; verified by rendering both shapes (current: 7 groups,
  24 of 24 columns; legacy five: 1 group, 5 of 5).
- The page's own wording stopped claiming the roster too — the header says
  "N voters", not "Jefferson TV stations, newspapers and radio", because that
  sentence is false for a season selected before they existed.
> **A grouping is a chance to drop a row.** Whenever a view renders a list only
> through a grouping derived from today's constants, an archive that predates the
> grouping renders as nothing at all — so the grouping owes the ungrouped
> remainder a home, and the check is to render the old shape, not to read the code.

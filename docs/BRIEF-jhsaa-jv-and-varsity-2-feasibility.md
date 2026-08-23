# BRIEF — a JHSAA sub-varsity season (JV and Varsity 2): feasibility

**Status: INVESTIGATION ONLY. Nothing is built, no code changed, no tests written.**
This is a read on whether a concurrent JV / Varsity 2 season is worth doing, what it
would cost, and what the owner has to decide before anyone writes a line of it.

**Everything labelled MEASURED comes from the real 2038 save** (the research exports
`playtoclinchjhsaa2038boys` / `…girls`, 864 girls' and 780 boys' programs, 31,766
players, 21,419 duals, 446k line appearances). Numbers labelled GENERATED come from
`jhsaa.build_roster` on a synthetic world and are only used where the real save can't
answer the question. Numbers labelled PROJECTED are arithmetic on top of the real save,
clearly derived, not simulated.

---

## 1. The problem, measured

The proposal exists because lower-roster players produce almost no data. That is true,
and it is bigger than it looks.

**MEASURED — matches actually played in 2038, by roster rank** (rank = ordered by
matches played, so it is the effective usage order, not the seeded ladder):

| rank | 1–9 | 10 | 11 | 12 | 13 | 14–15 | 16–19 | 20+ |
|---|---|---|---|---|---|---|---|---|
| median matches (girls) | 25–28 | 18 | 12 | **4** | **3** | **2** | **1** | **0** |
| median matches (boys) | 24–27 | 17 | 12 | **4** | **3** | **2** | **1** | **0** |

**MEASURED — the whole-state picture:**

| | girls | boys |
|---|---|---|
| players | 16,564 | 15,202 |
| zero matches all season | 1,352 (8.2%) | 1,496 (9.8%) |
| 1–5 matches | 5,400 (32.6%) | 4,935 (32.5%) |
| **≤5 matches** | **6,752 (40.8%)** | **6,431 (42.3%)** |
| **seniors playing ≤5 in their final year** | **749 of 4,125 (18%)** | **741 of 3,852 (19%)** |
| players at ≤5 matches with `current_grade` ≥ 50 | 59 | 171 |

Two things stand out beyond the headline:

* **~750 seniors per gender reach the college recruit hand-off with essentially no
  résumé.** `graduating_class` writes `Prospect.jhsaa` off `ts.records`, so those
  players arrive on the board at 0-0 or 1-2.
* Zero-match players are not all filler. Their median `current_grade` is 30 (girls) /
  33 (boys) against a population median of 38 / 41 — but the **best zero-match player
  in the state grades 60 (girls) / 65 (boys)**. Real players are invisible.

This is the same hole `world.jhsaa_underplayed` (world.py:3840) already exists to
paper over, and the same one `_rest_count`'s comment (jhsaa.py:2207) says the
weak-opponent starter-resting rule was written as a substitute for.

---

## 2. Roster depth is the binding constraint, and the real save ≠ the design bands

The whole proposal is gated on one number: how many players a program actually has.
The regular-season 3S/4D format dresses **11 distinct players** (`lineup_need`), so:

* JV needs **11 + N** where N is the JV format's player count.
* If varsity keeps its bench — and `ROSTER_FLOOR = 12` exists specifically so it has
  one, and `_rest_count` / `_ROTATE_ONE` / `_ROTATE_TWO` need spare bodies to move —
  the threshold is **12 + N**.
* A three-squad program (V + V2 + JV) needs **11 + 2N**, or **12 + 2N** with a bench.

### ‼️ The real save's small classes run well ABOVE their design bands

**MEASURED (real 2038) vs GENERATED (`build_roster`, medians stable across years 0/13
and two salts):**

| class | `ROSTER_SIZE_BAND_BY_CLASS` | generated median | **real 2038 median (g/b)** | real min (g) |
|---|---|---|---|---|
| 9A | 20–24 | 22 | 22 / 22 | 14 |
| 8A | 20–24 | 22 | 20 / 22 | 12 |
| 7A | 19–22 | 20 | 19 / 21 | 12 |
| 6A | 19–22 | 20 | 20 / 20 | 14 |
| 5A | 18–20 | 19 | 18 / 18 | 13 |
| 4A | 18–20 | 19 | 18 / 18 | 12 |
| 3A | 17–19 | 18 | 17 / 18 | 12 |
| 2A | 15–17 | 16 | **18 / 17** | 13 |
| 1A | 14–16 | 15 | **19 / 19** | **15** |

1A and 2A are running **3–4 players deeper than the generator produces**, and 1A's
*minimum* (15) is above the generated median. The big classes are roughly on band.
The likely cause is the documented one — the transfer portal appends on top of a
roster without a check, and the owner reallocates talent by hand every offseason
(`ROSTER_SIZE_BAND_BY_CLASS`'s "no ceiling, deliberately" note) — but this brief does
not prove it, and it is **question 1** below.

**Why it matters:** it inverts the intuition. On generated rosters, JV would be a
9A/8A feature. On the real save, **1A can field a small JV more reliably than 4A can**
(1A rosters cluster tightly at 15–25; 4A has more programs but a longer thin tail).

---

## 3. Varsity 2 — how many programs would there actually be?

This is the question that was asked directly. **MEASURED, real 2038 rosters:**

| roster ≥ | statewide (g/b) | **9A/8A/7A only (g/b)** | by class, girls (9A→1A) | by class, boys |
|---|---|---|---|---|
| 24 | 100 / 103 | 66 / 71 | 26·21·19·13·5·4·5·3·4 | 26·30·15·15·5·6·4·2·0 |
| 25 | 66 / 77 | 47 / 59 | 19·13·15·7·2·2·4·2·2 | 23·22·14·9·2·5·1·1·0 |
| 26 | 45 / 55 | 37 / 40 | 15·11·11·2·1·2·2·1·0 | 14·17·9·8·1·4·1·1·0 |
| **27** (the proposed line) | **28 / 33** | **22 / 25** | 9·7·6·2·0·2·1·1·0 | 8·11·6·7·0·1·0·0·0 |
| 28 | 19 / 21 | 13 / 15 | 6·5·2·2·0·2·1·1·0 | 6·7·2·5·0·1·0·0·0 |
| 29 | 8 / 13 | 6 / 10 | 3·1·2·1·0·1·0·0·0 | 5·3·2·2·0·1·0·0·0 |
| **30** (three squads, each with a bench) | **3 / 8** | **3 / 8** | 1·1·1·0·0·0·0·0·0 | 5·2·1·0·0·0·0·0·0 |

**Answer: at 27+ restricted to 9A/8A/7A, 22 girls' and 25 boys' programs.**

That is a real but *thin* tier — roughly two dozen per gender, five to eleven per
classification. It is enough to be interesting and not enough to be a league. It is
also **fragile**: move the line to 28 and it halves (13/15); require a bench on each
of the three squads (30) and it collapses to **3 girls' / 8 boys' programs**, which is
not a tier at all.

### ‼️ The proposed 27 is benchless arithmetic

27 = 11 + 8 + 8 exactly, i.e. varsity dresses all eleven with nobody spare, and both
sub-varsity squads dress every player they have. Under that reading:

* varsity loses its bench entirely, so `_ROTATE_ONE` / `_ROTATE_TWO` (which is where
  ranks #12–#15 get their current 2–4 matches) and `_rest_count`'s weak-opponent
  resting both stop firing for exactly the programs that have the most depth;
* `_squad`'s short-side wrap (`r[i % len(r)]`) has no margin left — an absence has
  nowhere to come from.

So the honest thresholds are 27 (benchless, 22/25 programs) or 30 (one bench per
squad, 3/8 programs). Something in between — bench varsity only, run sub-varsity
benchless — puts it at 28: **13 girls' / 15 boys' programs**.

### Geography is not a problem

**MEASURED:** all 22 girls' and all 25 boys' V2-eligible programs sit in an *area*
that contains ≥4 programs from 3A/2A/1A. The small-class opponent pool is 271 girls' /
248 boys' programs. There is no shortage of opponents and no travel problem.

---

## 4. JV — format choice is the whole decision

A JV dual can only happen when **both** schools clear the threshold. Using the duals
actually played in 2038 (7,389 girls'/6,212 boys' district duals, plus 2,488/2,304
invitational):

**MEASURED — share of real league dates where both sides could field a JV:**

| JV format | players | thr (no bench) | % programs (g/b) | **% district duals (g/b)** | thr (+bench) | % district duals (g/b) |
|---|---|---|---|---|---|---|
| 1S/2D | 5 | 16 | 88 / 89 | **78 / 79** | 17 | 61 / 64 |
| 2S/2D | 6 | 17 | 77 / 79 | **61 / 64** | 18 | 43 / 51 |
| 3S/2D | 7 | 18 | 64 / 69 | **43 / 51** | 19 | 32 / 36 |
| **2S/3D** (the "2/3" proposal) | **8** | **19** | **54 / 56** | **32 / 36** | 20 | 21 / 25 |
| 1S/4D | 9 | 20 | 42 / 45 | 21 / 25 | 21 | 11 / 17 |
| 3S/4D (mirror varsity) | 11 | 22 | 22 / 25 | **7 / 9** | 23 | 4 / 5 |

Per-classification coverage at 2S/3D, girls: 9A 60% · 8A 49% · 7A 31% · 6A 38% ·
5A 21% · 4A 12% · 3A 12% · 2A 23% · 1A 40%. At 1S/2D: 9A 94% · 5A 74% · 3A 58% ·
1A 97%.

### PROJECTED payoff

Model: JV squad = ranks 12..11+N by ability; a JV dual is played wherever both sides
clear the threshold on a dual they really played; each JV player plays exactly one
line per JV dual. Baseline in brackets.

**girls** (baseline zero-match 8.2%, ≤5 matches 40.8%):

| JV format | bench | JV programs | JV duals | median JV matches/player | zero-match | ≤5 matches |
|---|---|---|---|---|---|---|
| 1S/2D | no | 759 | 7,729 | 21 | 4.7% | **19.7%** |
| 2S/2D | no | 668 | 6,028 | 18 | 4.0% | **18.2%** |
| 3S/2D | no | 556 | 4,291 | 16 | 3.5% | **18.6%** |
| **2S/3D** | no | 464 | 3,132 | 14 | 3.2% | **19.9%** |
| 2S/3D | yes | 363 | 2,065 | 11 | 3.7% | 24.6% |
| 3S/4D | no | 189 | 685 | 7 | 4.6% | 32.2% |

**boys** (baseline 9.8% / 42.3%):

| JV format | bench | JV programs | JV duals | median JV matches/player | zero-match | ≤5 matches |
|---|---|---|---|---|---|---|
| 1S/2D | no | 691 | 6,708 | 20 | 5.7% | **21.1%** |
| 2S/2D | no | 618 | 5,466 | 18 | 5.0% | **19.2%** |
| 3S/2D | no | 539 | 4,343 | 17 | 4.3% | **18.8%** |
| **2S/3D** | no | 440 | 3,056 | 14 | 4.2% | **20.5%** |
| 2S/3D | yes | 351 | 2,121 | 12 | 4.6% | 25.4% |
| 3S/4D | no | 194 | 759 | 8 | 5.5% | 36.2% |

**Reading:** every sensible format roughly **halves** the ≤5-match population
(41% → 18–21%) and cuts zero-match by half or better. The payoff is remarkably flat
between 1S/2D and 2S/3D — a bigger JV format reaches fewer programs but gives each
reached player more lines, and the two effects cancel. **The choice is therefore not
about data yield; it is about what a JV dual should look like.** Mirroring varsity at
3S/4D is the one option that clearly fails: 7–9% coverage and it barely moves the
number.

Note what none of them fix: **ranks #20+ still get nothing.** A JV of 8 covers
#12–#19; a 26-player roster still has six invisible players. JV moves the line down,
it does not remove it.

---

## 5. What is cheap (cheaper than expected)

**A JV/V2 team wants to be its own `TeamSeason`, not a flag on the varsity one.**
`play_dual` (jhsaa.py:2644) mutates the TeamSeason in place — `wins`/`losses`,
`points_for`/`points_against`, `records`, `matches`, `schedule`, and the district
counters. Give the JV its own `TeamSeason` over the same `School` and the tail of the
roster and **the record bifurcation is free by construction**: no varsity counter can
ever see a JV dual because it is a different object. The whole "don't pollute the
varsity record" worry collapses to two decisions — which TeamSeasons enter
`every_team` (that list is what feeds TOSS, awards, standings and the postseason), and
how the archive is filtered on read.

**The dual format is already data.** `DualFormat(n_singles=2, n_doubles=3,
doubles_team_point=False)` — five courts, odd, so no ties and no tie-break logic; high
school has no clinch anyway. `jhsaa.FLIGHT_WEIGHTS` already carries D3/D4.

**MEASURED cost.** One gender's season today is **146.6s / 12,271 duals** (the 19s in
`DESIGN-jhsaa-high-school-season.md:280` is badly stale — the rung is ~5 minutes for
both genders now, not 19 seconds). Per-dual: 3S/4D regular **10.44 ms**, 1S/4D state
9.93 ms, 5S/2D early 7.25 ms, and a prototyped **2S/3D at 8.25 ms**. At 2S/3D that is
~3,100 JV duals a gender ≈ **+26s/gender**, so the rung goes ~5 min → ~6 min. At
1S/2D it is ~7,700 duals ≈ +60s/gender. V2 adds ~25 programs × ~14 duals ≈ 350 duals,
which is noise.

**The calendar can be free.** If a JV dual takes its varsity dual's date — which is
what really happens; JV and varsity play the same afternoon — `jhsaa_match_dates`
looks the date up instead of packing a new round. **Zero extra rounds**, no pressure
on the fitted Oct-31 / Jun-7 window (`_JH_SEASON_CLOSE`), no risk of tripping
`_jh_pattern` into a denser day pattern.

---

## 6. What is expensive, and where the pollution actually lives

**The archive needs a `level` column, not a phase.** `world_jhsaa_dual`
(world.py:213) has no axis for this. A `"jv"` *phase* is the wrong shape: phase is the
archive's identity for an EVENT and it selects the dual format and the postseason
calendar lane, but JV plays inside `early` *and* `regular`. There is an `ALTER TABLE`
migration idiom already in place (world.py:264).

**‼️ `jh_match_key` will break silently.** It is `(phase, district, home, away)`
(world.py:4024). A JV dual against the same opponent in the same phase produces the
**identical key**, which puts a self-edge into `_jh_global_order`'s topological sort,
drives it into its cycle fallback, and quietly degrades the whole gender's display
calendar. Level has to be in the key.

**Reader surface — small, but it must be complete.** Four SQL readers of
`world_jhsaa_dual` (world.py:3888 `jhsaa_underplayed`, :3942 `_schedule_rows`, :4170
`jhsaa_match_dates`, :5037 `jhsaa_history_rows`) plus `research_export.py:62`; and
about eight in-memory `t.schedule` readers (`rating_duals` jhsaa.py:3156,
`_district_duals` :2998, `district_oowp` :3014, the non-district `spent` tally :4487,
`_flat_format_profile` :5015, `_last_opponent` :3699).

**‼️ The one that will bite silently:** `_jh_line_records` (web/state.py:3626) builds
every player's season record by **matching NAMES inside the archived `lines` of that
school's card**. Miss it and a JV player's record merges into the varsity player card
with no error anywhere — the same name-keying fragility already flagged for family
ties in CLAUDE.md.

**Two documented owner rules get superseded** and should be re-decided rather than
quietly contradicted:

* `ROSTER_SIZE_BAND_BY_CLASS` (jhsaa.py:193) says the bands are deep *because*
  "varsity AND a JV feeder blur into one deeper roster here, since the association has
  no separate JV system to model with."
* `_rest_count` (jhsaa.py:2207) says "Colorado's big programs field V2/V3 squads;
  everywhere else the same depth is exercised by coaches SITTING starters… **We do not
  model a V2**." That rule is the current stand-in for this whole proposal.

---

## 7. Varsity 2's real problem: it is not a school

Everything in this section of the app is keyed on a **unique school display name** —
`world_jhsaa_dual.school`, `run_season`'s teams dict, the routes, the pids, the
crest/mark lookup, `_jh_school_groups` (the postseason calendar lanes), `former_school`.
CLAUDE.md states it outright: a JHSAA display name IS the archive identity.

If a V2 plays a 3A varsity program, that dual lands on the 3A program's card naming an
opponent `load_schools` does not return. Consequences, all of which **degrade quietly
rather than raise**: the opponent's program page 404s, its crest renders blank, its
calendar lane is unknown, `jhsaa_group_ranking` and `_season_row` cannot resolve it.
Solvable — a `level` on the dual row plus a display convention ("Bishop Valera V2") —
but it touches more surfaces than the JV work does.

And the design question underneath it, which nobody can answer from the code:

* If the V2 dual **doesn't** count for the 3A team, that program has played a match
  that is not in its record — visible on its own schedule and absent from its ledger.
* If it **does** count, a non-program is inside the varsity results graph: `rating`
  needs a rating for it, `district_oowp` needs its win %, and the awards' two-pass
  opponent-quality rating (`jhsaa_awards.build_pool`) needs it in the pool.

Also worth noting: a 3A program already plays ~28 duals. V2 dates are **new** dates
for that program (unlike JV, which shares the varsity date), so they either eat the
`NONDISTRICT_MIN/MAX` 4–8 allowance or lengthen the card.

---

## 8. Open questions for the owner

1. **Why are 1A/2A rosters 3–4 deeper than their bands in the real save?** Hand
   transfers, as suspected? The entire feasibility picture rests on real depth, not
   on the bands, and it currently makes JV *more* viable at 1A than at 4A.
2. **JV format — coverage or fidelity?** 1S/2D reaches 78–79% of real league dates,
   2S/3D reaches 32–36%, and *they produce nearly the same data payoff* (≤5-match
   population 20% vs 20%). So this is purely a question of what a JV dual should look
   like on the page.
3. **Does varsity keep its bench?** Threshold 12+N instead of 11+N. It costs ~10
   points of coverage and it is what `_ROTATE_*` and `_rest_count` need to keep
   working.
4. **Is the JV squad fixed or porous?** If ranks 12–19 are locked into JV, varsity
   loses the bench rotation that currently gives #12–#15 their 2–4 matches. If it is
   porous (call-ups, which is what real life does), a player has both a varsity and a
   JV record and the clean two-object separation gets harder.
5. **V2 threshold:** 27 benchless (22 girls / 25 boys), 28 (13/15), or 30 with a bench
   per squad (3/8)? Or raise the roster bands to support it — noting the bands' own
   comment says they are deep *because* there is no JV.
6. **Does a 3A varsity team's dual against a 9A's Varsity 2 count on the 3A team's
   record and TOSS?** This determines whether V2 lives inside the varsity results
   graph or entirely outside it, and it is the single biggest structural fork.
7. **Does a V2 get a page** — a browsable entity with a schedule — or does it only
   ever appear as an opponent on other programs' cards?
8. **What happens to `jhsaa_underplayed`** (the transfer-portal board, world.py:3840)?
   It finds 9th/10th graders under 12 matches. If JV puts them at ~14, the board
   mostly empties. Keep it counting varsity appearances only?
9. **The college hand-off.** `graduating_class` writes `Prospect.jhsaa` from
   `ts.records`. A senior who only played JV would go to the recruit board at 0-0.
   Merge JV in, carry it as a separate line, or leave it? (~750 seniors a gender
   currently arrive with ≤5 matches, so this line is already thin.)
10. **Does the weak-opponent rest rule stay?** It exists explicitly as the substitute
    for not modelling a V2.

---

## Appendix — method

* Real-save figures: the two 2038 research exports, read directly
  (`programs.csv`, `players.csv`, `duals.csv`, `line_players.csv`,
  `jhsaa_standings.csv`). Match counts are `line_players.csv` rows per `player_id`,
  which is the same appearance-by-line basis `_jh_line_records` and
  `jhsaa_underplayed` use.
* Roster ability order is `players.csv` sorted by `current_grade` descending — the
  seed `jhsaa._order` starts from, before results move it.
* JV pair coverage counts **duals actually played** in that season with
  `phase in ("regular","early")`, not theoretical league pairings, so it reflects the
  real schedule including invitationals.
* Season timing and per-dual cost: `jhsaa.run_season("girls", 0)` on a throwaway DB,
  and a direct `play_dual` microbenchmark over 9A/8A teams with a prototyped
  `DualFormat(2, 3, False)`.
* Generated-roster comparisons: `jhsaa.build_roster` at world years 0 and 13 under two
  salts, to separate save-specific drift from year-to-year noise.
* The projection in §4 is arithmetic, not a simulation: it assumes a JV plays wherever
  both sides clear the threshold and that each JV player takes exactly one line per
  dual. It does not model JV rotation, call-ups, or a JV non-district card of its own,
  all of which would raise the numbers.

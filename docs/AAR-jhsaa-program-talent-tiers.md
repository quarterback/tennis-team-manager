# AAR — JHSAA program talent tiers, and the non-district draw that stopped matching on strength

**Owner rule 2026-09.** "There should be genuinely abysmal teams, and on a gradient."

## The problem, measured (2080 export)

The Scoreline Realism page put the association 32.8 from the Oregon reference, almost
all of it in two buckets: 6-0 sets were 4.1% of ours against 26.4% of Oregon's, 6-1
were 11.0% against 21.5%. Our distribution peaked at 6-4. Oregon is not the goal — it
is reference data — but the shape it shows is what real high-school tennis looks like:
mostly blowouts, with competitive tennis inside the matchups that deserve it.

Two things produced ours, and both had to change together.

**Generation.** Every program in a classification drew its players from ONE
distribution (`_TALENT`, a (mean, spread) per class). So a bad 7A and a good 7A were
the same 35-point ladder shifted a few points: rosters were internally very unequal
(best minus eleventh, median 35) but externally equal to each other (median team gap
in a dual, 4.2). Team-strength sd was 8.3 for boys, the weakest program in the state
averaged 33, and 71% of boys programs sat between 40 and 60. There was no bottom
tier — nobody was ever bad enough to be blown out.

**Scheduling.** `_nondistrict_pairs` scored candidates on geography PLUS
`|strength gap|`, then drew from the best few. Measured on 2080: early non-district
opponents had a strength correlation of .84 and a median top-11 gap of 2.3 OVR. The
draw was arranging for good teams to meet good teams and bad to meet bad. Holding
roster quality constant (top-11 of 50-55), the same team was a .312 side in 9A
against a 57.5-average schedule and a .747 side in 1A against a 45.1 one. A 16-15
record did not mean average talent; it meant average results against a schedule the
matcher had normalised.

Fixing generation alone would have created a real bottom and a real top and then
protected each from the other: the elite would draw the elite, the abysmal the
abysmal, records would compress toward .500 again, and the scoreline mix would barely
move. Generation had to become unequal AND the schedule had to stop scheduling the
inequality back out.

## What changed

### 1. Three layers, one scale (`jhsaa.py`, "PROGRAM TALENT TIERS")

| layer | what it is | what it moves |
|---|---|---|
| classification | the STRUCTURAL environment | roster SIZE and depth (`roster_size`) — nothing about ability |
| program tier | where THIS school sits, on one association-wide scale | the cohort's draw centre |
| cohort roll | year-to-year variation around that identity | ±`BAND_COHORT_JITTER` for a narrow tier; the whole range for a wide one |

The owner's point about the classification is the one to keep: a 9A can be terrible
and a 1A can be elite, schools play up and down all the time, so talent cannot key on
the class. What enrollment still buys is DEPTH — more draws — which is why a 1A dynasty
reads a few points under a 9A dynasty in team terms and why the tests are loose there.

The tier ladder (owner's own numbers, `DEFAULT_TIERS` as the fallback): abysmal 20-31,
poor 24-33, weak 29-41, developing 33-48, below average 37-51, average 42-55, solid
46-59, good 50-63, strong 54-68, very strong 58-71, power 59-73, elite 60-76, dynasty
62-79, plus three VOLATILE tiers (24-50, 39-60, 30-66) whose centre re-rolls per
freshman class. "The ranges within each tier themselves have a roll so it isn't so
predictive — the floor isn't absolute."

**Ranges are in TEAM terms** — the mean current OVR of the top eleven, the number the
owner reads off a program page — not the ceiling a player is drawn at. The two are far
apart (the career model shows a fraction of the ceiling; order statistics lift the best
of twelve draws; `generate_prospect` floors the ceiling at 24 and attributes at 20) and
the relation was measured, not asserted: at `BAND_PLAYER_SPREAD` 10, a ceiling centre of
20 makes a 29.5 team, 40 → 43.4, 60 → 58.8, 80 → 73.3. `_band_ceiling_centre` inverts
that line (slope .722, intercept 14.85). Re-measure with the calibration idiom in this
doc's history if the career model or the spread changes.

### 2. The tier is data (`data/jhsaa/talent_bands.json`, `/jhsaa/programs`)

The file holds the tier table (key, label, lo, hi, wide, weight) AND the per-program
assignment. Both are edited on the JHSAA programs page: a tier selector on the
program card (per-save override, the archetype route's shape — a key sets it, "none"
pins the rolled default, clear reverts to the seed), a bulk assign/remove that writes
the seed file, a third board ("Talent tiers") listing every program by its effective
tier, and a tier-table form that rewrites ranges, labels, the volatile flag and the
roll weight, or adds a row. "If I want to change a trajectory it doesn't require big
code changes" — nothing here does.

`scripts/roll_talent_bands.py` wrote every program's initial tier into the file
(`rolled_band`: seeded on the school name only, weighted by each tier's `weight` so
the middle is thick, blue bloods forced to elite/dynasty). The roll is deterministic,
so a school missing from the file generates exactly what the script would have
written — the file is the record, not a different answer.

`overrides.jhsaa_band_version()` fingerprints the override table AND the seed file's
mtime, and is in every cache key the archetype fingerprint is in (the season cache, the
cohort cache, the census, the gap bands). The tier is resolved ONCE per roster build in
`_program_mod` (`mod["band"]`) — never per seat (the fingerprint-in-a-loop trap).

### 3. Era-gated (`band_era`)

Players are rebuilt from seed, so an ungated change rewrites every archived roster.
`band_era()` is the `dev_era()` idiom: cohorts entering before it draw on `_TALENT`
byte for byte; a fresh save is all new; an existing save converges over one four-year
cycle. `tests/test_jhsaa_talent_shape.py` and the archetype class-ladder test pin the
PRE-era path through `legacy_talent_draw` — that model still generates legacy cohorts,
so its shape is still worth pinning.

### 4. The non-district draw scores on geography, not strength

`_nondistrict_pairs` no longer adds `|strength gap|` to the score. Geography (county,
area, anywhere), availability, and the same-or-adjacent-class gate remain — the gate
no longer protects strength, because the class no longer says anything about it.
District play, rivalries, the mid-season challenge and the showcase are untouched:
peer-matched play is what those are for. A school plays its neighbours, whoever they
are: top vs top is elite tennis, bad vs bad is competitive tennis at a low level, elite
vs bad is the 6-0 that was missing, and a 25-5 record now says something about who was
played rather than how hard the schedule was normalised to be.

## Measured on a fresh save (boys, 877 programs, 2030 rosters; girls in brackets)

| metric | before | after |
|---|---|---|
| team-strength sd | 8.1 (7.7) | 12.5 (12.9) |
| weakest program | 32.8 | 22.5 (22.9) |
| programs 40-60 | 72% | 56% (53%) |
| programs under 30 | 0 | 7% |
| programs 65 and over | ~5% | 12% |
| best minus eleventh, median | 36 | 25 |
| random-pair team gap, median | ~8 | 12.5 |
| random-pair team gap ≥ 20 | 10% | 28% |

Every tier's mean sits inside its range (abysmal 28.0, average 48.4, dynasty 70.9);
the abysmal floor is ~23 (see below). The flatter within-roster ladder is intended: a
bad program is now mostly bad players rather than one 60 carrying ten 25s.

500 random boys duals through the engine, same seed both ways (this is the
UNSCHEDULED mixture — the old matcher never produced random pairs, which is why the
2080 archive read 1.2% of duals at a 20-point gap):

| set | classification draw | tier draw |
|---|---|---|
| 6-0 | 5.5% | 8.9% |
| 6-1 | 13.1% | 16.3% |
| 6-2 | 17.7% | 18.6% |
| 6-3 | 22.1% | 20.1% |
| 6-4 | 21.2% | 19.1% |
| 7-5 | 10.1% | 8.8% |
| 7-6 | 10.3% | 8.2% |
| three-set matches | 35.8% | 28.5% |

The blowout share moved in the right direction and by a real amount; it is not yet
Oregon-shaped, and it will not get there on the roster alone — at these gaps the
per-point curve (`engine.fast.HS_PROFILE`) is the remaining lever. The tier weights
produce a boys sd around 12.5; the brief hoped for 15-18, the ends of the ladder are
thin by the owner's own weighting, and the weights are in the file.

## What to watch

- The **showcase** runs its own profile; read it separately.
- **`_strength`-matched features that should stay matched**: the mid-season challenge
  and recovery-round pairing still use strength — by design.
- The abysmal floor is ~23, not 20: `generate_prospect` floors a ceiling at 24 and an
  attribute at 20. Lowering those is a scale change, not a tier change.
- A stray star can turn up anywhere: the per-player nation elite spike in
  `generate_prospect` runs regardless of the ceiling passed in. One is a feature.

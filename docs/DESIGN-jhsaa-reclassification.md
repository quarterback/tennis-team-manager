# DESIGN — JHSAA reclassification (owner spec 2026-09)

Status: **specified, not built.** The rule below is the owner's, given verbatim in
its two blocks and then mapped onto the code. The dry run at the end is on the
2086 export with placeholder coefficients, so the owner can see the shape of a
first cycle before anything is written. Background and the survey of real-state
models: `docs/REPORT-jhsaa-reclassification-models.md`.

‼️ This SUPERSEDES the 2046 note in `docs/AAR-jhsaa-2046-expansion.md` ("classes
are curated history; moves are named and minimal, never cut-line rebands").
Owner, 2026-09: the map is theirs and a sort-and-cut reband is now the rule.

---

## The rule, as given

### GROUP / 1A RULE

Group membership is geographic.

At each four-year reclassification cycle:

1. Resolve Group-vs-A ladder membership before competitive reclassification.
2. Group eligibility is restricted to designated Group territory and
   specifically approved eastern expansion areas.
3. Do not allow arbitrary 1A schools to cross into the Group ladder based on
   competitive performance.
4. For the initial realignment, repatriate enough geographically coherent
   eastern 1A schools to bring 1A and the three Group classes into roughly
   comparable counts (~11-12 schools using the current population).
5. Prefer moving complete areas / coherent geographic clusters rather than
   selecting individual schools solely to hit a count.
6. Once Group-ladder membership is resolved, calculate effective_size for every
   Group school, sort once, and divide into three equal Group 1 / Group 2 /
   Group 3 bands.
7. Schools leaving the Group ladder re-enter the A ladder through the normal
   A-class classification process; do not hard-code Group 3 = 1A.
8. Run the geography pass every reclassification cycle. Normally it will
   produce no cross-ladder changes after the initial reset.
9. Boys and girls are always treated as one school for every classification
   and geographic move.

### JHSAA RECLASSIFICATION

Normal cadence: every 4 seasons; manual/off-cycle invocation also allowed.

Scope: pool all 9A, 8A, 7A, 6A, 5A programs; leave 4A and below outside this
pooled system.

For each school:

    effective_size = enrollment + success_adjustment - futility_adjustment

Inputs: enrollment; four-season cycle success points; four-season boys/girls
performance used for hardship/futility; adjustment coefficients stored in
configuration.

Then:

1. sort the complete 9A-5A pool by effective_size descending
2. divide the ordered pool into five nearly equal bands
3. assign those bands 9A, 8A, 7A, 6A, 5A
4. generate proposal; do not commit immediately
5. allow manual veto, redirect, or addition
6. commit accepted classification changes
7. record each move and its evidence in `jhsaa_reclass_moves`
8. run existing redistricting logic for every affected class
9. use the resulting map beginning with the next JHSAA season

‼️ There is NO one-class-per-cycle guard (owner, 2026-09). A school lands
where its effective size ranks, however far that is from where it was. An
earlier draft of this document carried one; it was an agent's addition, not
the owner's, and it is withdrawn.

Proposal UI must show: school · current class · enrollment · cycle success
points · hardship/futility figures · adjustment · effective size · pool rank ·
proposed class · resulting league · before/after class counts.

Overrides apply to the current cycle only by default and are re-evaluated at
the next four-year cycle.

History: archived seasons remain unchanged; program history records each
reclassification; a Realignments page lists cycle-by-cycle changes.

---

## Mapping onto the code

### What moves
A reclassification moves **`classification`** (and `group` with it, since a
fresh assignment has the two equal). In the band era that touches nothing about
ability — ceilings come from the program tier (`band_centre`) — only the
roster-depth band (`ROSTER_SIZE_BAND_BY_CLASS`) and which championship the
school enters. Play-up overrides (`group` only) sit on top as today. Archived
seasons carry the class they were played in and keep reading as played.

### Where it runs
A **`jhsaa_reclass` hold** on the world advance ladder, after the year rollover
and before the next week-0 JHSAA rung (the fall-portal pattern: the sim
proposes, the owner edits on a page, the commit is a separate step). The hold
fires when `season_year - last_cycle_year >= 4`, or when the owner presses
"Run reclassification now" on the page. Nothing is computed on a plain page
load; the proposal is built once per cycle and stored.

### The score (school-level, both genders)
From `jhsaa_program_history` over the cycle's four archived seasons:

- **success points** = sum over both genders of per-season finish points
  (champion 4, finalist 3, semifinalist 2, made State 1 — configuration).
- **win rate** = combined wins / (wins + losses) over both genders and all
  four seasons. A single-gender sponsor is scored on that gender.
- `success_adjustment = points × SUCCESS_PER_POINT`
- `futility_adjustment = max(0, FUTILITY_FLOOR - win_rate) × FUTILITY_PER_UNIT`

All three coefficients live in `worldconfig` (the region-mix idiom: editable on
the page, exported with the proposal). Defaults used in the dry run below:
`SUCCESS_PER_POINT = 40`, `FUTILITY_FLOOR = 0.35`, `FUTILITY_PER_UNIT = 3000`.

### The passes, in order
1. **Geography pass.** Group territory is a configured set of areas
   (`Kangas`, `Silver Basin`, `Bear River Country`, `Millersylvania`,
   `Snake River Plain`) plus the owner's approved eastern expansion areas. A
   ladder school inside Group territory is proposed INTO the Group ladder; a
   Group school outside it is proposed OUT, into the A ladder's normal
   classification. The initial-reset 1A repatriation moves whole areas/clusters
   from the approved list until 1A and the three Groups are comparable.
2. **A-ladder sort.** 9A-5A pool, `effective_size` descending, five near-equal
   bands.
3. **Group sort.** All Group schools after pass 1, three equal bands.
4. **Proposal**, stored; **commit** writes `jhsaa_reclass_moves` (year,
   school, from, to, enrollment, points, win rate, adjustment, effective size,
   rank, reason, overridden-by-owner), updates `schools.json` (the owner starts
   fresh saves from the seed file, so the seed is written too), and calls the
   redistricter (`scripts/jhsaa_redistrict.py`'s clustering, imported, never
   shelled) for every class whose membership changed.
5. `reset_schools()` + `reset_all()`; the next week-0 rung plays the new map.

### Surfaces
- `/jhsaa/reclassification` — the proposal table (columns as specified), class
  counts before/after at the top, coefficient inputs, veto/redirect/add per
  row, "Commit" and "Run now".
- Program page: a line per reclassification ("2091: 7A → 8A, 26 pts").
- History sub-rail: **Realignments**, one block per cycle.

### Tests to pin
- A school's boys and girls never land in different classes.
- Bands are equal ±1 after an unguarded cut.
- No 1A school crosses to the Group ladder except through the geography pass.
- Archived seasons are byte-identical before and after a commit.
- The proposal is deterministic for a given archive and coefficients.

---

## Dry run on the 2086 export (placeholder coefficients)

391 schools in the 9A-5A pool → bands of 79/78/78/78/78.
**190 moves** (100 up, 90 down); exactly one is enrollment-only.

Top of the up list (school, from → to, enrollment, points, win rate,
adjustment, effective size, pool rank):

| school | move | enr | pts | wr | adj | eff | rank |
|---|---|---:|---:|---:|---:|---:|---:|
| Baptist | 7A → 8A | 1516 | 26 | .94 | +1040 | 2556 | 51 |
| Chaminade | 6A → 7A | 1074 | 22 | .92 | +880 | 1954 | 131 |
| Pacific Gate | 8A → 9A | 2043 | 19 | .89 | +760 | 2803 | 15 |
| Canyonlands | 7A → 8A | 1361 | 19 | .82 | +760 | 2121 | 106 |
| Star City | 5A → 6A | 949 | 19 | .90 | +760 | 1709 | 164 |
| Oakhaven | 6A → 7A | 1299 | 18 | .90 | +720 | 2019 | 121 |

Top of the down list:

| school | move | enr | pts | wr | adj | eff | rank |
|---|---|---:|---:|---:|---:|---:|---:|
| River Oaks | 8A → 7A | 1996 | 0 | .07 | -826 | 1169 | 292 |
| Observatory | 7A → 6A | 1357 | 0 | .07 | -826 | 530 | 379 |
| Jacmel | 7A → 6A | 1527 | 0 | .08 | -795 | 731 | 362 |
| Esperanza | 9A → 8A | 2352 | 0 | .11 | -730 | 1621 | 191 |
| Tippecanoe | 9A → 8A | 2361 | 0 | .12 | -685 | 1675 | 172 |

Unguarded, the cut lands every school where it ranks: Baptist (rank 51) goes
7A → 9A and Observatory (rank 379) goes 7A → 5A, and the five classes come out
79 / 78 / 78 / 78 / 78 by construction.

### Geography pass, initial reset
- Ladder schools inside Group territory today: **Baptist (7A, Millersylvania),
  Mater Dei (9A, Silver Basin), Minnesota City (8A, Kangas)**. Under rule 2
  they move to the Group ladder (Group 1's band, 1066-2551, holds all three).
  All three are strong programs; the owner may want to name them as the
  exception rather than the rule.
- 1A today: 87 (girls' count). Group classes: 70 / 72 / 70. Eastern 1A
  clusters, by county:
  - Boise Frontier — 4 (Barlowe 3, Vance 1)
  - Blue Mountain Country — 9 (Umatilla 3, Morrow 2, Wallowa 2, Baker 1, Malheur 1)
  - Columbia Gorge — 8 (Klickitat 5, Gilliam 2, Wasco 1)
  - Juniper Highlands — 8 · Southern Jefferson — 8 (central/south, not eastern)
  Two coherent options for "~11-12": **Boise Frontier + Blue Mountain Country
  (13)** or **Boise Frontier + Columbia Gorge (12)**. Blue Mountain Country and
  Columbia Gorge are the 2052 Oregon affiliate leagues (Columbia Range League,
  Columbia Gorge District), so either option moves an intact league, which is
  what rule 5 asks for. The owner names the approved areas.

---

## Decisions still the owner's
- Coefficient values (the three above), and the finish-point prices.
- The approved eastern expansion areas for 1A repatriation, and whether the
  three big ladder schools inside Group territory cross or are named exceptions.
- Whether 4A-1A get any competitive movement at all (the spec leaves them out
  of the pool; play-up overrides remain available).

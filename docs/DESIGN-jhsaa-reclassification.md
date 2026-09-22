# DESIGN — JHSAA reclassification (owner spec 2026-09)

Status: **built (2026-09)** — `app/jhsaa_reclass.py`, `docs/AAR-jhsaa-reclassification.md`. The rule below is the owner's, given verbatim in
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
  (champion 6, finalist 4, semifinalist 2, made State 1 — configuration).
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
   Group school outside it is proposed OUT, into the A ladder's normal
   classification. Two owner join tables (2026-09) sit beside it: every ladder
   school in `GROUP_JOIN_AREAS` (Blue Mountain Country, Columbia Gorge) is
   proposed INTO the Groups whatever its class, and `GROUP_JOIN_SCHOOLS`
   (Canal View) names one-off joiners; both areas then count as territory.
   Otherwise ladder schools are NEVER proposed into the Groups on
   territory alone — the 2046 realignment moved the big programs out and they
   stay out; the only inbound path is the owner-approved 1A repatriation. The initial-reset 1A repatriation moves whole areas/clusters
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
- No A-ladder school crosses to the Groups except an approved 1A cluster under
  rule 4; Baptist, Mater Dei and Minnesota City never do.
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
- ‼️ **A-ladder schools inside Group territory STAY on the A ladder** (owner,
  2026-09). Baptist (7A, Millersylvania), Mater Dei (9A, Silver Basin) and
  Minnesota City (8A, Kangas) were moved OUT of the Groups by the 2046
  realignment and do not go back. The geography pass is one-directional for
  the A ladder: it never proposes a ladder school into the Groups on territory
  alone. Repatriation into the Groups is only the owner-approved 1A clusters
  under rule 4; a Group school outside Group territory may still be proposed
  out.
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

## 4A-1A: the second pool (owner, 2026-09: "need their own realignment")

The same rule, run as a **second pool after the geography pass**, sorted once
and cut into four near-equal bands. Nothing new is invented; three things are
different from the 9A-5A pool and each is a coefficient, not code.

- **Order of passes.** Geography first (the 1A repatriation trims 1A), then the
  4A-1A sort over what is left. Condotti Vanguard Academy and Romero-Finniski
  (class 3A, group 7A by decree) are owner placements and are excluded from
  the pool, as is any school with a live play-up override the owner wants kept.
  Otherwise a commit supersedes the seeded play-up flags inside the pool: the
  sort now does what play-up was manufactured to do.
- **Scale.** The big pool spans 806-2597 in enrollment (1,791); the small pool
  spans 58-798 (740). The same adjustment in raw enrollment units would move a
  1A school four classes. So the small pool's coefficients are the big pool's
  scaled by the span ratio (0.41 on the 2086 data): `SUCCESS_PER_POINT` 16.5
  and `FUTILITY_PER_UNIT` 1240, with the same `FUTILITY_FLOOR`. They are stored
  as their own configuration keys, so the owner can set them independently.
  The Group pool does NOT span-scale (owner rule 2026-09): its raw span is
  dominated by Group 1 (~1,500 wide against Group 2/3's ~340-640), so the span
  ratio produced a coefficient that barely moved anybody. Its default is the
  big pool's numbers × `GROUP_COEFF_SCALE` (1.5 — success 60/pt, futility
  4,500/unit at the defaults), still overridable per pool on the page.
- **What the sort means down here.** Small-school enrollment already overlaps
  across three classes (2A 86-361 against 1A 58-311), so enrollment barely
  orders the bottom of the pool and results do most of the ordering. That is
  the intended effect: a dominant 1A rises, a futile 3A sinks, and two ordinary
  schools of 130 and 250 stay roughly where they are.

### Dry run, 2086, Boise Frontier + Blue Mountain Country repatriated first
298 schools → bands of 75 / 75 / 74 / 74. **117 moves** (63 up, 54 down), one
enrollment-only.

| school | move | enr | pts | wr | adj | rank |
|---|---|---:|---:|---:|---:|---:|
| California Canyons | 3A → 4A | 399 | 26 | .95 | +429 | 19 |
| Banfield Day | 1A → 3A | 126 | 23 | .92 | +380 | 109 |
| San Lorenzo | 3A → 4A | 450 | 20 | .91 | +330 | 26 |
| Porterfield | 2A → 4A | 351 | 20 | .88 | +330 | 53 |
| Cassius | 1A → 3A | 70 | 20 | .87 | +330 | 140 |
| Sojourner Truth | 4A → 2A | 629 | 0 | .10 | -313 | 185 |
| Calvary Christian | 3A → 1A | 464 | 0 | .10 | -303 | 246 |
| Hawk Bar | 2A → 1A | 319 | 0 | .12 | -286 | 279 |

Eleven schools jump two classes, in both directions; that is the sort working
without a guard, and it is where the owner will judge the coefficient by eye.
Resulting enrollment bands overlap heavily (3A 70-786), which is expected once
results order the pool: the class name stops meaning size and starts meaning
level, which is the point of the exercise.

---

## Operating the coefficients (the page carries no help text)

The Coefficients fold on `/jhsaa/reclassification` needs nothing filled in: the
boxes hold the approved defaults. A BLANK 4A-1A box means that pool uses the
9A-5A numbers scaled to its own enrollment span; a BLANK Group box means the
9A-5A numbers × 1.5 (`GROUP_COEFF_SCALE` — never span-scaled, see Scale above).
The live derived value is what the proposal actually ran on and is shown in
each pool's panel heading. Run the proposal first; change a number
only if the tables read too aggressive or too timid, then Save to rebuild the
proposal on the new numbers. Group territory and the approved eastern areas are
the two area lists the geography pass reads.

## Decisions (owner, 2026-09 — all approved)
- Coefficients: the defaults above for both pools (`SUCCESS_PER_POINT` 40 /
  16.5, `FUTILITY_FLOOR` 0.35, `FUTILITY_PER_UNIT` 3000 / 1240), editable on
  the page.
- Approved eastern expansion areas for the initial 1A repatriation: **Boise
  Frontier and Blue Mountain Country** (13 schools, both intact leagues).
- No guard. Bands are equal by construction.
- Baptist, Mater Dei and Minnesota City never return to the Groups.
- **A Group school that wants back onto the A ladder is a manual ADDITION on
  the proposal page**, nothing more: the owner adds the row and the sort places
  it. Pacific Friends (Group 2, enrollment 814, 13 cycle points, .830) is the
  first: it lived on the A ladder before the merger that put it in the Groups,
  and the sort lands it in **6A**, one class above its enrollment, where it can
  play its traditional big-school rivals again. Rule 2 is untouched; no
  exception list is needed.
- 4A-1A run as the second pool as described.

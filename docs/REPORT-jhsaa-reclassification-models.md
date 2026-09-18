# REPORT — JHSAA reclassification: how it works now, what the data says, and the models real associations use

Owner ask (2026-09): moving programs across classifications is a hassle and no
reclassification has run in a long time. Three questions: is there a better way,
which files control it, and does the current balance work, with real-state models
for comparison. This is an assessment, written to be revisited; nothing here is
built. Data: the owner's 2083-2086 research exports (both genders) and the 2087
cold assessment.

---

## 0. Two words that mean different things in this repo

The confusion is mine to clear up: in conversation I said "class" for both of
these. They are separate fields on every school row and every `School` object.

| field | what it is | what reads it |
|---|---|---|
| `classification` | What the school **IS**: its size class, 9A down to 1A or Group 1-3. | Roster depth only (`ROSTER_SIZE_BAND_BY_CLASS` via `roster_size` and `_freshman_class_size`), the play-up gate (`can_play_up`), the transfer-clearing ladder (`CLEARING_LEVELS`), and the archive's per-season record of which class a season was played in. |
| `group` | The championship the program **ENTERS** this season: which league map it is drawn into, which State draw it plays, whose All-State it is picked for. | Leagues, the postseason ladder, State/Parastate tables, awards, the coefficient's within-class ranking. |

**Neither of them sets talent any more.** From `band_era()` on, a cohort's
ceilings are drawn around the program's TIER (`band_centre`, off
`data/jhsaa/talent_bands.json`, the owner-editable program bucket), on one
association-wide scale. Classification sets how many players a school fields
and nothing about how good they are. The per-class `_TALENT` table is the
pre-era path only (the `legacy_talent_draw` tests pin it), with one residual
that still reads it: the `upstart` lift scales off `_TALENT[(talent_group,
gender)]` as its baseline (`_program_mod`), so an upstart's size is still priced
by classification. That is a leftover, not a design. ‼️ The CLAUDE.md bullets
for `COMPETITIVE_MOVES` and the play-up section still say a program moved on
`classification` would be "generated with the weaker class's talent"; that was
true before the band era and is stale now.

Consequences for a reclassification design:

- A results-driven move (play up, play down) should still move **`group`**,
  because that is the thing a competitive move means: the school is the same
  size, fields the same roster, and competes in a different tournament. The
  plumbing for the upward half exists (`overrides.set_jhsaa_playup`, `plays_up`,
  `_compute_playup_league`, the `/jhsaa/programs` action bar); the downward
  half has a name (`COMPETITIVE_MOVES`) and no implementation.
- A **size** recut (section 4, point 7) can now move `classification` without
  touching anybody's ability. Its costs are roster depth (a 7A moved to 6A
  drops from the 19-22 band to the same 19-22 band, so most adjacent moves
  change nothing) and the archive, which records the class each season was
  played in and keeps reading as played. That makes a TSSAA-style equal-count
  recut far cheaper than it was in the `_TALENT` era.
- The program bucket is the strength lever, and the coefficient already feeds a
  suggested tier (`jhsaa.suggested_bands`). A success factor is the
  complementary lever: the tier says how good a program is, the factor says
  where a program that good should compete.

---

## 1. What controls it today

Headline: **there is no classification formula anywhere.** A school's
`classification` is inherited verbatim from prep-network's records, and
everything else is hand-typed tables and one-off transform scripts applied on
top of `data/jhsaa/schools.json`.

### `scripts/import_jhsaa.py` — the one authority for tables
- `GROUPS` (the twelve names), `champ_group()` (an identity fold now that 1A and 2A crown separately).
- One-way promotion cut lines: `PROMOTE_2A_ABOVE = 300` and `PROMOTE_ABOVE = {8A: 2148, 7A: 1638, 6A: 1323, 5A: 1022}` — a school moves at most one class per pass, upward only. They exist because 9A boys sat at 72 sponsors against `sponsor_floor`'s 76.
- `_CLASS_ENROLLMENT_BAND` — the committed per-class enrollment band. **Stale against the live file**: 8A's floor in the data is 378 (Bardsley County), 4A's floor is 520 against the table's 552.
- Named tables keyed on display name: `RECLASSIFY_TO_2A` (32 schools, the 2033 realignment, moves `classification` and `group`), `RECLASSIFY_2039`, `RECLASSIFY_2039B`, `OWNER_SIZES`, `OWNER_EMIT`. `reclassify()` runs them in a fixed order that matters (the 2A list runs after the cut line or its schools are promoted straight back).
- `PLAY_UP_MAX_GROUP = "4A"`, `PLAY_UP_COUNT`, `PLAY_UP_SEED`; `COMPETITIVE_MOVES = {}` (empty, read by nothing; the script meant to feed it does not exist); `RIVALRIES`.
- `draw_districts()` and `district_count()` (`DISTRICT_TARGET` 10, `MAX_DISTRICT` 12).

### The transform scripts (each writes `schools.json` in place, each `--dry-run`-able)
`jhsaa_reclassify.py` (applies the importer's tables to the committed file, rehomes movers into a league, asserts the rivalry invariant) · `jhsaa_redistrict.py` (redraws membership, count and names of the classes named on argv) · `jhsaa_columbia_to_1a.py` · `jhsaa_affiliate_leagues.py` · `jhsaa_border_realignment.py` · `jhsaa_sponsors.py` · `jhsaa_playup.py` · the 2046, 2052 and 2056 expansion/closure scripts · `jhsaa_heritage_valley.py` (the one computed re-band: sorts the 222 Group schools by enrollment and cuts into three bands of 74). The replay order after a re-import is stated only across docstrings and CLAUDE.md; there is no runbook.

### `app/jhsaa.py` — the runtime
`School.classification` / `group` / `talent_group` / `plays_up`; `can_play_up`, `valid_playup_target`, `plays_up()`, `_compute_playup_league` (a play-up joins a league, never creates one; size gates, geography orders). Every per-class table keys on `group` or `classification` and would need nothing for a `group` move: `STATE_FIELD`, `AT_LARGE_BIDS`, `WIDE_GROUPS`, `THREE_THREE_GROUPS`, `LEAGUE_SHAPE_GROUPS`, `PILOT_GROUPS`, `ROSTER_SIZE_BAND_BY_CLASS`, `_TALENT`, `CLEARING_LEVELS`, `_GROUP_IX`.

### `app/overrides.py` and `app/web/server.py`
Six JHSAA override kinds; **none is classification or group.** The only per-save
lever is `set_jhsaa_playup` (a target group or `"no"`, ladder only, 4A and
below, strictly upward, re-validated on read). `/editor/jhsaa-programs-bulk`
writes the SEED FILE for band, archetype and play-up. Changing `classification`
means editing `schools.json` by hand or by script.

### Why it is a hassle
Every move so far has been a new script with its own names, its own enrollment
re-seeding and its own guard. Nothing is periodic, nothing is rule-driven, and
the one downward mechanism is an empty dict.

---

## 2. What the data says about balance

### Class sizes are uneven, and that is a real problem
Sponsors by `classification`, 2086:

| class | boys | girls |
|---|---:|---:|
| 9A | 86 | 86 |
| 8A | 81 | 81 |
| 7A | 61 | 69 |
| 6A | 66 | 73 |
| 5A | 76 | 82 |
| 4A | 68 | 70 |
| 3A | 77 | 77 |
| 2A | 74 | 77 |
| 1A | 84 | 87 |
| Group 1 | 70 | 70 |
| Group 2 | 69 | 72 |
| Group 3 | 65 | 70 |

9A, 8A and 5A are 76-86; 7A and 6A are 61-73. All twelve play the same road
shape (the 76-sponsor floor for a 40-field class was the reason `PROMOTE_ABOVE`
exists), so a thin class is one where the road runs closer to the floor and the
State field is a larger share of the class. TSSAA's answer to this is to cut
classes by **equal school count** rather than fixed enrollment thresholds; the
importer's `_CLASS_ENROLLMENT_BAND` cuts are the opposite and were calibrated once.

### Enrollment does not predict strength, by design
The 2087 assessment measured classification versus top-11 roster strength at
+0.04 (boys) and +0.04 (girls). In 2086 the mean top-11 strength by class runs
46-53 in every class, with a within-class spread of 10-14, so the classes
overlap almost completely. That is the talent-tier era working as designed
(tier is a per-program property; enrollment is fixed fiction). **An
enrollment-driven reclassification therefore moves nobody for a reason that
matters to the court.**

### Concentration is the imbalance that exists
Titles won by the two most successful programs in each class, last 20 seasons
(2067-2086), and the number of distinct champions:

| class | boys top-2 / distinct | girls top-2 / distinct |
|---|---:|---:|
| 9A | 10 / 9 | 9 / 7 |
| 8A | 4 / 16 | 8 / 10 |
| 7A | 11 / 10 | 12 / 6 |
| 6A | 13 / 9 | 8 / 14 |
| 5A | 10 / 11 | 10 / 11 |
| 4A | 12 / 5 | 9 / 10 |
| 3A | 5 / 16 | 6 / 14 |
| 2A | 11 / 8 | 6 / 12 |
| 1A | 8 / 12 | 7 / 15 |
| Group 1 | 8 / 13 | 6 / 14 |
| Group 2 | 8 / 8 | 13 / 8 |
| Group 3 | 9 / 10 | 7 / 13 |

Boys' 4A has had five champions in twenty years. Runs over the last eight
seasons: Gagarin (4A boys) six titles and a final; Porterfield (2A boys) six
straight; Westfield Friends (5A boys) four titles and two finals; Baptist (7A)
four and two; Banfield Day (1A girls) the top résumé in the association.

At the other end, eight boys' and ten girls' programs have finished in the
bottom 15 percent of their class in each of the last six seasons (Tippecanoe 9A
boys: ranks 81, 83, 78, 80, 85, 80 of 86).

State outcomes match: 87.5 percent of 2087 champions were top-four seeds, lower
seeds won 18 percent, one-point duals 28 percent, down from 33 and 45 in 2079.

So the balance question is not "are the classes the right size by enrollment"
but "should dominance and futility move a program". Today they cannot: the only
mechanism is upward play-up for 4A-and-below, and nothing moves a program down.

---

## 3. Models real associations use

**Indiana — Tournament Success Factor (IHSAA Rule 2-5, since 2012).** Points
per round of the state tournament, accumulated over a two-year window. Six or
more points moves the program up one class; a program already moved that
scores one point or fewer moves back down (unless enrollment has since grown
into the class). Symmetric, results-only, needs no enrollment, and the IHSAA
reports fewer repeat champions and more first-time finalists since adoption.
[IHSAA TSF provisions](https://www.ihsaa.org/sites/default/files/documents/Tournament%20Success%20Factor.pdf) ·
[IHSAA TSF summary](https://ihsaapublic.blob.core.windows.net/portals/0/ihsaa/documents/Tournament%20Success%20Factor/Tournament%20Success%20Factor%20Provisions.pdf) ·
[Indiana's "Are We Punishing Success?" study](https://journals.indianapolis.iu.edu/index.php/sij/article/view/27047).

**Oregon — OSAA four-year time block plus a hardship play-down.** Six
classifications on fixed enrollment cutoffs, redrawn every four years after a
four-month public process (the 2026-30 block took 300 written submissions and
171 testimonies). Football adds a play-down rule: a program with an in-class
winning percentage of 22 percent or less over two years may petition down one
classification; Centennial and McKay used it in 2022, and the association then
had to deal with play-down programs winning the lower title (Siuslaw, 2021).
[OSAA 2026-30 classifications](https://www.osaa.org/today/article/4704/view?title=Classifications+and+districts+approved+for+2026-30) ·
[OSAA adopted plan (PDF)](https://www.osaa.org/docs/committees/classification/Board%20Adopted%2012152025.pdf) ·
[East Oregonian on the play-down rule](https://eastoregonian.com/2022/01/13/osaa-committee-considering-policy-to-make-football-teams-playing-down-a-classification-ineligible-for-postseason-play/).

**California — CIF Southern Section Competitive Equity.** No class moves at
all: playoff divisions are reseeded every year at the end of the regular season
from computer rankings. The commissioner reports far closer first-round scores.
It changes what a "division champion" means, which is why it fits a section
that has no state-shaped identity to protect.
[AJC survey of state models](https://www.ajc.com/sports/high-school/as-ghsa-considers-model-for-competitive-balance-heres-how-other-states-did-it/ZKXNYCENKFE33IKXFJJAX6GXUQ/).

**Texas — UIL biennial fixed cutoffs.** Six conferences on fixed enrollment
thresholds (2026-28: 6A 2,215+, 5A 1,305-2,214, 4A 550-1,304, 3A 246-549, 2A
105-245, 1A below 105), redrawn every two years, districts drawn by geography.
[UIL conference cutoffs](https://www.uiltexas.org/athletics/conference-cutoffs).

**Tennessee — TSSAA equal-count splits, per sport.** A four-year cycle; each
sport gets its own number of classes and each class is cut by **equal school
count**, not by threshold. Tennis is two classes. Public and independent schools
play in separate divisions.
[TSSAA classification cycle](https://tssaa.org/overview-of-the-classification-cycle).

**Washington — WIAA socioeconomic adjustment.** Enrollment is reduced for
schools whose direct-certification (poverty) rate exceeds the state average
before the cutoffs are applied, so a poor school of 1,300 may classify as 3A.
[WIAA 2024-28 numbers](https://www.west42sports.com/2024/01/21/wiaa-finalizes-2024-28-classification-cycle-official-numbers-and-classifications-released/) ·
[Seattle Times on the change](https://www.seattletimes.com/sports/high-school/wiaa-representative-assembly-votes-to-change-state-classification-system-use-free-and-reduced-cost-lunch-as-factor/).

**Alabama, Mississippi, Georgia — private-school multipliers.** AHSAA's
Competitive Balance Factor multiplies private enrollment by 1.35 and adds a
success component; Mississippi uses 1.5; Georgia counts out-of-zone students at
2.0 to 2.5. Massachusetts goes the other way and subtracts for high-needs
share. Nationally about twenty states use multipliers, eight use success
factors, nine use socioeconomic factors.
[AHSAA CBF (PDF)](https://www.ahsaa.com/Portals/0/PDF's/AHSAA/AHSAA/Re-Classification/2024-2026/CBF%20Updated%20April%202023.pdf) ·
[NFHS on competitive balance](https://www.nfhs.org/articles/states-continue-to-address-competitive-balance-of-schools/) ·
[Journal of Amateur Sport decade review](https://journals.ku.edu/jams/article/view/23974).

### Which of these fit this world
- Multipliers and socioeconomic adjustments solve a public-versus-private
  enrollment problem. Here `private` is a flag on 8 to 12 programs per class
  and the program tier already carries what a private school's advantage would
  be. The nearest equivalent in this world is a tier-aware "effective
  enrollment" (a Dynasty-tier school counted at 1.35x) feeding a size recut.
  It is coherent, since classification no longer touches ability, but it is a
  second way of saying what the success factor says with results.
- Equal-count splits (TSSAA) address the 7A/6A thinness directly. They change
  `classification` for dozens of schools at once, which in the band era costs
  only roster-depth bands and archive labels (section 0), so this is now a
  cheap cycle-boundary event rather than the ongoing mechanism.
- The success factor and the hardship play-down are the ones that fit: they
  read results the archive already holds, they move `group` only, they are
  symmetric, and they can run from a button.

---

## 4. Recommendation

> Superseded by the owner's spec: `docs/DESIGN-jhsaa-reclassification.md`.

Replace the pile of named tables with one periodic, rule-driven pass.

1. **A cycle, not a migration.** Every N seasons (OSAA's four is a good default),
   a single script or route computes the pass from `jhsaa_program_history`.
   The owner presses one button; nothing is typed.
2. **Success factor up (Indiana).** Points per postseason finish over the cycle,
   priced off the round names `jhsaa` already archives (champion 4, finalist 3,
   semifinalist 2, made State 1 is the sketch used in section 2). At or above a
   threshold the program's `group` moves up one class. Group 1-3 move within
   their own ladder; the 4A-and-below gate on play-up does not apply to a
   results move.
3. **Hardship down (Oregon).** A program under a win-rate floor in class over the
   cycle, or one moved up that scores at most one point, moves its `group` back
   down one class. A program never moves below its `classification`'s own
   ladder floor, and never more than one class per cycle.
4. **`group` only, never `classification`**, for a results move (section 0):
   it is a competitive placement, not a size change. Rivalries outrank
   everything, as today.
5. **Leagues follow.** Movers join a league of the new class through the
   existing placement (`_compute_playup_league` for one-offs; `jhsaa_redistrict.py`
   for a cycle that moves many), which already handles the floor and rebrands.
6. **Persist the cycle's decisions as one table**, written by the pass with the
   season it took effect and the points that justified it, so a player's page
   can say "moved up to 5A for 2091 (TSF 7)". `COMPETITIVE_MOVES` and the
   `RECLASSIFY_*` lists retire into it. Archived seasons keep reading as played.
7. **Separately and once**: re-cut the ladder's `classification` bands by equal
   count to fix 7A/6A, at a cycle boundary, with the band table regenerated
   rather than typed.

Open decisions for the owner before any of this is built: cycle length; the
point prices and the up threshold (Indiana's six over two years, scaled to this
world's four-plus rounds and a longer cycle); the down floor (Oregon's 22
percent); whether Group 1-3 and the A ladder run one rule or two; and whether
the JV and individual events count toward the factor (Indiana counts team
tournaments only).

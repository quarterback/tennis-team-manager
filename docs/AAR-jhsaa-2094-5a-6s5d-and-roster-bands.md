# AAR — 5A's 6S/5D format, and the roster bands re-cut for the JV ladder (JHSAA rule 2094)

Two changes, one rule, because one of them forced the other.

**5A plays 6 singles / 5 doubles** — eleven flights, **a sixteen-player lineup** — on its road to
State, in the State draw and in a 5A-hosted showcase. It is the widest format in the
association by two flights and the only one where singles outweigh doubles.

**`ROSTER_FLOOR` goes 16 → 20 and every band is re-cut**, because the JV ladder had
outgrown bands that were never resized for it, and because a sixteen-player lineup against a
floor of sixteen left a floor-sized program dressing its whole roster.

Everything else in 5A is untouched: the league season is still the universal 3S/4D, the
early window is still 5S/2D, the **TOC is still 1S/4D** (it fields every classification's
champion at one shape, the same carve-out every pilot gets), and the individual state
tournaments read no dual format at all. Membership in `SINGLES_FORWARD_GROUPS` is the
whole format change, exactly as `WIDE_GROUPS` was for 8A/9A in 2070.

## Where this came from

The 5A schools petitioned. The association's objection was roster capacity — whether 5A
programs carry enough players to fill a format that size — and that objection did not
survive the exports.

Measured across 2092-2094, both genders, 445 5A program-seasons:

| | |
|---|---|
| Smallest 5A roster on record | **16** (the floor; the band never produced less) |
| Median | 19 |
| 5A program-seasons short of 4S/5D's fourteen | **0.0%** |
| Distinct 5A programs that have already played 4S/5D in showcases | **55**, over 231 dual-sides |
| Of those, sides played by a program carrying ≤17 | 78 — several at exactly 16 |
| Sides that failed to fill the format | **0** |

So the capacity objection was already falsified by play the association had been running
for years: under "the wider format wins" a 5A team drawn against a wide-class showcase host
simply plays nine flights, and they always filled it. What 6S/5D asks that 4S/5D does not
is two more bodies, and the floor is what decides whether that is comfortable.

## ‼️ The petition was for the WEIGHTING, not the width

Worth recording because it is the thing a later reader will most likely "tidy" away. 5A
did not ask for more flights; it asked to be **the singles class**. At 6/11 flights this is
the only JHSAA shape where singles outweigh doubles — every other postseason format runs 20%
(1S/4D) to 50% (Group 2's 3S/3D) singles:

| Shape | Flights | Singles share | Who |
|---|---|---|---|
| 1S/4D | 5 | 20.0% | 2A, 3A, 4A, Group 3 |
| 2S/3D | 5 | 40.0% | 1A |
| 3S/4D | 7 | 42.9% | 6A |
| 4S/5D | 9 | 44.4% | 7A, 8A, 9A, Group 1 |
| 3S/3D | 6 | 50.0% | Group 2 |
| **6S/5D** | **11** | **54.5%** | **5A** |

`FLIGHT_WEIGHTS_6S5D` carries that through to what a flight is WORTH: singles take **500 of
the table's 895** (55.9%), spread over six flights against five. **S1 and D1 stay tied at
2.00**, as they are on the 4S/5D table — the petition asked 5A to be the singles class, not
for the No. 1 doubles flight to be devalued, and tying the top two is also what keeps
`_arrange_wide`'s eight-player search live instead of pinning the best player to S1.

‼️ **The total is ODD in hundredths, and that is deliberate.** FWS is weight
won over weight contested, so a dual comes back level exactly when one side holds half the
contested weight. An odd total puts half of it between two whole hundredths, out of reach of
any subset, so **FWS cannot tie on this format** whichever way the flights fall. Eleven
flights already prevents a tie on points; this prevents one on the weighted share. Re-pricing
any flight must preserve the odd total — `tests/test_jhsaa_lineup.py` asserts it exhaustively.

‼️ **Three other formats were mispriced the same way, and are fixed here.** 5S/2D (370),
2S/3D (350) and 4S/5D (750) all totalled EVEN and could return a level FWS — 4S/5D tied on
S1+S2+S3+D5. That was a pricing error rather than a design choice, so all three are corrected
to odd and the invariant now holds association-wide.

The shared base table serves **five** formats as subsets (1S/4D, 3S/4D, 5S/2D, 2S/3D, 3S/3D),
so parity cannot be fixed one format at a time — an edit moves several subsets at once. Three
flights is the provable minimum that makes all five odd: S2 is forced by the system, S3
follows it, and one of D3/S4/S5 must join them. The minimal choice moves each by a single
hundredth:

| flight | was | now | why |
|---|---|---|---|
| S2 | 0.75 | **0.74** | forced — 2S/3D parity cannot move without it |
| S3 | 0.25 | **0.26** | follows S2 to hold 3S/4D and 3S/3D odd |
| S4 | 0.10 | **0.11** | third flip for 5S/2D; also retires the S4 = S5 flat spot |
| 4S/5D D5 | 0.10 | **0.09** | its own table; the tail is the cheapest hundredth to spend |

Totals after: 1S/4D 285, 3S/4D 385, 5S/2D 371, 2S/3D 349, 3S/3D 375, 4S/5D 749, 6S/5D 895 —
all odd. No ordering changes anywhere.

‼️ **The rated share DOES move, by more than a first reading suggests.** An earlier draft of
this AAR said "no rated share moves by more than ~0.1%", which was wrong by about five times.
FWS divides by the contested TOTAL, so a one-hundredth change to a flight moves both the
numerator and the denominator, and the two do not cancel. Searching every possible set of
flights won, per format:

| format | largest FWS shift | on |
|---|---|---|
| **5S/2D** | **0.514 pp** | winning S3+S4 |
| 3S/3D | 0.267 pp | S1+S3 |
| 3S/4D | 0.260 pp | S2 |
| 2S/3D | 0.225 pp | S2 |
| 4S/5D | 0.132 pp | D5 |
| 1S/4D | 0.000 pp | unchanged |

Half a point of FWS on a single dual is small but it is not nothing, and it can reorder teams
that were close. That is the price of the invariant and it should be recorded honestly rather
than rounded away; the 2070 backtest's judgement about what a flight is WORTH is untouched,
but what a result is worth moved slightly everywhere except 1S/4D.

‼️ **Why a tie is not survivable here.** FWS is the association's anti-stacking signal —
weight declines down the lineup so that farming a lower flight buys less rating than winning
a higher one. A level FWS prices nothing, which is precisely the outcome a stacking program
would play for. The S4 = S5 flat spot was a milder version of the same fault: a rung where
the gradient was not actually applying.

A class that wanted width alone would have
asked for 4S/5D, which was on the table and is not what was petitioned for. If that table
is ever "corrected" to tie S1 and D1 like its siblings, the rule has been undone.

Eleven flights is odd, so a 6S/5D dual **cannot tie** and no tie-breaking logic is
reachable from it. High school has no clinch, so all eleven are always played.

## What did not need building

`_arrange_wide` is already the general form — "`_arrange_state`'s mechanism at ANY singles
width", pooling the top `n_singles + 2` and searching which `n_singles` play singles.
6S/5D pools eight and picks six; the eight below them pair into D2-D5. No new arrangement
logic, no new anti-stacking rule. The engine names slots dynamically (`f"S{i+1}"`), so
S5/S6 arrive free.

What did need writing: the `FORMATS` entry, the membership tuple, one `dual_format` branch,
the flight-weight table above, and an `"S6"` entry on the base `FLIGHT_WEIGHTS` so a
generic per-slot reader ranks a sixth singles flight below a fifth instead of taking the
bare 0.25 default — the same reason `"D5"` is on that table.

`jv_postseason_cut` moved on its own and that is correct: it is derived from `lineup_need`
rather than typed, precisely so it follows a pilot's shape. 5A's JV championship field now
freezes at #17 down instead of #12. The **JV league season's** cut does not move — `jv_pool`
is rank #12 down for every classification, staffed off the 3S/4D varsity eleven, and
nothing here touches it.

## The roster bands, and why the floor moved

The old floor of 16 was never an arbitrary number: it was **the varsity eleven plus the
five a JV dual needs** (`JV_FORMATS`' smallest entry, 1S/2D). Two things broke it at once.

**The JV ladder had grown and the bands had not.** `jv_format` is unbounded —
`D = (spare + 1) // 3`, `S = spare - 2D` — and reaches 6S/5D at sixteen spare. The bands
still reflected the ladder as it launched, so the bottom of the association was pinned at
the three-flight minimum, and **three bands had minima BELOW the floor** (1A 14, Group 3 14,
2A 15) — dead numbers the floor was silently overriding.

**5A's format now needs sixteen.** A floor-sized program would dress its entire roster with
nothing in reserve — the identical "no bench at all" failure the original floor of 12
existed to prevent, arriving by a different door.

| class | old | new | JV spare | JV format at min → max |
|---|---|---|---|---|
| 9A, 8A | (20, 24) | **(26, 30)** | 15-19 | 5S/5D → 7S/6D |
| Group 1 | (19, 22) | **(25, 29)** | 14-18 | 4S/5D → 6S/6D |
| 7A, 6A | (19, 22) | **(24, 28)** | 13-17 | 5S/4D → 5S/6D |
| Group 2 | (17, 20) | **(24, 28)** | 13-17 | 5S/4D → 5S/6D |
| 5A | (18, 20) | **(23, 26)** | 12-15 | 4S/4D → 5S/5D |
| 4A | (18, 20) | **(22, 24)** | 11-13 | 3S/4D → 5S/4D |
| 3A | (17, 19) | **(21, 24)** | 10-13 | 4S/3D → 5S/4D |
| 2A | (15, 17) | **(21, 23)** | 10-12 | 4S/3D → 4S/4D |
| Group 3 | (14, 17) | **(20, 23)** | 9-12 | 3S/3D → 4S/4D |
| 1A | (14, 16) | **(20, 22)** | 9-11 | 3S/3D → 3S/4D |

Every class now reaches at least 3S/3D on JV, every band minimum is at or above the floor,
and a floor-sized 5A program dresses sixteen with four spare.

Three notes a later reader will want:

- **‼️ 5A AND 4A NO LONGER SHARE A BAND.** They shared one entry from 2027-08. 5A dresses
  sixteen and 4A still dresses nine, so one number cannot serve both. Do not tidy them back
  onto one line.
- **The Groups were re-cut against the ladder classes, not the old enrolment blend.** Group 1
  runs to 2556 enrolment — the 9A end, not the 7A/6A middle the blend gave it — and Group 2
  moves to the 7A/6A band. Both are deeper than enrolment alone implies. That is the owner's
  call, not an oversight: the Groups are geographically distinct and carried for JV depth.
  The comment above `ROSTER_SIZE_BAND_BY_CLASS` still describes the original blend and should
  be read as history.
- **There is still no ceiling.** The bands are targets `_freshman_class_size` draws around,
  not caps, and the portal appends on top. Over-band rosters remain intended.

## ‼️ OPEN: what this does to an in-progress save (NOT resolved here)

`_freshman_class_size` seeds its roll on `(salt, school_key, entry_year)` but takes its
MEAN from `roster_size(classification)` — the band. The seed is stable; the target is
not. So raising a band re-rolls the size of **every** cohort the band touches, including
entry years that are already archived, and `build_roster` reconstructs all four grades on
every read. On an in-progress save that means sophomores, juniors and seniors who were
not there last season appear with no prior-season history, and current lineups and
results move under them.

This is the same mechanism as the 2027-08 band raise, which shipped unconditionally, and
the standing ruling on that class of change is the owner's: *"not worried about past
data, it was a small enough problem"* — forward-only, nothing rewrites archived duals.

**That ruling should not be assumed to carry here, because the magnitude is not
comparable.** Change in band midpoint, which is four times the per-grade mean:

| | mean | max | direction |
|---|---|---|---|
| 2027-08 raise | **+0.33** | +2.0 | mixed — 9A/8A/7A moved *down* |
| 2094 raise (this) | **+5.75** | +7.5 | every class up |

Roughly seventeen times the average movement, all one way, worth about **+1.4 players per
grade** on a typical program. A fresh world is unaffected — it has no archived cohorts —
so this only bites saves already in progress.

**Nothing was built for it.** There is no entry-year or save-era cutover in this
repository and inventing one was outside what this rule was asked to do: it would have to
interact with `_freshman_class_size`'s "rolled once per (school, entry_year)" contract
and with save-era state that does not exist yet. The options, for whoever picks this up:

1. **Accept it** and treat in-progress saves as re-based, the 2027-08 precedent applied
   to a much larger step. Cheapest, and wrong if anyone is mid-dynasty.
2. **Gate the band on entry year** — archived cohorts keep the old band, cohorts entering
   after the cutover use the new one. Correct, and the largest piece of work: it needs a
   per-save record of when the rule landed.
3. **Ship the floor now and phase the bands**, since only `ROSTER_FLOOR` 16 → 20 is
   strictly required for 5A's sixteen-player lineup; the band raise is the JV ladder's
   half of the rule and could follow on a cutover.

Until one is chosen, this rule is **safe on a new world and disruptive on an old one**.

## What was NOT changed, deliberately

**The regular season.** 5A's league format is still 3S/4D like everyone's, so `jv_pool` and
the JV league season are untouched. A version of this change that also moved the regular
season would cut the JV pool at sixteen and starve the JV season — worth stating because the
petition's own rationale was more kids playing, and that version delivers the opposite.

**The TOC.** Still 1S/4D for every champion including 5A's.

**Competitive balance.** No claim here rests on parity, sweep rates or one-point rates, and
none was used to justify the change.

## Caveats

- **No 6S/5D dual had ever been played** in any class in any archived season when this was
  decided. The capacity case rests on roster arithmetic and on 4S/5D play; the shape's own
  behaviour is unobserved until it runs.
- Only ten of the 231 5A dual-sides at 4S/5D were 5A-versus-5A; the rest were against larger
  classes in showcases. For "can they fill the format" that does not matter.
- The 2092 export keys ~1.9% of its `line_players` rows by name rather than id, which shows
  up as an apparent short count on 46 of 152,522 dual-sides. Keying artifacts, not shortfalls.
- `tests/test_jhsaa_lineup.py::test_maximize_never_scores_worse_than_traditional` fails both
  before and after this change — a pre-existing `_arrange_regular("maximize")` defect, not
  this rule's. Untouched here.

---

## Follow-on: the JV team postseason (JHSAA rule 2096)

Separate rule, recorded here because it lands on the same branch and shares the roster
reasoning. The JV Team State Tournament is rebuilt around qualifying rather than regional
championships.

**What changed.** Every JV team now enters one of **thirty** Regions instead of qualifying
out of a league; each Region is a **qualifying draw only** — it runs down to four and stops,
crowning nobody — and the 30 × 4 = **120 qualifiers** fill a 128-slot State draw. At-large
bids, the selection index and the league-berth rule are gone from the team event. The event
format moves **3S/2D → 3S/4D**, the association's universal league format: seven flights,
eleven players, still odd so a dual cannot draw.

**Why the regions moved.** The twenty geographic areas were wildly uneven — 2 teams in one
and 22 in another in 2095, an 11× spread — so a Region title cost one win in one place and
five in another, and champions out of the tiny regions were eliminated in the opening round
at State (mean place 28, against ~19 for champions out of the big ones). Thirty buckets of
comparable size is the fix, and comparable size is the entire requirement: `assign_regions`
orders the field geographically and deals it into thirty near-equal slices, so a bucket holds
schools that are mostly near each other without anybody claiming it is a place.

**‼️ The format is NOT gated on `ROSTER_FLOOR`.** 3S/4D needs eleven players below the
varsity eleven, and the floor of 20 only guarantees nine. That is deliberate: the floor is a
theoretical minimum the real save does not sit on, and holding the event at a depth nobody
actually fields would be defending a constraint that does not exist. The floor was NOT raised
for this.

**Round names are debate parlance** — R120, Triple Octafinals, Doubles Octafinals,
Octafinals, Quarterfinals, Semifinals, Final — because a 120-team bracket runs out of tennis
words three rounds early and debate has named draws this size for a century. JV only;
`world._round_label` still bands varsity as "Round of 32".

**Finishes follow the rounds.** A JV State exit is named for the round it happened in —
Triple Octafinalist, Doubles Octafinalist, Octafinalist — rather than banded off the alive
count, which would read "Round of 64" and "Round of 32" and tell a reader nothing about where
in a 120-team draw that is. Scoped to those three names, the same carve-out shape the
Parastate exit already uses, so **varsity keeps its own spelling**: a JV team is an
*Octafinalist*, a varsity team is an *Octofinalist*, and each event uses its own vocabulary.
Quarterfinals, Semifinals and the Final already band correctly and are deliberately not
overridden.

**Archives keep reading.** `jv_qualifying_era()` gates the new shape on the season, the same
idiom as `jv_parastate_era`, so seasons played at twenty and at thirty-six still render as
what they were. `jhsaa_jv_state.csv` keeps ONE schema across all three eras: `entry` reads
`qualifier` from 2096, `selection_index` is empty (nothing is selected), and the varsity
columns remain as context rather than as a criterion — that they were a criterion, at 70%
weight on a JV event, is what this rule removed.

---

## Two crashes and an orphan, found running 2096

**‼️ A DUAL CAN BE DECIDED BEFORE A SINGLES BALL IS STRUCK** (`engine/dual.py`). Doubles are
played first, and a format with as many doubles flights as its clinch is decided outright by a
doubles sweep: 3S/4D totals seven points, clinches at four, and has four doubles. `clinch_at`
was recorded only when a SINGLES court finished, so the first singles court took the
abandon-in-progress branch with no clinch time and `_partial_score` divided by `None`.

It is a latent engine bug, not a JV one — **1S/4D (clinch 3, four doubles) and 4S/5D (clinch 5,
five doubles) are both vulnerable too**, and only escape it because JHSAA varsity plays every
flight out and never abandons. It sat unreachable while the JV event was 3S/2D, which clinches
at three with two doubles. Fixed by seeding `clinch_at` to `0.0` when the doubles already
decided it: singles had not started, so every abandoned court scores (0, 0).

**An explicit era pin must win.** `run_jv_state(expanded=...)` names the 20- or 36-team shape on
purpose — a test, or a re-render of an archive — and was being silently upgraded to the
qualifying shape because a fresh save's era resolves to 0. Only an unpinned call consults the
era now.

**‼️ ONE IS NOT A DISTRICT, BY ANY ROUTE** (`_merge_orphan_districts`, `MIN_DISTRICT`). The
loader already moved a played-up school's league with it, and a rename that broke realignment
reapply was fixed separately, but neither covers a school the SEED DATA leaves alone. Seven
were on the 2095 save, in two shapes and **none of them realigned**:

| program | district | shape of the fault |
|---|---|---|
| Fort Paynes (2A) | Marble Valley League | league holds 18 — it is the only 2A member |
| Shasta (9A) | Valle Vista League | league holds 24 — only 9A member |
| New Casper (1A) | Hacienda League | league holds 9 — only 1A member |
| Morne Caribou (5A) | Kajaani League | league holds 9 — only 5A member |
| Ridgeline (3A) | Sky-Em League | league holds **one program statewide** |
| Bridger (Group 2) | PacWest League | one program statewide |
| San Vito (Group 2) | Vesterheim Athletic Association | one program statewide |

Both shapes read identically downstream — `districts()` returns a bucket of one, and in a double
round robin that is a program with no league season, no district record and no district place to
seed off — so both are fixed in one pass at load, after every other league assignment. The
school moves to the nearest league in its OWN championship group that is not itself orphaned:
same area, then same county, then the largest, name breaking ties, so a re-load reproduces it
and both genders land on the same map.

---

## Leagues become class-scoped entities (JHSAA rule 2096)

**A league's identity is its code; the name is cosmetic.** Every district is stored as
`"<code> <name>"` — `6A-1 Portland Interscholastic League`, the OSAA form — where the code is
the classification's short form plus the block number.

**What was wrong.** The name alone was the identity, and the bank was drawn per class from one
statewide list, so the SAME name came up in several classes: Gold Valley League existed in 9A,
7A, 3A and 1A as four separate leagues that anything grouping by name added into a 37-team one.
Del Rey Athletic Association read as 52 programs across five classes. The leagues were already
class-confined competitively — `district_count` cuts each class's pool on its own — so this was
never a scheduling fault. It was a naming collision that made the renderer lie.

**‼️ AND NO NAME REPEATS ANYWHERE.** The code disambiguates a league for the ENGINE; it does
not stop two leagues reading as the same league to a person, and the owner's requirement is that
they not. `league_names` now carries its used names AND used leading words across every class in
one `taken` dict, threaded from the single `for g in GROUPS` loop rather than held module-global,
so a rebuild stays a pure function of its inputs. **This is the reason the bank was expanded**:
907 candidates with 900 distinct names and 191 distinct leading words against 96 leagues, so both
constraints hold globally with headroom and the fall-through to a numbered District stays
unreachable. Drawn on the real 2095 pools: 96 leagues, 96 distinct names, 96 distinct leading
words, zero fall-throughs, every league 9-10 teams.

Boys and girls share the code as they share the name — a league belongs to the SCHOOL. OSAA
renumbers when it moves the geography and so does this.

**The band is 8-11, with a hard floor.** `MAX_DISTRICT` 12 → 11, `DISTRICT_TARGET` 10 → 9.5,
and a new `MIN_DISTRICT_SIZE` of 8 clamps the block count so no block can come out under it.
The draw had a cap and no floor, which is how seven one-team districts reached the 2095 save —
a ragged remainder or a realignment that empties a league had nothing to catch it. Every class
in both genders now lands at 9-10.

**`DISTRICT_DUAL_CAP` 18 → 16**, so a league card is 14-16 duals instead of 10-to-18.

**‼️ The non-league allowance becomes a BACKFILL.** It was 4-8 drawn at random on top of
whatever the league gave you, with a comment arguing that "a fixed season total would force
wildly different non-league loads on schools of different districts". That was true at 6-13
league sizes. At 8-11 it is not: `nondistrict_quota` tops every program up to
`SEASON_DUAL_TARGET` (22), so an 8-team league plays 14 + 8 and a 10-team league plays 16 + 6,
and a program in a short league gets its gap filled instead of simply playing a shorter season.
The 4-8 band still clamps the top-up so a pathological league cannot demand a twelve-dual
non-league card.

**Name pool**: the owner's 114 stems × 7 suffixes are APPENDED to the 109 authored names rather
than substituted. ‼️ THAT DOES NOT PRESERVE EXISTING LEAGUE NAMES and an earlier draft of this
AAR wrongly said it did: `league_names` shuffles the whole bank, so growing it from 109 to 907
reorders the walk and nearly every pick changes. A re-import therefore RENAMES most leagues, not
just adds a code to them. That is accepted — the owner's rule is that leagues are not preserved
across a realignment, which is already how the redraws behave, and OSAA renames when it moves the
geography. Recorded because the previous wording would have had somebody treat a rename as a bug. 798 new candidates against ~100
leagues is the headroom that lets `league_names` keep leading words distinct within a class
without ever falling through to "District 7". No area affinity is carried on them — with the
code as identity, flavour is all a name has to carry.

**The runtime redraw is synced too.** `data/jhsaa/districting.json` is the app's copy of the
importer's constants and bank (the app cannot read `scripts/`), and it held the old 12/10 rules
and the 109-name bank — so an offseason class redraw would have drawn on different rules from a
fresh import. Worse, `districting_config` parsed the target with `int()`, which would have turned
9.5 into 9 silently. Both fixed, plus `min_district_size` carried across, and
`district_count` verified identical between importer and runtime for every pool size 0-200.

**And `redistrict` now claims names statewide.** Its `taken`/`heads` were scoped to the class
being redrawn, so an offseason redraw could hand 3A a name 9A already holds — drawn
independently, the current pools yield only 71 distinct names for 95 leagues. The foreign claim
set is derived from `rows`, which already holds the whole state, rather than threaded in as a
parameter: `redistrict` is the single door all six redraw scripts come through, so deriving it
there fixes every caller without touching any of them. A name the class is RETIRING is excluded
from the foreign set, so it stays available to the class giving it up.

**‼️ THIS NEEDS A RE-IMPORT TO TAKE EFFECT.** League membership and names live in
`data/jhsaa/schools.json`, written by `scripts/import_jhsaa.py`. Nothing changes in a save until
that is re-run, and re-running it relabels every league in every archive — the codes are new
strings. `_merge_orphan_districts` stays as the load-time backstop for any save that has not
been re-imported.

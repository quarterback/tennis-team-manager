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

`FLIGHT_WEIGHTS_6S5D` carries that through to what a flight is WORTH: **S1 is priced above
D1** (2.00 vs 1.50) where every other table in the association ties them, and the six
singles seats carry 65% of the format's weight. A class that wanted width alone would have
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

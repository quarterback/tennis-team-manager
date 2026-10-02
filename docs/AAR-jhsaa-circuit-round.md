# AAR — the Circuit round (owner rule 2026-10)

Code: `app/jhsaa.py` (`CIRCUIT_GROUPS`, `circuit`, `circuit_era`, `deal_contiguous`,
`circuit_field`, `deal_circuits`, `_circuit_stage`, the Circuit branch of
`_recovery`, `recovery_shape`, `state_field_size`), `app/world.py` (archive key,
finish walk, season row, title board, road ladder), `app/web/state.py` (chip, seeds,
bracket stage fold), `app/web/templates/jhsaa_school.html` (heading),
`app/jhsaa_coefficient.py` (price), `app/jhsaa_jv_state.py` (the dealer, shared),
`tests/conftest.py`, `tests/test_jhsaa_circuit.py`.

## What the Circuit is

In a Circuit class, from `circuit_era()` — **Group 1, Group 2, Group 3, 10B, 11B and
1A through 4A** by owner default — the two recovery rounds that used to be Super
Regionals (16 Regional losers paired high-low) and Semi-State (the 8 Super Regional
winners plus the 8 Zonal losers) are ONE stage played in two rounds over a **field
of 32**:

- the 24 already in recovery — the 16 Regional losers and the 8 Zonal losers —
  **plus the next 8 on seeding ATR** from the rest of the class, with the Zonal
  champions and anyone already admitted excluded (`circuit_field`). A district
  champion holds a protected Regionals seat, so it is either a Zonal champion or
  already in the 24; nothing is pulled in or swapped to force geography;
- the 32 dealt into **eight Circuits of four by where the programs are** — sorted on
  area, county, city, name and dealt four at a time (`deal_contiguous`, the JV
  Region dealer generalised to a bucket count; `assign_regions` now calls it). A
  Circuit of three is rejected: a thin pool is cut to a multiple of four by
  dropping its weakest, never padded;
- in each Circuit, two semifinals (**1 v 4 and 2 v 3 on seeding ATR within the
  Circuit**) and a final. **The semifinals keep the Super Regionals name, heading
  and calendar lane** (owner: "super regionals is accurate and works" — the
  composition changed, the nomenclature did not); **the finals are the Circuit
  round** (`CIRCUIT_PHASE`, in Semi-State's lane, chipped CIRCUIT). Sixteen
  semifinal duals then eight finals, 24 duals over two rounds, every one a
  numbered unit — the semifinals count on as "Super Regional N", the finals are
  **"Circuit 1" to "Circuit 8"**;
- the eight winners are **Circuit Champions**: a State berth with no bye and no
  Zonal privilege (a Circuit champion is never seeded 1-8), recorded as a title of
  its own — the unit honour "Circuit N" in Roman numerals on `unit_wins`, a
  "<class> Circuit Champion" team honour on the season row and the school page,
  and a CIRC column on the title board — never a State title.

Everything else on the road is untouched: Areas, Sectionals, Wards, Regionals,
Zonals, the Epiregional, the seeding, the Divisionals and below, the Challengers
and Specials, the TOC and its Qualifier, JV, All-State and Individual State.
Semi-State does not convene in a Circuit class; its arc keeps the "did not
convene" shape so every reader keeps reading.

## Where the losers go

The Circuit stands exactly where the two rounds it replaces stood, so the tail
below needed no new rule: the **final losers** stand where Semi-State losers stood
and the **semifinal losers** where Super Regional losers stood. The Divisionals
still take half of each, half and half; the orphans still walk into the
Semi-Conference pool ahead of the Ward losers; the Conference and the Specials
still fill whatever is outstanding. A 32-field class is therefore still 8 Zonal +
8 Circuit + 8 Divisional + 8 Specials.

## The pilot classes

A 16-team State pilot class on the Circuit (`sixteen_state` and `circuit` both
true) **grows to a 24-team State** (`CIRCUIT_PILOT_FIELD`): the 8 Zonal champions,
the 8 Circuit champions and the last 8 through the SAME tail a 24-field class (1A,
10B, 11B) already runs — 4 Divisional berths and 4 through the Specials. The
pilot's early return in `_recovery` and its 16-team draw in `run_season` are
skipped for such a class (`pilot = sixteen_state(...) and not circ`), so it plays
the ordinary 24 draw with its eight single byes. The committee still selects
nothing for it (`at_large_bids` keeps answering 0 off `sixteen_state`), and the
Metastate and Parastate still do not run. No new draw shape was invented.

## The switch

`circuit(group, year)` is membership in an explicit tuple AND
`year >= circuit_era()` — the `sixteen_state` idiom exactly. `circuit_era` is an
`ERA_SETTINGS` entry (`jhsaa_circuit_era`): the first unplayed season, 0 on a
fresh save, pinnable through `worldconfig`. Every shape question goes through it:
`state_field_size`, `recovery_shape`, `_recovery`, the season memo key. The
tests' conftest replaces the resolver (`_circuit_off`) so every other suite keeps
the standing pair on its season-2027 fixture; `tests/test_jhsaa_circuit.py` swaps
it back.

## The archive

One new key per group, `circuit` — the finals in `_recovery_round`'s shape
(`field`, one round, `survivors`, `round_names`) plus `circuits`, the eight
Circuits in seed order. The `super_regional` arc carries the same `circuits` list
and every semifinal game carries its `circuit` index. Seasons archived before the
key `.get` it; a non-Circuit class archives the "did not convene" shape. The
finish walk (`jhsaa_postseason_result`) tries the Circuit between the Divisionals
and the Super Regionals; `jh_road_ladder` ranks it there too; `_JH_STAGE_KEYS`
credits its units; the research export's road keys price it.

## The coefficient

`road_points()[CIRCUIT_NAME] = 0.25` — Semi-State's price, below Regionals (0.5),
in line with the halved schedule: recovery stays priced under the rung it is a
second chance at, and a Circuit title is a berth, so banking one takes a program
out of the "missed State" comparison exactly as a Semi-State title did.

## Measured on the smoke season

The owner's model (2100-2106, not engine output) expected every class sector to
carry a State team in about 72% of class seasons, against about 43% for the old
two rounds, and the best 8 of the 32 on rating to win their Circuit about 4.6 of 8
times, against about 6.0 for the old rounds.

Real engine figures, one scaled season, both genders, 1A / Group 2 / Group 3 /
10B / 11B (the owner's five), each sized to fill Wards and the Circuit's 32:

| Gender | Class | Areas with a State team | Top 8 of the 32 that won their Circuit | State field |
|---|---|---|---|---|
| girls | 1A | 10 of 12 | 4 of 8 | 24 |
| girls | Group 2 | 5 of 5 | 5 of 8 | 36 |
| girls | Group 3 | 4 of 5 | 6 of 8 | 24 |
| girls | 10B | 10 of 15 | 5 of 8 | 24 |
| girls | 11B | 11 of 17 | 4 of 8 | 24 |
| boys | 1A | 10 of 12 | 5 of 8 | 24 |
| boys | Group 2 | 5 of 5 | 6 of 8 | 36 |
| boys | Group 3 | 4 of 5 | 7 of 8 | 24 |
| boys | 10B | 11 of 15 | 5 of 8 | 24 |
| boys | 11B | 11 of 17 | 6 of 8 | 24 |

Overall: areas with a State team 81 of 108 (75%); the top 8 of the 32 won their Circuit 5.30 of 8 times on average over 10 class-seasons.

Group 2's 36 is the post-Metastate field (its 32-team road plus the four meta
winners); 1A and Group 3 crown from the Circuit's 24, 10B and 11B from their own 24.
Against the owner's model: area coverage 75% (model ~72%, old rounds ~43%); the
top 8 of the 32 won their Circuit 5.3 of 8 (model ~4.6, old rounds ~6.0) — the
Circuit spreads State across the map as intended and still lets most of the best
eight through, a little more than the model projected on one scaled season.

"Sector" is read as the JHSAA area; the top-8 ranking is a proxy off the archived
TOSS and the final record (the live seeding ATR is z-blended on the pre-Circuit
record and is not archived). One season is a shape check, not a calibration —
re-measure on the owner's exports once a few Circuit seasons exist.

## Lessons

- **Keep the owner's nomenclature when it is accurate.** The brief said "replace
  Super Regionals"; the owner overruled it: the semifinals ARE Super Regionals in
  every sense but composition, and renaming them "Circuit Semifinals" would have
  retired a round the association still plays. Only the round that stopped
  existing (Semi-State) got the new name.
- **A stage that stands in another's place inherits its exits.** Routing the
  final losers to Semi-State's slot and the semifinal losers to Super Regionals'
  meant the Divisionals, the Semi-Conference pool, the Conference and the Specials
  needed no change at all — and a 24-field class on the Circuit got its tail for
  free, which is what "find how 10B and 11B build their 24 and reuse that path"
  asked for.
- **A test fixture that loops `GROUPS` cannot see a Non-Public class.** 10B and
  11B are road classes outside `GROUPS`; the fixture loops `GROUPS +
  NONPUBLIC_GROUPS` and switches the split on, or the smoke silently covers three
  of the five classes the owner named.

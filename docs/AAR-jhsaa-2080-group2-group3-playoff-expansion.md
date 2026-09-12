# AAR — the 2080 playoff expansion: Group 2 to 40, Group 3 to 32

**Owner rule 2026-09, for the 2080 season of the lab save.** Heading into 2080 the
JHSAA expanded the last two classes that were not on a full at-large structure:

| class | before (2076-2079) | from 2080 | shape borrowed from |
|---|---|---|---|
| **Group 2** | 32, road only — the ONE class with no committee | **40 = 32 road + 8 at-large** | 7A, 6A, 5A, 4A, 3A, 2A |
| **Group 3** | 28 = 24 road + 4 at-large — the ONE four-bid class | **32 = 24 road + 8 at-large** | 1A |

The owner's instruction was to use "the structure the other classes that use
32/40 respectively" as the guide, and that is exactly what happened: nothing new
was designed. Every class in the association is now a Parastate class.

## What changed

Two entries in one table — `jhsaa.AT_LARGE_BIDS` gained `"Group 2": 8` and
`"Group 3"` went from 4 to 8. That is the whole code change, and it is the
whole code change because every earlier expansion was built to make it so:

- `ATLARGE_GROUPS` is `tuple(AT_LARGE_BIDS)`, so the committee page's group
  switcher, the season loop's `if group in ATLARGE_GROUPS` branch and the
  research export's `jhsaa_committee.json` all pick the two classes up with
  no edit.
- `run_state_parastate(byes=road − bids)` sizes the opening round off the
  two tables: Group 2 gets 7A's 8-dual Parastate (25v40 … 32v33, seeds 1-24
  bye), Group 3 gets 1A's (17v32 … 24v25, seeds 1-16 bye).
- `STATE_FIELD` is UNTOUCHED — Group 2's road still qualifies 32 and Group 3's
  24. The road ladder (`_recovery`, the Specials, the Challengers, the
  Epiregional) runs exactly as it did; the bid count is the decision and the
  field size is the consequence, as the 2026-09 AAR put it.
- `parastate_summary()` / `parastate_blurb()` are derived from the tables, so
  every surface that describes the committee reads the new shape: "7A, 6A,
  5A, 4A, 3A, 2A and Group 2 at 40 (32 road + 8); 1A and Group 3 at 32 (24
  road + 8)".
- The import-time assertion `bids <= state_field_size(g)` holds for both
  (8 ≤ 32, 8 ≤ 24).

The rest of the diff is prose: the header comment on the bid table, the
committee view's docstring, the export manifest's comment, CLAUDE.md and the
pinned test (`test_the_bid_table_and_the_committee_seat_count_agree`), which
now asserts `set(ATLARGE_GROUPS) == set(GROUPS)` and the two new field sizes.

## Group 2's Parastate plays 3S/3D — and it needed nothing

Group 2 is the one class whose road plays an EVEN shape (`THREE_THREE_GROUPS`,
JHSAA rule 2026-09), so it is the first Parastate whose duals can come up
level. That was checked before deciding it needed no code:

- The Parastate is phase `"state"` (it is part of State, not a road stage).
- `play_dual` gates the three deciding tiebreakers (S1, D1, D2, best two of
  three, `_deciding_tiebreaks`) on `phase in POSTSEASON`, not on a round name.

So a level Parastate dual is settled exactly like a level Sectional or a level
State quarterfinal, and the deciders archive on their own `tiebreak` key the
same way. The format axis (`THREE_THREE_GROUPS`, `WIDE_GROUPS`,
`LEAGUE_SHAPE_GROUPS`) and the field axis (`AT_LARGE_BIDS`, `STATE_FIELD`) stay
separate, and the test pins that Group 2's state shape is still `state_3s3d`
after the expansion.

## Group 3: the four-bid comparison is closed, not refuted

Group 3 ran four bids for 2076-2079 on purpose: measured over 2071-2075 its
road left the association's worst omission (best team left home at class rank
#14.3) and four bids cleared 97% of it, where eight reached to #32 of ~68.
The owner ran 4 (Group 3) and 8 (1A) side by side in two comparable classes to
see which reached too deep, and this is the decision at the end of that run:
Group 3 takes 1A's eight.

Two things to keep straight for the next reader:

1. **The two justifications that FAILED under the four-bid study are still
   false.** "A shallow class's middle wins as often as its top" (73.9% for the
   better-ranked team, inside every class's 73.9-77.9% band) and "Group 3
   travels furthest" (47/43 mi, mid-pack) were both measured and rejected in
   2026-09. Neither is why the class moved to eight, and neither should be
   cited as though it were. The move is an association decision after a
   four-season comparison, the same kind of decision that gave 7A eight
   rather than sixteen.
2. **Seasons archived at 28 keep rendering as 28.** Every bracket surface
   reads bye and seat counts off the ARCHIVE (`_jh_split_state`'s named prelim
   split), never off today's table — the same guarantee that lets a 7A season
   selected at 16 still render as sixteen. Nothing was migrated.

## Field share, for the record

| class | programs (G/B) | field | share |
|---|---:|---:|---:|
| Group 2 | 67 / 64 | 40 | 60-62% |
| 7A (its shape) | 70 / 62 | 40 | 57-65% |
| Group 3 | 70 / 65 | 32 | 46-49% |
| 1A (its shape) | 87 / 84 | 32 | 37-38% |

Group 2 at 40 is the deepest field share in the association by a hair, level
with 7A; Group 3 at 32 sits between 1A and the 32-road classes. Both are inside
what the association already crowns from elsewhere, which is what "use the
other classes as a guide" buys: no class is now an outlier on either axis.

## What did NOT move, and why

- **`CHALLENGE_SLOTS` stays empty.** The four-seat Challengers valve is a
  property of a 40 ROAD (a 40 Conference sends 14 to the Specials), not of a
  40 FIELD; Group 2's road is 32, so it runs the standard two seats like 7A.
- **No dual format changed.** The 2026-09 rule that playoff size and dual
  format are separate axes holds; Group 2 plays 3S/3D and Group 3 plays 1S/4D
  at their Parastates because that is what their roads play.
- **Sponsor floors are unaffected** — the road is what the floors gate, and
  the roads did not move.

## Lesson

When a structure has been parameterised well enough, an expansion is a table
edit plus the prose that described the old table. The work here was reading:
confirming the deciders were gated on phase rather than round, that the byes
derive from the tables, and that the archive — not the table — drives how an
old season renders. Three earlier AARs had made each of those true; this one
just checked them before trusting them.

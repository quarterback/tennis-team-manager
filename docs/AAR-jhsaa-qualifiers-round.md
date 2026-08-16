# AAR — the expanded State fields and the Qualifiers Round

**Date:** 2026-08-16
**Status:** Landed. Owner field table (2027-08).
**Scope:** `app/jhsaa.py` (`STATE_FIELD`, `QUALIFIER_NAME`, `run_state(champions=)`,
`ladder_scale`), `app/web/state.py` (`_jh_split_state`, `_jh_bracket_cols`
seed_map, `jhsaa_bracket_view`, `jhsaa_school_view` round chips),
`app/web/templates/jhsaa_bracket.html`, `scripts/import_jhsaa.py`
(`_collapse_school_of` campus qualifiers, `build` collision guard, one RENAMES
entry), `data/jhsaa/schools.json` (two renames), `tests/test_jhsaa_ladder.py`,
`tests/test_jhsaa_toc.py`.

## The owner's table

The three largest classes crown from **24**; the five smaller ones — which hold
MORE programs than the big ones since the nine-class ladder (2A-1A 137 and 3A
127 against 9A's 80) — crown from **40**, landing every class between 23% and
31% of its programs reaching State.

**A 40 is a 24 with a Qualifiers Round in front of it.** The eight Zonal
champions take a DOUBLE bye; seeds 9-40 play the Qualifiers Round ("Qualies" on
a chip) and then the First Round, and the eight who survive both join them in a
fresh draw. After the Qualies exactly 24 are alive — the other classes' bracket
— so both shapes converge and there is one championship from the Octofinals
down. A 32 could never do this: 32 is a full bracket, so a champion cannot be
given a bye without inventing a round for everybody else to sit out.

```
40 teams   Qualifiers Round   40 alive, 16 games
           First Round        24 alive,  8 games
           Octofinals         16 alive,  8 games   ← the 24-classes join here
           Quarterfinals       8 alive,  4 games
           Semifinals          4 alive,  2 games
           Championship        2 alive,  1 game
```

Pinned by `test_an_expanded_field_is_a_24_with_qualies_in_front` (the shape, the
double bye, the 24-shape untouched) and
`test_state_byes_belong_to_the_zonal_champions` (the double bye at fixture
scale).

## What actually blocked it — a school name, not the bracket

The first attempt verified the bracket in isolation, wired it into the season,
and hit `test_every_archived_record_covers_every_dual_played`: one school's
standings record covered a different number of duals than its archive rows. The
session ended flagging it as "how a 40-team field's rounds reach
`world_jhsaa_dual`" — the obvious suspect, and the wrong one.

The bracket was innocent. The class-rebalance re-import one commit earlier had
split an over-cap campus in prep-network into "Jefferson School of Science and
Technology" and "… Technology **North**" — and the display collapse ("School of
SUBJECT collapses to the subject, truncated at 'and'") truncated the campus
qualifier away with the subject, so BOTH campuses emitted as **"Jefferson
Science"**, in the same 8A district. A display name is the archive's identity
(`run_season`'s teams dict, `world_jhsaa_dual.school`, the routes, the pids):
the name-keyed dict collapsed 188 standings rows into 187 teams, only one
object's schedule reached the archive, and the OTHER object's standings row
mismatched it. Nothing errored; each row was internally consistent.

Diagnosed by measurement, not by reading the selector: every `TeamSeason`
balanced internally (record == schedule length, all 187), so the fault had to be
between two objects sharing a key — and `Counter` on the data found it in one
pass. The direction of the mismatch even flipped between runs (30-vs-25 one
session, 25-vs-27 the next) because which object wins the dict is arbitrary —
a signature worth remembering: **a record/archive mismatch that changes
direction is two objects fighting over one key.**

Fixes, all three layers:
- `_collapse_school_of` carries a trailing campus qualifier (North/South/…)
  through the subject truncation — the split reads "Jefferson Science North",
  which is how a real split campus of a Bronx-Science-style name reads anyway.
  (The owner then renamed that campus outright — a town would not carry two
  science high schools — to The Evans Larsen Day School, printed "Evans Larsen
  Day" under the no-suffix rule: a RENAMES entry off the same source identity,
  Steeplejacks, blue blood in `archetypes.json`. The collapse fix stays — it is
  what keeps the NEXT split campus from colliding.)
- `build` refuses to emit two rows with one display name — a collision is a
  missing RENAMES decision, and the import stops rather than ship it. The same
  sweep surfaced a second, latent collision: two genuinely distinct
  St. Genevieves (a 1A in Benchton, a 6A in San Cordero whose suffix strip
  landed on the bare name). The 6A takes the city — "St. Genevieve San
  Cordero", PRE + PLACE, the owner's "Jesuit Sacramento" convention — via
  RENAMES, so `canon()` still maps it to its roster identity and no pid moves.
- `test_display_names_are_unique_identities` pins the checked-in data for both
  genders.

## Scale is part of the shape, or the fixture lies

The first attempt triggered the expanded path on `len(field) > 32` with a
hardcoded 8 champions and a 32-slot sub-draw. Full size, correct; under
`ladder_scale` (the two-district test fixture), a 40 scales to 20, never
triggers, and plays one 32-slot draw — **12 byes against 4 champions**, the
exact unearned-bye shape the recovery redesign exists to prevent. Worse, a
20-team State out of a 24-team class drains the loser pools recovery draws
berths from, so the field came up short (19/20) and the two genders came up
short differently.

Both halves fixed at the root:
- `run_state` takes `champions` (the caller's `len(zc)`) and derives the shape
  from it: a field whose padding byes are exactly the champions plays one fixed
  draw; anything larger plays qualifying rounds among the rest until only
  `champions` survive, then the fresh draw. Every `ladder_scale` image works —
  40/8 → Qualies+First Round → 16; 20/4 → 10-into-6-into-4; 10/2 → 5-into-3.
- `ladder_scale` gains a second fit: the State field must stay at most half the
  class, for the same reason the ladder's seats must fit it — "the field is
  FIXED and recovery conforms" presumes the berths can be contested from the
  loser pools, and a State that admits most of a small class has no losers left
  to contest them.

## The bracket page renders TWO trees, because there are two

Between the First Round and the Octofinals sits a **fresh seeded draw** — the
survivors are re-placed, exactly as a tour event's qualifying feeds its main
draw. So there is no bracket path from a Qualies slot to a main-draw slot, and
`_bracket_canvas` — which connects columns positionally, 2k/2k+1 — would have
drawn links that do not exist (and stacked cards, since 24 cards feeding 16
fits neither its equal-width nor its halving rule). Not a rendering
limitation to work around: **the one-tree drawing was false**, and the split is
the honest picture.

`_jh_split_state` splits the archived bracket (the archive itself stays ONE
bracket) into render shapes: the main draw with the alive-count field the round
counter and bye derivation need, and the qualifying rounds over the teams that
played them. Both carry `seed_map` — the tournament's own seeds off the full
field — so a #23 seed that qualifies keeps its 23 chip in the main draw rather
than being renumbered by its position in the split. The page grows a
"Qualifying" tab on the existing toolbar (`data-view` switching it already
had); 24-team classes and old archives return `(br, None)` and render exactly
as before. Rendered-HTML coverage in
`test_an_expanded_bracket_page_renders_two_draws`, per the standing rule that
anything a template dereferences must be checked by rendering it.

## Lessons

- **A pinned invariant failing near your change is not necessarily your
  change.** The record-coverage test tripped on a data bug from the previous
  commit; the bracket work only made the season run that exposed it. Measure
  which objects disagree before reading the code that computes them.
- **"Verified in isolation" is not "wired in."** The synthetic 40-field was
  correct from the first session; everything that actually blocked the feature
  lived in the seams — the scale images, the fixture arithmetic, the renderer,
  the data underneath.
- **When a shape gains a parameter, grep for the hardcoded version of it.**
  The `> 32` trigger, the `field[:8]`, and the 32-slot sub-draw were all the
  same assumption written three ways; any one of them alone would have kept the
  fixture wrong.

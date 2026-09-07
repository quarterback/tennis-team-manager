# AAR — the 2026-09 JHSAA playoff expansion: 6A-1A to 40 on the Parastate

**Owner rule (2026-09).** "JHSAA has approved playoff expansion in 6A, 5A, 4A,
3A, 2A, 1A TO 40 teams using the same parastate format that 7A uses. None of
those classifications will change their dual match format from status quo, it's
just expanding the playoffs to include at-large committee decided seats."

**Scope:** `app/jhsaa.py` (`AT_LARGE_BIDS`, and the assertion beside
`state_field_size`), `app/jhsaa_committee.py` and `app/web/state.py` (prose
only), `tests/test_jhsaa_committee.py`.

## The whole change is one table

`AT_LARGE_BIDS` is what makes a class a Parastate class — `ATLARGE_GROUPS` is
derived from it, `run_state_parastate` takes its `byes` as `road − bids`, the
committee takes its `seats`, and the bracket page reads the shape off the
ARCHIVE. So six new entries is the feature:

| class | road (`STATE_FIELD`) | bids | field |
|---|---:|---:|---:|
| 9A · 8A · Group 1 | 32 | 16 | 48 |
| 7A · 6A · 5A · 4A · 3A · 2A | 32 | 8 | 40 |
| **1A** | **24** | **16** | **40** |
| Group 2 · Group 3 | 32 / 24 | 0 | road only |

Nothing else moved. The road qualifies exactly what it qualified before, by the
same ladder, with the same Zonal/Epiregional/recovery/Specials arithmetic; the
at-larges are added on top and seeded below every road qualifier, structurally.

## ‼️ 1A REACHES 40 ON BIDS — because the expansion touches no road at all

Every other expanded class is 32 + 8; 1A's road is **24**, so it takes **16 bids
on that 24 road**. The Parastate is byes 1-8 and 9v40 … 24v25; the sixteen
winners join the eight bye lines on the 24-team draw 1A has always played.

‼️ **The reason is the rule, not a structural obstacle — and a draft of this AAR
got that wrong.** It claimed `state_field_size(group) == 24` "routes a class to
the fixed `_recovery_24` wiring", so a 32 road would have re-plumbed 1A's whole
ladder. **`_recovery_24` is RETIRED AND UNWIRED** (owner rule 2026-08, and its
own docstring says so): `run_season` sends EVERY class through `_recovery`, the
same rungs everywhere with only the counts changing — at a 24 field the
Divisionals, Semi-Conference and Conference are 8 where a 32-road class runs 16,
and the berths split 8 Zonal + 8 Semi-State + 4 Divisional + 4 Specials instead
of 8/8/8/8. 1A's 24 is a TALENT decision recorded in `STATE_FIELD` ("the talent
really degrades at that level"), full stop.

So the honest statement of the choice: **moving 1A to a 32 road is a one-number
`STATE_FIELD` edit that the ladder re-derives from** (`recovery_shape` projects
it; both field sizes need the same 48 sponsors and 1A has 77-87). It was not
done because the owner asked to expand the PLAYOFF, not to lengthen 1A's road —
a values call about how much of 1A's field should be earned on court versus
selected, which is the owner's to make and cheap to change either way.

**The lesson:** a retired code path with a long explanatory docstring reads
exactly like a live one. Before citing a function as the reason a rule exists,
check that anything still calls it — `grep` for the call site, not the
definition.

**The general lesson:** when a spec says "same format as X", find the
PARAMETER that produced X's shape rather than copying X's numbers. Here the
parameter is `bids`, and the field size is `road + bids` — `run_state_parastate`
was already written that way and needed no change at any of the three shapes.

## ‼️ PLAYOFF SIZE AND DUAL FORMAT ARE SEPARATE AXES — do not tidy them together

The owner said it explicitly, and the code already agreed: `WIDE_GROUPS` (the
4S/5D road) and `ATLARGE_GROUPS` (the Parastate) are different tuples read by
different consumers. Before this pass every Parastate class happened to be in
both, and the constant's own comment said so ("All four are in `WIDE_GROUPS`") —
which is exactly the kind of coincidence a later pass "restores" as an
invariant. It is not one. 6A through 1A now run the Parastate at whatever shape
their road already played (1S/4D, or Group 2's 3S/3D had it been included), and
a test pins that the overlap has not grown.

## The one invariant worth asserting

`bids <= state_field_size(group)`, at import. The Parastate is the `2 × bids`
lowest seeds paired high-low, so every at-large plays a ROAD qualifier for its
seat; `bids > road` would pair at-larges against each other and hand one of
them a berth nobody defended. Two owner tables have to agree and neither knows
about the other, which is precisely when the agreement gets asserted rather
than assumed — the expansion added entries of both kinds (32 + 8 and 24 + 16),
so the check earns its keep immediately.

## Surfaces that needed nothing

- `/jhsaa/committee` — its group switcher IS `ATLARGE_GROUPS` and its seat count
  comes off the archived selection's own `seats`, so the seven new classes
  appear with the right numbers and every season archived before them keeps
  reading as the field it was actually selected at.
- The bracket page — `state._jh_split_state` splits on the named Parastate round
  and `_jh_state_view` computes the bye count as `field − 2 × bids` **off the
  archive**, never off today's table. 1A's eight bye lines fall out.
- `recovery_shape` / `sponsor_floor` — projections of the ROAD, which did not move.

## Cost

The Parastate is the only new duals: 8 a class a gender for 7A-2A and 16 for
1A, so **64 more duals per gender** against a season's ~5,100. The main draws
are the same size they were — a Parastate does not lengthen the bracket behind
it, it fills the same seed lines from a larger pool.

## Tests

`tests/test_jhsaa_committee.py`: the bid table pinned with its arithmetic
(`road + bids in (40, 48)`, `bids <= road`), the WIDE/Parastate overlap pinned
as unchanged, and 1A's 24-road 40 walked end to end through the real
`run_state_parastate` (pairings, round sizes, the surviving 24).

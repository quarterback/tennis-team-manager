# AAR — the 2026-10 public/private status worklist

## What the owner decided

A worklist of 18 schools arrived flagged as "wrong public/private status, wrong
class". Mid-application the owner corrected it: **only Evans Larsen Day is
private** (it was listed public). Jacmel, Tidewater, Lizard Creek, Aranaz, North
Averill, Winter Valley, Norbrook, Yarrowfield, Kuopio, Isla Verde, South Pomar, King,
Quartzburg and Odellville are PUBLIC and stay in their size classes, whatever
prep-network's source names say. **Washington San Cordero, Peregrine and Basalt are
public** and leave 10B/11B for their size classes (1A, 3A, 4A).

If the Non-Public classes ever run thin, the owner's stated remedy is more private
schools from the gazetteer, never re-flagging publics.

## Mechanism

* `import_jhsaa.PRIVATE_SCHOOLS` gains Evans Larsen Day. A new
  `import_jhsaa.PUBLIC_SCHOOLS` names the three ruled public and outranks both the
  source flag and the private table in `build` and in `jhsaa_apply_renames.apply`
  (the two must never share a name — asserted at import).
* `scripts/jhsaa_status_worklist.py` is the transform (the `jhsaa_apply_renames.py`
  idiom: holds no names, reads the tables, idempotent). A school ruled private goes
  through `jhsaa_districting.ensure_nonpublic(force=True)` — the forced-redraw tool —
  which seats it by the 550 cut (Evans Larsen Day, 1437 → 10B), records the public
  league it leaves as `old_group`/`old_league`, and redraws 10B and 11B at the
  ordinary 8-11 sizes. A school ruled public takes the seat its `old_league` already
  held for it.
* `source`, `name` and every pid are untouched; archived seasons stay as played.

## Public classes were deliberately NOT redrawn

A full `redraw_classes` pass was measured for 7A and 1A before deciding: the
clusterer left 7A with two 5-team leagues and 1A with a 3 and a 5, moving every
school's league for one departing or returning member. So a departing private's
league loses one member (7A Premier Athletic Association 6 → 5 girls) and a
returning public re-joins its old league. No public class fell under the 48-sponsor
floor (`jhsaa.sponsor_floor`), so the 015287a5 gap-fill rule did not fire.

## Program counts (girls / boys), before → after

| class | before | after |
|---|---|---|
| 10B | 57 / 54 | 58 / 55 (leagues 8·9·9·10·11·11) |
| 11B | 56 / 55 | 56 / 55 (leagues 8·8·9·9·11·11) |
| 7A | 61 / 54 | 60 / 53 |
| 4A | 64 / 62 | 65 / 63 |
| 3A | 67 / 67 | 68 / 68 |
| 1A | 79 / 77 | 80 / 78 |

Every private's class agrees with the 550 cut; no public row sits in 10B/11B (both
asserted by the script before it writes). Name list regenerated; the gazetteer
needs the prep-network checkout and was not regenerated in this pass.

## Addendum — the 2026-10 private expansion (25 net-new programs)

Follow-up from the same pass. prep-network has no private school left to add
(every private-flagged row was already in the association after 2026-09), so
the owner named 25 net-new programs for the seven areas with the thinnest private
coverage, placed in towns from the city records (`scripts/jhsaa_private_
expansion_2026_10.py` holds the rows; `PRIVATE_SCHOOLS` carries the names).
Names are written bare per the no-suffix rule ("Valderra Catholic", not
"Valderra Catholic High School"); mascots and colours are placeholders.

| area | private sponsors before → after |
|---|---|
| Gold Valley | 9 → 13 |
| Kangas | 3 → 8 |
| Silver Basin | 4 → 8 |
| Cascade Divide | 3 → 7 |
| Alderwold | 2 → 6 |
| Blue Mountain Country | 0 → 3 |
| Columbia Gorge | 0 → 1 |

10B 58 → 65 programs (seven leagues, 8-11); 11B 56 → 74 (eight leagues, 8-11).
Each new row's `old_league` is the league of the biggest public in its town of
the same size class. `roll_talent_bands.py` wrote rolled defaults for every
unassigned school, which also covered 33 earlier expansion rows that had none.

# AAR: the 2046 JHSAA expansion — Division 1 and Division 2

Owner spec (verbatim): "great basin counties are just gonna be called Division 1
and Division 2 for JHSAA purposes with their own leagues, think of them more as
10A and 11A than thinking of them as anything weird. just keeping the same
setup, just adding two classifications." So `Division 1` / `Division 2` are two
more entries in `jhsaa.GROUPS` / `jhsaa.STATE_FIELD` (`app/jhsaa.py`,
`scripts/import_jhsaa.py`) — not a parallel subsystem. Everything that already
iterates `GROUPS` (State field, TOC, awards, sponsor floor, rankings, title
board, directory) picked the two new groups up for free; nothing needed a
special case beyond the constant tables.

## What changed

- `GROUPS` gained `"Division 1"`, `"Division 2"` in both `app/jhsaa.py` and
  `scripts/import_jhsaa.py` (kept identical, per the existing convention).
- `STATE_FIELD["Division 1"] = STATE_FIELD["Division 2"] = 40` — the standard
  dynamic 40-team ladder, same shape as 9A-2A. 92 sponsors a gender clears the
  76-sponsor floor the dynamic shape needs comfortably. Neither uses the 1A-only
  fixed 24-team shape (`_recovery_24`) — that stays 1A-only per its own owner
  rule.
- New one-shot migration, `scripts/jhsaa_expansion_2046.py` (same shape as
  `jhsaa_reclassify.py` / `jhsaa_redistrict.py`): applies the owner-supplied
  target roster (`docs/handoff/JHSAA_2046_expansion_roster.csv`, 957 rows) to
  `data/jhsaa/schools.json`.
  - 864 `current` rows matched existing schools **by display name with zero
    misses** — no `RENAMES` lookup was needed. 300 of them change `group`
    (nothing else — enrollment/county/area/mascot/colors/private/sponsorship
    were already correct in the source data).
  - 93 `activation`/`new_territory` rows became brand-new schools: `source ==
    name` (no prep-network origin), both genders sponsored (all-new programs,
    no dice roll to reproduce), mascot/colors picked from a small
    ordinary-American-mascot pool on a stable per-school hash (the same idiom
    `fix_mascot` uses).
  - Every group's leagues were fully redrawn (`import_jhsaa.draw_districts`,
    reused exactly as `jhsaa_redistrict.py` does) — every one of the eleven
    groups' membership changed, so nothing short of a full redraw was correct.
- `docs/AAR-jhsaa-2046-expansion.md` (this file).

## Two things the source data got wrong, fixed rather than reproduced

1. **A split rivalry.** The roster CSV puts Condotti Vanguard Academy at 4A and
   its rival Romero-Finniski at 3A. `RIVALRIES` (and
   `jhsaa_reclassify.check_rivals`) forbid that outright — a rivalry outranks
   every other placement rule, the same reason the 2033/2039 realignments both
   carry rivalry-repair logic. Both are placed at 4A (Condotti's target)
   instead of trusting the split; this is why `4A` shows 87 schools against the
   roster's stated 86 and `3A` shows 85 against its stated 86.
2. **A retired-name collision.** The new 1A activation "Ransom City Union" is
   also a *former name* on file for the existing "Ransom Pass"
   (`import_jhsaa.RENAMES["Ransom City Union"] = "Ransom Pass"`, carried into
   `data/jhsaa/former_names.json`). CLAUDE.md is explicit that `source or name`
   must be globally unique — a second identity would either misresolve through
   `jhsaa.current_name`/`_relabel` or silently attach to Ransom Pass's archived
   history. Renamed to **Ransom City Regional**, which collides with nothing in
   either the display-name set or the former-names table.

## The sponsor floor did not clear on its own

The roster CSV's 5A group (86 schools) sponsors only 74 boys' programs against
the 76-sponsor floor the dynamic 40-team ladder needs — the one group, of
eleven, where the given roster falls short. Fixed the same way the 2039 AAR
describes checking for and not needing: two more girls-sponsoring 5A schools
(Belle Rive, East Burlington, picked in stable name order) had boys
sponsorship added. Preflighted with `jhsaa.sponsor_floor` before writing —
every group clears it after the fix; the script refuses to write otherwise.

## Final shape

| Group | Schools | Girls sponsors | Boys sponsors | Leagues |
|---|---:|---:|---:|---:|
| 9A | 86 | 86 | 78 | 9 |
| 8A | 86 | 86 | 82 | 9 |
| 7A | 86 | 86 | 76 | 9 |
| 6A | 86 | 86 | 76 | 9 |
| 5A | 86 | 86 | 76 | 9 |
| 4A | 87 | 87 | 81 | 9 |
| 3A | 85 | 85 | 78 | 8 |
| 2A | 86 | 86 | 83 | 9 |
| 1A | 85 | 85 | 79 | 8 |
| Division 1 | 92 | 92 | 85 | 9 |
| Division 2 | 92 | 92 | 87 | 9 |

957 total schools (864 existing + 93 new), matching the handoff's target count.
No league over `MAX_DISTRICT` (12); every league in the 9-12 band `district_count`
aims for.

## Not done / follow-up

- **`docs/GAZETTEER-jefferson.md` was not regenerated.** `scripts/
  jefferson_gazetteer.py` needs a `prep-network` sibling checkout for real
  lat/lon on existing territory, and none was available in this environment.
  The ten new counties' real-ground anchors (Elko NV, Jerome/Cassia/Oneida/
  Franklin/Bear Lake ID, Cache/Rich UT, Lincoln/Uinta WY — see the handoff doc's
  table) still need adding to the gazetteer script's data once a checkout is
  available.
- **The full JHSAA suite (`test_jhsaa*.py`) was intentionally not run** for
  this change, at the owner's request (repeat job, same shape as 2033/2039).
  Sanity-checked instead by loading both genders through `jhsaa.load_schools`
  and confirming `GROUPS`/`sponsor_floor`/`state_field_size` resolve correctly
  for both new groups, plus direct checks on the written data (unique display
  names, unique `source` identities, no league over cap, sponsor floor clear
  in every group/gender). Recommend a full run before merging.
- A literal-group-count test (`len(GROUPS) == 9` or similar) may exist and
  need updating to 11 — not checked, since the suite was not run; grep for it
  before merging.

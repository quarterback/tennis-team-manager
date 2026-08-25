# AAR: the 2046 JHSAA expansion — Group 1 and Group 2

> **RENAMED (owner rule 2026-08, NJSIAA language):** the two classifications were
> shipped as "Division 1"/"Division 2" and renamed to **"Group 1"/"Group 2"**
> (the NJSIAA crowns "Group 1 state champions") so the group names never collide
> with the recovery-round unit names — `renumber_divisions` already names units
> "Division N". No season was ever archived under the old names, so this was a
> plain string rename with no former-name machinery. The handoff CSVs in
> `docs/handoff/` keep "Division 1/2"; `scripts/jhsaa_expansion_2046.py`
> translates at the read (`GROUP_RENAME`).

Owner spec (verbatim): "great basin counties are just gonna be called Division 1
and Division 2 for JHSAA purposes with their own leagues, think of them more as
10A and 11A than thinking of them as anything weird. just keeping the same
setup, just adding two classifications." So `Group 1` / `Group 2` are two
more entries in `jhsaa.GROUPS` / `jhsaa.STATE_FIELD` (`app/jhsaa.py`,
`scripts/import_jhsaa.py`) — not a parallel subsystem. Everything that already
iterates `GROUPS` (State field, TOC, awards, sponsor floor, rankings, title
board, directory) picked the two new groups up for free; nothing needed a
special case beyond the constant tables.

## What changed

- `GROUPS` gained `"Group 1"`, `"Group 2"` in both `app/jhsaa.py` and
  `scripts/import_jhsaa.py` (kept identical, per the existing convention).
- `STATE_FIELD["Group 1"] = STATE_FIELD["Group 2"] = 40` — the standard
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
   history. First renamed to "Ransom City Regional"; the owner then dictated
   **Reverend City** (owner edict 2026-08, now in `import_jhsaa.OWNER_EDICTS`),
   which collides with nothing in either the display-name set or the
   former-names table. The town is unchanged (Ransom, Tamarack County), and no
   former_names/alias entry is needed — the school has never been archived.

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
| Group 1 | 92 | 92 | 85 | 9 |
| Group 2 | 92 | 92 | 87 | 9 |

957 total schools (864 existing + 93 new), matching the handoff's target count.
No league over `MAX_DISTRICT` (12); every league in the 9-12 band `district_count`
aims for.

## Follow-up audit (2026-08): GROUPS is no longer one ordered ladder

The owner asked whether the All-Region awards and regional structures were
adapted. The audit found that appending the two Division groups after 1A broke
every consumer that read `GROUPS` as a single size ordering. Fixed:

- **`LADDER_GROUPS` / `DIVISION_GROUPS` split** (`app/jhsaa.py`): `GROUPS[:9]`
  is the 9A→1A enrollment ladder; the Division pair is a geographic system, not
  rungs below 1A. Anything ordering-sensitive now reads the split.
- **Play-up was promotable into 1A.** `can_play_up` used `GROUPS.index`, so
  Group 1/2 (indices 9/10) read as "4A or below" and `play_up_group` handed
  Group 1 → `GROUPS[8]` = 1A. Now: `can_play_up` is False for both Division
  groups, `play_up_group` is an identity there, `valid_playup_target` requires
  ladder-only targets, and the editor's `targets` menu slices `LADDER_GROUPS`.
  Same fix in `scripts/jhsaa_playup.py`'s seed pool.
- **`_GROUP_IX` "classes apart" pairing gate**: raw enumeration put Group 1
  "one apart" from 1A (a 2,500-enrollment school gated onto 100-student
  opponents). The Division groups now take FRACTIONAL ladder positions from
  their enrollment midpoints — Group 1 = 3.5 (pairs 6A/5A/Group 2),
  Group 2 = 4.5 (pairs 5A/4A/Group 1) — exactly 1.0 apart, so the Great
  Basin pair can always meet non-district (geography makes that the common
  case anyway).
- **`_TALENT` and `ROSTER_SIZE_BAND_BY_CLASS` had NO Division entries** — every
  Great Basin roster build KeyError'd. Added blended bands per the "smaller =
  thinner mean, wider spread" rule: Group 1 (845–2556, ≈5A–9A mix) boys
  (54.5, 16.5) / girls (49.5, 15.5), roster band (18, 22); Group 2 (57–836,
  ≈1A–4A mix) boys (42.0, 20.5) / girls (37.5, 19.5), roster band (15, 19).
- **`renumber_divisions` / `reletter_conferences`**: `reversed(GROUPS)` now
  runs Group 2, Group 1, then 1A→9A — documented as the deliberate
  bottom-up order. **Name-collision check**: the recovery round's unit label
  "Division {n}" vs the group names "Group 1"/"Group 2" is COSMETIC only
  — no lookup anywhere keys a group name against a unit string (units are
  values inside stage dicts; title-board buckets key on stage `round_names`
  like "Divisionals"), and the honours chip renders units in ROMAN numerals
  ("Division XI") while groups keep arabic digits. No real key collision.
- **All-Region self-adapts — measured, no code change.** Regions are
  `t.school.area` with thresholds on program counts; no hardcoded area list
  exists in logic (only prose comments). Post-expansion counts (girls / boys):
  Halbrook Basin 222/204 and Gold Valley 116/108 clear the HM threshold (100);
  Selquah 98/86, Ashbury Metro 88/78, Sebastian Cape 71/64, Kangas 70/66,
  Yarrowmere 60/58, Cascade Divide 53/48 and Juniper Highlands 45/39-girls-only
  clear First+Second (45); Alderwold, Southern Jefferson, Millersylvania,
  **Bear River Country (21/21)** and **Snake River Plain (6/6)** get one
  unnumbered team; **Silver Basin (3/3) is below MIN_REGION_PROGRAMS (4) and
  crowns no All-Region team** — a real, self-consistent outcome of the
  thresholds, flagged here in case the owner wants Silver Basin folded into a
  neighbouring award region. Kangas/Millersylvania keep their areas; only the
  `group` of their schools moved.
- **Handoff data fix**: `great_basin_boundary.new_areas` in the roster JSON
  omitted "Silver Basin" (and the .md boundary bullet likewise) — a consumer
  applying that machine rule would wrongly exclude the three Ruby County
  schools (Vermillion, Atlanta, Ruby County Catholic). Fixed both; verified the
  expansion script trusted the per-row championship_group column, so all three
  are correctly in Group 1/2 in `data/jhsaa/schools.json`.
- **Smoke-tested** (no full suite, per owner): `load_schools` both genders,
  `state_field_size`/`sponsor_floor` (76, cleared by 92/92 girls and 85/87
  boys)/`recovery_shape`/`dual_format` for both Division groups, and real
  roster builds for four Division schools (16–18 players, sane OVR spreads).
- **`docs/GAZETTEER-jefferson.md` regenerated** with a prep-network checkout.
  The three new areas are NET-NEW territory prep-network lacks, so
  `jefferson_gazetteer.py` grew `_EXPANSION_2046_PLACES` (28 towns on real
  county-seat coordinates) and a documented `NET_NEW_AREAS` allowlist that
  exempts exactly those three areas from the two-repo area-agreement assertion
  — the assertion itself still guards everything else.
  `docs/JHSAA-school-names.txt` regenerated too.

## Not done / follow-up
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

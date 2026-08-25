# AAR — Heritage Valley migration: 46-school eastern reallocation, Group 3

## What started it

The owner supplied a full prescriptive migration guide
(`JHSAA_HERITAGE_VALLEY_MIGRATION_GUIDE_FINAL.md`) reallocating 46 current
school slots from three crowded western Areas (Belmonte Metro, Halbrook Basin,
Ashbury Metro) into eastern Jefferson — the "Heritage Valley" belt (Silver
Basin, Snake River Plain, Bear River Country), the same real Idaho/Utah/
Wyoming/Nevada ground the original 2046 Great Basin Group 1/Group 2 expansion
already stood on — plus an 8-school "Louisville by the Sea" satellite next to
Port Valdez. Net-zero: **957 schools before and after.** Explicit owner
correction mid-task: this is "just another realignment... it's not new work,
it's not sensitive" — treat it exactly like `jhsaa_reclassify.py` /
`jhsaa_expansion_2046.py`, no prep-network edit needed (a spec for that repo's
half is written up but not applied — see below).

## The new structure

**Two action types**, both from the guide:
- **MOVE** (24 schools) — same institution, new `area`/`county`/`city`. History,
  mascot, colors, enrollment, sponsorship all untouched.
- **RETIRE_AND_REPLACE** (14 schools) — the donor slot's sponsorship goes to
  `False`/`False` (never deleted — the `jhsaa.former_school` precedent: an
  institution that stops sponsoring keeps its archived page), and a brand-new
  eastern school is appended with fresh `source`/mascot/colors, inheriting only
  the donor's sponsorship pattern, private status and enrollment.
- **Louisville-by-the-Sea** (8 schools) — a third, simpler action: city/locality
  change only (`area`→"Port Valdez" a new area, `county`→"Valdez" a new
  county), classification and group entirely untouched. These are NOT eastern
  Group arrivals — they stay in the ordinary 1A-9A ladder.

**‼️ THE 38 EASTERN ARRIVALS LEAVE THE 1A-9A LADDER ENTIRELY** and join the
Great Basin's Group system as a new **third group**. The guide is explicit
(Section 11/12): the 24 moves + 14 replacements are removed from the ladder's
per-class counts, and the "post-migration eastern Group pool" is 222 — the
existing 184 Group 1/Group 2 schools plus the 38 arrivals. `retier_groups()`
sorts that 222-school pool by enrollment descending and cuts it into three
**exactly even** bands of 74 (222/3, landing precisely on the guide's own
"roughly 70-80 per Group" target) — Group 1 (1066-2556 enrollment), Group 2
(407-1059), Group 3 (57-396).

All of this lives in a new script, `scripts/jhsaa_heritage_valley.py`, same
shape as `jhsaa_reclassify.py`/`jhsaa_expansion_2046.py`: a one-time transform
over the committed `data/jhsaa/schools.json`, no prep-network dependency
(every new school's `city`/`county`/`area` is supplied directly by the
script's own tables — the `jhsaa_expansion_2046.new_school` idiom for a
program with no prep-network origin).

## Implementation notes worth keeping

- **A third Group classification is NOT just a data-file change — it needs
  registering everywhere "Group 1"/"Group 2" are keyed, in BOTH `app/jhsaa.py`
  AND `scripts/import_jhsaa.py` (they carry SEPARATE `GROUPS` tuples, and
  nothing keeps them in sync).** Missed the second copy on the first pass:
  `redraw_all_groups()` iterates `for g in m.GROUPS` (`m` = the imported
  `scripts/import_jhsaa` module, not `app/jhsaa`), so with only `app/jhsaa.
  GROUPS` updated, Group 3 silently never reached `draw_districts` — 66 of 74
  Group 3 schools showed non-empty but STALE districts (leftover strings from
  whichever old Group 1/2 league they used to belong to), and the 8 brand-new
  replacement schools (which start with `girls_district: ""`) showed the only
  visibly-empty ones. **Counting non-empty districts is not a correctness
  check here — every district on a re-tiered pool must be independently
  verified against a FRESH `draw_districts` call**, which is what caught it
  (a standalone re-run of `draw_districts` on the same pool filled all 74
  correctly, proving the pool itself was fine and only the dispatch was
  broken). Fixed by adding "Group 3" to both `GROUPS` tuples; the data file
  was restored from git and the migration re-run clean rather than patched in
  place, since RETIRE_AND_REPLACE's collision guard (`if new_name in rows`)
  makes the script correctly refuse to run twice over its own output.
- **`app/jhsaa.py` needed FIVE separate tables extended for Group 3**, not
  just `GROUPS`: `GROUP_SHORT` (display abbreviation), `ROSTER_SIZE_BAND_BY_
  CLASS`, `STATE_FIELD`, `_TALENT` (boys/girls mean+spread), and `_GROUP_IX`
  (the fractional ladder position the non-district pairing gate uses). All
  five are keyed on the group name as a dict, so a missing key doesn't error
  loudly at import — it `KeyError`s the first time a Group 3 roster actually
  tries to build (`_TALENT`) or a Group 3 dual tries to pair non-district
  (`_GROUP_IX`), which would have shipped invisibly if not checked. Values
  chosen by the SAME method the 2046 script's own comment documents:
  enrollment range → which ladder classes it overlaps → blend those classes'
  numbers, smaller mean / wider spread as enrollment falls.
- **Group 1 and Group 2's enrollment ranges genuinely SHIFTED** once the
  weakest third split off into Group 3 — Group 2 moved from 57-836 to
  407-1059, meaningfully stronger. `_TALENT`/`ROSTER_SIZE_BAND_BY_CLASS`/
  `_GROUP_IX` for Group 1 and Group 2 were RETUNED to their new ranges, not
  just extended with a Group 3 entry alongside the old numbers.
- **Group 1 and Group 2 both drop below `sponsor_floor` (76) as a direct,
  structural consequence of adding a third group** — splitting 184 schools
  three ways instead of two puts every band at 74, under the 76-body
  Semi-Conference floor a 40-field class needs. This is **reported, not
  patched** — the exact `sc_head` degrade-loudly precedent CLAUDE.md documents
  for 8A/9A after the original 2046 split, and for the same reason: a real
  geographic/structural realignment cost, not a bug to paper over by
  re-cutting band sizes to dodge the floor. Group 3 avoids it entirely by
  using the BYELESS 24-field shape (`state_field_size(group) == 24` routes to
  `_recovery_24`, which "has no floor of its own" per `sponsor_floor`'s own
  docstring) rather than the dynamic 40-field ladder.
- **The eastern moves also pull real boys sponsors out of 6A and 5A**, which
  were sitting at 77 and 76 — one and zero above the floor — before the
  migration. Both now read 71, also under floor, also reported rather than
  backfilled (no `backfill_boys_sponsorship` pass was run for this migration;
  the guide does not call for one, unlike the 2046 script which needed it for
  its own 5A shortfall).
- **A guide's roll-up total can be off by one without the plan being wrong.**
  Section 3 states Halbrook Basin reallocates 12 slots; the per-school tables
  in Sections 5/6/10 sum to 11 (5 intact moves + 4 sunsets + 2 Louisville
  moves) — verified against the LIVE data, not assumed away. Per the owner's
  own resolution when this was flagged mid-task: follow the per-school tables
  exactly as written, since those are what a migration actually executes:
  Halbrook Basin lands at the guide's own stated target (45) regardless.
  Never invent an extra move to force a rollup number to balance when the
  named tables don't call for one.
- **RETIRE_AND_REPLACE's new schools reuse cities the guide's OWN MOVE table
  already placed a different school in on purpose** — "Paul Robeson" (a MOVE)
  and "Boley Union" (a replacement) both land in "Boley"; "Ella Baker" (a
  MOVE) and "Langston Central" (a replacement) both land in "Langston". This
  mirrors how the guide's own naming layer already works — Vance County's
  existing Heritage Valley core (Aldecoa, Echevarria, Carden City...) already
  has many schools sharing one city — and is not a data error.
- **New counties were invented for two of the three eastern Areas, one reused
  for the third**: Snake River Plain gets "Minidoka" (a real, geographically
  adjacent Idaho county to the Raft/Eden counties already there), Bear River
  Country gets "Lincoln" (real, adjacent Wyoming county, matching the "real
  ground" convention `docs/GAZETTEER-jefferson.md`'s generator already
  enforces), and Silver Basin's arrivals join the EXISTING "Vance" county —
  deliberately, since Vance is already the Area's dense urban core and the
  guide's own hints for these schools ("Heritage Valley core city", "urban
  belt", "urban neighborhood school") describe exactly that fabric rather than
  new ground.
- **Prep-network is untouched, by explicit owner instruction mid-task**
  ("prep-network doesn't need to be edited, you can just make a file for that
  to have later... all i want is to edit the game"). The guide's own Phase 5
  ("update prep-network geography: settlement records, county membership,
  Area, coordinates, population") is written up as a standalone spec for
  later (`docs/PREP-NETWORK-heritage-valley-geography.md`) rather than
  applied — `data/jhsaa/schools.json` is the actual runtime source of truth
  for the JHSAA (confirmed by tracing `import_jhsaa.py`/`jhsaa_reclassify.py`/
  `jhsaa_expansion_2046.py`, all of which read/write ONLY that committed file
  and never touch a live prep-network checkout for anything but district
  redraws' county lookups), so nothing in the running game depends on
  prep-network's own `records/orgs/schools.json`/`cities.json` reflecting
  these new settlements. A future prep-network alignment pass can consume
  that spec file whenever the owner asks for it — never on an agent's own
  initiative, the same standing rule as the school-name-cleanup TODO already
  on file for that repo.
- **The migration script's own preflight is the only verification this pass
  ran** (`preflight()`/`report()`, plus a manual `app.jhsaa.load_schools()`
  round-trip checking every program's `district` field is non-empty) — no
  full `pytest` run, per explicit standing instruction for this kind of
  data/construction pass ("no full suite at the end").
- **‼️ A CLASS'S LEAGUE COUNT CAN STAY CORRECT WHILE ITS LEAGUE MEMBERSHIP
  GOES STALE — a second `redraw_all_groups` gap found on review, after the
  Group 3 dispatch bug above.** `have != district_count(len(pool)) or g in
  touched` redraws a class ONLY on a league-count mismatch or explicit
  membership in `touched` (originally just `{"Group 1", "Group 2", "Group
  3"}`) — a real check for "did this class gain or lose enough schools to
  need more/fewer leagues", but blind to "did a school's real location move
  without changing the class's total". 9A, 7A, 5A and 1A all lost exactly
  enough (or zero) schools to keep their OLD league count, so they kept
  their OLD, now-stale `girls_district`/`boys_district` strings: the three
  relocated 5A Louisville schools sat split between the old western
  Ambassador League and Capital Athletic Association, while a fresh
  `draw_districts` call over 5A's real post-migration membership put all
  three together in one eastern Valley Coast Interscholastic League (the
  live example a review caught this on) — 21-30 programs in each of the
  four skipped classes carried assignments from before the migration ever
  ran. **Fixed by explicitly touching every source class the three passes
  moved a school INTO OR OUT OF, not just relying on the count check**:
  `main()` now captures each MOVES/RETIRE_AND_REPLACE school's ORIGINAL
  `classification` (before `retier_groups` overwrites it to Group 1/2/3) and
  every LOUISVILLE school's class (unchanged by the move, but its city/
  county changed WITHIN that class, which is exactly the case a bare
  count-match can't see), and threads that set into `redraw_all_groups` as
  `extra_touched`, unioned into the same `touched` set Group 1/2/3 already
  used. The league-count check stays as the general `jhsaa_reclassify.
  rehome`-style catch-all for anything this script doesn't name — it is
  necessary, just not sufficient on its own once geography (not just
  headcount) can change inside a class.
  - **Why the existing 9-12 district-size test didn't catch this.** The
    suite's district-size invariant asserts every league lands in the
    9-12-team band `import_jhsaa.district_count`/`draw_districts` target —
    a real, useful check, but one that only ever inspects league SIZES, not
    WHICH schools ended up in which league. This bug left every league's
    SIZE untouched (nobody's league count changed) and only scrambled which
    three schools shared one — a stale assignment is invisible to a test
    that counts members, not identities. Catching this class of bug needs a
    membership assertion (e.g. "every school in a class's league roster
    also appears in a fresh `draw_districts` call for that class"), not a
    size one; nothing like that exists yet and none was added for this
    single migration pass, consistent with "no full suite at the end".
  - The data file was restored from the pre-migration base and the whole
    migration re-run clean (rather than patched in place) for the same
    reason as the Group 3 fix — `RETIRE_AND_REPLACE`'s collision guard makes
    a second pass over already-migrated output fail loudly rather than
    silently double-applying.

## What to check before touching this again

- `data/jhsaa/schools.json` now carries 971 rows (957 active sponsors + 14
  retired-but-kept RETIRE_AND_REPLACE donor rows). Anything that assumes "one
  row = one active program" (a raw `len(rows)` without filtering
  `girls`/`boys`) will overcount by 14 for the first time in this file's
  history — `former_school`'s whole reason for existing.
- If a future pass needs to shrink Group 1/Group 2 back over the sponsor
  floor, that is a NAMED realignment for the owner to call (moving specific
  schools between the three Groups, or re-cutting the band sizes), never a
  silent auto-rebalance — the same rule `_BALANCE_MOVES`/`RECLASSIFY_2039`
  already establish for the ladder classes.
- `scripts/jhsaa_redistrict.py` and `scripts/jhsaa_reclassify.py` both import
  `GROUPS` from `scripts/import_jhsaa.py` — any FUTURE group addition needs
  the same two-tuple check this AAR's first bullet describes, in both
  directions.

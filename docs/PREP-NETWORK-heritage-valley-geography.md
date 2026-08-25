# PREP-NETWORK SPEC — Heritage Valley geography (deferred, not applied)

**Status: NOT APPLIED.** This is a standalone spec for a future prep-network pass,
written per owner instruction ("prep-network doesn't need to be edited, you can just
make a file for that to have later — all i want is to edit the game"). Nothing in
`prep-network` has been touched. Do not apply this on an agent's own initiative — the
same standing rule as the JHSAA school-name-cleanup TODO already on file for that
repo (`CLAUDE.md`'s Jefferson section): only when the owner asks.

## Why this exists

The Heritage Valley migration (`scripts/jhsaa_heritage_valley.py`,
`docs/AAR-jhsaa-heritage-valley-migration.md`) moved 46 school slots into eastern
Jefferson entirely inside `tennis-team-manager`'s own committed
`data/jhsaa/schools.json` — the JHSAA's actual runtime source of truth. Nothing in
the running game reads prep-network at runtime; `import_jhsaa.py` only reads it at
one-time import. So the migration needed no prep-network change to work.

But prep-network carries its OWN, richer gazetteer of Jefferson (`docs/GAZETTEER-
jefferson.md` in this repo is generated FROM it — see `jefferson_gazetteer.py`), and
that gazetteer does not know about any of this yet: the settlement records, county
membership, Area names, coordinates and population figures for every arriving or
new eastern school are absent from prep-network's `records/orgs/schools.json` and
`cities.json`. A reader who goes looking for "Boley" or "Minidoka" in prep-network
today will find nothing, which is exactly the gap `jefferson_gazetteer.py`'s own
cross-check (comparing the two AREA sets) would catch on a future run.

## What a future prep-network pass would need to do

For each of the three action types in the migration (see the AAR for full detail):

1. **MOVE (24 schools)** — same institution, only its recorded settlement changes.
   Update the school's `area`/`county`/`city` fields in prep-network's own records to
   match the new eastern location the migration already assigned in
   `scripts/jhsaa_heritage_valley.py`'s `MOVES` table. No new institution — the
   prep-network row already exists under the school's `source` name.

2. **RETIRE_AND_REPLACE (14 schools)** — the donor institution's prep-network record
   is UNCHANGED (it still sponsors nothing in this game's data now, but it remains a
   real institution in its real western location in prep-network — sponsorship is
   this game's own decision, not a fact about the institution). The REPLACEMENT
   school is a genuinely new institution with no prep-network origin
   (`jhsaa_expansion_2046.new_school` idiom exactly — these were built the same way).
   A future pass would need to CREATE new prep-network records for the 14
   replacements: settlement (`city`), county, Area, coordinates (real ground in the
   Silver Basin / Snake River Plain / Bear River Country belt — see
   `scripts/jhsaa_heritage_valley.py`'s tables for the exact city/county/area already
   chosen), and a plausible enrollment/population figure consistent with the
   classification band it was assigned.

3. **Louisville-by-the-Sea (8 schools)** — city/locality change only. Update the
   `city`/`locality` to the new "Port Valdez" settlement and `county` to "Valdez" in
   prep-network's records; `area`, classification and group are untouched by the
   migration and need no prep-network change beyond the settlement fields.

## New settlement/geography facts this would introduce to prep-network

- **New counties**: "Minidoka" (Snake River Plain — real, adjacent Idaho county to
  the existing Raft/Eden counties), "Lincoln" (Bear River Country — real, adjacent
  Wyoming county). Silver Basin's arrivals join the EXISTING "Vance" county — no new
  county needed there.
- **New Area**: "Port Valdez" (Louisville-by-the-Sea's satellite), with its own new
  county "Valdez".
- **Real ground**: per `docs/GAZETTEER-jefferson.md`'s own convention, every
  settlement should stand on real southern-Oregon / northern-California /
  northern-Nevada / western-Idaho / (here, also Wyoming/Utah for Bear River Country)
  ground with real coordinates — consistent with how the original 2046 Great Basin
  Group 1/Group 2 expansion was grounded.

## What NOT to do

- Do not run any part of this against prep-network without an explicit owner request.
- Do not treat this file as a script or a diff — it is a plain-language brief for
  whoever picks up that future pass; the actual field-by-field mapping should be
  derived from `scripts/jhsaa_heritage_valley.py`'s own tables (`MOVES`,
  `RETIRE_AND_REPLACE`, `LOUISVILLE`) at the time the pass is done, since those are
  the authoritative record of what this game's data now says.
- Do not let this pass rename or restructure anything in prep-network beyond adding/
  updating the fields above — it is a geography sync, not a re-import.

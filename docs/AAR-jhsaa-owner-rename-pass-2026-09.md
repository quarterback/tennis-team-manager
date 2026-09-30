# AAR — the 2026-09 owner rename pass (54 schools, 10 towns)

**What changed.** The owner read the 2100 season review and the exports, hated a
class of names (irrigation and mining jargon, prairie grasses, words that are not
names, out-of-place people, and anything with "Spur" or "Bend" in it — "awkward to
say or picture on a shirt"), and renamed 54 programs and 10 towns in one pass.
PR: quarterback/tennis-team-manager#475.

## The process — a survey is a LIST handed back, never a commit
1. Survey every live, non-edict display name and hand back CANDIDATES grouped by
   why they read badly. The owner struck whole groups ("out-of-place city names is
   a lie, all of them were brought over for reasons") and named keepers (Michaeux =
   Oscar Micheaux; Harrisburgh is deliberate; Cassius = Cassius Clay; Wong).
2. Offer TWO options per name, drawn from real western high-school names
   (`generators/data/names/high_schools.json`, OR/CA/NV/ID/WA/MT/UT/CO/AZ, filtered
   against every live school, town and retired name). The owner picked, edited or
   supplied their own (Arnoldsberg, Quartz City, Industrial City, Marigot…).
3. **A pick that collides with a live name is HELD and reported, never
   substituted.** "Kelford" (Horseshoe Bend) and "Fort Valois" (Sagebrush) were live
   schools; the owner then supplied Cedarbrook and Franklin Fort Valois. "St.
   Genevieve" was accepted, turned out to be a REISSUE (the San Cordero school had
   once been emitted under it), was reported, and the owner replaced it with
   Washington San Cordero — so that name is no longer live and both histories
   resolve.
4. Apply EXACTLY the picks, one commit per owner message.

## The transform, and what it does NOT touch
- **`scripts/import_jhsaa.py` is the one authority.** A school renamed before gets
  its `RENAMES` VALUE rewritten in place (never chained — the former-names
  generator recovers the intermediate name from git); a school never renamed gets a
  NEW key equal to its own name. ‼️ `FORMER_NAMES` (lines ~367-1052) is a GENERATED
  block that sits ABOVE `RENAMES` and holds the same keys — a regex over the whole
  file matches it first. The Cedarbrook commit hit that block, applied as "0
  renamed", and the generator promptly rewrote it back. Slice to the `RENAMES`
  block before substituting.
- **`scripts/jhsaa_apply_renames.py` is the transform** (the committed
  `schools.json` cannot be regenerated). ‼️ IT NOW APPLIES `CITY_RENAMES` TO EVERY
  ROW. It sat below the `RENAMES` gate, so a town rename reached only the renamed
  school's own row: Dutchfork would have kept Cassius and King in "Ditch Fork",
  Quartz City would have left five schools in "Tunnel Diggings". Pinned by
  `tests/test_jhsaa_apply_renames.py` (fixture, not the data file; asserts the
  city-only row moves and a second application is a no-op).
- **Display-keyed tables move with the name**: `MASCOTS` (8), `LOCALITIES` (5 —
  Sally Ride/Roanoke, Ashbury South/Hackensack, Friendship, Fond Bleu, Penobscot),
  `OWNER_EDICTS` (Arthur Ashe → A. Ashe, at the owner's word — an edict is the
  owner's to change), `ALWAYS_EXTRA`/`EXTRA_SPONSORS`/the promote table, and
  `PRIVATE_SCHOOLS` (the restored St. Lucy and St. Dominic read private).
  `archetypes.json` is moved by the script; `talent_bands.json` keys on the ROSTER
  identity and needed nothing.
- **The institution-name bank lost Crown Paper and Quarry Workers** so a later
  pass cannot draw them again.
- **Towns**: `CITY_RENAMES` (keyed on the source town), `data/jhsaa/coords.json`
  keys, and the `us_states["JF"]` hometown pool in
  `generators/data/names/hometowns.json` (repeats are the weighting — rename every
  occurrence). `scripts/jefferson_gazetteer.py` carries an affiliate-town table of
  its own (Money → Corinne lives there too).
- **Deliberately untouched**: one-shot historical scripts that name these schools
  as they were when the script ran (`jhsaa_border_realignment`,
  `jhsaa_2056_promotions`, `jhsaa_secularise_2065`, …); tests that use "Ride" or
  "Scheelite County" as arbitrary strings; the research export's `program_id`,
  which is the ROSTER identity plus gender and still prints retired source names
  ("Caswell I-50 Technical|boys") — changing that changes the analytics join key
  and is a separate decision the owner has not made.

## Generated artifacts, in ORDER
1. Commit `import_jhsaa.py` + `schools.json`; then `scripts/jhsaa_former_names.py`
   (it reads git history for the value each `RENAMES` key held at each revision,
   so it runs pre-commit for the alias of the name being retired NOW and needs the
   previous value in a commit). Then `--check`. A reissue it names is a decision
   for the owner, not a thing to alias around.
2. `scripts/jhsaa_name_list.py` → `docs/JHSAA-school-names.txt`.
3. `scripts/jefferson_gazetteer.py --prep-network <checkout>` → BOTH
   `docs/GAZETTEER-jefferson.md` and the root `GAZETTEERjefferson.md`. It needs a
   prep-network checkout (public; a shallow clone is enough). ‼️ The gazetteer was
   already stale at the start of this pass (it predated the person-name
   abbreviation pass), so its diff is larger than the renames.
4. `scripts/build_jhsaa_coords.py` → `coords.json`, derived FROM the gazetteer.
   ‼️ Run it against a stale gazetteer and it REPLACES the new town keys with the
   retired ones — the hand-renamed keys in step 0 are only a bridge until this
   runs. ‼️ And its line pattern anchored on the coordinate, while the gazetteer
   now tags a program-less town with "· *no tennis programs*" AFTER it — Pellburg
   and Windrow (both still carrying a school row) were silently dropped on
   rebuild. The pattern now tolerates the suffix. Six towns (Allegheny, Cahaba,
   Hagerstown, Kishwaukee, Petoskey, Quincy) have no coordinate at all and had
   none before this pass — a pre-existing gap, not touched here.
5. `scripts/prep_network_name_map.py` writes INTO prep-network and was not run
   (read-only clone).

## Lessons
- **Two schools can both have carried one name.** A rename table that never chains
  still produces reissues when a SOURCE name (a former display name by
  construction) is handed to another school. `jhsaa_former_names.py --check` is
  the detector; run it before reporting a pass as done.
- **A generated file consumed by a second generator has an ORDER.** The
  gazetteer → coords pipeline is the case; document the order where the first
  generator lives.
- **The owner asked for no test runs.** A "subset" that hangs the session is not a
  subset. Run one fixture-sized file when a change needs it, and nothing else.

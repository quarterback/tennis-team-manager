# AAR — the 2056 closures and the suffix/collision rename batch

**Date:** 2026-08
**Status:** Owner lists, 2026-08
**Mechanisms:** the 2052 batch's (`docs/AAR-jhsaa-2052-eastern-oregon-expansion.md`)

## Closures — 43 programs sunset (`scripts/jhsaa_2056_closures.py`)

Flags off, rows kept, no redraw — `former_school` serves every page and archive
link forever; leagues stand as last-known. `NEVER_SPONSOR` deliberately unused
(it deletes the row and kills the pages). List notes:

- "Savanee Brulee" resolved to the committed **Savane Brulee**; case
  normalised for "Avalon PARK"/"Doyle ridge".
- **Manzanita Ridge was on both the close and rename lists; the rename won**
  (the owner's confirmation list omitted it) — it lives on as **Manzanita**.
- Pascagoula, Pendleton Heights, Pinyon Ridge and Abbey Prep were follow-up
  additions in the same session — and the owner then thinned the High-x names
  ("there are too many of them") by CLOSING High Bar, High Prairie and High
  Desert Christian rather than renaming them (High Timber, named in the same
  message, was already sunset by the 2052 batch and is not repeated; High
  Desert Cooperative was not named and stays).
- Sponsor floors measured at apply: **every class stays above its floor**
  (3A/4A, the two 76-floor classes, land at 80-82; the rest carry 48).

## Renames — nine, three stories (`import_jhsaa.RENAMES` + `jhsaa_apply_renames.py`)

1. **Woodrow Wilson → Sojourner Truth** (asked as "Sojourner Truth HS";
   committed without the suffix — the "Amelia High School" → "Amelia"
   precedent). Rewrote the existing `RENAMES["Belmonte Technical Arts
   Academy"]` target in place; moved the `LOCALITIES` key ("Tallulah").
2. **Manzanita Ridge → Manzanita** — the ordinary own-name-keyed rename;
   `source` stamped. No collision (1A Manzanita Junction is a different
   school whose name is its own town).
3. **The HS/High suffix sweep** (owner: "Singleton HS needs HS removed …
   along with any other school with High in the name"): Singleton HS →
   Singleton, Clara Brown HS → Clara Brown, Barlowe County High → Barlowe
   County, Lodestone County High → Lodestone County, Antler County High →
   Antler County (already sunset — a page rename). **Leading-word "High …"
   names were treated as identity, not suffix, and left alone** — and the
   owner then thinned most of them by closure instead (see above).
4. **The Orchard Hill swap — nobody keeps the name.** "Abbey Vale Orchard
   Hill → just Orchard Hill" collided with the live 9A Orchard Hill
   (Valderra), and reissuing the name would have merged the 9A's archived
   seasons onto the 2A's page (a display name is the archive identity; live
   name wins). The owner's final resolution kills the conflation outright:
   the 2A becomes **Booker T Washington** (owner's punctuation — no period
   after the T) and the 9A becomes **Bishop Turner**, so "Orchard Hill" is
   nobody's live name and the alias table sends the archived name to the 9A
   alone. Transient in-session targets ("just Orchard Hill" on the 2A,
   "Bishop Turner"/"Booker T Washington" briefly on the 9A) never reached an
   archive; targets were rewritten in place, never chained. `MASCOTS` key
   (Orchardists) followed the 9A; `RECLASSIFY_TO_2A`'s display-keyed entry
   followed the 2A; the source-keyed continuity table still matches the 9A's
   unchanged identity ("Orchard Hill", stamped into `source`).
   ‼️ This forced a THIRD generator rule: **an identity claim outranks a
   transient target.** Both chains claim the former name "Orchard Hill" —
   the 9A as its identity, the 2A as a target it passed through — and a dict
   would let iteration order decide whose page ~decades of archive land on.
   `jhsaa_former_names.collect` now lets the school whose IDENTITY the name
   is win the alias; the other chain's claim is dropped.
   ⚠️ Getting here took three tries in one session (Bishop Turner on the 9A →
   Booker T Washington on the 9A → the final swap): **when an owner names a
   school in a collision resolution, confirm WHICH school carries WHICH name
   before applying** — the assignment, not the name, is where the readings
   diverge.

The heritage-valley targets ("Singleton HS"/"Clara Brown HS") were rewritten
in place in `scripts/jhsaa_heritage_valley_renames.py`, and the 2052 script's
`SUNSET` entry followed "Antler County High" to its new name — a transform
script's display-keyed table breaks its replay if a rename leaves it behind.

## Faults found and fixed on the way

- **‼️ `jhsaa_apply_renames.apply()` recomputed EVERY row's display name from
  its source**, which was harmless while every row came out of
  `import_jhsaa.build`, and wrong once expansion scripts committed rows whose
  names are hand-assigned rather than `_display_name(source)`: a bare run
  would have renamed **63 rows** (the 2052/2046 affiliates — "Stanfield" back
  to "Stanfield High", "Nixyaawii" to "Nixyaawii Community") against the 2
  actually keyed. It now moves ONLY rows whose identity is a `RENAMES` key: a
  name with no recorded rename stands as committed. **Measure a batch script's
  blast radius against the whole file before running it** — the dry run
  listing 65 movers for a 2-entry edit was the tell.
- **‼️ `jhsaa_former_names.py` had two blind spots.** (1) It walked only
  `import_jhsaa.py` history, and the heritage batch renamed through its OWN
  table — so the display names it coined and later gave up existed in no
  revision it read, and a season archived under "Singleton HS" would have been
  unreachable. It now walks both files' `RENAMES` blocks. (2) It normalised
  each historical name through `_display_name` before emitting — which
  collapses "Singleton HS" INTO "Singleton", reads as a no-op, and drops
  exactly the alias the sweep created. Both spellings are now emitted; an
  alias no archive uses is a harmless map entry.
- **‼️ A SHALLOW CLONE IS NOT HISTORY.** The first regeneration on this
  session's fresh clone silently produced 505 aliases against the committed
  704 — `git log` saw 7 revisions of the importer instead of 105. The
  generator's output SHRINKING is the tripwire; `git fetch --unshallow` first.
  (The same lesson as the prep-network `git log --all` episode: "not in any
  ref" — or "not in any revision" — is a statement about your clone.)

## The third rename batch (owner list, 2026-08) — nine simplifications

Arroyo Water District → **Arroyo**, Cañada Irrigation → **Canyon**, Bracken
Works → **Bracken**, Sluice Crossing → **Crossing** (the TOWN keeps the name
Sluice Crossing), Bogue Chitto → **Harmony** (its `LOCALITIES` value stays
"Bogue Chitto" — the settlement keeps its name), Lost River Irrigation →
**Lost River**, Sacred Heart Cathedral → **Sacred Heart**, Pioneer Electric →
**Bolton**, Pacific Fruit Exchange → **Marshfield** (asked as "Lighthouse",
which collided with the live 7A Lighthouse in Fort Meriwether; the owner
picked Marshfield instead — one leading-word neighbour, Marshfield Prep,
noted and accepted). Eight rewrote existing `RENAMES` targets in place; the
display-keyed moves followed (`MASCOTS` ×3, `LOCALITIES`, `PRIVATE_SCHOOLS`,
`RECLASSIFY_2039B`). `INSTITUTION_NAMES` (the naming BANK) deliberately kept
the old strings — it is a record of the grammar, not a live-name list — but
note the standing risk: a bank name renamed away is re-drawable by a future
naming pass, the reissue trap one step removed.

## The 2056 move-up slate (owner list, 2026-08 — `scripts/jhsaa_2056_promotions.py`)

The counterweight to the closures: **25 programs promoted**, 22 into 9A
(64/64 → **86/86**, matching 8A and clearing the 40-field's 76 floor), plus
the owner's marked exceptions (Evans Larsen Day and Baptist → 7A, Minnesota
City → 8A). A RECLASSIFICATION, not a play-up — classification, group and
enrollment move together (the Lower Lake idiom; enrollments spaced into each
target class's live 25th-90th percentile band, preserving the batch's own
relative-stature order). Names resolved against the data: Wells = Ida B.
Wells, Mondale = Walter Mondale, Banneker = Benjamin Banneker, "Telfair
County Day" = Telfair Country Day, San Tomás. No rivalry pair split
(checked); the pinning entries in `RECLASSIFY_2039`/`2039B` are superseded at
the data level, and this script replays after them and after the closures.

**Every affected class was then redrawn** (`jhsaa_redistrict.py --cap 10`,
eleven classes in all — the owner's league band is 7-10, "a full ~16-match
league slate", and league identity churn is accepted flavor). End state,
verified: **every live league in every class holds 7-10 members in BOTH
genders**. One hand repair: 2A Foundry League drew 9 girls / 6 boys (three
girls-only members — a sponsorship asymmetry a size-based draw cannot see),
fixed by moving Gold Hollow (Antler County, beside five Foundry members) in
from Valle Vista League.

Three redistricter faults found by this batch, each shipped-and-measured:
- **`keep_rivals` displaced members into full leagues unconditionally** — a
  chain of rivalry repairs built 11/12-team leagues under a --cap 10 draw.
  A `spill` pass now re-enforces the cap after every repair.
- **`district_count` under a tighter cap could under-provision seats**
  (85 schools, round(8.5)=8 leagues, cap 10 → 80 seats) and the clusterer
  SILENTLY DROPPED the overflow — dropped schools kept stale league labels
  and read as phantom one-team leagues. `k` now respects the cap's own
  arithmetic floor and an assertion refuses a draw that drops anyone.
- **The multi-class runner writes once at the END**, so a `sys.exit` on the
  second class discarded the first class's finished redraw silently — the
  8A failure made the whole run a no-op while its output read as success.
  (Behaviour noted, not restructured: with the two faults above fixed the
  exit no longer fires; treat any future over-cap exit as "nothing landed".)

## The retunes the closures forced (owner rules, same session)

- **3A/4A State fields 40 → 32** — the association's last 40-field holdouts
  and its only 76-floor classes, at 81/80 sponsors after the batch. The Group
  1/2 precedent exactly (the `STATE_FIELD` table's own comment): down a field
  size, never a reported-and-ignored floor breach. Both clear the 32-shape's
  48 floor with 30+ of headroom, and the dynamic ladder needed no code — the
  shape falls out of the table. **Their brief `CHALLENGE_SLOTS` 4 retired
  with it** (owner: "3A/4A can match the rest of the state with only the 2
  worst qualifiers"): the wider valve was a 40-field correction, and at the
  standard shape every class runs the standard 2.
- **8A/9A went back UP to 40 ("the last switch")** — the deepest classes
  crown from the big field again — **and inherited the 4 Challenge seats**:
  the wider valve rides the 40-field shape, wherever it lives. 8A clears the
  40-field's 76 floor at 86/86. ‼️ **9A does not: 64/64 after the closures,
  12 short per gender** — its Semi-Conference will degrade LOUDLY every
  season (`sc_head`: the best bodies enter the Conference directly and a
  warning names the class), which is the documented under-floor behaviour,
  accepted with the switch. The repair, if ever wanted, is more 9A programs
  (the `FIELD_BOYS` idiom), never a smaller field. Note also the raw math a
  40 field over 64 sponsors implies: ~63% of the class reaches State.
- **1A leagues redrawn to the owner's 7-10 band** ("it ensures a full
  16-match league slate"). The 20 sunsets had left three live leagues at 5-6.
  `jhsaa_redistrict.py 1A --cap 10`: nine leagues became seven (Placer and
  Tailings revived, East Cascades and Vermilion Valley retired — league
  identity churn is "part of the deal and good flavor", owner), 33 schools
  moved, worst span 350 → 270 mi, and every league runs 8-10 LIVE members in
  both genders. Three script fixes rode along, each a real fault:
  - **A redraw pools LIVE sponsors only.** It pooled every row in the class,
    so 1A's 20 sunset rows occupied seats in a season they never play — the
    draw made 9 leagues where the live 69 want 7, and the cap check failed on
    schools that never take the court. Sunset rows keep their last-known
    league label and stay out of the arithmetic.
  - **`--cap`**: the clusterer packed to `MAX_DISTRICT` 12; the owner's
    preferred league is 7-10, so a draw can now be asked to stop at 10.
    MAX_DISTRICT stays the invariant the final check enforces.
  - **A live school with no prep-network town is placed at its county (then
    area) centroid**, never "left put" — left put strands it in a league the
    redraw may retire (Redwood Glen and Wheatley, both Jefferson-invented
    towns).

With prep-network on disk this session, the regeneration the 2052 batch
deferred also ran: `jefferson_gazetteer.py` (both gazetteer files current with
every rename and closure; its two-repo area assertion immediately caught
**Port Valdez**, the Heritage Valley migration's association-side satellite
area, never allowlisted because the gazetteer had not run since — added to
`NET_NEW_AREAS`) and `prep_network_name_map.py` (written into the read-only
clone; that repo cannot be pushed from this session, so re-run it beside a
writable checkout to land it there). `docs/JHSAA-school-names.txt` and
`data/jhsaa/former_names.json` regenerated.

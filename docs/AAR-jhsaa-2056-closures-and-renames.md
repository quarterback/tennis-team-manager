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

Deferred, per the 2052 precedent (no prep-network checkout in this session):
`jefferson_gazetteer.py` and `prep_network_name_map.py` regeneration.
`docs/JHSAA-school-names.txt` and `data/jhsaa/former_names.json` regenerated.

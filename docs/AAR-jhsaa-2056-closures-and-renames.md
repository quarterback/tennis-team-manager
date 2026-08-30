# AAR — the 2056 closures and the suffix/collision rename batch

**Date:** 2026-08
**Status:** Owner lists, 2026-08
**Mechanisms:** the 2052 batch's (`docs/AAR-jhsaa-2052-eastern-oregon-expansion.md`)

## Closures — 40 programs sunset (`scripts/jhsaa_2056_closures.py`)

Flags off, rows kept, no redraw — `former_school` serves every page and archive
link forever; leagues stand as last-known. `NEVER_SPONSOR` deliberately unused
(it deletes the row and kills the pages). List notes:

- "Savanee Brulee" resolved to the committed **Savane Brulee**; case
  normalised for "Avalon PARK"/"Doyle ridge".
- **Manzanita Ridge was on both the close and rename lists; the rename won**
  (the owner's confirmation list omitted it) — it lives on as **Manzanita**.
- Pascagoula, Pendleton Heights, Pinyon Ridge and Abbey Prep were follow-up
  additions in the same session.
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
   names are identity, not suffix, and stayed**: High Bar (its town's name),
   High Desert Christian/Cooperative, High Prairie, High Timber.
4. **Abbey Vale Orchard Hill → Orchard Hill** collided with the live 9A
   Orchard Hill (Valderra) — a display name is the archive identity, so the
   owner resolved it: **the 9A becomes Bishop Turner**, freeing the name.
   `MASCOTS` key moved with the 9A (Orchardists); the source-keyed continuity
   table still matches its unchanged identity; `RECLASSIFY_TO_2A`'s
   display-keyed entry moved with the 2A.

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

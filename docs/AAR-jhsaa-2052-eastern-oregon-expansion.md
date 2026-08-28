# AAR — The 2052 eastern Oregon / Columbia Gorge affiliate expansion

**Date:** 2026-08-28
**Scope:** `scripts/jhsaa_2052_expansion.py` (the one authority — every table
lives there), `data/jhsaa/schools.json` (applied), `scripts/
jefferson_gazetteer.py` (`_EXPANSION_2052_PLACES` + two `NET_NEW_AREAS`),
a pointer beside `import_jhsaa.NEVER_SPONSOR`. Plus, same session: the
Pennsauken sunset (a straight duplicate of Pennsauke, owner-stuck for decades).

## The ask

> "The JHSAA has admitted more Oregon and Washington schools in 2052 that we're
> bringing over due to geographic preference; we will sunset the commensurate
> amount of original Jefferson tennis programs to balance it out."

Owner-specified to the seat: one 5A league and four 2A districts (boys and
girls aligned identically), valid JHSAA band enrollments preserving the stated
relative stature, real city coordinates, `state` on every affiliate, Baker kept
with its history and moved into the new 5A league, and 40 named sunsets —
including several the owner wanted gone regardless of balance ("it wasn't an
accident… get them out of my game"). Separately: Amelia City, a net-new
JEFFERSON city on the real Amelia City, OR ghost-town site (44.3903,
-117.6233), with a 9A program.

## What shipped

- **40 in**: 39 real OR/WA affiliates + Amelia. **40 out**: 16×1A, 15×2A,
  4×3A, 4×9A, 1×Group 1, all sunset by the `former_school` mechanism — flags
  off, rows kept, pages and archives reachable forever. Nothing deleted.
- **Baker** 3A→5A, Sky-Em League → Eastern Oregon League, enrollment 517→830
  (the number follows the decision — the COMPETITIVE_MOVES idiom). ‼️ Verified
  before committing: all 20 of its 3A-era roster pids regenerate with
  IDENTICAL pids and names under 5A; the class change re-grades attributes and
  adds two seats (5A's roster band), exactly the 2033 reclassification
  precedent. A reviewer's first comparison said "names not stable" — it was
  comparing ordered lists of different lengths; compare by pid.
- **Amelia**: display name "Amelia" (the owner said "Amelia High School", and
  school names carry no institutional suffix — owner rule 2027-08), city
  Amelia City, mascot Ghosts, 9A at 2,350, seated in the Capital Athletic
  Association (which the sunsets had thinned from 11 to 8; it plays 9 now).
  Filed under Barlowe County / Boise Frontier — the nearest 9A-ladder ground —
  because the literal site sits in Group-system territory (the Kangas areas)
  where 9A cannot exist; the town itself is anchored at the REAL coordinates
  in the gazetteer table. The earlier "plays up" instruction died with the 5A
  draft: play-up is a ≤4A mechanism and 9A is the top of the ladder.

## Decisions a later agent must not "fix"

- **"Columbia / Blue Mountain District" is committed hyphenated** —
  `/jhsaa/district/<group>/<district>` cannot carry a slash in the segment.
- **"Trout Lake (WA)"**: the real Trout Lake, WA collides with the invented
  Jefferson 2A "Trout Lake" (Rimrock County), and a display name IS the
  archive identity (unique by pinned test). The affiliate carries the
  qualifier; if the owner prefers the invented program renamed instead, that
  is a rename pass with all its machinery (RENAMES, former_names, source
  stamping) — do not do it casually.
- **Owner-name resolutions** (confirmed in-session): "Ginsburg" = Ruth Bader
  Ginsburg (Group 1), "Talling Crossing" = Tailing Crossing (2A), bare
  "Harmon" = Annes Summit (source `Harmon` — Harmon Siding was already named
  separately on the same list).
- **Affiliates keep REAL counties** (Umatilla, Wallowa, Klickitat…) even where
  Jefferson's fictional ground overlaps: Stagewater County stands on Malheur
  County and Fort Valois on Ontario's coordinates, yet Ontario/Nyssa/Vale/
  Adrian enter under county "Malheur". Two ontologies, coexisting — the Baker
  precedent since 2046. Do not "reconcile" them.
- **No league redraw ran.** The owner assigned every seat, so the new
  districts exist by the rows that name them; the donor classes were left
  as-is (leagues run thinner — the association's normal answer). If a thinned
  league needs repair, that is `scripts/jhsaa_redistrict.py`, a separate
  owner-visible decision.
- **A full re-import cannot reproduce any of this** — affiliates have no
  prep-network rows, and the sunsets would come back as sponsors. The rule
  (noted beside `import_jhsaa.NEVER_SPONSOR`): after any re-import, re-run
  `jhsaa_2052_expansion.py`. It is idempotent and holds every table.

## Known consequences (flagged to the owner, accepted or pending)

- **Boys' 3A drops to 75 sponsors against `sponsor_floor("3A")` = 76** (all
  four 3A sunsets fielded boys). The Semi-Conference degrades LOUDLY by
  design — best bodies direct-admit to the Conference (`sc_head`) with a
  warning naming the class — rather than shipping a short State field. One
  more 3A boys' program (an `EXTRA_SPONSORS` add or one fewer 3A sunset)
  clears it.
- **Gazetteer doc regeneration is deferred** — `jefferson_gazetteer.py` needs
  a prep-network clone, unavailable in this session. The script tables are in
  place; run it (with `jhsaa_name_list.py` and `prep_network_name_map.py`)
  next time that repo is on disk.
- Amelia City is not yet in the JF hometown pool (`us_states["JF"]`) — that is
  `scripts/build_hometowns.py` / `import_jefferson.py` territory, a separate
  pass if the owner wants Amelia City kids appearing as recruits' hometowns.

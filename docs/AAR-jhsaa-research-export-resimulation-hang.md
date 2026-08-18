# AAR — the research export button that resimulated a state championship

## The report

Owner, live, on `/research/export` → JHSAA → Download ZIP: *"the export doesn't work
it just spins out of control or takes a long time to generate but that makes no
sense."* The loading overlay sat at **653s elapsed and climbing**, on a page whose own
copy promised "can take a little while" — not eleven minutes and counting.

It made no sense to the owner because it *shouldn't* have made sense: exporting is
supposed to be read-only packaging of something the game already computed. The button
was doing something else entirely.

## The chain

```
POST /research/export  (scope=jhsaa)
  └─ research_export.export_zip("jhsaa", year=..., gender=..., classification=...)
       └─ research_export.build_jhsaa(year, gender, classification)
            └─ season = season or jhsaa.run_season(gender, year, seed=0)   ← the whole state, from scratch
                 ├─ ~600 programs' district double round robin
                 ├─ non-district / invitational scheduling
                 ├─ mid-season showcases (pod + tiered)
                 └─ the FULL postseason recovery ladder:
                      Sectionals → Wards → Regionals/Zonals → Super Regionals →
                      Semi-State → Divisionals → Semi-Conference → Conference →
                      State (qualifiers + main draw) → Tournament of Champions
```

`build_jhsaa`'s only way to get a `season` was to call `jhsaa.run_season(gender, year,
seed=0)` when none was injected — and the web route never injects one. Every single
export request, for every user, replayed an entire high-school state championship from
the first non-district match to the TOC final, synchronously, inside the Flask request
handler.

## ‼️ The defect worth naming: the season was already sitting right there

That exact season — same gender, same year, same seed (0) — is simulated **once**,
already, at world week 0 (`world.run_jhsaa`), specifically so the recruiting hand-off
never has to re-derive it. It is archived across two tables the moment it's played:

- `world_jhsaa` — one row per `(world_id, year, gender)`: standings, brackets, awards,
  champions, all the postseason stages.
- `world_jhsaa_dual` — one row per side per dual: opponent, phase, score, lines.

Every `/jhsaa/*` page in the app already reads these tables instead of resimulating
(`world.get_jhsaa`, `world.jhsaa_schedule`, `jhsaa_school_view`, `jhsaa_group_ranking`,
…). The research-export feature is the one surface in the whole JHSAA section that
skipped the archive and went straight back to the simulator — not because reading the
archive was hard, but because nothing before this asked "does this button rerun the
sim?" It came in with the export feature itself; nothing regressed. It just was never
built to read what the rest of the section already knows how to read.

## Why "it just hangs" was actually "the whole site just hangs"

CLAUDE.md is explicit that this app runs **one `gthread` worker**, specifically so its
module caches stay warm across requests. That design has an unforgiving corollary: any
one request that runs long enough monopolizes the only thread handling requests at all.
A resimulated JHSAA season isn't a slow query — it's minutes of CPU across hundreds of
simulated matches. For as long as that export request ran, it wasn't just the exporting
tab that looked broken; every other page on the site was waiting behind it. This is the
same family of incident CLAUDE.md's "module-global caches under the threaded worker"
section already warns about (`docs/AAR-cache-invalidation-scope-lineup-stall.md` et
al.) — expensive, avoidable work landing on the one thread that has to keep serving
everyone — just via a different mechanism: not a cache miss cascading into a rebuild,
but a feature that never looked for a cache (or an archive) to hit in the first place.

## The fix

Added `research_export._load_archived_jhsaa_season(year, gender)`, which reconstructs
the exact dict shape `jhsaa.run_season()` returns — `{"teams", "groups", "awards"}` —
entirely from the persisted archive:

- `world.get_jhsaa(world_id, world_year, gender)` for standings/brackets/awards
  (`world_year` is the inverse of `world.jhsaa_season_year`: `year - BASE_YEAR - 1`).
- One bulk query against `world_jhsaa_dual` for the whole gender/year (not per school),
  grouped in Python into each team's `.schedule`.
- `jhsaa.load_schools(gender)` + `jhsaa.build_roster(school, season_year, salt)` for
  programs and rosters — both are deterministic, cheap, **pure generation** (name/rating
  RNG only) with no match simulation, exactly like every other `/jhsaa/*` page already
  relies on.

`build_jhsaa` now defaults to this instead of `jhsaa.run_season(...)`; the `season=`
injection point tests already used is untouched, so existing coverage kept working
unmodified. Read-only throughout — no world is created or advanced to serve an export.

One acknowledged trade-off, called out in the export's own `manifest.json` rather than
silently accepted: programs/rosters reflect the **current** association config
(renames, sponsorship, play-up) applied to an older archived year's results, since
`load_schools()`/`build_roster()` aren't re-derived per historical year. That mirrors
how the rest of the app already presents historical box scores (`seasonmode._pid_index`
does the same thing for college), so it's an existing convention, not a new gap — but
it's exactly the kind of thing that reads as "obviously correct" until someone exports
an old year for a renamed school and the numbers don't quite match what they remember.

## What to check first if this looks wrong later

- **An export is slow again.** Grep for `jhsaa.run_season(` or `sm.advance(` — or
  anything that plays a dual — inside `app/research_export.py`. There should be none;
  every builder should be reading a table, not a simulator.
- **A JHSAA export is empty or 400s.** Check `world.get_jhsaa(world_id, world_year,
  gender)` directly for that year — `_load_archived_jhsaa_season` raises `ExportError`
  rather than falling back to a resimulation, on purpose (see the "no graceful
  fallbacks on world resolution" rule elsewhere in this file — a silent resim-fallback
  here would just reintroduce the hang under a different trigger).
- **Numbers look off for an old archived year.** Check the trade-off above first —
  it's very likely a since-renamed or since-desponsored school, not a data bug.
- **The college exporter added alongside this fix is slow.** It should only ever read
  `seasonmode`'s persisted `duals`/`standings`/`cta_rankings` tables and rebuild
  rosters via `ncaa.build_roster` (cheap, no simulation) — same shape of guardrail
  applies.

# AAR — name_era silently self-reset to 2074 and scrambled 47 seasons of names

Owner incident, 2026-09-06 (a JHSAA lab save, 47 seasons). Reported as "the
players are scrambled" — year, teams, records, and history all correct, only the
regenerated roster/player NAMES wrong. It took most of a night because the first
several hours chased the wrong file; the actual cause was one integer in the save.

## Root cause
`jhsaa.name_era()` gates the name draw: a cohort entering >= name_era uses the new
weighted-US draw, earlier cohorts use the legacy draw. When the stored
`world_setting` row is missing/empty, `_resolve_era` self-configures it to
`BASE_YEAR + max(archived world_jhsaa.year) + 2`. On a 47-season save that is
**2074** — past every player who exists — so EVERY cohort flips to the legacy
draw. Names are regenerated from (salt, identity, era); records/history/awards are
stored strings and stay correct. Result: exactly "year right, names wrong."

The save's true boundary was **2031** (it really did switch name styles that
year). The self-config default assumes existing archives used the legacy draw and
preserves them by setting the era ABOVE them — which is backwards for any save
whose archived history is already new-style. Something cleared the stored row
(the owner had recently had the corner-year display changed; the row was absent
and re-resolved to 2074 on a later load).

## The two-hour detour (worth recording)
The owner runs the game via `scripts/jhsaa_lab_server.sh`, which binds
`TENNIS_DB_PATH=/tmp/jhsaa_lab.db` — a SEPARATE file from the repo's `tennis.db`.
Every diagnostic run and upload targeted `tennis.db` (a fresh 1-season decoy,
salt `doqy8fmq`), never the real universe at `/tmp/jhsaa_lab.db` (salt
`ee02d43bcf5e0883`, 47 seasons). The boot line added in
`AAR-dbpath-probe-race...` (`save [JHSAA LAB]: <path>`) exists precisely to end
this, but the owner's running build predated it. **When a save "looks wrong",
identify WHICH FILE before what's in it** — and lab mode's separate DB is the
first thing to check.

## The fix
`scripts/fix_name_era.py` (and the inline one-shot the owner ran): read the save
read-only, classify a sample of archived box-score names as new- vs legacy-style
by rebuilding each roster once each way, and take the boundary entry year as the
correct name_era. Verify it reproduces the archive (~90% is the ceiling —
transfers and depth-fill regenerate differently) and that it beats the current
value by a wide margin before writing only the single `jhsaa_name_era` row. It
correctly REFUSES on an already-correct save (no improvement). The owner's ran
`2074 -> 2031`, names restored.

## Prevention (follow-ups, not yet done)
- `_resolve_era`'s self-config is unsafe when it can REINTERPRET existing
  archives. name_era should never silently move once a save has archived seasons
  built under a known era; if the row is lost, it must be re-derived FROM the
  archive (which style the stored names actually are), not from `max(year)+2`.
- A lab save living in `/tmp` is one reboot from gone. The launcher should default
  to a persistent path, and the app should refuse to silently create a new world
  where an existing save was expected.

# Agent brief: NCAA team logos → schools

**Goal:** Every school in `data/ncaa/*.json` shows a logo next to its name in
the web UI (rankings, standings, team pages), mirroring how player country
flags work.

> Status: implemented on branch `claude/epic-fermi-qzte09`. An agent's job
> here is to **verify/extend**, not build from scratch.

## Context — what already exists

- `scripts/fetch_team_logos.py` — fetches logos from ESPN's public CDN
  (`a.espncdn.com/i/teamlogos/ncaa/500/<id>.png`; the ITA/NCAA sites return
  403 to automated requests, so ESPN is the source). Matches each school
  string to an ESPN team id via name normalization + aliases + fuzzy
  fallback. `--dry-run` prints a match report; `--no-placeholders` skips
  generated badges.
- `app/web/static/logos/<slug>.png` — 1,086 logos (748 real ESPN, 338
  generated monogram placeholders for schools ESPN doesn't track).
- `data/ncaa/logos.json` — the `{school name: {slug, espn_id, placeholder?}}`
  mapping the UI reads.
- `app/web/formatters.py` — Jinja filters `team_logo` (inline `<img>`),
  `team_logo_src` (bare URL), `has_team_logo`, registered in
  `app/web/server.py`.
- Wired templates: `rankings.html`, `season_standings.html`,
  `teams_index.html`, `teams.html`. CSS: `.team-logo-img` in
  `app/web/static/css/app.css`.

## Tasks

1. **Verify wiring.** Boot the app (`pip install -r requirements.txt`, then
   `app.web.server:create_app`) and confirm each of those four pages emits
   `/static/logos/...png` `<img>` tags and the assets serve 200. The
   school→logo lookup keys on the **exact** school string in
   `data/ncaa/*.json` — flag any mismatches.
2. **Audit coverage.** Run `python3 scripts/fetch_team_logos.py --dry-run` and
   confirm all 1,086 schools resolve (real or placeholder). Investigate any
   school rendering no mark.
3. **Improve match quality.** Spot-check that real logos map to the *correct*
   school (the fuzzy fallback can mis-map similar names, e.g. two "St."
   schools). Fix by adding entries to the `ALIASES` dict in the script, then
   re-run.
4. **Extend to remaining views** (if desired): wire `team_logo` /
   `team_logo_src` into the bracket and schedule/dual templates the same way.
5. Keep logos ≤128px + PNG-optimized; run `pytest` (161 tests should pass);
   commit and push to `claude/epic-fermi-qzte09`. Do **not** open a PR unless
   asked.

## Constraint

Logos are trademarked school marks — identification-only use in a
non-commercial sim, documented in `app/web/static/logos/README.md`. Don't
remove that NOTICE.

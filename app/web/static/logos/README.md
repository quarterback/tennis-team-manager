# Team logos

School logo marks rendered inline beside team names in the rankings,
standings, schedule, and team pages — the same role the country flags play
for players.

## Provenance & usage

These PNGs were fetched from ESPN's public team-logo CDN
(`a.espncdn.com/i/teamlogos/ncaa/500/<id>.png`) by
[`scripts/fetch_team_logos.py`](../../../../scripts/fetch_team_logos.py),
which matches each school string in `data/ncaa/*.json` to ESPN's universal
NCAA team id.

**The logos are the trademarks and property of their respective
institutions.** They are included here purely to identify schools in a
personal, non-commercial tennis simulator — nominative/identifying use, the
way a fan project or a sports scoreboard shows a team mark. They are not
endorsed by, affiliated with, or licensed from the schools, the NCAA, the
ITA, or ESPN. If you fork this for any commercial purpose, replace or remove
them.

## Mapping & rendering

- `data/ncaa/logos.json` — `{school name: {slug, espn_id}}`. The slug is the
  PNG filename stem (`TCU` → `tcu.png`, `NC State` → `nc-state.png`).
- `app/web/formatters.py` exposes the Jinja filters `team_logo` (ready-made
  inline `<img>`), `team_logo_src` (bare URL for crest boxes), and
  `has_team_logo`.
- Schools with no known logo (some D2/D3 programs ESPN doesn't track) are
  simply absent from the map and render with no mark — exactly like an
  unknown flag. No broken images.

## Conventions

- Source PNGs are square (originally 500×500), downsized to ≤128 px and
  PNG-optimized; the template scales them to ~1.4em. Transparent background.
- To refresh or extend coverage, re-run `python3 scripts/fetch_team_logos.py`
  (use `--dry-run` first to see the match report). Add hand mappings to
  `ALIASES` in the script for any school the matcher misses.

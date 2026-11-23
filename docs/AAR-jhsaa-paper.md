# AAR: the paper (`/jhsaa/paper`, `app/jhsaa_paper.py`)

Owner ask, 2026-11: a JHSAA season is simulated whole at week 0, so every page is
written from the finished archive and there is no way to follow a season, its
players or its storylines while it happens. The ask was a 90s local daily's
running coverage, inside the game, with nothing separate to run.

## What shipped

**The Paper tab** (`/jhsaa/paper`, beside Front page). An area daily, "The
<Area> Courier", covering one gazetteer area's programs (25 to 50 is the right
size; the default is the area nearest 35, and the choice sticks per save in
`worldconfig` key `jhsaa_paper_area`). One edition at a time, with an edition
picker, previous and next links, and an area picker.

**The edition calendar** (`editions`). A preseason edition the day before the
first dual, Tuesday and Friday mornings through the regular season, one the
morning the road to State opens, one every postseason morning that an area
program played or State/TOC results came in, and a closing edition. Built from
`world.jhsaa_match_dates`, the display calendar the schedule pages already use.
The 2042 boys season makes 39 editions for Juniper Highlands.

**The dated view** (`edition_view`). Every edition prints, deterministically:
results since the last edition with full flight lines (winner first, singles
before doubles, school tags), State and TOC results statewide ("Around the
state"), league standings as of that morning for every league an area program
plays in, and the fixtures before the next paper. Nothing dated on or after the
edition's morning is read. An unwritten edition still has all of this.

**Stories.** Written by an agent from `packet()` and stored per edition in
`world_jhsaa_paper` (`world_id, year, gender, area, edition`). The packet is the
dated view plus: each area program's record and league record to date, last
season's record, place and State finish, named head coaches, each player's
record and usual flight to date (preseason: last season's, plus who graduated),
the published regular-season schedule two weeks out, the paper's own earlier
stories, and its ledger of invented detail (assistant coaches, quotes, bylines)
so week 9 remembers week 2. `WRITER_BRIEF` holds the desk rules.

Three ways to write an edition:

1. In the game: start the server with `ANTHROPIC_API_KEY` set and press "Write
   the paper through this edition". A background thread writes every unwritten
   edition up to that one, in order, and the page refreshes itself.
   `JHSAA_PAPER_MODEL` overrides the model (default `claude-opus-5-5`).
2. An agent session: `python3 manage.py paper --season 2042 --gender boys --area
   "Juniper Highlands" --ed 3` prints the brief and the packet; the agent writes
   the JSON and stores it with `--file stories.json`. Against the lab save, set
   `TENNIS_DB_PATH=~/.tennis-team-manager/jhsaa_lab.db JHSAA_LAB_MODE=1`.
3. Off a research export, no database: `--export <zip> [--prior <last season's
   zip>] --stories <dir>`, and `--preview out.html` renders the written editions
   as one standalone page through the same template partial.

**A demo run**: `docs/paper/2042-boys-juniper-highlands/` holds the first three
editions of the 2042 boys season (preseason, Aug. 5, Aug. 8), written from the
packets by hand as the desk would. They follow on from each other: the preseason
asks who replaces Juniper Ridge's graduated No. 1, the Aug. 5 edition answers it,
the Aug. 8 edition covers the first loss.

## What was reused

`world.jhsaa_match_dates` and `jh_match_key` for dates; `world.unpack_lines` for
box scores; the home-row-only rule for reading each dual once; `jhsaa.
current_name` for renames; `jhsaa.load_schools` for area, league and class;
`jhsaa_coaches.season_heads` for coach names; `world.jhsaa_history_rows` for last
season; `jhsaa.build_roster` for grades (writer only); the research export's
shapes for the export loader.

## Deliberately not done

- No change to the sim, the advance, or the calendar. The season stays simulated
  at week 0; the paper replays it.
- The page never reads history or builds rosters: box scores unpack on first use
  for the duals an edition shows, and `_history` and `_ensure_grades` run only in
  the writer (CLAUDE.md rule 6 and the fifty-season rule).
- No ratings anywhere, in the packet or the page.
- College is not wired yet. The same packet idea fits it better (the season is
  live, so an edition can be written after each advance), but it reads season
  mode, not the JHSAA archive, and wants its own loader.
- No leak test as a gate; the tests do pin that the packet's results, standings
  and fixtures sit on the right side of the edition's morning.

## Traps

- **The writer only ever sees the packet.** The archive and the export hold final
  standings, awards and brackets; a writer shown those foreshadows the ending.
- **Postseason pairings are not in the two-week schedule.** They depend on
  results nobody has that morning. Regular-season fixtures are published in
  advance, so they are.
- **Write in order.** `start_writing` and the CLI write editions sequentially
  because each one reads the stories before it. Writing edition 12 before 11
  gives 12 nothing to follow up on.
- **A dual's `lines` are home-perspective**; the agate flips scores to the
  winner's side (`_flip_score`), the convention `state._jh_reported_lines`
  documents.
- **The shared real-season fixture in `tests/test_jhsaa_toc.py` fails on main**
  (`RuntimeError: JHSAA ward: field of 0`), as do two tests each in
  `test_jhsaa_routes.py` and `test_jhsaa_desk.py`. Not caused here; the paper's
  route test feeds the real 2042 export through the app instead.

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

## Addendum: the copy desk (same day, after the owner read the demo)

The first demo was written to a brief I condensed myself instead of the guides
the owner had already put in the repo, and it read like one template run three
times: "last season" 11 times, "No. 1 singles" nine times and "lineup" four
times in the preseason edition alone, every piece built on the same angle (who
replaces a graduated No. 1), AP errors throughout ("on Monday", "August 8"), and
a factual error (it said most of Juniper Ridge's champions were back; seven
regulars had graduated, which the packet did not yet show).

What changed:

- **The writer's instructions are the owner's guides, verbatim** (`DESK_DOCS`):
  `docs/writing-guide-update.md`, `docs/PREPS-STYLE-GUIDE.md`,
  `docs/paper/desk/AP-SPORTS.md` (the AP sports style sheet the desk applies)
  and `docs/paper/desk/HUMANIZER.md` (vendored from blader/humanizer, MIT, with
  its license). `WRITER_BRIEF` now only states the packet rules and the JSON
  shape.
- **`copy_desk()`** runs on every edition before it is saved: prose dashes, the
  preps guide's banned phrases, AP month abbreviations with dates, no "on"
  before a day, lowercase coach, numerals under 10, no exclamation points,
  headline periods, repeated openings across pieces, and edition-wide caps on
  the words that carried the first draft ("lineup" 2, "No. 1 singles" 3, "last
  season" 4, "graduated" 2). Quoted speech is exempt from the AP checks.
  `write_with_api` sends the findings back to the writer for up to two
  revisions and stores whatever remains under `desk`.
- **The preseason packet lists who graduated** (`graduated_from_last_season`,
  last season's regulars missing from this roster).
- The three demo editions were rewritten against the guides with a planned
  angle, lead type and headline archetype per piece, then run through the copy
  desk, Prosekeep (`check --profile vloora`, 0 findings) and Red Pen Editor
  (`inspect`; the headlines that echoed their own first sentences were rewritten).

Trap: the copy desk is the mechanical half. Angle rotation, history triggers and
whether a piece passes the consequence gate are still the writer's judgment,
which is why the guides go in whole rather than summarised.

## Addendum: leagues on second reference

The owner pointed out that papers abbreviate a league after first reference and
asked for it to be measured rather than assumed. Six real stories were read
(three Daily Herald tennis stories, one Sun-Times, two Boston Globe) and every
league reference counted; the table is in `docs/paper/desk/AP-SPORTS.md`. None
repeated a league's full name after the first use. Initials carried most later
references where a league has them; "the league," "league play" and division
names carried the rest.

What changed:

- `league_references()` gives every league in the packet a second reference
  (`league_names`): initials for a name of three or more words when no other
  league shares them and they do not already mean something (NIL, AAA, DSL);
  otherwise the league's own name without its tail. The writer brief tells the
  writer to spell a league out once per story and use that form after.
- The copy desk flags a league's full name used twice in one story, initials in
  parentheses after the full name, and initials that come before the full name.
  Headlines and quotes are exempt.
- The demo edition had one repeat ("the Kajaani League opener" in the same story
  as its first reference) and is fixed.

Not copied from the papers: the Herald's "Mid-Suburban League (MSL)" (against
AP) and the Chicago habit of using a home league's initials without ever
spelling it out.

Correction, same day: the owner overruled the "spell it out first" half of that.
The Courier is a local paper, and its readers know the area's leagues the way a
Chicago reader knows the CSL; spelling them out reads like a writer who has never
been here. The area's own leagues (`local` in `league_names`) now go by their
second reference from the first mention, headlines included, and the copy desk
only asks for a full name first on a league from outside the area. The writer
brief now tells the writer to write as someone who has covered these teams for
years and never explain a local school, league, rivalry or event. A short name
that is also the start of a school, town, county or area keeps the full name
(Juniper League next to Juniper Ridge and Juniper County). The demo editions were
rewritten to match: "the PAA champion," "DCL play," "1-0 Kajaani," "its Fiesta
opener," and league names in the headlines. The lesson for this desk: a style
rule written for a national wire is the wrong default for a hometown paper, and
the local papers' habits are the thing to copy, not to correct.


## Reconciliation: archive research and the working paper

The portable newsroom corpus from `claude/laughing-galileo-tiz0g1` is now
included under `docs/press/`. Its `VOICE.md` has priority for the 1980s–90s
newspaper register, article forms, agate, reporter roles and columnist character.
The prior JHSAA reporting guide and `PREPS-STYLE-GUIDE.md` remain available
for sport vocabulary, factual correctness and avoiding repetitive synthetic
features, but do not override the period-appropriate newspaper cadence.

The writer reads `VOICE.md` first and fails explicitly if it is absent.
The preseason, dated results, edition navigation, archive storage, API writer,
CLI and research-export path were preserved without changing match simulation.
No second independent newspaper implementation is introduced.

The copy desk previously blacklisted ordinary 1980s–90s sports verbs
(`edged`, `outlasted`, `cruised`, `rolled past`) despite those forms
being documented in the researched corpus. Those bans were removed. Banned
phrases are now checked against the writer's prose instead of the content of
quoted speech. Section labels such as `KUDOS —` are permitted in signed
columns. New tests check house-style precedence, those verbs and the fail-closed
loading rule.

**Remaining boundaries:** `packet()` is the evidence boundary and earlier
editions plus the invented-detail ledger are the initial continuity mechanism.
A full shared multi-game writer service, permanent writer-profile schema,
cross-game adapter and publication-wide storyline index are not implemented
by this reconciliation. The corpus is research, not a set of articles to copy.

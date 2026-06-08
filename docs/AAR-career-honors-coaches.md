# AAR — Career Honors, Coaches as Entities, Hall of Fame

## Segment summary

This segment built the awards/achievements system the original spec always
called for: persistent **career honors** stamped once and keyed to a player's or
coach's stable id (so they follow transfers and accumulate year over year),
**coaches promoted to first-class persisted entities** with their own pages and
free-agent movement at rollover, a full **awards slate** (Player/Coach of the
Year national + per conference, All-American, All-Conference, conference +
national titles), and a **Hall of Fame** that archives each season's winners
year by year. Shipped on `claude/awards-scheme` (PR #19); 127 tests green.

## The design mistake this rework exists to fix (owning it)

The honest root cause, which I should have surfaced at the start: the web layer
was built on a **pre-simulated "baseline" season** (`run_season` / `get_season`)
that fed *every* read surface — dashboard, rankings, standings, team and player
pages. That was the wrong foundation and not what the spec described. Season
mode (week-by-week progression) and player achievements were part of the
original design; the baseline shortcut quietly displaced them. The consequences
were exactly the problems the user kept hitting:

- a freshly-started league's dashboard showed a *finished* season ("Week 1" with
  21-0 records) because the baseline always simulates a complete year;
- per-year history had nowhere to live, because the baseline is a single
  throwaway snapshot keyed to the current year;
- awards could only be *recomputed live* for the current snapshot, with no
  natural place to persist or carry them forward.

I did not flag during the initial build that this contradicted the intended
season-mode-first design — the user had to discover it and direct the fix. That
is a design failure on my part, recorded here per the user's request. The
correct fix — **one model: season mode**, with the dual simulator demoted to an
"exhibition" side mode — is being done as a separate effort; this awards work
was deliberately built so it can repoint onto season mode with no schema change
(see "Handoff").

## What was built

### Career honors store (`app/honors.py`)
One flat `honors` table: `(subject_type, subject_id, year, school-as-of-then,
award, label, sort)`. `stamp()` is idempotent on the PK; `career()` /
`career_by_year()` read a subject's whole history; `years()` / `winners()` back
the Hall of Fame. Honors are **stamped once** during the awards phase and never
recomputed — querying by id is the career, and because the school is recorded
per season, honors follow players and coaches through transfers for free.

### Full award slate (`app/web/awards.py`)
`honor_records` / `coach_honor_records` compute, from the season + bracket:
National & Conference **Player of the Year**, **All-American** (First/Second/HM),
**All-Conference** (First/Second per conf), National & Conference **Coach of the
Year**, and **conference + national titles** credited to the whole roster and
the head coach. `stamp_world_honors()` is the awards-phase action (idempotent).

### Coaches as persisted entities (`app/coachreg.py`, `app/coachgen.py`)
Coaches are no longer regenerated from a school. They have a stable,
seat-independent `coach_id`, a registry (`coach` + `coach_seat`), their own pages
(`/coach/<id>`, rendering like player pages with honor badges + career panel +
profile + team record), and are linked from team pages. `coachgen` is the shared
engine-side generator so the web view and the rollover agree on identity.

### Coach free-agent movement (`world.coach_carousel`)
Runs **before** the transfer portal at rollover. ~10% of head coaches move up to
higher-prestige programs (a swap with the program they join). When a coach
moves, **up to half** of their old roster *may* follow — gated to players good
enough to make the new program's lineup (its 6th-best STR) — so a D3 coach
reaching D1 brings at most their very best. Honors key off `coach_id`, so a
coach's record follows them.

### Awards phase + Hall of Fame
Honors are stamped when a finished season is advanced, before the roster rolls
over (or on demand via `POST /world/awards`). The **Awards** page shows the
current season's full program; the **Hall of Fame** archives every stamped
season's national champion / POTY / COTY per universe, newest first — no manual
archiving (retirement archival was reframed, per the user, as this automatic
year-by-year award archive).

## Validation

- `pytest -q` → **127 passing** (honors, coaches, carousel, awards coverage
  added; carousel test deep-copies developed rosters to avoid mutating the
  shared cache — the production rollover clears that cache after).
- Headless-browser verified: player career-honors card, coach page, Awards page
  (POTY + Champions + COTY), Hall of Fame (all six universes), team→coach links.
- Sanity: National POTY = Jamie Jagielka (UTEP, 17-0); National COTY =
  NC State's head coach (the #1 team) — both consistent with the rankings.

## Handoff / not done by me

- **Season-mode unification** and the **staged season UI** are a separate
  effort. `docs/SPEC-staged-season-ui.md` is the shareable spec: the stage
  pipeline, the awards-phase split (Run Awards → Begin Next Season), and the
  exact hooks (`world.season_complete`, `awards.stamp_world_honors`,
  `honors.has_season`, `world.advance_week`). When the baseline is retired, only
  the *inputs* to `honor_records` / `coach_honor_records` move to season mode —
  the honors schema and readers stay put. Expect merge overlap in
  `app/web/awards.py` and the World hub template; everything else here is
  additive.
- **Coach movement** persists the carousel but does not yet model assistants
  moving or a coach being fired into unemployment — only head-coach upward swaps
  with their followers.
- Career match history on the player card still reads the current season (the
  by-year structure is ready for persisted multi-season data once season mode is
  the source).

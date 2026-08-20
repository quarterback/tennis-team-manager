# tennis-team-manager

A college dual-match **tennis season simulator and team manager**. Simulate
matches point by point, advance a living world year over year, and watch
rankings, recruiting, conferences, prestige, and the College bracket evolve across
**D1, D2, D3, and D4 — men's and women's** — each its own independent tournament.

It began as a deterministic singles match engine; the original
[`docs/README-genesis.md`](docs/README-genesis.md) keeps that starting point. Today
it runs as a full web app spanning the match engine, the season and postseason,
recruiting, prestige, and a pro tour.

> **Single-player sandbox, god-mode friendly.** One owner runs a whole tennis
> universe, peeks under the hood, and tweaks anything. Runs are seed-deterministic
> and reproducible. Injuries roll on real entropy, so save-scumming suits a
> single-player world — it's your world.

---

## Run

Needs **Python 3.11+**. The engine + CLI are pure standard library; the web UI
just needs Flask.

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 manage.py runserver --port 8000              # web app at http://localhost:8000
```

Then open <http://localhost:8000>. A local SQLite save is created at `./tennis.db`
automatically (override with `TENNIS_DB_PATH=/path/to/save.db`). Runs fully
offline once the deps are installed — great on a plane.

> **macOS:** don't use the default port 5000 — it's taken by AirPlay Receiver
> (you'll get a silent failure or a 403). Use `--port 8000` as above, or disable
> AirPlay Receiver in System Settings. Run from the repo root so `app/`,
> `engine/` and `generators/` import.

### `pip install` hangs, or "installs" and Flask still isn't there

The reliable fix is to throw the virtualenv away and build a fresh one — it's
cheap (three small packages) and it clears every cause below at once:

```bash
cd ~/path/to/tennis-team-manager      # always from the repo root
rm -rf .venv
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 manage.py runserver --port 8000
```

Sanity-check that pip is the venv's pip before blaming the install:

```bash
which python3 && pip -V     # both paths must be inside .../tennis-team-manager/.venv
```

What's usually actually wrong:

- **The venv isn't active** (a new terminal tab, or the `source` scrolled away), so
  `pip install` goes to the system Python. It succeeds, and the app still can't
  import Flask.
- **Installing into a distro-managed Python** — the giveaway is
  `ERROR: Cannot uninstall blinker … RECORD file not found. Hint: The package was
  installed by debian`. Nothing is broken; pip just refuses to touch an OS-owned
  package. In a fresh venv it never comes up (`pip install --ignore-installed
  blinker` forces past it if you're stuck with the system Python).
- **A stale venv built against a Python you've since upgraded** — Homebrew moving
  3.12 → 3.14 leaves `.venv/bin/python3` pointing at a runtime that no longer
  exists, and pip appears to hang.
- **A genuine hang** is nearly always the network, not pip. `pip install
  --timeout 10 -r requirements.txt` fails fast instead of sitting there, and the
  three deps are small enough that a slow index is obvious.

Rebuilding `.venv` never touches your save — `tennis.db` lives in the repo root,
not the virtualenv.

To play your **deployed** universe locally, pull its DB down first (don't run
both against it at once):

```bash
fly ssh sftp get /data/tennis.db ./tennis.db -a tennis-team-manager
```

Open the app, start a league, and advance the world week by week. The CLI also
drives the engine directly:

```bash
python3 manage.py simulate-match --seed 7 --pbp        # one singles match, play-by-play
python3 manage.py simulate-dual  --seed 7              # a College dual (3 doubles + 6 singles)
python3 manage.py season         --seed 2026 --division D1 --gender men
python3 manage.py ita-kickoff    --seed 2026 --gender men   # the opening season tournament
python3 manage.py simulate-gtt   --seed 7              # a co-ed Pro Tour dual
python3 manage.py runserver --port 8000
pytest                                                 # determinism + invariants (~10 min full)
```

---

## What's in the world

**The match engine** (`engine/`) — point→game→set→match scoring with a serve/rally
probability model, a fast game-level model for bulk sims, the College **dual**
format (3 doubles + 6 singles, clinch at 4), doubles, and box-score/play-by-play
render. Scoring rules toggle independently (`engine/format.py`): set and final-set
tiebreaks, 8-game pro sets, best-of-3/5, sudden-death deuce, with presets like
`grand_slam` and `pro_set_8`.

**Ratings** — every player carries an **STR** rating, a UTR-style number on a
distinctive 31–57 band, solved to a fixed point from results. Teams rank by a
**Power Index** and by **ITA-style team points** (résumé × schedule × league
strength), which feed the bracket.

**The season + postseason** — a full schedule, conference races, the **opening
season tournament**, conference tournaments (automatic bids), then the **College
championship**. A **Committee Seed Score** selects and seeds the field (Power Index
45%, ITA points 30%, a tiered automatic-bid championship bonus 15%, recent form
10%), holding selection, seeding, and bracketing as three separate questions. The
96-team D1 field (64 for D2–D4) draws into **four S-curve regions** with cosmetic
rotating names; region champions meet in the national semifinals. Then the
individual **singles** and **doubles** championships.

**The recruiting budget economy** — each program earns its roster. A recruiting
**budget** set by conference tier buys recruits that **cost** by star, from
blue-chip down to free walk-on. Blue-bloods fund deep and stack blue-chips; mid-
and low-majors build 4★/3★ cores; the top D3/D4 academic programs draw a thin
"gem" allocation. The guardrails live in [`CLAUDE.md`](CLAUDE.md) as tuned
game-design values.

**Dynamic prestige** — a program's prestige evolves each year by how it performs
against expectation, so a low-major that keeps overachieving climbs and recruits up
a budget tier, and a sliding blue-blood drifts down. The drift stays self-correcting
and bounded, and the journey shows on the Data Portal.

**The Analytics Bureau** — talent intelligence with zero scouting fog: every
player's true ceiling beside where they actually sit (buried studs, aid
misallocations, best-fit landing spots), plus a **Lineup Lab** strip-plot comparing
every team's singles ladder across a conference and ranking relative league strength.

**The JHSAA** — Jefferson, a fictional US state, runs its own high-school tennis
association *inside this engine*: 862 girls'/777 boys' programs across nine
classifications (1A-9A) playing a full
simulated season, browsable at `/jhsaa`, whose graduating seniors are Jefferson's
entries on the college recruiting board. Its own dual formats, double round-robin
district schedule, TOSS-based seeding, a multi-round State postseason with earned
(never bye-only) recovery rounds, résumé-based postseason awards (All-State/
All-Region/All-District), program archetypes, and a "playing up" mechanic for
small blue-bloods. See `docs/DESIGN-jhsaa-high-school-season.md` and the many
`docs/AAR-jhsaa-*.md` reports.

**More** — a season-long **recruiting** pipeline (a junior pool, signings, the
transfer portal), **coaches** (careers, localism, moves), an ATP/WTA-style **Data
Portal** newsroom, a **Pro Tour** (GTT) college-to-pro pipeline, program **honors /
hall of fame / archives**, and a live **editor** to move players, set lineups, and
override prestige, academics, and scholarship limits.

**The JHSAA** — Jefferson's high-school season, simulated and browsable at `/jhsaa`
(districts, brackets, TOSS rankings, awards, program pages). Its graduating
seniors feed the college recruit board. For offline analysis of many independent
seasons without touching the college/pro world, see **JHSAA Lab** below.

---

## JHSAA Lab — simulate standalone high-school seasons

A separate tool for generating and multi-year-advancing JHSAA seasons **on their
own**, decoupled from the college/pro sim — useful for offline data analysis
(many seasons, cohort aging/graduation) without building a whole college world
each time.

```bash
scripts/jhsaa_lab_server.sh [db-path] [port]   # defaults: /tmp/jhsaa_lab.db, port 5050
```

Then open `http://localhost:<port>/jhsaa-lab`. It's always safe to run alongside
your real app (default port 5000) — it's bound to its **own scratch database**
(never your real save) and the `/jhsaa-lab*` routes only exist when
`JHSAA_LAB_MODE=1`, which the launcher script sets for you.

From the page:
- **Generate new season** — wipes this scratch DB and starts a fresh multi-year
  run with a new set of programs/cohorts (optional `salt` to vary the draw).
- **Advance N years** — ages the *same* cohorts forward (1–50 years at a time),
  graduating and replacing them, to build a real multi-year history to browse.

Both run in the background and the page polls for progress — expect **~10
minutes per season, cold**. That's not a bug: the normal app hides this
behind a boot-time cache warm that isn't there in a fresh lab process, so
this is the real cost of simulating ~600 programs across both genders.

---

## Layout

```
engine/            match engine — state, rally, match, fast, dual, doubles, gtt, format, render, tournament
app/               the world: divisions, programs, rosters, prestige, season + postseason, recruiting, coaches…
  world.py           the living world — year rollover, development, portal, prestige momentum
  seasonmode.py      schedule, results, Power Index, College bracket draw + advancement
  recruit_economy.py the budget-by-tier recruiting economy (costs, floors, bands)
  regions.py         S-curve regional bracket structure + cosmetic region names
  scout_intel.py     Analytics Bureau (underplaced, playing time, fit, Lineup Lab)
  str_rating.py / rating.py   STR + Power Index
  recruiting.py / scholarships.py / economy.py   recruiting + scholarship layers
  gtt_seasonmode.py  the Pro Tour league
  web/               the Flask app — server.py (routes), state.py (data), templates/
docs/              DESIGN doc + ~70 AARs (one per change, the running changelog)
analytics/         The Clinch Report — offline static-site analytics sidecar (see analytics/README.md)
CLAUDE.md          agent guardrails — the recruiting/prestige economy invariants
manage.py          CLI;  wsgi.py / Dockerfile / fly.toml / Procfile  — deploy (Fly)
tests/             determinism, scoring, economy, bracket, world-rollover invariants
```

Most tests assert **invariants and determinism**.

---

## Docs

- [`docs/GUIDE.md`](docs/GUIDE.md) — **the game guide.** A complete, sectioned
  manual to how the game actually plays: divisions and dual formats, the
  recruiting/scholarship economy, injuries, the transfer portal, rankings,
  championships, Jefferson, the JHSAA, the pro tour — with an appendix
  indexing every AAR by topic. Also rendered in-app under **Tools → Guide**.
  Point an LLM sidecar here for "how does this game work" questions.
- [`CLAUDE.md`](CLAUDE.md) — the design invariants (the budget economy, walk-on
  sourcing, injuries, dynamic prestige). Read it before changing numbers.
- [`docs/`](docs/) — an AAR (after-action report) per change documents how each
  system works and why.
- [`docs/README-genesis.md`](docs/README-genesis.md) — where this started.

# tennis-team-manager

A college dual-match **tennis season simulator and team manager**. Simulate
matches point by point, advance a living world year over year, and watch
rankings, recruiting, conferences, prestige, and the NCAA bracket evolve across
**D1, D2, D3, and D4 — men's and women's** — each its own independent tournament.

It began as a deterministic singles match engine (the original
[`docs/README-genesis.md`](docs/README-genesis.md) is kept as an artifact of that
starting point). It's since grown well past that: a full web app with a season
engine, a recruiting **budget economy**, **dynamic year-to-year prestige**,
regional NCAA brackets, an analytics bureau, a pro tour, juniors, and coaches.

> **Single-player sandbox, god-mode friendly.** It's built for one owner to run a
> whole tennis universe, peek under the hood, and tweak anything. Most things are
> seed-deterministic so a run is reproducible — the one deliberate exception is
> **injuries**, which roll on real entropy (save-scumming is fine; it's your world).

---

## Run

```bash
pip install -r requirements.txt
python3 manage.py runserver            # web app at http://localhost:5000  (PORT to override)
```

Open the app, start a league, and advance the world week by week. The CLI also
drives the engine directly:

```bash
python3 manage.py simulate-match --seed 7 --pbp        # one singles match, play-by-play
python3 manage.py simulate-dual  --seed 7              # an NCAA dual (3 doubles + 6 singles)
python3 manage.py season         --seed 2026 --division D1 --gender men
python3 manage.py ita-kickoff    --seed 2026 --gender men   # the D1 season opener
python3 manage.py simulate-gtt   --seed 7              # a co-ed Pro Tour dual
python3 manage.py runserver --port 8000
pytest                                                 # determinism + invariants (~10 min full)
```

---

## What's in the world

**The match engine** (`engine/`) — point→game→set→match scoring with a serve/rally
probability model, a fast game-level model for bulk sims, the NCAA **dual** format
(3 doubles + 6 singles, clinch at 4), doubles, and box-score/play-by-play render.
Scoring rules are toggleable (`engine/format.py`): no-ad, set/final-set tiebreaks,
8-game pro sets, best-of-3/5 — presets like `ncaa_dual` and `grand_slam`.

**Ratings** — every player carries an **STR** rating (a UTR-style number on a
distinctive 31–57 band, solved to a fixed point from results). Teams are ranked by
a **Power Index** and by **ITA-style team points** (résumé × schedule × league
strength), which feed the bracket.

**The season + postseason** — a full schedule, conference races, the **ITA Kickoff
& Indoor** opener, conference tournaments (automatic bids), then the **NCAA
championship**. The field is selected and seeded by a **Committee Seed Score**
(Power Index 45% + ITA points 30% + a tiered AQ championship bonus 15% + recent
form 10%) — selection, seeding, and bracketing kept strictly separate. The 96-team
D1 field (64 for D2–D4) is drawn into **four S-curve regions** with cosmetic
rotating region names; region champions meet in the national semifinals. Then the
individual **singles** and **doubles** championships.

**The recruiting budget economy** — rosters are *earned*, not flat. Each program has
a recruiting **budget** set by its conference tier, and recruits **cost** budget by
star (blue-chip down to free walk-on). Blue-bloods fund deep and stack blue-chips;
mid/low-majors build 4★/3★ cores; the top D3/D4 academic programs get a thin "gem"
allocation. (The guardrails live in [`CLAUDE.md`](CLAUDE.md) — these are tuned
game-design values, not bugs.)

**Dynamic prestige** — a program's prestige is **not static**. Each year it drifts
by how it over- or under-performs its expectation, so a low-major that keeps
overachieving climbs (and recruits up a budget tier) while a sliding blue-blood
falls — self-correcting and bounded. The journey is visible on the Data Portal.

**The Analytics Bureau** — god-mode talent intelligence: every player's true
ceiling vs. where they actually sit (buried studs, aid misallocations, best-fit
landing spots), plus a **Lineup Lab** strip-plot comparing every team's singles
ladder across a conference and ranking relative league strength.

**More** — a season-long **recruiting** pipeline (a junior pool, signings, the
transfer portal), **coaches** (careers, localism, moves), an ATP/WTA-style **Data
Portal** newsroom, a **Pro Tour** (GTT) college-to-pro pipeline, program **honors /
hall of fame / archives**, and a live **editor** to move players, set lineups, and
override prestige/academics/scholarship limits.

---

## Layout

```
engine/            match engine — state, rally, match, fast, dual, doubles, gtt, format, render, tournament
app/               the world: season + postseason, ratings, recruiting, prestige, brackets, coaches…
  ncaa.py            divisions, programs, rosters, prestige, build_roster
  world.py           the living world — year rollover, development, portal, prestige momentum
  seasonmode.py      schedule, results, Power Index, NCAA bracket draw + advancement
  recruit_economy.py the budget-by-tier recruiting economy (costs, floors, bands)
  regions.py         S-curve regional NCAA bracket structure + cosmetic region names
  scout_intel.py     Analytics Bureau (underplaced, playing time, fit, Lineup Lab)
  str_rating.py / rating.py   STR + Power Index
  recruiting.py / scholarships.py / economy.py   recruiting + scholarship layers
  gtt_seasonmode.py  the Pro Tour league
  web/               the Flask app — server.py (routes), state.py (data), templates/
docs/              DESIGN doc + ~70 AARs (one per change, the real changelog)
CLAUDE.md          agent guardrails — the recruiting/prestige economy invariants (READ before "fixing")
manage.py          CLI;  wsgi.py / Dockerfile / fly.toml / Procfile  — deploy (Fly)
tests/             determinism, scoring, economy, bracket, world-rollover invariants
```

Most tests assert **invariants and determinism**, not golden values.

---

## Docs

- [`CLAUDE.md`](CLAUDE.md) — the load-bearing design invariants (the budget economy,
  walk-on sourcing, injuries, dynamic prestige). Read it before changing numbers.
- [`docs/`](docs/) — an [`AAR`](docs/) (after-action report) per change is the de
  facto changelog: how each system works, why, and the mistakes it avoids.
- [`docs/README-genesis.md`](docs/README-genesis.md) — where this started.

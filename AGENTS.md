# AGENTS.md

Context for coding agents working on **tennis-team-manager**. Read this first, then the
relevant doc in `docs/`, then the code. `CLAUDE.md` is the exhaustive guardrail reference —
this file is the front door.

---

## What this project is

A tennis management simulator built around **one save = one world**. A world contains three
linked competitive layers plus a separate analytics tool:

- **College** — NCAA divisions D1–D4, men and women. Recruiting, scholarships, transfer
  portal, ITA/NCAA postseason.
- **The JHSAA** — the high-school association of **Jefferson**, a fictional US state (`JF`).
  Roughly 1,800 programs across twelve championship groups, both genders, simulated in full
  with its own postseason ladder, individual tournaments and JV season. This is the largest
  and most intricate system in the repo.
- **GTT** — the professional tour/league layer.
- **`analytics/`** — a standalone static-site sidecar ("The Clinch Report") that ingests
  research-export zips and builds team/player/analysis pages. **It never touches the game
  database or app code.**

Everything is **seed-deterministic**: the same seed and inputs reproduce the same result.

---

## Setup and commands

```bash
pip install -r requirements.txt

# CLI — seed-deterministic simulation entry points
python3 manage.py simulate-match --seed 7
python3 manage.py simulate-dual  --seed 7
python3 manage.py gen-players --seed 7 --n 8
python3 manage.py presets
python3 manage.py initdb

# Web app
gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 32 --timeout 300 wsgi:app

# Tests (106 files)
python3 -m pytest tests -q
python3 -m pytest tests/test_jhsaa_ladder.py -q      # one file
```

**Analytics sidecar** runs separately and has its own loop:

```bash
cd analytics
python3 build.py                        # re-render from cache
python3 build.py path/to/export.zip     # ingest a season, then render
python3 build.py --latest 2 --no-player-pages   # practical default; full build is GBs
cd site && python3 -m http.server 8000  # serve over http://, not file://
```

See `analytics/README.md` for the full operational detail.

---

## Repo map

| Path | What's in it |
|---|---|
| `engine/` | Match simulation: points, games, sets, duals, formats, doubles, box stats. Pure logic, no web. |
| `app/` | Flask app, world/save state, and every league system — `jhsaa.py`, `jhsaa_individuals.py`, `jhsaa_jv_state.py`, `ncaa`, `gtt`, `injuries`, `development`, `economy`, `coaches`. |
| `app/web/` | Routes and templates. |
| `generators/` | Player, name, school and place generation. |
| `data/` | Curated data: name pools, school lists, Jefferson geography. |
| `docs/` | 250+ documents. See conventions below. |
| `analytics/` | The standalone sidecar. Separate concerns, separate rules. |
| `tests/` | 106 test files. `conftest.py` at repo root forces a separate test DB — do not weaken it. |
| `saves/` | Save slots. Never commit or clobber. |

---

## Documentation conventions

Read the relevant document **before** changing a system, and write one **after**.

- **`AAR-*`** — after-action reports. What was built, why, what broke, what the traps are.
  These are the most valuable files in the repo. If a system has an AAR, read it first.
- **`DESIGN-*`** — intent and structure for a system, usually written before it was built.
- **`BRIEF-*`** — a question being explored, feasibility work.
- **`FEATURE-*`** — a specific feature spec.
- **`GAZETTEER-jefferson.md`** — the geography of Jefferson: areas, counties, towns,
  populations, real-world mapping. Load it before reasoning about anything spatial.
- **`GUIDE.md`** — player-facing guide.

---

## Workflow

1. **Read the AAR** for the system you're touching. Most surprising behaviour is documented.
2. **Inspect existing code before writing new code.** Report which functions you intend to
   reuse for ingestion, scoping, seeding, bracket generation and archiving.
3. **Implement the smallest change that works.** Prefer a new column or view over a new page;
   a new function over a new module.
4. **Write tests that read the rendered output**, not just return values. An empty-state test
   cannot see a page.
5. **Write an AAR** describing what changed, what you reused, what you deliberately did not
   do, and any trap the next agent will hit.

---

## The rules that will bite you

### 1. Join on `program_id`, never a display name
Roughly 300 of 1,644 programs have been renamed across the archive, and an id often matches
neither the old name nor the new one.

### 2. Player names are not unique
Multiple players share a name across the association. **Join on `player_id`.** Name-keyed
lookups silently return the wrong player.

### 3. `classification` is enrollment; `championship_group` is who they play
These differ for a handful of programs — Condotti Vanguard Academy and Romero-Finniski are
3A by enrollment and compete in 7A under a permanent play-up exemption. **Every competitive
comparison keys on `championship_group`.**

### 4. Never surface player ratings in user-facing text
OVR / `current_grade` / `potential_grade` are backend calibration. They are invisible
in-world and nobody talks about a player that way. Describe players by **record, flight,
position, honors, opponents beaten**. Ratings are legitimate inputs to analysis; they are
never output.

### 5. Tennis vocabulary
A player plays **matches**, at a **flight** (or position, or line), inside a **dual**. A
**court** is the physical surface — "courts won" is wrong. Aggregates over flights are
**flight share**. Never call a lineup or format a "card"; say **format** (e.g. 4S/5D) or
**lineup**.

### 6. Derive, never hard-code
Dual format shapes, development curves, gap-response slopes, growth rates — all of these have
been changed at least once, and every hard-coded copy went stale silently. Derive them from
the data or read them from config. The regular-season format has already swapped from 5S/2D
to 3S/4D; the match engine's gap response has been rebuilt twice.

### 7. Determinism is a contract
Same seed and inputs, same output. **Injuries are the one intentionally non-deterministic
system** (`app/injuries.py`) — everything else must reproduce.

### 8. One world per save, one clock, one advance surface
`/world/advance` is the only place the world moves forward, and the offseason is a ladder of
single steps, never a bundle. "Seed" means three different things in this codebase; check
which one you're touching.

### 9. Varsity-only where it matters
The JHSAA plays a JV season and both levels live in the same tables. Filter on `level == "v"`
at the ingestion chokepoint. A missing `level` means varsity (pre-JV seasons). JV data must
never inflate varsity records, and the analytics sidecar must never see it.

### 10. Fixtures hide the real path
A small fixture can exercise a code path that production never takes — a fixture that crowns
12 regions will never run the 20-region branch, and every test passes while the real path has
never executed once. When a rule depends on a count, build a fixture at the real scale.

---

## Testing notes

- The suite **must not share a database with the app.** `conftest.py` handles this at repo
  root and it exists because running the tests once deleted a real save. Do not weaken it.
- Tests live in `tests/` (106 files). Analytics has its own suite: `python3 -m pytest
  analytics/tests -q`.
- Assertions should read rendered HTML where a page is involved.
- Add or update tests for what you change, even if nobody asked.

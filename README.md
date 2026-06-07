# tennis-team-manager

My longheld white whale of a tennis text simulation — a college dual-match
tennis simulator built on the O27 baseball engine's substrate (deterministic
seeded engine, global name generators, currency/recruiting/motivation
systems) rather than a from-scratch fork.

See [`docs/DESIGN-college-tennis-sim-fork.md`](docs/DESIGN-college-tennis-sim-fork.md)
for the full architecture + roadmap. This commit is the **P0/P1 skeleton**:
a runnable, deterministic singles match engine, a fast bulk model, a
dual-match team layer, and the lifted name generators.

## Layout

```
engine/       match engine
  state.py    Player (9 attributes), PlayerStats, MatchState
  rally.py    serve + rally probability tables (talent shifts the distribution)
  match.py    point→game→set→match scoring; simulate_match()
  fast.py     game-level hold-probability model (bulk juniors/HS); simulate_fast()
  dual.py     NCAA dual: 3 doubles + 6 singles, clinch at 4; simulate_dual()
  format.py   MatchFormat — the toggleable scoring rules (see below)
  render.py   box score + play-by-play text
generators/   make_name_picker + zaryan_names + data/names/* (lifted from O27)
app/          db.py — SQLite persistence scaffold
tests/        determinism, scoring correctness, stat invariants, names, dual
manage.py     CLI
docs/         design + roadmap
```

## Run

```bash
python3 manage.py simulate-match --seed 7 --pbp
python3 manage.py simulate-match --seed 7 --format pro_set_8
python3 manage.py simulate-dual  --seed 7
python3 manage.py gen-players    --seed 7 --n 8 --gender female --region european
python3 manage.py presets
pytest          # determinism + scoring + invariants
```

Everything is **seed-deterministic**: same seed + flags ⇒ identical
transcript and scoreline.

## Match formats (toggleable rules)

`engine/format.py` exposes each scoring variant as an independent switch
(`MatchFormat`), so they map cleanly to UI checkboxes:

| Toggle | Meaning |
| --- | --- |
| `no_ad` | sudden-death deciding point at deuce |
| `set_tiebreak` / `set_tiebreak_target` | tiebreak at games-all (off ⇒ advantage set) |
| `final_set_tiebreak` / `final_set_tiebreak_target` | **10-point tiebreak in lieu of a third set** |
| `pro_set` / `pro_set_games` | **8-game pro set** — one set to 8, tiebreak at 8-8 |
| `best_of` | 3 or 5 sets |

Presets: `ncaa_dual`, `best_of_3_mtb` (default), `grand_slam`, `advantage`, `pro_set_8`.

## What's next

P2+ in the design doc: leagues/seasons across D1/D2/D3 × M/W, the
modified-UTR rating + convergence pass, junior/HS circuits, and the
recruiting/scholarship layer.

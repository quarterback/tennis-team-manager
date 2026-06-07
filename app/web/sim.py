"""
Web ↔ engine glue for the Dual Simulator.

Turns a ranked school into a deterministic 6-player squad (strength scaled
from its Power Index), runs one dual at the chosen format/fidelity for the
displayed result, and estimates clinch probability with a fast Monte-Carlo
sweep — the "runs it thousands of times" the design promises.

Everything is seed-deterministic: same (home, away, seed, format) ⇒ same
squads, same transcript, same probability.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from engine import random_player, simulate_dual, Team
from engine.format import PRESETS
from generators import make_name_picker, region_preset

from .rankings_data import get_row, crest

SEASON_SEED = 2026
FIDELITIES = ["full", "fast"]


def _base_from_pi(pi: float) -> float:
    """Map a Power Index (~0.71–0.93) onto a player attribute base (~0.45–0.72)."""
    return max(0.40, min(0.75, 0.45 + (pi - 0.70) * 1.05))


def build_team(school: str, *, gender: str = "male") -> Team:
    """Deterministic 6-player squad for a school, strength scaled from its PI."""
    row = get_row(school)
    base = _base_from_pi(row.pi) if row else 0.55
    seed = (hash(school) & 0xFFFFFF) ^ SEASON_SEED
    rng = random.Random(seed)
    name_fn = make_name_picker(random.Random(seed ^ 0x5EED), gender=gender,
                               region_weights=region_preset("global"))
    singles = []
    for i in range(6):
        name, country = name_fn()
        # ladder: court 1 strongest → court 6 weakest
        b = base - i * 0.012
        singles.append(random_player(rng, name, country, base=b))
    return Team(name=school, singles=singles)


def _last(name: str) -> str:
    return name.split()[-1] if name else name


def _singles_label(full: str) -> str:
    parts = full.split()
    return f"{parts[0][0]}. {parts[-1]}" if len(parts) >= 2 else full


def _doubles_label(full: str) -> str:
    # synthetic doubles name is "First Last / First2 Last2"
    return " / ".join(_last(p.strip()) for p in full.split(" / "))


def _sides(result, home_won, label_fn):
    """Per-side rows: (name, won, [{g, w}, ...]) for home then away."""
    hp, ap = result.players[0], result.players[1]
    home_sets = [{"g": a, "w": a > b} for a, b in result.set_scores]
    away_sets = [{"g": b, "w": b > a} for a, b in result.set_scores]
    return [
        {"name": label_fn(hp.name), "won": home_won, "sets": home_sets},
        {"name": label_fn(ap.name), "won": not home_won, "sets": away_sets},
    ]


@dataclass
class DualView:
    home: dict
    away: dict
    home_points: int
    away_points: int
    winner_name: str
    doubles_point_name: str
    doubles: list
    singles: list
    win_prob: int          # home clinch probability (%)
    sims: int
    seed: int
    fmt_label: str
    fidelity: str


def run_dual_view(home_school: str, away_school: str, *, seed: int,
                  fidelity: str = "full", sims: int = 300) -> DualView:
    home = build_team(home_school)
    away = build_team(away_school)
    res = simulate_dual(home, away, seed=seed, fidelity=fidelity)

    doubles, singles = [], []
    for ln in res.lines:
        is_d = ln.slot.startswith("D")
        if not ln.completed:
            singles.append({"slot": ln.slot, "completed": False})
            continue
        label_fn = _doubles_label if is_d else _singles_label
        row = {
            "slot": ln.slot,
            "court": ln.slot[1:],
            "kind": "Dbl" if is_d else "Sgl",
            "completed": True,
            "sides": _sides(ln.result, ln.home_won, label_fn),
        }
        (doubles if is_d else singles).append(row)

    # Monte-Carlo clinch probability (fast model over a seed sweep).
    home_wins = 0
    for k in range(sims):
        mc = simulate_dual(home, away, seed=seed + 1 + k, fidelity="fast")
        if mc.winner == 0:
            home_wins += 1
    win_prob = round(100 * home_wins / sims) if sims else 50

    h_abbr, h_color = crest(home_school)
    a_abbr, a_color = crest(away_school)
    hr, ar = get_row(home_school), get_row(away_school)

    return DualView(
        home={"school": home_school, "abbr": h_abbr, "color": h_color,
              "rk": hr.rk if hr else "—", "rec": hr.rec if hr else ""},
        away={"school": away_school, "abbr": a_abbr, "color": a_color,
              "rk": ar.rk if ar else "—", "rec": ar.rec if ar else ""},
        home_points=res.home_points, away_points=res.away_points,
        winner_name=(home_school if res.winner == 0 else away_school),
        doubles_point_name=(home_school if res.doubles_point == 0 else away_school),
        doubles=doubles, singles=singles,
        win_prob=win_prob, sims=sims, seed=seed,
        fmt_label="NCAA dual (no-ad, 8-game doubles pro set, full 3rd set)",
        fidelity=fidelity,
    )

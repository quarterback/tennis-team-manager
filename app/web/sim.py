"""
Web ↔ engine glue for the Dual Simulator.

Runs a one-off dual between any two programs in a division×gender universe,
using their real persistent rosters (app.ncaa.build_squad), and estimates clinch
probability with a fast Monte-Carlo sweep. Seed-deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

from engine import simulate_dual
from app.ncaa import load_division, build_squad, crest
from .state import ranking_rows

FIDELITIES = ["full", "fast"]


def programs_for(division: str, gender: str) -> list[str]:
    return sorted(p.school for p in load_division(division, gender).programs)


def _last(name: str) -> str:
    return name.split()[-1] if name else name


def _singles_label(full: str) -> str:
    parts = full.split()
    return f"{parts[0][0]}. {parts[-1]}" if len(parts) >= 2 else full


def _doubles_label(full: str) -> str:
    return " / ".join(_last(p.strip()) for p in full.split(" / "))


def _sides(result, home_won, label_fn, home_school, away_school):
    hp, ap = result.players[0], result.players[1]
    return [
        {"name": label_fn(hp.name), "won": home_won, "school": home_school,
         "sets": [{"g": a, "w": a > b} for a, b in result.set_scores]},
        {"name": label_fn(ap.name), "won": not home_won, "school": away_school,
         "sets": [{"g": b, "w": b > a} for a, b in result.set_scores]},
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
    win_prob: int
    sims: int
    seed: int
    fmt_label: str
    fidelity: str
    # Panel captions sized to the dual's actual format (per-division shapes).
    doubles_label: str = "Win 2 of 3 — 1 team point"
    singles_label: str = "6 courts · 1 point each"


def run_dual_view(home_div: str, away_div: str, gender: str,
                  home_school: str, away_school: str, *,
                  seed: int, fidelity: str = "full", sims: int = 300) -> DualView:
    # Each side is loaded from its OWN division so an exhibition can pit talent
    # across levels (e.g. D1 vs D3) — the engine is division-blind, STR is one
    # global scale, so the gap simply shows up in the result. Gender is shared.
    home_progs = {p.school: p for p in load_division(home_div, gender).programs}
    away_progs = {p.school: p for p in load_division(away_div, gender).programs}
    home, away = home_progs[home_school], away_progs[away_school]
    hteam, ateam = build_squad(home), build_squad(away)
    # A cross-division exhibition plays the HOME side's format (the host stages it).
    from app.ncaa import dual_format
    fmt = dual_format(home_div)
    res = simulate_dual(hteam, ateam, seed=seed, fidelity=fidelity, dual_fmt=fmt)

    doubles, singles = [], []
    for ln in res.lines:
        is_d = ln.slot.startswith("D")
        if not ln.completed:
            # Abandoned at clinch: still played, so show who was on court and the
            # score it had reached (partial), flagged unfinished — never "not played".
            hp, ap = ln.result.players[0], ln.result.players[1]
            partial = ln.partial or []
            sides = [
                {"name": _singles_label(hp.name), "won": False, "unfinished": True,
                 "school": home_school, "sets": [{"g": a, "w": False} for a, _ in partial]},
                {"name": _singles_label(ap.name), "won": False, "unfinished": True,
                 "school": away_school, "sets": [{"g": b, "w": False} for _, b in partial]},
            ]
            singles.append({"slot": ln.slot, "court": ln.slot[1:], "kind": "Sgl",
                            "completed": False, "sides": sides})
            continue
        label_fn = _doubles_label if is_d else _singles_label
        row = {"slot": ln.slot, "court": ln.slot[1:], "kind": "Dbl" if is_d else "Sgl",
               "completed": True,
               "sides": _sides(ln.result, ln.home_won, label_fn, home_school, away_school)}
        (doubles if is_d else singles).append(row)

    home_wins = sum(1 for k in range(sims)
                    if simulate_dual(hteam, ateam, seed=seed + 1 + k, fidelity="fast",
                                     dual_fmt=fmt).winner == 0)
    win_prob = round(100 * home_wins / sims) if sims else 50

    # Ranks come from each side's own division (a rank is only meaningful within it).
    home_ranks = {r.school: r for r in ranking_rows(home_div, gender)}
    away_ranks = {r.school: r for r in ranking_rows(away_div, gender)}
    h_abbr, h_color = crest(home_school)
    a_abbr, a_color = crest(away_school)
    hr, ar = home_ranks.get(home_school), away_ranks.get(away_school)
    return DualView(
        home={"school": home_school, "abbr": h_abbr, "color": h_color, "div": home_div,
              "rk": hr.rk if hr else "—", "rec": hr.rec if hr else ""},
        away={"school": away_school, "abbr": a_abbr, "color": a_color, "div": away_div,
              "rk": ar.rk if ar else "—", "rec": ar.rec if ar else ""},
        home_points=res.home_points, away_points=res.away_points,
        winner_name=(home_school if res.winner == 0 else away_school),
        # Per-line doubles formats have no consolidated point to attribute.
        doubles_point_name=("" if res.doubles_point is None
                            else (home_school if res.doubles_point == 0 else away_school)),
        doubles=doubles, singles=singles, win_prob=win_prob, sims=sims, seed=seed,
        fmt_label=(f"{home_div} dual — {fmt.n_singles} singles + {fmt.n_doubles} doubles"
                   f" ({'doubles point' if fmt.doubles_team_point else 'doubles per line'},"
                   f" first to {fmt.clinch})"), fidelity=fidelity,
        doubles_label=(f"Win {fmt.n_doubles // 2 + 1} of {fmt.n_doubles} — 1 team point"
                       if fmt.doubles_team_point
                       else f"{fmt.n_doubles} pairs · 1 point each"),
        singles_label=f"{fmt.n_singles} courts · 1 point each",
    )

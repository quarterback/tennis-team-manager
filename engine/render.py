"""
Text renderers for a match result — box score + optional PBP.

Kept deliberately plain-text (the O27 `render/` layer grows templates
later); this is enough to eyeball a `simulate_match` run.
"""
from __future__ import annotations

from .match import MatchResult
from .state import PlayerStats


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def box_score(result: MatchResult) -> str:
    p = result.players
    lines: list[str] = []
    lines.append(f"{p[0].name} ({p[0].country})  vs  {p[1].name} ({p[1].country})")
    lines.append(f"Winner: {result.winner_name}   {result.scoreline}   [{result.fidelity}]")
    lines.append("")

    if result.fidelity == "fast":
        lines.append("(fast model — scoreline only, no per-point stats)")
        return "\n".join(lines)

    s0, s1 = result.stats
    rows = [
        ("Aces", s0.aces, s1.aces),
        ("Double faults", s0.double_faults, s1.double_faults),
        ("1st serve in", _pct(s0.first_serve_pct), _pct(s1.first_serve_pct)),
        ("Serve pts won", _pct(s0.serve_points_won_pct), _pct(s1.serve_points_won_pct)),
        ("BP saved/faced", f"{s0.break_points_saved}/{s0.break_points_faced}",
         f"{s1.break_points_saved}/{s1.break_points_faced}"),
        ("Breaks", s0.break_points_converted, s1.break_points_converted),
        ("Winners", s0.winners, s1.winners),
        ("Forced errors", s0.forced_errors, s1.forced_errors),
        ("Unforced errors", s0.unforced_errors, s1.unforced_errors),
        ("Total points", s0.points_won, s1.points_won),
    ]
    w = max(len(r[0]) for r in rows)
    lines.append(f"{'':<{w}}  {p[0].name[:16]:>16}  {p[1].name[:16]:>16}")
    for label, a, b in rows:
        lines.append(f"{label:<{w}}  {str(a):>16}  {str(b):>16}")
    return "\n".join(lines)


def pbp_text(result: MatchResult) -> str:
    return "\n".join(result.pbp)

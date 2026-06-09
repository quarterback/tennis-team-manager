"""
Juniors almanac — the COMPUTE layer.

Read-only derived math over a recruiting class, in the loader → compute → render →
export split the O27 almanac / viperball stats terminal use. Pure: no engine
coupling, no I/O, no template knowledge. It turns a recruit's frozen junior résumé
into stat lines, sortable columns, leaderboards and honor badges, so the same math
drives the live reference pages and the JSON export.
"""
from __future__ import annotations

# Minimum sample before a rate stat (win %) qualifies for a leaderboard.
MIN_MATCHES_FOR_RATE = 8
MIN_DOUBLES_EVENTS = 4


def stat_line(p) -> dict:
    """A recruit's junior W-L, titles, finals and win % from their frozen match/result
    logs (singles + doubles). Counts only; no ratings."""
    sm = getattr(p, "junior_matches", None) or []
    w = sum(1 for m in sm if m["won"])
    res = getattr(p, "junior_results", None) or []
    dm = getattr(p, "junior_doubles_matches", None) or []
    dw = sum(1 for m in dm if m["won"])
    n = len(sm)
    return {
        "w": w, "l": n - w, "n": n, "pct": (w / n) if n else 0.0,
        "titles": sum(1 for r in res if r["result"] == "Champion"),
        "finals": sum(1 for r in res if r["result"] in ("Champion", "Finalist")),
        "dw": dw, "dl": len(dm) - dw, "dn": len(dm),
    }


# Sortable columns for the rankings table: key -> (label, value reader). Higher value
# sorts "better first"; rank-style columns negate so #1 leads.
SORT_COLUMNS = {
    "rank":   ("#",      lambda p, s: -getattr(p, "points_rank", 10 ** 9)),
    "board":  ("Brd",    lambda p, s: -getattr(p, "recruit_rank", 10 ** 9)),
    "pts":    ("Pts",    lambda p, s: p.junior_points),
    "spts":   ("Sgl",    lambda p, s: p.singles_points),
    "dpts":   ("Dbl",    lambda p, s: p.doubles_points),
    "str":    ("STR",    lambda p, s: p.junior_str or 0.0),
    "dstr":   ("dSTR",   lambda p, s: p.junior_doubles_str or 0.0),
    "titles": ("Ti",     lambda p, s: s["titles"]),
    "finals": ("Fin",    lambda p, s: s["finals"]),
    "won":    ("W",      lambda p, s: s["w"]),
    "pct":    ("Win%",   lambda p, s: s["pct"]),
    "events": ("Ev",     lambda p, s: p.tournaments_played),
    "stars":  ("Stars",  lambda p, s: getattr(p, "recruit_stars", 0)),
}


def sort_recruits(recruits: list, stats: dict, sort: str, desc: bool = True) -> list:
    """Stable sort by a SORT_COLUMNS key (ties keep incoming points order)."""
    col = SORT_COLUMNS.get(sort) or SORT_COLUMNS["rank"]
    return sorted(recruits, key=lambda p: col[1](p, stats[p.pid]), reverse=desc)


def leaders(recruits: list, stats: dict, n: int = 5) -> list[tuple[str, list]]:
    """League-leader mini-boards: [(label, [(prospect, value_str)...])], rate stats
    gated by a min sample so leaders are legitimate."""
    def board(read, fmt, gate=lambda p, s: True):
        pool = [p for p in recruits if gate(p, stats[p.pid])]
        top = sorted(pool, key=lambda p: read(p, stats[p.pid]), reverse=True)[:n]
        return [(p, fmt(read(p, stats[p.pid]))) for p in top]
    return [
        ("Most Points", board(lambda p, s: p.junior_points, lambda v: f"{int(v):,}")),
        ("Most Titles", board(lambda p, s: s["titles"], lambda v: str(int(v)))),
        ("Highest STR", board(lambda p, s: p.junior_str or 0, lambda v: f"{v:.1f}")),
        ("Best Win%", board(lambda p, s: s["pct"], lambda v: f"{v*100:.0f}%",
                            gate=lambda p, s: s["n"] >= MIN_MATCHES_FOR_RATE)),
        ("Best Doubles STR", board(lambda p, s: p.junior_doubles_str or 0, lambda v: f"{v:.1f}",
                            gate=lambda p, s: bool(p.junior_doubles_str) and s["dn"] >= MIN_DOUBLES_EVENTS)),
    ]


# Honor badges: rank a recruit's marquee milestone for a colored medal chip. The
# badge list is highest-first (set by the circuit), so badges[0] is the top honor.
_HONOR_TIER = [("No. 1", "gold"), ("Top 5", "silver"), ("Top 10", "silver"),
               ("Top 25", "bronze"), ("Top 50", "bronze")]
_SHORTEN = [("National", "Nat"), ("Global", "Wld"), ("World", "Wld"), (" Junior", "")]


def _short_badge(label: str) -> str:
    for a, b in _SHORTEN:
        label = label.replace(a, b)
    return label.strip()


def honor_chip(p) -> dict | None:
    """The marquee honor for a recruit: {label, tier (gold/silver/bronze/muted),
    more (extra-badge count), all (full list)} — or None if unranked."""
    badges = getattr(p, "junior_badges", None) or []
    if not badges:
        return None
    top = badges[0]
    tier = next((c for kw, c in _HONOR_TIER if kw in top), "muted")
    return {"label": _short_badge(top), "tier": tier,
            "more": len(badges) - 1, "all": badges}

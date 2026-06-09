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


# Honor badges as shields.io-style two-segment chips: a scope label (left) + the
# accomplishment (right), the right coloured BY accomplishment — a distinct shade
# per level all the way down (No. 1 → Top 300) plus tournament wins (Grand Slam /
# Masters / Major champion). First keyword match wins, so list most prestigious
# first. The colour key maps to an `.al-r-<key>` class in almanac.css.
_BADGE_TIER = [
    ("Grand Slam Champion", "gschamp"), ("Grand Slam Finalist", "gsfinal"),
    ("Masters Champion", "masters"), ("Major Champion", "major"),
    ("No. 1", "r1"), ("Top 5", "r5"), ("Top 10", "r10"), ("Top 25", "r25"),
    ("Top 50", "r50"), ("Top 100", "r100"), ("Top 250", "r250"), ("Top 300", "r300"),
]
_SCOPE_SHORT = {"National": "NAT", "Global": "GLOBAL", "World": "WORLD",
                "Nation": "NATION", "State": "STATE"}
# Tournament-tier labels that head an accomplishment badge ("Grand Slam Champion").
_ACCOMP_LEVELS = ["Grand Slam", "Masters", "Major"]


def badge_shield(label: str) -> dict:
    """A badge string → shields.io-style {left, right, tier}. Handles tournament
    accomplishments ('Grand Slam Champion ×2' → GRAND SLAM | Champion ×2) and ranking
    milestones ('Global Top 10 Junior' → GLOBAL | Top 10), coloured by accomplishment."""
    lvl = next((L for L in _ACCOMP_LEVELS if label.startswith(L)), None)
    if lvl:
        left, right = lvl.upper(), label[len(lvl):].strip() or "Champion"
    else:
        words = label.replace(" Junior", "").split()
        left = _SCOPE_SHORT.get(words[0], words[0].upper()) if words else label
        right = " ".join(words[1:]) or (words[0] if words else label)
    return {"left": left, "right": right,
            "tier": next((c for kw, c in _BADGE_TIER if kw in label), "r300")}


def profile_badges(p) -> list[dict]:
    """All of a recruit's badges as shields — tournament accomplishments (from the
    result log) first, then the ranking milestones."""
    res = getattr(p, "junior_results", None) or []
    def titles(level, result):
        return sum(1 for r in res if r["level"] == level and r["result"] == result)
    acc: list[str] = []
    gs_t, gs_f = titles("Grand Slam", "Champion"), titles("Grand Slam", "Finalist")
    ms_t, mj_t = titles("Masters", "Champion"), titles("Major", "Champion")
    if gs_t:
        acc.append("Grand Slam Champion" + (f" ×{gs_t}" if gs_t > 1 else ""))
    elif gs_f:
        acc.append("Grand Slam Finalist")
    if ms_t:
        acc.append("Masters Champion" + (f" ×{ms_t}" if ms_t > 1 else ""))
    if mj_t:
        acc.append("Major Champion" + (f" ×{mj_t}" if mj_t > 1 else ""))
    return [badge_shield(b) for b in acc + (getattr(p, "junior_badges", None) or [])]


def honor_chip(p) -> dict | None:
    """The recruit's marquee badge as a shield plus `more` (extra count) and `all`
    (tooltip list) — accomplishments outrank ranking milestones. None if unranked."""
    badges = profile_badges(p)
    if not badges:
        return None
    return {**badges[0], "more": len(badges) - 1,
            "all": [f"{b['left']} {b['right']}" for b in badges]}

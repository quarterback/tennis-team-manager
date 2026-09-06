"""Match Center — shared, read-only display helpers for a dual's Statistics tab.

Renders the flashscore/sofascore-style grouped stat-comparison bars (Service /
Return / Points) that `_matchcenter.html`'s `mc_stat_bars` macro draws, shared
by the college (`season_dual.html`), pro/GTT (`gtt_dual.html`) and JHSAA
(`jhsaa_dual.html`) dual-detail pages.

‼️ EVERY ROW HERE MAPS 1:1 ONTO A FIELD THE ENGINE ALREADY TRACKS
(`engine.state.PlayerStats`/`STAT_KEYS`) — nothing is estimated or invented.
Two real gaps exist and are handled by DROPPING the row rather than faking a
number: GTT's `_stat_summary` never records a first-serve attempt count (only
`fs_in`), so "1st Serve %" has no denominator there; JHSAA never records box
stats at all (`FIDELITY` is always "fast" for that division — see CLAUDE.md),
so `sum_gtt_lines`/`sum_college_lines`-equivalent simply isn't called for it
and `stat_groups(None, None)` returns None. This is a pure aggregation layer:
no engine, cache, or persistence changes. See docs/AAR-match-center.md.
"""
from __future__ import annotations

from engine.state import STAT_KEYS

# Full PlayerStats field name -> college's persisted short code (season._line_stats).
_COLLEGE_KEY = {full: short for short, full in STAT_KEYS}

# Full PlayerStats field name -> GTT's persisted readable code (gtt_seasonmode._stat_summary).
_GTT_KEY = {
    "aces": "aces", "double_faults": "df",
    "serve_points_won": "sp_won", "serve_points_total": "sp_total",
    "return_points_won": "rp_won", "return_points_total": "rp_total",
    "break_points_saved": "bp_saved", "break_points_faced": "bp_faced",
    "break_points_converted": "bp_conv",
    "winners": "winners", "forced_errors": "fe", "unforced_errors": "ue",
    "points_won": "points",
}


def _add_into(totals: dict, src: dict, key_map: dict) -> None:
    for full, short in key_map.items():
        totals[full] = totals.get(full, 0) + int(src.get(short, 0) or 0)


def sum_college_lines(lines: list[dict]) -> tuple[dict, dict] | None:
    """Dual-wide Service/Return/Points totals from `season._line_stats`'s
    per-line `stats` blob. Singles carries one dict per side; doubles carries
    a list of the two partners' dicts (pooled here exactly as the existing
    per-line stat strip in `season_dual.html` already pools them)."""
    home: dict = {}
    away: dict = {}
    seen = False
    for ln in lines:
        st = ln.get("stats")
        if not st:
            continue
        for side, totals in (("home", home), ("away", away)):
            entries = st.get(side)
            if not entries:
                continue
            for e in (entries if isinstance(entries, list) else [entries]):
                _add_into(totals, e, _COLLEGE_KEY)
                seen = True
    return (home, away) if seen else None


def sum_gtt_lines(lines: list[dict]) -> tuple[dict, dict] | None:
    """Dual-wide totals from `gtt_seasonmode._stat_summary`'s per-line dicts
    (already pooled across doubles/mixed partners for that one line)."""
    home: dict = {}
    away: dict = {}
    seen = False
    for ln in lines:
        hs, aw = ln.get("home_stats"), ln.get("away_stats")
        if not hs or not aw:
            continue
        _add_into(home, hs, _GTT_KEY)
        _add_into(away, aw, _GTT_KEY)
        seen = True
    return (home, away) if seen else None


def _pct(made: int, total: int) -> int | None:
    return round(100 * made / total) if total else None


def _fmt_pct(made: int, total: int) -> str:
    p = _pct(made, total)
    return f"{p}% ({made}/{total})" if p is not None else "—"


def _share(a: float, b: float) -> tuple[float, float]:
    """Bar-fill percentages (0-100, home first) for two comparable magnitudes —
    the flashscore/sofascore "two half-bars meeting in the middle" pattern.
    A real zero still gets a visible floor rather than vanishing entirely."""
    total = a + b
    if total <= 0:
        return 50.0, 50.0
    h = min(max(100 * a / total, 6.0), 94.0)
    return round(h, 1), round(100 - h, 1)


def _row(label: str, home_disp, away_disp, home_w: float, away_w: float) -> dict:
    hs, aw = _share(home_w, away_w)
    return {"label": label, "home_disp": home_disp, "away_disp": away_disp,
            "home_share": hs, "away_share": aw}


def _drop_empty(rows: list[dict]) -> list[dict]:
    """A row both sides show as "—" carries no information — this is what
    keeps GTT's missing 1st-serve-attempt denominator from printing a
    permanently blank row rather than simply not appearing."""
    return [r for r in rows if not (r["home_disp"] in ("—", 0) and r["away_disp"] in ("—", 0))]


def stat_groups(totals: tuple[dict, dict] | None) -> list[dict] | None:
    """Build the Service / Return / Points comparison groups for the
    Statistics tab from `sum_college_lines`/`sum_gtt_lines`'s output. Returns
    None when there is nothing to show at all (no box stats recorded for this
    dual — e.g. every JHSAA dual, or a fast-fidelity college/GTT game)."""
    if not totals:
        return None
    home, away = totals
    if not home and not away:
        return None

    def g(d, k):
        return d.get(k, 0)

    hfsi, hfsp = g(home, "first_serves_in"), g(home, "first_serve_points")
    afsi, afsp = g(away, "first_serves_in"), g(away, "first_serve_points")
    hsvw, hsvt = g(home, "serve_points_won"), g(home, "serve_points_total")
    asvw, asvt = g(away, "serve_points_won"), g(away, "serve_points_total")
    hrtw, hrtt = g(home, "return_points_won"), g(home, "return_points_total")
    artw, artt = g(away, "return_points_won"), g(away, "return_points_total")
    hbps, hbpf = g(home, "break_points_saved"), g(home, "break_points_faced")
    abps, abpf = g(away, "break_points_saved"), g(away, "break_points_faced")
    # Break points CONVERTED, as a returner — the denominator is the OTHER
    # side's break_points_faced (the chances they had serving).
    hbpc, abpc = g(home, "break_points_converted"), g(away, "break_points_converted")

    service = _drop_empty([
        _row("Aces", g(home, "aces"), g(away, "aces"), g(home, "aces"), g(away, "aces")),
        _row("Double Faults", g(home, "double_faults"), g(away, "double_faults"),
             g(home, "double_faults"), g(away, "double_faults")),
        _row("1st Serve", _fmt_pct(hfsi, hfsp), _fmt_pct(afsi, afsp),
             _pct(hfsi, hfsp) or 0, _pct(afsi, afsp) or 0),
        _row("Service Points Won", _fmt_pct(hsvw, hsvt), _fmt_pct(asvw, asvt),
             _pct(hsvw, hsvt) or 0, _pct(asvw, asvt) or 0),
        _row("Break Points Saved", _fmt_pct(hbps, hbpf), _fmt_pct(abps, abpf),
             _pct(hbps, hbpf) or 0, _pct(abps, abpf) or 0),
    ])
    ret = _drop_empty([
        _row("Return Points Won", _fmt_pct(hrtw, hrtt), _fmt_pct(artw, artt),
             _pct(hrtw, hrtt) or 0, _pct(artw, artt) or 0),
        _row("Break Points Converted", _fmt_pct(hbpc, abpf), _fmt_pct(abpc, hbpf),
             _pct(hbpc, abpf) or 0, _pct(abpc, hbpf) or 0),
    ])
    pts = _drop_empty([
        _row("Winners", g(home, "winners"), g(away, "winners"),
             g(home, "winners"), g(away, "winners")),
        _row("Unforced Errors", g(home, "unforced_errors"), g(away, "unforced_errors"),
             g(home, "unforced_errors"), g(away, "unforced_errors")),
        _row("Service Points Won", hsvw, asvw, hsvw, asvw),
        _row("Return Points Won", hrtw, artw, hrtw, artw),
        _row("Total Points Won", g(home, "points_won"), g(away, "points_won"),
             g(home, "points_won"), g(away, "points_won")),
    ])
    groups = [{"title": t, "rows": r} for t, r in
              (("Service", service), ("Return", ret), ("Points", pts)) if r]
    return groups or None


# ---------------------------------------------------------------------------
# Head-to-head — a career SERIES record, not a "recent form" snapshot
# ---------------------------------------------------------------------------
# The Matches tab was originally a 5-row recency list, styled after flashscore/
# sofascore's H2H widget. That's the wrong model here: those sites cap it
# because the players it's showing rarely have a long history together. Two
# programs in the same league play every year for decades — the real-world
# pattern (rivalry pages, Winsipedia-style team-compare pages) leads with the
# CAREER series record (who leads, by how much, since when), then a full
# game-by-game list underneath, never a silently-truncated "top 5". See
# docs/AAR-match-center.md for the full writeup.

def summarize_series(meetings: list[dict], team_a: str, team_b: str) -> dict | None:
    """A full head-to-head record built from EVERY known meeting between two
    programs, not a capped list — `meetings` should be every row the
    caller's `prior_meetings`-style query can find, most-recent-first, each
    `{label, home, away, home_points, away_points, postseason}`. `team_a`/
    `team_b` are the two programs' current display names; a meeting's
    winner is tallied against whichever of the two it matches (a meeting's
    own `home`/`away` only says who hosted THAT game, which alternates)."""
    if not meetings:
        return None

    def winner_of(m: dict) -> str | None:
        # A row that states its outcome wins over the points: a level dual can be
        # a draw (JV) OR decided on tiebreakers (Group 2's road), and only the
        # archived result says which.
        if "winner" in m:
            return None if m.get("tied") else m["winner"]
        if m["home_points"] == m["away_points"]:
            return None
        return m["home"] if m["home_points"] > m["away_points"] else m["away"]

    wins = {team_a: 0, team_b: 0}
    ties = 0
    ps_wins = {team_a: 0, team_b: 0}
    ps_total = 0
    largest_margin = {team_a: None, team_b: None}
    longest_streak = {team_a: 0, team_b: 0}
    run_team, run_n = None, 0

    # Oldest-first pass, so a "streak" is built chronologically — both the
    # longest ever (kept running per side) and, once the loop ends, the
    # CURRENT streak (whatever run is still open at the most recent game).
    for m in reversed(meetings):
        w = winner_of(m)
        if w is None:
            ties += 1
            run_team, run_n = None, 0
            continue
        if w in wins:
            wins[w] += 1
        margin = abs(m["home_points"] - m["away_points"])
        best = largest_margin.get(w)
        if w in largest_margin and (best is None or margin > best["margin"]):
            largest_margin[w] = {"margin": margin, "label": m["label"]}
        if m.get("postseason"):
            ps_total += 1
            if w in ps_wins:
                ps_wins[w] += 1
        run_team, run_n = (w, run_n + 1) if w == run_team else (w, 1)
        if w in longest_streak:
            longest_streak[w] = max(longest_streak[w], run_n)

    a_w, b_w = wins[team_a], wins[team_b]
    if a_w > b_w:
        leader, trailer = team_a, team_b
    elif b_w > a_w:
        leader, trailer = team_b, team_a
    else:
        leader = trailer = None
    # ‼️ LEADER-FIRST, NOT team_a-FIRST. "record_str" is only ever printed
    # right after the leader's own name ("{{ leader }} leads the series
    # {{ record_str }}"), so it must read as THAT team's wins first — when
    # team_b actually led, `f"{a_w}-{b_w}"` put team_a's (lower) count
    # first, so "Away leads the series 2-8" read as the leader having two
    # wins. A tie has no leader to orient around, so team_a/team_b order is
    # fine there (the two numbers are equal anyway).
    record_str = (f"{wins[leader]}-{wins[trailer]}" if leader else f"{a_w}-{b_w}") + (
        f"-{ties}" if ties else "")

    last10 = meetings[:10]
    last10_wins = {team_a: 0, team_b: 0}
    for m in last10:
        w = winner_of(m)
        if w in last10_wins:
            last10_wins[w] += 1

    last = meetings[0]
    return {
        "total": len(meetings), "wins": wins, "ties": ties, "record_str": record_str,
        "leader": leader,
        "first_label": meetings[-1]["label"], "last_label": last["label"],
        "streak_team": run_team, "streak_n": run_n,
        "last_meeting": {"winner": winner_of(last), "home": last["home"], "away": last["away"],
                         "home_points": last["home_points"], "away_points": last["away_points"],
                         "label": last["label"]},
        "last10_wins": last10_wins, "last10_n": len(last10),
        "postseason_total": ps_total,
        "postseason_wins": ps_wins if ps_total else None,
        "largest_margin": largest_margin,
        "longest_streak": longest_streak,
    }

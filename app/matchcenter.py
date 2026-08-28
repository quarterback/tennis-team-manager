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

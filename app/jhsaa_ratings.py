"""JHSAA computer ratings — nine independent systems and a composite (owner spec
2026-09), the Massey-ratings-page idea brought inside the association.

Structure ported from viperball's `engine/ranking_composite.py` (the owner's other
sim already runs a composite ratings layer — Colley, Massey, SRS, Elo, BT, SOR —
so the shapes here are that module's, adapted to tennis), with three deliberate
departures:

  * **Exact solves, no rng.** The least-squares family (Colley, both Masseys, the
    schedule-adjusted set share) is solved by Gaussian elimination rather than
    Gauss-Seidel sweeps, and SOR is an exact Poisson-binomial DP rather than a
    simulation — same inputs, same numbers, every run, which is the determinism
    rule this repo holds everywhere outside injuries.
  * **Bradley-Terry is pure win/loss** (the spec's rule): it sits in the
    record-based family beside Colley and Win%, so viperball's margin-of-victory
    weighting is NOT ported.
  * **Margins are tennis margins** — a dual margin is flights (bounded at 9), a
    set at 6-0 — so no truncation constant is needed; the bound is the format's.

THE SYSTEMS ARE PARALLEL TO TOSS AND ATR, NEVER A REPLACEMENT. TOSS still rates,
ATR still seeds the road, and nothing here feeds either. These exist for the
ratings page (all twelve groups, both genders) and the at-large committee
(`jhsaa_committee`, 7A and Group 1 only).

Scope rules (spec Part 0/1.1):
  * Per (championship group, gender), never statewide — Massey/SRS need a
    connected schedule and cross-group play is too sparse. Only duals with BOTH
    sides inside the group enter the fit; a disconnected in-group graph is
    REPORTED (`disconnected`) and the least-squares family withheld rather than
    silently fit per component.
  * Varsity only — structural here: the input is `TeamSeason.schedule` and JV
    lives on `JVTeam`.
  * Keys are the ARCHIVE identity (the display name), the same key every other
    per-season table in this module family uses. The one-name-per-program rule
    (`test_display_names_are_unique_identities`) is what makes that safe.
  * Retirement/default guard (spec 1.2): a line carrying a single set is a
    retirement or default and is EXCLUDED from set/game-share input.
"""
from __future__ import annotations

import hashlib
import math
import statistics

#: The nine systems, in the page's column order. Keys are stable archive keys.
SYSTEMS = ("colley", "bt", "win_pct", "massey_dual", "srs",
           "massey_game", "set_share", "sor", "elo")

#: Elo constants — viperball's, minus home-field (JHSAA hosting alternates and
#: the neutral phases carry none; a constant HFA would be a guess).
ELO_BASE = 1500.0
ELO_K = 30.0

#: ‼️ SOR'S BENCHMARK IS DEFINED, PUBLISHED AND FROZEN PER RUN (owner rule
#: 2026-09): the MEDIAN Bradley-Terry rating of the teams ranked 9-16 in the
#: current BT field — "a normal bye-caliber team". "Average top-16 team" with no
#: mathematical identity is recursive; this one is a number the page can print
#: (`sor_bench` on the layer's output).
SOR_BENCH_RANKS = (9, 16)


# --- ingestion ---------------------------------------------------------------

def _phase_rank(phase: str) -> int:
    """Where a phase sits in the season's actual play sequence: the early
    non-district window first, the whole regular block (league passes, invites,
    showcases, challenges) next, then the road's rounds in `POSTSEASON` order.
    Phases are played WHOLE-GENDER in sequence (`play_regular_season` /
    `run_season`), so ordering phase-major first is what makes a per-team
    schedule index usable as the within-phase clock — without it, a road dual
    hosted by a short-schedule team sorted BEFORE another team's late league
    dual and Elo updated out of play order."""
    from .jhsaa import EARLY_FORMAT_PHASE, POSTSEASON
    if phase == EARLY_FORMAT_PHASE:
        return 0
    if phase in POSTSEASON:
        return 2 + POSTSEASON.index(phase)
    return 1                      # league passes, invitationals, showcases


def dual_rows(teams: list) -> list[dict]:
    """The group's duals as flat rows, deduped and in a deterministic play-order
    proxy. One row per dual (the HOME side's schedule row — `play_dual` writes
    exactly one per dual), both sides inside the group, varsity by construction,
    State/TOC excluded (the prestate posture: these ratings are the input a
    selection is made from, and State has not been played when they are taken).

    Order: a JHSAA season has no clock — the global sequence Elo walks is
    (phase rank, home-side schedule index, home, away). The PHASE carries the
    real calendar (each phase is played whole-gender before the next begins);
    the schedule index is the within-phase clock, monotone per team; the name
    tiebreak makes the walk reproducible. Rows also carry `phase` — the set and
    game currencies need it (`dual_shares`' pro-set rule)."""
    names = {t.school.name for t in teams}
    rows = []
    for t in teams:
        for idx, d in enumerate(t.schedule):
            if not d.get("home"):
                continue
            phase = d.get("phase") or "regular"
            if phase in ("state", "toc"):
                continue
            if d["opp"] not in names:
                continue
            rows.append({"home": t.school.name, "away": d["opp"],
                         "hp": d["pf"], "ap": d["pa"], "phase": phase,
                         "order": (_phase_rank(phase), idx,
                                   t.school.name, d["opp"]),
                         "lines": d.get("lines") or []})
    rows.sort(key=lambda r: r["order"])
    return rows


def _parse_sets(score: str) -> list[tuple[int, int]]:
    """`lines.score` is a comma-separated home-first set list ("6-1, 6-2") —
    the same convention `jhsaa._games` reads. Unparseable chunks are skipped."""
    out = []
    for chunk in (score or "").split(","):
        chunk = chunk.strip()
        if "-" not in chunk:
            continue
        a, _, b = chunk.partition("-")
        try:
            out.append((int(a), int(b)))
        except ValueError:
            continue
    return out


def dual_shares(row: dict) -> tuple[int, int, int, int] | None:
    """(home_sets, away_sets, home_games, away_games) for one dual, or None when
    no line yields usable set data.

    ‼️ THE RETIREMENT GUARD (spec 1.2): a line with a SINGLE parsed set is a
    retirement or default (~3.1k a gender-season) and is dropped — left raw it
    hands the healthy side a full-line game ratio it never played for.

    ‼️ EXCEPT AT A POD SHOWCASE. `showcase_pod` deliberately scores every court
    as ONE 8-game pro set (`PRESETS["pro_set_8"]` — three pro sets is the USTA
    junior daily limit), so a single-set line there is the COMPLETE match, not
    a retirement. Read the guard off the row's `phase`: a pod line counts as
    one set and its real games; everywhere else the two-set floor holds."""
    min_sets = 1 if row.get("phase") == "showcase_pod" else 2
    hs = as_ = hg = ag = 0
    any_line = False
    for ln in row["lines"]:
        sets = _parse_sets(ln.get("score", ""))
        if len(sets) < min_sets:
            continue
        any_line = True
        for h, a in sets:
            hg += h
            ag += a
            if h > a:
                hs += 1
            elif a > h:
                as_ += 1
    if not any_line:
        return None
    return hs, as_, hg, ag


def connected(rows: list[dict], teams: list) -> bool:
    """Is the in-group schedule graph one component? (spec 1.1 — a disconnected
    group is REPORTED, never silently fit.)"""
    names = sorted(t.school.name for t in teams)
    if not names:
        return True
    adj: dict[str, set] = {n: set() for n in names}
    for r in rows:
        adj[r["home"]].add(r["away"])
        adj[r["away"]].add(r["home"])
    seen, stack = {names[0]}, [names[0]]
    while stack:
        for nb in adj[stack.pop()]:
            if nb not in seen:
                seen.add(nb)
                stack.append(nb)
    return len(seen) == len(names)


# --- linear algebra ----------------------------------------------------------

def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Dense Gaussian elimination with partial pivoting. n here is a group
    (~60-120 teams), so an exact O(n^3) solve is both faster and better-behaved
    than iterating sweeps to a tolerance."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            continue
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / m[i][i] if abs(m[i][i]) > 1e-12 else 0.0
    return x


def _index(rows: list[dict]) -> tuple[list[str], dict]:
    names = sorted({r["home"] for r in rows} | {r["away"] for r in rows})
    return names, {n: i for i, n in enumerate(names)}


# --- the record-based family -------------------------------------------------

def _colley_frac(rows: list[dict], frac) -> dict[str, float]:
    """The Colley matrix generalised to FRACTIONAL wins: `frac(row)` returns the
    home side's win share of that dual (1/0 for plain Colley, the set share for
    system 7). Standard matrix: C[i][i] = 2 + games, C[i][j] = -games between,
    b[i] = 1 + (w - l)/2."""
    names, idx = _index(rows)
    n = len(names)
    if not n:
        return {}
    c = [[0.0] * n for _ in range(n)]
    wins = [0.0] * n
    games = [0] * n
    for r in rows:
        hi, ai = idx[r["home"]], idx[r["away"]]
        f = frac(r)
        if f is None:
            continue
        wins[hi] += f
        wins[ai] += 1.0 - f
        games[hi] += 1
        games[ai] += 1
        c[hi][ai] -= 1
        c[ai][hi] -= 1
    for i in range(n):
        c[i][i] = 2.0 + games[i]
    b = [1.0 + (wins[i] - (games[i] - wins[i])) / 2.0 for i in range(n)]
    r = _solve(c, b)
    return {names[i]: r[i] for i in range(n)}


def colley(rows: list[dict]) -> dict[str, float]:
    """System 1 — Colley: wins and losses with schedule adjustment."""
    return _colley_frac(rows, lambda r: 1.0 if r["hp"] > r["ap"] else 0.0)


def bradley_terry(rows: list[dict]) -> dict[str, float]:
    """System 2 — Bradley-Terry, maximum likelihood on dual WIN/LOSS (the spec's
    rule — margin deliberately not imported from the viperball version). One
    fictitious split dual against a virtual average team regularises the
    undefeated/winless boundary, the standard MM fix."""
    names, idx = _index(rows)
    n = len(names)
    if not n:
        return {}
    wins = [0.5] * n                       # the virtual half-win
    matchups: list[list[int]] = [[] for _ in range(n)]
    for r in rows:
        hi, ai = idx[r["home"]], idx[r["away"]]
        wins[hi if r["hp"] > r["ap"] else ai] += 1.0
        matchups[hi].append(ai)
        matchups[ai].append(hi)
    rating = [1.0] * n
    for _ in range(200):
        new = [0.0] * n
        for i in range(n):
            denom = 1.0 / (rating[i] + 1.0)          # the virtual opponent at 1.0
            for j in matchups[i]:
                denom += 1.0 / (rating[i] + rating[j])
            new[i] = wins[i] / denom if denom > 0 else rating[i]
        mean = sum(new) / n
        if mean > 0:
            new = [x / mean for x in new]
        delta = max(abs(new[i] - rating[i]) for i in range(n))
        rating = new
        if delta < 1e-10:
            break
    return {names[i]: rating[i] for i in range(n)}


def win_pct(rows: list[dict]) -> dict[str, float]:
    """System 3 — raw win percentage, unadjusted. The deliberately naive view."""
    w: dict[str, float] = {}
    g: dict[str, int] = {}
    for r in rows:
        for name, won in ((r["home"], r["hp"] > r["ap"]),
                          (r["away"], r["ap"] > r["hp"])):
            w[name] = w.get(name, 0.0) + (1.0 if won else 0.0)
            g[name] = g.get(name, 0) + 1
    return {n: w[n] / g[n] for n in w}


# --- the margin family -------------------------------------------------------

def _massey(rows: list[dict], margin) -> dict[str, float]:
    """Massey least squares: for each dual r_home - r_away ~ margin(row).
    Normal equations with the standard sum-to-zero constraint replacing the last
    row (the system is otherwise singular — ratings are relative)."""
    names, idx = _index(rows)
    n = len(names)
    if not n:
        return {}
    ata = [[0.0] * n for _ in range(n)]
    atb = [0.0] * n
    for r in rows:
        m = margin(r)
        if m is None:
            continue
        hi, ai = idx[r["home"]], idx[r["away"]]
        ata[hi][hi] += 1
        ata[ai][ai] += 1
        ata[hi][ai] -= 1
        ata[ai][hi] -= 1
        atb[hi] += m
        atb[ai] -= m
    for j in range(n):
        ata[n - 1][j] = 1.0
    atb[n - 1] = 0.0
    r = _solve(ata, atb)
    return {names[i]: r[i] for i in range(n)}


def _flight_margin(r: dict) -> float:
    """‼️ NORMALISED flight margin (owner rule 2026-09): a season mixes 5-, 7-
    and 9-flight duals, so raw margins are not one currency — +4 of five is not
    +4 of nine. `(flights won - lost) / flights played` puts a 5-0, 7-0 and 9-0
    on the same +1.0 scale, so format length never becomes a rating input."""
    played = r["hp"] + r["ap"]
    return (r["hp"] - r["ap"]) / played if played else 0.0


def massey_dual(rows: list[dict]) -> dict[str, float]:
    """System 4 — Massey on the NORMALISED flight margin per dual."""
    return _massey(rows, _flight_margin)


def srs(rows: list[dict]) -> dict[str, float]:
    """System 5 — SRS: average flight margin plus average opponent rating,
    iterated to convergence and centred at zero."""
    names, idx = _index(rows)
    n = len(names)
    if not n:
        return {}
    msum = [0.0] * n
    count = [0] * n
    opps: list[list[int]] = [[] for _ in range(n)]
    for r in rows:
        hi, ai = idx[r["home"]], idx[r["away"]]
        m = _flight_margin(r)                 # normalised — see `_flight_margin`
        msum[hi] += m
        msum[ai] -= m
        count[hi] += 1
        count[ai] += 1
        opps[hi].append(ai)
        opps[ai].append(hi)
    avg = [msum[i] / count[i] if count[i] else 0.0 for i in range(n)]
    val = [0.0] * n
    for _ in range(400):
        # DAMPED update (half old, half new): the plain iteration oscillates on
        # small or bipartite-ish schedule graphs (two teams flip between
        # (m, -m) and (0, 0) forever); damping converges to the same fixed
        # point everywhere the plain form converges, and actually gets there.
        new = [avg[i] + (sum(val[j] for j in opps[i]) / len(opps[i])
                         if opps[i] else 0.0) for i in range(n)]
        mean = sum(new) / n
        new = [0.5 * val[i] + 0.5 * (new[i] - mean) for i in range(n)]
        delta = max(abs(new[i] - val[i]) for i in range(n))
        val = new
        if delta < 1e-10:
            break
    return {names[i]: val[i] for i in range(n)}


def massey_game(rows: list[dict]) -> dict[str, float]:
    """System 6 — Massey where the per-dual observation is the NORMALISED game
    margin, `(games won - lost) / games played` at the dual level (the
    ~1.1M-game currency; raw games would hand long three-set duals more
    statistical mass just for lasting longer). Duals with no parseable lines
    contribute nothing to this fit; the retirement guard in `dual_shares`
    applies."""
    def margin(r):
        sh = dual_shares(r)
        if sh is None or (sh[2] + sh[3]) == 0:
            return None
        return (sh[2] - sh[3]) / (sh[2] + sh[3])
    return _massey(rows, margin)


def set_share(rows: list[dict]) -> dict[str, float]:
    """System 7 — sets won / sets played, schedule-adjusted exactly the way
    Colley adjusts win% (the fractional-win Colley above)."""
    def frac(r):
        sh = dual_shares(r)
        if sh is None or (sh[0] + sh[1]) == 0:
            return None
        return sh[0] / (sh[0] + sh[1])
    return _colley_frac(rows, frac)


# --- résumé and form ---------------------------------------------------------

def _elo_expected(a: float, b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-(a - b) / 400.0))


def elo(rows: list[dict]) -> dict[str, float]:
    """System 9 — sequential Elo in play order, the one system that weights
    late-season form. K carries viperball's margin-of-victory dampener
    (ln(1+|mov|) x 2.2/(2.2 + 0.001|diff|)), mov in flights."""
    val: dict[str, float] = {}
    for r in rows:                                   # rows already ordered
        h, a = r["home"], r["away"]
        eh = val.setdefault(h, ELO_BASE)
        ea = val.setdefault(a, ELO_BASE)
        exp_h = _elo_expected(eh, ea)
        actual = 1.0 if r["hp"] > r["ap"] else 0.0
        mov = abs(r["hp"] - r["ap"])
        k = ELO_K * math.log(1.0 + mov) * (2.2 / (2.2 + 0.001 * abs(eh - ea)))
        delta = k * (actual - exp_h)
        val[h] = eh + delta
        val[a] = ea - delta
    return val


def sor_benchmark(bt: dict[str, float]) -> float:
    """The published SOR benchmark: the median Bradley-Terry rating of the
    teams ranked 9-16 in the current BT field ("a normal bye-caliber team").
    A field shorter than sixteen falls back to the median of what exists."""
    if not bt:
        return 1.0
    vals = sorted(bt.values(), reverse=True)
    lo, hi = SOR_BENCH_RANKS
    band = vals[lo - 1:hi] or vals
    return statistics.median(band)


def sor(rows: list[dict], bt: dict[str, float]) -> dict[str, float]:
    """System 8 — strength of record: the probability a bye-caliber team (the
    published benchmark — `sor_benchmark`) would produce AT MOST this record
    against this exact schedule. Higher = the record is the more unusual
    achievement. Per-dual win probability is the Bradley-Terry form,
    bench / (bench + opponent); the whole thing is an exact Poisson-binomial
    DP, deterministic with no simulation."""
    if not bt:
        return {}
    bench = sor_benchmark(bt)
    sched: dict[str, list[str]] = {}
    wins: dict[str, int] = {}
    for r in rows:
        sched.setdefault(r["home"], []).append(r["away"])
        sched.setdefault(r["away"], []).append(r["home"])
        wins[r["home"]] = wins.get(r["home"], 0) + (1 if r["hp"] > r["ap"] else 0)
        wins[r["away"]] = wins.get(r["away"], 0) + (1 if r["ap"] > r["hp"] else 0)
    out = {}
    for name, opps in sched.items():
        dist = [1.0]                                 # P(k wins) over duals so far
        for opp in opps:
            op = bt.get(opp, 1.0)
            p = bench / (bench + op) if (bench + op) > 0 else 0.5
            nxt = [0.0] * (len(dist) + 1)
            for k, q in enumerate(dist):
                nxt[k] += q * (1.0 - p)
                nxt[k + 1] += q * p
            dist = nxt
        # Mid-P convention: P(W < wins) + P(W = wins)/2. Plain P(W <= wins)
        # hands every undefeated team exactly 1.0 whatever it played — the
        # continuity correction keeps a perfect record against a brutal
        # schedule above a perfect record against a soft one.
        w = wins.get(name, 0)
        out[name] = sum(dist[:w]) + 0.5 * dist[w]
    return out


# --- the composite -----------------------------------------------------------

def _ranks(values: dict[str, float], names: list[str]) -> dict[str, int]:
    """Ratings -> ranks (1 = best); a team the system could not rate ranks last.
    Ties break on the name so the archive is reproducible."""
    order = sorted(names, key=lambda n: (-values.get(n, float("-inf")), n))
    return {n: i + 1 for i, n in enumerate(order)}


def group_ratings(teams: list) -> dict:
    """The whole layer for one (group, gender): nine systems, ranks, composite.

    Returns {"teams": {name: {"record", "district", "ranks": {system: rank},
    "values": {system: rating}, "mean", "median", "sigma"}},
    "disconnected": bool, "systems": SYSTEMS}. On a disconnected schedule the
    least-squares family (massey_dual, massey_game, srs) is WITHHELD — reported,
    never fit — and the composite folds the systems that remain."""
    rows = dual_rows(teams)
    names = sorted(t.school.name for t in teams)
    disconnected = not connected(rows, teams)
    values: dict[str, dict] = {
        "colley": colley(rows),
        "bt": bradley_terry(rows),
        "win_pct": win_pct(rows),
        "set_share": set_share(rows),
        "elo": elo(rows),
    }
    values["sor"] = sor(rows, values["bt"])
    if not disconnected:
        values["massey_dual"] = massey_dual(rows)
        values["srs"] = srs(rows)
        values["massey_game"] = massey_game(rows)
    ranks = {s: _ranks(values[s], names) for s in SYSTEMS if s in values}
    out: dict[str, dict] = {}
    by_name = {t.school.name: t for t in teams}
    for n in names:
        rk = {s: ranks[s][n] for s in SYSTEMS if s in ranks}
        vals = list(rk.values())
        out[n] = {
            "record": by_name[n].record,
            "district": by_name[n].school.district,
            "ranks": rk,
            "values": {s: values[s].get(n) for s in SYSTEMS if s in values},
            "mean": sum(vals) / len(vals) if vals else 0.0,
            "median": statistics.median(vals) if vals else 0.0,
            "sigma": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
        }
    return {"teams": out, "disconnected": disconnected,
            "systems": list(SYSTEMS),
            # The SOR benchmark, frozen at this run and published on the page.
            "sor_bench": sor_benchmark(values["bt"])}


#: One-paragraph glossary per system (spec 1.5), rendered on the ratings page.
GLOSSARY = {
    "colley": ("Colley — wins and losses run through a schedule adjustment: "
               "beating teams that themselves win is worth more. Ignores margin "
               "entirely, so it over-rates teams that win close and under-rates "
               "teams that win big against the same schedule."),
    "bt": ("Bradley-Terry — a maximum-likelihood fit answering 'what team "
           "strengths make this exact set of wins and losses most likely?'. "
           "Margin-blind like Colley; over-rates a lucky record, under-rates "
           "dominant teams whose schedule never tested them."),
    "win_pct": ("Win% — the raw record, no adjustment at all. Included as the "
                "naive view on purpose: it over-rates a soft schedule and "
                "under-rates a brutal one, and when it disagrees with the "
                "adjusted systems, the schedule is why."),
    "massey_dual": ("Massey (dual) — least squares on the flight margin of "
                    "every dual: a 7-0 says more than a 4-3. Over-rates teams "
                    "that run up flight margins on weak sides; under-rates "
                    "teams that win tight duals against good ones."),
    "srs": ("SRS — average flight margin plus average opponent rating, iterated "
            "until stable. The simplest margin-plus-schedule blend; shares "
            "Massey-dual's blowout appetite but is easier to read."),
    "massey_game": ("Massey (game) — the same least squares built from total "
                    "GAME differential across every flight, ~1.1M games rather "
                    "than ~12k duals. Least sensitive to which close flights "
                    "fell a team's way; under-rates teams that win the big "
                    "points and nothing else."),
    "set_share": ("Set share — sets won over sets played, schedule-adjusted the "
                  "way Colley adjusts win%. Sits between the record systems and "
                  "the game-level ones; a team losing 4-3 duals while winning "
                  "most sets rises here first."),
    "sor": ("SOR — the probability that a bye-caliber team (the published "
            "benchmark: the median Bradley-Terry rating of this group's teams "
            "ranked 9-16) would do no better than this exact record against "
            "this exact schedule. Pure résumé: rewards who you beat, ignores "
            "how. Under-rates dominant teams with easy schedules."),
    "elo": ("Elo — updated dual by dual in play order, so September fades and "
            "form counts. The only system where WHEN you won matters; "
            "over-reacts to a hot finish, under-rates a team that banked its "
            "wins early."),
}

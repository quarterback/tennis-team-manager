"""JHSAA Coach of the Year — District (per league) and State (per class), by gender.

Owner spec 2026-09. Both awards go to HEAD coaches and both are RÉSUMÉ selections
off the archived season: nothing reads a coach's ratings. Every component is a
0-100 score, and a coach is ranked against the other heads in the same pool —
the league for District, the classification for State.

DISTRICT — a district-season award; a State run never decides it:
  45% district overperformance  z of district wins over the preseason expectation
  40% district achievement      100 × (0.65 × place percentile + 0.35 × district win %)
  10% program improvement       schedule-adjusted percentile vs a 3-season baseline
   5% overall team quality      final schedule-adjusted rating percentile

STATE — the whole season, where the record and the run matter:
  30% season quality            final schedule-adjusted rating percentile (class)
  30% postseason achievement    the coefficient's State prices + the TOC bonus
  30% overperformance           20 pts full-season z, 10 pts postseason surprise
  10% program improvement

THE EXPECTATION IS PRESEASON. Each program's strength is the mean overall of the
nine it would dress, read off the roster the season was played with
(`jhsaa_preseason`, written by the rung; a season archived before that table is
backfilled by rebuilding its rosters, which `build_roster` does deterministically).
A dual's win probability is a logistic on the strength gap plus a home-court term,
FITTED on that season's own varsity duals. The z uses the binomial denominator
√Σp(1−p): two wins over a schedule of coin flips is less remarkable than two wins
where the model was sure the team would lose. Capped ±2.5.

THE POSTSEASON SURPRISE simulates the qualifying process and the State bracket from
the preseason strengths (`SIMS` draws per class, seeded on blake2s): qualification
is the top of the class by strength plus a season's worth of noise, the bracket is
single elimination on the logistic. A team's expected State value is its mean
priced finish; the surprise is actual − expected.

SCHEDULE-ADJUSTED RATING is TOSS (`pi` on the archived standings row), read back,
never refitted. Improvement compares this season's percentile with a weighted
baseline of the previous three (0.5 / 0.3 / 0.2, renormalised over the seasons that
exist); a program with no history scores a neutral 50.

Selected once, when a season is archived, and stored in `jhsaa_coach_award` — never
recomputed on read. A season archived before this module is awarded once through
`ensure_season` (the rosters are rebuilt for its preseason strengths)."""

from __future__ import annotations

import hashlib
import json
import math
import random

SIMS = 400
Z_CAP = 2.5
FINALISTS = 5

DISTRICT_WEIGHTS = {"over": 0.45, "achieve": 0.40, "improve": 0.10, "quality": 0.05}
STATE_WEIGHTS = {"quality": 0.30, "post": 0.30, "over": 0.30, "improve": 0.10}
STATE_OVER_SPLIT = (20.0, 10.0)           # full-season z : postseason surprise
BASELINE_WEIGHTS = (0.5, 0.3, 0.2)        # one, two, three seasons back
IMPROVE_FULL = 0.5                        # a percentile move worth full marks
SURPRISE_FULL = 40.0                      # State points above expectation for full marks

SCHEMA = """
CREATE TABLE IF NOT EXISTS jhsaa_preseason (
  world_id INTEGER, year INTEGER, gender TEXT, school TEXT, strength REAL,
  PRIMARY KEY (world_id, year, gender, school)
);
CREATE TABLE IF NOT EXISTS jhsaa_coach_award (
  world_id INTEGER, year INTEGER, gender TEXT, level TEXT, grp TEXT, district TEXT,
  rank INTEGER, school TEXT, ident TEXT, coach_id TEXT, coach_name TEXT,
  score REAL, detail TEXT
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_coach_award ON jhsaa_coach_award(world_id, year, gender);
CREATE INDEX IF NOT EXISTS ix_jhsaa_coach_award_coach ON jhsaa_coach_award(world_id, coach_id);
"""


def _conn():
    from . import world
    return world._db()


def _rng(*parts) -> random.Random:
    h = hashlib.blake2s("|".join(map(str, parts)).encode(), digest_size=8).digest()
    return random.Random(int.from_bytes(h, "big"))


def strength_of(roster) -> float:
    """The preseason strength: the mean overall of the nine who would dress —
    `jhsaa._strength`'s rule, so the expectation reads the same talent the
    non-district draw and rest staffing read."""
    top = sorted((p.current_overall() for p in roster), reverse=True)[:9]
    return sum(top) / len(top) if top else 0.0


def record_preseason(conn, world_id: int, year: int, gender: str, teams) -> None:
    """Written by the rung inside its transaction, beside the coach history."""
    conn.executemany(
        "INSERT OR REPLACE INTO jhsaa_preseason (world_id, year, gender, school, strength)"
        " VALUES (?,?,?,?,?)",
        [(world_id, year, gender, t.school.name, strength_of(t.roster)) for t in teams])


def _preseason(world_id: int, year: int, gender: str, schools: list[str],
               salt: str) -> dict:
    """{school: strength} — the stored rows, else rebuilt rosters (backfill)."""
    conn = _conn()
    try:
        got = {s: v for s, v in conn.execute(
            "SELECT school, strength FROM jhsaa_preseason WHERE world_id=? AND year=?"
            " AND gender=?", (world_id, year, gender))}
    finally:
        conn.close()
    missing = [s for s in schools if s not in got]
    if missing:
        from . import jhsaa as jh
        from .world import BASE_YEAR
        season_year = BASE_YEAR + year + 1
        live = {s.name: s for s in jh.load_schools(gender)}
        rows = []
        for name in missing:
            sc = live.get(name) or jh.former_school(name, gender)
            if sc is None:
                continue
            v = strength_of(jh.build_roster(sc, season_year, salt))
            got[name] = v
            rows.append((world_id, year, gender, name, v))
        if rows:
            conn = _conn()
            try:
                conn.executemany(
                    "INSERT OR REPLACE INTO jhsaa_preseason (world_id, year, gender,"
                    " school, strength) VALUES (?,?,?,?,?)", rows)
                conn.commit()
            finally:
                conn.close()
    return got


# ---------------------------------------------------------------- the model ----

def _sig(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, x))))


def fit_curve(samples: list[tuple[float, float, float]]) -> tuple[float, float]:
    """(k, h) for P(win) = σ(k·gap + h·hosted), fitted by Newton's method on
    (gap, hosted ∈ {-1,0,1}, result ∈ [0,1]) — one row per dual, one side's
    perspective. Falls back to a mild slope when the season is degenerate."""
    k, h = 0.2, 0.0
    if len(samples) < 20:
        return k, h
    for _ in range(25):
        g0 = g1 = 0.0
        a00 = a11 = 1e-6                    # ridge on the diagonal only
        a01 = 0.0
        for gap, host, y in samples:
            p = _sig(k * gap + h * host)
            w = p * (1 - p)
            g0 += (y - p) * gap
            g1 += (y - p) * host
            a00 += w * gap * gap
            a01 += w * gap * host
            a11 += w * host * host
        det = a00 * a11 - a01 * a01
        if det <= 0:
            break
        dk = (a11 * g0 - a01 * g1) / det
        dh = (a00 * g1 - a01 * g0) / det
        k, h = k + dk, h + dh
        if abs(dk) < 1e-7 and abs(dh) < 1e-7:
            break
    return max(0.01, min(3.0, k)), max(-2.0, min(2.0, h))


def z_score(results: list[tuple[float, float]]) -> float | None:
    """(actual, expected p) per dual → the capped binomial z, or None with no duals."""
    if not results:
        return None
    w = sum(r for r, _p in results)
    e = sum(p for _r, p in results)
    v = sum(p * (1 - p) for _r, p in results)
    if v <= 1e-9:
        return 0.0
    return max(-Z_CAP, min(Z_CAP, (w - e) / math.sqrt(v)))


def z_to_score(z: float | None) -> float:
    return 50.0 if z is None else (z + Z_CAP) / (2 * Z_CAP) * 100.0


def _pctile(order: list[str]) -> dict:
    """[best … worst] → {name: 1.0 … 0.0}."""
    n = len(order)
    return {s: (1.0 if n <= 1 else 1.0 - i / (n - 1)) for i, s in enumerate(order)}


def expected_state_values(strength: dict, field: int, k: float, seed_key: tuple,
                          sims: int = SIMS) -> dict:
    """{school: mean priced State finish} for one class, simulated from preseason
    strengths: qualification = the top `field` by strength plus a season's noise,
    then a seeded single-elimination bracket (byes to the top seeds) played on
    the fitted logistic. TOC entry is priced on winning the class."""
    from .jhsaa_coefficient import state_points, TOC_BONUS
    names = sorted(strength)
    if field < 2 or len(names) < 2:
        return {s: 0.0 for s in names}
    field = min(field, len(names))
    rng = _rng("jhsaa-coy-sim", *seed_key)
    season_sd = 1.2 / k
    total = {s: 0.0 for s in names}
    size = 1
    while size < field:
        size *= 2
    for _ in range(sims):
        noisy = sorted(names, key=lambda s: -(strength[s] + rng.gauss(0, season_sd)))
        seeds = noisy[:field]
        # Standard bracket order: seed i meets seed (size+1-i); a missing seed is a bye.
        slots = _bracket_order(size)
        line = [seeds[i - 1] if i <= field else None for i in slots]
        alive = field
        while len(line) > 1:
            nxt = []
            losers = []
            for a, b in zip(line[0::2], line[1::2]):
                if a is None or b is None:
                    nxt.append(a or b)
                    continue
                p = _sig(k * (strength[a] - strength[b]))
                win, lose = (a, b) if rng.random() < p else (b, a)
                nxt.append(win)
                losers.append(lose)
            for lo in losers:
                total[lo] += state_points(alive)
            alive -= len(losers)
            line = nxt
        champ = line[0]
        if champ is not None:
            total[champ] += state_points(1) + TOC_BONUS
    return {s: v / sims for s, v in total.items()}


def _bracket_order(size: int) -> list[int]:
    order = [1]
    while len(order) < size:
        n = len(order) * 2
        order = [x for s in order for x in (s, n + 1 - s)]
    return order


# ------------------------------------------------------------ the selection ----

def select_season(world_id: int, year: int, gender: str, salt: str) -> dict:
    """Score every head coach of an archived season and store the District and
    State awards (winner + finalists per pool). Returns {"district": n, "state": n}."""
    from . import world
    from . import jhsaa as jh
    from . import jhsaa_coaches as jc
    from .jhsaa_coefficient import season_points
    arc = world.get_jhsaa(world_id, year, gender)
    if not arc:
        return {"district": 0, "state": 0}
    # Who played where: {school: (grp, district, row)}.
    where: dict = {}
    for grp, dists in (arc.get("standings") or {}).items():
        for dname, rows in (dists or {}).items():
            for r in rows or ():
                if r.get("school"):
                    where[r["school"]] = (grp, dname, r)
    if not where:
        return {"district": 0, "state": 0}
    heads = jc.season_heads(world_id, gender)
    inv = {nm: i for i, nm in jc.ident_names(gender).items()}
    strength = _preseason(world_id, year, gender, list(where), salt)
    alias = jh.former_names()
    # One side's perspective per row: every varsity dual appears once per school.
    conn = _conn()
    try:
        duals = conn.execute(
            "SELECT school, opp, home, phase, won, tied, district FROM world_jhsaa_dual"
            " WHERE world_id=? AND year=? AND gender=? AND COALESCE(level,'v')='v'",
            (world_id, year, gender)).fetchall()
    finally:
        conn.close()
    samples = []
    per_team: dict = {}
    for school, opp, home, phase, won, tied, dist in duals:
        school, opp = alias.get(school, school), alias.get(opp, opp)
        if school not in strength or opp not in strength:
            continue
        y = 0.5 if tied else (1.0 if won else 0.0)
        host = 0 if phase in jh.NEUTRAL_PHASES else (1 if home else -1)
        gap = strength[school] - strength[opp]
        samples.append((gap, host, y))
        per_team.setdefault(school, []).append((gap, host, y, bool(dist)))
    k, h = fit_curve(samples)

    def res(school, district_only):
        return [(y, _sig(k * gap + h * host))
                for gap, host, y, dist in per_team.get(school, ())
                if dist or not district_only]

    # Schedule-adjusted percentile (TOSS) within the class, this season and the
    # three before — the improvement baseline.
    def class_pctiles(a) -> dict:
        out = {}
        for grp, dists in (a.get("standings") or {}).items():
            rows = [r for rows in (dists or {}).values() for r in rows or ()
                    if r.get("school")]
            rows.sort(key=lambda r: -(r.get("pi") if r.get("pi") is not None else -9))
            out.update(_pctile([r["school"] for r in rows]))
        return out
    now_pct = class_pctiles(arc)
    past = []
    for back in (1, 2, 3):
        a = world.get_jhsaa(world_id, year - back, gender)
        past.append(class_pctiles(a) if a else {})

    def improve(school) -> float:
        num = den = 0.0
        for wgt, pc in zip(BASELINE_WEIGHTS, past):
            if school in pc:
                num += wgt * pc[school]
                den += wgt
        if den == 0:
            return 50.0
        delta = now_pct.get(school, 0.5) - num / den
        return 50.0 + 50.0 * max(-1.0, min(1.0, delta / IMPROVE_FULL))

    actual = season_points(arc)            # keyed by display name (no rows passed)
    rows_out = []

    def head_of(school):
        return heads.get((year, inv.get(school)))

    # ---------------- District: one per (class, league) ----------------
    n_d = 0
    by_district: dict = {}
    for school, (grp, dname, r) in where.items():
        by_district.setdefault((grp, dname), []).append((school, r))
    for (grp, dname), teams in by_district.items():
        n = len(teams)
        cands = []
        for school, r in teams:
            hd = head_of(school)
            if not hd:
                continue
            z = z_score(res(school, True))
            over = z_to_score(z)
            place = r.get("place") or n
            place_pct = 1.0 if n <= 1 else 1.0 - (place - 1) / (n - 1)
            dw, dl, dt = _wlt(r.get("drecord"))
            dpct = (dw + 0.5 * dt) / (dw + dl + dt) if dw + dl + dt else 0.0
            achieve = 100.0 * (0.65 * place_pct + 0.35 * dpct)
            imp = improve(school)
            qual = 100.0 * now_pct.get(school, 0.5)
            parts = {"over": over, "achieve": achieve, "improve": imp, "quality": qual}
            score = sum(DISTRICT_WEIGHTS[c] * v for c, v in parts.items())
            cands.append((score, school, hd, {**parts, "z": z, "place": place,
                                              "drecord": r.get("drecord", ""),
                                              "record": r.get("record", "")}))
        cands.sort(key=lambda c: (-c[0], c[1]))
        for rank, (score, school, hd, detail) in enumerate(cands[:FINALISTS], 1):
            rows_out.append((world_id, year, gender, "district", grp, dname, rank, school,
                             inv.get(school, ""), hd["coach_id"], hd["name"],
                             round(score, 2), json.dumps(detail)))
        n_d += bool(cands)

    # ---------------- State: one per class ----------------
    n_s = 0
    by_class: dict = {}
    for school, (grp, _d, r) in where.items():
        by_class.setdefault(grp, []).append((school, r))
    for grp, teams in by_class.items():
        br = (arc.get("brackets") or {}).get(grp) or {}
        field = len(br.get("field") or ())
        exp = expected_state_values({s: strength[s] for s, _r in teams if s in strength},
                                    field, k, (world_id, year, gender, grp))
        cands = []
        for school, r in teams:
            hd = head_of(school)
            if not hd:
                continue
            got = actual.get(school) or {}
            value = (got.get("state") or 0.0) + (got.get("toc") or 0.0)
            post = min(100.0, value / (52 + 4) * 100.0)
            z = z_score(res(school, False))
            surprise = value - exp.get(school, 0.0)
            s_score = 50.0 + 50.0 * max(-1.0, min(1.0, surprise / SURPRISE_FULL))
            zs, ss = STATE_OVER_SPLIT
            over = (zs * z_to_score(z) + ss * s_score) / (zs + ss)
            qual = 100.0 * now_pct.get(school, 0.5)
            imp = improve(school)
            parts = {"quality": qual, "post": post, "over": over, "improve": imp}
            score = sum(STATE_WEIGHTS[c] * v for c, v in parts.items())
            cands.append((score, school, hd, {**parts, "z": z,
                                              "state_value": value,
                                              "expected": round(exp.get(school, 0.0), 2),
                                              "record": r.get("record", "")}))
        cands.sort(key=lambda c: (-c[0], c[1]))
        for rank, (score, school, hd, detail) in enumerate(cands[:FINALISTS], 1):
            rows_out.append((world_id, year, gender, "state", grp, "", rank, school,
                             inv.get(school, ""), hd["coach_id"], hd["name"],
                             round(score, 2), json.dumps(detail)))
        n_s += bool(cands)

    conn = _conn()
    try:
        conn.execute("DELETE FROM jhsaa_coach_award WHERE world_id=? AND year=? AND gender=?",
                     (world_id, year, gender))
        conn.executemany(
            "INSERT INTO jhsaa_coach_award (world_id, year, gender, level, grp, district,"
            " rank, school, ident, coach_id, coach_name, score, detail)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows_out)
        conn.commit()
    finally:
        conn.close()
    return {"district": n_d, "state": n_s}


def _wlt(rec: str | None) -> tuple[int, int, int]:
    bits = [int(x) for x in (rec or "").split("-") if x.strip().isdigit()]
    bits += [0, 0, 0]
    return bits[0], bits[1], bits[2]


# ---------------------------------------------------------------- read side ----

def has_awards(world_id: int, year: int, gender: str) -> bool:
    conn = _conn()
    try:
        return conn.execute("SELECT 1 FROM jhsaa_coach_award WHERE world_id=? AND year=?"
                            " AND gender=? LIMIT 1", (world_id, year, gender)).fetchone() is not None
    finally:
        conn.close()


def needs_awards(world_id: int, year: int, gender: str) -> bool:
    """A season with a coaching history and no awards yet (archived before this
    module) — the one case `ensure_season` backfills."""
    conn = _conn()
    try:
        hist = conn.execute("SELECT 1 FROM jhsaa_coach_history WHERE world_id=? AND year=?"
                            " AND gender=? AND slot='head' LIMIT 1",
                            (world_id, year, gender)).fetchone()
    finally:
        conn.close()
    return bool(hist) and not has_awards(world_id, year, gender)


def season_awards(world_id: int, year: int, gender: str) -> dict:
    """{"state": {grp: [rows by rank]}, "district": {(grp, district): [rows]}}."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT level, grp, district, rank, school, coach_id, coach_name, score, detail"
            " FROM jhsaa_coach_award WHERE world_id=? AND year=? AND gender=?"
            " ORDER BY rank", (world_id, year, gender)).fetchall()
    finally:
        conn.close()
    out: dict = {"state": {}, "district": {}}
    for level, grp, dist, rank, school, cid, nm, score, detail in rows:
        r = {"rank": rank, "school": school, "coach_id": cid, "name": nm,
             "score": score, "detail": json.loads(detail or "{}")}
        if level == "state":
            out["state"].setdefault(grp, []).append(r)
        else:
            out["district"].setdefault((grp, dist), []).append(r)
    return out


def coach_awards(world_id: int, coach_id: str) -> list[dict]:
    """Every Coach of the Year a coach has WON, newest first."""
    from .world import BASE_YEAR
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT year, gender, level, grp, district, school FROM jhsaa_coach_award"
            " WHERE world_id=? AND coach_id=? AND rank=1 ORDER BY year DESC",
            (world_id, coach_id)).fetchall()
    finally:
        conn.close()
    return [{"world_year": y, "season_year": BASE_YEAR + int(y) + 1, "gender": g,
             "level": lv, "grp": grp, "district": d, "school": s,
             "label": (f"{grp} Coach of the Year" if lv == "state"
                       else f"{d} Coach of the Year")}
            for y, g, lv, grp, d, s in rows]


def program_awards(world_id: int, ident: str, gender: str) -> dict:
    """{world_year: [labels]} — the Coach of the Year honours a program's head won."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT year, level, grp, district FROM jhsaa_coach_award WHERE world_id=?"
            " AND ident=? AND gender=? AND rank=1", (world_id, ident, gender)).fetchall()
    finally:
        conn.close()
    out: dict = {}
    for y, lv, grp, d in rows:
        out.setdefault(y, []).append("State COY" if lv == "state" else "District COY")
    return out

"""THE JEFFERSON ALUMNI TRACKER — where the JHSAA's graduates played college tennis
(owner rule 2026-11).

The JHSAA sim is separate from the college game (`worldconfig.jhsaa_sim`), so a lab
save has no college world to send its seniors into. The owner still wants to follow
them — "as a finished product rather than real time seasons". Simulating a college
year for it was measured and rejected: one hands-off year cost 10 minutes with only
D1 active and about 25 with every division, on top of the 18-minute high-school
season.

So this is NOT a simulation. When a class graduates, its best `CLASS_SIZE` seniors a
gender are each given:
  - a real college PROGRAM (`ncaa.load_division` — the institutions, no rosters), and
  - a finished four-year LINE: lineup position and singles record per season, the
    peak position, the career record and any honours.
It is written ONCE (`world_jhsaa_college`, keyed on the pid) and only ever read after
that — a page never regenerates a career, so a constant retuned here reaches classes
that have not graduated yet and nobody else.

‼️ NOTHING HERE FEEDS ANYTHING. No rating, ladder, award, recruit board or college
save reads these rows; they are an epilogue. A lab save that later has college
ATTACHED plays real college tennis from that year on, and its recruit board comes
from the real hand-off — these rows are not written for a world with college rosters.

Costs: one class is ~200 placements against a short window of programs — a few
milliseconds. A class that graduated before the tracker existed is filled in from
the `jhsaa_alumni` index (every senior of every season since coaches landed, with
the rating they left on) the first time somebody asks for it; nothing is rebuilt.
"""
from __future__ import annotations

import json
import random

from . import ncaa

#: WHICH CAREER MODEL NEW CLASSES ARE WRITTEN WITH. Model 1 is the original
#: rank-matched line below; model 2 is `jhsaa_college_v2` (owner spec 2026-11).
#: ‼️ A career is written once and never regenerated, so switching this only
#: changes classes that have no rows yet — and it stays at 1 until the owner has
#: seen model 2's measured distribution (`scripts/jhsaa_college_validate.py`),
#: because every class written in the meantime would carry unapproved rates
#: permanently. Rewriting classes already stored is a separate, explicitly
#: authorised migration and nothing here does it.
ACTIVE_MODEL = 1

#: How many seniors a gender send on each year — about what Jefferson's origin
#: weight put on the national recruit board when the two sims were joined.
CLASS_SIZE = 200

#: Best to worst, the order a class is dealt into the divisions. D4 before D3 is the
#: college game's own ladder (the academic-first tier holds the real best non-D1
#: programs; D3 is the widest, lowest-floor tier).
DIVISION_ORDER = ("D1", "D2", "D4", "D3")

#: How far a senior's standing is blurred before the divisions are cut, as a share
#: of the class — so the line between two divisions is a band, not a rank.
RANK_BLUR = 0.05

#: The pull toward home. Jefferson DEVELOPS and its kids LEAVE (CLAUDE.md), so both
#: are tiebreak-sized next to the fit term: an in-state program, then the West.
HOME_STATE_PULL = 0.35
HOME_REGION_PULL = 0.15

#: At most this many of one class's seniors (per gender) at one program.
PER_PROGRAM = 1

_CLASS_YEARS = ("Fr", "So", "Jr", "Sr")
_COLLEGE_GENDER = {"boys": "men", "girls": "women"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_jhsaa_college (
  world_id INTEGER, grad_year INTEGER, gender TEXT, pid TEXT, rank INTEGER,
  name TEXT, hs TEXT, college TEXT, division TEXT, data TEXT,
  PRIMARY KEY (world_id, pid)
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_college_class
  ON world_jhsaa_college(world_id, grad_year, gender);
-- THE GRADUATION SNAPSHOT (owner spec 2026-11): what a class's leading seniors
-- had done and were when they graduated — ability, estimated and true ceiling,
-- singles and doubles records by flight, honours, style, academics, where they
-- are from — captured at the rung from the season it just played. It is the
-- career model's input, kept so a career never needs a roster rebuilt to explain
-- it. One row per senior, the class's top `CANDIDATES` by exit rating.
CREATE TABLE IF NOT EXISTS world_jhsaa_grad_snapshot (
  world_id INTEGER, grad_year INTEGER, gender TEXT, pid TEXT, data TEXT,
  PRIMARY KEY (world_id, pid)
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_grad_snapshot_class
  ON world_jhsaa_grad_snapshot(world_id, grad_year, gender);
-- The alumni index is read here one CLASS at a time (to fill in a class that
-- graduated before the tracker); its own index is by school.
CREATE INDEX IF NOT EXISTS ix_jhsaa_alumni_class
  ON jhsaa_alumni(world_id, gender, grad_year);
"""

_programs_cache: dict = {}


def _programs(gender: str) -> dict:
    """`{division: [Program, …]}` for a JHSAA gender, each list best prestige first.
    Institutions only — read off the data files, never a world's rosters."""
    hit = _programs_cache.get(gender)
    if hit is not None:
        return hit
    out = {}
    for d in DIVISION_ORDER:
        progs = list(ncaa.load_division(d, _COLLEGE_GENDER[gender]).programs)
        progs.sort(key=lambda p: (-p.prestige, p.school))
        out[d] = progs
    _programs_cache[gender] = out
    return out


def division_counts(n: int, gender: str) -> dict:
    """How many of a class of `n` each division takes: in proportion to the seats it
    turns over a year (programs × roster cap ÷ four classes). Derived, never typed."""
    progs = _programs(gender)
    seats = {d: len(progs[d]) * ncaa.roster_cap(d) / 4.0 for d in DIVISION_ORDER}
    total = sum(seats.values()) or 1.0
    counts, left = {}, n
    for d in DIVISION_ORDER[:-1]:
        counts[d] = min(left, round(n * seats[d] / total))
        left -= counts[d]
    counts[DIVISION_ORDER[-1]] = left
    return counts


def _place(seniors: list, gender: str, rng: random.Random) -> list:
    """Deal a ranked class into divisions and then programs.
    Returns `[(senior, Program, standing)]`, `standing` 1.0 = the best of the seniors
    headed to that division, 0.0 = the last."""
    n = len(seniors)
    blurred = sorted(range(n), key=lambda i: i / max(1, n) + rng.gauss(0.0, RANK_BLUR))
    counts = division_counts(n, gender)
    progs = _programs(gender)
    out, cursor = [], 0
    for d in DIVISION_ORDER:
        band = sorted(blurred[cursor:cursor + counts[d]])     # back in true rank order
        cursor += counts[d]
        pool, taken = progs[d], {}
        per = max(PER_PROGRAM, -(-len(band) // max(1, len(pool))))
        for j, i in enumerate(band):
            s = seniors[i]
            t = j / max(1, len(band) - 1)                    # 0 best … 1 last
            # Only the programs near where this senior stands are in view — a
            # window, so a class is ~200 × a few dozen scores, not 200 × ~1,000.
            centre = t * (len(pool) - 1)
            half = max(12, len(pool) // 6)
            lo, hi = max(0, int(centre - half)), min(len(pool), int(centre + half) + 1)
            best, best_score = None, None
            for k in range(lo, hi):
                p = pool[k]
                if taken.get(p.school, 0) >= per:
                    continue
                # Every pipeline that puts a player at a program asks the ONE
                # authority on the service academies (CLAUDE.md).
                if ncaa.us_only_program(p.school) and not s.get("domestic"):
                    continue
                score = (-abs(k - centre) / max(1.0, half)
                         + (HOME_STATE_PULL if p.state == "JF" else
                            HOME_REGION_PULL if p.region == "W" else 0.0)
                         + rng.gauss(0.0, 0.35))
                if best_score is None or score > best_score:
                    best, best_score = p, score
            if best is None:                                  # window exhausted
                best = min((p for p in pool
                            if not ncaa.us_only_program(p.school) or s.get("domestic")),
                           key=lambda p: taken.get(p.school, 0))
            taken[best.school] = taken.get(best.school, 0) + 1
            out.append((s, best, 1.0 - t))
    return out


def _career(senior: dict, prog, standing: float, salt: str) -> dict:
    """The finished four-year line for one senior at `prog`. Its own rng stream,
    keyed on the pid, so the line is the same whoever asks and whenever."""
    rng = random.Random(f"{salt}|jf-college|{senior['pid']}")
    pool = _programs(senior["gender"])[prog.division]
    strength = 1.0 - pool.index(prog) / max(1, len(pool) - 1)   # 1 = best program
    n = ncaa.lineup_size(prog.division)
    # FIT: how good this player is for THIS team. A strong recruit at a modest
    # program plays high from the start; a modest one at a power waits.
    fit = (standing - strength) + rng.gauss(0.0, 0.20)
    # How much they grow in college: the gap between what they are and what their
    # staff thought they could be, when the class was read at graduation.
    pot = senior.get("pot")
    growth = (max(0.0, min(1.0, (pot - senior["ovr"]) / 15.0)) if pot is not None
              else rng.random() * 0.6)
    knack = rng.gauss(0.0, 0.05)                                # wins more than the slot says
    spot = n * 0.55 - fit * n * 0.9 + 2.2                       # freshman-year position
    seasons = []
    for i, cls in enumerate(_CLASS_YEARS):
        raw = spot - i * (1.05 + 1.0 * growth) + rng.gauss(0.0, 0.8)
        pos = max(1, round(raw)) if raw <= n + 0.5 else None
        if pos is None:                                         # not in the lineup
            m = rng.randint(0, 8)
            p_win = 0.45 + 0.20 * (strength - 0.5)
        else:
            m = rng.randint(17, 27)
            # A team's record sets the base; higher on the ladder is harder.
            p_win = (0.50 + 0.26 * (strength - 0.5) + 0.10 * (pos - 1) / max(1, n - 1)
                     + knack + rng.gauss(0.0, 0.05))
        p_win = max(0.12, min(0.92, p_win))
        w = sum(rng.random() < p_win for _ in range(m))
        honors = []
        if pos is not None and m >= 15:
            pct = w / m
            if pos <= 2 and pct >= 0.62 and rng.random() < 0.8:
                honors.append("All-Conference")
            if pos == 1 and pct >= 0.76 and strength >= 0.55:
                honors.append("All-American")
        seasons.append({"year": senior["grad_year"] + 1 + i, "class": cls, "pos": pos,
                        "w": w, "l": m - w, "honors": honors})
    played = [s["pos"] for s in seasons if s["pos"]]
    tally: dict = {}
    for s in seasons:
        for h in s["honors"]:
            tally[h] = tally.get(h, 0) + 1
    return {
        "pid": senior["pid"], "name": senior["name"], "gender": senior["gender"],
        "hs": senior["hs"], "grad_year": senior["grad_year"], "rank": senior["rank"],
        "hs_ovr": round(senior["ovr"], 1),
        "college": prog.school, "division": prog.division, "conf": prog.conf_abbr,
        "seasons": seasons, "peak": min(played) if played else None,
        "w": sum(s["w"] for s in seasons), "l": sum(s["l"] for s in seasons),
        # Best honour first, each with how many times it was won.
        "honors": [f"{h} ×{c}" if c > 1 else h
                   for h, c in sorted(tally.items(),
                                      key=lambda kv: kv[0] != "All-American")],
    }


def build_class(seniors: list, gender: str, grad_year: int, salt: str) -> list:
    """The tracker rows for one graduating class. `seniors` is every senior of the
    gender as dicts (`pid`, `name`, `hs`, `ovr`, and optionally `pot`, `domestic`);
    the best `CLASS_SIZE` by the rating they left on go on."""
    ranked = sorted(seniors, key=lambda s: (-s["ovr"], s["pid"]))[:CLASS_SIZE]
    for i, s in enumerate(ranked, 1):
        s.update(rank=i, gender=gender, grad_year=grad_year)
    rng = random.Random(f"{salt}|jf-college-class|{gender}|{grad_year}")
    return sorted((_career(s, prog, standing, salt)
                   for s, prog, standing in _place(ranked, gender, rng)),
                  key=lambda r: r["rank"])


def ensure_columns(conn) -> None:
    """Columns added after the table first shipped. `ver` is the career model a
    row was written with (NULL reads as 1); `hs_ident` is the school's stable
    identity (`School.ident`), which a rename never moves."""
    for col, typ in (("ver", "INTEGER"), ("hs_ident", "TEXT")):
        try:
            conn.execute(f"ALTER TABLE world_jhsaa_college ADD COLUMN {col} {typ}")
        except Exception:                           # already there
            pass


def _insert(conn, world_id: int, rows: list) -> None:
    """Write careers. INSERT OR IGNORE on the pid: a career already on the record
    is never replaced, whatever model or constants produced the new one."""
    conn.executemany(
        "INSERT OR IGNORE INTO world_jhsaa_college (world_id, grad_year, gender, pid,"
        " rank, name, hs, college, division, data, ver, hs_ident)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [(world_id, r["grad_year"], r["gender"], r["pid"], r["rank"], r["name"],
          r["hs"], r["college"], r["division"], json.dumps(r),
          int(r.get("model", 1)), r.get("hs_ident", "")) for r in rows])


def snapshot_of(p, team, awards: dict | None = None) -> dict:
    """What one senior was at graduation, read off the season just played. Every
    field is something the rung already holds — nothing is rebuilt for it."""
    from . import jhsaa
    from .development import _STYLE_CLUSTERS
    log = team.matches.get(p.pid) or () if hasattr(team, "matches") else ()
    rec = {"s": [0, 0], "d": [0, 0]}
    flights: dict = {}
    post = 0
    for m in log:
        slot, won, phase = m[0], m[1], m[2]
        kind = "s" if str(slot).startswith("S") else "d"
        rec[kind][0 if won else 1] += 1
        flights[slot] = flights.get(slot, 0) + 1
        post += phase in jhsaa.POSTSEASON
    top = lambda k: max((f for f in flights if f.startswith(k)),        # noqa: E731
                        key=lambda f: flights[f], default=None)
    cur = getattr(p, "current", None) or {}
    net = [cur[a] for a in _STYLE_CLUSTERS["net"] if a in cur]
    serve = [cur[a] for a in _STYLE_CLUSTERS["serve"] if a in cur]
    ovr = float(p.current_overall())
    traits = getattr(p, "traits", {}) or {}
    honors = []
    if awards:
        try:
            honors = list(jhsaa.honors_for(p.pid, awards, team.school.group))
        except Exception:                           # an award shape this cannot read
            honors = []
    played = bool(log)
    return {
        "pid": p.pid, "name": p.name,
        "hs": team.school.name, "hs_ident": team.school.ident,
        "hs_class": team.school.classification, "hs_group": team.school.group,
        "hs_area": team.school.area, "hs_county": team.school.county,
        "hometown": getattr(p, "hometown", ""),
        "country": getattr(p, "country", "") or "US",
        "domestic": bool(ncaa.is_domestic_player(p)),
        "academic": int(getattr(p, "academic_rating", 0) or 0) or None,
        "ovr": ovr, "pot": float(jhsaa.pot_display(p)),
        "ceiling": float(p.ceiling_overall()),
        "style": traits.get("play_style", ""), "trait": traits.get("style_trait", ""),
        "net_edge": round(sum(net) / len(net) - ovr, 2) if net else None,
        "serve_edge": round(sum(serve) / len(serve) - ovr, 2) if serve else None,
        # The season's record — None when the senior did not play one (a class
        # captured without a played season), so the model knows not to read it.
        "s_w": rec["s"][0] if played else None, "s_l": rec["s"][1] if played else None,
        "d_w": rec["d"][0] if played else None, "d_l": rec["d"][1] if played else None,
        "s_flight": top("S"), "d_flight": top("D"),
        "matches": len(log), "post_matches": post,
        "honors": honors,
        "dev": {k: v for k, v in (getattr(p, "jhsaa", None) or {}).items()
                if isinstance(v, (int, float, str, bool))},
    }


def capture_snapshots(conn, world_id: int, gender: str, grad_year: int, teams,
                      awards_by_group: dict | None = None,
                      all_region: dict | None = None) -> list:
    """Store the graduation snapshot of the class's leading seniors and return
    them. Written once (the pid is the key) and on the rung's connection."""
    from . import jhsaa_college_v2 as v2
    pairs = [(p, t) for t in teams for p in t.roster if getattr(p, "grade", 0) == 12]
    pairs.sort(key=lambda pt: (-pt[0].current_overall(), pt[0].pid))
    snaps = []
    for p, t in pairs[:v2.CANDIDATES]:
        aw = None
        if awards_by_group is not None:
            aw = {**(awards_by_group.get(t.school.group) or {}),
                  "all_region": all_region or {}}
        snaps.append(snapshot_of(p, t, aw))
    conn.executemany(
        "INSERT OR IGNORE INTO world_jhsaa_grad_snapshot"
        " (world_id, grad_year, gender, pid, data) VALUES (?,?,?,?,?)",
        [(world_id, grad_year, gender, s["pid"], json.dumps(s)) for s in snaps])
    return snaps


def reference(conn, world_id: int, gender: str, grad_year: int) -> list:
    """The exit ratings a class is read against: the leading seniors of each of
    the classes before it, pooled, ascending. Empty for a save's first class."""
    from . import jhsaa_college_v2 as v2
    try:
        rows = conn.execute(
            "SELECT grad_year, ovr FROM jhsaa_alumni WHERE world_id=? AND gender=?"
            " AND grad_year BETWEEN ? AND ? AND rank > 0",
            (world_id, gender, grad_year - v2.REF_CLASSES, grad_year - 1)).fetchall()
    except Exception:
        return []
    by_year: dict = {}
    for gy, ovr in rows:
        by_year.setdefault(gy, []).append(float(ovr or 0.0))
    pool = []
    for vals in by_year.values():
        pool += sorted(vals, reverse=True)[:v2.TARGET_BOUND]
    return sorted(pool)


def stored_seasons(conn, world_id: int, gender: str, grad_year: int) -> dict:
    """`{(college, year): [alumnus-season, …]}` for the model-2 careers of the
    three classes ahead of this one — the alumni a new class will share a team
    with, and whose positions are already on the record."""
    out: dict = {}
    for (data,) in conn.execute(
            "SELECT data FROM world_jhsaa_college WHERE world_id=? AND gender=?"
            " AND grad_year BETWEEN ? AND ? AND ver=2",
            (world_id, gender, grad_year - 3, grad_year - 1)):
        row = json.loads(data)
        for s in row.get("seasons", []):
            out.setdefault((s["college"], s["year"]), []).append(
                {"pid": row["pid"], "slv": s.get("slv", 0.0), "dlv": s.get("dlv", 0.0),
                 "s_pos": s.get("s_pos"), "d_pair": s.get("d_pair")})
    return out


def _build(conn, world_id: int, gender: str, grad_year: int, salt: str,
           snaps: list) -> list:
    """One class's careers under the ACTIVE model."""
    if ACTIVE_MODEL == 1:
        return build_class(snaps, gender, grad_year, salt)
    from . import jhsaa_college_v2 as v2
    return v2.build_class(snaps, gender, grad_year, salt,
                          ref=reference(conn, world_id, gender, grad_year),
                          stored=stored_seasons(conn, world_id, gender, grad_year))


def record_class(conn, world_id: int, gender: str, grad_year: int, salt: str,
                 teams, awards_by_group: dict | None = None,
                 all_region: dict | None = None) -> int:
    """Write this season's graduating class — on the rung's connection, from the
    rosters and results of the season just played. Written once: a pid already
    tracked is left exactly as it was.

    The SNAPSHOT is captured whichever model is active, so a class that graduates
    under model 1 still has its full inputs on record."""
    ensure_columns(conn)
    teams = list(teams)
    snaps = capture_snapshots(conn, world_id, gender, grad_year, teams,
                              awards_by_group, all_region)
    if ACTIVE_MODEL == 1:
        # Model 1 reads every senior (it takes its own top CLASS_SIZE).
        from . import jhsaa
        snaps = [{"pid": p.pid, "name": p.name, "hs": t.school.name,
                  "hs_ident": t.school.ident, "ovr": float(p.current_overall()),
                  "pot": float(jhsaa.pot_display(p)),
                  "domestic": ncaa.is_domestic_player(p)}
                 for t in teams for p in t.roster if getattr(p, "grade", 0) == 12]
    rows = _build(conn, world_id, gender, grad_year, salt, snaps)
    _insert(conn, world_id, rows)
    return len(rows)


def _ensure_class(conn, world_id: int, gender: str, grad_year: int, salt: str) -> None:
    """Fill in a class that has no careers yet. ‼️ A class with ANY row is left
    alone — this never regenerates. The inputs are the graduation snapshot when
    the class has one, else the alumni index (the reduced path: every senior and
    the rating they left on, no ceiling, no record, no nationality — the model
    rolls what it cannot read, and the service academies are out of view).
    No roster is rebuilt either way."""
    if conn.execute("SELECT 1 FROM world_jhsaa_college WHERE world_id=? AND grad_year=?"
                    " AND gender=? LIMIT 1", (world_id, grad_year, gender)).fetchone():
        return
    ensure_columns(conn)
    snaps = [json.loads(r[0]) for r in conn.execute(
        "SELECT data FROM world_jhsaa_grad_snapshot WHERE world_id=? AND grad_year=?"
        " AND gender=?", (world_id, grad_year, gender))]
    if not snaps:
        try:
            idx = conn.execute(
                "SELECT pid, name, school, ovr, ident, style, trait FROM jhsaa_alumni"
                " WHERE world_id=? AND gender=? AND grad_year=?",
                (world_id, gender, grad_year)).fetchall()
        except Exception:                           # no alumni index in this save
            return
        snaps = [{"pid": r[0], "name": r[1], "hs": r[2], "ovr": float(r[3] or 0.0),
                  "hs_ident": r[4] or "", "style": r[5] or "", "trait": r[6] or ""}
                 for r in idx]
    if not snaps:
        return
    _insert(conn, world_id, _build(conn, world_id, gender, grad_year, salt, snaps))
    conn.commit()


def _relabelled(row: dict) -> dict:
    """An archived high-school name, as that school is called today (the archive's
    own rule: relabel on read, never migrate)."""
    from . import jhsaa
    row["hs"] = jhsaa.former_names().get(row["hs"], row["hs"])
    return row


def class_years(conn, world_id: int, gender: str) -> list:
    """Every graduating year the tracker can show for a gender, newest first —
    classes already written plus those the alumni index can still fill in."""
    years = {r[0] for r in conn.execute(
        "SELECT DISTINCT grad_year FROM world_jhsaa_college WHERE world_id=? AND"
        " gender=?", (world_id, gender))}
    try:
        years |= {r[0] for r in conn.execute(
            "SELECT DISTINCT grad_year FROM jhsaa_alumni WHERE world_id=? AND gender=?"
            " AND rank > 0", (world_id, gender))}
    except Exception:
        pass
    return sorted(years, reverse=True)


def class_rows(conn, world_id: int, gender: str, grad_year: int, salt: str,
               fill: bool = True) -> list:
    """One class, in rank order. `fill` False only reads — the caller's save
    sends its seniors to a real recruit board, so nothing is written for it."""
    if fill:
        _ensure_class(conn, world_id, gender, grad_year, salt)
    return [_relabelled(json.loads(r[0])) for r in conn.execute(
        "SELECT data FROM world_jhsaa_college WHERE world_id=? AND grad_year=? AND"
        " gender=? ORDER BY rank", (world_id, grad_year, gender))]


def line_for(conn, world_id: int, pid: str, salt: str,
             fill: bool = True) -> dict | None:
    """One player's college line, or None — they have not graduated, or were not
    among the class's `CLASS_SIZE`. One indexed read."""
    def _read():
        r = conn.execute("SELECT data FROM world_jhsaa_college WHERE world_id=? AND"
                         " pid=?", (world_id, pid)).fetchone()
        return _relabelled(json.loads(r[0])) if r else None
    hit = _read()
    if hit is not None or not fill:
        return hit
    try:
        a = conn.execute("SELECT gender, grad_year FROM jhsaa_alumni WHERE world_id=?"
                         " AND pid=? AND rank > 0", (world_id, pid)).fetchone()
    except Exception:
        return None
    if not a:
        return None
    _ensure_class(conn, world_id, a[0], a[1], salt)
    return _read()


def all_rows(conn, world_id: int, salt: str, fill: bool = True) -> list:
    """Every tracked alumnus of the save, for the research export — filling in any
    class the index still holds first."""
    for gender in ("girls", "boys") if fill else ():
        for gy in class_years(conn, world_id, gender):
            _ensure_class(conn, world_id, gender, gy, salt)
    return [_relabelled(json.loads(r[0])) for r in conn.execute(
        "SELECT data FROM world_jhsaa_college WHERE world_id=?"
        " ORDER BY grad_year, gender, rank", (world_id,))]

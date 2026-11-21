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


def _insert(conn, world_id: int, rows: list) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO world_jhsaa_college (world_id, grad_year, gender, pid,"
        " rank, name, hs, college, division, data) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(world_id, r["grad_year"], r["gender"], r["pid"], r["rank"], r["name"],
          r["hs"], r["college"], r["division"], json.dumps(r)) for r in rows])


def record_class(conn, world_id: int, gender: str, grad_year: int, salt: str,
                 teams) -> int:
    """Write this season's graduating class — on the rung's connection, from the
    rosters the season was just played with. Written once: a pid already tracked is
    left exactly as it was."""
    from . import jhsaa
    seniors = [{"pid": p.pid, "name": p.name, "hs": t.school.name,
                "ovr": float(p.current_overall()),
                # The staff's ESTIMATE of the ceiling, never the hidden one — the
                # read a college coach would have had of the kid too.
                "pot": float(jhsaa.pot_display(p)),
                "domestic": ncaa.is_domestic_player(p)}
               for t in teams for p in t.roster if getattr(p, "grade", 0) == 12]
    rows = build_class(seniors, gender, grad_year, salt)
    _insert(conn, world_id, rows)
    return len(rows)


def _ensure_class(conn, world_id: int, gender: str, grad_year: int, salt: str) -> None:
    """Fill in a class that graduated before the tracker existed, from the alumni
    index. No roster is rebuilt: the index already holds every senior and the rating
    they left on. It carries no ceiling and no nationality, so growth is rolled and
    the service academies are simply out of view for these classes."""
    if conn.execute("SELECT 1 FROM world_jhsaa_college WHERE world_id=? AND grad_year=?"
                    " AND gender=? LIMIT 1", (world_id, grad_year, gender)).fetchone():
        return
    try:
        idx = conn.execute(
            "SELECT pid, name, school, ovr FROM jhsaa_alumni WHERE world_id=? AND"
            " gender=? AND grad_year=?", (world_id, gender, grad_year)).fetchall()
    except Exception:                                   # no alumni index in this save
        return
    if not idx:
        return
    seniors = [{"pid": r[0], "name": r[1], "hs": r[2], "ovr": float(r[3] or 0.0)}
               for r in idx]
    _insert(conn, world_id, build_class(seniors, gender, grad_year, salt))
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


def class_rows(conn, world_id: int, gender: str, grad_year: int, salt: str) -> list:
    """One class, in rank order."""
    _ensure_class(conn, world_id, gender, grad_year, salt)
    return [_relabelled(json.loads(r[0])) for r in conn.execute(
        "SELECT data FROM world_jhsaa_college WHERE world_id=? AND grad_year=? AND"
        " gender=? ORDER BY rank", (world_id, grad_year, gender))]


def line_for(conn, world_id: int, pid: str, salt: str) -> dict | None:
    """One player's college line, or None — they have not graduated, or were not
    among the class's `CLASS_SIZE`. One indexed read."""
    def _read():
        r = conn.execute("SELECT data FROM world_jhsaa_college WHERE world_id=? AND"
                         " pid=?", (world_id, pid)).fetchone()
        return _relabelled(json.loads(r[0])) if r else None
    hit = _read()
    if hit is not None:
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


def all_rows(conn, world_id: int, salt: str) -> list:
    """Every tracked alumnus of the save, for the research export — filling in any
    class the index still holds first."""
    for gender in ("girls", "boys"):
        for gy in class_years(conn, world_id, gender):
            _ensure_class(conn, world_id, gender, gy, salt)
    return [_relabelled(json.loads(r[0])) for r in conn.execute(
        "SELECT data FROM world_jhsaa_college WHERE world_id=?"
        " ORDER BY grad_year, gender, rank", (world_id,))]

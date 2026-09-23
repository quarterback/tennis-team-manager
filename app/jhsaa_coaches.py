"""JHSAA coaching staffs — the people behind the coaching the association already
simulated (owner spec 2026-09, `docs/AAR-jhsaa-named-coaches.md`).

Before this module every JHSAA "coach" was a random draw seeded on the SCHOOL:
`jhsaa.coach_lens` (how well the staff reads a roster), `jhsaa.doubles_culture`
(how fast partnerships gel) and `jhsaa._coach_strategy` (the pairing philosophy).
Nobody had a name, a career or an alma mater. This module gives each program a
named STAFF and makes those three mechanics read the staff instead of the school.

‼️ STAGE A IS COSMETIC. `ensure_staff` builds every program's inaugural staff so
that the staff's EFFECTIVE values reproduce today's school draws EXACTLY — the
first season with coaches plays byte-identically to the season without them. A
program's behaviour changes only when the owner moves somebody.

‼️ ONE ENTITY, READ BY BOTH THE PAGES AND THE SIM. The college game has two
coach models (`coaches.program_coach`, never stored, and `coachreg`, a different
seed) that never agree; moving a registry coach there changes nothing in the sim.
Here the page and `jhsaa.district_teams` read the same rows.

‼️ RATINGS ARE IMPRINTED ONCE (owner rule). A coach's grades are rolled when the
coach is created and never develop — an assistant arrives with full ratings, which
is realistic (experienced people coach high school for fun, and retired heads step
back to help). Only the owner's editor changes a rating.

Storage is quantiles (0-1), shown as 20-80 grades. The quantile is what feeds the
existing parameter bands, and storing it (not the rounded grade) is what keeps the
inaugural reproduction exact.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field

# --------------------------------------------------------------- the model ----

#: Graded attributes, in display order. Each is a quantile in [0, 1].
GRADES = ("talent_id", "adaptability", "development", "doubles", "builder",
          "feeder", "clutch", "changeover")

GRADE_LABELS = {
    "talent_id": "Talent ID",
    "adaptability": "Adaptability",
    "development": "Development",
    "doubles": "Doubles instinct",
    "builder": "Program builder",
    "feeder": "Feeder ties",
    "clutch": "Clutch",
    "changeover": "Changeover",
}

#: Staff-blended ("cover weak spots"); the rest belong to the head alone.
BLENDED = ("talent_id", "adaptability", "development", "doubles", "builder", "feeder")
HEAD_ONLY = ("clutch", "changeover")

#: How much of the gap to the best assistant a staff closes, per attribute.
#: `effective = head + COVER * max(0, best_assistant - head)` — never above the
#: best coach on the staff, never below the head.
COVER = 0.4

PAIRINGS = ("maximize", "balanced", "traditional")   # + "mentorship" in Stage B
TEMPERAMENTS = ("broad", "steady", "senior")
TEMPERAMENT_LABELS = {"broad": "Broad rotation", "steady": "Steady",
                      "senior": "Senior-first"}

#: Profiles — each coach draws one; it is also an assistant's SPECIALTY. The
#: listed attributes get `PROFILE_BONUS`; one other attribute gets the penalty.
PROFILES = {
    "teacher": ("development",),
    "jv_whisperer": ("adaptability", "development"),
    "tactician": ("talent_id", "clutch", "changeover"),
    "builder": ("builder", "feeder"),
    "doubles_guru": ("doubles",),
    "motivator": ("adaptability", "changeover"),
    "generalist": (),
}
PROFILE_LABELS = {
    "teacher": "Teacher", "jv_whisperer": "JV whisperer",
    "tactician": "Tactician", "builder": "Program builder",
    "doubles_guru": "Doubles guru", "motivator": "Motivator",
    "generalist": "Generalist",
}
PROFILE_WEIGHTS = {"teacher": 18, "jv_whisperer": 12, "tactician": 16,
                   "builder": 14, "doubles_guru": 14, "motivator": 12,
                   "generalist": 14}
PROFILE_BONUS = 8.0          # grade points
PROFILE_PENALTY = 5.0
GENERALIST_BONUS = 3.0
GRADE_MEAN, GRADE_SD = 50.0, 10.0
GRADE_LO, GRADE_HI = 25.0, 75.0      # the roll's clamp; the editor may go 20-80

#: Assistants by ROSTER SIZE (owner rule): a small program carries one, a big
#: one up to three. Seats are opened by growth and never closed by shrinkage
#: while someone sits in them (`sync_seats`).
ASSISTANT_BANDS = ((20, 1), (28, 2))   # roster < 20 → 1, < 28 → 2, else 3
MAX_ASSISTANTS = 3
SLOTS = ("head", "asst1", "asst2", "asst3")


def assistants_for(roster: int) -> int:
    for bound, n in ASSISTANT_BANDS:
        if roster < bound:
            return n
    return MAX_ASSISTANTS


def to_grade(q: float) -> float:
    """A stored quantile as a 20-80 grade — DISPLAY only."""
    return 20.0 + 60.0 * q


def to_q(grade: float) -> float:
    return min(1.0, max(0.0, (grade - 20.0) / 60.0))


def _rng(*parts) -> random.Random:
    """A stable stream. blake2s, never `hash()` — the rolls are persisted, but the
    inaugural staff is also RE-DERIVED on a fresh save and must come out the same
    in every process."""
    h = hashlib.blake2s("|".join(str(p) for p in parts).encode(), digest_size=8)
    return random.Random(int(h.hexdigest(), 16))


@dataclass
class Coach:
    coach_id: str
    name: str
    grades: dict                       # {attr: quantile}
    profile: str = "generalist"
    pairing: str = "balanced"
    temperament: str = "steady"
    hometown: str = ""
    birth_year: int = 0
    origin: str = "inaugural"          # inaugural / alumnus / college_grad / editor
    alma: str = ""                     # school ident the coach played for, if any
    player_pid: str = ""
    created: int = 0                   # season year the coach was created
    # ‼️ EXACT REPRODUCTION PINS, inaugural heads only (`inaugural_staff`). The
    # head's grade is SOLVED so the staff blend lands on the school's old draw, and
    # float arithmetic lands within ~1e-16 of it rather than on it — so a blended
    # value within `_PIN_TOL` of a pin is snapped to the pin. `culture_pin` is the
    # exact `doubles_culture` of a tagged program, used when doubles snaps.
    pins: dict = field(default_factory=dict)
    culture_pin: float | None = None
    retired: int = 0                   # season year retired; 0 = active

    def grade(self, attr: str) -> int:
        return round(to_grade(self.grades.get(attr, 0.5)))


def roll_grades(rng: random.Random, profile: str, mean: float = GRADE_MEAN) -> dict:
    """One coach's imprinted grades, as quantiles. Base N(mean, 10) clamped to
    25-75, then the profile's bonus and one penalty elsewhere."""
    g = {a: min(GRADE_HI, max(GRADE_LO, rng.gauss(mean, GRADE_SD))) for a in GRADES}
    strong = PROFILES.get(profile, ())
    if profile == "generalist":
        for a in GRADES:
            g[a] += GENERALIST_BONUS
    else:
        for a in strong:
            g[a] += PROFILE_BONUS
        weak = [a for a in GRADES if a not in strong]
        g[rng.choice(weak)] -= PROFILE_PENALTY
    return {a: to_q(v) for a, v in g.items()}


def roll_profile(rng: random.Random) -> str:
    names = list(PROFILE_WEIGHTS)
    return rng.choices(names, weights=[PROFILE_WEIGHTS[n] for n in names])[0]


def roll_name(rng: random.Random, team_gender: str) -> str:
    from generators import draw_us_weighted
    male_share = 0.70 if team_gender == "boys" else 0.45
    sex = "male" if rng.random() < male_share else "female"
    nm, _ = draw_us_weighted(random.Random(rng.randrange(1 << 30)), sex)
    return nm


# ---------------------------------------------------------- the mechanics ----

def culture_of(q: float) -> float:
    """Doubles instinct → the `doubles_culture` multiplier. Grade 50 (q 0.5) is
    exactly 1.0, the untagged value; the top of the scale reaches the tagged band's
    3.0 and the bottom slows partnerships to 0.75."""
    if q < 0.5:
        return 0.75 + 0.5 * q
    return 1.0 + 4.0 * (q - 0.5)


def q_of_culture(c: float) -> float:
    if c >= 1.0:
        return min(1.0, 0.5 + (c - 1.0) / 4.0)
    return max(0.0, (c - 0.75) / 0.5)


_PIN_TOL = 1e-9


def effective(head: Coach | None, assistants: list[Coach]) -> dict:
    """The staff's effective quantile per attribute — "cover weak spots"."""
    out = {}
    pins = head.pins if head else {}
    for a in GRADES:
        h = head.grades.get(a, 0.5) if head else 0.5
        if a in BLENDED and assistants:
            b = max(x.grades.get(a, 0.5) for x in assistants)
            if b > h:
                h = h + COVER * (b - h)
        p = pins.get(a)
        if p is not None and abs(h - p) < _PIN_TOL:
            h = p
        out[a] = h
    return out


def solve_head(target: float, assistants: list[Coach], attr: str) -> float:
    """The head grade whose staff blend lands on `target`. When the best
    assistant is above the target the head sits below it:
    `h = (T − C·b) / (1 − C)`. Infeasible only when `b > T / C` (the head would
    need a negative grade) — the caller caps that assistant first."""
    b = max((x.grades.get(attr, 0.5) for x in assistants), default=0.0)
    if b <= target:
        return target
    return (target - COVER * b) / (1.0 - COVER)


@dataclass(frozen=True)
class StaffEffect:
    """What `jhsaa.district_teams` reads for one program — the three mechanics
    Stage A routes through the staff. Plain values so `jhsaa` needs no import of
    this module."""
    lens: object            # jhsaa.CoachLens
    culture: float
    strategy: str

    def fingerprint(self) -> tuple:
        return (round(self.lens.read, 12), round(self.lens.trust, 12),
                round(self.lens.form, 12), round(self.culture, 12), self.strategy)


def lens_of(talent_id: float, adaptability: float):
    """Talent ID and Adaptability → the coach lens.

    `jhsaa.coach_lens` drives all three weights off ONE draw `q`. Talent ID takes
    that role (misread size, and the overall lean on proof and form); Adaptability
    TILTS the lean — an adaptable coach trusts incumbents less and acts on results
    more, a stubborn one the reverse. At adaptability 0.5 the tilt is exactly zero,
    which is how an inaugural staff reproduces `coach_lens(q)` to the bit."""
    from . import jhsaa
    base = 1.0 - talent_id
    tilt = 0.5 - adaptability

    def lerp(band, t):
        t = min(1.0, max(0.0, t))
        return band[0] + (band[1] - band[0]) * t
    if tilt == 0.0:
        return jhsaa.CoachLens(read=lerp(jhsaa.COACH_READ, base),
                               trust=lerp(jhsaa.COACH_TRUST, base),
                               form=lerp(jhsaa.COACH_FORM, base))
    return jhsaa.CoachLens(read=lerp(jhsaa.COACH_READ, base),
                           trust=lerp(jhsaa.COACH_TRUST, base + tilt),
                           form=lerp(jhsaa.COACH_FORM, base - tilt))


def staff_effect(head: Coach | None, assistants: list[Coach]) -> StaffEffect | None:
    if head is None:
        return None
    eff = effective(head, assistants)
    culture = (head.culture_pin
               if head.culture_pin is not None and eff["doubles"] == head.pins.get("doubles")
               else culture_of(eff["doubles"]))
    return StaffEffect(lens=lens_of(eff["talent_id"], eff["adaptability"]),
                       culture=culture, strategy=head.pairing)


def effect_fingerprint(staff: dict | None) -> str:
    """A small digest of a gender's staff map, for `run_season`'s memo key — a
    season played under a different staff is a different season."""
    if not staff:
        return ""
    h = hashlib.blake2s(digest_size=10)
    for k in sorted(staff):
        h.update(repr((k, staff[k].fingerprint())).encode())
    return h.hexdigest()


# ----------------------------------------------------- the inaugural staff ----

def _cid(world_id, *parts) -> str:
    h = hashlib.blake2s("|".join(str(p) for p in parts).encode(), digest_size=6)
    return f"jc{world_id}-{h.hexdigest()}"


def inaugural_staff(school, n_assistants: int, salt: str, season_year: int,
                    world_id: int = 0, hometowns: list | None = None) -> list[Coach]:
    """A program's first staff: `[head, asst1, …]`, built so its EFFECTIVE values
    reproduce the school draws the association already played on.

    - Talent ID IS the school's `coach_lens` draw `q`; Adaptability is exactly 0.5
      (no tilt). So `lens_of` returns `coach_lens(school.name, salt)` exactly.
    - Doubles instinct reproduces `doubles_culture` (1.0 untagged → q 0.5 exactly).
    - The head's pairing philosophy is `_coach_strategy(school.key)`.
    - The assistants keep their FULL grades; the head's three reproduced grades
      are SOLVED against them (`solve_head`) and pinned, so the staff blend lands
      exactly on the old draw. A strong assistant therefore sits beside a head a
      little below the program's old read, which is the blend working as designed.
      Only when the solve is infeasible (a very low draw beside a very strong
      assistant) is that assistant's grade capped at `target / COVER`.
    """
    from . import jhsaa
    q = random.Random(f"{salt}|jhsaa-coach-lens|{school.name}").random()
    culture = jhsaa.doubles_culture(school.name, salt)
    towns = hometowns or [school.city]
    staff = []
    for i in range(1 + n_assistants):
        slot = SLOTS[i]
        rng = _rng("jhsaa-coach", salt, school.ident, school.gender, slot)
        profile = roll_profile(rng)
        grades = roll_grades(rng, profile)
        age = int(rng.triangular(32, 64, 47) if i == 0 else rng.triangular(23, 68, 40))
        hometown = school.city if rng.random() < 0.55 else rng.choice(towns)
        c = Coach(coach_id=_cid(world_id, salt, school.ident, school.gender, slot),
                  name=roll_name(rng, school.gender), grades=grades,
                  profile=profile,
                  pairing=rng.choice(PAIRINGS),
                  temperament="steady",
                  hometown=hometown, birth_year=season_year - age,
                  origin="inaugural", created=season_year)
        staff.append(c)
    head, ast = staff[0], staff[1:]
    targets = {"talent_id": q, "adaptability": 0.5,
               "doubles": 0.5 if culture == 1.0 else q_of_culture(culture)}
    for attr, t in targets.items():
        for a in ast:
            a.grades[attr] = min(a.grades[attr], t / COVER)
        head.grades[attr] = solve_head(t, ast, attr)
        head.pins[attr] = t
    if culture != 1.0:
        head.culture_pin = culture
    head.pairing = jhsaa._coach_strategy(school.key)
    return staff


# ------------------------------------------------------------ persistence ----

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jhsaa_coach (
  world_id INTEGER, coach_id TEXT, name TEXT, data TEXT,
  PRIMARY KEY (world_id, coach_id)
);
CREATE TABLE IF NOT EXISTS jhsaa_coach_seat (
  world_id INTEGER, ident TEXT, gender TEXT, slot TEXT, coach_id TEXT,
  since INTEGER, jv_head INTEGER DEFAULT 0,
  PRIMARY KEY (world_id, ident, gender, slot)
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_coach_seat_coach ON jhsaa_coach_seat(world_id, coach_id);
CREATE TABLE IF NOT EXISTS jhsaa_coach_history (
  world_id INTEGER, year INTEGER, ident TEXT, gender TEXT, slot TEXT,
  coach_id TEXT, school TEXT, classification TEXT, grp TEXT,
  wins INTEGER, losses INTEGER, ties INTEGER, eff TEXT
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_coach_hist ON jhsaa_coach_history(world_id, year, gender);
CREATE INDEX IF NOT EXISTS ix_jhsaa_coach_hist_coach ON jhsaa_coach_history(world_id, coach_id);
CREATE TABLE IF NOT EXISTS jhsaa_coach_event (
  world_id INTEGER, year INTEGER, coach_id TEXT, ident TEXT, gender TEXT,
  slot TEXT, event TEXT, note TEXT
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_coach_event ON jhsaa_coach_event(world_id, coach_id);
-- THE ALUMNI INDEX: every JHSAA senior at graduation, written when the season is
-- archived. JHSAA players are otherwise regenerated from seed and never stored, so
-- without this there is no list of former players to hire from.
CREATE TABLE IF NOT EXISTS jhsaa_alumni (
  world_id INTEGER, pid TEXT, gender TEXT, ident TEXT, school TEXT, grad_year INTEGER,
  name TEXT, style TEXT, trait TEXT, ovr REAL, rank INTEGER, honored INTEGER,
  PRIMARY KEY (world_id, pid)
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_alumni_school ON jhsaa_alumni(world_id, ident, gender);
"""

_TABLES = ("jhsaa_coach", "jhsaa_coach_seat", "jhsaa_coach_history", "jhsaa_coach_event",
           "jhsaa_alumni")


def _conn():
    """A world connection. ‼️ No `executescript(_SCHEMA)` here: `world._db()`
    ensures it once per process, and a CREATE on every open takes the write lock
    — "database is locked" whenever the season rung holds its transaction (the
    `worldconfig` lesson in CLAUDE.md)."""
    from . import world
    return world._db()


def reset() -> None:
    conn = _conn()
    conn.executescript("".join(f"DELETE FROM {t};" for t in _TABLES))
    conn.commit()
    conn.close()


def _coach_row(c: Coach) -> str:
    return json.dumps({k: getattr(c, k) for k in (
        "grades", "profile", "pairing", "temperament", "hometown", "birth_year",
        "origin", "alma", "player_pid", "created", "pins", "culture_pin", "retired")})


def _coach_from(coach_id: str, name: str, data: str) -> Coach:
    d = json.loads(data)
    return Coach(coach_id=coach_id, name=name, **d)


def save_coach(conn, world_id: int, c: Coach) -> None:
    conn.execute("INSERT OR REPLACE INTO jhsaa_coach (world_id, coach_id, name, data)"
                 " VALUES (?,?,?,?)", (world_id, c.coach_id, c.name, _coach_row(c)))


def _event(conn, world_id, year, coach_id, ident, gender, slot, event, note=""):
    conn.execute("INSERT INTO jhsaa_coach_event (world_id, year, coach_id, ident,"
                 " gender, slot, event, note) VALUES (?,?,?,?,?,?,?,?)",
                 (world_id, year, coach_id, ident, gender, slot, event, note))


def ensure_staff(world_id: int, season_year: int, salt: str) -> int:
    """Seat an inaugural staff for every sponsoring program that has no head
    seat yet. Idempotent — a program seated once is never re-rolled, and a
    program that starts sponsoring later is seated the first season it plays.
    Returns how many programs were seated."""
    from . import jhsaa
    conn = _conn()
    try:
        have = {(r[0], r[1]) for r in conn.execute(
            "SELECT ident, gender FROM jhsaa_coach_seat"
            " WHERE world_id=? AND slot='head'", (world_id,))}
        n = 0
        for gender in ("girls", "boys"):
            schools = jhsaa.load_schools(gender)
            towns = sorted({s.city for s in schools})
            for s in schools:
                if (s.ident, gender) in have:
                    continue
                n_ast = assistants_for(jhsaa.roster_size(s.classification, s.key, salt))
                staff = inaugural_staff(s, n_ast, salt, season_year, world_id, towns)
                for i, c in enumerate(staff):
                    save_coach(conn, world_id, c)
                    conn.execute(
                        "INSERT OR REPLACE INTO jhsaa_coach_seat (world_id, ident, gender,"
                        " slot, coach_id, since, jv_head) VALUES (?,?,?,?,?,?,?)",
                        (world_id, s.ident, gender, SLOTS[i], c.coach_id, season_year,
                         int(i == 1)))
                    _event(conn, world_id, season_year, c.coach_id, s.ident, gender,
                           SLOTS[i], "existing", "on staff when coaches were introduced")
                n += 1
        conn.commit()
        return n
    finally:
        conn.close()


def _load_coaches(conn, world_id: int, ids) -> dict:
    ids = [i for i in set(ids) if i]
    out = {}
    for k in range(0, len(ids), 500):
        chunk = ids[k:k + 500]
        q = ",".join("?" * len(chunk))
        for r in conn.execute(f"SELECT coach_id, name, data FROM jhsaa_coach"
                              f" WHERE world_id=? AND coach_id IN ({q})",
                              (world_id, *chunk)):
            out[r[0]] = _coach_from(r[0], r[1], r[2])
    return out


def seats(world_id: int, gender: str | None = None, ident: str | None = None) -> list:
    """Seat rows `[{ident, gender, slot, coach, since, jv_head}]`, coaches resolved
    in ONE extra query."""
    conn = _conn()
    try:
        sql = ("SELECT ident, gender, slot, coach_id, since, jv_head FROM jhsaa_coach_seat"
               " WHERE world_id=?")
        args = [world_id]
        if gender:
            sql += " AND gender=?"
            args.append(gender)
        if ident:
            sql += " AND ident=?"
            args.append(ident)
        rows = conn.execute(sql, args).fetchall()
        coaches = _load_coaches(conn, world_id, [r[3] for r in rows])
    finally:
        conn.close()
    return [{"ident": r[0], "gender": r[1], "slot": r[2], "coach": coaches.get(r[3]),
             "since": r[4], "jv_head": bool(r[5])} for r in rows]


def _staffs(rows) -> dict:
    """`{(ident, gender): (head, [assistants])}` from seat rows."""
    out: dict = {}
    for r in sorted(rows, key=lambda r: SLOTS.index(r["slot"])):
        key = (r["ident"], r["gender"])
        head, ast = out.get(key, (None, []))
        if r["coach"] is None:
            out[key] = (head, ast)
        elif r["slot"] == "head":
            out[key] = (r["coach"], ast)
        else:
            out[key] = (head, ast + [r["coach"]])
    return out


def current_effects(world_id: int, gender: str) -> dict:
    """`{school.key: StaffEffect}` for one gender from the CURRENT seats — one
    read for the whole association."""
    out = {}
    for (ident, g), (head, ast) in _staffs(seats(world_id, gender)).items():
        eff = staff_effect(head, ast)
        if eff is not None:
            out[f"{ident}|{g}"] = eff
    return out


def _eff_to_json(e: StaffEffect) -> str:
    return json.dumps({"read": e.lens.read, "trust": e.lens.trust, "form": e.lens.form,
                       "culture": e.culture, "strategy": e.strategy})


def _eff_from_json(s: str) -> StaffEffect:
    from . import jhsaa
    d = json.loads(s)
    return StaffEffect(lens=jhsaa.CoachLens(read=d["read"], trust=d["trust"],
                                            form=d["form"]),
                       culture=d["culture"], strategy=d["strategy"])


def season_effects(world_id: int, year: int, gender: str) -> dict:
    """The staff effects a season was PLAYED with: the archived history when that
    season is archived (so the recruit hand-off replays the archived season even
    if the owner has since moved a coach), else the current seats."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT ident, eff FROM jhsaa_coach_history"
            " WHERE world_id=? AND year=? AND gender=? AND slot='head' AND eff IS NOT NULL",
            (world_id, year, gender)).fetchall()
    finally:
        conn.close()
    if rows:
        return {f"{r[0]}|{gender}": _eff_from_json(r[1]) for r in rows}
    return current_effects(world_id, gender)


def record_season(conn, world_id: int, year: int, gender: str, teams, effects: dict,
                  season_year: int) -> None:
    """Archive who coached each program this season, with the effects the season
    was played under, and open any seat a grown roster now warrants.

    Written on the rung's own connection, inside its transaction, beside
    `world_jhsaa_standing`. ‼️ Never `executescript` here — it COMMITS the rung's
    open transaction; the schema is already ensured by `world.init_schema`."""
    seat_rows = conn.execute(
        "SELECT ident, slot, coach_id FROM jhsaa_coach_seat WHERE world_id=? AND gender=?",
        (world_id, gender)).fetchall()
    by_ident: dict = {}
    for ident, slot, cid in seat_rows:
        by_ident.setdefault(ident, {})[slot] = cid
    hist = []
    for t in teams:
        s = t.school
        slots = by_ident.get(s.ident, {})
        eff = effects.get(s.key)
        for slot, cid in sorted(slots.items(), key=lambda kv: SLOTS.index(kv[0])):
            if not cid:
                continue
            hist.append((world_id, year, s.ident, gender, slot, cid, s.name,
                         s.classification, s.group, t.wins, t.losses, t.ties,
                         _eff_to_json(eff) if (slot == "head" and eff) else None))
        # SEATS FOLLOW THE ROSTER, WITH HYSTERESIS: growth opens a vacant seat;
        # shrinkage never removes anybody.
        want = assistants_for(len(t.roster))
        for i in range(1, want + 1):
            if SLOTS[i] not in slots:
                conn.execute(
                    "INSERT OR IGNORE INTO jhsaa_coach_seat (world_id, ident, gender,"
                    " slot, coach_id, since, jv_head) VALUES (?,?,?,?,?,?,0)",
                    (world_id, s.ident, gender, SLOTS[i], None, season_year))
    conn.executemany(
        "INSERT INTO jhsaa_coach_history (world_id, year, ident, gender, slot, coach_id,"
        " school, classification, grp, wins, losses, ties, eff)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", hist)


# ------------------------------------------------------------ read models ----

def get_coach(world_id: int, coach_id: str) -> Coach | None:
    conn = _conn()
    try:
        return _load_coaches(conn, world_id, [coach_id]).get(coach_id)
    finally:
        conn.close()


def coach_career(world_id: int, coach_id: str) -> dict:
    """Seat history, events, and the current seat, for the coach page."""
    conn = _conn()
    try:
        hist = [dict(zip(("year", "ident", "gender", "slot", "school", "classification",
                          "grp", "wins", "losses", "ties"), r))
                for r in conn.execute(
                    "SELECT year, ident, gender, slot, school, classification, grp,"
                    " wins, losses, ties FROM jhsaa_coach_history"
                    " WHERE world_id=? AND coach_id=? ORDER BY year", (world_id, coach_id))]
        events = [dict(zip(("year", "ident", "gender", "slot", "event", "note"), r))
                  for r in conn.execute(
                      "SELECT year, ident, gender, slot, event, note FROM jhsaa_coach_event"
                      " WHERE world_id=? AND coach_id=? ORDER BY rowid", (world_id, coach_id))]
        seat = conn.execute(
            "SELECT ident, gender, slot, since, jv_head FROM jhsaa_coach_seat"
            " WHERE world_id=? AND coach_id=?", (world_id, coach_id)).fetchone()
    finally:
        conn.close()
    w = sum(h["wins"] or 0 for h in hist if h["slot"] == "head")
    l = sum(h["losses"] or 0 for h in hist if h["slot"] == "head")
    return {"history": hist, "events": events,
            "seat": dict(zip(("ident", "gender", "slot", "since", "jv_head"), seat))
            if seat else None,
            "head_record": f"{w}-{l}"}


def slot_label(slot: str, jv_head: bool) -> str:
    if slot == "head":
        return "Head coach"
    return "JV head coach" if jv_head else "Assistant coach"


def program_staff(world_id: int, ident: str, gender: str) -> dict | None:
    """The program page's staff block: every seat (vacant ones included), and the
    EFFECTIVE value per attribute with who covers it."""
    rows = seats(world_id, gender, ident)
    if not rows:
        return None
    rows.sort(key=lambda r: SLOTS.index(r["slot"]))
    head = next((r["coach"] for r in rows if r["slot"] == "head"), None)
    ast = [r["coach"] for r in rows if r["slot"] != "head" and r["coach"]]
    eff = effective(head, ast)
    cover = {}
    for a in GRADES:
        if a in BLENDED and ast and head:
            best = max(ast, key=lambda x: x.grades.get(a, 0.5))
            if best.grades.get(a, 0.5) > head.grades.get(a, 0.5):
                cover[a] = best
    return {
        "seats": [{**r, "label": slot_label(r["slot"], r["jv_head"])} for r in rows],
        "head": head,
        "effective": [{"attr": a, "label": GRADE_LABELS[a],
                       "grade": round(to_grade(eff[a])),
                       "via": cover.get(a)} for a in GRADES],
    }


def ident_names(gender: str) -> dict:
    """`{ident: display name}` — seats key on the roster identity, pages show the
    name. Former programs included, so a coach's old seat still resolves."""
    from . import jhsaa
    out = {}
    for r in jhsaa._rows():
        if r.get("name"):
            out[r.get("source") or r["name"]] = r["name"]
    for s in jhsaa.load_schools(gender):
        out[s.ident] = s.name
    return out


def coach_view(world_id: int, coach_id: str, season_year: int) -> dict | None:
    """The coach page's read model. Grades are shown (unlike a player's
    attributes, owner rule) on the 20-80 scale."""
    c = get_coach(world_id, coach_id)
    if c is None:
        return None
    car = coach_career(world_id, coach_id)
    seat = car["seat"]
    gender = (seat or {}).get("gender") or next(
        (h["gender"] for h in car["history"]), None) or next(
        (e["gender"] for e in car["events"]), "girls")
    names = ident_names(gender)
    history = [{**h, "school": names.get(h["ident"], h["school"]),
                "role": slot_label(h["slot"], False) if h["slot"] == "head" else "Staff"}
               for h in car["history"]]
    events = [{**e, "school": names.get(e["ident"], e["ident"])} for e in car["events"]]
    return {
        "coach": c,
        "grades": [{"attr": a, "label": GRADE_LABELS[a], "grade": c.grade(a),
                    "blended": a in BLENDED} for a in GRADES],
        "profile": PROFILE_LABELS.get(c.profile, c.profile),
        "pairing": c.pairing.title(),
        "temperament": TEMPERAMENT_LABELS.get(c.temperament, c.temperament),
        "age": season_year - c.birth_year if c.birth_year else None,
        "origin": {"inaugural": "On staff when coaches were introduced",
                   "alumnus": "Former JHSAA player", "college_grad": "Former college player",
                   "editor": "Appointed by the association"}.get(c.origin, c.origin),
        "alma": names.get(c.alma, c.alma) if c.alma else "",
        "gender": gender,
        "seat": ({**seat, "school": names.get(seat["ident"], seat["ident"]),
                  "label": slot_label(seat["slot"], seat["jv_head"])} if seat else None),
        "history": history,
        "events": events,
        "head_record": car["head_record"],
    }


# ------------------------------------------------------------ former players ----

def record_alumni(conn, world_id: int, gender: str, teams, season_year: int,
                  honored: set) -> None:
    """Index this season's seniors as alumni — on the rung's connection."""
    rows = []
    for t in teams:
        for rank, p in enumerate(t.roster, 1):
            if getattr(p, "grade", 0) != 12:
                continue
            tr = getattr(p, "traits", {}) or {}
            rows.append((world_id, p.pid, gender, t.school.ident, t.school.name,
                         season_year, p.name, tr.get("play_style", ""),
                         tr.get("style_trait", ""), float(p.current_overall()), rank,
                         int(p.pid in honored)))
    conn.executemany(
        "INSERT OR IGNORE INTO jhsaa_alumni (world_id, pid, gender, ident, school,"
        " grad_year, name, style, trait, ovr, rank, honored)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def alumnus(world_id: int, pid: str) -> dict | None:
    conn = _conn()
    try:
        r = conn.execute(
            "SELECT pid, gender, ident, school, grad_year, name, style, trait, ovr, rank,"
            " honored FROM jhsaa_alumni WHERE world_id=? AND pid=?",
            (world_id, pid)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return dict(zip(("pid", "gender", "ident", "school", "grad_year", "name", "style",
                     "trait", "ovr", "rank", "honored"), r))


def college_graduate(world_id: int, pid: str) -> dict | None:
    """A college graduate of this world (`world_graduates`) as a hire candidate."""
    conn = _conn()
    try:
        r = conn.execute("SELECT year, data FROM world_graduates WHERE world_id=? AND pid=?"
                         " ORDER BY year DESC LIMIT 1", (world_id, pid)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    d = json.loads(r[1])
    tr = d.get("traits") or {}
    return {"pid": pid, "name": d.get("name", pid), "style": tr.get("play_style", ""),
            "trait": tr.get("style_trait", ""), "ident": "", "school": "",
            "hometown": d.get("hometown", "")}


#: Playing style → the coaching grade it tilts (+3) and the philosophy it leans to.
#: Coaching ABILITY is never read off playing ability (owner rule): the tilt is
#: what the player TEACHES, not how good a coach they are.
_STYLE_TILT = {
    "serve_and_volley": ("doubles", "balanced"), "net_rusher": ("doubles", "balanced"),
    "chip_and_charge": ("doubles", "balanced"), "all_court": ("doubles", "balanced"),
    "grinder": ("development", None), "retriever": ("development", None),
    "counterpuncher": ("development", None), "pusher": ("development", None),
    "first_strike": ("clutch", "maximize"), "big_server": ("clutch", "maximize"),
    "serve_first": ("clutch", "maximize"), "aggressive_baseliner": ("clutch", "maximize"),
    "junkballer": ("changeover", "traditional"),
    "slice_specialist": ("changeover", "traditional"),
}
STYLE_TILT = 3.0 / 60.0


def coach_from_player(world_id: int, cand: dict, team_gender: str, season_year: int,
                      origin: str) -> Coach:
    """A former player's coaching identity. Grades are rolled INDEPENDENTLY of how
    good a player they were, seeded on the pid (so the same person is the same
    coach in any save built from the same world); their style tilts one grade and
    their pairing philosophy."""
    rng = _rng("jhsaa-coach-from-player", world_id, cand["pid"])
    profile = roll_profile(rng)
    grades = roll_grades(rng, profile)
    pairing = rng.choice(PAIRINGS)
    temperament = rng.choice(TEMPERAMENTS)
    for key in (cand.get("trait"), cand.get("style")):
        tilt = _STYLE_TILT.get(key or "")
        if tilt:
            attr, lean = tilt
            grades[attr] = min(1.0, grades[attr] + STYLE_TILT)
            if lean:
                pairing = lean
            if attr == "development":
                temperament = "broad"
            break
    grad = cand.get("grad_year") or season_year - 4
    age = max(22, season_year - grad + 18)
    return Coach(coach_id=_cid(world_id, "player", cand["pid"]), name=cand["name"],
                 grades=grades, profile=profile, pairing=pairing,
                 temperament=temperament,
                 hometown=cand.get("hometown") or "",
                 birth_year=season_year - age, origin=origin,
                 alma=cand.get("ident", ""), player_pid=cand["pid"], created=season_year)


class StaffError(ValueError):
    """A staff action the rules refuse — the message is shown to the owner."""


def _seat_rows(conn, world_id, ident, gender):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT slot, coach_id FROM jhsaa_coach_seat WHERE world_id=? AND ident=? AND gender=?",
        (world_id, ident, gender))}


def _place(conn, world_id: int, coach_id: str, ident: str, gender: str, slot: str,
           year: int, event: str) -> str | None:
    """Seat `coach_id`; the incumbent (if any) goes to the free pool, history
    intact. Returns the displaced coach's id. ‼️ A coach holds ONE seat: any seat
    they held before is vacated first."""
    if slot not in SLOTS:
        raise StaffError(f"Unknown seat {slot!r}.")
    have = _seat_rows(conn, world_id, ident, gender)
    if slot not in have:
        # A new assistant seat — only up to the cap, and only the next one.
        n_ast = sum(1 for s in have if s != "head")
        if slot == "head" or SLOTS.index(slot) != n_ast + 1 or n_ast >= MAX_ASSISTANTS:
            raise StaffError("That program has no such seat (a staff is a head coach"
                             f" plus at most {MAX_ASSISTANTS} assistants).")
    old = conn.execute("SELECT ident, gender, slot FROM jhsaa_coach_seat"
                       " WHERE world_id=? AND coach_id=?", (world_id, coach_id)).fetchone()
    if old:
        conn.execute("UPDATE jhsaa_coach_seat SET coach_id=NULL, since=?"
                     " WHERE world_id=? AND ident=? AND gender=? AND slot=?",
                     (year, world_id, old[0], old[1], old[2]))
        _event(conn, world_id, year, coach_id, old[0], old[1], old[2], "left")
    displaced = have.get(slot)
    if displaced and displaced != coach_id:
        _event(conn, world_id, year, displaced, ident, gender, slot, "replaced",
               "moved to the free pool")
    c = _load_coaches(conn, world_id, [coach_id]).get(coach_id)
    if c is not None and c.retired:
        c.retired = 0                      # coming out of retirement to take the seat
        save_coach(conn, world_id, c)
    jv = conn.execute("SELECT jv_head FROM jhsaa_coach_seat WHERE world_id=? AND ident=?"
                      " AND gender=? AND slot=?", (world_id, ident, gender, slot)).fetchone()
    conn.execute("INSERT OR REPLACE INTO jhsaa_coach_seat (world_id, ident, gender, slot,"
                 " coach_id, since, jv_head) VALUES (?,?,?,?,?,?,?)",
                 (world_id, ident, gender, slot, coach_id, year,
                  jv[0] if jv else int(slot == "asst1")))
    _event(conn, world_id, year, coach_id, ident, gender, slot, event)
    return displaced if displaced != coach_id else None


def appoint_former_player(world_id: int, pid: str, ident: str, gender: str, slot: str,
                          season_year: int) -> Coach:
    """Hire a graduated player (JHSAA alumnus or college graduate) into a seat."""
    cand = alumnus(world_id, pid)
    origin = "alumnus"
    if cand is None:
        cand = college_graduate(world_id, pid)
        origin = "college_grad"
    if cand is None:
        raise StaffError("Only a graduated player can be hired as a coach.")
    conn = _conn()
    try:
        existing = _load_coaches(conn, world_id, [_cid(world_id, "player", pid)])
        c = existing.get(_cid(world_id, "player", pid)) or coach_from_player(
            world_id, cand, gender, season_year, origin)
        save_coach(conn, world_id, c)
        _place(conn, world_id, c.coach_id, ident, gender, slot, season_year, "hired")
        conn.commit()
        return c
    finally:
        conn.close()


def move_coach(world_id: int, coach_id: str, ident: str, gender: str, slot: str,
               season_year: int) -> None:
    conn = _conn()
    try:
        if not _load_coaches(conn, world_id, [coach_id]):
            raise StaffError("No such coach.")
        _place(conn, world_id, coach_id, ident, gender, slot, season_year, "moved")
        conn.commit()
    finally:
        conn.close()


def retire_coach(world_id: int, coach_id: str, season_year: int) -> None:
    conn = _conn()
    try:
        old = conn.execute("SELECT ident, gender, slot FROM jhsaa_coach_seat"
                           " WHERE world_id=? AND coach_id=?", (world_id, coach_id)).fetchone()
        if old:
            conn.execute("UPDATE jhsaa_coach_seat SET coach_id=NULL, since=?"
                         " WHERE world_id=? AND ident=? AND gender=? AND slot=?",
                         (season_year, world_id, old[0], old[1], old[2]))
        c = _load_coaches(conn, world_id, [coach_id]).get(coach_id)
        if c is None:
            raise StaffError("No such coach.")
        c.retired = season_year
        save_coach(conn, world_id, c)
        _event(conn, world_id, season_year, coach_id, old[0] if old else "",
               old[1] if old else "", old[2] if old else "", "retired")
        conn.commit()
    finally:
        conn.close()


def set_jv_head(world_id: int, ident: str, gender: str, slot: str) -> None:
    """The JV-head label — a designation only; every coach's grades apply to the
    whole team."""
    if slot == "head":
        raise StaffError("The head coach cannot also be the JV head.")
    conn = _conn()
    try:
        conn.execute("UPDATE jhsaa_coach_seat SET jv_head=(slot=?)"
                     " WHERE world_id=? AND ident=? AND gender=? AND slot!='head'",
                     (slot, world_id, ident, gender))
        conn.commit()
    finally:
        conn.close()


def set_grade(world_id: int, coach_id: str, attr: str, grade: float) -> None:
    """The owner's god-mode edit — the ONLY thing that ever changes a rating."""
    if attr not in GRADES:
        raise StaffError(f"Unknown rating {attr!r}.")
    conn = _conn()
    try:
        c = _load_coaches(conn, world_id, [coach_id]).get(coach_id)
        if c is None:
            raise StaffError("No such coach.")
        c.grades[attr] = to_q(max(20.0, min(80.0, float(grade))))
        c.pins.pop(attr, None)
        if attr == "doubles":
            c.culture_pin = None
        save_coach(conn, world_id, c)
        conn.commit()
    finally:
        conn.close()


def free_pool(world_id: int) -> list:
    """Coaches with no seat — displaced or stepped away, careers intact."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT c.coach_id, c.name, c.data FROM jhsaa_coach c"
            " WHERE c.world_id=? AND NOT EXISTS (SELECT 1 FROM jhsaa_coach_seat s"
            "  WHERE s.world_id=c.world_id AND s.coach_id=c.coach_id)"
            " ORDER BY c.name", (world_id,)).fetchall()
    finally:
        conn.close()
    return [c for c in (_coach_from(r[0], r[1], r[2]) for r in rows) if not c.retired]


def resolve_slot(world_id: int, ident: str, gender: str, slot: str) -> str:
    """`asst` means "the next assistant seat": the first vacant one, else a new
    one if the staff is under the cap. Explicit slots pass through."""
    if slot != "asst":
        return slot
    conn = _conn()
    try:
        have = _seat_rows(conn, world_id, ident, gender)
    finally:
        conn.close()
    for s in SLOTS[1:]:
        if s in have and not have[s]:
            return s
    n = sum(1 for s in have if s != "head")
    if n >= MAX_ASSISTANTS:
        raise StaffError("That staff is full — pick an assistant to replace.")
    return SLOTS[n + 1]

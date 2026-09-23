"""JHSAA coaching staffs — the people behind the coaching the association already
simulated (owner spec 2026-09, `docs/AAR-jhsaa-named-coaches.md`).

Before this module every JHSAA "coach" was a random draw seeded on the SCHOOL:
`jhsaa.coach_lens` (how well the staff reads a roster), `jhsaa.doubles_culture`
(how fast partnerships gel) and `jhsaa._coach_strategy` (the pairing philosophy).
Nobody had a name, a career or an alma mater. This module gives each program a
named STAFF and makes those three mechanics read the staff instead of the school.

‼️ EVERY COACH ROLLS AT RANDOM, INAUGURAL STAFFS INCLUDED (owner rule 2026-09).
An earlier build solved the first head's grades so the staff reproduced the old
school draws exactly; it was withdrawn because it left every inaugural head at
Adaptability 50 and Doubles instinct 50 — visibly not a random roll. The staff
REPLACES the old hidden draws. Nothing needs the owner after an update:
`ensure_staff` seats every program the first time the season rung runs.

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

PAIRINGS = ("maximize", "balanced", "traditional", "mentorship")
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


def effective(head: Coach | None, assistants: list[Coach]) -> dict:
    """The staff's effective quantile per attribute — "cover weak spots"."""
    out = {}
    for a in GRADES:
        h = head.grades.get(a, 0.5) if head else 0.5
        if a in BLENDED and assistants:
            b = max(x.grades.get(a, 0.5) for x in assistants)
            if b > h:
                h = h + COVER * (b - h)
        out[a] = h
    return out


# --- STAGE B dials (owner spec 2026-09). Each is the ONLY knob for its effect;
# set one to 0 and that effect is gone. Every one is centred on grade 50, so an
# average staff changes nothing and the association's average is unchanged. ----
DEV_K = 0.40           # development: grade 20 → ×0.80 yearly capacity, 80 → ×1.20
LEAN_K = 0.20          # JV/floor-raiser lean: tilt of that multiplier toward depth
CLUTCH_MISS = 0.35     # chance a grade-20 head settles for the 2nd-best postseason lineup
CHANGEOVER_K = 0.8     # engine.fast set-break roll scale (≈±1-2 pts best vs worst coach)
FEEDER_K = 0.04        # ± freshman head start (share of peak) at the top/bottom
RETENTION_MAX = 2      # ± players a class at the culture extremes
MENTOR_K = 0.08        # mentorship: up to +8% of a year's growth for a mentored
                       # freshman/sophomore, scaled by how much they played
CULTURE_KEEP = 0.8     # culture carried year to year (the rest moves to the staff)
TEMPERAMENT_ROTATE = {"broad": 1.5, "steady": 1.0, "senior": 0.5}
TEMPERAMENT_REST = {"broad": 1.2, "steady": 1.0, "senior": 0.8}


@dataclass(frozen=True)
class StaffEffect:
    """What the season reads for one program. Stage A routes the lens, doubles
    culture and pairing through the staff; Stage B adds the rest. Plain values so
    `jhsaa` needs no import of this module. Every Stage B field defaults to the
    neutral value, which is also how a history row written before Stage B reads."""
    lens: object            # jhsaa.CoachLens
    culture: float
    strategy: str
    dev: float = 1.0        # yearly-capacity multiplier (staff Development)
    lean: float = 0.0       # −1 top-leaning … +1 depth-leaning (JV/floor-raiser)
    clutch: float | None = None       # head's Clutch quantile; None = no effect
    changeover: float | None = None   # head's Changeover quantile; None = no effect
    temperament: str = "steady"
    builder: float = 0.5    # staff Program builder quantile (feeds culture)
    feeder: float = 0.5     # staff Feeder ties quantile (freshman head start)

    def fingerprint(self) -> tuple:
        # Everything that changes how a SEASON plays (rosters read history, not
        # this, so dev/lean/builder/feeder are already fixed by the season year).
        return (round(self.lens.read, 12), round(self.lens.trust, 12),
                round(self.lens.form, 12), round(self.culture, 12), self.strategy,
                None if self.clutch is None else round(self.clutch, 9),
                None if self.changeover is None else round(self.changeover, 9),
                self.temperament)


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
    culture = culture_of(eff["doubles"])
    lean = 0.0
    for c in [head] + list(assistants):
        if c.profile == "jv_whisperer":
            lean = 1.0 if c is head else max(lean, 0.5)
    return StaffEffect(lens=lens_of(eff["talent_id"], eff["adaptability"]),
                       culture=culture, strategy=head.pairing,
                       dev=1.0 + DEV_K * (eff["development"] - 0.5),
                       lean=lean,
                       clutch=head.grades.get("clutch", 0.5),
                       changeover=head.grades.get("changeover", 0.5),
                       temperament=head.temperament,
                       builder=eff["builder"], feeder=eff["feeder"])


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
    """A program's first staff: `[head, asst1, …]`, EVERY grade and philosophy
    rolled at random (owner rule 2026-09 — "the attributes roll randomly for all
    coaches"). Nothing is solved or pinned to the school draws the association
    used before coaches existed: the staff REPLACES those draws, so the first
    season with coaches plays under the people, not the old hidden numbers.

    Deterministic per (salt, program, gender, seat) — the same save rolls the
    same staff — and needs no input from the owner: `ensure_staff` seats every
    program the first time the rung runs after an update."""
    towns = hometowns or [school.city]
    staff = []
    for i in range(1 + n_assistants):
        slot = SLOTS[i]
        rng = _rng("jhsaa-coach", salt, school.ident, school.gender, slot)
        profile = roll_profile(rng)
        age = int(rng.triangular(32, 64, 47) if i == 0 else rng.triangular(23, 68, 40))
        grades = roll_grades(rng, profile, mean=54.0 if age >= 55 else GRADE_MEAN)
        hometown = school.city if rng.random() < 0.55 else rng.choice(towns)
        c = Coach(coach_id=_cid(world_id, salt, school.ident, school.gender, slot),
                  name=roll_name(rng, school.gender), grades=grades,
                  profile=profile,
                  pairing=rng.choice(PAIRINGS),
                  temperament=rng.choice(TEMPERAMENTS),
                  hometown=hometown, birth_year=season_year - age,
                  origin="inaugural", created=season_year)
        staff.append(c)
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
-- The coaching carousel's proposals (a button, never a rung — see below).
CREATE TABLE IF NOT EXISTS jhsaa_coach_carousel (
  world_id INTEGER, year INTEGER, status TEXT, data TEXT
);
"""

_TABLES = ("jhsaa_coach", "jhsaa_coach_seat", "jhsaa_coach_history", "jhsaa_coach_event",
           "jhsaa_alumni", "jhsaa_coach_carousel")


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
        "origin", "alma", "player_pid", "created", "retired")})


_COACH_FIELDS = ("grades", "profile", "pairing", "temperament", "hometown",
                 "birth_year", "origin", "alma", "player_pid", "created", "retired")


def _coach_from(coach_id: str, name: str, data: str) -> Coach:
    """A stored coach. Unknown keys are ignored, so a row written by an earlier
    build (which carried reproduction pins) still loads."""
    d = json.loads(data)
    return Coach(coach_id=coach_id, name=name,
                 **{k: v for k, v in d.items() if k in _COACH_FIELDS})


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
                       "culture": e.culture, "strategy": e.strategy,
                       "dev": e.dev, "lean": e.lean, "clutch": e.clutch,
                       "changeover": e.changeover, "temperament": e.temperament,
                       "builder": e.builder, "feeder": e.feeder})


def _eff_from_json(s: str) -> StaffEffect:
    """‼️ TOLERANT OF A STAGE A ROW: a season archived before Stage B carries only
    the first five keys, and reads back NEUTRAL for everything else — so Stage B
    reaches only seasons played under it, with no era setting (the `_relabel`
    idiom: derive on read, never migrate)."""
    from . import jhsaa
    d = json.loads(s)
    return StaffEffect(lens=jhsaa.CoachLens(read=d["read"], trust=d["trust"],
                                            form=d["form"]),
                       culture=d["culture"], strategy=d["strategy"],
                       dev=d.get("dev", 1.0), lean=d.get("lean", 0.0),
                       clutch=d.get("clutch"), changeover=d.get("changeover"),
                       temperament=d.get("temperament", "steady"),
                       builder=d.get("builder", 0.5), feeder=d.get("feeder", 0.5))


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
    # A new archived year changes what a roster build reads.
    from . import jhsaa
    jhsaa._staff_hist_cache.clear()


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


def index_alumnus(world_id: int, cand: dict) -> None:
    """Add one former player to the alumni index by hand-off from their player
    page — how a player who graduated BEFORE coaches existed (so was never
    indexed at archive time) becomes hireable with no migration."""
    conn = _conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO jhsaa_alumni (world_id, pid, gender, ident, school,"
            " grad_year, name, style, trait, ovr, rank, honored)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (world_id, cand["pid"], cand["gender"], cand["ident"], cand["school"],
             cand["grad_year"], cand["name"], cand.get("style", ""),
             cand.get("trait", ""), float(cand.get("ovr") or 0.0), 0, 0))
        conn.commit()
    finally:
        conn.close()


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


# ------------------------------------------------------ the coaching carousel ----
#
# ‼️ A BUTTON, NEVER A RUNG (owner rule 2026-09). High-school coaches stay 10-25
# years — nobody is paid enough to chase jobs — so nothing here runs on its own and
# nothing holds `advance_week`. "Run a coaching cycle" builds a PENDING proposal
# (the `jhsaa_reclass_pending` idiom); the owner vetoes any line and commits. The
# proposal stores everything it will do, new coaches included, so what is committed
# is exactly what was reviewed.

RETIRE_BY_AGE = ((55, 0.01), (65, 0.06), (200, 0.25))   # age < bound → chance
RETIRE_LONG_TENURE = (25, 0.05)                          # years, extra chance
FIRE_MIN_SEASONS = 5          # a head is judged only on a long run…
FIRE_BELOW = 0.20             # …of this far below the program's own norm
FIRE_CHANCE = 0.30            # and even then, usually kept
PROMOTE_CHANCE = 0.60         # a head vacancy goes to the staff's own assistant first
ALUMNI_MIN_YEARS = 4          # an alumnus coaches once they are this far out
AREA_MOVE_CHANCE = 0.25       # a head vacancy lures an area assistant up

def _cconn():
    return _conn()


def legacy(world_id: int, gender: str) -> dict:
    """{ident: 0-1} — a program's coaching LEGACY: how much of its archived
    history was coached by long-tenured heads (10+ seasons there). Reputation
    only: it raises how often the program's own alumni come home to coach, and
    nothing in a match or a roster reads it."""
    conn = _conn()
    try:
        rows = conn.execute("SELECT ident, coach_id, COUNT(*) FROM jhsaa_coach_history"
                            " WHERE world_id=? AND gender=? AND slot='head'"
                            " GROUP BY ident, coach_id", (world_id, gender)).fetchall()
    finally:
        conn.close()
    out: dict = {}
    for ident, _cid_, n in rows:
        if n >= 10:
            out[ident] = min(1.0, out.get(ident, 0.0) + n / 20.0)
    return out


def _head_run(conn, world_id, gender, ident, coach_id):
    rows = conn.execute("SELECT year, coach_id, wins, losses, classification"
                        " FROM jhsaa_coach_history WHERE world_id=? AND gender=?"
                        " AND ident=? AND slot='head' ORDER BY year",
                        (world_id, gender, ident)).fetchall()
    mine = [r for r in rows if r[1] == coach_id]
    before = [r for r in rows if r[1] != coach_id and (not mine or r[0] < mine[0][0])]
    return mine, before


def _pct(rows):
    w = sum(r[2] or 0 for r in rows)
    l = sum(r[3] or 0 for r in rows)
    return w / (w + l) if w + l else None


def _new_candidate(world_id: int, season_year: int, gender: str, school_city: str,
                   tag: str) -> Coach:
    rng = _rng("jhsaa-coach-candidate", world_id, season_year, tag)
    age = int(rng.triangular(24, 68, 42))
    profile = roll_profile(rng)
    grades = roll_grades(rng, profile, mean=54.0 if age >= 55 else GRADE_MEAN)
    return Coach(coach_id=_cid(world_id, "cand", season_year, tag),
                 name=roll_name(rng, gender), grades=grades, profile=profile,
                 pairing=rng.choice(PAIRINGS), temperament=rng.choice(TEMPERAMENTS),
                 hometown=school_city, birth_year=season_year - age, origin="area",
                 created=season_year)


def propose_cycle(world_id: int, season_year: int) -> dict:
    """Build (and store as PENDING) one coaching cycle: retirements, the rare
    firing, then every vacancy filled — the program's own assistant first, then
    its alumni (more often at a legacy program), then an area move or a new
    local candidate. Deterministic for (world, season)."""
    from . import jhsaa
    lines = []
    conn = _conn()
    try:
        for gender in ("girls", "boys"):
            schools = {s.ident: s for s in jhsaa.load_schools(gender)}
            leg = legacy(world_id, gender)
            seat_rows = seats(world_id, gender)
            staff = _staffs(seat_rows)
            vacancies = []                      # (ident, slot)
            leaving = set()
            for r in sorted(seat_rows, key=lambda r: (r["ident"], SLOTS.index(r["slot"]))):
                ident, slot, c = r["ident"], r["slot"], r["coach"]
                if ident not in schools or c is None:
                    continue
                rng = _rng("jhsaa-carousel", world_id, season_year, c.coach_id)
                age = season_year - c.birth_year if c.birth_year else 45
                tenure = season_year - (r["since"] or season_year)
                p = next(ch for bound, ch in RETIRE_BY_AGE if age < bound)
                if tenure >= RETIRE_LONG_TENURE[0]:
                    p += RETIRE_LONG_TENURE[1]
                if rng.random() < p:
                    lines.append({"kind": "retire", "gender": gender, "ident": ident,
                                  "school": schools[ident].name, "slot": slot,
                                  "coach_id": c.coach_id, "name": c.name,
                                  "why": f"age {age}, {tenure} seasons in the seat"})
                    leaving.add(c.coach_id)
                    vacancies.append((ident, slot))
                    continue
                if slot == "head":
                    mine, before = _head_run(conn, world_id, gender, ident, c.coach_id)
                    # Only seasons in the program's CURRENT class count —
                    # a realignment is not the coach's doing.
                    cls = schools[ident].classification
                    mine_same = [r for r in mine if r[4] == cls]
                    norm = _pct(before)
                    got = _pct(mine_same)
                    if (len(mine_same) >= FIRE_MIN_SEASONS and norm is not None
                            and got is not None and got < norm - FIRE_BELOW
                            and rng.random() < FIRE_CHANCE):
                        lines.append({"kind": "fire", "gender": gender, "ident": ident,
                                      "school": schools[ident].name, "slot": "head",
                                      "coach_id": c.coach_id, "name": c.name,
                                      "why": f"{got:.3f} over {len(mine_same)} seasons"
                                             f" against the program's {norm:.3f}"})
                        leaving.add(c.coach_id)
                        vacancies.append((ident, "head"))
            # Seats already vacant (a grown roster, an earlier move).
            for r in seat_rows:
                if r["coach"] is None and r["ident"] in schools:
                    vacancies.append((r["ident"], r["slot"]))
            # Heads first, so a promotion's vacated assistant seat is filled too.
            vacancies.sort(key=lambda v: (v[1] != "head", v[0], v[1]))
            taken = set(leaving)
            alumni_used = set()
            k = 0
            while k < len(vacancies):
                ident, slot = vacancies[k]
                k += 1
                sc = schools[ident]
                rng = _rng("jhsaa-carousel-fill", world_id, season_year, gender, ident, slot)
                head, ast = staff.get((ident, gender), (None, []))
                line = None
                if slot == "head":
                    own = [a for a in ast if a.coach_id not in taken]
                    if own and rng.random() < PROMOTE_CHANCE:
                        best = max(own, key=lambda a: sum(a.grades.values()))
                        old_slot = next(r["slot"] for r in seats(world_id, gender, ident)
                                        if r["coach"] and r["coach"].coach_id == best.coach_id)
                        line = {"kind": "promote", "coach_id": best.coach_id,
                                "name": best.name, "why": "the program's own assistant",
                                "from_ident": ident, "from_slot": old_slot}
                        taken.add(best.coach_id)
                        vacancies.append((ident, old_slot))
                    elif rng.random() < AREA_MOVE_CHANCE:
                        near = [(i2, a) for (i2, g2), (_h, aa) in staff.items()
                                if i2 in schools and i2 != ident
                                and schools[i2].area == sc.area
                                for a in aa if a.coach_id not in taken]
                        if near:
                            i2, a = max(near, key=lambda t: (sum(t[1].grades.values()),
                                                             t[1].coach_id))
                            taken.add(a.coach_id)
                            old_slot = next(r["slot"] for r in seats(world_id, gender, i2)
                                            if r["coach"] and r["coach"].coach_id == a.coach_id)
                            line = {"kind": "move", "coach_id": a.coach_id, "name": a.name,
                                    "why": f"assistant at {schools[i2].name}, same area",
                                    "from_ident": i2, "from_slot": old_slot}
                            vacancies.append((i2, old_slot))
                if line is None:
                    p_alum = 0.25 + 0.5 * leg.get(ident, 0.0)
                    if rng.random() < p_alum:
                        alum = conn.execute(
                            "SELECT pid, name, grad_year FROM jhsaa_alumni WHERE world_id=?"
                            " AND gender=? AND ident=? AND grad_year<=? ORDER BY pid",
                            (world_id, gender, ident, season_year - ALUMNI_MIN_YEARS)).fetchall()
                        alum = [a for a in alum if a[0] not in alumni_used
                                and _cid(world_id, "player", a[0]) not in taken]
                        if alum:
                            pid, nm, gy = alum[rng.randrange(len(alum))]
                            alumni_used.add(pid)
                            line = {"kind": "alumnus", "pid": pid, "name": nm,
                                    "why": f"class of {gy} — home to coach"}
                if line is None:
                    c = _new_candidate(world_id, season_year, gender, sc.city,
                                       f"{gender}|{ident}|{slot}")
                    line = {"kind": "new", "coach": json.loads(_coach_row(c)),
                            "coach_id": c.coach_id, "name": c.name,
                            "why": f"{PROFILE_LABELS.get(c.profile, c.profile)}, local"}
                line.update({"gender": gender, "ident": ident, "school": sc.name,
                             "slot": slot, "fill": True})
                lines.append(line)
    finally:
        conn.close()
    for i, ln in enumerate(lines):
        ln["n"] = i
        ln["veto"] = False
    prop = {"year": season_year, "lines": lines}
    conn = _cconn()
    try:
        conn.execute("DELETE FROM jhsaa_coach_carousel WHERE world_id=? AND status='pending'",
                     (world_id,))
        conn.execute("INSERT INTO jhsaa_coach_carousel (world_id, year, status, data)"
                     " VALUES (?,?,?,?)", (world_id, season_year, "pending", json.dumps(prop)))
        conn.commit()
    finally:
        conn.close()
    return prop


def pending_cycle(world_id: int) -> dict | None:
    conn = _cconn()
    try:
        r = conn.execute("SELECT data FROM jhsaa_coach_carousel WHERE world_id=?"
                         " AND status='pending' ORDER BY rowid DESC LIMIT 1",
                         (world_id,)).fetchone()
    finally:
        conn.close()
    return json.loads(r[0]) if r else None


def _save_pending(world_id: int, prop: dict) -> None:
    conn = _cconn()
    try:
        conn.execute("UPDATE jhsaa_coach_carousel SET data=? WHERE world_id=?"
                     " AND status='pending'", (json.dumps(prop), world_id))
        conn.commit()
    finally:
        conn.close()


def set_vetoes(world_id: int, vetoed: set) -> None:
    prop = pending_cycle(world_id)
    if prop is None:
        raise StaffError("No coaching cycle is pending.")
    for ln in prop["lines"]:
        ln["veto"] = ln["n"] in vetoed
    _save_pending(world_id, prop)


def dismiss_cycle(world_id: int) -> None:
    conn = _cconn()
    try:
        conn.execute("UPDATE jhsaa_coach_carousel SET status='dismissed' WHERE world_id=?"
                     " AND status='pending'", (world_id,))
        conn.commit()
    finally:
        conn.close()


def commit_cycle(world_id: int) -> int:
    """Apply every line not vetoed, in proposal order. A fill whose incoming coach
    was vetoed out of their old seat still applies (the seat is the proposal's
    unit); a fill onto a seat whose departure was vetoed is skipped, since the
    seat is not vacant. Returns the number of lines applied."""
    prop = pending_cycle(world_id)
    if prop is None:
        raise StaffError("No coaching cycle is pending.")
    sy = prop["year"]
    # A vetoed departure keeps its seat filled, and so does a vetoed promotion or
    # move — for the seat the coach would have LEFT — so no fill lands on a coach
    # who is staying and sends them to the free pool.
    kept_seat = {(ln["gender"], ln["ident"], ln["slot"]) for ln in prop["lines"]
                 if ln["veto"] and ln["kind"] in ("retire", "fire")}
    kept_seat |= {(ln["gender"], ln["from_ident"], ln["from_slot"]) for ln in prop["lines"]
                  if ln["veto"] and ln.get("from_slot")}
    applied = 0
    for ln in prop["lines"]:
        if ln["veto"]:
            continue
        key = (ln["gender"], ln["ident"], ln["slot"])
        if ln["kind"] in ("retire", "fire"):
            retire_coach(world_id, ln["coach_id"], sy)
            if ln["kind"] == "fire":
                conn = _conn()
                try:
                    _event(conn, world_id, sy, ln["coach_id"], ln["ident"], ln["gender"],
                           "head", "fired", ln.get("why", ""))
                    c = _load_coaches(conn, world_id, [ln["coach_id"]]).get(ln["coach_id"])
                    if c is not None:          # fired, not retired: back to the pool
                        c.retired = 0
                        save_coach(conn, world_id, c)
                    conn.commit()
                finally:
                    conn.close()
            applied += 1
            continue
        if key in kept_seat:
            continue
        try:
            if ln["kind"] == "alumnus":
                appoint_former_player(world_id, ln["pid"], ln["ident"], ln["gender"],
                                      ln["slot"], sy)
            elif ln["kind"] == "new":
                conn = _conn()
                try:
                    c = Coach(coach_id=ln["coach_id"], name=ln["name"], **ln["coach"])
                    save_coach(conn, world_id, c)
                    conn.commit()
                finally:
                    conn.close()
                move_coach(world_id, c.coach_id, ln["ident"], ln["gender"], ln["slot"], sy)
            else:                              # promote / move
                move_coach(world_id, ln["coach_id"], ln["ident"], ln["gender"],
                           ln["slot"], sy)
            applied += 1
        except StaffError:
            continue
    conn = _cconn()
    try:
        conn.execute("UPDATE jhsaa_coach_carousel SET status='committed' WHERE world_id=?"
                     " AND status='pending'", (world_id,))
        conn.commit()
    finally:
        conn.close()
    return applied

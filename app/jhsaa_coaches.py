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
import heapq
import json
import random
import threading
from dataclasses import dataclass, field

# --------------------------------------------------------------- the model ----

#: Graded attributes, in display order. Each is stored as a quantile of the
#: 20-80 display scale — (grade − 20) / 60 — and an Elite coach may break it:
#: the roll runs to 90, so a quantile runs to 70/60 (owner rule 2026-09: "like
#: players, I would let Elite coaches break"). Every consumer of a quantile
#: either clamps (the lens) or stays in a sane range past 1.0 (checked, see the AAR).
GRADES = ("tactics", "singles", "doubles", "development", "talent_id",
          "adaptability", "builder", "feeder", "clutch", "changeover")

GRADE_LABELS = {
    "tactics": "Tactics",
    "singles": "Singles",
    "doubles": "Doubles instinct",
    "development": "Development",
    "talent_id": "Talent ID",
    "adaptability": "Adaptability",
    "builder": "Program builder",
    "feeder": "Feeder ties",
    "clutch": "Clutch",
    "changeover": "Changeover",
}

#: Staff-blended ("cover weak spots"); the rest belong to the head alone. Tactics
#: and Singles are BLENDED on purpose (owner, 2026-09): the point is that a
#: program-builder head can hire an assistant who is good at singles, doubles,
#: tactics or practice, and have the staff be good at it.
BLENDED = ("tactics", "singles", "doubles", "development", "talent_id",
           "adaptability", "builder", "feeder")
HEAD_ONLY = ("clutch", "changeover")

#: How much of the gap to the best assistant a staff closes, per attribute.
#: `effective = head + COVER * max(0, best_assistant - head)` — never above the
#: best coach on the staff, never below the head.
COVER = 0.4

PAIRINGS = ("maximize", "balanced", "traditional", "mentorship")
TEMPERAMENTS = ("broad", "steady", "senior")
TEMPERAMENT_LABELS = {"broad": "Broad rotation", "steady": "Steady",
                      "senior": "Senior-first"}

# --- HOW A COACH ROLLS (owner spec 2026-09) -------------------------------------
# ONE upstream quality roll, then the permanent attribute rolls, then nothing —
# no budget, no development, no regeneration:
#   1. a QUALITY BAND (overlapping, so a 35 can be Poor or Below Average);
#   2. the coach's own OVERALL, any integer inside that band — never a round tier
#      value — the anchor for everything after it;
#   3. an IDENTITY, whose FLOORS guarantee competence where it is built (a primary
#      of at least 50, so every coach — a Bad one included — is good at something);
#   4. every attribute rolled across a WIDE window around the overall, floored by
#      the identity. The attributes need not average back to the overall, and an
#      unrelated attribute can land as an unexpected strength.

#: (name, overall band lo, hi, share of coaches). The shares are this module's
#: call (the owner set the bands, not the mix); Average is the widest single block
#: and both tails are real — ~1 coach in 7 is Bad or Poor.
BANDS = (("Bad", 20, 32, 6), ("Poor", 25, 36, 9), ("Below average", 33, 46, 18),
         ("Average", 44, 56, 32), ("Good", 51, 68, 22), ("Excellent", 68, 79, 9),
         ("Elite", 78, 90, 4))
GRADE_MIN, GRADE_MAX = 20, 90

#: identity → (primary, primary floor, {related: floor}). Floors, never values:
#: a singles specialist's Singles is ROLLED, it just cannot finish below 50.
IDENTITIES = {
    "builder":    ("builder", 50, {"feeder": 40, "talent_id": 35}),
    "practice":   ("development", 50, {"adaptability": 40, "singles": 35,
                                       "doubles": 35}),
    "singles":    ("singles", 50, {"tactics": 40, "development": 38}),
    "doubles":    ("doubles", 50, {"tactics": 40, "changeover": 35}),
    "tactician":  ("tactics", 50, {"adaptability": 40, "changeover": 38}),
    "evaluator":  ("talent_id", 50, {"adaptability": 42, "development": 35}),
    "motivator":  ("clutch", 50, {"changeover": 42, "builder": 35}),
    "generalist": (None, 50, {}),        # one random primary; broad floors elsewhere
}
GENERALIST_FLOOR = 30
PROFILES = IDENTITIES                    # the identity is also an assistant's specialty
PROFILE_LABELS = {
    "builder": "Program builder", "practice": "Practice / development",
    "singles": "Singles specialist", "doubles": "Doubles specialist",
    "tactician": "Tactician", "evaluator": "Evaluator", "motivator": "Motivator",
    "generalist": "Generalist",
}
#: Identities retired by the 2026-09 band roll, still carried by coaches a save
#: persisted under the previous build. ‼️ NEVER REMAPPED ON LOAD: a coach's ratings
#: are imprinted and their identity is part of that record, and a remap would move
#: effects (an old "teacher" never carried the depth lean, so reading it as
#: "practice" would add one). They keep their name, their label and exactly the
#: effect they had — `JV_LEAN_PROFILES` is the one place an effect keys on one.
LEGACY_PROFILE_LABELS = {"teacher": "Teacher", "jv_whisperer": "JV whisperer",
                         "doubles_guru": "Doubles guru"}
PROFILE_LABELS.update(LEGACY_PROFILE_LABELS)
#: Identities that carry the JV / floor-raiser depth lean: the practice identity,
#: and the retired JV whisperer it replaced (so a stored one keeps its lean).
JV_LEAN_PROFILES = ("practice", "jv_whisperer")
PROFILE_WEIGHTS = {"builder": 12, "practice": 16, "singles": 14, "doubles": 14,
                   "tactician": 14, "evaluator": 10, "motivator": 10, "generalist": 10}

#: Roll windows around the overall: (below, above).
WIN_PRIMARY = (5, 30)
WIN_RELATED = (15, 20)
WIN_OTHER = (20, 15)
#: When a low overall puts the window's top under the identity floor, the top is
#: raised to leave a REAL roll of at least this many points above the floor,
#: rather than handing out the floor itself.
MIN_ROLL = 12

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
    """A stored quantile as a grade — DISPLAY only, and never clamped (an Elite
    coach shows the 84 they rolled)."""
    return 20.0 + 60.0 * q


def to_q(grade: float) -> float:
    g = min(float(GRADE_MAX), max(float(GRADE_MIN), grade))
    return (g - 20.0) / 60.0


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
    profile: str = "generalist"        # the IDENTITY
    pairing: str = "balanced"
    temperament: str = "steady"
    hometown: str = ""
    birth_year: int = 0
    origin: str = "inaugural"          # inaugural / alumnus / college_grad / editor
    alma: str = ""                     # school ident the coach played for, if any
    player_pid: str = ""
    created: int = 0                   # season year the coach was created
    retired: int = 0                   # season year retired; 0 = active
    overall: int = 0                   # the rolled caliber (the attribute anchor)
    tier: str = ""                     # the quality band it was rolled in

    def grade(self, attr: str) -> int:
        return round(to_grade(self.grades.get(attr, 0.5)))


def roll_band(rng: random.Random) -> tuple[str, int]:
    """Step 1 and 2: the quality band, then the coach's own overall inside it."""
    name, lo, hi, _w = rng.choices(BANDS, weights=[b[3] for b in BANDS])[0]
    return name, rng.randint(lo, hi)


def _window(overall: int, win: tuple[int, int], floor: int) -> tuple[int, int]:
    lo = max(GRADE_MIN, overall - win[0], floor)
    hi = min(GRADE_MAX, overall + win[1])
    if hi < lo + MIN_ROLL:
        hi = min(GRADE_MAX, lo + MIN_ROLL)
    return lo, max(lo, hi)


def roll_grades(rng: random.Random, profile: str, overall: int) -> dict:
    """Steps 3 and 4: every attribute, rolled once, as quantiles. Wide windows
    around `overall`, floored by the identity — independent rolls, no shared
    budget, nothing averaging back to the overall."""
    primary, pfloor, related = IDENTITIES.get(profile, IDENTITIES["generalist"])
    if primary is None:                                     # the generalist
        primary = rng.choice(GRADES)
        related = {a: GENERALIST_FLOOR for a in GRADES if a != primary}
    out = {}
    for a in GRADES:
        if a == primary:
            lo, hi = _window(overall, WIN_PRIMARY, pfloor)
        elif a in related:
            lo, hi = _window(overall, WIN_RELATED, related[a])
        else:
            lo, hi = _window(overall, WIN_OTHER, GRADE_MIN)
        out[a] = to_q(rng.randint(lo, hi))
    return out


def roll_profile(rng: random.Random) -> str:
    names = list(PROFILE_WEIGHTS)
    return rng.choices(names, weights=[PROFILE_WEIGHTS[n] for n in names])[0]


def roll_coach(rng: random.Random, profile: str | None = None) -> tuple:
    """The whole creation roll: (identity, tier, overall, grades). The ONLY way a
    coach's ratings come into being; nothing re-runs it."""
    profile = profile or roll_profile(rng)
    tier, overall = roll_band(rng)
    return profile, tier, overall, roll_grades(rng, profile, overall)


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
TACTICS_K = 0.5        # the game plan: how much a better tactician scales the STYLE
                       # MATCHUP edge (engine.fast.style_edge) — the favoured side's
                       # coach amplifies it, the other side's coach blunts it; a flat
                       # matchup stays zero, so it only acts where style already did
SINGLES_K = 1.2        # singles coaching: ± OVR points per side at the singles
                       # flights, per unit of quantile off grade 50 (best vs worst
                       # staff ≈ 1.4 OVR — home court is 1-4 for a whole dual)
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
    tactics: float | None = None      # staff Tactics quantile (style-matchup scale)
    singles: float | None = None      # staff Singles quantile (singles flights)

    def fingerprint(self) -> tuple:
        # Everything that changes how a SEASON plays (rosters read history, not
        # this, so dev/lean/builder/feeder are already fixed by the season year).
        return (round(self.lens.read, 12), round(self.lens.trust, 12),
                round(self.lens.form, 12), round(self.culture, 12), self.strategy,
                None if self.clutch is None else round(self.clutch, 9),
                None if self.changeover is None else round(self.changeover, 9),
                self.temperament,
                None if self.tactics is None else round(self.tactics, 9),
                None if self.singles is None else round(self.singles, 9))


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
        if c.profile in JV_LEAN_PROFILES:
            lean = 1.0 if c is head else max(lean, 0.5)
    return StaffEffect(lens=lens_of(eff["talent_id"], eff["adaptability"]),
                       culture=culture, strategy=head.pairing,
                       dev=1.0 + DEV_K * (eff["development"] - 0.5),
                       lean=lean,
                       clutch=head.grades.get("clutch", 0.5),
                       changeover=head.grades.get("changeover", 0.5),
                       temperament=head.temperament,
                       builder=eff["builder"], feeder=eff["feeder"],
                       tactics=eff["tactics"], singles=eff["singles"])


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
        profile, tier, overall, grades = roll_coach(rng)
        age = int(rng.triangular(32, 64, 47) if i == 0 else rng.triangular(23, 68, 40))
        hometown = school.city if rng.random() < 0.55 else rng.choice(towns)
        c = Coach(coach_id=_cid(world_id, salt, school.ident, school.gender, slot),
                  name=roll_name(rng, school.gender), grades=grades,
                  profile=profile,
                  pairing=rng.choice(PAIRINGS),
                  temperament=rng.choice(TEMPERAMENTS),
                  hometown=hometown, birth_year=season_year - age,
                  origin="inaugural", created=season_year,
                  overall=overall, tier=tier)
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
           "jhsaa_alumni", "jhsaa_coach_carousel", "jhsaa_preseason", "jhsaa_coach_award")


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
        "origin", "alma", "player_pid", "created", "retired", "overall", "tier")})


_COACH_FIELDS = ("grades", "profile", "pairing", "temperament", "hometown",
                 "birth_year", "origin", "alma", "player_pid", "created", "retired",
                 "overall", "tier")


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
    with _seat_lock:
        return _ensure_staff(jhsaa, world_id, season_year, salt)


def _seated_heads(conn, world_id: int) -> set:
    return {(r[0], r[1]) for r in conn.execute(
        "SELECT ident, gender FROM jhsaa_coach_seat"
        " WHERE world_id=? AND slot='head'", (world_id,))}


def _ensure_staff(jhsaa, world_id: int, season_year: int, salt: str) -> int:
    # 1. WHO IS MISSING, read without any lock.
    conn = _conn()
    try:
        have = _seated_heads(conn, world_id)
    finally:
        conn.close()
    # 2. ROLL THEIR STAFFS BEFORE TAKING THE WRITE LOCK. ‼️ `load_schools` and
    # `roster_size` open connections of their own (override and config reads, and
    # a config read can CREATE a table): run under our BEGIN IMMEDIATE they wait
    # on our own lock and the seater times out on itself — measured, every
    # caller failed "database is locked". So everything that might touch the
    # database is done here, and the locked section below only writes.
    todo = []
    for gender in ("girls", "boys"):
        schools = jhsaa.load_schools(gender)
        towns = sorted({s.city for s in schools})
        for s in schools:
            if (s.ident, gender) in have:
                continue
            n_ast = assistants_for(jhsaa.roster_size(s.classification, s.key, salt))
            todo.append((s.ident, gender,
                         inaugural_staff(s, n_ast, salt, season_year, world_id, towns)))
    if not todo:
        return 0
    # 3. THE WRITE LOCK, THEN RE-READ, THEN WRITE. A concurrent seater (another
    # process, or the rung) may have committed since step 1; BEGIN IMMEDIATE makes
    # the re-read and the writes one critical section, so a program somebody else
    # just seated is skipped rather than seated twice with duplicate events.
    conn = _conn()
    try:
        if conn.in_transaction:
            conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        have = _seated_heads(conn, world_id)
        n = 0
        for ident, gender, staff in todo:
            if (ident, gender) in have:
                continue
            for i, c in enumerate(staff):
                save_coach(conn, world_id, c)
                conn.execute(
                    "INSERT OR REPLACE INTO jhsaa_coach_seat (world_id, ident, gender,"
                    " slot, coach_id, since, jv_head) VALUES (?,?,?,?,?,?,?)",
                    (world_id, ident, gender, SLOTS[i], c.coach_id, season_year,
                     int(i == 1)))
                _event(conn, world_id, season_year, c.coach_id, ident, gender,
                       SLOTS[i], "existing", "on staff when coaches were introduced")
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


_seated: set = set()     # (db, world_id) already confirmed to have staffs
# ‼️ FIRST-TIME SEATING IS SINGLE-FLIGHT. Two requests reaching a coach surface on a
# save with no staffs both passed the memo and the probe and both entered
# `ensure_staff`: the second either timed out on SQLite's lock or, after the first
# committed, re-read an out-of-date "who has a head" set and appended every
# inaugural event a second time. The lock serialises this process (the one gthread
# worker); `ensure_staff` also takes the DATABASE write lock before it reads, which
# covers a second process and the season rung. Re-entrant because ensure_seated
# calls ensure_staff under it.
_seat_lock = threading.RLock()


def ensure_seated(world_id: int, season_year: int, salt: str) -> None:
    """Seat every program's staff NOW if this world has none yet — for the PAGES
    (owner report 2026-09: "you don't display them"). `ensure_staff` otherwise
    only runs inside the season rung, so a save opened after this build showed
    no coaches anywhere until its next season was simulated, and the program
    page's staff panel simply did not render.

    Cost: one indexed probe, memoised per (database, world) so later requests
    pay nothing; the one-time seating is ~1 s for the whole association. It
    rolls the SAME staffs the rung would (same salt, same season year, same
    seeds), so seating here or at the rung is indistinguishable."""
    from .dbpath import resolve_db_path
    key = (resolve_db_path(), world_id)
    if key in _seated:                 # the fast path: no lock once seated
        return
    with _seat_lock:
        if key in _seated:             # another request seated it while we waited
            return
        conn = _conn()
        try:
            have = conn.execute("SELECT 1 FROM jhsaa_coach_seat WHERE world_id=? LIMIT 1",
                                (world_id,)).fetchone()
        finally:
            conn.close()
        if not have:
            ensure_staff(world_id, season_year, salt)
        _seated.add(key)


def directory(world_id: int, gender: str) -> list[dict]:
    """Every program's HEAD coach and staff size, for the Coaches page — one read
    of the seats and one of the coaches, never a query per program."""
    from . import jhsaa
    rows = seats(world_id, gender)
    by = {}
    for r in rows:
        by.setdefault(r["ident"], []).append(r)
    out = []
    for s in jhsaa.load_schools(gender):
        seat_rows = by.get(s.ident, [])
        head = next((r["coach"] for r in seat_rows if r["slot"] == "head"), None)
        if head is None:
            continue
        ast = [r["coach"] for r in seat_rows if r["slot"] != "head" and r["coach"]]
        eff = effective(head, ast)
        out.append({"school": s.name, "group": s.group, "head": head,
                    "identity": PROFILE_LABELS.get(head.profile, head.profile),
                    "staff": 1 + len(ast),
                    "vacant": sum(1 for r in seat_rows if not r["coach"]),
                    "staff_best": max(round(to_grade(v)) for v in eff.values())})
    out.sort(key=lambda r: (-(r["head"].overall or 0), r["school"]))
    return out


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
                       "builder": e.builder, "feeder": e.feeder,
                       "tactics": e.tactics, "singles": e.singles})


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
                       builder=d.get("builder", 0.5), feeder=d.get("feeder", 0.5),
                       tactics=d.get("tactics"), singles=d.get("singles"))


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
    # A new archived year changes what a roster build reads. The rung invalidates
    # AGAIN after its commit (`world.run_jhsaa`) — this one alone would let a
    # concurrent reader re-cache the pre-commit history.
    from . import jhsaa
    jhsaa.invalidate_staff_history()


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
    # ‼️ `jhsaa_coach_history.year` is the WORLD KEY (0, 1, …), the same key the
    # archive uses — never a calendar year. The page shows the season, so map it the
    # way `world.jhsaa_season_year` does (events and seats already store seasons);
    # `world_year` keeps the key for anything that links back into the archive.
    from .world import BASE_YEAR
    for h in hist:
        h["world_year"] = h["year"]
        h["year"] = BASE_YEAR + int(h["year"]) + 1
    w = sum(h["wins"] or 0 for h in hist if h["slot"] == "head")
    l = sum(h["losses"] or 0 for h in hist if h["slot"] == "head")
    return {"history": hist, "events": events,
            "seat": dict(zip(("ident", "gender", "slot", "since", "jv_head"), seat))
            if seat else None,
            "head_record": f"{w}-{l}"}


def season_heads(world_id: int, gender: str) -> dict:
    """{(year, ident): {"coach_id", "name"}} — who was HEAD coach of every program
    in every archived season, for the champions history (the OSAA records' Coach
    column). ONE query for the whole archive; a season archived before coaches
    existed has no rows, so its coach cell stays blank — the OSAA's own convention
    for years nobody recorded who coached."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT h.year, h.ident, h.coach_id, c.name FROM jhsaa_coach_history h"
            " LEFT JOIN jhsaa_coach c ON c.world_id=h.world_id AND c.coach_id=h.coach_id"
            " WHERE h.world_id=? AND h.gender=? AND h.slot='head'",
            (world_id, gender)).fetchall()
    finally:
        conn.close()
    return {(y, ident): {"coach_id": cid, "name": nm or ""}
            for y, ident, cid, nm in rows if cid}


def slot_label(slot: str, jv_head: bool) -> str:
    if slot == "head":
        return "Head coach"
    return "JV head coach" if jv_head else "Assistant coach"


def program_staff(world_id: int, ident: str, gender: str,
                  season_year: int | None = None) -> dict | None:
    """The program page's staff block: every seat (vacant ones included), and the
    EFFECTIVE value per attribute with who covers it — plus the Staff tab's
    MATRIX (every coach's grade per attribute beside the staff's effective one)."""
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
    seat_rows = [{**r, "label": slot_label(r["slot"], r["jv_head"]),
                  "identity": PROFILE_LABELS.get(r["coach"].profile, r["coach"].profile)
                  if r["coach"] else "",
                  "age": (season_year - r["coach"].birth_year)
                  if (r["coach"] and season_year and r["coach"].birth_year) else None}
                 for r in rows]
    # The head's career record — HEAD seasons, varsity only (the history table is
    # varsity by construction), wherever they coached. One indexed read.
    if head is not None:
        conn = _conn()
        try:
            w, l, t = conn.execute(
                "SELECT COALESCE(SUM(wins),0), COALESCE(SUM(losses),0),"
                " COALESCE(SUM(ties),0) FROM jhsaa_coach_history WHERE world_id=?"
                " AND coach_id=? AND slot='head'", (world_id, head.coach_id)).fetchone()
        finally:
            conn.close()
        for r in seat_rows:
            if r["slot"] == "head":
                r["record"] = f"{w}-{l}" + (f"-{t}" if t else "")
    matrix = [{"attr": a, "label": GRADE_LABELS[a], "blended": a in BLENDED,
               "grades": [r["coach"].grade(a) if r["coach"] else None for r in rows],
               "effective": round(to_grade(eff[a])), "via": cover.get(a)}
              for a in GRADES]
    return {
        "seats": seat_rows,
        "matrix": matrix,
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
    attributes, owner rule) as the real rolled number, 20-90."""
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
                "role": "Head coach" if h["slot"] == "head" else "Assistant"}
               for h in car["history"]]
    ledger, totals = _career_ledger(world_id, history)
    # Coach of the Year (owner spec 2026-09): each award rides on its season row
    # and is counted on the career panel.
    from . import jhsaa_coy
    coy = jhsaa_coy.coach_awards(world_id, coach_id)
    by_season = {}
    for a in coy:
        by_season.setdefault((a["world_year"], a["gender"]), []).append(
            "State COY" if a["level"] == "state" else "District COY")
    for row in ledger:
        row["coy"] = by_season.get((row["world_year"], row["gender"]), [])
    totals["coy_state"] = sum(1 for a in coy if a["level"] == "state")
    totals["coy_district"] = sum(1 for a in coy if a["level"] == "district")
    events = transactions([{**e, "school": names.get(e["ident"], e["ident"])}
                           for e in car["events"]])
    # Off a staff a coach is a FREE AGENT, or RETIRED (owner rule 2026-09) — never
    # "not on a staff". A retired coach's page stays: history is never deleted.
    status = ("Retired" if c.retired else "Free agent") if not seat else ""
    return {
        "coach": c,
        "grades": [{"attr": a, "label": GRADE_LABELS[a], "grade": c.grade(a),
                    "blended": a in BLENDED} for a in GRADES],
        "profile": PROFILE_LABELS.get(c.profile, c.profile),
        "pairing": c.pairing.title(),
        "temperament": TEMPERAMENT_LABELS.get(c.temperament, c.temperament),
        "age": season_year - c.birth_year if c.birth_year else None,
        "origin": {"inaugural": "",
                   "alumnus": "Former JHSAA player", "college_grad": "Former college player",
                   "editor": "Appointed by the association"}.get(c.origin, c.origin),
        "alma": names.get(c.alma, c.alma) if c.alma else "",
        "gender": gender,
        "seat": ({**seat, "school": names.get(seat["ident"], seat["ident"]),
                  "label": slot_label(seat["slot"], seat["jv_head"])} if seat else None),
        "history": history,
        "ledger": ledger,
        "totals": totals,
        "events": list(reversed(events)),
        "status": status,
        "head_record": totals["record"],
    }


def _career_ledger(world_id: int, history: list[dict]) -> tuple[list, dict]:
    """The coach page's season ledger — the player page's career table, for a coach
    (owner, 2026-09). One row per season on a staff, newest first, with that
    program's season beside it (district, finish, titles, honours).

    ‼️ THE CAREER RECORD IS THE HEAD COACH'S VARSITY RECORD AND NOTHING ELSE (owner
    rule): an assistant season shows how the TEAM did but adds nothing to the
    coach's W-L, and JV never enters it (the archived W-L is the varsity
    TeamSeason's). A head season's W-L comes off the coach's own history row — the
    record that season was archived with — never re-derived."""
    from . import world
    wanted = [(h["world_year"], h["gender"], h["school"]) for h in history]
    rows = world.jhsaa_season_rows_at(world_id, wanted) if wanted else {}
    ledger = []
    t = {"head_seasons": 0, "asst_seasons": 0, "w": 0, "l": 0, "ties": 0,
         "district_titles": 0, "state_apps": 0, "state_titles": 0, "finals": 0,
         "toc_titles": 0, "all_state": 0, "poy": 0, "programs": set()}
    for h in sorted(history, key=lambda h: (-h["world_year"], h["slot"] != "head")):
        head = h["slot"] == "head"
        r = rows.get((h["world_year"], h["gender"], h["school"])) or {}
        rec = ""
        if head:
            w, l, ti = h.get("wins") or 0, h.get("losses") or 0, h.get("ties") or 0
            rec = f"{w}-{l}" + (f"-{ti}" if ti else "")
            t["head_seasons"] += 1
            t["w"] += w
            t["l"] += l
            t["ties"] += ti
            t["district_titles"] += int(r.get("place") == 1)
            t["state_apps"] += int(bool(r.get("made_state")))
            t["state_titles"] += int(bool(r.get("champion")))
            t["finals"] += int(0 < (r.get("state_place") or 0) <= 2)
            t["toc_titles"] += int(bool(r.get("toc_champion")))
            t["all_state"] += len(r.get("all_state") or ())
            t["poy"] += len(r.get("poy") or ())
        else:
            t["asst_seasons"] += 1
        t["programs"].add(h["school"])
        place = r.get("place") or 0
        ledger.append({
            "season_year": h["year"], "world_year": h["world_year"],
            "gender": h["gender"], "school": h["school"],
            "class": r.get("group") or h.get("grp") or h.get("classification") or "",
            "role": h["role"], "head": head, "record": rec,
            "team_record": r.get("record", ""),
            "district": r.get("district", ""),
            "district_place": place,
            "district_record": r.get("district_record", ""),
            "finish": r.get("state_finish") or "",
            "champion": bool(r.get("champion")),
            "toc_champion": bool(r.get("toc_champion")),
            "all_state": len(r.get("all_state") or ()),
            "poy": len(r.get("poy") or ()),
        })
    games = t["w"] + t["l"]
    t["pct"] = (t["w"] + 0.5 * t["ties"]) / (games + t["ties"]) if games + t["ties"] else None
    t["record"] = f"{t['w']}-{t['l']}" + (f"-{t['ties']}" if t["ties"] else "")
    t["programs"] = len(t["programs"])
    return ledger, t


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


#: Playing style → the coaching IDENTITY it leans to, and the pairing philosophy.
#: Coaching ABILITY is never read off playing ability (owner rule): the band and
#: the overall roll exactly as for anybody else — the style only nudges WHAT the
#: former player teaches, and only half the time.
_STYLE_IDENTITY = {
    "serve_and_volley": ("doubles", "balanced"), "net_rusher": ("doubles", "balanced"),
    "chip_and_charge": ("doubles", "balanced"), "all_court": ("tactician", None),
    "grinder": ("practice", None), "retriever": ("practice", None),
    "pusher": ("practice", None),
    "counterpuncher": ("singles", None), "aggressive_baseliner": ("singles", "maximize"),
    "serve_first": ("singles", "maximize"),
    "first_strike": ("motivator", "maximize"), "big_server": ("motivator", "maximize"),
    "junkballer": ("tactician", "traditional"),
    "slice_specialist": ("tactician", "traditional"),
}
STYLE_IDENTITY_SHARE = 0.5


def coach_from_player(world_id: int, cand: dict, team_gender: str, season_year: int,
                      origin: str) -> Coach:
    """A former player's coaching identity. Everything is rolled INDEPENDENTLY of
    how good a player they were, seeded on the pid (so the same person is the same
    coach in any save built from the same world); their style leans the identity
    (half the time) and the pairing philosophy."""
    rng = _rng("jhsaa-coach-from-player", world_id, cand["pid"])
    pairing = rng.choice(PAIRINGS)
    temperament = rng.choice(TEMPERAMENTS)
    profile = roll_profile(rng)
    lean_roll = rng.random()
    for key in (cand.get("trait"), cand.get("style")):
        lean = _STYLE_IDENTITY.get(key or "")
        if lean:
            ident, pair = lean
            if lean_roll < STYLE_IDENTITY_SHARE:
                profile = ident
            if pair:
                pairing = pair
            if ident == "practice":
                temperament = "broad"
            break
    profile, tier, overall, grades = roll_coach(rng, profile)
    grad = cand.get("grad_year") or season_year - 4
    age = max(22, season_year - grad + 18)
    return Coach(coach_id=_cid(world_id, "player", cand["pid"]), name=cand["name"],
                 grades=grades, profile=profile, pairing=pairing,
                 temperament=temperament,
                 hometown=cand.get("hometown") or "",
                 birth_year=season_year - age, origin=origin,
                 alma=cand.get("ident", ""), player_pid=cand["pid"], created=season_year,
                 overall=overall, tier=tier)


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
        c.grades[attr] = to_q(float(grade))
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
ALUMNI_MIN_YEARS = 4          # an alumnus coaches once they are this far out

# ‼️ A STATEWIDE MARKET (owner rule 2026-09). Coaches move for jobs, so a vacancy
# draws from EVERY program, not the area: successful heads are hired away by a
# bigger or more prestigious program, assistants chase head jobs anywhere, and
# assistants step up to better programs. A new coach is the LAST RESORT — rolled
# only when no existing coach, free-pool coach or alumnus is a candidate at all.
# Hiring is a weighted draw that FAVOURS the better coach (never always the best).
HEAD_AMBITION = 0.45          # share of heads open to a step-up job this cycle
ASST_HEAD_AMBITION = 0.60     # share of assistants chasing a head job
ASST_LATERAL = 0.35           # share of assistants open to a better assistant seat
STEP_UP = 0.05                # prestige a destination must add to tempt a mover
# ‼️ NO TENURE GATE on who applies (owner report 2026-09). A two-season minimum
# shut the whole market on a save whose staffs were seated one season ago —
# every opening fell through to a new coach. Ambition alone decides who is
# looking; a head's short record already shrinks their head-experience edge.
PROMOTE_BONUS = 2.5           # weight edge for the program's OWN assistant
FREE_POOL_WEIGHT = 0.8        # an unattached coach, relative to a working one
ALUMNI_WEIGHT = 0.6           # the school's own alumnus (× 0.5 + legacy)
SAME_AREA_BONUS = 1.15        # a mild tiebreak toward nearby coaches, never a gate
QUALITY_SCALE = 8.0           # overall points per e-fold of hiring weight

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
    profile, tier, overall, grades = roll_coach(rng)
    return Coach(coach_id=_cid(world_id, "cand", season_year, tag),
                 name=roll_name(rng, gender), grades=grades, profile=profile,
                 pairing=rng.choice(PAIRINGS), temperament=rng.choice(TEMPERAMENTS),
                 hometown=school_city, birth_year=season_year - age, origin="area",
                 created=season_year, overall=overall, tier=tier)


def _quality(c: Coach) -> float:
    """The coach's caliber as a hiring program sees it: the rolled overall, or
    (a coach created before overalls existed) the mean of their grades."""
    if c.overall:
        return float(c.overall)
    return sum(to_grade(v) for v in c.grades.values()) / max(1, len(c.grades))


def _prestige(world_id: int, gender: str, schools: dict, leg: dict) -> dict:
    """{ident: 0-1} — how attractive a job is: the program's standing in its
    class on the coefficient, its SIZE (enrollment across the association) and
    its coaching legacy. A job-market reading only; nothing in a match or a
    roster reads it."""
    from . import jhsaa_coefficient as jco
    coef = _coef(world_id, gender)
    order = sorted(schools, key=lambda i: (schools[i].enrollment, i))
    n = len(order)
    size = {i: (k / (n - 1) if n > 1 else 0.5) for k, i in enumerate(order)}
    return {i: 0.45 * coef.get(i, 0.5) + 0.35 * size[i] + 0.20 * leg.get(i, 0.0)
            for i in schools}


def _coef(world_id: int, gender: str) -> dict:
    from . import jhsaa_coefficient as jco
    return jco.percentiles(world_id, gender)


def head_record(runs: dict, coef: dict, coach_id: str) -> tuple | None:
    """(win %, seasons, edge, ident) for a coach who has been a HEAD in this
    gender — their last six head seasons wherever they were — or None. The
    edge is what running a program is worth in a head-job interview."""
    last = sorted((y, w, l, i) for (i, cid), rows in runs.items() if cid == coach_id
                  for y, w, l in rows)[-6:]
    if not last:
        return None
    w = sum(x[1] for x in last)
    l = sum(x[2] for x in last)
    n = len(last)
    shrunk = (w + HEAD_RECORD_SHRINK / 2) / (w + l + HEAD_RECORD_SHRINK)
    record = 0.6 * shrunk + 0.4 * coef.get(last[-1][3], 0.5)
    edge = max(0.0, n / (n + 1) * (HEAD_EDGE + HEAD_RECORD_EDGE * (record - 0.5)))
    return (w / (w + l) if w + l else 0.5, n, edge, last[-1][3])


def _head_runs(conn, world_id: int, gender: str) -> dict:
    """{(ident, coach_id): [(year, wins, losses), …]} — every head season, one read."""
    out: dict = {}
    for ident, cid, year, w, l in conn.execute(
            "SELECT ident, coach_id, year, wins, losses FROM jhsaa_coach_history"
            " WHERE world_id=? AND gender=? AND slot='head' ORDER BY year",
            (world_id, gender)):
        out.setdefault((ident, cid), []).append((year, w or 0, l or 0))
    return out


HIRE_NOISE = 5.0              # how far one interview can misjudge a candidate
OWN_ASSISTANT_EDGE = 6.0      # continuity: the staff's own assistant is known
ALUMNUS_EDGE = 4.0            # a program likes its own coming home
AREA_EDGE = 2.0               # nearby is a little easier; never a requirement
ALUMNUS_QUALITY = 50.0        # an alumnus's ratings are unknown until hired
HEAD_SHORTLIST = 5            # sitting heads a head job always interviews
# ‼️ HEAD EXPERIENCE OUTRANKS AN ASSISTANT'S (owner rule 2026-09). For a head job
# a candidate who has RUN a program carries an edge on top of their talent —
# sized by their record, so a head of any consequence beats an assistant who has
# never run one, while a poor head can still lose to a clearly better assistant.
# The record is not just wins (they are not all equal): it blends a shrunk win %
# with the program's postseason standing (the coefficient) under them.
HEAD_EDGE = 18.0              # overall points for an average head record …
HEAD_RECORD_EDGE = 30.0       # … ± this per unit of record quality from .500
HEAD_RECORD_SHRINK = 20       # phantom .500 matches (a thin record means less)


def propose_cycle(world_id: int, season_year: int) -> dict:
    """Build (and store as PENDING) one coaching cycle, deterministic for
    (world, season).

    1. DEPARTURES — retirement by age/tenure, and the rare firing.
    2. A STATEWIDE HIRING MARKET for every vacancy, best jobs first (head seats,
       then by prestige), each hire opening the seat it came from so moves
       cascade down the ladder:
       - a head job draws applicants from the whole association: the program's
         own assistants, assistants anywhere who want a head job, and successful
         heads at LESS prestigious programs, who are hired away; plus
         free-pool coaches and one of the school's alumni. Anyone who has RUN
         a program carries an edge sized by their record (`head_record`), so
         heads are preferred and a good one beats any first-time head;
       - an assistant seat draws assistants stepping up from less prestigious
         programs, free-pool coaches and an alumnus.
       More prestigious jobs draw more applicants; the pick is the best
       interview (quality + a noisy read + small edges), so better coaches win
       more often, not always.
    3. A NEW coach only when nobody applied — the last resort."""
    from . import jhsaa
    lines = []
    free = sorted(free_pool(world_id), key=lambda c: c.coach_id)
    taken: set = set()
    conn = _conn()
    try:
        for gender in ("girls", "boys"):
            schools = {s.ident: s for s in jhsaa.load_schools(gender)}
            leg = legacy(world_id, gender)
            prest = _prestige(world_id, gender, schools, leg)
            runs = _head_runs(conn, world_id, gender)
            seat_rows = seats(world_id, gender)
            where = {}                          # coach_id -> (ident, slot, since)
            coaches = {}
            vacancies = []                      # (ident, slot)
            for r in sorted(seat_rows, key=lambda r: (r["ident"], SLOTS.index(r["slot"]))):
                ident, slot, c = r["ident"], r["slot"], r["coach"]
                if ident not in schools:
                    continue
                if c is None:                   # already vacant (a grown roster, a move)
                    vacancies.append((ident, slot))
                    continue
                where[c.coach_id] = (ident, slot, r["since"])
                coaches[c.coach_id] = c
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
                                  "why": f"age {age}, {tenure} season{'s' if tenure != 1 else ''}"
                                         " in the seat"})
                    taken.add(c.coach_id)
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
                        taken.add(c.coach_id)
                        vacancies.append((ident, "head"))

            # Who is looking this cycle — one roll per coach, so a coach is either
            # on the market or not, whichever job is open.
            def want(cid):
                return _rng("jhsaa-carousel-want", world_id, season_year, cid).random()
            wants = {cid: want(cid) for cid in where}
            coef = _coef(world_id, gender)
            by_coach: dict = {}
            for (i, cid), rows in runs.items():
                by_coach.setdefault(cid, {})[(i, cid)] = rows
            recs = {}
            for cid in set(where) | {c.coach_id for c in free}:
                if cid in by_coach:
                    recs[cid] = head_record(by_coach[cid], coef, cid)
            head_seekers = sorted(cid for cid, (i, s, _since) in where.items()
                                  if s != "head" and wants[cid] < ASST_HEAD_AMBITION)
            laterals = sorted(cid for cid, (i, s, _since) in where.items()
                              if s != "head" and wants[cid] < ASST_LATERAL)
            movers = sorted(cid for cid, (i, s, _since) in where.items()
                            if s == "head" and wants[cid] < HEAD_AMBITION)

            heap = [((slot != "head"), -prest[ident], ident, slot) for ident, slot in vacancies]
            heapq.heapify(heap)
            done = set()
            while heap:
                _h, _p, ident, slot = heapq.heappop(heap)
                if (ident, slot) in done:
                    continue
                done.add((ident, slot))
                sc = schools[ident]
                P = prest[ident]
                rng = _rng("jhsaa-carousel-fill", world_id, season_year, gender, ident, slot)
                head_job = slot == "head"
                # Applicants from elsewhere: a better job draws a longer list.
                if head_job:
                    outside = [cid for cid in head_seekers
                               if cid not in taken and where[cid][0] != ident]
                    n_app = 4 + round(16 * P)
                    # Sitting heads get their OWN shortlist seats: a program
                    # stepping up always looks at heads, who would otherwise be
                    # a handful lost among thousands of assistants.
                    heads = [cid for cid in movers if cid not in taken
                             and where[cid][0] != ident
                             and P >= prest[where[cid][0]] + STEP_UP]
                    if len(heads) > HEAD_SHORTLIST:
                        heads = rng.sample(heads, HEAD_SHORTLIST)
                else:
                    outside = [cid for cid in laterals
                               if cid not in taken and where[cid][0] != ident
                               and P >= prest[where[cid][0]] + STEP_UP]
                    n_app = 2 + round(8 * P)
                    heads = []
                if len(outside) > n_app:
                    outside = rng.sample(outside, n_app)
                outside += heads
                def talent(c):
                    """Quality, plus — for a head job — what running a program
                    is worth (a past head in an assistant's seat carries it too)."""
                    q = _quality(c)
                    rec = recs.get(c.coach_id)
                    if head_job and rec:
                        q += rec[2]
                    return q
                apps = []                        # (score, kind, coach|None, extra)
                for cid in outside:
                    c = coaches[cid]
                    i2, s2, _since = where[cid]
                    q = talent(c) + (AREA_EDGE if schools[i2].area == sc.area else 0.0)
                    apps.append((q, "hired_away" if s2 == "head" else "move", c, None))
                if head_job:
                    for cid, (i2, s2, _s) in where.items():
                        if i2 == ident and s2 != "head" and cid not in taken:
                            apps.append((talent(coaches[cid]) + OWN_ASSISTANT_EDGE,
                                         "promote", coaches[cid], None))
                pool = [c for c in free if c.coach_id not in taken]
                for c in (rng.sample(pool, 3) if len(pool) > 3 else pool):
                    apps.append((talent(c), "hire", c, None))
                alum = conn.execute(
                    "SELECT pid, name, grad_year FROM jhsaa_alumni WHERE world_id=?"
                    " AND gender=? AND ident=? AND grad_year<=? ORDER BY pid",
                    (world_id, gender, ident, season_year - ALUMNI_MIN_YEARS)).fetchall()
                alum = [a for a in alum if _cid(world_id, "player", a[0]) not in taken]
                if alum and rng.random() < 0.25 + 0.5 * leg.get(ident, 0.0):
                    a = alum[rng.randrange(len(alum))]
                    apps.append((ALUMNUS_QUALITY + ALUMNUS_EDGE, "alumnus", None, a))
                line = None
                if apps:
                    scored = [(s + rng.gauss(0.0, HIRE_NOISE), k, c, x)
                              for s, k, c, x in apps]
                    _s, kind, c, extra = max(scored, key=lambda t: (
                        t[0], t[2].coach_id if t[2] else t[3][0]))
                    if kind == "alumnus":
                        pid, nm, gy = extra
                        taken.add(_cid(world_id, "player", pid))
                        line = {"kind": "alumnus", "pid": pid, "name": nm,
                                "why": f"class of {gy} — home to coach"}
                    elif kind == "hire":
                        taken.add(c.coach_id)
                        line = {"kind": "hire", "coach_id": c.coach_id, "name": c.name,
                                "why": f"available coach, {round(_quality(c))} overall"}
                    else:
                        taken.add(c.coach_id)
                        i2, s2, _since = where[c.coach_id]
                        if kind == "promote":
                            why = "the program's own assistant"
                        elif kind == "hired_away":
                            pct, n = recs[c.coach_id][:2]
                            why = (f"head coach at {schools[i2].name},"
                                   f" {f'{pct:.3f}'.lstrip('0')} over {n} seasons")
                        elif head_job:
                            why = f"assistant at {schools[i2].name}, up to head coach"
                        else:
                            why = f"assistant at {schools[i2].name}, a step up"
                        line = {"kind": kind, "coach_id": c.coach_id, "name": c.name,
                                "why": why, "from_ident": i2, "from_slot": s2}
                        # The seat they leave is open now: the chain goes on.
                        heapq.heappush(heap, ((s2 != "head"), -prest[i2], i2, s2))
                if line is None:
                    c = _new_candidate(world_id, season_year, gender, sc.city,
                                       f"{gender}|{ident}|{slot}")
                    line = {"kind": "new", "coach": json.loads(_coach_row(c)),
                            "coach_id": c.coach_id, "name": c.name,
                            "why": f"{PROFILE_LABELS.get(c.profile, c.profile)},"
                                   f" {round(_quality(c))} overall"}
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
    # ‼️ A move that is SKIPPED (its destination is kept) leaves its coach where
    # they are, so the seat they would have left is kept too — otherwise the fill
    # proposed for it replaces an assistant who never moved and sends them to the
    # free pool. That can chain (the skipped move's source had its own fill, whose
    # coach came from somewhere else), so close the set to a fixpoint first.
    grew = True
    while grew:
        grew = False
        for ln in prop["lines"]:
            src = (ln["gender"], ln.get("from_ident"), ln.get("from_slot"))
            if (not ln["veto"] and ln.get("from_slot")
                    and (ln["gender"], ln["ident"], ln["slot"]) in kept_seat
                    and src not in kept_seat):
                kept_seat.add(src)
                grew = True
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


# ------------------------------------------------ transactions and records ----
#
# ‼️ A COACH'S TRANSACTIONS ARE HIRED / LEFT STAFF / RETIRED, NOTHING ELSE (owner
# rule 2026-09). The raw event log says "existing — on staff when coaches were
# introduced", "replaced — moved to the free pool": plumbing, not a coaching
# history. Head or assistant does not matter to the line, and going to the free
# pool is what leaving a staff MEANS, so it is never said.

_HIRE_EVENTS = ("existing", "hired", "moved", "promoted", "appointed")
_LEAVE_EVENTS = ("left", "replaced", "fired")


def transactions(events: list[dict]) -> list[dict]:
    """[{year, label, school}] from a coach's raw events, oldest first. A move
    inside ONE program in one season (assistant → head) reads as a promotion, not
    as leaving and being hired by the same school; a firing that the carousel
    wrote as retire-then-unretire reads as leaving staff, never as retiring."""
    out: list[dict] = []
    fired = {(e["year"], e.get("school")) for e in events if e["event"] == "fired"}
    for e in events:
        ev, yr, sch = e["event"], e["year"], e.get("school", "")
        if ev in _LEAVE_EVENTS:
            if ev == "fired" and any(o["label"] == "Left staff" and o["year"] == yr
                                     and o["school"] == sch for o in out):
                continue
            out.append({"year": yr, "label": "Left staff", "school": sch})
        elif ev in _HIRE_EVENTS:
            last = out[-1] if out else None
            if last and last["label"] == "Left staff" and last["year"] == yr \
                    and last["school"] == sch:
                out.pop()                       # a shuffle inside one staff
                label = "Promoted to head coach" if e.get("slot") == "head" else None
                if label:
                    out.append({"year": yr, "label": label, "school": sch})
                continue
            out.append({"year": yr, "label": "Hired", "school": sch})
        elif ev == "retired":
            if (yr, sch) in fired:
                continue
            out.append({"year": yr, "label": "Retired", "school": ""})
    return out


def program_head_coaches(world_id: int, ident: str, gender: str,
                         current_year: int) -> list[dict]:
    """Every HEAD coach in a program's history, varsity only, newest first —
    one row per consecutive run ("Janes Jacobs 2056-present"). Off the season
    history, one indexed read; the sitting head who has not coached an archived
    season yet is read off the seat."""
    from .world import BASE_YEAR
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT h.year, h.coach_id, c.name, h.wins, h.losses, h.ties"
            " FROM jhsaa_coach_history h LEFT JOIN jhsaa_coach c"
            " ON c.world_id=h.world_id AND c.coach_id=h.coach_id"
            " WHERE h.world_id=? AND h.ident=? AND h.gender=? AND h.slot='head'"
            " ORDER BY h.year", (world_id, ident, gender)).fetchall()
        seat = conn.execute(
            "SELECT s.coach_id, c.name, s.since FROM jhsaa_coach_seat s"
            " LEFT JOIN jhsaa_coach c ON c.world_id=s.world_id AND c.coach_id=s.coach_id"
            " WHERE s.world_id=? AND s.ident=? AND s.gender=? AND s.slot='head'",
            (world_id, ident, gender)).fetchone()
    finally:
        conn.close()
    runs: list[dict] = []
    for y, cid, nm, w, l, t in rows:
        season = BASE_YEAR + int(y) + 1
        if runs and runs[-1]["coach_id"] == cid and runs[-1]["last"] == season - 1:
            r = runs[-1]
            r["last"] = season
        else:
            r = {"coach_id": cid, "name": nm or "", "first": season, "last": season,
                 "w": 0, "l": 0, "t": 0}
            runs.append(r)
        r["w"] += w or 0
        r["l"] += l or 0
        r["t"] += t or 0
    if seat and seat[0]:
        cid, nm, since = seat
        if runs and runs[-1]["coach_id"] == cid:
            runs[-1]["present"] = True
        else:
            runs.append({"coach_id": cid, "name": nm or "", "first": since or current_year,
                         "last": since or current_year, "w": 0, "l": 0, "t": 0,
                         "present": True})
    for r in runs:
        r["record"] = f"{r['w']}-{r['l']}" + (f"-{r['t']}" if r["t"] else "")
        r["span"] = (f"{r['first']}-present" if r.get("present")
                     else str(r["first"]) if r["first"] == r["last"]
                     else f"{r['first']}-{str(r['last'])[-2:]}")
    return list(reversed(runs))


def coach_win_leaders(world_id: int, gender: str | None, limit: int = 100) -> list[dict]:
    """Most HEAD-COACH varsity dual wins, one sport (`gender`) or both (None —
    a coach who crossed from the girls' program to the boys' is one career).
    One grouped query."""
    from .world import BASE_YEAR
    where, args = "h.world_id=? AND h.slot='head'", [world_id]
    if gender:
        where += " AND h.gender=?"
        args.append(gender)
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT h.coach_id, c.name, c.retired, SUM(h.wins), SUM(h.losses),"
            " SUM(COALESCE(h.ties,0)), COUNT(*), MIN(h.year), MAX(h.year),"
            " GROUP_CONCAT(DISTINCT h.ident), GROUP_CONCAT(DISTINCT h.gender)"
            f" FROM jhsaa_coach_history h LEFT JOIN jhsaa_coach c"
            " ON c.world_id=h.world_id AND c.coach_id=h.coach_id"
            f" WHERE {where} GROUP BY h.coach_id"
            " ORDER BY SUM(h.wins) DESC, SUM(h.losses) ASC, c.name LIMIT ?",
            (*args, limit)).fetchall()
    finally:
        conn.close()
    names = {g: ident_names(g) for g in ("girls", "boys")}
    out = []
    for cid, nm, retired, w, l, t, n, y0, y1, idents, genders in rows:
        gs = (genders or "").split(",")
        schools = []
        for i in (idents or "").split(","):
            s = next((names[g].get(i) for g in gs if names.get(g, {}).get(i)), i)
            if s and s not in schools:
                schools.append(s)
        games = (w or 0) + (l or 0) + (t or 0)
        out.append({"coach_id": cid, "name": nm or "", "retired": bool(retired),
                    "w": w or 0, "l": l or 0, "t": t or 0, "seasons": n,
                    "pct": ((w or 0) + 0.5 * (t or 0)) / games if games else None,
                    "first": BASE_YEAR + int(y0) + 1, "last": BASE_YEAR + int(y1) + 1,
                    "schools": schools, "genders": gs})
    return out


def coach_state_titles(world_id: int, gender: str | None, minimum: int = 2) -> list[dict]:
    """Head coaches with `minimum`+ state team titles, one sport or both — the
    Repeat POY roll's idea for coaches. Reads ONLY each season's `champions`
    (json_extract, never the whole archived blob) for the seasons that have a
    coach history at all."""
    from . import world
    from .world import BASE_YEAR
    genders = [gender] if gender else ["girls", "boys"]
    conn = _conn()
    try:
        titles: dict = {}
        for g in genders:
            heads = season_heads(world_id, g)
            if not heads:
                continue
            years = sorted({y for y, _i in heads})
            inv = {nm: i for i, nm in ident_names(g).items()}
            for y in years:
                r = conn.execute(
                    "SELECT json_extract(data, '$.champions') FROM world_jhsaa"
                    " WHERE world_id=? AND year=? AND gender=?",
                    (world_id, y, g)).fetchone()
                if not r or not r[0]:
                    continue
                champs = world._relabel({"champions": json.loads(r[0])})["champions"]
                for grp, nm in (champs or {}).items():
                    head = heads.get((y, inv.get(nm)))
                    if not head:
                        continue
                    t = titles.setdefault(head["coach_id"], {
                        "coach_id": head["coach_id"], "name": head["name"], "won": []})
                    t["won"].append({"season_year": BASE_YEAR + int(y) + 1,
                                     "group": grp, "school": nm, "gender": g})
    finally:
        conn.close()
    out = [t for t in titles.values() if len(t["won"]) >= minimum]
    for t in out:
        t["won"].sort(key=lambda a: a["season_year"])
        t["count"] = len(t["won"])
    out.sort(key=lambda t: (-t["count"], -t["won"][-1]["season_year"], t["name"]))
    return out


def program_heads_by_year(world_id: int, ident: str, gender: str) -> dict:
    """{world_year: {"coach_id", "name"}} — the program's HEAD coach each archived
    season, for the Seasons ledger's coach column. One indexed read; a season
    before coaches existed has no row and its cell stays blank."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT h.year, h.coach_id, c.name FROM jhsaa_coach_history h"
            " LEFT JOIN jhsaa_coach c ON c.world_id=h.world_id AND c.coach_id=h.coach_id"
            " WHERE h.world_id=? AND h.ident=? AND h.gender=? AND h.slot='head'",
            (world_id, ident, gender)).fetchall()
    finally:
        conn.close()
    return {y: {"coach_id": cid, "name": nm or ""} for y, cid, nm in rows if cid}

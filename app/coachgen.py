"""Deterministic coach generation, engine-side so both the web staff view and
the rollover coach carousel create identical coaches and share one persisted
identity (app.coachreg). The persisted entity is authoritative once it exists —
generation only supplies a coach the first time a seat is filled."""
from __future__ import annotations

import random

from app import coachreg, ncaa, worldconfig
from app.coaches import generate_coach
from generators import make_name_picker

ARCHETYPE_LABELS = {
    "coaching_lifer": "Coaching Lifer",
    "former_pro": "Former Pro",
    "recruiting_closer": "Recruiting Closer",
    "development_guru": "Development Guru",
    "tactician": "Tactician",
}

ROLE_TITLES = {"head": "Head Coach", "assoc": "Associate Head Coach", "asst": "Assistant Coach"}
_ROLE_BUMP = {"head": 4.0, "assoc": -2.0, "asst": -6.0}


def _generate(school: str, gender: str, role: str, base: float):
    # Coaches are former players of this tennis world, so draw their identity
    # from the same international pool the players come from (tennis_global) and
    # — crucially — keep the picker's nation so the name and home country stay
    # culturally coherent (a "Đặng Oanh" is from VN, not a random ARG).
    name_fn = make_name_picker(random.Random(f"coachname|{role}|{school}|{gender}"),
                               gender="mixed", region_weights=worldconfig.region_weights())
    nm, country = name_fn()
    return generate_coach(random.Random(f"coach|{role}|{school}|{gender}"), nm,
                          school=school, base=base, home_country=country or None)


def ensure(division: str, gender: str, school: str, role: str) -> dict:
    """Return the persisted coach record for this seat, generating + registering
    a coach the first time the seat is filled. Idempotent."""
    div = ncaa.load_division(division, gender)
    prog = div.by_school(school)
    base = 50.0 + (12.0 * prog.strength if prog else 0.0)
    c = _generate(school, gender, role, base=max(28.0, base + _ROLE_BUMP[role]))
    dev, rec, tac = round(c.development_score), round(c.recruiting_score), round(c.tactical_score)
    tenure = random.Random(f"tenure|{school}|{gender}|{role}").randint(1, 14 if role == "head" else 8)
    archetype = ARCHETYPE_LABELS.get(c.archetype, c.archetype.replace("_", " ").title())
    return coachreg.ensure_seat(division, gender, school, role, name=c.name,
                                home_country=c.home_country, archetype=archetype,
                                dev=dev, rec=rec, tac=tac, tenure=tenure)

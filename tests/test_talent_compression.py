"""Ceiling compression (owner rule 2026-08, `development.compress_talent`).

The universe was tuned at 100-200 schools; at ~850 programs plus the national
pool the unchanged distributions piled the tail onto the 80 clamp. Ordinary
ceilings now squash toward UTR 13 (boys) / 11 (girls); a 1-in-500 elite roll
is exempt and keeps the old sky. Era-gated in the JHSAA (`talent_era`) so
archived rosters keep their numbers byte-for-byte.
"""
import pytest

from app.development import (compress_talent, elite_talent, TALENT_KNEE,
                             TALENT_CAP, ELITE_TALENT_RATE, _ATTR_LIFT)


def _non_elite_key():
    for i in range(10_000):
        k = ("probe", i)
        if not elite_talent(k):
            return k
    raise AssertionError("no non-elite key in 10k probes")


def _elite_key():
    for i in range(10_000):
        k = ("probe", i)
        if elite_talent(k):
            return k
    raise AssertionError("no elite key in 10k probes")


def test_identity_below_the_knee():
    # The squash runs in INPUT-talent space, aimed _ATTR_LIFT below the
    # displayed targets (attribute noise lifts the visible ceiling that far).
    for sex in ("male", "female"):
        knee = TALENT_KNEE[sex] - _ATTR_LIFT
        assert compress_talent(knee - 5, sex) == knee - 5
        assert compress_talent(30.0, sex) == 30.0


def test_squash_is_monotonic_and_capped():
    k = _non_elite_key()
    for sex in ("male", "female"):
        cap = TALENT_CAP[sex] - _ATTR_LIFT
        vals = [compress_talent(x, sex, key=k) for x in range(20, 81)]
        assert all(b >= a for a, b in zip(vals, vals[1:]))       # order survives
        assert max(vals) < cap + 0.01                            # asymptote
        # an 80 draw lands near the cap, not near the knee
        assert vals[-1] > cap - 1.5


def test_elite_keeps_the_old_sky():
    k = _elite_key()
    assert compress_talent(78.0, "male", key=k) == 78.0
    assert compress_talent(78.0, "female", key=k) == 78.0
    assert compress_talent(85.0, "male", key=k) == 80.0          # legacy clamp


def test_elite_rate_is_about_one_in_five_hundred():
    n = 100_000
    hits = sum(1 for i in range(n) if elite_talent(("rate", i)))
    assert n * ELITE_TALENT_RATE * 0.6 <= hits <= n * ELITE_TALENT_RATE * 1.5


def test_gender_labels_normalise():
    # boys/men/male one band; girls/women/female the other.
    for g in ("boys", "men", "male"):
        assert compress_talent(80.0, g, key=_non_elite_key()) == \
               compress_talent(80.0, "male", key=_non_elite_key())
    for g in ("girls", "women", "female"):
        assert compress_talent(80.0, g, key=_non_elite_key()) == \
               compress_talent(80.0, "female", key=_non_elite_key())


# --- the JHSAA era gate --------------------------------------------------------

def _roster(school, year, salt=""):
    from app import jhsaa as jh
    return jh.build_roster(school, year, salt)


def test_jhsaa_new_era_is_compressed_and_pre_era_is_not(monkeypatch):
    from app import jhsaa as jh
    school = next(s for s in jh.load_schools("boys") if s.talent_group == "9A")
    cap = TALENT_CAP["male"]

    # Everyone pre-era: the legacy draw, byte-identical — ceilings may exceed
    # the cap (a 9A band at N(59.4, 14.4) puts a big share above it).
    monkeypatch.setattr(jh, "talent_era", lambda: 9999)
    jh._roster_cache.clear() if hasattr(jh, "_roster_cache") else None
    legacy = {p.pid: p.ceiling_overall() for p in _roster(school, 2050)}

    # Everyone new-era: no non-elite ceiling above the cap (attribute ceilings
    # scatter ~N(talent, 6) around the compressed centre, so allow that noise),
    # and the two eras genuinely differ.
    monkeypatch.setattr(jh, "talent_era", lambda: 0)
    new = {}
    for p in _roster(school, 2050):
        new[p.pid] = p.ceiling_overall()
        if p.ceiling_overall() > cap + 8:
            key = ("jhsaa-elite", school.ident, school.gender, p.entry_year,
                   jh.resolve_seat(school, p.entry_year, p.pid))
            assert elite_talent(key), (p.name, p.ceiling_overall())
    assert legacy.keys() == new.keys()          # same people either era
    assert any(legacy[k] != new[k] for k in legacy)   # the squash is real
    assert max(new.values()) < max(max(legacy.values()), cap + 8.01)


def test_recruit_pool_is_compressed():
    import random
    from app.juniors import generate_class
    from app.development import TALENT_CAP
    cls = generate_class(random.Random(7), n=400, grad_year=2051,
                         gender="male", talent_mean=60.0, talent_sd=14.0)
    over = [p for p in cls.recruits
            if p.ceiling_overall() > TALENT_CAP["male"] + 8]
    # a hot N(60,14) pool would land dozens above the cap; compressed, only the
    # rare elite (plus attribute noise) can be up there
    assert len(over) <= 4, [round(p.ceiling_overall(), 1) for p in over]

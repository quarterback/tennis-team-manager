"""THE INDIVIDUAL PARTICIPATION RULE (JHSAA rule 2101, owner spec 2026-09).

24 regular-season competition dates per player across V1/V2/V3/JV, one level per
date, the postseason exempt. See `docs/AAR-jhsaa-participation-limit.md`.
"""
import datetime as dt
import random

import pytest

import app.jhsaa as jh
import app.world as world


def _slice(gender="girls", groups=("1A", "5A"), per=2, salt="partest"):
    return {g: {n: jh.district_teams(ss, 0, salt)
                for n, ss in sorted(jh.districts(gender, g).items())[:per]}
            for g in groups}


def _teams(by_group):
    return [t for st in by_group.values() for ts in st.values() for t in ts]


# --- the budget --------------------------------------------------------------

def test_a_date_is_charged_once_per_key_and_once_per_dual():
    t = _teams(_slice(groups=("1A",), per=1))[0]
    top = t.roster[:3]
    jh._use_date(t, top)
    jh._use_date(t, top)
    assert all(jh.dates_left(t, p) == jh.PARTICIPATION_LIMIT - 2 for p in top)
    assert t.dates_played == 2
    jh._use_date(t, top[:2], key=("sc", 1))
    jh._use_date(t, top, key=("sc", 1))           # same showcase day: one date
    assert jh.dates_left(t, top[0]) == jh.PARTICIPATION_LIMIT - 3
    assert jh.dates_left(t, top[2]) == jh.PARTICIPATION_LIMIT - 3
    assert t.dates_played == 3


def test_a_spent_player_sits_and_a_short_one_rests_against_a_weaker_side():
    a, b = _teams(_slice(groups=("1A",), per=1))[:2]
    order = jh._healthy(a, jh._order(a))
    need = jh.lineup_need("regular", a.school.group)
    star = order[0]
    a.dates[star.pid] = jh.PARTICIPATION_LIMIT
    assert star not in jh._within_limit(a, order)
    a.dates[star.pid] = jh.PARTICIPATION_LIMIT - 2
    a.dates_planned, a.dates_played = 10, 0        # ten to go, two left
    strong, weak = (a, b) if jh._strength(a) >= jh._strength(b) else (b, a)
    if strong is not a:
        a, b = strong, weak
        order = jh._healthy(a, jh._order(a))
        star = order[0]
        a.dates[star.pid] = jh.PARTICIPATION_LIMIT - 2
        a.dates_planned, a.dates_played = 10, 0
    kept = jh._within_limit(a, order, b, need)
    assert star not in kept and len(kept) >= need
    # never below the lineup, and never against a stronger side
    a.dates_planned = 0
    assert star in jh._within_limit(a, order, b, need)


def test_jv_is_staffed_from_the_players_with_dates_left():
    t = _teams(_slice(groups=("5A",), per=1))[0]
    pool = jh.jv_pool(t)
    assert pool and jh.jv_available(t) == pool
    t.dates[pool[0].pid] = jh.PARTICIPATION_LIMIT
    assert pool[0] not in jh.jv_available(t)
    assert jh.jv_spare(t) == len(pool) - 1
    assert pool[0] not in jh.squad_pool(t, "V2")


def test_the_kill_switch_restores_the_old_staffing(monkeypatch):
    t = _teams(_slice(groups=("5A",), per=1))[0]
    pool = jh.jv_pool(t)
    t.dates[pool[0].pid] = jh.PARTICIPATION_LIMIT
    monkeypatch.setattr(jh, "PARTICIPATION_ENABLED", False)
    assert jh.jv_available(t) == pool
    assert jh._within_limit(t, pool) == pool


# --- a season ----------------------------------------------------------------

@pytest.fixture(scope="module")
def season():
    by_group = _slice(groups=("1A", "2A"), per=2)
    teams, _ = jh.play_regular_season(by_group, 0, "girls", "partest")
    jv = jh.play_jv_season(by_group, 0, "girls", "partest")
    return by_group, teams, jv


def _dressed(t, jv):
    """{name: regular-season dates} off the ledger, every level, a showcase day
    folded to one date — the archive's view, independent of the counters."""
    out: dict = {}
    seen: dict = {}
    for row in t.schedule + jv[t.school.name].schedule:
        if row["phase"] in jh.POSTSEASON:
            continue
        names = (set(row.get("played") or [])
                 | {n for ln in row["lines"] for n in ln["home" if row["home"] else "away"]})
        key = (row["phase"], row["opp"]) if row["phase"] in jh.SHOWCASE else id(row)
        for n in names:
            if seen.get(n) != key:
                out[n] = out.get(n, 0) + 1
                seen[n] = key
    return out


def test_nobody_exceeds_the_limit_across_levels_and_the_counters_match(season):
    by_group, teams, jv = season
    for t in teams:
        assert max(t.dates.values(), default=0) <= jh.PARTICIPATION_LIMIT
        plain = sum(1 for r in t.schedule if r["phase"] not in jh.POSTSEASON
                    and r["phase"] not in jh.SHOWCASE)
        assert plain <= t.dates_played <= plain + 2       # + at most one showcase weekend
        led = _dressed(t, jv)
        assert max(led.values(), default=0) <= jh.PARTICIPATION_LIMIT + 1, (t.school.name, led)
    # the rule bites somewhere: somebody in the slice used most of the budget
    assert any(max(t.dates.values(), default=0) >= 20 for t in teams)


# --- the calendar: JV shares the varsity dates ------------------------------------

def test_the_jv_calendar_shares_varsity_dates_and_keeps_each_school_in_order():
    """Owner rule 2026-10: JV plays on the same days as varsity — "they just can't
    use the same players", which is the lineup rule (2101), not a calendar rule.
    So the JV layout takes no varsity busy set; what it owes is a date inside the
    sport's window, on a JV day, and each school's own JV card in order."""
    year = 2101
    out = {}
    # a varsity Saturday for A — nothing stops a JV dual landing on it
    out[("v", "regular", 1, "A", "X")] = dt.date(year, 4, 4)
    jv_keys = [("jv", "regular", 1, "A", "B"), ("jv", "regular", 1, "A", "C"),
               ("jv", "regular", 0, "B", "C"), ("jv", "regular", 1, "C", "D"),
               ("jv", "showcase_pod", 0, "A", "D"), ("jv", "showcase_pod", 0, "A", "B"),
               ("jv", "jv_state", 0, "A", "C")]
    by_school = {}
    for k in jv_keys:
        by_school.setdefault(k[3], []).append(k)
        by_school.setdefault(k[4], []).append(k)
    seen = {k: i for i, k in enumerate(jv_keys)}
    world._jh_jv_dates(out, by_school, seen, "girls", year)
    mon, day = world._JH_JV_OPEN["girls"]
    mon_c, day_c = world._JH_SEASON_CLOSE["girls"]
    opening = dt.date(year, mon, day)
    close = dt.date(year, mon_c, day_c) + dt.timedelta(days=world._JH_CLOSE_GRACE)
    for k in jv_keys:
        # a league dual and the championship are always dated; an ancillary dual
        # (invitational, showcase) may go UNDATED rather than push the window
        if k[2] or k[1] == "jv_state":
            assert k in out, k
        if k in out:
            assert opening <= out[k] <= close, (k, out[k])
            assert out[k].weekday() in world._JH_JV_DAYS, (k, out[k])
    # a school's own card never reads backwards, and the championship is last
    for s, keys in by_school.items():
        dates = [out[k] for k in sorted(keys, key=seen.get) if k in out]
        assert dates == sorted(dates), (s, dates)
    assert out[("jv", "jv_state", 0, "A", "C")] >= max(
        out[k] for k in jv_keys if k[1] != "jv_state" and k in out)
    # the varsity date was never a constraint on the JV layout
    assert out[("v", "regular", 1, "A", "X")] == dt.date(year, 4, 4)

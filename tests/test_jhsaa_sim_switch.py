"""The JHSAA sim is SEPARATE from the college game (owner rule 2026-11).

Measured before the rule: the week-0 high-school step took ~18 minutes on the
request thread, and the college recruit board then REPLAYED the whole season in a
fresh process (~8 minutes a gender) to put names on ~200 Jefferson recruits. A new
college save was ~26 minutes from its first click to its first dual.

`worldconfig.jhsaa_sim()` is the per-save switch and it is OFF unless a save turns
it on. Off:
  - `world.advance_week` has no JHSAA rung and no JHSAA holds;
  - `world.recruit_class` never touches `jhsaa.apply_to_class` (the replay) —
    Jefferson recruits keep their generated identity and get a real, current
    JHSAA school (`jhsaa.assign_real_schools`).
"""
import pytest

import app.world as wd
import app.worldconfig as wc
from app import jhsaa


def _world(year=0, week=0, wid=1):
    return {"id": wid, "year": year, "week": week, "seed": 2026}


def _drop(salt):
    """Evict every class this test built. By SALT, not by a retyped key:
    `recruit_class` canonicalises the gender, so ("…", "men", year) names nothing."""
    for key in [k for k in list(wd._class_cache) if k[0] == salt]:
        wd._class_cache.pop(key, None)


@pytest.fixture
def week_zero(monkeypatch):
    """A world sitting at week 0 with everything AFTER the JHSAA steps stubbed, so
    the test sees only whether those steps fired."""
    fired = []
    monkeypatch.setattr(wd, "get_or_create", lambda *a, **k: _world(year=1))
    monkeypatch.setattr(wd, "_all_complete", lambda *a, **k: False)
    monkeypatch.setattr(wd, "jhsaa_done", lambda w: False)
    monkeypatch.setattr(wd, "run_jhsaa",
                        lambda seed, w: fired.append("jhsaa") or {"event": "jhsaa"})
    monkeypatch.setattr(wd, "pros_rolled", lambda w: False)
    monkeypatch.setattr(wd, "run_pro_offseason",
                        lambda seed=2026, world=None: fired.append("pros")
                        or {"event": "pro_offseason"})
    from app import jhsaa_reclass as rc, jhsaa_portal as jp
    monkeypatch.setattr(rc, "pending", lambda wid: fired.append("reclass") or None)
    monkeypatch.setattr(rc, "due", lambda w: False)
    monkeypatch.setattr(jp, "check_hold", lambda w, **k: fired.append("portal") or None)
    return fired


def test_the_switch_is_off_unless_a_save_turns_it_on(monkeypatch):
    monkeypatch.setattr(wc, "get", lambda k: "")
    assert wc.jhsaa_sim() is False
    monkeypatch.setattr(wc, "get", lambda k: "on" if k == "jhsaa_sim" else "")
    assert wc.jhsaa_sim() is True


def test_the_college_advance_has_no_jhsaa_step_or_hold(monkeypatch, week_zero):
    """Off: week 0 goes straight to the next COLLEGE step. Neither the rung nor
    either hold is even consulted — a hold nobody asked for is still a click."""
    monkeypatch.setattr(wc, "jhsaa_sim", lambda: False)
    assert wd.advance_week()["event"] == "pro_offseason"
    assert week_zero == ["pros"]


def test_a_simulating_save_still_plays_the_season_first(monkeypatch, week_zero):
    """On: the combined world is unchanged — holds consulted, then the rung, and
    nothing college before it."""
    monkeypatch.setattr(wc, "jhsaa_sim", lambda: True)
    assert wd.advance_week()["event"] == "jhsaa"
    assert week_zero == ["reclass", "portal", "jhsaa"]


def test_the_rung_drops_a_board_built_before_its_seniors_played(monkeypatch, week_zero):
    """A class cached before the season was archived holds generated recruits; the
    rung evicts THAT year's classes (per key — other years stay) so the next read
    hands the board the seniors who just graduated."""
    monkeypatch.setattr(wc, "jhsaa_sim", lambda: True)
    this_year, other_year = wd.BASE_YEAR + 2, wd.BASE_YEAR + 9
    wd._class_cache[("s", "men", this_year)] = object()
    wd._class_cache[("s", "women", this_year)] = object()
    wd._class_cache[("s", "men", other_year)] = keep = object()
    try:
        wd.advance_week()
        assert ("s", "men", this_year) not in wd._class_cache
        assert ("s", "women", this_year) not in wd._class_cache
        assert wd._class_cache[("s", "men", other_year)] is keep
    finally:
        wd._class_cache.pop(("s", "men", other_year), None)


@pytest.fixture
def no_replay(monkeypatch):
    """Any path that reaches the season simulator from the recruit board fails."""
    def boom(*a, **k):
        raise AssertionError("the college recruit board replayed a JHSAA season")
    monkeypatch.setattr(jhsaa, "run_season", boom)
    monkeypatch.setattr(jhsaa, "graduating_class", boom)


@pytest.mark.parametrize("gender", ["men", "women"])
def test_jefferson_recruits_get_a_real_current_school_and_no_season(
        monkeypatch, no_replay, gender):
    monkeypatch.setattr(wc, "jhsaa_sim", lambda: False)
    grad_year, salt = wd.BASE_YEAR + 1, f"sim-switch-{gender}"
    _drop(salt)
    klass = wd.recruit_class(gender, grad_year, salt)
    try:
        jf = [p for p in klass.recruits if p.region == "Jefferson"]
        assert jf, "the national class drew no Jefferson recruits"
        schools = [s for s in jhsaa.load_schools(jhsaa._GENDER[gender]) if not s.state]
        names = {s.name for s in schools}
        town_of = {}
        for s in schools:
            town_of.setdefault(s.name, set()).add(s.city)
        for p in jf:
            assert p.high_school in names, f"{p.high_school!r} is not a current program"
            # They live where a school they could attend stands.
            city, st = p.hometown.rsplit(", ", 1)
            assert st == "JF" and city in town_of[p.high_school]
            # No high-school record, because no season was played.
            assert not p.jhsaa
        # Not one school handed to the whole state.
        assert len({p.high_school for p in jf}) > len(jf) // 3
    finally:
        _drop(salt)


def test_the_school_assignment_changes_nothing_about_who_the_recruits_are(
        monkeypatch, no_replay):
    """Identity, ability and pid are the national class's. Only `high_school` and
    (when the town has no program) `hometown` move, and only for Jefferson — so the
    class's size, talent spread and every other state's recruits are untouched."""
    monkeypatch.setattr(wc, "jhsaa_sim", lambda: False)
    grad_year, salt = wd.BASE_YEAR + 1, "sim-switch-identity"

    def build(assign):
        _drop(salt)
        with monkeypatch.context() as m:
            if not assign:
                m.setattr(jhsaa, "assign_real_schools", lambda *a, **k: 0)
            k = wd.recruit_class("women", grad_year, salt)
        _drop(salt)
        return [(p.pid, p.name, p.region, round(p.current_overall(), 6),
                 p.recruit_rank, p.hometown, p.high_school) for p in k.recruits]

    bare, placed = build(False), build(True)
    assert len(bare) == len(placed)
    for b, a in zip(bare, placed):
        assert b[:5] == a[:5]                       # pid, name, state, ability, rank
        if b[2] != "Jefferson":
            assert b == a
    assert build(True) == placed                    # and it is the same every build


def test_a_simulating_save_reads_seniors_only_once_their_season_is_archived(monkeypatch):
    """On is not enough: `apply_to_class` gets its seniors by REPLAYING the season,
    so it is only reached for a class whose season the save has archived."""
    monkeypatch.setattr(wc, "jhsaa_sim", lambda: True)
    calls = []
    monkeypatch.setattr(jhsaa, "apply_to_class",
                        lambda klass, g, gy, salt: calls.append("seniors") or 0)
    monkeypatch.setattr(jhsaa, "assign_real_schools",
                        lambda klass, g, gy, salt: calls.append("schools") or 0)
    grad_year, salt = wd.BASE_YEAR + 1, "sim-switch-archived"
    for archived, expect in ((False, "schools"), (True, "seniors")):
        monkeypatch.setattr(wd, "_jhsaa_archived_for", lambda gy, a=archived: a)
        _drop(salt)
        wd.recruit_class("men", grad_year, salt)
        assert calls[-1] == expect
    _drop(salt)


# --- a build already under way must not undo the rung's invalidation -----------

def test_a_class_built_across_the_archive_is_not_published_stale(monkeypatch):
    """The race: a board build starts BEFORE the season is archived (so it takes the
    generated-recruits path), the rung finishes and evicts the year, and the build
    then finishes. Stored, that pre-archive class would outlive the eviction for the
    rest of the process. It must be thrown away and rebuilt from the archive."""
    monkeypatch.setattr(wc, "jhsaa_sim", lambda: True)
    grad_year, salt = wd.BASE_YEAR + 1, "sim-switch-race"
    state = {"archived": False}
    monkeypatch.setattr(wd, "_jhsaa_archived_for", lambda gy: state["archived"])

    def generated(klass, g, gy, s):
        klass.source = "generated"
        # …and while this build is still running, the rung archives the season
        # and evicts the year — exactly once.
        if not state["archived"]:
            state["archived"] = True
            wd._forget_recruit_classes(gy)
        return 0

    def seniors(klass, g, gy, s):
        klass.source = "seniors"
        return 0

    monkeypatch.setattr(jhsaa, "assign_real_schools", generated)
    monkeypatch.setattr(jhsaa, "apply_to_class", seniors)
    _drop(salt)
    try:
        klass = wd.recruit_class("men", grad_year, salt)
        assert klass.source == "seniors"              # the caller gets the real class
        cached = [v for k, v in wd._class_cache.items() if k[0] == salt]
        assert cached == [klass]                      # and that is what was stored
        assert wd.recruit_class("men", grad_year, salt) is klass
    finally:
        _drop(salt)


def test_pool_results_that_crossed_an_invalidation_are_dropped(monkeypatch):
    """The parallel path has the same race: `prime_recruit_classes` launches
    workers that read the archive when they START, and publishes when they return.
    If the year was invalidated in between, nothing is published."""
    import app.parallel as parallel
    grad_year, salt = wd.BASE_YEAR + 1, "sim-switch-pool"
    monkeypatch.setattr(wd, "active_salt", lambda seed=wd.DEFAULT_SEED: salt)
    monkeypatch.setattr(wd, "_active_unis", lambda: [("D1", "men"), ("D1", "women")])
    monkeypatch.setattr(parallel, "workers_for", lambda n, **k: 2)
    monkeypatch.setattr(wc, "snapshot", lambda: {})

    def run(invalidate):
        def fake_pmap(fn, tasks, workers=None):
            if invalidate:                            # the rung lands mid-flight
                wd._forget_recruit_classes(grad_year)
            return [(g, gy, []) for (_salt, _cfg, g, gy) in tasks]
        monkeypatch.setattr(parallel, "pmap", fake_pmap)
        _drop(salt)
        wd.prime_recruit_classes(wd.DEFAULT_SEED, 0)
        return sorted(k[1] for k in wd._class_cache if k[0] == salt)

    try:
        assert len(run(invalidate=False)) == 2        # the ordinary case still stores
        assert run(invalidate=True) == []             # a crossed result does not
    finally:
        _drop(salt)

"""Named JHSAA coaching staffs (owner spec 2026-09, `app/jhsaa_coaches.py`).

Every coach's grades and philosophies ROLL AT RANDOM, inaugural staffs included
(owner rule 2026-09) — nothing reproduces the school draws the association used
before coaches existed, and nothing needs the owner's input after an update:
`ensure_staff` seats every program the first time the rung runs.
"""
import json

import pytest

from app import jhsaa as jh
from app import jhsaa_coaches as jc
from app import world as wd
from app.web.server import create_app


# --- the model, as pure functions ------------------------------------------------

def _sample(n=120):
    out = []
    for g in ("girls", "boys"):
        out += jh.load_schools(g)[:n]
    return out


def test_every_inaugural_grade_and_philosophy_rolls_at_random():
    """No attribute is pinned: the head coaches' grades spread across the scale
    for EVERY attribute (none sits on one value), and philosophies vary."""
    from collections import Counter
    heads = [jc.inaugural_staff(s, 1, "", 2030)[0] for s in _sample()]
    for a in jc.GRADES:
        vals = {h.grade(a) for h in heads}
        assert len(vals) > 15, (a, sorted(vals))
        assert 30 < sum(h.grade(a) for h in heads) / len(heads) < 62
    assert len(Counter(h.pairing for h in heads)) == len(jc.PAIRINGS)
    assert len(Counter(h.temperament for h in heads)) == len(jc.TEMPERAMENTS)


def test_the_blend_covers_weak_spots_and_never_exceeds_the_best_coach():
    def coach(v):
        return jc.Coach(coach_id="x", name="x", grades={a: v for a in jc.GRADES})
    weak, strong, poor = coach(0.2), coach(0.9), coach(0.1)
    eff = jc.effective(weak, [strong])
    for a in jc.BLENDED:
        assert 0.2 < eff[a] < 0.9
        assert eff[a] == pytest.approx(0.2 + jc.COVER * 0.7)
    for a in jc.HEAD_ONLY:
        assert eff[a] == 0.2                     # the head's alone
    # a weak assistant never lowers the head
    assert jc.effective(strong, [poor]) == {a: 0.9 for a in jc.GRADES}


def test_seats_scale_with_roster_size():
    assert jc.assistants_for(14) == 1
    assert jc.assistants_for(19) == 1
    assert jc.assistants_for(20) == 2
    assert jc.assistants_for(27) == 2
    assert jc.assistants_for(28) == 3
    assert jc.assistants_for(40) == jc.MAX_ASSISTANTS == 3


def test_grades_are_imprinted_in_range_and_deterministic():
    s = _sample(1)[0]
    a = jc.inaugural_staff(s, 2, "salt", 2030)
    b = jc.inaugural_staff(s, 2, "salt", 2030)
    assert [c.grades for c in a] == [c.grades for c in b]
    assert [c.name for c in a] == [c.name for c in b]
    for c in a:
        for v in c.grades.values():
            assert 0.0 <= v <= 1.0


# --- Stage B, as pure functions -----------------------------------------------------

def test_the_changeover_roll_never_touches_set_one_and_is_inert_at_zero():
    import random
    from engine.state import random_player
    from engine.fast import simulate_fast, HS_PROFILE
    from engine.format import PRESETS
    fmt = PRESETS["high_school"]
    changed = 0
    for i in range(150):
        rng = random.Random(i)
        a, b = random_player(rng, "a"), random_player(rng, "b")
        base = simulate_fast(a, b, seed=i, fmt=fmt, profile=HS_PROFILE)
        off = simulate_fast(a, b, seed=i, fmt=fmt,
                            profile={**HS_PROFILE, "co_q": (0.9, 0.1), "co_k": 0.0})
        assert off.set_scores == base.set_scores and off.game_flow == base.game_flow
        on = simulate_fast(a, b, seed=i, fmt=fmt,
                           profile={**HS_PROFILE, "co_q": (0.9, 0.1), "co_k": 0.8})
        assert on.set_scores[0] == base.set_scores[0]      # rolls at set BREAKS only
        changed += on.set_scores != base.set_scores
    assert changed > 0


def test_a_stage_a_history_row_reads_neutral():
    """A season archived before Stage B carries only the lens/culture/strategy —
    it must read back with no development, clutch or changeover effect."""
    old = '{"read": 1.0, "trust": 1.1, "form": 1.1, "culture": 1.0, "strategy": "balanced"}'
    e = jc._eff_from_json(old)
    assert e.dev == 1.0 and e.lean == 0.0 and e.clutch is None and e.changeover is None
    assert e.feeder == 0.5 and e.builder == 0.5 and e.temperament == "steady"


def test_neutral_staff_history_leaves_rosters_identical(monkeypatch):
    s = jh.load_schools("girls")[5]
    base = [(p.pid, p.current_overall()) for p in jh.build_roster(s, 2032, "")]
    lens = jh.coach_lens(s.name, "")
    neutral = {y: jc.StaffEffect(lens=lens, culture=1.0, strategy="balanced")
               for y in range(2026, 2032)}
    monkeypatch.setattr(jh, "staff_history", lambda g, i: neutral)
    assert [(p.pid, p.current_overall()) for p in jh.build_roster(s, 2032, "")] == base
    strong = {y: jc.StaffEffect(lens=lens, culture=1.0, strategy="balanced", dev=1.2)
              for y in range(2026, 2032)}
    monkeypatch.setattr(jh, "staff_history", lambda g, i: strong)
    up = dict((p.pid, p.current_overall()) for p in jh.build_roster(s, 2032, ""))
    assert sum(up[pid] - v for pid, v in base) > 0


def test_mentorship_pairs_old_with_young_and_keeps_the_singles():
    s = jh.load_schools("girls")[5]
    ros = jh.build_roster(s, 2032, "")[:11]
    out = jh._arrange_regular(ros, "mentorship")
    assert out[:3] == ros[:3]
    assert sorted(p.pid for p in out) == sorted(p.pid for p in ros)
    assert jh._flip_strategy("mentorship") == "balanced"


def test_mentorship_grows_the_underclassmen_who_played(monkeypatch):
    """Under a mentorship head, a freshman/sophomore who dressed that season banks
    extra growth; nobody loses any, and a season nobody dressed in gives nothing."""
    s = jh.load_schools("girls")[5]
    lens = jh.coach_lens(s.name, "")
    years = range(2026, 2032)
    # Every prior season archived, everyone fully played.
    monkeypatch.setattr(jh, "school_exposure", lambda g, n, ys: {y: {} for y in ys})
    monkeypatch.setattr(jh, "_expo_factor", lambda season, name: 1.0)

    def build(strategy):
        hist = {y: jc.StaffEffect(lens=lens, culture=1.0, strategy=strategy) for y in years}
        monkeypatch.setattr(jh, "staff_history", lambda g, i: hist)
        return {p.pid: (p.grade, p.current_overall()) for p in jh.build_roster(s, 2032, "")}
    base, mentored = build("balanced"), build("mentorship")
    assert base.keys() == mentored.keys()
    for pid, (grade, ovr) in base.items():
        assert mentored[pid][1] >= ovr - 1e-9          # never lowers anyone
        if grade == 9:
            assert mentored[pid][1] == ovr             # no season behind them yet
    assert any(mentored[p][1] > base[p][1] for p in base if base[p][0] >= 10)
    # …and a season nobody dressed in (the exposure floor) gives nothing.
    monkeypatch.setattr(jh, "_expo_factor", lambda season, name: jh.EXPO_FLOOR)
    idle_base, idle_mentored = build("balanced"), build("mentorship")
    assert idle_base == idle_mentored


# --- a real season ----------------------------------------------------------------

def _small(real_load):
    def small(gender):
        out = []
        for grp in jh.GROUPS:
            names = sorted({s.district for s in real_load(gender) if s.group == grp})
            keep, pool = set(), []
            for name in names:
                keep.add(name)
                pool = [s for s in real_load(gender)
                        if s.group == grp and s.district in keep]
                if len(pool) > jh.PROTECTED + 8:
                    break
            out += pool
        return out
    return small


def _digest(season) -> str:
    rows = []
    for name, t in sorted(season["teams"].items()):
        rows.append([name, t.record, [(d["opp"], d["phase"], d["pf"], d["pa"],
                                       d["won"], json.dumps(d.get("lines"), sort_keys=True,
                                                            default=str))
                                      for d in t.schedule]])
    return json.dumps(rows, default=str)


def test_a_history_read_that_races_an_invalidation_is_never_cached(monkeypatch):
    """The threaded worker: `record_season` clears the staff history inside the
    rung's transaction, and a reader querying between that clear and the commit
    sees the OLD history. It may return it, but must never cache it — or the next
    season builds without the year just archived."""
    jh.invalidate_staff_history()

    def racing(_db):
        jh.invalidate_staff_history()          # the rung, mid-read
        return None
    monkeypatch.setattr(jh, "_expo_world_id", racing)
    assert jh.staff_history("girls", "race-ident") == {}
    assert not jh._staff_hist_cache, "a read that raced an invalidation was published"
    monkeypatch.setattr(jh, "_expo_world_id", lambda _db: None)
    jh.staff_history("girls", "race-ident")
    assert jh._staff_hist_cache, "an unraced read should still be memoised"
    jh.invalidate_staff_history()


def test_a_vetoed_departure_keeps_every_seat_its_skipped_moves_would_have_left(
        monkeypatch):
    """Veto the head's retirement, leave the promotion that would fill it: the
    promotion is skipped (the seat is not vacant), so the assistant stays — and
    the fill proposed for THEIR seat must be skipped too, and so on down the
    chain, or somebody who never moved is sent to the free pool."""
    def ln(kind, ident, slot, cid, veto=False, frm=None):
        d = {"kind": kind, "gender": "girls", "ident": ident, "slot": slot,
             "coach_id": cid, "veto": veto}
        if frm:
            d["from_ident"], d["from_slot"] = frm
        return d
    prop = {"year": 2030, "lines": [
        ln("retire", "X", "head", "old", veto=True),
        ln("promote", "X", "head", "a", frm=("X", "asst1")),
        ln("move", "X", "asst1", "b", frm=("Y", "asst1")),
        ln("move", "Y", "asst1", "c", frm=("Z", "asst2")),
        ln("promote", "Q", "head", "d", frm=("Q", "asst1")),   # unrelated, applies
    ]}
    moved = []
    monkeypatch.setattr(jc, "pending_cycle", lambda wid: prop)
    monkeypatch.setattr(jc, "move_coach", lambda wid, cid, *a: moved.append(cid))
    monkeypatch.setattr(jc, "retire_coach", lambda *a: moved.append("RETIRED"))

    class _Fake:
        def execute(self, *a): return self
        def commit(self): pass
        def close(self): pass
    monkeypatch.setattr(jc, "_cconn", lambda: _Fake())
    assert jc.commit_cycle(1) == 1
    assert moved == ["d"]


@pytest.fixture(scope="module")
def world_season(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("jhsaa") / "coaches.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for
    real_fields = dict(jh.STATE_FIELD)
    real_primed, real_prime = wd.is_primed, wd.prime
    for grp, real in real_fields.items():
        jh.STATE_FIELD[grp] = {24: 24, 32: 16, 40: 20}[real]
    jh.load_schools = _small(real_load)
    jh._season_cache.clear()
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    try:
        w = wd.get_or_create(wd.DEFAULT_SEED)
        salt = wd.active_salt(wd.DEFAULT_SEED)
        sy = wd.jhsaa_season_year(w)
        # The season with NO staffs — exactly the pre-coaches behaviour.
        bare = _digest(jh.run_season("girls", sy, seed=0, salt=salt))
        jh._season_cache.clear()
        wd.run_jhsaa(wd.DEFAULT_SEED, w)
        wd.is_primed = lambda *a, **k: True
        wd.prime = lambda *a, **k: None
        yield {"world": w, "salt": salt, "season_year": sy, "bare": bare,
               "client": create_app().test_client()}
    finally:
        jh.load_schools = real_load
        jh.STATE_FIELD.clear()
        jh.STATE_FIELD.update(real_fields)
        jh._season_cache.clear()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


def test_a_season_with_staffs_reads_the_staffs(world_season):
    """The staffs, not the old school draws, drive the season: the lens a program
    plays with is the one its staff produces."""
    staff = wd.jhsaa_staff_for_season(world_season["season_year"], "girls",
                                      world_season["world"]["id"])
    assert staff, "run_jhsaa should have seated staffs"
    s = jh.load_schools("girls")[0]
    teams = jh.district_teams([s], world_season["season_year"], world_season["salt"],
                              staff=staff)
    assert teams[0].lens == staff[s.key].lens
    assert teams[0].strategy == staff[s.key].strategy


def test_every_program_has_a_head_and_history(world_season):
    wid = world_season["world"]["id"]
    for g in ("girls", "boys"):
        rows = jc.seats(wid, g)
        heads = {r["ident"] for r in rows if r["slot"] == "head" and r["coach"]}
        assert heads == {s.ident for s in jh.load_schools(g)}
        per = {}
        for r in rows:
            per[r["ident"]] = per.get(r["ident"], 0) + 1
        assert max(per.values()) <= 1 + jc.MAX_ASSISTANTS
        assert min(per.values()) >= 2          # head + at least one assistant
    hist = jc.season_effects(wid, world_season["world"]["year"], "girls")
    assert hist and all(isinstance(v, jc.StaffEffect) for v in hist.values())


def test_ensure_staff_is_idempotent(world_season):
    wid = world_season["world"]["id"]
    before = [(r["ident"], r["slot"], r["coach"].coach_id if r["coach"] else None)
              for r in jc.seats(wid)]
    assert jc.ensure_staff(wid, world_season["season_year"], world_season["salt"]) == 0
    after = [(r["ident"], r["slot"], r["coach"].coach_id if r["coach"] else None)
             for r in jc.seats(wid)]
    assert sorted(before, key=str) == sorted(after, key=str)


def test_a_staff_change_moves_the_season(world_season):
    """The coach is the source now: a different read on one program changes
    that program's season (and the memo does not serve the old one)."""
    staff = dict(wd.jhsaa_staff_for_season(world_season["season_year"], "girls",
                                           world_season["world"]["id"]))
    key = sorted(staff)[0]
    old = staff[key]
    staff[key] = jc.StaffEffect(lens=jc.lens_of(1.0 if old.lens.read > 1.0 else 0.0, 0.5),
                                culture=old.culture, strategy=old.strategy)
    moved = _digest(jh.run_season("girls", world_season["season_year"], seed=0,
                                  salt=world_season["salt"], staff=staff))
    assert moved != world_season["bare"]


def test_program_and_coach_pages_render(world_season):
    wid = world_season["world"]["id"]
    client = world_season["client"]
    s = jh.load_schools("girls")[0]
    html = client.get(f"/jhsaa/school/{s.name}?g=girls").get_data(as_text=True)
    assert "Coaching staff" in html
    head = next(r["coach"] for r in jc.seats(wid, "girls", s.ident) if r["slot"] == "head")
    assert head.name in html
    page = client.get(f"/jhsaa/coach/{head.coach_id}?g=girls")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert head.name in body and "Changeover" in body and "Clutch" in body
    assert s.name in body                      # the career row
    # ‼️ the history row is keyed on the WORLD year; the page shows the SEASON
    car = jc.coach_career(wid, head.coach_id)
    assert [h["year"] for h in car["history"]] == [world_season["season_year"]]
    assert car["history"][0]["world_year"] == world_season["world"]["year"]
    assert f"<td>{world_season['season_year']}</td>" in body
    assert client.get("/jhsaa/coach/nope").status_code == 404


# --- former players and the editor (mutating — keep these LAST) --------------------

def test_seniors_are_indexed_as_alumni(world_season):
    wid = world_season["world"]["id"]
    conn = wd._db()
    try:
        n = conn.execute("SELECT COUNT(*) FROM jhsaa_alumni WHERE world_id=?",
                         (wid,)).fetchone()[0]
    finally:
        conn.close()
    assert n > 0


def _an_alumnus(wid, gender="girls"):
    conn = wd._db()
    try:
        return conn.execute("SELECT pid, school, ident FROM jhsaa_alumni"
                            " WHERE world_id=? AND gender=? ORDER BY pid LIMIT 1",
                            (wid, gender)).fetchone()
    finally:
        conn.close()


def test_hiring_a_former_player_is_independent_of_their_ability(world_season):
    wid = world_season["world"]["id"]
    pid, school, ident = _an_alumnus(wid)
    client = world_season["client"]
    # the player page offers the hire form once they have graduated
    page = client.get(f"/jhsaa/player/{school}/{pid}?g=girls").get_data(as_text=True)
    assert "Hire as coach" in page
    r = client.post("/editor/jhsaa-coach", data={
        "do": "hire", "jh_pid": pid, "jh_player_school": school, "g": "girls",
        "jh_school": school, "slot": "asst"})
    assert r.status_code == 302
    c = next(r["coach"] for r in jc.seats(wid, "girls", ident)
             if r["coach"] and r["coach"].player_pid == pid)
    assert c.origin == "alumnus" and c.alma == ident
    # grades come off the pid, not the player's OVR: same person → same coach
    again = jc.coach_from_player(wid, {**jc.alumnus(wid, pid), "hometown": ""}, "girls",
                                 world_season["season_year"], "alumnus")
    assert again.grades == c.grades
    body = client.get(f"/jhsaa/coach/{c.coach_id}?g=girls").get_data(as_text=True)
    assert "Player page" in body


def test_a_player_still_in_school_cannot_be_hired(world_season):
    wid = world_season["world"]["id"]
    with pytest.raises(jc.StaffError):
        jc.appoint_former_player(wid, "not-a-graduate", "x", "girls", "asst1",
                                 world_season["season_year"])


def test_moving_a_head_sends_the_incumbent_to_the_free_pool(world_season):
    wid = world_season["world"]["id"]
    sy = world_season["season_year"]
    schools = jh.load_schools("boys")
    a, b = schools[0], schools[1]
    seats_a = {r["slot"]: r["coach"] for r in jc.seats(wid, "boys", a.ident)}
    seats_b = {r["slot"]: r["coach"] for r in jc.seats(wid, "boys", b.ident)}
    mover, incumbent = seats_a["head"], seats_b["head"]
    jc.move_coach(wid, mover.coach_id, b.ident, "boys", "head", sy)
    now_b = {r["slot"]: r["coach"] for r in jc.seats(wid, "boys", b.ident)}
    now_a = {r["slot"]: r["coach"] for r in jc.seats(wid, "boys", a.ident)}
    assert now_b["head"].coach_id == mover.coach_id
    assert now_a["head"] is None                       # vacated, not refilled
    assert incumbent.coach_id in {c.coach_id for c in jc.free_pool(wid)}
    # the staff effect at the destination is now the mover's
    eff = jc.current_effects(wid, "boys")
    assert b.key in eff and a.key not in eff
    jc.retire_coach(wid, incumbent.coach_id, sy)
    assert incumbent.coach_id not in {c.coach_id for c in jc.free_pool(wid)}


def test_a_staff_never_exceeds_four_seats(world_season):
    wid = world_season["world"]["id"]
    s = jh.load_schools("girls")[2]
    have = [r["slot"] for r in jc.seats(wid, "girls", s.ident)]
    while len(have) < 4:
        pool = jc.free_pool(wid)
        slot = jc.resolve_slot(wid, s.ident, "girls", "asst")
        if pool:
            jc.move_coach(wid, pool[0].coach_id, s.ident, "girls", slot,
                          world_season["season_year"])
        else:
            break
        have = [r["slot"] for r in jc.seats(wid, "girls", s.ident)]
    if len(have) == 4:
        with pytest.raises(jc.StaffError):
            jc.resolve_slot(wid, s.ident, "girls", "asst")

"""The ordinary Jefferson cohort's international names (owner rule 2026-09).

Jefferson's non-US players are immigrant families — four-year students born
here, NOT exchange students. The slice existed to make the association diverse
and did the opposite: it drew from `tennis_global`, a PRO-TOUR mix that is
**69.3% Europe and 3.5% Africa**, and Canada held a separate 5% share equal to
the whole rest of the world. Between them, "only white people names" (owner).
"""
import app.jhsaa as jh


def test_the_retired_mix_was_the_problem():
    """Kept as the record of WHY this changed, and because cohorts entering
    before `intl_era()` still draw it — their names are already archived."""
    w = jh._intl_weights()
    europe = sum(v for k, v in w.items()
                 if k in ("europe_western", "europe_eastern", "europe_southeast",
                          "spain", "italy", "russia", "british_isles", "serbia",
                          "germany", "switzerland", "nordic", "belgium", "austria"))
    assert europe / sum(w.values()) > 0.6, "the retired mix was Europe-dominated"


def test_the_broad_mix_is_the_widest_pool():
    """`global_college` — the owner's own preset, "Africa fully represented" —
    minus the two shares that draw separately. 92 regions against 36."""
    broad, old = jh._broad_intl_weights(), jh._intl_weights()
    assert len(broad) > 2 * len(old)
    tot = sum(broad.values())
    africa = sum(v for k, v in broad.items() if "africa" in k) / tot
    asia = sum(broad[k] for k in ("china", "japan", "south_korea", "east_asia",
                                  "south_asia", "southeast_asia", "philippines",
                                  "indonesia")) / tot
    assert africa > 0.15, africa          # was 3.5%
    assert asia > 0.10, asia
    for drawn_separately in ("us", "canada"):
        assert drawn_separately not in broad


def test_canada_stops_being_half_of_every_foreign_name():
    """‼️ THE SECOND CAUSE, and the less obvious one. At 0.05 against the
    international slice's 0.05, Canada took 50% of all non-US names — and draws
    Anglo/French. From `intl_era()` on it is 1.5%, so the world takes ~85% of
    Jefferson's foreign names instead of 50%."""
    intl_old = 1.0 - jh.NAME_V2_US - jh.NAME_V2_CANADA
    intl_new = 1.0 - jh.NAME_V2_US - jh.NAME_V3_CANADA
    assert round(jh.NAME_V2_CANADA / (jh.NAME_V2_CANADA + intl_old), 6) == 0.5
    assert jh.NAME_V3_CANADA / (jh.NAME_V3_CANADA + intl_new) < 0.2
    # The US head is untouched — it was never the problem.
    assert jh.NAME_V2_US == 0.90


def test_the_us_head_was_never_the_problem():
    """It is Census-frequency weighted, so the 90% majority already carries the
    country's real surname distribution. Raising the foreign share is a separate
    decision nobody asked for."""
    import random
    from generators import draw_us_weighted
    rng = random.Random(7)
    sur = {draw_us_weighted(rng, "male")[0].split()[-1] for _ in range(3000)}
    assert {"Martinez", "Garcia", "Nguyen", "Rodriguez"} & sur


def test_a_cohort_that_predates_the_era_keeps_its_names(monkeypatch):
    """‼️ THE GUARD. A JHSAA name is regenerated from seed every time a roster is
    built, so widening the mix renames every already-archived cohort that draws
    from it — and `world_jhsaa_dual.lines` archives NAMES, which
    `_jh_line_records` keys off. `intl_era` is the `name_era` idiom, for exactly
    the same reason."""
    school = jh.load_schools("boys")[0]
    monkeypatch.setattr(jh, "intl_era", lambda: 50)
    old = {p.pid: p.name for p in jh.build_roster(school, 10, "")}
    monkeypatch.setattr(jh, "intl_era", lambda: 0)
    new = {p.pid: p.name for p in jh.build_roster(school, 10, "")}
    assert old != new, "the era gate is doing nothing"
    # …and a cohort on the far side of either era is identical both ways.
    monkeypatch.setattr(jh, "intl_era", lambda: 50)
    a = {p.pid: p.name for p in jh.build_roster(school, 60, "")}
    monkeypatch.setattr(jh, "intl_era", lambda: 40)
    b = {p.pid: p.name for p in jh.build_roster(school, 60, "")}
    assert a == b


def test_the_association_actually_draws_broadly_now():
    """The measured outcome: foreign cohort names come from every part of the
    world rather than western Europe and Canada."""
    seen = set()
    for school in jh.load_schools("boys")[:200]:
        for p in jh.build_roster(school, 6, ""):
            if p.country != "US":
                seen.add(p.country)
    assert len(seen) >= 25, sorted(seen)
    # Not a Europe-and-Canada list any more.
    assert seen & {"JP", "KR", "CN", "PH", "ID", "TW", "HK"}, "no Asia"
    assert seen & {"NG", "ZA", "ET", "MA", "KE", "GH", "EG", "SN"}, "no Africa"


def test_every_era_is_cleared_when_a_new_save_starts():
    """‼️ A NEW SAVE KEEPS `world_setting`. `world.reset()` deletes the JHSAA
    archive but not the settings table, so an era left behind carries the PRIOR
    league's cutoff — a CALENDAR YEAR — into the new one and holds its opening
    cohorts on the retired behaviour until the new save reaches that year, which
    can be decades away.

    `reset()` hand-listed the two eras that existed when it was written and had
    silently stopped covering `jhsaa_talent_era` and `jhsaa_career_era` when
    those were added. It now walks `jhsaa.ERA_SETTINGS`, so the list and the
    resetter cannot drift — which is the only reason a sixth era added later is
    covered by existing."""
    import inspect
    import app.world as wd
    # Every era resolver's setting name is in the table…
    src = inspect.getsource(__import__("app.jhsaa", fromlist=["x"]))
    declared = set(jh.ERA_SETTINGS)
    used = set(__import__("re").findall(r'_resolve_era\("([a-z_]+)"', src))
    assert used == declared, used ^ declared
    # …and `world.reset()` reads the table rather than naming any era itself.
    reset_src = inspect.getsource(wd.reset)
    assert "reset_eras()" in reset_src
    # No era named in reset's CODE (its prose may cite them as history).
    code = [ln.split("#", 1)[0] for ln in reset_src.splitlines()]
    for setting in jh.ERA_SETTINGS:
        assert not any(setting in ln for ln in code), \
            f"{setting} hand-listed in world.reset"

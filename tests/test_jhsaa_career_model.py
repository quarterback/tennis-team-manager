"""The JHSAA career model — starting ability / career peak / yearly capacity.

See docs/PROPOSAL-development-model-redesign.md §22-§24. These test the model
itself (`_career_plan`, `career_ability`, `_apply_career`) and the era gate that
keeps it off cohorts already in the building. The pure functions are exercised
directly — they need no roster, no world and no database, so the whole file runs
in well under a second.
"""
import random
import statistics as st

from app import jhsaa as jh


SALT = ""
CEIL = 55.0


def _plan(seat, ceiling=CEIL):
    return jh._career_plan("SCHOOL", 2040, seat, SALT, ceiling)


def _path(seat, ceiling=CEIL, exposure=None):
    return [jh.career_ability("SCHOOL", 2040, seat, g, SALT, ceiling, exposure)
            for g in (9, 10, 11, 12)]


# --- the model ---------------------------------------------------------------

def test_start_does_not_depend_on_grade():
    """‼️ THE WHOLE POINT. Nothing in the career model reads the grade to decide
    how much of a player is visible — grade only says which point of that
    player's own path to read. So a freshman's ability is drawn from the same
    distribution a senior's start was, and the population of grade-9 abilities
    must OVERLAP the population of grade-12 abilities substantially."""
    fresh = sorted(_path(s)[0] for s in range(600))
    senior = sorted(_path(s)[3] for s in range(600))
    sr_median = senior[len(senior) // 2]
    over = sum(1 for x in fresh if x >= sr_median) / len(fresh)
    # Measured 8.7% here, against 1.3% under the legacy maturity model and 0.0%
    # under the lockstep one before it — a different model, not a retuned one.
    # The floor is deliberately well under the measured value: this guards the
    # STRUCTURE (start is grade-free), not a calibration.
    assert over > 0.05, f"only {over:.1%} of freshmen reach the senior median"


def test_a_freshman_can_outrank_a_senior_outright():
    """The concrete form: some freshman, somewhere, is simply better than some
    senior on the same generated ceiling."""
    best_fresh = max(_path(s)[0] for s in range(400))
    worst_senior = min(_path(s)[3] for s in range(400))
    assert best_fresh > worst_senior


def test_every_career_shape_exists():
    """Ready / stagnant / one-big-leap / late are EMERGENT from the capacity
    draws — never labelled, never stored — so each must actually occur."""
    ready = stagnant = leap = late = 0
    for s in range(1500):
        start, peak, _ = _plan(s)
        p = _path(s)
        gains = [p[i + 1] - p[i] for i in range(3)]
        if start >= 0.90 * peak:
            ready += 1
        if p[-1] - p[0] < 3:
            stagnant += 1
        if max(gains) >= 8:
            leap += 1
        if gains[2] == max(gains) and gains[2] >= 3:
            late += 1
    for name, n in (("ready", ready), ("stagnant", stagnant),
                    ("one big leap", leap), ("late developer", late)):
        assert n > 0, f"no {name} careers in 1500 players"


def test_ability_never_falls():
    """Nobody regresses — the model's oldest rule. A capacity draw is always
    non-negative and exposure only scales it down, so a path is monotonic."""
    for s in range(400):
        p = _path(s)
        assert all(b >= a for a, b in zip(p, p[1:])), p


def test_the_senior_year_is_incremental_not_a_leap():
    """‼️ Owner rule: breakouts are sophomore and junior; the senior year ticks
    over. This is EMERGENT from the peak clamp — capacity is drawn identically in
    all four years, and late years grow less only because most players have
    already reached their peak. No rule anywhere says seniors grow less, so this
    is the test that would catch the taper being lost."""
    gains = [[], [], []]
    for s in range(2000):
        p = _path(s)
        for i in range(3):
            gains[i].append(p[i + 1] - p[i])
    # Measured medians 2.49 / 2.31 / 1.82 — a 27% fall from the sophomore year
    # to the senior one. Softer than a hard clamp would give (2.4 / 2.0 / 1.2),
    # because CAREER_OVERFLOW lets a third of players carry on past their peak;
    # that trade is deliberate (§23) and this threshold prices it in.
    med = [st.median(g) for g in gains]
    assert med[0] > med[2], f"no taper: {med}"
    assert med[2] < 0.85 * med[0], f"senior year not incremental enough: {med}"
    # ...but a late bloomer must still be possible.
    p90_senior = sorted(gains[2])[int(0.9 * len(gains[2]))]
    assert p90_senior > 3.0, f"senior ceiling too flat for a late bloomer: {p90_senior}"


def test_removing_the_peak_clamp_would_destroy_the_taper():
    """The mechanism, asserted rather than described. `CAREER_OVERFLOW` is
    load-bearing in BOTH directions: at 1.0 a senior year gains as much as a
    freshman year, which is the pattern the owner ruled out."""
    original = jh.CAREER_OVERFLOW
    try:
        jh.CAREER_OVERFLOW = 1.0
        gains = [[], [], []]
        for s in range(1500):
            p = _path(s)
            for i in range(3):
                gains[i].append(p[i + 1] - p[i])
        med = [st.median(g) for g in gains]
        assert med[2] > 0.9 * med[0], (
            "with no clamp the taper should vanish; if this fails the taper is "
            f"coming from somewhere other than the peak clamp: {med}")
    finally:
        jh.CAREER_OVERFLOW = original


def test_peak_is_a_projection_not_a_wall():
    """§23: some players finish ABOVE their career peak — peak is the best they
    could be, not a ceiling they cannot pass — but it must stay a minority."""
    over = sum(1 for s in range(1500) if _path(s)[-1] > _plan(s)[1] + 1e-9)
    assert 0 < over < 1500 * 0.6, over


def test_exposure_only_ever_costs_realisation():
    """Playing scales a player's OWN capacity, so it can never manufacture
    ability — a full-exposure career is an upper bound on a partial one."""
    for s in range(200):
        full = _path(s)[-1]
        sat = _path(s, exposure={9: 0.55, 10: 0.55, 11: 0.55})[-1]
        assert sat <= full + 1e-9
        assert sat >= _path(s)[0]                 # still develops while sitting


def test_a_stagnant_player_gains_little_however_much_they_play():
    """Exposure multiplies capacity, so it does not homogenise players: the gap
    between sitting and starting is proportional to what the player had to
    realise in the first place."""
    spans = []
    for s in range(500):
        full = _path(s)[-1] - _path(s)[0]
        sat = _path(s, exposure={9: 0.55, 10: 0.55, 11: 0.55})[-1] - _path(s)[0]
        spans.append((full, full - sat))
    low = [d for f, d in spans if f < 3]
    high = [d for f, d in spans if f > 15]
    assert low and high
    assert st.mean(low) < st.mean(high), (st.mean(low), st.mean(high))


def test_the_plan_is_fixed_at_entry_and_deterministic():
    """A career is rolled once from the same identity the pid is built from, so
    replaying it returns the same person — that is what lets rosters be
    regenerated rather than stored."""
    for s in (0, 7, 41):
        assert _plan(s) == _plan(s)
        assert _path(s) == _path(s)
    # and it is keyed on the seat, not shared across a roster
    assert _plan(0) != _plan(1)


def test_capacity_rolls_on_its_own_rng_stream():
    """Rolled off the main roster rng, a career draw would shift every
    subsequent draw and regenerate the whole association. The stream is keyed
    separately, so the main sequence is untouched."""
    before = random.random()
    _plan(3)
    random.seed(0)
    a = random.random()
    random.seed(0)
    _plan(4)
    b = random.random()
    assert a == b
    assert isinstance(before, float)


# --- the era gate ------------------------------------------------------------

def test_compression_stops_at_the_career_era():
    """Talent compression existed to stop high-school ceilings overrunning the
    COLLEGE scale. The career model separates the two scales and translates at
    graduation, so compression applies only BETWEEN the two eras — never to a
    cohort on the free scale."""
    assert not jh._compresses(jh.career_era())
    assert not jh._compresses(jh.career_era() + 4)
    if jh.talent_era() < jh.career_era():
        assert jh._compresses(jh.talent_era())


def test_the_free_scale_reaches_above_the_college_reference():
    """§24: a Jefferson ceiling is drawn on the JHSAA's own scale, not held under
    the college NORMALISATION reference of 80."""
    from app.player_attributes import GRADE_CEIL
    rng = random.Random(11)
    top = max(jh._ceiling(rng, "9A", "boys", None, cap=float(GRADE_CEIL))
              for _ in range(4000))
    assert top > 80.0, top
    rng = random.Random(11)
    capped = max(jh._ceiling(rng, "9A", "boys", None) for _ in range(4000))
    assert capped <= 80.0, capped

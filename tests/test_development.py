import random

from engine import ATTRS
from app.development import (
    ACADEMIC_MIN, ACADEMIC_MAX, STR_MIN, STR_MAX,
    generate_prospect, Prospect, GRADE_MIN, GRADE_MAX,
    stagger_scale, STAGGER_BLOCK_FRAC,
)
from app.player_attributes import RICH_ATTRS, PlayerAttributes


def _class(n=120, seed=1):
    rng = random.Random(seed)
    return [generate_prospect(rng, f"P{i}") for i in range(n)]


def _mk(current, ceiling, rate, tier, mult, fog=15):
    return Prospect(name="t", current={a: float(current) for a in ATTRS},
                    potential={a: float(ceiling) for a in ATTRS}, interest_rate=rate,
                    tier=tier, tier_mult=mult, fog=fog, consensus_seed=1)


def test_rich_attributes_derive_engine_drivers():
    p = generate_prospect(random.Random(11), "X")
    assert set(p.current) == set(RICH_ATTRS)
    drivers = PlayerAttributes(p.current, **p.traits).derive_drivers()
    assert set(drivers) == set(ATTRS)
    assert all(0.0 <= v <= 1.0 for v in drivers.values())
    assert GRADE_MIN <= PlayerAttributes(p.current).drop_shot <= GRADE_MAX


def test_current_is_visible_and_drives_str():
    p = generate_prospect(random.Random(3), "X")
    assert GRADE_MIN <= p.current_overall() <= GRADE_MAX
    assert STR_MIN <= p.str_value() <= STR_MAX
    # STR is a monotone function of current ability for now.
    lo, hi = _mk(35, 70, 0.2, 1, 1.0), _mk(60, 70, 0.2, 1, 1.0)
    assert hi.str_value() > lo.str_value()


def test_academic_rating_is_admissions_only_band():
    p = generate_prospect(random.Random(13), "X", "US")
    assert ACADEMIC_MIN <= p.academic_rating <= ACADEMIC_MAX
    assert p.public_view()["academic"] == p.academic_rating
    before = p.engine_player().overall
    p.academic_rating = ACADEMIC_MAX
    assert p.engine_player().overall == before


def test_current_grows_toward_ceiling_no_regression_no_overshoot():
    p = _mk(35, 70, 1.5, 3, 1.6)
    prev = p.current_overall()
    for _ in range(6):
        p.develop_year()
        cur = p.current_overall()
        assert cur >= prev
        prev = cur
    assert p.current_overall() <= p.ceiling_overall() + 1


def test_late_bloomer_outgrows_early_bloomer_from_same_utr():
    """Two juniors at the SAME current STR can have very different futures."""
    early = _mk(45, 47, 0.2, 1, 1.0)
    late = _mk(45, 74, 2.0, 3, 1.6)
    assert abs(early.current_overall() - late.current_overall()) <= 1
    assert late.project(4) > early.project(4) + 15


def test_engine_plays_current_ability():
    weak_now = _mk(30, 78, 2.0, 3, 1.6)
    strong_now = _mk(62, 64, 0.2, 1, 1.0)
    assert strong_now.engine_player().overall > weak_now.engine_player().overall


def test_two_ceiling_reports_independent_within_fog():
    p = generate_prospect(random.Random(9), "X")
    s, d = p.scouting_report("service"), p.scouting_report("dept")
    assert GRADE_MIN <= s <= GRADE_MAX and GRADE_MIN <= d <= GRADE_MAX
    assert abs(s - p.ceiling_overall()) <= p.fog + 1
    assert abs(d - p.ceiling_overall()) <= p.fog + 1


def test_stagger_scale_banks_full_year_for_everyone():
    """Staggered development: every player's per-tick slices sum to the same total
    by season's end — only the timing window differs."""
    ticks = 16
    for key in ("alpha", "bravo", "charlie", "delta", "echo"):
        total = sum(stagger_scale(key, t, ticks, total=1.0) for t in range(ticks))
        assert abs(total - 1.0) < 1e-9
        active = [t for t in range(ticks) if stagger_scale(key, t, ticks) > 0]
        assert active == list(range(active[0], active[-1] + 1))   # one contiguous window
        assert len(active) == max(1, round(ticks * STAGGER_BLOCK_FRAC))


def test_stagger_scale_is_staggered_and_deterministic():
    ticks = 16
    # Different players develop in different windows (not all at once).
    windows = {k: tuple(stagger_scale(k, t, ticks) > 0 for t in range(ticks))
               for k in ("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8")}
    assert len(set(windows.values())) > 1
    # Deterministic: same key → same schedule.
    assert all(stagger_scale("p1", t, ticks) == stagger_scale("p1", t, ticks)
               for t in range(ticks))


def test_regress_to_younger_inverts_development():
    """A junior's climb can be replayed: roll back to a younger self, develop the
    same span, and you land back near where you started."""
    p = _mk(45, 74, 2.0, 3, 1.6)          # super-bloomer with room to climb
    start = p.current_overall()
    p.regress_to_younger(1.0)
    younger = p.current_overall()
    assert younger < start                 # genuinely weaker as a 'younger self'
    p.develop(1.0)
    assert abs(p.current_overall() - start) <= 3   # climbs back near recruiting level
    # No development rate ⇒ no climb to replay ⇒ no rollback.
    flat = _mk(50, 50, 0.0, 1, 1.0)
    before = flat.current_overall()
    flat.regress_to_younger(1.0)
    assert flat.current_overall() == before


def test_star_tracks_current_so_gems_are_underrated():
    klass = _class(160, seed=7)
    assert all(1 <= p.star_rating() <= 5 for p in klass)

    gem = _mk(31, 72, 2.0, 3, 1.6)
    bust = _mk(55, 56, 0.15, 1, 1.0)
    assert gem.star_rating() <= 2 and (gem.project(4) - gem.current_overall()) >= 12
    assert bust.star_rating() >= 4 and (bust.project(4) - bust.current_overall()) <= 3

    assert any(a.star_rating() < b.star_rating() and a.project(4) > b.project(4) + 4
               for a in klass for b in klass)

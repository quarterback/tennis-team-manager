import os

import pytest

from app.season import run_season, NATIONAL_FIELD
from app.bracket import select_field, run_bracket

_HAS_D1 = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "data", "ncaa", "d1_women.json"))
pytestmark = pytest.mark.skipif(not _HAS_D1, reason="D1 conference data not present")


def test_season_shape():
    sr = run_season("D1", "women", seed=2026)
    assert len(sr.programs) > 300
    assert len(sr.standings) == len(sr.champions)        # one champion per conference
    assert all(p.school in sr.ratings for p in sr.programs)
    pis = [r.pi for r in sr.ratings.values()]
    assert min(pis) >= 0.54 and max(pis) <= 0.96         # display band
    for r in sr.ratings.values():
        assert 0.0 <= r.apr <= 1.0
        assert (r.wins + r.losses) > 0


def test_season_deterministic():
    a = run_season("D1", "women", seed=5)
    b = run_season("D1", "women", seed=5)
    ra = [p.school for p in a.ranked()[:10]]
    rb = [p.school for p in b.ranked()[:10]]
    assert ra == rb
    assert {c.school for c in a.champions} == {c.school for c in b.champions}


def test_bracket_structure():
    sr = run_season("D1", "women", seed=2026)
    seeded, autobids = select_field(sr.programs, sr.ratings, sr.champions, size=NATIONAL_FIELD)
    assert len(seeded) == NATIONAL_FIELD
    # every conference champion is in the field (autobids)
    assert {c.key for c in sr.champions}.issubset({p.key for p in seeded})
    br = run_bracket(seeded, autobids, seed=2026, final_fidelity="fast")
    assert br.champion is not None and br.runner_up is not None
    # round sizes: 32, 16, 8, 4, 2 matchups, then final resolves champion
    assert [len(r) for r in br.rounds] == [32, 16, 8, 4, 2, 1]
    # champion came from the field
    assert br.champion.key in {p.key for p in seeded}


def test_higher_seeds_usually_advance():
    """Skill does most of the work: most Round-of-64 winners are the higher seed."""
    sr = run_season("D1", "women", seed=2026)
    seeded, autobids = select_field(sr.programs, sr.ratings, sr.champions, size=NATIONAL_FIELD)
    br = run_bracket(seeded, autobids, seed=2026, final_fidelity="fast")
    r64 = br.rounds[0]
    favs = sum(1 for m in r64 if not m.upset)
    assert favs >= 20  # most (not all) favorites win — variance is real but bounded

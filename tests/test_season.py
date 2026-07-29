import os

import pytest

from app.season import run_season, NATIONAL_FIELD
from app.bracket import select_field, run_bracket

_HAS_D1 = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "data", "ncaa", "d1_women.json"))
_HAS_D3 = os.path.exists(os.path.join(os.path.dirname(__file__), "..", "data", "ncaa", "d3_women.json"))
pytestmark = pytest.mark.skipif(not _HAS_D1, reason="D1 conference data not present")


def _abandoned_singles(sr):
    return sum(1 for d in sr.duals for ln in d["lines"]
              if ln["slot"][0] == "S" and not ln.get("completed"))


@pytest.mark.skipif(not _HAS_D3, reason="D3 conference data not present")
def test_d3_plays_every_match_while_d1_clinches():
    """ITA D3 'play-play' wiring: D3 regular-season duals abandon no singles
    (every match completes, for fuller player stats), while D1 still clinches and
    abandons the dead rubbers. Winners are unaffected either way."""
    d3 = run_season("D3", "women", seed=2026)
    d1 = run_season("D1", "women", seed=2026)
    assert _abandoned_singles(d3) == 0        # play-play: nothing left unfinished
    assert _abandoned_singles(d1) > 0         # clinch-play: dead rubbers abandoned


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


def test_bracket_is_not_pure_noise():
    """Talent should be predictive — the Round of 64 is not a coin flip. We do NOT
    require the higher seed to win: how often chalk holds swings year to year (some
    seasons the committee looks great, some are upset-heavy), and that's fine. This
    only guards against the bracket degenerating into pure randomness."""
    sr = run_season("D1", "women", seed=2026)
    seeded, autobids = select_field(sr.programs, sr.ratings, sr.champions, size=NATIONAL_FIELD)
    br = run_bracket(seeded, autobids, seed=2026, final_fidelity="fast")
    favs = sum(1 for m in br.rounds[0] if not m.upset)
    assert favs >= 8           # a pure coin-flip would average ~16; this is a wide floor

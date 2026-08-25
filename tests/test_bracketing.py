"""Bracketing: selection and seeding are separate from bracket construction. After
teams are seeded, the draw swaps WITHIN seed bands (seed integrity preserved) to
minimise first-round penalties. The draw is TRUE-SEEDED: it is never rearranged to
keep same-conference teams apart (whole tournament, both genders, all divisions) —
it only avoids regular-season rematches (scaled by how many times they met) and
AQ-vs-AQ openers."""
from collections import Counter

from app.seasonmode import (_meeting_penalty, _pair_penalty, _seed_bracket,
                            _round1_pairs, _PEN_REMATCH,
                            _PEN_MEET2, _PEN_MEET3, _PEN_AQ_VS_AQ)


def test_meeting_penalty_escalates():
    assert _meeting_penalty(0) == 0
    assert _meeting_penalty(1) == _PEN_REMATCH
    assert _meeting_penalty(2) == _PEN_MEET2
    assert _meeting_penalty(3) == _PEN_MEET3
    assert _meeting_penalty(9) == _PEN_MEET3
    # more meetings is never cheaper to rematch
    assert _PEN_REMATCH < _PEN_MEET2 < _PEN_MEET3


def test_pair_penalty_stacks_and_counts_meetings():
    aq = {"A", "B"}
    met_twice = Counter({frozenset(("A", "B")): 2})
    # A vs B: 2 meetings + AQ-vs-AQ (conference affiliation is NOT penalised)
    assert _pair_penalty("A", "B", met_twice, aq) == _PEN_MEET2 + _PEN_AQ_VS_AQ
    # C vs D: never met, not AQs
    assert _pair_penalty("C", "D", met_twice, aq) == 0
    # a 2nd meeting is penalised harder than a 1st
    once = Counter({frozenset(("C", "D")): 1})
    twice = Counter({frozenset(("C", "D")): 2})
    assert (_pair_penalty("C", "D", twice, set())
            > _pair_penalty("C", "D", once, set()))


def test_pair_penalty_ignores_conference():
    # True seed: two teams that share a conference are NOT penalised — the bracketer
    # never separates them. (The penalty signature no longer takes conference at all.)
    aq = set()
    played = Counter()
    # nothing in common → 0; the only signals left are rematch and AQ-vs-AQ
    assert _pair_penalty("SEC1", "SEC2", played, aq) == 0
    assert _pair_penalty("SEC1", "SEC2", played, {"SEC1", "SEC2"}) == _PEN_AQ_VS_AQ


def _total(pairs, played, aq):
    return sum(_pair_penalty(h, a, played, aq) for _b, h, a in pairs)


def test_seed_bracket_true_seed_ignores_conference():
    # An all-one-conference field: with the old conference-separation rule the
    # bracketer would shuffle teams apart; true-seeded, it leaves them in pure-seed
    # order because nothing about sharing a conference is penalised.
    seeds = [f"T{i:02d}" for i in range(16)]
    played = Counter()
    aq = set()
    bracket = _seed_bracket(seeds, aq, played)
    # pure-seed placement is preserved exactly — nobody moved for conference reasons
    assert bracket == _round1_pairs(seeds)
    # valid: every team placed exactly once, n/2 pairs
    placed = [x for _b, h, a in bracket for x in (h, a)]
    assert sorted(placed) == sorted(seeds)
    assert len(bracket) == 8


def test_seed_bracket_never_worsens_and_is_valid():
    # A field with heavy regular-season rematches the bracketer can swap apart.
    seeds = [f"T{i:02d}" for i in range(16)]
    aq = set()
    pairs = _round1_pairs(seeds)
    played = Counter({frozenset((h, a)): 2 for _b, h, a in pairs[:4]})
    naive = _total(pairs, played, aq)
    bracket = _seed_bracket(seeds, aq, played)
    # valid: every team placed exactly once, n/2 pairs
    placed = [x for _b, h, a in bracket for x in (h, a)]
    assert sorted(placed) == sorted(seeds)
    assert len(bracket) == 8
    # the draw never increases the penalty vs the pure-seed placement
    assert _total(bracket, played, aq) <= naive


def test_seed_bracket_avoids_a_solvable_rematch():
    # Two teams that met TWICE in the regular season; with plenty of alternative
    # same-band opponents, the bracketer should pull them apart.
    seeds = [f"T{i:02d}" for i in range(16)]
    aq = set()
    # find the pure-seed first-round pairing and force a heavy rematch on one pair
    pairs = _round1_pairs(seeds)
    h0, a0 = pairs[0][1], pairs[0][2]
    played = Counter({frozenset((h0, a0)): 3})                    # 3 meetings → near-veto
    bracket = _seed_bracket(seeds, aq, played)
    # that exact rematch should no longer be a first-round pair
    assert not any(frozenset((h, a)) == frozenset((h0, a0)) for _b, h, a in bracket)
    assert _total(bracket, played, aq) == 0


# --- byes never double up in one pairing ------------------------------------
#
# ‼️ A PAIRING WITH TWO EMPTY SLOTS IS NOT A BYE, IT IS A MATCH THAT DOES NOT EXIST.
# Whoever is drawn opposite it advances twice without playing, the round after the
# first stops being half the size of the one before it, and `state._bracket_canvas`
# — which links bracket columns positionally on exactly that halving — then draws
# the tree wrong.
#
# `seeded_draw` gives byes to the top seeds' first-round opponents and used to drop
# any REMAINING byes on random open slots with no partner check. That is invisible
# until byes outnumber seeds, which needs a field well under the bracket size: a 128
# draw seeds 32, so a field of 82-92 needs 36-46 byes and leaked one past round one
# in most draws. Measured before the fix: sizes 82-92 failed, 93+ (<= 35 byes) never
# did — and the JHSAA individual tournaments field 82-107, so most boys'
# classifications sat in the broken band.
#
# It is ALWAYS avoidable: `n` is the smallest power of two >= `n_real`, so
# `n_real > n / 2` and the byes needed are fewer than the pairings available.

def _round_shape_is_clean(n, sizes):
    """Every round after the first is exactly half the field still alive."""
    if sum(sizes) != n - 1:
        return False
    alive = n
    for i, s in enumerate(sizes):
        if i > 0 and alive - 2 * s:
            return False
        alive -= s
    return True


def test_no_pairing_is_given_two_byes_at_any_field_size():
    import random as _random
    from engine.tournament import run_tournament

    def play(a, b, *, seed):
        return a if _random.Random(seed).random() < 0.5 else b

    for n in list(range(3, 40)) + list(range(60, 135)) + [200, 257]:
        for trial in range(4):
            r = run_tournament(list(range(n)), seed=9000 + trial, play=play,
                               key=lambda e: -e)
            sizes = [len(x) for x in r.rounds]
            assert _round_shape_is_clean(n, sizes), (n, trial, sizes)


def test_the_jhsaa_individual_field_sizes_draw_clean():
    """The real 2041 association: girls' classes field 85-107 and boys' 82-95, and
    82-92 is exactly the band that used to leak. Pinned separately from the sweep
    above so a regression names the league it breaks."""
    import random as _random
    from engine.tournament import run_tournament

    def play(a, b, *, seed):
        return a if _random.Random(seed).random() < 0.5 else b

    for n in (82, 83, 84, 85, 86, 87, 88, 89, 90, 92, 95, 96, 97, 100, 107):
        for trial in range(6):
            r = run_tournament(list(range(n)), seed=4200 + trial, play=play,
                               key=lambda e: -e)
            sizes = [len(x) for x in r.rounds]
            assert _round_shape_is_clean(n, sizes), (n, trial, sizes)
            # …so the opening round reduces the field to exactly the bracket's
            # half — 64 for every one of these, since they all sit in a 128 draw —
            # and round two pairs all of it with nobody sitting out.
            alive_after_r1 = n - sizes[0]
            assert alive_after_r1 == 64, (n, sizes)
            assert sizes[1] * 2 == alive_after_r1, (n, sizes)

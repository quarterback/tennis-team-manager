"""Bracketing: selection and seeding are separate from bracket construction. After
teams are seeded, the draw swaps WITHIN seed bands (seed integrity preserved) to
minimise first-round penalties — same-conference, regular-season rematches (scaled
by how many times they met), and AQ-vs-AQ."""
from collections import Counter

from app.seasonmode import (_meeting_penalty, _pair_penalty, _seed_bracket,
                            _round1_pairs, _true_seed_protected, _TRUE_SEED_TOP,
                            _PEN_SAME_CONF, _PEN_REMATCH,
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
    conf = {"A": "ACC", "B": "ACC", "C": "SEC", "D": "B1G"}
    aq = {"A", "B"}
    met_twice = Counter({frozenset(("A", "B")): 2})
    # A vs B: same conf + 2 meetings + AQ-vs-AQ
    assert _pair_penalty("A", "B", conf, met_twice, aq) == _PEN_SAME_CONF + _PEN_MEET2 + _PEN_AQ_VS_AQ
    # C vs D: nothing in common, never met
    assert _pair_penalty("C", "D", conf, met_twice, aq) == 0
    # a 2nd meeting is penalised harder than a 1st
    once = Counter({frozenset(("C", "D")): 1})
    twice = Counter({frozenset(("C", "D")): 2})
    assert (_pair_penalty("C", "D", conf, twice, set())
            > _pair_penalty("C", "D", conf, once, set()))


def _total(pairs, conf, played, aq):
    return sum(_pair_penalty(h, a, conf, played, aq) for _b, h, a in pairs)


def test_seed_bracket_never_worsens_and_is_valid():
    # 16 seeds across 4 conferences (4 each) — pure seeding creates some
    # same-conference first-rounders the bracketer can swap apart.
    seeds = [f"T{i:02d}" for i in range(16)]
    confs = ["ACC", "SEC", "B1G", "P12"]
    conf_of = {t: confs[i % 4] for i, t in enumerate(seeds)}
    played = Counter()
    aq = set()
    naive = _total(_round1_pairs(seeds), conf_of, played, aq)
    bracket = _seed_bracket(seeds, aq, conf_of, played)
    # valid: every team placed exactly once, n/2 pairs
    placed = [x for _b, h, a in bracket for x in (h, a)]
    assert sorted(placed) == sorted(seeds)
    assert len(bracket) == 8
    # the draw never increases the penalty vs the pure-seed placement
    assert _total(bracket, conf_of, played, aq) <= naive


def test_true_seed_protected_only_women_and_only_top16():
    # Women: the top 16 national seeds are exempt from conference separation; men: none.
    schools = [f"S{i:02d}" for i in range(64)]
    women = _true_seed_protected({"gender": "women"}, schools)
    assert women == frozenset(schools[:_TRUE_SEED_TOP])
    assert _true_seed_protected({"gender": "men"}, schools) == frozenset()


def test_pair_penalty_exempts_protected_from_same_conf():
    conf = {"A": "SEC", "B": "SEC", "C": "SEC", "D": "SEC"}
    aq = set()
    played = Counter()
    # unprotected same-conf pair still charged
    assert _pair_penalty("C", "D", conf, played, aq) == _PEN_SAME_CONF
    # a protected team on either side drops ONLY the conference charge
    assert _pair_penalty("A", "B", conf, played, aq, frozenset({"A"})) == 0
    assert _pair_penalty("A", "B", conf, played, aq, frozenset({"B"})) == 0
    # rematch/AQ survive protection — only the conference principle is dropped
    met = Counter({frozenset(("A", "B")): 1})
    assert (_pair_penalty("A", "B", conf, met, {"A", "B"}, frozenset({"A"}))
            == _PEN_REMATCH + _PEN_AQ_VS_AQ)


def test_seed_bracket_true_seed_keeps_top16_in_place():
    # An all-one-conference top band: with conference separation the bracketer would
    # shuffle the top seeds apart; under the women's true-seed exemption it must not.
    seeds = [f"T{i:02d}" for i in range(16)]
    conf_of = {t: "SEC" if i < _TRUE_SEED_TOP else "ACC" for i, t in enumerate(seeds)}
    played = Counter()
    aq = set()
    protected = frozenset(seeds[:_TRUE_SEED_TOP])   # all 16 here are "top 16"
    bracket = _seed_bracket(seeds, aq, conf_of, played, protected)
    # pure-seed placement is preserved exactly — nobody moved for conference reasons
    assert bracket == _round1_pairs(seeds)
    # the exemption zeroes the conference penalty for the protected field...
    assert sum(_pair_penalty(h, a, conf_of, played, aq, protected)
               for _b, h, a in bracket) == 0
    # ...while WITHOUT the exemption the same all-SEC top band would have been charged,
    # so men (protected=empty) still get the separation treatment.
    assert _total(bracket, conf_of, played, aq) > 0


def test_seed_bracket_avoids_a_solvable_rematch():
    # Two non-conference teams that met TWICE in the regular season; with plenty of
    # alternative same-band opponents, the bracketer should pull them apart.
    seeds = [f"T{i:02d}" for i in range(16)]
    conf_of = {t: "C{}".format(i) for i, t in enumerate(seeds)}   # all distinct confs
    aq = set()
    # find the pure-seed first-round pairing and force a heavy rematch on one pair
    pairs = _round1_pairs(seeds)
    h0, a0 = pairs[0][1], pairs[0][2]
    played = Counter({frozenset((h0, a0)): 3})                    # 3 meetings → near-veto
    bracket = _seed_bracket(seeds, aq, conf_of, played)
    # that exact rematch should no longer be a first-round pair
    assert not any(frozenset((h, a)) == frozenset((h0, a0)) for _b, h, a in bracket)
    assert _total(bracket, conf_of, played, aq) == 0

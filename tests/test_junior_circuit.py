import random

from engine import run_tournament, finish_label
from app.juniors import generate_class, national_rankings
from app.junior_circuit import (run_junior_circuit, assign_tiers, CALENDAR,
                                 TIER_LABELS, US_NATIONAL_BADGES, US_STATE_BADGES,
                                 INTL_GLOBAL_BADGES, INTL_NATION_BADGES)


# --------------------------------------------------------------------------
# Engine: the reusable individual-tournament framework
# --------------------------------------------------------------------------
def _higher_wins(a, b, *, seed):
    """Deterministic 'play': the higher-rated entrant always advances."""
    return a if a >= b else b


def test_tournament_champion_is_the_top_rating_when_deterministic():
    entrants = [5, 9, 1, 7, 3, 8, 2, 6]
    res = run_tournament(entrants, seed=1, play=_higher_wins, key=lambda x: x)
    assert res.champion == 9
    assert res.runner_up is not None
    # The #1 seed (rating 9) is never eliminated; everyone else has a finish.
    assert res.finish_of(0) == "Champion"
    assert all(res.finish_of(i) is not None for i in range(1, len(entrants)))


def test_tournament_finish_labels_are_valid_and_unique_per_round():
    entrants = list(range(16, 0, -1))   # 16 distinct ratings
    res = run_tournament(entrants, seed=2, play=_higher_wins, key=lambda x: x)
    labels = [res.finish_of(i) for i in range(16)]
    assert labels[0] == "Champion"
    assert labels.count("Finalist") == 1
    assert labels.count("Semifinalist") == 2
    assert labels.count("Quarterfinalist") == 4
    assert labels.count("R16") == 8


def test_tournament_handles_byes_for_non_power_of_two_fields():
    # 6 entrants → padded to 8; the two top seeds get byes but still finish.
    entrants = [10, 60, 30, 50, 20, 40]
    res = run_tournament(entrants, seed=3, play=_higher_wins, key=lambda x: x)
    assert res.champion == 60
    assert all(res.finish_of(i) is not None for i in range(len(entrants)))


def test_tournament_is_deterministic_with_real_engine():
    from engine import random_player
    rng = random.Random(11)
    players = [random_player(rng, f"P{i}", "US") for i in range(8)]
    a = run_tournament(players, seed=99, key=lambda p: p.overall)
    b = run_tournament(players, seed=99, key=lambda p: p.overall)
    assert a.champion_idx == b.champion_idx
    assert a.elim_size == b.elim_size


def test_finish_label_mapping():
    assert finish_label(2, champion=True) == "Champion"
    assert finish_label(2) == "Finalist"
    assert finish_label(4) == "Semifinalist"
    assert finish_label(8) == "Quarterfinalist"
    assert finish_label(16) == "R16"
    assert finish_label(32) == "R32"


# --------------------------------------------------------------------------
# Junior circuit: the recruit-history generator
# --------------------------------------------------------------------------
def _class(n=240, seed=5, gender="male"):
    k = generate_class(random.Random(seed), n=n, grad_year=2026, gender=gender,
                       intl_share=0.35)
    national_rankings(k)
    run_junior_circuit(k, seed=seed)
    return k


_CALENDAR_NAMES = {name for name, _level, _month in CALENDAR}
_ALL_BADGES = {label for _t, label in
               US_NATIONAL_BADGES + US_STATE_BADGES + INTL_GLOBAL_BADGES + INTL_NATION_BADGES}


def test_tiers_assigned_and_populated():
    k = _class()
    tiers = {p.junior_tier for p in k.recruits}
    assert tiers == {1, 2, 3, 4}
    assert all(p.junior_tier in TIER_LABELS for p in k.recruits)


def test_every_recruit_has_a_lived_in_resume():
    k = _class()
    for p in k.recruits:
        assert p.junior_results, f"{p.name} has no junior results"
        assert p.ranking_history
        # badges are optional (weak players earn none) but must be valid labels
        assert set(p.junior_badges) <= _ALL_BADGES


def test_matches_carry_scores_and_opponents():
    """The full engine plays real matches — scores and opponent names on record."""
    k = _class()
    for p in k.recruits:
        assert p.junior_matches                               # everyone played
        for m in p.junior_matches:
            assert set(m.keys()) == {"date", "tournament", "round", "opponent", "score", "won"}
            assert m["tournament"] in _CALENDAR_NAMES         # closed, real events
            assert m["opponent"] and m["opponent"] != p.name  # a real, different rival
            assert "-" in m["score"]                          # a real scoreline


def test_closed_ecosystem_every_opponent_is_a_recruit():
    """No anonymous opponents or synthetic filler — every rival is in the class."""
    k = _class()
    names = {p.name for p in k.recruits}
    for p in k.recruits:
        for m in p.junior_matches:
            assert m["opponent"] in names


def test_matches_are_reciprocal():
    """If A played B, B's record shows the same match with the result flipped."""
    k = _class(n=120)
    by_name = {p.name: p for p in k.recruits}
    for p in k.recruits:
        for m in p.junior_matches:
            opp = by_name[m["opponent"]]
            mirror = [q for q in opp.junior_matches
                      if q["opponent"] == p.name and q["tournament"] == m["tournament"]
                      and q["round"] == m["round"]]
            assert mirror, f"{opp.name} is missing the mirror of {p.name}'s match"
            assert mirror[0]["won"] != m["won"]               # exactly one winner


def test_str_is_results_based_and_dynamic():
    """STR evolves from results: anchored near ability but it grows and regresses,
    and reliability builds with matches played."""
    k = _class()
    for p in k.recruits:
        assert p.junior_str > 0
        assert 0.0 <= p.junior_str_reliability <= 1.0
    deltas = [p.junior_str - p.str_value() for p in k.recruits]
    assert any(d > 0.3 for d in deltas)                       # someone grew
    assert any(d < -0.3 for d in deltas)                      # someone regressed


def test_ranking_history_carries_evolving_str():
    k = _class()
    p = max(k.recruits, key=lambda x: len(x.junior_matches))
    assert all("str" in h and h["str"] > 0 for h in p.ranking_history)


def test_ranking_history_progresses_in_time():
    k = _class()
    p = max(k.recruits, key=lambda x: len(x.junior_badges))
    dates = [h["date"] for h in p.ranking_history]
    assert dates == sorted(set(dates), key=dates.index)       # ordered, no dupes
    assert len(p.ranking_history) == 4
    labels = {h["primary_label"] for h in p.ranking_history}
    assert labels <= {"National", "Global"}                   # one ladder per recruit


def test_badges_match_best_rank_reached():
    """A badge is awarded iff the best (lowest) rank reached clears its threshold."""
    k = _class()
    for p in k.recruits:
        if not p.domestic:
            continue
        best_nat = min(h["primary"] for h in p.ranking_history)
        expected = {label for thresh, label in US_NATIONAL_BADGES if best_nat <= thresh}
        got_nat = {b for b in p.junior_badges if b in {l for _t, l in US_NATIONAL_BADGES}}
        assert got_nat == expected


def test_domestic_and_international_use_different_ladders():
    k = _class()
    us_labels = {l for _t, l in US_NATIONAL_BADGES + US_STATE_BADGES}
    intl_labels = {l for _t, l in INTL_GLOBAL_BADGES + INTL_NATION_BADGES}
    for p in k.recruits:
        badges = set(p.junior_badges)
        if p.domestic:
            assert badges <= us_labels
        else:
            assert badges <= intl_labels


def test_points_ledger_is_frozen_and_bounded():
    """Every recruit gets junior_points + tournaments_played on an ITF-scaled best-6
    ledger, and the combined total = singles + ¼·doubles stays bounded."""
    from app.junior_circuit import (event_points, doubles_event_points, JUNIOR_POINTS,
                                     JUNIOR_DOUBLES_POINTS, BEST_N, DOUBLES_WEIGHT)
    k = _class(n=300)
    assert event_points("Major", "Champion") == 1000        # ITF Grand Slam title
    assert event_points("State", "Quarterfinalist") == 5    # ITF Grade 5 QF
    assert doubles_event_points("Major", "Champion") == 750  # ITF GS doubles title
    assert event_points("Major", "did-not-play") == 0
    for p in k.recruits:
        assert isinstance(p.junior_points, int) and p.junior_points >= 0
        assert p.tournaments_played == len(p.junior_results)   # count matches the résumé
        # Combined ledger = singles + ¼ × doubles (ITF CJR).
        assert p.junior_points == int(p.singles_points + DOUBLES_WEIGHT * p.doubles_points)
    assert sum(1 for p in k.recruits if p.tournaments_played >= 1) >= 0.9 * len(k.recruits)
    # Best-6 cap: 6 Major titles + 6 top bonuses, plus ¼ of 6 Major doubles titles.
    smax = BEST_N * max(JUNIOR_POINTS["Champion"].values()) + BEST_N * 75
    dmax = BEST_N * max(JUNIOR_DOUBLES_POINTS["Champion"].values())
    assert all(p.junior_points <= smax + DOUBLES_WEIGHT * dmax for p in k.recruits)


def test_doubles_participation_and_specialist_str():
    """Doubles is grit-driven (not everyone plays), folds into the one ledger, and
    yields a doubles STR that can diverge from singles STR — the specialist signal."""
    k = _class(n=400)
    played = [p for p in k.recruits if p.doubles_played > 0]
    assert 0.3 < len(played) / len(k.recruits) < 0.95          # some, not all, play
    # Grittier players (stamina/resilience/competitiveness) play doubles more often.
    grit = lambda p: sum(p.current_grade(a) for a in ("stamina", "resilience", "competitiveness")) / 3
    hi = [p for p in k.recruits if grit(p) >= 55]
    lo = [p for p in k.recruits if grit(p) <= 45]
    rate = lambda g: sum(1 for p in g if p.doubles_played) / max(1, len(g))
    assert rate(hi) > rate(lo)
    # Doubles players get a doubles STR; across the pool it diverges from singles STR.
    assert all(p.junior_doubles_str is not None for p in played)
    assert any(p.junior_doubles_str - p.junior_str > 1 for p in played)   # specialists
    assert any(p.junior_doubles_str - p.junior_str < -1 for p in played)  # singles types


def test_points_rank_diverges_from_recruiting_board():
    """The points ledger and the consensus recruiting board are different rankings —
    that divergence is the gem signal — yet broadly agree at the very top."""
    from app.juniors import points_rankings, us_points_rankings, nation_points_top
    k = _class(n=400)
    ranked = points_rankings(k)
    assert [p.points_rank for p in ranked[:5]] == [1, 2, 3, 4, 5]
    assert ranked[0].junior_points >= ranked[-1].junior_points
    # Distinct orderings (not a relabel of the board).
    assert any(p.points_rank != p.recruit_rank for p in ranked)
    # US board is domestic-only; nation boards are international, densest first.
    assert all(p.domestic for p in us_points_rankings(k))
    boards = nation_points_top(k, per=10, min_players=5)
    assert boards and all(len(players) <= 10 for _n, players in boards)
    assert all(not p.domestic for _n, players in boards for p in players)


def test_super_bloomers_climb_while_early_bloomers_plateau():
    """Staggered junior development surfaces the bloom/plateau arc: across the season
    high-interest recruits (super-bloomers) climb the national board on average,
    while low-interest early bloomers hold flat or slide as peers pass them."""
    k = _class(n=300)
    def climb(p):  # +ve = rank improved (number got smaller) from first to last snapshot
        return p.ranking_history[0]["primary"] - p.ranking_history[-1]["primary"]
    dom = [p for p in k.recruits if p.domestic and len(p.ranking_history) >= 2]
    bloomers = [climb(p) for p in dom if p.tier == 3]          # super-bloomers
    ordinary = [climb(p) for p in dom if p.tier == 1]          # ordinary/early
    assert bloomers and ordinary
    assert sum(bloomers) / len(bloomers) > sum(ordinary) / len(ordinary)


def test_recruiting_ability_is_not_mutated_by_the_circuit():
    """The junior climb runs on throwaway copies — the recruit's recruiting-time
    ability (str_value/stars) is identical before and after the circuit."""
    import random as _r
    from app.juniors import generate_class as _gc, national_rankings as _nr
    from app.junior_circuit import run_junior_circuit as _run
    k = _gc(_r.Random(5), n=120, grad_year=2026, gender="male", intl_share=0.35)
    _nr(k)
    before = {p.pid: (round(p.str_value(), 4), p.recruit_stars) for p in k.recruits}
    _run(k, seed=5)
    after = {p.pid: (round(p.str_value(), 4), p.recruit_stars) for p in k.recruits}
    assert before == after


def test_circuit_is_deterministic():
    a = _class(seed=8)
    b = _class(seed=8)
    a_by = {p.pid: p for p in a.recruits}
    for p in b.recruits:
        q = a_by[p.pid]
        assert p.junior_results == q.junior_results
        assert p.junior_badges == q.junior_badges
        assert p.junior_tier == q.junior_tier


def test_circuit_run_is_idempotent():
    k = _class(seed=9)
    before = [list(p.junior_results) for p in k.recruits]
    run_junior_circuit(k, seed=9)        # guard: should be a no-op
    after = [list(p.junior_results) for p in k.recruits]
    assert before == after

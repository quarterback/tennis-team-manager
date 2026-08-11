"""JHSAA schedule shape (owner rule 2027-08).

District play is a DOUBLE round-robin — home and away — and the rest of the card is
non-district, drawn on geography, talent and availability, at your classification or one
apart. Every one of these was got wrong once: a single round-robin, a uniform-random
opponent draw, and a crossover locked inside one classification.

And then the round-robin itself was wrong in a way that only showed on a rendered card.
`for a: for b: for leg in (0, 1)` is a correct double round robin and a schedule no high
school has ever played — the two meetings with an opponent landed on CONSECUTIVE dates,
every opponent, all season:

    Mar 10  at Alder Landing        Mar 15  at Altamonte
    Mar 12  vs Alder Landing        Mar 17  vs Altamonte

The league is now two SEPARATED passes with the non-district card spread through them:

    early non-district → pass 1 → mid-season window → pass 2 → late tune-up

These pin the separation, the venue reversal, the venue balance, and the fact that the
mid-season challenge can never reach district place.

Scoped to a few districts so the file stays fast, but it plays the SHIPPED path
(`jhsaa.play_regular_season`) rather than a re-implementation of the order — the order
is the thing under test.
"""
import collections
import random

import pytest

from app import jhsaa


@pytest.fixture(scope="module")
def played():
    """Two 7A districts and two 6A, played in `run_season`'s order and windows."""
    by_group = {}
    for group in ("7A", "6A"):
        d = jhsaa.districts("girls", group)
        by_group[group] = {name: jhsaa.district_teams(d[name], 2030)
                           for name in sorted(d)[:2]}
    return jhsaa.play_regular_season(by_group, 2030, "girls")


def _regular(t):
    return [x for x in t.schedule if x["phase"] == "regular"]


def _district(t):
    return [x for x in _regular(t) if x["district"]]


def _peers(t, played):
    return sum(1 for o in played
               if (o.school.group, o.school.district)
               == (t.school.group, t.school.district)) - 1


# --- the round robin itself ---------------------------------------------------

def test_district_play_is_a_double_round_robin(played):
    """Every league opponent exactly twice, once home and once away."""
    for t in played:
        legs = collections.defaultdict(list)
        for x in _district(t):
            legs[x["opp"]].append(x["home"])
        assert len(legs) == _peers(t, played), (t.school.name, len(legs))
        for opp, homes in legs.items():
            assert sorted(homes) == [False, True], (t.school.name, opp, homes)


def test_the_second_meeting_reverses_the_venue(played):
    """Not just 'one of each' — the LATER date must be the away one if the earlier was
    home. One orientation bit per pairing serves both passes, so this holds by
    construction and the venue balancer cannot break it."""
    for t in played:
        met = collections.defaultdict(list)
        for i, x in enumerate(_district(t)):
            met[x["opp"]].append((i, x["home"]))
        for opp, ms in met.items():
            (_, first), (_, second) = sorted(ms)
            assert first != second, (t.school.name, opp, ms)


def test_no_district_opponent_on_consecutive_dates(played):
    """The bug this rewrite exists for. A district of two has only one pairing and
    cannot avoid it; nothing here is that small, and the assertion says so."""
    for t in played:
        assert _peers(t, played) >= 2, "fixture districts are too small to test this"
        dates = [x["opp"] for x in _district(t)]
        back_to_back = [a for a, b in zip(dates, dates[1:]) if a == b]
        assert not back_to_back, (t.school.name, back_to_back)


def test_the_two_meetings_are_a_meaningful_part_of_the_season_apart(played):
    """A return match belongs weeks later, not on the next available date. The floor is
    half a pass (`_mirror_orders`), and the mid-season window sits on top of that."""
    for t in played:
        dates = _district(t)
        n = len(dates)
        met = collections.defaultdict(list)
        for i, x in enumerate(dates):
            met[x["opp"]].append(i)
        for opp, (first, second) in ((o, sorted(v)) for o, v in met.items()):
            assert second - first >= n // 4, (t.school.name, opp, first, second, n)


def test_district_home_and_away_dates_are_balanced(played):
    """A double round robin gives every team exactly one home and one away date against
    every opponent, so the totals are even by construction — what needs checking is that
    they are not clumped into long runs of one venue."""
    for t in played:
        seq = [x["home"] for x in _district(t)]
        assert abs(2 * sum(seq) - len(seq)) <= 1, (t.school.name, seq)
        run = worst = 1
        for a, b in zip(seq, seq[1:]):
            run = run + 1 if a == b else 1
            worst = max(worst, run)
        assert worst <= 4, (t.school.name, worst, seq)


def test_the_district_card_is_two_passes_not_a_series(played):
    """Structural: the first half of a team's league dates hits every opponent once, and
    so does the second. That is what makes it two passes rather than a home-and-home."""
    for t in played:
        dates = [x["opp"] for x in _district(t)]
        half = len(dates) // 2
        assert len(set(dates[:half])) == half, (t.school.name, dates[:half])
        assert len(set(dates[half:])) == len(dates) - half, (t.school.name, dates[half:])


# --- the windows --------------------------------------------------------------

def test_the_season_opens_and_breaks_for_non_district_play(played):
    """The shape: non-district before the league, a window in the middle, and the league
    split around it. Previously every non-district dual came first and the league ran to
    the end, so `flags == sorted(flags)` held — it must not any more."""
    windows = 0
    for t in played:
        flags = [x["district"] for x in _regular(t)]
        assert flags[0] is False, (t.school.name, flags)     # opens non-district
        assert True in flags, t.school.name
        # count non-district groups that fall BETWEEN league dates
        first_d, last_d = flags.index(True), len(flags) - 1 - flags[::-1].index(True)
        if False in flags[first_d:last_d]:
            windows += 1
    assert windows == len(played), f"only {windows}/{len(played)} cards had a mid-season window"


def test_non_district_count_is_an_allowance_not_a_season_total(played):
    for t in played:
        n = sum(1 for x in _regular(t) if not x["district"])
        assert jhsaa.NONDISTRICT_MIN <= n <= jhsaa.NONDISTRICT_MAX, (t.school.name, n)


def test_no_opponent_is_played_more_than_twice_in_the_regular_season(played):
    """Non-district play must not quietly recreate a second home-and-home."""
    for t in played:
        counts = collections.Counter(x["opp"] for x in _regular(t))
        assert not [o for o, n in counts.items() if n > 2], (t.school.name, counts)


def test_non_district_stays_within_one_classification(played):
    """A 7A card mixes 7A and 6A; it never lands on 1A."""
    by = {t.school.name: t for t in played}
    seen = 0
    for t in played:
        for x in _regular(t):
            o = by.get(x["opp"])
            if x["district"] or o is None:
                continue
            seen += 1
            gap = abs(jhsaa._GROUP_IX[o.school.group] - jhsaa._GROUP_IX[t.school.group])
            assert gap <= 1, (t.school.name, x["opp"], gap)
    assert seen, "no cross-district duals were scheduled at all"


def test_non_district_opponents_are_never_from_your_own_district(played):
    by = {t.school.name: t for t in played}
    for t in played:
        for x in _regular(t):
            o = by.get(x["opp"])
            if x["district"] or o is None:
                continue
            assert (o.school.group, o.school.district) \
                != (t.school.group, t.school.district), (t.school.name, x["opp"])


def test_non_district_draw_prefers_near_opponents_on_geography_and_talent(played):
    """Not a golden value — a directional check that the draw is scored, not uniform.
    Compare each actual non-district opponent against the classification-eligible field:
    the picks must sit well inside it on both geography and talent."""
    by = {t.school.name: t for t in played}
    geo_pick, geo_all, tal_pick, tal_all = [], [], [], []
    for t in played:
        gi = jhsaa._GROUP_IX[t.school.group]
        st = jhsaa._strength(t)
        field = [o for o in played if o is not t
                 and abs(jhsaa._GROUP_IX[o.school.group] - gi) <= 1
                 and (o.school.group, o.school.district)
                 != (t.school.group, t.school.district)]
        if not field:
            continue
        geo_all += [jhsaa._geo_gap(t.school, o.school) for o in field]
        tal_all += [abs(jhsaa._strength(o) - st) for o in field]
        for x in _regular(t):
            o = by.get(x["opp"])
            if x["district"] or o is None or x.get("challenge"):
                continue
            geo_pick.append(jhsaa._geo_gap(t.school, o.school))
            tal_pick.append(abs(jhsaa._strength(o) - st))
    assert geo_pick and tal_pick
    mean = lambda v: sum(v) / len(v)                          # noqa: E731
    assert mean(geo_pick) < mean(geo_all), "draw ignores geography"
    assert mean(tal_pick) < mean(tal_all), "draw ignores talent"


# --- the mid-season challenge -------------------------------------------------

def test_the_challenge_never_touches_district_records(played):
    """It is a LABEL on a non-district dual, not a phase. If it were ever marked
    `district` it would rewrite a league table with a game against another league."""
    seen = 0
    for t in played:
        for x in _regular(t):
            if not x.get("challenge"):
                continue
            seen += 1
            assert x["district"] is False, (t.school.name, x["opp"])
    assert seen, "no challenge duals were scheduled at all"
    # and the league table still adds up to league play alone
    for t in played:
        assert t.dwins + t.dlosses == len(_district(t)), t.school.name


def test_the_challenge_is_cross_district_and_sits_in_the_window(played):
    by = {t.school.name: t for t in played}
    for t in played:
        flags = [x["district"] for x in _regular(t)]
        first_d, last_d = flags.index(True), len(flags) - 1 - flags[::-1].index(True)
        for i, x in enumerate(_regular(t)):
            if not x.get("challenge"):
                continue
            o = by.get(x["opp"])
            if o is not None:
                assert o.school.district != t.school.district, (t.school.name, x["opp"])
            assert first_d < i < last_d, (t.school.name, i, first_d, last_d)


def test_challenge_hosting_is_not_systematically_one_sided(played):
    """Hosting alternates on a hash of the pairing and the year, so the slate as a whole
    should be near an even split rather than always favouring, say, the first name."""
    home = sum(1 for t in played for x in _regular(t)
               if x.get("challenge") and x["home"])
    total = sum(1 for t in played for x in _regular(t) if x.get("challenge"))
    assert total, "no challenge duals"
    assert 0.25 <= home / total <= 0.75, (home, total)


# --- determinism and rotation -------------------------------------------------

def test_the_same_seed_produces_the_same_schedule():
    """Same salt and year, same card — the save seed has to reproduce a season."""
    def card(salt):
        d = jhsaa.districts("girls", "7A")
        name = sorted(d)[0]
        teams = jhsaa.district_teams(d[name], 2030, salt)
        return [[(h.school.name, a.school.name) for h, a in rnd]
                for rnd in jhsaa.district_rounds(teams, 2030, salt)]

    assert card("save-a") == card("save-a")
    assert card("save-a") != card("save-b")


def test_the_rotation_varies_by_season():
    """Several deterministic rotations, so a program's opponent order is not identical
    every year while every one of them is reproducible."""
    d = jhsaa.districts("girls", "7A")
    name = sorted(d)[0]
    orders = set()
    for year in range(2030, 2036):
        teams = jhsaa.district_teams(d[name], year, "s")
        rounds = jhsaa.district_rounds(teams, year, "s")
        first = teams[0].school.name
        seq = []
        for rnd in rounds:
            for h, a in rnd:
                if first in (h.school.name, a.school.name):
                    seq.append(a.school.name if h.school.name == first else h.school.name)
        orders.add(tuple(seq))
    assert len(orders) > 1, "every season produced the identical opponent order"


def test_mirror_orders_always_clear_half_a_pass():
    """The separation floor, at every district size. A plain reverse scores 1 — the
    last opponent of pass 1 is the first of pass 2 — which is why the second pass is a
    rotated mirror rather than `reversed()`."""
    for r in range(1, 13):
        for order in jhsaa._mirror_orders(r):
            pos = {x: j for j, x in enumerate(order)}
            assert sorted(order) == list(range(r))
            assert min(r + pos[i] - i for i in range(r)) >= (r + 1) // 2, (r, order)


def test_every_round_robin_size_is_a_complete_round_robin():
    """The circle method, at every size a district can be: every pairing exactly once,
    and no team twice in a round."""
    for n in range(2, 14):
        rounds = jhsaa._rr_rounds(n)
        pairs = [p for rnd in rounds for p in rnd]
        assert len(pairs) == len(set(pairs)) == n * (n - 1) // 2, n
        for rnd in rounds:
            teams = [t for p in rnd for t in p]
            assert len(teams) == len(set(teams)), (n, rnd)

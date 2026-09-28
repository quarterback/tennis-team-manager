"""COACH INVESTMENT — Future Value and Program Interest (owner spec 2026-09).

Two bounded judgments in `coach_eval`, resolved per team from the named staff:
investment in what the staff ESTIMATES a young player will become, and trust
earned by seasons in the program. Selection only; nothing changes how anybody
plays. See `docs/AAR-jhsaa-early-participation.md` §9.
"""
import dataclasses
import json

import pytest

from app import jhsaa as jh
from app import jhsaa_coaches as jc


class P:
    """A stand-in Prospect: the fields the terms read and nothing else."""
    def __init__(self, pid, ovr, pot, grade, entry, early=(), str_v=None):
        self.pid, self._ovr, self.grade, self.entry_year = pid, ovr, grade, entry
        self.jhsaa = {"pot_est": pot, "early": list(early)}
        self._str = str_v if str_v is not None else ovr
    def current_overall(self):
        return self._ovr
    def ceiling_overall(self):
        return self.jhsaa["pot_est"]
    def str_value(self):
        return self._str


# --- the two terms --------------------------------------------------------------

def test_future_value_reads_the_estimate_and_the_horizon_and_is_capped():
    seventh = P("a", 30.0, 60.0, 7, 2102)
    senior = P("b", 30.0, 60.0, 12, 2097)
    assert jh.future_value(seventh, 1.0) == pytest.approx(0.20 * 1.0 * 1.0 * 30.0)
    assert jh.future_value(senior, 1.0) == 0.0            # no imagined future seasons
    # freshmen and sophomores keep most of it (owner: no rapid fall at 9th)
    assert jh.FUTURE_HORIZON[9] >= 0.85 and jh.FUTURE_HORIZON[10] >= 0.75
    assert jh.FUTURE_HORIZON[11] < 0.5 and jh.FUTURE_HORIZON[12] == 0.0
    big = P("c", 20.0, 90.0, 8, 2102)
    assert jh.future_value(big, 1.6) == jh.FUTURE_MAX     # the proof tier's ceiling
    # it never reads the true ceiling when an estimate exists
    est = P("d", 40.0, 45.0, 9, 2101)
    est.jhsaa["pot_est"] = 45.0
    assert jh.future_value(est, 1.0) == pytest.approx(0.20 * 0.9 * 5.0)
    assert jh.future_value(P("e", 50.0, 40.0, 9, 2101), 1.0) == 0.0   # no headroom
    assert jh.future_value(seventh, 0.0) == 0.0            # no staff, no term


def test_program_interest_is_tenure_times_class_times_loyalty_and_capped():
    senior6 = P("a", 52.0, 55.0, 12, 2100, early=(2098, 2099))
    senior4 = P("b", 52.0, 55.0, 12, 2100)
    assert jh.program_tenure(senior6, "S", 2103) == 6
    assert jh.program_tenure(senior4, "S", 2103) == 4
    assert jh.program_interest(senior6, 6, 1.6) == jh.INTEREST_MAX
    assert jh.program_interest(senior6, 6, 1.0) == pytest.approx(5.0)
    assert jh.program_interest(senior4, 4, 1.0) == pytest.approx(5.0 * 4 / 6)
    # accumulates gradually: a junior counts, a 7th/8th-grader does not
    junior = P("c", 52.0, 55.0, 11, 2101, early=(2099, 2100))
    assert 0 < jh.program_interest(junior, 5, 1.0) < jh.program_interest(senior6, 6, 1.0)
    assert jh.program_interest(P("d", 40.0, 60.0, 8, 2104, early=(2102, 2103)), 2, 1.6) == 0.0
    assert jh.program_interest(senior6, 6, 0.0) == 0.0     # no staff, no term


def test_a_transfer_brings_no_tenure_and_a_move_resets_it():
    p = P("a", 52.0, 55.0, 12, 2100)
    rec = {"from": "Origin", "gender": "girls", "entry": 2100, "seat": 3,
           "moves": [{"to": "New", "year": 2103}]}
    assert jh.program_tenure(p, "New", 2103, rec) == 1        # this season only
    assert jh.program_tenure(p, "Origin", 2103, rec) == 3     # the years before it
    assert jh.program_tenure(p, "Origin", 2102, rec) == 3


def test_the_senior_interest_rate_turns_a_close_call_and_collapses_on_a_gap():
    """52 vs 55: the six-year senior wins. 52 vs 59: coach-dependent. 52 vs 65:
    nobody benches a dramatically better player as a sentimental gesture."""
    senior = P("s", 52.0, 55.0, 12, 2097, early=(2095, 2096))
    def beats(fresh_ovr, loyalty_w):
        fresh = P("f", fresh_ovr, fresh_ovr + 5, 9, 2103)
        ten = jh.program_tenure(senior, "S", 2100)
        i = jh.program_interest(senior, ten, loyalty_w)
        # The two weights are DIFFERENT staff grades (Program builder vs
        # Development): a loyal coach need not be a development-minded one, so
        # the freshman's own future value is read at a neutral weight here.
        f = jh.future_value(fresh, 1.0)
        return jh.coach_eval(senior, interest=i) > jh.coach_eval(fresh, future=f)
    assert beats(55.0, 1.0)
    assert beats(59.0, 1.6) and not beats(59.0, 0.4)
    assert not beats(65.0, 1.6)


def test_coach_eval_with_no_terms_is_exactly_what_it_was():
    p = P("a", 47.3, 60.0, 10, 2101)
    assert jh.coach_eval(p) == 47.3
    assert jh.coach_eval(p, future=0.0, interest=0.0) == 47.3


# --- the staff, the team, the archive -------------------------------------------

def test_a_staff_effect_carries_the_weights_and_an_old_row_reads_them_off():
    lens = jh.CoachLens()
    e = jc.StaffEffect(lens=lens, culture=1.0, strategy="balanced", future=0.7, loyalty=0.4)
    back = jc._eff_from_json(jc._eff_to_json(e))
    assert back.future == 0.7 and back.loyalty == 0.4
    assert e.fingerprint() != dataclasses.replace(e, future=0.2).fingerprint()
    old = jc._eff_from_json(json.dumps({"read": 0.0, "trust": 1.0, "form": 1.0,
                                        "culture": 1.0, "strategy": "balanced"}))
    assert old.future is None and old.loyalty is None


def test_a_team_without_a_staff_has_neither_term_and_orders_on_ability():
    real = jh.load_schools("girls")[0]
    roster = jh.build_roster(real, 2027, "")
    ts = jh.TeamSeason(school=real, roster=roster)
    assert ts.future == {} and ts.interest == {} and ts.future_w == 0.0
    order = jh._order(ts)
    assert [p.pid for p in order] == [p.pid for p in
                                      sorted(roster, key=lambda p: (-p.current_overall(),
                                                                    -p.str_value()))]


def test_investment_terms_resolve_once_per_roster_and_key_on_pid():
    # a 7th-grader always carries the two early seasons it is rostered for
    roster = [P("a", 30.0, 60.0, 7, 2102, early=(2100, 2101)),
              P("b", 52.0, 55.0, 12, 2097, early=(2095, 2096)),
              P("c", 50.0, 50.0, 12, 2097)]
    fut, itr, ten = jh.investment_terms(roster, "S", 2100, 1.0, 1.0, {})
    assert set(fut) == {"a"} and set(itr) == {"b", "c"}
    assert ten == {"a": 1, "b": 6, "c": 4}
    assert itr["b"] > itr["c"]                         # six years beats four


def test_the_owners_read_override_round_trips():
    from app import overrides as ov
    ov.clear_jhsaa_read("pid-x")
    v0 = ov.jhsaa_read_version()
    ov.set_jhsaa_read("pid-x", "Some School", 4.5)
    assert ov.get_jhsaa_read("pid-x") == {"school": "Some School", "delta": 4.5}
    assert ov.get_jhsaa_reads()["pid-x"]["delta"] == 4.5
    assert ov.jhsaa_read_version() != v0
    ov.clear_jhsaa_read("pid-x")
    assert ov.get_jhsaa_read("pid-x") is None
    assert ov.jhsaa_read_version() == v0

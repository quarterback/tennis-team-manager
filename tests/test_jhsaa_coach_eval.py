"""THE COACH EVALUATION LAYER — selection is a judgment, not a talent sort.

    RAW ABILITY  →  COACH EVALUATION  →  LINEUP SELECTION  →  MATCH ENGINE
                                                              (raw ability)

`_order` used to be a pure OVR sort on the first dual of every season: `TeamSeason`
is rebuilt each year with an empty `records`, so a returning starter was re-ranked
from scratch against a freshman class the coach had never seen play.

Measured over the owner's real 2072→2075 saves, both genders, three transitions:
~6,500 returning varsity regulars a year, ~3.7% of whom (≈240, three quarters of
them juniors and seniors) essentially lost their place — and the MEDIAN one was
**3 OVR** short of his team's 11th man, with a newcomer above him in 98% of cases.

What these pin is the SHAPE of the fix rather than its calibration:

  * with no evidence and no coach, evaluation is exactly ability and results — the
    pre-layer ladder, to the bit, which is what every standalone caller still gets;
  * proof is a DISPLACEMENT THRESHOLD, not a reserved seat: a marginally better
    newcomer waits, a plainly better one plays and everyone below shifts down one;
  * nothing here reaches the match engine.
"""
import pytest

from app import jhsaa as jh


class _Eng:
    """The `engine.doubles` fallback path's inputs — `net_rating` and friends use
    these when a player carries no `rich` attribute dict, which is all this file
    needs to make one stub a better doubles player than another."""

    rich = None

    def __init__(self, net):
        self.movement = self.forehand = self.mental = net
        self.serve_power = self.serve_placement = net
        self.return_game = self.consistency = net


class _P:
    """The things the evaluation layer reads off a player, and a pid.

    `net` is the doubles aptitude the second captain's seat is chosen on; it
    defaults to tracking ability so a test that does not care about doubles gets
    the ordering it expects."""

    def __init__(self, pid, ovr, grade=12, strv=None, net=None):
        self.pid, self._ovr, self.grade = pid, ovr, grade
        self._str = strv if strv is not None else ovr
        self._net = ovr / 100.0 if net is None else net

    def current_overall(self):
        return self._ovr

    def str_value(self):
        return self._str

    def engine_player(self):
        return _Eng(self._net)


def _proof(**kw):
    """A `PriorSeason` that clears the regular bar unless a test says otherwise."""
    base = dict(apps=30, wins=22, losses=8, rank=6, flags=0, years=1)
    return jh.PriorSeason(**{**base, **kw})


def _team(roster, records=None, prior=None, lens=None, read=None):
    return jh.TeamSeason(school=jh.load_schools("boys")[0], roster=roster,
                         records=records or {}, prior=prior or {},
                         lens=lens or jh.CoachLens(), read=read or {})


# --- the layer is optional, and its absence is the old behaviour --------------

def test_with_no_evidence_and_no_coach_evaluation_is_exactly_ability():
    """Every standalone caller — a test, the lab's opening year, a calibration
    script — must get the pre-layer ladder to the bit, or the layer has silently
    become mandatory."""
    p = _P("a", 47.5)
    assert jh.coach_eval(p) == 47.5
    assert jh.coach_eval(p, None, lens=jh.CoachLens()) == 47.5


def test_a_team_with_no_memory_ranks_on_ability_and_results_alone():
    roster = [_P("a", 51), _P("b", 39), _P("c", 28)]
    ts = _team(roster, records={"b": [12, 8], "c": [10, 10]})
    # The `ladder_score` rule this replaced: nobody starts at the bottom for not
    # having played, and a winning record still moves you.
    assert [p.pid for p in jh._order(ts)] == ["a", "b", "c"]


# --- varsity proof: what the coach can point to -------------------------------

def test_proof_tiers_separate_turning_up_from_being_a_reason_they_won():
    assert jh.proof_tier(None) == 0
    assert jh.proof_tier(_proof(apps=4)) == 0                     # a call-up
    assert jh.proof_tier(_proof(apps=20, rank=11)) == 1           # a regular
    assert jh.proof_tier(_proof(flags=jh.PROOF_POSTSEASON)) == 2  # and it went well
    assert jh.proof_tier(_proof(flags=jh.PROOF_HONORED)) == 3     # the association said so
    # "Two strong years" without an award: trusted with the postseason, twice, winning.
    assert jh.proof_tier(_proof(flags=jh.PROOF_POSTSEASON, years=2,
                                wins=25, losses=5)) == 3


def test_being_in_the_postseason_lineup_is_not_by_itself_established():
    """‼️ THE TIERS ONLY MEAN SOMETHING IF THE MIDDLE ONE ASKS FOR A GOOD SEASON.
    Every program in this association enters the road to State and every road dual
    dresses the top nine, so `PROOF_POSTSEASON` is true of essentially every
    returning starter. Keyed on it alone, tier 2 swallowed the ladder: measured over
    two scaled seasons the mix came out 5,706 established to 435 contributors — two
    tiers rather than three, with the ORDINARY starter sitting on the middle value
    instead of the small one."""
    losing = _proof(flags=jh.PROOF_POSTSEASON, years=2, wins=10, losses=20)
    assert jh.proof_tier(losing) == 1
    winning = _proof(flags=jh.PROOF_POSTSEASON, wins=20, losses=10)
    assert jh.proof_tier(winning) == 2
    # …and volume still matters: a handful of postseason duals is not a season.
    assert jh.proof_tier(_proof(apps=5, wins=5, losses=0,
                                flags=jh.PROOF_POSTSEASON)) == 1


def test_an_award_alone_is_proof_even_on_a_short_season():
    """An injured All-State player is still an All-State player. `apps` below the
    regular bar must not veto a flag the association itself awarded."""
    assert jh.proof_tier(_proof(apps=3, flags=jh.PROOF_HONORED)) == 3


def test_proof_fades_as_the_season_produces_its_own_evidence_but_never_to_zero():
    """Proof gets a returning starter into the September lineup; by October his own
    results carry him. A floor rather than zero — a coach never fully forgets."""
    p, st, lens = _P("a", 50), _proof(flags=jh.PROOF_HONORED), jh.CoachLens()
    fresh = jh.varsity_proof(p, st, lens, played=0)
    mid = jh.varsity_proof(p, st, lens, played=12)
    late = jh.varsity_proof(p, st, lens, played=40)
    assert fresh > mid > late > 0.0
    assert late >= fresh * jh.PROOF_FLOOR


def test_a_freshman_never_spends_anybody_elses_proof():
    """A ninth-grader has no prior season in the program, so evidence found on his
    pid belongs to another identity. A wrong lookup must be worth nothing."""
    assert jh.varsity_proof(_P("a", 50, grade=9), _proof(flags=jh.PROOF_HONORED),
                            jh.CoachLens()) == 0.0


def test_seniority_scales_proof():
    st, lens = _proof(flags=jh.PROOF_HONORED), jh.CoachLens()
    by_grade = [jh.varsity_proof(_P("a", 50, grade=g), st, lens) for g in (12, 11, 10)]
    assert by_grade[0] > by_grade[1] > by_grade[2] > 0.0


# --- the systemic property the owner asked for --------------------------------

def test_proof_is_a_threshold_for_displacement_not_a_reserved_seat():
    """The whole point. A newcomer 2 OVR better waits; one 12 OVR better plays."""
    st = {"vet": _proof(flags=jh.PROOF_HONORED)}
    marginal = _team([_P("vet", 60), _P("kid", 62, grade=9)], prior=st)
    assert [p.pid for p in jh._order(marginal)] == ["vet", "kid"]
    plainly = _team([_P("vet", 60), _P("kid", 72, grade=9)], prior=st)
    assert [p.pid for p in jh._order(plainly)] == ["kid", "vet"]


def test_a_genuine_newcomer_pushes_everyone_down_exactly_one_seat():
    """"If a newcomer is genuinely elite the model should not protect everybody" —
    it is an ORDERING, so the freshman enters at his own rank and the veterans below
    him each move down one, rather than the lineup either freezing or resetting."""
    vets = [_P(f"v{i}", 70 - 2 * i) for i in range(5)]        # 70 68 66 64 62
    prior = {p.pid: _proof(flags=jh.PROOF_POSTSEASON) for p in vets}
    before = [p.pid for p in jh._order(_team(list(vets), prior=prior))]
    after = [p.pid for p in jh._order(
        _team(vets + [_P("kid", 67, grade=9)], prior=prior))]
    assert before == ["v0", "v1", "v2", "v3", "v4"]
    # He is better than v2 by 1 and worse than v1 by 1 — proof holds him off both,
    # so he slots behind the proven pair he is level with, and nobody is skipped.
    assert after.index("v0") == 0 and set(after) == set(before) | {"kid"}
    assert [x for x in after if x != "kid"] == before, "the veterans keep their order"


def test_nobody_is_advantaged_because_every_coach_evaluates():
    """The selection RULE changed association-wide; it is not one program's
    entitlement. Two identical rosters under two different coaches still rank their
    own proven players ahead of their own marginal newcomers."""
    for name in ("Vale", "Ride"):
        lens = jh.coach_lens(name)
        ts = _team([_P("vet", 60), _P("kid", 62, grade=9)],
                   prior={"vet": _proof(flags=jh.PROOF_HONORED)}, lens=lens)
        assert jh._order(ts)[0].pid == "vet"


# --- the ability lens ---------------------------------------------------------

def test_coach_quality_drives_every_weight_off_one_draw():
    """A coach who cannot read a roster leans on what he can read instead — so the
    weak end misjudges ability AND over-weights proof AND chases form, all from one
    quality variable rather than three unrelated knobs."""
    lenses = [jh.coach_lens(f"school-{i}") for i in range(400)]
    weak = max(lenses, key=lambda x: x.read)
    strong = min(lenses, key=lambda x: x.read)
    assert weak.trust > strong.trust and weak.form > strong.form
    assert jh.COACH_READ[0] <= strong.read < weak.read <= jh.COACH_READ[1]


def test_a_coachs_read_of_a_player_is_stable_within_a_season():
    """Redrawn per dual this would be a lineup that flickers week to week rather
    than a coach with an opinion."""
    lens = jh.CoachLens(read=2.5)
    a = jh.coach_read("pid", "Vale", 2075, lens)
    assert a == jh.coach_read("pid", "Vale", 2075, lens)
    assert a != jh.coach_read("pid", "Vale", 2076, lens), "he re-evaluates over a summer"


def test_the_misread_shrinks_as_the_coach_watches_the_player_play():
    """‼️ THE ANTI-RATCHET GUARD. A persistent negative misread would bury a player
    for a season exactly the way the win-COUNT ladder used to: ranked low, so never
    dressed, so nothing ever corrects the coach. From his first match his own
    results have to start outweighing the first impression."""
    p = _P("a", 50)
    early = jh.coach_eval(p, [0, 0], read=-6.0)
    late = jh.coach_eval(p, [10, 10], read=-6.0)
    assert late > early
    assert abs(late - 50.0) < abs(early - 50.0)


def test_a_strong_coach_reads_a_roster_close_to_true_ability():
    """`COACH_READ` bottoms at zero, so the best coaches select on what is there."""
    assert jh.coach_lens("x", "s").read >= 0.0
    assert jh.coach_read("pid", "Vale", 2075, jh.CoachLens(read=0.0)) == 0.0


# --- the separation from the engine -------------------------------------------

def test_evaluation_never_touches_the_player():
    """The layer's whole premise: the coach can be wrong about who should play
    without the underlying rating being wrong. Nothing here may mutate a Prospect —
    they are globally cached and shared across saves besides."""
    p = _P("a", 50)
    jh.coach_eval(p, [3, 9], prior=_proof(flags=jh.PROOF_HONORED),
                  lens=jh.coach_lens("Vale"), read=2.0)
    assert p.current_overall() == 50 and p.str_value() == 50


# --- the archive shape --------------------------------------------------------

def test_a_prior_season_round_trips_and_a_short_row_still_reads():
    """The row may grow; a season archived under an older shape has to keep reading
    (derived on read, never migrated)."""
    st = _proof(flags=jh.PROOF_HONORED, years=3)
    assert jh.PriorSeason.from_row(st.to_row()) == st
    old = jh.PriorSeason.from_row([12, 10, 2])
    assert (old.apps, old.wins, old.losses, old.years) == (12, 10, 2, 1)


def test_an_individual_draw_match_is_not_a_varsity_appearance():
    """‼️ The individual state tournaments credit `records` and `matches` exactly
    like a court does (owner rule 2026-08), so a raw `records` count answers a
    DIFFERENT question from the one `PROOF_MIN_APPS` asks — a player can reach 6-1
    having never dressed for his team."""
    roster = [_P("a", 50)]
    ts = _team(roster)
    ts.matches["a"] = ([("S1", True, "individual", (), "", "")] * 8
                       + [("S1", True, "regular", (), "", "")] * 3)
    rows = jh.team_standing(ts, {}, None)
    # Three duals is under the regular bar, so the draw entry is the only proof —
    # and it registers as its own flag rather than as eleven appearances.
    st = rows["a"]
    assert st.apps == 3
    assert st.has(jh.PROOF_INDIVIDUAL) and not st.has(jh.PROOF_POSTSEASON)


def test_only_players_who_carry_proof_are_stored():
    """A row worth nothing is a row nobody needs to write, read or key a cache on."""
    ts = _team([_P("a", 50), _P("b", 40)])
    ts.matches["a"] = [("S1", True, "regular", (), "", "")] * 20
    ts.matches["b"] = [("S3", False, "regular", (), "", "")] * 2
    assert set(jh.team_standing(ts, {}, None)) == {"a"}


def test_consecutive_years_of_proof_are_carried_forward():
    """What makes "two strong years" a tier without storing two seasons."""
    ts = _team([_P("a", 50)])
    ts.matches["a"] = [("S1", True, "regular", (), "", "")] * 20
    first = jh.team_standing(ts, {}, None)["a"]
    second = jh.team_standing(ts, {}, {"a": first})["a"]
    assert (first.years, second.years) == (1, 2)


# --- captains (owner rule 2026-09) --------------------------------------------

def _capteam(roster, prior=None, records=None):
    ts = _team(roster, records=records, prior=prior)
    ts.captains = jh.pick_captains(ts, "cap", 2075)
    return ts


def test_a_program_names_one_to_three_captains_never_more():
    """Owner rule: "you can't have more than 3 captains"."""
    roster = [_P(f"p{i}", 70 - i, grade=12 - i % 4) for i in range(16)]
    counts = set()
    for yr in range(2060, 2100):
        ts = _team(roster)
        counts.add(len(jh.pick_captains(ts, "cap", yr)))
    assert counts and max(counts) <= jh.CAPTAINS_MAX == 3
    assert min(counts) >= 1


def test_the_best_player_is_almost_always_a_captain():
    """"It's hard to run a team without doing it that way."

    ‼️ THE COIN IS ONLY DECISIVE FOR AN UNDERCLASSMAN. A senior No. 1 who loses the
    `CAPTAIN_BEST_CHANCE` roll is still the best remaining SENIOR, so the second seat
    names him anyway — he is captain essentially always. A ninth-grade No. 1 is not
    reachable that way and is captain at the coin's rate. That falls out of the two
    rules rather than being designed, and it is the right behaviour: the exception
    the owner left room for is a young star who does not lead the room, not a senior
    No. 1 who somehow isn't a captain."""
    senior = [_P(f"p{i}", 70 - i, grade=12) for i in range(16)]
    always = sum(1 for yr in range(2000, 2200)
                 if "p0" in jh.pick_captains(_team(senior), "cap", yr))
    assert always == 200

    # ‼️ The young star must not ALSO be the best doubles player, or seat 2 would
    # pick him up whatever the coin did and there would be nothing to measure.
    young = ([_P("kid", 90, grade=9, net=0.1)]
             + [_P(f"p{i}", 70 - i, grade=12, net=0.5) for i in range(15)])
    hit = sum(1 for yr in range(2000, 2400)
              if "kid" in jh.pick_captains(_team(young), "cap", yr))
    assert 0.80 < hit / 400 < 0.96


def test_every_captain_dresses_for_the_program():
    """"They're always on varsity — it doesn't work otherwise." The pool is the
    dressing group, so a coach never starts out having named someone who cannot
    play."""
    roster = [_P(f"p{i}", 70 - i, grade=12 if i < 6 else 10) for i in range(20)]
    need = jh.lineup_need("regular")
    for yr in range(2060, 2090):
        ts = _team(roster)
        caps = jh.pick_captains(ts, "cap", yr)
        top = {p.pid for p in jh._order(ts)[:need]}
        assert set(caps) <= top


def test_the_second_seat_is_the_best_doubles_player_not_the_next_best_player():
    """Owner rule 2026-09: "seat 1 will almost always be No. 1 singles", so the
    second seat is the other half of the team. `dbl` here is a weak singles player
    with the best hands at the net — the ladder would never reach him."""
    # `dbl` is mid-ladder — comfortably inside the dressing group, nowhere near
    # second on it — but has the best hands at the net on the team.
    roster = [_P(f"p{i}", 70 - i, grade=12, net=0.5) for i in range(11)]
    roster.append(_P("dbl", 64, grade=11, net=9.0))
    caps = jh.pick_captains(_team(roster), "cap", 2075)
    assert caps[0] == "p0", "the best player still takes seat 1"
    assert caps[1] == "dbl", "seat 2 is the best doubles player, not p1"


def test_the_second_seat_has_no_grade_gate():
    """It used to prefer seniors; the owner removed that — "I don't want to restrict
    juniors from becoming captains, since teams benefit from having captains who have
    been around a bit." Tenure is seat 3's job."""
    roster = [_P(f"s{i}", 70 - i, grade=12, net=0.5) for i in range(11)]
    roster.append(_P("jun", 64, grade=11, net=9.0))
    assert "jun" in jh.pick_captains(_team(roster), "cap", 2075)[:2]


def test_the_glue_seat_is_not_ability_ranked():
    """The third captain is "someone who is a culture/glue … the hardest working
    person irrespective of talent — could be the last player on varsity"."""
    roster = [_P(f"p{i}", 70 - i, grade=12) for i in range(11)]
    # p9 has been on varsity three years; everyone else one.
    prior = {"p9": _proof(years=3, flags=jh.PROOF_POSTSEASON)}
    seats = [jh.pick_captains(_team(roster, prior=prior), "cap", yr)
             for yr in range(2000, 2200)]
    thirds = [c[2] for c in seats if len(c) >= 3]
    assert thirds, "some years name three"
    assert all(t == "p9" for t in thirds), "the longest-serving player, not the 3rd best"


def test_captains_dress_even_after_the_ladder_moves_under_them():
    """‼️ THE FORCE IS REAL AND IT CAN COST THE TEAM — which is the whole point:
    "it creates an incentive by the coach NOT to pick kids who won't play." A glue
    captain who slides down the ladder is still in the lineup."""
    roster = [_P(f"p{i}", 70 - i, grade=12) for i in range(16)]
    ts = _team(roster)
    ts.captains = ["p0", "p13"]
    ts.records["p13"] = [0, 40]                    # a disastrous season on top of it
    order = jh._order(ts)
    need = jh.lineup_need("regular")
    assert "p13" not in [p.pid for p in order[:need]], \
        "he really has fallen out of the dressing group"
    # `_seat_captains` is the whole mechanism, and it is what every `_lineup` branch
    # ends on. Called here directly rather than through `_lineup`, which arranges the
    # result and so needs real `Prospect`s rather than this file's stub.
    seated = jh._seat_captains(ts, order[:need], order)
    assert {p.pid for p in seated} >= {"p0", "p13"}
    assert len(seated) == need, "somebody gave up the seat; the group did not grow"


def test_an_injured_captain_is_not_forced_onto_court():
    """The one thing the owner allows to bench anybody. It holds by construction —
    `_healthy` drops him before `_seat_captains` ever sees the order, which is why
    there is no injury check inside the seating itself."""
    roster = [_P(f"p{i}", 70 - i, grade=12) for i in range(16)]
    ts = _team(roster)
    ts.captains = ["p9"]
    ts.injuries["p9"] = 3
    order = jh._healthy(ts, jh._order(ts))
    need = jh.lineup_need("regular")
    assert not any(p.pid == "p9" for p in jh._seat_captains(ts, order[:need], order))


def test_a_captain_keeps_the_c_until_he_graduates():
    """Owner rule 2026-09: named as a tenth- or eleventh-grader, captain until he
    leaves. He is re-seated FIRST and unconditionally — including from outside the
    dressing group, since a captain dresses anyway."""
    roster = [_P(f"p{i}", 70 - i, grade=12) for i in range(16)]
    was = _proof(flags=jh.PROOF_CAPTAIN, school="Vale")
    ts = _team(roster, prior={"p13": was})
    for yr in range(2000, 2040):
        assert "p13" in jh.pick_captains(ts, "cap", yr), "he does not re-earn it"


def test_returning_captains_never_get_stripped_by_a_lean_year():
    """`want` is a FLOOR of the returning count. Drawn first and applied to them, a
    one-captain year would have had to take the C off somebody still enrolled."""
    roster = [_P(f"p{i}", 70 - i, grade=12) for i in range(16)]
    prior = {p: _proof(flags=jh.PROOF_CAPTAIN, school="Vale")
             for p in ("p2", "p5", "p9")}
    for yr in range(2000, 2040):
        caps = jh.pick_captains(_team(roster, prior=prior), "cap", yr)
        assert set(caps) == {"p2", "p5", "p9"}, "three return, so nobody new is named"


def test_a_captain_who_transfers_has_to_earn_it_again():
    """"If a captain transfers, they'd need to be re-selected by their new program."
    The evidence map is keyed on pid so it follows a mover by design — right for his
    RECORD, wrong for a captaincy, which is a thing one particular room gave him."""
    was = _proof(flags=jh.PROOF_CAPTAIN, school="Vale")
    assert jh._uncaptain(was, "Vale").has(jh.PROOF_CAPTAIN)
    moved = jh._uncaptain(was, "Ride")
    assert not moved.has(jh.PROOF_CAPTAIN)
    assert moved.apps == was.apps and moved.years == was.years, \
        "everything else about the season he played comes with him"
    # A row archived before the school was stamped is left alone: silently
    # un-captaining every returning captain in an older save is the worse answer.
    legacy = jh.PriorSeason(flags=jh.PROOF_CAPTAIN)
    assert jh._uncaptain(legacy, "Ride").has(jh.PROOF_CAPTAIN)


# --- presence, and what it absorbs --------------------------------------------

def test_an_ordinary_captain_earns_presence_without_any_award():
    """The question the three seats never answered. Tenure and a winning record are
    worth real weight, so the three-year glue captain the team actually trusts is
    not worth nothing next to a decorated one."""
    poy = _proof(flags=jh.PROOF_HONORED | jh.PROOF_POY, years=3)
    district = _proof(flags=jh.PROOF_HONORED | jh.PROOF_ALL_DISTRICT, years=1)
    glue = _proof(apps=20, wins=8, losses=12, flags=0, years=3)
    rookie = _proof(apps=14, wins=7, losses=7, flags=0, years=1)
    p = [jh.captain_presence(st) for st in (poy, district, glue, rookie)]
    assert p[0] > p[1] > p[2] > p[3] > 0.0, "everyone carries something; the order holds"
    assert p[2] > 0.5 * p[1], "a three-year glue captain is not a rounding error"


def test_awards_are_ranked_and_never_summed():
    """"Decorated" is not one thing — a Player of the Year and an All-District pick
    do not command the same room. And a player holding two takes the better, not
    both."""
    poy = jh.captain_presence(_proof(flags=jh.PROOF_HONORED | jh.PROOF_POY))
    state = jh.captain_presence(_proof(flags=jh.PROOF_HONORED | jh.PROOF_ALL_STATE))
    dist = jh.captain_presence(_proof(flags=jh.PROOF_HONORED | jh.PROOF_ALL_DISTRICT))
    assert poy > state > dist
    both = jh.captain_presence(_proof(
        flags=jh.PROOF_HONORED | jh.PROOF_POY | jh.PROOF_ALL_DISTRICT))
    assert both == poy


def test_three_decorated_captains_can_roll_a_whole_slump_off():
    """Owner rule: the cap is 1-100% — "if you have 3 decorated captains they could
    roll all of a slump off"."""
    roster = [_P(f"p{i}", 70 - i, grade=12) for i in range(11)]
    decorated = _proof(flags=jh.PROOF_HONORED | jh.PROOF_POY, years=3)
    ts = _team(roster, prior={p: decorated for p in ("p0", "p1", "p2")})
    ts.captains = ["p0", "p1", "p2"]
    assert jh.team_absorption(ts) == pytest.approx(1.0)
    lean = _team(roster, prior={"p0": _proof(flags=0, years=1)})
    lean.captains = ["p0"]
    assert 0.0 < jh.team_absorption(lean) < 0.35


def test_absorption_softens_a_slump_and_never_inflates_a_hot_streak():
    """‼️ THE ASYMMETRY IS THE WHOLE THING. Leadership is a return to the mean, not
    a lift above it — which is what keeps this from being a team-wide ability bonus
    in disguise. And it never reaches the match engine: it changes where the coach
    RANKS a slumping player, so a well-led team stops benching people over a bad
    fortnight. Nobody plays any better."""
    p = _P("a", 50)
    slump, hot = [4, 20], [20, 4]
    assert jh.coach_eval(p, slump) < 50.0 < jh.coach_eval(p, hot)
    assert jh.coach_eval(p, slump, absorb=1.0) == pytest.approx(50.0)
    assert jh.coach_eval(p, hot, absorb=1.0) == jh.coach_eval(p, hot)
    half = jh.coach_eval(p, slump, absorb=0.5)
    assert jh.coach_eval(p, slump) < half < 50.0


def test_a_captain_with_no_proof_is_still_stored():
    """`PROOF_CAPTAIN` is what carries the C across the boundary, so dropping a
    tier-0 captain from the standing would quietly strip the captaincy off exactly
    the glue player the third seat exists for."""
    roster = [_P("a", 50)]
    ts = _team(roster)
    ts.captains = ["a"]
    ts.matches["a"] = [("S1", False, "regular", (), "", "")] * 2   # tier 0
    rows = jh.team_standing(ts, {}, None)
    assert "a" in rows and rows["a"].has(jh.PROOF_CAPTAIN)
    assert jh.proof_tier(rows["a"]) == 0, "kept for the C, not for his record"


def test_captaincy_sharpens_the_coachs_read_and_nothing_else():
    """It is worth `CAPTAIN_VALUE` off the misread and NOTHING to a player: no
    attribute moves, and the figure is flat however many captains are named."""
    assert jh.captain_mitigation(["a"]) == jh.captain_mitigation(["a", "b", "c"])
    assert jh.captain_mitigation([]) == 0.0
    p = _P("a", 50)
    before = p.current_overall()
    jh.coach_eval(p, [3, 9], lens=jh.coach_lens("Vale"), read=2.0)
    assert p.current_overall() == before


def test_the_store_round_trips_and_flattens_to_pids(tmp_path, monkeypatch):
    """Rows are STORED per program (a program's memory is its own row) and READ
    flattened to `{pid: PriorSeason}`, so an owner-authored transfer carries the
    record the player earned — the answer a coach would give about a junior who
    started two years somewhere else."""
    import json
    from app import world as wd
    monkeypatch.setattr(wd, "WORLD_DB", str(tmp_path / "w.db"))
    monkeypatch.setattr(wd, "_schema_ready_for", None)
    conn = wd._db()
    conn.executemany(
        "INSERT INTO world_jhsaa_standing (world_id, year, gender, school, data)"
        " VALUES (?,?,?,?,?)",
        [(1, 4, "boys", "Vale", json.dumps({"p1": _proof().to_row()})),
         (1, 4, "boys", "Ride", json.dumps({"p2": _proof(apps=25).to_row()})),
         (1, 4, "girls", "Vale", json.dumps({"p3": _proof().to_row()})),
         (1, 3, "boys", "Vale", json.dumps({"p4": _proof().to_row()}))])
    conn.commit()
    conn.close()
    got = wd.jhsaa_prior_standing(1, 4, "boys")
    assert set(got) == {"p1", "p2"}, "one flat map across every program, gender-scoped"
    assert got["p2"].apps == 25
    assert wd.jhsaa_prior_standing(1, 9, "boys") == {}, "a year with nothing archived"


def test_the_season_year_converter_lands_on_the_archive_key(tmp_path, monkeypatch):
    """‼️ The rung that PLAYS a season and the recruit hand-off that replays it must
    resolve to the SAME key, or the college board is built from a differently-played
    season. Both go through `jhsaa_prior_for_season`, so this pins its arithmetic
    against the `jhsaa_season_year` it inverts."""
    import json
    from app import world as wd
    monkeypatch.setattr(wd, "WORLD_DB", str(tmp_path / "w.db"))
    monkeypatch.setattr(wd, "_schema_ready_for", None)
    world_year = 5
    season_year = wd.jhsaa_season_year({"year": world_year})
    conn = wd._db()
    conn.execute("INSERT INTO world_jhsaa_standing"
                 " (world_id, year, gender, school, data) VALUES (?,?,?,?,?)",
                 (7, world_year - 1, "boys", "Vale",
                  json.dumps({"p": _proof().to_row()})))
    conn.commit()
    conn.close()
    assert set(wd.jhsaa_prior_for_season(season_year, "boys", 7)) == {"p"}


def test_the_memo_fingerprint_is_stable_and_distinguishes_maps():
    """`run_season` is memoised, and last season's evidence moves every ladder in
    the association — keyed without it, a save would serve its first year's
    no-memory season to every year after. `blake2s`, never `hash()`: a season cache
    that changes identity on restart can be served two ways in one save."""
    a = {"p": _proof()}
    assert jh._prior_fingerprint(a) == jh._prior_fingerprint({"p": _proof()})
    assert jh._prior_fingerprint(a) != jh._prior_fingerprint({"p": _proof(apps=31)})
    assert jh._prior_fingerprint(None) == jh._prior_fingerprint({}) == ""

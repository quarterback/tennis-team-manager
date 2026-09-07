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


class _P:
    """The four things the evaluation layer reads off a player, and a pid."""

    def __init__(self, pid, ovr, grade=12, strv=None):
        self.pid, self._ovr, self.grade = pid, ovr, grade
        self._str = strv if strv is not None else ovr

    def current_overall(self):
        return self._ovr

    def str_value(self):
        return self._str


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

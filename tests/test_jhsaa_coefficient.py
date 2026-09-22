"""The JHSAA Program Coefficient (owner spec 2026-09) — pinned as arithmetic on
hand-built archives, so it needs no played season and cannot rot behind a small
fixture. `season_points` is a pure fold over one archive dict; `fold` over a list
of them."""
from app import jhsaa as jh
from app import jhsaa_coefficient as coef


def _game(home, away, winner):
    return {"home": home, "away": away, "winner": winner, "score": "3-0"}


def _stage(name, games):
    return {"round_names": [name], "rounds": [games]}


def _bracket(field, rounds, champion):
    """A state draw the way `run_state` archives one: `field`, `rounds` (lists of
    games), `champion`, and `round_names` so the Parastate can be named."""
    return {"field": field, "rounds": rounds, "champion": champion,
            "round_names": ["Round of 4", "Final"]}


def _season(year):
    """One 9A season: A wins Sectionals, Regionals, Zonals, the Epiregional and
    the State title; B loses the final; C loses a Sectional, wins a Super
    Regional, loses at State in the semis; D is a Parastate exit."""
    return {
        "standings": {"9A": {"League": [{"school": s} for s in "ABCD"]},
                      "3A": {"Other": [{"school": "E"}]}},
        "sectionals": {"9A": _stage("Sectionals", [_game("A", "C", "A")])},
        "prestate": {"9A": {"round_names": [jh._STAGE_NAMES["regional"], jh._STAGE_NAMES["zonal"]],
                            "rounds": [[_game("A", "B", "A")], [_game("A", "D", "A")]]}},
        "epiregional": {"9A": _stage(jh.EPIREGIONAL_NAME, [_game("A", "B", "A")])},
        "super_regional": {"9A": _stage(jh._RECOVERY_NAMES["super_regional"],
                                        [_game("C", "D", "C"),
                                         # a materialised bye is not a win
                                         {"home": "B", "away": None, "winner": "B"}])},
        "brackets": {"9A": {"field": ["A", "B", "C", "D"],
                            "round_names": [jh.PARASTATE_NAME, "Semifinal", "Final"],
                            "rounds": [[_game("D", "C", "C")],
                                       [_game("A", "C", "A")],
                                       [_game("A", "B", "A")]],
                            "champion": "A"},
                     "3A": {"field": ["E"], "round_names": [], "rounds": [], "champion": "E"}},
        "toc": {"field": ["A", "E"], "rounds": [[_game("A", "E", "A")]], "champion": "A"},
    }


def test_the_season_schedule_prices_every_road_win_and_one_state_finish():
    pts = coef.season_points(_season(10))
    # A: Sectional .125 + Regional .5 + Zonal 1 + Epiregional .5 = 2.125 road;
    # champion 52; TOC 4
    assert pts["A"]["road"] == 2.125 and pts["A"]["state"] == 52 and pts["A"]["toc"] == 4
    assert pts["A"]["points"] == 58.125 and pts["A"]["group"] == "9A"
    # B: no road wins (its Super Regional "game" was a bye); runner-up 42
    assert pts["B"]["road"] == 0 and pts["B"]["state"] == 42
    # C: Super Regional .25; out in the semis with 4 alive → 22
    assert pts["C"]["road"] == 0.25 and pts["C"]["state"] == coef.STATE_SEMI
    # D: a Parastate exit is priced with the qualifying rounds, not the draw
    assert pts["D"]["state"] == coef.STATE_PARASTATE == 3
    # E: a 3A champion with a one-team draw — champion 52, TOC entrant 4
    assert pts["E"]["points"] == 56 and pts["E"]["group"] == "3A"


def test_the_road_can_no_longer_imitate_depth_at_state():
    """‼️ THE CORRECTION (owner rule 2026-09). Every road rung used to cost 1, 2 or
    3, so ELEVEN of them aggregated into a number that rivalled a real State run —
    measured on the owner's 2090 girls export, 4.5% of ordered pairs had the
    program with the SHALLOWER State run outscoring the deeper one, and the deepest
    road haul banked before State was 11 points against a first-round exit's 4.
    Under this schedule that is 0.04% and 4 points.

    Pinned as arithmetic on the tables, because the property is a property of the
    PRICES: no reachable road total may approach the gap between two State rounds."""
    road = coef.road_points()
    # ‼️ THE BOUND IS A LEGAL PATH, NOT THE SUM OF EVERY RUNG. The ladder is a
    # route: Super Regionals is for Regional LOSERS, the Conference for Semi-State
    # losers, so no program can bank both halves and `sum(road.values())` (11.6)
    # is a number nobody can reach. The longest chain of wins one program can
    # actually assemble is the local rungs, then a Regionals loss into the full
    # recovery run, then the Metastate on a low seed.
    longest = (road["Areas"] + road["Sectionals"] + road["Wards"]
               + road["Super Regionals"]        # lost Regionals, won the recovery
               + road["Semi-Conference"] + road["Conference"]
               + road["State Specials"]         # the Conference's berth round
               + road["Metastate"])             # seeded low into the draw
    assert longest < coef.STATE_OCTO, (longest, coef.STATE_OCTO)
    # ‼️ AND THE SECOND PASS HALVED IT: 4.10 → 2.05. Re-grading the rungs fixed the
    # ORDER and left the SCALE, so a program's ROUTE still weighed as much as two
    # rounds of the draw. Every price is exactly half its first-pass value, which is
    # what keeps every relative judgement below intact while the road goes quiet.
    assert 2.0 <= longest <= 2.1, longest
    # And the local rungs together are worth less than one first-round State dual.
    assert road["Areas"] + road["Sectionals"] + road["Wards"] < coef.STATE_ENTRY
    # The recovery rungs are priced BELOW the rounds they are a second chance at.
    assert road["Super Regionals"] < road["Regionals"]
    assert road["Semi-State"] < road["Zonals"]
    # The whole ladder reads as one progression, qualifying rounds to title.
    ladder = [coef.STATE_PARASTATE, coef.STATE_ENTRY, coef.STATE_OCTO,
              coef.STATE_QUARTER, coef.STATE_SEMI, coef.STATE_FINAL,
              coef.STATE_CHAMPION]
    assert ladder == sorted(ladder) and len(set(ladder)) == len(ladder), ladder
    assert road["Metastate"] <= coef.STATE_PARASTATE
    # ‼️ AND THE TOP DISCRIMINATES. It was 20 · 22 · 30, so reaching the FINAL beat
    # losing the semifinal by 2 while the semifinal beat the quarters by 8 — the
    # schedule stopped separating teams exactly where the season is decided. The
    # gaps do NOT widen monotonically all the way (entry→octo is 6, octo→quarter 4)
    # and must not be asserted to; what the correction guarantees is this.
    assert (coef.STATE_FINAL - coef.STATE_SEMI) > (coef.STATE_SEMI - coef.STATE_QUARTER)
    assert coef.STATE_CHAMPION > coef.STATE_FINAL > coef.STATE_SEMI
    # ‼️ AND THE BOTTOM STOPPED JUMPING. It was 1 · 2 · 8: one point between an
    # at-large's only dual and entering the draw, then SIX for winning once. The
    # lower steps now rise like the upper ones instead of stalling and lurching.
    steps = [b - a for a, b in zip(ladder, ladder[1:])]
    assert steps[:4] == sorted(steps[:4]), steps


def test_making_state_outscores_every_road_without_it():
    """‼️ THE BOUNDARY THE SCHEDULE EXISTS TO STATE (owner rule 2026-09): making
    State is worth more than any road a program can walk WITHOUT making it.

    The road is cumulative, so before this pass the two scales overlapped — a long
    qualification route out-scored an at-large's State berth, and the bottom of the
    table read as a measure of how a program ARRIVED rather than what it did. The
    floor is arithmetic now, not a judgement: the longest legal road chain is 2.05
    and the State floor is 3, so every program in the State field outscores every
    program that missed it, whatever route either walked.

    That is what the 3 MEANS — a qualification floor, not a reward for anything done
    inside the tournament. Everything above it measures what a program did after
    arriving, which is why a Parastate exit still sits far below one bracket win."""
    road = coef.road_points()
    longest = (road["Areas"] + road["Sectionals"] + road["Wards"]
               + road["Super Regionals"] + road["Semi-Conference"]
               + road["Conference"] + road["State Specials"] + road["Metastate"])
    assert longest < coef.STATE_PARASTATE, (longest, coef.STATE_PARASTATE)
    # ‼️ The bound is GENEROUS on purpose: that chain ENDS in qualification (the
    # Conference's berth round is in it), so no program that missed State can even
    # reach it. The inequality has to hold against the unreachable case, since a
    # schedule that only worked for the reachable one would be one rung-price away
    # from breaking silently.
    assert max(road.values()) < coef.STATE_PARASTATE
    # And arriving is still worth far less than doing anything once there.
    assert coef.STATE_PARASTATE < coef.STATE_ENTRY < coef.STATE_OCTO
    # The TOC bonus is champions-only, so it can never lift a weaker State finisher
    # past a stronger one — the gap it has to clear is the smallest State step.
    assert coef.TOC_BONUS <= min(b - a for a, b in
                                 zip((coef.STATE_SEMI, coef.STATE_FINAL),
                                     (coef.STATE_FINAL, coef.STATE_CHAMPION)))


def test_every_road_round_the_association_plays_is_priced():
    """A rung with no price scores NOTHING and reads like a program that never
    played it — which is exactly what the Metastate did until this schedule. Swept
    against `jhsaa`'s own stage tables so a new round fails here rather than
    silently costing its programs."""
    from app import jhsaa as jh
    road = coef.road_points()
    for name in (["Areas", "Sectionals", jh.EPIREGIONAL_NAME, jh.METASTATE_NAME]
                 + list(jh._STAGE_NAMES.values())
                 + list(jh._RECOVERY_NAMES.values())):
        assert road.get(name), name
    # And the archive key the round is stored under is walked for road wins.
    assert jh.METASTATE_PHASE in coef._ROAD_KEYS


def test_the_window_weights_recency_and_drops_the_tenth_season():
    seasons = [(y, {"A": {"points": 10.0, "group": "9A"}}) for y in range(20, 9, -1)]
    groups = coef.fold(seasons, {"A": "9A"}, {"A": 11})
    row = groups["9A"][0]
    assert abs(row["coefficient"] - 10 * (3 * 1.0 + 3 * 0.6 + 3 * 0.3)) < 1e-9
    assert len(row["breakdown"]) == coef.WINDOW and not row["bootstrap"]


def test_a_program_ranks_in_its_current_class_with_its_whole_history():
    seasons = [(y, {"A": {"points": 10.0, "group": "5A"},
                    "B": {"points": 1.0, "group": "6A"}}) for y in range(5, 0, -1)]
    groups = coef.fold(seasons, {"A": "6A", "B": "6A"})     # A moved up this year
    assert [r["school"] for r in groups["6A"]] == ["A", "B"]
    assert "5A" not in groups and abs(groups["6A"][0]["coefficient"] - 10 * (3 + 1.2)) < 1e-9


def test_a_new_program_is_seeded_at_the_class_q1_not_zero():
    est = {f"P{i}": {"points": float(i), "group": "9A"} for i in range(1, 9)}
    seasons = [(3, {**est, "NEW": {"points": 50.0, "group": "9A"}}),
               (2, est), (1, est)]
    hist = {**{k: 3 for k in est}, "NEW": 1}
    rows = coef.fold(seasons, {}, hist)["9A"]
    new = next(r for r in rows if r["school"] == "NEW")
    q1 = coef._q1([r["coefficient"] for r in rows if not r["bootstrap"]])
    assert new["bootstrap"] and new["coefficient"] == q1 and 0 < q1
    # its own 50 points did not rank it first
    assert new["rank"] > 1
    # a program with 3+ seasons that just moved classes is NOT bootstrapped
    rows2 = coef.fold(seasons, {"P8": "3A"}, hist)
    assert rows2["3A"][0]["school"] == "P8" and not rows2["3A"][0]["bootstrap"]


def test_the_explorer_suggestion_deals_the_ladder_by_roll_weight(monkeypatch):
    """Percentiles within a class, laid onto the non-volatile tiers by roll weight —
    the suggested distribution matches the tier table, never a volatile tier."""
    names = [f"S{i}" for i in range(200)]
    pcts = {n: i / 199 for i, n in enumerate(names)}
    monkeypatch.setattr(coef, "percentiles", lambda wid, g: pcts if g == "boys" else {})
    monkeypatch.setattr("app.world.load_world", lambda seed: {"id": 1})
    got = jh.suggested_bands()
    assert set(got) == set(names)
    ladder = [t for t in jh.band_tiers() if not t.get("wide")]
    assert set(got.values()) <= {t["key"] for t in ladder}
    total = sum(t["weight"] for t in ladder)
    counts = {k: sum(1 for v in got.values() if v == k) for k in got.values()}
    for t in ladder:
        assert abs(counts.get(t["key"], 0) - 200 * t["weight"] / total) <= 1.5
    assert got["S0"] == ladder[0]["key"] and got["S199"] == ladder[-1]["key"]


def test_history_is_keyed_on_the_roster_identity_not_the_display_string():
    """The reissued-name trap: X was archived as "Treasure Valley", renamed to
    "Treasure Peak" (source keeps the old string), and a DIFFERENT program Y is
    live today AS "Treasure Valley". `_relabel` cannot alias that string. Per
    season: X present under its new name → the string is Y's; X absent under its
    new name → the string is X's own pre-rename season."""
    # Y carries its OWN source — the data's shape (every live holder of a reissued
    # name does), which is what keeps the two roster identities distinct.
    rows = [{"name": "Treasure Peak", "source": "Treasure Valley"},
            {"name": "Treasure Valley", "source": "Orellana Treasure Valley"},
            {"name": "Plain", "source": "Old Plain"}]
    # A pre-rename season: only "Treasure Valley" (X) played.
    m = coef.identity_map({"Treasure Valley", "Old Plain"}, rows)
    assert m["Treasure Valley"] == "Treasure Valley" and m["Old Plain"] == "Old Plain"
    # A post-rename season: X plays as Treasure Peak, so "Treasure Valley" is Y.
    m = coef.identity_map({"Treasure Peak", "Treasure Valley"}, rows)
    assert m["Treasure Peak"] == "Treasure Valley"      # X's ident is its source
    assert m["Treasure Valley"] == "Orellana Treasure Valley"   # the string is Y's
    # Through season_points: the same arc credits X or Y by who else is in it.
    arc = _season(1)
    arc["standings"]["9A"]["League"].append({"school": "Treasure Valley"})
    pts = coef.season_points(arc, rows + [{"name": n} for n in "ABCDE"])
    assert "Treasure Valley" in pts                     # X, pre-rename
    arc["standings"]["9A"]["League"].append({"school": "Treasure Peak"})
    pts = coef.season_points(arc, rows + [{"name": n} for n in "ABCDE"])
    assert {"Treasure Valley", "Orellana Treasure Valley"} <= set(pts)
    assert pts["Treasure Valley"]["name"] == "Treasure Peak"


def test_suggestions_read_only_current_sponsors(monkeypatch):
    """A program that dropped the gender keeps its archive but gets no standing,
    and takes no seat in the roll-weight deal."""
    class S:
        def __init__(self, ident): self.ident = ident
    monkeypatch.setattr(jh, "load_schools", lambda g: [S("A"), S("C")])
    rows = [{"school": "A", "rank": 1, "bootstrap": False},
            {"school": "B", "rank": 2, "bootstrap": False},     # former program
            {"school": "C", "rank": 3, "bootstrap": False}]
    monkeypatch.setattr(coef, "coefficient",
                        lambda wid, g, as_of=None: {"groups": {"9A": rows}})
    got = coef.percentiles(1, "boys")
    assert got == {"A": 1.0, "C": 0.0}


def test_a_reset_during_a_load_stops_the_old_save_publishing(monkeypatch):
    """The threaded-worker race: a request that began loading the OLD archive
    finishes after `world.reset()` and would repopulate the memo under a key the
    NEW save reuses (SQLite hands out the same world id and years). The
    generation stamp taken at the start of the load must refuse the publish."""
    import app.world as world
    coef.reset()
    calls = {"n": 0}

    def slow_archive(world_id, year, gender):
        calls["n"] += 1
        if calls["n"] == 1:
            coef.reset()            # the new save arrives mid-load
        return _season(year)
    monkeypatch.setattr(world, "get_jhsaa", slow_archive)
    monkeypatch.setattr(jh, "_rows", lambda: [{"name": n} for n in "ABCDE"])
    # Off the fixture, never a typed total: the prices move and this test is about
    # the reset, not the schedule.
    want = coef.season_points(_season(1))["A"]["points"]
    first = coef._season(1, 5, "girls")
    assert first["A"]["points"] == want                  # the caller still gets its answer
    assert not coef._season_cache, "a stale load must not be published after a reset"
    second = coef._season(1, 5, "girls")                # the new save computes afresh
    assert calls["n"] == 2 and second["A"]["points"] == want
    assert len(coef._season_cache) == 1                  # and this one IS published
    coef.reset()

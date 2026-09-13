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
    # A: Sectional 1 + Regional 2 + Zonal 2 + Epiregional 1 = 6 road; champion 30; TOC 4
    assert pts["A"]["road"] == 6 and pts["A"]["state"] == 30 and pts["A"]["toc"] == 4
    assert pts["A"]["points"] == 40 and pts["A"]["group"] == "9A"
    # B: no road wins (its Super Regional "game" was a bye); runner-up 22
    assert pts["B"]["road"] == 0 and pts["B"]["state"] == 22
    # C: Super Regional 2; out in the semis with 4 alive → 20
    assert pts["C"]["road"] == 2 and pts["C"]["state"] == coef.STATE_SEMI
    # D: a Parastate exit scores nothing at State
    assert pts["D"]["state"] == 0
    # E: a 3A champion with a one-team draw — champion 30, TOC entrant 4
    assert pts["E"]["points"] == 34 and pts["E"]["group"] == "3A"


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
    first = coef._season(1, 5, "girls")
    assert first["A"]["points"] == 40                    # the caller still gets its answer
    assert not coef._season_cache, "a stale load must not be published after a reset"
    second = coef._season(1, 5, "girls")                # the new save computes afresh
    assert calls["n"] == 2 and second["A"]["points"] == 40
    assert len(coef._season_cache) == 1                  # and this one IS published
    coef.reset()

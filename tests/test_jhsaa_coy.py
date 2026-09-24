"""Coach of the Year (owner spec 2026-09) — the scoring pieces as arithmetic, and
one hand-archived season selected end to end."""

from __future__ import annotations

import json

from app import jhsaa as jh
from app import jhsaa_coy as coy
from app import world as wd


def test_z_uses_the_binomial_denominator_and_is_capped():
    # Two wins over expectation against coin flips…
    flips = [(1.0, 0.5)] * 4 + [(0.0, 0.5)] * 0
    # …is less remarkable than two where the model was sure of a loss.
    longshots = [(1.0, 0.1), (1.0, 0.1)] + [(0.0, 0.1)] * 2
    assert coy.z_score(longshots) > 0
    assert coy.z_score([(1.0, 0.5)] * 2 + [(0.0, 0.5)] * 2) == 0
    assert coy.z_score([(1.0, 0.01)] * 30) == coy.Z_CAP
    assert coy.z_to_score(coy.Z_CAP) == 100 and coy.z_to_score(-coy.Z_CAP) == 0
    assert coy.z_to_score(None) == 50
    assert flips  # (kept for readability)


def test_the_fitted_curve_recovers_a_real_slope():
    import random
    rng = random.Random(3)
    samples = []
    for _ in range(3000):
        gap = rng.uniform(-10, 10)
        samples.append((gap, 0, 1.0 if rng.random() < coy._sig(0.4 * gap) else 0.0))
    k, h = coy.fit_curve(samples)
    assert 0.33 < k < 0.47 and abs(h) < 0.2


def test_expected_state_value_rises_with_preseason_strength():
    strength = {f"T{i}": 40.0 + i for i in range(40)}
    exp = coy.expected_state_values(strength, 16, 0.4, ("t",), sims=300)
    assert exp["T39"] > exp["T30"] > exp["T20"]
    assert exp["T0"] < 1.0


def test_a_hand_archived_season_crowns_both_awards(tmp_path, monkeypatch):
    """Six programs in one league of one class: the team the model expected to
    finish last that won the league takes District; the champion that was
    already the favourite does not automatically take it."""
    db = str(tmp_path / "coy.db")
    real_db, real_ready = wd.WORLD_DB, wd._schema_ready_for
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    try:
        wd.init_schema()
        schools = [s for s in jh.load_schools("girls") if s.group == "5A"][:6]
        names = [s.name for s in schools]
        wid, year = 1, 3
        # Preseason: names[0] strongest … names[5] weakest.
        strength = {n: 60.0 - 4 * i for i, n in enumerate(names)}
        # Season: the weakest (names[5]) wins the league; the strongest is 2nd.
        order = [names[5], names[0], names[1], names[2], names[3], names[4]]
        standings = {"5A": {"L": [
            {"school": n, "record": "10-3", "drecord": f"{5 - i}-{i}", "place": i + 1,
             "pi": 0.9 - 0.1 * i} for i, n in enumerate(order)]}}
        arc = {"season_year": 2030, "standings": standings,
               "brackets": {"5A": {"field": [names[0], names[5]],
                                   "rounds": [[{"home": names[0], "away": names[5],
                                                "winner": names[0]}]],
                                   "champion": names[0]}},
               "champions": {"5A": names[0]}}
        conn = wd._db()
        conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data) VALUES (?,?,?,?)",
                     (wid, year, "girls", json.dumps(arc)))
        # A round robin in league: rank order wins every meeting.
        rank = {n: i for i, n in enumerate(order)}
        rows = []
        for a in names:
            for b in names:
                if a == b:
                    continue
                won = int(rank[a] < rank[b])
                rows.append((wid, year, "girls", a, b, int(a < b), "regular", won, 1))
        conn.executemany(
            "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp, home,"
            " phase, won, district, level) VALUES (?,?,?,?,?,?,?,?,?, 'v')", rows)
        conn.executemany(
            "INSERT INTO jhsaa_preseason (world_id, year, gender, school, strength)"
            " VALUES (?,?,?,?,?)", [(wid, year, "girls", n, v) for n, v in strength.items()])
        for i, s in enumerate(schools):
            conn.execute("INSERT INTO jhsaa_coach (world_id, coach_id, name, data) VALUES (?,?,?,?)",
                         (wid, f"c{i}", f"Coach {i}", "{}"))
            conn.execute(
                "INSERT INTO jhsaa_coach_history (world_id, year, ident, gender, slot,"
                " coach_id, school, classification, grp, wins, losses, ties, eff)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (wid, year, s.ident, "girls", "head", f"c{i}", s.name, "5A", "5A",
                 10, 3, 0, None))
        conn.commit()
        conn.close()
        assert coy.needs_awards(wid, year, "girls")
        got = coy.select_season(wid, year, "girls", salt="")
        assert got == {"district": 1, "state": 1}
        assert not coy.needs_awards(wid, year, "girls")
        aw = coy.season_awards(wid, year, "girls")
        district = aw["district"][("5A", "L")]
        assert district[0]["school"] == names[5]          # the surprise league title
        assert district[0]["name"] == "Coach 5"
        state = aw["state"]["5A"]
        assert {r["school"] for r in state} <= set(names)
        assert "district" in {a["level"] for a in coy.coach_awards(wid, "c5")}
        assert district[0]["detail"]["repeat"] == 0

        # A District COY won earlier IN THIS DISTRICT discounts the ranking score;
        # one won in another league does not.
        conn = wd._db()
        conn.executemany(
            "INSERT INTO jhsaa_coach_award (world_id, year, gender, level, grp, district,"
            " rank, school, ident, coach_id, coach_name, score, detail)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(wid, 1, "girls", "district", "5A", "L", 1, names[5], "", "c5", "Coach 5", 60, "{}"),
             (wid, 1, "girls", "district", "5A", "Other", 1, names[0], "", "c0", "Coach 0", 60, "{}")])
        conn.commit()
        conn.close()
        before = {r["coach_id"]: r["score"] for r in district}
        coy.select_season(wid, year, "girls", salt="")
        again = {r["coach_id"]: r for r in coy.season_awards(wid, year, "girls")["district"][("5A", "L")]}
        assert again["c5"]["detail"]["repeat"] == coy.DISTRICT_REPEAT_PENALTY
        assert abs(again["c5"]["score"] - (before["c5"] - coy.DISTRICT_REPEAT_PENALTY)) < 0.011
        assert all(r["detail"]["repeat"] == 0 for c, r in again.items() if c != "c5")
    finally:
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready

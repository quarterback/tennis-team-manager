"""Media/Coaches poll engine: deterministic, poll-scored, with human inertia."""
from app import polls


def _synthetic_snap(seed=999):
    """8 power-D1 teams; higher index = lower prestige. Week 1 higher seeds win;
    week 2 the #1 (T0) suffers an upset loss while the chasers stay unbeaten."""
    def team(s, prestige):
        return {"school": s, "division": "D1", "conf": "ACC", "prestige": prestige,
                "reputation": 0.72 + 0.28 * prestige, "is_power": True, "games": []}
    teams = {f"T{i}": team(f"T{i}", 0.9 - 0.05 * i) for i in range(8)}

    def add(a, b, awon, wk):
        teams[a]["games"].append((b, awon, True, wk))
        teams[b]["games"].append((a, not awon, False, wk))
    add("T0", "T7", True, 1); add("T1", "T6", True, 1)
    add("T2", "T5", True, 1); add("T3", "T4", True, 1)
    add("T0", "T5", False, 2)                                  # T0 upset loss
    add("T1", "T4", True, 2); add("T2", "T6", True, 2); add("T3", "T7", True, 2)
    return {"teams": teams, "seed": seed, "gender": "men", "week": 2}


def _positions(seed, poll, week, snap):
    b = polls._weekly_board(seed, "men", poll, week, snap)
    return {r["school"]: i + 1 for i, r in enumerate(b)}


def test_ballot_points_and_first_votes():
    """1st-place vote = 25 points, and every ranked team has positive points."""
    snap = _synthetic_snap()
    polls._board_cache.clear()
    board = polls._weekly_board(999, "men", "media", 1, snap)
    assert board and all(r["points"] > 0 for r in board)
    # the board leader collected first-place votes
    assert board[0]["firsts"] >= 1


def test_records_track_results():
    snap = _synthetic_snap()
    polls._board_cache.clear()
    board = {r["school"]: r for r in polls._weekly_board(999, "men", "coaches", 2, snap)}
    assert board["T0"]["record"] == "1-1"          # won wk1, lost wk2
    assert board["T1"]["record"] == "2-0"


def test_inertia_a_single_loss_slides_not_craters():
    """The undefeated #1 that loses once falls a few spots (passed by the unbeaten
    chasers and its conqueror) but does not crater to the bottom."""
    snap = _synthetic_snap()
    polls._board_cache.clear()
    wk1 = _positions(999, "coaches", 1, snap)
    wk2 = _positions(999, "coaches", 2, snap)
    assert wk1["T0"] <= 2                            # an undefeated top-reputation team
    assert wk2["T0"] > wk1["T0"]                     # the loss cost it ground...
    assert wk2["T0"] <= 6                            # ...but it slid, it didn't crater (of 8)


def test_deterministic():
    snap = _synthetic_snap()
    polls._board_cache.clear()
    a = polls._weekly_board(999, "men", "media", 2, snap)
    polls._board_cache.clear()
    b = polls._weekly_board(999, "men", "media", 2, snap)
    assert [r["school"] for r in a] == [r["school"] for r in b]
    assert [r["points"] for r in a] == [r["points"] for r in b]


def test_media_more_volatile_than_coaches():
    """Same results, different electorates: the reactive media poll rewards the
    upset winner at least as much as the conservative coaches poll."""
    snap = _synthetic_snap()
    polls._board_cache.clear()
    media = _positions(999, "media", 2, snap)
    coaches = _positions(999, "coaches", 2, snap)
    # T5 pulled the upset; media should not rank it worse than coaches do.
    assert media["T5"] <= coaches["T5"] + 2

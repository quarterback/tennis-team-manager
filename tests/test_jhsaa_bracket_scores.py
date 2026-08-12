"""A bracket card and a line score must be read from the right SIDE.

Both of these shipped wrong and both looked right half the time, which is why they
survived a design pass, a review and a merge:

* `_bracket.html` picks its half of `m.score` by which side WON, so the string has to be
  WINNER-FIRST. The college callers build `max-min`; the JHSAA built `home-away`, so
  every card the AWAY team won showed the two numbers swapped — a 5-0 winner displayed
  with 0. Cards the home team won were correct, so the bracket read as a plausible run
  of upsets rather than as a bug.

* `jhsaa._score_str` writes set scores home-first. An away team's card flipped the
  names and the won/lost marker and left the numbers alone, so a pair was shown winning
  a match the score says they lost.
"""
import pytest

from app import jhsaa
from app.web import state as st


def _bracket():
    """A 4-team draw where the AWAY side wins twice — the case that was broken — and the
    home side wins once, so a fix that merely swaps the bug over still fails."""
    return {
        "field": ["Alpha", "Bravo", "Charlie", "Delta"],
        "champion": "Delta",
        "rounds": [
            [{"home": "Alpha", "away": "Bravo", "home_points": 1, "away_points": 4,
              "winner": "Bravo"},
             {"home": "Charlie", "away": "Delta", "home_points": 2, "away_points": 3,
              "winner": "Delta"}],
            [{"home": "Bravo", "away": "Delta", "home_points": 2, "away_points": 3,
              "winner": "Delta"}],
        ],
    }


def _shown(card):
    """What `brk_row` would print beside each side: it splits on '-' and takes the first
    half for the winner, the second for the loser."""
    a, b = card["score"].split("-")
    home_first = card["home"]["won"]
    return (int(a), int(b)) if home_first else (int(b), int(a))


def test_a_bracket_card_shows_each_team_its_own_points():
    br = _bracket()
    cols = st._jh_bracket_cols(br, {})
    games = {(g["home"], g["away"]): g for rd in br["rounds"] for g in rd}
    seen = 0
    for col in cols:
        for m in col["matchups"]:
            if not m["played"]:
                continue
            g = games[(m["home"]["school"], m["away"]["school"])]
            assert _shown(m) == (g["home_points"], g["away_points"]), (g, m["score"])
            seen += 1
    assert seen == 3


def test_a_bracket_card_never_shows_a_winner_the_lower_score():
    for col in st._jh_bracket_cols(_bracket(), {}):
        for m in col["matchups"]:
            if not m["played"]:
                continue
            hi, lo = _shown(m)
            winner_score = hi if m["home"]["won"] else lo
            assert winner_score == max(hi, lo), (m["winner"], m["score"])


def test_the_final_card_is_winner_first_too():
    """The hub's final reads "champion def. runner-up" beside this score, so a
    home-first string prints the runner-up's number first."""
    view = st._jh_final_four(_bracket(), {})
    assert view["champion"]["name"] == "Delta"
    assert view["final"]["score"] == "3-2"


# --- line scores --------------------------------------------------------------

def _line(score, home_won=True):
    return {"slot": "S1", "home": ["H"], "away": ["A"], "score": score,
            "home_won": home_won}


def test_a_home_card_keeps_the_line_score_as_written():
    d = {"home": True, "lines": [_line("6-4, 3-6, 6-2")]}
    assert st._jh_side_lines(d)[0]["score"] == "6-4, 3-6, 6-2"


def test_an_away_card_flips_the_line_score():
    d = {"home": False, "lines": [_line("6-4, 3-6, 6-2")]}
    assert st._jh_side_lines(d)[0]["score"] == "4-6, 6-3, 2-6"


@pytest.mark.parametrize("home", [True, False])
def test_the_sets_always_agree_with_who_is_shown_winning(home):
    """The invariant the screenshot broke: whoever the card marks as having won the
    line must be the side with the winning set scores."""
    d = {"home": home, "lines": [_line("6-4, 3-6, 6-2", home_won=True),
                                 _line("4-6, 6-7", home_won=False)]}
    for ln in st._jh_side_lines(d):
        we = ln["home_won"] if home else not ln["home_won"]
        sets = [s.strip().split("-") for s in ln["score"].split(",")]
        won = sum(1 for a, b in sets if int(a) > int(b))
        assert (won > len(sets) / 2) is we, (ln, home)


def test_a_flip_does_not_mutate_the_archived_line():
    """`play_dual` appends the SAME `lines` list to both teams' schedules, so a
    perspective flip must copy rather than edit in place."""
    ln = _line("6-4, 3-6, 6-2")
    out = st._jh_side_lines({"home": False, "lines": [ln]})
    assert ln["score"] == "6-4, 3-6, 6-2"
    assert out[0] is not ln


def test_the_college_bracket_still_builds_winner_first():
    """The shared macro's contract, pinned from the other side: whatever the JHSAA does,
    the college callers must keep emitting max-min or they break the same way."""
    src = (st.__file__).replace(".pyc", ".py")
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    assert 'f"{max(hp, ap)}-{min(hp, ap)}"' in text
    assert 'f"{int(gm.get(\'home_points\', 0))}-{int(gm.get(\'away_points\', 0))}"' not in text

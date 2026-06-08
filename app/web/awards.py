"""Postseason honors — All-American (national) and All-Conference — derived from
the same cached season everything else renders. Selection is rating-based: a
player's STR (live results rating) ranks them nationally for All-American and
within their conference for All-Conference, with a minimum match count so a
tiny-sample hot streak can't sneak onto a team.

These are *computed* honors (a transparent proxy for the real NCAA selection),
so they stay consistent with the rankings, box scores, and player cards."""
from __future__ import annotations

from .state import get_season, ranking_rows, DEFAULT_SEED

# Selection sizes (singles). Tunable; deliberately conservative.
AA_FIRST = 10           # First Team All-American (national)
AA_SECOND = 25          # through here = Second Team All-American
AA_HM = 40              # through here = Honorable Mention All-American
CONF_FIRST = 6          # First Team All-Conference (per conference)
CONF_SECOND = 12        # through here = Second Team All-Conference
MIN_MATCHES = 4         # ignore tiny-sample players

_cache: dict = {}


def _eff_seed(seed: int) -> int:
    import app.world as world
    if world.exists(seed):
        world.prime(seed)
        return world.current_year_seed(seed)
    return seed


def _eligible(division: str, gender: str, seed: int) -> list[dict]:
    """STR-rated players with enough matches, tagged with school + conference,
    sorted strongest first."""
    sr = get_season(division, gender, seed)
    conf = {r.school: (r.conf, r.conf_abbr) for r in ranking_rows(division, gender, seed)}
    out = []
    for school, roster in sr.rosters.items():
        c, ca = conf.get(school, ("Independent", "IND"))
        for pr in roster:
            s, rel = sr.player_str.get(pr.pid, (None, 0.0))
            if s is None:
                continue
            w, l = sr.player_record.get(pr.pid, (0, 0))
            if w + l < MIN_MATCHES:
                continue
            out.append({"pid": pr.pid, "name": pr.name, "school": school,
                        "conf": c, "conf_abbr": ca, "str": s, "w": w, "l": l})
    out.sort(key=lambda p: (p["str"], p["w"]), reverse=True)
    return out


def season_awards(division: str, gender: str, seed: int = DEFAULT_SEED) -> dict:
    """Returns:
      all_american: [{tier, players:[...]}]   (national, by STR)
      all_conference: [(conf, [{tier, players:[...]}])]   (per conference)
      by_pid: { pid: [honor_label, ...] }   (for player cards / rosters)
    """
    eff = _eff_seed(seed)
    key = (division, gender, eff)
    if key in _cache:
        return _cache[key]

    players = _eligible(division, gender, seed)
    by_pid: dict[str, list[str]] = {}

    def tag(p, label):
        by_pid.setdefault(p["pid"], []).append(label)

    # ---- All-American (national) ----
    aa_first, aa_second, aa_hm = [], [], []
    for i, p in enumerate(players):
        if i < AA_FIRST:
            aa_first.append(p); tag(p, "First Team All-American")
        elif i < AA_SECOND:
            aa_second.append(p); tag(p, "Second Team All-American")
        elif i < AA_HM:
            aa_hm.append(p); tag(p, "All-American Honorable Mention")
        else:
            break
    all_american = [t for t in (
        {"tier": "First Team", "players": aa_first},
        {"tier": "Second Team", "players": aa_second},
        {"tier": "Honorable Mention", "players": aa_hm},
    ) if t["players"]]

    # ---- All-Conference (per conference) ----
    by_conf: dict[str, list[dict]] = {}
    for p in players:                       # already STR-sorted
        by_conf.setdefault(p["conf"], []).append(p)
    all_conference = []
    for conf in sorted(by_conf):
        ps = by_conf[conf]
        first, second = [], []
        for i, p in enumerate(ps):
            if i < CONF_FIRST:
                first.append(p); tag(p, f"First Team All-{p['conf_abbr']}")
            elif i < CONF_SECOND:
                second.append(p); tag(p, f"Second Team All-{p['conf_abbr']}")
            else:
                break
        teams = [t for t in ({"tier": "First Team", "players": first},
                             {"tier": "Second Team", "players": second}) if t["players"]]
        if teams:
            all_conference.append((conf, teams))

    result = {"all_american": all_american, "all_conference": all_conference,
              "by_pid": by_pid, "player_count": len(players)}
    _cache[key] = result
    return result


def player_honors(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED) -> list[str]:
    return season_awards(division, gender, seed)["by_pid"].get(pid, [])


def reset_cache() -> None:
    _cache.clear()

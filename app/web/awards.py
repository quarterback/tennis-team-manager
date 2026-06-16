"""Postseason honors — All-American (national) and All-Conference — derived from
the same cached season everything else renders. Selection is rating-based: a
player's STR (live results rating) ranks them nationally for All-American and
within their conference for All-Conference, with a minimum match count so a
tiny-sample hot streak can't sneak onto a team.

These are *computed* honors (a transparent proxy for the real NCAA selection),
so they stay consistent with the rankings, box scores, and player cards."""
from __future__ import annotations

from .state import ranking_rows, DEFAULT_SEED

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


def _sid(division: str, gender: str, seed: int) -> int:
    import app.world as world
    import app.seasonmode as sm
    return sm.get_or_create(division, gender, seed=world.current_year_seed(seed))


def _concluded(division: str, gender: str, seed: int) -> bool:
    """True once this universe's season has fully concluded (postseason done).
    Honors are end-of-season, NOT weekly — nothing is awarded before this, so
    every honors surface (All-American, All-Conference, POTY, COTY) stays empty
    until the season's phase reaches 'complete'."""
    import app.seasonmode as sm
    return sm.load_season(_sid(division, gender, seed)).get("phase") == "complete"


def _empty_awards() -> dict:
    return {"all_american": [], "all_conference": [], "by_pid": {}, "player_count": 0,
            "national_poty": None, "conf_poty": [], "conf_champions": [],
            "national_champion": None, "concluded": False}


def _roster(division: str, gender: str, school: str):
    from app.ncaa import build_roster, load_division
    prog = load_division(division, gender).by_school(school)
    return build_roster(prog) if prog else []


def _eligible(division: str, gender: str, seed: int) -> list[dict]:
    """STR-rated players with enough matches, tagged with school + conference,
    sorted strongest first — from the live week-by-week season."""
    import app.seasonmode as sm
    sid = _sid(division, gender, seed)
    conf = {r.school: (r.conf, r.conf_abbr) for r in ranking_rows(division, gender, seed)}
    pidx = sm._pid_index(division, gender)
    strmap = sm.season_player_str(sid)
    recs = sm.player_records(sid)
    out = []
    for pid, (s, rel) in strmap.items():
        info = pidx.get(pid)
        if info is None or s is None:
            continue
        w, l = recs.get(pid, (0, 0))
        if w + l < MIN_MATCHES:
            continue
        c, ca = conf.get(info["school"], ("Independent", "IND"))
        out.append({"pid": pid, "name": info["name"], "school": info["school"],
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
    # Honors are end-of-season: nothing is named until the season concludes.
    # Don't cache the in-progress empty (so it fills once the season completes).
    if not _concluded(division, gender, seed):
        return _empty_awards()

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

    # Player of the Year (national + per conference) and team champions.
    national_poty = players[0] if players else None
    conf_poty = sorted(({"conf": c, **ps[0]} for c, ps in by_conf.items() if ps),
                       key=lambda p: p["conf"])
    import app.seasonmode as sm
    sid = _sid(division, gender, seed)
    confmap = {r.school: r.conf for r in ranking_rows(division, gender, seed)}
    conf_champions = sorted(((confmap.get(school, ""), school)
                             for school in sm.conf_champions(sid)))
    national_champion = sm.national_champion(sid)

    result = {"all_american": all_american, "all_conference": all_conference,
              "by_pid": by_pid, "player_count": len(players),
              "national_poty": national_poty, "conf_poty": conf_poty,
              "conf_champions": conf_champions, "national_champion": national_champion,
              "concluded": True}
    _cache[key] = result
    return result


def player_honors(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED) -> list[str]:
    return season_awards(division, gender, seed)["by_pid"].get(pid, [])


# ---------------------------------------------------------------------------
# Stampable honor records — the single computation the persistence + the player
# cards both consume. Includes the individual honors plus Player of the Year and
# team titles (conference + national champions credited to the whole roster).
# ---------------------------------------------------------------------------
_rec_cache: dict = {}


def honor_records(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[dict]:
    eff = _eff_seed(seed)
    key = (division, gender, eff)
    if key in _rec_cache:
        return _rec_cache[key]
    # End-of-season honors only — empty (and uncached) until the season concludes.
    if not _concluded(division, gender, seed):
        return []

    import app.world as world
    import app.seasonmode as sm
    sid = _sid(division, gender, seed)
    yr = world.load_world(seed)["year"] if world.exists(seed) else 0
    year, season_no = 2026 + yr, yr + 1
    conf = {r.school: (r.conf, r.conf_abbr) for r in ranking_rows(division, gender, seed)}
    players = _eligible(division, gender, seed)        # STR-sorted, conf-tagged

    recs: list[dict] = []

    def add(pid, name, school, award, label, sort):
        recs.append({"subject_type": "player", "subject_id": pid, "name": name,
                     "year": year, "season_no": season_no, "division": division,
                     "gender": gender, "school": school, "award": award,
                     "label": label, "sort": sort})

    def add_p(p, award, label, sort):
        add(p["pid"], p["name"], p["school"], award, label, sort)

    by_conf: dict[str, list[dict]] = {}
    for p in players:
        by_conf.setdefault(p["conf"], []).append(p)

    # Player of the Year — national + per conference.
    if players:
        add_p(players[0], "national_poty", "National Player of the Year", 100)
    for c, ps in by_conf.items():
        if ps:
            add_p(ps[0], "conf_poty", f"{c} Player of the Year", 60)

    # All-American (national).
    for i, p in enumerate(players):
        if i < AA_FIRST:
            add_p(p, "all_american", "First Team All-American", 90)
        elif i < AA_SECOND:
            add_p(p, "all_american", "Second Team All-American", 85)
        elif i < AA_HM:
            add_p(p, "all_american", "All-American Honorable Mention", 80)
        else:
            break

    # All-Conference (per conference).
    for c, ps in by_conf.items():
        for i, p in enumerate(ps):
            if i < CONF_FIRST:
                add_p(p, "all_conference", f"First Team All-{p['conf_abbr']}", 50)
            elif i < CONF_SECOND:
                add_p(p, "all_conference", f"Second Team All-{p['conf_abbr']}", 45)
            else:
                break

    # Team titles — credit every player on the roster.
    def credit_roster(school, award, label, sort):
        for pr in _roster(division, gender, school):
            add(pr.pid, pr.name, school, award, label, sort)

    for school in sm.conf_champions(sid):
        cname = conf.get(school, ("Conference", ""))[0]
        credit_roster(school, "conf_champion", f"{cname} Champion", 55)
    champ = sm.national_champion(sid)
    if champ:
        credit_roster(champ, "national_champion", "National Champion", 110)

    _rec_cache[key] = recs
    return recs


def coach_honor_records(division: str, gender: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """Coach of the Year (national + per conference) and team titles for the
    head coach of each champion. Keyed to the coach's stable id so they follow
    the coach between schools."""
    import app.world as world
    import app.seasonmode as sm
    from .state import head_coach

    if not _concluded(division, gender, seed):     # COTY/titles only at season's end
        return []
    sid = _sid(division, gender, seed)
    rows = ranking_rows(division, gender, seed)
    yr = world.load_world(seed)["year"] if world.exists(seed) else 0
    year, season_no = 2026 + yr, yr + 1
    recs: list[dict] = []

    def add_head(school, award, label, sort):
        hc = head_coach(division, gender, school)
        if not hc:
            return
        recs.append({"subject_type": "coach", "subject_id": hc["coach_id"],
                     "name": hc["name"], "year": year, "season_no": season_no,
                     "division": division, "gender": gender, "school": school,
                     "award": award, "label": label, "sort": sort})

    # Coach of the Year — head coach of the top-PI team, national + per conference.
    if rows:
        top = max(rows, key=lambda r: r.pi)
        add_head(top.school, "national_coty", "National Coach of the Year", 95)
    by_conf: dict[str, list] = {}
    for r in rows:
        by_conf.setdefault(r.conf, []).append(r)
    for conf, rs in by_conf.items():
        best = max(rs, key=lambda r: r.pi)
        add_head(best.school, "conf_coty", f"{conf} Coach of the Year", 58)

    # National Assistant Coach of the Year — rewards player development, not the
    # head-coach W-L: the program with the most wins at the BOTTOM of the lineup
    # (4/5/6 singles + 3rd doubles), among the division's top-25 programs, where an
    # assistant's developmental work shows. Credited to that staff's lead developer
    # (best development-rated non-head coach). Per division × gender, deterministic.
    from .state import coaching_staff
    top25 = [r.school for r in sorted(rows, key=lambda r: r.pi, reverse=True)[:25]]
    if top25:
        devwins = sm.developmental_wins(sid)
        pi_by = {r.school: r.pi for r in rows}
        school = max(top25, key=lambda s: (devwins.get(s, 0), pi_by.get(s, 0.0), s))
        asst_staff = [c for c in coaching_staff(division, gender, school) if c["role"] != "head"]
        if asst_staff:
            dev_coach = max(asst_staff, key=lambda c: (c["dev"], c["role"]))
            recs.append({"subject_type": "coach", "subject_id": dev_coach["coach_id"],
                         "name": dev_coach["name"], "year": year, "season_no": season_no,
                         "division": division, "gender": gender, "school": school,
                         "award": "national_asst_coty",
                         "label": "National Assistant Coach of the Year", "sort": 92})

    # Team titles for the head coach of each champion.
    confmap = {r.school: r.conf for r in rows}
    for school in sm.conf_champions(sid):
        add_head(school, "conf_champion", f"{confmap.get(school, 'Conference')} Champion", 55)
    champ = sm.national_champion(sid)
    if champ:
        add_head(champ, "national_champion", "National Champion", 110)
    return recs


def record_coach_seasons(division: str, gender: str, seed: int = DEFAULT_SEED) -> int:
    """Stamp the concluded season onto every coach's history: the seat they held
    and their team's final record. Captured at the awards phase (alongside honors,
    before the rollover) so a coach's career record persists by team, year over
    year — even after they move. Career wins later count head seasons only."""
    import app.world as world
    import app.coachreg as coachreg
    from .state import coaching_staff, team_results
    if not _concluded(division, gender, seed):
        return 0
    yr = world.load_world(seed)["year"] if world.exists(seed) else 0
    year, season_no = 2026 + yr, yr + 1
    from app import ncaa
    n = 0
    for prog in ncaa.load_division(division, gender).programs:
        rec = team_results(division, gender, prog.school, seed)
        for s in coaching_staff(division, gender, prog.school):
            coachreg.record_season(s["coach_id"], year, season_no, division, gender,
                                   prog.school, s["role"], rec["wins"], rec["losses"])
            n += 1
    return n


def stamp_world_honors(seed: int = DEFAULT_SEED) -> int:
    """Compute and persist this season-year's honors (players + coaches) for
    every universe. The 'awards phase' action — idempotent, re-runnable."""
    import app.world as world
    import app.honors as honors
    from .state import UNIVERSES
    yr = world.load_world(seed)["year"] if world.exists(seed) else 0
    year = 2026 + yr
    total = 0
    for _u, division, gender, _label in UNIVERSES:
        honors.clear_season(year, division, gender)
        total += honors.stamp(honor_records(division, gender, seed))
        total += honors.stamp(coach_honor_records(division, gender, seed))
        record_coach_seasons(division, gender, seed)
    return total


def coach_career_table(coach_id: str, seed: int = DEFAULT_SEED) -> dict:
    """A coach's record by team, year over year (the player record table, applied
    to coaches). Each row is a season seat (year, school, role, team W-L); the
    current season is shown live until it concludes. Career wins count HEAD-coach
    seasons ONLY — assistants bank no wins until they run a program."""
    import app.world as world
    import app.coachreg as coachreg
    from .state import team_results
    ROLE = {"head": "Head Coach", "assoc": "Associate Head Coach", "asst": "Assistant Coach"}
    rows = coachreg.history(coach_id)
    cur_year = 2026 + (world.load_world(seed)["year"] if world.exists(seed) else 0)
    # Prepend the live current season for the coach's present seat (not yet stamped).
    if not any(r["year"] == cur_year for r in rows):
        c = coachreg.get(coach_id)
        if c and c.get("school"):
            rec = team_results(c["division"], c["gender"], c["school"], seed)
            rows.insert(0, {"coach_id": coach_id, "year": cur_year,
                            "season_no": (cur_year - 2026) + 1, "division": c["division"],
                            "gender": c["gender"], "school": c["school"], "role": c["role"],
                            "wins": rec["wins"], "losses": rec["losses"], "live": True})
    out, cw, cl = [], 0, 0
    for r in rows:
        is_head = r["role"] == "head"
        if is_head:
            cw += r["wins"] or 0
            cl += r["losses"] or 0
        out.append({"year": r["year"], "season_no": r["season_no"], "school": r["school"],
                    "division": r["division"], "gender": r["gender"], "role": r["role"],
                    "role_label": ROLE.get(r["role"], "Coach"), "wins": r["wins"],
                    "losses": r["losses"], "counts": is_head, "live": r.get("live", False)})
    return {"rows": out, "career_w": cw, "career_l": cl,
            "head_seasons": sum(1 for r in out if r["counts"])}


def coach_player_awards(coach_id: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """Players a coach helped develop who won awards — every player honor at a
    program during a season the coach was on its staff, grouped by year."""
    import app.honors as honors
    import app.coachreg as coachreg
    seen, groups = set(), {}
    for r in coachreg.history(coach_id):
        k = (r["year"], r["division"], r["gender"], r["school"])
        if k in seen:
            continue
        seen.add(k)
        for h in honors.at_school(r["year"], r["division"], r["gender"], r["school"], "player"):
            g = groups.setdefault(r["year"], {"year": r["year"], "school": r["school"], "players": []})
            g["players"].append({"pid": h["subject_id"], "name": h["name"],
                                 "label": h["label"], "award": h["award"]})
    return [groups[y] for y in sorted(groups, reverse=True)]


def coach_career_honors(division: str, gender: str, coach_id: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """A coach's honors grouped by season-year (persisted + live current year)."""
    import app.world as world
    import app.honors as honors
    groups = honors.career_by_year(coach_id, "coach")
    cur_year = 2026 + (world.load_world(seed)["year"] if world.exists(seed) else 0)
    if not any(g["year"] == cur_year for g in groups):
        live = [r for r in coach_honor_records(division, gender, seed) if r["subject_id"] == coach_id]
        if live:
            live.sort(key=lambda r: r["sort"], reverse=True)
            groups.insert(0, {"year": cur_year, "season_no": live[0]["season_no"],
                              "school": live[0]["school"], "awards": live, "live": True})
    return groups


def player_career_honors(division: str, gender: str, pid: str, seed: int = DEFAULT_SEED) -> list[dict]:
    """A player's honors grouped by season-year (newest first), keyed to pid so
    they follow transfers. Persisted years come from the store; the current year
    is shown live until the awards phase stamps it."""
    import app.world as world
    import app.honors as honors
    groups = honors.career_by_year(pid, "player")
    cur_year = 2026 + (world.load_world(seed)["year"] if world.exists(seed) else 0)
    if not any(g["year"] == cur_year for g in groups):
        live = [r for r in honor_records(division, gender, seed) if r["subject_id"] == pid]
        if live:
            live.sort(key=lambda r: r["sort"], reverse=True)
            groups.insert(0, {"year": cur_year, "season_no": live[0]["season_no"],
                              "school": live[0]["school"], "awards": live, "live": True})
    return groups


def reset_cache() -> None:
    _cache.clear()
    _rec_cache.clear()

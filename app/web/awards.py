"""Postseason honors — All-American (national) and All-Conference — derived from
the same cached season everything else renders. Selection is PURELY results-based
and position-weighted: a player is ranked by their position-weighted win total
(1st singles wins count full, each lower line less, doubles lines a quarter to
three-quarters — see ``_POS_W`` / ``_DBL_W``), with a minimum match count so a
tiny-sample hot streak can't sneak onto a team. Rating (STR) plays NO part in
selection — it is carried only for display.

These are *computed* honors (a transparent proxy for the real NCAA selection),
so they stay consistent with the rankings, box scores, and player cards."""
from __future__ import annotations

import logging

from .state import ranking_rows, DEFAULT_SEED

log = logging.getLogger("baseline.awards")

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


# Award performance is position-weighted WINS ONLY — no rating (STR), no win%, no
# team factor. A win at the top of the lineup faces far stronger opponents than one
# at the bottom, so it is worth proportionally more; a padded record at 5th/6th
# singles can no longer out-honor a player carrying the 1-2-3 courts. Weights are
# owner-set (2027): each singles line is worth 0.2 less than the one above it, and
# the three doubles lines add at 0.75 / 0.50 / 0.25. Wins count at the line they
# were ACTUALLY won at (from the per-line box record), not the player's rank on
# their team — so bouncing down the lineup for easy wins gains nothing. An unusually
# strong team still places lower-line players: their teammates are elite, but they
# personally pile up wins at a meaningful line, which is exactly what the score
# rewards.
_POS_W = {1: 1.00, 2: 0.80, 3: 0.60, 4: 0.40, 5: 0.20, 6: 0.10,
          # The expanded cards (D1/D4 field 10 singles, D1 five doubles) extend the
          # owner's 1-6 weights unchanged and taper below them — a deep-card win is
          # worth little but never nothing, and the top courts still decide honors.
          7: 0.08, 8: 0.06, 9: 0.04, 10: 0.02}
_DBL_W = {1: 0.75, 2: 0.50, 3: 0.25, 4: 0.15, 5: 0.10}


def _eligible(division: str, gender: str, seed: int) -> list[dict]:
    """Players with enough matches, tagged with school + conference, ranked by
    POSITION-WEIGHTED WINS (see ``_POS_W`` / ``_DBL_W``). Honors are earned on
    court and only on court: rating plays no part. STR is carried on each record
    for display only, never for selection."""
    import app.seasonmode as sm
    from app.ncaa import conf_prestige
    sid = _sid(division, gender, seed)
    rrows = ranking_rows(division, gender, seed)
    conf = {r.school: (r.conf, r.conf_abbr) for r in rrows}

    def _wpct(rec):
        try:
            w, l = rec.split("-")
            g = int(w) + int(l)
            return int(w) / g if g else 0.5
        except (ValueError, AttributeError):
            return 0.5
    team_wpct = {r.school: _wpct(r.rec) for r in rrows}     # national tiebreak input
    pidx = sm._pid_index(division, gender)
    strmap = sm.season_player_str(sid)          # display only
    recs = sm.player_records(sid)               # pid -> (w, l) singles totals (eligibility)
    lrec = sm.player_line_records(sid)          # pid -> {'singles': {n:[w,l]}, 'doubles': {n:[w,l]}}
    out = []
    unresolved = 0
    for pid, (w, l) in recs.items():
        if w + l < MIN_MATCHES:
            continue
        info = pidx.get(pid)
        if info is None:
            # A pid in the season's results that the CURRENT roster generation
            # does not produce. One or two is ordinary churn (a transfer, a
            # portal move); all of them means the season and the rosters are
            # describing different populations — see the guard below.
            unresolved += 1
            continue
        c, ca = conf.get(info["school"], ("Independent", "IND"))
        lr = lrec.get(pid, {})
        sing = lr.get("singles", {})
        dbl = lr.get("doubles", {})
        perf = sum(wl[0] * _POS_W.get(n, 0.02) for n, wl in sing.items())
        perf += sum(wl[0] * _DBL_W.get(n, 0.10) for n, wl in dbl.items())
        # Primary singles line = where they logged the most matches (display + POTY
        # context); ties break to the higher (lower-numbered) line.
        line = min(sing, key=lambda n: (-(sing[n][0] + sing[n][1]), n)) if sing else 99
        s, _rel = strmap.get(pid, (None, None))
        out.append({"pid": pid, "name": info["name"], "school": info["school"],
                    "conf": c, "conf_abbr": ca, "str": s if s is not None else 0.0,
                    "w": w, "l": l, "line": line, "perf": round(perf, 2),
                    "team_wpct": round(team_wpct.get(info["school"], 0.5), 3),
                    "conf_prestige": round(conf_prestige(ca), 3)})
    # ‼️ AN EMPTY HONORS BOARD ON A PLAYED SEASON IS A FAULT, NOT A RESULT.
    # Every pid failing to resolve means the season's results and the roster
    # generation are describing DIFFERENT POPULATIONS — the save's world was
    # reset (or rebuilt under a new salt) while its played season rows survived.
    # Nothing errored: `_eligible` returned [], every All-American tier came back
    # empty, and the awards page rendered a clean, plausible, completely wrong
    # "nobody was honored". That is the silent-degradation shape this codebase
    # keeps paying for, so it is now loud.
    if unresolved and not out:
        log.error(
            "awards: %s-%s has %d players with results but NONE resolve against the "
            "current roster index (%d pids). The season and the rosters are from "
            "different worlds — the world was probably reset while its season rows "
            "survived. Honors will be empty until the season is replayed.",
            division, gender, unresolved, len(pidx))
    elif unresolved > 0.25 * max(1, unresolved + len(out)):
        log.warning("awards: %s-%s dropped %d of %d players as unresolved pids",
                    division, gender, unresolved, unresolved + len(out))
    out.sort(key=lambda p: (p["perf"], p["w"], -p["l"]), reverse=True)
    return out


# National tiebreak. Position-weighted wins pick the field; when two players are
# within ~NAT_BAND of each other, the tougher résumé wins the spot — team record
# and conference prestige, equal weight. The boost tops out at NAT_BAND of a
# player's own score, so it ONLY reorders near-ties: it can lift a player over
# someone within 10% of them, never over a clearly greater record. Applied to the
# NATIONAL awards only (All-American, national Player of the Year); per-conference
# awards keep the raw position-weighted order (prestige is constant inside a
# conference).
NAT_BAND = 0.10


def _resume(p: dict) -> float:
    """Strength-of-résumé in [0,1]: team record + conference prestige, equal weight."""
    return 0.5 * p.get("team_wpct", 0.5) + 0.5 * p.get("conf_prestige", 0.5)


def _national_order(players: list[dict]) -> list[dict]:
    """`players` (already position-weighted-win sorted) reordered for national
    honors, applying the bounded near-tie résumé boost. Stable within a perfect
    tie via the base order."""
    return sorted(players, key=lambda p: p["perf"] * (1.0 + NAT_BAND * _resume(p)),
                  reverse=True)


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
    nat = _national_order(players)              # national honors: near-tie résumé boost
    by_pid: dict[str, list[str]] = {}

    def tag(p, label):
        by_pid.setdefault(p["pid"], []).append(label)

    # ---- All-American (national) ----
    aa_first, aa_second, aa_hm = [], [], []
    for i, p in enumerate(nat):
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
    for p in players:                       # per-conference: raw position-weighted order
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
    national_poty = nat[0] if nat else None
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


def archive_years(division: str, gender: str):
    """Season-years that have stamped honors for this universe (newest first) —
    the year picker for the past-winners archive."""
    import app.honors as honors
    return [y for y in honors.years() if honors.has_season(y, division, gender)]


def awards_archive(division: str, gender: str, year: int) -> dict:
    """A past season's award winners, read from the stamped honors store (so the
    list is saved, not regenerated). Grouped for display; links resolve by the
    same pid/coach_id the honors were stamped under."""
    import app.honors as honors
    from .rankings_data import crest

    def deco(r):
        ab, col = crest(r["school"]) if r.get("school") else ("—", "#888")
        return {**r, "abbr": ab, "color": col}

    rows = honors.for_season(year, division, gender)
    poty = None
    conf_poty, asst_coty, conf_coty = [], [], []
    coty = None
    aa_tiers: dict = {}
    all_conf: dict = {}
    nat_champ = None
    conf_champs: dict = {}
    for r in rows:
        a = r["award"]
        if a == "national_poty":
            poty = deco(r)
        elif a == "conf_poty":
            conf_poty.append(deco(r))
        elif a == "all_american":
            aa_tiers.setdefault(r["label"], []).append(deco(r))
        elif a == "all_conference":
            all_conf.setdefault(r["label"], []).append(deco(r))
        elif a == "national_champion":
            nat_champ = nat_champ or deco(r)
        elif a == "conf_champion":
            conf_champs.setdefault(r["school"], deco(r))   # credited to whole roster → dedupe
        elif a == "national_coty":
            coty = deco(r)
        elif a == "national_asst_coty":
            asst_coty.append(deco(r))
        elif a == "conf_coty":
            conf_coty.append(deco(r))
    # All-American tiers in prestige order (First, Second, Honorable Mention).
    aa = [{"tier": lbl, "players": ps}
          for lbl, ps in sorted(aa_tiers.items(), key=lambda kv: -kv[1][0]["sort"])]
    # Group All-Conference by conference so the archive collapses per league
    # instead of listing every team flat (it gets long across ~30 conferences).
    conf_groups: dict = {}
    for lbl, ps in all_conf.items():
        conf = lbl.split("All-", 1)[1] if "All-" in lbl else lbl
        conf_groups.setdefault(conf, []).append((lbl, ps))
    all_conference = [
        {"conf": conf,
         "count": sum(len(ps) for _, ps in teams),
         "teams": [{"tier": lbl, "players": ps}
                   for lbl, ps in sorted(teams, key=lambda kv: kv[0])]}
        for conf, teams in sorted(conf_groups.items())
    ]
    return {
        "year": year, "empty": not rows,
        "national_poty": poty, "conf_poty": sorted(conf_poty, key=lambda r: r["label"]),
        "national_coty": coty, "national_asst_coty": asst_coty,
        "conf_coty": sorted(conf_coty, key=lambda r: r["label"]),
        "national_champion": nat_champ,
        "conf_champions": sorted(conf_champs.values(), key=lambda r: r["label"]),
        "all_american": aa, "all_conference": all_conference,
    }


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
    players = _eligible(division, gender, seed)        # position-weighted-win sorted
    nat = _national_order(players)                     # national honors: near-tie résumé boost

    recs: list[dict] = []

    def add(pid, name, school, award, label, sort):
        recs.append({"subject_type": "player", "subject_id": pid, "name": name,
                     "year": year, "season_no": season_no, "division": division,
                     "gender": gender, "school": school, "award": award,
                     "label": label, "sort": sort})

    def add_p(p, award, label, sort):
        add(p["pid"], p["name"], p["school"], award, label, sort)

    by_conf: dict[str, list[dict]] = {}
    for p in players:                                  # per-conference: raw perf order
        by_conf.setdefault(p["conf"], []).append(p)

    # Player of the Year — national (résumé-adjusted) + per conference (raw perf).
    if nat:
        add_p(nat[0], "national_poty", "National Player of the Year", 100)
    for c, ps in by_conf.items():
        if ps:
            add_p(ps[0], "conf_poty", f"{c} Player of the Year", 60)

    # All-American (national).
    for i, p in enumerate(nat):
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
    indoor = sm.indoor_champion(sid)
    if indoor:
        credit_roster(indoor, "ita_indoor_champion", "ITA Indoor National Champion", 108)

    # NCAA individual titles — the singles champion and both halves of the winning
    # doubles pair get their own award chip. The draws are computed (memoized) once
    # the team season is complete, which is exactly when honors are stamped.
    from .state import get_singles_championship, get_doubles_championship
    for getter, award, label, sort in (
            (get_singles_championship, "singles_champion", "NCAA Singles Champion", 106),
            (get_doubles_championship, "doubles_champion", "NCAA Doubles Champion", 104)):
        ch = getter(division, gender, seed)
        winner = getattr(ch, "champion", None) if ch else None
        for pl in (getattr(winner, "players", None) or []):
            if pl.get("pid"):
                add(pl["pid"], pl["name"], winner.program.school, award, label, sort)

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
    # (best development-rated non-head coach). If multiple programs tie at the top,
    # every tied staff's developer is honored (the award simply repeats that year).
    from .state import coaching_staff
    top25 = [r.school for r in sorted(rows, key=lambda r: r.pi, reverse=True)[:25]]
    if top25:
        devwins = sm.developmental_wins(sid)
        best = max((devwins.get(s, 0) for s in top25), default=0)
        if best > 0:
            for school in sorted(s for s in top25 if devwins.get(s, 0) == best):
                asst_staff = [c for c in coaching_staff(division, gender, school)
                              if c["role"] != "head" and c.get("coach_id")]
                if not asst_staff:
                    continue
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
    indoor = sm.indoor_champion(sid)
    if indoor:
        add_head(indoor, "ita_indoor_champion", "ITA Indoor National Champion", 108)
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
            if not s.get("coach_id"):       # skip a vacant (retired) seat
                continue
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
    # Prepend the live current stint for the coach's present seat. A coach can
    # change programs during a season, so a row at the old school must not hide
    # the new live destination.
    c = coachreg.get(coach_id)
    if c and c.get("school"):
        current_key = (cur_year, c["division"], c["gender"], c["school"], c["role"])
        if not any((r["year"], r["division"], r["gender"], r["school"], r["role"])
                   == current_key for r in rows):
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

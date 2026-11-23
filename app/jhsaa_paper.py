"""THE PAPER — a local daily's prep tennis coverage of one JHSAA season, read one
edition at a time (owner ask 2026-11: "a local newspaper style 90s 'we actually hire
journalists covering high school sports' experience ... running reads on what's
going on").

A JHSAA season is simulated whole at week 0, so every page in the section is
written from the finished archive and every story knows the ending. But every
varsity dual carries a date inside the sport's real window (`world.
jhsaa_match_dates`), so the season can be REPLAYED: this module slices it into
dated editions and builds each one from what a reporter could have known that
morning.

Three layers, and only the last one writes prose:

1. **Edition calendar** (`editions`) — a preseason edition, Tuesday and Friday
   mornings through the regular season, then one every morning of the postseason,
   then a closing edition.
2. **The dated view** (`edition_view`) — results since the last edition, records
   and league standings THROUGH that morning, the fixtures before the next paper.
   Deterministic, a fold over the archive, no hindsight: nothing dated on or after
   the edition's morning is read.
3. **Stories** — written by an agent from `packet()` (the same dated facts plus
   the paper's own earlier stories) and stored per edition (`save_edition`). The
   page renders whatever has been written; an unwritten edition still has its
   results, standings and schedule.

‼️ THE AGENT ONLY EVER SEES THE PACKET. The archive and the research export both
hold end-of-season facts (final standings, awards, brackets). A writer that sees
the final table foreshadows it, and the paper reads like a retrospective again.

‼️ READ, NEVER RESIMULATE (CLAUDE.md rule 6). Everything here reads
`world_jhsaa_dual` and the display calendar the schedule pages already use.

The paper covers ONE AREA (a gazetteer area, 25-50 programs), the way a 90s daily
covered its circulation area; the rest of the state reaches it as State and TOC
results.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import re
import threading
import zipfile
from collections import defaultdict

#: Regular-season editions publish on these mornings (Mon=0): Tuesday carries the
#: weekend, Friday carries midweek.
REGULAR_EDITION_DAYS = (1, 4)

#: The phase a reader would see named on a results line.
PHASE_LABEL = {
    "early": "Invitational", "regular": "Invitational",
    "showcase_pod": "Showcase", "showcase_tiered": "Showcase",
    "sectional": "Sectionals", "ward": "Wards", "regional": "Regionals",
    "zonal": "Zonals", "epiregional": "Epiregional",
    "super_regional": "Super Regionals", "circuit": "Circuit",
    "semi_state": "Semi-State", "divisional": "Divisionals",
    "semi_conference": "Semi-Conference", "conference": "Conference",
    "special_challenger": "Special Challengers", "state_special": "State Specials",
    "metastate": "Metastate", "state": "State", "toc_qualifier": "TOC Qualifier",
    "toc": "Tournament of Champions",
}

#: Statewide results the paper prints whatever the area (the wire column).
WIRE_PHASES = ("state", "toc_qualifier", "toc")


def _postseason() -> tuple:
    from . import jhsaa as jh
    return tuple(jh.POSTSEASON)


def phase_label(phase: str, district: bool = False) -> str:
    if phase in ("regular", "early") and district:
        return "League"
    return PHASE_LABEL.get(phase, (phase or "").replace("_", " ").title())


# ------------------------------------------------------------------ loading ----
#
# Both loaders return the same normalised season:
#   {"season_year", "world_year", "gender", "source",
#    "programs": {name: {name, city, county, area, group, district, private, coach}},
#    "duals": [{id, date, phase, district, home, away, hp, ap, winner, tied,
#               lines: [{slot, score, home_won, home: [names], away: [names]}]}],
#    "grades": {(school, player name): grade}   (export only; filled lazily in-app)
#    "history": {name: [season rows, newest first]}  (seasons BEFORE this one)}

_cache: dict = {}
_cache_lock = threading.Lock()


def _lines(d: dict) -> list:
    """A dual's box score, unpacked on first use (archive mode stores it packed)."""
    if d.get("lines") is None:
        raw = d.get("_raw")
        if raw is None:
            d["lines"] = []
        else:
            from . import world as wd
            d["lines"] = wd.unpack_lines(raw) or []
    return d["lines"]


def _history(season: dict) -> dict:
    """Program seasons BEFORE this one, newest first. Loaded on first use, in the
    writer, never on a page render (it folds every archived season)."""
    if season.get("history") is None:
        from . import world as wd
        hist = {}
        try:
            for school, rows in wd.jhsaa_history_rows(season["world_id"], season["gender"],
                                                       current=False).items():
                older = [r for r in rows if (r.get("year") or 0) < season["world_year"]]
                if older:
                    hist[school] = older
        except Exception:
            hist = {}
        season["history"] = hist
    return season["history"]


def _date(s) -> dt.date | None:
    if isinstance(s, dt.date):
        return s
    try:
        return dt.date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def load_archive(world_id: int, world_year: int, gender: str) -> dict | None:
    """One archived gender-season off the persisted archive, varsity only. Memoised
    on the archive's own stamp (row count + max rowid), the desk's idiom, so a lab
    regenerate invalidates it."""
    from . import jhsaa as jh
    from . import world as wd
    conn = wd._db()
    try:
        stamp = tuple(conn.execute(
            "SELECT COUNT(*), MAX(rowid) FROM world_jhsaa_dual"
            " WHERE world_id=? AND year=? AND gender=?",
            (world_id, world_year, gender)).fetchone())
    finally:
        conn.close()
    if not stamp[0]:
        return None
    key = ("arc", world_id, world_year, gender, stamp)
    hit = _cache.get(key)
    if hit is not None:
        return hit
    arc = wd.get_jhsaa(world_id, world_year, gender)
    if not arc:
        return None
    season_year = arc.get("season_year")
    conn = wd._db()
    try:
        rows = conn.execute(
            "SELECT school, opp, home, phase, pf, pa, won, district, lines, level,"
            " tied, squad, opp_squad FROM world_jhsaa_dual"
            " WHERE world_id=? AND year=? AND gender=? AND home=1 ORDER BY rowid",
            (world_id, world_year, gender)).fetchall()
    finally:
        conn.close()
    dates = wd.jhsaa_match_dates(world_id, world_year, gender, season_year)
    duals = []
    for n, r in enumerate(rows):
        d = dict(r)
        # Varsity V1 play only: JV shares the table (the `level` rule) and a squad
        # dual is a JV fixture as far as a reader of the varsity season goes.
        if (d.get("level") or "v") != "v" or d.get("squad") or d.get("opp_squad"):
            continue
        when = dates.get(wd.jh_match_key(d))
        home = jh.current_name(d["school"], gender)
        away = jh.current_name(d["opp"], gender)
        tied = bool(d.get("tied"))
        duals.append({
            "id": f"d{n}", "date": when, "phase": d["phase"] or "",
            "district": bool(d["district"]), "home": home, "away": away,
            "hp": d["pf"], "ap": d["pa"], "tied": tied,
            "winner": None if tied else (home if d["won"] else away),
            # The box score stays packed until an edition needs it: a page reads a
            # few dozen of a season's ~10k duals, and unpacking all of them is the
            # cost of the first view.
            "lines": None, "_raw": d["lines"],
        })
    programs = {}
    try:
        from . import jhsaa_coaches as jc
        heads = jc.season_heads(world_id, gender)
        idents = jc.ident_names(gender)
        coach = {idents.get(ident, ident): h["name"]
                 for (y, ident), h in heads.items() if y == world_year}
    except Exception:                      # a save with no named staffs
        coach = {}
    for s in jh.load_schools(gender):
        programs[s.name] = {"name": s.name, "city": s.city, "county": s.county,
                            "area": s.area, "group": s.group, "district": s.district,
                            "private": bool(s.private), "coach": coach.get(s.name, "")}
    season = {"season_year": season_year, "world_year": world_year, "gender": gender,
              "source": "archive", "world_id": world_id, "programs": programs,
              "duals": duals, "grades": {}, "pid_grade": {}, "rosters": {},
              "history": None}
    with _cache_lock:
        for k in [k for k in _cache if k[:4] == key[:4]]:
            _cache.pop(k, None)
        _cache[key] = season
    return season


def load_export(path: str) -> dict:
    """The same season off a research-export zip (the demo and CLI path)."""
    zf = zipfile.ZipFile(path)

    def rows(name):
        if name not in zf.namelist():
            return []
        return list(csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8")))

    manifest = json.loads(zf.read("manifest.json"))
    gender = manifest["scope"]["gender"]
    programs, by_id = {}, {}
    for p in rows("programs.csv"):
        by_id[p["program_id"]] = p["name"]
        programs[p["name"]] = {"name": p["name"], "city": p["city"], "county": p["county"],
                               "area": p["area"], "group": p["championship_group"],
                               "district": p["district"], "private": p["private"] == "1",
                               "coach": ""}
    grade_by_pid, grades, rosters = {}, {}, defaultdict(list)
    for p in rows("players.csv"):
        g = int(p["grade"]) if p.get("grade", "").isdigit() else None
        grade_by_pid[p["player_id"]] = g
        sc = by_id.get(p["program_id"], "")
        grades[(sc, p["name"])] = g
        rosters[sc].append((p["player_id"], p["name"], g))
    for c in rows("jhsaa_coaches.csv"):
        nm = by_id.get(c.get("program_id", ""))
        if nm and (c.get("slot") or c.get("role") or "head") == "head" and c.get("name"):
            programs[nm]["coach"] = c["name"]
    # Names are not unique (two team-mates can share one), so the player_id rides
    # beside every name and is what records are joined on.
    blank = {"home": [], "away": [], "home_ids": [], "away_ids": []}
    players = defaultdict(lambda: {k: [] for k in blank})
    for lp in rows("line_players.csv"):
        players[lp["line_id"]][lp["side"]].append(lp["player_name"])
        players[lp["line_id"]][lp["side"] + "_ids"].append(lp.get("player_id") or "")
    lines = defaultdict(list)
    for ln in rows("lines.csv"):
        pl = players.get(ln["line_id"], blank)
        lines[ln["dual_id"]].append({"slot": ln["slot"], "score": ln["score"],
                                     "home_won": ln["home_won"] == "1",
                                     "home": pl["home"], "away": pl["away"],
                                     "home_ids": pl["home_ids"], "away_ids": pl["away_ids"]})
    duals = []
    for d in rows("duals.csv"):
        if (d.get("level") or "v") != "v" or d.get("squad"):
            continue
        home, away = by_id.get(d["home_program_id"], ""), by_id.get(d["away_program_id"], "")
        win = by_id.get(d.get("winner_program_id") or "")
        duals.append({"id": d["dual_id"], "date": _date(d["date"]), "phase": d["phase"],
                      "district": d["district"] == "1", "home": home, "away": away,
                      "hp": float(d["home_points"] or 0), "ap": float(d["away_points"] or 0),
                      "tied": not win, "winner": win or None,
                      "lines": lines.get(d["dual_id"], [])})
    year = int(manifest["scope"]["year"])
    history = defaultdict(list)
    for h in rows("jhsaa_program_history.csv"):
        nm = by_id.get(h["program_id"]) or h.get("program_name") or h["program_id"].split("|")[0]
        sy = int(h.get("season_year") or 0)
        if sy and sy < year:
            history[nm].append({"season_year": sy, "record": h.get("record", ""),
                                "district_record": h.get("district_record", ""),
                                "place": h.get("district_place") or "",
                                "state_finish": h.get("state_finish", ""),
                                "district_title": h.get("district_title") == "1",
                                "champion": h.get("state_champion") == "1"})
    for v in history.values():
        v.sort(key=lambda r: -r["season_year"])
    return {"season_year": year, "world_year": None, "gender": gender, "source": "export",
            "programs": programs, "duals": duals, "grades": grades,
            "pid_grade": grade_by_pid, "rosters": dict(rosters),
            "history": dict(history)}


# ----------------------------------------------------------- the calendar ----

def editions(season: dict, area: str | None = None) -> list[dict]:
    """The paper's run for one season: [{n, date, kind, label, since}] where an
    edition reports every dual dated in [since, date). `date` is the morning it
    lands on the doorstep. Given the paper's `area`, a postseason morning is only
    printed when one of its programs played the day before or the wire carries
    State or TOC results; a quiet day folds into the next edition."""
    dated = sorted({d["date"] for d in season["duals"] if d["date"]})
    if not dated:
        return []
    post = _postseason()
    post_days = sorted({d["date"] for d in season["duals"]
                        if d["date"] and d["phase"] in post})
    first, last = dated[0], dated[-1]
    road = post_days[0] if post_days else last + dt.timedelta(days=1)
    mornings = {first - dt.timedelta(days=1): "preseason"}
    day = first + dt.timedelta(days=1)
    while day < road:
        if day.weekday() in REGULAR_EDITION_DAYS:
            mornings[day] = "regular"
        day += dt.timedelta(days=1)
    mornings[road] = "road"                 # the morning the road to State opens
    local = ({p["name"] for p in season["programs"].values() if p.get("area") == area}
             if area else None)
    busy = None
    if local is not None:
        busy = {d["date"] for d in season["duals"] if d["date"] and d["phase"] in post
                and ({d["home"], d["away"]} & local or d["phase"] in WIRE_PHASES)}
    for p in post_days:
        if busy is None or p in busy:
            mornings.setdefault(p + dt.timedelta(days=1), "postseason")
    mornings[last + dt.timedelta(days=1)] = "closing"
    out, prev = [], None
    for n, (when, kind) in enumerate(sorted(mornings.items())):
        out.append({"n": n, "date": when, "kind": kind, "since": prev,
                    "label": _edition_label(when, kind)})
        prev = when
    return out


def _edition_label(when: dt.date, kind: str) -> str:
    day = f"{when.strftime('%A')}, {when.strftime('%B')} {when.day}"
    return {"preseason": f"Season preview · {day}",
            "closing": f"Season's end · {day}"}.get(kind, day)


# ------------------------------------------------------- folds over a date ----

def _rec(w, l, t=0) -> str:
    return f"{w}-{l}-{t}" if t else f"{w}-{l}"


def records_through(season: dict, before: dt.date) -> dict:
    """{school: {w, l, t, dw, dl, dt}} over every varsity dual dated before the
    morning `before` — the record a reader had in hand that day."""
    out = defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "dw": 0, "dl": 0, "dt": 0})
    for d in season["duals"]:
        if not d["date"] or d["date"] >= before:
            continue
        for side in (d["home"], d["away"]):
            r = out[side]
            if d["tied"]:
                r["t"] += 1
                if d["district"]:
                    r["dt"] += 1
            elif d["winner"] == side:
                r["w"] += 1
                if d["district"]:
                    r["dw"] += 1
            else:
                r["l"] += 1
                if d["district"]:
                    r["dl"] += 1
    return out


def league_tables(season: dict, schools: list[str], before: dt.date) -> list[dict]:
    """The league standings the paper prints for its area's leagues, through the
    morning `before`. A league is (class, name) — the same name in another class
    is a different league. Ordered by league win share, then overall record."""
    progs = season["programs"]
    recs = records_through(season, before)
    keys = sorted({(progs[s]["group"], progs[s]["district"]) for s in schools if s in progs},
                  key=lambda k: (k[0], k[1]))
    tables = []
    for group, district in keys:
        members = [p for p in progs.values()
                   if p["group"] == group and p["district"] == district]
        rows = []
        for p in members:
            r = recs.get(p["name"]) or {"w": 0, "l": 0, "t": 0, "dw": 0, "dl": 0, "dt": 0}
            dn = r["dw"] + r["dl"] + r["dt"]
            n = r["w"] + r["l"] + r["t"]
            rows.append({"school": p["name"], "league": _rec(r["dw"], r["dl"], r["dt"]),
                         "overall": _rec(r["w"], r["l"], r["t"]),
                         "local": p["name"] in schools,
                         "_k": (-((r["dw"] + r["dt"] / 2) / dn if dn else 0), -r["dw"],
                                r["dl"], -((r["w"] + r["t"] / 2) / n if n else 0),
                                p["name"])})
        rows.sort(key=lambda x: x["_k"])
        for x in rows:
            x.pop("_k")
        tables.append({"group": group, "district": district, "rows": rows})
    return tables


def _abbr(name: str) -> str:
    """The agate's school tag: initials for a multi-word name, else four letters."""
    words = [w for w in name.replace("-", " ").split() if w[:1].isalpha()]
    if len(words) > 1:
        return "".join(w[0] for w in words).upper()
    return name[:4]


#: The generic tail of a league name. What is left is the league's own name, the
#: form a paper uses on later references ("South Coast play", "the Desert Sky").
_LEAGUE_TAILS = ("Interscholastic League", "Athletic Association", "Athletic League",
                 "Athletic Conference", "League", "Association", "Alliance", "Conference",
                 "Assembly", "Circuit", "District", "Organization", "Province")


def league_short(name: str) -> str:
    for tail in _LEAGUE_TAILS:
        if name.endswith(" " + tail):
            return name[: -len(tail) - 1]
    return name


#: Initials that already mean something to a reader. AP warns against alphabet
#: soup; a league called the NIL on a sports page reads as name, image and likeness.
_TAKEN_INITIALS = {"AAA", "NIL", "FAA", "DSL", "NBA", "NFL", "NHL", "MLB", "CIA", "FBI",
                   "IRS", "ACT", "SAT", "GPA", "USA", "NRA", "DMV", "ESPN", "MLS"}


def league_initials(name: str) -> str | None:
    """MSL for Mid-Suburban League, DCL for Dual County League: the first letters
    of every word, hyphenated parts counted apart. None under three letters, which
    no paper prints (nobody calls the Kajaani League the KL)."""
    words = [w for w in re.split(r"[\s-]+", name) if w and w.lower() not in ("of", "the", "and")]
    ini = "".join(w[0].upper() for w in words)
    return ini if len(words) >= 3 and ini not in _TAKEN_INITIALS else None


def league_references(season: dict, leagues, local=()) -> list[dict]:
    """How the paper names each league. Initials when the name has them and no
    other league in the association shares them; otherwise the league's own name
    without its tail, unless that is also the start of a school, town, county or
    area name (the Juniper League stays the Juniper League next to Juniper Ridge
    and Juniper County). `local` is the coverage area's leagues: readers know
    those, so the paper uses the short form from the first mention, the way a
    Chicago paper writes "CSL North title" in a headline and never spells it out.
    A league from outside the area is spelled out the first time a story names it."""
    progs = season["programs"].values()
    every = {p["district"] for p in progs}
    places = set()
    for p in progs:
        for k in ("name", "city", "county", "area"):
            if p.get(k):
                places.add(p[k])
    taken: dict = {}
    for lg in every:
        ini = league_initials(lg)
        if ini:
            taken.setdefault(ini, set()).add(lg)
    local = set(local)
    out = []
    for lg in sorted(set(leagues)):
        ini, short = league_initials(lg), league_short(lg)
        clash = any(pl == short or pl.startswith(short + " ") for pl in places)
        if ini and len(taken.get(ini, ())) == 1:
            ref, also = ini, (None if clash else short)
        else:
            ref, also = (lg if clash else short), None
        out.append({"full": lg, "second_reference": ref, "also": also,
                    "local": lg in local})
    return out


def _slot_key(slot: str) -> tuple:
    """Singles before doubles, then by number: the order a results column prints."""
    return (0 if slot[:1] == "S" else 1, int(slot[1:]) if slot[1:].isdigit() else 0)


_GRADE_ABBR = {12: "Sr.", 11: "Jr.", 10: "So.", 9: "Fr.", 8: "8th", 7: "7th"}


def _pkey(ln: dict, side: str, i: int):
    """A line participant's identity: the player_id when the source carries one
    (the export does), else the name (the archive's box scores hold names only)."""
    ids = ln.get(side + "_ids") or []
    names = ln.get(side) or []
    return (ids[i] if i < len(ids) and ids[i] else names[i])


def _grade_of(season: dict, school: str, ln: dict, side: str, i: int):
    ids = ln.get(side + "_ids") or []
    if i < len(ids) and ids[i] and ids[i] in season.get("pid_grade", {}):
        return season["pid_grade"][ids[i]]
    return season.get("grades", {}).get((school, (ln.get(side) or [])[i]))


def _line_row(ln: dict, home: str, away: str, season: dict) -> dict:
    """One flight of a result, winner first, every player with a grade:
    {flight, win: [{name, grade, cls}], win_tag, lose: [...], lose_tag, score}."""
    def side(key, school):
        out = []
        for i, nm in enumerate(ln.get(key) or []):
            g = _grade_of(season, school, ln, key, i)
            out.append({"name": nm, "grade": g, "cls": _GRADE_ABBR.get(g, "")})
        return out or [{"name": "unknown", "grade": None, "cls": ""}]
    hw = bool(ln.get("home_won"))
    score = ln.get("score") or ""
    if not hw:
        score = _flip_score(score)
    h, a = side("home", home), side("away", away)
    return {"flight": _flight_name(ln.get("slot", "")),
            "win": h if hw else a, "win_tag": _abbr(home if hw else away),
            "lose": a if hw else h, "lose_tag": _abbr(away if hw else home),
            "score": score}


def _flip_score(score: str) -> str:
    """Write a set score from the winner's side (agate reads winner-first)."""
    out = []
    for part in score.split(","):
        part = part.strip()
        tb = ""
        if "(" in part:
            part, tb = part.split("(", 1)
            tb = "(" + tb
        if "-" in part:
            a, b = part.strip().split("-", 1)
            out.append(f"{b}-{a}{tb}")
        else:
            out.append(part + tb)
    return ", ".join(out)


def _pts(x) -> str:
    return str(int(x)) if float(x) == int(x) else f"{x:g}"


def _dual_row(d: dict, local: set, season: dict) -> dict:
    """One results-column entry, winner first."""
    if d["tied"]:
        a, b, pa, pb = d["home"], d["away"], d["hp"], d["ap"]
        head = f"{a} {_pts(pa)}, {b} {_pts(pb)} (tie)"
    else:
        win = d["winner"]
        lose = d["away"] if win == d["home"] else d["home"]
        pw, pl = (d["hp"], d["ap"]) if win == d["home"] else (d["ap"], d["hp"])
        head = f"{win} {_pts(pw)}, {lose} {_pts(pl)}"
    return {"id": d["id"], "date": d["date"], "phase": d["phase"],
            "label": phase_label(d["phase"], d["district"]), "head": head,
            "home": d["home"], "away": d["away"],
            "local": bool({d["home"], d["away"]} & local),
            "lines": [_line_row(ln, d["home"], d["away"], season)
                      for ln in sorted(_lines(d), key=lambda x: _slot_key(x.get("slot") or ""))]}


def territories(season: dict) -> list[dict]:
    """Every area a paper could cover, with its program count."""
    n = defaultdict(int)
    for p in season["programs"].values():
        if p.get("area"):
            n[p["area"]] += 1
    return [{"area": a, "programs": c} for a, c in sorted(n.items())]


def default_area(season: dict) -> str:
    """A circulation area a single desk could cover: the area nearest 35
    programs (a gazetteer area runs ~25-200)."""
    ts = territories(season)
    if not ts:
        return ""
    return min(ts, key=lambda t: (abs(t["programs"] - 35), t["area"]))["area"]


def masthead(area: str) -> str:
    return f"The {area} Courier" if area else "The Courier"


# ------------------------------------------------------------- the view ----

def edition_view(season: dict, area: str, n: int | None = None,
                 stories: dict | None = None) -> dict:
    """Everything one edition prints. `stories` is {edition date iso: payload}."""
    eds = editions(season, area)
    if not eds:
        return {"ready": False}
    n = 0 if n is None else max(0, min(int(n), len(eds) - 1))
    ed = eds[n]
    nxt = eds[n + 1]["date"] if n + 1 < len(eds) else None
    progs = season["programs"]
    local = sorted(p["name"] for p in progs.values() if p.get("area") == area)
    lset = set(local)
    since, until = ed["since"], ed["date"]
    _store_grades(season)        # grades for the results lists (one read, memoised)
    window = [d for d in season["duals"] if d["date"] and until > d["date"]
              and (since is None or d["date"] >= since)]
    results = [_dual_row(d, lset, season) for d in window if {d["home"], d["away"]} & lset]
    results.sort(key=lambda r: (r["date"], r["phase"] != "regular", r["head"]))
    by_day = defaultdict(list)
    for r in results:
        by_day[r["date"]].append(r)
    wire = [_dual_row(d, lset, season) for d in window if d["phase"] in WIRE_PHASES
            and not ({d["home"], d["away"]} & lset)]
    ahead = []
    if nxt:
        for d in season["duals"]:
            if d["date"] and until <= d["date"] < nxt and {d["home"], d["away"]} & lset:
                ahead.append({"date": d["date"], "label": phase_label(d["phase"], d["district"]),
                              "home": d["home"], "away": d["away"]})
        ahead.sort(key=lambda a: (a["date"], a["label"], a["away"]))
    recs = records_through(season, until)
    payload = (stories or {}).get(until.isoformat()) or {}
    written = payload.get("stories") or []
    lead = next((s for s in written if s.get("slot") == "lead"), None)
    rest = [s for s in written if s is not lead]
    return {
        "ready": True, "area": area, "masthead": masthead(area),
        "season_year": season["season_year"], "gender": season["gender"],
        "edition": ed, "n": n, "count": len(eds),
        "prev": eds[n - 1] if n > 0 else None, "next": eds[n + 1] if n + 1 < len(eds) else None,
        "editions": eds, "written": bool(written),
        "written_dates": sorted((stories or {}).keys()),
        "lead": lead, "stories": rest,
        "results": [{"date": day, "rows": rows} for day, rows in sorted(by_day.items())],
        "wire": wire, "ahead": ahead,
        "tables": league_tables(season, local, until) if ed["kind"] != "preseason" else [],
        "local": [{"school": s, "record": _rec(recs[s]["w"], recs[s]["l"], recs[s]["t"])
                   if s in recs else "0-0", "group": progs[s]["group"],
                   "district": progs[s]["district"], "city": progs[s]["city"]}
                  for s in local],
        "areas": territories(season),
    }


# --------------------------------------------------------- the packet ----

def _grade_word(g) -> str:
    return {9: "freshman", 10: "sophomore", 11: "junior", 12: "senior",
            8: "eighth-grader", 7: "seventh-grader"}.get(g, "")


def _store_grades(season: dict) -> None:
    """Archive mode: grades and rosters off the preseason store the season rung
    wrote (one indexed read per season, memoised on the cached season). Cheap
    enough for a page render; a season archived before the store has none."""
    if season["source"] != "archive" or season.get("_stored"):
        return
    season["_stored"] = True
    try:
        from . import jhsaa as jh
        from . import jhsaa_preseason as jp
        for school, st in jp.load(season["world_id"], season["world_year"],
                                  season["gender"]).items():
            if st.get("provisional"):
                continue
            nm = jh.current_name(school, season["gender"])
            rows = [(e["pid"], e["name"], e["grade"]) for e in st.get("ladder") or []]
            season["rosters"][nm] = rows
            for pid, name, g in rows:
                season["grades"][(nm, name)] = g
                season["pid_grade"][pid] = g
    except Exception:
        pass


def _ensure_grades(season: dict, schools: list[str]) -> None:
    """Fill grades and rosters for these programs in archive mode. The store is
    read first; a program it does not hold is built off the roster generator, so
    that part runs in the WRITER (a background thread or the CLI), never on a
    page render. Tracked per school: a second area gets its own programs."""
    if season["source"] != "archive":
        return
    _store_grades(season)
    done = season.setdefault("_graded", set())
    todo = [nm for nm in schools if nm not in done and nm not in season["rosters"]]
    done.update(schools)
    if not todo:
        return
    from . import jhsaa as jh
    from . import world as wd
    try:
        salt = wd.active_salt(wd.DEFAULT_SEED)
        by_name = {s.name: s for s in jh.load_schools(season["gender"])}
        for nm in todo:
            s = by_name.get(nm)
            if not s:
                continue
            rows = []
            for p in jh.build_roster(s, season["season_year"], salt):
                g = getattr(p, "grade", None) or getattr(p, "class_year", None)
                if isinstance(g, int):
                    season["grades"][(nm, p.name)] = g
                    season["pid_grade"][p.pid] = g
                    rows.append((p.pid, p.name, g))
            season["rosters"][nm] = rows
    except Exception:
        pass


_FLIGHT_WORD = {"S": "singles", "D": "doubles"}


def _flight_name(slot: str) -> str:
    return f"No. {slot[1:]} {_FLIGHT_WORD.get(slot[:1], '')}".strip() if slot else ""


def player_lines(season: dict, schools: set, before: dt.date | None = None) -> dict:
    """{(school, player key): {"name", "w", "l", "flights": {slot: n}}}, the key
    being the player_id where the source has one (never merge two same-named
    team-mates), over varsity duals
    dated before `before` (all of them when None) for the given schools."""
    out: dict = {}
    for d in season["duals"]:
        if not d["date"] or (before and d["date"] >= before):
            continue
        for side, school in (("home", d["home"]), ("away", d["away"])):
            if school not in schools:
                continue
            for ln in _lines(d):
                won = bool(ln.get("home_won")) == (side == "home")
                for i, nm in enumerate(ln.get(side) or []):
                    r = out.setdefault((school, _pkey(ln, side, i)),
                                       {"name": nm, "w": 0, "l": 0, "flights": {}})
                    r["w" if won else "l"] += 1
                    slot = ln.get("slot") or ""
                    r["flights"][slot] = r["flights"].get(slot, 0) + 1
    return out


def _player_note(rec: dict) -> str:
    top = sorted(rec["flights"].items(), key=lambda kv: -kv[1])[:2]
    where = " and ".join(_flight_name(s) for s, _ in top)
    return f"{rec['w']}-{rec['l']}, mostly {where}" if where else f"{rec['w']}-{rec['l']}"


def packet(season: dict, area: str, n: int, stories: dict | None = None,
           clips: int = 12, prior: dict | None = None) -> dict:
    """The ONLY thing the writer reads for edition `n`: the dated facts plus the
    paper's own earlier stories and its running ledger of invented detail. Nothing
    dated on or after the edition's morning is in it."""
    view = edition_view(season, area, n, stories)
    ed = view["edition"]
    until = ed["date"]
    progs = season["programs"]
    local = [r["school"] for r in view["local"]]
    _ensure_grades(season, local)
    grades = season["grades"]

    def who(school, ln, side):
        out = []
        for i, nm in enumerate(ln.get(side) or []):
            g = _grade_of(season, school, ln, side, i)
            out.append(f"{nm} ({_grade_word(g)})" if g else nm)
        return out

    results = []
    for d in season["duals"]:
        if not d["date"] or d["date"] >= until or (ed["since"] and d["date"] < ed["since"]):
            continue
        if not ({d["home"], d["away"]} & set(local)) and d["phase"] not in WIRE_PHASES:
            continue
        results.append({
            "date": d["date"].isoformat(), "event": phase_label(d["phase"], d["district"]),
            "home": d["home"], "away": d["away"],
            "score": f"{_pts(d['hp'])}-{_pts(d['ap'])}",
            "winner": d["winner"] or "tie", "local": bool({d["home"], d["away"]} & set(local)),
            "flights": [{"flight": ln.get("slot"), "score": ln.get("score"),
                         "won_by": d["home"] if ln.get("home_won") else d["away"],
                         d["home"]: who(d["home"], ln, "home"),
                         d["away"]: who(d["away"], ln, "away")}
                        for ln in _lines(d)]})
    recs = records_through(season, until)
    programs = []
    for s in local:
        p = progs[s]
        r = recs.get(s) or {"w": 0, "l": 0, "t": 0, "dw": 0, "dl": 0, "dt": 0}
        last = (_history(season).get(s) or [None])[0]
        programs.append({
            "school": s, "city": p["city"], "class": p["group"], "league": p["district"],
            "private": p["private"], "head_coach": p.get("coach") or "",
            "record_to_date": _rec(r["w"], r["l"], r["t"]),
            "league_record_to_date": _rec(r["dw"], r["dl"], r["dt"]),
            "last_season": ({k: last.get(k) for k in ("record", "district_record", "place",
                                                       "state_finish", "champion")}
                            if last else None)})
    earlier = sorted(k for k in (stories or {}) if k < until.isoformat())
    morgue, ledger = [], []
    for k in earlier:
        pay = stories[k]
        ledger.extend(pay.get("ledger") or [])
        for st in pay.get("stories") or []:
            morgue.append({"edition": k, "headline": st.get("headline"),
                           "byline": st.get("byline"), "body": st.get("body")})
    roster_lines, graduated = {}, {}
    if ed["kind"] == "preseason":
        # Returning players with what they did LAST season (the prior archive),
        # which is all a preseason writer can know about them.
        last = player_lines(prior, set(local)) if prior else {}
        rosters = season.get("rosters") or {}
        for s in local:
            roster = sorted(rosters.get(s) or [], key=lambda r: (-(r[2] or 0), r[1]))
            out, matched = [], set()
            for pid, nm, g in roster:
                # The same player, by id; a name is only tried when last season's
                # records carry no ids at all (an archive box score).
                key = (s, pid) if (s, pid) in last else (s, nm)
                rec = last.get(key)
                if rec is not None:
                    matched.add(key)
                out.append(f"{nm} ({_grade_word(g)}; last season {_player_note(rec)})" if rec
                           else f"{nm} ({_grade_word(g)})")
            roster_lines[s] = out
            # Last season's regulars who are no longer on the roster: the graduates.
            if roster:
                for (sc, k), rec in sorted(last.items(), key=lambda kv: kv[1]["name"]):
                    if sc == s and (sc, k) not in matched and (rec["w"] + rec["l"]) >= 10:
                        graduated.setdefault(sc, []).append(
                            f"{rec['name']} ({_player_note(rec)})")
    else:
        so_far = player_lines(season, set(local), until)
        pid_grade = season.get("pid_grade") or {}
        for s in local:
            rows = sorted(((k, r) for (sc, k), r in so_far.items() if sc == s),
                          key=lambda x: -(x[1]["w"] + x[1]["l"]))
            out = []
            for k, r in rows:
                g = pid_grade.get(k, grades.get((s, r["name"])))
                out.append(r["name"] + (f" ({_grade_word(g)})" if g else "")
                           + f": {_player_note(r)}")
            roster_lines[s] = out
    return {
        "paper": view["masthead"], "area": area, "sport": f"{season['gender']} tennis",
        "season": season["season_year"],
        "edition": {"number": n, "of": view["count"], "date": until.isoformat(),
                    "kind": ed["kind"], "label": ed["label"],
                    "covers_from": ed["since"].isoformat() if ed["since"] else None},
        "programs": programs,
        "players": roster_lines,
        "graduated_from_last_season": graduated,
        "results_since_last_edition": results,
        "league_standings_this_morning": view["tables"],
        # Full name on first reference in a story, then the second reference.
        "league_names": league_references(season, {
            progs[x]["district"] for x in set(local)
            | {r[k] for r in results for k in ("home", "away")} if x in progs},
            local={progs[x]["district"] for x in local if x in progs}),
        "before_the_next_edition": [{"date": a["date"].isoformat(), "event": a["label"],
                                     "home": a["home"], "away": a["away"]}
                                    for a in view["ahead"]],
        # The published regular-season schedule two weeks out. Postseason pairings
        # are left out: they depend on results nobody has yet.
        "regular_season_schedule_next_two_weeks": [
            {"date": d["date"].isoformat(), "event": phase_label(d["phase"], d["district"]),
             "home": d["home"], "away": d["away"]}
            for d in sorted(season["duals"], key=lambda d: (d["date"] or until, d["home"]))
            if d["date"] and until <= d["date"] < until + dt.timedelta(days=14)
            and d["phase"] not in _postseason() and {d["home"], d["away"]} & set(local)],
        "earlier_stories": morgue[-clips:],
        "ledger": ledger,
    }


# --------------------------------------------------------- the writer ----

WRITER_BRIEF = """\
You are the prep sports desk of {paper}, a local daily covering {sport} in the
{area} area of Jefferson, a fictional US state, in the {season} season. Write
edition {number} ({label}).

You only know what is in the packet: results since the last edition, records and
league standings as of this morning, the published schedule, and the paper's own
earlier stories. Nothing has happened after this morning. Never hint at how the
season ends. Use the head coaches named in the packet; keep every invented person
and fact consistent with the ledger, and add new ones to it. Follow up on what the
paper already wrote instead of reintroducing teams. The preseason edition is a
county-by-county outlook.

This is a local paper. Its readers live here, went to these schools and know
what a league title or a district tournament means. Write like a reporter who
has covered these teams for years: call the area's leagues what the readers call
them, the second reference in league_names, from the first mention and in
headlines ("Juniper Ridge (3-1, 1-0 Kajaani)", "DCL champion California
Canyons"). Never explain a local school, league, rivalry or event to the reader.
Spell out a league from outside the area the first time a story names it.

The house style is the 1980s-1990s prep sports voice in docs/press/VOICE.md.
It controls period vocabulary, reporting forms, area and local coverage, staff
bylines, section mix and columnist persona. The tennis guide supplies accurate
sport vocabulary and evidence rules. The older preps style guide corrects flat,
repetitive retrospective prose, but its statewide consequence gate, prohibition
on ordinary period sports verbs, ban on all punning headlines, and demand for
a quote or scene in every piece do not apply to agate, briefs, local notebooks
or signed columns. AP sports and humanizer rules apply when they do not erase
the period register.

Publish a newspaper page, with an uneven mix of news, short reports, a notebook
or briefs, not four identical feature articles. The game's results, standings
and fixtures already print in agate; do not turn every score into paragraphs.
A local school can merit a brief even if it loses. Statewide results belong in
the paper only when they matter to local readers. A column is OPTIONAL: write
one only when the writer has a factual basis for a real opinion. The columnist
has a stable byline, longstanding interests, previously expressed positions
and a distinctive way of noticing things; remember these in the ledger. Never
make the columnist speak as the game developer.

Give other recurring bylines stable habits and beats too, using earlier stories
and the ledger. Invent plausible quotes, scenes and off-court context, and
record new durable details in the ledger. Do not create a new injury, transfer,
family relationship already contradicted by the game, match result or award.
You may interpret why an actual event happened, provided you maintain canon.
Never fabricate an exact play-by-play point from an aggregate match score.

Plan the edition before drafting; each substantial article needs a distinct
angle and story form, but a results brief does not need a dramatic opening.

Return ONLY a JSON object:
{{"stories": [{{"slot": "lead" | "story" | "brief" | "notebook" | "column",
               "headline": "...", "byline": "By ... | Courier staff writer",
               "body": ["paragraph", "..."], "about": ["School", "..."]}}],
  "ledger": ["one line per invented person or fact"]}}
"""

#: House voice leads. Earlier guides contribute tennis facts, not rival house voices.
DESK_DOCS = ("docs/press/VOICE.md", "docs/JHSAA_HIGH_SCHOOL_TENNIS_REPORTING_GUIDE.md",
             "docs/PREPS-STYLE-GUIDE.md", "docs/paper/desk/AP-SPORTS.md",
             "docs/paper/desk/HUMANIZER.md")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def desk_rules() -> str:
    parts = []
    for rel in DESK_DOCS:
        path = os.path.join(_repo_root(), rel)
        if rel == "docs/press/VOICE.md" and not os.path.isfile(path):
            raise FileNotFoundError("JHSAA paper requires docs/press/VOICE.md")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                parts.append(f"=== {rel} ===\n{fh.read()}")
    return "\n\n".join(parts)


def writer_prompt(pk: dict) -> tuple[str, str]:
    e = pk["edition"]
    system = WRITER_BRIEF.format(paper=pk["paper"], sport=pk["sport"], area=pk["area"],
                                 season=pk["season"], number=e["number"], label=e["label"])
    return system + "\n\n" + desk_rules(), json.dumps(pk, default=str, ensure_ascii=False)


# --------------------------------------------------------- the copy desk ----
#
# Deterministic checks run on every edition before it is saved. They are the
# mechanical half of AP-SPORTS.md, the preps style guide's banned phrases, and the
# repetition rule; the writer revises against whatever they find.

import re as _re

_MONTH_FULL = {"January": "Jan.", "February": "Feb.", "August": "Aug.",
               "September": "Sept.", "October": "Oct.", "November": "Nov.",
               "December": "Dec."}
_DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_SMALL = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
          "6": "six", "7": "seven", "8": "eight", "9": "nine"}
BANNED = ("testament to", "beacon of hope", "proved their mettle", "stark contrast",
          "navigated the waters", "defied the odds", "from the get go", "passed the test",
          "gutsy", "avenged", "when all was said and done", "the interesting part is",
          "that is the story", "the distinction is", "the number that matters",
          "the season was", "the year belonged to", "the lesson was",
          "the story of the season", "in the end", "set the tone", "statement win",
          "lineup card", "courts won")
#: Words that may carry one piece of an edition; past this count across the
#: edition the desk asks for a different angle.
WATCH = {"lineup": 2, "no. 1 singles": 3, "graduated": 2, "graduation": 1,
         "returns": 2, "is back": 2, "are back": 2, "last season": 4, "a year ago": 2}


def _league_findings(tag: str, body: list[str], leagues: list[dict]) -> list[str]:
    """A league is never spelled out twice in a story and never carries its
    initials in parentheses. The area's own leagues go by their short form from
    the first mention; a league from outside the area is spelled out before its
    initials appear. Headlines and quotes are exempt."""
    text = " ".join(_re.sub(r'"[^"]*"', '""', p) for p in body)
    out = []
    for lg in leagues or []:
        full, second = lg["full"], lg["second_reference"]
        hits = [m.start() for m in _re.finditer(r"\b" + _re.escape(full) + r"\b", text)]
        if len(hits) > 1:
            out.append(f"{tag} league: {full!r} spelled out {len(hits)} times; "
                       f"after the first, write {second!r} or 'the league'")
        for ini in {second, lg.get("also")} - {None}:
            if _re.search(_re.escape(full) + r"\s*\(" + _re.escape(ini) + r"\)", text):
                out.append(f"{tag} AP: no ({ini}) after {full!r}; just use {ini} later")
        ini = second if second.isupper() else None
        if ini and not lg.get("local"):
            m = _re.search(r"\b" + _re.escape(ini) + r"\b", text)
            if m and (not hits or m.start() < hits[0]):
                out.append(f"{tag} league: {ini} before {full!r} is spelled out")
    return out


def copy_desk(payload: dict, names: set | None = None,
              leagues: list[dict] | None = None) -> list[str]:
    """Findings for one edition; an empty list means it passes the mechanical desk.
    `leagues` is the packet's league_names."""
    out: list[str] = []
    stories = payload.get("stories") or []
    whole = []
    for st in stories:
        head = (st.get("headline") or "").strip()
        tag = f"[{head[:48]}]"
        if head.endswith("."):
            out.append(f"{tag} headline ends with a period")
        out.extend(_league_findings(tag, list(st.get("body") or []), leagues))
        for raw in [head] + list(st.get("body") or []):
            low = raw.lower()
            whole.append(low)
            # AP and banned-phrase checks read the reporter's words, not a quote's.
            para = _re.sub(r'"[^"]*"', '""', raw) if raw is not head else raw
            column_tag = (st.get("slot") == "column" and raw is not head
                          and _re.match(r"^[A-Z][A-Z ]{3,32}\s*[—–-]\s+", para))
            if ("\u2014" in para or "\u2013" in para or " -- " in para or " - " in para) and not column_tag:
                out.append(f"{tag} a dash in prose: {para[:60]!r}")
            for b in BANNED:
                if _re.search(r"\b" + _re.escape(b) + r"\b", para.lower()):
                    out.append(f"{tag} banned phrase {b!r}")
            for full, short in _MONTH_FULL.items():
                if _re.search(full + r" \d", para):
                    out.append(f"{tag} AP: {full} with a date is {short}")
            if _re.search(r"\bon (" + _DAYS + r")\b", para):
                out.append(f"{tag} AP: no 'on' before a day ({para[:50]!r})")
            if _re.search(r"[A-Za-z,] Coach [A-Z]", para):
                out.append(f"{tag} AP: coach is lowercase before a name")
            if "!" in para:
                out.append(f"{tag} AP: no exclamation points")
            if raw is not head:
                for m in _re.finditer(r"(?<![\w.(-])([1-9])(?![\w.)-])", para):
                    before = para[max(0, m.start() - 8):m.start()]
                    if "No." in before or _re.search(
                            r"(Jan|Feb|Aug|Sept|Oct|Nov|Dec)\. $|(March|April|May|June|July) $",
                            before):
                        continue
                    out.append(f"{tag} AP: spell out {m.group(1)} ({_SMALL[m.group(1)]})")
    text = "\n".join(whole)
    for phrase, cap in WATCH.items():
        n = len(_re.findall(r"\b" + _re.escape(phrase) + r"\b", text))
        if n > cap:
            out.append(f"repetition: {phrase!r} appears {n} times in the edition (keep it to {cap})")
    # The same opening words on two pieces reads as one template run twice.
    openers = {}
    for st in stories:
        body = st.get("body") or [""]
        first = " ".join(body[0].split()[:3]).lower()
        if first:
            openers.setdefault(first, []).append(st.get("headline", "")[:40])
    for first, heads in openers.items():
        if len(heads) > 1:
            out.append(f"repetition: {len(heads)} pieces open with {first!r}")
    # Content words, excluding the packet's names, repeated across the edition.
    skip = {w.lower() for n in (names or ()) for w in n.split()}
    words = _re.findall(r"[a-z]{6,}", text)
    common = {"singles", "doubles", "season", "league", "senior", "seniors", "junior",
              "juniors", "freshman", "sophomore", "against", "second", "points", "matches",
              "against", "before", "school", "schools", "played", "thursday", "tuesday",
              "wednesday", "friday", "saturday", "monday", "sunday", "courier"}
    counts = {}
    for w in words:
        if w not in skip and w not in common:
            counts[w] = counts.get(w, 0) + 1
    for w, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n >= 6:
            out.append(f"repetition: {w!r} appears {n} times in the edition")
    return out


def _names(pk: dict) -> set:
    names = {p["school"] for p in pk.get("programs") or []}
    for rows in (pk.get("players") or {}).values():
        for r in rows:
            names.add(r.split(" (")[0].split(":")[0])
    for r in pk.get("results_since_last_edition") or []:
        names.update((r["home"], r["away"]))
    return names


REVISE = """\
The copy desk returned these findings on your edition. Revise the edition to
clear every one, keeping every fact as it is. Return the whole edition in the same
JSON shape.

Findings:
{findings}

Edition:
{edition}
"""


def _parse_payload(text: str) -> dict:
    """The edition JSON out of a model reply, whatever text surrounds it."""
    s, e = text.find("{"), text.rfind("}")
    data = json.loads(text[s:e + 1])
    if not isinstance(data.get("stories"), list):
        raise ValueError("writer returned no stories")
    return {"stories": data["stories"], "ledger": data.get("ledger") or []}


def _call(system: str, user: str, model: str | None) -> str:
    import urllib.request
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    body = json.dumps({"model": model or os.environ.get("JHSAA_PAPER_MODEL", "claude-opus-5-5"),
                       "max_tokens": 12000, "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read())
    return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


def write_with_api(pk: dict, model: str | None = None, rounds: int = 2) -> dict:
    """Write one edition through the Anthropic Messages API, then put it through
    the copy desk and revise until it passes or `rounds` revisions are spent.
    Needs ANTHROPIC_API_KEY; the model is JHSAA_PAPER_MODEL or claude-opus-5-5.
    Whatever the desk still finds is stored with the edition under "desk"."""
    system, user = writer_prompt(pk)
    payload = _parse_payload(_call(system, user, model))
    names, leagues = _names(pk), pk.get("league_names")
    for _ in range(rounds):
        findings = copy_desk(payload, names, leagues)
        if not findings:
            break
        payload = _parse_payload(_call(system, REVISE.format(
            findings="\n".join(f"- {f}" for f in findings),
            edition=json.dumps(payload, ensure_ascii=False)), model))
    payload["desk"] = copy_desk(payload, names, leagues)
    return payload


def can_write_in_app() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


# ---------------------------------------------------------- the morgue ----

_SCHEMA = """CREATE TABLE IF NOT EXISTS world_jhsaa_paper (
  world_id INTEGER, year INTEGER, gender TEXT, area TEXT, edition TEXT,
  data TEXT, written_at TEXT,
  PRIMARY KEY (world_id, year, gender, area, edition))"""


def _conn():
    from . import world as wd
    conn = wd._db()
    conn.execute(_SCHEMA)
    return conn


def load_stories(world_id: int, year: int, gender: str, area: str) -> dict:
    conn = _conn()
    try:
        rows = conn.execute("SELECT edition, data FROM world_jhsaa_paper WHERE world_id=?"
                            " AND year=? AND gender=? AND area=?",
                            (world_id, year, gender, area)).fetchall()
    finally:
        conn.close()
    return {r["edition"]: json.loads(r["data"]) for r in rows}


def save_edition(world_id: int, year: int, gender: str, area: str, edition: str,
                 payload: dict) -> None:
    conn = _conn()
    try:
        conn.execute("INSERT OR REPLACE INTO world_jhsaa_paper VALUES (?,?,?,?,?,?,?)",
                     (world_id, year, gender, area, edition, json.dumps(payload),
                      dt.datetime.now(dt.timezone.utc).isoformat()))
        conn.commit()
    finally:
        conn.close()


def load_stories_dir(path: str) -> dict:
    """Stories for the export/demo path: one `<edition date>.json` per edition."""
    out = {}
    if path and os.path.isdir(path):
        for f in sorted(os.listdir(path)):
            if f.endswith(".json"):
                with open(os.path.join(path, f), encoding="utf-8") as fh:
                    out[f[:-5]] = json.load(fh)
    return out


# ------------------------------------------------- the background writer ----
#
# One gthread worker serves the whole app (CLAUDE.md), so an edition is never
# written on a request thread: a POST starts this thread and returns.

_jobs: dict = {}
_jobs_lock = threading.Lock()


def job_status(world_id: int, year: int, gender: str, area: str) -> dict | None:
    return _jobs.get((world_id, year, gender, area))


def start_writing(world_id: int, year: int, gender: str, area: str, through: int) -> bool:
    """Write every unwritten edition up to and including `through`, in order (each
    edition reads the ones before it). False if a run is already going."""
    key = (world_id, year, gender, area)
    with _jobs_lock:
        if (_jobs.get(key) or {}).get("running"):
            return False
        _jobs[key] = {"running": True, "done": 0, "error": "", "through": through}

    def run():
        try:
            season = load_archive(world_id, year, gender)
            prior = load_archive(world_id, year - 1, gender)
            eds = editions(season, area)
            for ed in eds[:through + 1]:
                stories = load_stories(world_id, year, gender, area)
                if ed["date"].isoformat() in stories:
                    continue
                pk = packet(season, area, ed["n"], stories, prior=prior)
                save_edition(world_id, year, gender, area, ed["date"].isoformat(),
                             write_with_api(pk))
                _jobs[key]["done"] += 1
        except Exception as exc:          # surfaced on the page, never swallowed
            _jobs[key]["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            _jobs[key]["running"] = False

    threading.Thread(target=run, daemon=True, name="jhsaa-paper").start()
    return True


# ------------------------------------------------------------ the preview ----

def render_preview(season: dict, area: str, stories: dict, only_written: bool = True) -> str:
    """A standalone HTML page of the paper's editions (the written ones by default),
    built from the same edition partial the in-app page uses."""
    import jinja2
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "templates")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(here), autoescape=True)
    part = env.get_template("_jhsaa_paper_edition.html")
    eds = editions(season, area)
    keep = [e for e in eds if not only_written or e["date"].isoformat() in stories]
    shown = {e["n"] for e in keep}
    href = (lambda k: f"#ed-{k}" if k in shown else None)
    body = []
    for e in keep:
        v = edition_view(season, area, e["n"], stories)
        body.append(part.render(view=v, school_href=lambda n: None, edition_href=href,
                                write_box=False))
    title = f"{masthead(area)} · {season['gender']} tennis {season['season_year']}"
    return ("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{title}</title><style>body{{margin:0;padding:24px;background:#fff;"
            "font-family:system-ui,sans-serif}} .pp-paper{margin-bottom:80px}"
            "</style></head><body>" + "".join(body) + "</body></html>")

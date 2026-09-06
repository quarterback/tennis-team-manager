"""The JHSAA front page's STORY DESK — deterministic detectors over one archived
season (owner spec 2026-09, "newspaper meets thepudding.cool").

The front page (`/jhsaa`) is an editorial front door, not a dashboard: a strip of
facts, ONE lead story, a short feed of stories, a players desk, a programs desk,
one chart, a record-book strip. Everything here is a fold over the archive —
counts, ranks, seeds, records — through headline TEMPLATES. There is no prose
generation and no model anywhere in it.

‼️ THE HEADLINE REGISTER (owner rule 2026-09: "no AI slop microcopy anywhere").
A headline leads with a NUMBER or a NAME, carries no adjective and no verb of
opinion, and is one line. "23 of 24 champions were top-4 seeds" — never "The
titles were chalk." A dek is one more fact line in the same register. If a
template needs a word to sound better, the word is wrong.

‼️ DETECTORS ARE PURE and take the loaded season (`compile_desk`), so a test
hand-builds an archive and asserts the stories; `load_season` is the only I/O and
`front_page` the only cache. Every story carries `salience` — the feed is the top
of that order — and a `link` (endpoint + args) into the page that owns the detail.
"""
from __future__ import annotations

import json
from typing import Any

from . import jhsaa as jh

#: Story kinds, for tests and templates. A kind is the archive's identity for a
#: story shape, the way a phase is for an event.
KINDS = ("cinderella", "chalk", "nailbiter", "freshman_champ", "undefeated",
         "missed_state", "disagreement", "one_flight", "sweep", "riser")

#: Only a genuine class-rank rise is a story; a two-place wobble is noise.
RISER_MIN = 8
#: One-flight duals: a record is a story only past this many played.
ONE_FLIGHT_MIN = 8
#: An undefeated season needs a season's worth of duals behind it.
UNDEFEATED_MIN_WINS = 14
#: Seed-gap bands for the Data Desk chart (favourite's win rate by gap).
GAP_BANDS = ((1, 2), (3, 5), (6, 10), (11, 20), (21, 99))

GENDER_LABEL = {"girls": "Girls", "boys": "Boys"}


# ---------------------------------------------------------------- loading ----

def _stage_dict(arc: dict, g: str) -> dict:
    """The per-group stage draws under the singular keys `jhsaa_postseason_result`
    reads — the archive stores them plural (`sectionals`, `wards`, `brackets`)."""
    def get(k):
        return (arc.get(k) or {}).get(g)
    return {"sectional": get("sectionals"), "ward": get("wards"),
            "prestate": get("prestate"), "super_regional": get("super_regional"),
            "semi_state": get("semi_state"), "divisional": get("divisional"),
            "semi_conference": get("semi_conference"), "conference": get("conference"),
            "special_challenger": get("special_challenger"),
            "state_special": get("state_special"), "state": get("brackets"),
            "wildcards": get("wildcards"),
            "district_qualifiers": get("district_qualifiers")}


def _one_flight_records(conn, world_id: int, year: int, gender: str) -> dict:
    """{school: (won, lost)} in one-flight duals — varsity only (the `level` rule),
    every phase. Two rows per dual, one a side, so a per-school GROUP BY is exact."""
    rows = conn.execute(
        "SELECT school, SUM(CASE WHEN won THEN 1 ELSE 0 END) AS w,"
        " SUM(CASE WHEN won THEN 0 ELSE 1 END) AS l"
        " FROM world_jhsaa_dual WHERE world_id=? AND year=? AND gender=?"
        " AND COALESCE(level,'v')='v' AND abs(pf-pa)=1 GROUP BY school",
        (world_id, year, gender)).fetchall()
    names = jh.former_names()
    out: dict = {}
    for r in rows:
        s = names.get(r["school"], r["school"])
        w, l = out.get(s, (0, 0))
        out[s] = (w + int(r["w"] or 0), l + int(r["l"] or 0))
    return out


def _top_flight_champions(conn, world_id: int, year: int, gender: str) -> dict:
    """{group: {flight: champion entry}} for S1 and D1 only — the json_extract idiom,
    so the ~30 KB draws stay inside SQLite."""
    from . import world as wd
    rows = conn.execute(
        "SELECT grp, flight,"
        " json_extract(data, '$.entries[' || json_extract(data, '$.champion') || ']') AS champ"
        " FROM world_jhsaa_individual WHERE world_id=? AND year=? AND gender=?"
        " AND flight IN ('S1','D1') AND json_extract(data, '$.champion') IS NOT NULL",
        (world_id, year, gender)).fetchall()
    out: dict = {}
    for r in rows:
        if not r["champ"]:
            continue
        out.setdefault(r["grp"], {})[r["flight"]] = wd._relabel(json.loads(r["champ"]))
    return out


def load_season(world_id: int, year: int) -> dict | None:
    """Everything the desk reads for one world-year, both genders: the two archive
    blobs, the previous season's (for risers), one-flight records, the top-flight
    individual champions, and the record-book heads. None if nothing is archived."""
    from . import world as wd
    arcs, prev = {}, {}
    for g in ("girls", "boys"):
        arc = wd.get_jhsaa(world_id, year, g)
        if arc:
            arcs[g] = arc
            years = wd.jhsaa_years(world_id, g)
            older = [y for y in years if y < year]
            prev[g] = wd.get_jhsaa(world_id, older[0], g) if older else None
    if not arcs:
        return None
    conn = wd._db()
    try:
        one = {g: _one_flight_records(conn, world_id, year, g) for g in arcs}
        indiv = {g: _top_flight_champions(conn, world_id, year, g) for g in arcs}
    finally:
        conn.close()
    records = {}
    for g in arcs:
        try:
            cw = wd.jhsaa_career_wins(world_id, g, limit=3)
            records[g] = {"top": (cw.get("players") or {}).get("top") or [],
                          "titles": wd.jhsaa_individual_title_repeats(world_id, g)[:3]}
        except Exception:                       # a record board must never sink the page
            records[g] = {"top": [], "titles": []}
    any_arc = next(iter(arcs.values()))
    return {"year": year, "season_year": any_arc.get("season_year"),
            "arcs": arcs, "prev": prev, "one_flight": one, "indiv": indiv,
            "records": records}


# ---------------------------------------------------------- season folds ----

def _seeds(br: dict) -> dict:
    return {s: i + 1 for i, s in enumerate((br or {}).get("field") or ())}


def _ranking(arc: dict, g: str) -> list[dict]:
    from . import world as wd
    return wd.jhsaa_group_ranking(arc, g)


def _state_duals(arc: dict) -> list[dict]:
    """Every State-bracket dual of a season as {group, round, alive, home, away,
    home_seed, away_seed, home_points, away_points, winner, fav_won, gap, margin}."""
    from . import world as wd
    out = []
    for g, br in (arc.get("brackets") or {}).items():
        if not br:
            continue
        seeds = _seeds(br)
        for rd in wd.jhsaa_state_rounds(br):
            for gm in rd["games"]:
                h, a = gm.get("home"), gm.get("away")
                hs, as_ = seeds.get(h, 0), seeds.get(a, 0)
                if not (h and a and hs and as_):
                    continue
                w = gm.get("winner")
                hp, ap = gm.get("home_points") or 0, gm.get("away_points") or 0
                fav, dog = (h, a) if hs < as_ else (a, h)
                out.append({"group": g, "round": rd["name"], "alive": rd["alive"],
                            "home": h, "away": a, "home_seed": hs, "away_seed": as_,
                            "home_points": hp, "away_points": ap, "winner": w,
                            "loser": a if w == h else h,
                            "fav": fav, "dog": dog, "fav_won": w == fav,
                            "gap": abs(hs - as_), "margin": abs(hp - ap),
                            "win_points": max(hp, ap), "lose_points": min(hp, ap)})
    return out


def _champ_seed(arc: dict, g: str) -> int:
    br = (arc.get("brackets") or {}).get(g) or {}
    return _seeds(br).get(br.get("champion"), 0)


def _link_school(school: str, gender: str) -> dict:
    return {"ep": "jhsaa_school", "args": {"school": school, "g": gender}}


def _link_bracket(group: str, gender: str) -> dict:
    return {"ep": "jhsaa_bracket", "args": {"group": group, "g": gender}}


def _story(kind: str, gender: str, salience: float, headline: str, dek: str,
           stat: str, stat_label: str, link: dict, group: str = "",
           desk: str = "") -> dict:
    return {"kind": kind, "gender": gender, "group": group, "salience": float(salience),
            "headline": headline, "dek": dek, "stat": stat, "stat_label": stat_label,
            "link": link, "desk": desk}


# ------------------------------------------------------------- detectors ----

def d_cinderella(data: dict) -> list[dict]:
    """The lowest seed to reach a State final or semifinal — one story a gender."""
    out = []
    for g, arc in data["arcs"].items():
        best = None
        for d in _state_duals(arc):
            if d["alive"] > 4:
                continue
            for side, seed in ((d["home"], d["home_seed"]), (d["away"], d["away_seed"])):
                if seed <= 4:               # a top-4 seed in the semis is the draw working
                    continue
                won_it = d["winner"] == side
                place = ("champion" if (d["alive"] <= 2 and won_it) else
                         "final" if d["alive"] <= 2 else
                         "final" if won_it else "semifinal")
                rank = {"champion": 3, "final": 2, "semifinal": 1}[place]
                # The LAST dual of the run tells the story (a semifinal win and a
                # final loss both mean "reached the final" — the dek reads the final).
                key = (seed * 3 + rank * 12, -d["alive"])
                if best is None or key > best[0]:
                    best = (key, side, seed, place, d)
        if not best:
            continue
        _, school, seed, place, d = best
        grp = d["group"]
        if place == "champion":
            head = f"No. {seed} seed {school} won the {grp} title"
        elif place == "final":
            head = f"No. {seed} seed {school} reached the {grp} final"
        else:
            head = f"No. {seed} seed {school} reached the {grp} semifinals"
        opp = d["loser"] if d["winner"] == school else d["winner"]
        verb = "def." if d["winner"] == school else "lost to"
        dek = f"{GENDER_LABEL[g]} · {verb} {opp} {d['win_points']}–{d['lose_points']}"
        out.append(_story("cinderella", g, best[0][0], head, dek, f"No. {seed}",
                          "seed", _link_bracket(grp, g), grp, "championship"))
    return out


def d_chalk(data: dict) -> list[dict]:
    """How many champions were top-4 seeds, against how often lower seeds won a
    State dual — the two numbers together are the story."""
    out = []
    for g, arc in data["arcs"].items():
        seeds = [_champ_seed(arc, gp) for gp in jh.GROUPS]
        seeds = [s for s in seeds if s]
        duals = _state_duals(arc)
        if not seeds or not duals:
            continue
        top4 = sum(1 for s in seeds if s <= 4)
        dogs = sum(1 for d in duals if not d["fav_won"])
        pct = round(100 * dogs / len(duals))
        head = f"{top4} of {len(seeds)} {GENDER_LABEL[g].lower()}' champions were top-4 seeds"
        dek = f"Lower seeds won {pct}% of {len(duals)} State duals"
        # Both extremes are the story: a chalk sweep, or a field full of upsets.
        sal = 40 + abs(top4 / len(seeds) - 0.5) * 60 + abs(pct - 25)
        out.append(_story("chalk", g, sal, head, dek, f"{top4}/{len(seeds)}",
                          "top-4 seed champions",
                          {"ep": "jhsaa_champions", "args": {"g": g}}, "", "championship"))
    return out


def d_nailbiter(data: dict) -> list[dict]:
    """The closest late dual — a final or semifinal decided on the last flight."""
    out = []
    for g, arc in data["arcs"].items():
        late = [d for d in _state_duals(arc) if d["alive"] <= 4 and d["margin"] == 1]
        if not late:
            continue
        late.sort(key=lambda d: (d["alive"], -d["gap"]))
        d = late[0]
        rd = "final" if d["alive"] <= 2 else "semifinal"
        head = f"{d['winner']} {d['win_points']}–{d['lose_points']} {d['loser']} in the {d['group']} {rd}"
        n_finals = sum(1 for x in late if x["alive"] <= 2)
        dek = f"{GENDER_LABEL[g]} · {n_finals} of {len([x for x in _state_duals(arc) if x['alive'] <= 2])} finals went to the last flight"
        out.append(_story("nailbiter", g, 55 + (12 if d["alive"] <= 2 else 0) + d["gap"],
                          head, dek, f"{d['win_points']}–{d['lose_points']}", rd,
                          _link_bracket(d["group"], g), d["group"], "championship"))
    return out


def d_freshman_champ(data: dict) -> list[dict]:
    """A ninth-grader who won No. 1 Singles or No. 1 Doubles."""
    out = []
    for g, groups in data["indiv"].items():
        for grp, flights in groups.items():
            for fl, entry in flights.items():
                players = entry.get("players") or []
                if not players or any((p.get("grade") or 12) != 9 for p in players):
                    continue
                name = " / ".join(p.get("name", "") for p in players)
                from .jhsaa_individuals import FLIGHT_NAMES
                fname = FLIGHT_NAMES.get(fl, fl)
                head = f"{name} won {grp} {fname} as a freshman" if fl == "S1" else \
                    f"{name} won {grp} {fname} as freshmen"
                dek = f"{GENDER_LABEL[g]} · {entry.get('school', '')}"
                pid = players[0].get("pid")
                link = {"ep": "jhsaa_player", "args": {"school": entry.get("school", ""),
                                                        "pid": pid, "g": g}} if pid else \
                    {"ep": "jhsaa_individuals", "args": {"group": grp, "g": g, "flight": fl}}
                out.append(_story("freshman_champ", g,
                                  70 + (15 if grp in jh.WIDE_GROUPS else 0) + (5 if fl == "S1" else 0),
                                  head, dek, "9", "grade", link, grp, "players"))
    return out


def d_undefeated(data: dict) -> list[dict]:
    """A season without a loss, postseason included."""
    from . import world as wd
    out = []
    for g, arc in data["arcs"].items():
        for grp in jh.GROUPS:
            br = (arc.get("brackets") or {}).get(grp) or {}
            for r in _ranking(arc, grp):
                if r.get("losses", 1) == 0 and r.get("wins", 0) >= UNDEFEATED_MIN_WINS:
                    st = wd.jhsaa_state_result(br, r["school"])
                    fin = st["finish"] or "did not reach State"
                    head = f"{r['school']} went {r['record']}"
                    dek = f"{GENDER_LABEL[g]} {grp} · {fin}"
                    out.append(_story("undefeated", g, 60 + r["wins"] + (20 if st["champion"] else 0),
                                      head, dek, r["record"], "record",
                                      _link_school(r["school"], g), grp, "programs"))
    return out


def d_missed_state(data: dict) -> list[dict]:
    """The best-ranked program that did not reach State — one a gender."""
    from . import world as wd
    out = []
    for g, arc in data["arcs"].items():
        best = None
        for grp in jh.GROUPS:
            field = set(((arc.get("brackets") or {}).get(grp) or {}).get("field") or ())
            for r in _ranking(arc, grp):
                if r["school"] in field:
                    continue
                if best is None or r["rank"] < best[0]["rank"]:
                    best = (r, grp)
                break                       # the first non-qualifier is the best one
        if not best or best[0]["rank"] > 12:
            continue
        r, grp = best
        ps = wd.jhsaa_postseason_result(_stage_dict(arc, grp), r["school"])
        where = ps.get("finish") or "no postseason"
        head = f"No. {r['rank']} {r['school']} missed State"
        dek = f"{GENDER_LABEL[g]} {grp} · {r['record']} · out at {where}"
        out.append(_story("missed_state", g, 90 - r["rank"] * 6, head, dek,
                          f"No. {r['rank']}", "TOSS rank",
                          {"ep": "jhsaa_rankings", "args": {"group": grp, "g": g}},
                          grp, "rankings"))
    return out


def d_disagreement(data: dict) -> list[dict]:
    """The team the nine computer systems disagree about most."""
    out = []
    for g, arc in data["arcs"].items():
        best = None
        for grp, rt in (arc.get("ratings") or {}).items():
            for school, t in ((rt or {}).get("teams") or {}).items():
                ranks = [v for v in (t.get("ranks") or {}).values() if v]
                if len(ranks) < 5:
                    continue
                sig = float(t.get("sigma") or 0)
                if best is None or sig > best[0]:
                    best = (sig, school, grp, min(ranks), max(ranks), t.get("mean"), t.get("record", ""))
        if not best:
            continue
        sig, school, grp, lo, hi, mean, rec = best
        head = f"{school} ranks No. {lo} to No. {hi} across nine systems"
        dek = f"{GENDER_LABEL[g]} {grp} · {rec} · mean rank {mean:.1f}" if mean is not None else \
            f"{GENDER_LABEL[g]} {grp} · {rec}"
        out.append(_story("disagreement", g, 40 + sig * 3, head, dek, f"{lo}–{hi}",
                          "rank range", {"ep": "jhsaa_computer", "args": {"group": grp, "g": g}},
                          grp, "rankings"))
    return out


def d_one_flight(data: dict) -> list[dict]:
    """The best record in duals decided by one flight, past a minimum sample."""
    out = []
    for g, recs in data["one_flight"].items():
        arc = data["arcs"][g]
        grp_of = {r["school"]: grp for grp in jh.GROUPS for r in _ranking(arc, grp)}
        best = None
        for school, (w, l) in recs.items():
            if w + l < ONE_FLIGHT_MIN or school not in grp_of:
                continue
            key = (w / (w + l), w + l)
            if best is None or key > best[0]:
                best = (key, school, w, l)
        if not best:
            continue
        _, school, w, l = best
        head = f"{school} went {w}–{l} in one-flight duals"
        dek = f"{GENDER_LABEL[g]} {grp_of[school]} · {w + l} duals decided on the last flight"
        out.append(_story("one_flight", g, 40 + (w / (w + l)) * 40 + (w + l),
                          head, dek, f"{w}–{l}", "one-flight duals",
                          _link_school(school, g), grp_of[school], "programs"))
    return out


def d_sweep(data: dict) -> list[dict]:
    """One school, both State titles."""
    out = []
    arcs = data["arcs"]
    if "girls" not in arcs or "boys" not in arcs:
        return out
    gc = {v: k for k, v in (arcs["girls"].get("champions") or {}).items() if v}
    bc = {v: k for k, v in (arcs["boys"].get("champions") or {}).items() if v}
    for school in sorted(set(gc) & set(bc)):
        ggrp, bgrp = gc[school], bc[school]
        head = (f"{school} won both {ggrp} titles" if ggrp == bgrp else
                f"{school} won the girls' {ggrp} and boys' {bgrp} titles")
        out.append(_story("sweep", "both", 85, head, "Girls and boys State champions",
                          "2", "state titles", _link_school(school, "girls"), ggrp, "programs"))
    return out


def d_riser(data: dict) -> list[dict]:
    """The biggest rise in class rank on last season."""
    out = []
    for g, arc in data["arcs"].items():
        prev = (data.get("prev") or {}).get(g)
        if not prev:
            continue
        best = None
        for grp in jh.GROUPS:
            was = {r["school"]: r["rank"] for r in _ranking(prev, grp)}
            for r in _ranking(arc, grp):
                if r["school"] not in was or r["rank"] > 10:
                    continue
                rise = was[r["school"]] - r["rank"]
                if rise >= RISER_MIN and (best is None or rise > best[0]):
                    best = (rise, r, grp, was[r["school"]])
        if not best:
            continue
        rise, r, grp, old = best
        head = f"{r['school']} rose from No. {old} to No. {r['rank']} in {grp}"
        dek = f"{GENDER_LABEL[g]} · {r['record']} · {data['season_year'] - 1} to {data['season_year']}"
        out.append(_story("riser", g, 45 + rise, head, dek, f"+{rise}", "places",
                          _link_school(r["school"], g), grp, "programs"))
    return out


DETECTORS = (d_cinderella, d_chalk, d_nailbiter, d_freshman_champ, d_undefeated,
             d_missed_state, d_disagreement, d_one_flight, d_sweep, d_riser)


# ------------------------------------------------------------- the desks ----

def facts(data: dict) -> list[dict]:
    """The strip above everything: five counts over the season, no panels."""
    arcs = data["arcs"]
    seeds = [_champ_seed(arc, gp) for arc in arcs.values() for gp in jh.GROUPS]
    seeds = [s for s in seeds if s]
    duals = [d for arc in arcs.values() for d in _state_duals(arc)]
    undefeated = sum(1 for arc in arcs.values() for gp in jh.GROUPS
                     for r in _ranking(arc, gp)
                     if r.get("losses", 1) == 0 and r.get("wins", 0) >= UNDEFEATED_MIN_WINS)
    one_seeds_fell = sum(1 for s in seeds if s != 1) if seeds else 0
    # Six facts, one line on a wide screen. The champion COUNT is not one of them —
    # it is the same number every season and Honors owns the names.
    out = []
    if seeds:
        out.append({"n": sum(1 for s in seeds if s <= 4), "label": f"of {len(seeds)} champions were top-4 seeds"})
        out.append({"n": max(seeds), "label": "lowest seed to win a title"})
        out.append({"n": one_seeds_fell, "label": "No. 1 seeds did not win"})
    if duals:
        out.append({"n": f"{round(100 * sum(1 for d in duals if not d['fav_won']) / len(duals))}%",
                    "label": "of State duals won by the lower seed"})
        out.append({"n": f"{round(100 * sum(1 for d in duals if d['margin'] == 1) / len(duals))}%",
                    "label": "decided on the last flight"})
    out.append({"n": undefeated, "label": "undefeated seasons"})
    return out


def players_desk(data: dict) -> list[dict]:
    """Players of the Year, both genders, every class — name, school, record."""
    from . import jhsaa_awards as jaw
    rows = []
    for g, arc in data["arcs"].items():
        for grp in jh.GROUPS:
            poy = ((arc.get("awards") or {}).get(grp) or {}).get("poy")
            if not poy:
                continue
            names = poy.get("names") or [poy.get("name", "")]
            grades = poy.get("grades") or ([poy.get("grade")] if poy.get("grade") else [])
            pids = jaw.row_pids(poy)
            rows.append({"gender": g, "group": grp, "names": names, "grades": grades,
                         "pids": list(pids), "school": poy.get("school", ""),
                         "record": f"{poy.get('wins', 0)}–{poy.get('losses', 0)}",
                         "kind": poy.get("kind", ""),
                         "underclass": any((gr or 12) < 12 for gr in grades)})
    order = {gp: i for i, gp in enumerate(jh.GROUPS)}
    rows.sort(key=lambda r: (r["gender"] != "girls", order.get(r["group"], 99)))
    return rows


def chart(data: dict) -> dict:
    """The Data Desk: seed against outcome, both genders. Two readings of every
    State dual this season — the favourite's win rate by seed gap, and the
    champion's seed in each class."""
    duals = {g: _state_duals(arc) for g, arc in data["arcs"].items()}
    bands = []
    for lo, hi in GAP_BANDS:
        row = {"label": f"{lo}–{hi}" if hi < 99 else f"{lo}+", "lo": lo, "hi": hi}
        for g, ds in duals.items():
            sel = [d for d in ds if lo <= d["gap"] <= hi]
            row[g] = {"n": len(sel),
                      "pct": round(100 * sum(1 for d in sel if d["fav_won"]) / len(sel)) if sel else None}
        bands.append(row)
    champ_seeds = []
    for gp in jh.GROUPS:
        champ_seeds.append({"group": gp, "short": jh.group_short(gp),
                            **{g: _champ_seed(arc, gp) for g, arc in data["arcs"].items()}})
    return {"bands": bands, "champ_seeds": champ_seeds,
            "n": {g: len(ds) for g, ds in duals.items()}}


def record_book(data: dict) -> list[dict]:
    """A strip of standing records — top-flight career wins and most individual
    titles, per gender."""
    out = []
    for g, rec in (data.get("records") or {}).items():
        for r in (rec.get("top") or [])[:1]:
            out.append({"n": r.get("t_w", ""),
                        "name": r.get("name", ""), "school": r.get("school", ""),
                        "label": f"{GENDER_LABEL[g].lower()}' top-flight career wins",
                        "gender": g, "pid": r.get("pid"), "ep": "jhsaa_career_wins"})
        for r in (rec.get("titles") or [])[:1]:
            out.append({"n": r.get("count", ""), "name": r.get("name", ""),
                        "school": ", ".join(r.get("schools") or []) if isinstance(r.get("schools"), list) else r.get("schools", ""),
                        "label": f"{GENDER_LABEL[g].lower()}' individual state titles",
                        "gender": g, "pid": r.get("pid"), "ep": "jhsaa_repeat_champions"})
    return out


def compile_desk(data: dict, feed: int = 6) -> dict:
    """The whole front page, from a loaded season. Pure."""
    stories: list[dict] = []
    for det in DETECTORS:
        try:
            stories.extend(det(data))
        except Exception:                  # one broken detector never sinks the page
            continue
    stories.sort(key=lambda s: (-s["salience"], s["kind"], s["gender"], s["headline"]))
    lead = stories[0] if stories else None
    rest = stories[1:] if stories else []
    # The feed: the next best, no more than two of one kind so a season of
    # freshman champions does not read as one story six times.
    seen: dict = {}
    picked = []
    for s in rest:
        if seen.get(s["kind"], 0) >= 2:
            continue
        seen[s["kind"]] = seen.get(s["kind"], 0) + 1
        picked.append(s)
        if len(picked) >= feed:
            break
    programs = [s for s in stories if s["desk"] == "programs"][:3]
    return {"year": data["year"], "season_year": data["season_year"],
            "genders": list(data["arcs"].keys()),
            "facts": facts(data), "lead": lead, "feed": picked,
            "players": players_desk(data), "programs": programs,
            "freshmen": [s for s in stories if s["kind"] == "freshman_champ"][:4],
            "chart": chart(data), "record_book": record_book(data),
            "all": stories}


_front_cache: dict = {}


def front_page(world_id: int, year: int) -> dict | None:
    """The compiled front page for one world-year, memoised on the archive's own
    stamp (an archived season is immutable; a lab regenerate rewrites its rows
    and so moves the stamp). Compute into a local, publish, return the local."""
    from . import world as wd
    conn = wd._db()
    try:
        st = conn.execute("SELECT COUNT(*) AS n, MAX(rowid) AS r FROM world_jhsaa"
                          " WHERE world_id=? AND year=?", (world_id, year)).fetchone()
    finally:
        conn.close()
    key = (world_id, year, st["n"], st["r"], id(jh.former_names()))
    hit = _front_cache.get(key)
    if hit is not None:
        return hit
    data = load_season(world_id, year)
    if data is None:
        return None
    out = compile_desk(data)
    _front_cache.clear()
    _front_cache[key] = out
    return out


def reset() -> None:
    _front_cache.clear()

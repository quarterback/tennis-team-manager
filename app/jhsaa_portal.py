"""THE RISING-FRESHMAN PORTAL — JHSAA rule 2100 (owner spec 2026-09).

An early participant (a 7th/8th-grader rostered by a 1A, 2A or Group 3 program —
`jhsaa.early_seasons`) who, going into ninth grade, has NO PROJECTED V1 SEAT at
the school they played for is proposed a transfer to a program that projects
them onto its V1. The first interactive system in the high-school game, and the
college transfer portal's shape: the world HOLDS before the season's JHSAA rung
on a proposal the owner reviews on `/jhsaa/portal` (redirect a player to another
of their V1 destinations, drop a move), then commits or dismisses it.

‼️ V1 IS THE GAME'S OWN PROJECTION, never "top eleven by OVR": the coach's
preseason ladder (`jhsaa._order` on the team `district_teams` builds, with last
season's evidence and the program's named staff — the rung's own inputs), cut at
the regular-season lineup (`lineup_need("regular", group)`). A destination
qualifies only if that same projection, with the player added, seats them on it.

‼️ GEOGRAPHY IS A CASCADE, NOT A SCORE: same COUNTY first, then the same AREA,
then NEIGHBOURING AREAS (`area_neighbors`). No league preference. Within the
first tier that has any V1 destination, the best genuine opportunity wins — the
highest projected V1 seat — and any classification may take the player (they are
freshmen now, no longer early participants).

Placement is SEQUENTIAL and sees its own moves: the best players are placed
first, each destination's projected ladder includes every mover already sent to
it, and a pass that pushes somebody else's rising freshman off V1 makes them a
candidate in the next pass (`MAX_PASSES`). A committed move is an ordinary
transfer record (`overrides.set_jhsaa_transfer`, effective the freshman season),
so everything downstream — rosters, the ledger, the player card — already knows
what to do with it. This table is the record of what the PORTAL did, which is
what the research export reads.
"""
from __future__ import annotations

import dataclasses
import json
import math
import time

from . import jhsaa as jh

MAX_PASSES = 4
#: Two areas neighbour when any of their towns lie within this many miles of each
#: other — a shared border, read off real coordinates rather than typed.
AREA_NEIGHBOR_MILES = 30.0
#: How many V1 destinations a proposal keeps for the owner to redirect to.
MAX_OPTIONS = 6

_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_jhsaa_portal (
  world_id INTEGER, season INTEGER, status TEXT, data TEXT, edits TEXT,
  created INTEGER, committed INTEGER,
  PRIMARY KEY (world_id, season)
);
"""

_neighbor_cache: dict = {}


def _conn():
    from . import world
    conn = world._db()
    conn.executescript(_SCHEMA)
    return conn


# ------------------------------------------------------------- geography ----

def _miles(a, b):
    (la1, lo1), (la2, lo2) = a, b
    return 69.0 * math.hypot(la1 - la2,
                             (lo1 - lo2) * math.cos(math.radians((la1 + la2) / 2)))


def area_neighbors() -> dict:
    """{area: sorted neighbouring areas} — areas with a pair of towns within
    `AREA_NEIGHBOR_MILES`; an area that would have none takes its two nearest, so
    the third tier is never empty. Memoised (the map is data, not save state)."""
    got = _neighbor_cache.get("n")
    if got is not None:
        return got
    from .jhsaa_districting import coords
    pos = coords()
    towns: dict = {}
    for g in ("girls", "boys"):
        for s in jh.load_schools(g):
            if s.city in pos:
                towns.setdefault(s.area, set()).add(pos[s.city])
    gap: dict = {}
    areas = sorted(towns)
    for i, a in enumerate(areas):
        for b in areas[i + 1:]:
            d = min(_miles(p, q) for p in towns[a] for q in towns[b])
            gap[(a, b)] = gap[(b, a)] = d
    out = {}
    for a in areas:
        near = [b for b in areas if b != a and gap[(a, b)] <= AREA_NEIGHBOR_MILES]
        if not near:
            near = sorted((b for b in areas if b != a), key=lambda b: gap[(a, b)])[:2]
        out[a] = sorted(near)
    _neighbor_cache["n"] = out
    return out


# ------------------------------------------------------------ projection ----

def v1_size(ts) -> int:
    return jh.lineup_need("regular", ts.school.group)


def v1_rank(ts, pid: str) -> int | None:
    """The player's projected ladder index on `ts` if it seats them on V1."""
    for i, p in enumerate(jh._order(ts)[:v1_size(ts)]):
        if p.pid == pid:
            return i
    return None


def _with(ts, p, prior: dict, season: int, salt: str):
    """`ts` with `p` added, carrying the player's own evidence and this coach's
    read of them — the inputs `district_teams` would have given them."""
    read = dict(ts.read)
    if ts.lens.read > 0.0:
        read[p.pid] = jh.coach_read(p.pid, ts.school.name, season, ts.lens, salt)
    pr = dict(ts.prior)
    if p.pid in prior:
        pr[p.pid] = prior[p.pid]
    # COACH INVESTMENT (owner spec 2026-09): the destination coach values the
    # newcomer's future at his own weight; Program Interest is zero there by
    # construction (no tenure), so a move resets it and the origin keeps it.
    fut = dict(ts.future)
    f = jh.future_value(p, ts.future_w)
    if f:
        fut[p.pid] = f
    itr = {k: v for k, v in ts.interest.items() if k != p.pid}
    return dataclasses.replace(ts, roster=list(ts.roster) + [p], prior=pr, read=read,
                               future=fut, interest=itr)


def _without(ts, pid: str):
    return dataclasses.replace(ts, roster=[q for q in ts.roster if q.pid != pid])


def _rising(ts, season: int) -> list:
    """This team's rising freshmen who played here as 8th-graders."""
    return [p for p in ts.roster
            if p.entry_year == season and p.grade == 9
            and (season - 1) in ((p.jhsaa or {}).get("early") or ())]


def build(world_id: int, season: int, salt: str) -> dict:
    """The proposal for `season` — both genders. Writes nothing."""
    from . import world as wd
    neighbors = area_neighbors()
    active, _inbound = jh.enrolled_transfers(season)
    moves, stays = [], []
    for gender in ("girls", "boys"):
        schools = jh.load_schools(gender)
        prior = wd.jhsaa_prior_for_season(season, gender, world_id)
        staff = wd.jhsaa_staff_for_season(season, gender, world_id)
        teams = {t.school.name: t for t in jh.district_teams(schools, season, salt,
                                                           prior=prior, staff=staff)}
        origin_of: dict = {}          # pid -> origin team name (never changes)
        where: dict = {}              # pid -> the team they are on now
        player: dict = {}
        for name, ts in teams.items():
            if ts.school.classification not in jh.EARLY_CLASSES and not any(
                    (p.jhsaa or {}).get("early") for p in ts.roster):
                continue
            for p in _rising(ts, season):
                if p.pid in active:           # an owner-authored move already
                    continue
                origin_of[p.pid] = where[p.pid] = name
                player[p.pid] = p
        by_county: dict = {}
        by_area: dict = {}
        for name, ts in teams.items():
            by_county.setdefault(ts.school.county, []).append(name)
            by_area.setdefault(ts.school.area, []).append(name)

        def tiers(origin):
            """Destination names tier by tier — county, area, neighbouring areas."""
            county = [n for n in by_county.get(origin.county, ()) if n != origin.name]
            area = [n for n in by_area.get(origin.area, ())
                    if n != origin.name and teams[n].school.county != origin.county]
            near = [n for a in neighbors.get(origin.area, ()) for n in by_area.get(a, ())]
            return (("county", sorted(county)), ("area", sorted(area)),
                    ("neighbor", sorted(near)))

        placed: dict = {}             # pid -> move row
        stuck: set = set()            # no V1 destination anywhere in reach
        # ‼️ THE TRIGGER IS THE ORIGIN'S OWN PRESEASON LADDER, with no portal move
        # applied — a rising freshman with a projected seat at home is never
        # proposed out because a mover was later sent INTO his program (that
        # cascade pushed home kids into the portal and the slate churned). The
        # destinations DO see the moves already sent to them, so nobody is
        # projected onto a seat somebody in this same slate already took.
        todo = [pid for pid in player
                if v1_rank(teams[origin_of[pid]], pid) is None]
        for _ in range(MAX_PASSES):
            todo = [pid for pid in todo if pid not in stuck]
            if not todo:
                break
            todo.sort(key=lambda pid: (-player[pid].current_overall(), pid))
            for pid in todo:
                p = player[pid]
                origin = teams[origin_of[pid]].school
                options = []
                # The FIRST tier with any V1 seat is the tier the player moves in;
                # the owner may redirect within it.
                for tier, names in tiers(origin):
                    for dname in names:
                        if dname == where[pid]:
                            continue
                        trial = _with(teams[dname], p, prior, season, salt)
                        r = v1_rank(trial, pid)
                        if r is not None:
                            options.append({"school": dname,
                                            "class": teams[dname].school.classification,
                                            "tier": tier, "rank": r + 1,
                                            "v1": v1_size(trial)})
                    if options:
                        break
                if not options:
                    stuck.add(pid)
                    continue
                options.sort(key=lambda o: (o["rank"], o["school"]))
                best = options[0]
                teams[where[pid]] = _without(teams[where[pid]], pid)
                teams[best["school"]] = _with(teams[best["school"]], p, prior,
                                              season, salt)
                where[pid] = best["school"]
                placed[pid] = {
                    "pid": pid, "name": p.name, "gender": gender,
                    "from": origin.name, "from_class": origin.classification,
                    "entry": p.entry_year, "seat": (p.jhsaa or {}).get("seat"),
                    "ovr": round(p.current_overall(), 1),
                    "pot": round((p.jhsaa or {}).get("pot_est")
                                 or p.ceiling_overall(), 1),
                    "maturity": (p.jhsaa or {}).get("maturity"),
                    "from_v1": v1_size(teams[origin_of[pid]]),
                    "to": best["school"], "to_class": best["class"],
                    "tier": best["tier"], "rank": best["rank"], "v1": best["v1"],
                    "options": options[:MAX_OPTIONS],
                }
            # Only MOVERS are re-checked: an earlier mover a later one pushed off
            # V1 at the same destination is placed again (his old destination no
            # longer projects him, so he goes elsewhere or is stuck).
            todo = [pid for pid in placed
                    if v1_rank(teams[where[pid]], pid) is None]
        for pid in stuck:
            if pid not in placed:
                p = player[pid]
                o = teams[origin_of[pid]].school
                stays.append({"pid": pid, "name": p.name, "gender": gender,
                              "school": o.name, "class": o.classification,
                              "ovr": round(p.current_overall(), 1)})
        moves += [m for m in placed.values() if m["to"] != m["from"]]
    return {"season": season, "moves": moves, "stays": stays,
            "neighbors": neighbors}


# --------------------------------------------------------------- the hold ----

def upcoming_season(world: dict, lab: bool = False) -> int:
    """The season about to be played: the lab advances the year first."""
    from . import world as wd
    return wd.BASE_YEAR + world["year"] + (2 if lab else 1)


def pending(world_id: int) -> dict | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT season, data, edits, created FROM world_jhsaa_portal"
                         " WHERE world_id=? AND status='proposed'"
                         " ORDER BY season DESC LIMIT 1", (world_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {"season": r["season"], "data": json.loads(r["data"]),
            "edits": json.loads(r["edits"] or "{}"), "created": r["created"]}


def _row(world_id: int, season: int):
    conn = _conn()
    try:
        return conn.execute("SELECT status FROM world_jhsaa_portal WHERE world_id=?"
                            " AND season=?", (world_id, season)).fetchone()
    finally:
        conn.close()


def due(world: dict, lab: bool = False) -> bool:
    """A portal is due for the upcoming season once its 8th-grade season is a
    season of early participation, and it has not been resolved yet."""
    season = upcoming_season(world, lab)
    if season - 1 < jh.early_era():
        return False
    return _row(world["id"], season) is None


def _store(world_id: int, season: int, status: str, data: dict, edits: dict) -> None:
    conn = _conn()
    try:
        conn.execute("INSERT OR REPLACE INTO world_jhsaa_portal (world_id, season, status,"
                     " data, edits, created, committed) VALUES (?,?,?,?,?,?,?)",
                     (world_id, season, status, json.dumps(data), json.dumps(edits),
                      int(time.time()), int(time.time()) if status != "proposed" else None))
        conn.commit()
    finally:
        conn.close()


def open_proposal(world: dict, lab: bool = False, force: bool = False) -> dict | None:
    """Build and store the upcoming season's proposal; None (and nothing held)
    when nobody needs a move — an empty portal is recorded as resolved."""
    from . import world as wd
    cur = pending(world["id"])
    if cur and not force:
        return cur
    season = cur["season"] if cur else upcoming_season(world, lab)
    data = build(world["id"], season, wd.active_salt(world["seed"]))
    if not data["moves"]:
        _store(world["id"], season, "committed", {**data, "applied": []}, {})
        return None
    _store(world["id"], season, "proposed", data, (cur or {}).get("edits") or {})
    return pending(world["id"])


def check_hold(world: dict, lab: bool = False) -> dict | None:
    """The hold, for both advance paths: the open proposal, opening it if due."""
    cur = pending(world["id"])
    if cur is None and due(world, lab):
        cur = open_proposal(world, lab)
    return cur


def final_moves(cur: dict) -> list:
    """The proposal with the owner's edits applied: dropped moves removed, a
    redirect replacing the destination (only to one of the player's own V1
    options — a projection the portal made, never a guess)."""
    edits = cur.get("edits") or {}
    out = []
    for m in cur["data"]["moves"]:
        e = edits.get(m["pid"]) or {}
        if e.get("drop"):
            continue
        to = e.get("to")
        if to:
            opt = next((o for o in m["options"] if o["school"] == to), None)
            if opt:
                m = {**m, "to": to, "to_class": opt["class"], "tier": opt["tier"],
                     "rank": opt["rank"], "v1": opt["v1"], "redirected": True}
        out.append(m)
    return out


def edit(world: dict, pid: str, action: str, to: str = "") -> None:
    cur = pending(world["id"])
    if cur is None:
        return
    edits = cur["edits"]
    if action == "drop":
        edits[pid] = {"drop": True}
    elif action == "to" and to:
        edits[pid] = {"to": to}
    elif action == "reset":
        edits.pop(pid, None)
    _store(world["id"], cur["season"], "proposed", cur["data"], edits)


def commit(world: dict) -> dict:
    """Write every surviving move as a transfer record effective the freshman
    season, and release the hold."""
    from . import overrides as ov
    cur = pending(world["id"])
    if cur is None:
        return {"ok": False, "msg": "No open portal."}
    moves = final_moves(cur)
    for m in moves:
        ov.set_jhsaa_transfer(m["pid"], m["from"], m["gender"], m["entry"], m["seat"],
                              m["to"], cur["season"])
    _store(world["id"], cur["season"], "committed", {**cur["data"], "applied": moves},
           cur["edits"])
    jh.reset_schools()
    return {"ok": True, "moves": len(moves)}


def dismiss(world: dict) -> None:
    cur = pending(world["id"])
    if cur is not None:
        _store(world["id"], cur["season"], "dismissed", {**cur["data"], "applied": []},
               cur["edits"])


def applied(world_id: int) -> list:
    """Every committed portal move in THE world, oldest season first — the
    research export's `jhsaa_portal.csv` and the player fields."""
    conn = _conn()
    try:
        rows = conn.execute("SELECT season, data FROM world_jhsaa_portal WHERE world_id=?"
                            " AND status='committed' ORDER BY season",
                            (world_id,)).fetchall()
    finally:
        conn.close()
    out = []
    for season, data in rows:
        for m in json.loads(data).get("applied") or []:
            out.append({**m, "season": season})
    return out

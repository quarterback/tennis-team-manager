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


def _describe(p, origin_ts, prior: dict) -> dict:
    """What the page says about a player INSTEAD of a rating (owner rule 2026-09:
    no OVR / Pot on the portal). Where they sit on the origin's projected ladder
    against its V1, what they did last season as an 8th-grader, and how many
    early seasons they played — all things the game already knows and shows."""
    order = jh._order(origin_ts)
    ladder = next((i + 1 for i, q in enumerate(order) if q.pid == p.pid), None)
    pr = prior.get(p.pid)
    return {"ladder": ladder, "roster_n": len(order), "from_v1": v1_size(origin_ts),
            "apps": pr.apps if pr else 0, "wins": pr.wins if pr else 0,
            "losses": pr.losses if pr else 0, "prior_rank": pr.rank if pr else 0,
            "early_years": len((p.jhsaa or {}).get("early") or ())}


def build(world_id: int, season: int, salt: str, edits: dict | None = None) -> dict:
    """The proposal for `season` — both genders. Writes nothing.

    `edits` is the owner's `{pid: {"drop": True} | {"to": school}}`. ‼️ EDITS ARE
    REPROJECTED, NEVER TRUSTED: a redirect is placed FIRST, in ability order, and
    only where that destination's ladder — with every earlier redirect on it —
    seats the player on V1; a redirect that fails falls back to the automatic pass
    and says so (`redirect_failed`). The automatic pass then never takes a seat
    that would push a redirected player off (the owner's decision outranks the
    cascade). A dropped player never enters placement and is reported as staying.

    ‼️ ONLY MOVERS WHO STILL PROJECT ONTO V1 AT THEIR FINAL DESTINATION ARE EMITTED.
    A later mover can push an earlier one off the seat he was placed on; if the
    passes run out before he is re-placed he is removed from that roster and
    listed as displaced (a stay), never proposed to a seat he does not have.
    """
    from . import world as wd
    edits = edits or {}
    dropped = {pid for pid, e in edits.items() if (e or {}).get("drop")}
    redirect = {pid: e["to"] for pid, e in edits.items() if (e or {}).get("to")}
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

        # ‼️ THE TRIGGER IS THE ORIGIN'S OWN PRESEASON LADDER, with no portal move
        # applied — a rising freshman with a projected seat at home is never
        # proposed out because a mover was later sent INTO his program (that
        # cascade pushed home kids into the portal and the slate churned). The
        # destinations DO see the moves already sent to them, so nobody is
        # projected onto a seat somebody in this same slate already took.
        need = [pid for pid in player if v1_rank(teams[origin_of[pid]], pid) is None]
        desc = {pid: _describe(player[pid], teams[origin_of[pid]], prior) for pid in need}
        by_ovr = lambda pid: (-player[pid].current_overall(), pid)   # noqa: E731

        def base_row(pid):
            p, o = player[pid], teams[origin_of[pid]].school
            return {"pid": pid, "name": p.name, "gender": gender,
                    "from": o.name, "from_class": o.classification,
                    "from_district": o.district,
                    "entry": p.entry_year, "seat": (p.jhsaa or {}).get("seat"),
                    # kept for the research export, never shown on the page
                    "ovr": round(p.current_overall(), 1),
                    "pot": round((p.jhsaa or {}).get("pot_est")
                                 or p.ceiling_overall(), 1),
                    "maturity": (p.jhsaa or {}).get("maturity"),
                    **desc[pid]}

        held: dict = {}               # destination -> pids the owner redirected there

        def seats(pid, dname):
            """The player's V1 rank at `dname`, or None — and None too when the
            trial would push a REDIRECTED player at that school off V1."""
            trial = _with(teams[dname], player[pid], prior, season, salt)
            r = v1_rank(trial, pid)
            if r is None:
                return None, trial
            if any(v1_rank(trial, q) is None for q in held.get(dname, ())):
                return None, trial
            return r, trial

        def options_for(pid):
            """The first tier with any V1 seat, as option rows; () when none."""
            origin = teams[origin_of[pid]].school
            for tier, names in tiers(origin):
                out = []
                for dname in names:
                    if dname == where[pid]:
                        continue
                    r, trial = seats(pid, dname)
                    if r is not None:
                        out.append({"school": dname,
                                    "class": teams[dname].school.classification,
                                    "tier": tier, "rank": r + 1, "v1": v1_size(trial)})
                if out:
                    out.sort(key=lambda o: (o["rank"], o["school"]))
                    return out
            return []

        def place(pid, dname, tier, r, options, **flags):
            p = player[pid]
            teams[where[pid]] = _without(teams[where[pid]], pid)
            teams[dname] = _with(teams[dname], p, prior, season, salt)
            where[pid] = dname
            placed[pid] = {**base_row(pid), "to": dname,
                           "to_class": teams[dname].school.classification,
                           "tier": tier, "rank": r + 1, "v1": v1_size(teams[dname]),
                           "options": options[:MAX_OPTIONS], **flags}

        placed: dict = {}             # pid -> move row
        stuck: set = set()            # no V1 destination anywhere in reach
        failed: dict = {}             # pid -> the redirect that could not be honoured
        # 1. dropped by the owner: never placed, reported as staying
        for pid in need:
            if pid in dropped:
                stays.append({**base_row(pid), "dropped": True})
        todo = [pid for pid in need if pid not in dropped]
        # 2. the owner's redirects, strongest first, each reprojected
        for pid in sorted((q for q in todo if q in redirect), key=by_ovr):
            dest = redirect[pid]
            origin = teams[origin_of[pid]].school
            tier = next((t for t, names in tiers(origin) if dest in names), None)
            r = None
            if tier is not None and dest != origin.name:
                r, _trial = seats(pid, dest)
            if r is None:
                failed[pid] = dest
                continue
            options = options_for(pid)
            if all(o["school"] != dest for o in options):
                options.append({"school": dest, "class": teams[dest].school.classification,
                                "tier": tier, "rank": r + 1,
                                "v1": v1_size(teams[dest])})
            place(pid, dest, tier, r, options, redirected=True)
            held.setdefault(dest, []).append(pid)
        # 3. the automatic cascade
        todo = [pid for pid in todo if pid not in placed]
        for _ in range(MAX_PASSES):
            todo = [pid for pid in todo if pid not in stuck]
            if not todo:
                break
            todo.sort(key=by_ovr)
            for pid in todo:
                options = options_for(pid)
                if not options:
                    stuck.add(pid)
                    continue
                best = options[0]
                flags = {"redirect_failed": failed[pid]} if pid in failed else {}
                place(pid, best["school"], best["tier"], best["rank"] - 1, options, **flags)
            # Only MOVERS are re-checked: an earlier mover a later one pushed off
            # V1 at the same destination is placed again (his old destination no
            # longer projects him, so he goes elsewhere or is stuck).
            todo = [pid for pid in placed
                    if v1_rank(teams[where[pid]], pid) is None]
        # 4. emit only what still holds; the rest stay where they are
        for pid in list(placed):
            m = placed[pid]
            r = v1_rank(teams[where[pid]], pid)
            if r is None or where[pid] == origin_of[pid]:
                teams[where[pid]] = _without(teams[where[pid]], pid)
                where[pid] = origin_of[pid]
                placed.pop(pid)
                stays.append({**base_row(pid), "displaced": True,
                              "redirect_failed": failed.get(pid, "")})
                continue
            m["rank"] = r + 1             # the FINAL projected seat, not the one at placement
        for pid in stuck:
            if pid not in placed:
                stays.append({**base_row(pid), "redirect_failed": failed.get(pid, "")})
        moves += placed.values()
    order = {g: i for i, g in enumerate(jh.GROUPS)}
    key = lambda m: (m["gender"], order.get(m["from_class"], 99), m["from_district"],   # noqa: E731
                     m["from"], m.get("ladder") or 999, m["pid"])
    moves.sort(key=key)
    stays.sort(key=key)
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
    edits = (cur or {}).get("edits") or {}
    data = build(world["id"], season, wd.active_salt(world["seed"]), edits)
    if not data["moves"] and not edits:
        _store(world["id"], season, "committed", {**data, "applied": []}, {})
        return None
    _store(world["id"], season, "proposed", data, edits)
    return pending(world["id"])


def check_hold(world: dict, lab: bool = False) -> dict | None:
    """The hold, for both advance paths: the open proposal, opening it if due."""
    cur = pending(world["id"])
    if cur is None and due(world, lab):
        cur = open_proposal(world, lab)
    return cur


def final_moves(cur: dict) -> list:
    """The slate as it will be committed. The stored proposal is already built
    WITH the owner's edits (`build(edits=)` reprojects every redirect and leaves
    every drop at home), so this is the move list itself — kept as the one name
    both the page and the commit read it by."""
    return [m for m in cur["data"]["moves"] if not m.get("dropped")]


def edit(world: dict, pid: str, action: str, to: str = "") -> None:
    """Record one owner decision and REBUILD the proposal around it — a redirect
    is a projection the portal makes, never a row rewritten from a cached option."""
    from . import world as wd
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
    data = build(world["id"], cur["season"], wd.active_salt(world["seed"]), edits)
    _store(world["id"], cur["season"], "proposed", data, edits)


def commit(world: dict) -> dict:
    """Write every surviving move as a transfer record effective the freshman
    season, and release the hold. The slate is REPROJECTED with the edits first:
    what is committed is what the ladders say now, never a stale proposal."""
    from . import overrides as ov
    from . import world as wd
    cur = pending(world["id"])
    if cur is None:
        return {"ok": False, "msg": "No open portal."}
    data = build(world["id"], cur["season"], wd.active_salt(world["seed"]), cur["edits"])
    moves = final_moves({"data": data})
    for m in moves:
        ov.set_jhsaa_transfer(m["pid"], m["from"], m["gender"], m["entry"], m["seat"],
                              m["to"], cur["season"])
    _store(world["id"], cur["season"], "committed", {**data, "applied": moves},
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

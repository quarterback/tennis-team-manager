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
the class's DISTRICT lineup (`district_need(group)` — its State format since
owner rule 2026-10: 8 in 1A, 9 in 2A/Group 3). A destination
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
from . import jhsaa_preseason as jps

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
    # The class's DISTRICT lineup (owner rule 2026-10): 8 in 1A, 9 in the 1S/4D
    # classes — V1 is the side that plays for the league title.
    return jh.district_need(ts.school.group)


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


class _Teams:
    """The gender's teams, BUILT ON DEMAND. `district_teams` on every program of
    a gender is the season rung's own cost (~860 roster builds a gender on a real
    save, none of them memoised) — the first portal built all of them, both
    genders, before it had looked at a single ladder, and again on every edit
    and at the commit. The portal only ever needs the gated ORIGINS and the
    destinations it actually consults, tier by tier; most candidates resolve in
    their own county. `ensure()` builds a batch in ONE `district_teams` call
    (each call resolves the family / transfer / read fingerprints — the
    query-storm rule — so never build one school per call)."""

    def __init__(self, schools, season, salt, prior, staff):
        self.schools = {s.name: s for s in schools}
        self.season, self.salt, self.prior, self.staff = season, salt, prior, staff
        self.built: dict = {}

    def ensure(self, names) -> None:
        todo = [self.schools[n] for n in names if n not in self.built and n in self.schools]
        if not todo:
            return
        for ts in jh.district_teams(todo, self.season, self.salt,
                                    prior=self.prior, staff=self.staff):
            self.built[ts.school.name] = ts

    def __getitem__(self, name):
        if name not in self.built:
            self.ensure([name])
        return self.built[name]

    def __setitem__(self, name, ts):
        self.built[name] = ts

    def __contains__(self, name):
        return name in self.schools


class _Ladders:
    """Each built team's ladder as a SORTED KEY LIST, kept incrementally.

    `v1_rank(_with(ts, p))` re-sorts the whole roster — every entry's
    `coach_eval`, each recomputing the player's overall from 49 attributes — to
    learn where ONE newcomer lands. Measured on the fixture: 1.05M coach_eval
    calls and 2.2M overall recomputes for ~700 candidates, and the real save's
    tiers are wider. The ladder is a sorted list on `_order`'s own key, so a
    trial is one key for the newcomer and a bisect; a placement inserts, a
    removal deletes, and nothing is ever re-sorted. ‼️ The EMIT step still asks
    the real `v1_rank` on the real team — this cache only steers the search, so
    a key that disagreed with `_order` (a float tie, say) could cost a proposal
    a row, never hand a player a seat the ladder does not give."""

    def __init__(self, teams: _Teams, season: int, salt: str, prior: dict):
        self.teams, self.season, self.salt, self.prior = teams, season, salt, prior
        self.rows: dict = {}          # name -> [(key, pid)] ascending on key

    @staticmethod
    def _key(ts, p, read, future, interest):
        return (-jh.coach_eval(p, ts.records.get(p.pid), prior=ts.prior.get(p.pid),
                               lens=ts.lens, read=read, future=future,
                               interest=interest), -p.str_value())

    def rows_for(self, name):
        got = self.rows.get(name)
        if got is None:
            ts = self.teams[name]
            fut, itr = ts.future or {}, ts.interest or {}
            got = sorted((self._key(ts, p, ts.read.get(p.pid, 0.0), fut.get(p.pid, 0.0),
                                    itr.get(p.pid, 0.0)), p.pid) for p in ts.roster)
            self.rows[name] = got
        return got

    def newcomer_key(self, name, p):
        """`p`'s key on `name`'s ladder, as `_with` would give them: this coach's
        read, their own prior, his future weight, no program interest."""
        ts = self.teams[name]
        read = (jh.coach_read(p.pid, ts.school.name, self.season, ts.lens, self.salt)
                if ts.lens.read > 0.0 else 0.0)
        pr = self.prior.get(p.pid)
        return (-jh.coach_eval(p, None, prior=pr, lens=ts.lens, read=read,
                               future=jh.future_value(p, ts.future_w), interest=0.0),
                -p.str_value())

    def trial(self, name, p, held=()) -> int | None:
        """Where `p` would land on `name`'s ladder (0-based), or None when that
        is off V1 — or when landing there would push a HELD player off it."""
        import bisect
        rows = self.rows_for(name)
        v1 = v1_size(self.teams[name])
        idx = bisect.bisect_right(rows, (self.newcomer_key(name, p), p.pid))
        if idx >= v1:
            return None
        if held:
            pos = {pid: i for i, (_k, pid) in enumerate(rows)}
            for q in held:
                j = pos.get(q)
                if j is not None and idx <= j and j + 1 >= v1:
                    return None
        return idx

    def rank(self, name, pid) -> int | None:
        for i, (_k, q) in enumerate(self.rows_for(name)):
            if q == pid:
                return i if i < v1_size(self.teams[name]) else None
        return None

    def add(self, name, p) -> None:
        import bisect
        rows = self.rows_for(name)
        bisect.insort_right(rows, (self.newcomer_key(name, p), p.pid))

    def remove(self, name, pid) -> None:
        rows = self.rows_for(name)
        self.rows[name] = [r for r in rows if r[1] != pid]


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
        teams = _Teams(schools, season, salt, prior, staff)
        ladders = _Ladders(teams, season, salt, prior)
        # THE STORED PRESEASON STATE (read-path fix #3): the rung wrote every
        # program's projected ladder and V1 FLOOR for this season, provisionally,
        # when it archived the last one. A destination is eliminated against its
        # stored floor with one key and a bisect — no roster built — and only a
        # program that seats the player on the STORED ladder is built live and
        # confirmed. Empty on a save whose last rung predates the store, in which
        # case every destination is built live (the old cost, once).
        stored = jps.load(world_id, season - wd.BASE_YEAR - 1, gender)
        # ORIGINS: the programs that could have rostered an 8th-grader last
        # season (the gate rewound to that season, `early_seasons`) — a school
        # list question, no roster needed. Built in ONE batch.
        origins = [s.name for s in schools if (season - 1) in jh.early_seasons(s, season)]
        teams.ensure(origins)
        origin_of: dict = {}          # pid -> origin team name (never changes)
        where: dict = {}              # pid -> the team they are on now
        player: dict = {}
        for name in origins:
            for p in _rising(teams[name], season):
                if p.pid in active:           # an owner-authored move already
                    continue
                origin_of[p.pid] = where[p.pid] = name
                player[p.pid] = p
        by_county: dict = {}
        by_area: dict = {}
        for sc in schools:
            by_county.setdefault(sc.county, []).append(sc.name)
            by_area.setdefault(sc.area, []).append(sc.name)
        county_of = {sc.name: sc.county for sc in schools}

        def tiers(origin):
            """Destination names tier by tier — county, area, neighbouring areas."""
            county = [n for n in by_county.get(origin.county, ()) if n != origin.name]
            area = [n for n in by_area.get(origin.area, ())
                    if n != origin.name and county_of[n] != origin.county]
            near = [n for a in neighbors.get(origin.area, ()) for n in by_area.get(a, ())]
            return (("county", sorted(county)), ("area", sorted(area)),
                    ("neighbor", sorted(near)))

        # ‼️ THE TRIGGER IS THE ORIGIN'S OWN PRESEASON LADDER, with no portal move
        # applied — a rising freshman with a projected seat at home is never
        # proposed out because a mover was later sent INTO his program (that
        # cascade pushed home kids into the portal and the slate churned). The
        # destinations DO see the moves already sent to them, so nobody is
        # projected onto a seat somebody in this same slate already took.
        need = [pid for pid in player if ladders.rank(origin_of[pid], pid) is None]
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
            return ladders.trial(dname, player[pid], held.get(dname, ()))

        def plausible(pid, names):
            """The destinations worth BUILDING: already live, or seating the
            player on their stored ladder, or with no stored state to ask."""
            p = player[pid]
            keep = []
            for dname in names:
                if dname in teams.built:
                    keep.append(dname)
                    continue
                st = stored.get(dname)
                if st is None or st.get("floor") is None:
                    keep.append(dname)                     # nothing to eliminate on
                    continue
                if jps.seat_on(st, jps.newcomer_key(st, p, season, salt,
                                                    prior.get(pid))) is not None:
                    keep.append(dname)
            return keep

        def options_for(pid):
            """The first tier with any V1 seat, as option rows; () when none.
            A tier's destinations are BUILT only when the tier is consulted, and
            only the ones the stored floors do not eliminate."""
            origin = teams[origin_of[pid]].school
            for tier, names in tiers(origin):
                names = plausible(pid, [n for n in names if n != where[pid]])
                teams.ensure(names)
                out = []
                for dname in names:
                    r = seats(pid, dname)
                    if r is not None:
                        out.append({"school": dname,
                                    "class": teams[dname].school.classification,
                                    "tier": tier, "rank": r + 1,
                                    "v1": v1_size(teams[dname])})
                if out:
                    out.sort(key=lambda o: (o["rank"], o["school"]))
                    return out
            return []

        def place(pid, dname, tier, r, options, **flags):
            p = player[pid]
            teams[where[pid]] = _without(teams[where[pid]], pid)
            ladders.remove(where[pid], pid)
            teams[dname] = _with(teams[dname], p, prior, season, salt)
            ladders.add(dname, p)
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
            if tier is not None and dest != origin.name and dest in teams:
                teams.ensure([dest])
                r = seats(pid, dest)
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
            todo = [pid for pid in placed if ladders.rank(where[pid], pid) is None]
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


def effective(cur: dict, skip: str = "") -> tuple:
    """The slate AS THE OWNER HAS EDITED IT — `(moves, stays)` — laid over the
    stored proposal without rebuilding anything (owner rule 2026-09: a drop is
    a row struck off, not a reprojection of every ladder in the state).

    The stored `data` is the last FULL build (the automatic pass, or a "Rebuild
    proposal" / commit that reprojected every edit). Each edit overlays it:
    a DROP moves the row to the stays; a REDIRECT the portal has checked against
    that one destination's ladder (`edit`) replaces the row with its validated
    row, or — when the seat was not there — leaves the automatic row standing,
    flagged `redirect_failed`, exactly what `build(edits=)` would say. An edit
    the last full build already baked in (its row carries `redirected` /
    `redirect_failed` for the same school) keeps the built row, which saw the
    whole slate. `skip` leaves one player's own edit out, for re-checking it."""
    edits = cur.get("edits") or {}
    moves, stays = [], list(cur["data"].get("stays") or [])
    for m in cur["data"]["moves"]:
        e = edits.get(m["pid"]) if m["pid"] != skip else None
        e = e or {}
        if e.get("drop"):
            stays.append({**{k: v for k, v in m.items()
                             if k not in ("to", "to_class", "tier", "rank", "v1",
                                          "options", "redirected", "redirect_failed")},
                          "dropped": True})
            continue
        to = e.get("to")
        if to and not (m.get("redirected") and m.get("to") == to) \
                and m.get("redirect_failed") != to:
            if e.get("row"):
                moves.append(dict(e["row"]))
                continue
            if e.get("failed"):
                moves.append({**m, "redirect_failed": to})
                continue
        moves.append(m)
    return moves, stays


def final_moves(cur: dict) -> list:
    """The slate as it will be committed — the edited overlay's moves. The
    commit still reprojects the whole slate with the edits first; this is what
    the page counts and what a test reads."""
    return [m for m in effective(cur)[0] if not m.get("dropped")]


def _tier_of(origin, dest, neighbors: dict) -> str | None:
    if dest.county == origin.county:
        return "county"
    if dest.area == origin.area:
        return "area"
    if dest.area in neighbors.get(origin.area, ()):
        return "neighbor"
    return None


def _check_redirect(world_id: int, season: int, salt: str, cur: dict,
                    pid: str, dest: str) -> dict:
    """Validate ONE redirect: does `dest`'s ladder — carrying the other movers
    this slate already sends there — seat the player on V1? Builds the origin,
    the destination and those movers' origins (a handful of programs, one
    `district_teams` call), never the slate. Returns the edit to store:
    `{"to", "row"}` with the validated move row, or `{"to", "failed": True}`."""
    from . import world as wd
    row = next((m for m in cur["data"]["moves"] if m["pid"] == pid), None)
    if row is None:
        return {"to": dest, "failed": True}
    gender, origin = row["gender"], row["from"]
    if dest == origin:
        return {"to": dest, "failed": True}
    schools = jh.load_schools(gender)
    prior = wd.jhsaa_prior_for_season(season, gender, world_id)
    staff = wd.jhsaa_staff_for_season(season, gender, world_id)
    teams = _Teams(schools, season, salt, prior, staff)
    if dest not in teams or origin not in teams:
        return {"to": dest, "failed": True}
    tier = _tier_of(teams.schools[origin], teams.schools[dest], area_neighbors())
    if tier is None:
        return {"to": dest, "failed": True}
    others = [m for m in effective(cur, skip=pid)[0]
              if m["gender"] == gender and m["to"] == dest and m["pid"] != pid]
    teams.ensure({origin, dest, *[m["from"] for m in others]})
    p = next((q for q in teams[origin].roster if q.pid == pid), None)
    if p is None:
        return {"to": dest, "failed": True}
    ts = teams[dest]
    for m in others:
        q = next((x for x in teams[m["from"]].roster if x.pid == m["pid"]), None)
        if q is not None:
            ts = _with(ts, q, prior, season, salt)
    r = v1_rank(_with(ts, p, prior, season, salt), pid)
    if r is None:
        return {"to": dest, "failed": True}
    new = {k: v for k, v in row.items() if k != "redirect_failed"}
    options = list(row.get("options") or [])
    if all(o["school"] != dest for o in options):
        options.append({"school": dest, "class": ts.school.classification,
                        "tier": tier, "rank": r + 1, "v1": v1_size(ts)})
    new.update({"to": dest, "to_class": ts.school.classification, "tier": tier,
                "rank": r + 1, "v1": v1_size(ts), "options": options, "redirected": True})
    return {"to": dest, "row": new}


def edit(world: dict, pid: str, action: str, to: str = "") -> None:
    """Record one owner decision. ‼️ NEVER A FULL REBUILD (owner rule 2026-09:
    "if i remove a kid it repolls for each single kid"): a drop and an undo are
    stored and overlaid (`effective`); a redirect is checked against the ONE
    destination it names (`_check_redirect`) and stored with its validated row.
    The whole slate is reprojected only by "Rebuild proposal" and the commit.
    The one exception: undoing a drop the last full build already baked in
    (the player is in no move row to restore) rebuilds, since nothing else can
    bring the row back."""
    from . import world as wd
    cur = pending(world["id"])
    if cur is None:
        return
    edits = cur["edits"]
    salt = wd.active_salt(world["seed"])
    rebuild = False
    if action == "drop":
        edits[pid] = {"drop": True}
    elif action == "to" and to:
        edits[pid] = _check_redirect(world["id"], cur["season"], salt, cur, pid, to)
    elif action == "reset":
        was = edits.pop(pid, None)
        in_moves = any(m["pid"] == pid for m in cur["data"]["moves"])
        rebuild = bool(was) and not in_moves
    else:
        return
    data = cur["data"]
    if rebuild:
        data = build(world["id"], cur["season"], salt, edits)
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

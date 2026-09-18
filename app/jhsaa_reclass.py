"""JHSAA reclassification — the four-season realignment cycle (owner spec 2026-09,
`docs/DESIGN-jhsaa-reclassification.md`; background in
`docs/REPORT-jhsaa-reclassification-models.md`).

One pass, three stages, nothing typed:

  1. GEOGRAPHY. Group membership is territory. A Group school outside Group
     territory re-enters the A ladder; the owner-approved eastern 1A areas
     repatriate into the Groups (the initial reset; idempotent after). Ladder
     schools NEVER enter the Groups on territory — the 2046 realignment moved the
     big programs out and they stay out (Baptist, Mater Dei, Minnesota City).
  2. SORT. Three pools — 9A-5A, 4A-1A, Group 1-3 — each sorted ONCE on
     `effective_size = enrollment + success_adjustment - futility_adjustment`
     and cut into equal bands. There is NO one-class-per-cycle guard (owner): a
     school lands where it ranks.
  3. PROPOSE, never commit. The owner vetoes, redirects or adds rows on
     `/jhsaa/reclassification`; the commit writes `world_jhsaa_reclass_move`,
     rewrites `data/jhsaa/schools.json` (the seed file — the owner starts fresh
     saves from it), and redraws the leagues of every class whose membership
     changed through `app.jhsaa_districting`. The next week-0 JHSAA season plays
     the new map. Archived seasons are untouched: each carries the class it was
     played in.

‼️ SCHOOL-LEVEL, BOTH GENDERS. Success points are the SUM of both programs' cycle
points and the win rate is the COMBINED record; a single-gender sponsor is scored on
that one. Boys and girls never land in different classes (pinned).

‼️ IT MOVES `classification` AND `group` TOGETHER. In the band era classification
touches nothing about ability (`jhsaa.band_centre` draws on the program tier);
only roster depth (`ROSTER_SIZE_BAND_BY_CLASS`) and the championship entered.
Play-up overrides (`group` only) stay on top; a commit pops the seeded `play_up`
flag on any school the sort moved, since the sort now does what the flag was for.

‼️ ONE FOLD PER SEASON, NOT PER SCHOOL (the title-board rule): `score()` walks each
archived season once and credits whoever it names. Coefficients live in
`worldconfig` so the page can edit them; the small pool's default is the big
pool's scaled by enrollment span, and the Group pool's likewise.
"""
from __future__ import annotations

import collections
import copy
import json
import os
import time

from . import jhsaa as jh

CYCLE_SEASONS = 4
POOL_A = ("9A", "8A", "7A", "6A", "5A")
POOL_B = ("4A", "3A", "2A", "1A")
POOL_G = ("Group 1", "Group 2", "Group 3")
POOLS = {"A": POOL_A, "B": POOL_B, "G": POOL_G}
#: Finish points per season, by teams alive when eliminated (`jhsaa_state_result`).
FINISH_POINTS = ((1, 4), (2, 3), (4, 2))
MADE_STATE_POINTS = 1
#: Group territory — the five eastern areas (all but three Group schools sit here).
GROUP_TERRITORY = ("Kangas", "Silver Basin", "Bear River Country", "Millersylvania",
                   "Snake River Plain")
#: Owner-approved eastern expansion areas for the 1A repatriation (2026-09).
REPATRIATE_AREAS = ("Boise Frontier", "Blue Mountain Country")
DEFAULTS = {"success_pp": 40.0, "futility_floor": 0.35, "futility_pu": 3000.0}
_CFG = "jhsaa_reclass_"


def config() -> dict:
    """The cycle's knobs, off `worldconfig` with the defaults above. Per-pool
    coefficients for B and G default to A's scaled by enrollment span at build
    time (see `_pool_coeffs`); an explicit value wins."""
    from . import worldconfig as wc
    cfg = {
        "cycle": wc.get_int(_CFG + "cycle", CYCLE_SEASONS, lo=1, hi=20),
        "success_pp": wc.get_float(_CFG + "success_pp", DEFAULTS["success_pp"], hi=1e5),
        "futility_floor": wc.get_float(_CFG + "futility_floor", DEFAULTS["futility_floor"], hi=1.0),
        "futility_pu": wc.get_float(_CFG + "futility_pu", DEFAULTS["futility_pu"], hi=1e6),
        "group_areas": wc.get_json(_CFG + "group_areas", list(GROUP_TERRITORY)),
        "repatriate_areas": wc.get_json(_CFG + "repatriate_areas", list(REPATRIATE_AREAS)),
    }
    for pool in ("b", "g"):
        for key in ("success_pp", "futility_pu"):
            raw = wc.get(f"{_CFG}{key}_{pool}")
            try:
                cfg[f"{key}_{pool}"] = float(raw) if raw not in ("", None) else None
            except (ValueError, TypeError):
                cfg[f"{key}_{pool}"] = None
    return cfg


def set_config(values: dict) -> None:
    from . import worldconfig as wc
    for key, val in values.items():
        if key in ("group_areas", "repatriate_areas"):
            wc.set(_CFG + key, json.dumps([v for v in val if v]))
        else:
            wc.set(_CFG + key, "" if val in (None, "") else str(val))


# ---------------------------------------------------------------- scoring ----

def _wl(record: str) -> tuple[int, int]:
    try:
        parts = [int(x) for x in str(record or "0-0").split("-")[:2]]
        return parts[0], parts[1]
    except (ValueError, IndexError):
        return 0, 0


def finish_points(place: int, made_state: bool) -> int:
    if not made_state:
        return 0
    for cut, pts in FINISH_POINTS:
        if place and place <= cut:
            return pts
    return MADE_STATE_POINTS


def cycle_years(world_id: int, n: int) -> list[int]:
    """The last `n` archived world-years, oldest first, over both genders."""
    from . import world
    years = sorted(set(world.jhsaa_years(world_id, "girls"))
                   | set(world.jhsaa_years(world_id, "boys")))
    return years[-n:]


def score(world_id: int, years: list[int]) -> dict:
    """{school: {pts, wins, losses, wr, seasons, by_gender: {g: {pts, wins, losses}}}}
    over `years` — one pass per archived season, both genders, school-level."""
    from . import world
    out: dict = {}

    def row(name):
        r = out.get(name)
        if r is None:
            r = out[name] = {"pts": 0, "wins": 0, "losses": 0, "seasons": 0,
                             "by_gender": {}}
        return r

    for year in years:
        for g in ("girls", "boys"):
            arc = world.get_jhsaa(world_id, year, g)
            if not arc:
                continue
            for _grp, dists in (arc.get("standings") or {}).items():
                for _d, teams in (dists or {}).items():
                    for t in teams or ():
                        r = row(t.get("school", ""))
                        w, l = _wl(t.get("record"))
                        gd = r["by_gender"].setdefault(g, {"pts": 0, "wins": 0, "losses": 0})
                        r["wins"] += w
                        r["losses"] += l
                        gd["wins"] += w
                        gd["losses"] += l
                        r["seasons"] += 1
            for _grp, br in (arc.get("brackets") or {}).items():
                for school in (br or {}).get("field") or ():
                    st = world.jhsaa_state_result(br, school)
                    p = finish_points(st["place"], st["made_state"])
                    r = row(school)
                    r["pts"] += p
                    r["by_gender"].setdefault(g, {"pts": 0, "wins": 0, "losses": 0})["pts"] += p
    for r in out.values():
        n = r["wins"] + r["losses"]
        r["wr"] = round(r["wins"] / n, 4) if n else None
    return out


# ------------------------------------------------------------- the passes ----

def pool_of(cls: str) -> str | None:
    for key, members in POOLS.items():
        if cls in members:
            return key
    return None


def _ladder_pool_for(enrollment: int, rows: list[dict]) -> str:
    """Which A-ladder pool a school entering from the Groups joins: by enrollment
    against the big pool's current floor (rule 7 — the normal A-class process)."""
    floor = min((r["enrollment"] for r in rows if r["classification"] in POOL_A),
                default=800)
    return "A" if enrollment >= floor else "B"


def _pool_coeffs(cfg: dict, pool: str, spans: dict) -> tuple[float, float, float]:
    """(success_pp, futility_floor, futility_pu) for a pool. B and G default to A's
    numbers scaled by their enrollment span over A's, so one authored pair serves
    every pool unless the owner sets a pool's own."""
    pp, floor, pu = cfg["success_pp"], cfg["futility_floor"], cfg["futility_pu"]
    if pool == "A":
        return pp, floor, pu
    k = pool.lower()
    scale = (spans.get(pool) or 1.0) / (spans.get("A") or 1.0)
    return (cfg.get(f"success_pp_{k}") if cfg.get(f"success_pp_{k}") is not None else pp * scale,
            floor,
            cfg.get(f"futility_pu_{k}") if cfg.get(f"futility_pu_{k}") is not None else pu * scale)


def _live_rows() -> list[dict]:
    """Live sponsors only, as copies — a former program keeps its row and its page
    but plays no season and is placed by nothing."""
    return [copy.deepcopy(r) for r in jh._rows() if r.get("girls") or r.get("boys")]


def build_proposal(world_id: int, years: list[int], cfg: dict | None = None,
                   edits: dict | None = None, redraw: bool = True) -> dict:
    """The whole cycle as a dict: every pooled school with its evidence and proposed
    class, the geography moves, class counts before and after, and (when `redraw`)
    the league each moved school lands in.

    `edits` is {school: {"action": "veto"|"redirect"|"add", "to": class|pool}}.
    A veto pins the school to its current class; a redirect pins it to `to`; an
    add puts a school the passes left alone into pool `to` ("A"/"B"/"G") and the
    sort places it. Pinned schools count toward their class's band so the cut stays
    even around them."""
    cfg = cfg or config()
    edits = edits or {}
    rows = _live_rows()
    sc = score(world_id, years)
    by_name = {r["name"]: r for r in rows}
    territory = set(cfg["group_areas"]) | set(cfg["repatriate_areas"])
    decreed = {r["name"] for r in rows if r.get("talent")}

    # --- 1. geography: which ladder each school is on for this cycle ---------
    pool_for: dict[str, str] = {}
    geo: list[dict] = []
    for r in rows:
        cls = r["classification"]
        p = pool_of(cls)
        if p is None or r["name"] in decreed:
            continue
        if p == "G" and r["area"] not in territory:
            dest = _ladder_pool_for(int(r["enrollment"]), rows)
            pool_for[r["name"]] = dest
            geo.append({"school": r["name"], "area": r["area"], "from": cls,
                        "pool": dest, "reason": "outside Group territory"})
        elif cls == "1A" and r["area"] in set(cfg["repatriate_areas"]):
            pool_for[r["name"]] = "G"
            geo.append({"school": r["name"], "area": r["area"], "from": cls,
                        "pool": "G", "reason": "approved eastern area"})
        else:
            pool_for[r["name"]] = p
    # Owner additions: a Group school asking back onto the A ladder, or the reverse.
    for name, e in edits.items():
        if e.get("action") == "add" and name in by_name and e.get("to") in POOLS:
            pool_for[name] = e["to"]
            geo.append({"school": name, "area": by_name[name]["area"],
                        "from": by_name[name]["classification"], "pool": e["to"],
                        "reason": "owner addition"})

    # --- 2. the three sorts ----------------------------------------------------
    spans = {}
    for key in POOLS:
        enr = [int(r["enrollment"]) for r in rows if pool_for.get(r["name"]) == key]
        spans[key] = (max(enr) - min(enr)) if enr else 0.0
    proposed: dict[str, str] = {}
    pooled: list[dict] = []
    for key, classes in POOLS.items():
        members = [r for r in rows if pool_for.get(r["name"]) == key]
        if not members:
            continue
        pp, floor, pu = _pool_coeffs(cfg, key, spans)
        entries = []
        pinned: dict[str, str] = {}
        for r in members:
            e = edits.get(r["name"]) or {}
            if e.get("action") == "veto":
                pinned[r["name"]] = r["classification"]
            elif e.get("action") == "redirect" and e.get("to") in classes:
                pinned[r["name"]] = e["to"]
            s = sc.get(r["name"]) or {}
            pts = s.get("pts", 0)
            wr = s.get("wr")
            fut = max(0.0, floor - wr) * pu if wr is not None else 0.0
            adj = pts * pp - fut
            entries.append({
                "school": r["name"], "area": r["area"], "city": r["city"],
                "pool": key, "current": r["classification"], "enrollment": int(r["enrollment"]),
                "points": pts, "wins": s.get("wins", 0), "losses": s.get("losses", 0),
                "win_rate": wr, "seasons": s.get("seasons", 0),
                "by_gender": s.get("by_gender", {}),
                "success_adj": round(pts * pp, 1), "futility_adj": round(fut, 1),
                "adjustment": round(adj, 1), "effective": round(int(r["enrollment"]) + adj, 1),
                "pinned": pinned.get(r["name"]), "edit": e.get("action") or "",
                "league_before": r.get("girls_district") or r.get("boys_district") or "",
            })
        entries.sort(key=lambda x: (-x["effective"], -x["enrollment"], x["school"]))
        for i, x in enumerate(entries, start=1):
            x["rank"] = i
        # Equal bands, with pinned schools counted toward their class's seats.
        n = len(entries)
        k = len(classes)
        base, rem = divmod(n, k)
        quota = {c: base + (1 if i < rem else 0) for i, c in enumerate(classes)}
        for name, cls in pinned.items():
            quota[cls] = max(0, quota[cls] - 1)
        free = [x for x in entries if not x["pinned"]]
        ci = 0
        for x in free:
            while ci < k - 1 and quota[classes[ci]] <= 0:
                ci += 1
            x["proposed"] = classes[ci]
            quota[classes[ci]] -= 1
        for x in entries:
            if x["pinned"]:
                x["proposed"] = x["pinned"]
            x["moves"] = x["proposed"] != x["current"]
            proposed[x["school"]] = x["proposed"]
        pooled.extend(entries)

    # --- 3. counts, and the leagues the redraw would produce -------------------
    before = collections.Counter(r["classification"] for r in rows)
    after = collections.Counter(proposed.get(r["name"], r["classification"]) for r in rows)
    touched = sorted({x["current"] for x in pooled if x["moves"]}
                     | {x["proposed"] for x in pooled if x["moves"]},
                     key=lambda c: jh.GROUPS.index(c) if c in jh.GROUPS else 99)
    league_after: dict[str, str] = {}
    notes: dict[str, list[str]] = {}
    if redraw and touched:
        from . import jhsaa_districting as jd
        draft = copy.deepcopy(jh._rows())
        for r in draft:
            p = proposed.get(r["name"])
            if p:
                r["classification"] = r["group"] = p
        notes = jd.redraw_classes(draft, touched)
        league_after = {r["name"]: r["girls_district"] for r in draft
                        if r["name"] in proposed}
    for x in pooled:
        x["league_after"] = league_after.get(x["school"], x["league_before"])
    moves = [x for x in pooled if x["moves"]]
    return {
        "years": years, "season_years": [],
        "config": {k: v for k, v in cfg.items()},
        "coefficients": {key: _pool_coeffs(cfg, key, spans) for key in POOLS},
        "spans": spans,
        "rows": pooled, "geo": geo, "moves": moves,
        "counts_before": dict(before), "counts_after": dict(after),
        "touched": touched, "redraw_notes": notes,
        "n_up": sum(1 for x in moves if _rank(x["proposed"]) < _rank(x["current"])),
        "n_down": sum(1 for x in moves if _rank(x["proposed"]) > _rank(x["current"])),
        "built_at": int(time.time()),
    }


def _rank(cls: str) -> int:
    return jh.GROUPS.index(cls) if cls in jh.GROUPS else 99


# ----------------------------------------------------------- persistence ----

_SCHEMA = """
CREATE TABLE IF NOT EXISTS world_jhsaa_reclass (
  world_id INTEGER, year INTEGER, status TEXT, data TEXT, edits TEXT,
  created INTEGER, committed INTEGER
);
CREATE TABLE IF NOT EXISTS world_jhsaa_reclass_move (
  world_id INTEGER, year INTEGER, school TEXT, from_cls TEXT, to_cls TEXT,
  enrollment INTEGER, points INTEGER, win_rate REAL, adjustment REAL,
  effective REAL, rank INTEGER, reason TEXT, manual INTEGER DEFAULT 0,
  league_before TEXT, league_after TEXT
);
CREATE INDEX IF NOT EXISTS ix_jhsaa_reclass_move ON world_jhsaa_reclass_move(world_id, school);
"""


def _conn():
    from . import world
    conn = world._db()
    conn.executescript(_SCHEMA)
    return conn


def pending(world_id: int) -> dict | None:
    """The open proposal, if any: {year, data, edits, created}."""
    conn = _conn()
    try:
        r = conn.execute("SELECT year, data, edits, created FROM world_jhsaa_reclass"
                         " WHERE world_id=? AND status='proposed' ORDER BY year DESC LIMIT 1",
                         (world_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {"year": r["year"], "data": json.loads(r["data"]),
            "edits": json.loads(r["edits"] or "{}"), "created": r["created"]}


def last_cycle_year(world_id: int) -> int | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT MAX(year) y FROM world_jhsaa_reclass WHERE world_id=?"
                         " AND status='committed'", (world_id,)).fetchone()
    finally:
        conn.close()
    return r["y"] if r and r["y"] is not None else None


def due(world: dict) -> bool:
    """A cycle is due at week 0 once `cycle` seasons have been archived since the last
    commit (or since the save began). The hold only bites while a proposal is open."""
    cfg = config()
    years = cycle_years(world["id"], 10_000)
    if len(years) < cfg["cycle"]:
        return False
    last = last_cycle_year(world["id"])
    played_since = [y for y in years if last is None or y > last]
    return len(played_since) >= cfg["cycle"]


def open_proposal(world: dict, force: bool = False) -> dict:
    """Build and store the proposal for this world-year (idempotent: an open one is
    returned as is unless `force` rebuilds it, keeping the owner's edits)."""
    cur = pending(world["id"])
    if cur and not force:
        return cur
    cfg = config()
    years = cycle_years(world["id"], cfg["cycle"])
    edits = (cur or {}).get("edits") or {}
    data = build_proposal(world["id"], years, cfg, edits)
    from . import world as wd
    data["season_years"] = [wd.BASE_YEAR + y + 1 for y in years]
    conn = _conn()
    try:
        conn.execute("DELETE FROM world_jhsaa_reclass WHERE world_id=? AND status='proposed'",
                     (world["id"],))
        conn.execute("INSERT INTO world_jhsaa_reclass (world_id, year, status, data, edits,"
                     " created, committed) VALUES (?,?,?,?,?,?,NULL)",
                     (world["id"], world["year"], "proposed", json.dumps(data),
                      json.dumps(edits), int(time.time())))
        conn.commit()
    finally:
        conn.close()
    return pending(world["id"])


def edit(world: dict, school: str, action: str, to: str = "") -> dict | None:
    """Record one owner edit and rebuild the proposal around it. `action` is
    veto / redirect / add / clear."""
    cur = pending(world["id"])
    if not cur:
        return None
    edits = dict(cur["edits"])
    if action == "clear":
        edits.pop(school, None)
    elif action in ("veto", "redirect", "add"):
        edits[school] = {"action": action, "to": to}
    conn = _conn()
    try:
        conn.execute("UPDATE world_jhsaa_reclass SET edits=? WHERE world_id=? AND status='proposed'",
                     (json.dumps(edits), world["id"]))
        conn.commit()
    finally:
        conn.close()
    return open_proposal(world, force=True)


def dismiss(world: dict) -> None:
    conn = _conn()
    try:
        conn.execute("UPDATE world_jhsaa_reclass SET status='dismissed' WHERE world_id=?"
                     " AND status='proposed'", (world["id"],))
        conn.commit()
    finally:
        conn.close()


def commit(world: dict) -> dict:
    """Apply the open proposal: move classes on the seed file, redraw the touched
    classes' leagues, record every move, close the cycle. Returns a summary."""
    cur = pending(world["id"])
    if not cur:
        return {"ok": False, "msg": "No open proposal."}
    data = cur["data"]
    moves = data["moves"]
    proposed = {x["school"]: x["proposed"] for x in data["rows"]}
    with open(jh._DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    for r in doc["schools"]:
        p = proposed.get(r["name"])
        if p and p != r["classification"]:
            r["classification"] = r["group"] = p
            r.pop("play_up", None)          # the sort now places it
    from . import jhsaa_districting as jd
    from . import overrides as ov
    notes = jd.redraw_classes(doc["schools"], data["touched"]) if data["touched"] else {}
    after_league = {r["name"]: r["girls_district"] for r in doc["schools"]}
    with open(jh._DATA, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    # The per-save play-up overrides go first, on their own connection: the
    # overrides table shares this file, and a second writer while the move
    # transaction below is open is a "database is locked".
    for x in moves:
        ov.clear_jhsaa_playup(x["school"])
    conn = _conn()
    try:
        for x in moves:
            conn.execute(
                "INSERT INTO world_jhsaa_reclass_move (world_id, year, school, from_cls,"
                " to_cls, enrollment, points, win_rate, adjustment, effective, rank, reason,"
                " manual, league_before, league_after) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (world["id"], world["year"], x["school"], x["current"], x["proposed"],
                 x["enrollment"], x["points"], x["win_rate"], x["adjustment"],
                 x["effective"], x["rank"],
                 "owner" if x["edit"] else ("geography" if x["pool"] != pool_of(x["current"]) else "sort"),
                 1 if x["edit"] else 0, x["league_before"],
                 after_league.get(x["school"], x["league_after"])))
        data["redraw_notes"] = notes
        conn.execute("UPDATE world_jhsaa_reclass SET status='committed', committed=?, data=?"
                     " WHERE world_id=? AND status='proposed'",
                     (int(time.time()), json.dumps(data), world["id"]))
        conn.commit()
    finally:
        conn.close()
    jh.reset_schools()
    paths = write_ledger(cycle(world["id"], world["year"]))
    return {"ok": True, "moves": len(moves), "touched": data["touched"], "notes": notes,
            "ledger": paths}


def moves_for(world_id: int, school: str) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM world_jhsaa_reclass_move WHERE world_id=? AND"
                            " school=? ORDER BY year", (world_id, school)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def cycle_index(world_id: int) -> list[dict]:
    """Every committed cycle, newest first, WITHOUT its moves: {year, season_year,
    n_moves, n_geo, n_manual, counts_before, counts_after, committed}. The
    Realignments page lists cycles off this and loads ONE cycle's moves — a cycle
    is ~400 rows on a real save, and the page must not grow by that every four
    seasons (owner, 2026-09)."""
    from . import world as wd
    conn = _conn()
    try:
        cycles = conn.execute("SELECT year, data, committed FROM world_jhsaa_reclass WHERE"
                              " world_id=? AND status='committed' ORDER BY year DESC",
                              (world_id,)).fetchall()
        counts = {r["year"]: (r["n"], r["m"]) for r in conn.execute(
            "SELECT year, COUNT(*) AS n, SUM(manual) AS m FROM world_jhsaa_reclass_move"
            " WHERE world_id=? GROUP BY year", (world_id,))}
    finally:
        conn.close()
    out = []
    for c in cycles:
        data = json.loads(c["data"])
        n, m = counts.get(c["year"], (0, 0))
        out.append({"year": c["year"], "season_year": wd.BASE_YEAR + c["year"] + 1,
                    "n_moves": n, "n_manual": m or 0, "n_geo": len(data.get("geo", [])),
                    "counts_before": data.get("counts_before", {}),
                    "counts_after": data.get("counts_after", {}),
                    "committed": c["committed"]})
    return out


def cycle(world_id: int, year: int) -> dict | None:
    """ONE committed cycle with its moves (from_cls, to_cls, school order), the
    geography pass, the counts and the league-redraw notes; None if no cycle was
    committed at that world-year."""
    from . import world as wd
    conn = _conn()
    try:
        c = conn.execute("SELECT year, data, committed FROM world_jhsaa_reclass WHERE"
                         " world_id=? AND year=? AND status='committed'",
                         (world_id, year)).fetchone()
        if not c:
            return None
        mv = conn.execute("SELECT * FROM world_jhsaa_reclass_move WHERE world_id=? AND"
                          " year=? ORDER BY from_cls, to_cls, school",
                          (world_id, year)).fetchall()
    finally:
        conn.close()
    data = json.loads(c["data"])
    return {"year": c["year"], "season_year": wd.BASE_YEAR + c["year"] + 1,
            "moves": [dict(r) for r in mv],
            "counts_before": data.get("counts_before", {}),
            "counts_after": data.get("counts_after", {}),
            "geo": data.get("geo", []), "redraw_notes": data.get("redraw_notes", {}),
            "years": data.get("years", []), "committed": c["committed"]}


def history(world_id: int) -> list[dict]:
    """Every committed cycle IN FULL, newest first. Tests and the ledger use it;
    the page reads `cycle_index` + one `cycle`."""
    return [cycle(world_id, c["year"]) for c in cycle_index(world_id)]


def all_moves(world_id: int) -> list[dict]:
    """Every recorded move of every committed cycle, newest cycle first — the
    research export's `jhsaa_realignments.csv`. One query, never per cycle."""
    from . import world as wd
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM world_jhsaa_reclass_move WHERE world_id=?"
                            " ORDER BY year DESC, from_cls, to_cls, school",
                            (world_id,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["season_year"] = wd.BASE_YEAR + d["year"] + 1
        out.append(d)
    return out


# ------------------------------------------------------------- the ledger ----
# ‼️ EVERY COMMITTED CYCLE IS ALSO WRITTEN TO A FILE (owner rule 2026-09): the
# owner wants to track realignments "with an llm at some point across the arc
# of seasons", and a database row is not something a model can be handed. The
# commit rewrites `data/jhsaa/schools.json` already, so the ledger lives beside
# it: one JSON and one Markdown per cycle (`<season_year>.json` / `.md`), plus
# `LEDGER.md`, the whole arc in one document, REGENERATED from the JSON files
# on every commit — never appended, so it cannot drift from its cycles. The
# path is resolved off `jh._DATA` at call time, so a test that points the seed
# file at a copy writes its ledger beside that copy.


def ledger_dir() -> str:
    return os.path.join(os.path.dirname(jh._DATA), "realignments")


def _md_table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def cycle_markdown(c: dict, depth: int = 1) -> str:
    """One cycle as a Markdown document: counts, the geography pass, every move
    with its evidence, the league redraw. Plain tables — the reader is a model.
    `depth` is the heading level of the cycle's own title (LEDGER.md nests each
    cycle one level down)."""
    from . import world as wd
    h1, h2, h3 = "#" * depth, "#" * (depth + 1), "#" * (depth + 2)
    classes = [g for g in jh.GROUPS]
    scored = ", ".join(str(wd.BASE_YEAR + y + 1) for y in c.get("years", []))
    lines = [f"{h1} JHSAA realignment — {c['season_year']} season",
             "",
             (f"Committed at world year {c['year']}; scored on the {scored} seasons."
              if scored else f"Committed at world year {c['year']}."),
             "",
             f"{len(c['moves'])} schools moved "
             f"({sum(1 for m in c['moves'] if m.get('manual'))} by owner decision, "
             f"{len(c.get('geo', []))} across the ladder/Group line).",
             "", f"{h2} Class counts", "",
             _md_table(["", *[jh.group_short(g) for g in classes]],
                       [["Before", *[c["counts_before"].get(g, 0) for g in classes]],
                        ["After", *[c["counts_after"].get(g, 0) for g in classes]]]),
             ""]
    if c.get("geo"):
        pool_name = {"A": "9A-5A", "B": "4A-1A", "G": "Groups"}
        lines += [f"{h2} Geography pass", "",
                  _md_table(["School", "Area", "From", "To pool", "Reason"],
                            [[g["school"], g.get("area", ""), g["from"],
                              pool_name.get(g.get("pool"), g.get("pool", "")),
                              g.get("reason", "")] for g in c["geo"]]), ""]
    by_pair: dict[tuple, list] = {}
    for m in c["moves"]:
        by_pair.setdefault((m["from_cls"], m["to_cls"]), []).append(m)
    lines += [f"{h2} Moves", ""]
    for (a, b), ms in sorted(by_pair.items(), key=lambda kv: (_rank(kv[0][0]), _rank(kv[0][1]))):
        lines += [f"{h3} {a} → {b} ({len(ms)})", "",
                  _md_table(["School", "Enrollment", "Points", "Win%", "Adjustment",
                             "Effective size", "Rank", "Reason", "League before", "League after"],
                            [[m["school"], m["enrollment"], m["points"],
                              "" if m["win_rate"] is None else f"{m['win_rate']:.3f}",
                              f"{m['adjustment']:+.0f}", f"{m['effective']:.0f}", m["rank"],
                              m["reason"],
                              m.get("league_before", ""), m.get("league_after", "")]
                             for m in ms]), ""]
    notes = c.get("redraw_notes") or {}
    if notes:
        lines += [f"{h2} League redraw", ""]
        for cls, n in notes.items():
            lines.append(f"- **{cls}**")
            lines += [f"  - {line}" for line in (n or [])]
        lines.append("")
    return "\n".join(lines)


def write_ledger(c: dict) -> dict:
    """Write one committed cycle's JSON and Markdown and regenerate LEDGER.md
    from every cycle file in the directory. Returns the paths written."""
    d = ledger_dir()
    os.makedirs(d, exist_ok=True)
    stem = os.path.join(d, str(c["season_year"]))
    with open(stem + ".json", "w", encoding="utf-8") as fh:
        json.dump(c, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with open(stem + ".md", "w", encoding="utf-8") as fh:
        fh.write(cycle_markdown(c))
    cycles = []
    for name in sorted(os.listdir(d)):
        if name.endswith(".json") and name[:-5].isdigit():
            with open(os.path.join(d, name), encoding="utf-8") as fh:
                cycles.append(json.load(fh))
    cycles.sort(key=lambda x: x["season_year"])
    head = ["# JHSAA realignment ledger", "",
            "Every reclassification cycle the association has committed, oldest first — "
            "regenerated from the per-cycle JSON files in this directory on every commit. "
            "Each cycle names the schools that moved, the class they left and joined, and "
            "the evidence the sort placed them on (enrollment, State points, win rate, the "
            "adjustment and the resulting effective size).", "",
            _md_table(["Season", "Moved", "Owner decisions", "Cross-ladder"],
                      [[x["season_year"], len(x["moves"]),
                        sum(1 for m in x["moves"] if m.get("manual")), len(x.get("geo", []))]
                       for x in cycles]), ""]
    body = "\n\n".join(cycle_markdown(x, depth=2) for x in cycles)
    ledger = os.path.join(d, "LEDGER.md")
    with open(ledger, "w", encoding="utf-8") as fh:
        fh.write("\n".join(head) + "\n" + body + "\n")
    return {"json": stem + ".json", "md": stem + ".md", "ledger": ledger}

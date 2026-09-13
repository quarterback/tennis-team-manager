"""The JHSAA Program Coefficient — a UEFA-coefficient-style longitudinal strength
score (owner spec 2026-09, `docs/AAR-jhsaa-program-coefficient.md`).

Per program, per gender, ranked WITHIN A CLASSIFICATION ONLY. Built entirely from
road-to-state and State-bracket results: the regular season already decides who
qualifies for the road and does not count again here, the way UEFA's coefficient
ignores domestic league position.

    season total = Σ road-round wins (by phase)  +  State-finish lookup  +  TOC bonus
    coefficient  = Σ over the trailing 9 seasons of  season total × recency weight

Three rules the fold is built on:
- **ONE PASS PER SEASON, NOT ONE PER SCHOOL** (`season_points`): each archived
  season is read once and credits every program it names, the title board's
  idiom. A per-season result is memoised — an archived season is immutable.
- **RANK WITHIN THE CURRENT `group`.** A program that moved classes is ranked in
  its current class with its FULL history; history is never fragmented across a
  reclassification, and no cross-class ranking exists anywhere.
- **A NEW PROGRAM IS SEEDED, NOT ZEROED.** Fewer than `MIN_HISTORY` archived
  seasons in the whole source data (a classification change is never a trigger)
  → the exact Q1 of the established programs' coefficients in its current class.
"""
from __future__ import annotations

# ---- point schedule (owner spec) ----------------------------------------------

#: Road-to-state round WINS, by the round's archived name → points per win. Keyed
#: on `jhsaa`'s own name constants (the `jhsaa_title_stages` rule): a renamed round
#: must move its price with it rather than silently stop scoring. Areas are on the
#: road and score nothing — the spec starts at Sectionals.
def road_points() -> dict[str, float]:
    import app.jhsaa as jh
    return {
        "Sectionals": 1, jh._STAGE_NAMES["ward"]: 1,
        jh._STAGE_NAMES["regional"]: 2, jh._STAGE_NAMES["zonal"]: 2,
        jh.EPIREGIONAL_NAME: 1,
        jh._RECOVERY_NAMES["super_regional"]: 2, jh._RECOVERY_NAMES["semi_state"]: 2,
        jh._RECOVERY_NAMES["divisional"]: 2, jh._RECOVERY_NAMES["semi_conference"]: 2,
        jh._RECOVERY_NAMES["conference"]: 2,
        jh._RECOVERY_NAMES["special_challenger"]: 3,
        jh._RECOVERY_NAMES["state_special"]: 3,
    }


#: State-bracket finish → points, ONE lookup on the terminal result (not cumulative
#: with the road). Keyed on `place` = teams still alive when eliminated, the archive's
#: own number (`world.jhsaa_state_result`), never a label string.
STATE_CHAMPION, STATE_FINAL, STATE_SEMI, STATE_QUARTER, STATE_OCTO, STATE_ENTRY = \
    30, 22, 20, 12, 6, 4
TOC_BONUS = 4

#: Recency weights by seasons back from the newest archived season: three tiers,
#: faded but never zeroed inside the window, dropped past it.
WINDOW = 9
WEIGHTS = (1.0, 1.0, 1.0, 0.6, 0.6, 0.6, 0.3, 0.3, 0.3)
assert len(WEIGHTS) == WINDOW

#: Fewer archived seasons than this, in the WHOLE source data, and a program is
#: bootstrapped rather than scored.
MIN_HISTORY = 3
BOOTSTRAP_Q = 0.25

#: Archive keys whose `rounds` are road-to-state duals (every one carries the
#: round's name in `round_names`, which is what prices it). `prestate` holds both
#: Regionals and Zonals; `epiregional`'s rounds carry EPIREGIONAL_NAME.
_ROAD_KEYS = ("sectionals", "wards", "prestate", "epiregional", "super_regional",
              "semi_state", "divisional", "semi_conference", "conference",
              "special_challenger", "state_special")


def state_points(place: int, parastate: bool = False) -> float:
    """The State-finish award. A Parastate exit is 0 — the at-large's only State
    dual, a preliminary the road qualifiers never play."""
    if place <= 0 or parastate:
        return 0
    if place == 1:
        return STATE_CHAMPION
    if place == 2:
        return STATE_FINAL
    if place <= 4:
        return STATE_SEMI
    if place <= 8:
        return STATE_QUARTER
    if place <= 16:
        return STATE_OCTO
    return STATE_ENTRY


def identity_map(season_names, rows: list[dict]) -> dict[str, str]:
    """`{archived display name: stable program identity}` for ONE season.

    ‼️ HISTORY IS KEYED ON THE ROSTER IDENTITY (`source or name`), NEVER THE DISPLAY
    STRING. `world._relabel` rewrites every unambiguous rename on read, but it
    deliberately cannot touch a retired name that a DIFFERENT program now uses as
    its live name (`jhsaa.former_names` drops those six — Treasure Valley, Goodman,
    River Plain, …). Keyed on the string, the older program's seasons would be
    credited to the current holder of its former name and drive both its ranking
    and its tier suggestion.

    The archive has no year on a rename, but it has a structural fact: two
    programs never share a display name in one season (pinned by
    `test_display_names_are_unique_identities`). So an ambiguous name resolves, per
    season, to the program whose CURRENT name is absent from that season — if the
    renamed program appears under its new name, the old string is its neighbour's;
    if it does not, the string is the renamed program's own pre-rename season.
    Pure over the season's name set and the school rows, so it is pinned as
    arithmetic."""
    names = set(season_names)
    live = {r["name"]: (r.get("source") or r["name"]) for r in rows}
    out = dict(live)
    for r in rows:
        src = r.get("source")
        if not src or src == r["name"]:
            continue
        if src in live:
            # Ambiguous: `src` is also some other program's live name. It is the
            # renamed program's own season only if that program is absent under
            # its current name.
            if r["name"] not in names:
                out[src] = src            # the renamed program's ident IS its source
        else:
            out[src] = src
    return out


def season_points(arc: dict, rows: list[dict] | None = None) -> dict[str, dict]:
    """ONE archived season → `{ident: {"points", "road", "state", "toc", "group",
    "name"}}` for every program the season names, keyed on the stable roster
    identity (`identity_map`; without `rows` the display name is the identity, the
    hand-built-archive case). A pure fold over the archive dict, so a test can
    hand-build a season and assert the arithmetic without a database."""
    from app.world import jhsaa_state_result
    import app.jhsaa as jh
    prices = road_points()
    out: dict[str, dict] = {}
    named: set[str] = set()
    for dists in (arc.get("standings") or {}).values():
        for teams in (dists or {}).values():
            for t in teams or ():
                if t.get("school"):
                    named.add(t["school"])
    ident = identity_map(named, rows) if rows is not None else {}

    def row(school: str) -> dict:
        k = ident.get(school, school)
        r = out.get(k)
        if r is None:
            r = out[k] = {"points": 0.0, "road": 0.0, "state": 0.0, "toc": 0.0,
                          "group": "", "name": school}
        return r

    # Who played, and in which class THAT season (the archive's own group).
    for grp, dists in (arc.get("standings") or {}).items():
        for teams in (dists or {}).values():
            for t in teams or ():
                if t.get("school"):
                    row(t["school"])["group"] = grp
    # The road: every WIN of every round, priced by the round's archived name.
    # A game with no opponent is a materialised bye, not a win.
    for key in _ROAD_KEYS:
        for d in (arc.get(key) or {}).values():
            names = (d or {}).get("round_names") or ()
            for i, games in enumerate((d or {}).get("rounds") or ()):
                price = prices.get(names[i] if i < len(names) else "", 0)
                if not price:
                    continue
                for gm in games:
                    w = gm.get("winner")
                    if w and gm.get("home") and gm.get("away"):
                        row(w)["road"] += price
    # State: one lookup on the terminal finish, for every entrant.
    for br in (arc.get("brackets") or {}).values():
        for school in (br or {}).get("field") or ():
            st = jhsaa_state_result(br, school)
            row(school)["state"] += state_points(
                st["place"], st["finish"] == jh.PARASTATE_NAME)
    # The Tournament of Champions: a flat bonus for being in the field.
    for school in (arc.get("toc") or {}).get("field") or ():
        row(school)["toc"] += TOC_BONUS
    for r in out.values():
        r["points"] = r["road"] + r["state"] + r["toc"]
    return out


def _q1(values: list[float]) -> float:
    """The exact value at the 25th-percentile cut of `values` (linear
    interpolation between order statistics), or 0 for an empty list."""
    if not values:
        return 0.0
    xs = sorted(values)
    pos = BOOTSTRAP_Q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def fold(seasons: list[tuple[int, dict]], current_group: dict[str, str],
         history_counts: dict[str, int] | None = None) -> dict[str, list[dict]]:
    """The coefficient from PER-SEASON point maps.

    `seasons` — `(year, season_points(arc))` pairs, NEWEST FIRST, at most `WINDOW`
    of them: index is seasons-back and picks the weight. `current_group` — each
    program's class to rank in TODAY (a program absent from it is ranked in the
    class it last played). `history_counts` — archived seasons per program over
    the WHOLE source data (defaults to a count over `seasons`), the bootstrap gate.

    Returns `{group: [row…]}`, each group ranked, rows carrying `coefficient`,
    `rank`, `seasons`, `bootstrap`, `points` (the newest season's total) and a
    per-season `breakdown` of `(year, total, weight)`."""
    totals: dict[str, float] = {}
    breakdown: dict[str, list] = {}
    last_group: dict[str, str] = {}
    counted: dict[str, int] = {}
    last_name: dict[str, str] = {}
    for back, (year, pts) in enumerate(seasons[:WINDOW]):
        w = WEIGHTS[back]
        for school, r in pts.items():
            totals[school] = totals.get(school, 0.0) + r["points"] * w
            breakdown.setdefault(school, []).append((year, r["points"], w))
            counted[school] = counted.get(school, 0) + 1
            if r.get("group") and school not in last_group:
                last_group[school] = r["group"]
            if r.get("name") and school not in last_name:
                last_name[school] = r["name"]
    hist = history_counts if history_counts is not None else counted
    groups: dict[str, list[dict]] = {}
    for school, total in totals.items():
        grp = current_group.get(school) or last_group.get(school, "")
        groups.setdefault(grp, []).append({
            # `school` is the identity the fold ran on; `name` the newest display
            # name it was archived under (the page shows today's name for a live
            # program, resolved by the caller).
            "school": school, "name": last_name.get(school, school),
            "group": grp, "coefficient": total,
            "seasons": hist.get(school, 0),
            "bootstrap": hist.get(school, 0) < MIN_HISTORY,
            "points": breakdown[school][0][1] if breakdown[school]
            and breakdown[school][0][0] == seasons[0][0] else 0.0,
            "breakdown": breakdown[school]})
    for grp, rows in groups.items():
        q1 = _q1([r["coefficient"] for r in rows if not r["bootstrap"]])
        for r in rows:
            if r["bootstrap"]:
                r["coefficient"] = q1
        rows.sort(key=lambda r: (-r["coefficient"], r["school"]))
        for i, r in enumerate(rows):
            r["rank"] = i + 1
    return groups


# ---- the world-facing entry point ----------------------------------------------

_season_cache: dict = {}      # (world_id, year, gender) -> season_points — immutable
_coef_cache: dict = {}        # (world_id, gender, as_of, playup version) -> result


def _season(world_id: int, year: int, gender: str) -> dict:
    from app import world
    import app.jhsaa as jh
    ck = (world_id, year, gender)
    hit = _season_cache.get(ck)
    if hit is not None:
        return hit
    arc = world.get_jhsaa(world_id, year, gender)
    got = season_points(arc, jh._rows()) if arc else {}
    _season_cache[ck] = got
    return got


def reset() -> None:
    _season_cache.clear()
    _coef_cache.clear()


def coefficient(world_id: int, gender: str, as_of: int | None = None) -> dict:
    """`{"as_of", "years", "groups": {group: [rows]}}` for `gender`, as of the newest
    archived season (or `as_of`, an earlier world-year — how `trend` is computed).
    Memoised on the override fingerprint that moves a program's class (play-up),
    since the class a program is ranked IN is today's."""
    from app import world, overrides as ov
    import app.jhsaa as jh
    years = world.jhsaa_years(world_id, gender)            # newest first
    if as_of is not None:
        years = [y for y in years if y <= as_of]
    if not years:
        return {"as_of": None, "years": [], "groups": {}}
    ck = (world_id, gender, years[0], ov.jhsaa_playup_version())
    hit = _coef_cache.get(ck)
    if hit is not None:
        return hit
    window = years[:WINDOW]
    seasons = [(y, _season(world_id, y, gender)) for y in window]
    # History over the WHOLE source data — the bootstrap gate counts every archived
    # season a program appears in, not only the window's.
    hist: dict[str, int] = {}
    for y in years:
        for school in _season(world_id, y, gender):
            hist[school] = hist.get(school, 0) + 1
    schools = jh.load_schools(gender)
    current = {s.ident: s.group for s in schools}
    groups = fold(seasons, current, hist)
    # A live program reads under TODAY's name; a former one under the last it played.
    today = {s.ident: s.name for s in schools}
    for rows in groups.values():
        for r in rows:
            r["name"] = today.get(r["school"], r["name"])
    out = {"as_of": years[0], "years": window, "groups": groups}
    _coef_cache[ck] = out
    return out


def ranked(world_id: int, gender: str, as_of: int | None = None) -> dict:
    """`coefficient()` with `trend` on every row — this coefficient minus the same
    program's coefficient as of the previous archived season (0 when there is no
    prior season, or the program was not in it). `as_of` is the season the reader
    picked: the window, the ranking and the trend all end there."""
    now = coefficient(world_id, gender, as_of=as_of)
    if not now["years"]:
        return now
    prior = {}
    prev = coefficient(world_id, gender, as_of=now["as_of"] - 1)
    for rows in prev["groups"].values():
        for r in rows:
            prior[r["school"]] = r["coefficient"]
    for rows in now["groups"].values():
        for r in rows:
            r["trend"] = r["coefficient"] - prior[r["school"]] \
                if r["school"] in prior else 0.0
    return now


def percentiles(world_id: int, gender: str) -> dict[str, float]:
    """`{school: 0..1}` — a program's standing WITHIN its class on the coefficient
    (1.0 = top of its class, 0.0 = bottom). The one thing a class-scoped ranking
    may legitimately hand to an association-wide consumer (the explorer's tier
    suggestion): a percentile within a class is class-blind by construction, so
    no cross-class ordering is ever formed."""
    import app.jhsaa as jh
    # ‼️ CURRENT SPONSORS ONLY. A program that dropped this gender, or stopped
    # sponsoring altogether, still carries up to nine seasons of archive — ranked
    # here it would keep an obsolete standing in the school's tier suggestion and
    # take a seat in the roll-weight deal, shifting every live program's cut.
    members = {s.ident for s in jh.load_schools(gender)}
    out: dict[str, float] = {}
    for rows in coefficient(world_id, gender)["groups"].values():
        # A class with NO established program (a save younger than MIN_HISTORY
        # seasons) has every row at the same seeded value, ranked by name — an
        # ordering that says nothing, so it hands out no standing at all.
        if not any(not r["bootstrap"] for r in rows):
            continue
        live = [r for r in rows if r["school"] in members]     # already ranked
        n = len(live)
        for i, r in enumerate(live):
            out[r["school"]] = 1.0 if n <= 1 else 1.0 - i / (n - 1)
    return out

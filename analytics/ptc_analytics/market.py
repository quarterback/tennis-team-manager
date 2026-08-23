"""The player market — who is where, who moved, and who is in the wrong place.

This is the layer the sidecar was missing entirely. The tool could tell you how
a TEAM was good; it could not answer a single one of the questions an actual
roster pass asks, all of which are player-market queries:

  * who is buried — good enough to be in a lineup, not in this one
  * who is in the reservoir — the middle-class mass that plays two matches a
    year and would start a class or two down
  * who is stranded — a genuine top-of-ladder player on a program going nowhere
  * who is nearby — every player within one county of a program you want to
    build, so a group can be moved together the way a real cohort converges

Four different questions, not one. A single "mismatch between ability and
playing time" list answers none of them, because a mismatch is a FACT, not a
problem: a 67 at No. 1 singles for a bad team is a perfectly ordinary thing to
be. What makes a move interesting is a pull somewhere else, so every finder
here reports the pull (where would they start, who else is nearby, what does
the destination ladder look like) rather than just the mismatch.

Two joins do all the work and both are already in the export:

  MOVEMENT   diff `program_id` across consecutive seasons on the stable
             `player_id`. Nothing else is needed and nothing currently uses it.
  PLACEMENT  a program's ladder is its roster sorted on OVR, so "where would
             this player slot in over there" is a lookup, not a model.

‼️ Class comparisons key on `championship_group` (who a program actually
plays), never `classification` (enrollment). Six programs differ, two of them
by four classes.

‼️ Programs join on `program_id`. Roughly 300 of 1,644 display names have
changed across the archive and an id often matches neither the old name nor
the new one.
"""
from __future__ import annotations

import statistics
from collections import defaultdict

from . import aggregate

# A finder needs the class's own starting line to say anything, and a class
# with almost nobody in the export can't supply one.
MIN_CLASS_SAMPLE = 12

# "Barely played" — the reservoir's defining symptom. Derived intent, fixed
# number: two matches is the line the association's own bench rotation sits
# above, and it is what the roster passes have used throughout.
FEW_MATCHES = 2

# ‼️ A FINDER IS NOT CAPPED. An earlier version kept the best 60 per
# classification, which reads on screen exactly like "these are the
# candidates" while silently being "these are 60 of 533" — the association's
# own no-silent-caps rule, one level up. The finders return everything that
# qualifies; the GRID caps what it draws at once and says so on screen, which
# is a display limit the reader can see and work around by narrowing.

# How deep a catchment list goes. A cohort build is a handful of players from
# one area, not a draft board.
CATCHMENT_LIMIT = 40


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- movement --

def movement(bundles) -> dict:
    """Transfers, read off the archive by diffing where a player was.

    Returns {"moved": {(family, gender, year, player_id): {...}},
             "seen":  {(family, gender, year): {player_id: program_id}},
             "years": {(family, gender): [year, ...]}}

    A move is recorded on the season it LANDS in (the year the player shows up
    somewhere new), because that is the season whose roster it changed. A
    player absent from either side of a year pair is not a transfer, it is a
    player the export does not cover — freshmen arriving and seniors leaving
    must never read as movement.
    """
    seen: dict[tuple, dict] = defaultdict(dict)
    names: dict[tuple, dict] = defaultdict(dict)
    who: dict[str, str] = {}
    for b in bundles:
        key = (b.family, b.gender, b.year)
        for pid, p in b.players.items():
            seen[key][pid] = p.get("program_id")
            who[pid] = p.get("name") or pid
        for prog_id, prog in b.programs.items():
            names[key][prog_id] = prog.get("name") or prog_id

    years: dict[tuple, list] = defaultdict(list)
    for (family, gender, year) in seen:
        years[(family, gender)].append(year)
    for k in years:
        years[k] = sorted(set(years[k]))

    moved: dict[tuple, dict] = {}
    for (family, gender), yrs in years.items():
        for prev, cur in zip(yrs, yrs[1:]):
            if cur - prev != 1:
                continue        # a gap year can't distinguish a move from two
            before = seen[(family, gender, prev)]
            after = seen[(family, gender, cur)]
            for pid, prog in after.items():
                was = before.get(pid)
                if was is None or was == prog:
                    continue
                moved[(family, gender, cur, pid)] = {
                    "player_id": pid, "name": who.get(pid, pid),
                    "year": cur, "from_id": was, "to_id": prog,
                    "from": names[(family, gender, prev)].get(was, was),
                    "to": names[(family, gender, cur)].get(prog, prog),
                }
    return {"moved": moved, "seen": seen, "years": dict(years)}


def fit_growth(bundles, ability) -> dict:
    """Expected one-year OVR gain by remaining headroom, FITTED from the
    ingested seasons.

    The constants an earlier pass wrote down (0.7 / 3.6 / 5.8 / 6.8 / 7.6 per
    headroom decade) were fitted on one specific year pair, and the game's
    development model has been rebuilt and is era-gated by entry year — so a
    copied table describes whichever era it was measured in and silently
    mis-scores every other one. Refit; don't trust.

    Returns {decade: mean_gain} plus {"n": {decade: count}}.
    """
    buckets: dict[int, list] = defaultdict(list)
    by_year: dict[tuple, dict] = defaultdict(dict)
    for b in bundles:
        sa = ability.ability(b.scope_id)
        if sa is None:
            continue
        for pid in b.players:
            if pid in sa.ovr:
                by_year[(b.family, b.gender, b.year)][pid] = (sa.ovr[pid], sa.pot.get(pid))

    keys = sorted(by_year)
    for family, gender, year in keys:
        prev = by_year.get((family, gender, year - 1))
        if not prev:
            continue
        for pid, (cur, _pot) in by_year[(family, gender, year)].items():
            was = prev.get(pid)
            if not was:
                continue
            prev_ovr, prev_pot = was
            if prev_pot is None:
                continue
            headroom = max(0.0, prev_pot - prev_ovr)
            buckets[min(int(headroom // 10), 4)].append(cur - prev_ovr)

    curve = {d: statistics.fmean(v) for d, v in buckets.items() if v}
    return {"gain": curve, "n": {d: len(v) for d, v in buckets.items()}}


def expected_gain(curve: dict, headroom: float | None) -> float | None:
    gain = curve.get("gain") or {}
    if headroom is None or not gain:
        return None
    return gain.get(min(int(max(headroom, 0) // 10), 4))


# ------------------------------------------------------------ player rows --

def _starting_lines(rows: list[dict], dressed: int | None) -> dict:
    """Per classification, the OVR of a MEDIAN player in a lineup — the line a
    player has to clear to be a starter in that class.

    This is the number that makes the whole market legible: "where would this
    player start" is just the biggest class whose line they clear. It is read
    off the ingested season rather than assumed, so it moves with the world
    (nine seasons of hand transfers have moved it) instead of encoding whatever
    the classes looked like once.
    """
    if not dressed:
        return {}
    pool: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["ovr"] is None or r["ladder_rank"] is None:
            continue
        if r["ladder_rank"] <= dressed:
            pool[r["classification"]].append(r["ovr"])
    return {cls: statistics.median(v) for cls, v in pool.items()
            if len(v) >= MIN_CLASS_SAMPLE}


def _starts_in(lines: dict, order: list[str], ovr: float | None) -> str:
    """The strongest classification whose starting line this player clears."""
    if ovr is None or not lines:
        return ""
    for cls in order:                     # biggest class first
        line = lines.get(cls)
        if line is not None and ovr >= line:
            return cls
    return ""


def player_rows(bundles, careers, boards, ability, move, growth) -> dict:
    """scope_id -> [row], one row per player-season, carrying everything the
    Player Stat Center and every finder need. Built once; nothing downstream
    re-walks the raw tables."""
    out: dict[str, list[dict]] = {}
    for b in bundles:
        sa = ability.ability(b.scope_id)
        board = boards.get(b.scope_id, {})
        by_program = board.get("by_program", {})
        curve = growth
        prev_key = (b.family, b.gender, b.year - 1)
        prev_seen = move["seen"].get(prev_key, {})
        prev_ability = None
        for other in bundles:
            if (other.family, other.gender, other.year) == prev_key:
                prev_ability = ability.ability(other.scope_id)
                break

        rows = []
        for pid, p in b.players.items():
            program_id = p.get("program_id")
            prog = b.programs.get(program_id, {})
            if not prog:
                continue
            standing = by_program.get(program_id, {})
            stat = ability.player.get((b.scope_id, pid), {})
            ovr = sa.ovr.get(pid) if sa else None
            pot = sa.pot.get(pid) if sa else None
            grade_label, grade_sort = aggregate.grade_label(p)

            matches = stat.get("matches", 0)
            pct = stat.get("pct")
            team_pct = None
            tw, tl = _i(standing.get("wins")), _i(standing.get("losses"))
            if tw is not None and tl is not None and (tw + tl):
                team_pct = tw / (tw + tl)

            prev_ovr = prev_pot = None
            if prev_ability and pid in prev_ability.ovr:
                prev_ovr = prev_ability.ovr[pid]
                prev_pot = prev_ability.pot.get(pid)
            gain = (ovr - prev_ovr) if (ovr is not None and prev_ovr is not None) else None
            exp = expected_gain(curve, (prev_pot - prev_ovr)
                                if (prev_pot is not None and prev_ovr is not None) else None)

            mv = move["moved"].get((b.family, b.gender, b.year, pid))
            rows.append({
                "player_id": pid, "name": p.get("name") or pid,
                "program_id": program_id, "program": prog.get("name") or program_id,
                "classification": aggregate.program_class(prog),
                "league": aggregate.program_league(prog),
                "county": prog.get("county") or "", "area": prog.get("area") or "",
                "grade": grade_label, "grade_sort": grade_sort,
                "ovr": ovr, "pot": pot,
                "headroom": (pot - ovr) if (ovr is not None and pot is not None) else None,
                "ladder_rank": sa.rank_of(pid) if sa else None,
                "roster_size": sa.roster_size(program_id) if sa else 0,
                "matches": matches,
                "w": stat.get("w", 0), "l": stat.get("l", 0), "pct": pct,
                "singles_rec": f"{stat.get('singles_w', 0)}-{stat.get('singles_l', 0)}",
                "doubles_rec": f"{stat.get('doubles_w', 0)}-{stat.get('doubles_l', 0)}",
                "top_flight": stat.get("top_slot", ""),
                "wae": stat.get("wae"),
                "avg_opp_ovr": stat.get("avg_opp_ovr"),
                "avg_gap": stat.get("avg_gap"),
                # 'Good player on a bad team', in one number: the player's own
                # win rate minus the rate at which their team wins duals.
                "lift": (pct - team_pct) if (pct is not None and team_pct is not None) else None,
                "team_record": f"{tw}-{tl}" if tw is not None and tl is not None else "",
                "team_pct": team_pct,
                "team_class_rank": standing.get("class_rank"),
                "team_class_size": standing.get("class_size"),
                "team_class_pctile": ((standing.get("class_rank") / standing["class_size"])
                                      if standing.get("class_size") else None),
                "dev_gain": gain,
                "dev_vs_expected": (gain - exp) if (gain is not None and exp is not None) else None,
                "moved_from": mv["from"] if mv else "",
                "returning": grade_sort and grade_sort < 12,
                "was_here": pid in prev_seen,
            })

        dressed = sa.dressed if sa else None
        order = sorted({r["classification"] for r in rows},
                       key=aggregate.classification_sort_key)
        lines = _starting_lines(rows, dressed)
        for r in rows:
            r["starts_in"] = _starts_in(lines, order, r["ovr"])
            line = lines.get(r["classification"])
            # How far above/below a median starter in their OWN class they sit,
            # now and at their ceiling. The second one is what tells a player
            # having a quiet year apart from one who is never going to start
            # here, which is the difference between two entirely different
            # kinds of move.
            r["vs_starter"] = (r["ovr"] - line) if (r["ovr"] is not None and line is not None) else None
            r["pot_vs_starter"] = (r["pot"] - line) if (r["pot"] is not None and line is not None) else None
            r["benched"] = bool(dressed and r["ladder_rank"] and r["ladder_rank"] > dressed)
        out[b.scope_id] = rows
    return out


def starting_lines(rows: list[dict], dressed: int | None) -> dict:
    """Public wrapper — the classification report shows these directly."""
    return _starting_lines(rows, dressed)


# ------------------------------------------------------------- the finders --

def find_benched(rows: list[dict]) -> list[dict]:
    """Buried: outside the lineup, and good enough to be IN one — they clear
    the median starting line of their own classification and still don't
    dress. The pull is real and local: they would start, right now, at an
    ordinary program of the size they already attend."""
    return sorted((r for r in rows if r["benched"] and (r["vs_starter"] or -1) >= 0),
                  key=lambda r: -(r["vs_starter"] or 0))


def find_reservoir(rows: list[dict]) -> list[dict]:
    """The reservoir: returning players outside the lineup, barely playing,
    who do not clear their own class's starting line AND will not clear it at
    their ceiling either. The move is down, not sideways.

    ‼️ The ceiling test is what separates this from `find_benched`, and
    dropping it collapses the two: a good player having a quiet year is buried
    and should move ACROSS, while a player who is never going to start here is
    the cascade. It is also why the finder does NOT require `starts_in` to be
    set — that would demand they beat the MEDIAN starter of some class, and
    half of every class's starters are below their own median. Where they
    would start is reported when it is known and is not a gate.
    """
    hits = [r for r in rows
            if r["benched"] and r["returning"] and r["matches"] <= FEW_MATCHES
            and r["vs_starter"] is not None and r["vs_starter"] < 0
            and (r["pot_vs_starter"] is None or r["pot_vs_starter"] < 0)]
    return sorted(hits, key=lambda r: (r["matches"], -(r["ovr"] or 0)))


def find_stranded(rows: list[dict]) -> list[dict]:
    """Stranded: a genuine top-of-ladder player on a program in the bottom
    third of its own class. Not 'their OVR is high for their team' — that is
    the ordinary state of a small program — but 'this player is good in
    ABSOLUTE terms and the program around them is not going anywhere'."""
    by_class: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["ovr"] is not None:
            by_class[r["classification"]].append(r["ovr"])
    elite = {}
    for cls, vals in by_class.items():
        if len(vals) < MIN_CLASS_SAMPLE:
            continue
        vals = sorted(vals)
        elite[cls] = vals[int(0.90 * (len(vals) - 1))]

    hits = []
    for r in rows:
        cut = elite.get(r["classification"])
        pctile = r["team_class_pctile"]
        if cut is None or pctile is None or r["ovr"] is None:
            continue
        if r["ovr"] >= cut and (r["ladder_rank"] or 99) <= 3 and pctile >= 0.667:
            hits.append(r)
    return sorted(hits, key=lambda r: -(r["ovr"] or 0))


def catchments(rows: list[dict]) -> dict:
    """Best available talent by county and by area — the raw material for a
    cohort build. A destination's own roster is filtered out in the browser,
    since the destination is chosen there.

    Keyed by geography rather than by destination on purpose: ~860 programs ×
    a candidate list each is a large embedded table that says the same thing
    twenty times, once per county.
    """
    by_county: dict[str, list] = defaultdict(list)
    by_area: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["ovr"] is None:
            continue
        if r["county"]:
            by_county[r["county"]].append(r)
        if r["area"]:
            by_area[r["area"]].append(r)

    def top(pool):
        return [r["player_id"] for r in
                sorted(pool, key=lambda r: -(r["ovr"] or 0))[:CATCHMENT_LIMIT]]

    return {"county": {k: top(v) for k, v in by_county.items()},
            "area": {k: top(v) for k, v in by_area.items()}}


# key, label, finder, blurb, (grid sort key, direction) — the sort carries the
# finder's OWN ranking into the grid, which is information the id list alone
# loses: a reservoir list ordered by ability answers a different question from
# one ordered by how little the player has played.
FINDERS = (
    ("benched", "Buried", find_benched,
     "Outside the lineup and above their own class's median starter — they would "
     "start today at an ordinary program the size of the one they already attend. "
     "The smallest and most valuable of the three lists.",
     ("vs", -1)),
    ("reservoir", "Reservoir", find_reservoir,
     "Returning, barely played, and below their class's starting line now AND at "
     "their ceiling: the move is DOWN. “Starts in” names the class where "
     "they walk into a lineup.",
     ("matches", 1)),
    ("stranded", "Stranded", find_stranded,
     "Top-decile ability in their class, top three on their own ladder, on a program "
     "in the bottom third of that class — the star carrying a team going nowhere.",
     ("ovr", -1)),
)


# ----------------------------------------------------------- team movement --

def team_movement(bundles, rows_by_scope: dict, move: dict, ability) -> dict:
    """(scope_id, program_id) -> in/out/net plus what the arrivals were worth.

    A program's departures are read from the NEXT season (where those players
    turn up), so the newest ingested season legitimately shows no outbound
    figure — there is nothing yet to read it from. That is reported as unknown
    rather than as zero: a program that lost seven players and a program that
    lost none must not print the same number.
    """
    out: dict[tuple, dict] = {}
    scope_of: dict[tuple, str] = {}
    for b in bundles:
        scope_of[(b.family, b.gender, b.year)] = b.scope_id

    for b in bundles:
        rows = rows_by_scope.get(b.scope_id, [])
        arrivals: dict[str, list] = defaultdict(list)
        stayers: dict[str, list] = defaultdict(list)
        for r in rows:
            if r["moved_from"]:
                arrivals[r["program_id"]].append(r)
            elif r["was_here"]:
                stayers[r["program_id"]].append(r)

        departures: dict[str, list] = defaultdict(list)
        nxt = scope_of.get((b.family, b.gender, b.year + 1))
        for (family, gender, year, pid), mv in move["moved"].items():
            if (family, gender, year) == (b.family, b.gender, b.year + 1):
                departures[mv["from_id"]].append(mv)

        for program_id in b.programs:
            arr = arrivals.get(program_id, [])
            dep = departures.get(program_id, [])
            stay = stayers.get(program_id, [])
            arr_wins = sum(r["w"] for r in arr)
            all_wins = sum(r["w"] for r in rows if r["program_id"] == program_id)

            def dev(pool):
                vals = [r["dev_vs_expected"] for r in pool if r["dev_vs_expected"] is not None]
                return statistics.fmean(vals) if vals else None

            out[(b.scope_id, program_id)] = {
                "in": len(arr), "out": (len(dep) if nxt else None),
                "net": (len(arr) - len(dep)) if nxt else None,
                "next_scope": nxt,
                "arrivals": sorted(arr, key=lambda r: -(r["ovr"] or 0)),
                "departures": sorted(dep, key=lambda m: m["to"]),
                # Share of the season's flight wins that came from players who
                # were not on this roster last year. A title built by arrivals
                # and a title built at home look identical on a standings row.
                "arrival_win_share": (arr_wins / all_wins) if all_wins else None,
                "dev_arrivals": dev(arr), "dev_stayers": dev(stay),
            }
    return out

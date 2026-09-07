"""Read-only, self-describing research bundles for browser downloads.

Dataset families register builders here rather than teaching the web route about
their schemas.  Shared concepts use the same filenames; family-specific material
is intentionally allowed to remain separate.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace


class ExportError(ValueError):
    """A user-correctable export request error."""


def _csv(rows: list[dict]) -> bytes:
    out = io.StringIO(newline="")
    fields = list(rows[0]) if rows else []
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def _player_id(school: str, name: str, lookup: dict) -> str:
    return lookup.get((school, name)) or "name:" + hashlib.sha1(
        f"{school}|{name}".encode()).hexdigest()[:16]


def _load_archived_jhsaa_season(year: int, gender: str) -> dict:
    """Reconstruct a ``jhsaa.run_season``-shaped dict from the PERSISTED archive
    (``world_jhsaa`` / ``world_jhsaa_dual``) instead of resimulating the whole
    state — a full JHSAA season is ~600 programs playing a district double
    round robin plus the full postseason recovery ladder, and that has already
    been played once (at world week 0) and archived. Re-running it on every
    export request blocks the app's single request-handling thread for as long
    as the resimulation takes (minutes), hanging the whole site — the same
    "never rebuild on the request thread" trap as the cache-invalidation
    incidents. Read-only: never creates or advances anything."""
    from app import jhsaa, world as wd

    world = wd.load_world(wd.DEFAULT_SEED)
    if not world:
        raise ExportError("No world exists yet to export a JHSAA season from.")
    world_year = year - wd.BASE_YEAR - 1        # inverse of wd.jhsaa_season_year
    data = wd.get_jhsaa(world["id"], world_year, gender)
    if not data:
        raise ExportError(f"No JHSAA {gender} season was played for {year}.")
    season_year = data.get("season_year", year)
    salt = wd.active_salt(wd.DEFAULT_SEED)

    conn = wd._db()
    try:
        # ‼️ BOTH LEVELS, LABELLED (owner rule 2070 — the JV team and individual
        # events "have become signature events statewide and the JHSAA needs
        # that detail"). This loader used to be varsity-only, and for a reason
        # that still binds: the two seasons share this table, and a JV dual
        # reaching `duals.csv` UNLABELLED corrupts every consumer that derives
        # a phase's shape from its line counts (the 2039 leak — see
        # docs/AAR-jv-duals-leaked-into-the-research-export.md). The
        # precondition that AAR named is now met — every exported dual row
        # carries `level` (plus the JV row's own `shape` and `tied`), the
        # manifest says so, and `analytics/ptc_analytics/aggregate.py` filters
        # on it — so JV rows ride along as DATA rather than as contamination.
        #
        # COALESCE semantics still matter to readers: a season archived before
        # the JV column existed reads back NULL, and those are all varsity.
        rows = conn.execute(
            "SELECT school, opp, home, phase, pf, pa, won, district, lines,"
            " level, tied, shape, tiebreak"
            " FROM world_jhsaa_dual WHERE world_id=? AND year=? AND gender=?"
            " ORDER BY school, rowid",
            (world["id"], world_year, gender)).fetchall()

        # Individual State was added after the original research-export shape.
        # Its draws deliberately live outside `world_jhsaa` (they are large and
        # the ordinary season pages must not deserialize all of them), so reading
        # only that summary silently omitted an event which the site could show.
        # Read the scoped gender plus mixed doubles in one bulk query.  Mixed is
        # shown on both boys' and girls' player histories, but is stored under its
        # own gender because a pair spans both fields.
        individual_rows = conn.execute(
            "SELECT gender, grp, flight, data FROM world_jhsaa_individual"
            " WHERE world_id=? AND year=? AND gender IN (?, 'mixed')"
            " ORDER BY gender, grp, flight",
            (world["id"], world_year, gender)).fetchall()
    finally:
        conn.close()
    # The display calendar the game's own schedule pages show (one date per
    # dual, identical from both sides — world.jhsaa_match_dates). Resolved
    # ONCE here and threaded down, never per row.
    dates = wd.jhsaa_match_dates(world["id"], world_year, gender, season_year)
    schedule_by_school = {}
    for r in rows:
        d = dict(r)
        d["home"] = bool(d["home"])
        d["won"] = bool(d["won"])
        d["district"] = bool(d["district"])
        # ‼️ `level` must reach `jh_match_key`, or every JV row hashes to its VARSITY
        # namesake's key and takes that dual's date — the two seasons genuinely do meet
        # the same opponent in the same phase. It is also what lets a reader separate
        # them at all: a JV row carries no `lines`, which on its own is indistinguishable
        # from a varsity dual whose lines failed to record.
        d["level"] = d.get("level") or "v"
        d["tied"] = bool(d.get("tied"))
        d["lines"] = json.loads(d.pop("lines") or "[]")
        # The deciders of a level Group 2 postseason dual (JHSAA rule 2026-09) —
        # their own field, NEVER folded into `lines`: a 10-point tiebreaker is not
        # a match, and every line-count consumer downstream would count it as one.
        d["tiebreak"] = json.loads(d.pop("tiebreak", None) or "[]")
        played = dates.get(wd.jh_match_key(d))
        d["date"] = played.isoformat() if played else ""
        schedule_by_school.setdefault(d.pop("school"), []).append(d)

    individuals = {}
    for r in individual_rows:
        # Match every other archived JHSAA reader: school renames are applied on
        # read while the persisted bracket remains untouched.
        draw = wd._relabel(json.loads(r["data"]))
        individuals.setdefault(r["gender"], {}).setdefault(r["grp"], {})[
            r["flight"]] = draw

    standings_by_school = {}
    for group_rows in data.get("standings", {}).values():
        for district_rows in group_rows.values():
            for row in district_rows:
                standings_by_school[row["school"]] = row

    teams = {}
    for school in jhsaa.load_schools(gender):
        st = standings_by_school.get(school.name)
        wins, losses = (map(int, st["record"].split("-")) if st else (0, 0))
        dwins, dlosses = (map(int, st["drecord"].split("-")) if st else (0, 0))
        teams[school.key] = SimpleNamespace(
            school=school, roster=jhsaa.build_roster(school, season_year, salt),
            wins=wins, losses=losses, dwins=dwins, dlosses=dlosses,
            district_place=st["place"] if st else None,
            points_for=st["pf"] if st else 0, points_against=st["pa"] if st else 0,
            power=st["pi"] if st else 0.0,
            schedule=schedule_by_school.get(school.name, []))
    return {"teams": teams, "groups": {g: {"state": data.get("brackets", {}).get(g, {})}
                                       for g in jhsaa.GROUPS},
            "awards": data.get("awards", {}), "individuals": individuals,
            # THE COMPUTER-RATINGS LAYER + AT-LARGE COMMITTEE (owner spec
            # 2026-09): archived on the summary blob per group, relabelled on
            # read by `get_jhsaa` like everything else. `.get` — seasons
            # archived before they existed carry no key, and an injected test
            # season need not fake them.
            "ratings": data.get("ratings", {}),
            "committee": data.get("committee", {}),
            # The JV TEAM State Tournament draw — its own table
            # (`world_jhsaa_jv_state`, one row per gender-year), relabelled on
            # read like every JHSAA archive. Its DUALS are ordinary
            # level='jv' phase='jv_state' rows and ride in with the schedule.
            "jv_state": wd.jhsaa_jv_state(world["id"], world_year, gender) or {}}


def build_jhsaa(year: int, gender: str, classification: str = "all", *, season=None) -> dict[str, bytes]:
    """Build JHSAA files. ``season`` is injectable for tests and archive adapters;
    otherwise READ from the persisted archive (see ``_load_archived_jhsaa_season``
    — never resimulated)."""
    from app import jhsaa

    if gender not in jhsaa.GENDERS:
        raise ExportError("JHSAA gender must be girls or boys.")
    valid_classes = {"all", *jhsaa.GROUPS}
    if classification not in valid_classes:
        raise ExportError("Unknown JHSAA classification.")
    season = season or _load_archived_jhsaa_season(year, gender)
    all_teams = list(season["teams"].values())
    selected = [t for t in all_teams if classification == "all" or t.school.group == classification]
    selected_names = {t.school.name for t in selected}
    included_names = selected_names | {d["opp"] for t in selected for d in t.schedule}

    programs, players, standings = [], [], []
    player_lookup = {}
    for team in all_teams:
        s = team.school
        if s.name not in included_names:
            continue
        programs.append({
            "program_id": s.key, "name": s.name, "gender": gender, "city": s.city,
            "locality": s.locality, "county": s.county, "area": s.area,
            "classification": s.classification, "championship_group": s.group,
            "district": s.district, "enrollment": s.enrollment, "private": int(s.private),
            "mascot": s.mascot, "colors_json": json.dumps(s.colors, ensure_ascii=False),
            "scope_member": int(s.name in selected_names),
        })
        if s.name in selected_names:
            standings.append({
                "program_id": s.key, "wins": team.wins, "losses": team.losses,
                "district_wins": team.dwins, "district_losses": team.dlosses,
                "district_place": team.district_place, "points_for": team.points_for,
                "points_against": team.points_against, "toss_power_raw": team.power,
            })
        for p in team.roster:
            pid = p.pid or _player_id(s.name, p.name, {})
            player_lookup[(s.name, p.name)] = pid
            players.append({
                "player_id": pid, "program_id": s.key, "name": p.name,
                "gender": gender, "grade": p.grade, "hometown": p.hometown,
                "country": p.country, "current_grade": p.current_overall(),
                "potential_grade": p.ceiling_overall(), "academic_rating": p.academic_rating,
                "style": p.traits.get("play_style", ""),
            })

    duals, lines, line_players = [], [], []
    # The ARCHIVE path already delivers JV duals inside each school's schedule
    # (one shared table, labelled by `level`). A LIVE `run_season` dict keeps
    # them on the JVTeam objects under season["jv"] instead, so fold those
    # schedules in behind the varsity ones — the archive loader sets no "jv"
    # key, which is what keeps the two paths from double-counting.
    team_by_name = {t.school.name: t for t in all_teams}
    walks = [(t, t.schedule) for t in all_teams]
    walks += [(team_by_name[name], jvt.schedule)
              for name, jvt in (season.get("jv") or {}).items()
              if name in team_by_name]
    for team, schedule in walks:
        for ordinal, dual in enumerate(schedule, 1):
            if not dual.get("home") or not ({team.school.name, dual["opp"]} & selected_names):
                continue                         # each event appears on both cards
            level = dual.get("level") or "v"
            tied = bool(dual.get("tied"))
            key = (f"{year}|{gender}|{team.school.name}|{dual['opp']}|{ordinal}"
                   f"|{dual['phase']}|{level}")
            dual_id = "jhdual:" + hashlib.sha1(key.encode()).hexdigest()[:16]
            duals.append({
                "dual_id": dual_id, "year": year, "gender": gender,
                "home_program_id": team.school.key,
                "away_program_id": next((x.school.key for x in all_teams if x.school.name == dual["opp"]), dual["opp"]),
                "date": dual.get("date") or "",
                # ‼️ `level` must be on the row. The archive loader reads JV and
                # varsity duals together, so without this a JV dual arrives in
                # duals.csv indistinguishable from a varsity one: it inflates
                # the record a reader derives from the schedule (while
                # jhsaa_standings.csv stays varsity-only, so the two disagree),
                # and any consumer that derives a dual's SHAPE by counting its
                # lines averages JV's elastic lineup into the varsity one.
                # "no lines" is not a usable substitute — that is also what a
                # varsity dual whose lines failed to record looks like.
                "level": level,
                # The JV lineup is ELASTIC (`JV_FORMATS`), so a JV row states its
                # shape ("2S/2D") outright; a varsity row leaves it empty — its
                # shape is a function of phase + classification. And an
                # even-court JV dual can genuinely TIE (the association's only
                # ties): `tied=1` and NO winner, rather than inventing one.
                "shape": dual.get("shape") or "",
                "tied": int(tied),
                # A LEVEL varsity postseason dual settled by the deciders (Group 2's
                # 3S/3D, JHSAA rule 2026-09): points read 3-3 and `winner_program_id`
                # names who won the three 10-point tiebreakers. Flagged so a reader
                # does not mistake the level score for a tie.
                "decided_on_tiebreak": int(bool(dual.get("tiebreak"))),
                "phase": dual["phase"], "district": int(bool(dual.get("district"))),
                "home_points": dual["pf"], "away_points": dual["pa"],
                "winner_program_id": "" if tied else (team.school.key if dual["won"] else next((x.school.key for x in all_teams if x.school.name == dual["opp"]), dual["opp"])),
            })
            for line_no, line in enumerate(dual.get("lines", []), 1):
                line_id = f"{dual_id}:{line_no}"
                lines.append({"line_id": line_id, "dual_id": dual_id, "slot": line["slot"],
                              "score": line["score"], "home_won": int(bool(line["home_won"]))})
                for side, school in (("home", team.school.name), ("away", dual["opp"])):
                    for pos, name in enumerate(line.get(side, []), 1):
                        line_players.append({"line_id": line_id, "side": side, "position": pos,
                                             "player_id": _player_id(school, name, player_lookup), "player_name": name})

    # PROGRAM HISTORY — the multi-year ledger the app's program pages show
    # (`world.jhsaa_school_history`), which the zip never carried: the export
    # used to be a single-season snapshot only, so "the zip has no program
    # history" and "the app shows it fine" were both true. One row per program
    # per ARCHIVED season (all years, not just this export's scope year —
    # history is the point), read off the persisted archive in one bulk pass,
    # never resimulated. Empty when no archive exists (injected seasons/tests).
    history = []
    from app import world as wd
    w = wd.load_world(wd.DEFAULT_SEED)
    if w:
        key_by_name = {t.school.name: t.school.key for t in all_teams}
        for school, rows_ in sorted(wd.jhsaa_history_rows(w["id"], gender).items()):
            if school not in included_names:
                continue
            for r in rows_:
                history.append({
                    "program_id": key_by_name.get(school, school),
                    "program_name": school,
                    "season_year": r.get("season_year") or "",
                    "world_year": r["year"],
                    "classification": r["group"], "district": r["district"],
                    "record": r["record"], "district_record": r["district_record"],
                    "district_place": r["place"],
                    "district_title": int(r["district_title"]),
                    "courts_won": r["courts_won"], "courts_lost": r["courts_lost"],
                    "toss_power_raw": r["pi"] if r["pi"] is not None else "",
                    "class_rank": r["state_rank"],
                    "made_state": int(r["made_state"]), "state_seed": r["seed"],
                    "state_place": r["state_place"], "state_finish": r["state_finish"],
                    "state_champion": int(r["champion"]),
                    "made_toc": int(r["made_toc"]), "toc_place": r["toc_place"],
                    "toc_finish": r["toc_finish"],
                    "toc_champion": int(r["toc_champion"]),
                    "unit_wins": "; ".join(r["unit_wins"]),
                    "honors": "; ".join(r["honors"]),
                })

    json_files = {
        "jhsaa_championships.json": {g: season["groups"][g].get("state", {}) for g in jhsaa.GROUPS},
        "jhsaa_awards.json": season.get("awards", {}),
        # Keep the draw's native archive representation: entries, rounds,
        # champion/runner-up indices and match scorelines are all research data.
        # Gender remains an outer key so mixed doubles cannot be mistaken for a
        # boys- or girls-only flight.  Classification scope applies just as it
        # does to the team championship JSON.
        "jhsaa_individuals.json": {
            draw_gender: {
                # ‼️ "ALL" survives every scope: the JV Singles/JV Doubles
                # tournaments (flights JVS/JVD + their qualifying draws) are
                # STATEWIDE AND CLASSLESS, archived under group "ALL" — a value
                # no classification can collide with — so a class-scoped export
                # that filtered on the class alone silently dropped two state
                # championships (the known group-scoped-reader trap).
                group: flights for group, flights in groups.items()
                if classification == "all" or group in (classification, "ALL")
            }
            for draw_gender, groups in season.get("individuals", {}).items()
        },
        # The JV TEAM State Tournament (owner rule 2070 — a signature event, in
        # the export like the varsity brackets): the archived draw itself —
        # regions, region champions, the state field/rounds in the varsity
        # bracket shape. Classless and statewide, so classification scope does
        # not cut it. Its duals are the level='jv' phase='jv_state' rows in
        # duals.csv. Empty when the season predates the event (JV_STATE_FROM).
        "jhsaa_jv_state.json": season.get("jv_state") or {},
        # THE AT-LARGE COMMITTEE (owner spec 2026-09): the full archived
        # selection per 48-team group — ballots, ranges, Borda (bubble and
        # seeding), locks, automatic bids, statuses and the published member
        # weights. None/absent for the ten groups without a committee and for
        # seasons archived before it existed.
        "jhsaa_committee.json": {
            g: sel for g, sel in (season.get("committee") or {}).items()
            if sel and (classification == "all" or g == classification)
        },
    }

    # THE COMPUTER-RATINGS LAYER (owner spec 2026-09): one row per
    # (championship_group, program) — the nine system ranks AND raw values,
    # the composite (mean/median/sigma), the published SOR benchmark and the
    # disconnected flag. Joined on program_id like every other table (display
    # names repeat across renames; ids do not). Archived seasons predating the
    # layer simply emit an empty table.
    from app.jhsaa_ratings import SYSTEMS as _rating_systems
    name_to_id = {t.school.name: t.school.key for t in all_teams}
    computer_ratings = []
    for group, layer in sorted((season.get("ratings") or {}).items()):
        if not layer or (classification != "all" and group != classification):
            continue
        for name, t in sorted((layer.get("teams") or {}).items()):
            row = {"program_id": name_to_id.get(name, ""), "name": name,
                   "gender": gender, "championship_group": group,
                   "record": t.get("record", ""),
                   "district": t.get("district", ""),
                   "mean_rank": t.get("mean", ""),
                   "median_rank": t.get("median", ""),
                   "sigma": t.get("sigma", ""),
                   "disconnected": int(bool(layer.get("disconnected"))),
                   "sor_bench": layer.get("sor_bench", "")}
            for s in _rating_systems:
                row[f"rank_{s}"] = (t.get("ranks") or {}).get(s, "")
                row[f"value_{s}"] = (t.get("values") or {}).get(s, "")
            computer_ratings.append(row)

    tables = {"programs.csv": programs, "players.csv": players, "duals.csv": duals,
              "lines.csv": lines, "line_players.csv": line_players,
              "jhsaa_standings.csv": standings,
              "jhsaa_computer_ratings.csv": computer_ratings,
              "jhsaa_program_history.csv": history}
    files = {name: _csv(rows) for name, rows in tables.items()}
    files.update({name: json.dumps(value, indent=2, ensure_ascii=False, default=str).encode()
                  for name, value in json_files.items()})
    manifest = {
        "format": "play-to-clinch-research-export", "format_version": 1,
        "dataset_family": "jhsaa", "scope": {"year": year, "gender": gender,
        "classification": classification}, "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {name: {"media_type": "text/csv" if name.endswith(".csv") else "application/json",
                          "rows": len(tables[name]) if name in tables else None} for name in files},
        "rating_semantics": {
            "current_grade": "Current visible tennis ability on the game's 20-80 scouting scale.",
            "potential_grade": "Hidden ceiling on the same 20-80 scale; included for unrestricted research.",
            "toss_power_raw": "JHSAA opponent-adjusted team power used for selection/seeding; compare only within this season and gender."
        },
        "domain_rules": ["JHSAA gender values are girls/boys (college uses women/men).",
            "jhsaa_individuals.json contains the archived Individual State brackets "
            "for this gender plus mixed doubles. Its outer keys are gender, then "
            "classification, then flight (S1-S3, D1-D3, or XD); mixed is stored "
            "separately because each pair contains one boy and one girl.",
            "jhsaa_program_history.csv spans EVERY archived season for this gender (one row "
            "per program per year — the app's program-history ledger), not just this export's "
            "scope year; it is empty only when the save has no archived seasons.",
            "duals.level is 'v' for varsity and 'jv' for the JV season; they share a "
            "schedule table, so a consumer that wants one must filter on it. JV duals ARE "
            "included (the JV season, its Showcase, and the JV Team State Tournament at "
            "phase='jv_state'); jhsaa_standings.csv and every rating stay varsity-only, so "
            "filter level='v' before deriving varsity records. Absent on seasons exported "
            "before the JV season existed, where every dual is varsity.",
            "duals.shape states a JV dual's elastic lineup ('2S/2D'); varsity rows leave it "
            "empty because their shape is a function of phase and classification. duals.tied "
            "marks the association's only drawn results (even-court JV duals); a tied dual "
            "has no winner_program_id. duals.decided_on_tiebreak marks a LEVEL varsity "
            "postseason dual (Group 2's 3S/3D road) whose winner was decided on three "
            "concurrent 10-point tiebreakers — its points are level and it is NOT a tie.",
            "jhsaa_jv_state.json is the JV Team State Tournament: the twenty geographic-area "
            "regional championships and the statewide classless bracket their champions play. "
            "jhsaa_individuals.json carries the JV Singles/JV Doubles state draws (flights "
            "JVS/JVD, qualifying QJVS/QJVD) under classification key 'ALL' — statewide and "
            "classless, kept in every classification scope.",
            "duals.date is the game's own display calendar (world.jhsaa_match_dates — one date "
            "per dual, identical from both sides); empty on seasons archived before dates existed. "
            "It is the play order: there is no clock inside a JHSAA season.",
            "jhsaa_computer_ratings.csv is the nine-system computer-ratings layer (Colley, "
            "Bradley-Terry, Win%, Massey dual, SRS, Massey game, Set share, SOR, Elo) plus the "
            "composite mean/median/sigma of the system RANKS, per championship_group — fitted "
            "on same-group varsity duals only, margins format-normalised, State/TOC excluded. "
            "sor_bench is the published SOR benchmark (median Bradley-Terry rating of the "
            "group's ranks 9-16); disconnected=1 means the group's schedule graph was not one "
            "component and the least-squares systems (Massey dual/game, SRS) were withheld. "
            "Parallel to TOSS/ATR — it feeds neither. Empty on seasons archived before the "
            "layer existed.",
            "jhsaa_committee.json is the at-large selection committee for the 48-team groups "
            "(7A and Group 1): the five members' full ballots and published weights, the "
            "per-member at-large ranges, locks, automatic bids (district champions who missed "
            "the road), bubble and seeding Borda totals, statuses, and the sixteen selections "
            "in seed order 33-48. The road's 32 qualifiers are unchanged; an at-large is never "
            "seeded above 33. Their State bracket opens with the Parastate (17v48..32v33) in "
            "jhsaa_championships.json, its duals ordinary phase='state' rows in duals.csv.",
            "Regular duals use 3 singles/4 doubles; early-window dates use 5/2; showcases and postseason use 1/4. "
            "7A, 8A, 9A and Group 1 play 4S/5D on the road to State and in the early window.",
            "Every court finishes. JHSAA has no clinch abandonment.",
            "1A crowns from a 24-team field on a fixed recovery shape (Super Regional/"
            "Semi-State/Divisional/Semi-Conference/Conference all award direct State "
            "berths, unlike the other classes' dynamic ladder). Every other class, 2A "
            "included since the 2033 realignment, crowns from 40 on the dynamic ladder. "
            "The eight Zonal champions are automatic State berths, seeded 1-8, in every "
            "class and under both shapes.",
            "Programs and rosters reflect the CURRENT association config (renames/sponsorship/"
            "play-up as they stand today), applied to the archived season's own results and "
            "roster year — a school that has since stopped sponsoring tennis or been renamed "
            "may not line up with an older archived year."],
        "college_plan": {"status": "available", "note": "Use dataset_family=college for D1-D4 seasons."},
    }
    manifest["files"].update({
        "manifest.json": {"media_type": "application/json", "rows": None},
        "README.md": {"media_type": "text/markdown", "rows": None},
    })
    files["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    files["README.md"] = (f"# Play to Clinch research export\n\n**Family:** JHSAA  \n**Scope:** {year} {gender}, {classification}\n\n"
        "Start with `manifest.json`. Shared entity tables are `programs`, `players`, `duals`, `lines`, and `line_players`; "
        "JHSAA-only standings, awards, team championships, and individual championship brackets remain separate rather than being forced into a college schema.\n").encode()
    return files


DIVISIONS = {"D1", "D2", "D3", "D4"}
COLLEGE_GENDERS = {"men", "women"}


def build_college(year: int, division: str, gender: str, *, season_id: int | None = None) -> dict[str, bytes]:
    """Build college files from an already-played season. ``season_id`` is
    injectable for tests (a season played by the ``played_season``-style
    fixtures); otherwise resolved READ-ONLY from the current world — this never
    creates or advances a season (see ONE WORLD PER SAVE / seed-vs-year rules).

    Player and program fields reflect the CURRENT roster/program config
    (``ncaa.build_roster``), the same convention every season/dual detail page
    in the app already uses to label historical box scores — not a per-season
    historical snapshot. Results (duals/lines) are the actual season archive.
    """
    from app import ncaa, seasonmode as sm, world as wd, rankings_archive, economy

    if division not in DIVISIONS:
        raise ExportError("College division must be D1, D2, D3, or D4.")
    if gender not in COLLEGE_GENDERS:
        raise ExportError("College gender must be men or women.")

    if season_id is None:
        world = wd.load_world(wd.DEFAULT_SEED)
        if not world:
            raise ExportError("No world exists yet to export a college season from.")
        seed = wd.year_seed(world["seed"], year - wd.BASE_YEAR)
        season_id = sm.find_season(division, gender, seed=seed)
        if season_id is None:
            raise ExportError(f"No {division} {gender} season was played for {year}.")

    season = sm.load_season(season_id)
    if not season:
        raise ExportError("That season id does not exist.")

    div = ncaa.load_division(division, gender)

    programs, players, standings, scholarships = [], [], [], []
    for prog in div.programs:
        programs.append({
            "program_id": prog.key, "name": prog.school, "division": division, "gender": gender,
            "conference": prog.conf, "conference_abbr": prog.conf_abbr, "city": prog.city,
            "state": prog.state, "region": prog.region, "prestige": prog.prestige,
            "academics": prog.academics, "facilities": prog.facilities, "autobid": int(prog.autobid),
        })
        roster = ncaa.build_roster(prog)
        for p in roster:
            players.append({
                "player_id": p.pid, "program_id": prog.key, "name": p.name, "gender": gender,
                "country": p.country, "class_year": p.class_year, "hometown": p.hometown,
                "high_school": p.high_school, "walk_on": int(p.walk_on),
                "scholarship_fraction": p.scholarship,
                "scholarship_label": economy.fraction_label(p.scholarship),
                "academic_rating": p.academic_rating, "recruit_stars": p.recruit_stars,
                "recruit_tier": p.recruit_tier, "current_grade": p.current_overall(),
                "potential_grade": p.ceiling_overall(),
            })
        result = sm.season_program_result(season_id, prog.school)
        if result:
            standings.append({
                "program_id": prog.key, "conference": result["conf"], "wins": result["wins"],
                "losses": result["losses"], "reg_season_conf_champ": int(result["reg_conf_champ"]),
                "conf_tournament_champ": int(result["ct_champ"]), "ncaa_finish": result["ncaa"] or "",
                "ita_indoor_finish": result["ita"] or "", "national_champ": int(result["national_champ"]),
                "regional_champ": int(result["regional_champ"]),
            })
        budget = economy.budget_summary(roster, division, gender)
        scholarships.append({"program_id": prog.key, **budget})

    # duals/lines: each dual is shared by both sides' schedules (one row IS the
    # dual for both teams), so dedupe on id — same idiom the JHSAA export uses
    # to dedupe on the home side.
    seen_ids, duals, lines, line_players = set(), [], [], []
    for prog in div.programs:
        for row in sm.team_schedule(season_id, prog.school):
            if row["status"] != "final" or row["id"] in seen_ids:
                continue
            seen_ids.add(row["id"])
            home_prog, away_prog = div.by_school(row["home"]), div.by_school(row["away"])
            dual_id = f"ncdual:{row['id']}"
            duals.append({
                "dual_id": dual_id, "year": year, "division": division, "gender": gender,
                "week": row["week"], "round": row["round"], "conf_or_round_name": row["conf"],
                "is_conference": row["is_conf"],
                "home_program_id": home_prog.key if home_prog else row["home"],
                "away_program_id": away_prog.key if away_prog else row["away"],
                "home_points": row["home_points"], "away_points": row["away_points"],
                "winner_program_id": ((home_prog.key if home_prog else row["home"]) if row["winner"] == 0
                                      else (away_prog.key if away_prog else row["away"])),
            })
            for line in json.loads(row["lines_json"] or "[]"):
                if not line.get("completed"):
                    continue
                line_id = f"{dual_id}:{line['slot']}"
                lines.append({"line_id": line_id, "dual_id": dual_id, "slot": line["slot"],
                              "home_games": line.get("home_games"), "away_games": line.get("away_games"),
                              "home_won": int(bool(line.get("home_won")))})
                if line["slot"].startswith("S"):
                    entries = [("home", line.get("home_pid"), line.get("home_player")),
                              ("away", line.get("away_pid"), line.get("away_player"))]
                else:
                    entries = [(side, pid, None) for side in ("home", "away")
                              for pid in line.get(f"{side}_pids", [])]
                for side, pid, name in entries:
                    if pid:
                        line_players.append({"line_id": line_id, "side": side,
                                             "player_id": pid, "player_name": name or ""})

    rankings = []
    for which in ("teams", "singles", "doubles"):
        try:
            rankings.extend({**row, "board": which} for row in
                            rankings_archive.board(year, division, gender, which))
        except Exception:
            pass    # not archived for this year/division/gender — leave it out, not an error

    json_files = {}
    tables = {"programs.csv": programs, "players.csv": players, "duals.csv": duals,
              "lines.csv": lines, "line_players.csv": line_players,
              "college_standings.csv": standings, "college_scholarships.csv": scholarships,
              "college_rankings.csv": rankings}
    files = {name: _csv(rows) for name, rows in tables.items()}
    manifest = {
        "format": "play-to-clinch-research-export", "format_version": 1,
        "dataset_family": "college", "scope": {"year": year, "division": division, "gender": gender},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {name: {"media_type": "text/csv" if name.endswith(".csv") else "application/json",
                          "rows": len(tables[name]) if name in tables else None} for name in files},
        "rating_semantics": {
            "current_grade": "Current visible tennis ability on the game's 20-80 scouting scale.",
            "potential_grade": "Hidden ceiling on the same 20-80 scale; included for unrestricted research.",
            "scholarship_fraction": "Equivalency fraction of a full scholarship (app.economy); 0 for walk-ons.",
        },
        "domain_rules": [
            "College gender values are men/women (JHSAA uses girls/boys).",
            "duals.round is REG (regular season), CT (conference tournament), NCAA (postseason), "
            "ITAK/ITAI (fall ITA Kickoff/Indoor). conf_or_round_name holds the conference for REG/CT "
            "and the round name (e.g. 'Round of 16') for NCAA.",
            "player/program fields reflect the roster as currently built, not a frozen per-season "
            "snapshot — a player who has since transferred or graduated may not appear in players.csv "
            "even though they appear in duals from this season.",
            "college_rankings.csv is empty unless this (year, division, gender) has an archived CTA "
            "rankings snapshot (stamped at conference-tournament completion each season).",
        ],
    }
    manifest["files"].update({
        "manifest.json": {"media_type": "application/json", "rows": None},
        "README.md": {"media_type": "text/markdown", "rows": None},
    })
    files["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False).encode()
    files["README.md"] = (f"# Play to Clinch research export\n\n**Family:** College  \n**Scope:** {year} {division} {gender}\n\n"
        "Start with `manifest.json`. Shared entity tables are `programs`, `players`, `duals`, `lines`, and "
        "`line_players`; college-only standings, scholarships, and rankings remain separate rather than "
        "being forced into a JHSAA schema.\n").encode()
    return files


def build_underplayed(year: int, gender: str, classification: str = "all") -> dict[str, bytes]:
    """The transfer-candidates export: every 9th/10th grader in the archived
    `year` season with under a dozen matches, best OVR first — the input an
    analysis agent turns into the `player_id, destination` pairs the batch
    importer (`/jhsaa/transfers` paste panel, `scripts/jhsaa_transfers_import.py`)
    accepts. READ off the archive + deterministic roster rebuild, never
    re-simulated; read-only like every export here."""
    from app import world as wd

    world = wd.load_world(wd.DEFAULT_SEED)
    if not world:
        raise ExportError("No world exists yet to export candidates from.")
    board = wd.jhsaa_underplayed(world["id"], gender,
                                 wd.active_salt(wd.DEFAULT_SEED), season_year=year)
    if board["season_year"] is None:
        raise ExportError(f"No JHSAA {gender} season was played for {year}.")
    rows = board["rows"]
    if classification != "all":
        rows = [r for r in rows if r["group"] == classification]
    csv_rows = [{"player_id": r["pid"], "name": r["name"], "school": r["school"],
                 "classification": r["group"], "grade": r["grade"],
                 "ladder": r["ladder"], "ovr": r["ovr"], "str": r["str"],
                 "matches": r["matches"], "season_year": year}
                for r in rows]
    readme = f"""# Play to Clinch — JHSAA transfer candidates ({year} {gender})

Every 9th and 10th grader on a {year} roster who played fewer than 12 matches,
sorted best-OVR first. `matches` counts every archived line appearance (singles
or doubles); 0 means they never took a court. `ladder` is their seat on their
own team's ability ladder that season.

To move players: produce lines of `player_id, destination school` (destination
must be a JHSAA program of the same gender, exact display name) and either
paste them into the Batch import panel on /jhsaa/transfers or run
`python3 scripts/jhsaa_transfers_import.py moves.csv --apply`. Moves are
effective the NEXT season ({year + 1}) and are validated row by row — an
invalid row is reported and skipped, never silently dropped.
"""
    tables = {"underplayed_candidates.csv": csv_rows}
    manifest = {
        "format": "play-to-clinch-research-export", "format_version": 1,
        "dataset_family": "underplayed",
        "scope": {"year": year, "gender": gender, "classification": classification},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {
            "underplayed_candidates.csv": {"media_type": "text/csv", "rows": len(csv_rows)},
            "manifest.json": {"media_type": "application/json", "rows": None},
            "README.md": {"media_type": "text/markdown", "rows": None},
        },
        "domain_rules": [
            "This is a candidate list, not a full season bundle — it has no "
            "programs/players/duals tables of its own.",
        ],
    }
    return {"underplayed_candidates.csv": _csv(csv_rows),
            "manifest.json": json.dumps(manifest, indent=2, ensure_ascii=False).encode(),
            "README.md": readme.encode()}


BUILDERS = {"jhsaa": build_jhsaa, "college": build_college,
            "underplayed": build_underplayed}


def export_zip(family: str, **scope) -> io.BytesIO:
    if family not in BUILDERS:
        raise ExportError(f"The {family} exporter is planned but not available yet.")
    files = BUILDERS[family](**scope)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    out.seek(0)
    return out


def export_zip_bulk(family: str, *, years: list[int], genders: list[str],
                     **scope) -> tuple[io.BytesIO, dict]:
    """Bundle several (year, gender) scopes of one family into ONE zip, each
    under its own ``<year>/<gender>/`` folder, reusing the same per-scope
    builders as ``export_zip`` (still a pure READ off the persisted archive —
    no season is created or resimulated). Meant for backing up a save's whole
    history in one download instead of one request per year/gender.

    A (year, gender) with nothing archived is SKIPPED, not fatal — an early
    save year may predate a feature (JV, individual state) or simply never
    have been played for one gender, and the point of a bulk backup is to grab
    everything that exists, not to abort on the first gap. Every skip is
    recorded in the returned summary so the user can see what's missing rather
    than silently losing seasons the way a lost original archive already did.
    """
    if family not in BUILDERS:
        raise ExportError(f"The {family} exporter is planned but not available yet.")
    builder = BUILDERS[family]
    included, skipped = [], []
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for year in years:
            for gender in genders:
                try:
                    files = builder(year=year, gender=gender, **scope)
                except ExportError as exc:
                    skipped.append({"year": year, "gender": gender, "reason": str(exc)})
                    continue
                for name, data in files.items():
                    zf.writestr(f"{year}/{gender}/{name}", data)
                included.append({"year": year, "gender": gender})
        summary = {
            "format": "play-to-clinch-research-export-bulk", "format_version": 1,
            "dataset_family": family, "scope": scope,
            "years": years, "genders": genders,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "included": included, "skipped": skipped,
            "note": "Each included (year, gender) is a complete standalone bundle "
                    "under <year>/<gender>/ — same files export_zip would have "
                    "produced for that scope alone, manifest.json and README.md "
                    "included. 'skipped' lists scopes with nothing archived.",
        }
        zf.writestr("bulk_manifest.json", json.dumps(summary, indent=2, ensure_ascii=False).encode())
    out.seek(0)
    return out, summary

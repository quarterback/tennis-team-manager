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


def _record_parts(record: str) -> tuple[int, int, int]:
    """Read the archive's ``W-L`` or ``W-L-T`` record representation."""
    try:
        parts = tuple(map(int, record.split("-")))
    except (AttributeError, ValueError) as exc:
        raise ExportError(f"Invalid archived JHSAA record: {record!r}.") from exc
    if len(parts) == 2:
        return parts[0], parts[1], 0
    if len(parts) == 3:
        return parts
    raise ExportError(f"Invalid archived JHSAA record: {record!r}.")


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
    # CAPTAINS (owner rule 2026-09) — read off the archive
    # (`world_jhsaa_standing`, the row `jhsaa.team_standing` writes), never
    # re-derived: `pick_captains` reads the ladder as it stood at team-build time
    # and a rebuilt roster cannot reproduce that. Keyed by the school's display
    # name at archive time, exactly as the program page reads it. Empty for a
    # season archived before captains existed.
    # ‼️ KEYED BY THE NAME AT ARCHIVE TIME, so it is relabelled into today's names
    # here (`jhsaa.current_name`, the `_relabel` rule) — read raw, every program
    # renamed since that season exports its captains as nobody. And a season
    # archived BEFORE captains existed yields an EMPTY map: that is "unknown",
    # not "no captains", so `captains` stays None on every team and the column
    # is left blank rather than written as 0.
    raw_caps = wd.jhsaa_captains(world["id"], world_year, gender)
    captains = ({jhsaa.current_name(k, gender): v for k, v in raw_caps.items()}
                if raw_caps else None)
    # ‼️ THE BOX SCORE IS ON THE HOME ROW ONLY (world `_archive_lines`). This
    # query already fetches BOTH rows of every dual, so the counterpart is in
    # hand — index the home rows once and let the away rows read across. Keyed on
    # `jh_match_key`, the same tuple from either side. A pre-dedup archive keeps
    # its own copy on both rows and never consults this.
    home_lines = {wd.jh_match_key(dict(r)): r["lines"] for r in rows if r["home"]}
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
        d["lines"] = wd.unpack_lines(d.pop("lines")) or wd.unpack_lines(
            home_lines.get(wd.jh_match_key(d)))
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
        wins, losses, ties = _record_parts(st["record"]) if st else (0, 0, 0)
        dwins, dlosses, _ = _record_parts(st["drecord"]) if st else (0, 0, 0)
        teams[school.key] = SimpleNamespace(
            school=school, roster=jhsaa.build_roster(school, season_year, salt),
            wins=wins, losses=losses, ties=ties, dwins=dwins, dlosses=dlosses,
            district_place=st["place"] if st else None,
            points_for=st["pf"] if st else 0, points_against=st["pa"] if st else 0,
            power=st["pi"] if st else 0.0,
            captains=(None if captains is None
                      else list(captains.get(school.name) or ())),
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
    injected = season is not None
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
                "ties": getattr(team, "ties", 0),
                "district_wins": team.dwins, "district_losses": team.dlosses,
                "district_place": team.district_place, "points_for": team.points_for,
                "points_against": team.points_against, "toss_power_raw": team.power,
            })
        # Who wore the C: `TeamSeason.captains` on a live season, the archived
        # standing row on the archive path (both are pids, best-known first).
        # Until now this lived only on the program page's roster chip, so an
        # analyst reading the zip could not tell a captain from anybody else.
        # None means the season carries no captain data at all (archived before
        # captains existed): both columns stay blank. A list — even an empty one —
        # is a known answer and writes 0/1.
        caps = getattr(team, "captains", None)
        known = caps is not None
        caps = list(caps or ())
        for p in team.roster:
            pid = p.pid or _player_id(s.name, p.name, {})
            player_lookup[(s.name, p.name)] = pid
            players.append({
                "player_id": pid, "program_id": s.key, "name": p.name,
                "gender": gender, "grade": p.grade, "hometown": p.hometown,
                "country": p.country, "current_grade": p.current_overall(),
                # `potential_grade` is what the program SHOWS — the staff's estimate
                # of the ceiling (`jhsaa.pot_display`), which converges on the true
                # value with time and participation; `ceiling_grade` is the fixed
                # hidden ceiling itself (the pinned generation value). A drop in
                # potential_grade season to season is the estimate correcting,
                # never the player losing anything — ceiling_grade never moves.
                "potential_grade": jhsaa.pot_display(p),
                "ceiling_grade": p.ceiling_overall(), "academic_rating": p.academic_rating,
                "style": p.traits.get("play_style", ""),
                "style_trait": p.traits.get("style_trait", "none"),
                "captain": int(pid in caps) if known else "",
                "captain_order": caps.index(pid) + 1 if pid in caps else "",
                # The GENERATED older sibling's player_id (`jhsaa.sibling_link`),
                # blank for most rows. Authored families are not exported here.
                "sibling_id": (getattr(p, "jhsaa", None) or {}).get("sibling", ""),
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
                # an even-court dual can genuinely TIE (JV, or a varsity showcase
                # on Group 2's format): `tied=1` and NO winner, rather than inventing one.
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
        # THE AT-LARGE COMMITTEE (owner spec 2026-09, expanded 2026-09): the
        # full archived selection per Parastate group — ballots, ranges, Borda
        # (bubble and seeding), locks, automatic bids, statuses and the
        # published member weights. Absent for the groups without a committee
        # (none since the 2080 expansion put Group 2 and Group 3 on a committee
        # too) and for seasons archived before it existed.
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

    # THE PROGRAM COEFFICIENT (owner spec 2026-09): the nine-season UEFA-style
    # standing as of THIS export's season — road-round wins and the State finish
    # only, ranked within the championship_group the program plays in today.
    # Read off the same memo the /jhsaa/coefficient page uses (a pure fold over
    # the archive, never resimulated). ‼️ ARCHIVE PATH ONLY: an injected season
    # is not in the archive the fold reads, so the table is empty for it — keyed
    # on `injected`, never on "a world exists", or a fixture run beside a real
    # save would package coefficient data from an unrelated persisted archive.
    # The export's `year` is the SEASON year, so it is mapped back to the
    # archive's world-year exactly as the season loader does.
    from app import jhsaa_coefficient as _coef
    coefficient_rows = []
    if not injected and w:
        # ‼️ ONLY PROGRAMS WITH A programs.csv ROW. `ranked()` keeps a program that
        # has since stopped sponsoring this gender (its archive is still real), but
        # programs.csv is `all_teams` — current sponsors — so its id would have no
        # entity row to join. Filter to the entity table and RE-RANK within the
        # group among those, the `percentiles()` rule (the page still lists the
        # former program; a normalised consumer must not have a dangling id).
        ident_to_id = {t.school.ident: t.school.key for t in all_teams}
        world_year = year - wd.BASE_YEAR - 1        # inverse of wd.jhsaa_season_year
        standing = _coef.ranked(w["id"], gender, as_of=world_year)
        for group, rows_ in sorted(standing["groups"].items()):
            if classification != "all" and group != classification:
                continue
            live = [r for r in rows_ if r["school"] in ident_to_id]   # already ranked
            for rank, r in enumerate(live, start=1):
                coefficient_rows.append({
                    "program_id": ident_to_id[r["school"]],
                    "program_name": r["name"], "gender": gender,
                    "championship_group": group, "rank": rank,
                    "coefficient": r["coefficient"],
                    "trend": r.get("trend", 0.0),
                    "season_points": r["points"],
                    "seasons_of_history": r["seasons"],
                    "bootstrap": int(bool(r["bootstrap"])),
                    "as_of_world_year": standing["as_of"],
                    "window_world_years": " ".join(str(y) for y in standing["years"]),
                    "breakdown_json": json.dumps(
                        [[y, pts, wt] for y, pts, wt in r["breakdown"]]),
                })

    # FLIGHT EFFICIENCY (owner request 2026-09): the /jhsaa/flights table —
    # one row per program and flight, actual vs expected win rate. The SAME
    # fold the page runs (`world.flight_efficiency_fold`), answered off the
    # rosters and lines THIS BUNDLE HAS ALREADY BUILT — never
    # `jhsaa_flight_efficiency`, whose ~20 s roster rebuild is keyed per
    # (year, gender) and cannot be shared across a bulk export's scopes: 120
    # scopes would have added ~40 minutes to one POST. So it costs the fold
    # alone, and an injected season carries rows like an archived one. The fit
    # runs over EVERY varsity dual of the gender (the whole season's curve),
    # then the rows are cut to the classification scope. `held_most_by_ids`
    # carries the holder's player_id(s) beside the display string, since a
    # name is not a join key.
    roster_ovr: dict[str, dict | None] = {}

    def _ovr_of(name: str) -> dict | None:
        if name not in roster_ovr:
            t = team_by_name.get(name)
            roster_ovr[name] = ({p.name: p.current_overall() for p in t.roster}
                                if t is not None else None)
        return roster_ovr[name]

    def _varsity_home_duals():
        for t in all_teams:
            for d in t.schedule:
                if d.get("home") and (d.get("level") or "v") == "v":
                    yield t.school.name, d["opp"], d.get("lines") or []

    name_to_group = {t.school.name: t.school.group for t in all_teams}
    fe = wd.flight_efficiency_fold(_varsity_home_duals(), _ovr_of)
    flight_rows = []
    for r in sorted(fe["rows"], key=lambda r: (r["school"], r["slot"])):
        t = team_by_name.get(r["school"])
        if t is None:
            continue
        if classification != "all" and t.school.group != classification:
            continue
        flight_rows.append({
            "program_id": t.school.key, "program_name": r["school"], "gender": gender,
            "championship_group": name_to_group.get(r["school"], ""),
            "slot": r["slot"], "matches": r["n"], "wins": r["wins"],
            "actual_pct": round(r["actual"], 2), "expected_pct": round(r["expected"], 2),
            "delta_pct": round(r["delta"], 2),
            "held_most_by": r["top"],
            "held_most_by_ids": " / ".join(_player_id(r["school"], nm, player_lookup)
                                           for nm in r["top_names"]),
            "held_most_matches": r["top_n"],
        })
    # ‼️ The slots ADVERTISED are the slots EMITTED: 5S/2D, 3S/4D, 1S/4D, 2S/3D
    # and 4S/5D all reach this table, so a typed "S1..D4" would have told a
    # consumer to drop S5 and D5 on a real export.
    flight_slots = sorted({r["slot"] for r in flight_rows},
                          key=lambda x: (x[0] != "S", int(x[1:]) if x[1:].isdigit() else 0, x))

    # THE JV TEAM STATE TOURNAMENT, FLAT (owner rule 2026-09 — "make sure the
    # data gets exported … as well as analytic for future analysis"): one row
    # per team in the State field, in seed order, with how it entered
    # (regional champion / at-large), the JV and varsity regular-season records
    # and the 30/70 selection index the at-larges were picked on, and how far
    # it went — read off the SAME archived bracket the JSON carries, through
    # the shared `jhsaa_state_result`, so the two files cannot disagree. A
    # season archived at twenty (before `jhsaa.jv_parastate_era`) has no
    # `selection` table; its champions are still listed off `ranked`, with the
    # index columns empty, so the file exists for every JV State season and an
    # analysis across the expansion joins on one shape. Classless and
    # statewide, so classification scope does not cut it.
    from app import jhsaa as _jh
    jv_state_rows = []
    jv_ev = season.get("jv_state") or {}
    if jv_ev.get("state"):
        st_ = jv_ev["state"]
        key_by_name = {t.school.name: t.school.key for t in all_teams}
        region_of_ = {v: k for k, v in (jv_ev.get("region_champions") or {}).items()}
        sel_ = jv_ev.get("selection") or [
            {"school": nm, "entry": "champion", "region": region_of_.get(nm, "")}
            for nm in (jv_ev.get("ranked") or st_.get("field") or ())]
        for seed_, r in enumerate(sel_, start=1):
            nm = r["school"]
            res = wd.jhsaa_state_result(st_, nm)
            jv_state_rows.append({
                "program_id": key_by_name.get(nm, nm), "program_name": nm,
                "gender": gender, "seed": seed_, "entry": r.get("entry", ""),
                "region": r.get("region", ""),
                "jv_wins": r.get("jv_wins", ""), "jv_losses": r.get("jv_losses", ""),
                "jv_ties": r.get("jv_ties", ""), "jv_pct": r.get("jv_pct", ""),
                "varsity_reg_wins": r.get("v_wins", ""),
                "varsity_reg_losses": r.get("v_losses", ""),
                "varsity_reg_pct": r.get("v_pct", ""),
                "selection_index": r.get("index", ""),
                "made_main_draw": int(res["finish"] != _jh.PARASTATE_NAME),
                "state_place": res["place"], "state_finish": res["finish"],
                "champion": int(bool(res["champion"]))})
    # INDIVIDUAL HISTORY — the record book (owner request 2026-09): every
    # individual state champion of every archived season, one row per champion
    # PLAYER, so a consumer groups by champion_pid and reads a career (titles,
    # consecutive titles, a four-grade sweep) instead of reconstructing it from
    # dozens of archived brackets. Archive path only, like program history;
    # classification scope does not cut it — a career crosses reclassification.
    # ‼️ STABLE PROGRAM IDS BESIDE THE NAMES. The archive names a school by its
    # display name at the time (relabelled to today's on read), and ~300 programs
    # have been renamed — a name cannot join programs.csv reliably. The id is the
    # gender's roster identity, as everywhere else in this bundle; a program with
    # no programs.csv row (a former sponsor) gets an empty id rather than a
    # dangling one, the coefficient file's rule.
    individual_history = []
    if w and not injected:
        key_by_name_ = {t.school.name: t.school.key for t in all_teams}
        for r in wd.jhsaa_individual_history_rows(w["id"], gender):
            r["program_id"] = key_by_name_.get(r["school"], "")
            r["runner_up_program_id"] = key_by_name_.get(r["runner_up_school"], "")
            individual_history.append(r)
    # THE REALIGNMENT LEDGER (owner rule 2026-09): every move of every committed
    # reclassification cycle, newest cycle first, so a consumer can track a
    # program's class across the whole arc of seasons without opening the app.
    # Archive path only (the coefficient file's rule) and NOT cut to this export's
    # season: a cycle moves both genders of a school at once, so the rows are
    # gender-blind and the same in the girls' and boys' bundle. ‼️ program_id
    # joins programs.csv on the school's IDENT (`School.ident`, the roster
    # identity a rename never moves), recorded on the move row at commit — the
    # display name is the name AT THE TIME and a later rename would orphan the
    # row, or worse attach it to whoever inherits the name. A row written
    # before the column existed falls back to the name. A school that has since
    # stopped sponsoring this gender gets an empty id, never a dangling one.
    from app import jhsaa_reclass as _rc
    realignments = []
    if w and not injected:
        key_by_ident_r = {t.school.ident: t.school.key for t in all_teams}
        key_by_name_r = {t.school.name: t.school.key for t in all_teams}
        for m in _rc.all_moves(w["id"]):
            ident = m.get("ident") or ""
            realignments.append({
                "season_year": m["season_year"], "world_year": m["year"],
                "school": m["school"], "program_ident": ident,
                "program_id": (key_by_ident_r.get(ident) if ident else None)
                              or key_by_name_r.get(m["school"], ""),
                "from_class": m["from_cls"], "to_class": m["to_cls"],
                "enrollment": m["enrollment"], "state_points": m["points"],
                "win_rate": "" if m["win_rate"] is None else m["win_rate"],
                "adjustment": m["adjustment"], "effective_size": m["effective"],
                "rank_in_pool": m["rank"], "reason": m["reason"],
                "owner_decision": int(bool(m["manual"])),
                "league_before": m["league_before"] or "",
                "league_after": m["league_after"] or ""})
    tables = {"programs.csv": programs, "players.csv": players, "duals.csv": duals,
              "lines.csv": lines, "line_players.csv": line_players,
              "jhsaa_standings.csv": standings,
              "jhsaa_computer_ratings.csv": computer_ratings,
              "jhsaa_coefficient.csv": coefficient_rows,
              "jhsaa_flights.csv": flight_rows,
              "jhsaa_realignments.csv": realignments,
              "jhsaa_jv_state.csv": jv_state_rows,
              "jhsaa_program_history.csv": history,
              "jhsaa_individual_history.csv": individual_history}
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
            "style": "Primary play style (counterpuncher, junkballer, all_court, serve_and_volley, serve_first, aggressive_baseliner, pusher, balanced).",
            "style_trait": "Secondary tactical trait, or none (net_rusher, chip_and_charge, first_strike, grinder, retriever, heavy_topspin, flat_hitter, slice_specialist, return_specialist, big_server).",
            "potential_grade": "The program's ESTIMATE of the player's ceiling (what the JHSAA pages show as POT): a one-time per-player misread that shrinks with seasons in the building and participation. It can move either way season to season as the staff learn the player; that is the estimate correcting, never ability lost.",
            "ceiling_grade": "The fixed hidden ceiling (pinned at generation; never changes for an enrolled player). Use this, not potential_grade, for any talent analysis.",
            "toss_power_raw": "JHSAA opponent-adjusted team power used for selection/seeding; compare only within this season and gender.",
            "expected_pct": "jhsaa_flights: win rate the flight's matchups were expected to return, fitted on this season's varsity flights with home court; delta_pct is actual minus expected in points.",
            "captain": "players.csv: 1 if the player was one of the program's team captains "
                       "this season (named preseason; 1-3 per program), 0 if not. "
                       "captain_order ranks them best-known first (1 = the lead captain) and "
                       "is empty for non-captains. Captaincy changes no rating; a captain dresses "
                       "for every dual from the naming point on. BOTH columns are empty (not 0) "
                       "for a season archived before captains existed — unknown, not absent.",
        },
        "domain_rules": ["JHSAA gender values are girls/boys (college uses women/men).",
            "jhsaa_individuals.json contains the archived Individual State brackets "
            "for this gender plus mixed doubles. Its outer keys are gender, then "
            "classification, then flight (S1-S3, D1-D3, or XD); mixed is stored "
            "separately because each pair contains one boy and one girl.",
            "jhsaa_program_history.csv spans EVERY archived season for this gender (one row "
            "per program per year — the app's program-history ledger), not just this export's "
            "scope year; it is empty only when the save has no archived seasons.",
            "jhsaa_individual_history.csv is the individual RECORD BOOK: every individual "
            "state champion of EVERY archived season for this gender, one row per champion "
            "player, with program_id and runner_up_pids/runner_up_program_id for stable joins "
            "(a doubles title is one row per partner, with the partner as context; a "
            "mixed title credits only this gender's half; JV brackets carry an empty "
            "classification), with the runner-up and seeds. Group by champion_pid for career "
            "title counts, consecutive runs and four-grade sweeps. Empty when the save has no "
            "archived seasons.",
            "duals.level is 'v' for varsity and 'jv' for the JV season; they share a "
            "schedule table, so a consumer that wants one must filter on it. JV duals ARE "
            "included (the JV season, its Showcase, and the JV Team State Tournament at "
            "phase='jv_state'); jhsaa_standings.csv and every rating stay varsity-only, so "
            "filter level='v' before deriving varsity records. Absent on seasons exported "
            "before the JV season existed, where every dual is varsity.",
            "duals.shape states a JV dual's elastic lineup ('2S/2D'); varsity rows leave it "
            "empty because their shape is a function of phase and classification. duals.tied "
            "marks drawn results: even-court JV duals and an even-format varsity showcase "
            "that remains level after the sets-and-games ladder. A tied dual "
            "has no winner_program_id. duals.decided_on_tiebreak marks a LEVEL varsity "
            "postseason dual (Group 2's 3S/3D road) whose winner was decided on three "
            "concurrent 10-point tiebreakers — its points are level and it is NOT a tie.",
            "jhsaa_jv_state.json is the JV Team State Tournament: the twenty geographic-area "
            "regional championships and the statewide classless bracket their champions play. "
            "From the 36-team seasons its bracket's first round is named 'Parastate' in "
            "round_names: sixteen at-large selections (at_large / selection, an index of 30% JV "
            "record + 70% varsity regular-season record) played high-low for eight seats in "
            "the 28-team main draw, where seeds 1-4 bye. jhsaa_jv_state.csv is that field "
            "FLAT for analysis: one row per team in seed order — entry (champion/at_large), "
            "region, jv_* and varsity_reg_* records and percentages, selection_index, "
            "made_main_draw, state_place (teams alive when eliminated, 1 = champion) and "
            "state_finish — read off the same archived bracket. Seasons played at twenty "
            "list their champions with the index columns empty. "
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
            "jhsaa_flights.csv is Flight Efficiency: one row per program per flight "
            "(the flights present in this export: "
            + (", ".join(flight_slots) if flight_slots else "none — no contested varsity line")
            + "; every JHSAA dual format from 5S/2D to 4S/5D reaches this table, so S5 and "
            "D5 appear whenever they were played), matches and wins at that flight, "
            "actual_pct, expected_pct (a logistic fitted on this season's own varsity "
            "flights — the matchup and home court — so the row is judged against how the "
            "association converted its matchups this year) and delta_pct = actual - "
            "expected in points, with the player or pair that held the flight most: "
            "held_most_by is the display name(s), held_most_by_ids the matching "
            "player_id(s) in the same order (joined ' / ' for a pair) for joining "
            "players.csv — names are not unique. Computed from this bundle's own rosters "
            "and lines with the same fold as /jhsaa/flights; the fit covers every varsity "
            "dual of the gender, the rows are cut to this export's classification. A row "
            "of 25-35 matches swings ~9 points by chance; trust programs moving the same "
            "way across several flights.",
            # ‼️ Prices DERIVED from `jhsaa_coefficient`, never retyped — the
            # committee sentence above learned this the hard way.
            "jhsaa_coefficient.csv is the Program Coefficient (UEFA-style): one row per "
            "program per championship_group, ranked WITHIN that group only — never across "
            "classes — as of this export's season. coefficient sums the last "
            f"{_coef.WINDOW} archived seasons' points weighted "
            f"{'/'.join(str(x) for x in _coef.WEIGHTS)} newest to oldest; a season's "
            "points are road-round wins (" + ", ".join(
                f"{k} {v:g}" for k, v in _coef.road_points().items()) + ") plus ONE "
            f"State finish (champion {_coef.STATE_CHAMPION}, runner-up {_coef.STATE_FINAL}, "
            f"semifinalist {_coef.STATE_SEMI}, quarterfinalist {_coef.STATE_QUARTER}, "
            f"octofinalist {_coef.STATE_OCTO}, any other main-draw entry {_coef.STATE_ENTRY}, "
            # ‼️ DERIVED like every other price in this sentence. It was typed as a
            # literal 0 and went stale the moment the owner priced a Parastate exit
            # (2026-09) — the one retyped number in a sentence whose whole rule is
            # that it must not retype them.
            f"a Parastate exit {_coef.STATE_PARASTATE:g}) plus {_coef.TOC_BONUS} for a TOC entry; the regular season "
            "is NEVER an input. season_points is this season's own points; trend is the "
            "coefficient minus the same program's coefficient as of the previous archived "
            "season (0 with no prior season); seasons_of_history counts every archived "
            f"season the program appears in; bootstrap=1 marks fewer than {_coef.MIN_HISTORY}, "
            "whose coefficient is SEEDED at the first quartile of its group's established "
            "programs (its own points do not rank it). breakdown_json lists [world_year, "
            "points, weight] triples for the window, newest first; as_of_world_year and "
            "window_world_years are the archive's zero-based world-years (season_year = "
            f"{wd.BASE_YEAR} + world_year + 1). program_id keys on the roster identity, so "
            "a renamed program keeps one row across its history, and every row joins "
            "programs.csv: a program that has since stopped sponsoring this gender is "
            "omitted and rank counts current sponsors only (the app's page still lists "
            "it). Empty on an injected season or when the save has no archive.",
            "jhsaa_realignments.csv is the reclassification LEDGER: one row per school per "
            "committed realignment cycle, EVERY cycle the save has committed (newest first), "
            "not just this export's season, and identical in the girls' and boys' bundles — a "
            "cycle moves a school with both its programs. from_class/to_class are the "
            "classification left and joined (classification and championship group move "
            "together); enrollment, state_points, win_rate, adjustment and effective_size "
            "are the evidence the sort placed the school on (effective_size = enrollment + "
            "success adjustment − futility adjustment); rank_in_pool is its place in the pool "
            "it was sorted in; reason is sort, geography (a cross-ladder move on territory) "
            "or owner (a veto, pin or manual addition; owner_decision=1). league_before/after "
            "name the league the school played in before the cycle and after the redraw. "
            "season_year is the first season played in the new class. Empty on an injected "
            "season or when no cycle has been committed.",
            # ‼️ DERIVED from `AT_LARGE_BIDS`/`STATE_FIELD`, never retyped: this
            # sentence claimed "the 48-team groups (7A and Group 1)" and "sixteen
            # selections in seed order 33-48" after both had stopped being true,
            # so a consumer of a 6A-1A export was handed the wrong field
            # semantics. Each shape states its own seat count and seed range.
            "jhsaa_committee.json is the at-large selection committee, which runs for "
            f"{jhsaa.parastate_blurb()}: the five members' full ballots and published "
            "weights, the per-member at-large ranges, locks, automatic bids (district "
            "champions who missed the road), bubble and seeding Borda totals, statuses, "
            "and the selections in seed order — "
            + "; ".join(f"{lbl.split(' ')[0]}-team: {bids} selections seeded "
                        f"{road + 1}-{road + bids}"
                        for lbl, _gs, road, bids in jhsaa.parastate_summary())
            + ". The road's qualifiers are unchanged and an at-large is NEVER seeded "
            "above the whole road. Their State bracket opens with the Parastate (the "
            "2 x bids lowest seeds, paired high-low) in jhsaa_championships.json, its "
            "duals ordinary phase='state' rows in duals.csv.",
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

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
        rows = conn.execute(
            "SELECT school, opp, home, phase, pf, pa, won, district, lines"
            " FROM world_jhsaa_dual WHERE world_id=? AND year=? AND gender=?"
            " ORDER BY school, rowid",
            (world["id"], world_year, gender)).fetchall()
    finally:
        conn.close()
    schedule_by_school = {}
    for r in rows:
        d = dict(r)
        d["home"] = bool(d["home"])
        d["won"] = bool(d["won"])
        d["district"] = bool(d["district"])
        d["lines"] = json.loads(d.pop("lines") or "[]")
        schedule_by_school.setdefault(d.pop("school"), []).append(d)

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
            "awards": data.get("awards", {})}


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
    for team in all_teams:
        for ordinal, dual in enumerate(team.schedule, 1):
            if not dual.get("home") or not ({team.school.name, dual["opp"]} & selected_names):
                continue                         # each event appears on both cards
            key = f"{year}|{gender}|{team.school.name}|{dual['opp']}|{ordinal}|{dual['phase']}"
            dual_id = "jhdual:" + hashlib.sha1(key.encode()).hexdigest()[:16]
            duals.append({
                "dual_id": dual_id, "year": year, "gender": gender,
                "home_program_id": team.school.key,
                "away_program_id": next((x.school.key for x in all_teams if x.school.name == dual["opp"]), dual["opp"]),
                "phase": dual["phase"], "district": int(bool(dual.get("district"))),
                "home_points": dual["pf"], "away_points": dual["pa"],
                "winner_program_id": team.school.key if dual["won"] else next((x.school.key for x in all_teams if x.school.name == dual["opp"]), dual["opp"]),
            })
            for line_no, line in enumerate(dual.get("lines", []), 1):
                line_id = f"{dual_id}:{line_no}"
                lines.append({"line_id": line_id, "dual_id": dual_id, "slot": line["slot"],
                              "score": line["score"], "home_won": int(bool(line["home_won"]))})
                for side, school in (("home", team.school.name), ("away", dual["opp"])):
                    for pos, name in enumerate(line.get(side, []), 1):
                        line_players.append({"line_id": line_id, "side": side, "position": pos,
                                             "player_id": _player_id(school, name, player_lookup), "player_name": name})

    json_files = {
        "jhsaa_championships.json": {g: season["groups"][g].get("state", {}) for g in jhsaa.GROUPS},
        "jhsaa_awards.json": season.get("awards", {}),
    }
    tables = {"programs.csv": programs, "players.csv": players, "duals.csv": duals,
              "lines.csv": lines, "line_players.csv": line_players,
              "jhsaa_standings.csv": standings}
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
            "Regular duals use 5 singles/2 doubles; early dates use 3/4; showcases and postseason use 1/4.",
            "Every court finishes. JHSAA has no clinch abandonment.",
            "1A and 2A crown SEPARATELY via a fixed 24-team postseason shape "
            "(Super Regional/Semi-State/Divisional/Semi-Conference/Conference all "
            "award direct State berths, unlike the other classes' dynamic ladder); "
            "Zonal is advancement-only there and grants no automatic State berth.",
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
        "JHSAA-only standings, awards, and championship structures remain separate rather than being forced into a college schema.\n").encode()
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


BUILDERS = {"jhsaa": build_jhsaa, "college": build_college}


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

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


def build_jhsaa(year: int, gender: str, classification: str = "all", *, season=None) -> dict[str, bytes]:
    """Build JHSAA files. ``season`` is injectable for tests and archive adapters."""
    from app import jhsaa

    if gender not in jhsaa.GENDERS:
        raise ExportError("JHSAA gender must be girls or boys.")
    valid_classes = {"all", *jhsaa.GROUPS}
    if classification not in valid_classes:
        raise ExportError("Unknown JHSAA classification.")
    season = season or jhsaa.run_season(gender, year, seed=0)
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
            "2A and 1A compete in the combined 2A-1A championship group."],
        "college_plan": {"status": "not implemented", "available_sources": ["world_roster", "seasonmode dual/results archives", "college ranking and recruiting views"],
            "proposed_domain_tables": ["college_program_seasons", "college_conferences", "college_eligibility", "college_scholarships", "college_rankings", "college_postseason"]},
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


BUILDERS = {"jhsaa": build_jhsaa}


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

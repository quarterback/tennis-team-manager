"""Turn ingested research-export bundles into the shapes the templates render.

Nothing here recomputes anything the game already decided (records, TOSS,
scores) — it only reshapes the exported tables into team pages, player pages,
and leaderboards. One season's worth of files is a "bundle"; a player who
appears across multiple bundles (multiple seasons ingested over time) gets
one career page that stitches them together on player_id.
"""
from __future__ import annotations

from collections import Counter, defaultdict


def _f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


class Bundle:
    """One ingested (family, year, gender[, division]) scope, indexed for
    lookups the templates need."""

    def __init__(self, raw: dict):
        self.family = raw["family"]
        self.scope = raw["scope"]
        self.manifest = raw["manifest"]
        t = raw["tables"]
        self.programs = {p["program_id"]: p for p in t.get("programs", [])}
        self.players = {p["player_id"]: p for p in t.get("players", [])}
        self.duals = {d["dual_id"]: d for d in t.get("duals", [])}
        self.lines_by_dual = defaultdict(list)
        for line in t.get("lines", []):
            self.lines_by_dual[line["dual_id"]].append(line)
        self.line_players = defaultdict(list)
        for lp in t.get("line_players", []):
            self.line_players[lp["line_id"]].append(lp)
        self.standings = {}
        for row in t.get("jhsaa_standings", t.get("college_standings", [])):
            self.standings[row["program_id"]] = row
        self.scholarships = {r["program_id"]: r for r in t.get("college_scholarships", [])}
        self.rankings = t.get("college_rankings", [])
        self.awards = t.get("jhsaa_awards", {})
        self.championships = t.get("jhsaa_championships", {})

        if self.family == "jhsaa":
            self.scope_id = f"jhsaa-{self.scope['year']}-{self.scope['gender']}"
            self.label = f"{self.scope['year']} JHSAA {self.scope['gender'].title()}"
            self.year = self.scope["year"]
            self.gender = self.scope["gender"]
            self.division = None
        else:
            self.scope_id = f"college-{self.scope['year']}-{self.scope['division']}-{self.scope['gender']}"
            self.label = f"{self.scope['year']} {self.scope['division']} {self.scope['gender'].title()}"
            self.year = self.scope["year"]
            self.gender = self.scope["gender"]
            self.division = self.scope["division"]

        # dual_id -> {home, away, home_prog, away_prog, lines:[{...,players:[...]}]}
        self.duals_full = {}
        for did, d in self.duals.items():
            lines = []
            for line in sorted(self.lines_by_dual.get(did, []), key=lambda x: x["slot"]):
                players = self.line_players.get(line["line_id"], [])
                lines.append({**line, "players": players})
            self.duals_full[did] = {**d, "lines": lines}

    def program_name(self, pid: str) -> str:
        p = self.programs.get(pid)
        return p["name"] if p else pid

    def player_name(self, pid: str) -> str:
        p = self.players.get(pid)
        return p["name"] if p else pid


def load_bundles(raw_bundles: list[dict]) -> list[Bundle]:
    return [Bundle(r) for r in raw_bundles]


def team_pages(bundles: list[Bundle]) -> dict:
    """program_id -> per-scope team record: {bundle, program, record, schedule, roster}"""
    out = {}
    for b in bundles:
        for pid, prog in b.programs.items():
            standing = b.standings.get(pid)
            roster = [p for p in b.players.values() if p["program_id"] == pid]
            roster.sort(key=lambda p: (-_i(p.get("current_grade")), p.get("name", "")))

            schedule = []
            for did, d in b.duals_full.items():
                if d["home_program_id"] != pid and d["away_program_id"] != pid:
                    continue
                home = d["home_program_id"] == pid
                opp_id = d["away_program_id"] if home else d["home_program_id"]
                us = d["home_points"] if home else d["away_points"]
                them = d["away_points"] if home else d["home_points"]
                won = d["winner_program_id"] == pid
                schedule.append({
                    "dual_id": did, "opp_id": opp_id, "opp_name": b.program_name(opp_id),
                    "home": home, "us": us, "them": them, "won": won,
                    "phase": d.get("phase") or d.get("round"), "week": d.get("week"),
                })
            schedule.sort(key=lambda s: (s.get("week") is None, s.get("week", 0)))

            key = (pid, b.scope_id)
            out[key] = {
                "bundle": b, "program_id": pid, "program": prog, "standing": standing,
                "roster": roster, "schedule": schedule,
                "wins": sum(1 for s in schedule if s["won"]),
                "losses": sum(1 for s in schedule if not s["won"]),
            }
    return out


def _line_result_for_player(line: dict, pid: str, side_of_pid: str) -> tuple[bool | None, str]:
    """Return (won, score) for a player's own side of a line."""
    home_won = bool(_i(line.get("home_won")))
    if side_of_pid == "home":
        won = home_won
    else:
        won = not home_won
    score = line.get("score")
    if score is None and "home_games" in line:
        score = f"{line.get('home_games')}-{line.get('away_games')}"
    return won, score or ""


def player_careers(bundles: list[Bundle]) -> dict:
    """player_id -> {name, seasons: [...], matches: [...], position_counts: Counter,
    wins, losses, teams: set of program names}"""
    careers: dict[str, dict] = {}

    for b in bundles:
        for did, d in b.duals_full.items():
            home_pid, away_pid = d["home_program_id"], d["away_program_id"]
            for line in d["lines"]:
                by_side = defaultdict(list)
                for lp in line["players"]:
                    by_side[lp["side"]].append(lp)
                for side, entries in by_side.items():
                    opp_side = "away" if side == "home" else "home"
                    partners = [e["player_name"] for e in entries]
                    opp_entries = by_side.get(opp_side, [])
                    opp_names = [e["player_name"] for e in opp_entries]
                    own_prog_id = home_pid if side == "home" else away_pid
                    opp_prog_id = away_pid if side == "home" else home_pid
                    for e in entries:
                        pid = e["player_id"]
                        won, score = _line_result_for_player(line, pid, side)
                        c = careers.setdefault(pid, {
                            "player_id": pid, "name": e.get("player_name") or b.player_name(pid),
                            "matches": [], "position_counts": Counter(), "teams": set(),
                            "wins": 0, "losses": 0, "seasons": set(),
                        })
                        c["name"] = e.get("player_name") or c["name"]
                        c["teams"].add(b.program_name(own_prog_id))
                        c["seasons"].add(b.scope_id)
                        c["position_counts"][line["slot"]] += 1
                        if won is True:
                            c["wins"] += 1
                        elif won is False:
                            c["losses"] += 1
                        c["matches"].append({
                            "scope_id": b.scope_id, "scope_label": b.label, "dual_id": did,
                            "slot": line["slot"], "won": won, "score": score,
                            "opp_program": b.program_name(opp_prog_id),
                            "own_program": b.program_name(own_prog_id),
                            "partners": [n for n in partners if n != e.get("player_name")],
                            "opponents": opp_names,
                            "phase": d.get("phase") or d.get("round"),
                            "week": d.get("week"),
                        })

    # attach bio info from the most recent bundle's players table
    for b in bundles:
        for pid, p in b.players.items():
            if pid in careers:
                careers[pid].setdefault("bio", {})
                careers[pid]["bio"] = p  # last bundle wins -- most current snapshot

    for c in careers.values():
        c["matches"].sort(key=lambda m: (m["scope_id"], m.get("week") if m.get("week") is not None else 0))
        c.setdefault("bio", {})
    return careers


def leaderboards(bundles: list[Bundle], careers: dict) -> dict:
    """Simple, defensible leaderboards per scope: best records, most match wins,
    plus award winners pulled straight from the exported award JSON."""
    boards = {}
    for b in bundles:
        rows = []
        for pid, standing in b.standings.items():
            wins = _i(standing.get("wins"))
            losses = _i(standing.get("losses"))
            total = wins + losses
            rows.append({
                "program_id": pid, "name": b.program_name(pid),
                "wins": wins, "losses": losses,
                "pct": wins / total if total else 0.0,
                "power": _f(standing.get("toss_power_raw")) if "toss_power_raw" in standing else None,
            })
        rows.sort(key=lambda r: (-r["pct"], -r["wins"]))

        top_players = []
        for pid, c in careers.items():
            if b.scope_id not in c["seasons"]:
                continue
            total = c["wins"] + c["losses"]
            if total < 3:
                continue
            top_players.append({
                "player_id": pid, "name": c["name"], "wins": c["wins"], "losses": c["losses"],
                "pct": c["wins"] / total if total else 0.0, "team": next(iter(c["teams"]), ""),
            })
        top_players.sort(key=lambda r: (-r["pct"], -r["wins"]))

        boards[b.scope_id] = {
            "bundle": b, "team_standings": rows, "top_players": top_players[:25],
            "awards": b.awards,
        }
    return boards

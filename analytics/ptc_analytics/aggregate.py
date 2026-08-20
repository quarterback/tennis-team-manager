"""Turn ingested research-export bundles into the shapes the templates render.

Nothing here recomputes anything the game already decided (records, TOSS,
scores) — it only reshapes the exported tables into team pages, player pages,
and leaderboards. One season's worth of files is a "bundle"; a player who
appears across multiple bundles (multiple seasons ingested over time) gets
one career page that stitches them together on player_id.
"""
from __future__ import annotations

from collections import Counter, defaultdict


def _is_singles_slot(slot: str) -> bool:
    return slot.upper().startswith("S")


_REGULAR_BUCKET = "regular"
_POSTSEASON_BUCKET = "state"


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


def program_class(prog: dict) -> str:
    """The championship a program COMPETES in. JHSAA exports carry both
    `championship_group` (where the program plays — play-ups move this) and
    `classification` (enrollment size) — the game's own hub, rankings and
    State draw all key on the group, so every grouping here does too.
    College programs carry `division` instead."""
    return (prog.get("championship_group") or prog.get("classification")
            or prog.get("division") or "—")


def program_league(prog: dict) -> str:
    """JHSAA district / college conference — the regular league schedule."""
    return prog.get("district") or prog.get("conference") or "—"


_CLASS_YEAR_ORDER = {"FR": 9, "SO": 10, "JR": 11, "SR": 12, "GR": 13}


def grade_label(p: dict) -> tuple[str, int]:
    """(display, sort value) for a player's grade — shown in EVERY list a
    player appears in (owner rule: no clicking through to find out someone's
    a senior). JHSAA players carry an int grade 9-12 ('12th'); college ones a
    class-year string ('Sr', 'RS-Jr' — the RS- tag is cosmetic, sort on the
    base class)."""
    grade = p.get("grade")
    if grade not in (None, ""):
        g = _i(grade)
        return f"{g}th", g
    cy = str(p.get("class_year") or "")
    if cy:
        base = cy.upper().replace("RS-", "").strip()[:2]
        return cy, _CLASS_YEAR_ORDER.get(base, 0)
    return "", 0


def classification_sort_key(cls: str):
    """Biggest/most-competitive classification first: JHSAA '9A'..'1A' by the
    leading number descending, college 'D1'..'D4' likewise (D1 = smallest
    digit first, handled by the JHSAA rule being descending — college scopes
    only ever hold ONE division so the order never actually mixes them).
    Falls back to the raw string so an unrecognized value sorts last."""
    digits = "".join(c for c in cls if c.isdigit())
    if not digits:
        return (1, 0, cls)
    n = int(digits)
    # 'D1' should lead college lists while '9A' leads JHSAA ones — divisions
    # ascend, classifications descend. A JHSAA group always ends in 'A'.
    return (0, n if cls.upper().startswith("D") else -n, cls)


# ---- schedule presentation: the in-game card's own vocabulary ----
# A JHSAA schedule tag is THREE things in the game (dist / road / state·toc),
# plus the invite and showcase labels the card uses. Sections mirror the
# in-game school page: league play, invitationals, showcases, road to State,
# then the State event and the TOC.

_JH_ROAD_LABELS = {
    "area": "Areas", "sectional": "Sectionals", "ward": "Wards",
    "regional": "Regionals", "zonal": "Zonals",
    "super_regional": "Super Regionals", "semi_state": "Semi-State",
    "divisional": "Divisionals", "semi_conference": "Semi-Conference",
    "conference": "Conference",
}

# section key -> (order, heading)
_SECTIONS = {
    "invite": (0, "Invitationals & early season"),
    "league": (1, "League play"),
    "showcase": (2, "Showcases"),
    "road": (3, "Road to State"),
    "state": (4, "State championship"),
    "toc": (5, "Tournament of Champions"),
    # college
    "ita": (0, "ITA fall events"),
    "reg": (1, "Regular season"),
    "ct": (2, "Conference tournament"),
    "ncaa": (3, "NCAA championship"),
    "other": (6, "Other events"),
}


def _dual_presentation(d: dict, family: str) -> tuple[str, str, str]:
    """(tag_text, tag_kind, section_key) for one dual — the TYPE chip and the
    schedule section it belongs to, in the in-game card's own vocabulary,
    never a raw phase string."""
    if family == "jhsaa":
        phase = d.get("phase") or ""
        if phase == "state":
            return "STATE", "state", "state"
        if phase == "toc":
            return "TOC", "toc", "toc"
        if phase.startswith("showcase"):
            kind = "Pod" if phase.endswith("pod") else "Tiered"
            return f"SHOWCASE · {kind}", "showcase", "showcase"
        if phase in _JH_ROAD_LABELS:
            return _JH_ROAD_LABELS[phase].upper(), "road", "road"
        if bool(_i(d.get("district"))):
            return "DIST", "dist", "league"
        # early window + plain non-district regular play: the association
        # calls these Invitationals ("INVITE" on a card).
        return "INVITE", "invite", "invite"
    round_ = d.get("round") or ""
    if round_ == "NCAA":
        return "NCAA", "state", "ncaa"
    if round_ == "CT":
        return "CONF TOURNEY", "road", "ct"
    if round_ in ("ITAK", "ITAI"):
        return ("ITA KICKOFF" if round_ == "ITAK" else "ITA INDOOR"), "showcase", "ita"
    if round_ == "REG":
        if bool(_i(d.get("is_conference"))):
            return "CONF", "dist", "reg"
        return "NON-CONF", "invite", "reg"
    return (round_ or "—").upper(), "invite", "other"


def _pretty_date(iso: str) -> str:
    """'2027-08-04' -> 'Aug 4' (the in-game schedule's own date style)."""
    try:
        y, m, day = (int(x) for x in (iso or "").split("-"))
    except ValueError:
        return ""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return f"{months[m - 1]} {day}" if 1 <= m <= 12 else ""


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
            # classification is part of the exporter's own scope (research_
            # export.build_jhsaa year/gender/classification) — two exports for
            # the same year/gender but different classifications are
            # different datasets, so it has to be in the identity here too,
            # not just in the ingest cache key, or a per-scope page (team
            # pages, leaderboards, metrics) silently merges them.
            classification = self.scope.get("classification", "all")
            self.scope_id = f"jhsaa-{self.scope['year']}-{self.scope['gender']}-{slug(classification)}"
            cls_label = "" if classification == "all" else f" {classification}"
            self.label = f"{self.scope['year']} JHSAA {self.scope['gender'].title()}{cls_label}"
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

        # ‼️ Card shapes (how many singles/doubles lines a "regular" or
        # "postseason" dual plays) are DERIVED from the actual exported lines,
        # never hard-coded — the game has already swapped its own regular-vs-
        # early JHSAA shapes once (5S/2D <-> 3S/4D), and a fixed assumption
        # here would go stale silently the same way a fixed flight-weight
        # table did in the game itself (see CLAUDE.md's TOSS flight-weight
        # AAR). regular_shape/state_shape are (n_singles, n_doubles) or None
        # if the bucket has no duals on record in this scope.
        self.regular_shape = self._derive_card_shape(_REGULAR_BUCKET)
        self.state_shape = self._derive_card_shape(_POSTSEASON_BUCKET)

    def _dual_bucket(self, d: dict) -> str | None:
        if self.family == "jhsaa":
            phase = d.get("phase")
            if phase == "regular":
                return _REGULAR_BUCKET
            if phase in ("state", "toc"):
                return _POSTSEASON_BUCKET
            return None   # early / showcases / challenge: a real third shape, not noise to blend in
        round_ = d.get("round")
        if round_ == "REG":
            return _REGULAR_BUCKET
        if round_ == "NCAA":
            return _POSTSEASON_BUCKET
        return None       # CT / ITAK / ITAI: not modeled as either card shape

    def _derive_card_shape(self, bucket: str) -> tuple[int, int] | None:
        counts = Counter()
        for d in self.duals_full.values():
            if self._dual_bucket(d) != bucket:
                continue
            ns = sum(1 for line in d["lines"] if _is_singles_slot(line["slot"]))
            nd = sum(1 for line in d["lines"] if not _is_singles_slot(line["slot"]))
            if ns or nd:
                counts[(ns, nd)] += 1
        return counts.most_common(1)[0][0] if counts else None

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
            for order, (did, d) in enumerate(b.duals_full.items()):
                if d["home_program_id"] != pid and d["away_program_id"] != pid:
                    continue
                home = d["home_program_id"] == pid
                opp_id = d["away_program_id"] if home else d["home_program_id"]
                us = _f(d["home_points"] if home else d["away_points"])
                them = _f(d["away_points"] if home else d["home_points"])
                won = d["winner_program_id"] == pid
                tag, tag_kind, section = _dual_presentation(d, b.family)
                schedule.append({
                    "dual_id": did, "opp_id": opp_id, "opp_name": b.program_name(opp_id),
                    "home": home, "us": us, "them": them, "won": won,
                    # a dual's team score is written WINNER-first, like every
                    # scoreline in the game (see the bracket-score AAR) — the
                    # W/L marker carries whose result it was.
                    "score": f"{max(us, them):g}–{min(us, them):g}",
                    "phase": d.get("phase") or d.get("round"), "week": d.get("week"),
                    "date": d.get("date") or "", "date_label": _pretty_date(d.get("date") or ""),
                    "tag": tag, "tag_kind": tag_kind, "section": section,
                    "_order": order,
                })
            # Play order: the exported date is the game's own display calendar
            # (one date per dual, both cards agree). The export-file fallback
            # order is NOT play order — it lists a team's home duals first
            # (its own card) and its away duals wherever the opponents' cards
            # put them — so undated rows at least group by section (the
            # in-game card's sections) instead of by venue. College scopes
            # order on week.
            schedule.sort(key=lambda s: (
                _SECTIONS.get(s["section"], _SECTIONS["other"])[0],
                s["date"] or "9999",
                s["week"] is None, _f(s.get("week"), 0), s["_order"]))

            key = (pid, b.scope_id)
            out[key] = {
                "bundle": b, "program_id": pid, "program": prog, "standing": standing,
                "roster": roster, "schedule": schedule,
                "wins": sum(1 for s in schedule if s["won"]),
                "losses": sum(1 for s in schedule if not s["won"]),
            }
    return out


def schedule_sections(schedule: list[dict]) -> list[dict]:
    """Group an already-ordered team schedule into the in-game card's sections
    (League play / Invitationals / Showcases / Road to State / State / TOC —
    or the college equivalents). Returns [{heading, rows}] in section order,
    empty sections omitted."""
    grouped: dict[str, list[dict]] = {}
    for s in schedule:
        grouped.setdefault(s.get("section") or "other", []).append(s)
    out = []
    for key, (order, heading) in sorted(_SECTIONS.items(), key=lambda kv: kv[1][0]):
        if key in grouped:
            out.append({"heading": heading, "rows": grouped[key]})
    return out


def _reorient_score(score: str, side_of_pid: str) -> str:
    """The export stores a line's score HOME-first, always — but a match log
    is read from ONE player's own perspective. Left alone, an away-side
    winner shows a score that reads like a loss (and vice versa). Swap each
    "a-b" component to "own-opp" order when the player was on the away side;
    home-side stays as exported."""
    if side_of_pid != "away" or not score:
        return score
    parts = []
    for s in score.split(","):
        s = s.strip()
        if "-" not in s:
            parts.append(s)
            continue
        a, _, b = s.partition("-")
        parts.append(f"{b.strip()}-{a.strip()}")
    return ", ".join(parts)


def _line_result_for_player(line: dict, pid: str, side_of_pid: str) -> tuple[bool | None, str]:
    """Return (won, score) for a player's own side of a line, score reoriented
    to that player's own-opponent order regardless of which side was home."""
    home_won = bool(_i(line.get("home_won")))
    if side_of_pid == "home":
        won = home_won
    else:
        won = not home_won
    score = line.get("score")
    if score is None and "home_games" in line:
        score = f"{line.get('home_games')}-{line.get('away_games')}"
    return won, _reorient_score(score or "", side_of_pid)


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
                        tag, tag_kind, _section = _dual_presentation(d, b.family)
                        c["matches"].append({
                            "scope_id": b.scope_id, "scope_label": b.label, "dual_id": did,
                            "slot": line["slot"], "won": won, "score": score,
                            "opp_program": b.program_name(opp_prog_id),
                            "own_program": b.program_name(own_prog_id),
                            "own_program_id": own_prog_id,
                            "partners": [n for n in partners if n != e.get("player_name")],
                            "opponents": opp_names,
                            "phase": d.get("phase") or d.get("round"),
                            "tag": tag, "tag_kind": tag_kind,
                            "week": d.get("week"),
                            "date": d.get("date") or "",
                            "date_label": _pretty_date(d.get("date") or ""),
                        })

    # attach bio info from the most recent bundle's players table
    for b in bundles:
        for pid, p in b.players.items():
            if pid in careers:
                careers[pid].setdefault("bio", {})
                careers[pid]["bio"] = p  # last bundle wins -- most current snapshot

    for c in careers.values():
        c["matches"].sort(key=lambda m: (m["scope_id"], m.get("date") or "",
                                         _f(m.get("week"), 0)))
        c.setdefault("bio", {})
    return careers


def leaderboards(bundles: list[Bundle], careers: dict) -> dict:
    """Per-scope season boards, structured the way the game (and
    oregontennis.org) present a season — never one statewide splat:

      rows              every team, enriched with classification / league /
                        league record / league place, ranked STATEWIDE on the
                        archived TOSS power (the game's own ranking basis; a
                        rating never gets recomputed here — see the game's
                        region-drift AAR) with win%% as the pre-TOSS fallback.
      classifications   [{name, teams (class-ranked), districts:[{name, teams
                        (league-standings order)}]}] — the class → district
                        hierarchy every in-game JHSAA surface is built on.
      by_program        program_id -> row, for team pages to pull their own
                        rank/standing context from.
    """
    boards = {}
    for b in bundles:
        rows = []
        for pid, standing in b.standings.items():
            prog = b.programs.get(pid, {})
            wins = _i(standing.get("wins"))
            losses = _i(standing.get("losses"))
            total = wins + losses
            raw_power = standing.get("toss_power_raw")
            power = _f(raw_power) if raw_power not in (None, "") else None
            dw = _i(standing.get("district_wins"))
            dl = _i(standing.get("district_losses"))
            place = standing.get("district_place")
            rows.append({
                "program_id": pid, "name": b.program_name(pid),
                "classification": program_class(prog), "league": program_league(prog),
                "wins": wins, "losses": losses,
                "pct": wins / total if total else 0.0,
                "power": power,
                "league_wins": dw, "league_losses": dl,
                "league_pct": dw / (dw + dl) if (dw + dl) else 0.0,
                "league_place": _i(place) if place not in (None, "") else None,
            })

        # Statewide rank on the archived power where this season has one
        # (TOSS is the game's seeding/ranking index); win%% breaks ties and
        # carries seasons archived before TOSS existed — the same fallback
        # the game's own jhsaa_group_ranking uses.
        def rank_key(r):
            return (-(r["power"] if r["power"] is not None else -1e9),
                    -r["pct"], -r["wins"], r["name"])
        rows.sort(key=rank_key)
        for i, r in enumerate(rows, 1):
            r["state_rank"] = i

        by_class: dict[str, list[dict]] = {}
        for r in rows:
            by_class.setdefault(r["classification"], []).append(r)
        classifications = []
        for cls, cls_rows in sorted(by_class.items(),
                                    key=lambda kv: classification_sort_key(kv[0])):
            for i, r in enumerate(cls_rows, 1):   # already in rank_key order
                r["class_rank"] = i
                r["class_size"] = len(cls_rows)
            districts = {}
            for r in cls_rows:
                districts.setdefault(r["league"], []).append(r)
            district_list = []
            for name, teams in sorted(districts.items(), key=lambda kv: kv[0]):
                # League standings order: the archived place when the export
                # carries one (the association's own tiebreak ladder already
                # decided it — don't re-derive), else league win%%.
                teams = sorted(teams, key=lambda r: (
                    r["league_place"] if r["league_place"] is not None else 999,
                    -r["league_pct"], rank_key(r)))
                district_list.append({"name": name, "teams": teams})
            classifications.append({"name": cls, "teams": cls_rows,
                                     "districts": district_list})

        top_players = []
        for pid, c in careers.items():
            # This board is per-SCOPE, but `c["wins"]`/`c["losses"]` are the
            # player's CAREER totals across every ingested season — using
            # them here would rank a player on matches from other seasons
            # entirely. Derive the record from this scope's matches only.
            scope_matches = [m for m in c["matches"] if m["scope_id"] == b.scope_id]
            wins = sum(1 for m in scope_matches if m["won"] is True)
            losses = sum(1 for m in scope_matches if m["won"] is False)
            total = wins + losses
            if total < 3:
                continue
            team = next((m["own_program"] for m in scope_matches), next(iter(c["teams"]), ""))
            team_id = next((m.get("own_program_id") for m in scope_matches), None)
            team_prog = b.programs.get(team_id, {})
            glabel, gsort = grade_label(b.players.get(pid, {}))
            top_players.append({
                "player_id": pid, "name": c["name"], "wins": wins, "losses": losses,
                "pct": wins / total if total else 0.0, "team": team,
                "classification": program_class(team_prog) if team_prog else "—",
                "league": program_league(team_prog) if team_prog else "",
                "grade": glabel, "grade_sort": gsort,
            })
        top_players.sort(key=lambda r: (-r["pct"], -r["wins"]))
        # Cap leaders PER CLASSIFICATION, never statewide: the page filters
        # this list by class, so a statewide top-50 slice would leave a small
        # classification's view sparse or empty even when it has plenty of
        # qualifying players. Ranks are stamped before the trim so both
        # numbers stay honest (a 3A player can be #4 in class, #212 statewide).
        per_class = Counter()
        leaders = []
        for i, r in enumerate(top_players, 1):
            r["state_rank"] = i
            per_class[r["classification"]] += 1
            r["class_rank"] = per_class[r["classification"]]
            if r["class_rank"] <= 25:
                leaders.append(r)

        boards[b.scope_id] = {
            "bundle": b, "rows": rows, "classifications": classifications,
            "by_program": {r["program_id"]: r for r in rows},
            "top_players": leaders,
            "awards": b.awards,
        }
    return boards

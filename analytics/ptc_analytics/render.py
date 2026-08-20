"""Render the static site from ingested bundles + computed aggregates."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import aggregate, metrics as metrics_mod, prose

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"
SITE = HERE.parent / "site"
DATA = HERE.parent / "data"

CREST_COLORS = [f"var(--crest-{i})" for i in range(12)]


def crest_color(name: str) -> str:
    return CREST_COLORS[hash(name) % len(CREST_COLORS)]


def initials(name: str) -> str:
    words = [w for w in name.replace("-", " ").split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def team_href(program_id: str, scope_id: str) -> str:
    return f"../teams/{aggregate.slug(scope_id)}__{aggregate.slug(program_id)}.html"


def player_href(pid: str) -> str:
    return f"../players/{aggregate.slug(pid)}.html"


def _round_names(n: int, explicit: list[str] | None = None) -> list[str]:
    """Label archived bracket rounds. `explicit` is the export's own
    `round_names` for a classification's PRELIMINARY rounds (e.g. a 40-field
    class's "Qualifiers Round" / "First Round" ahead of where the Qualifiers
    and main-draw byes converge — see jhsaa.run_state) and must be used
    verbatim: those rounds are NOT a continuation of the same single-
    elimination sequence the tail is, so distance-from-final labeling would
    misname them (and silently present two separate draws as one). Whatever
    rounds remain after the explicit prefix get Final/Semifinals/Quarterfinals/
    Octofinals by distance from the end, same as before."""
    prefix = list(explicit or [])
    remaining = max(0, n - len(prefix))
    labels_from_end = ["Final", "Semifinals", "Quarterfinals", "Octofinals", "Round of 32"]
    tail = []
    for i in range(remaining):
        from_end = remaining - 1 - i
        tail.append(labels_from_end[from_end] if from_end < len(labels_from_end) else f"Round {i + 1}")
    return prefix + tail


def _roster_records(careers: dict) -> dict:
    """(scope_id, program_id, player_id) -> {'s': [w, l], 'd': [w, l]} — the
    per-player singles/doubles season records the in-game roster panel shows.
    One pass over every career, never a per-team rescan."""
    out: dict[tuple, dict] = {}
    for pid, c in careers.items():
        for m in c["matches"]:
            if m["won"] is None or not m.get("own_program_id"):
                continue
            key = (m["scope_id"], m["own_program_id"], pid)
            rec = out.setdefault(key, {"s": [0, 0], "d": [0, 0]})
            half = "s" if m["slot"].upper().startswith("S") else "d"
            rec[half][0 if m["won"] else 1] += 1
    return out


def _fmt_opt(v, spec="%.3f"):
    return spec % v if v is not None else None


def _team_stat_row(pid: str, scope_id: str, m, b) -> dict:
    """One Stat Center row: identity + every first-pass team metric, formatted
    for the grid (None -> None, rendered as em-dash by the template)."""
    prog = b.programs.get(pid, {})
    q = m.quartile_record
    lg = m.league_record

    def rec(d):
        return f"{d.get('w', 0)}-{d.get('l', 0)}" if d else "—"

    return {
        "program_id": pid, "scope_id": scope_id, "name": m.name,
        "scope_label": b.label,
        "classification": aggregate.program_class(prog),
        "league": aggregate.program_league(prog),
        "record": f"{m.dual_wins}-{m.duals - m.dual_wins}",
        "lines_played": m.lines_played,
        # shape
        "s_pct": m.s_pct, "d_pct": m.d_pct, "dr": m.doubles_reliance,
        "balance": m.balance,
        # format
        "rci": m.card_index("regular"), "sci": m.card_index("state"),
        "fmt": m.fmt_lift, "swp": m.state_dual_win_prob(),
        "fwpl": m.format_win_prob_lift(),
        # résumé
        "q1": rec(q.get("Q1")), "q4": rec(q.get("Q4")),
        "league_rec": rec(lg.get("league")), "non_league_rec": rec(lg.get("non_league")),
        "close": f"{m.close_wins}-{m.close_duals - m.close_wins}" if m.close_duals else "—",
        "avg_opp_power": m.avg_opp_power,
        # depth & volatility
        "top": m.top_end_index, "depth": m.depth_index, "star_dep": m.star_dependence,
        "floor": m.floor, "ceiling": m.ceiling, "vol": m.volatility,
        "blowout": m.blowout_rate, "resist": m.resistance_rate,
        # predictive
        "expected": m.expected_wins, "luck": m.record_luck,
        "uv": m.upset_value, "blv": m.bad_loss_value, "ews": m.elite_win_share,
    }


def build_site(raw_bundles: list[dict]) -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "teams").mkdir(parents=True, exist_ok=True)
    (SITE / "players").mkdir(parents=True, exist_ok=True)
    (SITE / "seasons").mkdir(parents=True, exist_ok=True)
    (SITE / "metrics").mkdir(parents=True, exist_ok=True)
    (SITE / "brackets").mkdir(parents=True, exist_ok=True)
    shutil.copytree(STATIC, SITE / "static")

    env = Environment(loader=FileSystemLoader(TEMPLATES),
                       autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.globals["team_href"] = team_href
    env.globals["player_href"] = player_href

    bundles = aggregate.load_bundles(raw_bundles)
    teams = aggregate.team_pages(bundles)
    careers = aggregate.player_careers(bundles)
    boards = aggregate.leaderboards(bundles, careers)
    team_metrics = metrics_mod.compute_team_metrics(bundles, careers)
    player_value = metrics_mod.compute_player_value(careers)
    roster_records = _roster_records(careers)

    # Storylines are ARCHIVED, not rendered (owner call 2028-08: the prose
    # list was unusable on screen). The computation stays — it's substrate
    # for later passes — and lands beside the ingest cache as JSON.
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "storylines.json").write_text(json.dumps(
        metrics_mod.storylines(team_metrics), indent=2, ensure_ascii=False))

    def w(tmpl: str, out: Path, rel: str, **ctx):
        html = env.get_template(tmpl).render(rel=rel, **ctx)
        out.write_text(html)

    # index.html
    w("index.html", SITE / "index.html", rel="",
      bundles=bundles, scopes=[b.scope_id for b in bundles],
      team_count=len({k[0] for k in teams}), player_count=len(careers),
      dual_count=sum(len(b.duals) for b in bundles))

    # brackets — read straight off jhsaa_championships.json (already-decided
    # postseason draws), never recomputed. JHSAA-only: the college export has
    # no equivalent bracket table yet. Computed BEFORE team pages so each
    # team page can link to its own classification's bracket.
    bracket_scopes = []   # [{scope_id, label, classifications: [{name, champion, rounds}]}]
    for b in bundles:
        if not b.championships:
            continue
        classes = []
        for cls, data in sorted(b.championships.items(),
                                key=lambda kv: aggregate.classification_sort_key(kv[0])):
            rounds = data.get("rounds") or []
            if not rounds:
                continue
            names = _round_names(len(rounds), data.get("round_names"))
            fname = f"{aggregate.slug(b.scope_id)}__{aggregate.slug(cls)}.html"
            classes.append({"name": cls, "champion": data.get("champion") or "",
                             "rounds": list(zip(names, rounds)), "href": fname})
        if classes:
            bracket_scopes.append({"scope_id": b.scope_id, "label": b.label, "classifications": classes})
            for cls in classes:
                w("bracket_scope.html", SITE / "brackets" / cls["href"], rel="../",
                  scope_label=b.label, cls=cls)
    w("bracket_index.html", SITE / "brackets" / "index.html", rel="../", bracket_scopes=bracket_scopes)

    # teams/index.html + team pages — grouped by season -> classification/division
    # -> league, never a flat list of everything. Classification is the
    # CHAMPIONSHIP group (program_class — play-ups list under the class they
    # compete in, same as the game's hub); the league is `district` (JHSAA)
    # or `conference` (college).
    team_cards = []
    for (pid, scope_id), t in teams.items():
        b = t["bundle"]
        prog = t["program"]
        classification = aggregate.program_class(prog)
        league = aggregate.program_league(prog)
        team_cards.append({"program": prog, "bundle": b, "wins": t["wins"], "losses": t["losses"],
                            "color": crest_color(prog["name"]), "initials": initials(prog["name"]),
                            "classification": classification, "league": league,
                            "href": f"{aggregate.slug(scope_id)}__{aggregate.slug(pid)}.html"})
    team_cards.sort(key=lambda c: c["program"]["name"])

    scope_groups = []   # [{label, classifications: [{name, count, leagues: [{name, teams}]}]}]
    for b in bundles:
        scope_cards = [c for c in team_cards if c["bundle"].scope_id == b.scope_id]
        by_class = {}
        for c in scope_cards:
            by_class.setdefault(c["classification"], {}).setdefault(c["league"], []).append(c)
        classifications = []
        for cls, leagues in sorted(by_class.items(),
                                   key=lambda kv: aggregate.classification_sort_key(kv[0])):
            league_list = [{"name": lg, "teams": sorted(tms, key=lambda x: x["program"]["name"])}
                           for lg, tms in sorted(leagues.items(), key=lambda kv: kv[0])]
            classifications.append({"name": cls, "count": sum(len(lg["teams"]) for lg in league_list),
                                     "leagues": league_list})
        scope_groups.append({"scope_id": b.scope_id, "label": b.label, "classifications": classifications})
    w("teams_index.html", SITE / "teams" / "index.html", rel="../", scope_groups=scope_groups,
      teams=team_cards)

    for (pid, scope_id), t in teams.items():
        fname = f"{aggregate.slug(scope_id)}__{aggregate.slug(pid)}.html"
        name = t["program"]["name"]
        prog = t["program"]
        b = t["bundle"]
        classification = aggregate.program_class(prog)
        league = aggregate.program_league(prog)
        bracket_href = None
        for scope in bracket_scopes:
            if scope["scope_id"] != scope_id:
                continue
            for cls in scope["classifications"]:
                if cls["name"] == classification:
                    bracket_href = cls["href"]
        standing_row = boards.get(scope_id, {}).get("by_program", {}).get(pid)
        roster = []
        for p in t["roster"]:
            rec = roster_records.get((scope_id, pid, p["player_id"]))
            glabel, gsort = aggregate.grade_label(p)
            roster.append({**p, "grade_label": glabel, "grade_sort": gsort,
                            "s_rec": f"{rec['s'][0]}-{rec['s'][1]}" if rec and sum(rec["s"]) else "—",
                            "d_rec": f"{rec['d'][0]}-{rec['d'][1]}" if rec and sum(rec["d"]) else "—"})
        w("team.html", SITE / "teams" / fname, rel="../", team=t,
          blurb=prose.team_blurb(t), color=crest_color(name), initials=initials(name),
          classification=classification, league=league, own_href=fname, bracket_href=bracket_href,
          standing=standing_row, sections=aggregate.schedule_sections(t["schedule"]),
          roster=roster, m=team_metrics.get((pid, scope_id)))

    # players/index.html + player pages
    cards = [{"player_id": pid, "name": c["name"], "teams": sorted(c["teams"]),
              "wins": c["wins"], "losses": c["losses"],
              "grade": aggregate.grade_label(c["bio"])[0],
              "href": f"{aggregate.slug(pid)}.html"} for pid, c in
             sorted(careers.items(), key=lambda kv: kv[1]["name"])]
    w("players_index.html", SITE / "players" / "index.html", rel="../", careers=cards)

    for pid, c in careers.items():
        total = c["wins"] + c["losses"]
        pct = c["wins"] / total if total else 0.0
        fname = f"{aggregate.slug(pid)}.html"
        w("player.html", SITE / "players" / fname, rel="../", career=c, blurb=prose.player_blurb(c),
          pct=pct, total=total or 1, pvar=player_value.get(pid))

    # seasons — one dashboard per scope: class-first rankings on the archived
    # power index, league standings, individual leaders and awards as views
    # of one season, never a statewide splat.
    w("seasons_index.html", SITE / "seasons" / "index.html", rel="../", bundles=bundles,
      boards=boards)
    for scope_id, board in boards.items():
        w("season.html", SITE / "seasons" / f"{scope_id}.html", rel="../", board=board)

    # metrics / analytics — ONE sortable, filterable Stat Center grid over
    # every (team, season), plus Player Value. The seven single-metric splat
    # pages this replaces were unparseable at real scale.
    stat_rows = []
    for (pid, scope_id), m in team_metrics.items():
        if m.duals == 0:
            continue    # context-only program rows (scope_member=0) have no season here
        b = next(bb for bb in bundles if bb.scope_id == scope_id)
        stat_rows.append(_team_stat_row(pid, scope_id, m, b))
    stat_rows.sort(key=lambda r: (r["scope_label"], r["classification"], r["name"]))
    stat_scopes = []
    for b in bundles:
        classes = sorted({r["classification"] for r in stat_rows if r["scope_id"] == b.scope_id},
                         key=aggregate.classification_sort_key)
        leagues = {cls: sorted({r["league"] for r in stat_rows
                                if r["scope_id"] == b.scope_id and r["classification"] == cls})
                   for cls in classes}
        stat_scopes.append({"scope_id": b.scope_id, "label": b.label,
                             "classes": classes, "leagues": leagues})
    w("metrics_index.html", SITE / "metrics" / "index.html", rel="../")
    w("metrics_teams.html", SITE / "metrics" / "teams.html", rel="../",
      rows=stat_rows, scopes=stat_scopes)

    value_rows = []
    for pid, pv in player_value.items():
        c = careers[pid]
        glabel, gsort = aggregate.grade_label(c["bio"])
        value_rows.append({"player_id": pid, "name": c["name"], "teams": sorted(c["teams"]),
                            "wins": c["wins"], "losses": c["losses"], "pvar": pv["total"],
                            "grade": glabel, "grade_sort": gsort})
    value_rows.sort(key=lambda r: -r["pvar"])
    w("metrics_value.html", SITE / "metrics" / "value.html", rel="../", rows=value_rows[:100])

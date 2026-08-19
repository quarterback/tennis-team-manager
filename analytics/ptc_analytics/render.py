"""Render the static site from ingested bundles + computed aggregates."""
from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import aggregate, metrics as metrics_mod, prose

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"
SITE = HERE.parent / "site"

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


def _classification_sort_key(cls: str):
    """Biggest/most-competitive classification first: JHSAA '9A'..'1A' by the
    leading number descending, college 'D1'..'D4' likewise. Falls back to the
    raw string for anything else so an unrecognized value doesn't crash the
    build, it just sorts last alphabetically."""
    digits = "".join(c for c in cls if c.isdigit())
    return (0, -int(digits)) if digits else (1, cls)


def build_site(raw_bundles: list[dict]) -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "teams").mkdir(parents=True, exist_ok=True)
    (SITE / "players").mkdir(parents=True, exist_ok=True)
    (SITE / "leaderboards").mkdir(parents=True, exist_ok=True)
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
    stories = metrics_mod.storylines(team_metrics)
    player_value = metrics_mod.compute_player_value(careers)

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
        for cls, data in sorted(b.championships.items(), key=lambda kv: _classification_sort_key(kv[0])):
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
    # -> league, never a flat list of everything. A classification/division is
    # `program["classification"]` (JHSAA) or `program["division"]` (college,
    # constant within a scope but included for a uniform template); the league
    # is `district` (JHSAA) or `conference` (college).
    team_cards = []
    for (pid, scope_id), t in teams.items():
        b = t["bundle"]
        prog = t["program"]
        classification = prog.get("classification") or prog.get("division") or "—"
        league = prog.get("district") or prog.get("conference") or "—"
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
        for cls, leagues in sorted(by_class.items(), key=lambda kv: _classification_sort_key(kv[0])):
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
        classification = prog.get("classification") or prog.get("division") or "—"
        league = prog.get("district") or prog.get("conference") or "—"
        bracket_href = None
        for scope in bracket_scopes:
            if scope["scope_id"] != scope_id:
                continue
            for cls in scope["classifications"]:
                if cls["name"] == classification:
                    bracket_href = cls["href"]
        w("team.html", SITE / "teams" / fname, rel="../", team=t,
          blurb=prose.team_blurb(t), color=crest_color(name), initials=initials(name),
          classification=classification, league=league, own_href=fname, bracket_href=bracket_href)

    # players/index.html + player pages
    career_list = sorted(careers.values(), key=lambda c: c["name"])
    cards = [{"player_id": pid, "name": c["name"], "teams": sorted(c["teams"]),
              "wins": c["wins"], "losses": c["losses"],
              "href": f"{aggregate.slug(pid)}.html"} for pid, c in
             sorted(careers.items(), key=lambda kv: kv[1]["name"])]
    w("players_index.html", SITE / "players" / "index.html", rel="../", careers=cards)

    for pid, c in careers.items():
        total = c["wins"] + c["losses"]
        pct = c["wins"] / total if total else 0.0
        fname = f"{aggregate.slug(pid)}.html"
        w("player.html", SITE / "players" / fname, rel="../", career=c, blurb=prose.player_blurb(c),
          pct=pct, total=total or 1, pvar=player_value.get(pid))

    # leaderboards
    w("leaderboards_index.html", SITE / "leaderboards" / "index.html", rel="../", bundles=bundles)
    for scope_id, board in boards.items():
        w("leaderboards_scope.html", SITE / "leaderboards" / f"{scope_id}.html", rel="../", board=board)

    # metrics / analytics
    w("metrics_index.html", SITE / "metrics" / "index.html", rel="../")

    shape_rows = []
    fmt_rows = []
    resume_rows = []
    for (pid, scope_id), m in team_metrics.items():
        b = next(bb for bb in bundles if bb.scope_id == scope_id)
        base = {"program_id": pid, "scope_id": scope_id, "name": m.name, "scope_label": b.label}
        shape_rows.append({**base, "s_pct": m.s_pct, "d_pct": m.d_pct, "dr": m.doubles_reliance,
                            "balance": m.balance, "lines_played": m.lines_played})
        fmt_rows.append({**base, "rci": m.card_index("regular"), "sci": m.card_index("state"),
                          "fmt": m.fmt_lift, "swp": m.state_dual_win_prob()})
        q = m.quartile_record
        lg = m.league_record
        resume_rows.append({**base,
            "q1": f"{q.get('Q1', {}).get('w', 0)}-{q.get('Q1', {}).get('l', 0)}",
            "q4": f"{q.get('Q4', {}).get('w', 0)}-{q.get('Q4', {}).get('l', 0)}",
            "league": f"{lg.get('league', {}).get('w', 0)}-{lg.get('league', {}).get('l', 0)}",
            "non_league": f"{lg.get('non_league', {}).get('w', 0)}-{lg.get('non_league', {}).get('l', 0)}",
            "close": f"{m.close_wins}-{m.close_duals - m.close_wins}" if m.close_duals else "—",
        })
    shape_rows.sort(key=lambda r: -(r["dr"] or -999) if r["dr"] is not None else 999)
    fmt_rows.sort(key=lambda r: -(r["fmt"] if r["fmt"] is not None else -999))
    resume_rows.sort(key=lambda r: r["name"])

    w("metrics_shape.html", SITE / "metrics" / "shape.html", rel="../", rows=shape_rows)
    w("metrics_format_lift.html", SITE / "metrics" / "format-lift.html", rel="../", rows=fmt_rows)
    w("metrics_resume.html", SITE / "metrics" / "resume.html", rel="../", rows=resume_rows)

    depth_rows = []
    pred_rows = []
    for (pid, scope_id), m in team_metrics.items():
        b = next(bb for bb in bundles if bb.scope_id == scope_id)
        base = {"program_id": pid, "scope_id": scope_id, "name": m.name, "scope_label": b.label}
        depth_rows.append({**base, "top": m.top_end_index, "depth": m.depth_index,
                            "star_dep": m.star_dependence, "floor": m.floor, "ceiling": m.ceiling,
                            "vol": m.volatility, "blowout": m.blowout_rate, "resist": m.resistance_rate})
        pred_rows.append({**base, "record": f"{m.dual_wins}-{m.duals - m.dual_wins}",
                           "expected": m.expected_wins, "luck": m.record_luck,
                           "uv": m.upset_value, "blv": m.bad_loss_value, "ews": m.elite_win_share})
    depth_rows.sort(key=lambda r: -(r["star_dep"] or -999) if r["star_dep"] is not None else 999)
    pred_rows.sort(key=lambda r: -(r["luck"] if r["luck"] is not None else -999))
    w("metrics_depth.html", SITE / "metrics" / "depth.html", rel="../", rows=depth_rows)
    w("metrics_predictive.html", SITE / "metrics" / "predictive.html", rel="../", rows=pred_rows)

    value_rows = []
    for pid, pv in player_value.items():
        c = careers[pid]
        value_rows.append({"player_id": pid, "name": c["name"], "teams": sorted(c["teams"]),
                            "wins": c["wins"], "losses": c["losses"], "pvar": pv["total"]})
    value_rows.sort(key=lambda r: -r["pvar"])
    w("metrics_value.html", SITE / "metrics" / "value.html", rel="../", rows=value_rows[:100])

    kinds = [("format-lift", "Format Lift"), ("team-shape", "Team Shape"), ("record-luck", "Record Luck"),
             ("upsets", "Upsets"), ("close-matches", "Close Matches"),
             ("volatility", "Volatility"), ("quality-wins", "Quality Wins"), ("bad-losses", "Bad Losses")]
    stories_by_kind = {}
    for s in stories:
        stories_by_kind.setdefault(s["kind"], []).append(s)
    w("metrics_storylines.html", SITE / "metrics" / "storylines.html", rel="../",
      stories=stories, kinds=kinds, stories_by_kind=stories_by_kind)

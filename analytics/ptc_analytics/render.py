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


def build_site(raw_bundles: list[dict]) -> None:
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "teams").mkdir(parents=True, exist_ok=True)
    (SITE / "players").mkdir(parents=True, exist_ok=True)
    (SITE / "leaderboards").mkdir(parents=True, exist_ok=True)
    (SITE / "metrics").mkdir(parents=True, exist_ok=True)
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

    def w(tmpl: str, out: Path, rel: str, **ctx):
        html = env.get_template(tmpl).render(rel=rel, **ctx)
        out.write_text(html)

    # index.html
    w("index.html", SITE / "index.html", rel="",
      bundles=bundles, scopes=[b.scope_id for b in bundles],
      team_count=len({k[0] for k in teams}), player_count=len(careers),
      dual_count=sum(len(b.duals) for b in bundles))

    # teams/index.html + team pages
    team_cards = []
    for (pid, scope_id), t in teams.items():
        b = t["bundle"]
        team_cards.append({"program": t["program"], "bundle": b, "wins": t["wins"], "losses": t["losses"],
                            "color": crest_color(t["program"]["name"]), "initials": initials(t["program"]["name"]),
                            "href": f"{aggregate.slug(scope_id)}__{aggregate.slug(pid)}.html"})
    team_cards.sort(key=lambda c: c["program"]["name"])
    w("teams_index.html", SITE / "teams" / "index.html", rel="../", teams=team_cards)

    for (pid, scope_id), t in teams.items():
        fname = f"{aggregate.slug(scope_id)}__{aggregate.slug(pid)}.html"
        name = t["program"]["name"]
        w("team.html", SITE / "teams" / fname, rel="../", team=t,
          blurb=prose.team_blurb(t), color=crest_color(name), initials=initials(name))

    # players/index.html + player pages
    career_list = sorted(careers.values(), key=lambda c: c["name"])
    cards = [{"player_id": pid, "name": c["name"], "teams": sorted(c["teams"]),
              "wins": c["wins"], "losses": c["losses"]} for pid, c in
             sorted(careers.items(), key=lambda kv: kv[1]["name"])]
    w("players_index.html", SITE / "players" / "index.html", rel="../", careers=cards)

    for pid, c in careers.items():
        total = c["wins"] + c["losses"]
        pct = c["wins"] / total if total else 0.0
        fname = f"{aggregate.slug(pid)}.html"
        w("player.html", SITE / "players" / fname, rel="../", career=c, blurb=prose.player_blurb(c),
          pct=pct, total=total or 1)

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
        fmt_rows.append({**base, "rci": m.card_index(m.family, "regular"), "sci": m.card_index(m.family, "state"),
                          "fmt": m.fmt_lift, "swp": m.state_dual_win_prob(m.family)})
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

    kinds = [("format-lift", "Format Lift"), ("team-shape", "Team Shape"), ("close-matches", "Close Matches"),
             ("volatility", "Volatility"), ("quality-wins", "Quality Wins"), ("bad-losses", "Bad Losses")]
    stories_by_kind = {}
    for s in stories:
        stories_by_kind.setdefault(s["kind"], []).append(s)
    w("metrics_storylines.html", SITE / "metrics" / "storylines.html", rel="../",
      stories=stories, kinds=kinds, stories_by_kind=stories_by_kind)

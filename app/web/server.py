"""
Baseline web app (Flask) — the only way users touch the sim, mirroring the
O27 baseball model (web UI over a sim engine).

Implemented now: the **Rankings / Power Index** flagship (design kit
ui_kits/rankings) + the Methodology page. Other nav sections are roadmap
placeholders (P2/P6/P7/P8) so the chrome is complete and navigable.

Run:  python3 manage.py runserver   (PORT env to override; default 5000)
"""
from __future__ import annotations

import os
from flask import Flask, render_template, request, abort, redirect, url_for

from .rankings_data import all_schools, crest, get_row
from .sim import run_dual_view, FIDELITIES, programs_for
from .state import (ranking_rows, conferences_for, get_bracket, UNIVERSES, FIELD_PRESETS,
                    recruit_rows, get_recruit, recruit_profile, team_roster,
                    RECRUIT_GENDERS, editor_roster, all_programs_grouped,
                    active_overrides, reset_all)
from app.juniors import US_STATES

from app import seasonmode as sm
from app import overrides as ov
from .state import DEFAULT_SEED

# label → route; drives the green TopNav across every page.
NAV = [
    ("Rankings", "/"),
    ("Season", "/season"),
    ("Dual Simulator", "/dual"),
    ("Bracket", "/bracket"),
    ("Recruiting", "/recruiting"),
    ("Teams", "/teams"),
    ("Editor", "/editor"),
    ("Methodology", "/methodology"),
]

def _universe(req) -> tuple[str, str, str, str]:
    """Resolve (division, gender, label, u-key) from the request."""
    u = req.args.get("u", "D1-men")
    match = next((x for x in UNIVERSES if x[0] == u), UNIVERSES[0])
    _, division, gender, label = match
    return division, gender, label, match[0]


def create_app() -> Flask:
    app = Flask(__name__)

    @app.context_processor
    def _inject_nav():
        return {"nav": NAV, "universes": UNIVERSES}

    @app.route("/")
    def rankings():
        division, gender, label, u = _universe(request)
        conf = request.args.get("conf", "All")
        tier = request.args.get("tier", "All")
        sort = request.args.get("sort", "Rank")
        rows = ranking_rows(division, gender)
        total = len(rows)
        tiers = ["All"] + sorted({r.tier for r in rows})
        filtered = [r for r in rows
                    if (conf == "All" or r.conf == conf) and (tier == "All" or r.tier == tier)]
        if sort == "Power Index":
            filtered = sorted(filtered, key=lambda r: r.pi, reverse=True)
        elif sort == "APR":
            filtered = sorted(filtered, key=lambda r: r.apr, reverse=True)
        # Unfiltered view shows the top of the table; filtered shows all matches.
        shown = filtered if (conf != "All" or tier != "All") else filtered[:75]
        return render_template(
            "rankings.html", active="Rankings", rows=shown, total=total, shown=len(shown),
            conferences=conferences_for(division, gender), tiers=tiers,
            conf=conf, tier=tier, sort=sort, u=u, uni_label=label,
        )

    @app.route("/bracket")
    def bracket():
        division, gender, label, u = _universe(request)
        try:
            size = int(request.args.get("size", 64))
        except ValueError:
            size = 64
        br = get_bracket(division, gender, size=size)
        return render_template("bracket.html", active="Bracket", br=br, u=u,
                               uni_label=label, division=division,
                               field=len(br.seeds), field_presets=FIELD_PRESETS)

    @app.route("/api/health")
    def health():
        return {"status": "ok"}, 200

    @app.route("/methodology")
    def methodology():
        return render_template("methodology.html", active="Methodology")

    @app.route("/dual")
    def dual():
        division, gender, label, u = _universe(request)
        schools = programs_for(division, gender)
        ranks = {r.school: r for r in ranking_rows(division, gender)}
        home = request.args.get("home") or ("Oregon" if "Oregon" in schools else schools[0])
        away = request.args.get("away") or ("Stanford" if "Stanford" in schools else schools[1])
        return render_template("dual_setup.html", active="Dual Simulator", schools=schools,
                               home=home, away=away, crest=crest, ranks=ranks,
                               fidelities=FIDELITIES, u=u, uni_label=label)

    @app.route("/dual/run")
    def dual_run():
        division, gender, label, u = _universe(request)
        schools = programs_for(division, gender)
        home = request.args.get("home") or schools[0]
        away = request.args.get("away") or schools[1]
        if home == away:
            away = next(s for s in schools if s != home)
        try:
            seed = int(request.args.get("seed", "7"))
        except ValueError:
            seed = 7
        fidelity = request.args.get("fidelity", "full")
        if fidelity not in FIDELITIES:
            fidelity = "full"
        view = run_dual_view(division, gender, home, away, seed=seed, fidelity=fidelity)
        return render_template("dual_result.html", active="Dual Simulator", v=view,
                               home=home, away=away, u=u)

    @app.route("/teams")
    def teams():
        division, gender, label, u = _universe(request)
        school = request.args.get("school", "Oregon")
        rows = team_roster(division, gender, school)
        if not rows:                                  # fall back to a real school
            school = ranking_rows(division, gender)[0].school
            rows = team_roster(division, gender, school)
        schools = [r.school for r in ranking_rows(division, gender)]
        abbr, color = crest(school)
        row = get_row(school)
        return render_template("teams.html", active="Teams", rows=rows, school=school,
                               abbr=abbr, color=color, row=row, schools=schools, u=u,
                               uni_label=label)

    @app.route("/player/<pid>")
    def player(pid):
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=DEFAULT_SEED)
        info = sm.player_info(sid, pid)
        if not info:
            abort(404)
        log = sm.player_log(sid, pid)
        strv, rel = sm.season_player_str(sid).get(pid, (None, 0.0))
        wins = sum(1 for m in log if m["won"])
        return render_template("player.html", active="Teams", pid=pid, info=info, log=log,
                               strv=strv, rel=rel, wins=wins, losses=len(log) - wins,
                               crest=crest, u=u, uni_label=label)

    @app.route("/recruiting")
    def recruiting():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        try:
            grad_year = int(request.args.get("grad_year", "2026"))
        except ValueError:
            grad_year = 2026
        scope = request.args.get("scope", "national")
        state = request.args.get("state", "California")
        rows = recruit_rows(rg, grad_year, scope=scope, state=state)
        return render_template("recruiting.html", active="Recruiting", rows=rows[:100],
                               total=len(rows), gender=gender, grad_year=grad_year,
                               scope=scope, state=state, u=u, uni_label=label,
                               states=[s for s, _ in US_STATES],
                               grad_years=[2026, 2027, 2028, 2029])

    @app.route("/recruit/<pid>")
    def recruit(pid):
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        try:
            grad_year = int(request.args.get("grad_year", "2026"))
        except ValueError:
            grad_year = 2026
        p = get_recruit(rg, grad_year, pid)
        if p is None:
            abort(404)
        view = recruit_profile(p, rg, grad_year)
        return render_template("recruit.html", active="Recruiting", p=p, view=view,
                               gender=gender, grad_year=grad_year, u=u, uni_label=label)

    # ------------------------------------------------------------------ Editor
    @app.route("/editor")
    def editor():
        division, gender, label, u = _universe(request)
        schools = [r.school for r in ranking_rows(division, gender)]
        school = request.args.get("school") or (schools[0] if schools else "")
        rows, head = editor_roster(division, gender, school)
        if rows is None:
            school = schools[0]
            rows, head = editor_roster(division, gender, school)
        return render_template("editor.html", active="Editor", u=u, uni_label=label,
                               school=school, schools=schools, rows=rows, head=head,
                               groups=all_programs_grouped(), ov=active_overrides())

    @app.route("/editor/move", methods=["POST"])
    def editor_move():
        u = request.form.get("u", "D1-men")
        school = request.form.get("school", "")
        pid = request.form.get("pid", "")
        dest = request.form.get("dest", "")
        if pid and dest:
            ov.set_move(pid, dest)
            reset_all()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/lineup", methods=["POST"])
    def editor_lineup():
        division, gender, label, u = _universe(request)
        school = request.form.get("school", "")
        pid = request.form.get("pid", "")
        direction = request.form.get("dir", "")
        rows, _ = editor_roster(division, gender, school)
        order = [r["pid"] for r in (rows or [])]
        if pid in order:
            i = order.index(pid)
            j = i - 1 if direction == "up" else i + 1
            if 0 <= j < len(order):
                order[i], order[j] = order[j], order[i]
                ov.set_lineup(school, order)
                reset_all()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/clear_move", methods=["POST"])
    def editor_clear_move():
        u = request.form.get("u", "D1-men")
        school = request.form.get("school", "")
        pid = request.form.get("pid", "")
        if pid:
            ov.clear_move(pid)
            reset_all()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/clear_lineup", methods=["POST"])
    def editor_clear_lineup():
        u = request.form.get("u", "D1-men")
        school = request.form.get("school", "")
        if school:
            ov.clear_lineup(school)
            reset_all()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/reset", methods=["POST"])
    def editor_reset():
        u = request.form.get("u", "D1-men")
        school = request.form.get("school", "")
        ov.clear_all()
        reset_all()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/season")
    def season_hub():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=DEFAULT_SEED)
        s = sm.load_season(sid)
        cw, tw = s["current_week"], s["total_weeks"]
        upcoming = sm.week_duals(sid, cw) if s["phase"] == "regular" and cw <= tw else []
        last = sm.recent_duals(sid)
        champions = {}
        if s["phase"] in ("ncaa", "complete") and s["champion"]:
            try:
                champions = __import__("json").loads(s["champion"]) if s["phase"] == "ncaa" else {}
            except Exception:
                champions = {}
        return render_template("season.html", active="Season", s=s, u=u, uni_label=label,
                               upcoming=upcoming, last=last, top=sm.national_top(sid, 15), crest=crest)

    @app.route("/season/advance", methods=["POST"])
    def season_advance():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=DEFAULT_SEED)
        sm.advance(sid)
        return redirect(url_for("season_hub", u=u))

    @app.route("/season/standings")
    def season_standings():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=DEFAULT_SEED)
        return render_template("season_standings.html", active="Season", u=u, uni_label=label,
                               standings=sm.standings(sid))

    @app.route("/season/schedule")
    def season_schedule():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=DEFAULT_SEED)
        school = request.args.get("school", "Oregon")
        schools = [r.school for r in ranking_rows(division, gender)]
        return render_template("season_schedule.html", active="Season", u=u, uni_label=label,
                               rows=sm.team_schedule(sid, school), school=school, schools=schools)

    @app.route("/season/dual/<int:dual_id>")
    def season_dual(dual_id):
        division, gender, label, u = _universe(request)
        d = sm.dual_detail(dual_id)
        if not d:
            abort(404)
        return render_template("season_dual.html", active="Season", u=u, uni_label=label,
                               d=d, crest=crest)

    return app


def main():
    port = int(os.environ.get("PORT", "5000"))
    create_app().run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()

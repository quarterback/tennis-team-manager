"""
Play to Clinch web app (Flask) — the only way users touch the sim, mirroring the
O27 baseball model (web UI over a sim engine).

Implemented now: the **Rankings / Power Index** flagship (design kit
ui_kits/rankings) + the Methodology page. Other nav sections are roadmap
placeholders (P2/P6/P7/P8) so the chrome is complete and navigable.

Run:  python3 manage.py runserver   (PORT env to override; default 5000)
"""
from __future__ import annotations

import os
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify

from .rankings_data import all_schools, crest, get_row
from .sim import run_dual_view, FIDELITIES, programs_for
from .state import (ranking_rows, conferences_for, get_bracket, UNIVERSES, FIELD_PRESETS,
                    recruit_rows, get_recruit, recruit_profile, team_roster,
                    RECRUIT_GENDERS, editor_roster, all_programs_grouped,
                    active_overrides, reset_all, teams_by_conference, coaching_staff,
                    junior_ranking_rows, junior_nation_boards, junior_leaders, junior_feed,
                    junior_setup_view, save_junior_setup, reset_junior_setup,
                    dashboard_view, team_budget, team_results,
                    conference_schools, team_conference, world_hub, player_career, get_coach)
from .state import preseason_view as preseason_view_data
from app import world as wd
from app.juniors import US_STATES
from .pagination import paginate
from .awards import (season_awards, player_career_honors, stamp_world_honors,
                     coach_career_honors, coach_honor_records)

from app import seasonmode as sm
from app import overrides as ov
from app.ncaa import load_division
from .state import DEFAULT_SEED

MY_TEAM = "Oregon"          # the club the human manages

# Grouped sidebar nav (Football-Manager style). Each item's href is resolved
# per-request so the universe `u` carries through. "World" is the primary
# season-to-season surface; the legacy per-universe season views sit under it.
NAV_GROUPS = [
    ("Your Team", [
        {"id": "preseason", "label": "Preseason",     "icon": "⚙️", "endpoint": "preseason_view",   "args": {}},
        {"id": "roster",    "label": "Roster",       "icon": "🎾", "endpoint": "teams",           "args": {"school": MY_TEAM}},
        {"id": "schedule",  "label": "Schedule",     "icon": "📅", "endpoint": "season_schedule", "args": {"school": MY_TEAM}},
    ]),
    ("World", [
        {"id": "world",     "label": "World Hub",    "icon": "🌎", "endpoint": "world_view",       "args": {}},
        {"id": "dashboard", "label": "Dashboard",    "icon": "🏠", "endpoint": "dashboard",        "args": {}},
        {"id": "rankings",  "label": "Rankings",     "icon": "🏆", "endpoint": "rankings",         "args": {}},
        {"id": "standings", "label": "Standings",    "icon": "📊", "endpoint": "season_standings", "args": {}},
        {"id": "awards",    "label": "Awards",       "icon": "🏅", "endpoint": "awards",           "args": {}},
        {"id": "hof",       "label": "Hall of Fame", "icon": "🏛️", "endpoint": "hall_of_fame",     "args": {}},
        {"id": "teams",     "label": "All Teams",    "icon": "🏫", "endpoint": "teams",            "args": {}},
    ]),
    ("Management", [
        {"id": "recruiting","label": "Recruiting",   "icon": "🎓", "endpoint": "recruiting",       "args": {}},
        {"id": "juniors",   "label": "Junior Rankings","icon": "🌐", "endpoint": "junior_rankings",  "args": {}},
    ]),
    ("Simulate", [
        {"id": "season",    "label": "Season Mode",  "icon": "📆", "endpoint": "season_hub",       "args": {}},
        {"id": "dual",      "label": "Dual Match",   "icon": "⚔️", "endpoint": "dual",             "args": {}},
        {"id": "bracket",   "label": "NCAA Bracket", "icon": "🥇", "endpoint": "bracket",          "args": {}},
        {"id": "projection","label": "Bracket Projection","icon": "🔮", "endpoint": "projection",   "args": {}},
    ]),
    ("Tools", [
        {"id": "editor",    "label": "Editor",       "icon": "🛠️", "endpoint": "editor",          "args": {}},
        {"id": "junior_setup","label": "Junior Setup","icon": "🎛️", "endpoint": "junior_setup",    "args": {}},
        {"id": "methodology","label": "Methodology", "icon": "📐", "endpoint": "methodology",      "args": {}},
    ]),
]


def _active_nav(req) -> str:
    p = req.path
    if p == "/":                          return "dashboard"
    if p.startswith("/preseason"):        return "preseason"
    if p.startswith("/world"):            return "world"
    if p.startswith("/rankings"):         return "rankings"
    if p.startswith("/awards"):           return "awards"
    if p.startswith("/hall-of-fame"):     return "hof"
    if p.startswith("/season/standings"): return "standings"
    if p.startswith("/season/schedule"):  return "schedule"
    if p.startswith("/season"):           return "season"
    if p.startswith("/dual"):             return "dual"
    if p.startswith("/projection"):       return "projection"
    if p.startswith("/bracket"):          return "bracket"
    if p.startswith("/tools/junior"):     return "junior_setup"
    if p.startswith("/juniors"):          return "juniors"
    if p.startswith("/recruit"):          return "recruiting"
    if p.startswith("/teams") or p.startswith("/player"):
        return "roster" if req.args.get("school") == MY_TEAM else "teams"
    if p.startswith("/editor"):           return "editor"
    if p.startswith("/methodology"):      return "methodology"
    return ""


def _game_context():
    """Persistent world state for the top bar (year / week / signed class).
    None before a world is started, so the bar hides cleanly."""
    try:
        if not wd.exists():
            return None
        w = wd.load_world()
        return {"year": 2026 + w["year"], "season_no": w["year"] + 1,
                "week": w["week"], "phase": "Regular season", "complete": False,
                "signed": sum(wd.signed_counts().values())}
    except Exception:
        return None


def _universe(req) -> tuple[str, str, str, str]:
    """Resolve (division, gender, label, u-key) from the request."""
    u = req.args.get("u", "D1-men")
    match = next((x for x in UNIVERSES if x[0] == u), UNIVERSES[0])
    _, division, gender, label = match
    return division, gender, label, match[0]


def create_app() -> Flask:
    app = Flask(__name__)

    # Create every DB schema up front (before any sim transaction) so nested
    # connections never deadlock on first-time table creation.
    from app import db as _db
    _db.bootstrap()

    from .formatters import (
        flag, flags, country_name, country_abbrev,
        team_logo, has_team_logo, team_logo_src,
    )
    app.jinja_env.filters["flag"] = flag
    app.jinja_env.filters["flags"] = flags
    app.jinja_env.filters["country_name"] = country_name
    app.jinja_env.filters["country_abbrev"] = country_abbrev
    app.jinja_env.filters["team_logo"] = team_logo
    app.jinja_env.filters["has_team_logo"] = has_team_logo
    app.jinja_env.filters["team_logo_src"] = team_logo_src

    @app.context_processor
    def _inject_chrome():
        """Everything the persistent FM shell needs on every page: grouped
        sidebar (hrefs resolved with the current universe), active item, and the
        world game-context top bar."""
        division, gender, label, u = _universe(request)
        groups = [(glabel, [{**it, "href": url_for(it["endpoint"], u=u, **it["args"])}
                            for it in items])
                  for glabel, items in NAV_GROUPS]
        return {"universes": UNIVERSES, "u": u, "uni_label": label, "my_team": MY_TEAM,
                "nav_groups": groups, "active_nav": _active_nav(request),
                "game": _game_context()}

    @app.before_request
    def _prime_world():
        # A league exists → prime every page to its current week and carry on.
        if wd.exists():
            wd.prime()
            return
        # No league yet → the entry point (dashboard) is the "ongoing sim" the
        # user lands in, so send first-login there to onboarding instead. Other
        # pages stay browsable against the deterministic baseline.
        if request.endpoint == "dashboard":
            return redirect(url_for("onboarding"))

    @app.route("/start")
    def onboarding():
        from app import worldconfig
        return render_template("onboarding.html", active="World",
                               bands=worldconfig.BANDS, band=worldconfig.name_preset(),
                               region_groups=worldconfig.region_groups(),
                               mult_choices=worldconfig.MULT_CHOICES)

    @app.route("/world/new", methods=["POST"])
    def world_new():
        # Persist the nationality band, per-region tuning and active universes
        # BEFORE seeding (generation reads them). Then reset any existing world and
        # begin a fresh league at preseason (week 0, nothing played), clearing the
        # web-layer caches too so no stale season/bracket/coach data (e.g. coach ids
        # wiped by the reset) survives into the new league.
        from app import worldconfig
        worldconfig.set_name_preset(request.form.get("name_preset", "tennis_global"))
        worldconfig.set_active(request.form.getlist("divisions"), request.form.getlist("genders"))
        # Per-region tuning: read mult_<region> for every region in the editor.
        mult = {}
        for grp in worldconfig.region_groups():
            for r in grp["regions"]:
                try:
                    mult[r["id"]] = float(request.form.get(f"mult_{r['id']}", "1"))
                except (TypeError, ValueError):
                    pass
        worldconfig.set_region_mult(mult)
        wd.start_new()
        reset_all()
        return redirect(url_for("world_view"))

    @app.route("/preseason")
    def preseason_view():
        return render_template("preseason.html", active="Preseason", ps=preseason_view_data())

    @app.route("/world")
    def world_view():
        return render_template("world.html", active="World", hub=world_hub(), crest=crest)

    @app.route("/world/advance", methods=["POST"])
    def world_advance():
        # Staged pipeline: during play this advances a week / postseason round.
        # Once every bracket is done, the awards phase must run BEFORE the roster
        # rolls over (so honors are captured against the right teams) — so block
        # rollover until honors are stamped (the hub shows "Run awards" instead).
        import app.honors as honors
        if wd.season_complete() and not honors.has_season(wd.BASE_YEAR + wd.load_world()["year"], "D1", "men"):
            return redirect(url_for("world_view"))
        wd.advance_week()
        return redirect(url_for("world_view"))

    @app.route("/world/awards", methods=["POST"])
    def world_awards():
        """Awards phase: stamp this year's honors (idempotent), then return to the
        hub so the next stage (begin next season) is offered."""
        stamp_world_honors()
        return redirect(request.referrer or url_for("world_view"))

    @app.route("/")
    def dashboard():
        division, gender, label, u = _universe(request)
        return render_template("dashboard.html", active="Dashboard", u=u, uni_label=label,
                               d=dashboard_view(division, gender))

    @app.route("/rankings")
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
        p = paginate(filtered, request.args.get("page", 1))
        return render_template(
            "rankings.html", active="Rankings", p=p, rows=p.items, total=total,
            matches=len(filtered), conferences=conferences_for(division, gender),
            tiers=tiers, conf=conf, tier=tier, sort=sort, u=u, uni_label=label,
        )

    @app.route("/coach/<coach_id>")
    def coach(coach_id):
        division, gender, label, u = _universe(request)
        c = get_coach(coach_id)
        if not c:
            abort(404)
        div = c.get("division", division)
        gen = c.get("gender", gender)
        honor_years = coach_career_honors(div, gen, coach_id)
        return render_template("coach.html", active="Teams", c=c, honor_years=honor_years,
                               crest=crest, u=u, uni_label=label)

    @app.route("/awards")
    def awards():
        division, gender, label, u = _universe(request)
        aw = season_awards(division, gender)
        coty = coach_honor_records(division, gender)
        coach_awards = {
            "national": next((r for r in coty if r["award"] == "national_coty"), None),
            "conference": sorted((r for r in coty if r["award"] == "conf_coty"),
                                 key=lambda r: r["label"]),
        }
        conf_p = paginate(aw["all_conference"], request.args.get("page", 1), per_page=6)
        return render_template("awards.html", active="Awards", aw=aw, conf_p=conf_p,
                               coach_awards=coach_awards, u=u, uni_label=label, crest=crest)

    @app.route("/hall-of-fame")
    def hall_of_fame():
        division, gender, label, u = _universe(request)
        import app.honors as honors
        uni_label = {(d, g): lbl for _v, d, g, lbl in UNIVERSES}
        archive = []
        for y in honors.years():
            rows = honors.winners(y, ["national_champion", "national_poty", "national_coty"])
            unis: dict = {}
            for r in rows:
                slot = unis.setdefault((r["division"], r["gender"]), {})
                if r["award"] == "national_champion":
                    slot.setdefault("champion", r["school"])      # one per team
                else:
                    slot[r["award"]] = r
            archive.append({
                "year": y,
                "universes": [(uni_label.get(k, f"{k[0]} {k[1]}"), v)
                              for k, v in sorted(unis.items())],
            })
        return render_template("hall_of_fame.html", active="Hall of Fame",
                               archive=archive, u=u, uni_label=label, crest=crest)

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
                               field=len(br.seeds) if br else 0, field_presets=FIELD_PRESETS)

    @app.route("/projection")
    def projection():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        return render_template("projection.html", active="Bracket", u=u, uni_label=label,
                               division=division, proj=sm.field_projection(sid))

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
        school = request.args.get("school")
        # No school selected → conference index (browse by conference/gender).
        if not school:
            conf = request.args.get("conf", "All")
            groups = teams_by_conference(division, gender, conf)
            p = paginate(groups, request.args.get("page", 1), per_page=8)
            return render_template("teams_index.html", active="Teams", u=u, uni_label=label,
                                   groups=p.items, p=p,
                                   conferences=conferences_for(division, gender), conf=conf)
        rows = team_roster(division, gender, school)
        if not rows:                                  # fall back to a real school
            school = ranking_rows(division, gender)[0].school
            rows = team_roster(division, gender, school)
        schools = [r.school for r in ranking_rows(division, gender)]
        abbr, color = crest(school)
        row = get_row(school)
        prog = load_division(division, gender).by_school(school)
        return render_template("teams.html", active="Teams", rows=rows, school=school,
                               abbr=abbr, color=color, row=row, schools=schools, u=u,
                               uni_label=label, staff=coaching_staff(division, gender, school),
                               results=team_results(division, gender, school), crest=crest,
                               city=(prog.location if prog else ""),
                               budget=team_budget(division, gender, school))

    @app.route("/player/<pid>")
    def player(pid):
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        info = sm.player_info(sid, pid)
        if not info:
            abort(404)
        # STR + career both come from the persisted week-by-week season, so the
        # card reflects matches actually played as the world advances (not a
        # pre-simulated baseline).
        strv, rel = sm.season_player_str(sid).get(pid, (None, 0.0))
        career, (wins, losses) = player_career(division, gender, pid)
        honor_years = player_career_honors(division, gender, pid)
        return render_template("player.html", active="Teams", pid=pid, info=info,
                               career=career, strv=strv, rel=rel, wins=wins, losses=losses,
                               honor_years=honor_years, crest=crest, u=u, uni_label=label)

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
        rows = recruit_rows(rg, grad_year, scope=scope, state=state, division=division)
        p = paginate(rows, request.args.get("page", 1))
        return render_template("recruiting.html", active="Recruiting", rows=p.items, p=p,
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
        p = get_recruit(rg, grad_year, pid, division=division)
        if p is None:
            abort(404)
        view = recruit_profile(p, division, gender, grad_year)
        return render_template("recruit.html", active="Recruiting", p=p, view=view,
                               gender=gender, grad_year=grad_year, u=u, uni_label=label)

    @app.route("/juniors/rankings")
    def junior_rankings():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        try:
            grad_year = int(request.args.get("grad_year", "2026"))
        except ValueError:
            grad_year = 2026
        scope = request.args.get("scope", "world")
        nation = request.args.get("nation", "")
        sort = request.args.get("sort", "rank")
        desc = request.args.get("dir", "desc") != "asc"
        boards = junior_nation_boards(rg, grad_year) if scope == "nation" and not nation else []
        rows = junior_ranking_rows(rg, grad_year, scope=scope, nation=nation, sort=sort, desc=desc)
        pg = paginate(rows, request.args.get("page", 1))
        from app.almanac import SORT_COLUMNS
        return render_template("junior_rankings.html", active="Recruiting", rows=pg.items,
                               p=pg, total=len(rows), gender=gender, grad_year=grad_year,
                               scope=scope, nation=nation, boards=boards, u=u, uni_label=label,
                               sort=sort, dir=("asc" if not desc else "desc"),
                               columns=SORT_COLUMNS, leaders=junior_leaders(rg, grad_year),
                               grad_years=[2026, 2027, 2028, 2029])

    @app.route("/juniors/feed.json")
    def junior_feed_json():
        _division, gender, _label, _u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        try:
            grad_year = int(request.args.get("grad_year", "2026"))
        except ValueError:
            grad_year = 2026
        return jsonify(junior_feed(rg, grad_year))

    @app.route("/tools/junior-setup", methods=["GET", "POST"])
    def junior_setup():
        division, gender, label, u = _universe(request)
        if request.method == "POST":
            if request.form.get("reset"):
                reset_junior_setup()
            else:
                save_junior_setup(request.form)
            return redirect(url_for("junior_setup", u=u))
        return render_template("junior_setup.html", active="Tools",
                               view=junior_setup_view(), u=u, uni_label=label)

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
        from app import scholarships as sch
        # Per (classification, gender) — women's tennis is a headcount sport,
        # men's an equivalency sport, so the caps differ by gender like real life.
        schol = [{"division": d, "gender": g, **sch.limits(d, g)}
                 for d in ("D1", "D2", "D3") for g in ("men", "women")]
        prog = load_division(division, gender).by_school(school)
        prestige = {"value": round((prog.prestige if prog else 0.5) * 100),
                    "overridden": school in ov.get_prestige()}
        return render_template("editor.html", active="Editor", u=u, uni_label=label,
                               school=school, schools=schools, rows=rows, head=head,
                               groups=all_programs_grouped(), ov=active_overrides(),
                               scholarships=schol, prestige=prestige,
                               schol_elite=sch.limits("D3", "men", academics=0.95))

    @app.route("/editor/prestige", methods=["POST"])
    def editor_prestige():
        school = request.form.get("school", "")
        u = request.form.get("u", "D1-men")
        try:
            val = float(request.form.get("prestige", "50")) / 100.0
        except ValueError:
            val = 0.5
        if school:
            ov.set_prestige(school, val)
            reset_all()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/prestige/clear", methods=["POST"])
    def editor_prestige_clear():
        school = request.form.get("school", "")
        u = request.form.get("u", "D1-men")
        if school:
            ov.clear_prestige(school)
            reset_all()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/scholarship", methods=["POST"])
    def editor_scholarship():
        from app import scholarships as sch
        u = request.form.get("u", "D1-men")
        for d in ("D1", "D2", "D3"):
            for g in ("men", "women"):
                kwargs = {}
                count_raw = request.form.get(f"count_{d}_{g}")
                cap_raw = request.form.get(f"cap_{d}_{g}")
                rate_raw = request.form.get(f"rate_{d}_{g}")
                if count_raw not in (None, ""):
                    try:
                        kwargs["count"] = int(count_raw)
                    except ValueError:
                        pass
                if cap_raw not in (None, ""):
                    try:
                        kwargs["cap"] = float(cap_raw)
                    except ValueError:
                        pass
                if rate_raw not in (None, ""):
                    try:
                        kwargs["rate"] = float(rate_raw)
                    except ValueError:
                        pass
                if kwargs:
                    sch.set_limit(d, g, **kwargs)
        reset_all()
        return redirect(url_for("editor", u=u))

    @app.route("/editor/scholarship/reset", methods=["POST"])
    def editor_scholarship_reset():
        from app import scholarships as sch
        sch.clear_overrides()
        reset_all()
        return redirect(url_for("editor", u=request.form.get("u", "D1-men")))

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
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
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
                               upcoming=upcoming, last=last, top=sm.national_top(sid, 15), crest=crest,
                               bubble=sm.bubble_watch(sid))

    @app.route("/season/advance", methods=["POST"])
    def season_advance():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        sm.advance(sid)
        return redirect(url_for("season_hub", u=u))

    @app.route("/season/standings")
    def season_standings():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        return render_template("season_standings.html", active="Season", u=u, uni_label=label,
                               standings=sm.standings(sid), bubble=sm.bubble_watch(sid))

    @app.route("/season/schedule")
    def season_schedule():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        groups = dict(conference_schools(division, gender))
        conferences = sorted(groups)
        conf = request.args.get("conf")
        school = request.args.get("school")
        # Resolve a (conference, team) pair from whatever was passed: a chosen
        # conference narrows the team list; otherwise derive the conference from
        # the team so the two dropdowns always stay in sync.
        if conf in groups:
            schools = groups[conf]
            if school not in schools:
                school = schools[0]
        else:
            school = school or ("Oregon" if "Oregon" in [s for g in groups.values() for s in g]
                                else conferences and groups[conferences[0]][0])
            conf = team_conference(division, gender, school) or (conferences[0] if conferences else "")
            schools = groups.get(conf, [school])
        rows = sm.team_schedule(sid, school)
        import datetime
        base = datetime.date(2026, 1, 16)        # season opens mid-January
        for r in rows:
            day = base + datetime.timedelta(weeks=int(r["week"]) - 1)
            r["date"] = day.strftime("%a, %b %-d")
        return render_template("season_schedule.html", active="Season", u=u, uni_label=label,
                               rows=rows, school=school, schools=schools,
                               conferences=conferences, conf=conf, crest=crest,
                               abbr=crest(school)[0], color=crest(school)[1])

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

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
from .state import (ranking_rows, singles_ranking_rows, doubles_ranking_rows,
                    conferences_for, get_bracket, get_doubles_championship,
                    get_singles_championship, championship_years, UNIVERSES, FIELD_PRESETS,
                    recruit_rows, get_recruit, recruit_profile, team_roster,
                    player_career_table, player_career_records, search_players,
                    results_by_week, ncaa_bracket_view, ncaa_bracket_years, transfer_portal_view,
                    RECRUIT_GENDERS, editor_roster, all_programs_grouped,
                    all_programs_by_universe,
                    active_overrides, reset_all, teams_by_conference, coaching_staff,
                    junior_ranking_rows, junior_nation_boards, junior_leaders, junior_feed,
                    junior_tournaments, junior_tournament_detail,
                    recruiting_hub, signing_tracker, team_recruiting_class,
                    junior_setup_view, save_junior_setup, reset_junior_setup,
                    dashboard_view, data_portal_view, team_budget, team_results,
                    program_history,
                    conference_schools, team_conference, conference_ratings,
                    world_hub, player_career, get_coach, injury_rows, fall_portal_view,
                    player_ranks, player_journey)
from .state import preseason_view as preseason_view_data
from app import world as wd
from app.juniors import US_STATES
from .pagination import paginate
from .awards import (season_awards, player_career_honors, stamp_world_honors,
                     coach_career_honors, coach_honor_records,
                     coach_career_table, coach_player_awards,
                     awards_archive, archive_years)

from app import seasonmode as sm
from app import gtt_seasonmode as gs
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
        {"id": "season",    "label": "Season Hub",   "icon": "📆", "endpoint": "season_hub",       "args": {}},
        {"id": "world",     "label": "World Hub",    "icon": "🌎", "endpoint": "world_view",       "args": {}},
        {"id": "dashboard", "label": "Dashboard",    "icon": "🏠", "endpoint": "dashboard",        "args": {}},
        {"id": "data",      "label": "Data Portal",  "icon": "📈", "endpoint": "data_portal",      "args": {}},
        {"id": "rankings",  "label": "Rankings",     "icon": "🏆", "endpoint": "rankings",         "args": {}},
        {"id": "results",   "label": "Results",      "icon": "📋", "endpoint": "results",          "args": {}},
        {"id": "ita",       "label": "ITA Opener",   "icon": "❄️", "endpoint": "season_ita",        "args": {}},
        {"id": "ncaa",      "label": "NCAA Bracket", "icon": "🥇", "endpoint": "ncaa_bracket",     "args": {}},
        {"id": "standings", "label": "Standings",    "icon": "📊", "endpoint": "season_standings", "args": {}},
        {"id": "injuries",  "label": "Injuries",     "icon": "🩹", "endpoint": "injuries_page",    "args": {}},
        {"id": "awards",    "label": "Awards",       "icon": "🏅", "endpoint": "awards",           "args": {}},
        {"id": "hof",       "label": "Hall of Fame", "icon": "🏛️", "endpoint": "hall_of_fame",     "args": {}},
        {"id": "teams",     "label": "All Teams",    "icon": "🏫", "endpoint": "teams",            "args": {}},
    ]),
    ("Management", [
        {"id": "rec_hub",   "label": "Recruiting HQ", "icon": "🏛️", "endpoint": "recruiting_hub_page","args": {}},
        {"id": "recruiting","label": "Recruiting Board","icon": "🎓","endpoint": "recruiting",       "args": {}},
        {"id": "transfers", "label": "Transfer Portal","icon": "🔁", "endpoint": "transfers",        "args": {}},
        {"id": "juniors",   "label": "Junior Rankings","icon": "🌐", "endpoint": "junior_rankings",  "args": {}},
        {"id": "jrtour",    "label": "Junior Tour",   "icon": "📅", "endpoint": "junior_tour",      "args": {}},
        {"id": "signings",  "label": "Signing Tracker","icon": "✍️", "endpoint": "signing_tracker_page","args": {}},
    ]),
    ("Analytics Bureau", [
        {"id": "intel",        "label": "Bureau HQ",        "icon": "🛰️", "endpoint": "intel_hub",         "args": {}},
        {"id": "intel_lineups","label": "Lineup Lab",       "icon": "📊", "endpoint": "intel_lineups",     "args": {}},
        {"id": "intel_under",  "label": "Underplaced Talent","icon": "📡", "endpoint": "intel_underplaced", "args": {}},
        {"id": "intel_aid",    "label": "Playing Time",    "icon": "🎾", "endpoint": "intel_scholarships", "args": {}},
    ]),
    ("Simulate", [
        {"id": "dual",      "label": "Dual Match",   "icon": "⚔️", "endpoint": "dual",             "args": {}},
        {"id": "bracket",   "label": "College Bracket", "icon": "🥇", "endpoint": "bracket",        "args": {}},
        {"id": "singles",   "label": "Singles Championship","icon": "🎾", "endpoint": "singles_championship", "args": {}},
        {"id": "doubles",   "label": "Doubles Championship","icon": "👥", "endpoint": "doubles_championship", "args": {}},
        {"id": "projection","label": "Bracket Projection","icon": "🔮", "endpoint": "projection",   "args": {}},
    ]),
    ("Pro Tour", [
        {"id": "gtt",       "label": "League Hub",   "icon": "🌐", "endpoint": "gtt_hub",          "args": {}},
        {"id": "gtt_hall",  "label": "Hall of Fame", "icon": "🏛️", "endpoint": "gtt_hall",         "args": {}},
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
    if p.startswith("/data"):             return "data"
    if p.startswith("/rankings"):         return "rankings"
    if p.startswith("/results"):          return "results"
    if p.startswith("/injuries"):         return "injuries"
    if p.startswith("/ncaa"):             return "ncaa"
    if p.startswith("/awards"):           return "awards"
    if p.startswith("/hall-of-fame"):     return "hof"
    if p.startswith("/season/standings"): return "standings"
    if p.startswith("/season/schedule"):  return "schedule"
    if p.startswith("/season/ita"):       return "ita"
    if p.startswith("/season"):           return "season"
    if p.startswith("/dual"):             return "dual"
    if p.startswith("/projection"):       return "projection"
    if p.startswith("/singles-championship"): return "singles"
    if p.startswith("/doubles-championship"): return "doubles"
    if p.startswith("/bracket"):          return "bracket"
    if p.startswith("/tools/junior"):     return "junior_setup"
    if p.startswith("/juniors/tour") or p.startswith("/juniors/tournament"): return "jrtour"
    if p.startswith("/intel/lineups"):    return "intel_lineups"
    if p.startswith("/intel/underplaced"): return "intel_under"
    if p.startswith("/intel/scholarships"): return "intel_aid"
    if p.startswith("/intel"):            return "intel"
    if p.startswith("/recruiting/team"):  return "signings"
    if p.startswith("/recruiting/signings"): return "signings"
    if p.startswith("/transfers"):        return "transfers"
    if p.startswith("/recruiting/hub"):   return "rec_hub"
    if p.startswith("/juniors"):          return "juniors"
    if p.startswith("/recruit"):          return "recruiting"
    if p.startswith("/teams") or p.startswith("/player"):
        return "roster" if req.args.get("school") == MY_TEAM else "teams"
    if p.startswith("/editor"):           return "editor"
    if p.startswith("/gtt/hall-of-fame"): return "gtt_hall"
    if p.startswith("/gtt"):              return "gtt"
    if p.startswith("/methodology"):      return "methodology"
    return ""


def _game_context():
    """Persistent world state for the top bar (year / week / signed class).
    None before a world is started, so the bar hides cleanly."""
    try:
        if not wd.exists():
            return None
        w = wd.load_world()
        # Reflect the live stage across ACTIVE universes (cheap single-row reads),
        # so the bar reads "Conf tournaments" / "NCAA championship" instead of
        # always "Regular season".
        import app.seasonmode as sm
        from app import worldconfig
        _ORD = {"ita_kickoff": 0, "ita_indoor": 1, "fall_portal": 1.5, "regular": 2,
                "conf_tournaments": 3, "selection": 4, "ncaa": 5, "complete": 6}
        _LBL = {"ita_kickoff": "ITA Kickoff Weekend", "ita_indoor": "ITA Indoor",
                "fall_portal": "Fall transfer portal", "regular": "Regular season",
                "conf_tournaments": "Conf tournaments", "selection": "Bracket reveal",
                "ncaa": "NCAA championship", "complete": "Postseason complete"}
        phases = []
        for _v, d, g, _lbl in UNIVERSES:
            if not worldconfig.is_active(d, g):
                continue
            s = sm.load_season(sm.get_or_create(d, g, seed=wd.current_year_seed()))
            phases.append(s.get("phase", "regular"))
        stage = min(phases, key=lambda p: _ORD.get(p, 0)) if phases else "regular"
        return {"year": 2026 + w["year"], "season_no": w["year"] + 1,
                "week": w["week"], "phase": _LBL.get(stage, "Regular season"),
                "complete": stage == "complete",
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

    @app.before_request
    def _publish_world_salt():
        # Keep the ncaa generator pinned to the active league's salt so every
        # roster/recruit built during this request matches the saved world.
        try:
            from app import world as _world
            _world.active_salt()
        except Exception:
            pass

    from .formatters import (
        flag, flags, country_name, country_abbrev, state_abbrev,
        team_logo, has_team_logo, team_logo_src,
    )
    app.jinja_env.filters["flag"] = flag
    app.jinja_env.filters["flags"] = flags
    app.jinja_env.filters["country_name"] = country_name
    app.jinja_env.filters["country_abbrev"] = country_abbrev
    app.jinja_env.filters["state_abbrev"] = state_abbrev
    app.jinja_env.filters["team_logo"] = team_logo
    app.jinja_env.filters["has_team_logo"] = has_team_logo
    app.jinja_env.filters["team_logo_src"] = team_logo_src
    from app.almanac import badge_shield, profile_badges
    app.jinja_env.filters["shield"] = badge_shield
    app.jinja_env.filters["profile_badges"] = profile_badges
    from .rankings_data import crest as _crest
    app.jinja_env.globals["crest"] = _crest

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

    @app.route("/export/db")
    def export_db():
        import sqlite3
        import tempfile
        from flask import after_this_request, send_file
        from app.dbpath import resolve_db_path

        token = os.environ.get("EXPORT_TOKEN")
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() \
            or request.args.get("token", "")
        if token and supplied != token:
            abort(404)
        src_path = resolve_db_path()
        if not os.path.exists(src_path):
            abort(404)
        parts = []
        for p in (src_path, src_path + "-wal"):
            try:
                st = os.stat(p)
                parts.append(f"{st.st_mtime_ns}-{st.st_size}")
            except OSError:
                parts.append("0")
        etag = '"' + ".".join(parts) + '"'
        if request.headers.get("If-None-Match") == etag:
            return "", 304
        fd, snap_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        if request.args.get("full"):
            src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
            dst = sqlite3.connect(snap_path)
            src.backup(dst)
            dst.close()
            src.close()
        else:
            hub_tables = ("seasons", "duals", "gtt_leagues", "gtt_franchises",
                          "gtt_players", "gtt_seasons", "gtt_duals", "gtt_hof")
            dst = sqlite3.connect(snap_path)
            dst.execute("ATTACH DATABASE ? AS src", (src_path,))
            for t in hub_tables:
                try:
                    dst.execute(f"CREATE TABLE {t} AS SELECT * FROM src.{t}")
                except sqlite3.Error:
                    continue
            dst.commit()
            dst.execute("DETACH DATABASE src")
            dst.close()

        @after_this_request
        def _cleanup(resp):
            try:
                os.unlink(snap_path)
            except OSError:
                pass
            return resp

        resp = send_file(snap_path, mimetype="application/x-sqlite3",
                         as_attachment=True, download_name="tennis.db")
        resp.headers["ETag"] = etag
        return resp

    @app.route("/start")
    def onboarding():
        from app import worldconfig
        return render_template("onboarding.html", active="World",
                               bands=worldconfig.BANDS, band=worldconfig.name_preset(),
                               region_groups=worldconfig.region_groups(),
                               mult_choices=worldconfig.MULT_CHOICES,
                               intl_share=worldconfig.intl_share(),
                               intl_share_choices=worldconfig.INTL_SHARE_CHOICES)

    @app.route("/world/new", methods=["POST"])
    def world_new():
        from app import worldconfig
        worldconfig.set_name_preset(request.form.get("name_preset", "tennis_global"))
        worldconfig.set_intl_share(request.form.get("intl_share"))
        worldconfig.set_active(request.form.getlist("divisions"), request.form.getlist("genders"))
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
        import app.honors as honors
        # Once the active seasons are complete, hold at the awards step until honors
        # are stamped for every ACTIVE universe (don't wait on a dormant one, whose
        # honors never stamp — that would jam a single-gender save here forever).
        if wd.season_complete():
            year = wd.BASE_YEAR + wd.load_world()["year"]
            awards_pending = not all(honors.has_season(year, d, g) for (d, g) in wd._active_unis())
            if awards_pending:
                return redirect(url_for("world_view"))
        wd.advance_week()
        return redirect(url_for("world_view"))

    @app.route("/world/awards", methods=["POST"])
    def world_awards():
        stamp_world_honors()
        return redirect(request.referrer or url_for("world_view"))

    @app.route("/fall-portal")
    def fall_portal():
        # Review the post-ITA reshuffle: redirect a rider, add one the sim missed,
        # or drop one, then commit. If we're holding in the portal but nothing's been
        # proposed yet (e.g. the user navigated here directly), generate the slate.
        w = wd.load_world()
        year = w["year"] if w else 0
        if w and wd._all_in_fall_portal(DEFAULT_SEED, w) and not ov.get_proposals(year):
            wd.run_fall_portal()
        return render_template("fall_portal.html", active="World", fp=fall_portal_view(), crest=crest)

    @app.route("/fall-portal/approve", methods=["POST"])
    def fall_portal_approve():
        # Keep/drop riders (cascades follow their rider, so only riders toggle).
        w = wd.load_world()
        year = w["year"] if w else 0
        action = request.form.get("action", "")
        if action == "reject_all":
            for r in ov.get_proposals(year):
                if r["cascade_from"] is None and r["status"] != "rejected":
                    ov.set_status(year, r["gender"], r["pid"], "rejected")
        elif action == "approve_all":
            for r in ov.get_proposals(year):
                if r["cascade_from"] is None and r["status"] == "rejected":
                    ov.set_status(year, r["gender"], r["pid"], "proposed")
        else:
            pid, gender = request.form.get("pid", ""), request.form.get("gender", "")
            if pid and gender:
                ov.set_status(year, gender, pid, request.form.get("status", "rejected"))
        return redirect(url_for("fall_portal"))

    @app.route("/fall-portal/redirect", methods=["POST"])
    def fall_portal_redirect():
        pid, dest = request.form.get("pid", "").strip(), request.form.get("dest", "").strip()
        if pid and dest:
            wd.redirect_fall_portal_mover(DEFAULT_SEED, pid, dest)
        return redirect(url_for("fall_portal"))

    @app.route("/fall-portal/add", methods=["POST"])
    def fall_portal_add():
        pid = request.form.get("pid", "").strip()
        dest = request.form.get("dest", "").strip() or None
        if not pid:
            name = request.form.get("player", "").strip()
            if name:
                hits = search_players(name).get("players", [])
                if hits:
                    pid = hits[0]["pid"]
        if pid:
            wd.add_fall_portal_mover(DEFAULT_SEED, pid, dest)
        return redirect(url_for("fall_portal"))

    @app.route("/fall-portal/commit", methods=["POST"])
    def fall_portal_commit():
        # Commit resolves the whole kept slate (sim picks + your edits/adds) and
        # applies it — relocations, two-stint history, cascade and all.
        wd.commit_fall_portal()
        return redirect(url_for("world_view"))

    @app.route("/")
    def dashboard():
        division, gender, label, u = _universe(request)
        return render_template("dashboard.html", active="Dashboard", u=u, uni_label=label,
                               d=dashboard_view(division, gender))

    @app.route("/data")
    def data_portal():
        division, gender, label, u = _universe(request)
        return render_template("data_portal.html", active="Data", u=u, uni_label=label,
                               portal=data_portal_view(division, gender))

    @app.route("/export/data_portal.json")
    def export_data_portal():
        token = os.environ.get("EXPORT_TOKEN")
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip() \
            or request.args.get("token", "")
        if token and supplied != token:
            abort(404)
        from app import worldconfig
        universes = []
        for _u, division, gender, label in UNIVERSES:
            if not worldconfig.is_active(division, gender):
                continue
            try:
                portal = data_portal_view(division, gender)
            except Exception:
                continue
            universes.append({
                "division": division.lower(), "gender": gender,
                "label": label,
                **{k: portal[k] for k in (
                    "phase", "current_week", "total_weeks",
                    "programs", "conferences", "players",
                    "completed_duals", "total_duals",
                    "live_rankings", "player_leaders",
                    "standings_leaders", "recent", "upcoming",
                    "top_prospects", "has_live_results",
                    "conf_power", "prestige_board")},
            })
        return jsonify({"universes": universes})

    @app.route("/rankings")
    def rankings():
        division, gender, label, u = _universe(request)
        conf = request.args.get("conf", "All")
        view = request.args.get("view", "teams")
        # National field sizes, ITA-style: teams 75/50, singles 125/75, doubles 60/40 (D2 smaller).
        small = division == "D2"
        if view in ("singles", "doubles"):
            prows = (singles_ranking_rows if view == "singles"
                     else doubles_ranking_rows)(division, gender)
            limit = ({"singles": 75, "doubles": 40} if small
                     else {"singles": 125, "doubles": 60})[view]
            prows = [r for r in prows if conf == "All" or r["conf"] == conf][:limit]
            p = paginate(prows, request.args.get("page", 1))
            return render_template(
                "rankings.html", active="Rankings", mode=view, view=view, p=p, prows=p.items,
                total=len(prows), matches=len(prows), conferences=conferences_for(division, gender),
                tiers=["All"], conf=conf, tier="All", sort="Rank", u=u, uni_label=label,
            )
        tier = request.args.get("tier", "All")
        sort = request.args.get("sort", "Rank")
        limit = 50 if small else 75
        rows = ranking_rows(division, gender)[:limit]
        total = len(rows)
        tiers = ["All"] + sorted({r.tier for r in rows})
        filtered = [r for r in rows
                    if (conf == "All" or r.conf == conf) and (tier == "All" or r.tier == tier)]
        if sort == "Power Index":
            filtered = sorted(filtered, key=lambda r: r.pi, reverse=True)
        elif sort == "APR":
            filtered = sorted(filtered, key=lambda r: r.apr, reverse=True)
        elif sort == "Power 6":
            filtered = sorted(filtered, key=lambda r: r.p6, reverse=True)
        p = paginate(filtered, request.args.get("page", 1))
        return render_template(
            "rankings.html", active="Rankings", mode="teams", view="teams", p=p, rows=p.items,
            total=total, matches=len(filtered), conferences=conferences_for(division, gender),
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
        career = coach_career_table(coach_id)
        player_awards = coach_player_awards(coach_id)
        # Staff at the coach's current school — the in-staff swap targets.
        staff = coaching_staff(div, gen, c["school"]) if c.get("school") else []
        # Move target: any program in ANY division/gender.
        move_universes = all_programs_by_universe() if c.get("school") else []
        return render_template("coach.html", active="Teams", c=c, honor_years=honor_years,
                               career=career, player_awards=player_awards, staff=staff,
                               move_universes=move_universes, crest=crest, u=u, uni_label=label)

    @app.route("/coach/<coach_id>/move", methods=["POST"])
    def coach_move(coach_id):
        import app.coachreg as coachreg
        c = coachreg.get(coach_id)
        if not c or not c.get("school"):
            abort(404)
        u = request.form.get("u", "D1-men")
        tgt = request.form.get("target", "")     # staff swap: "division|gender|school|role"
        if tgt:
            try:
                d2, g2, s2, r2 = tgt.split("|")
            except ValueError:
                return redirect(url_for("coach", coach_id=coach_id, u=u))
        else:                                    # cross-program move (ANY universe)
            dest = request.form.get("dest_school", "")
            r2 = request.form.get("dest_role", "head")
            if "|" in dest:                      # "division|gender|school" — move anywhere
                d2, g2, s2 = dest.split("|", 2)
            else:                                # plain school name — same universe
                s2, d2, g2 = dest, c["division"], c["gender"]
        if not s2:
            return redirect(url_for("coach", coach_id=coach_id, u=u))
        # Ensure the destination seat row exists (generate it if never viewed — a
        # vacant/retired seat row already exists and is left alone), then move:
        # swap if the target is occupied, just fill it if it's vacant (no demotion).
        from app import coachgen
        coachgen.ensure(d2, g2, s2, r2)
        coachreg.move_to(coach_id, g2, d2, s2, r2)
        reset_all()
        if request.form.get("back") == "editor":     # invoked from the Editor — stay there
            return redirect(url_for("editor", u=u, conf=request.form.get("conf", "All"),
                                    school=request.form.get("ed_school", c["school"])))
        return redirect(url_for("coach", coach_id=coach_id, u=u))

    @app.route("/coach/<coach_id>/retire", methods=["POST"])
    def coach_retire(coach_id):
        import app.coachreg as coachreg
        c = coachreg.get(coach_id)
        u = request.form.get("u", "D1-men")
        coachreg.retire(coach_id)
        reset_all()
        if request.form.get("back") == "editor":
            return redirect(url_for("editor", u=u, conf=request.form.get("conf", "All"),
                                    school=request.form.get("ed_school", c["school"] if c else "")))
        return redirect(url_for("coach", coach_id=coach_id, u=u))

    @app.route("/awards")
    def awards():
        division, gender, label, u = _universe(request)
        aw = season_awards(division, gender)
        coty = coach_honor_records(division, gender)
        coach_awards = {
            "national": next((r for r in coty if r["award"] == "national_coty"), None),
            "national_asst": [r for r in coty if r["award"] == "national_asst_coty"],
            "conference": sorted((r for r in coty if r["award"] == "conf_coty"),
                                 key=lambda r: r["label"]),
        }
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        s = sm.load_season(sid)
        final = aw.get("concluded", False)      # honors are only named once the season concludes
        conf_p = paginate(aw["all_conference"], request.args.get("page", 1), per_page=6)
        cur_year = wd.BASE_YEAR + (wd.load_world()["year"] if wd.exists() else 0)
        past_years = [y for y in archive_years(division, gender) if y < cur_year]
        return render_template("awards.html", active="Awards", aw=aw, conf_p=conf_p,
                               coach_awards=coach_awards, u=u, uni_label=label, crest=crest,
                               final=final, phase=s["phase"], past_years=past_years,
                               week=s["current_week"], total_weeks=s["total_weeks"])

    @app.route("/awards/archive")
    def awards_archive_page():
        division, gender, label, u = _universe(request)
        years = archive_years(division, gender)
        year = request.args.get("year", type=int) or (years[0] if years else None)
        aw = awards_archive(division, gender, year) if year else None
        return render_template("awards_archive.html", active="Awards", u=u, uni_label=label,
                               crest=crest, years=years, year=year, aw=aw)

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
                    slot.setdefault("champion", r["school"])
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
        raw = request.args.get("size")          # no explicit size → division default (D1=96)
        try:
            size = int(raw) if raw else None
        except ValueError:
            size = None
        br = get_bracket(division, gender, size=size)
        return render_template("bracket.html", active="Bracket", br=br, u=u,
                               uni_label=label, division=division,
                               field=len(br.seeds) if br else 0, field_presets=FIELD_PRESETS)

    @app.route("/season/ita")
    def season_ita():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        return render_template("ita.html", active="Season", u=u, uni_label=label,
                               view=sm.ita_view(sid), division=division, crest=crest)

    @app.route("/singles-championship")
    def singles_championship():
        division, gender, label, u = _universe(request)
        try:
            size = int(request.args.get("size", 128))
        except ValueError:
            size = 128
        years = championship_years(division, gender)
        sel = request.args.get("year", type=int)
        ch = get_singles_championship(division, gender, size=size, year=sel)
        return render_template("singles.html", active="Singles", u=u, uni_label=label,
                               division=division, ch=ch, champ_years=years,
                               sel_year=sel or (years[0] if years else None),
                               field=len(ch.entries) if ch else 0, field_presets=[32, 64, 128])

    @app.route("/doubles-championship")
    def doubles_championship():
        division, gender, label, u = _universe(request)
        try:
            size = int(request.args.get("size", 64))
        except ValueError:
            size = 64
        years = championship_years(division, gender)
        sel = request.args.get("year", type=int)
        ch = get_doubles_championship(division, gender, size=size, year=sel)
        return render_template("doubles.html", active="Doubles", u=u, uni_label=label,
                               division=division, ch=ch, champ_years=years,
                               sel_year=sel or (years[0] if years else None),
                               field=len(ch.entries) if ch else 0, field_presets=FIELD_PRESETS)

    @app.route("/projection")
    def projection():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        return render_template("projection.html", active="Bracket", u=u, uni_label=label,
                               division=division, proj=sm.field_projection(sid))

    def _current_league():
        leagues = gs.list_leagues()
        if not leagues:
            return None, []
        lid = request.args.get("lg", type=int)
        chosen = next((l for l in leagues if l["id"] == lid), leagues[-1])
        return chosen, leagues

    @app.route("/gtt")
    def gtt_hub():
        league, leagues = _current_league()
        if not league:
            return render_template("gtt_hub.html", active="GTT", league=None, leagues=[])
        lid = league["id"]
        return render_template(
            "gtt_hub.html", active="GTT", league=league, leagues=leagues,
            standings=gs.standings(lid), honors=gs.honors_board(lid),
            history=gs.season_history(lid), transactions=gs.transactions(lid, limit=40),
            recent=gs.week_duals(lid, max(1, league["current_week"] - 1)),
            recent_week=max(1, league["current_week"] - 1))

    @app.route("/gtt/new", methods=["POST"])
    def gtt_new():
        name = (request.form.get("name") or "Global Team Tennis").strip()
        seed = request.form.get("seed", type=int)
        teams = min(16, max(4, request.form.get("teams", type=int) or gs.DEFAULT_TEAMS))
        lid = gs.create_league(name, seed=seed, n_teams=teams)
        return redirect(url_for("gtt_hub", lg=lid))

    @app.route("/gtt/advance", methods=["POST"])
    def gtt_advance():
        lid = request.form.get("lg", type=int)
        mode = request.form.get("mode", "step")
        if lid:
            if mode == "finish":
                gs.advance_all(lid, fidelity="fast")
            else:
                gs.advance(lid, fidelity="full")
        return redirect(url_for("gtt_hub", lg=lid))

    @app.route("/gtt/dual/<int:dual_id>")
    def gtt_dual(dual_id):
        league, _ = _current_league()
        if not league:
            abort(404)
        detail = gs.dual_detail(league["id"], dual_id)
        if not detail:
            abort(404)
        return render_template("gtt_dual.html", active="GTT", league=league, d=detail)

    @app.route("/gtt/franchise/<int:fid>")
    def gtt_franchise(fid):
        league, _ = _current_league()
        if not league:
            abort(404)
        lid = league["id"]
        fr = next((f for f in gs.franchises(lid) if f["id"] == fid), None)
        if not fr:
            abort(404)
        row = next((r for r in gs.standings(lid) if r["fid"] == fid), None)
        return render_template("gtt_franchise.html", active="GTT", league=league,
                               fr=fr, row=row, roster=gs.franchise_roster(lid, fid),
                               free_agents=gs.free_agents(lid), franchises=gs.franchises(lid),
                               moves=[t for t in gs.transactions(lid) if t["fid"] == fid],
                               is_champion=(league.get("champion") == fid))

    @app.route("/gtt/franchise/<int:fid>/edit", methods=["POST"])
    def gtt_franchise_edit(fid):
        lid = request.form.get("lg", type=int)
        gs.edit_franchise(fid,
                          name=(request.form.get("name") or None),
                          city=(request.form.get("city") or None),
                          abbrev=(request.form.get("abbrev") or None))
        return redirect(url_for("gtt_franchise", fid=fid, lg=lid))

    @app.route("/gtt/franchise/<int:fid>/move", methods=["POST"])
    def gtt_move(fid):
        lid = request.form.get("lg", type=int)
        pid = request.form.get("pid", "")
        dest = request.form.get("dest", "")
        if lid and pid:
            dest_fid = None if dest in ("", "FA") else int(dest)
            gs.move_player(lid, pid, dest_fid)
        # land on whichever roster the player ended up on (or stay put for a waive)
        return redirect(url_for("gtt_franchise",
                                fid=(int(dest) if dest not in ("", "FA") else fid), lg=lid))

    @app.route("/gtt/player/<pid>")
    def gtt_player(pid):
        league, _ = _current_league()
        if not league:
            abort(404)
        detail = gs.player_detail(league["id"], pid)
        if not detail:
            abort(404)
        return render_template("gtt_player.html", active="GTT", league=league, p=detail)

    @app.route("/gtt/player/<pid>/enshrine", methods=["POST"])
    def gtt_enshrine(pid):
        lid = request.form.get("lg", type=int)
        if lid:
            gs.enshrine(lid, pid)
        return redirect(url_for("gtt_player", pid=pid, lg=lid))

    @app.route("/gtt/hall-of-fame")
    def gtt_hall():
        league, leagues = _current_league()
        if not league:
            return render_template("gtt_hall.html", active="GTT", league=None, leagues=[],
                                   hof=[], history=[])
        lid = league["id"]
        return render_template("gtt_hall.html", active="GTT", league=league, leagues=leagues,
                               hof=gs.hall_of_fame(lid), history=gs.season_history(lid))

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
        if not school:
            conf = request.args.get("conf", "All")
            groups = teams_by_conference(division, gender, conf)
            p = paginate(groups, request.args.get("page", 1), per_page=8)
            return render_template("teams_index.html", active="Teams", u=u, uni_label=label,
                                   groups=p.items, p=p,
                                   conferences=conferences_for(division, gender), conf=conf)
        rows = team_roster(division, gender, school)
        live = ranking_rows(division, gender)
        if not rows:
            school = live[0].school
            rows = team_roster(division, gender, school)
        schools = [r.school for r in live]
        power6 = next((r.p6 for r in live if r.school == school), 0.0)
        abbr, color = crest(school)
        row = get_row(school)
        prog = load_division(division, gender).by_school(school)
        conf = team_conference(division, gender, school) or (row.conf if row else "")
        return render_template("teams.html", active="Teams", rows=rows, school=school,
                               abbr=abbr, color=color, row=row, power6=power6, conf=conf, schools=schools, u=u,
                               uni_label=label, staff=coaching_staff(division, gender, school),
                               results=team_results(division, gender, school), crest=crest,
                               city=(prog.location if prog else ""),
                               budget=team_budget(division, gender, school),
                               injuries=injury_rows(division, gender, school),
                               history=program_history(division, gender, school))

    @app.route("/injuries")
    def injuries_page():
        division, gender, label, u = _universe(request)
        conf = request.args.get("conf", "All")
        status = request.args.get("status", "active")        # who's hurt now, by default
        rows = injury_rows(division, gender, conf_filter=conf,
                           active_only=(status != "all"))
        rows.sort(key=lambda r: (r["school"], not r["active"]))
        return render_template("injuries.html", active="Injuries", u=u, uni_label=label,
                               rows=rows, conf=conf, status=status,
                               conferences=conferences_for(division, gender))

    @app.route("/player/<pid>")
    def player(pid):
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        info = sm.player_info(sid, pid)
        if not info:
            abort(404)
        strv, rel = sm.season_player_str(sid).get(pid, (None, 0.0))
        career, (wins, losses) = player_career(division, gender, pid)
        career_table = player_career_table(division, gender, pid)
        records = player_career_records(division, gender, pid)
        honor_years = player_career_honors(division, gender, pid)
        ranks = player_ranks(division, gender, pid)
        journey = player_journey(division, gender, pid)
        return render_template("player.html", active="Teams", pid=pid, info=info,
                               career=career, career_table=career_table, records=records,
                               strv=strv, rel=rel, wins=wins, losses=losses, gender=gender,
                               honor_years=honor_years, ranks=ranks, journey=journey,
                               crest=crest, u=u, uni_label=label)

    @app.route("/ncaa")
    def ncaa_bracket():
        division, gender, label, u = _universe(request)
        years = ncaa_bracket_years(division, gender)
        cur_year = wd.BASE_YEAR + (wd.load_world()["year"] if wd.exists() else 0)
        sel = request.args.get("year", type=int)
        view_year = sel if (sel and sel != cur_year) else None
        return render_template("ncaa_bracket.html", active="NCAA Bracket", u=u, uni_label=label,
                               br=ncaa_bracket_view(division, gender, year=view_year),
                               division=division, bracket_years=years,
                               cur_year=cur_year, sel_year=sel or cur_year)

    @app.route("/results")
    def results():
        division, gender, label, u = _universe(request)
        wk = request.args.get("week")
        res = results_by_week(division, gender, week=wk)
        return render_template("results.html", active="Results", u=u, uni_label=label, res=res)

    @app.route("/search")
    def search():
        division, gender, label, u = _universe(request)
        q = request.args.get("q", "")
        res = search_players(q)
        return render_template("search.html", active="", u=u, uni_label=label, res=res, q=q)

    @app.route("/transfers")
    def transfers():
        division, gender, label, u = _universe(request)
        year = request.args.get("year", type=int)
        tp = transfer_portal_view(division, gender, year=year)
        pg = paginate(tp["transfers"], request.args.get("page", 1), per_page=40)
        return render_template("transfers.html", active="Transfer Portal", u=u, uni_label=label,
                               tp=tp, p=pg, sel_year=year)

    @app.route("/recruiting")
    def recruiting():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
        scope = request.args.get("scope", "national")
        state = request.args.get("state", "California")
        status = request.args.get("status", "all")
        rows = recruit_rows(rg, grad_year, scope=scope, state=state, division=division,
                            unsigned_only=(status == "unsigned"))
        p = paginate(rows, request.args.get("page", 1))
        return render_template("recruiting.html", active="Recruiting", rows=p.items, p=p,
                               total=len(rows), gender=gender, grad_year=grad_year,
                               scope=scope, state=state, status=status, u=u, uni_label=label,
                               states=[s for s, _ in US_STATES],
                               grad_years=[grad_year])

    @app.route("/recruit/<pid>")
    def recruit(pid):
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
        p = get_recruit(rg, grad_year, pid, division=division)
        if p is None:
            abort(404)
        view = recruit_profile(p, division, gender, grad_year)
        return render_template("recruit.html", active="Recruiting", p=p, view=view,
                               gender=gender, grad_year=grad_year, u=u, uni_label=label)

    @app.route("/recruiting/team/<school>")
    def team_recruiting(school):
        division, gender, label, u = _universe(request)
        return render_template("team_recruiting.html", active="Recruiting",
                               cls=team_recruiting_class(gender, school), school=school,
                               u=u, uni_label=label)

    @app.route("/recruiting/signings")
    def signing_tracker_page():
        division, gender, label, u = _universe(request)
        return render_template("signing_tracker.html", active="Recruiting",
                               trk=signing_tracker(gender, division), gender=gender,
                               u=u, uni_label=label)

    @app.route("/recruiting/hub")
    def recruiting_hub_page():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
        return render_template("recruiting_hub.html", active="Recruiting",
                               hub=recruiting_hub(rg, grad_year), gender=gender,
                               grad_year=grad_year, u=u, uni_label=label,
                               grad_years=[grad_year])

    # ---- Analytics Bureau: god-mode player intelligence (additive mod) ----
    @app.route("/intel")
    def intel_hub():
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        return render_template("intel_hub.html", active="Analytics Bureau",
                               ov=si.overview(gender), gender=gender, u=u, uni_label=label)

    @app.route("/intel/underplaced")
    def intel_underplaced():
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        div_f = request.args.get("div", "All")
        cls_f = request.args.get("class", "All")
        sort = request.args.get("sort", "gap")
        q = request.args.get("q", "")
        rows = si.underplaced_board(gender, division=div_f, class_year=cls_f, sort=sort, q=q)
        pg = paginate(rows, request.args.get("page", 1))
        return render_template("intel_underplaced.html", active="Analytics Bureau",
                               rows=pg.items, p=pg, total=len(rows), gender=gender,
                               div_f=div_f, cls_f=cls_f, sort=sort, q=q, u=u, uni_label=label,
                               divisions=["All", "D1", "D2", "D3", "D4"],
                               classes=["All", "Fr", "So", "Jr", "Sr"])

    @app.route("/intel/scholarships")
    def intel_scholarships():
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        div_f = request.args.get("div", "All")
        rows = si.playing_time_watch(gender, division=div_f)
        pg = paginate(rows, request.args.get("page", 1))
        return render_template("intel_scholarships.html", active="Analytics Bureau",
                               rows=pg.items, p=pg, total=len(rows), gender=gender,
                               div_f=div_f, u=u, uni_label=label,
                               divisions=["All", "D1", "D2"])

    @app.route("/intel/lineups")
    def intel_lineups():
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        div_f = request.args.get("div", division)
        if div_f not in ("D1", "D2", "D3", "D4"):
            div_f = division
        confs = si.conference_list(div_f, gender)
        conf = request.args.get("conf") or (confs[0] if confs else "")
        highlight = request.args.get("team") or None
        lineups = si.conference_lineups(div_f, gender, conf, highlight=highlight)
        strength = si.conference_strength(div_f, gender)
        return render_template("intel_lineups.html", active="Analytics Bureau",
                               gender=gender, u=u, uni_label=label, div_f=div_f, conf=conf,
                               confs=confs, lineups=lineups, strength=strength,
                               highlight=highlight, divisions=["D1", "D2", "D3", "D4"])

    @app.route("/intel/fit/<pid>")
    def intel_fit(pid):
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        p, targets = si.fit_targets(gender, pid)
        if p is None:
            abort(404)
        return render_template("intel_fit.html", active="Analytics Bureau",
                               p=p, targets=targets, gender=gender, u=u, uni_label=label)

    @app.route("/juniors/rankings")
    def junior_rankings():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
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
                               grad_years=[grad_year])

    @app.route("/juniors/feed.json")
    def junior_feed_json():
        _division, gender, _label, _u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
        return jsonify(junior_feed(rg, grad_year))

    @app.route("/juniors/tour")
    def junior_tour():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
        tier = request.args.get("tier", "")
        rows = junior_tournaments(rg, grad_year, tier=tier)
        pg = paginate(rows, request.args.get("page", 1))
        tiers = ["Grand Slam", "Masters", "Major", "Premier", "National", "Developmental", "State"]
        return render_template("junior_tournaments.html", active="Recruiting", rows=pg.items,
                               p=pg, total=len(rows), gender=gender, grad_year=grad_year,
                               tier=tier, tiers=tiers, u=u, uni_label=label,
                               grad_years=[grad_year])

    @app.route("/juniors/tournament")
    def junior_tournament():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
        t = junior_tournament_detail(rg, grad_year, request.args.get("t", ""))
        if t is None:
            abort(404)
        return render_template("junior_tournament.html", active="Recruiting", t=t,
                               gender=gender, grad_year=grad_year, u=u, uni_label=label)

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

    @app.route("/editor")
    def editor():
        division, gender, label, u = _universe(request)
        # The pickers only need each school's name + conference — NOT the Power
        # Index, whose preseason path builds all ~366 rosters to rank them (~6s
        # cold). load_division is a cheap cached file read, so the editor opens
        # instantly and the conference filter is applied on that list directly.
        div = load_division(division, gender)
        conferences = conferences_for(division, gender)
        conf = request.args.get("conf", "All")
        if conf not in conferences:
            conf = "All"
        schools = sorted(p.school for p in div.programs
                         if conf == "All" or p.conf == conf)
        school = request.args.get("school")
        if school not in schools:
            school = schools[0] if schools else ""
        rows, head = editor_roster(division, gender, school)
        if rows is None:
            school = schools[0]
            rows, head = editor_roster(division, gender, school)
        from app import scholarships as sch
        schol = [{"division": d, "gender": g, **sch.limits(d, g)}
                 for d in ("D1", "D2", "D3", "D4") for g in ("men", "women")]
        prog = div.by_school(school)
        prestige = {"value": round((prog.prestige if prog else 0.5) * 100),
                    "overridden": school in ov.get_prestige()}
        academics = {"value": round((prog.academics if prog else 0.5) * 100),
                     "overridden": school in ov.get_academics()}
        conf_ratings = conference_ratings(division, gender, conf) if conf != "All" else None
        return render_template("editor.html", active="Editor", u=u, uni_label=label,
                               school=school, schools=schools, rows=rows, head=head,
                               conferences=conferences, conf=conf, conf_ratings=conf_ratings,
                               groups=all_programs_grouped(), ov=active_overrides(),
                               scholarships=schol, prestige=prestige, academics=academics,
                               staff=coaching_staff(division, gender, school),
                               move_universes=all_programs_by_universe(),
                               all_schools=sorted(p.school for p in div.programs),
                               schol_elite=sch.limits("D3", "men", academics=0.95))

    def _pct01(field: str, default: float = 0.5) -> float:
        """Read a 0–100 form field as a 0..1 rating."""
        try:
            return float(request.form.get(field, str(default * 100))) / 100.0
        except (TypeError, ValueError):
            return default

    def _editor_redirect():
        return redirect(url_for("editor", u=request.form.get("u", "D1-men"),
                                school=request.form.get("school", ""),
                                conf=request.form.get("conf", "All")))

    @app.route("/editor/prestige", methods=["POST"])
    def editor_prestige():
        school = request.form.get("school", "")
        if school:
            ov.set_prestige(school, _pct01("prestige"))
            reset_all()
        return _editor_redirect()

    @app.route("/editor/prestige/clear", methods=["POST"])
    def editor_prestige_clear():
        school = request.form.get("school", "")
        if school:
            ov.clear_prestige(school)
            reset_all()
        return _editor_redirect()

    @app.route("/editor/academics", methods=["POST"])
    def editor_academics():
        school = request.form.get("school", "")
        if school:
            ov.set_academics(school, _pct01("academics"))
            reset_all()
        return _editor_redirect()

    @app.route("/editor/academics/clear", methods=["POST"])
    def editor_academics_clear():
        school = request.form.get("school", "")
        if school:
            ov.clear_academics(school)
            reset_all()
        return _editor_redirect()

    @app.route("/editor/conf_prestige", methods=["POST"])
    def editor_conf_prestige():
        conf = request.form.get("conf", "")
        if conf and conf != "All":
            ov.set_conf_prestige(conf, _pct01("conf_prestige"))
            reset_all()
        return _editor_redirect()

    @app.route("/editor/conf_prestige/clear", methods=["POST"])
    def editor_conf_prestige_clear():
        conf = request.form.get("conf", "")
        if conf:
            ov.clear_conf_prestige(conf)
            reset_all()
        return _editor_redirect()

    @app.route("/editor/conf_academics", methods=["POST"])
    def editor_conf_academics():
        conf = request.form.get("conf", "")
        if conf and conf != "All":
            ov.set_conf_academics(conf, _pct01("conf_academics"))
            reset_all()
        return _editor_redirect()

    @app.route("/editor/conf_academics/clear", methods=["POST"])
    def editor_conf_academics_clear():
        conf = request.form.get("conf", "")
        if conf:
            ov.clear_conf_academics(conf)
            reset_all()
        return _editor_redirect()

    @app.route("/editor/scholarship", methods=["POST"])
    def editor_scholarship():
        from app import scholarships as sch
        u = request.form.get("u", "D1-men")
        for d in ("D1", "D2", "D3", "D4"):
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
        elite = {}
        for field, key, cast in (("count_elite", "count", int),
                                 ("cap_elite", "cap", float), ("rate_elite", "rate", float)):
            raw = request.form.get(field)
            if raw not in (None, ""):
                try:
                    elite[key] = cast(raw)
                except ValueError:
                    pass
        if elite:
            sch.set_elite_limit(**elite)
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
            w = wd.load_world()
            if w and sm.FALL_PORTAL_ENABLED and wd._all_in_fall_portal(DEFAULT_SEED, w):
                # During the fall-portal window an editor move becomes a portal ADD,
                # so it earns the two-stint history + balancing cascade instead of
                # collapsing the season to one school. It lands when you commit the
                # portal, not immediately — review it on the fall-portal screen.
                if not ov.get_proposals(w["year"]):
                    wd.run_fall_portal()
                wd.add_fall_portal_mover(DEFAULT_SEED, pid, dest)
                return redirect(url_for("fall_portal"))
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
                               bubble=sm.bubble_watch(sid), ita_champ=sm.indoor_champion(sid))

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
        standings = sm.standings(sid)
        conferences = sorted(standings)
        conf = request.args.get("conf")
        if conf not in standings:
            conf = conferences[0] if conferences else ""
        return render_template("season_standings.html", active="Season", u=u, uni_label=label,
                               conferences=conferences, conf=conf, crest=crest,
                               table=standings.get(conf, []))

    @app.route("/season/schedule")
    def season_schedule():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        groups = dict(conference_schools(division, gender))
        conferences = sorted(groups)
        conf = request.args.get("conf")
        school = request.args.get("school")
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
        base = datetime.date(2026, 1, 16)
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

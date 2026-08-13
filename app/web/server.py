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
import threading
from flask import Flask, render_template, request, abort, redirect, url_for, jsonify, Response

from .rankings_data import all_schools, crest, get_row
from .sim import run_dual_view, FIDELITIES, programs_for
from .state import (ranking_rows, singles_ranking_rows, doubles_ranking_rows,
                    conferences_for, get_bracket, get_doubles_championship,
                    get_singles_championship, championship_years, get_world_cup,
                    past_individual_champions, UNIVERSES, FIELD_PRESETS,
                    recruit_rows, get_recruit, recruit_profile, team_roster,
                    player_career_table, player_career_records, search_players,
                    results_by_week, ncaa_bracket_view, ncaa_bracket_years,
                    ita_bracket_view, ita_bracket_years, transfer_portal_view,
                    RECRUIT_GENDERS, editor_roster, all_programs_grouped,
                    all_programs_by_universe, coach_move_tree,
                    active_overrides, reset_all, reset_lineup, teams_by_conference, coaching_staff,
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
from .state import (jhsaa_view, jhsaa_school_view, jhsaa_past_winners,
                    jhsaa_bracket_view, jhsaa_toc_view, jhsaa_district_view, jhsaa_districts_view,
                    jhsaa_rankings_view, jhsaa_player_view)
from .state import (preseason_portal_view, recruit_economy_view, portal_class_rankings,
                    wire_view)
from .state import my_program_view, my_schedule_plan, my_season_report, job_offers
from .state import staff_search
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

# The coached program (career mode) is per-save state, resolved at request time
# from worldconfig.user_program() — NOT a module constant. None => spectator mode
# (the "Your Team" nav group hides entirely). See docs/DESIGN-team-takeover-career-mode.md.

# A cold prime (fresh machine, or a rebuild after a week advance / roster move)
# materialises the whole world's rosters and can take a minute+. Rather than block
# the request — and the GIL, which would starve /api/health and trip fly's recycle
# loop — we warm in a background thread and answer instantly with this loader, which
# polls /api/ready and reloads itself once the world is warm. Self-contained (no
# base.html / context processor, which would themselves touch the cold world).
_warming = threading.Event()        # set while a background warm is in flight
_warmed_salt = {"v": None}          # generation salt whose first (slow) prime is done
LOADING_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Play to Clinch — loading…</title>
<style>
 html,body{height:100%;margin:0}
 body{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:22px;
   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
   background:#0f1720;color:#e8edf2}
 .ring{width:46px;height:46px;border:4px solid #25323f;border-top-color:#2bb3c0;
   border-radius:50%;animation:spin 1s linear infinite}
 @keyframes spin{to{transform:rotate(360deg)}}
 .t{font-size:15px;font-weight:600;letter-spacing:.02em}
 .s{font-size:12.5px;color:#8a99a8;max-width:300px;text-align:center;line-height:1.5}
</style></head><body>
 <div class=ring></div>
 <div class=t>Warming up the league…</div>
 <div class=s>Building this season's rosters and ratings. This can take up to a minute on a cold start — the page will load automatically.</div>
 <script>
 (function poll(){
   fetch('/api/ready',{cache:'no-store'}).then(function(r){return r.json()})
     .then(function(d){ if(d&&d.ready){ location.reload(); } else { setTimeout(poll,1500); } })
     .catch(function(){ setTimeout(poll,2500); });
 })();
 </script>
</body></html>"""

# Grouped sidebar nav (Football-Manager style). Each item's href is resolved
# per-request so the universe `u` carries through. "World" is the primary
# season-to-season surface; the legacy per-universe season views sit under it.
NAV_GROUPS = [
    # "Your Team" items are resolved per-request in _inject_chrome against the
    # coached program: the school arg is injected and `u` is pinned to the
    # program's own universe. The whole group is hidden in spectator mode.
    ("Your Team", [
        {"id": "my_program","label": "Clubhouse",    "icon": "fa-solid fa-house", "endpoint": "my_program",      "args": {}},
        {"id": "preseason", "label": "Preseason",     "icon": "fa-solid fa-gear", "endpoint": "preseason_view",   "args": {}},
        {"id": "roster",    "label": "Roster",       "icon": "fa-solid fa-table-tennis-paddle-ball", "endpoint": "teams",           "args": {}},
        {"id": "schedule",  "label": "Schedule",     "icon": "fa-solid fa-calendar-days", "endpoint": "season_schedule", "args": {}},
    ]),
    ("World", [
        {"id": "season",    "label": "Season Hub",   "icon": "fa-solid fa-calendar", "endpoint": "season_hub",       "args": {}},
        {"id": "world",     "label": "World Hub",    "icon": "fa-solid fa-earth-americas", "endpoint": "world_view",       "args": {}},
        {"id": "dashboard", "label": "Dashboard",    "icon": "fa-solid fa-gauge-high", "endpoint": "dashboard",        "args": {}},
        {"id": "data",      "label": "Data Portal",  "icon": "fa-solid fa-chart-line", "endpoint": "data_portal",      "args": {}},
        {"id": "rankings",  "label": "Rankings",     "icon": "fa-solid fa-ranking-star", "endpoint": "rankings",         "args": {}},
        {"id": "results",   "label": "Results",      "icon": "fa-solid fa-clipboard-list", "endpoint": "results",          "args": {}},
        {"id": "ita",       "label": "Preseason NIT", "icon": "fa-solid fa-snowflake", "endpoint": "season_ita",        "args": {}},
        {"id": "ncaa",      "label": "NCAA Bracket", "icon": "fa-solid fa-medal", "endpoint": "ncaa_bracket",     "args": {}},
        {"id": "standings", "label": "Standings",    "icon": "fa-solid fa-table-list", "endpoint": "season_standings", "args": {}},
        {"id": "injuries",  "label": "Injuries",     "icon": "fa-solid fa-bandage", "endpoint": "injuries_page",    "args": {}},
        {"id": "awards",    "label": "Awards",       "icon": "fa-solid fa-award", "endpoint": "awards",           "args": {}},
        {"id": "hof",       "label": "Hall of Fame", "icon": "fa-solid fa-building-columns", "endpoint": "hall_of_fame",     "args": {}},
        {"id": "teams",     "label": "All Teams",    "icon": "fa-solid fa-school", "endpoint": "teams",            "args": {}},
    ]),
    ("Management", [
        {"id": "rec_hub",   "label": "Recruiting HQ", "icon": "fa-solid fa-binoculars", "endpoint": "recruiting_hub_page","args": {}},
        {"id": "recruiting","label": "Recruiting Board","icon": "fa-solid fa-graduation-cap","endpoint": "recruiting",       "args": {}},
        {"id": "transfers", "label": "Transfer Portal","icon": "fa-solid fa-right-left", "endpoint": "transfers",        "args": {}},
        {"id": "portal_rk", "label": "Portal Rankings","icon": "fa-solid fa-ranking-star", "endpoint": "portal_rankings_page","args": {}},
        {"id": "wire",      "label": "The Wire",      "icon": "fa-solid fa-tower-broadcast", "endpoint": "wire_page",           "args": {}},
        {"id": "juniors",   "label": "Junior Rankings","icon": "fa-solid fa-globe", "endpoint": "junior_rankings",  "args": {}},
        {"id": "jhsaa",     "label": "High School",  "icon": "fa-solid fa-school-flag", "endpoint": "jhsaa_page",       "args": {}},
        {"id": "jrtour",    "label": "Junior Tour",   "icon": "fa-solid fa-calendar-days", "endpoint": "junior_tour",      "args": {}},
        {"id": "signings",  "label": "Signing Tracker","icon": "fa-solid fa-file-signature", "endpoint": "signing_tracker_page","args": {}},
        {"id": "staff",     "label": "Staff Search",  "icon": "fa-solid fa-user-tie", "endpoint": "staff_search_page","args": {}},
        {"id": "rec_econ",  "label": "Scholarship Economy","icon": "fa-solid fa-coins", "endpoint": "recruit_economy_page","args": {}},
    ]),
    ("Analytics Bureau", [
        {"id": "intel",        "label": "Bureau HQ",        "icon": "fa-solid fa-satellite", "endpoint": "intel_hub",         "args": {}},
        {"id": "intel_targets","label": "My Transfer Targets","icon": "fa-solid fa-crosshairs", "endpoint": "intel_my_targets",  "args": {}},
        {"id": "intel_search", "label": "Portal Search",    "icon": "fa-solid fa-magnifying-glass-location", "endpoint": "intel_portal_search", "args": {}},
        {"id": "intel_teams",  "label": "Team Scanner",     "icon": "fa-solid fa-table-cells", "endpoint": "intel_teams",       "args": {}},
        {"id": "intel_arch",   "label": "Lineup Architect", "icon": "fa-solid fa-compass-drafting", "endpoint": "intel_architect",   "args": {}},
        {"id": "intel_lineups","label": "Lineup Lab",       "icon": "fa-solid fa-flask", "endpoint": "intel_lineups",     "args": {}},
        {"id": "intel_under",  "label": "Underplaced Talent","icon": "fa-solid fa-satellite-dish", "endpoint": "intel_underplaced", "args": {}},
        {"id": "intel_aid",    "label": "Playing Time",    "icon": "fa-solid fa-clock", "endpoint": "intel_scholarships", "args": {}},
    ]),
    ("Simulate", [
        {"id": "dual",      "label": "Dual Match",   "icon": "fa-solid fa-table-tennis", "endpoint": "dual",             "args": {}},
        {"id": "bracket",   "label": "College Bracket", "icon": "fa-solid fa-sitemap", "endpoint": "bracket",        "args": {}},
        {"id": "singles",   "label": "Singles Championship","icon": "fa-solid fa-user", "endpoint": "singles_championship", "args": {}},
        {"id": "doubles",   "label": "Doubles Championship","icon": "fa-solid fa-user-group", "endpoint": "doubles_championship", "args": {}},
        {"id": "projection","label": "Bracket Projection","icon": "fa-solid fa-wand-magic-sparkles", "endpoint": "projection",   "args": {}},
        {"id": "worldcups", "label": "World Cups",   "icon": "fa-solid fa-earth-americas", "endpoint": "world_cups",       "args": {}},
    ]),
    ("Pro Tour", [
        {"id": "gtt",       "label": "League Hub",   "icon": "fa-solid fa-globe", "endpoint": "gtt_hub",          "args": {}},
        {"id": "gtt_sched", "label": "Schedule",     "icon": "fa-solid fa-calendar-days", "endpoint": "gtt_schedule",     "args": {}},
        {"id": "gtt_lead",  "label": "Leaders",      "icon": "fa-solid fa-ranking-star", "endpoint": "gtt_leaders",      "args": {}},
        {"id": "gtt_draft", "label": "Draft",        "icon": "fa-solid fa-list-ol", "endpoint": "gtt_draft",        "args": {}},
        {"id": "gtt_hall",  "label": "Hall of Fame", "icon": "fa-solid fa-building-columns", "endpoint": "gtt_hall",         "args": {}},
        {"id": "gtt_alumni","label": "Alumni",       "icon": "fa-solid fa-address-book",     "endpoint": "gtt_alumni",       "args": {}},
    ]),
    ("Tools", [
        {"id": "guide",     "label": "Guide",        "icon": "fa-solid fa-book-open", "endpoint": "guide",           "args": {}},
        {"id": "editor",    "label": "Editor",       "icon": "fa-solid fa-screwdriver-wrench", "endpoint": "editor",          "args": {}},
        {"id": "junior_setup","label": "Junior Setup","icon": "fa-solid fa-sliders", "endpoint": "junior_setup",    "args": {}},
        {"id": "methodology","label": "Methodology", "icon": "fa-solid fa-ruler-combined", "endpoint": "methodology",      "args": {}},
    ]),
]


def _active_nav(req) -> str:
    p = req.path
    if p == "/":                          return "dashboard"
    if p.startswith("/my-program"):       return "my_program"
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
    if p.startswith("/intel/teams"):      return "intel_teams"
    if p.startswith("/intel/architect"):  return "intel_arch"
    if p.startswith("/intel/underplaced"): return "intel_under"
    if p.startswith("/intel/scholarships"): return "intel_aid"
    if p.startswith("/intel/my-targets"): return "intel_targets"
    if p.startswith("/intel/portal-search"): return "intel_search"
    if p.startswith("/intel"):            return "intel"
    if p.startswith("/staff-search"):     return "staff"
    if p.startswith("/recruiting/team"):  return "signings"
    if p.startswith("/recruiting/signings"): return "signings"
    if p.startswith("/portal-rankings"):  return "portal_rk"
    if p.startswith("/wire"):             return "wire"
    if p.startswith("/transfers"):        return "transfers"
    if p.startswith("/recruiting/hub"):   return "rec_hub"
    if p.startswith("/juniors"):          return "juniors"
    if p.startswith("/recruit"):          return "recruiting"
    if p.startswith("/teams") or p.startswith("/player"):
        from app import worldconfig
        prog = worldconfig.user_program()
        return "roster" if prog and req.args.get("school") == prog["school"] else "teams"
    if p.startswith("/editor"):           return "editor"
    if p.startswith("/gtt/hall-of-fame"): return "gtt_hall"
    if p.startswith("/gtt/alumni"):       return "gtt_alumni"
    if p.startswith("/gtt/schedule"):     return "gtt_sched"
    if p.startswith("/gtt/leaders"):      return "gtt_lead"
    if p.startswith("/gtt/draft"):        return "gtt_draft"
    if p.startswith("/gtt"):              return "gtt"
    if p.startswith("/methodology"):      return "methodology"
    if p.startswith("/guide"):            return "guide"
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
        _LBL = {"ita_kickoff": "NIT Kickoff Weekend", "ita_indoor": "Preseason NIT",
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
        # The header's advance button is now the ONLY advance control in the app
        # (the Season Hub's per-universe one desynced saves — see
        # docs/AAR-universe-desync-season-hub-advance.md), so its label has to carry
        # what that page's button used to say about the stage.
        _ACT = {"ita_kickoff": "Run NIT Kickoff", "ita_indoor": "Run NIT Indoor",
                "fall_portal": "Review fall portal", "regular": "Advance week",
                "conf_tournaments": "Run conf tournaments", "selection": "Start NCAAs",
                "ncaa": "Advance NCAA round", "complete": "Finalize season"}
        action = _ACT.get(stage, "Advance week")
        # The offseason runs as separate steps; the button names the one that's next.
        # AWARDS COME FIRST: /world/advance deliberately refuses to advance while any
        # active universe's honors are unstamped, so advertising the cup here made the
        # button a no-op — it redirected and nothing happened, and the real next step
        # was only reachable from the World Hub. Name (and post to) the awards step
        # until it's done. Only computed in the offseason, so it costs nothing in-season.
        awards_pending = False
        if stage == "complete":
            import app.honors as honors
            awards_pending = not all(honors.has_season(2026 + w["year"], d, g)
                                     for (d, g) in wd._active_unis())
            if awards_pending:
                action = "Run awards"
            elif not wd.cups_done(w):
                action = "Run Davis / BJK Cup"
        elif w["week"] == 0 and not wd.jhsaa_done(w):
            # The JHSAA rung runs FIRST at week 0 (before the pros, before any college
            # dual — see advance_week), so the button must advertise it first or it
            # reads "Run NIT Kickoff" / "Run pro offseason" and then visibly does
            # neither, costing an unexplained extra click.
            action = "Play JHSAA season"
        elif w["week"] == 0 and w["year"] > 0 and not wd.pros_rolled(w):
            action = "Run pro offseason"
        return {"year": 2026 + w["year"], "season_no": w["year"] + 1,
                "week": w["week"], "phase": _LBL.get(stage, "Regular season"),
                "stage": stage, "action": action, "awards_pending": awards_pending,
                "complete": stage == "complete",
                "signed": sum(wd.signed_counts().values())}
    except Exception:
        return None


def _universe(req) -> tuple[str, str, str, str]:
    """Resolve (division, gender, label, u-key) from the request. POST forms carry
    `u` as a hidden field (no query string), so fall back to the form body — without
    it an editor edit for any non-default universe is validated against the D1-men
    roster. `request.form` is empty on GET, so this is a no-op there."""
    u = req.args.get("u") or req.form.get("u") or "D1-men"
    match = next((x for x in UNIVERSES if x[0] == u), UNIVERSES[0])
    _, division, gender, label = match
    return division, gender, label, match[0]


def _str_scale_rows():
    """STR ↔ UTR ↔ WTN reference rows, derived from the canonical band in
    app.str_rating so the table can never drift from the engine. STR is the
    game-native 31–57 scale; UTR is the upward-facing real-world comparison
    (1.00–16.50); WTN is the inverse-facing one (40 beginner → 1 elite). The
    UTR/WTN endpoints line up cleanly with the band, but they're separate
    proprietary systems, so treat the off-anchor values as approximate."""
    from app.str_rating import STR_MIN, STR_MAX
    span = STR_MAX - STR_MIN                      # 26.0
    rows = []
    for s in range(int(STR_MIN), int(STR_MAX) + 1):
        utr = 1.0 + (s - STR_MIN) / span * 15.5   # 1.00 → 16.50
        wtn = 40.0 - (s - STR_MIN) / span * 39.0   # 40 → 1
        rows.append({"str": s, "utr": round(utr, 2), "wtn": round(wtn, 1)})
    return rows


def create_app() -> Flask:
    app = Flask(__name__)

    # Create every DB schema up front (before any sim transaction) so nested
    # connections never deadlock on first-time table creation.
    from app import db as _db
    _db.bootstrap()

    # Warm the expensive caches at BOOT, off the request path, in a daemon thread.
    # The first reload after a cold start or a Fly machine recycle otherwise pays
    # (and BLOCKS the single gunicorn worker on) the ~170MB roster build plus the
    # junior-circuit recruit build — which holds the GIL, starves /api/health, and
    # gets the machine recycled mid-build: the crash-on-reload loop. Doing it here
    # spends that cost once during the health-check grace window instead. The
    # roster prime is GIL-bound but runs with no user traffic yet; the recruit
    # prime offloads to a process pool, so it never holds the worker's GIL. Skipped
    # under pytest and via PTC_NO_BOOT_WARM; best-effort, since the lazy
    # request-path builds still cover anything this misses.
    # See docs/AAR-boot-cache-warm.md.
    import sys as _sys
    if "pytest" not in _sys.modules and not os.environ.get("PTC_NO_BOOT_WARM"):
        def _warm_caches_async():
            try:
                wd.warm_caches()              # roster cache + every gender's recruit board
            except Exception:
                pass                          # lazy paths still build on demand
            try:
                from app.web import state as _state
                _state.warm_championships()   # complete-season singles/doubles draws
            except Exception:
                pass                          # per-key build lock + lazy path cover the rest
        import threading as _threading
        _threading.Thread(target=_warm_caches_async, name="ptc-cache-warm",
                          daemon=True).start()

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
    from app.pros import is_pro as _is_pro
    app.jinja_env.filters["is_pro"] = _is_pro
    app.jinja_env.filters["flag"] = flag
    app.jinja_env.filters["flags"] = flags
    app.jinja_env.filters["country_name"] = country_name
    app.jinja_env.filters["country_abbrev"] = country_abbrev
    app.jinja_env.filters["state_abbrev"] = state_abbrev
    app.jinja_env.filters["team_logo"] = team_logo
    app.jinja_env.filters["has_team_logo"] = has_team_logo
    app.jinja_env.filters["team_logo_src"] = team_logo_src
    def _ordsuffix(n):
        try:
            n = int(n)
        except (TypeError, ValueError):
            return ""
        return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    app.jinja_env.filters["ordsuffix"] = _ordsuffix
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
        from app import worldconfig
        division, gender, label, u = _universe(request)
        prog = worldconfig.user_program()
        groups = []
        for glabel, items in NAV_GROUPS:
            if glabel == "Your Team":
                if not prog:
                    continue                       # spectator mode: hide the group
                pu = f"{prog['division']}-{prog['gender']}"   # pin to the coached universe
                built = []
                for it in items:
                    a = dict(it["args"])
                    if it["id"] in ("roster", "schedule"):
                        a["school"] = prog["school"]
                    built.append({**it, "href": url_for(it["endpoint"], u=pu, **a)})
                groups.append((glabel, built))
            else:
                groups.append((glabel, [{**it, "href": url_for(it["endpoint"], u=u, **it["args"])}
                                        for it in items]))
        return {"universes": UNIVERSES, "u": u, "uni_label": label,
                "my_team": prog["school"] if prog else None,
                "nav_groups": groups, "active_nav": _active_nav(request),
                "game": _game_context()}

    @app.before_request
    def _prime_world():
        # Health/readiness/static must answer INSTANTLY even while the world is
        # cold — never prime here, or a cold health check holds the GIL for a
        # minute, fly marks the machine unhealthy, and it recycles (the 503 loop).
        if request.endpoint in ("health", "ready", "static"):
            return
        if not wd.exists():
            # No league yet → first-login lands on onboarding via the dashboard.
            if request.endpoint == "dashboard":
                return redirect(url_for("onboarding"))
            return
        # League exists and is warm → prime() is an instant no-op, carry on.
        if wd.is_primed():
            wd.prime()
            return
        # Cold. Decide loader vs inline by WORLD IDENTITY (the generation salt — a
        # fresh random per New League / takeover, stable within a league), NOT a
        # process flag and NOT the world row id (SQLite reuses the rowid after
        # start_new, so a brand-new takeover world reappears as id 1):
        #  • same league we've already warmed → a fast re-prime (post week advance /
        #    roster edit): the developed-roster cache stays warm, so do it inline.
        #  • a DIFFERENT league — takeover, new league, or a fresh machine — is the
        #    slow cold gen: warm in the background and answer with the loader so the
        #    URL responds now instead of blocking for a minute (the page that
        #    "wouldn't reload" after a takeover).
        cur_key = wd.active_salt()
        if not cur_key:
            # Legacy saves created before the salt column was backfilled have an
            # empty salt; fall back to the world id (stable for a continuing save —
            # rowid reuse only bites across start_new, which always sets a fresh
            # non-empty salt) so they still get the fast inline re-prime.
            w = wd.load_world()
            cur_key = str(w["id"]) if w else None
        if cur_key and _warmed_salt["v"] == cur_key:
            wd.prime()
            return
        if not _warming.is_set():
            _warming.set()

            def _warm():
                try:
                    wd.prime()
                    _warmed_salt["v"] = cur_key    # only on success → a fail retries
                finally:
                    _warming.clear()

            threading.Thread(target=_warm, name="world-warm", daemon=True).start()
        return Response(LOADING_HTML, mimetype="text/html")

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
        from generators import region_preset
        from .state import all_programs_by_universe
        import secrets
        # Every band's raw {region: weight} map, so the editor can recompute live
        # effective shares when the player switches bands (not just multipliers).
        band_weights = {value: region_preset(value) for value, _ in worldconfig.BANDS}
        return render_template("onboarding.html", active="World",
                               bands=worldconfig.BANDS, band=worldconfig.name_preset(),
                               region_groups=worldconfig.region_groups(),
                               band_weights=band_weights,
                               weight_scale=worldconfig.WEIGHT_SCALE,
                               intl_share=worldconfig.intl_share(),
                               intl_share_choices=worldconfig.INTL_SHARE_CHOICES,
                               programs_by_universe=all_programs_by_universe(),
                               user_program=worldconfig.user_program(),
                               default_seed=secrets.token_hex(4))

    @app.route("/world/new", methods=["POST"])
    def world_new():
        from app import worldconfig
        worldconfig.set_name_preset(request.form.get("name_preset", "tennis_global"))
        worldconfig.set_intl_share(request.form.get("intl_share"))
        worldconfig.set_active(request.form.getlist("divisions"), request.form.getlist("genders"))
        # Coached program (career mode). Value is "division|gender|school", or empty
        # for spectate-only. The coached universe is force-activated so it always
        # runs in detail, even if its division/gender box was left unchecked.
        prog_raw = request.form.get("user_program", "").strip()
        if prog_raw.count("|") == 2:
            pdiv, pgen, pschool = prog_raw.split("|", 2)
            worldconfig.set_user_program(pdiv, pschool, pgen)
            if worldconfig.user_program():
                worldconfig.set_active(
                    list(dict.fromkeys(worldconfig.active_divisions() + [pdiv])),
                    list(dict.fromkeys(worldconfig.active_genders() + [pgen])))
        else:
            worldconfig.clear_user_program()
        weights = {}
        for grp in worldconfig.region_groups():
            for r in grp["regions"]:
                if r.get("is_domestic"):
                    continue                      # US share is the intl_share split
                try:
                    weights[r["id"]] = float(request.form.get(f"w_{r['id']}", "0"))
                except (TypeError, ValueError):
                    pass
        worldconfig.set_region_weights(weights)
        # The world SEED is the generation salt — it drives every name, roster and
        # recruit roll. A typed seed makes the world reproducible; blank → a fresh
        # random one (so two restarts never collide). See onboarding "World seed".
        seed = request.form.get("seed", "").strip()
        wd.start_new(salt=seed or None)
        reset_all()
        return redirect(url_for("world_view"))

    @app.route("/preseason")
    def preseason_view():
        return render_template("preseason.html", active="Preseason", ps=preseason_view_data())

    @app.route("/my-program")
    def my_program():
        mp = my_program_view()
        if not mp:                      # spectator mode (or saved team gone) → pick one
            return redirect(url_for("onboarding"))
        return render_template("my_program.html", active="My Program", mp=mp)

    @app.route("/my-program/lineup", methods=["POST"])
    def my_program_lineup():
        # Hand-set the coached team's singles ladder. The school is taken from the
        # saved program, never the form, so this only ever edits your own team.
        from app import worldconfig
        from app.ncaa import build_roster, load_division
        prog = worldconfig.user_program()
        if not prog:
            return redirect(url_for("onboarding"))
        school, division, gender = prog["school"], prog["division"], prog["gender"]
        if request.form.get("action") == "reset":
            ov.clear_lineup(school)             # back to the auto ladder
            reset_lineup()
            return redirect(url_for("my_program"))
        p = load_division(division, gender).by_school(school)
        valid = {pr.pid for pr in build_roster(p)} if p else set()
        # Slot picker: one dropdown per singles court (the division's card size —
        # ncaa.lineup_size) sets the whole ladder at once (any roster player into
        # any slot — no more nudging ▲▼ one row at a time).
        from app.ncaa import lineup_size
        n = lineup_size(division)
        slots = [f"s{i}" for i in range(1, n + 1)]
        if any(request.form.get(s) for s in slots):
            pids = [request.form.get(s, "").strip() for s in slots]
            if all(pid in valid for pid in pids) and len(set(pids)) == n:
                ov.set_lineup(school, pids)     # pinned card leads; rest fall in by ability
                reset_lineup()
            return redirect(url_for("my_program"))
        # Legacy single-step nudge (kept for any old links / accessibility).
        pid = request.form.get("pid", "")
        direction = request.form.get("dir", "")
        order = [pr.pid for pr in build_roster(p)] if p else []
        if pid in order:
            i = order.index(pid)
            j = i - 1 if direction == "up" else i + 1
            if 0 <= j < len(order):
                order[i], order[j] = order[j], order[i]
                ov.set_lineup(school, order)
                reset_lineup()
        return redirect(url_for("my_program"))

    @app.route("/my-program/doubles", methods=["POST"])
    def my_program_doubles():
        # Hand-set the coached team's INDEPENDENT doubles lineup (the division's
        # doubles-line count — D1 fields 5 pairs, the rest 3). Players may be any
        # roster member, not just singles starters — a doubles specialist. School
        # comes from the saved program, so this only ever edits your own team.
        from app import worldconfig
        from app.ncaa import build_roster, load_division, dual_format
        prog = worldconfig.user_program()
        if not prog:
            return redirect(url_for("onboarding"))
        school, division, gender = prog["school"], prog["division"], prog["gender"]
        if request.form.get("action") == "reset":
            ov.clear_doubles(school)            # back to the auto pairing
            reset_lineup()
            return redirect(url_for("my_program"))
        n_d = dual_format(division).n_doubles
        slots = [x for i in range(1, n_d + 1) for x in (f"d{i}a", f"d{i}b")]
        pids = [request.form.get(s, "").strip() for s in slots]
        p = load_division(division, gender).by_school(school)
        valid = {pr.pid for pr in build_roster(p)} if p else set()
        if all(pid in valid for pid in pids) and len(set(pids)) == 2 * n_d:
            ov.set_doubles(school, pids)
            reset_lineup()
        return redirect(url_for("my_program"))

    @app.route("/my-program/offers")
    def my_offers():
        off = job_offers()
        if not off:
            return redirect(url_for("onboarding"))
        return render_template("my_offers.html", active="My Program", off=off)

    @app.route("/my-program/offers/accept", methods=["POST"])
    def my_offers_accept():
        # Take a new job. Opt-in only; the chosen offer must be on the live slate.
        from app import worldconfig
        prog = worldconfig.user_program()
        if not prog:
            return redirect(url_for("onboarding"))
        gender = prog["gender"]
        new_div = request.form.get("division", "")
        new_school = request.form.get("school", "")
        off = job_offers() or {}
        if off.get("available") and any(o["school"] == new_school and o["division"] == new_div
                                        for o in off.get("offers", [])):
            rep = my_season_report() or {}
            worldconfig.push_coach_seat({          # archive the seat you're leaving
                "year": rep.get("year"), "division": prog["division"],
                "school": prog["school"], "gender": gender,
                "wins": rep.get("wins"), "losses": rep.get("losses"),
                "verdict": rep.get("verdict"), "finish": rep.get("pi_rank")})
            worldconfig.set_user_program(new_div, new_school, gender)
            worldconfig.set_active(                # the new universe must run in detail
                list(dict.fromkeys(worldconfig.active_divisions() + [new_div])),
                list(dict.fromkeys(worldconfig.active_genders() + [gender])))
            reset_all()
        return redirect(url_for("my_program"))

    @app.route("/my-program/report")
    def my_report():
        rep = my_season_report()
        if not rep:
            return redirect(url_for("onboarding"))
        return render_template("my_report.html", active="My Program", rep=rep)

    @app.route("/my-program/schedule")
    def my_schedule():
        plan = my_schedule_plan()
        if not plan:
            return redirect(url_for("onboarding"))
        return render_template("my_schedule.html", active="My Program", plan=plan)

    @app.route("/my-program/schedule/edit", methods=["POST"])
    def my_schedule_edit():
        # Re-opponent a non-conference dual — preseason only, coached team only.
        from app import worldconfig
        prog = worldconfig.user_program()
        if not prog:
            return redirect(url_for("onboarding"))
        division, gender, school = prog["division"], prog["gender"], prog["school"]
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        if wd.load_world()["week"] == 0:            # planning locks once the season starts
            dual_id = request.form.get("dual_id", type=int)
            action = request.form.get("action", "")
            if dual_id and action == "swap":
                sm.swap_nonconf_opponent(sid, dual_id, school,
                                         request.form.get("opponent", ""), division, gender)
            elif dual_id and action == "home":
                sm.set_nonconf_home(sid, dual_id, school, request.form.get("home") == "1")
            reset_all()
        return redirect(url_for("my_schedule"))

    @app.route("/world")
    def world_view():
        from app import worldconfig
        return render_template("world.html", active="World", hub=world_hub(), crest=crest,
                               box_stats=worldconfig.box_stats_enabled(),
                               full_engine=worldconfig.match_fidelity() == "full")

    @app.route("/world/boxstats", methods=["POST"])
    def world_boxstats():
        # Per-save switch for per-match box stats on season duals (outcomes are
        # untouched either way — off just means scoreline-only persistence).
        from app import worldconfig
        worldconfig.set_box_stats(request.form.get("on") == "1")
        return redirect(request.referrer or url_for("world_view"))

    @app.route("/world/fidelity", methods=["POST"])
    def world_fidelity():
        # Per-save switch for match fidelity. "full" resolves every point (slow,
        # offline-calibration use); "fast" is the tuned production model. Read at
        # sim time, so flipping it applies from the next dual on.
        from app import worldconfig
        worldconfig.set_match_fidelity(request.form.get("full") == "1")
        return redirect(request.referrer or url_for("world_view"))

    @app.route("/world/advance", methods=["POST"])
    def world_advance():
        """THE advance control — the only route in the app that moves a season
        forward. Every surface that offers "advance" posts here (see the rule in
        docs/AAR-universe-desync-season-hub-advance.md): a second endpoint that
        stepped one universe on its own is what forked a save into universes
        sitting at different weeks. Pass `back=1` to return to the referring page
        instead of the World hub."""
        import app.honors as honors
        if not wd.exists():
            # No world: a standalone season (dev / tests) is self-contained — there
            # is no other universe to fall out of step with, and no world to build.
            division, gender, _label, _u = _universe(request)
            sm.advance(sm.get_or_create(division, gender, seed=wd.current_year_seed()))
        else:
            # Once the active seasons are complete, hold at the awards step until honors
            # are stamped for every ACTIVE universe (don't wait on a dormant one, whose
            # honors never stamp — that would jam a single-gender save here forever).
            year = wd.BASE_YEAR + wd.load_world()["year"]
            pending = (wd.season_complete()
                       and not all(honors.has_season(year, d, g) for (d, g) in wd._active_unis()))
            if not pending:
                wd.advance_week()
        if request.form.get("back") or request.args.get("back"):
            return redirect(request.referrer or url_for("world_view"))
        return redirect(url_for("world_view"))

    @app.route("/world/resync", methods=["POST"])
    def world_resync():
        # Repair a save whose universes fell out of step (the Season Hub's advance
        # used to step one alone): catch the laggards up to the furthest-along one.
        # No reset_all() — like `advance_week`, this only plays more duals, and the
        # result caches are keyed by completed-dual count, so they self-invalidate.
        wd.resync_universes()
        return redirect(request.referrer or url_for("world_view"))

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
        try:
            page = int(request.args.get("page", 1))
        except (ValueError, TypeError):
            page = 1
        from .pagination import per_page_arg
        from .state import PRESEASON_PORTAL_PER_PAGE
        per = per_page_arg(request.args.get("per"), PRESEASON_PORTAL_PER_PAGE)
        q = (request.args.get("q", "") or "").strip()
        return render_template("fall_portal.html", active="World",
                               fp=fall_portal_view(page=page, per_page=per, q=q),
                               crest=crest)

    def _fp_return():
        """Redirect back to the fall portal with the SAME page / page-size / search an
        action was fired from, so editing a row (redirect/drop/sign/add) doesn't throw
        you to the top or reset your view. The fall slate isn't gender-filtered — the
        drop form's `gender` field is the player's own (for set_status), never a
        view filter."""
        args = {}
        for k in ("page", "per", "q"):
            v = (request.form.get(k, "") or "").strip()
            if v:
                args[k] = v
        return redirect(url_for("fall_portal", **args))

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
            return _fp_return()          # single-row drop: stay on the current page
        return redirect(url_for("fall_portal"))

    @app.route("/fall-portal/redirect", methods=["POST"])
    def fall_portal_redirect():
        pid, dest = request.form.get("pid", "").strip(), request.form.get("dest", "").strip()
        if pid and dest:
            wd.redirect_fall_portal_mover(DEFAULT_SEED, pid, dest)
        return _fp_return()

    def _portal_add_pids():
        """Resolve the add form into pids: an explicit `pid`, plus every name in the
        `player` field — comma- or newline-separated, so a whole list of players can
        be added in ONE submit instead of one form round-trip each."""
        pids = []
        pid = request.form.get("pid", "").strip()
        if pid:
            pids.append(pid)
        raw = request.form.get("player", "")
        for name in (n.strip() for chunk in raw.split("\n") for n in chunk.split(",")):
            if not name:
                continue
            hits = search_players(name).get("players", [])
            if hits:
                pids.append(hits[0]["pid"])
        return pids

    @app.route("/fall-portal/add", methods=["POST"])
    def fall_portal_add():
        dest = request.form.get("dest", "").strip() or None
        for pid in _portal_add_pids():
            wd.add_fall_portal_mover(DEFAULT_SEED, pid, dest)
        return _fp_return()

    @app.route("/fall-portal/apply", methods=["POST"])
    def fall_portal_apply():
        # Batch-edit the slate in ONE submit: every rider row's staged destination
        # change becomes a redirect, every checked row a drop — instead of one form
        # round-trip per player.
        w = wd.load_world()
        if not w:
            return _fp_return()
        year = w["year"]
        for k, v in request.form.items():
            if k.startswith("dest_") and v.strip():
                pid = k[5:]
                if v.strip() != request.form.get("cur_" + pid, "").strip():
                    wd.redirect_fall_portal_mover(DEFAULT_SEED, pid, v.strip())
            elif k.startswith("drop_") and v:
                ov.set_status(year, v, k[5:], "rejected")   # value carries the gender
        return _fp_return()

    @app.route("/fall-portal/pro-sign", methods=["POST"])
    def fall_portal_pro_sign():
        pid = request.form.get("pid", "")
        dest = request.form.get("dest", "")           # blank -> unsign (back to free agent)
        args = {}
        page = (request.form.get("page", "") or "").strip()
        if page:
            args["page"] = page
        if pid:
            w = wd.load_world()
            cyc = f"{w['year']}-fall" if w else None
            r = wd.sign_pro(DEFAULT_SEED, pid, dest, cycle_key=cyc)
            if not r.get("ok") and dest.strip():
                args["signerr"] = r.get("error", "Could not sign that pro.")
        return redirect(url_for("fall_portal", **args))

    @app.route("/fall-portal/commit", methods=["POST"])
    def fall_portal_commit():
        # Commit resolves the whole kept slate (sim picks + your edits/adds) and
        # applies it — relocations, two-stint history, cascade and all.
        wd.commit_fall_portal()
        return redirect(url_for("world_view"))

    @app.route("/preseason-portal")
    def preseason_portal():
        # The week-0 misallocation reshuffle: move players who are too good for their
        # division (the first-launch D3/D4 over-allocation) to a fitting program before
        # the season opens. Seeds the slate on first visit if nothing's proposed yet.
        w = wd.load_world()
        if w and w["week"] == 0 and not ov.ps_get_proposals(w["year"]):
            wd.run_preseason_portal()
        gender = request.args.get("gender", "all")
        try:
            page = int(request.args.get("page", 1))
        except (ValueError, TypeError):
            page = 1
        from .pagination import per_page_arg
        from .state import PRESEASON_PORTAL_PER_PAGE
        per = per_page_arg(request.args.get("per"), PRESEASON_PORTAL_PER_PAGE)
        q = (request.args.get("q", "") or "").strip()
        return render_template("preseason_portal.html", active="Preseason",
                               pp=preseason_portal_view(gender=gender, page=page,
                                                        per_page=per, q=q), crest=crest)

    def _pp_return():
        """Redirect back to the portal with the SAME page / page-size / search + gender
        FILTER the action was fired from, so editing a row (redirect/sign/drop/add)
        doesn't bounce you to page 1. Reads the explicit current-filter field `fg` in
        preference to `gender`: the single-row drop carries `gender` as the PLAYER's
        own gender (ps_set_status needs it), which is NOT the active filter — using it
        would collapse an 'All' slate to one gender."""
        args = {}
        g = (request.form.get("fg") or request.form.get("gender") or "").strip()
        if g:
            args["gender"] = g
        for k in ("page", "per", "q"):
            v = (request.form.get(k, "") or "").strip()
            if v:
                args[k] = v
        return redirect(url_for("preseason_portal", **args))

    @app.route("/preseason-portal/rescan", methods=["POST"])
    def preseason_portal_rescan():
        wd.rescan_preseason_portal()
        return redirect(url_for("preseason_portal"))

    @app.route("/preseason-portal/cap", methods=["POST"])
    def preseason_portal_cap_set():
        from app import worldconfig
        worldconfig.set_preseason_portal_cap(request.form.get("cap", ""))
        wd.rescan_preseason_portal()          # re-scan with the new per-gender cap
        return redirect(url_for("preseason_portal"))

    @app.route("/preseason-portal/pros", methods=["POST"])
    def preseason_portal_pros_set():
        from app import worldconfig
        worldconfig.set_pros_per_cycle(request.form.get("pros", ""))   # even, per gender
        return redirect(url_for("preseason_portal"))

    @app.route("/preseason-portal/pro-sign", methods=["POST"])
    def preseason_portal_pro_sign():
        pid = request.form.get("pid", "")
        dest = request.form.get("dest", "")           # blank -> unsign (back to free agent)
        args = {"gender": request.form.get("gender", "all")}
        page = (request.form.get("page", "") or "").strip()
        if page:
            args["page"] = page
        if pid:
            r = wd.sign_pro(DEFAULT_SEED, pid, dest)
            if not r.get("ok") and dest.strip():
                args["signerr"] = r.get("error", "Could not sign that pro.")
        return redirect(url_for("preseason_portal", **args))

    @app.route("/preseason-portal/approve", methods=["POST"])
    def preseason_portal_approve():
        w = wd.load_world()
        year = w["year"] if w else 0
        action = request.form.get("action", "")
        if action == "reject_all":
            for r in ov.ps_get_proposals(year):
                if r["cascade_from"] is None and r["status"] != "rejected":
                    ov.ps_set_status(year, r["gender"], r["pid"], "rejected")
        elif action == "approve_all":
            for r in ov.ps_get_proposals(year):
                if r["cascade_from"] is None and r["status"] == "rejected":
                    ov.ps_set_status(year, r["gender"], r["pid"], "proposed")
        else:
            pid, gender = request.form.get("pid", ""), request.form.get("gender", "")
            if pid and gender:
                ov.ps_set_status(year, gender, pid, request.form.get("status", "rejected"))
            return _pp_return()          # single-row drop: stay on the current page
        return redirect(url_for("preseason_portal"))

    @app.route("/preseason-portal/redirect", methods=["POST"])
    def preseason_portal_redirect():
        pid, dest = request.form.get("pid", "").strip(), request.form.get("dest", "").strip()
        if pid and dest:
            wd.redirect_preseason_portal_mover(DEFAULT_SEED, pid, dest)
        return _pp_return()

    @app.route("/preseason-portal/add", methods=["POST"])
    def preseason_portal_add():
        dest = request.form.get("dest", "").strip() or None
        for pid in _portal_add_pids():
            wd.add_preseason_portal_mover(DEFAULT_SEED, pid, dest)
        return _pp_return()

    @app.route("/preseason-portal/apply", methods=["POST"])
    def preseason_portal_apply():
        # Batch-edit the slate in ONE submit (staged redirects + checked drops) —
        # the pre-season mirror of /fall-portal/apply.
        w = wd.load_world()
        if not w:
            return _pp_return()
        year = w["year"]
        for k, v in request.form.items():
            if k.startswith("dest_") and v.strip():
                pid = k[5:]
                if v.strip() != request.form.get("cur_" + pid, "").strip():
                    wd.redirect_preseason_portal_mover(DEFAULT_SEED, pid, v.strip())
            elif k.startswith("drop_") and v:
                ov.ps_set_status(year, v, k[5:], "rejected")
        return _pp_return()

    @app.route("/preseason-portal/commit", methods=["POST"])
    def preseason_portal_commit():
        wd.commit_preseason_portal()
        return redirect(url_for("preseason_portal"))

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

    def _archived_rankings(season, division, gender, label, u, view, scope, season_opts):
        """Serve a PAST season's final CTA boards from the archive (stamped when
        that season's conference tournaments ended) through the same view/scope
        chrome as the live page. Conference/tier/min-matches filters don't apply —
        the final board is a frozen artifact, not a live query."""
        from app import rankings_archive
        from app.scout_intel import US_REGION_ORDER
        rows = rankings_archive.board(season, division, gender, view)
        common = dict(active="Rankings", mode=view, view=view, scope=scope,
                      archive=True, season=season, season_opts=season_opts,
                      conferences=["All"], tiers=["All"], conf="All", tier="All",
                      sort="Rank", u=u, uni_label=label, division=division, minm=3)
        if scope == "regional":
            groups = {}
            for r in rows:
                if r["region"]:
                    groups.setdefault(r["region"], []).append(r)
            regions = [(reg, groups[reg][:10]) for reg in US_REGION_ORDER if groups.get(reg)]
            return render_template("rankings.html", regions=regions, **common)
        if scope == "newcomer":
            rows = [r for r in rows if wd._base_class(r.get("cls") or "") == "Fr"][:50]
        return render_template("rankings.html", arows=rows, **common)

    @app.route("/rankings")
    def rankings():
        division, gender, label, u = _universe(request)
        conf = request.args.get("conf", "All")
        view = request.args.get("view", "teams")
        scope = request.args.get("scope", "national")
        if view == "regional":       # legacy URLs from before scopes existed
            view, scope = "teams", "regional"
        if view not in ("teams", "singles", "doubles"):
            view = "teams"
        if scope not in ("national", "regional", "newcomer"):
            scope = "national"
        # Newcomer is a D1, SINGLES-only freshman board (owner rule — the real ITA
        # only runs newcomer rankings for D1; ours restricts to freshmen).
        if scope == "newcomer" and (view != "singles" or division != "D1"):
            scope = "national"

        # Season select: the current year is the LIVE board; past years serve the
        # final rankings stamped when that season's conference tournaments ended.
        from app import rankings_archive
        cur_year = 2026 + (wd.load_world()["year"] if wd.exists() else 0)
        past_years = [y for y in rankings_archive.years(division, gender) if y != cur_year]
        season_opts = [cur_year] + past_years
        try:
            season = int(request.args.get("season", cur_year))
        except (ValueError, TypeError):
            season = cur_year
        if season in past_years:
            return _archived_rankings(season, division, gender, label, u, view, scope,
                                      season_opts)
        season = cur_year
        # National field sizes, CTA-style: teams 75/50, singles 125/75, doubles 60/40 (D2 smaller).
        small = division == "D2"
        if view in ("singles", "doubles"):
            try:
                minm = int(request.args.get("minm", 3))
            except (ValueError, TypeError):
                minm = 3
            minm = max(1, min(30, minm))
            common = dict(active="Rankings", mode=view, view=view, scope=scope,
                          conferences=conferences_for(division, gender), tiers=["All"],
                          conf=conf, tier="All", sort="Rank", u=u, uni_label=label,
                          minm=minm, division=division, archive=False,
                          season=season, season_opts=season_opts)
            if scope == "regional":
                from .state import regional_player_rows
                regions = regional_player_rows(division, gender, view, min_matches=minm)
                return render_template("rankings.html", regions=regions, **common)
            if scope == "newcomer":
                from .state import newcomer_ranking_rows
                prows = newcomer_ranking_rows(division, gender, min_matches=minm)
                prows = [r for r in prows if conf == "All" or r["conf"] == conf]
                p = paginate(prows, request.args.get("page", 1))
                return render_template("rankings.html", p=p, prows=p.items,
                                       total=len(prows), matches=len(prows), **common)
            prows = (singles_ranking_rows if view == "singles"
                     else doubles_ranking_rows)(division, gender, min_matches=minm)
            limit = ({"singles": 75, "doubles": 40} if small
                     else {"singles": 125, "doubles": 60})[view]
            prows = [r for r in prows if conf == "All" or r["conf"] == conf][:limit]
            p = paginate(prows, request.args.get("page", 1))
            return render_template("rankings.html", p=p, prows=p.items,
                                   total=len(prows), matches=len(prows), **common)
        if scope == "regional":
            from .state import regional_ranking_rows
            regions = regional_ranking_rows(division, gender)
            return render_template(
                "rankings.html", active="Rankings", mode="regional", view="teams",
                scope="regional", regions=regions,
                conferences=conferences_for(division, gender), tiers=["All"],
                conf=conf, tier="All", sort="Rank", u=u, uni_label=label, division=division,
                archive=False, season=season, season_opts=season_opts,
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
            "rankings.html", active="Rankings", mode="teams", view="teams", scope="national",
            p=p, rows=p.items,
            total=total, matches=len(filtered), conferences=conferences_for(division, gender),
            tiers=tiers, conf=conf, tier=tier, sort=sort, u=u, uni_label=label,
            division=division, archive=False, season=season, season_opts=season_opts,
        )

    @app.route("/polls")
    def polls_page():
        from app import polls as pollmod
        division, uni_gender, label, u = _universe(request)
        gender = request.args.get("gender", uni_gender)
        if gender not in ("men", "women"):
            gender = "men"
        which = request.args.get("poll", "media")
        if which not in ("media", "coaches"):
            which = "media"
        scope = request.args.get("scope", "national")
        div = scope if scope in ("D1", "D2", "D3", "D4") else None
        p = pollmod.poll(wd.current_year_seed(), gender, which, division=div)
        return render_template("polls.html", active="Rankings", u=u, gender=gender,
                               which=which, scope=(div or "national"), poll=p, crest=crest,
                               labels=pollmod.POLL_LABELS)

    @app.route("/staff-search")
    def staff_search_page():
        division, uni_gender, label, u = _universe(request)
        gender = request.args.get("gender", uni_gender)
        if gender not in ("men", "women", "all"):
            gender = uni_gender
        div_f = request.args.get("div", "All")
        role = request.args.get("role", "both")
        if role not in ("head", "assistant", "both"):
            role = "both"
        sort = request.args.get("sort", "overall")
        q = request.args.get("q", "")
        res = staff_search(gender, division=div_f, role=role, sort=sort, q=q)
        pg = paginate(res["rows"], request.args.get("page", 1))
        return render_template("staff_search.html", active="Management",
                               rows=pg.items, p=pg, total=len(res["rows"]), hc_bar=res["hc_bar"],
                               gender=gender, div_f=div_f, role=role, sort=sort, q=q,
                               u=u, uni_label=label, crest=crest,
                               divisions=["All", "D1", "D2", "D3", "D4"],
                               genders=[("men", "Men"), ("women", "Women"), ("all", "Both")],
                               roles=[("both", "Head + Assistants"), ("head", "Head coaches"),
                                      ("assistant", "Assistants")])

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
        import app.coachreg as coachreg
        career_path = list(reversed(coachreg.assignments(coach_id)))
        player_awards = coach_player_awards(coach_id)
        # Staff at the coach's current school — the in-staff swap targets.
        staff = coaching_staff(div, gen, c["school"]) if c.get("school") else []
        # Move target: any program in ANY division/gender, as a Gender→Conference→School
        # cascade instead of one dropdown of every program.
        move_tree = coach_move_tree() if c.get("school") else {"men": [], "women": []}
        return render_template("coach.html", active="Teams", c=c, honor_years=honor_years,
                               career=career, player_awards=player_awards, staff=staff,
                               career_path=career_path,
                               move_tree=move_tree, crest=crest, u=u, uni_label=label)

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
        move_year = wd.BASE_YEAR + (wd.load_world()["year"] if wd.exists() else 0)
        coachreg.move_to(coach_id, g2, d2, s2, r2, year=move_year)
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
        # Individual singles/doubles champions come from the world_championship
        # snapshots (stored at each year rollover), keyed (year, division, gender).
        indiv: dict = {}
        for _v, d, g, _lbl in UNIVERSES:
            for e in past_individual_champions(d, g):
                indiv[(e["year"], d, g)] = e
        years = sorted(set(honors.years()) | {y for y, _d, _g in indiv}, reverse=True)
        archive = []
        for y in years:
            rows = honors.winners(y, ["national_champion", "national_poty", "national_coty"])
            unis: dict = {}
            for r in rows:
                slot = unis.setdefault((r["division"], r["gender"]), {})
                if r["award"] == "national_champion":
                    slot.setdefault("champion", r["school"])
                else:
                    slot[r["award"]] = r
            for (yy, d, g), e in indiv.items():
                if yy == y:
                    slot = unis.setdefault((d, g), {})
                    slot["singles"] = e.get("singles")
                    slot["doubles"] = e.get("doubles")
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
        # The Preseason NIT draws through the NCAA bracket's surface — same tree,
        # same canvas, same viewer — so it takes the same season picker too.
        division, gender, label, u = _universe(request)
        years = ita_bracket_years(division, gender)
        cur_year = wd.BASE_YEAR + (wd.load_world()["year"] if wd.exists() else 0)
        sel = request.args.get("year", type=int)
        view_year = sel if (sel and sel != cur_year) else None
        return render_template("ita.html", active="Season", u=u, uni_label=label,
                               br=ita_bracket_view(division, gender, year=view_year),
                               division=division, bracket_years=years,
                               cur_year=cur_year, sel_year=sel or cur_year)

    @app.route("/world-cups")
    def world_cups():
        # National-team cups: Davis Cup (men) / Billie Jean King Cup (women) —
        # derived off the same rosters as everything else, snapshotted at rollover.
        g = request.args.get("g", "men")
        if g not in ("men", "women"):
            g = "men"
        sel_year = request.args.get("year", type=int)
        cup = get_world_cup(g, year=sel_year)
        # ARCHIVED years only. The picker used to also offer the current year as soon
        # as the seasons completed, back when the cup was computed live at that point.
        # It is now an explicit step, so between "seasons complete" and "cup step run"
        # the current year has no cup — and `get_world_cup` falls through to the most
        # recent archive, which rendered LAST year's champion and draw under a pill
        # highlighting this year.
        years = sorted((wd.BASE_YEAR + y for y in wd.world_cup_years(DEFAULT_SEED)),
                       reverse=True)
        return render_template("world_cups.html", active="World Cups", g=g,
                               cup=cup, years=years, sel_year=sel_year, crest=crest)

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
                               past_champs=past_individual_champions(division, gender),
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
                               past_champs=past_individual_champions(division, gender),
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
            can_next=gs.can_start_next(lid),
            standings=gs.standings(lid), honors=gs.honors_board(lid),
            history=gs.season_history(lid), transactions=gs.transactions(lid, limit=40),
            recent=gs.week_duals(lid, max(1, league["current_week"] - 1)),
            recent_week=max(1, league["current_week"] - 1))

    @app.route("/gtt/new", methods=["POST"])
    def gtt_new():
        # No seed input: a league always binds to the save's ACTIVE world (the
        # college game being played) — the pro league is a continuation of it,
        # never a self-contained parallel universe.
        name = (request.form.get("name") or "Global Team Tennis").strip()
        teams = min(16, max(4, request.form.get("teams", type=int) or gs.DEFAULT_TEAMS))
        lid = gs.create_league(name, n_teams=teams)
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

    @app.route("/gtt/schedule")
    def gtt_schedule():
        league, _ = _current_league()
        if not league:
            abort(404)
        return render_template("gtt_schedule.html", active="GTT Schedule", league=league,
                               sched=gs.season_schedule(league["id"]))

    @app.route("/gtt/leaders")
    def gtt_leaders():
        league, _ = _current_league()
        if not league:
            abort(404)
        return render_template("gtt_leaders.html", active="GTT Leaders", league=league,
                               leaders=gs.league_leaders(league["id"]))

    @app.route("/gtt/draft")
    def gtt_draft():
        league, _ = _current_league()
        if not league:
            abort(404)
        board = gs.draft_board(league["id"])
        return render_template("gtt_draft.html", active="GTT", league=league, board=board)

    @app.route("/gtt/delete", methods=["POST"])
    def gtt_delete():
        # Deleting a league is irreversible (rosters, results, honors, HoF all go);
        # the college world it drew graduates from is untouched.
        lid = request.form.get("lg", type=int)
        if lid:
            gs.delete_league(lid)
        return redirect(url_for("gtt_hub"))

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

    @app.route("/gtt/alumni")
    def gtt_alumni():
        # Everyone who persisted past college, in one place — a query over the live
        # tables, deliberately not a separate archive that could drift from them.
        league, leagues = _current_league()
        state = request.args.get("state", "all")
        if state not in gs.ALUMNI_STATES:
            state = "all"
        people = gs.alumni(league["id"], state) if league else []
        counts = {}
        if league:
            for r in gs.alumni(league["id"], "all", limit=100000):
                counts[r["state"]] = counts.get(r["state"], 0) + 1
        return render_template("gtt_alumni.html", active="GTT", league=league,
                               leagues=leagues, people=people, state=state,
                               states=gs.ALUMNI_STATES, counts=counts)

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
        # Liveness only — must NOT touch the world (see _prime_world). Always 200.
        return {"status": "ok"}, 200

    @app.route("/api/ready")
    def ready():
        # The loader polls this. Ready = no league yet (loader hands off to
        # onboarding) or the world is warm. Cheap + read-only; never primes.
        return {"ready": (not wd.exists()) or wd.is_primed()}, 200

    @app.route("/methodology")
    def methodology():
        return render_template("methodology.html", active="Methodology")

    @app.route("/guide")
    def guide():
        # The definitive, sectioned game manual — the same reference material as
        # docs/GUIDE.md (which is the canonical source: point an LLM sidecar at
        # that file for the full text plus the AAR changelog appendix). This page
        # is the in-app, player-facing rendering of it; keep the two in sync when
        # a system changes rather than letting one drift stale.
        from .guide_data import APPENDIX_CATEGORIES
        return render_template("guide.html", active="Guide",
                               appendix_cats=APPENDIX_CATEGORIES,
                               scale_rows=_str_scale_rows())

    def _dual_pick(req):
        """Resolve (gender, home_div, away_div, home_schools, away_schools, home, away)
        for the exhibition dual. Gender is shared; each side picks its OWN division so
        talent can be benchmarked across levels. Falls back cleanly when a school isn't
        in the (possibly just-switched) division on its side."""
        divisions = list(dict.fromkeys(d for _v, d, _g, _l in UNIVERSES))   # D1..D4, in order
        gender = req.args.get("gender", "men")
        if gender not in ("men", "women"):
            gender = "men"
        home_div = req.args.get("home_div", "D1")
        away_div = req.args.get("away_div", "D1")
        if home_div not in divisions:
            home_div = divisions[0]
        if away_div not in divisions:
            away_div = divisions[0]
        home_schools = programs_for(home_div, gender)
        away_schools = programs_for(away_div, gender)
        home = req.args.get("home")
        if home not in home_schools:
            home = "Oregon" if "Oregon" in home_schools else home_schools[0]
        away = req.args.get("away")
        if away not in away_schools:
            away = "Stanford" if "Stanford" in away_schools else away_schools[0]
        return (gender, divisions, home_div, away_div,
                home_schools, away_schools, home, away)

    @app.route("/dual")
    def dual():
        (gender, divisions, home_div, away_div,
         home_schools, away_schools, home, away) = _dual_pick(request)
        home_ranks = {r.school: r for r in ranking_rows(home_div, gender)}
        away_ranks = {r.school: r for r in ranking_rows(away_div, gender)}
        return render_template("dual_setup.html", active="Dual Simulator",
                               home_schools=home_schools, away_schools=away_schools,
                               home=home, away=away, crest=crest,
                               home_ranks=home_ranks, away_ranks=away_ranks,
                               fidelities=FIDELITIES, gender=gender, divisions=divisions,
                               home_div=home_div, away_div=away_div)

    @app.route("/dual/run")
    def dual_run():
        (gender, divisions, home_div, away_div,
         home_schools, away_schools, home, away) = _dual_pick(request)
        if home_div == away_div and home == away:
            away = next((s for s in away_schools if s != home), away)
        try:
            seed = int(request.args.get("seed", "7"))
        except ValueError:
            seed = 7
        fidelity = request.args.get("fidelity", "full")
        if fidelity not in FIDELITIES:
            fidelity = "full"
        view = run_dual_view(home_div, away_div, gender, home, away,
                             seed=seed, fidelity=fidelity)
        return render_template("dual_result.html", active="Dual Simulator", v=view,
                               home=home, away=away, gender=gender,
                               home_div=home_div, away_div=away_div)

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
        power6 = next((r.p6 for r in live if r.school == school), 0.0)
        abbr, color = crest(school)
        row = get_row(school)
        div_obj = load_division(division, gender)
        prog = div_obj.by_school(school)
        conf = team_conference(division, gender, school) or (row.conf if row else "")
        conf_abbr = (prog.conf_abbr if prog else "") or conf
        # Team picker: a separate CONFERENCE filter + ALPHABETICAL schools, so a team is easy to
        # find (the old picker listed every school in ranking order).
        _progs = {p.school: p for p in div_obj.programs}
        _sch_conf = {r.school: getattr(_progs.get(r.school), "conf_abbr", "") for r in live}
        conferences = sorted({c for c in _sch_conf.values() if c})
        conf_filter = request.args.get("conf", "All")
        if conf_filter != "All" and conf_filter not in conferences:
            conf_filter = "All"
        schools = sorted(r.school for r in live
                         if conf_filter == "All" or _sch_conf.get(r.school) == conf_filter)
        if school not in schools:                       # keep the current team selectable
            schools = sorted(set(schools) | {school})
        return render_template("teams.html", active="Teams", rows=rows, school=school,
                               abbr=abbr, color=color, row=row, power6=power6, conf=conf,
                               conf_abbr=conf_abbr, schools=schools, conferences=conferences,
                               conf_filter=conf_filter, u=u,
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
        is_alumni = False
        if not info:
            # Maybe it's a free-agent pro not yet on any roster — render a preview (STR +
            # attributes) so they can be scouted BEFORE being signed through the portal.
            found = wd.find_pro(DEFAULT_SEED, pid)
            if found:
                from app.web.state import scout_bars as _sb
                from app import pros as _pros
                pro, pg, _cyc, _dest = found
                info = {"name": pro.name, "school": _dest or "Pros", "class": "Pro",
                        "country": pro.country, "secondary_country": getattr(pro, "secondary_country", ""),
                        "hometown": getattr(pro, "hometown", ""), "major": "",
                        "overall": pro.current_overall(), "ceiling": pro.ceiling_overall(),
                        "walk_on": False, "high_school": "", "school_city": "",
                        "recruit_stars": 6, "is_pro": True, "free_agent": not _dest,
                        "signed_with": _dest, "scholarship": 0.0, "scholarship_label": ""}
                _empty_box = {"any": False, "lines": [], "rows": [], "tcells": {},
                              "toverall": "", "tdual": ""}
                return render_template("player.html", active="", pid=pid, info=info,
                                       career=[], career_table=[],
                                       records={"singles": _empty_box, "doubles": _empty_box},
                                       strv=round(pro.str_value(), 1), rel=0.0, wins=0, losses=0,
                                       gender=pg, honor_years=[], ranks=[], journey=[],
                                       attrs=_sb(pro), crest=crest, u=u,
                                       uni_label="Pro free agent")
            # Alumni / historical fallback: graduates and moved players persist in the
            # world store (world_signing / world_roster keeps every year) even after
            # they leave the current season's rosters — hydrate from there so archive
            # links (Hall of Fame, past singles/doubles champions, old honors) never
            # 404. The career card below reads persisted history + honors, so it
            # renders their full record; only live-season bits come back empty.
            from app import economy
            p = wd.find_persisted_player(pid)
            if not p:
                abort(404)
            school, _pdiv = wd.persisted_team(pid)
            # A persisted roster row can also be a current player viewed from the
            # wrong universe. Only the graduate archive enables coach conversion.
            is_alumni = wd.is_graduate(pid)
            info = {"name": p.name, "school": school or "—",
                    "class": getattr(p, "class_year", ""),
                    "country": getattr(p, "country", ""),
                    "secondary_country": getattr(p, "secondary_country", ""),
                    "hometown": getattr(p, "hometown", ""),
                    "major": getattr(p, "major", ""),
                    "overall": p.current_overall(), "ceiling": p.ceiling_overall(),
                    "walk_on": getattr(p, "walk_on", False),
                    "high_school": getattr(p, "high_school", ""), "school_city": "",
                    "recruit_stars": getattr(p, "recruit_stars", 0),
                    "recruit_tier": getattr(p, "recruit_tier", ""),
                    "scholarship": getattr(p, "scholarship", 0.0),
                    "scholarship_label": economy.fraction_label(
                        getattr(p, "scholarship", 0.0))}
        strv, rel = sm.season_player_str(sid).get(pid, (None, 0.0))
        from app.ncaa import player_by_pid
        from app.web.state import scout_bars
        from app import pros as _pros
        pr = player_by_pid(pid)
        # Pros live in world_roster (portal-injected), not the base index — resolve from
        # the persisted roster so the green PRO badge shows on their page. The same
        # fallback serves alumni (graduated / moved players reached from the archives).
        _pp = pr or wd.find_persisted_player(pid)
        attrs = scout_bars(_pp) if _pp else []
        info["is_pro"] = _pros.is_pro(_pp) if _pp else False
        career, (wins, losses) = player_career(division, gender, pid)
        career_table = player_career_table(division, gender, pid)
        records = player_career_records(division, gender, pid)
        honor_years = player_career_honors(division, gender, pid)
        ranks = player_ranks(division, gender, pid)
        journey = player_journey(division, gender, pid)
        season_stats = sm.player_season_stats(sid).get(pid)
        intl = wd.player_world_cups(DEFAULT_SEED, pid)   # International record (cups)
        import app.coachreg as coachreg
        linked_coach = coachreg.coach_for_player(pid)
        return render_template("player.html", active="Teams", pid=pid, info=info,
                               career=career, career_table=career_table, records=records,
                               strv=strv, rel=rel, wins=wins, losses=losses, gender=gender,
                               honor_years=honor_years, ranks=ranks, journey=journey,
                               season_stats=season_stats, intl=intl,
                               linked_coach=linked_coach, is_alumni=is_alumni,
                               coach_move_tree=coach_move_tree() if is_alumni and not linked_coach else {},
                               attrs=attrs, crest=crest, u=u, uni_label=label)

    @app.route("/player/<pid>/become-coach", methods=["POST"])
    def player_become_coach(pid):
        """Give an alumnus a new coaching identity at the program the user picks."""
        division, gender, _label, u = _universe(request)
        p = wd.find_persisted_player(pid)
        if not p or not wd.is_graduate(pid):
            abort(404)
        import app.coachreg as coachreg
        from app import coachgen
        role = request.form.get("role", "asst")
        if role not in ("head", "assoc", "asst"):
            role = "asst"
        dest = request.form.get("dest_school", "")
        try:
            pdiv, coach_gender, school = dest.split("|", 2)
        except ValueError:
            abort(400)
        if coach_gender not in ("men", "women") or pdiv not in ("D1", "D2", "D3", "D4"):
            abort(400)
        # Never trust the form's program tuple: it must resolve in that universe.
        if load_division(pdiv, coach_gender).by_school(school) is None:
            abort(400)
        coachgen.ensure(pdiv, coach_gender, school, role)
        overall = float(p.current_overall())
        c = coachreg.create_from_player(
            pid, name=p.name, home_country=getattr(p, "country", "US"),
            division=pdiv, gender=coach_gender, school=school, role=role,
            dev=max(25, min(80, overall + 4)), rec=max(25, min(80, overall - 3)),
            tac=max(25, min(80, overall)))
        reset_all()
        return redirect(url_for("coach", coach_id=c["coach_id"], u=u))

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
        from .pagination import per_page_arg
        pg = paginate(tp["transfers"], request.args.get("page", 1),
                      per_page=per_page_arg(request.args.get("per"), 40))
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
        # A Jefferson recruit came out of the JHSAA, so their four high-school seasons
        # can be replayed on demand (deterministic; a roster build per year, no duals).
        hs = []
        if getattr(p, "jhsaa", None):
            try:
                from app import jhsaa as _jh
                hs = _jh.career(p.jhsaa["school"], gender, p.name, grad_year,
                                salt=wd.active_salt())
            except Exception:
                hs = []
        return render_template("recruit.html", active="Recruiting", p=p, view=view, hs=hs,
                               gender=gender, grad_year=grad_year, u=u, uni_label=label)

    # ---- JHSAA: state → classification → district → school → player -----------
    # Another layer of the same world, so it browses like the college one. Every
    # route carries the SAME scope in the query string (`g` gender, `group`
    # classification, `year` season), which is what keeps a selected class selected
    # as you move down and back up. All of them READ the archive the rung wrote at
    # week 0 — a JHSAA season is ~5,100 duals and is never re-simulated on a request.

    def _jh_scope_args():
        """The scope every JHSAA page is browsed in, off the query string."""
        division, gender, label, u = _universe(request)
        g = request.args.get("g") or ("girls" if gender in ("women", "female") else "boys")
        year = request.args.get("year", type=int)
        return gender, label, u, g, request.args.get("group"), year

    @app.route("/jhsaa")
    def jhsaa_page():
        """The state high-school home: the selected classification's state tournament
        as the dominant object, its awards beside it, its districts below."""
        gender, label, u, g, group, year = _jh_scope_args()
        view = jhsaa_view(DEFAULT_SEED, g, group, year)
        return render_template("jhsaa.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/jhsaa/bracket")
    def jhsaa_bracket():
        """The full state draw, on the SAME server-positioned tree the NCAA bracket
        and the Preseason NIT use — never a third bracket implementation."""
        gender, label, u, g, group, year = _jh_scope_args()
        view = jhsaa_bracket_view(DEFAULT_SEED, g, group, year)
        return render_template("jhsaa_bracket.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/jhsaa/toc")
    def jhsaa_toc():
        """The Tournament of Champions — its own bracket, per gender."""
        gender, label, u, g, group, year = _jh_scope_args()
        return render_template("jhsaa_toc.html", active="High School",
                               view=jhsaa_toc_view(DEFAULT_SEED, g, year), u=u)

    @app.route("/jhsaa/rankings")
    def jhsaa_rankings():
        """A whole classification, ranked on TOSS — the hub's rail panel showed the
        first twelve of a list that already runs to every program in the class."""
        gender, label, u, g, group, year = _jh_scope_args()
        view = jhsaa_rankings_view(DEFAULT_SEED, g, group, year)
        return render_template("jhsaa_rankings.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/jhsaa/districts")
    def jhsaa_districts():
        gender, label, u, g, group, year = _jh_scope_args()
        view = jhsaa_districts_view(DEFAULT_SEED, g, group, year)
        return render_template("jhsaa_districts.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/jhsaa/district/<group>/<district>")
    def jhsaa_district(group, district):
        """A district is keyed by (CLASSIFICATION, name): the JHSAA reuses its
        geographic district names at every level, so "Halbrook Basin District" is five
        different leagues. Keying on the name alone serves the wrong one."""
        gender, label, u, g, _grp, year = _jh_scope_args()
        view = jhsaa_district_view(DEFAULT_SEED, g, group, district, year)
        if not view.get("found"):
            abort(404)
        return render_template("jhsaa_district.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/jhsaa/school/<school>")
    @app.route("/jhsaa/school/<school>/<int:year>")
    def jhsaa_school(school, year=None):
        """A program page. With `year` it is that ARCHIVED season — the schedule, the
        roster that played it and the standing it finished in — so a season row in the
        program history is a link into the season itself."""
        gender, label, u, g, _group, qyear = _jh_scope_args()
        view = jhsaa_school_view(DEFAULT_SEED, g, school,
                                 year if year is not None else qyear)
        if not view.get("found"):
            abort(404)
        return render_template("jhsaa_school.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/jhsaa/player/<school>/<pid>")
    def jhsaa_player(school, pid):
        """One player's four high-school years. Keyed by pid at their school, which is
        stable across all of them — the continuity the section exists for."""
        gender, label, u, g, _group, _year = _jh_scope_args()
        view = jhsaa_player_view(DEFAULT_SEED, g, school, pid)
        if not view.get("found"):
            abort(404)
        return render_template("jhsaa_player.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/jhsaa/champions")
    def jhsaa_champions():
        gender, label, u, g, _group, _year = _jh_scope_args()
        view = jhsaa_past_winners(DEFAULT_SEED, g)
        return render_template("jhsaa_champions.html", active="High School", view=view,
                               gender=gender, u=u, uni_label=label)

    @app.route("/recruiting/team/<school>")
    def team_recruiting(school):
        division, gender, label, u = _universe(request)
        return render_template("team_recruiting.html", active="Recruiting",
                               cls=team_recruiting_class(gender, school), school=school,
                               u=u, uni_label=label)

    @app.route("/recruiting/signings")
    def signing_tracker_page():
        division, gender, label, u = _universe(request)
        year = request.args.get("year", type=int)   # world-year; past = archived class
        return render_template("signing_tracker.html", active="Recruiting",
                               trk=signing_tracker(gender, division, year=year),
                               gender=gender, u=u, uni_label=label)

    @app.route("/portal-rankings")
    def portal_rankings_page():
        _division, _g, label, u = _universe(request)
        pr = portal_class_rankings(gender=request.args.get("gender", "all"),
                                   division=request.args.get("div", "All"),
                                   year=request.args.get("year"))
        return render_template("portal_rankings.html", active="World", u=u, uni_label=label,
                               pr=pr, divisions=["All", "D1", "D2", "D3", "D4"],
                               genders=["all", "men", "women"])

    @app.route("/wire")
    def wire_page():
        """The Wire — every archived transfer, every season, filterable.

        Paginated in the route (the archive runs to thousands of moves over a decade),
        but the VIEW is computed unpaginated so the KPI strip and the season/conference
        dropdowns describe the whole filtered set rather than the page you're looking at."""
        _division, _g, label, u = _universe(request)
        v = wire_view(gender=request.args.get("gender", "all"),
                      division=request.args.get("div", "All"),
                      conf=request.args.get("conf", "All"),
                      kind=request.args.get("kind", "All"),
                      year=request.args.get("year", "all"),
                      sort=request.args.get("sort", "recent"),
                      q=request.args.get("q", ""))
        pg = paginate(v["rows"], request.args.get("page", 1))
        v = {**v, "rows": pg.items}
        return render_template("wire.html", active="World", u=u, uni_label=label,
                               v=v, p=pg, base_year=wd.BASE_YEAR,
                               divisions=["All", "D1", "D2", "D3", "D4"])

    @app.route("/recruiting/hub")
    def recruiting_hub_page():
        division, gender, label, u = _universe(request)
        rg = RECRUIT_GENDERS.get(gender, "male")
        grad_year = wd.recruiting_grad_year()   # the single active class — this year only
        return render_template("recruiting_hub.html", active="Recruiting",
                               hub=recruiting_hub(rg, grad_year), gender=gender,
                               grad_year=grad_year, u=u, uni_label=label,
                               grad_years=[grad_year])

    @app.route("/recruiting/economy")
    def recruit_economy_page():
        division, gender, label, u = _universe(request)
        return render_template("recruit_economy.html", active="Recruiting",
                               econ=recruit_economy_view(), gender=gender,
                               u=u, uni_label=label)

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
        from app import worldconfig
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
                               classes=["All", "Fr", "So", "Jr", "Sr"],
                               fit_up=worldconfig.fit_reach_up(),
                               fit_down=worldconfig.fit_reach_down())

    @app.route("/intel/underplaced/fit-band", methods=["POST"])
    def intel_underplaced_fit_band():
        from app import worldconfig
        worldconfig.set_fit_reach_up(request.form.get("fit_up", ""))
        worldconfig.set_fit_reach_down(request.form.get("fit_down", ""))
        args = {k: request.form.get(k) for k in ("sort", "div", "class", "q", "u")
                if request.form.get(k)}
        return redirect(url_for("intel_underplaced", **args))

    @app.route("/intel/teams")
    def intel_teams():
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        div_f = request.args.get("div", "All")
        if div_f not in ("All", "D1", "D2", "D3", "D4"):
            div_f = "All"
        confs = si.team_board_conferences(gender, div_f)
        conf_f = request.args.get("conf", "All")
        if conf_f not in confs:
            conf_f = "All"
        sort = request.args.get("sort", "card_ovr")
        direction = "asc" if request.args.get("dir") == "asc" else "desc"
        q = request.args.get("q", "")
        rows = si.team_board(gender, division=div_f, conf=conf_f, sort=sort,
                             direction=direction, q=q)
        pg = paginate(rows, request.args.get("page", 1))
        # Rosters only for the page on screen — embedding all ~1k teams' rosters
        # in one response would swamp the HTML for nothing.
        rosters = si.team_rosters(gender, [t["school"] for t in pg.items])
        return render_template("intel_teams.html", active="Analytics Bureau",
                               rows=pg.items, p=pg, total=len(rows), rosters=rosters,
                               gender=gender, div_f=div_f, conf_f=conf_f, confs=confs,
                               sort=sort, direction=direction, q=q, u=u, uni_label=label,
                               divisions=["All", "D1", "D2", "D3", "D4"])

    @app.route("/intel/architect")
    def intel_architect():
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        div_t = request.args.get("div", division)
        if div_t not in ("D1", "D2", "D3", "D4"):
            div_t = division
        pool = request.args.get("pool", "buried")
        if pool not in ("buried", "below", "any"):
            pool = "buried"
        def _num(name, cast, default):
            try:
                return cast(request.args.get(name, ""))
            except (TypeError, ValueError):
                return default
        min_ovr = max(0, min(80, _num("min_ovr", int, 0)))
        max_ovr = max(min_ovr, min(80, _num("max_ovr", int, 80)))
        min_str = max(0.0, min(99.0, _num("min_str", float, 0.0)))
        max_str = max(min_str, min(99.0, _num("max_str", float, 99.0)))
        n_squads = max(1, min(6, _num("squads", int, 3)))
        arch = si.lineup_architect(gender, target_division=div_t, pool=pool,
                                   min_ovr=min_ovr, max_ovr=max_ovr,
                                   min_str=min_str, max_str=max_str, n_squads=n_squads)
        return render_template("intel_architect.html", active="Analytics Bureau",
                               arch=arch, gender=gender, div_t=div_t, pool=pool,
                               min_ovr=min_ovr, max_ovr=max_ovr,
                               min_str=min_str, max_str=max_str, n_squads=n_squads,
                               u=u, uni_label=label, divisions=["D1", "D2", "D3", "D4"])

    @app.route("/intel/portal-search")
    def intel_portal_search():
        division, uni_gender, label, u = _universe(request)
        import app.scout_intel as si
        # Gender is a first-class filter here (not just the universe key): pick Men,
        # Women, or Both. Defaults to the current universe gender; one gender ~halves
        # the rows loaded. `all` merges both scans.
        gender = request.args.get("gender", uni_gender)
        if gender not in ("men", "women", "all"):
            gender = uni_gender
        div_f = request.args.get("div", "All")
        cls_f = request.args.get("class", "All")
        scope = request.args.get("scope", "all")
        state = request.args.get("state", "All")
        region = request.args.get("region", "All")
        sort = request.args.get("sort", "talent")
        q = request.args.get("q", "")
        rows = si.portal_search(gender, division=div_f, class_year=cls_f, scope=scope,
                                state=state, region=region, sort=sort, q=q)
        pg = paginate(rows, request.args.get("page", 1))
        return render_template("intel_portal_search.html", active="Analytics Bureau",
                               rows=pg.items, p=pg, total=len(rows), gender=gender,
                               div_f=div_f, cls_f=cls_f, scope=scope, state=state,
                               region=region, sort=sort, q=q, u=u, uni_label=label,
                               divisions=["All", "D1", "D2", "D3", "D4"],
                               classes=["All", "Fr", "So", "Jr", "Sr"],
                               genders=[("men", "Men"), ("women", "Women"), ("all", "Both")],
                               regions=["All"] + si.US_REGION_ORDER,
                               states=["All"] + si.portal_search_states(gender),
                               home_state=si.home_state, home_region=si.home_region)

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
        from app.ncaa import lineup_size
        return render_template("intel_lineups.html", active="Analytics Bureau",
                               gender=gender, u=u, uni_label=label, div_f=div_f, conf=conf,
                               confs=confs, lineups=lineups, strength=strength,
                               n_card=lineup_size(div_f),
                               highlight=highlight, divisions=["D1", "D2", "D3", "D4"],
                               scale_rows=_str_scale_rows())

    @app.route("/intel/fit/<pid>")
    def intel_fit(pid):
        division, gender, label, u = _universe(request)
        import app.scout_intel as si
        p, targets = si.fit_targets(gender, pid)
        if p is None:
            abort(404)
        return render_template("intel_fit.html", active="Analytics Bureau",
                               p=p, targets=targets, gender=gender, u=u, uni_label=label)

    @app.route("/intel/my-targets")
    def intel_my_targets():
        _division, _g, label, u = _universe(request)
        import app.scout_intel as si
        tg = si.targets_for_my_program(
            div_filter=request.args.get("div", "All"),
            sort=request.args.get("sort", "fit"),
            impact=request.args.get("impact", "top3"),
            upgrades_only=request.args.get("upgrades") == "1")
        pg = paginate(tg["targets"], request.args.get("page", 1)) if tg else None
        return render_template("intel_my_targets.html", active="Analytics Bureau",
                               tg=tg, p=pg, u=u, uni_label=label,
                               divisions=["All", "D1", "D2", "D3", "D4"])

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
        from app.ncaa import dual_format, lineup_size
        return render_template("editor.html", active="Editor", u=u, uni_label=label,
                               school=school, schools=schools, rows=rows, head=head,
                               n_lineup=lineup_size(division),
                               n_doubles=dual_format(division).n_doubles,
                               doubles_pin=ov.get_doubles().get(school) or [],
                               conferences=conferences, conf=conf, conf_ratings=conf_ratings,
                               groups=all_programs_grouped(gender), ov=active_overrides(),
                               scholarships=schol, prestige=prestige, academics=academics,
                               staff=coaching_staff(division, gender, school),
                               move_tree=coach_move_tree(),
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

    @app.route("/editor/jhsaa-archetype", methods=["POST"])
    def editor_jhsaa_archetype():
        """Promote or demote a JHSAA program's archetype.

        Stored per SCHOOL NAME (a school's courts and coaching serve both its teams), so
        the owner can rewrite Jefferson's high-school pecking order as its history
        develops without touching generation code. `upstart` is deliberately absent: it
        is a temporary run the world rolls and expires by itself."""
        school = request.form.get("school", "")
        kind = request.form.get("archetype", "")
        if school:
            # "none" DEMOTES a seeded program (a stored override that says "not one of
            # these"); anything else clears the override entirely, reverting the school to
            # whatever `data/jhsaa/archetypes.json` says it is. Two different intentions,
            # and a single "clear" could only express one of them.
            if kind in ("blue_blood", "development", "doubles", "none"):
                ov.set_jhsaa_archetype(school, kind)
            else:
                ov.clear_jhsaa_archetype(school)
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

    def _apply_editor_moves(moves: list[tuple[str, str]]):
        """Commit editor moves — ALL of them under a single invalidation, because
        `reset_all()` + the move-version prime stamp make the next full-world page
        rebuild every roster; paying that once per player was the old per-row flow's
        friction. During the fall-portal hold the moves become portal ADDs instead
        (two-stint history + balancing cascade; they land at portal commit)."""
        w = wd.load_world()
        if w and sm.FALL_PORTAL_ENABLED and wd._all_in_fall_portal(DEFAULT_SEED, w):
            if not ov.get_proposals(w["year"]):
                wd.run_fall_portal()
            for pid, dest in moves:
                wd.add_fall_portal_mover(DEFAULT_SEED, pid, dest)
            return redirect(url_for("fall_portal"))
        for pid, dest in moves:
            ov.set_move(pid, dest)
        reset_all()                                    # ONCE for the whole batch
        return None

    @app.route("/editor/move", methods=["POST"])
    def editor_move():
        u = request.form.get("u", "D1-men")
        school = request.form.get("school", "")
        pid = request.form.get("pid", "")
        dest = request.form.get("dest", "")
        if pid and dest:
            resp = _apply_editor_moves([(pid, dest)])
            if resp:
                return resp
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/move_batch", methods=["POST"])
    def editor_move_batch():
        # One POST for the whole roster: every `dest_<pid>` field whose destination
        # differs from the current school becomes a move; unchanged rows are ignored.
        _division, gender, _label, u = _universe(request)
        school = request.form.get("school", "")
        moves = [(k[5:], v) for k, v in request.form.items()
                 if k.startswith("dest_") and v and v != school]
        # Guard: a player may only move to a program of their OWN gender. The MOVE
        # picker is already gender-filtered, but a hand-crafted POST could still name
        # a men's program for a women's player (or vice versa) — drop those silently.
        same_gender = {s for _lbl, slist in all_programs_grouped(gender) for s in slist}
        moves = [(pid, dest) for pid, dest in moves if dest in same_gender]
        if moves:
            resp = _apply_editor_moves(moves)
            if resp:
                return resp
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
                reset_lineup()
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
            reset_lineup()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/doubles", methods=["POST"])
    def editor_doubles():
        # Pin an INDEPENDENT doubles lineup: the division's doubles-line count
        # (D1 fields 5 pairs, the rest 3) as d{i}a/d{i}b pids. Players may be ANY
        # roster member, not just singles starters (doubles specialists).
        # Rejected unless all pids are distinct roster members.
        from app.ncaa import dual_format
        division, gender, label, u = _universe(request)
        school = request.form.get("school", "")
        n_d = dual_format(division).n_doubles
        slots = [x for i in range(1, n_d + 1) for x in (f"d{i}a", f"d{i}b")]
        pids = [request.form.get(s, "").strip() for s in slots]
        rows, _ = editor_roster(division, gender, school)
        valid = {r["pid"] for r in (rows or [])}
        if all(p in valid for p in pids) and len(set(pids)) == 2 * n_d:
            ov.set_doubles(school, pids)
            reset_lineup()
        return redirect(url_for("editor", u=u, school=school))

    @app.route("/editor/clear_doubles", methods=["POST"])
    def editor_clear_doubles():
        u = request.form.get("u", "D1-men")
        school = request.form.get("school", "")
        if school:
            ov.clear_doubles(school)
            reset_lineup()
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
        all_week = sm.week_duals(sid, cw) if s["phase"] == "regular" and cw <= tw else []
        # The week is ~500+ duals, so search it BY CONFERENCE: pick a league and see
        # every game its teams play that week (conference AND non-conference). Order
        # by the two teams' combined Power Index so the marquee matchups lead.
        conf_of = {p.school: p.conf_abbr for p in sm.load_division(division, gender).programs}
        week_confs = sorted({conf_of.get(d["home"]) for d in all_week}
                            | {conf_of.get(d["away"]) for d in all_week} - {None})
        conf_sel = request.args.get("conf", "All")
        pi = sm.power_index(sid)
        rank = {s: i + 1 for i, s in enumerate(sorted(pi, key=lambda s: pi[s].pi, reverse=True))} if pi else {}
        if pi:
            all_week.sort(key=lambda d: (pi[d["home"]].pi if d["home"] in pi else 0)
                          + (pi[d["away"]].pi if d["away"] in pi else 0), reverse=True)
        for d in all_week:
            d["home_rank"], d["away_rank"] = rank.get(d["home"]), rank.get(d["away"])
            d["home_conf"], d["away_conf"] = conf_of.get(d["home"]), conf_of.get(d["away"])
        if conf_sel != "All":
            upcoming = [d for d in all_week
                        if conf_sel in (conf_of.get(d["home"]), conf_of.get(d["away"]))]
        else:
            upcoming = all_week[:16]
        last = sm.recent_duals(sid)
        champions = {}
        if s["phase"] in ("ncaa", "complete") and s["champion"]:
            try:
                champions = __import__("json").loads(s["champion"]) if s["phase"] == "ncaa" else {}
            except Exception:
                champions = {}
        return render_template("season.html", active="Season", s=s, u=u, uni_label=label,
                               upcoming=upcoming, n_week=len(all_week), week_confs=week_confs,
                               conf_sel=conf_sel, last=last, top=sm.national_top(sid, 15), crest=crest,
                               bubble=sm.bubble_watch(sid), ita_champ=sm.indoor_champion(sid))

    # NOTE: there is deliberately NO /season/advance. The Season Hub used to carry
    # its own advance button, which stepped only the universe the page was showing
    # and left the world clock (and every other universe) behind — see
    # docs/AAR-universe-desync-season-hub-advance.md. `world_advance` is the single
    # advance route; the hub's header button is the single advance control.

    @app.route("/season/standings")
    def season_standings():
        division, gender, label, u = _universe(request)
        sid = sm.get_or_create(division, gender, seed=wd.current_year_seed())
        standings = sm.standings(sid)
        conferences = sorted(standings)
        conf = request.args.get("conf")
        if conf not in standings:
            conf = conferences[0] if conferences else ""
        from .state import attach_power6
        table = attach_power6(division, gender, standings.get(conf, []))
        return render_template("season_standings.html", active="Season", u=u, uni_label=label,
                               conferences=conferences, conf=conf, crest=crest, table=table)

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
        # Panel captions from the dual AS RECORDED (line counts), so historical
        # 6+3 box scores in a converted save stay labeled correctly; the scoring
        # rule comes from the division's format when the shape matches it, else
        # the classic consolidated rule the old duals were played under.
        from app.ncaa import dual_format
        from engine import CLASSIC
        n_s = sum(1 for ln in d["lines"] if (ln.get("slot") or "").startswith("S"))
        n_d = sum(1 for ln in d["lines"] if (ln.get("slot") or "").startswith("D"))
        f = dual_format(division)
        fmt = f if (n_s, n_d) == (f.n_singles, f.n_doubles) else CLASSIC
        dbl_label = (f"win {fmt.n_doubles // 2 + 1} of {fmt.n_doubles} → 1 team point"
                     if fmt.doubles_team_point else f"{n_d} pairs · 1 team point each")
        sgl_label = f"{n_s} courts · 1 team point each · clinch at {fmt.clinch}"
        return render_template("season_dual.html", active="Season", u=u, uni_label=label,
                               d=d, crest=crest, dbl_label=dbl_label, sgl_label=sgl_label)

    return app


def main():
    port = int(os.environ.get("PORT", "5000"))
    create_app().run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()

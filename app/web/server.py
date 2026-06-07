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
from flask import Flask, render_template, request

from .rankings_data import all_schools, crest, get_row
from .sim import run_dual_view, FIDELITIES
from .state import ranking_rows, conferences_for, get_bracket, UNIVERSES, FIELD_PRESETS

# label → route; drives the green TopNav across every page.
NAV = [
    ("Rankings", "/"),
    ("Dual Simulator", "/dual"),
    ("Bracket", "/bracket"),
    ("Teams", "/teams"),
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

    @app.route("/methodology")
    def methodology():
        return render_template("methodology.html", active="Methodology")

    @app.route("/dual")
    def dual():
        schools = all_schools()
        home = request.args.get("home", "Oregon")
        away = request.args.get("away", "Stanford")
        return render_template(
            "dual_setup.html", active="Dual Simulator", schools=schools,
            home=home, away=away, crest=crest, get_row=get_row,
            fidelities=FIDELITIES,
        )

    @app.route("/dual/run")
    def dual_run():
        schools = all_schools()
        home = request.args.get("home", "Oregon")
        away = request.args.get("away", "Stanford")
        if home == away:
            away = next(s for s in schools if s != home)
        try:
            seed = int(request.args.get("seed", "7"))
        except ValueError:
            seed = 7
        fidelity = request.args.get("fidelity", "full")
        if fidelity not in FIDELITIES:
            fidelity = "full"
        view = run_dual_view(home, away, seed=seed, fidelity=fidelity)
        return render_template("dual_result.html", active="Dual Simulator", v=view,
                               home=home, away=away)

    @app.route("/teams")
    def teams():
        return render_template("placeholder.html", active="Teams",
                               title="Teams", phase="P8 · team pages",
                               blurb="Roster ladder (singles 1–6, doubles pairings) and dual results, "
                                     "with each player's modified-UTR and reliability.")

    @app.route("/schedule")
    def schedule():
        return render_template("placeholder.html", active="Schedule",
                               title="Schedule", phase="P4 · leagues & seasons",
                               blurb="Season schedules and standings across the six concurrent "
                                     "divisions (D1/D2/D3 × men's/women's).")

    return app


def main():
    port = int(os.environ.get("PORT", "5000"))
    create_app().run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()

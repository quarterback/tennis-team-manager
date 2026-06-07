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

from .rankings_data import get_rankings, CONFERENCES, TIERS, all_schools, crest, get_row
from .sim import run_dual_view, FIDELITIES

# label → route; drives the green TopNav across every page.
NAV = [
    ("Rankings", "/"),
    ("Dual Simulator", "/dual"),
    ("Teams", "/teams"),
    ("Schedule", "/schedule"),
    ("Methodology", "/methodology"),
]


def create_app() -> Flask:
    app = Flask(__name__)

    @app.context_processor
    def _inject_nav():
        return {"nav": NAV}

    @app.route("/")
    def rankings():
        conf = request.args.get("conf", "All")
        tier = request.args.get("tier", "All")
        sort = request.args.get("sort", "Rank")
        rows = get_rankings(conf=conf, tier=tier, sort=sort)
        return render_template(
            "rankings.html", active="Rankings", rows=rows,
            conferences=CONFERENCES, tiers=TIERS, conf=conf, tier=tier, sort=sort,
        )

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

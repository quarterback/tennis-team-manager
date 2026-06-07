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

from .rankings_data import get_rankings, CONFERENCES, TIERS

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
        return render_template("placeholder.html", active="Dual Simulator",
                               title="Dual Simulator", phase="P2 · dual-match team layer",
                               blurb="Pick two programs, set the format, and run the doubles point "
                                     "plus six singles to a clinch. The engine is built "
                                     "(engine/dual.py); this screen wires it to the web.")

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

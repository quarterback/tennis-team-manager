"""Render the static site from ingested bundles + computed aggregates."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import ability as ability_mod
from . import aggregate, classes as classes_mod, market as market_mod
from . import metrics as metrics_mod, prose

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


def _json_for_script(obj) -> str:
    """Serialise a payload for embedding in a <script> element.

    ‼️ It must NOT be HTML-escaped and it must NOT be emitted raw either.
    Script content is raw text, so Jinja's autoescape turns `"` into `&#34;`
    and the browser does NOT decode it back — `JSON.parse` throws on a page
    that looks perfectly fine in the source. Emitting it unescaped instead
    lets a `</script>` inside a school or player name close the element early.
    Escaping the three characters that can start markup as \\u sequences is
    still valid JSON and is safe in both directions.
    """
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _round(v, places):
    """Round for the packed scouting payload. None stays None — the grid
    renders it as an em-dash, which is a different statement from 0."""
    return None if v is None else round(v, places)


def _r1(v):
    return _round(v, 1)


def _r2(v):
    return _round(v, 2)


def _r3(v):
    return _round(v, 3)


def _team_stat_row(pid: str, scope_id: str, m, b, abil=None, mv=None) -> dict:
    """One Stat Center row: identity + every team metric, formatted for the
    grid (None -> None, rendered as em-dash by the template).

    `abil` is this team's ability row and `mv` its movement row — the two
    column groups the grid gained: **Talent** (what the roster's OVR says
    should have happened, against what did) and **Movement** (who came and
    went). Both are None-safe: a scope with no OVR on file, or the newest
    season with no following one to read departures from, renders em-dashes
    rather than zeroes."""
    prog = b.programs.get(pid, {})
    q = m.quartile_record
    lg = m.league_record
    abil = abil or {}
    mv = mv or {}

    def rec(d):
        return f"{d.get('w', 0)}-{d.get('l', 0)}" if d else "—"

    return {
        # talent: expected flight share from the OVR gaps every flight was
        # actually contested at, vs the share the team took. This is Record
        # Luck computed against the engine's own input instead of against
        # TOSS — the one question a results-only library cannot ask.
        "x_share": abil.get("x_share"), "talent_luck": abil.get("luck"),
        "avg_gap": abil.get("avg_gap"),
        "in": mv.get("in"), "out": mv.get("out"), "net": mv.get("net"),
        "arrival_share": mv.get("arrival_win_share"),
        "dev_arrivals": mv.get("dev_arrivals"), "dev_stayers": mv.get("dev_stayers"),
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
    (SITE / "scout").mkdir(parents=True, exist_ok=True)
    (SITE / "classes").mkdir(parents=True, exist_ok=True)
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

    # The ability layer: OVR joined onto every flight, and the win curve
    # fitted on the gaps those flights were played at. Built before anything
    # that reads it, and pooled across every ingested season because the curve
    # is a property of the engine rather than of a season.
    ability = ability_mod.build(bundles)
    move = market_mod.movement(bundles)
    growth = market_mod.fit_growth(bundles, ability)
    scout_rows = market_mod.player_rows(bundles, careers, boards, ability, move, growth)
    team_move = market_mod.team_movement(bundles, scout_rows, move, ability)
    class_reports = classes_mod.build(bundles, boards, ability)

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
        # Roster rows carry the ability layer too: a ladder position and an
        # OVR turn the roster panel from a list of names into the depth chart
        # every market decision is actually read off.
        sa = ability.ability(scope_id)
        for r in roster:
            r["ovr"] = sa.ovr.get(r["player_id"]) if sa else None
            r["pot"] = sa.pot.get(r["player_id"]) if sa else None
            r["ladder_rank"] = sa.rank_of(r["player_id"]) if sa else None
        roster.sort(key=lambda r: (r["ladder_rank"] is None, r["ladder_rank"] or 0))
        w("team.html", SITE / "teams" / fname, rel="../", team=t,
          blurb=prose.team_blurb(t), color=crest_color(name), initials=initials(name),
          classification=classification, league=league, own_href=fname, bracket_href=bracket_href,
          standing=standing_row, sections=aggregate.schedule_sections(t["schedule"]),
          roster=roster, m=team_metrics.get((pid, scope_id)),
          abil=ability.team.get((scope_id, pid)), mv=team_move.get((scope_id, pid)),
          dressed=sa.dressed if sa else None,
          scout_href=f"../scout/{aggregate.slug(scope_id)}.html")

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
        stat_rows.append(_team_stat_row(pid, scope_id, m, b,
                                        ability.team.get((scope_id, pid)),
                                        team_move.get((scope_id, pid))))
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

    # Career value board: PVAR (results vs a slot's replacement level) beside
    # WAE (results vs what the OVR gaps priced). They disagree on purpose and
    # the disagreement is the point — PVAR asks "was this seat filled better
    # than the next player would have", WAE asks "did they beat the matches
    # they were actually given". A player can lead one and not the other.
    career_wae: dict[str, dict] = {}
    for (scope_id, pid), row in ability.player.items():
        acc = career_wae.setdefault(pid, {"wae": 0.0, "priced": 0, "matches": 0, "known": True})
        acc["matches"] += row["matches"]
        if row.get("wae") is None:
            acc["known"] = False
        else:
            acc["wae"] += row["wae"]
            acc["priced"] += row["matches"]

    value_rows = []
    for pid, pv in player_value.items():
        c = careers[pid]
        glabel, gsort = aggregate.grade_label(c["bio"])
        cw = career_wae.get(pid)
        value_rows.append({"player_id": pid, "name": c["name"], "teams": sorted(c["teams"]),
                            "wins": c["wins"], "losses": c["losses"], "pvar": pv["total"],
                            "wae": cw["wae"] if cw and cw["known"] else None,
                            "grade": glabel, "grade_sort": gsort})
    value_rows.sort(key=lambda r: -r["pvar"])
    w("metrics_value.html", SITE / "metrics" / "value.html", rel="../",
      rows=value_rows[:100], curves=sorted(ability.curves.values(),
                                           key=lambda cv: (cv.family, cv.kind)))

    # ---- Scouting: search the association by AREA, not only by class ----
    # The organizing hierarchy on every OTHER page is classification ->
    # district, and that is right for a competition. It is the wrong index for
    # a market: a cohort build is "the best players within one county", and a
    # class-first tree makes that query unaskable — you would walk nine class
    # pages and re-filter each one. So this surface carries BOTH cascades side
    # by side (area -> county -> town, and class -> district) over one list,
    # and narrows on whichever the question uses. It still never opens on the
    # whole state: nothing renders until at least one axis is set.
    # ‼️ Snapshot scopes only, and the ones left out are NAMED on the index.
    # A scouting page for a non-snapshot export would price players at OVRs
    # they did not play at — and its batch would be rejected anyway, since
    # /editor/jhsaa-transfer-batch resolves ids through JHSAA rosters alone.
    scout_scopes = []
    skipped_scopes = [{"label": b.label,
                       "why": "players.csv reflects the current roster, not the one that played"}
                      for b in bundles if not b.roster_is_snapshot]
    for b in aggregate.snapshot_bundles(bundles):
        rows = scout_rows.get(b.scope_id, [])
        if not rows:
            continue
        sa = ability.ability(b.scope_id)
        board = boards.get(b.scope_id, {}).get("by_program", {})
        prog_index, prog_pos = [], {}
        for program_id, prog in sorted(b.programs.items(),
                                       key=lambda kv: kv[1].get("name") or kv[0]):
            standing = board.get(program_id, {})
            ladder = [round(sa.ovr[p], 1) for p in (sa.ladder.get(program_id) or [])
                      if p in sa.ovr] if sa else []
            prog_pos[program_id] = len(prog_index)
            prog_index.append([
                prog.get("name") or program_id, aggregate.program_class(prog),
                aggregate.program_league(prog), prog.get("city") or "",
                prog.get("county") or "", prog.get("area") or "",
                standing.get("class_rank"), standing.get("class_size"),
                standing.get("wins"), standing.get("losses"), ladder,
            ])

        packed = []
        for r in rows:
            packed.append([
                r["player_id"], r["name"], prog_pos.get(r["program_id"], -1),
                r["grade_sort"], _r1(r["ovr"]), _r1(r["pot"]), r["ladder_rank"],
                r["matches"], r["w"], r["l"], r["top_flight"],
                _r3(r["lift"]), _r2(r["wae"]), r["starts_in"],
                _r2(r["dev_vs_expected"]), r["moved_from"], _r1(r["vs_starter"]),
            ])

        # Every qualifying player, not a per-class top slice: the grid's own
        # display cap is the only limit, and it announces itself on screen.
        finders_out = {}
        for key, _label, fn, _blurb, (sort_key, sort_dir) in market_mod.FINDERS:
            hits = fn(rows)
            finders_out[key] = {"ids": [r["player_id"] for r in hits],
                                "sort": sort_key, "dir": sort_dir}
        scout_scopes.append({
            "scope_id": b.scope_id, "label": b.label,
            "href": f"{aggregate.slug(b.scope_id)}.html",
            "players": len(rows),
            "payload": {
                "scope": b.scope_id, "label": b.label,
                "dressed": sa.dressed if sa else None,
                "programs": prog_index, "players": packed,
                "areas": sorted({p[5] for p in prog_index if p[5]}),
                "counties": sorted({p[4] for p in prog_index if p[4]}),
                "classes": sorted({p[1] for p in prog_index if p[1] and p[1] != "—"},
                                  key=aggregate.classification_sort_key),
                "finders": finders_out,
                "catchment": market_mod.catchments(rows),
                "lines": {k: round(v, 1) for k, v in
                          market_mod.starting_lines(rows, sa.dressed if sa else None).items()},
            },
        })

    w("scout_index.html", SITE / "scout" / "index.html", rel="../", scopes=scout_scopes,
      skipped=skipped_scopes)
    for s in scout_scopes:
        w("scout.html", SITE / "scout" / s["href"], rel="../", scope=s,
          payload=_json_for_script(s["payload"]),
          finders=[{"key": k, "label": lb, "blurb": bl,
                    "found": len(s["payload"]["finders"][k]["ids"])}
                   for k, lb, _fn, bl, _sort in market_mod.FINDERS])

    # ---- Classification report ----
    w("classes_index.html", SITE / "classes" / "index.html", rel="../", reports=class_reports,
      skipped=skipped_scopes)
    for rep in class_reports:
        w("classes.html", SITE / "classes" / f"{rep['scope_id']}.html", rel="../", rep=rep)

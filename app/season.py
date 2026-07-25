"""
Season simulation for one division × gender universe.

Flow (P4/P5):
  1. Build a schedule — conference round-robin + a few non-conference duals
     (the non-conf links give RPI/APR a real strength-of-schedule graph).
  2. Simulate every dual (fast model) → dual records.
  3. Conference standings from conference duals.
  4. Compute the Power Index (APR + FQI + oGS) over the regular season.
  5. Conference tournaments (seeded by conf record, tiebreak PI) → champions
     = automatic NCAA bids.

The result feeds the rankings page and the NCAA bracket (app/bracket.py).
Seed-deterministic: same (division, gender, seed) ⇒ same season.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field

from engine import simulate_dual, Team
from .ncaa import Program, Division, load_division, build_squad, build_roster, squad_and_ladder
from .rating import compute_ratings, RatingLine
from .str_rating import converge_ids
from .bracket import play_dual, _seed_positions

NONCONF_PER_TEAM = 3
NATIONAL_FIELD = 64

# Persist per-player box stats (aces / DFs / winners / UEs / serve+return points /
# break points) on every completed line of a SEASON-MODE dual. Outcomes still come
# from the tuned fast model; stats are an engine.boxstats conditioned replay, so
# scorelines are unchanged (see docs/AAR-box-stat-persistence.md). Costs ~10ms per
# dual. This constant is the code default; the per-save UI switch on the world hub
# (worldconfig.box_stats_enabled) overrides it at sim time.
BOX_STATS = True

# Dual-match fidelity for season-mode sims. "full" (default) resolves every POINT
# through the rich attribute engine (engine.match): real serve/return/rally talent
# decides the outcome AND yields native box stats from one sim. It is also faster
# than "fast"+box-stats (which rejection-samples to reconstruct stats). "fast" is
# the legacy game-level Bernoulli model (outcome from an `overall` gap only), kept
# as an opt-in speed mode. The authority is the per-save switch on the world hub
# (worldconfig.match_fidelity); env var TTM_FIDELITY=fast forces the legacy model.
BOX_STATS_FALLBACK_FIDELITY = "full"


def _fidelity() -> str:
    """The per-save match fidelity ("full"/"fast"), read at sim time so flipping
    the world-hub switch takes effect from the next dual on."""
    try:
        from app import worldconfig
        f = worldconfig.match_fidelity()
        return f if f in ("fast", "full") else BOX_STATS_FALLBACK_FIDELITY
    except Exception:
        import os
        return "fast" if os.environ.get("TTM_FIDELITY", "").strip().lower() == "fast" else BOX_STATS_FALLBACK_FIDELITY


def _box_stats_on() -> bool:
    """The per-save box-stats switch, defaulting to BOX_STATS. Wrapped
    defensively (same as _coached_pin) so a config/DB hiccup degrades to the
    code default, never an error."""
    try:
        from app import worldconfig
        return worldconfig.box_stats_enabled() and BOX_STATS
    except Exception:
        return BOX_STATS


@dataclass
class SeasonResult:
    division: str
    gender: str
    seed: int
    programs: list[Program]
    ratings: dict[str, RatingLine]
    standings: dict[str, list[tuple]]          # conf -> [(Program, w, l), ...]
    champions: list[Program]
    duals: list[dict]
    rosters: dict = field(default_factory=dict)        # school -> list[Prospect] (full roster)
    player_str: dict = field(default_factory=dict)     # pid -> (STR, reliability)
    player_record: dict = field(default_factory=dict)  # pid -> (singles wins, losses)

    def ranked(self) -> list[Program]:
        return sorted(self.programs, key=lambda p: self.ratings[p.school].pi, reverse=True)


# Coach lineup model -----------------------------------------------------------
# Players on a roster are close in ability, so RESULTS (live STR) drive the
# ladder, with a stable per-season noise term standing in for coach preference.
# Against clearly weaker opponents coaches rest a starter or two and give the
# bench / walk-ons match reps — so everyone on the roster gets evaluated rather
# than the bottom of the bench never seeing the court.
LINEUP_NOISE = 1.4
# Doubles pairing permutations (index pairs into the chosen six); the coach picks
# one per season, so pairings persist but vary program to program / year to year.
DOUBLES_PERMS = [
    [(0, 1), (2, 3), (4, 5)], [(0, 2), (1, 3), (4, 5)],
    [(0, 1), (2, 4), (3, 5)], [(0, 3), (1, 2), (4, 5)],
    [(0, 2), (1, 4), (3, 5)],
]


def _form_str(form, p) -> float | None:
    if not form:
        return None
    v = form.get(p.pid)
    if v is None:
        return None
    return v[0] if isinstance(v, tuple) else v


BASELINE_REP_CHANCE = 0.35      # chance a coach gives the bench a look even vs a peer


def coach_lineup(prog: Program, roster: list, form: dict | None,
                 opp_prestige: float, lineup_seed: int, dual_seed: int = 0,
                 forced: set | None = None, unavailable: set | None = None,
                 pinned: list | None = None, doubles_pin: list | None = None,
                 best_six: bool = False):
    """Return (engine Team, chosen Prospects) for `prog` this dual.

    The ladder is set by live results STR (ability before results exist) plus a
    season-stable coach-preference noise, so the persistent order is dictated by
    results with a little coach discretion. Bench/walk-ons get reps two ways:
    the coach rests starters against weaker opponents, and there's a baseline
    chance of a look even against a peer — and *which* bench players come in
    rotates per dual, so over a season everyone on the roster gets evaluated.
    `chosen[i]` is exactly Team.singles[i] so line identity stays unambiguous.

    `forced` is a set of pids that MUST appear this dual (the season's
    playing-time guarantee — see `forced_appearances`). A forced player is slotted
    around S3, which always completes before a 4-point clinch, so the appearance
    actually counts; it also reflects bench players playing *up* against weaker
    opponents.

    `unavailable` is a set of pids that are INJURED this dual — dropped from
    contention entirely, so an injured starter pulls up the next body and the
    coach is forced to use depth. A guaranteed (`forced`) player who's hurt is
    dropped too (you can't play the injured).

    Short-handed safety: the engine fields six singles + three doubles, so the
    lineup MUST be six. If filtering the injured (or a thin roster) would leave
    fewer than six healthy bodies, the least-compromised injured players are
    pressed back into service (best STR first) — a banged-up team plays hurt
    rather than forfeit. Only a roster with fewer than six players total can't
    reach six; that's clamped below so the engine never indexes past the end."""
    if unavailable:
        healthy = [p for p in roster if p.pid not in unavailable]
        if len(healthy) < 6 and len(roster) > len(healthy):
            benched = sorted((p for p in roster if p.pid in unavailable),
                             key=lambda p: p.str_value(), reverse=True)
            healthy = healthy + benched[:6 - len(healthy)]
        roster = healthy
        if forced:
            live = {p.pid for p in roster}
            forced = {pid for pid in forced if pid in live}
    srng = random.Random(f"{prog.key}|lineup|{lineup_seed}")    # season-stable ladder

    def score(p):
        base = _form_str(form, p)
        if base is None:
            base = p.str_value()
        # Elimination lineups (`best_six`) are STRICTLY form/record/level — the
        # results-based STR, ability as the fallback — no coach-discretion noise.
        return base if best_six else base + srng.gauss(0, LINEUP_NOISE)

    scores = {p.pid: score(p) for p in roster}                  # one draw per player, in order
    if pinned:
        # The human coach hand-set this team's order (career mode, coached team
        # ONLY — see dual_between._coached_pin). Pinned, available players lead in
        # the coach's order; everyone else falls in behind by ladder score. No
        # auto-rotation — the coach decides who plays. Injured pids were already
        # dropped above, so a hurt pin pulls up the next body; the playing-time
        # guarantee (`forced`) below still applies. With no pin this branch never
        # runs, so a coach who leaves the lineup alone is treated exactly like the
        # AI and is never disadvantaged.
        rank = {pid: i for i, pid in enumerate(pinned)}
        order = sorted(roster, key=lambda p: (rank.get(p.pid, len(pinned)), -scores[p.pid]))
        chosen = order[:6]
    else:
        order = sorted(roster, key=lambda p: scores[p.pid], reverse=True)
        starters, bench = order[:6], order[6:]
        drng = random.Random(f"{prog.key}|rot|{dual_seed}")     # per-dual rotation
        gap = getattr(prog, "prestige", 0.5) - opp_prestige
        # `best_six` = the conference tournament / NCAA bracket: no coach rests
        # starters or hands out bench reps when losing ends the season — the
        # healthy top six by form always take the court. Rotation is a REGULAR-
        # season device (bench evaluation + playing time vs weaker opponents), and
        # the ITA events deliberately KEEP it (their point is that everyone plays).
        if best_six:
            rotate = 0
        else:
            rotate = 2 if gap > 0.18 else 1 if gap > 0.05 else 0
            if rotate == 0 and drng.random() < BASELINE_REP_CHANCE:
                rotate = 1
        rotate = min(rotate, len(bench))
        if rotate:
            picks = drng.sample(bench, rotate)                  # varied bench each time
            chosen = starters[:6 - rotate] + picks
        else:
            chosen = list(starters)

    if forced:                                                  # guarantee these pids play
        by_pid = {p.pid: p for p in roster}
        # S1-S3 always complete before a 4-point clinch, so a guaranteed player
        # only needs a top-3 slot — and only if they aren't already there (an ace
        # forced into "their" dual stays at S1; a benched player is seated ~S3,
        # i.e. playing up). Each dual carries at most a couple of forced pids.
        for fp_pid in sorted(forced):
            if fp_pid not in by_pid:
                continue
            cur = next((i for i, p in enumerate(chosen) if p.pid == fp_pid), None)
            if cur is not None and cur < 3:
                continue                                        # already a completing slot
            comp = [i for i in (2, 1, 0) if i < len(chosen) and chosen[i].pid not in forced]
            if cur is not None:                                 # in lineup but too low — swap up
                tgt = comp[0] if comp else cur
                chosen[cur], chosen[tgt] = chosen[tgt], chosen[cur]
            else:                                               # off the lineup — bring in
                droppable = [p for p in chosen if p.pid not in forced]
                if not droppable:
                    continue
                drop = min(droppable, key=lambda p: scores[p.pid])
                di = chosen.index(drop)
                chosen[di] = by_pid[fp_pid]
                tgt = comp[0] if comp else di
                chosen[di], chosen[tgt] = chosen[tgt], chosen[di]

    # Final safety: the engine indexes six singles and three doubles pairs. If a
    # roster is so depleted it can't seat six distinct players, repeat the last
    # available body into the empty courts so the dual still resolves (a degenerate
    # forfeit-like lineup) instead of raising IndexError mid-season.
    if len(chosen) < 6 and chosen:
        chosen = chosen + [chosen[-1]] * (6 - len(chosen))

    # Doubles is its OWN lineup. By default it's the classic auto-permutation of the
    # singles six. If the coach pinned a doubles lineup (career mode, coached team),
    # honor it — INDEPENDENT of singles, so a doubles specialist who isn't a singles
    # starter can play (real college tennis: a "1 doubles / 5 singles" player). The
    # pin is 6 pids → pairs [(0,1),(2,3),(4,5)]; it's used only if all six are on the
    # available (healthy) roster, otherwise we fall back to the auto pairing.
    dbl_players = None
    chosen_dbl = chosen
    if doubles_pin:
        avail = {p.pid: p for p in roster}
        picks = [avail[pid] for pid in doubles_pin if pid in avail]
        if len(picks) >= 6:
            chosen_dbl = picks[:6]
            dbl_players = [p.engine_player() for p in chosen_dbl]
    if dbl_players is not None:
        doubles = [(0, 1), (2, 3), (4, 5)]
    else:
        doubles = [tuple(x) for x in srng.choice(DOUBLES_PERMS)]
    team = Team(name=prog.school, singles=[p.engine_player() for p in chosen],
                doubles=doubles, doubles_players=dbl_players)
    return team, chosen, chosen_dbl


def forced_appearances(prog: Program, roster: list,
                       nonconf_duals: list[tuple]) -> dict:
    """Deterministic map ``dual_key -> {pid}`` giving EVERY roster player one
    non-conference dual where they're guaranteed to appear. The weakest players
    get the most favorable duals (weakest opponent), so the bench plays *up*
    against lower-prestige competition. Players who'd start anyway are no-ops at
    lineup time; only the genuinely-benched get seated into a completing slot —
    keeping ~most teams on a standard six most weeks. (We can't pick the "bench"
    by ability up front because the live-form ladder drifts during the season, so
    we cover everyone, spread evenly across the team's non-conf duals.)

    `nonconf_duals` is ``[(dual_key, opp_prestige), ...]``. Pure function of roster
    ability + schedule, so it's stable across re-sims."""
    if not nonconf_duals:
        return {}
    players = sorted(roster, key=lambda p: p.str_value())      # weakest first
    favorable = sorted(nonconf_duals, key=lambda t: t[1])      # weakest opponent first
    out: dict = {}
    for i, p in enumerate(players):
        key = favorable[i % len(favorable)][0]                 # weakest -> most favorable
        out.setdefault(key, set()).add(p.pid)
    return out


def _line_identity(slot: str, la: list, lb: list,
                   ha_dbl: list, aw_dbl: list,
                   la_d: list | None = None, lb_d: list | None = None) -> dict:
    """Who played a line, both sides, so box scores can show position↔player.
    Singles carry stable pids (STR/record are singles-based); doubles use the actual
    pairing, indexing each side's DOUBLES roster (`la_d`/`lb_d`) — which may differ
    from the singles six when a coach pins an independent doubles lineup. Falls back
    to the singles list when no separate doubles roster is supplied."""
    la_d = la if la_d is None else la_d
    lb_d = lb if lb_d is None else lb_d
    out: dict = {}
    if slot.startswith("S"):
        i = int(slot[1:]) - 1
        if 0 <= i < len(la) and i < len(lb):
            hp, ap = la[i], lb[i]
            out.update(home_pid=hp.pid, away_pid=ap.pid,
                       home_player=hp.name, away_player=ap.name,
                       home_country=hp.country, away_country=ap.country)
    else:                                        # doubles — a pair per side
        i = int(slot[1:]) - 1
        if 0 <= i < len(ha_dbl) and i < len(aw_dbl):
            hp = [la_d[x] for x in ha_dbl[i] if x < len(la_d)]
            ap = [lb_d[x] for x in aw_dbl[i] if x < len(lb_d)]
            if hp and ap:
                out.update(home_player=" / ".join(p.name.split()[-1] for p in hp),
                           away_player=" / ".join(p.name.split()[-1] for p in ap),
                           home_pids=[p.pid for p in hp], away_pids=[p.pid for p in ap])
    return out


def _line_stats(ln) -> dict | None:
    """Per-player box stats for a completed line, JSON-ready (compact keys per
    engine.state.STAT_KEYS). Singles: one stat dict per side. Doubles: a list of
    two per side, ordered exactly like `home_pids`/`away_pids`. None when the
    result carries no stats (overlay off / legacy)."""
    stats = getattr(ln.result, "stats", None)
    if not stats or not stats[0].has_data:
        return None
    if len(stats) == 2:                      # singles
        return {"home": stats[0].to_dict(), "away": stats[1].to_dict()}
    return {"home": [stats[0].to_dict(), stats[1].to_dict()],
            "away": [stats[2].to_dict(), stats[3].to_dict()]}


def _dual_record(a: Program, b: Program, sa: Team, sb: Team,
                 la: list, lb: list, *, seed: int, conf: bool,
                 forced_home: set | None = None, forced_away: set | None = None,
                 la_d: list | None = None, lb_d: list | None = None,
                 box_stats: bool = False, play_all: bool = False) -> dict:
    """Simulate a dual between prebuilt squads `sa`/`sb`. `la`/`lb` are the
    Prospects who played (la[i] ↔ sa.singles[i]) so every line carries the
    identity of who played that position (singles pids + names; doubles names
    from the actual pairing). `box_stats=True` additionally records per-player
    box stats on every completed line (see engine.boxstats)."""
    # A court with a guaranteed-appearance player on either side finishes early so
    # that line completes (and lands in the corpus) regardless of how long it ran.
    forced = (forced_home or set()) | (forced_away or set())
    priority = {i for i in range(len(la))
                if (i < len(lb)) and (la[i].pid in forced or lb[i].pid in forced)} or None
    res = simulate_dual(sa, sb, seed=seed, fidelity=_fidelity(), priority_finish=priority,
                        box_stats=box_stats, play_all=play_all)
    lines = []
    for ln in res.lines:
        if not ln.completed:
            # Abandoned mid-match: keep the score it had reached so the box score
            # shows where it stood, not a blank "did not play".
            rec = {"slot": ln.slot, "completed": False,
                   "sets": [[h, a] for (h, a) in (ln.partial or [])]}
            rec.update(_line_identity(ln.slot, la, lb, sa.doubles, sb.doubles, la_d, lb_d))
            lines.append(rec)
            continue
        gw = ln.result.games_won
        rec = {"slot": ln.slot, "completed": True, "home_won": ln.home_won,
               "home_games": gw[0], "away_games": gw[1], "finish": ln.finish,
               "sets": [[h, a] for (h, a) in ln.result.set_scores]}
        rec.update(_line_identity(ln.slot, la, lb, sa.doubles, sb.doubles, la_d, lb_d))
        # Honor the box-stats toggle: the full engine always computes native stats,
        # but with the switch OFF we keep history scoreline-only (don't serialize).
        if box_stats:
            st = _line_stats(ln)
            if st:
                rec["stats"] = st
        lines.append(rec)
    return {
        "home": a.school, "away": b.school, "conf": conf,
        "home_won": res.winner == 0,
        "home_points": res.home_points, "away_points": res.away_points,
        "lines": lines,
    }


def _coached_pin(prog) -> list | None:
    """The hand-set lineup order for `prog`, but ONLY when it is the human-coached
    program (career mode). Every other program — and a coached program whose coach
    never set a lineup — returns None and plays the normal auto ladder, so opting
    out, spectating, or simply not touching the lineup never disadvantages a team.

    Cheap for the ~all non-coached teams: a cached identity check (worldconfig's
    in-process cache), no DB read. Only the coached team's own duals hit get_lineups().
    Wrapped defensively so a config/DB hiccup degrades to auto, never an error."""
    try:
        from app import worldconfig, overrides as ov
        cp = worldconfig.user_program()
        if not cp or cp["school"] != prog.school or cp["gender"] != prog.gender \
                or cp["division"] != prog.division:
            return None
        return ov.get_lineups().get(prog.school) or None
    except Exception:
        return None


def _coached_doubles(prog) -> list | None:
    """The hand-set doubles lineup (6 pids → 3 pairs) for `prog`, but ONLY when it is
    the human-coached program — same guard as `_coached_pin`. None everywhere else, so
    every other team auto-pairs its doubles exactly as before."""
    try:
        from app import worldconfig, overrides as ov
        cp = worldconfig.user_program()
        if not cp or cp["school"] != prog.school or cp["gender"] != prog.gender \
                or cp["division"] != prog.division:
            return None
        return ov.get_doubles().get(prog.school) or None
    except Exception:
        return None


def dual_between(a: Program, b: Program, *, seed: int, conf: bool,
                 form: dict | None = None, lineup_seed: int = 0,
                 forced_home: set | None = None, forced_away: set | None = None,
                 unavailable_home: set | None = None,
                 unavailable_away: set | None = None,
                 best_six: bool = False) -> dict:
    """Simulate one dual between two programs and return the record dict. Each
    coach sets a lineup from their full roster (results-driven ladder + coach
    noise, rotating bench/walk-ons in against weaker opponents), so the bottom of
    the roster actually gets evaluated. `forced_home`/`forced_away` are pids the
    season's playing-time guarantee requires in this dual. `unavailable_*` are
    injured pids dropped from each lineup. Used by season mode.

    The record carries `home_played`/`away_played` (pids who competed) so the
    caller can roll fresh injuries on exactly the players who took the court."""
    sa, la, la_d = coach_lineup(a, build_roster(a), form, getattr(b, "prestige", 0.5),
                                lineup_seed, seed, forced=forced_home,
                                unavailable=unavailable_home, pinned=_coached_pin(a),
                                doubles_pin=_coached_doubles(a), best_six=best_six)
    sb, lb, lb_d = coach_lineup(b, build_roster(b), form, getattr(a, "prestige", 0.5),
                                lineup_seed, seed, forced=forced_away,
                                unavailable=unavailable_away, pinned=_coached_pin(b),
                                doubles_pin=_coached_doubles(b), best_six=best_six)
    # ITA Division III "play-play": D3/D4 regular-season & ITA duals play every
    # match to completion (fuller player stats for portal/move-up decisions).
    # Postseason (CT/NCAA — the best_six duals) keeps clinch-play, as does D1/D2.
    play_all = (a.division in ("D3", "D4") and b.division in ("D3", "D4")
                and not best_six)
    rec = _dual_record(a, b, sa, sb, la, lb, seed=seed, conf=conf,
                       forced_home=forced_home, forced_away=forced_away,
                       la_d=la_d, lb_d=lb_d, box_stats=_box_stats_on(), play_all=play_all)
    # Everyone who took the court — singles AND doubles — so season-mode rolls fresh
    # injuries on them. A doubles-only specialist (in la_d but not la) must be counted
    # or they'd play every dual injury-free.
    rec["home_played"] = list(dict.fromkeys([p.pid for p in la] + [p.pid for p in la_d]))
    rec["away_played"] = list(dict.fromkeys([p.pid for p in lb] + [p.pid for p in lb_d]))
    return rec


def build_corpus(duals: list[dict]) -> dict[str, list[tuple]]:
    """Per-player singles match corpus: pid -> [(opp_pid, games_won, games_lost), ...]."""
    return _build_corpus(duals)


def _build_corpus(duals: list[dict]) -> dict[str, list[tuple]]:
    corpus: dict[str, list[tuple]] = {}
    for d in duals:
        for ln in d["lines"]:
            if not ln.get("completed") or "home_pid" not in ln:
                continue
            hp, ap = ln["home_pid"], ln["away_pid"]
            hg, ag = ln["home_games"], ln["away_games"]
            corpus.setdefault(hp, []).append((ap, hg, ag))
            corpus.setdefault(ap, []).append((hp, ag, hg))
    return corpus


def _schedule(div: Division, rng: random.Random) -> list[tuple[Program, Program, bool]]:
    games: list[tuple[Program, Program, bool]] = []
    # conference round robin
    for members in div.conferences.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                games.append((members[i], members[j], True))
    # non-conference: connect the SoS graph
    progs = div.programs
    for p in progs:
        for _ in range(NONCONF_PER_TEAM):
            q = rng.choice(progs)
            if q.conf != p.conf and q is not p:
                games.append((p, q, False))
    return games


def _conf_tournament(members: list[Program], standings_order: list[Program],
                     rng: random.Random) -> Program:
    """Single-elim conference tournament; champion earns the autobid."""
    seeded = standings_order[:min(8, len(members))]
    if len(seeded) == 1:
        return seeded[0]
    n = 1
    while n < len(seeded):
        n *= 2
    positions = _seed_positions(n)
    slots = [seeded[s - 1] if s <= len(seeded) else None for s in positions]
    while len([s for s in slots if s]) > 1:
        nxt = []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if not a or not b:
                nxt.append(a or b); continue
            nxt.append(play_dual(a, b, seed=rng.randint(1, 10**9), fidelity=_fidelity()))
        slots = nxt
    return next(s for s in slots if s)


def run_season(division: str = "D1", gender: str = "men", *, seed: int = 2026,
               rosters: dict | None = None) -> SeasonResult:
    div = load_division(division, gender)
    rng = random.Random(seed)

    # Persistent rosters of Prospects (the League passes its own; otherwise build).
    if rosters is None:
        rosters = {p.school: build_roster(p) for p in div.programs}
    ladders = {s: sorted(r, key=lambda pr: pr.current_overall(), reverse=True)[:6]
               for s, r in rosters.items()}
    squads = {s: Team(name=s, singles=[pr.engine_player() for pr in ladders[s]])
              for s in rosters}

    games = _schedule(div, rng)
    play_all = division in ("D3", "D4")   # ITA D3 play-play — all these are regular-season duals
    duals = [_dual_record(a, b, squads[a.school], squads[b.school],
                          ladders[a.school], ladders[b.school],
                          seed=rng.randint(1, 10**9), conf=c, play_all=play_all)
             for (a, b, c) in games]

    ratings = compute_ratings(duals)

    # conference standings (conference duals only)
    conf_wl: dict[str, dict[str, list[int]]] = {}
    for d in duals:
        if not d["conf"]:
            continue
        for t in (d["home"], d["away"]):
            conf_wl.setdefault(t, [0, 0])
        if d["home_won"]:
            conf_wl[d["home"]][0] += 1; conf_wl[d["away"]][1] += 1
        else:
            conf_wl[d["away"]][0] += 1; conf_wl[d["home"]][1] += 1

    standings: dict[str, list[tuple]] = {}
    champions: list[Program] = []
    for conf, members in div.conferences.items():
        def keyf(p: Program):
            w, l = conf_wl.get(p.school, [0, 0])
            n = w + l
            return (w / n if n else 0.0, ratings[p.school].pi)
        order = sorted(members, key=keyf, reverse=True)
        standings[conf] = [(p, *conf_wl.get(p.school, [0, 0])) for p in order]
        if members:
            champions.append(_conf_tournament(members, order, rng))

    # Live STR from results: per-player singles corpus → convergence, seeded by
    # each player's ability-derived STR (results take over as reliability rises).
    corpus = _build_corpus(duals)
    priors = {pr.pid: pr.str_value() for s in rosters for pr in ladders[s]}
    player_str = converge_ids(corpus, priors=priors)
    player_record = {pid: (sum(1 for (_, gw, gl) in ms if gw > gl),
                           sum(1 for (_, gw, gl) in ms if gw <= gl))
                     for pid, ms in corpus.items()}

    return SeasonResult(division, gender, seed, div.programs, ratings,
                        standings, champions, duals,
                        rosters=rosters, player_str=player_str, player_record=player_record)

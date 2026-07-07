"""
Simulated AP (Media) + Coaches poll ecosystem.

A subjective, reputation+results snapshot of what HUMANS believe — deliberately
SEPARATE from the Power Index and Power 6 (what the game knows). One national
board per gender spanning D1-D4: D1 powers sit up top on reputation, a dominant
lower-division team can crack the bottom, and week-to-week movement + storylines
tell the season's story.

How it works — exactly like the real polls (see the AP/Coaches methodology):
  • Two polls share ONE scoring system; only the electorate differs.
      - MEDIA (~51 voters): reactive, rewards upsets, moves fast.
      - COACHES (~40 voters): conservative, prestige-leaning, slow to move.
  • Every voter submits a top-25 ballot; 1st = 25 pts … 25th = 1 pt. Sum every
    ballot; most points wins. First-place votes are tracked and shown.
  • Past #25 we keep counting — "Others Receiving Votes".
  • INERTIA: humans don't re-rank from scratch, so each week's ballots lean on
    last week's board (heavier for coaches). A one-loss #1 slides a spot, not to
    #11. Boards are therefore computed FORWARD from a preseason (reputation) seed.
  • Every simulated voter has an archetype (resume / computer / traditional /
    upset-chaser) with its own signal weights, plus per-voter noise, so ballots
    differ. The pool's archetype MIX is what makes media ≠ coaches.

Deterministic: seeded per (world seed, gender, week, poll). Cached.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

POLL_SIZE = 25            # a ranked board is the top 25
ORV_SHOW = 15            # how many "others receiving votes" to surface
BALLOT_DEPTH = 25         # each voter ranks this many
_CANDIDATES = 80          # only the top-N reputational/results teams are balloted (bounds work)

# Division reputation floor — the cross-division prior a human carries ("a good
# D1 team is simply better than a good D3 team"). Blended with athletic prestige.
_DIV_TIER = {"D1": 1.00, "D2": 0.62, "D3": 0.36, "D4": 0.20}
_POWER_CONFS = {"ACC", "SEC", "Big Ten", "Big 12", "Pac-16"}   # D1 "power" (non-mid-major)


# --- Voter archetypes: signal → weight (weights need not sum to 1) ------------
_ARCHETYPES = {
    # résumé voter: what you did on the court
    "resume":      {"winpct": 0.40, "sos": 0.30, "ranked": 0.20, "road": 0.10},
    # analytics voter: reputation + schedule strength (a poll-side proxy, NOT the
    # game's Power Index — polls stay "what humans believe")
    "computer":    {"reputation": 0.45, "sos": 0.30, "winpct": 0.25},
    # traditionalist: last week's board, quality wins, established brands
    "traditional": {"inertia": 0.50, "ranked": 0.30, "reputation": 0.20},
    # upset chaser: recent form and momentum
    "upset":       {"momentum": 0.50, "ranked": 0.30, "winpct": 0.20},
}

# Electorate mixes (fractions of the pool by archetype) + behavioural knobs.
_POOLS = {
    "media": {
        "voters": 51, "mix": {"resume": 0.35, "computer": 0.20, "traditional": 0.15, "upset": 0.30},
        "inertia": 0.75, "noise": 0.065, "prestige_bias": 0.05,
    },
    "coaches": {
        "voters": 40, "mix": {"resume": 0.25, "computer": 0.20, "traditional": 0.40, "upset": 0.15},
        "inertia": 1.20, "noise": 0.030, "prestige_bias": 0.12,
    },
}
POLL_LABELS = {"media": "Media Poll", "coaches": "Coaches Poll"}


@dataclass
class BoardRow:
    rank: int
    school: str
    division: str
    conf: str
    record: str
    points: int
    first_votes: int
    move: int | None            # +up / -down / 0 steady / None = new to the board
    prev: int | None            # last week's rank (None = unranked/NR)


@dataclass
class Poll:
    poll: str                    # 'media' | 'coaches'
    label: str
    gender: str
    week: int
    board: list                  # list[BoardRow], top 25
    others: list                 # [(school, points), ...] receiving votes
    storylines: dict = field(default_factory=dict)
    movers_up: list = field(default_factory=list)
    movers_down: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Data gathering — one gender's teams + game logs across all four divisions.
# ---------------------------------------------------------------------------
_snap_cache: dict = {}


def _gather(seed: int, gender: str) -> dict:
    """{school: team dict} across D1-D4 for `gender`. Each team carries division,
    conf, a reputation prior (prestige × division tier), and its game log
    [(opp, won, home, week)] from the season's ranking-corpus duals. Cached by the
    total number of finalised duals so it refreshes as the season advances."""
    import app.seasonmode as sm
    import app.world as world
    from app.ncaa import load_division

    wseed = world.current_year_seed(seed)
    sids = {}
    for div in ("D1", "D2", "D3", "D4"):
        sids[div] = sm.get_or_create(div, gender, seed=wseed)
    conn = sm._db()
    qs = ",".join("?" for _ in sm.RANKING_ROUNDS)
    total_final = 0
    logs: dict = {}
    week_now = 0
    for div, sid in sids.items():
        s = sm.load_season(sid)
        week_now = max(week_now, (s or {}).get("current_week", 0) or 0)
        rows = conn.execute(
            f"SELECT week, home, away, winner FROM duals WHERE season_id=? AND status='final'"
            f" AND round IN ({qs})", (sid, *sm.RANKING_ROUNDS)).fetchall()
        total_final += len(rows)
        for r in rows:
            h, a, hw, wk = r["home"], r["away"], r["winner"] == 0, r["week"]
            logs.setdefault(h, []).append((a, hw, True, wk))
            logs.setdefault(a, []).append((h, not hw, False, wk))
    conn.close()

    key = (wseed, gender, total_final)
    if key in _snap_cache:
        return _snap_cache[key]

    teams: dict = {}
    for div in ("D1", "D2", "D3", "D4"):
        for p in load_division(div, gender).programs:
            prestige = float(getattr(p, "prestige", 0.5))
            tier = _DIV_TIER.get(div, 0.2)
            teams[p.school] = {
                "school": p.school, "division": div, "conf": p.conf_abbr,
                "prestige": prestige,
                # reputation prior: division tier dominates (cross-division), athletic
                # prestige separates within a tier.
                "reputation": 0.72 * tier + 0.28 * prestige,
                "is_power": p.conf_abbr in _POWER_CONFS,
                "games": logs.get(p.school, []),
            }
    snap = {"teams": teams, "week": week_now, "seed": wseed}
    _snap_cache.clear()
    _snap_cache[key] = snap
    return snap


def _record(games, upto) -> tuple[int, int]:
    w = sum(1 for _o, won, _h, wk in games if wk <= upto and won)
    l = sum(1 for _o, won, _h, wk in games if wk <= upto and not won)
    return w, l


def _norm(d: dict) -> dict:
    """Min-max a {key: value} map into 0..1 (flat 0.5 when degenerate)."""
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    span = (hi - lo) or 1.0
    return {k: (v - lo) / span for k, v in d.items()} if hi > lo else {k: 0.5 for k in d}


def _signals(teams: dict, upto: int, prior_board: dict) -> dict:
    """Per-team normalized voter signals as of week `upto`. `prior_board` is last
    week's {school: rank} (for inertia + ranked-wins). Reputation is the preseason
    anchor; the rest come from results."""
    ranked = set(list(prior_board)[:POLL_SIZE]) if prior_board else set()
    winpct, sos, ranked_w, road_w, momentum = {}, {}, {}, {}, {}
    for t in teams.values():
        s = t["school"]
        g = [(o, won, h, wk) for (o, won, h, wk) in t["games"] if wk <= upto]
        w = sum(1 for _o, won, _h, _wk in g if won)
        n = len(g)
        winpct[s] = w / n if n else 0.0
        # strength of schedule: mean opponent win% (self-referential but one pass is fine)
        opp_wl = []
        for o, _won, _h, _wk in g:
            ow, ol = _record(teams.get(o, {}).get("games", []), upto)
            opp_wl.append(ow / (ow + ol) if (ow + ol) else 0.5)
        sos[s] = sum(opp_wl) / len(opp_wl) if opp_wl else 0.5
        ranked_w[s] = sum(1 for o, won, _h, _wk in g if won and o in ranked)
        road_w[s] = sum(1 for _o, won, h, _wk in g if won and not h)
        recent = [won for _o, won, _h, wk in g if wk >= upto - 1]      # last ~2 weeks
        momentum[s] = (sum(1 for x in recent if x) - sum(1 for x in recent if not x))
    winpct, sos = _norm(winpct), _norm(sos)
    ranked_w, road_w, momentum = _norm(ranked_w), _norm(road_w), _norm(momentum)
    reputation = {t["school"]: t["reputation"] for t in teams.values()}
    # inertia: last week's board position as a 0..1 score (1 = last week's #1)
    inertia = {}
    for s in teams:
        p = prior_board.get(s)
        inertia[s] = (POLL_SIZE + 10 - p) / (POLL_SIZE + 10) if p and p <= POLL_SIZE + 10 else 0.0
    return {"winpct": winpct, "sos": sos, "ranked": ranked_w, "road": road_w,
            "momentum": momentum, "reputation": reputation, "inertia": inertia}


def _candidates(teams: dict, sig: dict, prior_board: dict) -> list:
    """Bound the electorate's work: the ~top-N teams worth balloting — a coarse
    reputation+résumé prescreen, always including last week's board."""
    def prelim(s):
        return (0.45 * sig["reputation"].get(s, 0) + 0.30 * sig["winpct"].get(s, 0)
                + 0.15 * sig["sos"].get(s, 0) + 0.10 * sig["inertia"].get(s, 0))
    ranked = sorted(teams, key=prelim, reverse=True)[:_CANDIDATES]
    keep = set(ranked) | set(list(prior_board)[:POLL_SIZE])
    return list(keep)


def _archetype_roster(pool: dict, n: int) -> list:
    """Deterministically assign `n` voters to archetypes per the pool's mix."""
    roster = []
    for arch, frac in pool["mix"].items():
        roster += [arch] * round(frac * n)
    while len(roster) < n:
        roster.append("resume")
    return roster[:n]


def _run_ballots(pool_name: str, cands: list, sig: dict, salt: str) -> tuple[dict, dict]:
    """Every voter in `pool_name` ranks a top-25 from `cands`; tally poll points
    (25..1) and first-place votes. Returns ({school: points}, {school: 1st votes}).
    `salt` seeds each voter's lean and is week-INDEPENDENT on purpose: a voter is
    the same person all season, so week-to-week movement comes from results, not a
    reshuffle of noise."""
    pool = _POOLS[pool_name]
    roster = _archetype_roster(pool, pool["voters"])
    points: dict = {s: 0 for s in cands}
    firsts: dict = {s: 0 for s in cands}
    for vi, arch in enumerate(roster):
        w = _ARCHETYPES[arch]
        rng = random.Random(f"{salt}|{pool_name}|{vi}")
        scored = []
        for s in cands:
            base = 0.0
            for key, wt in w.items():
                mult = pool["inertia"] if key == "inertia" else 1.0
                base += wt * mult * sig[key].get(s, 0.0)
            base += pool["prestige_bias"] * sig["reputation"].get(s, 0.0)
            base += rng.uniform(-pool["noise"], pool["noise"])
            scored.append((base, s))
        scored.sort(key=lambda x: x[0], reverse=True)
        for pos, (_v, s) in enumerate(scored[:BALLOT_DEPTH], 1):
            points[s] += POLL_SIZE + 1 - pos            # 1st→25 … 25th→1
            if pos == 1:
                firsts[s] += 1
    return points, firsts


def _board(teams: dict, points: dict, firsts: dict, upto: int) -> list:
    """Order the tally into a board of (school, points, firsts, record). Ties broken
    by first-place votes then reputation, as a poll would."""
    order = sorted(
        (s for s in points if points[s] > 0),
        key=lambda s: (points[s], firsts.get(s, 0), teams[s]["reputation"]),
        reverse=True,
    )
    out = []
    for s in order:
        w, l = _record(teams[s]["games"], upto)
        out.append({"school": s, "points": points[s], "firsts": firsts.get(s, 0),
                    "record": f"{w}-{l}", "division": teams[s]["division"],
                    "conf": teams[s]["conf"]})
    return out


# recursion memo: (seed, gender, poll, week) -> full ordered board (list of dicts)
_board_cache: dict = {}


def _weekly_board(seed: int, gender: str, poll: str, week: int, snap: dict) -> list:
    """The full ordered tally for `poll` at `week`, computed forward from the
    preseason seed so inertia carries. Memoized."""
    ck = (snap["seed"], gender, poll, week)
    if ck in _board_cache:
        return _board_cache[ck]
    teams = snap["teams"]
    if week <= 0:
        prior_positions = {}
    else:
        prev = _weekly_board(seed, gender, poll, week - 1, snap)
        # A week with no new results doesn't move the poll (a bye week / pre-season):
        # carry the prior board forward so movement only ever reflects real games.
        if not any(wk == week for t in teams.values() for (_o, _w, _h, wk) in t["games"]):
            _board_cache[ck] = prev
            return prev
        prior_positions = {r["school"]: i + 1 for i, r in enumerate(prev)}
    sig = _signals(teams, week, prior_positions)
    cands = _candidates(teams, sig, prior_positions)
    # NB: week-independent salt — voter leans are fixed for the season, so the board
    # only moves when RESULTS move (signals/inertia), never from per-week noise.
    points, firsts = _run_ballots(poll, cands, sig, f"{snap['seed']}|{gender}")
    board = _board(teams, points, firsts, week)
    _board_cache[ck] = board
    return board


def _storylines(teams: dict, board: list, positions: dict, prev_pos: dict) -> dict:
    """Auto-generated weekly narrative: biggest rise/fall, new/dropped, and the
    highest-ranked mid-major and D2/D3/D4 team on the board."""
    top = board[:POLL_SIZE]
    top_names = {r["school"] for r in top}
    prev_top = {s for s, p in prev_pos.items() if p <= POLL_SIZE}

    def _delta(s):
        return (prev_pos[s] - positions[s]) if s in prev_pos and s in positions else None

    rises = sorted(((s, _delta(s)) for s in top_names if _delta(s)), key=lambda x: -(x[1] or 0))
    falls = sorted(((s, _delta(s)) for s in top_names if _delta(s)), key=lambda x: (x[1] or 0))
    new_in = sorted((r for r in top if r["school"] not in prev_top),
                    key=lambda r: positions[r["school"]])
    dropped = sorted((s for s in prev_top if s not in top_names), key=lambda s: prev_pos[s])

    def highest(pred):
        for r in top:
            if pred(r):
                return r
        return None
    mid_major = highest(lambda r: r["division"] == "D1" and not teams[r["school"]]["is_power"])
    return {
        "biggest_rise": (rises[0] if rises and rises[0][1] and rises[0][1] > 0 else None),
        "biggest_fall": (falls[0] if falls and falls[0][1] and falls[0][1] < 0 else None),
        "new_to_poll": [r["school"] for r in new_in],
        "dropped_out": list(dropped),
        "highest_mid_major": (mid_major["school"] if mid_major else None),
        "highest_d2": next((r["school"] for r in top if r["division"] == "D2"), None),
        "highest_d3": next((r["school"] for r in top if r["division"] == "D3"), None),
        "highest_d4": next((r["school"] for r in top if r["division"] == "D4"), None),
    }


def poll(seed: int, gender: str, which: str = "media") -> Poll:
    """The current-week `which` ('media'|'coaches') national poll for `gender`:
    top-25 board with movement + first-place votes, Others Receiving Votes, biggest
    movers and weekly storylines. Empty board only before any team has a result."""
    which = which if which in _POOLS else "media"
    snap = _gather(seed, gender)
    teams = snap["teams"]
    week = snap["week"]
    cur = _weekly_board(seed, gender, which, week, snap)
    positions = {r["school"]: i + 1 for i, r in enumerate(cur)}
    prev = _weekly_board(seed, gender, which, week - 1, snap) if week > 0 else []
    prev_pos = {r["school"]: i + 1 for i, r in enumerate(prev)}

    board = []
    for i, r in enumerate(cur[:POLL_SIZE], 1):
        s = r["school"]
        p = prev_pos.get(s)
        move = None if p is None else (p - i)
        board.append(BoardRow(
            rank=i, school=s, division=r["division"], conf=r["conf"], record=r["record"],
            points=r["points"], first_votes=r["firsts"], move=move, prev=p))
    others = [(r["school"], r["points"]) for r in cur[POLL_SIZE:POLL_SIZE + ORV_SHOW]]

    story = _storylines(teams, cur, positions, prev_pos) if prev else {}
    # biggest movers within the board (poll-position deltas)
    deltas = [(r.school, r.move) for r in board if r.move]
    movers_up = sorted((d for d in deltas if d[1] > 0), key=lambda x: -x[1])[:5]
    movers_down = sorted((d for d in deltas if d[1] < 0), key=lambda x: x[1])[:5]
    return Poll(poll=which, label=POLL_LABELS[which], gender=gender, week=week,
                board=board, others=others, storylines=story,
                movers_up=movers_up, movers_down=movers_down)

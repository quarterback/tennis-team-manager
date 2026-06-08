"""
Junior circuit — the recruit-history generator.

It is a one-shot pipeline that runs ONCE per recruiting class, *before* recruiting
opens, and freezes a believable pre-college résumé onto every recruit:

    seed STR from ability → run ~14 abstract WEEKS, each rank-gating the whole field
    into parallel graded draws (Grand Slam / Masters / … / State) → accumulate
    ranking points + a results-based STR → rank → badge → freeze

so a recruit arrives in recruiting already feeling lived-in — real matches against
real rivals (scores and opponents on record), a points ranking and STR that climbed
or slid with form across the year, a ranking progression, and permanent badges.

The schedule is a points pyramid, like the real junior tours: every "week" the
elite contest the top events while everyone else plays level-appropriate draws, so
all ~1000 juniors keep playing. Tournament names auto-roll from the city database;
only the four Grand Slams are fixed.

Why the full engine, why before college
----------------------------------------
The junior circuit runs once per class, not continuously, so it can afford the
*full* point-by-point match engine — the best results the engine can produce. Those
matches feed the same results-based STR rating the college game uses
(`app.str_rating.converge_ids`): STR is seeded by a player's visible ability but
then SOLVED from what they actually did on court, recency-weighted, so a winning
junior rises and a slumping one regresses. Players are dynamic, not fixed.

Closed ecosystem
----------------
Every player in every draw is a recruit the game generated — no anonymous opponents,
no synthetic filler. Future college teammates may have faced each other as juniors;
rivals carry real histories in from before college. Big fields split into parallel
sections so everyone gets matches; if only four players enter a state championship,
that is fine — consistency beats realistic draw sizes (the build spec).

Determinism: one seed threads tiering, every match, and the participation rolls, so
the same class + seed reproduce identical résumés.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass

from engine import run_tournament, simulate_match, MatchFormat, Player, ATTRS
from generators import roll_hometown
from .str_rating import converge_ids
from .development import stagger_scale

# --------------------------------------------------------------------------
# The junior season runs as abstract "weeks" — not a real calendar, just enough
# graded tournaments to give every recruit matches and data, then they graduate to
# college. Each week the WHOLE field is rank-gated into parallel draws: the elite
# get the Grand Slam / Masters, the next bands get Majors / Premiers, on down to
# State — so all ~1000 juniors play every week at their own level in small draws
# (real junior tours run hundreds of graded events in parallel weekly). Only the
# four slams are fixed; every other event's name auto-rolls from the city database.
# Tiers, highest first (also the points-table keys):
#   Grand Slam > Masters > Major > Premier > National > Developmental > State
# --------------------------------------------------------------------------
SEASON_WEEKS = 14
DRAW_SIZE = 32                 # one single-elim draw per 32 players in a band (ITF-ish)

# The four Junior Grand Slams land on these weeks; only the top DRAW_SIZE by ranking
# get in. They are the only fixed-name events.
GS_SCHEDULE = {2: "Australian Open Junior Championships",
               6: "Roland-Garros Junior Championships",
               9: "Wimbledon Junior Championships",
               12: "US Open Junior Championships"}

# Each week the ranked field is sliced into these tiers by cumulative fraction, and
# each slice split into DRAW_SIZE draws. (On a slam week the top DRAW_SIZE are pulled
# into the slam first and these bands fill the remainder.)
BANDS = [("Masters", 0.08), ("Major", 0.22), ("Premier", 0.42),
         ("National", 0.62), ("Developmental", 0.82), ("State", 1.00)]

# Snapshot weeks the ranking history reports at (four points across the season).
SNAP_WEEKS = [("Early", max(1, SEASON_WEEKS // 4)), ("Mid", SEASON_WEEKS // 2),
              ("Late", (3 * SEASON_WEEKS) // 4), ("Final", SEASON_WEEKS)]

# Tournament-name flavor by tier; the city rolls from the hometowns database, so
# names read like "Nice Open", "Sendai Classic", "Madrid Masters".
_TOURNEY_SUFFIX = {
    "Masters": ["Masters", "International Masters", "Masters Cup"],
    "Major": ["Open", "International", "Championships"],
    "Premier": ["Open", "International", "Classic"],
    "National": ["Open", "Classic", "Championships"],
    "Developmental": ["Challenger", "Open", "Cup"],
    "State": ["Open", "Cup", "Classic", "Invitational"],
}
# Tennis nations the city pool draws from (US weighted by duplication).
_CITY_COUNTRIES = ["US", "US", "FR", "ES", "IT", "DE", "GB", "AU", "JP", "AR",
                   "BR", "CZ", "CN", "CA", "NL", "BE", "RS", "HR", "MX", "IN"]
_GENERIC_CITIES = ["Riverside", "Fairview", "Lakeside", "Highland", "Westport"]

# Tier cutoffs as a cumulative fraction of the STR-sorted class. A thin international
# elite on top, a national-elite band, a thick regional body, then a local tail.
TIER_CUTOFFS = [(0.05, 1), (0.25, 2), (0.65, 3), (1.01, 4)]
TIER_LABELS = {1: "International Elite", 2: "National Elite",
               3: "Regional / State Elite", 4: "Local Competitive"}

# Junior development: a recruit's CURRENT (recruiting-time) ability is the END of
# the junior climb. We replay that climb across the season — start each recruit at
# their younger self (~this many development-years back) and develop them, in
# staggered waves, back UP to current. A super-bloomer was far weaker early and
# surges up the rankings; an early bloomer was always near here and gets passed as
# peers keep climbing (the "looked great at 14, ordinary by 16" arc). The recruit
# object is never mutated — only throwaway copies develop — so the recruiting board
# stays calibrated. See docs/DEV-MODEL-tennis-adaptation.md.
JUNIOR_DEV_YEARS = 1.0

# A draw is capped at this size; bigger fields split into parallel sections (real
# junior tennis runs many L4/L5 draws at once), so every recruit gets matches.
SECTION_CAP = 32

# ---- Junior ranking POINTS (pro-tour scaling: Slam 2000 > Masters 1000 > …) ----
# Distinct from STR (a rating) and the recruiting board (consensus ability): this is
# an accomplishment LEDGER — points earned by round reached, scaled by event tier
# (Grand Slam > Masters > Major > Premier > National > Developmental > State), best
# six results counted, plus a bonus for beating ranked players. Doubles fold into the
# SAME ledger at a 1/4 weight (the ITF Combined Junior Ranking — no separate doubles
# ranking). See docs/DEV-MODEL-tennis-adaptation.md.
# finish_label -> {tier: points}, pro-tour scaled: Grand Slam 2000 > Masters 1000 >
# Major 500 > Premier 250 > National 125 > Developmental 60 > State 30, with rounds
# decaying in ATP-style ratios. Single-elim has no 3rd-place playoff, so both
# semifinal losers take the Semifinalist row.
JUNIOR_POINTS = {
    "Champion":        {"Grand Slam": 2000, "Masters": 1000, "Major": 500, "Premier": 250, "National": 125, "Developmental": 60, "State": 30},
    "Finalist":        {"Grand Slam": 1200, "Masters": 600,  "Major": 300, "Premier": 150, "National": 75,  "Developmental": 36, "State": 18},
    "Semifinalist":    {"Grand Slam": 720,  "Masters": 360,  "Major": 180, "Premier": 90,  "National": 45,  "Developmental": 22, "State": 11},
    "Quarterfinalist": {"Grand Slam": 360,  "Masters": 180,  "Major": 90,  "Premier": 45,  "National": 23,  "Developmental": 11, "State": 5},
    "R16":             {"Grand Slam": 180,  "Masters": 90,   "Major": 45,  "Premier": 23,  "National": 11,  "Developmental": 5,  "State": 3},
    "R32":             {"Grand Slam": 90,   "Masters": 45,   "Major": 23,  "Premier": 11,  "National": 6,   "Developmental": 3,  "State": 1},
}
# DOUBLES table (≈75% of singles); folded in at DOUBLES_WEIGHT. A Grand Slam doubles
# title (1500, ¼ → 375 combined) dwarfs everything else — the boost the user wanted.
JUNIOR_DOUBLES_POINTS = {
    "Champion":        {"Grand Slam": 1500, "Masters": 750, "Major": 375, "Premier": 188, "National": 94, "Developmental": 45, "State": 23},
    "Finalist":        {"Grand Slam": 900,  "Masters": 450, "Major": 225, "Premier": 113, "National": 56, "Developmental": 27, "State": 14},
    "Semifinalist":    {"Grand Slam": 540,  "Masters": 270, "Major": 135, "Premier": 68,  "National": 34, "Developmental": 16, "State": 8},
    "Quarterfinalist": {"Grand Slam": 270,  "Masters": 135, "Major": 68,  "Premier": 34,  "National": 17, "Developmental": 8,  "State": 4},
    "R16":             {"Grand Slam": 135,  "Masters": 68,  "Major": 34,  "Premier": 17,  "National": 8,  "Developmental": 4,  "State": 2},
    "R32":             {"Grand Slam": 0,    "Masters": 0,   "Major": 0,   "Premier": 0,   "National": 0,  "Developmental": 0,  "State": 0},
}
DOUBLES_WEIGHT = 0.25      # ITF CJR: combined = best-6 singles + ¼ × best-6 doubles
# USTA-style bonus for beating a ranked opponent (singles), by the opponent's
# standing in the provisional combined order.
_RANKED_WIN_BONUS = [(10, 75), (25, 68), (50, 56), (75, 45), (100, 34),
                     (150, 23), (250, 15), (350, 8), (500, 4)]
BEST_N = 6        # only a player's best six results (and best six ranked wins) count

# Junior doubles is the FULL match engine (not the 8-game pro set) — best-of-3,
# no-ad, with a 10-point match tiebreak in lieu of the third set (ITF junior rules).
JUNIOR_DOUBLES_FMT = MatchFormat(best_of=3, no_ad=True, set_tiebreak=True,
                                 final_set_tiebreak=True, final_set_tiebreak_target=10)
# Likelihood a recruit also enters the doubles draw, driven by stamina + grit
# (resilience/competitiveness): grinders play doubles more. Winning is talent.
DOUBLES_BASE_P, DOUBLES_SPAN = 0.20, 0.65
_GRIT_ATTRS = ("stamina", "resilience", "competitiveness")


def event_points(level: str, finish: str, *, table=JUNIOR_POINTS) -> int:
    return table.get(finish, {}).get(level, 0)


def doubles_event_points(level: str, finish: str) -> int:
    return event_points(level, finish, table=JUNIOR_DOUBLES_POINTS)


def _ranked_win_bonus(rank: int | None) -> int:
    if rank is None:
        return 0
    for ceil, pts in _RANKED_WIN_BONUS:
        if rank <= ceil:
            return pts
    return 0


def _freeze_points(recruits: list, c: "_Circuit") -> None:
    """Freeze each recruit's junior ranking POINTS onto them. ITF Combined Junior
    Ranking: best-6 singles results (+ best-6 ranked-win bonuses) plus ¼ of best-6
    doubles results — one ledger, no separate doubles ranking. Two-pass: provisional
    combined order decides which singles wins earn a ranked-win bonus."""
    singles, doubles, played, dbl_played = {}, {}, {}, {}
    for p in recruits:
        s = sorted((event_points(lv, f) for (_m, _t, lv, f) in c.finishes.get(p.pid, [])),
                   reverse=True)
        d = sorted((doubles_event_points(lv, f)
                    for (_m, _t, lv, f, _pn) in c.dbl_finishes.get(p.pid, [])), reverse=True)
        singles[p.pid] = sum(s[:BEST_N])
        doubles[p.pid] = sum(d[:BEST_N])
        played[p.pid] = len(c.finishes.get(p.pid, []))
        dbl_played[p.pid] = len(c.dbl_finishes.get(p.pid, []))
    prov_base = {pid: singles[pid] + DOUBLES_WEIGHT * doubles[pid] for pid in singles}
    prov = sorted(recruits, key=lambda q: (-prov_base[q.pid], q.pid))
    prov_rank = {q.pid: i for i, q in enumerate(prov, 1)}
    for p in recruits:
        bonuses = sorted((_ranked_win_bonus(prov_rank.get(opp))
                          for (_m, opp, _mg, _og, won) in c.corpus.get(p.pid, []) if won),
                         reverse=True)
        p.singles_points = int(singles[p.pid] + sum(bonuses[:BEST_N]))
        p.doubles_points = int(doubles[p.pid])
        p.junior_points = int(p.singles_points + DOUBLES_WEIGHT * p.doubles_points)
        p.tournaments_played = played[p.pid]
        p.doubles_played = dbl_played[p.pid]


# Iterations for the results-based STR fixed point (cheaper per snapshot, full final).
_SNAP_ITERS = 6
_FINAL_ITERS = 10

# Badge ladders: (rank threshold, label). Awarded if the BEST rank ever reached is
# at or below the threshold — badges are permanent milestones, so a recruit who
# touched National Top 10 keeps it even if they slide.
US_NATIONAL_BADGES = [(300, "National Top 300 Junior"), (100, "National Top 100 Junior"),
                      (50, "National Top 50 Junior"), (25, "National Top 25 Junior"),
                      (10, "National Top 10 Junior"), (1, "National No. 1 Junior")]
US_STATE_BADGES = [(25, "State Top 25 Junior"), (10, "State Top 10 Junior"),
                   (5, "State Top 5 Junior"), (1, "State No. 1 Junior")]
INTL_GLOBAL_BADGES = [(250, "Global Top 250 Junior"), (100, "Global Top 100 Junior"),
                      (50, "Global Top 50 Junior"), (25, "Global Top 25 Junior"),
                      (10, "Global Top 10 Junior"), (1, "World No. 1 Junior")]
INTL_NATION_BADGES = [(10, "Nation Top 10 Junior"), (5, "Nation Top 5 Junior"),
                      (1, "Nation No. 1 Junior")]


def assign_tiers(recruits: list) -> None:
    """Sort by ability STR and stamp each recruit's competitive tier (1 = elite …
    4 = local). Tier seeds which events a player enters, so it comes first — results
    then re-sort everyone via the evolved STR."""
    ordered = sorted(recruits, key=lambda p: (-p.str_value(), p.pid))
    n = max(1, len(ordered))
    for i, p in enumerate(ordered):
        q = (i + 1) / n
        p.junior_tier = next(t for cut, t in TIER_CUTOFFS if q <= cut)


def _sections(players: list, seed_rank) -> list[list]:
    """Split a field into parallel draws of <= SECTION_CAP, spreading strength evenly
    (serpentine over the rating-sorted list) so each section has a real title race."""
    if len(players) <= SECTION_CAP:
        return [players] if players else []
    ordered = sorted(players, key=lambda p: (-seed_rank(p), p.pid))
    n_sec = (len(ordered) + SECTION_CAP - 1) // SECTION_CAP
    buckets: list[list] = [[] for _ in range(n_sec)]
    forward = True
    for i in range(0, len(ordered), n_sec):
        chunk = ordered[i:i + n_sec]
        idxs = range(n_sec) if forward else range(n_sec - 1, -1, -1)
        for player, b in zip(chunk, idxs):
            buckets[b].append(player)
        forward = not forward
    return [b for b in buckets if b]


def _score_str(set_scores, pi: int) -> str:
    """Set-by-set scoreline from player `pi`'s perspective, e.g. '6-4 3-6 7-5'."""
    parts = []
    for a, b in set_scores:
        hi, lo = (a, b) if pi == 0 else (b, a)
        parts.append(f"{hi}-{lo}")
    return " ".join(parts)


@dataclass
class _Circuit:
    """Mutable scratch state threaded through the season build."""
    grad_year: int
    engine_players: dict          # pid -> engine.Player (built once, reused)
    finishes: dict                # pid -> [(month, name, level, finish_label)]
    matches: dict                 # pid -> [{date, tournament, round, opponent, score, won}]
    corpus: dict                  # pid -> [(month, opp_pid, my_games, opp_games)] chronological
    dbl_finishes: dict            # pid -> [(month, name, level, finish_label, partner_name)]
    dbl_matches: dict             # pid -> [{date, tournament, round, partner, opponents, score, won}]
    dbl_corpus: dict              # pid -> [(opp_pid, my_games, opp_games)] (each partner faced)


def _run_event(c: _Circuit, name: str, level: str, month: int, field: list,
               rng: random.Random) -> None:
    """Play one event (possibly several parallel sections) with the FULL engine and
    record finishes, per-match lore (opponent + score), and the STR corpus."""
    date = f"Wk {month}"
    for section in _sections(field, lambda p: p.str_value()):
        if len(section) < 2:
            continue
        played: dict = {}   # frozenset(pid pair) -> MatchResult

        def play(a, b, *, seed):
            res = simulate_match(c.engine_players[a.pid], c.engine_players[b.pid], seed=seed)
            played[frozenset((a.pid, b.pid))] = res
            return a if res.winner == 0 else b

        result = run_tournament(section, seed=rng.randint(1, 10 ** 9),
                                play=play, key=lambda p: p.str_value())

        for idx, p in enumerate(result.entrants):
            finish = result.finish_of(idx)
            if finish is not None:
                c.finishes.setdefault(p.pid, []).append((month, name, level, finish))

        # Walk the bracket in round order (chronological within the event). The
        # framework always calls play(seeded[hi], seeded[lo]), so hi is side 0.
        for rnd in result.rounds:
            for m in rnd:
                hp, lp = result.entrants[m.hi], result.entrants[m.lo]
                res = played[frozenset((hp.pid, lp.pid))]
                hg, lg = res.games_won            # (side0=hi, side1=lo)
                for player, opp, pi, mg, og in (
                        (hp, lp, 0, hg, lg), (lp, hp, 1, lg, hg)):
                    won = (res.winner == pi)
                    c.matches.setdefault(player.pid, []).append({
                        "date": date, "tournament": name, "round": m.rnd,
                        "opponent": opp.name, "score": _score_str(res.set_scores, pi),
                        "won": won})
                    c.corpus.setdefault(player.pid, []).append((month, opp.pid, mg, og, won))

    _run_doubles(c, name, level, month, field, rng)


# Doubles tilts the engine drivers toward the skills that win doubles — serve,
# court coverage, net instincts (mental) — and eases off long-rally baseline play.
# A serve+movement player therefore rates ABOVE their singles level in doubles and a
# baseline grinder below, so a doubles STR ≠ singles STR and specialists surface.
_DOUBLES_TILT = {"serve_power": 1.25, "serve_placement": 1.25, "movement": 1.20,
                 "mental": 1.10, "stamina": 0.90,
                 "forehand": 0.85, "backhand": 0.85, "consistency": 0.85}


def _pair_engine(a: Player, b: Player) -> Player:
    """Collapse a doubles pair into one synthetic, doubles-tilted engine Player so the
    full match engine resolves the team match — the college-dual trick, plus the tilt
    that makes doubles a distinct skill."""
    attrs = {at: max(0.0, min(1.0, (getattr(a, at) + getattr(b, at)) / 2.0 * _DOUBLES_TILT.get(at, 1.0)))
             for at in ATTRS}
    return Player(name=f"{a.name} / {b.name}", country=getattr(a, "country", "US"), **attrs)


def _plays_doubles(p, rng: random.Random) -> bool:
    """Whether a recruit also enters the doubles draw — driven by stamina + grit, so
    grinders play doubles more. Not everyone plays; winning is talent (the engine)."""
    g = sum(p.current_grade(a) for a in _GRIT_ATTRS) / len(_GRIT_ATTRS)   # ~20..80
    return rng.random() < DOUBLES_BASE_P + DOUBLES_SPAN * max(0.0, min(1.0, (g - 30) / 45))


def _run_doubles(c: _Circuit, name: str, level: str, month: int, field: list,
                 rng: random.Random) -> None:
    """Run the event's doubles draw: stamina/grit decides who enters, partners are
    drawn on the fly (whoever's there), and pairs play the full junior-doubles format.
    Both partners share the team's finish, points and per-opponent STR corpus."""
    date = f"Wk {month}"
    entrants = [p for p in field if _plays_doubles(p, rng)]
    for section in _sections(entrants, lambda p: p.str_value()):
        order = section[:]
        rng.shuffle(order)                                   # on-the-fly pairing
        pairs = [(order[i], order[i + 1]) for i in range(0, len(order) - 1, 2)]
        if len(pairs) < 2:
            continue
        def pkey(pr):                      # pairs hold unhashable Prospects → key by pids
            return (pr[0].pid, pr[1].pid)
        teams = {pkey(pr): _pair_engine(c.engine_players[pr[0].pid], c.engine_players[pr[1].pid])
                 for pr in pairs}
        played: dict = {}

        def play(ta, tb, *, seed):
            res = simulate_match(teams[pkey(ta)], teams[pkey(tb)], seed=seed, fmt=JUNIOR_DOUBLES_FMT)
            played[frozenset((pkey(ta), pkey(tb)))] = res
            return ta if res.winner == 0 else tb

        result = run_tournament(pairs, seed=rng.randint(1, 10 ** 9), play=play,
                                key=lambda pr: pr[0].str_value() + pr[1].str_value())

        for idx, pr in enumerate(result.entrants):
            finish = result.finish_of(idx)
            if finish is not None:
                for me, partner in ((pr[0], pr[1]), (pr[1], pr[0])):
                    c.dbl_finishes.setdefault(me.pid, []).append(
                        (month, name, level, finish, partner.name))

        for rnd in result.rounds:
            for m in rnd:
                hp, lp = result.entrants[m.hi], result.entrants[m.lo]
                res = played[frozenset((pkey(hp), pkey(lp)))]
                hg, lg = res.games_won
                for team, opp, pi, mg, og in ((hp, lp, 0, hg, lg), (lp, hp, 1, lg, hg)):
                    won = (res.winner == pi)
                    for me, mate in ((team[0], team[1]), (team[1], team[0])):
                        c.dbl_matches.setdefault(me.pid, []).append({
                            "date": date, "tournament": name, "round": m.rnd,
                            "partner": mate.name,
                            "opponents": f"{opp[0].name} / {opp[1].name}",
                            "score": _score_str(res.set_scores, pi), "won": won})
                        for foe in opp:        # each partner is credited vs both foes
                            c.dbl_corpus.setdefault(me.pid, []).append((foe.pid, mg, og))


def _random_city(rng: random.Random) -> str:
    """A real city for a tournament name, rolled from the world's hometowns DB."""
    for _ in range(6):
        city = roll_hometown(rng.choice(_CITY_COUNTRIES), rng)
        if city:
            return city
    return rng.choice(_GENERIC_CITIES)


def _gen_tournament_name(tier: str, rng: random.Random, used: set) -> str:
    """Roll a fresh, plausible event name for `tier` (e.g. 'Nice Open'), avoiding
    duplicates within the season so résumés don't repeat a city."""
    name = ""
    for _ in range(8):
        name = f"{_random_city(rng)} {rng.choice(_TOURNEY_SUFFIX[tier])}"
        if name not in used:
            break
    used.add(name)
    return name


def _chunks(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _schedule_week(ranked: list, week: int, used: set, rng: random.Random) -> list:
    """Rank-gate the whole field into this week's parallel draws. The top DRAW_SIZE
    play the Grand Slam on slam weeks; the rest are sliced into tier bands and each
    band split into DRAW_SIZE draws, so everyone plays at their level. Returns a list
    of (name, tier, field)."""
    events: list[tuple[str, str, list]] = []
    i = 0
    if week in GS_SCHEDULE:
        events.append((GS_SCHEDULE[week], "Grand Slam", ranked[:DRAW_SIZE]))
        i = min(DRAW_SIZE, len(ranked))
    rest = ranked[i:]
    n = len(rest)
    start = 0
    for k, (tier, frac) in enumerate(BANDS):
        end = n if k == len(BANDS) - 1 else round(frac * n)
        band = rest[start:end]
        start = end
        for chunk in _chunks(band, DRAW_SIZE):
            events.append((_gen_tournament_name(tier, rng, used), tier, chunk))
    return events


def _solve_str(recruits: list, corpus: dict, priors: dict, month: int,
               iterations: int) -> dict[str, float]:
    """Results-based STR for the whole class through `month` — the closed ecosystem
    solved to a fixed point. Recruits with no matches yet sit at their ability prior,
    so everyone is rankable from the first snapshot."""
    by_player = {p.pid: [] for p in recruits}
    for pid, entries in corpus.items():
        by_player[pid] = [(opp, mg, og) for (m, opp, mg, og, _won) in entries if m <= month]
    solved = converge_ids(by_player, priors=priors, iterations=iterations)
    return {pid: priors.get(pid, 44.0) for pid in by_player} | {
        pid: v[0] for pid, v in solved.items()}


def _rank_within(players: list, strs: dict[str, float]) -> dict[str, int]:
    """1-based ranking of `players` by results-based STR (pid breaks ties)."""
    ordered = sorted(players, key=lambda p: (-strs.get(p.pid, 0.0), p.pid))
    return {p.pid: i for i, p in enumerate(ordered, 1)}


def _badges_for(best: int | None, ladder) -> list[str]:
    """All milestone labels a best-ever rank of `best` clears, highest first."""
    if best is None:
        return []
    return [label for thresh, label in reversed(ladder) if best <= thresh]


def run_junior_circuit(klass, *, seed: int = 0) -> None:
    """Run the whole junior circuit over `klass` and freeze the résumé onto every
    recruit. Idempotent: a class is only processed once."""
    if getattr(klass, "circuit_done", False):
        return
    recruits = klass.recruits
    rng = random.Random(f"{seed}|junior-circuit|{klass.gender}|{klass.grad_year}")

    # Throwaway "junior selves": start each recruit at their younger self and develop
    # back up to current across the season. The recruit object itself is untouched,
    # so the recruiting board keeps the calibrated recruiting-time ability while the
    # junior matches/STR reflect the climb.
    selves = {p.pid: copy.deepcopy(p) for p in recruits}
    for p in recruits:
        selves[p.pid].regress_to_younger(JUNIOR_DEV_YEARS)
    # The younger ability is the PRIOR the results-based rating regresses toward, so
    # thin early-season records sit low and rise with results — the arc shows.
    priors = {p.pid: selves[p.pid].str_value() for p in recruits}
    assign_tiers(recruits)        # schedule by recruiting-time (current) ability

    c = _Circuit(grad_year=klass.grad_year,
                 engine_players={pid: s.engine_player() for pid, s in selves.items()},
                 finishes={}, matches={}, corpus={},
                 dbl_finishes={}, dbl_matches={}, dbl_corpus={})

    # ---- play the season week by week. Each week: pulse a staggered slice of
    # development, rank the field by running points (ability seeds week 1), then
    # rank-gate everyone into parallel graded draws so all play at their level. ----
    standing = {p.pid: 0.0 for p in recruits}     # running points → next week's gate
    used_names: set = set()
    for week in range(1, SEASON_WEEKS + 1):
        for p in recruits:
            sc = stagger_scale(p.pid, week - 1, SEASON_WEEKS, total=JUNIOR_DEV_YEARS)
            if sc:
                selves[p.pid].develop(sc)
                c.engine_players[p.pid] = selves[p.pid].engine_player()
        ranked = sorted(recruits, key=lambda p: (-standing[p.pid], -priors[p.pid], p.pid))
        for (name, tier, field) in _schedule_week(ranked, week, used_names, rng):
            if len(field) >= 2:
                _run_event(c, name, tier, week, field, rng)
        for p in recruits:                         # refresh the running ranking
            standing[p.pid] = sum(event_points(lv, f)
                                  for (_w, _t, lv, f) in c.finishes.get(p.pid, []))

    # ---- rankings + badges from the EVOLVING results-based STR, split US
    # (national/state) vs intl (global/nation) ----
    domestic = [p for p in recruits if p.domestic]
    intl = [p for p in recruits if not p.domestic]
    state_pools: dict[str, list] = {}
    for p in domestic:
        state_pools.setdefault(p.region, []).append(p)
    nation_pools: dict[str, list] = {}
    for p in intl:
        nation_pools.setdefault(p.region, []).append(p)

    _rank_and_freeze(recruits, domestic, c, priors, SNAP_WEEKS, state_pools,
                     "National", "State", US_NATIONAL_BADGES, US_STATE_BADGES)
    _rank_and_freeze(recruits, intl, c, priors, SNAP_WEEKS, nation_pools,
                     "Global", "Nation", INTL_GLOBAL_BADGES, INTL_NATION_BADGES)

    # ---- freeze the evolved STR + the résumé (finishes + per-match lore) ----
    final = converge_ids(
        {p.pid: [(o, mg, og) for (_m, o, mg, og, _w) in c.corpus.get(p.pid, [])]
         for p in recruits},
        priors=priors, iterations=_FINAL_ITERS)
    # Doubles STR: solved over the doubles corpus, seeded from singles ability — so a
    # mid singles player who wins in doubles rates ABOVE their singles STR (the
    # recruiting lever that surfaces doubles specialists).
    dbl_final = converge_ids(
        {p.pid: list(c.dbl_corpus.get(p.pid, [])) for p in recruits},
        priors=priors, iterations=_FINAL_ITERS)
    _freeze_points(recruits, c)
    for p in recruits:
        s, rel = final.get(p.pid, (priors[p.pid], 0.0))
        p.junior_str = round(s, 2)
        p.junior_str_reliability = round(rel, 3)
        ds, drel = dbl_final.get(p.pid, (priors[p.pid], 0.0))
        p.junior_doubles_str = round(ds, 2) if c.dbl_corpus.get(p.pid) else None
        p.junior_results = [
            {"date": f"Wk {m}", "tournament": t,
             "level": level, "result": finish}
            for (m, t, level, finish) in sorted(c.finishes.get(p.pid, []), key=lambda r: r[0])]
        p.junior_matches = list(c.matches.get(p.pid, []))
        p.junior_doubles_results = [
            {"date": f"Wk {m}", "tournament": t,
             "level": level, "result": finish, "partner": partner}
            for (m, t, level, finish, partner) in
            sorted(c.dbl_finishes.get(p.pid, []), key=lambda r: r[0])]
        p.junior_doubles_matches = list(c.dbl_matches.get(p.pid, []))

    klass.circuit_done = True


def _rank_and_freeze(all_recruits, players, c, priors, snapshots, sub_pools,
                     primary_label, secondary_label, primary_ladder, secondary_ladder):
    """Compute the ranking-history progression (results-based STR re-solved at each
    snapshot) + best-rank badges for one population, and freeze it onto each recruit."""
    best_primary: dict[str, int] = {}
    best_secondary: dict[str, int] = {}
    history: dict[str, list] = {p.pid: [] for p in players}

    for label, month in snapshots:
        strs = _solve_str(all_recruits, c.corpus, priors, month, _SNAP_ITERS)
        primary_rank = _rank_within(players, strs)
        sub_ranks = {k: _rank_within(pool, strs) for k, pool in sub_pools.items()}
        for p in players:
            pr = primary_rank[p.pid]
            sr = sub_ranks.get(p.region, {}).get(p.pid)
            history[p.pid].append({
                "date": f"{label} {c.grad_year}",
                "primary_label": primary_label, "primary": pr,
                "secondary_label": secondary_label, "secondary": sr,
                "str": round(strs.get(p.pid, 0.0), 1),
            })
            best_primary[p.pid] = min(best_primary.get(p.pid, pr), pr)
            if sr is not None:
                best_secondary[p.pid] = min(best_secondary.get(p.pid, sr), sr)

    for p in players:
        p.ranking_history = history[p.pid]
        p.junior_badges = (_badges_for(best_primary.get(p.pid), primary_ladder)
                           + _badges_for(best_secondary.get(p.pid), secondary_ladder))

"""THE ALUMNI TRACKER, CAREER MODEL 2 — a college career as a sequence of states
(owner spec 2026-11).

Model 1 (`jhsaa_college.build_class`) ranked a class 1-200, dealt it into fixed
division shares, matched each senior to a program at the same relative standing and
derived the whole career from that match. The matching is what flattened it: fit
was `standing - strength`, and placement set those two equal on purpose, so nearly
every recruit started mid-lineup and climbed a spot or two a year. Every tracked
senior played all four years, nobody left or transferred, and a record followed the
program's prestige rather than the player.

This model keeps the architecture — deterministic, generated ONCE from a stable
seed, persisted whole, no college season simulated — and replaces what is inside:

  1. LEVEL, not rank. A senior's exit rating is read against the pooled classes
     before theirs and mapped onto the college game's own recruit distribution
     (`ncaa._talent_mean(0.5, "D2")`, `world.RECRUIT_TALENT_SD` — the national
     pool Jefferson's recruits were always a sample of). A deep class sends more
     players further; a thin one fewer.
  2. A DESTINATION THE PLAYER CHOOSES among programs that would take them:
     prestige, projected playing time, academics, geography, by aspiration. Who
     recruits whom follows the college game's radar (D1 chases the ceiling
     estimate, D2 reads current ability, D3/D4 blend). No division quota.
  3. A DEPTH CHART per program per season, generated from the program's own
     strength and roster cap on a seed that does not depend on the player — so two
     Jefferson alumni at one college meet the same team, and a teammate who is a
     freshman one year is a sophomore the next.
  4. A CAREER played through it one season at a time: development on one of five
     shapes (and it can go backwards), lineup position from where the player's
     level falls on that chart, singles and doubles separately, results against
     the opposing program's player at the same position, injuries, and at the end
     of each season a decision — stay, transfer, stop playing, leave.

‼️ NOTHING HERE READS A JHSAA SEASON OR BUILDS A ROSTER. The inputs are a
SNAPSHOT taken at graduation (`jhsaa_college.capture_snapshots`) or, for a class
that graduated before snapshots existed, the alumni index's exit rating alone —
the REDUCED path, which rolls what it cannot read.

‼️ EVERY CONSTANT BELOW IS A FIRST CANDIDATE. `scripts/jhsaa_college_validate.py`
measures what they produce; nothing was tuned to hit a target rate, and the model
is not the active one until the owner has seen those numbers
(`jhsaa_college.ACTIVE_MODEL`).
"""
from __future__ import annotations

import math
import random
from statistics import NormalDist

from . import ncaa

MODEL = 2

#: How many prior classes a senior's exit rating is read against.
REF_CLASSES = 5
#: The calibration point for how many seniors a gender send on — a class's own
#: count comes out above or below it. Also how deep each prior class is pooled.
TARGET_BOUND = 200
#: How far down a class the model looks at all (snapshot depth).
CANDIDATES = 320

_CLASS_YEARS = ("Fr", "So", "Jr", "Sr")
_COLLEGE_GENDER = {"boys": "men", "girls": "women"}
DIVISIONS = ("D1", "D2", "D4", "D3")

# --- level -------------------------------------------------------------------------
#: COLLEGE GROWTH IS THE COLLEGE GAME'S, RANKED BY THE HIGH-SCHOOL SIGNAL. A
#: recruit's growth from freshman to senior is what the college game's own class
#: maturity gives a player of their talent (`ncaa._CLASS_MATURITY`, about a tenth
#: of talent); how much of that a given senior gets is where their high-school
#: headroom (ceiling minus exit rating) stands IN THEIR CLASS — this share at the
#: bottom, rising by `HEADROOM_SPAN` to the top. The absolute high-school gap is
#: not used: the best seniors sit close to their high-school ceiling, and read
#: literally that made every Jefferson recruit look finished (measured: staffs
#: projected a median 2.7 points of growth against a teammate's 4.3, and no D1
#: program would take anybody).
HEADROOM_FLOOR, HEADROOM_SPAN = 0.35, 1.30
HEADROOM_MAX = 13.0
#: Share of total growth banked by the end of each season, by career shape. A
#: `regress` career goes backwards in absolute points (see `_levels`).
SHAPES = {
    "steady":  (0.05, 0.38, 0.70, 1.00),
    "early":   (0.30, 0.72, 0.90, 1.00),
    "late":    (0.00, 0.12, 0.50, 1.00),
    "stalled": (0.05, 0.15, 0.20, 0.20),
    "regress": (0.00, 0.05, -0.15, -0.35),
}
SHAPE_WEIGHTS = {"steady": 0.44, "early": 0.15, "late": 0.17, "stalled": 0.16,
                 "regress": 0.08}
#: A coach plays the upperclassman when it is close: how far a younger player's
#: level is marked down for LINEUP ORDER only (never for results).
SENIORITY = (1.0, 0.4, 0.0, 0.0)

# --- recruiting ---------------------------------------------------------------------
#: How a staff reads a recruit, as the share of the read that is PROJECTION
#: (arrival level plus the estimated headroom, as a senior) rather than today's
#: level — the college game's radar (CLAUDE.md §3b): D1 chases the projection,
#: D2 reads today, D3/D4 weigh both evenly. A transfer is read on today's level.
HYPE = {"D1": 1.00, "D2": 0.15, "D4": 0.50, "D3": 0.50}
HYPE_TRANSFER = 0.10
#: How far below its own roster's talent a program still recruits, in talent
#: points. D1 barely reaches (its seats go to the best of a national pool); D2
#: absorbs aggressively; D3 takes nearly anybody.
REACH = {"D1": 1.5, "D2": 5.0, "D4": 4.0, "D3": 9.0}
#: A program this far BELOW a player is not one they look at.
LOOK_DOWN = 7.0
#: What the level of tennis itself is worth to a player, beside prestige: a
#: program's roster talent on a 30-60 scale times this.
LEVEL_PRIDE = 1.80
#: What a senior is looking for. (prestige, playing time, academics, home).
ASPIRATIONS = {
    "prestige":     (0.52, (1.00, 0.35, 0.15, 1.0)),
    "playing_time": (0.18, (0.45, 1.00, 0.15, 1.0)),
    "academic":     (0.18, (0.50, 0.30, 1.00, 1.0)),
    "close":        (0.12, (0.60, 0.40, 0.15, 2.5)),
}
HOME_STATE, HOME_REGION, WARM = 0.05, 0.05, 0.06
CHOICE_NOISE = 0.12
#: A senior below everybody the reference classes sent can still walk on
#: somewhere: this chance right at the line, falling away below it.
WALK_ON = 0.20
#: At most this many of one class at one program (in-state programs take two).
PER_PROGRAM, PER_PROGRAM_HOME = 1, 1

# --- a season ------------------------------------------------------------------------
#: Level points per e-fold of the odds in a singles match; doubles is noisier.
WIN_SCALE, WIN_SCALE_D = 4.0, 5.5
#: Share of a starter's duals that produce a FINISHED singles match. D1/D2 stop at
#: the clinch; D3/D4 play every match out (the college game's own rule).
FINISH = {"D1": 0.82, "D2": 0.85, "D3": 1.0, "D4": 1.0}
CONFERENCE_SHARE = 0.55
INJURY_RATE = 0.07            # a season
INJURY_OUT = 0.30             # of injuries, the season is lost outright
#: Seats per entering cohort that are recruited at the program's level; the rest
#: of the roster is depth, this many points below.
CORE_PER_COHORT, DEPTH_DROP, SEAT_SD = 2, 4.0, 2.5

# --- after a season -------------------------------------------------------------------
#: By class year just finished (Fr, So, Jr): what a player who did not play does.
BENCH_TRANSFER = (0.24, 0.22, 0.10)
BENCH_QUIT = (0.12, 0.22, 0.30)
DOUBLES_ONLY_TRANSFER, DOUBLES_ONLY_QUIT = 0.08, 0.05
STAR_TRANSFER_UP = (0.12, 0.12, 0.04)
LEAVE_COLLEGE = 0.025
TURN_PRO = 0.25               # a D1 singles All-American with eligibility left

# --- honours -------------------------------------------------------------------------
#: HONOURS, BY DIVISION (owner decisions 2026-11): how many singles players and
#: doubles teams are honoured, and how far down a lineup an honour reaches —
#: (singles depth, doubles depth, deepest singles position, deepest doubles pair).
#:
#: D1 ALL-CONFERENCE IS DEEPER AND REACHES FURTHER DOWN THE LINEUP. A D1
#: conference names a first and a second team, and a strong No. 3 or No. 4 on a
#: good team makes it. Measured before this: zero All-Conference singles in ~450
#: D1 careers, because a Jefferson recruit is an average core player at the
#: program that signs them and only reaches the top two on a weak team, where the
#: record is not there. The lower divisions keep the depth they were measured at.
ALL_CONFERENCE = {"D1": (14, 7, 4, 2), "D2": (8, 4, 2, 1),
                  "D4": (8, 4, 2, 1), "D3": (8, 4, 2, 1)}
#: D1 ALL-AMERICAN IS UNCHANGED. The lower divisions name a deeper list, so a
#: genuinely strong player there — above all a D1-level player who is playing
#: down, by choice or by transfer — is likelier to be recognised nationally.
ALL_AMERICAN = {"D1": (20, 10, 2, 1), "D2": (40, 20, 2, 1),
                "D4": (40, 20, 2, 1), "D3": (40, 20, 2, 1)}
#: Results count beside level when a season is judged: points per unit of
#: winning percentage above the record an honoured player ordinarily has. The
#: line itself is built from LEVELS, so a record at that par adds nothing —
#: counted from .500 it handed every winning No. 1 a head start on a field that
#: had no results at all.
RESULT_WEIGHT = 6.0
RESULT_PAR = {"conf": 0.60, "div": 0.68}
#: And nobody is honoured for a season they lost: the least a record can be.
RESULT_MIN = {"conf": 0.55, "div": 0.65}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


class Context:
    """Everything one class's generation shares: the programs, their depth charts
    by season, and the alumni already on those teams. Built once per class."""

    def __init__(self, gender: str, salt: str, stored=None):
        self.gender, self.salt = gender, salt
        self.cg = _COLLEGE_GENDER[gender]
        self.programs = {}            # school -> Program
        self.by_div = {}              # division -> [Program] best level first
        self.by_conf = {}             # (division, conf) -> [Program]
        self.level = {}               # school -> roster talent, COMPRESSED
        self.raw = {}                 # school -> the raw mean seats are drawn round
        from .development import compress_talent
        self._compress = compress_talent
        for d in DIVISIONS:
            progs = list(ncaa.load_division(d, self.cg).programs)
            for p in progs:
                self.programs[p.school] = p
                # ‼️ ONE SCALE. The college game squashes every drawn talent above
                # a knee (`development.compress_talent`) — recruits and rosters
                # alike — so a program's level has to be read through the same
                # squash as the players measured against it. Compared raw, no
                # compressed recruit clears any D1 program's bar (measured: zero
                # D1 signees a class).
                self.raw[p.school] = ncaa._talent_mean(p.strength, d, self.cg)
                self.level[p.school] = compress_talent(self.raw[p.school], self.cg)
                self.by_conf.setdefault((d, p.conf_abbr), []).append(p)
            progs.sort(key=lambda p: (-self.level[p.school], p.school))
            self.by_div[d] = progs
        self._depth, self._lines = {}, {}
        # Alumni ALREADY written at a program in a season — {(college, year):
        # [{pid, cohort, slv, dlv, s_pos, d_pos}]}. They are part of the team a
        # later class walks into, and the positions they hold are theirs.
        self.stored = {k: list(v) for k, v in (stored or {}).items()}
        self.mid = {c: sum(ncaa._CLASS_MATURITY[c]) / 2.0 for c in _CLASS_YEARS}

    # -- the depth chart -----------------------------------------------------------
    def seats(self, prog, season: int) -> list:
        """The generated roster of `prog` in `season`: one dict per seat. A seat is
        (program, entry cohort, index), so its talent is the same every year it is
        on the roster and only its class year moves."""
        key = (prog.school, season)
        hit = self._depth.get(key)
        if hit is not None:
            return hit
        cap = ncaa.roster_cap(prog.division)
        per = [cap // 4 + (1 if i < cap % 4 else 0) for i in range(4)]
        base = self.raw[prog.school]
        out = []
        for age in range(4):                       # 0 = this season's freshmen
            cohort, cls = season - age, _CLASS_YEARS[age]
            # A cohort's size is the COHORT's, so it is the same every year it
            # is on the roster — and four consecutive cohorts always add up to
            # the cap. (Keyed on `cohort + age` it was keyed on the season:
            # every cohort got the same size and a ten-man roster came out as
            # eight or twelve.)
            for j in range(per[cohort % 4]):
                r = random.Random(f"{self.salt}|dc|{prog.school}|{self.cg}|{cohort}|{j}")
                # Drawn round the raw mean and squashed AT THE DRAW, exactly as the
                # college game builds a roster — keyed, so about one seat in five
                # hundred keeps its raw draw: the genuine national elite, who are
                # who an All-American has to be measured against.
                talent = self._compress(
                    r.gauss(base - (DEPTH_DROP if j >= CORE_PER_COHORT else 0.0),
                            SEAT_SD), self.cg,
                    key=("jf-dc", self.salt, prog.school, cohort, j))
                grow = r.random()                  # where in each class band they sit
                dbl = r.gauss(0.0, 1.8)
                lo, hi = ncaa._CLASS_MATURITY[cls]
                lvl = talent * (lo + (hi - lo) * grow)
                out.append({"cohort": cohort, "j": j, "s": lvl, "d": lvl + dbl})
        self._depth[key] = out
        return out

    def chart(self, prog, season: int) -> tuple:
        """`(singles, doubles)` level lists for an OPPONENT, best first."""
        key = ("chart", prog.school, season)
        hit = self._depth.get(key)
        if hit is None:
            seats = self.seats(prog, season)
            hit = (sorted((x["s"] for x in seats), reverse=True),
                   sorted((x["d"] for x in seats), reverse=True))
            self._depth[key] = hit
        return hit

    # -- honour lines ----------------------------------------------------------------
    def line(self, scope: tuple, season: int, doubles: bool) -> float:
        """The rating a player (or pair) has to reach to be honoured in `scope` —
        a conference `("conf", division, abbr)` or a division `("div", division)` —
        that season: the level of the Nth best No. 1/No. 2 player (or No. 1 pair)
        across its programs. Division-sensitive by construction."""
        key = (scope, season, doubles)
        hit = self._lines.get(key)
        if hit is not None:
            return hit
        progs = (self.by_conf.get((scope[1], scope[2]), []) if scope[0] == "conf"
                 else self.by_div[scope[1]])
        pool = []
        for p in progs:
            s, d = self.chart(p, season)
            if doubles:
                pool.append((d[0] + d[1]) / 2.0)
            else:
                pool += s[:2]
        pool.sort(reverse=True)
        n = (ALL_CONFERENCE if scope[0] == "conf" else ALL_AMERICAN)[scope[1]][
            1 if doubles else 0]
        hit = pool[min(n, len(pool)) - 1] if pool else 1e9
        self._lines[key] = hit
        return hit


# --- the senior ----------------------------------------------------------------------

def percentile(x: float, ref: list) -> float:
    """Where `x` stands among `ref` (ascending), 0-1, interpolated. Clamped just
    inside the ends so the best senior in years still maps to a finite level."""
    if not ref:
        return 0.5
    lo, hi, n = 0, len(ref), len(ref)
    while lo < hi:
        mid = (lo + hi) // 2
        if ref[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    if 0 < lo < n and ref[lo] > ref[lo - 1]:
        frac = (x - ref[lo - 1]) / (ref[lo] - ref[lo - 1])
        pos = lo - 1 + frac
    else:
        pos = float(lo)
    return max(0.5 / n, min(1.0 - 0.5 / n, pos / max(1, n - 1)))


def college_level(snap: dict, ref: list, gender: str, rng: random.Random) -> dict:
    """The senior on the COLLEGE scale: arrival level, true and estimated
    headroom, the doubles lean, academics. Reads what the snapshot has and rolls
    what it does not (the reduced path)."""
    from .development import compress_talent
    cg = _COLLEGE_GENDER[gender]
    from . import world
    mu, sd = world._recruit_talent_mean(cg), world.RECRUIT_TALENT_SD
    p = percentile(snap["ovr"], ref)
    talent = NormalDist(mu, sd).inv_cdf(p)
    talent = compress_talent(max(24.0, min(80.0, talent)), cg,
                             key=("jf-college", snap["pid"]))
    fr_lo, fr_hi = ncaa._CLASS_MATURITY["Fr"]
    arrive = talent * (fr_lo + fr_hi) / 2.0
    sr_lo, sr_hi = ncaa._CLASS_MATURITY["Sr"]
    base = talent * ((sr_lo + sr_hi) - (fr_lo + fr_hi)) / 2.0   # a recruit's Fr→Sr
    # `head_q` / `est_q`: where this senior's true and estimated headroom stand in
    # their class (set by `build_class`). The reduced path has neither and rolls.
    hq = snap.get("head_q")
    if hq is None:
        hq = rng.random()
    eq = snap.get("est_q")
    if eq is None:
        eq = max(0.0, min(1.0, hq + rng.gauss(0.0, 0.25)))
    head = min(HEADROOM_MAX, base * (HEADROOM_FLOOR + HEADROOM_SPAN * hq))
    est = min(HEADROOM_MAX, base * (HEADROOM_FLOOR + HEADROOM_SPAN * eq))
    # Doubles: the net game relative to the rest of the player, the style, and
    # what they actually did in high-school doubles when that is on record.
    lean = rng.gauss(0.0, 1.6)
    net = snap.get("net_edge")
    if net is not None:
        lean = 0.30 * net + rng.gauss(0.0, 1.0)
    if snap.get("style") in ("serve_and_volley", "all_court") or \
            snap.get("trait") in ("net_rusher", "chip_and_charge"):
        lean += 1.2
    dw, dl = snap.get("d_w"), snap.get("d_l")
    sw, sl = snap.get("s_w"), snap.get("s_l")
    if dw is not None and (dw + dl) >= 8 and sw is not None and (sw + sl) >= 8:
        lean += 4.0 * (dw / (dw + dl) - sw / (sw + sl))
    # A senior with a real record at a high flight has shown it; one with a
    # losing record there has shown that too. Small — the rating already knows
    # most of this.
    if sw is not None and (sw + sl) >= 10:
        arrive += 1.5 * (sw / (sw + sl) - 0.6)
    acad = snap.get("academic")
    if acad is None:
        acad = max(59, min(99, round(rng.gauss(79, 8))))
    return {"p": p, "talent": talent, "arrive": arrive, "head": head, "est": est,
            "lean": max(-6.0, min(6.0, lean)), "academic": acad,
            "domestic": snap.get("domestic", None)}


# --- destination ----------------------------------------------------------------------

def _projected_rank(ctx: Context, prog, season: int, level: float, age: int) -> int:
    s, _d = ctx.chart(prog, season)
    eff = level - SENIORITY[age]
    return 1 + sum(1 for x in s if x > eff)


def choose(ctx: Context, lv: dict, season: int, rng: random.Random, taken: dict,
           *, level: float, age: int = 0, aspiration: str | None = None,
           mode: str = "recruit", avoid: set | None = None):
    """The program this player joins for `season`, or None when nobody who would
    take them is somewhere they would go.

    `mode` "recruit" is a senior choosing; "opportunity" is a transfer looking for
    a place to play (the receiving staff reads today's level, not a projection);
    "up" is a transfer by a player who outgrew their program."""
    from . import recruit_economy
    weights = ASPIRATIONS[aspiration or "prestige"][1]
    if mode == "opportunity":
        weights = (0.30, 1.20, 0.15, 1.2)
    elif mode == "up":
        weights = (1.00, 0.45, 0.15, 0.8)
    best, best_u = None, None
    a_norm = (lv["academic"] - 59) / 40.0
    cls = _CLASS_YEARS[age]
    cur_t = level / ctx.mid[cls]                       # today, as roster talent
    proj_t = (level + lv["est"] * (1.0 - age / 4.0)) / ctx.mid["Sr"]
    for d in DIVISIONS:
        hype = HYPE[d] if mode == "recruit" else HYPE_TRANSFER
        seen = (1.0 - hype) * cur_t + hype * proj_t
        n_s = ncaa.lineup_size(d)
        for p in ctx.by_div[d]:
            if avoid and p.school in avoid:
                continue
            gap = seen - ctx.level[p.school]
            if gap < -REACH[d]:
                continue                           # this staff is not recruiting them
            if gap > LOOK_DOWN:
                continue                           # and they are not looking this far down
            cap = PER_PROGRAM_HOME if p.state == "JF" else PER_PROGRAM
            if mode == "recruit" and taken.get(p.school, 0) >= cap:
                continue
            # The one authority every placement pipeline asks (CLAUDE.md).
            if ncaa.us_only_program(p.school) and lv["domestic"] is not True:
                continue
            # D4 admits on academics — the division's whole design.
            if d == "D4" and lv["academic"] < recruit_economy.d4_academic_min(
                    p, 0, ctx.salt):
                continue
            # A senior weighs the CAREER, not the freshman year: where they expect
            # to stand as a junior, on their own estimate of how much they will
            # grow. A transfer weighs next season.
            if mode == "recruit":
                rank = _projected_rank(ctx, p, season, level + 0.6 * lv["est"], 2)
            else:
                rank = _projected_rank(ctx, p, season, level, age)
            # Playing time SATURATES: being the No. 1 is not worth more than being
            # a sure starter, or everybody would pick the weakest team they can find.
            # A player who wants to LEAD a team sets the bar at the top three.
            safe = (0.3 if aspiration == "playing_time" else 0.6) * n_s
            pt = 1.0 if rank <= safe else max(-0.6, 1.0 - (rank - safe) / (n_s + 1 - safe))
            if mode == "up" and rank > 4:
                continue
            home = (HOME_STATE if p.state == "JF" else 0.0) \
                + HOME_REGION * ncaa.region_proximity("W", p.region) \
                + (WARM if p.state in ncaa.WARM_STATES else 0.0)
            u = (weights[0] * (0.15 + p.prestige)
                 + LEVEL_PRIDE * (ctx.level[p.school] - 30.0) / 30.0
                 + weights[1] * ncaa_play_weight() * pt
                 + weights[2] * 0.5 * (1.0 - abs(p.academics - a_norm))
                 + weights[3] * home
                 - CHOICE_NOISE * math.log(-math.log(max(1e-12, rng.random()))))
            if best_u is None or u > best_u:
                best, best_u = p, u
    return best


def ncaa_play_weight() -> float:
    """Playing time's weight beside prestige — the college game's own number
    (`world.PLAY_TIME_WEIGHT`, kept BELOW prestige by owner rule), scaled so an
    aspiration weight of 1.0 means a player who puts it first."""
    from . import world
    return world.PLAY_TIME_WEIGHT / 0.35


# --- a season ---------------------------------------------------------------------------

def _roster(ctx: Context, prog, season: int, pid: str, cohort: int) -> tuple:
    """The team this player is on: the generated seats, less the seat they took
    (the weakest of their own entering cohort), plus the alumni already there."""
    seats = ctx.seats(prog, season)
    mine = [x for x in seats if x["cohort"] == cohort]
    drop = min(mine, key=lambda x: x["s"]) if mine else None
    mates = [x for x in seats if x is not drop]
    others = [a for a in ctx.stored.get((prog.school, season), []) if a["pid"] != pid]
    return mates, others


def _rank(level: float, mates: list, others: list, mkey: str, okey: str,
          age: int) -> int:
    """Where `level` falls on the team's ladder — generated teammates and the
    alumni already there alike. Seniority marks a younger player down for ORDER
    only."""
    eff = level - SENIORITY[age]
    return 1 + sum(1 for x in mates if x[mkey] > eff) \
        + sum(1 for a in others if a.get(okey, -1e9) > eff)


def play_season(ctx: Context, prog, season: int, age: int, pid: str, cohort: int,
                s_lvl: float, d_lvl: float, rng: random.Random, *,
                injured: str | None = None) -> dict:
    """One season at `prog`: where the player stood on the depth chart and what
    they did there, singles and doubles separately."""
    d = prog.division
    fmt = ncaa.dual_format(d)
    n_s, n_d = fmt.n_singles, fmt.n_doubles
    mates, others = _roster(ctx, prog, season, pid, cohort)
    s_rank = _rank(s_lvl, mates, others, "s", "slv", age)
    # A singles position already on the record belongs to the alumnus who holds
    # it: careers are written once, so a later arrival steps past it.
    held = {a["s_pos"] for a in others if a.get("s_pos")}
    while s_rank in held:
        s_rank += 1
    d_rank = _rank(d_lvl, mates, others, "d", "dlv", age)
    s_pos = s_rank if s_rank <= n_s else None
    d_pair = (d_rank + 1) // 2 if d_rank <= 2 * n_d else None
    duals = rng.randint(20, 26)
    share = 1.0
    if injured == "out":
        share = 0.0
    elif injured == "part":
        share = rng.uniform(0.15, 0.55)
    conf = ctx.by_conf.get((d, prog.conf_abbr), [prog])
    div = ctx.by_div[d]
    here = div.index(prog)
    near = div[max(0, here - len(div) // 5):here + len(div) // 5 + 1]

    def opponent():
        pool = conf if (rng.random() < CONFERENCE_SHARE and len(conf) > 1) else near
        for _ in range(4):
            o = rng.choice(pool)
            if o is not prog:
                return o
        return prog

    s_w = s_l = d_w = d_l = 0
    if s_pos:
        n = round(duals * share * FINISH[d])
    else:                                          # a spot start when somebody sits
        n = round(rng.randint(0, 5) * share) if s_rank <= n_s + 3 else 0
    spot = s_pos or n_s
    for _ in range(n):
        opp = ctx.chart(opponent(), season)[0]
        o = opp[min(spot, len(opp)) - 1]
        if rng.random() < _sigmoid((s_lvl - o) / WIN_SCALE):
            s_w += 1
        else:
            s_l += 1
    if d_pair:
        n = round(duals * share)
    else:
        n = round(rng.randint(0, 4) * share) if d_rank <= 2 * n_d + 3 else 0
    pair = d_pair or n_d
    # The partner is whoever sits beside them on the doubles ladder.
    dl = sorted([x["d"] for x in mates] + [a.get("dlv", 0.0) for a in others],
                reverse=True)
    i = min(len(dl) - 1, max(0, 2 * pair - 2))
    mine = (d_lvl + dl[i]) / 2.0
    for _ in range(n):
        opp = ctx.chart(opponent(), season)[1]
        j = min(len(opp) - 2, 2 * pair - 2)
        o = (opp[j] + opp[j + 1]) / 2.0
        if rng.random() < _sigmoid((mine - o) / WIN_SCALE_D):
            d_w += 1
        else:
            d_l += 1
    honors = []
    conf_rule, div_rule = ALL_CONFERENCE[d], ALL_AMERICAN[d]
    # ‼️ ALL-CONFERENCE COMES FIRST, AT EVERY LEVEL (owner rule 2026-11): a player
    # is only CONSIDERED for All-American in a season they made All-Conference in
    # that same discipline. It is a gate, not a coincidence of two thresholds —
    # the two lines are built from different fields (a conference's, a
    # division's), so without the gate a player in a strong conference could
    # clear the national line and miss their own.
    if s_pos and (s_w + s_l) >= 12:
        pct = s_w / (s_w + s_l)
        if s_pos <= conf_rule[2] and pct >= RESULT_MIN["conf"] and \
                s_lvl + RESULT_WEIGHT * (pct - RESULT_PAR["conf"]) >= \
                ctx.line(("conf", d, prog.conf_abbr), season, False):
            honors.append("All-Conference")
            if s_pos <= div_rule[2] and pct >= RESULT_MIN["div"] and \
                    s_lvl + RESULT_WEIGHT * (pct - RESULT_PAR["div"]) >= \
                    ctx.line(("div", d), season, False):
                honors.append("All-American")
    if d_pair and (d_w + d_l) >= 12:
        pct = d_w / (d_w + d_l)
        if d_pair <= conf_rule[3] and pct >= RESULT_MIN["conf"] and \
                mine + RESULT_WEIGHT * (pct - RESULT_PAR["conf"]) >= \
                ctx.line(("conf", d, prog.conf_abbr), season, True):
            honors.append("All-Conference (doubles)")
            if d_pair <= div_rule[3] and pct >= RESULT_MIN["div"] and \
                    mine + RESULT_WEIGHT * (pct - RESULT_PAR["div"]) >= \
                    ctx.line(("div", d), season, True):
                honors.append("All-American (doubles)")
    role = ("out" if injured == "out" else "starter" if s_pos else
            "doubles" if d_pair else "reserve")
    return {"year": season, "class": _CLASS_YEARS[age], "college": prog.school,
            "division": d, "conf": prog.conf_abbr, "role": role,
            "s_pos": s_pos, "s_w": s_w, "s_l": s_l,
            "d_pair": d_pair, "d_w": d_w, "d_l": d_l,
            "honors": honors, "injury": injured,
            "slv": round(s_lvl, 2), "dlv": round(d_lvl, 2),
            # Model 1's keys, so a page written for it still reads a season.
            "pos": s_pos, "w": s_w, "l": s_l}


# --- a career ----------------------------------------------------------------------------

def _levels(lv: dict, shape: str, rng: random.Random) -> list:
    """The player's own level at the end of... each of four seasons. `regress`
    loses ground in absolute points; every shape wobbles year to year."""
    out = []
    for y in range(4):
        f = SHAPES[shape][y]
        grown = f * lv["head"] if f >= 0 else f * 6.0
        out.append(lv["arrive"] + grown + rng.gauss(0.0, 0.6))
    return out


def career(ctx: Context, snap: dict, lv: dict, taken: dict) -> dict | None:
    """One senior's whole college career, or None when they do not play in
    college. Its own rng stream, keyed on the pid."""
    rng = random.Random(f"{ctx.salt}|jf-college-v2|{snap['pid']}")
    names = list(ASPIRATIONS)
    aspiration = rng.choices(names, weights=[ASPIRATIONS[k][0] for k in names])[0]
    # Not everybody who could play in college does. The further down the class,
    # the likelier tennis ends at graduation.
    if rng.random() < 0.03 + 0.14 * (1.0 - lv["p"]) ** 2:
        return None
    first = snap["grad_year"] + 1
    prog = choose(ctx, lv, first, rng, taken, level=lv["arrive"], aspiration=aspiration)
    if prog is None:
        return None
    taken[prog.school] = taken.get(prog.school, 0) + 1
    names = list(SHAPE_WEIGHTS)
    shape = rng.choices(names, weights=[SHAPE_WEIGHTS[k] for k in names])[0]
    levels = _levels(lv, shape, rng)
    seasons, stints, transfers = [], [], []
    status, knock, cohort = "graduated", 0.0, first
    cause = None                       # why a career ended early, when it did
    stint = {"college": prog.school, "division": prog.division,
             "conf": prog.conf_abbr, "from": first}
    for age in range(4):
        season = first + age
        injured = None
        if rng.random() < INJURY_RATE:
            injured = "out" if rng.random() < INJURY_OUT else "part"
        s_lvl = levels[age] - knock
        if injured:                                # hurt players lose ground
            knock += rng.uniform(0.0, 2.5)
        s = play_season(ctx, prog, season, age, snap["pid"], cohort,
                        s_lvl, s_lvl + lv["lean"], rng, injured=injured)
        seasons.append(s)
        if age == 3:
            break
        # --- what they do next ---
        if "All-American" in s["honors"] and prog.division == "D1" \
                and rng.random() < TURN_PRO:
            status, cause = "turned_pro", "professional"
            break
        if injured == "out" and rng.random() < 0.18:
            status, cause = "injury_ended", "injury"
            break
        if rng.random() < LEAVE_COLLEGE:
            status, cause = "left_college", "personal"
            break
        move = None
        if s["role"] == "reserve":
            r = rng.random()
            if r < BENCH_TRANSFER[age]:
                move = "opportunity"
            elif r < BENCH_TRANSFER[age] + BENCH_QUIT[age]:
                # Hurt and then not playing is a different story from simply
                # never getting on court.
                status, cause = "left_team", ("injury" if injured else "no_role")
                break
        elif s["role"] == "doubles":
            r = rng.random()
            if r < DOUBLES_ONLY_TRANSFER:
                move = "opportunity"
            elif r < DOUBLES_ONLY_TRANSFER + DOUBLES_ONLY_QUIT:
                status, cause = "left_team", "doubles_only"
                break
        elif s["s_pos"] and s["s_pos"] <= 2 and (s["s_w"] + s["s_l"]) >= 12 \
                and s["s_w"] / (s["s_w"] + s["s_l"]) >= 0.65 \
                and rng.random() < STAR_TRANSFER_UP[age]:
            move = "up"
        if move:
            dest = choose(ctx, lv, season + 1, rng, taken, level=levels[age] - knock,
                          age=age + 1, mode=move, avoid={prog.school})
            # A move has to be a move: up means a better program, opportunity
            # means one where they would actually play.
            if dest is not None and (
                    (move == "up" and dest.prestige > prog.prestige + 0.03) or
                    (move == "opportunity" and _projected_rank(
                        ctx, dest, season + 1, levels[age] - knock, age + 1)
                     <= ncaa.lineup_size(dest.division))):
                stint["to"] = season
                stints.append(stint)
                transfers.append({"after": _CLASS_YEARS[age], "year": season,
                                  "from": prog.school, "to": dest.school,
                                  "reason": move, "role_before": s["role"]})
                prog = dest
                # They join as a transfer; the seat they take is in the cohort
                # that entered with them.
                stint = {"college": prog.school, "division": prog.division,
                         "conf": prog.conf_abbr, "from": season + 1}
    stint["to"] = seasons[-1]["year"]
    stints.append(stint)
    for t in transfers:
        after = next((x for x in seasons if x["year"] == t["year"] + 1), None)
        t["role_after"] = after["role"] if after else None
    departure = None
    if status != "graduated":
        last = seasons[-1]
        departure = {"kind": status, "cause": cause, "after": last["class"],
                     "year": last["year"], "college": last["college"],
                     "role": last["role"]}
    return _finish(snap, lv, seasons, stints, transfers, status, shape, aspiration,
                   departure)


def _arc(seasons, transfers, status, lv, shape) -> str:
    """What kind of career it turned out to be — read off what happened, never
    assigned in advance."""
    starts = [s for s in seasons if s["role"] == "starter"]
    dbl_only = [s for s in seasons if s["role"] == "doubles"]
    # A career that ended early is named for HOW it ended — the four are
    # different stories and are never folded into one "departure".
    if status != "graduated":
        return status
    if transfers:
        before = [s for s in seasons if s["year"] <= transfers[0]["year"]]
        after = [s for s in seasons if s["year"] > transfers[0]["year"]]
        b = min((s["s_pos"] for s in before if s["s_pos"]), default=99)
        a = min((s["s_pos"] for s in after if s["s_pos"]), default=99)
        return "transfer_success" if a < b or (b == 99 and a < 99) else "transfer"
    if sum(1 for s in seasons if s["injury"]) >= 1 and len(starts) <= 2:
        return "injury_affected"
    d_best = min((s["d_pair"] for s in seasons if s["d_pair"]), default=None)
    s_best = min((s["s_pos"] for s in seasons if s["s_pos"]), default=None)
    if (len(starts) <= 1 and len(dbl_only) >= 2) or (
            d_best is not None and d_best <= 2
            and (s_best is None or s_best >= 2 * d_best + 3)):
        return "doubles_specialist"
    if len(starts) <= 1:
        return "reserve"
    first, last = seasons[0], seasons[-1]
    if first["s_pos"] and first["s_pos"] <= 2 and first["s_w"] >= first["s_l"]:
        return "immediate_star"
    if not first["s_pos"] and last["s_pos"] and last["s_pos"] <= 3:
        return "late_developer"
    pos = [s["s_pos"] for s in seasons if s["s_pos"]]
    if shape in ("stalled", "regress") and len(pos) >= 2 and pos[-1] >= pos[0]:
        return "stalled_prospect"
    return "steady_contributor"


def _finish(snap, lv, seasons, stints, transfers, status, shape, aspiration,
            departure=None) -> dict:
    s_pos = [s["s_pos"] for s in seasons if s["s_pos"]]
    d_pos = [s["d_pair"] for s in seasons if s["d_pair"]]
    tally = {}
    for s in seasons:
        for h in s["honors"]:
            tally[h] = tally.get(h, 0) + 1
    order = ["All-American", "All-American (doubles)", "All-Conference",
             "All-Conference (doubles)"]
    honors = [f"{h} ×{tally[h]}" if tally[h] > 1 else h for h in order if h in tally]
    first = stints[0]
    return {
        "model": MODEL,
        "pid": snap["pid"], "name": snap["name"], "gender": snap["gender"],
        "hs": snap["hs"], "hs_ident": snap.get("hs_ident", ""),
        "grad_year": snap["grad_year"], "rank": snap["rank"],
        "hs_ovr": round(snap["ovr"], 1),
        "reduced": snap.get("ceiling") is None,
        "level": {"arrive": round(lv["arrive"], 2), "head": round(lv["head"], 2),
                  "est": round(lv["est"], 2), "doubles_lean": round(lv["lean"], 2),
                  "talent": round(lv["talent"], 2), "p": round(lv["p"], 4)},
        "aspiration": aspiration, "shape": shape,
        "college": first["college"], "division": first["division"],
        "conf": first["conf"],
        "colleges": stints, "transfers": transfers, "status": status,
        # HOW A CAREER ENDED EARLY, kept apart (owner decision 2026-11): a
        # transfer is a move and is in `transfers`; `departure` is one of
        # left_team (still enrolled, no longer playing), left_college,
        # injury_ended, turned_pro — with the class year it followed and why.
        "departure": departure,
        "seasons": seasons, "years": len(seasons),
        "arc": _arc(seasons, transfers, status, lv, shape),
        "s_peak": min(s_pos) if s_pos else None,
        "d_peak": min(d_pos) if d_pos else None,
        "s_w": sum(s["s_w"] for s in seasons), "s_l": sum(s["s_l"] for s in seasons),
        "d_w": sum(s["d_w"] for s in seasons), "d_l": sum(s["d_l"] for s in seasons),
        "honors": honors,
        # Model 1's summary keys (singles), so the page built for it still reads.
        "peak": min(s_pos) if s_pos else None,
        "w": sum(s["s_w"] for s in seasons), "l": sum(s["s_l"] for s in seasons),
    }


# --- a class -------------------------------------------------------------------------------

def build_class(snaps: list, gender: str, grad_year: int, salt: str,
                ref: list | None = None, stored: dict | None = None) -> list:
    """The careers of one graduating class. `snaps` is the class's candidates
    (snapshot dicts, any order); `ref` the pooled exit ratings of the classes
    before it, ascending (None → the class is read against itself, which is what
    a save's first class has). Returns the rows of those who played in college —
    HOW MANY is an outcome, not an input."""
    cands = sorted(snaps, key=lambda s: (-s["ovr"], s["pid"]))[:CANDIDATES]
    for i, s in enumerate(cands, 1):
        s.update(rank=i, gender=gender, grad_year=grad_year)
    if not ref:
        ref = sorted(s["ovr"] for s in cands[:TARGET_BOUND])
    # Headroom is read as a STANDING within the class (see `HEADROOM_FLOOR`).
    for key, src in (("head_q", "ceiling"), ("est_q", "pot")):
        have = sorted(s[src] - s["ovr"] for s in cands if s.get(src) is not None)
        for s in cands:
            if s.get(src) is not None and len(have) > 1:
                s[key] = percentile(s[src] - s["ovr"], have)
    ctx = Context(gender, salt, stored)
    floor = ref[0]
    taken, rows = {}, []
    for s in cands:
        rng = random.Random(f"{salt}|jf-college-v2-lvl|{s['pid']}")
        # Below everybody the last five classes sent, a senior is a walk-on
        # hopeful at best — and less likely the further below they are.
        if s["ovr"] < floor and rng.random() > WALK_ON * math.exp(-(floor - s["ovr"]) / 1.5):
            continue
        lv = college_level(s, ref, gender, rng)
        row = career(ctx, s, lv, taken)
        if row is not None:
            rows.append(row)
            # Classmates share teams too: everybody generated after this player
            # walks into a roster that has them on it.
            for x in row["seasons"]:
                ctx.stored.setdefault((x["college"], x["year"]), []).append(
                    {"pid": row["pid"], "slv": x["slv"], "dlv": x["dlv"],
                     "s_pos": x["s_pos"], "d_pair": x["d_pair"]})
    for i, r in enumerate(rows, 1):
        r["hs_rank"], r["rank"] = r["rank"], i
    return rows

"""Team-shape analytics: the "how are they good" layer on top of the raw
exports, one level past a plain win-loss record or TOSS.

Design rules (owner spec, first-pass library):
  - Every derived stat stores its COMPONENTS alongside the number, not just
    the finished metric — an analyst should be able to reproduce or challenge
    it without reverse-engineering the calc. See TeamMetrics fields below.
  - Card weights (how many singles/doubles lines a format plays) are
    CONFIGURABLE, not hard-coded — see CARD_WEIGHTS. Different divisions/
    classifications play different shapes (see the game's own per-division
    dual-format rule); this module defaults to the JHSAA regular (5S/2D) vs
    State (1S/4D) shapes because that's the data on hand, and is written so a
    per-division weight table can be dropped in later without touching the
    formulas.
  - This is a first pass, not the full 70-metric wishlist: it computes the
    raw substrate (S%/D%, per-flight win%, line/game share) plus the first
    tier of derived stats (RCI/SCI/Fmt, Doubles Reliance/Balance, State Dual
    Win Probability, opponent-quartile splits, close-match record) and flags
    statistical extremes as storylines. Everything else in the wishlist slots
    in later against this same substrate.
"""
from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

CARD_WEIGHTS = {
    "jhsaa": {"regular": (5, 2), "state": (1, 4)},
    # College dual shape is per-division (see ncaa.DUAL_FORMATS in the game) —
    # not modeled per-division here yet; CLASSIC 6+3 stands in until a
    # division-aware weight table is added.
    "college": {"regular": (6, 3), "state": (6, 3)},
}


def _is_singles(slot: str) -> bool:
    return slot.upper().startswith("S")


def _games_from_score_string(score: str) -> tuple[int, int]:
    """JHSAA lines.csv stores '6-0, 6-1' style set scores. Sum games across
    sets for a rough game-share input. Retirements/odd strings degrade to 0-0
    rather than raising — this is a descriptive stat, not a source of truth."""
    won = lost = 0
    for s in (score or "").split(","):
        s = s.strip()
        if "-" not in s:
            continue
        a, _, b = s.partition("-")
        try:
            won += int(a.strip())
            lost += int(b.strip())
        except ValueError:
            continue
    return won, lost


def _sets_from_score_string(score: str) -> tuple[int, int]:
    """Sets won/lost for the line's own side, parsed from the same '6-0, 6-1'
    string. JHSAA-only — college's export gives one aggregate game count per
    line, no set-level detail, so set share only ever renders for JHSAA."""
    won = lost = 0
    for s in (score or "").split(","):
        s = s.strip()
        if "-" not in s:
            continue
        a, _, b = s.partition("-")
        try:
            ai, bi = int(a.strip()), int(b.strip())
        except ValueError:
            continue
        if ai > bi:
            won += 1
        elif bi > ai:
            lost += 1
    return won, lost


def binom_at_least(n: int, p: float, k: int) -> float:
    """P(Binomial(n, p) >= k)."""
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))


def binom_pmf(n: int, p: float, k: int) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def mixed_win_dist(ns: int, pS: float, nd: int, pD: float) -> dict:
    """Distribution of total lines won when ns independent singles lines each
    land at rate pS and nd independent doubles lines each land at rate pD —
    the convolution of two binomials. Returns {total_won: probability}."""
    from collections import defaultdict as _dd
    dist = _dd(float)
    for si in range(ns + 1):
        ps = binom_pmf(ns, pS, si)
        if ps <= 0:
            continue
        for di in range(nd + 1):
            pd = binom_pmf(nd, pD, di)
            if pd <= 0:
                continue
            dist[si + di] += ps * pd
    return dict(dist)


def dual_win_prob(ns: int, pS: float, nd: int, pD: float) -> float:
    """P(win a dual of this shape) = P(win more than half the lines)."""
    total = ns + nd
    dist = mixed_win_dist(ns, pS, nd, pD)
    need = total // 2 + 1
    return sum(p for k, p in dist.items() if k >= need)


@dataclass
class TeamMetrics:
    program_id: str
    scope_id: str
    name: str
    family: str

    sp: int = 0; sw: int = 0
    dp: int = 0; dw: int = 0
    flight: dict = field(default_factory=dict)     # slot -> {"played": n, "won": n, "pct": f}

    lines_played: int = 0
    lines_won: int = 0
    line_share: float = 0.0
    games_won: int = 0
    games_lost: int = 0
    game_share: float | None = None

    duals: int = 0
    dual_wins: int = 0
    close_duals: int = 0            # decided by 1 point (proxy for a 2-1/3-2 dogfight)
    close_wins: int = 0

    avg_opp_power: float | None = None
    quartile_record: dict = field(default_factory=dict)   # "Q1".."Q4" -> {"w":..,"l":..}
    # league play = JHSAA district / college conference (the regular-season
    # league schedule, NOT a "conference tournament" postseason round) vs
    # everything scheduled outside it (JHSAA non-district / college non-conf).
    league_record: dict = field(default_factory=dict)      # "league"/"non_league" -> {"w","l"}
    postseason: list = field(default_factory=list)

    volatility: float | None = None    # stdev of per-dual line share
    floor: float | None = None         # 25th percentile of per-dual line share
    ceiling: float | None = None       # 75th percentile of per-dual line share

    blowout_wins: int = 0              # wins by 80%+ of that dual's lines
    resistance_losses: int = 0         # losses where the team still won >=40% of lines

    singles_games_won: int = 0; singles_games_lost: int = 0
    doubles_games_won: int = 0; doubles_games_lost: int = 0
    singles_sets_won: int = 0; singles_sets_lost: int = 0
    doubles_sets_won: int = 0; doubles_sets_lost: int = 0

    expected_wins: float | None = None   # sum of pre-dual win probabilities (power-based)
    upsets: int = 0; upset_opportunities: int = 0    # wins/opportunities where team was <35% favorite
    upset_value: float = 0.0             # Sigma max(0, 0.5 - pre-match win prob) over wins
    bad_loss_value: float = 0.0          # Sigma max(0, pre-match win prob - 0.5) over losses
    elite_win_share_num: int = 0         # wins vs top-decile-power opponents
    elite_win_share_den: int = 0         # all wins with an opponent power on file

    @property
    def s_pct(self) -> float | None:
        return self.sw / self.sp if self.sp else None

    @property
    def d_pct(self) -> float | None:
        return self.dw / self.dp if self.dp else None

    def card_index(self, family: str, kind: str) -> float | None:
        """RCI/SCI: (singles_lines*pS + doubles_lines*pD) / total_lines for the
        named card shape ('regular' or 'state')."""
        pS, pD = self.s_pct, self.d_pct
        if pS is None or pD is None:
            return None
        ns, nd = CARD_WEIGHTS.get(family, CARD_WEIGHTS["jhsaa"])[kind]
        return (ns * pS + nd * pD) / (ns + nd)

    @property
    def fmt_lift(self) -> float | None:
        """State-card expectation minus regular-card expectation, in percentage
        points. Positive = the postseason format shape favors this team."""
        sci = self.card_index(self.family, "state")
        rci = self.card_index(self.family, "regular")
        if sci is None or rci is None:
            return None
        return (sci - rci) * 100

    @property
    def doubles_reliance(self) -> float | None:
        if self.s_pct is None or self.d_pct is None:
            return None
        return (self.d_pct - self.s_pct) * 100

    @property
    def balance(self) -> float | None:
        if self.s_pct is None or self.d_pct is None:
            return None
        return 1 - abs(self.d_pct - self.s_pct)

    def state_dual_win_prob(self, family: str) -> float | None:
        """P(win a neutral State-format dual) under equal-opponent, independent-
        court assumptions: needs 3 of 5 courts in a 1S/4D card."""
        if family != "jhsaa":
            return None
        pS, pD = self.s_pct, self.d_pct
        if pS is None or pD is None:
            return None
        # win = take S + at least 2 of 4 doubles, OR lose S + at least 3 of 4
        return pS * binom_at_least(4, pD, 2) + (1 - pS) * binom_at_least(4, pD, 3)

    @property
    def close_win_pct(self) -> float | None:
        return self.close_wins / self.close_duals if self.close_duals else None

    # ---- tier 2: what happens under the state card, in more detail ----

    def format_dependency(self, family: str) -> float | None:
        """FD = Fmt / RCI — normalizes the format lift by underlying quality.
        The same +15pp lift means more on a .50 team than an .85 one."""
        fmt = self.fmt_lift
        rci = self.card_index(family, "regular")
        if fmt is None or not rci:
            return None
        return (fmt / 100) / rci

    def regular_dual_win_prob(self, family: str) -> float | None:
        if self.s_pct is None or self.d_pct is None:
            return None
        ns, nd = CARD_WEIGHTS.get(family, CARD_WEIGHTS["jhsaa"])["regular"]
        return dual_win_prob(ns, self.s_pct, nd, self.d_pct)

    def format_win_prob_lift(self, family: str) -> float | None:
        """FWPL = P(win the State-card dual) - P(win the regular-card dual).
        Stronger signal than raw Fmt because duals have a win THRESHOLD —
        moving court share from .55 to .65 can flip a lot more duals than
        moving .30 to .40 does."""
        if family != "jhsaa":
            return None
        swp = self.state_dual_win_prob(family)
        rwp = self.regular_dual_win_prob(family)
        if swp is None or rwp is None:
            return None
        return swp - rwp

    def state_score_profile(self, family: str) -> dict | None:
        """Distribution of State-card (1S/4D) final margins: {lines_won: prob}."""
        if family != "jhsaa" or self.s_pct is None or self.d_pct is None:
            return None
        return mixed_win_dist(1, self.s_pct, 4, self.d_pct)

    def three_court_prob(self, family: str) -> float | None:
        """P(exactly 3 of 5 State courts) — high P3 = a knife-edge team, lots
        of plausible 3-2s rather than blowouts either way."""
        profile = self.state_score_profile(family)
        return profile.get(3) if profile else None

    def sweep_prob(self, family: str) -> float | None:
        """P(5-0 sweep) under the State card."""
        if family != "jhsaa" or self.s_pct is None or self.d_pct is None:
            return None
        return self.s_pct * (self.d_pct ** 4)

    def expected_state_margin(self, family: str) -> float | None:
        """ESM = expected State lines won minus expected lines lost = 5*(2*SCI-1).
        +1.4 reads immediately as "roughly a 3.2-1.8 card"."""
        sci = self.card_index(family, "state")
        if sci is None:
            return None
        return 5 * (2 * sci - 1)

    @property
    def dominance_margin(self) -> float | None:
        """DM = (lines won - lines lost) / lines played. -1..+1; much better
        than dual record alone for spotting teams that win comfortably."""
        if not self.lines_played:
            return None
        return (self.lines_won - (self.lines_played - self.lines_won)) / self.lines_played

    @property
    def singles_game_share(self) -> float | None:
        t = self.singles_games_won + self.singles_games_lost
        return self.singles_games_won / t if t else None

    @property
    def doubles_game_share(self) -> float | None:
        t = self.doubles_games_won + self.doubles_games_lost
        return self.doubles_games_won / t if t else None

    @property
    def singles_set_share(self) -> float | None:
        t = self.singles_sets_won + self.singles_sets_lost
        return self.singles_sets_won / t if t else None

    @property
    def doubles_set_share(self) -> float | None:
        t = self.doubles_sets_won + self.doubles_sets_lost
        return self.doubles_sets_won / t if t else None

    @property
    def line_conversion(self) -> float | None:
        """LineWin% - GameShare, both 0-1. Positive = the team wins close lines
        and/or loses ugly ones; negative = wins ugly and loses close ones.
        Descriptive, not yet claimed as a repeatable skill."""
        if self.game_share is None:
            return None
        return self.line_share - self.game_share

    def _numbered_flight(self, prefix: str) -> list[tuple[int, float, int]]:
        """[(flight_number, win_pct, played)] for slots starting with prefix
        (e.g. 'S' -> S1, S2, ...), sorted by flight number. Skips slots with no
        trailing digit (shouldn't happen in this schema) or zero appearances."""
        out = []
        for slot, fl in self.flight.items():
            if not slot.upper().startswith(prefix) or fl["pct"] is None:
                continue
            digits = "".join(c for c in slot if c.isdigit())
            if digits:
                out.append((int(digits), fl["pct"], fl["played"]))
        return sorted(out)

    @property
    def singles_flight_curve(self) -> list[tuple[int, float, int]]:
        return self._numbered_flight("S")

    @property
    def doubles_flight_curve(self) -> list[tuple[int, float, int]]:
        return self._numbered_flight("D")

    @staticmethod
    def _slope(points: list[tuple[int, float, int]]) -> float | None:
        """Least-squares slope of win% against flight number. Sign flipped so
        larger = deeper (less drop-off top to bottom), matching the wishlist's
        framing; strongly negative in the raw sense (steep decline) becomes a
        strongly negative "depth" score here too — 0 = perfectly flat/deep."""
        if len(points) < 2:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        denom = sum((x - mx) ** 2 for x in xs)
        if denom == 0:
            return None
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        return num / denom   # already "larger (less negative) = deeper"

    @property
    def singles_depth_slope(self) -> float | None:
        return self._slope(self.singles_flight_curve)

    @property
    def doubles_depth_slope(self) -> float | None:
        return self._slope(self.doubles_flight_curve)

    @property
    def top_end_index(self) -> float | None:
        """Top = .6*S1% + .4*D1% — who has stars."""
        s1 = self.flight.get("S1", {}).get("pct")
        d1 = self.flight.get("D1", {}).get("pct")
        if s1 is None and d1 is None:
            return None
        if d1 is None:
            return s1
        if s1 is None:
            return d1
        return 0.6 * s1 + 0.4 * d1

    @property
    def depth_index(self) -> float | None:
        """Mean win% across the lower flights actually on record (S3+, D2+) —
        who survives when the match needs more than the stars."""
        vals = [fl["pct"] for slot, fl in self.flight.items() if fl["pct"] is not None and (
            (slot.upper().startswith("S") and slot[1:].isdigit() and int(slot[1:]) >= 3) or
            (slot.upper().startswith("D") and slot[1:].isdigit() and int(slot[1:]) >= 2))]
        return sum(vals) / len(vals) if vals else None

    @property
    def star_dependence(self) -> float | None:
        """StarDep = TopEnd - Depth. Big positive = one or two players carrying
        the program; near zero/negative = unusually even quality."""
        top, depth = self.top_end_index, self.depth_index
        if top is None or depth is None:
            return None
        return top - depth

    @property
    def blowout_rate(self) -> float | None:
        return self.blowout_wins / self.dual_wins if self.dual_wins else None

    @property
    def resistance_rate(self) -> float | None:
        losses = self.duals - self.dual_wins
        return self.resistance_losses / losses if losses else None

    @property
    def record_luck(self) -> float | None:
        """Actual dual wins minus power-model expected wins. Positive = the
        record is stronger than a neutral power-based model expects; negative
        = the team may be better than its record."""
        if self.expected_wins is None:
            return None
        return self.dual_wins - self.expected_wins

    @property
    def upset_rate(self) -> float | None:
        return self.upsets / self.upset_opportunities if self.upset_opportunities else None

    @property
    def elite_win_share(self) -> float | None:
        return self.elite_win_share_num / self.elite_win_share_den if self.elite_win_share_den else None


def compute_team_metrics(bundles, careers: dict) -> dict:
    """Returns {(program_id, scope_id): TeamMetrics}. Uses `careers` (from
    aggregate.player_careers) purely to avoid re-deriving line_players -> we
    walk duals_full directly instead so this stays independent of that shape."""
    out = {}
    for b in bundles:
        # opponent power lookup for this scope, for quartile splits
        opp_power = {}
        for pid, standing in b.standings.items():
            if "toss_power_raw" in standing and standing["toss_power_raw"] not in (None, ""):
                try:
                    opp_power[pid] = float(standing["toss_power_raw"])
                except ValueError:
                    pass
        power_values = sorted(opp_power.values())
        # crude, auto-scaled Elo-style win-probability model: teams are only
        # comparable within one scope, so the logistic scale is the spread of
        # power actually observed here rather than an arbitrary constant.
        power_scale = statistics.pstdev(power_values) or 1.0

        def win_prob(own: float, opp: float) -> float:
            return 1 / (1 + math.exp(-(own - opp) / power_scale))

        def quartile_of(v: float) -> str:
            if not power_values:
                return "Q?"
            import bisect
            rank = bisect.bisect_left(power_values, v) / len(power_values)
            if rank >= 0.75:
                return "Q1"     # top quartile by power
            if rank >= 0.5:
                return "Q2"
            if rank >= 0.25:
                return "Q3"
            return "Q4"

        def decile_of(v: float) -> int:
            if not power_values:
                return -1
            import bisect
            return int(bisect.bisect_left(power_values, v) / len(power_values) * 10)

        per_program_lines = defaultdict(list)   # program_id -> list of (line, side, dual)
        per_program_duals = defaultdict(list)

        for did, d in b.duals_full.items():
            for side, pid in (("home", d["home_program_id"]), ("away", d["away_program_id"])):
                per_program_duals[pid].append((d, side))
                for line in d["lines"]:
                    per_program_lines[pid].append((line, side, d))

        for pid, prog in b.programs.items():
            m = TeamMetrics(program_id=pid, scope_id=b.scope_id, name=prog["name"], family=b.family)
            per_dual_share = []

            for line, side, d in per_program_lines.get(pid, []):
                home_won = bool(int(float(line.get("home_won") or 0)))
                won = home_won if side == "home" else not home_won
                if _is_singles(line["slot"]):
                    m.sp += 1
                    m.sw += 1 if won else 0
                else:
                    m.dp += 1
                    m.dw += 1 if won else 0
                fl = m.flight.setdefault(line["slot"], {"played": 0, "won": 0})
                fl["played"] += 1
                fl["won"] += 1 if won else 0

                if "score" in line and line.get("score"):
                    gw, gl = _games_from_score_string(line["score"])
                    if not won:
                        gw, gl = gl, gw
                    m.games_won += gw; m.games_lost += gl
                    sw, sl = _sets_from_score_string(line["score"])
                    if not won:
                        sw, sl = sl, sw
                elif line.get("home_games") not in (None, ""):
                    hg, ag = float(line.get("home_games") or 0), float(line.get("away_games") or 0)
                    gw, gl = (hg, ag) if side == "home" else (ag, hg)
                    m.games_won += gw; m.games_lost += gl
                    sw = sl = None    # no set-level detail in the college export
                else:
                    gw = gl = sw = sl = None

                if gw is not None:
                    if _is_singles(line["slot"]):
                        m.singles_games_won += gw; m.singles_games_lost += gl
                    else:
                        m.doubles_games_won += gw; m.doubles_games_lost += gl
                if sw is not None:
                    if _is_singles(line["slot"]):
                        m.singles_sets_won += sw; m.singles_sets_lost += sl
                    else:
                        m.doubles_sets_won += sw; m.doubles_sets_lost += sl

            for slot, fl in m.flight.items():
                fl["pct"] = fl["won"] / fl["played"] if fl["played"] else None

            m.lines_played = m.sp + m.dp
            m.lines_won = m.sw + m.dw
            m.line_share = m.lines_won / m.lines_played if m.lines_played else 0.0
            total_games = m.games_won + m.games_lost
            m.game_share = m.games_won / total_games if total_games else None

            for d, side in per_program_duals.get(pid, []):
                opp_id = d["away_program_id"] if side == "home" else d["home_program_id"]
                us = d["home_points"] if side == "home" else d["away_points"]
                them = d["away_points"] if side == "home" else d["home_points"]
                won = d["winner_program_id"] == pid
                m.duals += 1
                m.dual_wins += 1 if won else 0
                margin = abs(float(us) - float(them))
                if margin <= 1:
                    m.close_duals += 1
                    m.close_wins += 1 if won else 0

                dual_lines = [(line, s, dd) for line, s, dd in per_program_lines.get(pid, []) if dd is d]
                if dual_lines:
                    dw_ = sum(1 for line, s, dd in dual_lines
                             if (bool(int(float(line.get("home_won") or 0))) == (s == "home")))
                    dp_ = len(dual_lines)
                    share = dw_ / dp_
                    per_dual_share.append(share)
                    if won and share >= 0.8:
                        m.blowout_wins += 1
                    if not won and share >= 0.4:
                        m.resistance_losses += 1

                # JHSAA `district` = in-league play (the association's league
                # schedule); college `is_conference` = in-conference play. Both
                # mean "part of the regular league card", never a tournament
                # round — normalize both to one league_record split.
                in_league = None
                if "district" in d:
                    in_league = bool(int(d.get("district") or 0))
                elif "is_conference" in d:
                    in_league = bool(int(d.get("is_conference") or 0))
                if in_league is not None:
                    key = "league" if in_league else "non_league"
                    rec = m.league_record.setdefault(key, {"w": 0, "l": 0})
                    rec["w" if won else "l"] += 1

                if opp_id in opp_power:
                    q = quartile_of(opp_power[opp_id])
                    rec = m.quartile_record.setdefault(q, {"w": 0, "l": 0})
                    rec["w" if won else "l"] += 1

                # power-based pre-match win-probability model, for expected
                # record / upset / elite-win-share — only where both teams
                # have an archived power number in this scope.
                if pid in opp_power and opp_id in opp_power:
                    p = win_prob(opp_power[pid], opp_power[opp_id])
                    if m.expected_wins is None:
                        m.expected_wins = 0.0
                    m.expected_wins += p
                    m.upset_opportunities += 1 if p < 0.35 else 0
                    if won and p < 0.35:
                        m.upsets += 1
                    if won:
                        m.upset_value += max(0.0, 0.5 - p)
                    else:
                        m.bad_loss_value += max(0.0, p - 0.5)
                if won:
                    m.elite_win_share_den += 1
                    if opp_id in opp_power and decile_of(opp_power[opp_id]) >= 9:
                        m.elite_win_share_num += 1

                phase = d.get("phase") or d.get("round") or ""
                if phase and phase not in ("regular", "early", "REG", "district"):
                    m.postseason.append({"opp": b.program_name(opp_id), "phase": phase,
                                         "won": won, "us": us, "them": them})

            opp_powers = [opp_power[oid] for d, side in per_program_duals.get(pid, [])
                         for oid in [d["away_program_id"] if side == "home" else d["home_program_id"]]
                         if oid in opp_power]
            if opp_powers:
                m.avg_opp_power = sum(opp_powers) / len(opp_powers)
            if len(per_dual_share) >= 2:
                m.volatility = statistics.pstdev(per_dual_share)
            if len(per_dual_share) >= 4:
                s = sorted(per_dual_share)
                m.floor = s[max(0, round(0.25 * (len(s) - 1)))]
                m.ceiling = s[max(0, round(0.75 * (len(s) - 1)))]

            out[(pid, b.scope_id)] = m
    return out


def compute_player_value(careers: dict) -> dict:
    """Crude Player Value Above Replacement (owner wishlist #58): for every
    (scope, slot) a player appeared in, replacement level is the 25th-
    percentile win rate among OTHER players who logged 3+ matches at that
    same slot in that same scope — so it's read off the data on hand, not an
    arbitrary constant. A player's value is (their win rate at that slot -
    replacement) * matches played there, summed across every slot and season
    they appeared in. This is deliberately NOT limited to singles or doubles
    separately — the whole point (per the owner) is a number that looks past
    the S%/D% split at what a player is actually worth on court, wherever
    they were used.

    Crude on purpose: no opponent adjustment, no positional replacement curve
    beyond the flat percentile — a first cut, not a finished WAR model."""
    by_slot = defaultdict(lambda: defaultdict(list))   # (scope_id, slot) -> pid -> [won,...]
    for pid, c in careers.items():
        for m in c["matches"]:
            if m["won"] is None:
                continue
            by_slot[(m["scope_id"], m["slot"])][pid].append(m["won"])

    replacement = {}
    for key, players in by_slot.items():
        rates = sorted(sum(r) / len(r) for r in players.values() if len(r) >= 3)
        if len(rates) >= 4:
            replacement[key] = rates[max(0, round(0.25 * (len(rates) - 1)))]
        elif rates:
            replacement[key] = rates[0]
        else:
            replacement[key] = 0.35   # thin-sample fallback prior, not a claim

    pvar = {}
    for pid, c in careers.items():
        per_slot = defaultdict(list)
        for m in c["matches"]:
            if m["won"] is None:
                continue
            per_slot[(m["scope_id"], m["slot"])].append(m["won"])
        total = 0.0
        breakdown = []
        for key, results in per_slot.items():
            rep = replacement.get(key, 0.35)
            actual = sum(results) / len(results)
            contribution = (actual - rep) * len(results)
            total += contribution
            breakdown.append({"scope_id": key[0], "slot": key[1], "matches": len(results),
                               "actual": actual, "replacement": rep, "value": contribution})
        pvar[pid] = {"total": total, "breakdown": sorted(breakdown, key=lambda x: -abs(x["value"]))}
    return pvar


def storylines(metrics: dict) -> list[dict]:
    """Flag statistical extremes worth a human look, grouped by kind."""
    stories = []
    for (pid, scope_id), m in metrics.items():
        if m.lines_played < 10:
            continue    # too little sample for any of these to mean much
        fmt = m.fmt_lift
        if fmt is not None and abs(fmt) >= 10:
            direction = "gains" if fmt > 0 else "loses"
            stories.append({
                "kind": "format-lift", "program_id": pid, "scope_id": scope_id, "name": m.name,
                "value": fmt,
                "text": f"{m.name} {direction} {abs(fmt):.1f} points of expected court share when "
                        f"the card shifts from the regular 5S/2D shape to 1S/4D State weighting "
                        f"(S% {m.s_pct:.3f}, D% {m.d_pct:.3f})." if m.s_pct is not None else "",
            })
        dr = m.doubles_reliance
        if dr is not None and abs(dr) >= 25:
            shape = "doubles-driven" if dr > 0 else "singles-driven"
            stories.append({
                "kind": "team-shape", "program_id": pid, "scope_id": scope_id, "name": m.name,
                "value": dr,
                "text": f"{m.name} is sharply {shape}: S% {m.s_pct:.3f} vs D% {m.d_pct:.3f}, "
                        f"a {abs(dr):.1f}-point gap.",
            })
        cw = m.close_win_pct
        if cw is not None and m.close_duals >= 4 and (cw >= 0.75 or cw <= 0.25):
            tone = "thrives" if cw >= 0.75 else "struggles"
            stories.append({
                "kind": "close-matches", "program_id": pid, "scope_id": scope_id, "name": m.name,
                "value": cw,
                "text": f"{m.name} {tone} in one-point duals: {m.close_wins}-{m.close_duals - m.close_wins} "
                        f"({cw:.3f}) in {m.close_duals} decided by a single point. Small-sample caveat applies.",
            })
        if m.volatility is not None and m.volatility >= 0.22 and m.duals >= 6:
            stories.append({
                "kind": "volatility", "program_id": pid, "scope_id": scope_id, "name": m.name,
                "value": m.volatility,
                "text": f"{m.name}'s court share swings hard match to match (stdev {m.volatility:.3f} "
                        f"across {m.duals} duals) — a volatile team, not a steady one.",
            })
        luck = m.record_luck
        if luck is not None and m.duals >= 6 and abs(luck) >= 2.5:
            tone = "outperforming" if luck > 0 else "underperforming"
            stories.append({
                "kind": "record-luck", "program_id": pid, "scope_id": scope_id, "name": m.name,
                "value": luck,
                "text": f"{m.name} is {m.dual_wins}-{m.duals - m.dual_wins}, {tone} a power-based "
                        f"expected record of {m.expected_wins:.1f} wins by {abs(luck):.1f}.",
            })
        if m.upset_value >= 1.0:
            stories.append({
                "kind": "upsets", "program_id": pid, "scope_id": scope_id, "name": m.name,
                "value": m.upset_value,
                "text": f"{m.name} has banked {m.upsets} win(s) as a clear underdog (upset value "
                        f"{m.upset_value:.2f}) — a résumé worth more than its raw record.",
            })
        q1 = m.quartile_record.get("Q1")
        q4 = m.quartile_record.get("Q4")
        if q1 and (q1["w"] + q1["l"]) >= 3:
            pct = q1["w"] / (q1["w"] + q1["l"])
            if pct >= 0.7:
                stories.append({
                    "kind": "quality-wins", "program_id": pid, "scope_id": scope_id, "name": m.name,
                    "value": pct,
                    "text": f"{m.name} is {q1['w']}-{q1['l']} against top-quartile-power opponents.",
                })
        if q4 and (q4["w"] + q4["l"]) >= 3:
            pct = q4["w"] / (q4["w"] + q4["l"])
            if pct <= 0.5:
                stories.append({
                    "kind": "bad-losses", "program_id": pid, "scope_id": scope_id, "name": m.name,
                    "value": pct,
                    "text": f"{m.name} is only {q4['w']}-{q4['l']} against bottom-quartile-power "
                            f"opponents — a résumé worth a second look.",
                })
    stories.sort(key=lambda s: -abs(s["value"]) if isinstance(s["value"], (int, float)) else 0)
    return stories

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


def binom_at_least(n: int, p: float, k: int) -> float:
    """P(Binomial(n, p) >= k)."""
    return sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i)) for i in range(k, n + 1))


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
                elif line.get("home_games") not in (None, ""):
                    hg, ag = float(line.get("home_games") or 0), float(line.get("away_games") or 0)
                    gw, gl = (hg, ag) if side == "home" else (ag, hg)
                    m.games_won += gw; m.games_lost += gl

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
                    w = sum(1 for line, s, dd in dual_lines
                            if (bool(int(float(line.get("home_won") or 0))) == (s == "home")))
                    per_dual_share.append(w / len(dual_lines))

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

            out[(pid, b.scope_id)] = m
    return out


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

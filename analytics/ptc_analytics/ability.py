"""The ability layer — the one input the match engine actually reads.

Everything in `metrics.py` measures OUTCOMES: line win rates, flight share,
close-match records, and a power model built on TOSS. All of that models the
engine's OUTPUT. The engine itself reads exactly one number per player, their
current overall, so a library with no OVR in it can describe what happened and
can never say whether it should have.

This module supplies the input. It joins `lines` -> `line_players` ->
`players.current_grade`, so every flight on record carries the OVR gap it was
actually contested at, and then answers "what should have happened" from that.

‼️ The win curve is FITTED FROM THE INGESTED DATA, never hard-coded. The
engine's gap response has been retuned at least once (the hinge/knee work) and
a table copied in here would go stale silently — the same failure mode the
`regular_shape`/`state_shape` derivation in `aggregate.py` exists to avoid, and
the same one the game's own flight-weight AAR is about. `WinCurve` therefore
carries its OBSERVED bands alongside the fitted parameters: the bands are the
receipt, and if the fit and the bands disagree the bands win the argument.

‼️ Within one season a player's OVR is CONSTANT — development lands at the
rollover — so a season's `players.csv` value is the number every dual that
season was played at, not an end-of-year snapshot standing in for it. Across
seasons it is a per-season value and must be read per season.

Vocabulary (owner rule): a player plays MATCHES, at a FLIGHT / position /
line. "Courts played" is wrong; a court is the physical surface.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

# Reporting bands for an OVR gap, in 20-80 grade points. These are DISPLAY
# buckets for the observed table — not the model, which is continuous — and
# they are deliberately narrow at the bottom because that is where the engine
# keeps a match competitive and where a lineup decision is actually live.
GAP_BANDS = ((1.0, "even"), (3.0, "0-3"), (5.0, "3-5"), (8.0, "5-8"),
             (12.0, "8-12"), (20.0, "12-20"), (float("inf"), "20+"))

# A fit needs enough contested flights to mean anything. Under this the curve
# reports itself unfitted and every expectation reads None rather than serving
# a number nobody has evidence for.
MIN_FIT_SAMPLES = 200


def band_of(gap: float) -> str:
    """Label an OVR gap (own minus opponent, so negative = underdog) by the
    magnitude band it sits in."""
    a = abs(gap)
    for edge, name in GAP_BANDS:
        if a < edge:
            return name
    return GAP_BANDS[-1][1]


def _is_singles(slot: str) -> bool:
    return slot.upper().startswith("S")


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class WinCurve:
    """P(win a flight) as a function of the OVR gap, fitted on the ingested
    seasons. Singles and doubles get their own curve: two players' errors
    average out, so doubles is measurably steeper at the same gap and one
    shared curve would under-call favourites in doubles and over-call them in
    singles."""

    kind: str                       # "S" or "D"
    family: str
    a: float = 0.0                  # intercept (should sit at ~0: an even gap is a coin flip)
    b: float = 0.0                  # slope per OVR point
    samples: int = 0
    fitted: bool = False
    # observed win rate by gap band, from the favourite's side: the receipt
    # for the fit. {band: {"n": int, "won": int, "pct": float, "fit": float}}
    bands: dict = field(default_factory=dict)

    def p(self, gap: float) -> float | None:
        """Probability the side with this signed gap takes the flight."""
        if not self.fitted:
            return None
        z = self.a + self.b * gap
        if z >= 0:                  # numerically stable both ways
            return 1.0 / (1.0 + math.exp(-z))
        e = math.exp(z)
        return e / (1.0 + e)


def _fit(kind: str, family: str, real: Counter, wins: Counter) -> WinCurve:
    """Two-parameter logistic fitted by Newton-Raphson over GAP BINS rather
    than raw samples — a season is hundreds of thousands of flights and the
    likelihood only depends on (gap, n, wins), so binning at 0.25 of a grade
    point makes the fit cost nothing and changes nothing.

    `real` / `wins` are counted ONE ROW PER CONTESTED FLIGHT, signed from the
    home side. ‼️ The mirror is added inside this function and deliberately
    NOT counted as sample: a mirrored row is the same flight seen from the
    other bench, so folding it into the total halves the real bar
    `MIN_FIT_SAMPLES` sets and doubles the flight count the page reports.
    """
    n_total = sum(real.values())
    curve = WinCurve(kind=kind, family=family, samples=n_total)
    if n_total < MIN_FIT_SAMPLES:
        return curve

    # The FIT sees both sides, so the curve is symmetric about a zero gap and
    # the intercept has a reason to sit at zero. This is a modelling choice
    # about the likelihood, not a claim about how much evidence there is —
    # which is why it goes in its OWN counters and never rebinds `real`/`wins`.
    binned: Counter = Counter()
    fit_wins: Counter = Counter()
    for gap, n in real.items():
        y = wins[gap]
        binned[gap] += n
        fit_wins[gap] += y
        binned[-gap] += n
        fit_wins[-gap] += n - y

    a, b = 0.0, 0.1
    for _ in range(40):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for gap, n in binned.items():
            y = fit_wins[gap]
            z = a + b * gap
            p = 1.0 / (1.0 + math.exp(-z)) if z >= 0 else math.exp(z) / (1.0 + math.exp(z))
            w = n * p * (1.0 - p)
            r = y - n * p
            g0 += r
            g1 += r * gap
            h00 += w
            h01 += w * gap
            h11 += w * gap * gap
        det = h00 * h11 - h01 * h01
        if abs(det) < 1e-12:
            break
        da = (h11 * g0 - h01 * g1) / det
        db = (h00 * g1 - h01 * g0) / det
        a += da
        b += db
        if abs(da) < 1e-9 and abs(db) < 1e-9:
            break

    curve.a, curve.b, curve.fitted = a, b, True

    # Observed vs fitted by band, folded onto the FAVOURITE's side so the two
    # halves of every flight don't cancel to .500 and say nothing. Folded from
    # `real`, not from the mirrored fit input — the counts here are the number
    # of flights actually played at that gap, which is what makes the column a
    # receipt rather than a restatement of the model.
    agg: dict[str, list[float]] = {}
    for gap, n in real.items():
        # Fold the underdog's rows onto the favourite's side: a flight played
        # at -8 and won is the SAME evidence as one played at +8 and lost.
        y = (n - wins[gap]) if gap < 0 else wins[gap]
        mag = abs(gap)
        row = agg.setdefault(band_of(mag), [0.0, 0.0, 0.0])
        row[0] += n
        row[1] += y
        row[2] += n * (curve.p(mag) or 0.0)
    # In band order, not dict order — the table reads as a curve.
    for _edge, name in GAP_BANDS:
        if name not in agg:
            continue
        n, y, fit = agg[name]
        curve.bands[name] = {"n": int(n), "won": int(y),
                             "pct": y / n if n else None,
                             "fit": fit / n if n else None}
    return curve


@dataclass
class ScopeAbility:
    """Per-season ability index for one ingested scope."""

    scope_id: str
    ovr: dict = field(default_factory=dict)          # player_id -> current overall
    pot: dict = field(default_factory=dict)          # player_id -> ceiling
    ladder: dict = field(default_factory=dict)       # program_id -> [player_id] best first
    rank: dict = field(default_factory=dict)         # player_id -> 1-based ladder position
    dressed: int | None = None                       # distinct players one league dual uses

    def rank_of(self, pid: str) -> int | None:
        return self.rank.get(pid)

    def roster_size(self, program_id: str) -> int:
        return len(self.ladder.get(program_id, ()))

    def slot_in(self, program_id: str, ovr: float) -> int:
        """Where a player of this OVR would land on that program's ladder
        (1-based). The destination-fit question: 'would they start there'."""
        board = self.ladder.get(program_id, ())
        n = sum(1 for pid in board if (self.ovr.get(pid) or 0.0) > ovr)
        return n + 1


def dressed_players(shape: tuple[int, int] | None) -> int | None:
    """Distinct players a dual of this shape puts on court — ns singles plus
    two per doubles flight. DERIVED from the scope's own shape, never a
    constant: 3S/4D dresses 11, 5S/2D dresses 9, 1S/4D dresses 9."""
    if not shape:
        return None
    ns, nd = shape
    return ns + 2 * nd


def scope_ability(bundle) -> ScopeAbility:
    sa = ScopeAbility(scope_id=bundle.scope_id,
                      dressed=dressed_players(bundle.regular_shape))
    by_program: dict[str, list[str]] = defaultdict(list)
    for pid, p in bundle.players.items():
        cur = _f(p.get("current_grade"))
        if cur is not None:
            sa.ovr[pid] = cur
        pot = _f(p.get("potential_grade"))
        if pot is not None:
            sa.pot[pid] = pot
        by_program[p.get("program_id") or ""].append(pid)

    for program_id, pids in by_program.items():
        # Ties break on name so a ladder is stable between builds rather than
        # reordering on dict iteration order.
        board = sorted(pids, key=lambda x: (-(sa.ovr.get(x) or 0.0),
                                            bundle.players.get(x, {}).get("name", "")))
        sa.ladder[program_id] = board
        for i, pid in enumerate(board, 1):
            sa.rank[pid] = i
    return sa


def _side_ovr(entries: list[dict], ovr: dict) -> float | None:
    """Mean OVR of the players on one side of a flight. A doubles pair is the
    average of the two — the pair is the entity that contests the line."""
    vals = [ovr[e["player_id"]] for e in entries if e.get("player_id") in ovr]
    if not vals or len(vals) != len(entries):
        return None     # a partly-resolved pair would misprice the whole line
    return sum(vals) / len(vals)


def line_matchups(bundle, sa: ScopeAbility):
    """Yield every contested flight on record, once per SIDE, with the gap it
    was played at:

        {dual, line, side, program_id, opp_program_id, players, slot,
         singles, own_ovr, opp_ovr, gap, won}

    Once per side is deliberate: a team page and a player page both need the
    row from their own perspective, and the two halves are exact mirrors, so
    anything summing over a whole scope must pick one side (see the callers)."""
    for did, d in bundle.duals_full.items():
        home_prog, away_prog = d["home_program_id"], d["away_program_id"]
        for line in d["lines"]:
            by_side: dict[str, list[dict]] = defaultdict(list)
            for lp in line["players"]:
                by_side[lp["side"]].append(lp)
            if not by_side.get("home") or not by_side.get("away"):
                continue
            h = _side_ovr(by_side["home"], sa.ovr)
            a = _side_ovr(by_side["away"], sa.ovr)
            if h is None or a is None:
                continue
            home_won = bool(int(float(line.get("home_won") or 0)))
            singles = _is_singles(line["slot"])
            for side in ("home", "away"):
                own, opp = (h, a) if side == "home" else (a, h)
                yield {
                    "dual": d, "dual_id": did, "line": line, "slot": line["slot"],
                    "side": side, "singles": singles,
                    "program_id": home_prog if side == "home" else away_prog,
                    "opp_program_id": away_prog if side == "home" else home_prog,
                    "players": by_side[side],
                    "own_ovr": own, "opp_ovr": opp, "gap": own - opp,
                    "won": home_won if side == "home" else not home_won,
                }


def fit_curves(bundles, abilities: dict) -> dict:
    """Fit one curve per (family, singles/doubles) across EVERY ingested season
    of that family. The curve is a property of the engine, not of a season, so
    pooling seasons is what makes it well-determined — and it means a single
    exported season still gets a usable model."""
    # ONE ROW PER CONTESTED FLIGHT, signed from the home side. ‼️ The mirror
    # belongs to `_fit` and must not also be added here — it was, and the two
    # together made `samples` (and every observed band's n) twice the number
    # of flights that were actually played, which in turn halved the real bar
    # `MIN_FIT_SAMPLES` sets.
    real: dict[tuple, Counter] = defaultdict(Counter)
    wins: dict[tuple, Counter] = defaultdict(Counter)
    for b in bundles:
        sa = abilities.get(b.scope_id)
        if sa is None:
            continue
        for mu in line_matchups(b, sa):
            if mu["side"] != "home":
                continue    # one row per flight: both sides would double-count
            key = (b.family, "S" if mu["singles"] else "D")
            gap = round(mu["gap"] * 4) / 4
            real[key][gap] += 1
            wins[key][gap] += 1 if mu["won"] else 0
    return {key: _fit(key[1], key[0], real[key], wins[key]) for key in real}


@dataclass
class AbilityIndex:
    """Everything the rest of the sidecar asks the ability layer for."""

    abilities: dict = field(default_factory=dict)       # scope_id -> ScopeAbility
    curves: dict = field(default_factory=dict)          # (family, "S"/"D") -> WinCurve
    # (scope_id, player_id) -> {"matches","w","l","xw","wae","gap_sum","bands"}
    player: dict = field(default_factory=dict)
    # (scope_id, program_id) -> {"flights","won","x_won","x_share","share","luck"}
    team: dict = field(default_factory=dict)
    # scope_ids deliberately left unpriced — reported, never silently dropped
    skipped: list = field(default_factory=list)

    def curve_for(self, family: str, singles: bool) -> WinCurve | None:
        return self.curves.get((family, "S" if singles else "D"))

    def ability(self, scope_id: str) -> ScopeAbility | None:
        return self.abilities.get(scope_id)


def build(bundles) -> AbilityIndex:
    """‼️ Only scopes whose players.csv is the roster that PLAYED are indexed
    (`Bundle.roster_is_snapshot`). A scope that is left out has no entry in
    `abilities`, so every downstream lookup returns None and renders an
    em-dash — which is the correct answer, and is why nothing here degrades
    into pricing old flights at today's OVRs."""
    idx = AbilityIndex()
    scoped = [b for b in bundles if b.roster_is_snapshot]
    idx.skipped = [b.scope_id for b in bundles if not b.roster_is_snapshot]
    for b in scoped:
        idx.abilities[b.scope_id] = scope_ability(b)
    idx.curves = fit_curves(scoped, idx.abilities)

    for b in scoped:
        sa = idx.abilities[b.scope_id]
        for mu in line_matchups(b, sa):
            curve = idx.curve_for(b.family, mu["singles"])
            p = curve.p(mu["gap"]) if curve else None

            trow = idx.team.setdefault((b.scope_id, mu["program_id"]), {
                "flights": 0, "won": 0, "x_won": 0.0, "priced": 0,
                "gap_sum": 0.0, "bands": Counter(), "band_won": Counter()})
            trow["flights"] += 1
            trow["won"] += 1 if mu["won"] else 0
            trow["gap_sum"] += mu["gap"]
            band = band_of(mu["gap"]) if mu["gap"] >= 0 else "-" + band_of(mu["gap"])
            trow["bands"][band] += 1
            trow["band_won"][band] += 1 if mu["won"] else 0
            if p is not None:
                trow["x_won"] += p
                trow["priced"] += 1

            for e in mu["players"]:
                pid = e.get("player_id")
                if not pid:
                    continue
                prow = idx.player.setdefault((b.scope_id, pid), {
                    "matches": 0, "w": 0, "l": 0, "x_won": 0.0, "priced": 0,
                    "gap_sum": 0.0, "opp_sum": 0.0, "slots": Counter(),
                    "singles_w": 0, "singles_l": 0, "doubles_w": 0, "doubles_l": 0})
                prow["matches"] += 1
                prow["w" if mu["won"] else "l"] += 1
                half = "singles" if mu["singles"] else "doubles"
                prow[f"{half}_{'w' if mu['won'] else 'l'}"] += 1
                prow["slots"][mu["slot"]] += 1
                prow["gap_sum"] += mu["gap"]
                prow["opp_sum"] += mu["opp_ovr"]
                if p is not None:
                    prow["x_won"] += p
                    prow["priced"] += 1

    for row in idx.player.values():
        n = row["matches"]
        row["pct"] = row["w"] / n if n else None
        row["avg_gap"] = row["gap_sum"] / n if n else None
        row["avg_opp_ovr"] = row["opp_sum"] / n if n else None
        row["x_pct"] = row["x_won"] / row["priced"] if row["priced"] else None
        # ‼️ WAE compares actual wins against expectation over the PRICED
        # matches only. Scoring every match against a partial expectation
        # would credit a player for matches the model never saw.
        row["wae"] = (row["w"] - row["x_won"]) if row["priced"] == n and n else None
        row["top_slot"] = row["slots"].most_common(1)[0][0] if row["slots"] else ""

    for row in idx.team.values():
        n = row["flights"]
        row["share"] = row["won"] / n if n else None
        row["x_share"] = row["x_won"] / row["priced"] if row["priced"] else None
        row["avg_gap"] = row["gap_sum"] / n if n else None
        row["luck"] = (row["won"] - row["x_won"]) if row["priced"] == n and n else None
    return idx

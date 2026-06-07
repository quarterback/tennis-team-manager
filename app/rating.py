"""
Power Index (TOSS model) computed from simulated dual results.

  Power Index = 40% APR + 40% FQI + 20% oGS

- **APR** (Adjusted Power Rating) — RPI: 25% own dual win% + 50% opponents'
  win% + 25% opponents'-opponents' win%.
- **FQI** (Flight Quality Index) — per-dual flight-weighted line wins
  (#1 lines weigh most), averaged and scaled by opponent strength
  (opp_APR / median_APR).
- **oGS** (opponent-weighted Game Share) — share of games won per dual,
  scaled by the same opponent multiplier.

This is the rating that seeds rankings + the NCAA bracket. Display PI is
linearly remapped to a plausible 0.55–0.95 band; ordering is preserved.

Input: a list of dual dicts (see season.py / DualRecord):
  {home, away, home_won, home_points, away_points,
   lines:[{slot, home_won, home_games, away_games}]}
"""
from __future__ import annotations

from dataclasses import dataclass

# College flight weights: #1 lines carry the most competitive weight.
FLIGHT_WEIGHTS = {
    "S1": 1.00, "S2": 0.85, "S3": 0.60, "S4": 0.45, "S5": 0.30, "S6": 0.20,
    "D1": 0.80, "D2": 0.50, "D3": 0.30,
}


@dataclass
class RatingLine:
    school: str
    wins: int = 0
    losses: int = 0
    apr: float = 0.0
    fqi: float = 0.0
    ogs: float = 0.0
    pi_raw: float = 0.0
    pi: float = 0.0          # display-normalized

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}"

    @property
    def win_pct(self) -> float:
        n = self.wins + self.losses
        return self.wins / n if n else 0.0


def _flight_score(lines: list[dict], side: str) -> float | None:
    """Flight-weighted share of lines won by `side` ('home'/'away')."""
    earned = total = 0.0
    for ln in lines:
        w = FLIGHT_WEIGHTS.get(ln["slot"], 0.3)
        total += w
        won = ln["home_won"] if side == "home" else not ln["home_won"]
        if won:
            earned += w
    return earned / total if total else None


def _game_share(lines: list[dict], side: str) -> float | None:
    gw = gp = 0
    for ln in lines:
        hg, ag = ln.get("home_games", 0), ln.get("away_games", 0)
        gp += hg + ag
        gw += hg if side == "home" else ag
    return gw / gp if gp else None


def compute_ratings(duals: list[dict]) -> dict[str, RatingLine]:
    teams: dict[str, RatingLine] = {}
    opps: dict[str, list[str]] = {}

    def get(t: str) -> RatingLine:
        if t not in teams:
            teams[t] = RatingLine(school=t)
            opps[t] = []
        return teams[t]

    # --- dual W/L + opponents ---
    for d in duals:
        h, a = get(d["home"]), get(d["away"])
        opps[d["home"]].append(d["away"])
        opps[d["away"]].append(d["home"])
        if d["home_won"]:
            h.wins += 1; a.losses += 1
        else:
            a.wins += 1; h.losses += 1

    # --- APR (RPI) ---
    wp = {t: r.win_pct for t, r in teams.items()}
    owp = {t: (sum(wp[o] for o in opps[t]) / len(opps[t]) if opps[t] else 0.0) for t in teams}
    oowp = {t: (sum(owp[o] for o in opps[t]) / len(opps[t]) if opps[t] else 0.0) for t in teams}
    for t, r in teams.items():
        r.apr = 0.25 * wp[t] + 0.50 * owp[t] + 0.25 * oowp[t]

    aprs = sorted(r.apr for r in teams.values())
    median_apr = aprs[len(aprs) // 2] if aprs else 1.0
    median_apr = median_apr or 1.0

    # --- FQI + oGS (opponent-weighted) ---
    fqi_acc: dict[str, list[float]] = {t: [] for t in teams}
    ogs_acc: dict[str, list[float]] = {t: [] for t in teams}
    for d in duals:
        lines = [ln for ln in d.get("lines", []) if ln.get("completed", True)]
        if not lines:
            continue
        h, a = d["home"], d["away"]
        mh = teams[a].apr / median_apr   # home's opponent multiplier
        ma = teams[h].apr / median_apr
        for side, t, m in (("home", h, mh), ("away", a, ma)):
            fs = _flight_score(lines, side)
            gs = _game_share(lines, side)
            if fs is not None:
                fqi_acc[t].append(fs * m)
            if gs is not None:
                ogs_acc[t].append(gs * m)

    for t, r in teams.items():
        r.fqi = sum(fqi_acc[t]) / len(fqi_acc[t]) if fqi_acc[t] else 0.0
        r.ogs = sum(ogs_acc[t]) / len(ogs_acc[t]) if ogs_acc[t] else 0.0
        r.pi_raw = 0.40 * r.apr + 0.40 * r.fqi + 0.20 * r.ogs

    # --- display normalization to 0.55–0.95 (order preserved) ---
    raws = [r.pi_raw for r in teams.values()]
    lo, hi = (min(raws), max(raws)) if raws else (0.0, 1.0)
    span = (hi - lo) or 1.0
    for r in teams.values():
        r.pi = 0.55 + 0.40 * (r.pi_raw - lo) / span

    return teams

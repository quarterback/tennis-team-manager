"""The JHSAA at-large selection committee (owner spec 2026-09) — five named
members, each a FIXED, CONCENTRATED preference vector over the `jhsaa_ratings`
systems, used only by the Parastate groups (`jhsaa.ATLARGE_GROUPS`: 8A, 9A and
Group 1 at 16 bids in a 48-team field; 7A/6A/5A/4A/3A/2A at 8 bids in a 40; and
1A at 8 bids in a 32, off the 24-team road it keeps — `AT_LARGE_BIDS`, and
`jhsaa.parastate_summary()` renders exactly this list for a reader).

‼️ 1A IS ON A 32, NOT A 40, AND SIXTEEN BIDS THERE WAS EXPLICITLY REJECTED
(owner rule 2026-09: "I do not want 16 at-large teams in 1A" — a 40 off a 24
road costs 16 bids and would make 1A the one class where the committee picks
40% of the field). The bid count is the decision; the field size is the
consequence.

The committee is deliberately deterministic and legible: the same five members
exist every season, their weights are published in the UI, every ballot is a
full ordering of the eligible non-road field, and every selection traces to the
five ballots — a snub is five defensible opinions, never a coin flip. There is
NO random component, and NO discretion after the ballots (owner rule: "the five
philosophies already are the discretion").

‼️ The vectors are CONCENTRATED, not tiny variations on equal weights (owner
rule 2026-09): a member uses the systems their philosophy names and ignores the
rest — forcing all nine on everyone collapses the ballots toward the mean and
deletes the disagreement this exists to produce. Only the Balancer reads all
nine.

What it can and cannot do (spec, hard rules):
  * The road to State is untouched — it still qualifies exactly the group's
    `jhsaa.state_field_size` (32 everywhere but 1A, which keeps its 24). The
    committee only fills the group's at-large seats (`seats`).
  * The candidate pool is EVERY team outside the road field — including teams
    the systems rank above road qualifiers. Nothing pre-cuts it.
  * A district champion who missed the road gets an AUTOMATIC at-large berth,
    and it CONSUMES a seat rather than adding a berth.
  * ‼️ At-large teams are ALWAYS seeded below the whole road — 33 down in a
    48 (33-48) and in a 32-road 40 (33-40), 25 down in 1A's 32 (25-32). Never
    above a road qualifier, whatever the record, rating or Borda total.
    `jhsaa.run_state_parastate` enforces it structurally (the at-larges arrive
    after every road seed); a test pins a case whose Borda would otherwise
    outrank a road seed.
"""
from __future__ import annotations

import statistics

#: The five members (owner weights, 2026-09). Fractions over the systems each
#: member actually reads; a member's ballot is the ordering of the field by the
#: weighted mean of those systems' ranks. Published in the UI — not secret.
MEMBERS: dict[str, dict[str, float]] = {
    "The Traditionalist": {"colley": 0.30, "bt": 0.30, "win_pct": 0.25,
                           "sor": 0.15},
    "The Quant": {"massey_game": 0.35, "set_share": 0.30, "massey_dual": 0.20,
                  "srs": 0.15},
    "The Schedule Hawk": {"sor": 0.40, "colley": 0.20, "massey_dual": 0.20,
                          "bt": 0.20},
    "The Eye Test": {"elo": 0.40, "srs": 0.25, "win_pct": 0.20, "bt": 0.15},
    "The Balancer": {s: 1.0 / 9.0 for s in
                     ("colley", "bt", "win_pct", "massey_dual", "srs",
                      "massey_game", "set_share", "sor", "elo")},
}

#: At-large seats (spec 2.1) — the DEFAULT. The seat count is per group now
#: (`jhsaa.AT_LARGE_BIDS`: 16 for 8A/9A/Group 1, 8 for 7A through 1A) and
#: `select` takes it as `seats`; this is the 48-field's number and what a bare
#: call gets.
AT_LARGE = 16


def ballot(ratings: dict, weights: dict[str, float]) -> list[str]:
    """One member's full ordering of the group: weighted mean of the member's
    OWN systems' ranks, ascending (rank 1 = best). A system the layer withheld
    (a disconnected group drops the least-squares family) contributes nothing —
    the weights renormalise over what exists. Ties break on the name so a
    ballot is reproducible."""
    teams = ratings["teams"]

    def score(name: str) -> float:
        rk = teams[name]["ranks"]
        num = sum(w * rk[s] for s, w in weights.items() if s in rk)
        den = sum(w for s, w in weights.items() if s in rk)
        return num / den if den else 0.0

    return sorted(teams, key=lambda n: (score(n), n))


def ballots(ratings: dict) -> dict[str, list[str]]:
    """All five ballots. Changing one member's weights changes only that
    member's ballot — each is an independent read of the same ranks."""
    return {m: ballot(ratings, w) for m, w in MEMBERS.items()}


def select(ratings: dict, road: set[str], district_champions: list[str],
           atr: dict[str, float] | None = None, seats: int = AT_LARGE) -> dict:
    """The whole selection (spec 3.2, owner refinements 2026-09), returning an
    auditable dict. `seats` is the group's at-large count (`jhsaa.AT_LARGE_BIDS`
    — 16 in a 48, 8 in a 32-road 40, 8 in 1A's 24-road 32); every step below
    scales off it and a district
    champion who missed the road consumes one of them, never adds one.

      {"selected": [`seats` names in SEED ORDER, 33 down], "auto": [...],
       "locks": [...], "borda": {bubble name: total}, "seed_borda": {...},
       "ballots": {member: full candidate ordering},
       "ranges": {member: that member's at-large range},
       "status": {name: Qualified|Lock|In|Bubble|Out}, "weights": MEMBERS}

    Steps:
      1. AUTOMATIC BIDS — district champions who missed the road.
      2. LOCKS — in the at-large range (each member's top N remaining
         candidates, N = 16 - automatics) on ALL five ballots.
      3. THE BUBBLE — teams on at least one but fewer than five ranges. Borda
         is scored over the FULL ORDERING OF THE BUBBLE POPULATION (locks and
         automatics removed first): with B bubble teams a member's first gets
         B points down to 1 — so No. 17 on a ballot and No. 50 stay
         distinguishable, and the ranking disagreement itself keeps mattering.
      4. SEEDING (33-48 in a 48; 33-40 in a 40; 25-32 in 1A's 32) — Borda over
         the selected teams, ties broken INSIDE
         the same conceptual system (owner ladder): number of ballots selecting
         the team, then median ballot rank, then composite mean rank, then the
         seeding ATR, then the name (head-to-head sits in the ladder before ATR
         in the owner's wording; two at-larges have rarely met and a played
         pairing is not always defined, so the ATR rung carries it).
    """
    all_ballots = ballots(ratings)
    # Candidate pool: EVERY non-road team — nothing pre-cut.
    candidates = [n for n in sorted(ratings["teams"]) if n not in road]
    cand_ballots = {m: [n for n in order if n not in road]
                    for m, order in all_ballots.items()}

    # Step 1 — automatic bids.
    auto = [n for n in district_champions
            if n not in road and n in ratings["teams"]][:seats]
    open_seats = seats - len(auto)

    # Each member's at-large range: their top `open_seats` remaining candidates.
    ranges = {m: [n for n in order if n not in auto][:open_seats]
              for m, order in cand_ballots.items()}
    appearances = {n: sum(1 for m in MEMBERS if n in ranges[m])
                   for n in candidates}

    # Step 2 — locks: unanimous across the five ranges.
    locks = sorted((n for n in candidates
                    if n not in auto and appearances[n] == len(MEMBERS)),
                   key=lambda n: n)
    locks = locks[:open_seats]

    # Step 3 — the bubble: on >=1 but <5 ranges. Borda over the FULL ordering
    # of the bubble population, locks and automatics removed first.
    bubble = [n for n in candidates
              if n not in auto and n not in locks and appearances[n] >= 1]
    nb = len(bubble)
    borda: dict[str, int] = {n: 0 for n in bubble}
    for m, order in cand_ballots.items():
        pool = [n for n in order if n in borda]
        for pos, n in enumerate(pool):
            borda[n] += nb - pos
    fill = sorted(bubble, key=lambda n: (-borda[n], n))[:open_seats - len(locks)]

    chosen = set(auto) | set(locks) | set(fill)

    # Step 4 — seed the at-larges below the road: Borda over the SELECTED, then the owner's
    # tie ladder, every rung inside the same conceptual system.
    ns = len(chosen)
    seed_borda: dict[str, int] = {n: 0 for n in chosen}
    positions: dict[str, list[int]] = {n: [] for n in chosen}
    for m, order in cand_ballots.items():
        pool = [n for n in order if n in chosen]
        for pos, n in enumerate(pool):
            seed_borda[n] += ns - pos
        for n in chosen:
            positions[n].append(order.index(n) + 1)

    def seed_key(n: str):
        return (-seed_borda[n],
                -appearances.get(n, 0),
                statistics.median(positions[n]),
                ratings["teams"][n]["mean"],
                -(atr or {}).get(n, 0.0),
                n)

    selected = sorted(chosen, key=seed_key)

    status: dict[str, str] = {}
    for n in ratings["teams"]:
        if n in road:
            status[n] = "Qualified"
        elif n in locks:
            status[n] = "Lock"
        elif n in chosen:
            status[n] = "In"
        elif n in bubble:
            status[n] = "Bubble"
        else:
            status[n] = "Out"

    return {"selected": selected, "auto": auto, "locks": locks,
            "borda": borda, "seed_borda": seed_borda,
            "ballots": cand_ballots, "ranges": ranges, "status": status,
            "seats": seats,
            "weights": {m: dict(w) for m, w in MEMBERS.items()}}


# --- RECORD OVER EXPECTED (owner rule 2026-09) ---------------------------------
#
# Context beside the record and TOSS, never a ballot. "Show the committee when a
# team's record and its underlying flight performance tell different stories"
# (docs/reports/REPORT-jhsaa-2079-format-selection-companion.md §6). Counted in
# FLIGHTS — never sets, games or appearances — over the pre-State varsity duals.
#
# ‼️ THE EXPONENT IS A NAMED CONSTANT, CALIBRATED ONCE. Fitted on the 2079
# pre-State duals: boys 1.815, girls 1.850, correlation with actual W% .95 in
# both. 1.83 association-wide; recalibrate after several seasons or a material
# format change (`fit_xw_exponent`), never every year.
XW_EXPONENT = 1.83
#: |ROE| at which the page shows a flag. Descriptive only — no committee points.
ROE_FLAG = 0.10
#: Phases NOT yet played when the committee sits.
_STATE_PHASES = ("state", "toc")


def flight_record(schedule: list) -> dict:
    """Flights won/lost, duals won/lost and one-flight-margin duals won/lost from
    a program's pre-State VARSITY schedule (`TeamSeason.schedule` rows — JV rows
    carry `level='jv'` and are skipped; a tie counts as neither a win nor a loss
    but its flights count)."""
    fw = fl = w = l = cw = cl = 0
    for d in schedule:
        if d.get("level") == "jv" or d.get("phase") in _STATE_PHASES:
            continue
        home = bool(d.get("home"))
        for ln in d.get("lines") or ():
            if bool(ln.get("home_won")) == home:
                fw += 1
            else:
                fl += 1
        if d.get("tied"):
            continue
        won = d.get("won") if "won" in d else (d.get("pf", 0) > d.get("pa", 0))
        w += won; l += not won
        if abs(d.get("pf", 0) - d.get("pa", 0)) <= 1:
            cw += won; cl += not won
    return {"flights_won": fw, "flights_lost": fl, "wins": w, "losses": l,
            "close_wins": cw, "close_losses": cl}


def expected_win_pct(flights_won: int, flights_lost: int,
                     k: float = XW_EXPONENT) -> float | None:
    """Pythagorean expectation over flights. None with nothing played."""
    if flights_won + flights_lost == 0:
        return None
    a, b = flights_won ** k, flights_lost ** k
    return a / (a + b) if a + b else None


def record_context(teams) -> dict:
    """`{school: {...}}` for every TeamSeason passed — the archived context panel.

    `flag` is "underrated" when the record trails the flights by `ROE_FLAG` or
    more, "overstated" when it leads by as much, else "". Nothing here selects."""
    out = {}
    for t in teams:
        fr = flight_record(t.schedule)
        played = fr["wins"] + fr["losses"]
        pct = fr["wins"] / played if played else None
        xw = expected_win_pct(fr["flights_won"], fr["flights_lost"])
        share = (fr["flights_won"] / (fr["flights_won"] + fr["flights_lost"])
                 if fr["flights_won"] + fr["flights_lost"] else None)
        roe = (pct - xw) if pct is not None and xw is not None else None
        flag = ""
        if roe is not None and roe <= -ROE_FLAG:
            flag = "underrated"
        elif roe is not None and roe >= ROE_FLAG:
            flag = "overstated"
        out[t.school.name] = {**fr, "win_pct": pct, "flight_share": share,
                              "xwin_pct": xw, "record_over_expected": roe,
                              "flag": flag}
    return out


def fit_xw_exponent(rows, lo: float = 0.5, hi: float = 4.0) -> float:
    """The Pythagorean exponent that best fits `rows` of (flights_won,
    flights_lost, wins, losses) — least squares on W%, golden-section over
    [lo, hi]. A CALIBRATION tool (scripts), never called per season."""
    rows = [r for r in rows if r[0] + r[1] and r[2] + r[3]]
    def sse(k):
        return sum((expected_win_pct(fw, fl, k) - w / (w + l)) ** 2
                   for fw, fl, w, l in rows)
    g = (5 ** 0.5 - 1) / 2
    a, b = lo, hi
    c, d = b - g * (b - a), a + g * (b - a)
    while b - a > 1e-4:
        if sse(c) < sse(d):
            b, d = d, c; c = b - g * (b - a)
        else:
            a, c = c, d; d = a + g * (b - a)
    return round((a + b) / 2, 3)

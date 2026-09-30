"""The JHSAA at-large selection committee (owner spec 2026-09) — a TWENTY-FOUR
member statewide electorate of named Jefferson media outlets, each a FIXED,
published preference vector over the `jhsaa_ratings` systems, used only by the
Parastate groups (`jhsaa.ATLARGE_GROUPS`: 8A, 9A and Group 1 at 16 bids in a
48-team field; 7A/6A/5A/4A/3A/2A at 8 bids in a 40; and 1A at 8 bids in a 32,
off the 24-team road it keeps — `AT_LARGE_BIDS`, and `jhsaa.parastate_summary()`
renders exactly this list for a reader).

‼️ 1A IS ON A 32, NOT A 40, AND SIXTEEN BIDS THERE WAS EXPLICITLY REJECTED
(owner rule 2026-09: "I do not want 16 at-large teams in 1A" — a 40 off a 24
road costs 16 bids and would make 1A the one class where the committee picks
40% of the field). The bid count is the decision; the field size is the
consequence.

The committee is deliberately deterministic and legible: the same voters exist
every season, their weights are published in the UI, every ballot is a full
ordering of the eligible non-road field, and every selection traces to those
ballots — a snub is twenty-four defensible opinions, never a coin flip. There is
NO random component, and NO discretion after the ballots (owner rule: "the
philosophies already are the discretion").

‼️ TWO THINGS GOT CONFLATED AND ARE NOW SEPARATE (owner rule 2026-09): HOW MANY
PHILOSOPHIES the committee needs, and HOW MANY VOTERS it has. It needs enough
distinct philosophies not to be a handful of formulas wearing human names —
`TENDENCIES`, seven of them — and it needs an ELECTORATE big enough to be a
state: twenty-four voters, three or four per tendency (`TENDENCY_SEATS`), each
with its own weights INSIDE that tendency. Nobody has to invent twenty-four
unique mathematical personalities, and nobody is a carbon copy: one Schedule
voter reads
0.40 SOR / 0.25 Markov / 0.20 Massey-dual / 0.15 BT, another 0.50 / 0.25 / 0.25.

‼️ FIVE WAS TOO SMALL AND THE ARITHMETIC IS WHY. One voter WAS 20% of the
electorate, a 3-2 split was the narrowest possible majority, "unanimous lock"
meant five perspectives agreeing, the whole look-at-everything position was one
member, and a genuinely new rating (the Markov chain, which replaced Colley in
the same pass) could only reach the committee through the one voter who read it.
At twenty-four a team appears on 21 ballots or 14 or 8 — granularity 5/5, 4/5,
3/5 cannot express — and one idiosyncratic ballot can no longer throw a team ten
seed lines through the Borda count.

‼️ THE VECTORS ARE CONCENTRATED, not tiny variations on equal weights (owner
rule 2026-09): a voter uses the systems its philosophy names and ignores the
rest — forcing all nine on everyone collapses the ballots toward the mean and
deletes the disagreement this exists to produce. Only the three `consensus`
voters read all nine, and even they are not identical.

‼️ THE VOTERS ARE REAL PLACES. Every outlet sits in a city that exists in
`data/jhsaa/schools.json` with the area recorded here (verified against the
file: all seventeen markets resolve), because the association's geography is
real everywhere else and a statewide committee that covered nowhere in
particular would be the one part of it that was not. ‼️ THE OUTLETS AND THEIR
MARKETS ARE THE OWNER'S OWN LIST and are not an agent's to rename; the
tendency each votes on and its weights are this module's, and one line changes
either. The `beat` and `area` fields are identity for the page and reach no
ballot.

What it can and cannot do (spec, hard rules):
  * The road to State is untouched — it still qualifies exactly the group's
    `jhsaa.state_field_size` (32 everywhere but 1A, which keeps its 24). The
    committee only fills the group's at-large seats (`seats`).
  * The candidate pool is EVERY team outside the road field — including teams
    the systems rank above road qualifiers. Nothing pre-cuts it, and that
    includes the display tiers below: `Fringe` is a LABEL, never a cut, and a
    team on one ballot is still scored by the Borda count.
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

import math
import statistics
from typing import NamedTuple

from .jhsaa_ratings import SYSTEMS as _SYSTEMS

#: The seven philosophies. A tendency is a recognisable way of reading a season;
#: the three voters inside it disagree about the details, never about the frame.
TENDENCIES = ("traditional", "resume", "schedule", "margin", "network", "form",
              "consensus")

#: What each tendency is FOR, in one line — rendered on the page beside its
#: voters so a coach can see which frame keeps them out.
TENDENCY_BLURB = {
    "traditional": "Wins and losses first. What does the record say?",
    "resume": "What has been EARNED — wins against difficulty, not estimated "
              "strength.",
    "schedule": "Who you played. Corrects a record for the company it kept.",
    "margin": "Dominance. A 7-0 says more than a 4-3, and sets and games say "
              "more again.",
    "network": "The chain of results through the whole association — who is "
               "connected to the strongest evidence.",
    "form": "Demonstrated strength lately. When you won counts.",
    "consensus": "All nine systems, no favourite. The centre of the board.",
}


class Voter(NamedTuple):
    """One seat on the committee. `name` is the archive key and the display
    name; `weights` is the only field any ballot reads."""
    name: str
    kind: str                  # TV | Newspaper | Radio
    home: str                  # a real Jefferson city
    area: str                  # that city's area, per `schools.json`
    beat: str                  # Statewide | <area> | Small schools | Big schools | Non-Public
    tendency: str
    weights: dict


def _consensus(**tilt: float) -> dict:
    """A `consensus` vector: every system, DERIVED from `jhsaa_ratings.SYSTEMS`
    so a system added or dropped there cannot leave a stale hand-typed tuple
    behind, plus a named tilt (a multiplier on a system's flat share) and then
    renormalised. A bare call is the flat nine."""
    raw = {s: tilt.get(s, 1.0) for s in _SYSTEMS}
    tot = sum(raw.values())
    return {s: v / tot for s, v in raw.items()}


#: ‼️ THE TWENTY-FOUR OUTLETS ARE THE OWNER'S OWN LIST (2026-09) — call signs,
#: mastheads, types and markets exactly as handed over, in that order. An agent
#: drafted a roster of its own first and it was discarded: names are the owner's
#: to pick (the private-school-layer rule), and that holds for a media outlet as
#: firmly as for a school. What this module chose is only which PHILOSOPHY each
#: outlet votes on, and the weights inside it.
#:
#: Distribution: the owner's own shape (four voters each for the three frames a
#: selection argument is actually fought over — record, schedule, margin — and
#: three each for the rest), which comes to 24 across the seven tendencies. The
#: three Port Veles outlets deliberately sit in three DIFFERENT tendencies: a
#: market's paper, station and radio disagreeing is the texture, and three
#: outlets in one city voting one way would be one voter with three ballots.
#:
#: Ten of the twenty areas carry an outlet, weighted to the populous ones
#: (Selquah, Gold Valley, Ashbury Metro, Belmonte Metro, Sebastian Cape) — which
#: is how media markets actually fall, not an oversight. The `beat` field is
#: where the small-school, big-school and Non-Public perspectives are seated, and
#: it is identity for the page: no beat reaches a ballot.
VOTERS: tuple[Voter, ...] = (
    # --- traditional (4): the record, lightly corrected -----------------------
    Voter("KVLS 8", "TV", "Port Veles", "Selquah", "Big schools",
          "traditional", {"bt": 0.40, "win_pct": 0.35, "sor": 0.25}),
    Voter("Belmonte Tribune", "Newspaper", "Belmonte", "Belmonte Metro",
          "Belmonte Metro", "traditional",
          {"bt": 0.35, "win_pct": 0.35, "sor": 0.20, "markov": 0.10}),
    Voter("Belyakov Register", "Newspaper", "Belyakov", "Boise Frontier",
          "Boise Frontier", "traditional",
          {"win_pct": 0.45, "bt": 0.35, "sor": 0.20}),
    Voter("Mercer City Ledger", "Newspaper", "Mercer City", "Gold Valley",
          "Gold Valley", "traditional",
          {"bt": 0.45, "win_pct": 0.30, "sor": 0.25}),
    # --- resume (3): what was earned -----------------------------------------
    Voter("San Borondón Herald", "Newspaper", "San Borondón", "Sebastian Cape",
          "Sebastian Cape", "resume",
          {"sor": 0.40, "win_pct": 0.25, "bt": 0.20, "markov": 0.15}),
    Voter("Ashbury Gazette", "Newspaper", "Ashbury", "Ashbury Metro",
          "Ashbury Metro", "resume",
          {"sor": 0.45, "bt": 0.25, "win_pct": 0.20, "set_share": 0.10}),
    Voter("KLLE 1240 AM", "Radio", "Llerena", "Halbrook Basin", "Small schools",
          "resume", {"sor": 0.40, "bt": 0.30, "markov": 0.20, "win_pct": 0.10}),
    # --- schedule (4): who you played ----------------------------------------
    Voter("KBMT 6", "TV", "Belmonte", "Belmonte Metro", "Big schools",
          "schedule",
          {"sor": 0.40, "markov": 0.25, "massey_dual": 0.20, "bt": 0.15}),
    Voter("Serrano Daily Record", "Newspaper", "Serrano", "Halbrook Basin",
          "Halbrook Basin", "schedule",
          {"sor": 0.50, "massey_dual": 0.25, "bt": 0.25}),
    Voter("Aldecoa Dispatch", "Newspaper", "Aldecoa", "Silver Basin",
          "Silver Basin", "schedule",
          {"sor": 0.35, "markov": 0.30, "srs": 0.20, "bt": 0.15}),
    Voter("KCAS 980 AM", "Radio", "Caswell", "Belmonte Metro", "Belmonte Metro",
          "schedule",
          {"sor": 0.45, "srs": 0.25, "markov": 0.20, "win_pct": 0.10}),
    # --- margin (4): dominance -----------------------------------------------
    Voter("Gold Valley Journal", "Newspaper", "Valderra", "Gold Valley",
          "Gold Valley", "margin",
          {"massey_game": 0.35, "set_share": 0.30, "massey_dual": 0.20,
           "srs": 0.15}),
    Voter("KSCN 13", "TV", "San Cordero", "Cascade Divide", "Cascade Divide",
          "margin", {"massey_dual": 0.40, "srs": 0.30, "massey_game": 0.30}),
    Voter("Echevarria Times", "Newspaper", "Echevarria", "Silver Basin",
          "Silver Basin", "margin",
          {"set_share": 0.40, "massey_game": 0.35, "massey_dual": 0.25}),
    Voter("KSBO 11", "TV", "San Borondón", "Sebastian Cape", "Sebastian Cape",
          "margin",
          {"massey_dual": 0.35, "massey_game": 0.30, "srs": 0.20,
           "set_share": 0.15}),
    # --- network (3): the chain of results -----------------------------------
    Voter("KORL 105.3 FM", "Radio", "Orellana", "Boise Frontier",
          "Boise Frontier", "network",
          {"markov": 0.50, "bt": 0.20, "sor": 0.20, "elo": 0.10}),
    Voter("KPVN 1010 AM", "Radio", "Port Veles", "Selquah", "Selquah",
          "network",
          {"markov": 0.45, "sor": 0.25, "massey_dual": 0.20, "win_pct": 0.10}),
    Voter("KPRY 92.7 FM", "Radio", "Puerto de los Reyes", "Sebastian Cape",
          "Small schools", "network",
          {"markov": 0.55, "bt": 0.25, "srs": 0.20}),
    # --- form (3): who is playing well now -----------------------------------
    Voter("KBYK 4", "TV", "Belyakov", "Boise Frontier", "Boise Frontier",
          "form", {"elo": 0.40, "srs": 0.25, "win_pct": 0.20, "bt": 0.15}),
    Voter("Santa Michaela Sentinel", "Newspaper", "Santa Michaela", "Selquah",
          "Selquah", "form", {"elo": 0.45, "srs": 0.30, "markov": 0.25}),
    Voter("KHAR 9", "TV", "Harriman", "Kangas", "Non-Public", "form",
          {"elo": 0.50, "massey_dual": 0.30, "bt": 0.20}),
    # --- consensus (3): the centre of the board ------------------------------
    Voter("KASH 5", "TV", "Ashbury", "Ashbury Metro", "Statewide", "consensus",
          _consensus()),
    Voter("Port Veles Chronicle", "Newspaper", "Port Veles", "Selquah",
          "Statewide", "consensus", _consensus(win_pct=0.5)),
    Voter("KVDR 7", "TV", "Valderra", "Gold Valley", "Gold Valley",
          "consensus", _consensus(markov=1.6, sor=1.3)),
)

#: Name -> weights, the shape every ballot, archive row and template reads. The
#: richer identity lives on `VOTERS`; `MEMBERS` is derived so the two cannot
#: disagree.
MEMBERS: dict[str, dict[str, float]] = {v.name: dict(v.weights) for v in VOTERS}

#: `name -> Voter`, for the page's identity columns.
BY_NAME: dict[str, Voter] = {v.name: v for v in VOTERS}

#: How many voters each tendency seats (owner's shape: the three frames a
#: selection argument is fought over carry four).
TENDENCY_SEATS = {"traditional": 4, "resume": 3, "schedule": 4, "margin": 4,
                  "network": 3, "form": 3, "consensus": 3}

# --- import-time invariants ---------------------------------------------------
assert len(VOTERS) == len(MEMBERS) == 24, "a voter name is duplicated"
assert set(v.tendency for v in VOTERS) == set(TENDENCIES)
assert set(TENDENCY_BLURB) == set(TENDENCIES) == set(TENDENCY_SEATS)
assert sum(TENDENCY_SEATS.values()) == len(VOTERS)
for _t, _n in TENDENCY_SEATS.items():
    assert sum(1 for v in VOTERS if v.tendency == _t) == _n, f"{_t}: seats"
for _v in VOTERS:
    # A vector naming a system that does not exist would silently contribute
    # nothing (`ballot` renormalises over what it finds), so the ballot would
    # still look reasonable while reading a philosophy nobody wrote.
    assert set(_v.weights) <= set(_SYSTEMS), f"{_v.name}: unknown system"
    assert abs(sum(_v.weights.values()) - 1.0) < 1e-9, f"{_v.name}: weights"
# ‼️ Three outlets share Port Veles and two share four other markets: a market's
# paper, station and radio must not all vote the same frame, or one city casts
# one opinion several times.
for _c in {v.home for v in VOTERS}:
    _ts = [v.tendency for v in VOTERS if v.home == _c]
    assert len(set(_ts)) == len(_ts), f"{_c}: two outlets on one tendency"


#: ‼️ A LOCK IS A SHARE OF THE ELECTORATE, NEVER A COUNT (owner rule 2026-09).
#: At five voters a lock was literal unanimity, which was a fair reading of
#: "every reasonable interpretation thinks this team belongs". With seven
#: deliberately divergent philosophies — let alone twenty-one voters — unanimity
#: is brittle: one specialist can erase almost every lock. Six of seven is the
#: owner's threshold and 18 of 21 is exactly that, which is why the share is
#: written as the fraction and the count derived from it: change the roster size
#: and the bar moves with it.
LOCK_SHARE = 6.0 / 7.0
#: The DISPLAY tier between a lock and the fringe (owner: 10-17 of 21 is
#: "serious consideration"). A label only — the Borda count sees every candidate
#: on at least one ballot either way.
BUBBLE_SHARE = 10.0 / 21.0


def lock_threshold(n_voters: int | None = None) -> int:
    """How many at-large ranges a team must appear on to be a LOCK.
    Derived from `LOCK_SHARE` so it tracks the roster: 21 of 24 at the current size, and the
    same 6/7 bar the owner set at seven philosophies."""
    n = len(MEMBERS) if n_voters is None else n_voters
    return max(1, math.ceil(LOCK_SHARE * n - 1e-9))


def bubble_threshold(n_voters: int | None = None) -> int:
    """How many ranges make a candidate a `Bubble` rather than `Fringe` team —
    the owner's "serious consideration" band, 12 of 24. Display only."""
    n = len(MEMBERS) if n_voters is None else n_voters
    return max(1, math.ceil(BUBBLE_SHARE * n - 1e-9))


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
    """Every voter's ballot. Changing one voter's weights changes only that
    voter's ballot — each is an independent read of the same ranks."""
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
       "ballots": {voter: full candidate ordering},
       "ranges": {voter: that voter's at-large range},
       "appearances": {name: ranges made}, "lock_at": int, "bubble_at": int,
       "status": {name: Qualified|Lock|In|Bubble|Fringe|Out},
       "weights": MEMBERS, "voters": [identity rows]}

    Steps:
      1. AUTOMATIC BIDS — district champions who missed the road.
      2. LOCKS — in the at-large range (each voter's top N remaining
         candidates, N = seats - automatics) on `lock_threshold()` of the
         ballots (21 of 24), never on all of them.
      3. THE BUBBLE — every remaining team on at least one range. Borda
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

    # Step 2 — locks: on `lock_threshold()` of the ranges (21 of 24). ‼️ NOT
    # unanimity: with seven divergent philosophies one specialist voter erases
    # almost every lock, so the bar is a SHARE of the electorate (`LOCK_SHARE`)
    # and 21 of 24 is stronger evidence in absolute terms than the old 5 of 5
    # while still allowing three principled dissents.
    lock_at = lock_threshold(len(MEMBERS))
    locks = sorted((n for n in candidates
                    if n not in auto and appearances[n] >= lock_at),
                   key=lambda n: (-appearances[n], n))
    locks = locks[:open_seats]

    # Step 3 — the bubble: on at least one range and not already in. Borda over
    # the FULL ordering of the bubble population, locks and automatics removed
    # first. ‼️ The `Bubble`/`Fringe` split below is a LABEL and never a cut —
    # nothing pre-cuts the pool (the spec's rule), so a team on one ballot is
    # still scored here.
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

    # Status: the owner's bands (2026-09). A larger electorate can say how close
    # a miss was, which 5/5-4/5-3/5 could not — `Bubble` is serious
    # consideration (>= `bubble_threshold()` ranges, 12 of 24), `Fringe` is a
    # team some voter had in but most did not.
    bubble_at = bubble_threshold(len(MEMBERS))
    status: dict[str, str] = {}
    for n in ratings["teams"]:
        if n in road:
            status[n] = "Qualified"
        elif n in locks:
            status[n] = "Lock"
        elif n in chosen:
            status[n] = "In"
        elif appearances.get(n, 0) >= bubble_at:
            status[n] = "Bubble"
        elif appearances.get(n, 0) >= 1:
            status[n] = "Fringe"
        else:
            status[n] = "Out"

    return {"selected": selected, "auto": auto, "locks": locks,
            "borda": borda, "seed_borda": seed_borda,
            "ballots": cand_ballots, "ranges": ranges, "status": status,
            "seats": seats,
            # How many of the ranges each candidate made — the number the page
            # reports as "18 of 24", and the reason the electorate grew.
            "appearances": {n: appearances[n] for n in candidates},
            "lock_at": lock_at, "bubble_at": bubble_at,
            # The whole electorate as it voted, so an archived selection renders
            # with ITS voters and not today's (the `pi` rule).
            "weights": {m: dict(w) for m, w in MEMBERS.items()},
            "voters": [{"name": v.name, "kind": v.kind, "home": v.home,
                        "area": v.area, "beat": v.beat,
                        "tendency": v.tendency} for v in VOTERS]}


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
_STATE_PHASES = ("state", "toc_qualifier", "toc")   # keep in step with `jhsaa.TOC_PHASES`


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

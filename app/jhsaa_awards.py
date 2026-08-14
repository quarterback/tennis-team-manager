"""
JHSAA postseason awards — RÉSUMÉ selections, not a rating leaderboard.

Owner SOP 2027-08. The old system sorted every player by (wins, win%, OVR) and
took the top six for All-State and six per district; for an association of ~500
programs that is both too small and the wrong question. These awards ask what
HAPPENED this season, and they ask it from the match log (`TeamSeason.matches`)
rather than from ability ratings.

WHAT IS SELECTED, per classification and gender, in ONE pass (there is no
district vote feeding a later state vote — everything below comes off the same
completed season):

  * State Player of the Year
  * All-State First / Second / Third team — plus a FOURTH in 7A, whose talent
    pool is substantially larger — then Honorable Mention
  * District Player of the Year, for every district
  * one All-District team per district (not first/second/third)

and ONCE PER GENDER, across every classification together (`region_awards`):

  * one All-Region team per geographic region — there is no 7A All-Region team,
    there is a Gold Valley All-Region team

The geographic honours OVERLAP on purpose — nobody is dropped from a lower team
for having won a higher one, so a State POY is normally also All-State,
All-Region and All-District.

An All-State team and an All-District team are the same size (owner, 2027-08):
ten singles selections and eight DOUBLES TEAMS apiece — eighteen selections,
twenty-six athletes.

‼️ DOUBLES HONOURS ARE AWARDED TO PAIRINGS, NOT TO INDIVIDUAL DOUBLES PLAYERS
(owner correction, 2027-08). "Eight doubles" means eight doubles TEAMS — sixteen
athletes — and a doubles selection is two players who actually competed
TOGETHER. This module therefore has two candidate entities, not one:

  * a PLAYER, for singles (`_collect`)
  * a PARTNERSHIP, for doubles (`_pairs`) — keyed on the two pids, with a
    résumé built ONLY from the matches those two played together, rated against
    the OPPOSING PAIR rather than against individual opponents.

A player who partnered around produces SEVERAL candidates, one per partnership,
each judged on its own body of work; a partnership needs `MIN_PAIR_MATCHES`
together before it is a partnership at all. No athlete may hold two slots on the
same honours team, in either direction — see `_take`'s `used` set and the
primary-discipline rule below.

WHICH CATEGORY AN ATHLETE IS CONSIDERED IN is whichever they were BETTER at
(owner: "kids can't play singles and doubles in the same match so just take
their better thing and give them that"). "Better" is STANDING, not a raw score —
where they sit in the gender-wide singles field against where their strongest
partnership sits in the gender-wide field of partnerships, both as percentiles
of the same shape (`_assign_primary`, ties to singles). One category per athlete
is what makes "no athlete in both halves of one team" true by construction
rather than by a post-hoc filter.

HOW A RÉSUMÉ IS SCORED (the SOP's criteria, in the order it lists them):

  1. RECORD — wins and losses, volume, and consistency. Credit is signed and
     accumulated per match, so a long strong season outranks a short one
     without a bare win% ever being the measure.
  2. POSITION — see the flight section below. This is STRUCTURAL.
  3. OPPOSITION — a first pass rates every candidate by a shrunk win rate; the
     second pass weighs each result by who it came against. Strength of
     schedule is therefore per-opponent (per-opposing-PAIR in doubles), not
     per-opposing-team.
  4. QUALITY WINS — a win's value scales with the opponent's rating, so beating
     serious candidates is the fastest way up the board.
  5. GOOD LOSSES — a loss's cost SHRINKS with the opponent's rating. Losing to
     the best player in the class is nearly free; losing to a weak one is not.
  6. HEAD-TO-HEAD — among candidates whose résumés are close (`H2H_BAND`),
     direct results reorder them. Evidence, not an override: it only moves
     candidates already tied on everything else.
  7. POSTSEASON — Sectionals through State count, weighted up (`PHASE_WEIGHT`).
     Jefferson has no individual tournament and none is invented; this is the
     team postseason a player actually played.
  8. TEAM — never an eligibility gate. It enters only through opposition
     quality: playing (and beating) good players is what a good team gives you.
  9. THIS SEASON ONLY — nothing here reads class year, talent, potential,
     reputation or last year's honours. GRADE IS NEVER A FACTOR.

‼️ FLIGHT WEIGHTING IS STRUCTURAL, NOT A SMALL BONUS (owner correction,
2027-08). See `FLIGHT_ALPHA` and `FLIGHT_FLOOR`.
"""
from __future__ import annotations

from collections import Counter, defaultdict

# --- shape of the awards -----------------------------------------------------
# An All-State team and an All-District team are the SAME SIZE (owner, 2027-08):
# ten singles selections and eight DOUBLES TEAMS apiece.
TEAM_SINGLES = 10
TEAM_DOUBLES = 8               # ‼️ eight PAIRS — sixteen athletes
AS_SINGLES, AS_DOUBLES = TEAM_SINGLES, TEAM_DOUBLES
AR_SINGLES, AR_DOUBLES = TEAM_SINGLES, TEAM_DOUBLES
AD_SINGLES, AD_DOUBLES = TEAM_SINGLES, TEAM_DOUBLES

# ALL-REGION sits between All-State and All-District (owner, 2027-08). The region
# is the school's AREA — the association's existing geography, the one its
# districts are named after — never a second awards-only map. One team per
# region, no first/second/third, and deliberately no Region Player of the Year.
#
# ‼️ AND IT IS CLASS-BLIND — there is no 7A All-Region team, only a Gold Valley
# All-Region team (owner rule 2027-08, and how it works in real life). See
# `region_awards`; the guard below is now nearly vacant, since a region taken
# whole holds ~40 programs rather than the four or five a class-region did.
MIN_REGION_PROGRAMS = 4

# ‼️ A BIG REGION CROWNS TWO TEAMS (owner rule 2027-08). The association's regions
# are nowhere near the same size — Halbrook Basin has 115 boys' programs and North
# Range has 17 — so one team of ten singles is a far scarcer honour in one than in
# the other. Regions at or above this many programs crown a First AND a Second
# Team; the rest crown a single unnumbered All-Region team.
#
# Derived from the PROGRAM COUNT, never a list of region names: the association's
# shape changes when schools are added, and the reason for the rule is the size,
# not the name. Measured — boys: Halbrook 115 · Gold Valley 65 · Harborline 51 ·
# South Coast 49 · Ashbury Metro 45, then a clean break to Sage Plains 36. Girls
# is the same five, 50-128 against 38. So 45 splits exactly the regions the owner
# named, plus South Coast, which is BIGGER than Ashbury Metro on the boys' side
# and so cannot be left out on the owner's own reasoning.
AR_TIER2_MIN_PROGRAMS = 45

# ‼️ AND THE BIGGEST REGION GETS AN HONORABLE MENTION TOO (owner rule 2027-08):
# "Halbrook should have honorable mention too, it's so much bigger than everywhere
# else." It is not a close call — Halbrook Basin has 115 boys' / 128 girls'
# programs and the next region down, Gold Valley, has 65 / 77. Two full teams
# still only reach 36 athletes out of a region the size of a small classification.
#
# Same rule as All-State's HM and for the same reason: a THRESHOLD, not a team.
# No slot count, so the size is an OUTPUT of how deep the region actually was,
# and at most two ENTRIES per school.
AR_HM_MIN_PROGRAMS = 100
AS_TIERS = {"7A": 4}           # numbered teams; everyone else gets three
AS_TIERS_DEFAULT = 3

# ‼️ HONORABLE MENTION IS A THRESHOLD, NOT A TEAM (owner, 2027-08). There is no
# slot count: after the numbered teams are filled, HM takes the candidates whose
# résumé is still clearly of statewide award quality — "not strong enough to
# displace someone off the final numbered team, but legitimately in the
# conversation". So a deep classification produces a big HM group and a thin one
# produces almost none, and a good season can miss HM entirely, which is what
# makes the honour mean anything.
#
# The cutoff is measured against the numbered teams themselves rather than set as
# an absolute number, because résumé credit scales with how much tennis a
# classification played: HM reaches `HM_DROP` of the way down the numbered teams'
# own spread, below the weakest of them. `HM_MAX_MULT` is a runaway guard, not a
# target — if it ever binds, the threshold is the thing to look at (it did bind,
# at the first value tried, which made HM a fixed 27 in every classification and
# quietly reintroduced the fixed-size team this rule exists to remove).
#
# ⚠️ The two-per-school cap counts ENTRIES, not athletes: a doubles pairing from
# a school is ONE entry against the cap even though it honours two players.
HM_DROP = 0.10
HM_MAX_MULT = 2.5              # runaway guard on the TOTAL, never a target
HM_PER_SCHOOL = 2              # HM only — the numbered teams have no such cap
# ‼️ THE REGION'S HM IS CAPPED AT ONE ENTRY PER SCHOOL (owner rule 2027-08), half
# the All-State cap. All-Region HM exists in exactly one region, and that region
# is a fifth of the association — without a tighter cap its deepest programs
# would take the tail of it two at a time. An entry is one singles player OR one
# doubles pairing, so a school takes one or the other, never both.
AR_HM_PER_SCHOOL = 1

TEAM_NAMES = ["First Team", "Second Team", "Third Team", "Fourth Team"]

# ‼️ FLIGHT WEIGHTING IS STRUCTURAL, NOT A SMALL BONUS (owner correction,
# 2027-08). Position is part of the RÉSUMÉ, not a tiebreak applied afterwards:
# 19-7 at #1 singles is a substantially more impressive season than 25-1 at #5,
# because the #1 spent the year playing every other program's best player. Two
# mechanisms carry that, and BOTH are load-bearing:
#
#   1. `FLIGHT_ALPHA` — an exponent on `jhsaa.FLIGHT_WEIGHTS` (1.0 = the
#      association's table as written, 0 = flat). It never inverts the order of
#      the flights, only how far apart they sit. The three levels ask different
#      questions, so they sit differently:
#
#        State    the table as written. A dominant #1 outranks the same record
#                 accumulated at #4, which is the honest statewide read.
#        Region   very nearly as hard — this is where the excellent #1/#2/#3 who
#                 just missed All-State belongs.
#        District softened, because a district is a smaller pond: a #4 who went
#                 24-2 produced one of the district's outstanding seasons. It is
#                 softened, NOT flattened — the hierarchy still holds.
#
#   2. `FLIGHT_FLOOR` — the flight band that DOMINATES each level, past which a
#      selection needs extraordinary evidence rather than merely a good score.
#      State is a #1/#2 honour; Region reaches #3; District has no floor. A
#      below-floor candidate is admitted only by `_extraordinary`: a near-perfect
#      record AND at least one win over an opponent who played at or above the
#      floor. That is the "beat people who were higher up the card" test, and it
#      is checked against the match log rather than assumed.
#
# The weighting alone was NOT enough at the lower levels — softening it to open
# the district up also opened the state and region lists to #4s with fat records
# against nobody. The floor is what makes flight structural instead of a dial.
FLIGHT_ALPHA = {"state": 1.0, "region": 0.90, "district": 0.70}
FLIGHT_FLOOR = {"state": 2, "region": 3, "district": 0}    # 0 = no floor
EXTRAORDINARY_PCT = 0.88       # a below-floor singles résumé must be near-perfect…
# …and must contain a win over somebody who played at or above the floor.

# --- scoring dials -----------------------------------------------------------
PRIOR = 2.0                    # Laplace shrink on the first-pass win rate
WIN_BASE = 0.55                # a win is worth this before opponent quality…
WIN_SLOPE = 1.30               # …plus this much of the opponent's rating
LOSS_BASE = 0.85               # a loss costs this…
GOOD_LOSS = 1.15               # …reduced by this much of the opponent's rating
PHASE_WEIGHT = 1.45            # postseason matches count for more
MIN_MATCHES = 6                # below this a singles résumé is too thin to rank
MIN_PAIR_MATCHES = 6           # …and below this two players are not a partnership
H2H_BAND = 0.06                # résumé gap inside which head-to-head decides
H2H_SWAP_PASSES = 3


def _is_singles(slot: str) -> bool:
    return slot.startswith("S")


def _flight_no(slot: str) -> int:
    """The number off a slot label — "S3" → 3. Used for the floor test."""
    try:
        return int(slot[1:])
    except (ValueError, IndexError):
        return 99


def _weight(slot: str, phase: str, postseason, alpha: float = 1.0) -> float:
    from .jhsaa import FLIGHT_WEIGHTS
    w = FLIGHT_WEIGHTS.get(slot, 0.25) ** alpha
    return w * (PHASE_WEIGHT if phase in postseason else 1.0)


def _pair_key(pids) -> tuple:
    return tuple(sorted(pids))


# --- the two candidate entities ----------------------------------------------

def _collect(teams) -> dict:
    """{pid: {...}} — every player's season, split singles vs doubles."""
    out: dict[str, dict] = {}
    for t in teams:
        for pid, log in t.matches.items():
            p = t.by_pid.get(pid)
            if p is None:
                continue
            rec = out.setdefault(pid, {
                "pid": pid, "pids": (pid,),
                "name": p.name, "names": (p.name,),
                "grade": p.grade, "grades": (p.grade,),
                "school": t.school.name, "district": t.school.district,
                # The REGION is the school's area — the association's existing
                # geography, taken from school data, never parsed off a display
                # string.
                "region": t.school.area,
                "group": t.school.group, "log": [],
            })
            rec["log"].extend(log)
    return out


def _split(rec: dict) -> tuple[list, list]:
    s = [m for m in rec["log"] if _is_singles(m[0])]
    d = [m for m in rec["log"] if not _is_singles(m[0])]
    return s, d


def _assign_primary(players: dict, pairs: dict) -> None:
    """Give every athlete ONE category — the one they were BETTER at.

    ‼️ Owner rule, 2027-08: *"kids can't play singles and doubles in the same
    match so just take their better thing and give them that."* An athlete is
    honoured once, in the discipline where their season actually stands higher,
    and is not a candidate in the other.

    "Better" cannot be a raw score comparison — a singles résumé and a
    partnership's are on different flight weights and different volumes, so the
    numbers are not the same currency. It is STANDING: where the athlete sits in
    the gender-wide singles field, against where their strongest partnership sits
    in the gender-wide field of partnerships. Both are percentiles of the same
    shape, so they compare honestly. No qualifying record in a discipline means a
    standing of zero there; a dead tie goes to singles.

    (This replaces an earlier rule that assigned on PARTICIPATION — whichever
    discipline they played more of. That was defensible and it was not what the
    owner asked for: a player who filled in at doubles for most of a rotation
    while producing the region's best singles season was being judged as a
    doubles player.)"""
    def _pct(scores: dict) -> dict:
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        n = len(ranked) or 1
        return {k: 1.0 - i / n for i, (k, _v) in enumerate(ranked)}

    s_pct = _pct({pid: r["s"] for pid, r in players.items() if r["s_n"] >= MIN_MATCHES})
    d_pct = _pct({k: pr["d"] for k, pr in pairs.items() if pr["d_n"] >= MIN_PAIR_MATCHES})
    best_pair: dict[str, float] = {}
    for k, v in d_pct.items():
        for pid in k:
            if v > best_pair.get(pid, 0.0):
                best_pair[pid] = v
    for pid, rec in players.items():
        rec["primary"] = "d" if best_pair.get(pid, 0.0) > s_pct.get(pid, 0.0) else "s"


def _pairs(players: dict) -> dict:
    """{(pidA, pidB): {...}} — PARTNERSHIPS, from matches played TOGETHER.

    A doubles honour goes to two players who actually competed as a team, so the
    candidate entity is the pairing and its résumé is the matches those two
    played side by side — never a doubles record accumulated across a season of
    different partners. A player who partnered around therefore produces several
    candidates, each judged on its own body of work.

    Both members log the same match, so each is taken ONCE, from the higher pid's
    side; the pair itself is keyed on the sorted pids so the two halves of a
    partnership can never disagree about its identity.

    EVERY partnership is built here, whatever its members' primary discipline —
    the primary is DECIDED from these ratings (`_assign_primary`), so gating the
    pairs on it first would be circular."""
    out: dict[tuple, dict] = {}
    for pid, rec in players.items():
        for m in rec["log"]:
            slot, _won, _ph, opps, partner, _os = m
            if _is_singles(slot) or not partner or partner >= pid:
                continue                    # log it once, from the higher pid
            mate = players.get(partner)
            if mate is None:
                continue
            key = (partner, pid)
            pr = out.get(key)
            if pr is None:
                pr = out[key] = {
                    "pid": partner, "pids": key,
                    "name": f"{mate['name']} / {rec['name']}",
                    "names": (mate["name"], rec["name"]),
                    "grade": mate["grade"], "grades": (mate["grade"], rec["grade"]),
                    "school": rec["school"], "district": rec["district"],
                    "region": rec["region"], "group": rec["group"], "log": [],
                }
            pr["log"].append(m)
    return out


# --- rating ------------------------------------------------------------------

def _shrunk(log) -> float:
    w = sum(1 for m in log if m[1])
    n = len(log)
    return (w + PRIOR / 2) / (n + PRIOR) if n else 0.5


def _base_singles(players: dict) -> dict:
    """First pass — a shrunk singles win rate per player. Deliberately crude: it
    exists only to give the second pass something to weigh opponents by."""
    return {pid: _shrunk(_split(rec)[0]) for pid, rec in players.items()}


def _base_pairs(pairs: dict) -> dict:
    """The same first pass, PAIR against PAIR."""
    return {k: _shrunk(pr["log"]) for k, pr in pairs.items()}


def _resume(log, q_of, postseason, alpha: float = 1.0) -> float:
    """Signed résumé credit — the SOP's criteria 1-5 and 7, per match.

    `q_of(opps)` returns the opposition's rating: the mean of the individual
    opponents in singles, the OPPOSING PAIR's rating in doubles. `alpha` is the
    level's flight emphasis (`FLIGHT_ALPHA`)."""
    total = 0.0
    for slot, won, phase, opps, _partner, _os in log:
        w = _weight(slot, phase, postseason, alpha)
        q = q_of(opps)
        if won:
            total += w * (WIN_BASE + WIN_SLOPE * q)
        else:
            total -= w * max(0.05, LOSS_BASE - GOOD_LOSS * q)
    return total


def _q_singles(base: dict):
    def q(opps):
        return (sum(base.get(o, 0.5) for o in opps) / len(opps)) if opps else 0.5
    return q


def _q_pairs(base: dict):
    def q(opps):
        return base.get(_pair_key(opps), 0.5) if len(opps) == 2 else 0.5
    return q


# --- head-to-head ------------------------------------------------------------

def _h2h_players(a: dict, b: dict) -> int:
    """Net head-to-head between two players: +1 a leads, -1 b leads, 0 level."""
    net = 0
    for slot, won, _ph, opps, _pt, _os in a["log"]:
        if _is_singles(slot) and b["pid"] in opps:
            net += 1 if won else -1
    return (net > 0) - (net < 0)


def _h2h_pairs(a: dict, b: dict) -> int:
    """Net head-to-head between two PARTNERSHIPS — the pairs that met, not the
    individuals inside them."""
    net = 0
    for _slot, won, _ph, opps, _pt, _os in a["log"]:
        if _pair_key(opps) == b["pids"]:
            net += 1 if won else -1
    return (net > 0) - (net < 0)


def _apply_h2h(ranked: list, key: str, h2h) -> list:
    """Reorder CLOSE candidates on direct results (SOP criterion 6). Only pairs
    already within `H2H_BAND` can move, so one match never erases a season."""
    out = list(ranked)
    for _ in range(H2H_SWAP_PASSES):
        moved = False
        for i in range(len(out) - 1):
            a, b = out[i], out[i + 1]
            if a[key] - b[key] <= H2H_BAND and h2h(b, a) > 0:
                out[i], out[i + 1] = b, a
                moved = True
        if not moved:
            break
    return out


# --- the flight floor: where "structural" stops being a weight ---------------

def _extraordinary(rec: dict, floor: int, flight_of: dict) -> bool:
    """Is a below-floor singles résumé extraordinary enough to be honoured here?

    Two tests, both off the match log and neither of them a score comparison
    (a lower flight can rarely out-SCORE a higher one, which is the point of the
    weighting — so scoring it again would just re-ask the question the weights
    already answered):

      * the record must be near-perfect (`EXTRAORDINARY_PCT`), and
      * at least one of those wins must have come against somebody who played
        AT OR ABOVE the floor — the evidence that the player could have held a
        higher court, rather than a fat record against the bottom of the class.
    """
    n, w = rec["s_n"], rec["s_w"]
    if not n or w / n < EXTRAORDINARY_PCT:
        return False
    for slot, won, _ph, opps, _pt, _os in rec["log"]:
        if won and _is_singles(slot) and any(flight_of.get(o, 99) <= floor for o in opps):
            return True
    return False


def _rank_singles(players: dict, pool, scope: str, flight_of: dict) -> list:
    """Singles candidates for one scope, best résumé first.

    `pool` is a set of PIDS — the dicts are unhashable and, more to the point, a
    pid is the identity everything else in the archive keys on.

    The scope decides BOTH how hard flight is weighted (`FLIGHT_ALPHA`) and how
    far down the card the honour reaches at all (`FLIGHT_FLOOR`), so a district
    ranking is genuinely a different question from a state one rather than the
    same list cut lower."""
    sk = f"s:{scope}"
    floor = FLIGHT_FLOOR[scope]
    got = [p for pid, p in players.items()
           if pid in pool and p["primary"] == "s" and p["s_n"] >= MIN_MATCHES
           and (not floor or p["s_flight"] <= floor
                or _extraordinary(p, floor, flight_of))]
    got.sort(key=lambda r: (-r[sk], -r["s_n"], r["name"]))
    return _apply_h2h(got, sk, _h2h_players)


def _rank_pairs(pairs: dict, pool, scope: str) -> list:
    """Doubles candidates — PARTNERSHIPS — for one scope, best résumé first.

    `pool` is a set of pids; a partnership belongs to a region/district when its
    players do (they are always team-mates, so both or neither)."""
    sk = f"d:{scope}"
    got = [pr for k, pr in pairs.items()
           if k[0] in pool and pr["d_n"] >= MIN_PAIR_MATCHES]
    got.sort(key=lambda r: (-r[sk], -r["d_n"], r["name"]))
    return _apply_h2h(got, sk, _h2h_pairs)


# --- geographic breadth: a soft coaches-vote consideration, NEVER a quota ------
# Owner rule: when candidates are genuinely close, a selector may reasonably
# favour breadth rather than handing every marginal slot to one school or corner
# of the map — and if one area simply produced the best candidates, they can all
# be selected. So breadth only ever reorders inside `BREADTH_BAND`, the same
# shape as head-to-head: a clearly superior résumé is untouchable, and there is
# no quota anywhere.
BREADTH_BAND = 0.05      # fraction of the field's résumé spread that counts as "tied"


def _take(ranked: list, n: int, key_for_row, breadth_keys: tuple,
          used: set | None = None) -> list:
    """Pick `n` from `ranked`, resolving genuine near-ties toward breadth.

    `used` is the set of pids already holding a slot on THIS honours team. A
    candidate that would seat an athlete twice on one team is skipped and the
    slot goes to the next one down — so a player with two strong partnerships is
    honoured for the better of them and the second pairing does not take a place
    an unrelated pair earned."""
    if not ranked:
        return []
    sk = key_for_row
    span = (ranked[0][sk] - ranked[-1][sk]) or 1.0
    band = BREADTH_BAND * span
    seen = {k: defaultdict(int) for k in breadth_keys}
    pool, out = list(ranked), []
    while pool and len(out) < n:
        lead = pool[0][sk]
        tied = [i for i, r in enumerate(pool) if lead - r[sk] <= band]
        # Among the genuinely tied, prefer the least-represented; the résumé
        # order breaks any remaining tie, so this never reaches past the band.
        pick = min(tied, key=lambda i: (sum(seen[k][pool[i][k]] for k in breadth_keys), i))
        rec = pool.pop(pick)
        if used is not None and any(p in used for p in rec["pids"]):
            continue
        for k in breadth_keys:
            seen[k][rec[k]] += 1
        if used is not None:
            used.update(rec["pids"])
        out.append(rec)
    return out


_FLIGHT_LABEL = {"S": "Singles", "D": "Doubles"}


def _primary_flight(rec: dict, key: str) -> str:
    """The flight this selection mostly played, in that discipline — "#1 Singles".

    Position materially changes an award, so the row carries it: it is what makes
    an unbeaten #5 on the Fourth Team legible next to a 23-5 #1 on the First."""
    want = "S" if key == "s" else "D"
    slots = Counter(m[0] for m in rec["log"] if m[0][:1] == want)
    if not slots:
        return ""
    slot = max(slots.items(), key=lambda kv: (kv[1], -_flight_no(kv[0])))[0]
    return f"#{slot[1:]} {_FLIGHT_LABEL[want]}"


def _flight_seat(rec: dict, key: str) -> int:
    want = "S" if key == "s" else "D"
    slots = Counter(m[0] for m in rec["log"] if m[0][:1] == want)
    if not slots:
        return 99
    return _flight_no(max(slots.items(), key=lambda kv: (kv[1], -_flight_no(kv[0])))[0])


def _row(rec: dict, key: str, score: float | None = None) -> dict:
    """The award row that gets archived — the résumé, never the ability.

    A doubles row is ONE selection describing TWO athletes: `pids`/`names` carry
    the pairing and `pid`/`name` stay populated so every older reader (the school
    page's honours ledger, the career line) keeps working. Anything that asks
    "was this person honoured?" must read `pids`, not `pid` — that is what
    `row_pids` is for."""
    return {"pid": rec["pid"], "pids": list(rec["pids"]),
            "name": rec["name"], "names": list(rec["names"]),
            "grade": rec["grade"], "grades": list(rec["grades"]),
            "school": rec["school"], "district": rec["district"],
            "region": rec["region"],
            "wins": rec[key + "_w"], "losses": rec[key + "_n"] - rec[key + "_w"],
            "kind": "singles" if key == "s" else "doubles",
            "flight": _primary_flight(rec, key),
            "score": round(rec[key] if score is None else score, 4)}


def row_pids(row: dict) -> list:
    """Every athlete an award row honours — one for a singles row, TWO for a
    doubles pairing. Every "did this player win X?" lookup goes through here."""
    if not row:
        return []
    return list(row.get("pids") or ([row["pid"]] if row.get("pid") else []))


def _hm_cut(scores: list[float]) -> float:
    """The statewide-recognition line for one discipline, from the numbered
    teams' own spread — see `HM_DROP`. Everything below this stops being an
    award and starts being a list."""
    if not scores:
        return float("inf")
    top, last = max(scores), min(scores)
    return last - HM_DROP * max(0.0, top - last)


def _honorable_mention(tiers, s_rank, d_rank, si, di, scope="state",
                       per_school=HM_PER_SCHOOL) -> list:
    """Candidates past the numbered teams whose résumé still clears the bar.

    Not "the next N": each discipline gets its own cutoff from the numbered
    selections it produced, candidates below it are simply not honoured, and the
    size of the group is therefore an OUTPUT — a deep classification honours
    more than a thin one, which is the point.

    ‼️ AT MOST `HM_PER_SCHOOL` ENTRIES from any one school (owner, 2027-08), and
    the cap is HM-ONLY: a school may take as many First/Second/Third/Fourth Team
    places as its résumés earn. A doubles PAIRING is one entry against the cap
    even though it honours two athletes. When a school has more qualifiers than
    the cap the strongest are kept and the rest are simply dropped — nothing
    backfills the space, because HM has no quota to fill."""
    placed = {p for t in tiers for r in t["players"] for p in row_pids(r)}
    cands: list[tuple[float, dict]] = []
    for rank, start, key in ((s_rank, si, "s"), (d_rank, di, "d")):
        sk = f"{key}:{scope}"
        cut = _hm_cut([r[sk] for r in rank[:start]])
        for rec in rank[start:]:
            if rec[sk] < cut or any(p in placed for p in rec["pids"]):
                continue
            cands.append((rec[sk], rec))
    cands.sort(key=lambda kv: (-kv[0], kv[1]["name"]))
    per_school_n: dict[str, int] = defaultdict(int)
    used: set[str] = set()
    out, limit = [], int((TEAM_SINGLES + TEAM_DOUBLES) * HM_MAX_MULT)
    for score, rec in cands:
        if (per_school_n[rec["school"]] >= per_school or len(out) >= limit
                or any(p in used for p in rec["pids"])):
            continue
        per_school_n[rec["school"]] += 1
        used.update(rec["pids"])
        out.append(_row(rec, "s" if len(rec["pids"]) == 1 else "d", score))
    return out


def _row_flight(row: dict) -> int:
    """The flight number off a rendered row — "#3 Singles" → 3."""
    head = (row.get("flight") or "").lstrip("#").split(" ")[0]
    return _flight_no("S" + head)


def _flight_report(rows, scope: str) -> dict:
    """‼️ THE MANDATORY FLIGHT SANITY CHECK (owner, 2027-08).

    Before a singles honour team is finalised, every below-floor selection is
    inspected. `_rank_singles` already refuses to offer one that has not cleared
    `_extraordinary`, so this cannot fail silently — but the check has to be
    VISIBLE, because "the weighting looks about right" is exactly how flight
    stopped being structural the first time. The report is archived with the
    awards and rendered on the honours page, so a season can be audited without
    re-running the selector."""
    singles = [r for r in rows if r["kind"] == "singles"]
    floor = FLIGHT_FLOOR[scope]
    flights = Counter(r["flight"] for r in singles)
    below = [r for r in singles if floor and _row_flight(r) > floor]
    return {"floor": floor, "total": len(singles),
            "flights": {k: v for k, v in sorted(flights.items())},
            "below_floor": len(below),
            "exceptions": [{"name": r["name"], "school": r["school"],
                            "flight": r["flight"],
                            "record": f"{r['wins']}-{r['losses']}"} for r in below]}


def build_pool(teams, postseason=None) -> dict:
    """The candidate pool for a WHOLE GENDER, rated once.

    Built over every classification together, deliberately, for the same reason
    `jhsaa.power_index` is: **non-district play crosses classifications**, so a
    7A player's schedule is full of 6A and 5A opponents. Rating each class in
    isolation cut those edges out of the graph and silently defaulted every
    cross-class opponent to an average 0.5.

    It is also what makes an All-Region team possible at all — that honour is
    region-wide and class-blind (see `region_awards`), so it needs one ranking
    that spans the association."""
    from .jhsaa import POSTSEASON
    postseason = POSTSEASON if postseason is None else postseason
    players = _collect(teams)
    for rec in players.values():
        sl, dl = _split(rec)
        rec["s_n"], rec["s_w"] = len(sl), sum(1 for m in sl if m[1])
        rec["s_flight"] = _flight_seat(rec, "s")
    pairs = _pairs(players)
    qs, qp = _q_singles(_base_singles(players)), _q_pairs(_base_pairs(pairs))
    for rec in players.values():
        sl = [m for m in rec["log"] if _is_singles(m[0])]
        for scope, alpha in FLIGHT_ALPHA.items():
            rec[f"s:{scope}"] = _resume(sl, qs, postseason, alpha)
        rec["s"] = rec["s:state"]
    for pr in pairs.values():
        pr["d_n"] = len(pr["log"])
        pr["d_w"] = sum(1 for m in pr["log"] if m[1])
        for scope, alpha in FLIGHT_ALPHA.items():
            pr[f"d:{scope}"] = _resume(pr["log"], qp, postseason, alpha)
        pr["d"] = pr["d:state"]

    # Every athlete gets ONE category, decided on standing (see `_assign_primary`),
    # and a partnership survives only if BOTH its members are doubles-primary.
    # That is what makes "nobody is honoured in both halves" true by construction
    # rather than by a filter applied afterwards.
    _assign_primary(players, pairs)
    pairs = {k: pr for k, pr in pairs.items()
             if players[k[0]]["primary"] == "d" and players[k[1]]["primary"] == "d"}
    return {"players": players, "pairs": pairs,
            "flight_of": {pid: r["s_flight"] for pid, r in players.items()}}


def _pick_team(pool, ranked_s, ranked_d, n_s, n_d, scope, breadth, used=None):
    """One team from ALREADY-RANKED lists — see `_build_team` for the common case.

    ‼️ `used` is shared ACROSS THE TIERS of one level, not reset per team. The
    ranked slices already keep a First and a Second Team disjoint by INDEX, but a
    player with two strong partnerships appears at two different indices — so
    without a carried set the same athlete lands on the First Team with one
    partner and the Second with another, which reads as a selector that could not
    make up its mind. You are honoured at your best tier, once."""
    used = set() if used is None else used
    s_picks = _take(ranked_s, n_s, f"s:{scope}", breadth, used)
    d_picks = _take(ranked_d, n_d, f"d:{scope}", breadth, used)
    return ([_row(r, "s", r[f"s:{scope}"]) for r in s_picks]
            + [_row(r, "d", r[f"d:{scope}"]) for r in d_picks])


def _build_team(pool, pids, n_s, n_d, scope, breadth):
    """One honours team of `n_s` singles + `n_d` DOUBLES PAIRS, drawn from `pids`.

    ‼️ No athlete may hold two slots on one team, in either direction: the `used`
    set carries across both halves, and the primary-discipline rule
    (`_assign_primary`) already keeps a singles player out of the doubles pool
    entirely. What `used` catches is the case that rule cannot — a player with two
    strong partnerships, whose weaker pairing must not take a place another pair
    earned."""
    rs = _rank_singles(pool["players"], pids, scope, pool["flight_of"])
    rd = _rank_pairs(pool["pairs"], pids, scope)
    used: set[str] = set()
    s_picks = _take(rs, n_s, f"s:{scope}", breadth, used)
    d_picks = _take(rd, n_d, f"d:{scope}", breadth, used)
    return ([_row(r, "s", r[f"s:{scope}"]) for r in s_picks]
            + [_row(r, "d", r[f"d:{scope}"]) for r in d_picks])


def region_awards(pool) -> dict:
    """‼️ ALL-REGION IS REGION-WIDE AND CLASS-BLIND (owner rule 2027-08).

    There is no 7A All-Region team — there is a **Gold Valley All-Region team**,
    and it is drawn from every program in Gold Valley whatever its enrollment.
    That is how it works in real life, and it is the fix for the association's
    three geographies blurring into each other: a region team selected per
    classification is a district by another name, because a class-region holds
    four or five schools.

    The size of the change is the point. Per classification it produced ten
    regions × six classes × 18 selections ≈ **1,080** region honours a gender, on
    an association of ~300 programs — every school placed somebody. Region-wide it
    is **180**, drawn from ~40 programs each, so a place on one is a genuinely
    competitive statewide-by-geography honour sitting between All-State and
    All-District rather than a second All-District.

    Regions below `MIN_REGION_PROGRAMS` crown nothing; class-blind, essentially
    none are."""
    players = pool["players"]
    by_region, programs = defaultdict(set), defaultdict(set)
    for pid, rec in players.items():
        by_region[rec["region"]].add(pid)
        programs[rec["region"]].add(rec["school"])
    teams = {}
    for rname, pids in by_region.items():
        n_prog = len(programs[rname])
        if n_prog < MIN_REGION_PROGRAMS:
            continue
        # Breadth here is school + CLASSIFICATION: when candidates are genuinely
        # tied, a selector spreads across the region's schools and its class
        # ladder alike. Still a near-tie reorder, never a quota — a region whose
        # best ten singles seasons are all 7A gets all ten.
        #
        # A big region takes a Second Team from the candidates the First did not,
        # exactly as All-State's tiers do: `_build_team` is handed the remainder
        # of the ranked lists rather than re-ranking, so the Second Team is the
        # next ten and eight and never a re-shuffle of the same names.
        n_tiers = 2 if n_prog >= AR_TIER2_MIN_PROGRAMS else 1
        rs = _rank_singles(pool["players"], pids, "region", pool["flight_of"])
        rd = _rank_pairs(pool["pairs"], pids, "region")
        tiers, used, si, di = [], set(), 0, 0
        for t in range(n_tiers):
            picks = _pick_team(pool, rs[si:], rd[di:], AR_SINGLES, AR_DOUBLES,
                               "region", ("school", "group"), used)
            si += AR_SINGLES
            di += AR_DOUBLES
            if not picks:
                break
            # One team = one honour, UNNUMBERED. Calling it "First Team" when
            # there is no second promises a tier that does not exist.
            tiers.append({"name": TEAM_NAMES[t] if n_tiers > 1 else "",
                          "players": picks})
        if not tiers:
            continue
        hm = (_honorable_mention(tiers, rs, rd, si, di, "region", AR_HM_PER_SCHOOL)
              if n_prog >= AR_HM_MIN_PROGRAMS else [])
        teams[rname] = {"tiers": tiers, "honorable_mention": hm,
                        "programs": n_prog}
    flat = [r for _rn, _t, r in region_rows(teams)]
    return {"teams": teams, "flight_check": _flight_report(flat, "region")}


def region_rows(all_region: dict):
    """Every All-Region selection as (region, tier_name, row).

    ONE place knows the archive's shape. A region's value is a LIST OF TIERS —
    one unnumbered team in a small region, First and Second in a big one — and
    half a dozen readers walk it (`honors_for`, the school ledger, the roster
    badges, the honors page, the tests). Walking it by hand in each of them is
    how one of them ends up showing a big region's First Team only."""
    for rname, reg in (all_region or {}).items():
        for t in reg["tiers"]:
            for r in t["players"]:
                yield rname, t.get("name") or "", r
        for r in reg.get("honorable_mention") or ():
            yield rname, "Honorable Mention", r


def season_awards(teams, postseason=None, pool=None) -> dict:
    """Every postseason award for ONE classification, in ONE pass.

    ⚠️ All-Region is NOT here — it is region-wide and class-blind, selected once
    per gender by `region_awards`. What is per-classification is State (the class
    is the field) and District (a district IS `(classification, name)`).

    State and district are separate QUESTIONS asked of the same evidence (see
    `FLIGHT_ALPHA` / `FLIGHT_FLOOR`), not one ranking sliced twice — and the
    geographic honours OVERLAP by design: nobody is removed from a lower team for
    having won a higher one, so a State POY is normally also All-Region and
    All-District.

    `pool` is the gender-wide rating pass (`build_pool`); passing it is how the
    opponent graph keeps its cross-classification edges. Without one this rates
    the class in isolation, which is only right when the class IS the association
    (tests, a single-group call)."""
    empty = {"poy": None, "all_state": [], "teams": [], "honorable_mention": [],
             "all_district": {}, "district_poy": {}, "flight_check": {}}
    mine = {pid for t in teams for pid in t.matches}
    if pool is None:
        pool = build_pool(teams, postseason)
    players = pool["players"]
    mine &= set(players)
    if not mine:
        return empty
    pairs = pool["pairs"]

    group = players[next(iter(mine))]["group"]
    s_rank = _rank_singles(players, mine, "state", pool["flight_of"])
    d_rank = _rank_pairs(pairs, mine, "state")

    # --- All-State: numbered teams, then the merit threshold ------------------
    # Breadth at the STATE level is school + district + region: statewide quality
    # is overwhelmingly primary, and this only unpicks a near-tie. `used` carries
    # across the tiers — see `_pick_team`.
    n_teams = AS_TIERS.get(group, AS_TIERS_DEFAULT)
    tiers, si, di = [], 0, 0
    used: set[str] = set()
    for t in range(n_teams):
        picks = _pick_team(pool, s_rank[si:], d_rank[di:], AS_SINGLES, AS_DOUBLES,
                           "state", ("school", "district", "region"), used)
        si += AS_SINGLES
        di += AS_DOUBLES
        if picks:
            tiers.append({"name": TEAM_NAMES[t], "players": picks})
    hm = _honorable_mention(tiers, s_rank, d_rank, si, di)

    # --- Player of the Year ---------------------------------------------------
    # Read from BOTH candidate pools: a doubles season can be the best in the
    # classification, and since a doubles honour is a pairing the award is then
    # shared by the two players who produced it.
    cands = ([(r["s:state"], r, "s") for r in s_rank[:AS_SINGLES]]
             + [(r["d:state"], r, "d") for r in d_rank[:AS_DOUBLES]])
    poy = None
    if cands:
        sc, rec, key = max(cands, key=lambda kv: (kv[0], kv[1]["name"]))
        poy = _row(rec, key, sc)

    # --- the districts, from the same evidence, at district scope -------------
    # A DISTRICT IS `(CLASSIFICATION, name)` — the association reuses its
    # geographic names at every level — so this genuinely belongs per class, in a
    # way All-Region does not.
    by_district = defaultdict(set)
    for pid in mine:
        by_district[players[pid]["district"]].add(pid)
    all_district, district_poy = {}, {}
    for dname, pids in by_district.items():
        all_district[dname] = _build_team(pool, pids, AD_SINGLES, AD_DOUBLES,
                                          "district", ("school",))
        ds = _rank_singles(players, pids, "district", pool["flight_of"])
        dd = _rank_pairs(pairs, pids, "district")
        dc = ([(r["d:district"], r, "d") for r in dd[:3]]
              + [(r["s:district"], r, "s") for r in ds[:3]])
        if dc:
            sc, rec, key = max(dc, key=lambda kv: (kv[0], kv[1]["name"]))
            district_poy[dname] = _row(rec, key, sc)

    flat = [p for tier in tiers for p in tier["players"]]
    check = {"state": _flight_report(flat + hm, "state")}
    if all_district:
        check["district"] = _flight_report(
            [r for rows in all_district.values() for r in rows], "district")
    return {"poy": poy, "all_state": flat, "teams": tiers,
            "honorable_mention": hm,
            "all_district": all_district, "district_poy": district_poy,
            "flight_check": check}


def honors_for(pid: str, awards: dict, group: str) -> list[str]:
    """The honours one player earned, best first — the string form a recruit
    carries onto the college board.

    ‼️ Every membership test goes through `row_pids`: a doubles row honours TWO
    athletes, so matching on `row["pid"]` would credit half of every pairing."""
    out = []
    if pid in row_pids(awards.get("poy")):
        out.append(f"{group} Player of the Year")
    for dname, r in (awards.get("district_poy") or {}).items():
        if pid in row_pids(r):
            out.append(f"{dname} Player of the Year")
            break
    for tier in awards.get("teams") or ():
        if any(pid in row_pids(r) for r in tier["players"]):
            out.append(f"All-State {tier['name']} ({group})")
            break
    else:
        if any(pid in row_pids(r) for r in awards.get("honorable_mention") or ()):
            out.append(f"All-State Honorable Mention ({group})")
    # ⚠️ All-Region is GENDER-WIDE, not part of a classification's slate, so the
    # caller has to merge it in — the same shape `all_district` already needs.
    # A big region crowns two teams, so the tier is named when there is one.
    for rname, tier, r in region_rows(awards.get("all_region")):
        if pid in row_pids(r):
            out.append(f"All-Region {tier} ({rname})".replace("  ", " "))
            break
    for dname, rs in (awards.get("all_district") or {}).items():
        if any(pid in row_pids(r) for r in rs):
            out.append(f"All-District ({dname})")
            break
    return out

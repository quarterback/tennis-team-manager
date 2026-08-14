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

An All-State team and an All-District team are the same size (owner, 2027-08):
ten singles selections and eight doubles selections apiece. Honorable Mention is
not a team at all but a THRESHOLD — see `HM_DROP`.

HOW A RÉSUMÉ IS SCORED (the SOP's criteria, in the order it lists them):

  1. RECORD — wins and losses, volume, and consistency. Credit is signed and
     accumulated per match, so a long strong season outranks a short one
     without a bare win% ever being the measure.
  2. POSITION — every match is weighted by the flight it was played at
     (`jhsaa.FLIGHT_WEIGHTS`, the association's own table: #1 singles and #1
     doubles carry the most). Beating people at the top of a card is worth more
     than beating people at the bottom, and the weight comes off the match the
     player actually played rather than an assumed lineup slot.
  3. OPPOSITION — a first pass rates every player by a shrunk win rate; the
     second pass weighs each result by who it came against. Strength of
     schedule is therefore per-opponent, not per-opposing-team.
  4. QUALITY WINS — a win's value scales with the opponent's rating, so beating
     serious candidates is the fastest way up the board.
  5. GOOD LOSSES — a loss's cost SHRINKS with the opponent's rating. Losing to
     the best player in the class is nearly free; losing to a weak one is not.
  6. HEAD-TO-HEAD — among candidates whose résumés are close (`H2H_BAND`),
     direct results reorder them. Evidence, not an override: it only moves
     players already tied on everything else.
  7. POSTSEASON — Sectionals through State count, weighted up (`PHASE_WEIGHT`).
     Jefferson has no individual tournament and none is invented; this is the
     team postseason a player actually played.
  8. TEAM — never an eligibility gate. It enters only through opposition
     quality: playing (and beating) good players is what a good team gives you.
  9. THIS SEASON ONLY — nothing here reads class year, talent, potential,
     reputation or last year's honours.

Doubles is evaluated AS DOUBLES: its own rating pass over doubles lines only,
so a pair's record against other pairs is what counts. Players who partnered
around are judged on the body of their doubles work rather than on one invented
permanent partnership (the SOP's rule); the most frequent partner rides along
for display.
"""
from __future__ import annotations

from collections import defaultdict

# --- shape of the awards -----------------------------------------------------
# An All-State team and an All-District team are the SAME SIZE (owner, 2027-08):
# ten singles selections and eight doubles selections apiece.
TEAM_SINGLES = 10
TEAM_DOUBLES = 8
AS_SINGLES, AS_DOUBLES = TEAM_SINGLES, TEAM_DOUBLES
AD_SINGLES, AD_DOUBLES = TEAM_SINGLES, TEAM_DOUBLES
AS_TIERS = {"7A": 4}           # numbered teams; everyone else gets three
AS_TIERS_DEFAULT = 3

# ‼️ HONORABLE MENTION IS A THRESHOLD, NOT A TEAM (owner, 2027-08). There is no
# slot count: after the numbered teams are filled, HM takes the players whose
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
# Measured through the shipped path at HM_DROP 0.10, against numbered teams of 72
# (7A) and 54 (everyone else) — boys 7A 30 · 6A 11 · 5A 7 · 4A 9 · 3A 18 ·
# 2A-1A 7; girls 7A 19 · 6A 9 · 5A 11 · 4A 11 · 3A 14 · 2A-1A 15. That is the
# shape the rule asks for: the size is an OUTPUT of how many genuine résumés a
# classification produced that year, it differs by class AND by gender AND by
# season, and nobody is ever honoured to fill a quota.
HM_DROP = 0.10
HM_MAX_MULT = 2.5              # runaway guard on the TOTAL, never a target
HM_PER_SCHOOL = 2              # HM only — the numbered teams have no such cap

TEAM_NAMES = ["First Team", "Second Team", "Third Team", "Fourth Team"]

# --- scoring dials -----------------------------------------------------------
PRIOR = 2.0                    # Laplace shrink on the first-pass win rate
WIN_BASE = 0.55                # a win is worth this before opponent quality…
WIN_SLOPE = 1.30               # …plus this much of the opponent's rating
LOSS_BASE = 0.85               # a loss costs this…
GOOD_LOSS = 1.15               # …reduced by this much of the opponent's rating
PHASE_WEIGHT = 1.45            # postseason matches count for more
MIN_MATCHES = 6                # below this a résumé is too thin to rank
H2H_BAND = 0.06                # résumé gap inside which head-to-head decides
H2H_SWAP_PASSES = 3


def _is_singles(slot: str) -> bool:
    return slot.startswith("S")


def _weight(slot: str, phase: str, postseason) -> float:
    from .jhsaa import FLIGHT_WEIGHTS
    w = FLIGHT_WEIGHTS.get(slot, 0.25)
    return w * (PHASE_WEIGHT if phase in postseason else 1.0)


def _collect(teams) -> dict:
    """{pid: {...}} — every player's season, split singles vs doubles."""
    out: dict[str, dict] = {}
    for t in teams:
        for pid, log in t.matches.items():
            p = t.by_pid.get(pid)
            if p is None:
                continue
            rec = out.setdefault(pid, {
                "pid": pid, "name": p.name, "grade": p.grade,
                "school": t.school.name, "district": t.school.district,
                "group": t.school.group, "log": [],
                "partners": defaultdict(int),
            })
            rec["log"].extend(log)
            for slot, _won, _ph, _opp, partner, _os in log:
                if partner:
                    rec["partners"][partner] += 1
    return out


def _split(rec: dict) -> tuple[list, list]:
    s = [m for m in rec["log"] if _is_singles(m[0])]
    d = [m for m in rec["log"] if not _is_singles(m[0])]
    return s, d


def _base_ratings(players: dict) -> tuple[dict, dict]:
    """First pass — a shrunk win rate per discipline. Deliberately crude: it
    exists only to give the second pass something to weigh opponents by."""
    bs, bd = {}, {}
    for pid, rec in players.items():
        s, d = _split(rec)
        for log, tgt in ((s, bs), (d, bd)):
            w = sum(1 for m in log if m[1])
            n = len(log)
            tgt[pid] = (w + PRIOR / 2) / (n + PRIOR) if n else 0.5
    return bs, bd


def _resume(log, base: dict, postseason) -> float:
    """Signed résumé credit — the SOP's criteria 1-5 and 7, per match."""
    total = 0.0
    for slot, won, phase, opps, _partner, _os in log:
        w = _weight(slot, phase, postseason)
        q = (sum(base.get(o, 0.5) for o in opps) / len(opps)) if opps else 0.5
        if won:
            total += w * (WIN_BASE + WIN_SLOPE * q)
        else:
            total -= w * max(0.05, LOSS_BASE - GOOD_LOSS * q)
    return total


def _h2h(a: dict, b: dict) -> int:
    """Net head-to-head between two players: +1 a leads, -1 b leads, 0 level."""
    net = 0
    for _slot, won, _ph, opps, _pt, _os in a["log"]:
        if b["pid"] in opps:
            net += 1 if won else -1
    return (net > 0) - (net < 0)


def _apply_h2h(ranked: list, key: str) -> list:
    """Reorder CLOSE candidates on direct results (SOP criterion 6). Only pairs
    already within `H2H_BAND` can move, so one match never erases a season."""
    out = list(ranked)
    for _ in range(H2H_SWAP_PASSES):
        moved = False
        for i in range(len(out) - 1):
            a, b = out[i], out[i + 1]
            if a[key] - b[key] <= H2H_BAND and _h2h(b, a) > 0:
                out[i], out[i + 1] = b, a
                moved = True
        if not moved:
            break
    return out


def _rank(players: dict, key: str, pool) -> list:
    """`pool` is a set of PIDS — the dicts are unhashable and, more to the point,
    a pid is the identity everything else in the archive keys on."""
    got = [p for pid, p in players.items()
           if pid in pool and p[key + "_n"] >= MIN_MATCHES]
    got.sort(key=lambda r: (-r[key], -r[key + "_n"], r["name"]))
    return _apply_h2h(got, key)


def _row(rec: dict, key: str) -> dict:
    """The award row that gets archived — the résumé, never the ability."""
    best = max(rec["partners"].items(), key=lambda kv: kv[1])[0] if rec["partners"] else ""
    return {"pid": rec["pid"], "name": rec["name"], "grade": rec["grade"],
            "school": rec["school"], "district": rec["district"],
            "wins": rec[key + "_w"], "losses": rec[key + "_n"] - rec[key + "_w"],
            "kind": "singles" if key == "s" else "doubles",
            "partner": best if key == "d" else "",
            "score": round(rec[key], 4)}


def _hm_cut(scores: list[float]) -> float:
    """The statewide-recognition line for one discipline, from the numbered
    teams' own spread — see `HM_DROP`. Everything below this stops being an
    award and starts being a list."""
    if not scores:
        return float("inf")
    top, last = max(scores), min(scores)
    return last - HM_DROP * max(0.0, top - last)


def _honorable_mention(tiers, s_rank, d_rank, si, di) -> list:
    """Players past the numbered teams whose résumé still clears the bar.

    Not "the next N": each discipline gets its own cutoff from the numbered
    selections it produced, candidates below it are simply not honoured, and the
    size of the group is therefore an OUTPUT — a deep classification honours
    more players than a thin one, which is the point.

    ‼️ AT MOST `HM_PER_SCHOOL` from any one school (owner, 2027-08), and the cap
    is HM-ONLY: a school may take as many First/Second/Third/Fourth Team places
    as its résumés earn. When a school has more than two qualifiers the two
    strongest are kept and the rest are simply dropped — nothing backfills the
    space, because HM has no quota to fill."""
    picked = {r["pid"] for t in tiers for r in t["players"]}
    cands: dict[str, tuple[float, dict]] = {}
    for rank, start, key in ((s_rank, si, "s"), (d_rank, di, "d")):
        cut = _hm_cut([r[key] for r in rank[:start]])
        for rec in rank[start:]:
            if rec["pid"] in picked or rec[key] < cut:
                continue
            # A player over the line in both disciplines is honoured once, on
            # whichever résumé is stronger.
            prev = cands.get(rec["pid"])
            if prev is None or rec[key] > prev[0]:
                cands[rec["pid"]] = (rec[key], _row(rec, key))
    ranked = sorted(cands.values(), key=lambda kv: -kv[0])
    per_school: dict[str, int] = defaultdict(int)
    out, limit = [], int((TEAM_SINGLES + TEAM_DOUBLES) * HM_MAX_MULT)
    for score, row in ranked:
        if per_school[row["school"]] >= HM_PER_SCHOOL or len(out) >= limit:
            continue
        per_school[row["school"]] += 1
        out.append(row)
    return out


def season_awards(teams, postseason=None) -> dict:
    """Every postseason award for ONE classification, in one pass."""
    from .jhsaa import POSTSEASON
    postseason = POSTSEASON if postseason is None else postseason
    players = _collect(teams)
    if not players:
        return {"poy": None, "all_state": [], "teams": [], "honorable_mention": [],
                "all_district": {}, "district_poy": {}}
    bs, bd = _base_ratings(players)
    for rec in players.values():
        s, d = _split(rec)
        rec["s_n"], rec["d_n"] = len(s), len(d)
        rec["s_w"] = sum(1 for m in s if m[1])
        rec["d_w"] = sum(1 for m in d if m[1])
        rec["s"] = _resume(s, bs, postseason)
        rec["d"] = _resume(d, bd, postseason)

    group = next(iter(players.values()))["group"]
    everyone = set(players)
    s_rank = _rank(players, "s", everyone)
    d_rank = _rank(players, "d", everyone)

    # --- All-State: numbered teams shaped like a lineup card, then merit HM ---
    n_teams = AS_TIERS.get(group, AS_TIERS_DEFAULT)
    tiers, si, di = [], 0, 0
    for t in range(n_teams):
        picks = ([_row(r, "s") for r in s_rank[si:si + AS_SINGLES]]
                 + [_row(r, "d") for r in d_rank[di:di + AS_DOUBLES]])
        si += AS_SINGLES
        di += AS_DOUBLES
        if picks:
            tiers.append({"name": TEAM_NAMES[t], "players": picks})
    hm = _honorable_mention(tiers, s_rank, d_rank, si, di)

    # --- Player of the Year: the best résumé in the class, either discipline --
    cands = [(r["s"], r, "s") for r in s_rank[:AS_SINGLES]] + \
            [(r["d"], r, "d") for r in d_rank[:AS_DOUBLES]]
    poy = None
    if cands:
        sc, rec, key = max(cands, key=lambda kv: kv[0])
        poy = _row(rec, key)

    # --- the districts, from the same evidence --------------------------------
    by_district = defaultdict(set)
    for pid, rec in players.items():
        by_district[rec["district"]].add(pid)
    all_district, district_poy = {}, {}
    for dname, pool in by_district.items():
        ds = _rank(players, "s", pool)
        dd = _rank(players, "d", pool)
        all_district[dname] = ([_row(r, "s") for r in ds[:AD_SINGLES]]
                               + [_row(r, "d") for r in dd[:AD_DOUBLES]])
        dc = [(r["s"], r, "s") for r in ds[:3]] + [(r["d"], r, "d") for r in dd[:3]]
        if dc:
            sc, rec, key = max(dc, key=lambda kv: kv[0])
            district_poy[dname] = _row(rec, key)

    flat = [p for tier in tiers for p in tier["players"]]
    return {"poy": poy, "all_state": flat, "teams": tiers,
            "honorable_mention": hm, "all_district": all_district,
            "district_poy": district_poy}


def honors_for(pid: str, awards: dict, group: str) -> list[str]:
    """The honours one player earned, best first — the string form a recruit
    carries onto the college board."""
    out = []
    if (awards.get("poy") or {}).get("pid") == pid:
        out.append(f"{group} Player of the Year")
    for dname, r in (awards.get("district_poy") or {}).items():
        if r and r.get("pid") == pid:
            out.append(f"{dname} Player of the Year")
            break
    for tier in awards.get("teams") or ():
        if any(r["pid"] == pid for r in tier["players"]):
            out.append(f"All-State {tier['name']} ({group})")
            break
    else:
        if any(r["pid"] == pid for r in awards.get("honorable_mention") or ()):
            out.append(f"All-State Honorable Mention ({group})")
    for dname, rs in (awards.get("all_district") or {}).items():
        if any(r["pid"] == pid for r in rs):
            out.append(f"All-District ({dname})")
            break
    return out

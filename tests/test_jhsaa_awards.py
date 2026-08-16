"""Postseason awards are RÉSUMÉ selections (owner SOP 2027-08).

The old model sorted on (wins, win%, OVR) and took six for All-State and six per
district. These pin the SOP's shape and its two load-bearing rules: Honorable
Mention is a THRESHOLD rather than a team, and the two-per-school cap applies to
HM and to nothing else.
"""
import pytest

from app import jhsaa as jh
from app import jhsaa_awards as aw


@pytest.fixture(scope="module")
def season():
    """Two districts per classification — the shipped path, a tenth the size."""
    real = jh.load_schools

    def small(gender):
        out = []
        for grp in jh.GROUPS:
            keep = sorted({s.district for s in real(gender) if s.group == grp})[:2]
            out += [s for s in real(gender) if s.group == grp and s.district in keep]
        return out

    jh.load_schools = small
    jh._season_cache.clear()
    try:
        yield jh.run_season("boys", 2027, seed=0, salt="awards")
    finally:
        jh.load_schools = real
        jh._season_cache.clear()


def test_all_state_and_all_district_teams_are_the_same_size(season):
    """Owner: an All-State team is the size of an All-District team."""
    for g in jh.GROUPS:
        a = season["awards"][g]
        for tier in a["teams"]:
            s = [r for r in tier["players"] if r["kind"] == "singles"]
            d = [r for r in tier["players"] if r["kind"] == "doubles"]
            assert (len(s), len(d)) == (aw.TEAM_SINGLES, aw.TEAM_DOUBLES), (g, tier["name"])
        for dname, rows in a["all_district"].items():
            s = [r for r in rows if r["kind"] == "singles"]
            assert len(s) <= aw.TEAM_SINGLES and len(rows) - len(s) <= aw.TEAM_DOUBLES


def test_7a_gets_a_fourth_team_and_everyone_else_three(season):
    assert [t["name"] for t in season["awards"]["7A"]["teams"]][:4] == \
        ["First Team", "Second Team", "Third Team", "Fourth Team"]
    for g in jh.GROUPS:
        if g != "7A":
            assert len(season["awards"][g]["teams"]) == aw.AS_TIERS_DEFAULT, g


def test_honorable_mention_is_a_threshold_not_a_fixed_size(season):
    """‼️ The size is an OUTPUT. If every classification honours the same number,
    a slot count has crept back in — which is exactly what a too-loose runaway
    guard did on the first attempt (a flat 27 everywhere)."""
    sizes = [len(season["awards"][g]["honorable_mention"]) for g in jh.GROUPS]
    assert len(set(sizes)) > 1, sizes
    guard = int((aw.TEAM_SINGLES + aw.TEAM_DOUBLES) * aw.HM_MAX_MULT)
    assert max(sizes) < guard, (sizes, guard)     # the THRESHOLD must be binding


def test_honorable_mention_caps_a_school_at_two(season):
    from collections import Counter
    for g in jh.GROUPS:
        c = Counter(r["school"] for r in season["awards"][g]["honorable_mention"])
        assert not c or max(c.values()) <= aw.HM_PER_SCHOOL, (g, c.most_common(3))


def test_the_school_cap_applies_to_nothing_but_honorable_mention(season):
    """A school may take as many numbered-team places as its résumés earn."""
    from collections import Counter
    stacked = 0
    for g in jh.GROUPS:
        c = Counter(r["school"] for t in season["awards"][g]["teams"]
                    for r in t["players"])
        stacked = max(stacked, max(c.values()) if c else 0)
    assert stacked > aw.HM_PER_SCHOOL, stacked


def test_awards_are_not_an_ability_leaderboard(season):
    """The whole point of the SOP: a résumé, not a rating. No award row carries an
    ability figure, and the selections are not simply the highest-OVR players."""
    a = season["awards"]["7A"]
    rows = [r for t in a["teams"] for r in t["players"]]
    assert rows and not any("ovr" in r or "str" in r for r in rows)
    teams = [t for t in season["teams"].values() if t.school.group == "7A"]
    best_ovr = sorted((p for t in teams for p in t.roster),
                      key=lambda p: -p.current_overall())[:len(rows)]
    picked = {p for r in rows for p in aw.row_pids(r)}
    assert {p.pid for p in best_ovr} != picked


def test_every_district_gets_a_player_of_the_year(season):
    for g in jh.GROUPS:
        a = season["awards"][g]
        assert set(a["district_poy"]) == set(a["all_district"]), g
        assert a["poy"] is not None


def test_award_rows_name_the_PLAYER_not_the_school(season):
    """The SELECTOR's rows name individuals.

    ⚠️ This is the weaker half of the pair. The bug it is named after was never
    here — `_jh_deco` describes a SCHOOL and its dict is keyed `name`, so it was
    `jhsaa_honors_view.deco()` splatting that over an award row that overwrote
    every selection's player name, and these records were correct the whole time.
    Reverting the production fix leaves this test green. The one that can actually
    see it builds the VIEW: `test_jhsaa_toc.py::
    test_the_honors_view_never_overwrites_a_player_with_their_school`."""
    schools = {s.name for s in jh.load_schools("boys")}
    for g in jh.GROUPS:
        a = season["awards"][g]
        rows = ([r for t in a["teams"] for r in t["players"]]
                + a["honorable_mention"]
                + [r for rs in a["all_district"].values() for r in rs]
                + [a["poy"]] + list(a["district_poy"].values()))
        for r in rows:
            assert r["name"] not in schools, (g, r["name"], r["school"])
            assert r["name"] != r["school"], (g, r["name"])


# --- All-Region, and the checks the SOP asks for across every honors surface ----

def _all_rows(a):
    """Every award row on every surface, tagged with the surface it came from."""
    out = [("poy", a["poy"])] if a["poy"] else []
    for t in a["teams"]:
        out += [(f"all-state {t['name']}", r) for r in t["players"]]
    out += [("hm", r) for r in a["honorable_mention"]]
    for dn, rs in a["all_district"].items():
        out += [(f"all-district {dn}", r) for r in rs]
    out += [(f"district poy {d}", r) for d, r in a["district_poy"].items()]
    return out


# --- All-Region is REGION-WIDE and CLASS-BLIND (owner rule 2027-08) ------------

def test_all_region_is_not_selected_per_classification(season):
    """‼️ There is no 7A All-Region team — there is a Gold Valley All-Region team.

    A region team selected per classification is a DISTRICT by another name: a
    class-region holds four or five schools. So All-Region lives on the SEASON,
    not in any classification's slate, and there is exactly one team per region
    for the whole gender."""
    assert "all_region" in season and season["all_region"]
    for g in jh.GROUPS:
        assert "all_region" not in season["awards"][g], g


def test_every_region_team_is_ten_singles_and_eight_doubles(season):
    """Region-wide the pool is ~40 programs, so unlike the old per-class teams
    these fill: ten singles and eight DISJOINT partnerships in EVERY tier."""
    assert len(season["all_region"]) >= 2
    for rn, reg in season["all_region"].items():
        for t in reg["tiers"]:
            s = [r for r in t["players"] if r["kind"] == "singles"]
            d = [r for r in t["players"] if r["kind"] == "doubles"]
            assert (len(s), len(d)) == (aw.AR_SINGLES, aw.AR_DOUBLES), (rn, t["name"])


def test_a_big_region_crowns_two_teams_and_a_small_one_crowns_one(season):
    """‼️ The association's regions are nowhere near the same size — Halbrook
    Basin has 199 boys' programs, Millersylvania 25 — so a single team of ten is a
    far scarcer honour in one than in the other. Regions at or above
    `AR_TIER2_MIN_PROGRAMS` crown a First AND a Second Team.

    The threshold is on the PROGRAM COUNT, never a list of region names: the
    reason for the rule is the size, and the association's shape changes when
    schools are added."""
    progs = {}
    for t in season["teams"].values():
        progs.setdefault(t.school.area, set()).add(t.school.name)
    big = small = 0
    for rn, reg in season["all_region"].items():
        tiers, n = reg["tiers"], len(progs[rn])
        if n >= aw.AR_TIER2_MIN_PROGRAMS:
            assert [t["name"] for t in tiers] == ["First Team", "Second Team"], (rn, n)
            big += 1
        else:
            # One team is UNNUMBERED — calling it "First Team" with no second
            # promises a tier that does not exist.
            assert len(tiers) == 1 and tiers[0]["name"] == "", (rn, n)
            small += 1
    assert big and small, (big, small)


def test_a_second_team_is_the_next_ten_not_a_reshuffle(season):
    """The Second Team takes the candidates the First did not — the ranked lists
    are sliced, never re-ranked — so no athlete appears on both."""
    checked = 0
    for rn, reg in season["all_region"].items():
        if len(reg["tiers"]) < 2:
            continue
        checked += 1
        first = {p for r in reg["tiers"][0]["players"] for p in aw.row_pids(r)}
        second = {p for r in reg["tiers"][1]["players"] for p in aw.row_pids(r)}
        assert not (first & second), (rn, first & second)
    assert checked, "no region crowned a second team"


def test_a_region_team_draws_from_more_than_one_classification(season):
    """The whole point: enrollment does not enter into it, so a region team mixes
    classifications where its region holds more than one.

    ⚠️ The per-region league count is NOT asserted: this fixture keeps two
    districts per classification, so a region can legitimately end up holding
    programs from a single league — an artefact of the cut, not of the rule. What
    holds at any size is that a region team spans several SCHOOLS and that the
    association's teams are not all single-class."""
    home = {}
    for t in season["teams"].values():
        for pid in t.records:
            home[pid] = (t.school.area, t.school.group, t.school.district)
    mixed = 0
    for rn, reg in season["all_region"].items():
        rows = [r for _a, _b, r in aw.region_rows({rn: reg})]
        groups, leagues = set(), set()
        for r in rows:
            for pid in aw.row_pids(r):
                assert home[pid][0] == rn, (rn, r["name"])
                groups.add(home[pid][1])
                # ‼️ A LEAGUE IS `(CLASSIFICATION, name)` — the association reuses
                # its district names at every level, so comparing names alone
                # makes six different leagues look like one.
                leagues.add((home[pid][1], home[pid][2]))
        assert len({r["school"] for r in rows}) > 2, (rn, "a team, not a roster")
        mixed += len(groups) > 1
    assert mixed, "no region team drew from more than one classification"


def test_all_region_is_the_same_slate_whatever_class_you_came_from(season):
    """It is one gender-wide selection, so a player's All-Region honour cannot
    depend on which classification page it is read from."""
    seen = {p for _rn, _t, r in aw.region_rows(season["all_region"])
            for p in aw.row_pids(r)}
    for g in jh.GROUPS:
        aws = {**season["awards"][g], "all_region": season["all_region"]}
        for pid in list(seen)[:25]:
            assert any("All-Region" in h for h in aw.honors_for(pid, aws, g))


def test_all_region_is_far_smaller_than_it_was_per_class(season):
    """Selected per classification it produced ten regions × six classes × 18
    selections — on an association of ~300 programs, every school placed
    somebody, which is what made it a second All-District. Region-wide it is one
    team per region, so the honour is scarce enough to mean something."""
    n = sum(1 for _ in aw.region_rows(season["all_region"]))
    assert n <= 2 * len(season["all_region"]) * (aw.AR_SINGLES + aw.AR_DOUBLES)
    schools = {s.name for s in jh.load_schools("boys")}
    placed = {r["school"] for _rn, _t, r in aw.region_rows(season["all_region"])}
    assert len(placed) < 0.75 * len(schools), (len(placed), len(schools))


def test_honors_identity_resolves_to_a_real_player(season):
    """Every selection on every surface names a real person, with the school
    resolved separately — the decorator collision must not come back anywhere."""
    schools = {s.name for s in jh.load_schools("boys")}
    by_pid = {}
    for t in season["teams"].values():
        by_pid.update(t.by_pid)
    for g in jh.GROUPS:
        for where, r in _all_rows(season["awards"][g]):
            pids, names = aw.row_pids(r), r["names"]
            assert r["kind"] in ("singles", "doubles")
            assert len(pids) == len(names) == (1 if r["kind"] == "singles" else 2), \
                (g, where, r["kind"], names)
            for pid, nm in zip(pids, names):
                assert pid in by_pid, (g, where, pid)
                assert nm == by_pid[pid].name, (g, where, nm)
                assert nm not in schools, (g, where, nm)
            assert r["name"] == " / ".join(names), (g, where)
            assert r["school"] in schools and r["name"] != r["school"], (g, where)


def test_geographic_scope_comes_from_school_data(season):
    """A region/district team may only select players who belong to it, and
    membership is read off the school record, never off a display string."""
    home = {}
    for t in season["teams"].values():
        for pid in t.records:
            home[pid] = (t.school.area, t.school.district, t.school.group)
    for g in jh.GROUPS:
        a = season["awards"][g]
        for dn, rows in a["all_district"].items():
            for r in rows:
                assert all(home[p][1] == dn for p in aw.row_pids(r)), (g, dn, r["name"])
        for where, r in _all_rows(a):
            assert all(home[p][2] == g for p in aw.row_pids(r)), (g, where, r["name"])


def test_no_athlete_holds_two_slots_on_one_honors_team(season):
    """‼️ Overlap ACROSS teams is intentional — State/Region/District all honour the
    same best seasons. What must never happen is one athlete twice on ONE team, in
    either direction: not two singles slots, not two of the eight pairings, and not
    a singles slot plus a doubles slot (owner correction, 2027-08 — which reversed
    the earlier "if it happens it's okay")."""
    for g in jh.GROUPS:
        a = season["awards"][g]
        rosters = ([(t["name"], t["players"]) for t in a["teams"]]
                   + [("hm", a["honorable_mention"])]
                   + list(a["all_district"].items()))
        for name, rows in rosters:
            pids = [p for r in rows for p in aw.row_pids(r)]
            assert len(pids) == len(set(pids)), (g, name)
    for rn, reg in season["all_region"].items():
        for t in reg["tiers"] + [{"name": "HM", "players": reg["honorable_mention"]}]:
            pids = [p for r in t["players"] for p in aw.row_pids(r)]
            assert len(pids) == len(set(pids)), (rn, t["name"])


# --- doubles honours are PAIRINGS (owner correction, 2027-08) -----------------

def test_a_doubles_honor_is_a_pairing_of_two_athletes(season):
    """‼️ "Eight doubles" means eight doubles TEAMS — sixteen athletes — not eight
    individual players ranked by their doubles records. Every doubles row names two
    players; every singles row names one."""
    seen = 0
    for g in jh.GROUPS:
        for where, r in _all_rows(season["awards"][g]):
            n = len(aw.row_pids(r))
            assert n == (2 if r["kind"] == "doubles" else 1), (g, where, r["kind"], n)
            seen += r["kind"] == "doubles"
    assert seen > 0, "no doubles selection anywhere"


def test_a_pairing_is_two_players_who_actually_played_together(season):
    """The partnership's résumé comes from the matches those two played SIDE BY
    SIDE, so the two must be team-mates who really partnered — and the record on
    the row must be the partnership's, not either player's doubles season."""
    logs = {}
    for t in season["teams"].values():
        for pid, log in t.matches.items():
            logs[pid] = log
    for g in jh.GROUPS:
        for where, r in _all_rows(season["awards"][g]):
            if r["kind"] != "doubles":
                continue
            a, b = aw.row_pids(r)
            together = [m for m in logs[a] if not m[0].startswith("S") and m[4] == b]
            assert len(together) >= aw.MIN_PAIR_MATCHES, (g, where, len(together))
            w = sum(1 for m in together if m[1])
            assert (r["wins"], r["losses"]) == (w, len(together) - w), (g, where)


def test_an_athlete_takes_one_pairing_per_level(season):
    """Partners rotate in this format, so a player is a separate CANDIDATE with
    each of them — but within one level they are honoured ONCE, for their best
    partnership.

    ‼️ This is the fix for a real bug. `used` was reset per tier, so a player with
    two strong partnerships landed on the First Team with one partner and the
    Second with another — the same athlete honoured twice at the same level,
    which reads as a selector that could not make up its mind. Owner: "that
    should not happen." Different LEVELS (State / Region / District) are separate
    selections and may legitimately land on different partnerships."""
    for g in jh.GROUPS:
        a = season["awards"][g]
        for name, rows in ([(t["name"], t["players"]) for t in a["teams"]]
                           + [("all-state", [r for t in a["teams"] for r in t["players"]])]
                           + [("hm", a["honorable_mention"])]):
            seen = {}
            for r in rows:
                if r["kind"] != "doubles":
                    continue
                for p in aw.row_pids(r):
                    assert seen.setdefault(p, tuple(r["pids"])) == tuple(r["pids"]), \
                        (g, name, p)
    for rn, reg in season["all_region"].items():
        seen = {}
        for _a, _b, r in aw.region_rows({rn: reg}):
            if r["kind"] != "doubles":
                continue
            for p in aw.row_pids(r):
                assert seen.setdefault(p, tuple(r["pids"])) == tuple(r["pids"]), (rn, p)


def test_an_athlete_is_honoured_in_one_category_only(season):
    """‼️ Owner: "kids can't play singles and doubles in the same match so just
    take their better thing and give them that." Each athlete has ONE category
    across the whole slate — the discipline they stood higher in — so nobody is
    ever a singles selection on one surface and a doubles selection on another."""
    cat = {}
    for g in jh.GROUPS:
        for where, r in _all_rows(season["awards"][g]):
            for pid in aw.row_pids(r):
                assert cat.setdefault(pid, r["kind"]) == r["kind"], (pid, where)
    for _rn, _t, r in aw.region_rows(season["all_region"]):
        for pid in aw.row_pids(r):
            assert cat.setdefault(pid, r["kind"]) == r["kind"], (pid, "region")
    assert cat


def _superseded_participation_rule(season):
    """Superseded by the rule above — kept only to show what changed."""
    split = {}
    for t in season["teams"].values():
        for pid, log in t.matches.items():
            s = sum(1 for m in log if m[0].startswith("S"))
            split[pid] = (s, len(log) - s)
    for g in jh.GROUPS:
        for where, r in _all_rows(season["awards"][g]):
            for p in aw.row_pids(r):
                s, d = split[p]
                if r["kind"] == "singles":
                    assert s >= d, (g, where, p, s, d)
                else:
                    assert d > s, (g, where, p, s, d)


def test_the_honorable_mention_cap_counts_entries_not_athletes(season):
    """A pairing is ONE selection against the two-per-school cap even though it
    honours two players — the cap is on entries."""
    from collections import Counter
    for g in jh.GROUPS:
        hm = season["awards"][g]["honorable_mention"]
        c = Counter(r["school"] for r in hm)
        assert not c or max(c.values()) <= aw.HM_PER_SCHOOL, (g, c.most_common(3))
        # …and it really is entries: a school at the cap may still have three or
        # four ATHLETES honoured, if one of its two selections is a pairing.
        athletes = Counter(r["school"] for r in hm for _ in aw.row_pids(r))
        assert not athletes or max(athletes.values()) <= 2 * aw.HM_PER_SCHOOL


# --- flight weighting is STRUCTURAL (owner correction, 2027-08) ---------------

def test_all_state_singles_is_a_number_one_and_number_two_honor(season):
    """‼️ Position is part of the RÉSUMÉ, not a tiebreak: 19-7 at #1 is a bigger
    season than 25-1 at #5. All-State singles must be dominated by #1 and #2, with
    anything lower a rare exception rather than a slice of the team."""
    for g in jh.GROUPS:
        rows = [r for t in season["awards"][g]["teams"] for r in t["players"]
                if r["kind"] == "singles"]
        top = [r for r in rows if aw._row_flight(r) <= aw.FLIGHT_FLOOR["state"]]
        assert len(top) >= 0.9 * len(rows), \
            (g, len(top), len(rows), sorted({r["flight"] for r in rows}))


def test_a_lower_flight_all_state_pick_beat_somebody_higher_up_the_card(season):
    """The only way below the band is extraordinary evidence, and the check is made
    against the match log: a near-perfect record AND a win over an opponent who
    played at or above the floor. A fat record against the bottom of the class is
    not enough."""
    logs, flight = {}, {}
    for t in season["teams"].values():
        for pid, log in t.matches.items():
            logs[pid] = log
            flight[pid] = _mode_flight([m for m in log if m[0].startswith("S")])
    checked = 0
    for g in jh.GROUPS:
        for t in season["awards"][g]["teams"]:
            for r in t["players"]:
                if r["kind"] != "singles" or aw._row_flight(r) <= aw.FLIGHT_FLOOR["state"]:
                    continue
                checked += 1
                pid = r["pid"]
                s = [m for m in logs[pid] if m[0].startswith("S")]
                wins = sum(1 for m in s if m[1])
                assert wins / len(s) >= aw.EXTRAORDINARY_PCT, (g, r["name"])
                assert any(m[1] and any(flight.get(o, 99) <= aw.FLIGHT_FLOOR["state"]
                                        for o in m[3]) for m in s), (g, r["name"])
    assert checked, "no below-band All-State selection to verify"


def _mode_flight(singles_log):
    from collections import Counter
    if not singles_log:
        return 99
    c = Counter(m[0] for m in singles_log)
    slot = max(c.items(), key=lambda kv: (kv[1], -int(kv[0][1:])))[0]
    return int(slot[1:])


def test_the_levels_reach_progressively_further_down_the_card(season):
    """State is a #1/#2 honour, Region reaches #3, District broadens further —
    three different questions, not one list read at three depths."""
    assert aw.FLIGHT_FLOOR["state"] < aw.FLIGHT_FLOOR["region"]
    assert aw.FLIGHT_FLOOR["district"] == 0          # no floor at all
    assert aw.FLIGHT_ALPHA["state"] > aw.FLIGHT_ALPHA["region"] > aw.FLIGHT_ALPHA["district"]
    for g in jh.GROUPS:
        a = season["awards"][g]

        def deepest(rows):
            f = [aw._row_flight(r) for r in rows if r["kind"] == "singles"]
            return max(f) if f else 0
        state = deepest([r for t in a["teams"] for r in t["players"]])
        dist = max((deepest(rows) for rows in a["all_district"].values()), default=0)
        assert dist >= 2, (g, dist)      # a district reaches past its #1s
        assert state >= 1


def test_the_flight_check_is_archived_with_the_season(season):
    """‼️ THE MANDATORY SANITY CHECK. It is not enough for the selector to apply
    the rule — the rule has to be auditable years later, so what each level
    produced by flight is archived with the awards, exceptions named."""
    for g in jh.GROUPS:
        fc = season["awards"][g]["flight_check"]
        assert "state" in fc, g
        for lvl, rep in fc.items():
            assert rep["floor"] == aw.FLIGHT_FLOOR[lvl], (g, lvl)
            assert sum(rep["flights"].values()) == rep["total"], (g, lvl)
            assert len(rep["exceptions"]) == rep["below_floor"], (g, lvl)
            for e in rep["exceptions"]:
                assert e["name"] and e["school"] and e["record"], (g, lvl)
    # The REGION check hangs off the season, like the teams it describes.
    rep = season["all_region_flight_check"]
    assert rep["floor"] == aw.FLIGHT_FLOOR["region"]
    assert sum(rep["flights"].values()) == rep["total"] > 0
    assert len(rep["exceptions"]) == rep["below_floor"]


def test_a_player_may_hold_several_geographic_honors(season):
    """The ladder overlaps by design — nobody is removed from a lower team for
    winning a higher one. The State POY should normally be on all of them."""
    hits = 0
    for g in jh.GROUPS:
        a = season["awards"][g]
        who = set(aw.row_pids(a["poy"]))
        on_state = any(who & set(aw.row_pids(r))
                       for t in a["teams"] for r in t["players"])
        on_dist = any(who & set(aw.row_pids(r))
                      for rs in a["all_district"].values() for r in rs)
        hits += bool(on_state and on_dist)
    assert hits >= len(jh.GROUPS) - 1, hits


def test_region_teams_are_recomputed_not_the_all_state_leftovers(season):
    """All-Region is its own comparison inside the region, so All-State players
    from that region belong on it — it is not a consolation list."""
    shared = 0
    for g in jh.GROUPS:
        a = season["awards"][g]
        state = {p for t in a["teams"] for r in t["players"] for p in aw.row_pids(r)}
        for rn, reg in season["all_region"].items():
            if state & {p for _a, _b, r in aw.region_rows({rn: reg})
                        for p in aw.row_pids(r)}:
                shared += 1
    assert shared > 0, "no All-State player appears on any All-Region team"


def test_selections_carry_the_flight_they_were_earned_at(season):
    for g in jh.GROUPS:
        for where, r in _all_rows(season["awards"][g]):
            assert r["flight"].startswith("#"), (g, where, r["flight"])
            assert r["flight"].endswith("Singles" if r["kind"] == "singles" else "Doubles")


def test_the_three_levels_are_not_one_ranking_at_three_depths(season):
    """State weights the top of the card hardest and district the least, so the
    lists must genuinely differ — a district team that is just the state list
    filtered would mean FLIGHT_ALPHA stopped doing anything."""
    assert aw.FLIGHT_ALPHA["state"] > aw.FLIGHT_ALPHA["region"] > aw.FLIGHT_ALPHA["district"]
    differing = 0
    for g in jh.GROUPS:
        a = season["awards"][g]
        state_order = [r["pid"] for t in a["teams"] for r in t["players"]
                       if r["kind"] == "singles"]
        for dn, rows in a["all_district"].items():
            dist = [r["pid"] for r in rows if r["kind"] == "singles"]
            in_state = [p for p in dist if p in state_order]
            if [p for p in dist if p in in_state] != \
                    [p for p in state_order if p in dist]:
                differing += 1
    assert differing > 0, "district order never diverges from state order"

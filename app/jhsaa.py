"""
JHSAA — Jefferson's high-school tennis association.

The one place a high-school season is played. Jefferson's 862 girls' and 777 boys'
programs (nine classifications, 1A-9A) play a district schedule and a state
dual-team tournament here, in this engine,
with players generated and developed here. `prep-network` supplied the institutions only
(see `scripts/import_jhsaa.py`); nothing about a player comes from that repo.

The point is that Jefferson's entries on the college recruit board are not invented — they
are the kids who just finished four years in this association, carrying their real records.
`graduating_class()` is that hand-off.

FORMATS (owner rule 2027-08) — read them through `dual_format()`, never by literal:
  * early non-district  5 singles / 2 doubles → 7 points
  * regular season      3 singles / 4 doubles → 7 points
  * state tournament    1 singles / 4 doubles → 5 points
‼️ 1A PILOT (owner rule 2026-08, `docs/AAR-jhsaa-1a-2s3d-postseason-pilot.md`): 1A
ALONE plays 2 singles / 3 doubles → 5 points for its ROAD-TO-STATE-THROUGH-STATE
postseason (`dual_format(phase, group)` — every other class, and 1A's own TOC entry,
keep 1S/4D). Nothing else about 1A changes: its regular season stays the universal
3S/4D league card and its mid-season Match Showcases stay 1S/4D — the owner's call,
since the regular season's 3-singles structure already exercises multi-singles-court
management, so a showcase specifically rehearsing a 2S/3D shape adds nothing a coach
hasn't already run all year. See the AAR for the calibration data behind the call.
All totals are ODD, so a dual cannot be tied and no tie-breaking exists anywhere.
Every match plays to completion — there is no clinch in high school
(`simulate_dual(play_all=True)`, as D3/D4 already do).

SCORING is a separate axis from shape and is the SAME for every line, singles and
doubles: a full best-of-3, no-ad, tiebreak sets, a real third set (`MATCH_FORMAT`).
High-school doubles is NOT the college 8-game pro set — that is `engine.dual`'s
default, so both formats are passed explicitly.

TALENT is far below the college floor and much wider (`_TALENT`). A 7A number one may be
a future D1 signee; a 1A number one would lose to a college walk-on. That spread inside a
single dual is the character of the level, not a calibration bug.

See docs/DESIGN-jhsaa-high-school-season.md.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import logging
import os
import random
import uuid
import re
from collections import defaultdict
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

from engine.dual import DualFormat, Team, simulate_dual
from engine.format import PRESETS
from .development import Prospect, generate_prospect, make_pid, overall_to_str

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "jhsaa", "schools.json")

GROUPS = ("9A", "8A", "7A", "6A", "5A", "4A", "3A", "2A", "1A", "Division 1", "Division 2")

# ‼️ GROUPS IS NO LONGER ONE ORDERED LADDER (2046 expansion). The first nine entries
# are the enrollment LADDER, biggest to smallest; the two "Division" groups are the
# Great Basin's own big/small PAIR ("think of them more as 10A and 11A than thinking
# of them as anything weird" — two more classifications, but NOT rungs above or below
# 1A). Anything that walks GROUPS as a single size ordering — play-up, "classes
# apart" pairing gates, "every class above mine" menus — must use LADDER_GROUPS and
# treat DIVISION_GROUPS separately; plain enumeration (archiving, scope bars,
# renumbering passes) may keep iterating GROUPS.
LADDER_GROUPS = GROUPS[:9]                       # 9A … 1A, a real size ordering
DIVISION_GROUPS = GROUPS[9:]                     # ("Division 1", "Division 2")
assert LADDER_GROUPS[-1] == "1A" and DIVISION_GROUPS == ("Division 1", "Division 2")


def champ_group(classification: str) -> str:
    """The championship group a raw classification plays in.

    2A and 1A used to share one combined "2A-1A" group (too few sponsors each
    to run the standard 40-team format on their own); they now crown SEPARATELY,
    2A on the standard ladder and 1A on the fixed 24-team shape
    (`_recovery_24`), so every classification maps
    to its own group and this is an identity fold. The same fold as
    `scripts/import_jhsaa.champ_group`; kept here because a School's `group`
    and its `classification` are no longer always equal (a play-up moves the
    first and not the second), so the app has to be able to derive one from
    the other."""
    return classification if classification in GROUPS else classification
GENDERS = ("girls", "boys")

# --- formats ----------------------------------------------------------------
FORMATS = {
    "early":    DualFormat(n_singles=5, n_doubles=2, doubles_team_point=False),
    "regular":  DualFormat(n_singles=3, n_doubles=4, doubles_team_point=False),
    "state":    DualFormat(n_singles=1, n_doubles=4, doubles_team_point=False),
    # 1A's pilot postseason shape (owner rule 2026-08) — see `dual_format()`.
    "state_1a": DualFormat(n_singles=2, n_doubles=3, doubles_team_point=False),
}
PILOT_GROUPS = ("1A",)          # groups whose road-to-State plays `state_1a`

# THE LEAGUE CARD PLAYS 3S/4D (owner rule 2027-08, swapped from the original 5S/2D so
# it matches the 1S/4D postseason's doubles-forward character all season, not just in
# the early window). A JHSAA roster carries 12+ players, and 3S/4D dresses eleven of
# them every league dual — S1 plus an 8-player doubles pool split into four pairs (see
# `_arrange_regular`) plus two more starters at S2/S3 — so a program gets real minutes
# and doubles reps for nearly its whole roster all season, not just #1-#9. Every court
# is a real result on the existing `FLIGHT_WEIGHTS` table.
#
# The FIRST non-district window (`phase="early"`, played in `play_regular_season`
# before any district round) plays the OTHER shape instead — 5 singles / 2 doubles,
# the format the league card used to use — before the season settles into its regular
# 3S/4D card. Once district play starts, the card goes to 3S/4D for good: the
# mid-season non-district window and the late tune-up are both scheduled AFTER district
# pass 1 has begun, so they stay `phase="regular"` like every league dual. The
# mid-season MATCH SHOWCASES (`SHOWCASE`, 1S/4D) are a different, separately-scheduled
# event and are untouched by any of this — an early-window program still gets its
# normal showcase invites at their own shape. Postseason stays 1S/4D as always.
EARLY_FORMAT_PHASE = "early"


# The POSTSEASON phases — one per stage, because the archive (`world_jhsaa_dual.phase`)
# is the only place the stages can be told apart afterwards. All of them share the
# 1S/4D shape, the strict best-nine lineup, and exclusion from the cutoff TOSS.
# "super_regional" and "semi_state" are the RECOVERY rounds (owner rule 2027-08):
# the second-chance ladder that earns the non-automatic State berths on court.
POSTSEASON = ("sectional", "ward", "regional", "zonal",
              "super_regional", "semi_state", "divisional", "semi_conference",
              "conference", "state", "toc")

# The mid-season MATCH SHOWCASES (owner spec 2027-08) — see the INVITATIONALS section
# below for the scheduling rules. Two phases rather than one, because the phase is the
# archive's identity for an event and the two showcases are two events: they are scored
# differently (an 8-game pro set against a full best-of-3) and sit on the calendar
# differently (one Saturday against a Friday-Saturday block). Written as one phase, a
# card could not tell them apart and the display calendar could not place either.
SHOWCASE = ("showcase_pod", "showcase_tiered")


def dual_format(phase: str, group: str | None = None) -> DualFormat:
    """The dual shape for `phase` ("early" | "regular" | a showcase | one of
    `POSTSEASON`). District duals play the regular-season shape (they are always
    `phase="regular"`); the postseason switches — and so do the showcases, which exist
    precisely to play the 1S/4D card in the middle of a 3S/4D league season. The early
    non-district window switches the other way, to 5S/2D.

    ‼️ THE 1A PILOT IS SCOPED TO THE ROAD-TO-STATE, NOT `POSTSEASON` WHOLESALE
    (owner rule 2026-08). `POSTSEASON` includes `"toc"` — the Tournament of
    Champions fields every classification's champion at the SAME shape, so 1A's
    entrant plays it at 1S/4D like everyone else; only its OWN road (Sectionals
    through State) plays `state_1a`. Showcases are untouched for every group,
    1A included — pass `group` only for a `POSTSEASON` phase; it does nothing
    for `SHOWCASE` or any other phase."""
    if (group in PILOT_GROUPS and phase in POSTSEASON and phase != "toc"):
        return FORMATS["state_1a"]
    if phase in POSTSEASON or phase in SHOWCASE:
        return FORMATS["state"]
    if phase == EARLY_FORMAT_PHASE:
        return FORMATS["early"]
    return FORMATS["regular"]


# SCORING (owner rule 2027-08), a different axis from the SHAPE above: every high-school
# match — singles AND doubles — is a full best-of-3, no-ad, tiebreak sets, real third set.
# College doubles is an 8-game pro set and `engine.dual` defaults to it, so both formats
# are passed explicitly at every call; without them a JHSAA doubles line scores "5-8".
MATCH_FORMAT = PRESETS["high_school"]

# The ONE exception, and it is a scoring axis rather than a shape: a 1-Day Pod showcase
# plays a single 8-game pro set per court, 7-point tiebreak at 8-8. NO-AD, like every
# other ball struck in this association — `pro_set_8` already carries that, so the pod
# needs no preset of its own. The 2-Day Tiered showcase plays the ordinary high-school
# best-of-3, deliberately: it exists to replicate State-tournament length and endurance,
# so scoring it any other way would defeat the point of holding it.
#
# ‼️ THREE INDEPENDENT SWITCHES, AND "TIEBREAK" IS TWO DIFFERENT THINGS. Tangle any two
# and the format is silently wrong — every combination still produces plausible scores.
#   * NO-AD is about DEUCE: next point wins the game. It says nothing about sets or
#     match length, and it is true of ALL JHSAA play (owner rule).
#   * A SET tiebreak (`set_tiebreak*`) is played inside a level set — at 6-6 in a
#     standard set, 8-8 in an 8-game pro set — first to 7 by 2. The pod's is this.
#   * A MATCH tiebreak (`final_set_tiebreak*`) is played IN LIEU OF A THIRD SET at one
#     set all, first to 10 by 2. It is what makes a match not a full best-of-3, and no
#     JHSAA format has one: the two-day block plays its third set for real, which is
#     precisely what "replicates State length" means.
#   * An ADVANTAGE set has no set tiebreak at all (win by two games, however long).
#     Independent of the other two; nothing here uses it.
# See `docs/AAR-jhsaa-mid-season-showcases.md`.
SHOWCASE_FORMAT = {"showcase_pod": PRESETS["pro_set_8"],
                   "showcase_tiered": MATCH_FORMAT}


def match_format(phase: str):
    """The SCORING rules for `phase`. Everything is the high-school best-of-3 except
    the pod showcase's pro set. Keyed, never inferred from the dual shape — the two
    showcases share a shape and differ only here."""
    return SHOWCASE_FORMAT.get(phase, MATCH_FORMAT)


def lineup_need(phase: str, group: str | None = None) -> int:
    """Players a program must dress for `phase` with nobody doubling up."""
    f = dual_format(phase, group)
    return f.n_singles + 2 * f.n_doubles          # 3+8=11 regular, 1+8=9 state, 2+6=8 1A


# --- THE JV SEASON (owner rule 2026-08) --------------------------------------
#
# ‼️ ONE ROSTER, ONE LADDER, BEST ELEVEN PLAY. There is no varsity squad and no JV
# squad — `_order` ranks the whole roster, the top eleven dress varsity, and everyone
# below them is JV. A JV player who gets good enough walks into the varsity lineup,
# which is what happens in life, and with no injuries or fatigue in this association it
# is where the season's variability comes from. Nothing new was needed to make that
# porous: `_order` / `_rest_count` / `_ROTATE_*` already move the line.
#
# ‼️ THE POROUSNESS IS NOT TEMPORAL — see `jv_pool`. The varsity season is played to
# completion before the JV season starts, so the JV pool is fixed for the whole JV
# season rather than re-cut per date. Measured at 4.1% of the pool; do not describe it
# as "everyone below them is JV THAT DAY", which is what this comment used to say.
#
# ‼️ THE JV LINEUP IS ELASTIC — fit to what the program has, never dogmatic. A fixed JV
# format has to be fielded by BOTH schools, so its reach is the PRODUCT of two roster
# constraints and it collapses: measured against the real 2038 save, a 3S/4D JV could be
# fielded on 7-9% of league dates and a 2S/3D one on 32-36%. The elastic table has no
# product — the format simply drops to whatever the thinner side can dress — so a dual
# happens whenever both sides have five spare, which under `ROSTER_FLOOR` 16 is always.
#
# The table is the owner's. Note that three entries have an EVEN court count and can
# therefore be drawn; that is accepted and handled (`_tie_break`), and it is not a
# corner case — 2S/2D alone is ~20% of the JV slate.
#: The owner's authored table, 5 through 12 — and the FLOOR of a rule that continues
#: past it. Kept as literals because these eight are the ones that were decided; the
#: rule below is checked against them at import, so a future edit here cannot silently
#: diverge from what the generator produces.
JV_FORMATS = {
    5:  DualFormat(n_singles=1, n_doubles=2, doubles_team_point=False),   # 3 courts
    6:  DualFormat(n_singles=2, n_doubles=2, doubles_team_point=False),   # 4 — even
    7:  DualFormat(n_singles=3, n_doubles=2, doubles_team_point=False),   # 5
    8:  DualFormat(n_singles=2, n_doubles=3, doubles_team_point=False),   # 5
    9:  DualFormat(n_singles=3, n_doubles=3, doubles_team_point=False),   # 6 — even
    10: DualFormat(n_singles=4, n_doubles=3, doubles_team_point=False),   # 7
    11: DualFormat(n_singles=3, n_doubles=4, doubles_team_point=False),   # 7
    12: DualFormat(n_singles=4, n_doubles=4, doubles_team_point=False),   # 8 — even
}
JV_MIN_SPARE = min(JV_FORMATS)          # 5 — below this a program cannot field a JV

#: ‼️ AND THERE IS NO CEILING (owner rule 2026-08): "if two teams have bigger than 4/4
#: can we add those formats to go bigger? 5/5, 4/5, 5/6, whatever to fit their jv roster
#: avail". The table above is not eight arbitrary shapes — it is one rule, and the rule
#: keeps going:
#:
#:     D = (spare + 1) // 3        S = spare - 2D
#:
#: which reproduces all eight authored entries exactly and then continues
#: 13 → 5S/4D · 14 → 4S/5D · 15 → 5S/5D · 16 → 6S/5D · 17 → 5S/6D · 18 → 6S/6D …
#: i.e. the owner's three examples in order. Read another way, doubles steps up and
#: singles runs D-1, D, D+1 beneath it, which is what keeps the card doubles-forward
#: at every size — the same character as the varsity 3S/4D league format.
#:
#: A twelve-player clamp was here first and is gone. It is not needed as a safety
#: rail either: the shape is always the SMALLER side's capacity, so a huge card needs
#: BOTH programs to be that deep, and the association's own roster distribution is
#: what bounds it in practice rather than a constant nobody chose.


def jv_format(spare: int) -> DualFormat | None:
    """The JV dual shape for a side with `spare` players available below varsity's
    eleven, or None if it cannot field one at all. Unbounded above."""
    if spare < JV_MIN_SPARE:
        return None
    got = JV_FORMATS.get(spare)
    if got is not None:
        return got
    d = (spare + 1) // 3
    return DualFormat(n_singles=spare - 2 * d, n_doubles=d, doubles_team_point=False)


# The authored table and the rule are ONE decision; if they ever disagree the table is
# a set of magic numbers and the rule is a guess about them.
for _n, _f in JV_FORMATS.items():
    _d = (_n + 1) // 3
    assert (_f.n_singles, _f.n_doubles) == (_n - 2 * _d, _d), f"JV_FORMATS[{_n}]"
del _n, _f, _d


def jv_lineup_need(fmt: DualFormat) -> int:
    return fmt.n_singles + 2 * fmt.n_doubles


def jv_dual_format(a_spare: int, b_spare: int) -> DualFormat | None:
    """The shape TWO sides play: the SMALLER side's capacity. Both dress the same
    number of courts, so a deep program is throttled by a thin opponent — the accepted
    price of the elastic table, and now also the thing that keeps the card's size
    honest at the top end, since a 9S/8D needs both sides carrying 25 spare."""
    if min(a_spare, b_spare) < JV_MIN_SPARE:
        return None
    return jv_format(min(a_spare, b_spare))


#: A JV program plays at most this many duals. ‼️ A LIMIT, NOT A FLOOR (owner rule
#: 2026-08): the district single round robin gets most programs to 9-11 and the
#: invitational window fills toward the cap, but a program in a small league simply
#: plays fewer. The showcase weekend is NOT counted here.
JV_DUAL_CAP = 16

#: The JV SHOWCASE WEEKEND — the season-ending event, and the only JV event there is
#: (owner rule 2026-08). One per program, played after the invitational cap has bound,
#: and it does NOT count against `JV_DUAL_CAP`. The varsity showcase machinery is
#: reused wholesale.
#:
#: It is also the answer to "should JV have playoffs", which is no: a playoff needs a
#: ranking to seed it and JV has none by design, a JV team is a slice of the ladder
#: rather than a standing squad, and the format is elastic so a semifinal and a final
#: could be different shapes. A showcase weekend needs none of that — no bracket, no
#: advancement, no seeding.
JV_SHOWCASES_PER_PROGRAM = 1
JV_SHOWCASE_NAME = 'JV Showcase Weekend'

#: The JV level marker, on the schedule entry and on `world_jhsaa_dual.level`.
#: ‼️ A LEVEL, NEVER A PHASE. A phase is the archive's identity for an EVENT and it
#: selects the dual format and the postseason lane; JV plays inside its own league and
#: its own invitationals, at every phase varsity has. And under the archive rule below
#: it is load-bearing for IDENTITY, not merely for filtering: a JV row and a varsity row
#: can BOTH carry an empty `lines`, so `level` is the only thing telling them apart.
LEVEL_VARSITY = "v"
LEVEL_JV = "jv"


ROSTER_SIZE = 12          # legacy flat default; real depth is per-classification, see below

# ‼️ BIGGER SCHOOLS CARRY BIGGER ROSTERS (owner rule 2027-08) — the same pattern
# `ncaa.ROSTER_CAP`/`ncaa.roster_cap` already uses for college divisions, extended
# here rather than invented fresh. Depth scales with classification because a big
# school genuinely has more kids trying out — varsity AND a JV feeder blur into one
# deeper roster here, since the association has no separate JV system to model with.
# On the SAME talent metrics as everyone else in the classification (`_ceiling`,
# `talent_group`) — a bigger roster means more players at the going talent level,
# not weaker filler bodies. That deliberately means big-classification rosters carry
# real depth "above their station" relative to a bare lineup card; that is the
# point of modelling depth at all, not a side effect to suppress.
#: Roster depth is a BAND per classification (owner rule 2027-08, "we can go
#: bigger"), not one classification-wide number — the same shape as the college
#: side's recruiting-budget bands. Two classes share a band (9A/8A, 7A/6A, 5A/4A);
#: 3A, 2A and 1A each get their own, since the old flat 16/14/13 compressed the
#: bottom of the ladder the most. Every band was raised versus the old flat
#: targets (9A 24→20-24, 8A 23→20-24, 7A 22→19-22, 6A 20→19-22, 5A 19→18-20,
#: 4A 18→18-20, 3A 16→17-19, 2A 14→15-17, 1A 13→14-16) — smallest classes gained
#: the most, which is exactly where `ROSTER_FLOOR` was getting hit.
ROSTER_SIZE_BAND_BY_CLASS = {
    "9A": (20, 24), "8A": (20, 24),
    "7A": (19, 22), "6A": (19, 22),
    "5A": (18, 20), "4A": (18, 20),
    "3A": (17, 19),
    "2A": (15, 17),
    "1A": (14, 16),
    # 2046 Great Basin groups: each spans a wide enrollment range rather than one
    # rung, so the bands blend the ladder classes they cover — Division 1
    # (845-2556, roughly 5A-9A) blends the 6A/5A bands; Division 2 (57-836,
    # roughly 1A-4A/low-5A) blends the 4A-2A bands.
    "Division 1": (18, 22),
    "Division 2": (15, 19),
}


def roster_size(classification: str, school_key: str = "", salt: str = "") -> int:
    """A program's TARGET total roster depth for `classification` — a STABLE
    per-program draw within the classification's band, not one number shared by
    every school in it. Real programs inside one classification support
    noticeably different squad depth (a big feeder program vs. a thin rural
    one), so each school draws ONE point in its band and keeps it — seeded on
    the SCHOOL alone, NEVER the year, so it reads as a durable program trait
    (the same idiom as a recruiting budget) rather than something that
    reshuffles season to season. `_freshman_class_size` is what actually turns
    this into player counts, one grade's worth at a time.

    `school_key` is optional: omit it for a bare classification-level query (an
    band midpoint) — nothing in the roster-build path does this, but division-
    level reporting/analysis code might. Falls back to the flat `ROSTER_SIZE`
    for anything not in the table (there shouldn't be any real classification
    that isn't)."""
    band = ROSTER_SIZE_BAND_BY_CLASS.get(classification)
    if band is None:
        return ROSTER_SIZE
    lo, hi = band
    if not school_key:
        return round((lo + hi) / 2)
    rng = random.Random(f"{salt}|jhsaa-roster-band|{school_key}")
    return rng.randint(lo, hi)


#: ONE MORE THAN the regular-season format's distinct-player count (owner rule
#: 2026-08). That format needs 11 — S1 + the doubles pool #2-#9 + S2 + S3 — which is
#: the biggest single-dual requirement in the whole JHSAA calendar (the early 5S/2D
#: window and the 1S/4D postseason both need only 9). The floor sits at 12 so a
#: program at the floor still has ONE player who is not dressed: a squad with exactly
#: enough bodies to field a dual has no bench at all, so an absence has nowhere to
#: come from and the rest/rotation rules have nothing to move. A HARD FLOOR on
#: `build_roster`'s total output, same invariant as the college side's
#: `ncaa.lineup_size`/`refill_walkons`.
#:
#: ‼️ AND THERE IS NO CEILING, DELIBERATELY (owner rule 2026-08).
#: `ROSTER_SIZE_BAND_BY_CLASS` is a TARGET that `_freshman_class_size` draws around
#: with real variance, not a cap — measured rosters run 11 to 36 — and the transfer
#: portal appends on top of that without checking anything. Both are intended: the
#: owner reallocates talent by hand every offseason, and a big school being able to
#: roll a deep squad is what makes moving players down the ladder worth doing. Do not
#: "fix" the over-band rosters by clamping them.
#:
#: ‼️ WHY THIS EXISTS: `_freshman_class_size` rolls each grade INDEPENDENTLY with
#: real downside variance (35% of a mean as low as ~3.5/grade even at 1A's raised
#: 14-16 band), so a real, unlucky run of four grades can and does land a program's
#: roster below what the
#: format needs — not a "the generation code isn't running" bug, a missing floor
#: under code that otherwise works exactly as designed. Below this floor, `_squad`
#: has no choice but to wrap (`r[i % len(r)]`, "degrade, never crash, on a short
#: side") and put the SAME player on two lines of the SAME dual at once — which a
#: real tennis rule never allows and which corrupts that dual's stats permanently
#: once archived. `build_roster` tops the CURRENT year's incoming freshman class up
#: to this floor when short (never grades 10-12, whose sizes are already fixed from
#: a PRIOR year's roll — touching them would break `_freshman_class_size`'s "rolled
#: once per (school, entry_year)" contract and desync from anything already
#: archived against that class).
#: ‼️ RAISED 12 -> 16 WHEN THE JV SEASON LANDED (owner rule 2026-08). A JV dual needs
#: FIVE spare players on top of varsity's eleven (`JV_FORMATS`' smallest entry, 1S/2D),
#: so 11 + 5 = 16 is the floor at which EVERY program in the association can field a
#: JV. Fifteen was considered and rejected by measurement: it raises the 12-14 rosters
#: to 15 and leaves them — plus the 61 girls'/42 boys' programs already sitting at
#: exactly 15 — still one player short, i.e. it changes nothing at all for JV. At 16,
#: 864/864 girls' and 780/780 boys' programs field one.
#: See `docs/BRIEF-jhsaa-jv-and-varsity-2-feasibility.md` §3.
ROSTER_FLOOR = 16


def _freshman_class_size(school_key: str, entry_year: int, classification: str,
                         salt: str = "") -> int:
    """How many freshmen entered `school` in `entry_year`.

    ‼️ ROLLED ONCE PER (school, entry_year), NEVER PER VIEWING YEAR (owner rule
    2027-08). This is the ONLY source of randomness in grade distribution: a
    cohort's size is fixed for the rest of its four years no matter which
    season you view it from — a grade's seat count in `build_roster` is simply
    ITS OWN entry-year's roll, aged forward unchanged. Two consequences fall
    out for free, with no separate "which year is this" branch needed:
      * Year 1's snapshot mixes FOUR different entry years (this year's, and
        three retroactive ones for the returning classes), each independently
        rolled — a naturally random class mix, not an even split.
      * Every later year's growth comes ENTIRELY from that year's own
        freshman roll; grades 10-12 never get a separate random bump.
    No non-freshman newcomers are procedurally generated at all — a real
    sophomore/junior arrival is a TRANSFER (a separate mechanic, scaled from
    the college game's transfer portal; not modelled here), never a generation
    roll pretending to be one."""
    target = roster_size(classification, school_key, salt) / len(GRADES)
    rng = random.Random(f"{salt}|jhsaa-class|{school_key}|{entry_year}")
    return max(1, round(rng.gauss(target, target * 0.35)))

# Non-district duals per team (owner rule 2027-08). The POSTSEASON IS EXEMPT.
# This is an ALLOWANCE ON TOP of the district card, not a season total: district
# size sets most of the schedule (a 12-team district is 18 league duals under
# `DISTRICT_DUAL_CAP`, a 6-team one is 10), so a fixed season total would force
# wildly different non-league loads on schools of different districts. To shorten
# seasons, lower `DISTRICT_DUAL_CAP` or shrink the districts (`MAX_DISTRICT` in
# `scripts/import_jhsaa.py`) — not this.
NONDISTRICT_MIN, NONDISTRICT_MAX = 4, 8

# How that allowance is spread across the season (owner rule 2027-08). A high-school
# card is not "all the non-league games, then all the league ones" — it opens
# non-district, runs the league, breaks for a mid-season window, runs the league back
# the other way, and has room for a tune-up before districts. USTA's model treats
# district, non-district and tournament play as separate schedule TYPES rather than one
# undifferentiated block, and this is where that shows up in the order of play.
EARLY_SHARE = 0.55        # of the non-challenge non-district card, played before league
MID_NONDISTRICT = 1       # non-district duals in the mid-season window, besides the challenge

# --- the mid-season challenge (owner rule 2027-08) ---------------------------
# One cross-district dual in the mid-season window, paired AFTER the first league pass
# on how the season has actually gone — the scheduling idea behind college basketball's
# old BracketBusters: hold a date open, then match comparable programs from different
# leagues once you know who is comparable. So the #3 team in one district draws the #3
# in another, not whoever geography threw up in February.
#
# It is NON-DISTRICT and can never touch district place; it is an ordinary result
# everywhere else (overall record, TOSS, at-large selection), which is the point of
# playing it. Hosting alternates on a hash of the pairing and the year, so no program
# is systematically at home for it.
CHALLENGE_ENABLED = True
CHALLENGE_PLACE_SLACK = 1     # pair a #3 with a #2-#4; never a #1 with a #8
CHALLENGE_GEO_WEIGHT = 6.0    # travel matters, but less than getting the level right

# --- the mid-season MATCH SHOWCASES (owner spec 2027-08) ----------------------
#
# ‼️ THE ASSOCIATION'S POSTSEASON IS A DIFFERENT SPORT FROM ITS LEAGUE SEASON... or it
# was, before the 2027-08 swap moved the league card to 3S/4D too — see EARLY_FORMAT_
# PHASE above. League play now shares State's doubles-forward shape all season (only
# the early non-district window still plays the old 5S/2D singles-heavy card); the
# showcases exist so a program still fields the exact 1S/4D card before Sectionals asks
# for it, since even 3S/4D never puts a #4-#9 pairing through a full four-doubles dual.
# The showcases are the ONLY 1S/4D duals before the postseason.
#
# ‼️ THEY ARE NOT A TOURNAMENT. No bracket, no draw, no compass, no elimination, no
# champion, no title, no seed and nothing at stake — a program attends to play a fixed
# number of duals against opponents it would not otherwise meet. Everything in this
# module that crowns something takes a bracket (`run_state`, `run_rounds`); a showcase
# is a flat list of pairings, and that difference is deliberate rather than incidental.
# If a showcase ever needs a standing, it has stopped being a showcase.
SHOWCASE_ENABLED = True

# Six to eight designated weekend windows, half of each kind. A window is a WEEKEND, not
# a week: there is no clock inside a JHSAA season (see `play_regular_season`), so a
# window is a position in the order of play, and `world.jhsaa_match_dates` is what lands
# it on a Saturday or a Friday-Saturday.
SHOWCASE_WINDOWS_MIN, SHOWCASE_WINDOWS_MAX = 6, 8

# A 1-DAY POD is four programs playing a full round robin: three duals, one Saturday,
# three pro sets per player. That is the USTA junior daily limit exactly, and it is why
# the pod is scored as a pro set and sized at four rather than five — a fourth dual, or
# a best-of-3, would put a junior over the limit in a single day.
POD_SIZE, POD_DUALS = 4, 3
# A 2-DAY TIERED group is six programs playing four of the other five: two duals a day
# across Friday and Saturday. Six rather than five because a 6-team round robin's first
# four rounds are four PERFECT matchings — everybody plays in every session, so the four
# duals fall as 2 + 2 with nobody sitting out a day. A 5-team group would give the same
# four duals only by byeing somebody out of each session.
TIER_SIZE, TIER_DUALS = 6, 4
# The three skill tiers a 2-day showcase's field is split into, top down. Statewide and
# CLASSIFICATION-BLIND (owner spec): the point of the event is cross-classification
# exposure, so a 3A program that has earned an Open-tier seat plays there.
SHOWCASE_TIERS = ("Open", "B", "C")

# Participation, as a share of the association (owner spec 2027-08). About half the
# programs attend a showcase in a given season, nearly all of them once.
SHOWCASE_SHARE = 0.50         # of all programs, per gender, per season
SHOWCASE_TWO_SHARE = 0.045    # of those, attending twice
SHOWCASE_THREE_MAX = 3        # statewide, and elite only — 1% of a ~450-program field
SHOWCASE_ELITE = 25           # the Top 25 get first call on every multi-event seat

# ‼️ A SHOWCASE RESULT IS TOSS-RATED — THAT IS THE POINT OF PLAYING THEM (owner rule
# 2027-08, and it reverses my first reading of "non-competitive").
#
# "Non-competitive" means no bracket, no advancement and no title. It does NOT mean the
# results are thrown away: a showcase is four duals against cross-district,
# cross-classification opposition a program would otherwise never meet, which is the
# single most valuable thing that can happen to an opponent-strength rating. TOSS is
# 40% APR + 40% FQI + 20% oGS and all three are opponent-weighted, so a season played
# only inside one league is a rating computed on a nearly disconnected graph. The
# showcases are the cross edges. Excluding them would throw away the evidence the event
# was held to generate.
#
# This is why `FLIGHT_WEIGHTS` must weight D3/D4 for the CUTOFF table and not only for
# the in-postseason recomputes — see the note there.
SHOWCASE_RATED = True

# High school runs at "fast" fidelity, deliberately. `full` resolves every POINT, which
# is 6.7x the cost and is meant for the college season you actually watch; a season here
# is ~5,100 duals per gender and at full fidelity it added ~100s to the first recruit
# class build — on the request thread, which is the outage class CLAUDE.md warns about.
# Winners, scores and individual records are all unaffected; only per-point box detail is.
FIDELITY = "fast"

# --- the postseason (owner spec 2027-08, expanded State fields) ----------------
#
# Decoupled mechanisms, in ladder order:
#
#   1. SECTIONALS (Areas when multi-round) — broad access and field reduction.
#      Every non-protected team enters; the shape is flexible per classification
#      (byes/play-ins as needed); the ONLY fixed requirement is the output:
#      exactly `WARD_FIELD` teams.
#   2. The qualification ladder — fixed for every classification and both genders:
#         Wards      32 -> 16
#         Regionals  32 -> 16   (16 Ward champions + 16 protected)
#         Zonals     16 -> 8    (Zonal champions qualify for State, WITH the
#                                privileged path: they are the State draw's top
#                                seeds, so a 24-team field's eight byes are theirs)
#      The protected 16 enter at Regionals: district champions first, then the
#      best remaining cutoff TOSS until the seats are filled.
#   3. THE DISTRICT GUARANTEE — a district champion is guaranteed State ACCESS
#      even if it loses in the ladder (a geographic-access safeguard: no region
#      is excluded from State because TOSS dislikes it). Access only: no State
#      bye unless it also won its Zonal, and no extra berth if it did.
#   4. THE RECOVERY ROUNDS — Super Regionals -> Semi-State. The remaining State
#      berths are EARNED ON COURT by the loser pool (16 Regional losers + 8
#      Zonal losers, minus anyone the district guarantee already admitted),
#      never handed out by a TOSS recompute: the owner replaced the wild-card
#      model precisely because teams sitting at home could out-rank teams still
#      playing. Regional losers enter at Super Regionals; Zonal losers join at
#      Semi-State; Semi-State and the Divisionals take the berths that remain;
#      and where those still fall short, the SEMI-CONFERENCE qualifies everyone
#      else on court for a CONFERENCE that fills the rest. The arithmetic is
#      DYNAMIC (`_recovery`): berths = state field - Zonal champions, and every
#      round pairs its whole field, so the shape follows the field size rather
#      than a constant. `recovery_shape` projects it from the constants alone.
#
# `STATE_FIELD`: the owner's field table below. EVERY class now crowns from 40, but
# the 24 remains the shape underneath it — a 24-team seeded draw has exactly eight
# first-round byes and those byes ARE the Zonal champions' privilege; a 40 puts a
# Qualifiers Round in front of that same 24 (see the table's own comment).
#
# ‼️ THERE IS NO SCALING. Every classification plays the full ladder and the
# owner's field table as written; a pool too small for it is a broken fixture,
# not a format to accommodate.
PROTECTED = 16
WARD_FIELD = 32
# Field size per classification (owner table, 2027-08; 7A raised 2026-08). EVERY
# classification crowns from 40. The table stays a table rather than becoming one
# constant because the field size is an owner DECISION per class, and the ladder's
# arithmetic is derived from it (`_recovery`, `recovery_shape`, `sponsor_floor`) —
# a class could be moved back without touching anything else.
#
# It got here in two steps and 7A was the straggler: all three of the largest classes
# crowned from 24, then 9A and 8A were raised because the deepest classes were leaving
# plainly good teams home, and 7A was simply not changed in that pass. Nothing about
# 7A was ever special.
#
# ⚠️ A 40 IS A 24 WITH A QUALIFIERS ROUND IN FRONT OF IT. The eight Zonal champions
# take a DOUBLE bye to the Octofinals; seeds 9-40 play the Qualifiers Round and then
# the First Round, and the eight who survive both join them. After the Qualies
# exactly 24 are alive — the other classes' bracket — so both shapes converge and
# there is one championship from the Octofinals down.
#
# This is what a 32 could never do: 32 is a full bracket, so a champion cannot be
# given a bye without inventing a round for everybody else to sit out.
#
# 2A joined them in the 2033 realignment (owner rule 2026-08): it was the class the
# 1A/2A split was meant to leave viable and it had 63 programs to 3A's 125, so 3A
# crowned from 40 and 2A from 24. The realignment moved 32 schools down, and once 2A
# is a 95-program class its playoff "mirrors every other classification" (owner) —
# the dynamic recovery ladder, not the fixed 24-team shape. It clears
# `sponsor_floor` comfortably: 95 girls' programs and 87 boys' against a floor of 76.
# 1A is unchanged and stays the one class on the 24 (`_recovery_24`).
STATE_FIELD = {"9A": 40, "8A": 40, "7A": 40,
               "6A": 40, "5A": 40, "4A": 40, "3A": 40, "2A": 40, "1A": 24,
               # 2046 expansion (owner rule): the two Great Basin groups are two
               # more classifications, full stop -- "think of them more as 10A
               # and 11A than thinking of them as anything weird." 92 sponsors
               # each clears the dynamic-ladder floor comfortably (76 required
               # at a 40-field) so they play the standard shape, not `_recovery_24`
               # (that shape stays 1A-only per its own owner rule).
               "Division 1": 40, "Division 2": 40}
STATE_FIELD_DEFAULT = 24

#: The preliminary round of an expanded field — "Qualies" on a chip. It is PART OF
#: STATE, not a road-to-State stage: it plays the state dual format, carries the
#: state phase and rides on the state bracket.
QUALIFIER_NAME = "Qualifiers Round"


def state_field_size(group: str) -> int:
    """The classification's State field. There is no scaling: every class plays the
    owner's table at full size, and a pool too small for it is a broken fixture, not
    a format to accommodate."""
    return STATE_FIELD.get(group, STATE_FIELD_DEFAULT)


def _even(n: int) -> int:
    """The largest even number <= n. Every recovery field is byeless, so a pool is
    only ever used at an even size."""
    return max(0, n - (n % 2))


def recovery_shape(group: str) -> dict:
    """The PROJECTED size of every recovery round for `group`, from the constants
    alone — no season required.

    ‼️ This is a projection, not the live computation. `_recovery` sizes its rounds
    off the pools it is actually handed, because it must degrade rather than crash
    on a thin one; this reproduces the same arithmetic on a full-size ladder so the
    data layer can be checked BEFORE a season is played (`sponsor_floor`, and
    `scripts/import_jhsaa.py`'s preflight). The two are bound by
    `tests/test_jhsaa_ladder.py`, which asserts a real season lands on these
    numbers — keep them together or this becomes a second source of truth for a
    shape only `_recovery` really decides."""
    ward_champs = WARD_FIELD // 2
    regional_field = PROTECTED + ward_champs
    reg_losers = regional_field // 2                  # Regionals halve
    champions = zon_losers = reg_losers // 2          # Zonals halve again
    berths = max(0, state_field_size(group) - champions)

    sr = _even(reg_losers)
    sr_w, sr_l = sr // 2, sr - sr // 2
    need = -(-4 * berths // 3)
    need += need % 2                                  # the Semi-State floor, EVEN
    base = sr_w + zon_losers
    target = min(max(need, base), 2 * berths, base + sr_l)
    ss = _even(target)
    ss_w, ss_l = ss // 2, ss - ss // 2

    dv = _even(min(2 * max(0, berths - ss_w), ss_l))
    dv_w, dv_l = dv // 2, dv - dv // 2

    cf_seats = 2 * max(0, berths - ss_w - dv_w)
    # District champions all take protected seats, so they are always already
    # somewhere in the ladder — the direct pool is the Divisional losers.
    body_seats = max(0, cf_seats - dv_l) if cf_seats else 0
    return {"berths": berths, "champions": champions,
            "super_regional": sr, "semi_state": ss, "divisional": dv,
            "semi_conference": 2 * body_seats, "conference": cf_seats,
            "body_seats": body_seats}


def sponsor_floor(group: str) -> int:
    """The fewest sponsors per gender a classification needs to play its own format.

    ‼️ THE SEMI-CONFERENCE IS WHAT SETS THIS, and it is a DATA invariant, not a
    format to bend (`scripts/import_jhsaa.py` preflights it and refuses to emit
    under it). The body reservoir — everyone eliminated in Areas, Sectionals or
    Wards, i.e. every team that can still be called back — is `programs - 32`:
    `PROTECTED` teams skip to Regionals and `WARD_FIELD` reach Wards, of which
    half lose there and rejoin the pool. For a 40-field class the Semi-Conference
    wants 44 bodies, so the floor is `32 + 44 = 76`; a 24-field class fills without
    a Conference, neither round convenes, and it has no floor of its own.

    ‼️ 1A's FIXED 24-TEAM SHAPE (`_recovery_24`) IS A DIFFERENT FORMULA. Every
    round size in that shape (Super Regional/Semi-State 16, Divisional/Semi-
    Conference/Conference 8) is a fixed function of `PROTECTED`/`WARD_FIELD` alone
    — never of total sponsor count — so there is no Semi-Conference body reservoir
    to run dry the way the dynamic 40-team shape's can. The only real requirement
    is enough sponsors to fill the entry gates at all: `PROTECTED` district champs
    plus `WARD_FIELD` at Wards."""
    if state_field_size(group) == 24:
        return PROTECTED + WARD_FIELD
    shape = recovery_shape(group)
    return WARD_FIELD + shape["semi_conference"] if shape["conference"] else 0


# --- talent ------------------------------------------------------------------
# (mean, spread) of the 20-80 grade per classification. Well beneath the college bands
# (D1 men 60/16, D3 men 39/27) and far wider — a 7A roster and a 1A roster barely
# belong to the same sport. Girls sit a little under boys, mirroring the college split.
# NOTE these are CEILING targets, not current ability: `generate_prospect` treats
# `talent` as the potential and derives a much lower current from maturity, so a 7A
# number one with a ceiling of 46 still plays at a current ~30 while in school. That is
# the whole reason the bands look high for high schoolers — do not "fix" them downward
# by comparing them to the college _TALENT means, which ARE current.
# The top-190 graduating seniors are Jefferson's entry on the national recruit board.
# MEASURED, not asserted: best ~#227 of 2500, median ~#483, i.e. the hand-off sits in the
# top fifth of the class rather than astride its median. (The comment here used to claim
# "best ~#25, median near the national median"; it was ~#274/#527 before this rebalance
# too, so it was describing an intention rather than the numbers. Re-measure before
# quoting it — `graduating_class` against `world.board_class`.)
# ⚠️ SMALLER SCHOOLS ARE THINNER, NOT CAPPED (owner rule 2027-08). Tennis is not a
# sport where the big school simply has better players — good players turn up
# everywhere, and what enrollment actually buys you is DEPTH. So the classifications
# differ in the BULK of the distribution (the mean) while the upper tail stays broadly
# common (the spread WIDENS as the mean falls), and 7A/6A are near-indistinguishable at
# the top with the real steps coming below.
#
# The previous ladder was a flat -5/-4 shift per class with the spread NARROWING as the
# mean fell, which gets the sport backwards in a way that only shows if you measure the
# lineup position by position. Measured on the old numbers (boys, mean current OVR):
#
#            #1     #9   drop   best #1 seen
#   7A     54.4   31.1   23.2     60.0
#   3A-1A  42.0   22.8   19.2     51.0
#
# The #1s were 12.4 apart and the #9s only 8.3 — the TOP fell faster than the depth, and
# the drop from #1 to #9 was FLATTER at a small school than a big one. A 3A-1A program
# could not produce a 60 at all, so it could never be the small school sitting top-10 in
# the state, which is a completely ordinary thing in real high-school tennis (in Oregon's
# 2026 boys table, Oregon Episcopal — the smallest classification — finished No. 9
# statewide, and four of the top eight were 5A).
#
# Widening the spread as the mean falls does both jobs at once, because 12 ceilings are
# drawn and the best 9 dress: a wide draw lifts the number one a long way and drags the
# number nine down. Do NOT "tidy" these back into an even ladder with shrinking spreads.
# The nine-class ladder (owner 2027-08) extended the top of this table. 9A/8A/7A
# sit close together on purpose — see the note above: the real steps are lower
# down, and every classification can still produce an elite number one.
_TALENT = {
    ("9A", "boys"):   (59.4, 14.4), ("9A", "girls"):   (54.6, 13.4),
    ("8A", "boys"):   (58.7, 14.8), ("8A", "girls"):   (53.9, 13.8),
    ("7A", "boys"):   (58.0, 15.0), ("7A", "girls"):   (53.3, 13.9),
    ("6A", "boys"):   (56.5, 15.5), ("6A", "girls"):   (51.5, 14.5),
    ("5A", "boys"):   (51.0, 17.5), ("5A", "girls"):   (46.5, 16.5),
    ("4A", "boys"):   (46.0, 19.0), ("4A", "girls"):   (42.0, 18.0),
    ("3A", "boys"):    (43.5, 20.0), ("3A", "girls"):    (38.0, 19.0),
    ("2A", "boys"):    (41.0, 21.0), ("2A", "girls"):    (36.5, 20.0),
    ("1A", "boys"):    (36.0, 23.0), ("1A", "girls"):    (32.5, 22.0),
    # 2046 Great Basin groups. Each classification spans several ladder classes'
    # worth of enrollment, so the band is a BLEND of the classes it covers, per
    # the section rule (smaller = thinner mean, wider spread): Division 1
    # (845-2556 ≈ a 5A-9A mix) sits between 6A and 5A; Division 2 (57-836 ≈ a
    # 1A-4A mix) sits between 3A and 2A. `classification` on these schools IS
    # "Division 1"/"Division 2", so `School.talent_group` reads these keys —
    # without them every Great Basin roster build KeyErrors.
    ("Division 1", "boys"): (54.5, 16.5), ("Division 1", "girls"): (49.5, 15.5),
    ("Division 2", "boys"): (42.0, 20.5), ("Division 2", "girls"): (37.5, 19.5),
}
# --- PROGRAM ARCHETYPES (owner rule 2027-08) ---------------------------------
#
# A school-level modifier ON TOP of the classification bands above, never a replacement
# for them: a blue-blood 3A-1A program is a strong SMALL-SCHOOL program, not a 7A one.
# It describes DURABLE PROGRAM CONDITIONS — facilities, feeder networks, community
# participation, coaching tradition, reputation — not current team strength, and it is
# deliberately NOT derived from classification or public/private. Those may inform who
# gets seeded onto the list; the property belongs to the individual school and is
# editable (`/editor`, `overrides.set_jhsaa_archetype`) so the owner can promote and
# demote programs as Jefferson's history develops.
#
#   blue_blood   generates better, and CLUSTERS — several strong players in one roster
#   development  generates normal CURRENT ability but high POTENTIAL, and develops it
#                faster, so the effect shows over a four-year career rather than on
#                arrival
#   doubles      generates normally; the edge is in DOUBLES ONLY, as a per-match boost
#   neglect      generates normal CEILING but develops it SLOWER — a governor on the
#                same mechanism `development` accelerates, run in reverse; see
#                `neglect_severity()`
#   upstart      a TEMPORARY multi-year run, rolled per world — see `upstarts()`
#   (untagged)   normal
#
# `mean` shifts the classification band's centre; `spread` scales its width; `pot` is a
# ceiling-only bonus (potential without present ability); `mature` accelerates how much
# of that ceiling has surfaced by each grade.
ARCHETYPES = {
    # BETTER ON BALANCE than a development programme (owner rule 2027-08) — that is what
    # makes it a blue blood — and it shows on ARRIVAL: its ninth-graders are already in
    # the low thirties, where an ordinary program's are mid-twenties. A development
    # program can still beat one in a given season; it just has to earn it over four
    # years rather than have it on day one.
    "blue_blood":  {"mean": +15.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Blue blood"},
    # A development programme SHOULD be able to beat a blue blood outright (owner rule
    # 2027-08) — that is the point of it, and it is how coaching levels a playing field
    # that facilities and reputation tilt. What separates them is the SHAPE, not the
    # ceiling: `mean` is 0 and the maturity bonus starts at ZERO for freshmen and
    # compounds by grade, so this program's ninth-graders look ordinary and its seniors
    # are the best in the association. Arrive good vs leave great.
    "development": {"mean":  0.0, "spread": 1.05, "pot": +6.0, "mature": 0.038,
                    "label": "Development program"},
    "doubles":     {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Doubles school"},
    # ⚠️ NEGLECT (owner rule 2026-08) — bad coaching, bad facilities, a program that
    # wastes what its players walk in with. "Doesn't mean players won't get what they
    # get normally, it just dampens it" (owner) is the exact spec: CEILING is left
    # alone (`mean`/`spread`/`pot` all 0.0, same as `doubles`) and only the RATE a
    # player reaches that ceiling is throttled — a governor on the SAME `mature` lever
    # `development` accelerates, run negative. The real per-school number is drawn by
    # `neglect_severity()`, not read from this table (`mature` sits at the placeholder
    # 0.0 here for the same reason `upstart`'s row is all zeros: the effect is
    # per-program, not one constant every tagged school shares equally).
    "neglect":     {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Neglected program"},
    "upstart":     {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Upstart"},
}

# A blue blood does not just draw higher, it draws TOGETHER: a share of its seats are
# re-rolled and the better draw kept, which is what "several strong players in the same
# roster" means. Applied per seat, so it lifts the top of the lineup much more than the
# bottom — the same best-of-n effect the classification spread uses.
BLUE_BLOOD_REDRAW = 0.70

# UPSTART — a temporary run, not a promotion. ~10 programs statewide at any time, each
# for a few seasons, rolled deterministically from the world salt so a save reproduces
# its own history and the run EXPIRES on its own.
UPSTART_N = 10
UPSTART_RUN = (2, 4)              # seasons a run lasts
UPSTART_LIFT = (0.15, 0.30)       # 15-30% stronger than the program's own baseline

# DOUBLES SCHOOLS — the edge is ephemeral and per-match, not a better roster. There was
# no existing per-match boost to reuse (`coaches.development_multiplier` is a growth
# rate, not a match modifier), so this is the first: `_squad` already builds doubles as
# its OWN lineup (`Team.doubles_players`), so a boosted copy of those players is confined
# to doubles by construction and cannot leak into a singles court.
DOUBLES_BOOST = (5.0, 11.0)

# NEGLECT — a per-grade maturity DRAG, the mirror of `development`'s +0.038 `mature`
# bonus. ⚠️ ITS MAGNITUDE MUST STAY WELL UNDER `DEV_MIN_STEP` (0.045, the per-year
# development floor "nobody stagnates" is built on): `_gen_seat` adds this constant
# once per grade elapsed (`step = mature * (grade - 9)`), so the year-over-year CHANGE
# in that step is the constant itself, and if it ever exceeded `DEV_MIN_STEP` a
# neglected senior could read as LESS mature than they were as a junior — reversing
# development, not dampening it, which contradicts the owner's own framing ("doesn't
# mean players won't get what they get normally, it just dampens it"). At -0.030 the
# worst case (three grade-years) is a 0.09 drag against a guaranteed minimum 0.135
# rise over the same span — real, but a player under even the harshest Neglect roll
# still improves every season.
#
# ‼️ A RANGE, NOT ONE CONSTANT — deliberately, unlike every other archetype's fixed
# numbers. "I want to be able to constrain some programs partially" (owner): a real
# under-resourced program is not a uniform, on/off kind of bad, and a single number
# would flatten Neglect into exactly the binary switch the owner asked NOT to build.
# `neglect_severity()` draws each tagged school ONE stable point in this band — same
# one-point-per-band idiom as `roster_size` — so severity varies continuously across
# the tagged population, which is also what makes it usable as an A/B surface: compare
# development outcomes against the DRAWN severity, not just against a tag.
NEGLECT_MATURE = (-0.030, -0.012)


def neglect_severity(school_name: str, salt: str = "") -> float:
    """This program's stable per-grade maturity drag — negative, drawn once from
    `NEGLECT_MATURE` and durable for as long as the school is tagged `neglect`.
    Seeded on the school alone, never the year or the player, so it reads as a
    durable program trait (bad facilities don't get better or worse season to
    season) rather than something that reshuffles on read."""
    return random.Random(f"{salt}|jhsaa-neglect|{school_name}").uniform(*NEGLECT_MATURE)


# TWO LAYERS, as the owner specified: the SEED list ships with the repo as school data
# (`data/jhsaa/archetypes.json`), and the override table is the editable layer on top, so
# a save can promote or demote a program without editing the file — and clearing an
# override reverts that program to whatever the seed says. An override of "none"
# explicitly DEMOTES a seeded program, which is different from having no override at all.
_ARCH_SEED_PATH = os.path.join(os.path.dirname(_DATA), "archetypes.json")
_arch_cache: dict = {}


def _arch_seed() -> dict:
    try:
        with open(_ARCH_SEED_PATH, encoding="utf-8") as fh:
            return {k: v for k, v in json.load(fh).get("programs", {}).items() if v}
    except (FileNotFoundError, ValueError):
        return {}


def bulk_edit_archetype_seed(kind: str | None, names: list[str], remove: bool = False) -> dict:
    """Add or remove MANY schools' archetype tag in ONE pass, writing the SEED FILE
    itself (`data/jhsaa/archetypes.json`) rather than the per-save override table.

    ‼️ WHY THE SEED FILE, NOT AN OVERRIDE (owner request): the override table lives
    in the SAME sqlite file as the world, and the owner routinely starts over with a
    brand-new database file rather than resetting the existing save — a per-save
    override cannot survive that, since there is no "the save" for it to attach to
    the next time. The seed list, by contrast, ships with the code and is read fresh
    by every database. One-by-one editing through `/editor/jhsaa-archetype` (which
    DOES write a per-save override, and still exists for a single quick change) was
    "massively tedious" for a real list and had to be redone after every fresh save
    — this is the fix for both problems in one move: bulk, and permanent.

    Unknown names are silently skipped (never invents a school); returns
    {"applied": [...], "unknown": [...]} so the caller can report both. Existing
    per-save overrides for a touched school are NOT cleared — an override still
    wins over the seed on read (`_arch_map`), exactly as before."""
    valid_names = {r["name"] for r in playup_rows()}
    applied, unknown = [], []
    with open(_ARCH_SEED_PATH, encoding="utf-8") as fh:
        doc = json.load(fh)
    programs = doc.setdefault("programs", {})
    for name in names:
        name = name.strip()
        if not name:
            continue
        if name not in valid_names:
            unknown.append(name)
            continue
        if remove:
            programs.pop(name, None)
        else:
            programs[name] = kind
        applied.append(name)
    with open(_ARCH_SEED_PATH, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    _arch_cache.clear()
    return {"applied": applied, "unknown": unknown}


def archetype(school: str) -> str:
    """A program's archetype tag, or "" — the seed list with the editable table on top."""
    from app import overrides as ov
    return _arch_map(ov.jhsaa_archetype_version()).get(school, "")


def _arch_map(version: str) -> dict:
    """{school: archetype}, memoised on the override table's fingerprint. Computed into a
    LOCAL and published (the gthread rule); never read back out of the dict it wrote."""
    hit = _arch_cache.get(version)
    if hit is not None:
        return hit
    from app import overrides as ov
    out = _arch_seed()
    for school, kind in ov.get_jhsaa_archetypes().items():
        if kind == "none":
            out.pop(school, None)           # an explicit demotion of a seeded program
        else:
            out[school] = kind
    _arch_cache.clear()                     # one entry: only the current version matters
    _arch_cache[version] = out
    return out


def upstarts(year: int, salt: str = "") -> dict[str, float]:
    """{school: lift} for the programs currently on an upstart run.

    ‼️ MEMOISED PER SEASON, because `_program_mod` calls it for EVERY program and it
    walks the whole association twice (both genders) to build its pool. Unmemoised
    that is two `load_schools` calls per roster built — and once `load_schools` stopped
    being free (see there), it was 39,776 database round trips and 6.2 seconds for one
    program's roster. The table is a pure function of (year, salt) and the two override
    tables, so it is computed once per season and reused.

    Rolled per world rather than stored, because an upstart is a RUN and a stored tag
    would make it permanent. Each candidate's run start and length are derived from the
    salt, so the same save always tells the same story and a run ends by itself.

    Already-tagged programs are skipped — an upstart is a school having a moment, not a
    blue blood having a slightly better one — but they are skipped AT APPLICATION, never
    removed from the pool the draw runs over. Filtering the pool made the archetype table
    non-local: tagging one school changed which OTHER schools drew an upstart that
    season, because it changed what `rng.sample` was sampling from. A tag must only ever
    affect the school it is on."""
    from app import overrides as ov
    ck = (year, salt, ov.jhsaa_archetype_version(), ov.jhsaa_playup_version())
    hit = _upstart_cache.get(ck)
    if hit is not None:
        return hit
    tagged = set(_arch_map(ov.jhsaa_archetype_version()))
    pool = sorted({s.name for s in load_schools("girls")} | {s.name for s in load_schools("boys")})
    if not pool:
        return {}
    out: dict[str, float] = {}
    # Walk a window of seasons so runs overlap and roughly UPSTART_N are live at once.
    lo, hi = UPSTART_RUN
    for start in range(year - hi + 1, year + 1):
        rng = random.Random(f"{salt}|jhsaa-upstart|{start}")
        per_season = max(1, round(UPSTART_N / ((lo + hi) / 2)))
        for n in rng.sample(pool, min(per_season, len(pool))):
            run = rng.randint(lo, hi)
            lift = round(rng.uniform(*UPSTART_LIFT), 3)
            if start <= year < start + run and n not in tagged:
                out[n] = lift
    _upstart_cache.clear()               # one season is live at a time
    _upstart_cache[ck] = out
    return out


def _program_mod(school: School, year: int, salt: str) -> dict:
    """The combined school-level modifier for one program-season."""
    kind = archetype(school.name)        # one lookup: it resolves a table fingerprint
    a = ARCHETYPES.get(kind, {})
    mod = {"mean": a.get("mean", 0.0), "spread": a.get("spread", 1.0),
           "pot": a.get("pot", 0.0), "mature": a.get("mature", 0.0),
           "kind": kind}
    if kind == "neglect":
        # The table row is a 0.0 placeholder (see ARCHETYPES) — the real, per-school
        # number lives here, same reason `upstart`'s lift is layered on below rather
        # than read off the table.
        mod["mature"] += neglect_severity(school.name, salt)
    lift = upstarts(year, salt).get(school.name)
    if lift:
        # A percentage of the program's OWN baseline, so an upstart 1A is a strong 1A.
        mean, _spread = _TALENT[(school.talent_group, school.gender)]
        mod["mean"] += mean * lift
        mod["kind"] = mod["kind"] or "upstart"
    return mod


GRADE_FLOOR = 12.0        # below the 20-80 scale's nominal floor on purpose: 1A depth

# High school is grades 9-12 and nothing else. A player enters at 9 and leaves after 12.
GRADES = (9, 10, 11, 12)

# MATURITY is the share of a player's ceiling that is visible as current ability, and it
# is what keeps high school looking like high school. College freshmen already sit at
# 0.83 (`ncaa._CLASS_MATURITY`); a 9th grader shows well under half of what they will
# become. So ceilings can be as high as the talent deserves — a future D1 star really is
# in here — while nobody PLAYS beyond a high-school range until they leave.
# It also is the aging model: the same player's current rises every year purely because
# more of their ceiling has surfaced.
_MATURITY = {9: (0.40, 0.48), 10: (0.50, 0.58), 11: (0.60, 0.68), 12: (0.70, 0.78)}

# ⚠️ A FEW FRESHMEN ARRIVE FINISHED (owner rule 2027-08). Roughly 1 in 100 shows up with
# most of their ceiling already accessible — the kid who has been playing juniors since
# they were eight and walks straight into the number one spot. This is NOT a potential
# bonus: a prodigy can be an ordinary 45 ceiling who simply arrives at 40 instead of 20.
#
# It is a maturity FLOOR, and it persists for all four years, which is the whole point.
# The normal band rises with each grade, so a one-off ninth-grade boost would quietly
# un-mature them as a sophomore. Carrying the floor instead means they start near their
# ceiling and then barely grow — the early bloomer their classmates catch, which is what
# actually happens.
#
# Rolled on its OWN rng stream, not the roster one. Drawing it from the main sequence
# would shift every subsequent draw and regenerate every player in the association;
# keyed separately, the only rosters that change are the ones that gain a prodigy.
PRODIGY_RATE = 0.01
PRODIGY_MATURITY = (0.84, 0.93)

# --- PER-PLAYER DEVELOPMENT CURVES (owner rule 2026-08, era-gated) --------------------
#
# The old model above is LOCKSTEP: every player's maturity is one uniform draw mapped
# into their grade's band, so the whole association climbs the same four steps together
# and the ladder barely reorders between seasons — a freshman behind a senior in year
# one is behind that senior for four years, and "waiting your turn" is baked into the
# arithmetic. Six live seasons in, the owner's report was exactly that: senior-heavy
# lineups, underclassmen who never surface, and no way to even SEE what a young player
# is until the roster ahead of him graduates.
#
# New-era cohorts (entry year >= `dev_era()`, the `name_era()` idiom exactly) instead
# get a whole TRAJECTORY rolled once at entry, on its own rng stream:
#   * ARRIVAL is a wide, overlapping draw — a real share of freshmen arrive at
#     sophomore/junior maturity and crack a lineup on day one (`DEV_READY_RATE`,
#     distinct from the 1-in-100 PRODIGY, who still arrives nearly finished);
#     others arrive rawer than the old floor.
#   * FINISH is wide too — some seniors max out, some never fully arrive.
#   * The PATH between them has a per-player SHAPE: steady climbers, early bloomers
#     who arrive fast and flatten, late bloomers invisible until junior year, and a
#     thin senior-year spike. So players PASS each other between seasons, which is
#     what makes a ladder move.
#   * `DEV_MIN_STEP` is the program-wide floor: nobody stagnates outright — every kid
#     on a roster banks a visible minimum year over year, playing time or not.
# Bands are chosen MEAN-PRESERVING against `_MATURITY` (~0.44/0.54/0.64/0.74 by
# grade), so the association's overall level and the classification talent shape are
# unchanged — only the VARIANCE of who is good when moves.
#
# ‼️ ERA-GATED for the same reason names are: players are regenerated from seed, so an
# ungated curve change re-rates every archived season's rosters — ladders, player
# cards and awards would all disagree with the seasons that were actually played.
# Cohorts already in the building keep the old lockstep model byte-for-byte; the new
# model phases in over four seasons as classes turn over.
# ‼️ Rolled on its OWN rng stream (`jhsaa-dev`), like the prodigy roll — never off the
# main roster rng, which would shift every subsequent draw and regenerate everyone.
# ‼️ DELIBERATELY NOT MEAN-PRESERVING (owner numbers, 2026-08). A first draft held
# each grade's mean to the legacy bands; the owner — a real high-school coach —
# rejected it as too conservative: "you need them able to contribute and play …
# the whole point of a high school sim is to watch 4-year player development, that
# gets broken if they're only getting 1-2 years to play." So the whole association
# plays closer to its ceiling than the legacy cohorts do (freshman mean ~0.57 of
# ceiling vs 0.44; senior ~0.85 vs 0.74), a level shift on top of the wider spread.
DEV_ARRIVAL = (0.40, 0.64)         # base freshman arrival band
DEV_READY_RATE = 0.24              # share of freshmen who arrive ready to play
DEV_READY_ARRIVAL = (0.66, 0.82)   # their arrival band
DEV_FINISH = (0.76, 0.94)          # senior maturity band
DEV_MIN_RISE = 0.16                # a senior always sits at least this above arrival
DEV_MIN_STEP = 0.045               # the per-year development floor (nobody stagnates)
DEV_CAP = 0.98                     # nobody plays at full ceiling in high school
#: (shape, probability, exponent) — the curve m(g) = m9 + (m12-m9) * t**exp over
#: t = (grade-9)/3.
DEV_SHAPES = (("steady", 0.38, 1.0), ("early", 0.36, 0.55),
              ("late", 0.21, 1.75), ("spike", 0.05, 3.0))


def _dev_maturity(school_key: str, entry: int, seat: int, grade: int,
                  salt: str) -> float:
    """This player's maturity at `grade` under the new-era trajectory model.
    Deterministic from the same identity the pid is built from, so the whole
    four-year path is fixed at entry and each season just reads it off."""
    drng = random.Random(f"{salt}|jhsaa-dev|{school_key}|{entry}|{seat}")
    if drng.random() < DEV_READY_RATE:
        m9 = drng.uniform(*DEV_READY_ARRIVAL)
    else:
        m9 = drng.uniform(*DEV_ARRIVAL)
    m12 = max(drng.uniform(*DEV_FINISH), m9 + DEV_MIN_RISE)
    roll = drng.random()
    exp = DEV_SHAPES[-1][2]
    for _name, p, e in DEV_SHAPES:
        if roll < p:
            exp = e
            break
        roll -= p
    # Walk the curve from arrival to the requested grade, applying the per-year
    # floor along the way so a late bloomer still visibly improves every season.
    m = m9
    for g in range(10, grade + 1):
        t = (g - 9) / 3.0
        m = max(m9 + (m12 - m9) * (t ** exp), m + DEV_MIN_STEP)
    return min(DEV_CAP, m)


@dataclass
class School:
    name: str
    city: str
    county: str
    area: str
    classification: str
    group: str
    enrollment: int
    private: bool
    mascot: str
    colors: list
    district: str
    gender: str
    # ‼️ THE SETTLEMENT INSIDE THE CITY, and it is NOT a second city (owner spec,
    # 2026-08). `city` stays the metro — every district cut, geography lookup and
    # non-district pairing reads it, and none of them should change — while
    # `locality` names the CDP / unincorporated place / absorbed town the school
    # actually sits in. Empty for a CORE CITY school, which is a real distinction
    # and not a missing value. Nothing keys on it: localities repeat, both within
    # a metro (Natchez Prep and Natchez Cliff) and across two of them.
    locality: str = ""
    # ‼️ THE ROSTER IDENTITY, and it is NOT the name. A program's twelve players
    # are rebuilt on demand from (identity, entry year, seat) — nothing about a
    # roster is persisted — so whatever string seeds that RNG *is* the school as
    # far as its people are concerned. `name` is a DISPLAY string and the owner
    # renames schools (`import_jhsaa.RENAMES`), which would otherwise hand every
    # renamed program twelve strangers overnight: its juniors never become
    # seniors, and every archived pid (awards, All-State rows, /jhsaa/player
    # links) stops resolving to anybody. So generation keys on `source` — the
    # school's ORIGINAL prep-network name, stamped into `data/jhsaa/schools.json`
    # at import and never rewritten, even after prep-network itself is renamed.
    # Empty for schools that were never renamed, where the name IS the identity.
    #
    # The owner rebuilds the sim from scratch on reload, so no save currently
    # crosses a rename and nothing depends on this today. It is kept because it
    # costs one optional field and makes "a rename is a rename, not a roster
    # transplant" true by construction — the invariant is cheap here and
    # expensive to retrofit once a save DOES carry history across one.
    source: str = ""
    # ‼️ TALENT OVERRIDE (owner rule 2026-08) — the classification a roster
    # GENERATES at when the owner decrees it differs from enrollment. Empty for
    # every ordinary school (talent comes from `classification`, as always).
    # Exists for exactly the Condotti Vanguard Academy / Romero-Finniski pair:
    # enrollment-level 3A academies that compete in 7A while producing
    # 9A-caliber rosters — the owner's lore, not a size relationship any
    # existing field could express (classification drives ROSTER SIZE and, by
    # default, talent; group drives the championship; this decouples talent
    # alone). Read ONLY through `talent_group`.
    talent: str = ""

    @property
    def ident(self) -> str:
        """The stable identity string — see `source`."""
        return self.source or self.name

    @property
    def key(self) -> str:
        return f"{self.ident}|{self.gender}"

    @property
    def plays_up(self) -> bool:
        """True when the program has chosen to compete a classification above its
        enrollment class (owner rule 2027-08). Real associations let a school play
        up; here it is a durable property of strong-at-tennis programs, seeded at
        import and editable like an archetype."""
        return champ_group(self.classification) != self.group

    @property
    def talent_group(self) -> str:
        """The classification a roster is GENERATED at — the school's OWN size,
        never where it competes.

        ‼️ THESE COME APART FOR A PLAY-UP AND THE DIFFERENCE IS THE WHOLE POINT.
        `group` is the championship the program enters; `classification` is how
        many students it has, and `_TALENT` is a statement about enrollment. Key
        the bands on `group` and a 5A blue-blood that plays up to 6A is silently
        handed 6A talent — a free roster upgrade that inverts the choice, since
        playing up is meant to COST you a harder field, not buy you better
        players. A no-op for every school that is not playing up.

        The one exception is an explicit owner `talent` decree (see the field
        above) — a stated generation class that outranks enrollment for the
        named pair and nobody else."""
        return champ_group(self.talent or self.classification)


@dataclass
class TeamSeason:
    school: School
    roster: list
    wins: int = 0                       # overall, district + crossover
    losses: int = 0
    dwins: int = 0                      # DISTRICT only — what decides district place
    dlosses: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    district_place: int = 0
    # TOSS Power Index (raw, pre-display-normalisation), set once the regular season
    # is complete. It is what at-large selection and state seeding sort on, so it is
    # archived with the season rather than recomputed on read — see world.run_jhsaa.
    power: float = 0.0
    # pid -> [wins, losses] at any line. Awards are individual, so they need this.
    records: dict = field(default_factory=dict)
    by_pid: dict = field(default_factory=dict)
    # pid -> [(slot, won, phase, opp_pids, partner_pid, opp_school), ...] — the
    # match-by-match RÉSUMÉ the awards are selected from (`_credit`).
    matches: dict = field(default_factory=dict)
    # Every dual this team played, in order. Kept so a school's season can be read
    # match by match without replaying it — the college side's schedule view.
    schedule: list = field(default_factory=list)
    # The Order of Ability (pids, best first) — established before the program's
    # first postseason dual and FROZEN for the rest of the season. Empty until
    # then; the regular season runs on the live ladder. See `_postseason_nine`.
    order_of_ability: list = field(default_factory=list)
    # {pid: {sibling pids}} for THIS roster only — the doubles nudge's whole input.
    # SIBLINGS, not the household (owner rule 2026-08): it held a family_id and the
    # arrangers compared two of them, so cousins — and anyone merely reachable
    # through a third member's tie — drew the partnering bonus too.
    # ‼️ Resolved once when the team is built, never inside `_lineup`. `families()`
    # resolves an override fingerprint, which costs a SQLite connect+query: called
    # per dual that is ~5,100 queries a gender, the exact shape of the play-up
    # fingerprint storm. A dual reads this dict instead.
    sibling_ids: dict = field(default_factory=dict)

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}"

    @property
    def district_record(self) -> str:
        return f"{self.dwins}-{self.dlosses}"

    @property
    def win_pct(self) -> float:
        n = self.wins + self.losses
        return self.wins / n if n else 0.0

    @property
    def district_pct(self) -> float:
        n = self.dwins + self.dlosses
        return self.dwins / n if n else 0.0


@dataclass
class JVTeam:
    """A program's JV season — its own W-L-T, points and schedule, hanging off the
    varsity `TeamSeason` it shares a roster and a LADDER with.

    ‼️ A SEPARATE OBJECT, NOT A SECOND TeamSeason. It has to be separate so a JV dual
    can never touch `wins` / `points_for` / `records` / `matches` — JV counts for
    nothing (no TOSS, no rankings, no awards, no seeding, no postseason), and the
    cheapest way to guarantee that is for the varsity counters to be unreachable from
    here rather than for every writer to remember to skip them.

    ‼️ AND IT DELIBERATELY HAS NO `records` / `matches` OF ITS OWN. Those two feed the
    awards (`jhsaa_awards.build_pool` reads `matches`) and the ladder (`ladder_score`
    reads `records`), so a JV appearance must not reach either. It also means no
    per-player JV data exists to archive, which is exactly what the archive rule
    settled on independently — see `world_jhsaa_dual.level` and the `lines=[]` note in
    `world.run_jhsaa`."""
    team: TeamSeason
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    schedule: list = field(default_factory=list)

    @property
    def school(self) -> School:
        return self.team.school

    @property
    def record(self) -> str:
        """‼️ W-L-T, and the T is not decorative. Three of the eight `JV_FORMATS` have
        an EVEN court count, so ~27-31% of JV duals can be drawn — 2S/2D alone is about
        a fifth of the slate. A `W-L` string would silently lose them."""
        return (f"{self.wins}-{self.losses}-{self.ties}" if self.ties
                else f"{self.wins}-{self.losses}")

    @property
    def win_pct(self) -> float:
        """Ties count a half, the ordinary sporting convention. The denominator is
        every dual played, NOT `wins + losses` — that is the shape every other win%
        in this module has, and it is wrong the moment a draw exists."""
        n = self.wins + self.losses + self.ties
        return (self.wins + 0.5 * self.ties) / n if n else 0.0


def jv_pool(ts: TeamSeason) -> list:
    """The players below the varsity eleven on the ladder — the JV, in order.

    ‼️ Read off `_order`, which is the ONE ladder (owner rule 2026-08): there is no
    standing JV squad to keep in step with anything. A varsity player who lost through
    the season has already fallen past a JV player's seed, and they swap — that is the
    porousness, and it costs nothing to have.

    ‼️ BUT IT IS NOT TEMPORAL, AND THE DOCS USED TO SAY IT WAS. `run_season` plays the
    whole varsity regular season and only THEN the whole JV season, so `ts.records` is
    complete before the first JV dual and `play_jv_dual` credits nothing back — every
    JV dual of the year therefore resolves this to the SAME ordering. The swap happens
    once, ahead of the JV season, not date by date within it: a JV dual dated 12 April
    is staffed off the ladder as it finished in June.

    Measured before anyone re-derives it: reading the ladder 10% into the season
    instead of at the end changes **4.1% of the JV pool** (13 of 408 players over 42
    programs), and a player's median rank change across a whole season is **0 places**
    (mean 0.5, max 4). That is small because `ladder_score` is deliberately sticky —
    ±`LADDER_SWING` (7) OVR, damped by evidence — so *when* the ladder is read barely
    matters. ‼️ The error scales with `LADDER_SWING`: make the ladder more
    results-sensitive and this shortcut starts to bite, at which point the fix is to
    interleave `play_jv_season` with `play_regular_season`'s blocks.

    Deliberately takes the plain top-eleven cut and NOT `_lineup`'s: resting (which
    sits 1-2 starters out entirely) and bench rotation are per-DUAL decisions about a
    varsity match, and "available that day" for JV is the per-program constant (owner
    rule 2026-08). Threading a varsity dual's rest into a JV dual's size would couple
    two schedules that are explicitly independent."""
    return _order(ts)[lineup_need("regular"):]


def jv_spare(ts: TeamSeason) -> int:
    """How many players a program has for JV — the size input to `jv_format`."""
    return len(jv_pool(ts))


def jv_strength(ts: TeamSeason) -> float:
    """The JV pool's mean current overall — what JV opponents are MATCHED on.

    ‼️ RATE THE POOL, NOT THE PROGRAM (owner rule 2026-08). Varsity pairs on
    `_strength`, the top-nine mean, and reusing it here would rate a JV team by players
    who are not on it. The two orderings do correlate (Spearman 0.875 over the real
    2038 save, with no quartile inversions), so this is a precision gain rather than a
    reversal — but the median program still sits ~80 places apart in the two rankings
    of ~860, and p90 is ~205, so the wrong metric mismatches by a quarter of the field
    in the middle of the table where most duals are."""
    pool = jv_pool(ts)
    if not pool:
        return 0.0
    return sum(p.current_overall() for p in pool) / len(pool)


_schools_cache: dict | None = None
_playup_cache: dict = {}
_transfer_cache: dict = {}
_family_cache: dict = {}
# The BUILT School objects, keyed (gender, play-up version). `_schools_cache` above is
# only the raw JSON; rebuilding the objects is what used to be free and is not any
# more — see `load_schools`. Read-only: callers filter and group it, nobody mutates a
# School, and handing out the same list is the entire point.
_schoolobj_cache: dict = {}
_upstart_cache: dict = {}
# {version: {school: league}} for every played-up program's shared league — see
# `_playup_league`. Keyed on the play-up fingerprint ALONE (never per gender): the
# whole point is that both genders read the identical dict.
_playup_league_cache: dict = {}


# ‼️ A RENAME MUST NOT COST A SCHOOL ITS HISTORY (owner rule 2026-08). The archive
# keys on the DISPLAY NAME at the moment a season was written, so renaming a program
# orphans every row it has already earned — its page finds nothing under the new name,
# and the old name is no longer a school, so that page 404s too. A 2031 state champion
# vanished from its own program page exactly that way. **Nothing was lost but the
# link**, and this is the link.
#
# Generated from the git history of RENAMES by `scripts/jhsaa_former_names.py` — it
# cannot be typed, because renaming a school twice REWRITES the target in place (the
# rule: never chain), so intermediate names survive only in git.
_FORMER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "jhsaa", "former_names.json")
_former_cache: dict | None = None


def former_names() -> dict[str, str]:
    """Old display name -> the name that school goes by now."""
    global _former_cache
    if _former_cache is None:
        try:
            with open(_FORMER, encoding="utf-8") as fh:
                built = json.load(fh)["former_names"]
        except (FileNotFoundError, ValueError, KeyError):
            built = {}
        _former_cache = built          # publish a local (the gthread rule)
    return _former_cache


def current_name(name: str, gender: str = "girls") -> str:
    """‼️ A LIVE NAME ALWAYS WINS. An alias must never outrank a school that exists —
    `Ashbury` is both a name some school used to have AND, today, nobody's; but the
    general case (a retired name reissued to another program) is exactly how a lookup
    would silently serve the wrong school's record."""
    if any(s.name == name for s in load_schools(gender)):
        return name
    return former_names().get(name, name)


def known_names(name: str, gender: str = "girls") -> list[str]:
    """Every name this program's archived rows could be filed under — current first."""
    now = current_name(name, gender)
    return [now] + sorted(o for o, n in former_names().items() if n == now and o != now)


def reset_schools() -> None:
    """Drop the school and play-up caches. Needed when a play-up override changes,
    because `load_schools` bakes the championship group and the league INTO the
    School objects it builds — an archetype only changes ability, so `reset_all()`
    alone is enough for that, and was not for this."""
    global _schools_cache
    _schools_cache = None
    _playup_cache.clear()
    _schoolobj_cache.clear()
    _upstart_cache.clear()
    _playup_league_cache.clear()
    _name_era_cache.clear()
    _dev_era_cache.clear()
    global _former_cache
    _former_cache = None


# --- name-generation era (owner rule 2026-08, mid-save cutover) ----------------------
#
# The broadened, frequency-weighted name draw (see `_gen_seat`) must NOT rename
# players who already exist: JHSAA players are regenerated deterministically from
# (school, entry, seat), so changing the draw retroactively renames every archived
# season's rosters — awards, brackets and school pages would all point at strangers.
# The cutover is therefore keyed on ENTRY YEAR: cohorts entering from `name_era()`
# on draw with the new mix, everyone earlier keeps their exact old name.
#
# The era self-configures ONCE per save and persists (`worldconfig`): on first read
# it becomes (latest archived JHSAA season year + 1) — so every cohort a live save
# has already seen keeps its names and only future freshmen classes broaden — or 0
# on a fresh save with no archive, where everything is new anyway.
#
# ‼️ Memoised keyed on the DB path and cleared in `reset_schools()` — NEVER resolve
# this per seat (the play-up fingerprint query storm, CLAUDE.md caches §5).
_name_era_cache: dict = {}

#: New-era mix: overwhelmingly US, a real Canadian slice, and a thin international
#: remainder ("IRL there are exchange students who play HS for a year"). ~90/5/5.
NAME_V2_US = 0.90
NAME_V2_CANADA = 0.05

_intl_weights_cache: dict | None = None


def _intl_weights() -> dict:
    """The exchange-student mix: the owner's tennis_global preset minus the two
    shares that draw separately. Static data — computed once, published whole."""
    global _intl_weights_cache
    w = _intl_weights_cache
    if w is None:
        from generators import region_preset
        w = {k: v for k, v in region_preset("tennis_global").items()
             if k not in ("us", "canada")}
        _intl_weights_cache = w
    return w


def name_era() -> int:
    """The first entry year that draws new-era names for this save (see above)."""
    from .dbpath import resolve_db_path
    key = resolve_db_path()
    got = _name_era_cache.get(key)
    if got is not None:
        return got
    from . import worldconfig
    raw = worldconfig.get("jhsaa_name_era")
    if raw is not None and str(raw).strip():
        era = int(raw)
    else:
        import sqlite3
        era = 0
        try:
            conn = sqlite3.connect(key)
            try:
                r = conn.execute("SELECT MAX(year) FROM world_jhsaa").fetchone()
            finally:
                conn.close()
            if r and r[0] is not None:
                # ‼️ `world_jhsaa.year` is the ZERO-BASED WORLD INDEX (the DB
                # key), while `entry` in `_gen_seat` is a CALENDAR year — the
                # same conversion `world.jhsaa_season_year` makes. Stored raw,
                # the era would be e.g. 5 and every existing cohort would
                # satisfy `entry >= era` — the archive-wide rename this gate
                # exists to prevent. Season year of the newest archive is
                # BASE_YEAR + index + 1; the first NEW cohort is one later.
                from .world import BASE_YEAR
                era = BASE_YEAR + int(r[0]) + 2
        except sqlite3.Error:
            era = 0                      # no archive yet — a fresh save, all new
        worldconfig.set("jhsaa_name_era", str(era))
    _name_era_cache[key] = era
    return era


# --- development era (owner rule 2026-08) — the name_era idiom, for the growth model
#
# The per-player development-curve model (see `_dev_maturity` above) must not re-rate
# cohorts that already exist: like names, current ability is regenerated from seed, so
# an ungated change rewrites every archived roster's ladder. Same self-configuration:
# first read on a save with an archive sets the era to the first UNSEEN cohort, a
# fresh save gets 0 (everything new). Memoised on the DB path, cleared by
# `reset_schools()` — never resolved per seat.
_dev_era_cache: dict = {}


def dev_era() -> int:
    """The first entry year that develops on the per-player curve model."""
    from .dbpath import resolve_db_path
    key = resolve_db_path()
    got = _dev_era_cache.get(key)
    if got is not None:
        return got
    from . import worldconfig
    raw = worldconfig.get("jhsaa_dev_era")
    if raw is not None and str(raw).strip():
        era = int(raw)
    else:
        import sqlite3
        era = 0
        try:
            conn = sqlite3.connect(key)
            try:
                r = conn.execute("SELECT MAX(year) FROM world_jhsaa").fetchone()
            finally:
                conn.close()
            if r and r[0] is not None:
                # Same conversion as name_era(): world_jhsaa.year is the
                # ZERO-BASED WORLD INDEX; entry years are calendar years. The
                # newest archive's season year is BASE_YEAR + index + 1, its
                # freshmen entered THAT year, so the first new cohort is +2.
                from .world import BASE_YEAR
                era = BASE_YEAR + int(r[0]) + 2
        except sqlite3.Error:
            era = 0                      # no archive yet — a fresh save, all new
        worldconfig.set("jhsaa_dev_era", str(era))
    _dev_era_cache[key] = era
    return era


#: Playing up is a SMALL-SCHOOL mechanism (owner correction 2027-08): eligible at this
#: championship group and below. Mirrors `scripts/import_jhsaa.PLAY_UP_MAX_GROUP`, which
#: seeds the file — but the rule has to live HERE too, because the seed list is not the
#: only way a program can be promoted. The editor is, and until this constant existed at
#: runtime nothing checked it: `/editor/jhsaa-playup` would happily move an 8A program
#: into 9A, which is not playing up, it is a big school in a slightly bigger class.
#: 9A's exclusion falls out of the same rule (it has nothing above it).
PLAY_UP_MAX_GROUP = "4A"


def can_play_up(classification: str) -> bool:
    """Whether a program of this size is allowed to play up at all.

    ‼️ SCOPED TO THE 1A-9A LADDER (2046 expansion). The Great Basin's Division
    1/Division 2 are a geographic PAIR appended after 1A in `GROUPS`, not rungs
    on the size ladder — a naive `GROUPS.index` test read them as "below 4A" and
    would have promoted a 2,500-enrollment Division 1 program "up" into 1A.
    Play-up does not exist in the Division system at all."""
    g = champ_group(classification)
    if g not in LADDER_GROUPS:
        return False
    return LADDER_GROUPS.index(g) >= LADDER_GROUPS.index(PLAY_UP_MAX_GROUP)


def play_up_group(classification: str) -> str:
    """The classification one step ABOVE `classification`'s championship group, or
    the group itself at the top of the ladder — 9A has nothing to play up to. This
    is the SEED-LIST default (a school with `play_up: true` and no editor override
    moves exactly one class) — an explicit override can name any class further up;
    see `plays_up`."""
    g = champ_group(classification)
    if g not in LADDER_GROUPS:      # Division 1/2: no ladder above or below them
        return g
    i = LADDER_GROUPS.index(g)
    return LADDER_GROUPS[i - 1] if i else g


def valid_playup_target(classification: str, target: str) -> bool:
    """Whether `target` is a legal play-up destination for a program of this
    `classification`: the program must be eligible to play up at all
    (`can_play_up` — 4A and below), and `target` must be a real group STRICTLY
    above the program's own championship group (never sideways, never down —
    owner rule: play-up is never play-down)."""
    if not can_play_up(classification) or target not in LADDER_GROUPS:
        return False
    return (LADDER_GROUPS.index(target)
            < LADDER_GROUPS.index(champ_group(classification)))


def plays_up(school_name: str, seeded: bool, pmap: dict | None = None,
             classification: str | None = None) -> str | None:
    """The group `school_name` actually competes in if it's playing up, or None if
    it isn't — the seed list in `schools.json` with the editor table on top
    (`overrides.set_jhsaa_playup`), exactly the layering `archetype()` uses.

    ‼️ AN OVERRIDE NAMES A REAL TARGET GROUP, NOT JUST "yes"/"no" (owner rule
    2027-08, multi-step play-up). Real associations approve play-up/play-down
    applications annually and for all kinds of reasons — a program is not
    limited to exactly one class up. The stored value is either a group string
    ("7A") or "no" (an explicit hold, reverting a seeded play-up to its own
    class); anything else falls back to the seed list's one-step default via
    `seeded`. A stored group is re-validated on every read (`valid_playup_target`)
    so a program that shrinks below `PLAY_UP_MAX_GROUP`, or a stale/crafted row
    naming an illegal target, can never promote — the rule belongs on the read,
    not only where a promotion is written.

    ‼️ PASS `pmap` WHEN ASKING ABOUT MORE THAN ONE SCHOOL. Without it this resolves
    the override table's fingerprint itself, and that fingerprint costs a SQLite
    connect + query + close EVERY CALL — the `_playup_cache` memoises the map but is
    keyed on the very thing that is expensive to compute, so the cache never saved the
    cost. In a loop over the association that is one database round trip per school
    per pass. See `load_schools`."""
    from app import overrides as ov
    if classification is not None and not can_play_up(classification):
        return None
    m = _playup_map(ov.jhsaa_playup_version()) if pmap is None else pmap
    hit = m.get(school_name)
    if hit is None:
        return play_up_group(classification) if (seeded and classification is not None) else None
    if hit == "no":
        return None
    # A stored explicit target — validate it every read; classification is
    # required to validate, so no classification means "trust nothing".
    if classification is None or not valid_playup_target(classification, hit):
        return None
    return hit


def _playup_map(version: str) -> dict:
    """{school: "yes"|"no"}, memoised on the override table's fingerprint. Computed
    into a LOCAL and published (the gthread rule); never read back out of the dict
    it wrote."""
    hit = _playup_cache.get(version)
    if hit is not None:
        return hit
    from app import overrides as ov
    fresh = ov.get_jhsaa_playups()
    _playup_cache.clear()
    _playup_cache[version] = fresh
    return fresh


# --- Offseason transfers (owner rule 2027-08) --------------------------------
# Manual, always-approved, no eligibility logic — a module to MOVE a player, not to
# find one. `overrides.set_jhsaa_transfer` is the write path (editor); everything
# here is the read side `build_roster` consults.

def _transfer_map(version: str) -> dict:
    """{pid: {from, gender, entry, seat, to, year}}, memoised on the override
    table's fingerprint — same shape as `_playup_map`."""
    hit = _transfer_cache.get(version)
    if hit is not None:
        return hit
    from app import overrides as ov
    fresh = ov.get_jhsaa_transfers()
    _transfer_cache.clear()
    _transfer_cache[version] = fresh
    return fresh


def transfers() -> dict:
    """{pid: record} for every transferred player — the version fingerprint is
    resolved here, ONCE, never inside a per-school or per-seat loop."""
    from app import overrides as ov
    return _transfer_map(ov.jhsaa_transfer_version())


#: A roster never carries more seats than this per class — plenty of headroom over
#: the biggest classification's `ROSTER_SIZE_BY_CLASS` (24).
_MAX_SEAT = 40


def resolve_seat(school: School, entry: int, pid: str) -> int | None:
    """The seat number behind a player's pid — pid is `make_pid("jhsaa", ident,
    gender, entry, seat)`, a one-way hash, so the seat isn't recoverable from the
    pid alone. It IS recoverable by brute force over the small seat range, which is
    what the transfer editor needs (it only has a school, an entry year and a pid;
    nothing stores seat numbers)."""
    for seat in range(_MAX_SEAT):
        if make_pid("jhsaa", school.ident, school.gender, entry, seat) == pid:
            return seat
    return None


def transfer_for(pid: str) -> dict | None:
    """This player's transfer record, or None if they haven't moved."""
    return transfers().get(pid)


def transfer_moves(rec: dict | None) -> list[dict]:
    """A record's moves as `[{to, year}, …]`, oldest first.

    ‼️ A CAREER CAN HOLD MORE THAN ONE MOVE (owner rule 2026-08). It used to hold
    exactly one — `{to, year}` on the record — so a player who moved a second time
    had to have the first move CANCELLED, which did not just forget it: the card
    derives which school each season belonged to from this record, so the seasons
    actually played at the second school were re-attributed to the origin and their
    results silently went 0-0 (the archived duals still named the right school, so
    the two surfaces disagreed with nothing erroring). The college side has always
    written a history row per player per season; this is the same idea in the shape
    high school needs — moves only ever happen between seasons.

    Records written before `moves` existed carry the single `to`/`year` pair and are
    read back as a one-move history. Derived on READ, never migrated — the section's
    own idiom, and the next shape change needs no migration either."""
    if not rec:
        return []
    moves = rec.get("moves")
    if moves is None:
        return ([{"to": rec.get("to"), "year": rec.get("year")}]
                if rec.get("to") else [])
    return sorted((dict(m) for m in moves if m.get("to")),
                  key=lambda m: (m.get("year") or 0))


def transfer_school(rec: dict | None, season_year: int) -> str:
    """Which school this record says the player attends in `season_year` — the LAST
    move effective by then, or their origin if none is.

    ‼️ ONE AUTHORITY FOR "WHERE ARE THEY". `build_roster` (both the outbound skip and
    the inbound pull) and the career card all ask this, so a move back to the origin
    school resolves the same way everywhere. Asking it in three places with three
    inline comparisons is what let the card and the roster disagree."""
    if not rec:
        return ""
    where = rec.get("from", "")
    for m in transfer_moves(rec):
        if (m.get("year") or 0) <= season_year:
            where = m["to"]
    return where


def transfer_rows() -> list[dict]:
    """Every recorded transfer, with the mover's NAME resolved for display — the
    list the `/jhsaa/transfers` board reads. Player identity is regenerated (same
    rng draws as `build_roster`) rather than stored, same as everywhere else in
    JHSAA; the record itself carries no name."""
    rows = []
    for pid, rec in transfers().items():
        gender = rec.get("gender", "")
        origin = next((s for s in load_schools(gender) if s.name == rec.get("from")), None)
        name = ""
        if origin is not None:
            entry = rec.get("entry")
            # `grade` only steers maturity/talent in `_gen_seat`, not identity or pid
            # (both keyed on entry+seat alone) — 9 is an arbitrary valid choice here,
            # this call exists only to read the name back off the regenerated Prospect.
            mod = _program_mod(origin, 0, "")
            p = _gen_seat(origin, mod, entry, rec.get("seat"), 9, "")
            if p.pid == pid:
                name = p.name
        # ‼️ ONE ROW PER MOVE, not per player: the ledger is the record of what
        # happened, and a career with three schools happened three times. Each row's
        # `from` is where they were BEFORE that move (the previous destination, or
        # the origin for the first), which is the only reading that makes a
        # multi-move career legible — and the only one where a move back to the old
        # school does not read as a move from itself.
        moves = transfer_moves(rec)
        where = rec.get("from")
        for i, m in enumerate(moves):
            rows.append({"pid": pid, "name": name or "(unresolved)", "gender": gender,
                         "from": where, "to": m.get("to"), "year": m.get("year"),
                         "entry": rec.get("entry"), "origin": rec.get("from"),
                         "step": i + 1, "steps": len(moves)})
            where = m.get("to")
    rows.sort(key=lambda r: (-(r["year"] or 0), r["name"]))
    return rows


# --- batch transfers (owner tool, 2026-08) ------------------------------------
# The owner is this league's only market maker: every offseason ~40-50 buried
# players are redistributed by hand, one player card at a time. The batch path
# accepts the artifact that analysis already produces — (pid, destination) pairs
# — validates every row, and writes the same `set_jhsaa_transfer` rows the player
# card does, so nothing downstream changes. Rows are DECLARATIVE (applied on read
# by `build_roster` from the effective year on), so "apply" is just writing them.

_pid_idx_cache: dict = {}


def roster_pid_index(gender: str, year: int, salt: str = "") -> dict:
    """pid -> (school name, entry year, grade, player name) for everyone enrolled
    in season `year`, over the whole gender — the lookup a bare (pid, destination)
    pair needs. A full-association roster build (~7s cold), so it is memoised;
    the transfer fingerprint is resolved ONCE here, never per row."""
    from app import overrides as ov
    from .dbpath import resolve_db_path
    key = (resolve_db_path(), gender, year, salt, ov.jhsaa_transfer_version())
    got = _pid_idx_cache.get(key)
    if got is not None:
        return got
    idx = {}
    for school in load_schools(gender):
        for p in build_roster(school, year, salt):
            idx[p.pid] = (school.name, p.entry_year, p.grade, p.name)
    # Prune THIS (db, gender)'s stale entries only — a global clear() would evict
    # the sibling gender between the two builds one batch call makes, so every
    # preview→apply round would pay all four builds again.
    for k in [k for k in _pid_idx_cache if k[:2] == key[:2]]:
        _pid_idx_cache.pop(k, None)
    _pid_idx_cache[key] = idx
    return idx


def transfer_batch(pairs: list[tuple[str, str]], year: int, salt: str = "",
                   apply: bool = False) -> list[dict]:
    """Validate (and with `apply`, write) a batch of transfers, effective season
    `year`. `pairs` is [(pid, destination school)], both genders welcome — the
    pid says which gender it is. Returns one report row per pair, in order:
    {pid, name, gender, from, to, year, ok, msg}. Invalid rows never block valid
    ones and are never silently dropped — the report is the contract.

    A row is rejected when: the pid is on no roster for season `year` (wrong pid,
    or the player graduates before then), the destination is not a sponsoring
    program of that gender, or the destination is where they already play. A pid
    that already has a transfer record keeps its stored origin/seat (the pid is
    generated from the ORIGIN school, so a re-transfer must not re-resolve the
    seat against the school they merely play for now)."""
    from app import overrides as ov
    idx = {g: roster_pid_index(g, year, salt) for g in ("girls", "boys")}
    schools = {g: {s.name: s for s in load_schools(g)} for g in ("girls", "boys")}
    existing = transfers()
    out = []
    for pid, to_school in pairs:
        pid, to_school = (pid or "").strip(), (to_school or "").strip()
        gender = next((g for g in ("girls", "boys") if pid in idx[g]), None)
        row = {"pid": pid, "name": "", "gender": gender or "", "from": "",
               "to": to_school, "year": year, "ok": False, "msg": ""}
        out.append(row)
        if gender is None:
            row["msg"] = f"no player with this pid is enrolled anywhere in {year}"
            continue
        school_name, entry, grade, name = idx[gender][pid]
        row["name"], row["from"] = name, school_name
        rec = existing.get(pid)
        if rec:
            origin_name, entry, seat = rec.get("from"), rec.get("entry"), rec.get("seat")
        else:
            origin = schools[gender][school_name]
            origin_name, seat = school_name, resolve_seat(origin, entry, pid)
        if not to_school:
            row["msg"] = "no destination given"
        elif to_school == school_name:
            row["msg"] = f"{to_school} is already their school"
        elif to_school not in schools[gender]:
            row["msg"] = f'no {gender} program named "{to_school}"'
        elif seat is None:
            row["msg"] = "could not resolve this player's roster seat"
        else:
            row["ok"] = True
            row["msg"] = f"grade {grade} in {year}; moves {origin_name} → {to_school}"
            if apply:
                ov.set_jhsaa_transfer(pid, origin_name, gender, entry, seat,
                                      to_school, year)
    return out


#: The archetypes an owner can ASSIGN. `upstart` is deliberately absent: it is a
#: temporary run the world rolls from the salt and expires by itself, and storing one
#: would make it permanent — the one thing an upstart must never be.
EDITABLE_ARCHETYPES = ("blue_blood", "development", "doubles", "neglect")


def archetype_board() -> dict:
    """The archetype EDITOR's view — the programs that HAVE an archetype, nothing else.

    Same shape and same rule as `playup_board`: a list of the tagged programs, never the
    association to scroll. ~91 programs carry a tag, so it is longer than the play-up
    board and is grouped by kind for that reason."""
    from app import overrides as ov
    amap = _arch_map(ov.jhsaa_archetype_version())
    seed = _arch_seed()
    cls = {r["name"]: r["classification"] for r in _rows()}
    rows = [{"name": n, "kind": k, "classification": cls.get(n, ""),
             # As on the play-up board: REMOVING a seeded program is a demotion
             # ("none"), removing an added one is a clear. One button, two meanings.
             "seeded": n in seed}
            for n, k in amap.items()]
    by_kind = {k: sorted((r for r in rows if r["kind"] == k),
                         key=lambda r: r["name"]) for k in EDITABLE_ARCHETYPES}
    demoted = sorted(n for n, k in ov.get_jhsaa_archetypes().items() if k == "none")
    return {"by_kind": by_kind, "kinds": EDITABLE_ARCHETYPES, "total": len(rows),
            "demoted": demoted, "names": sorted(cls)}


#: District-name suffixes, longest first so "Interscholastic League" is matched before
#: "League". The identity bank deliberately varies these (League · Interscholastic
#: League · Athletic Association · Assembly · Province · Organization · District), which
#: is what makes the names read like real leagues and also what makes them long.
_DISTRICT_SUFFIXES = ("Interscholastic League", "Athletic Association",
                      "Athletic Organization", "Athletic Assembly",
                      "League", "Assembly", "Province", "Organization", "District")


def district_short(name: str) -> str:
    """A district name with its institutional suffix dropped — "Black Canyon League"
    -> "Black Canyon", "Millworks Athletic Association" -> "Millworks".

    ‼️ FOR DENSE TABLES AND MENUS ONLY, never for the archive, a link target or a
    heading. A district is `(classification, name)` and THE NAME IS THE FULL ONE; this
    is a label. Always render it beside the full name (a `title`, the row it sits on).

    Initials were the obvious answer and are wrong here: district names are only
    guaranteed distinct by their LEADING word within a classification (`import_jhsaa`
    rejects a candidate sharing one), so "Marble Valley League" and "Millworks Athletic
    Association" both come out "MVL"/"MAA"-ish and collide the moment two names share
    a shape. Dropping the suffix keeps exactly the part the association guarantees is
    distinct."""
    out = (name or "").strip()
    for suf in _DISTRICT_SUFFIXES:
        if out.endswith(" " + suf):
            return out[: -(len(suf) + 1)].strip()
    return out


def program_editor(selected: str = "", board: str = "", cat: str = "",
                   show_all: bool = False, recent: list | None = None) -> dict:
    """The JHSAA program editor — a DIRECTORY, not a dataset.

    ‼️ NARROW BEFORE YOU SHOW (owner rule 2026-08). The first version listed all ~91
    archetyped programs and all ~13 play-ups as editable rows — 195 of them. Sorting or
    searching that table does not fix it: the problem is not organisation, it is
    EXPOSURE. Even a perfect table makes somebody confront a whole dataset to change one
    school.

    So the page is: pick a board, pick a type, pick the program — then only that program.
    A search box for anyone who already knows the name, recently-viewed for anyone
    coming back, and the full table kept as an escape hatch for the rare reader who
    genuinely wants the reference view. Find what I need, see only that, optionally
    browse everything."""
    from app import overrides as ov
    rows = _rows()
    version = ov.jhsaa_playup_version()
    pmap = _playup_map(version)
    # The league a played-up program actually competes in — LIVE, via the same
    # cached mapping `load_schools` uses, never the raw stored field. The stored
    # `girls_district`/`boys_district` names the program's OLD class's league;
    # reading it here is what made this card disagree with the district page for
    # every played-up program on the board.
    moved = _playup_league(version, rows, pmap)
    amap = _arch_map(ov.jhsaa_archetype_version())
    arch_ov, play_ov = ov.get_jhsaa_archetypes(), ov.get_jhsaa_playups()
    by_name = {r["name"]: r for r in rows}

    def card(name):
        r = by_name.get(name)
        if not r:
            return None
        target = plays_up(name, bool(r.get("play_up")), pmap, r["classification"])
        cls = r["classification"]
        # Every group strictly above the program's own class — the picker's real
        # menu (owner rule 2027-09, multi-step play-up), not just a one-step toggle.
        # Ladder only: Division 1/2 are not "above" anything (can_play_up is
        # False there, and the slice must never hand a Division as a target).
        targets = ([g for g in LADDER_GROUPS[:LADDER_GROUPS.index(champ_group(cls))]]
                  if can_play_up(cls) else [])
        district = moved.get(name) if target else _row_league(r)
        return {"name": name, "classification": cls, "city": r["city"],
                "district": district or "",
                "archetype": amap.get(name, ""),
                # `plays_up` truthy = the string of the group they're IN; None = not.
                "plays_up": bool(target),
                "can_play_up": can_play_up(cls),
                # The group actually competed in — an explicit override target if
                # one is set, else the seed-list one-step default.
                "competes": target or play_up_group(cls),
                "targets": targets,
                "arch_edited": name in arch_ov, "play_edited": name in play_ov}

    up = {r["name"] for r in rows
          if plays_up(r["name"], bool(r.get("play_up")), pmap, r["classification"])}
    held = {n for n, v in pmap.items() if v == "no"}

    BOARDS = [("archetype", "Archetypes"), ("playup", "Play-up")]
    if board == "playup":
        cats = [("up", "Playing up", len(up)), ("held", "Held in own class", len(held))]
        members = {"up": sorted(up), "held": sorted(held)}
    else:
        board = "archetype"
        cats = [(k, k.replace("_", " ").title(),
                 sum(1 for v in amap.values() if v == k)) for k in EDITABLE_ARCHETYPES]
        members = {k: sorted(n for n, v in amap.items() if v == k)
                   for k in EDITABLE_ARCHETYPES}
    programs = members.get(cat, [])

    counts = {k: sum(1 for v in amap.values() if v == k) for k in EDITABLE_ARCHETYPES}
    counts["play_up"] = len(up)
    everything = None
    if show_all:
        everything = [c for c in (card(n) for n in sorted(set(amap) | up | held)) if c]
    return {"selected": card(selected) if selected else None,
            "board": board, "boards": BOARDS, "cat": cat, "cats": cats,
            "programs": programs,
            "edited": [c for c in (card(n) for n in sorted({*arch_ov, *play_ov})) if c],
            "recent": [c for c in (card(n) for n in (recent or [])) if c],
            "counts": counts, "kinds": EDITABLE_ARCHETYPES,
            "names": sorted(by_name), "all": everything}


def playup_rows() -> list[dict]:
    """Every JHSAA school as {name, classification} — the raw rows, for a caller that
    has to VALIDATE a submitted name rather than offer one."""
    return [{"name": r["name"], "classification": r["classification"]}
            for r in _rows()]


def playup_board() -> dict:
    """The play-up EDITOR's view — the handful of programs that play up, nothing else.

    ‼️ THIS IS A SHORT LIST BY CONSTRUCTION and that is the whole point (owner, 2026-08:
    "I don't want a list with 100s of schools I have to scroll"). It returns the ~13
    programs currently playing up, the ones the file seeds that the owner has held back
    so a removal can be undone, and the bare NAMES for the add control's type-ahead —
    never the association as a browsable list.

    Play-up is a property of the SCHOOL, not of a gender's team, so this reads the raw
    rows rather than `load_schools`: both genders of one program always move together."""
    from app import overrides as ov
    pmap = _playup_map(ov.jhsaa_playup_version())
    up, names = [], []
    for r in _rows():
        # ‼️ The picker offers only ELIGIBLE schools. Listing the whole association
        # invited a 5A-9A program to be submitted with play_up=yes, which the route
        # then stored — the small-school rule lived in the import script and nothing
        # at runtime checked it.
        if can_play_up(r["classification"]):
            names.append(r["name"])
        seeded = bool(r.get("play_up"))
        target = plays_up(r["name"], seeded, pmap, r["classification"])
        if target:
            up.append({"name": r["name"], "classification": r["classification"],
                       "competes": target,
                       # Where this program's play-up comes from, because REMOVING it
                       # means two different things: a seeded one is HELD ("no"), an
                       # added one is CLEARED. A single "remove" could express only one.
                       "seeded": seeded})
    # Seeded programs the owner has turned off — shown so a removal is reversible
    # rather than a thing that silently vanishes off the board.
    held = sorted(n for n, v in pmap.items() if v == "no")
    return {"schools": sorted(up, key=lambda x: x["name"]),
            "held": held, "names": sorted(names)}


def load_schools(gender: str) -> list[School]:
    """Every JHSAA program for `gender`, with its district.

    ‼️ MEMOISED, AND THE PLAY-UP MAP IS RESOLVED ONCE. This was a pure JSON-to-objects
    loop with no database access at all until play-up landed, which is why nothing was
    cached and why nobody noticed when it stopped being free: `_plays_up_row` went into
    the per-row loop, and each call resolved the override table's FINGERPRINT with its
    own SQLite connect + query + close. One call to this function did ~20,000 database
    round trips — the row loop, plus `_playup_league` walking the rows twice more.

    `build_roster` then calls `upstarts()`, which called this twice per program, so a
    single program's roster cost 39,776 queries and 6.2 seconds, and the JHSAA rung —
    ~1,630 programs — would never finish. Measured, not estimated.

    So: the fingerprint is resolved ONCE here, the map is threaded down, and the built
    objects are cached per (gender, version). Anything that walks the association must
    hold the map, never re-ask per school."""
    from app import overrides as ov
    version = ov.jhsaa_playup_version()
    ck = (gender, version)
    hit = _schoolobj_cache.get(ck)
    if hit is not None:
        return hit
    rows = _rows()
    pmap = _playup_map(version)
    # `rows`, not the module global: `_rows()` is the one accessor that guarantees
    # the file is loaded, and reading the global directly here passed None into the
    # league map on any path that had just cleared it.
    moved = _playup_league(version, rows, pmap)
    out = []
    for r in rows:
        if not r.get(gender):
            continue
        # ‼️ PLAYING UP MOVES `group` AND LEAVES `classification` ALONE. `group` is
        # the championship the program enters — leagues, the ladder, State and
        # All-State all key off it — while `classification` stays what the school
        # actually is, which is what `School.talent_group` generates from. A school
        # that plays up gets a HARDER FIELD, never better players.
        group = r["group"]
        target = _plays_up_row(r, pmap)
        if target:
            group = target
        out.append(School(
            name=r["name"], city=r["city"], county=r["county"], area=r["area"],
            classification=r["classification"], group=group,
            enrollment=r["enrollment"], private=r["private"], mascot=r["mascot"],
            colors=r["colors"], talent=r.get("talent", ""),
            # ‼️ THE LEAGUE MOVES WITH THE PROGRAM. A district is (classification,
            # name), so a school competing in 6A while carrying its 5A league name
            # lands in a 6A district that holds nobody else — a one-team league,
            # which in a double round robin is a team with no league season at all.
            district=moved.get(r["name"], r[f"{gender}_district"]),
            gender=gender, source=r.get("source", ""),
            locality=r.get("locality", ""),
        ))
    # Compute into a local, publish, return the LOCAL (the gthread rule): a sibling
    # thread can clear this between the store and the return.
    _schoolobj_cache.clear()          # one version is live at a time
    _schoolobj_cache[ck] = out
    return out


def former_school(name: str, gender: str) -> School | None:
    """A program that no longer sponsors this sport, built from its data row anyway.

    ‼️ A PROGRAM THAT STOPS SPONSORING MUST NOT LOSE ITS HISTORY (owner rule
    2026-08). `load_schools` filters on the sponsorship flag, which is right for
    every CURRENT-season surface — the directory, the leagues, the ladder — and it
    also meant the program page and every player page 404'd the moment the flag went
    off. The archive was untouched (their state title still stood on the title board
    and on the champions grid), so the trophies stayed and the pages that explain
    them died, with every link into them dead. That is the same fault a rename used
    to cause, and it gets the same answer: resolve it on READ rather than migrating
    anything.

    Deliberately NOT part of `load_schools`. That call is the hot path — a season
    builds ~1,600 rosters through it — and every one of its callers means "the
    programs playing this year". This is the fallback a page takes when the live
    lookup misses, and it is the ONLY way a non-sponsor is ever built.

    Returns None for a name no data row carries, which is a genuine 404: the school
    does not exist, rather than existing and not fielding a team."""
    live = next((s for s in load_schools(gender) if s.name == name), None)
    if live is not None:
        return live
    for r in _rows():
        if r["name"] != name:
            continue
        return School(
            name=r["name"], city=r["city"], county=r["county"], area=r["area"],
            classification=r["classification"], group=r["group"],
            enrollment=r["enrollment"], private=r["private"], mascot=r["mascot"],
            colors=r["colors"], talent=r.get("talent", ""),
            # Their last known league. A former sponsor plays in none, but the
            # archive's own rows carry the league they played in each season, so
            # this is only what the header prints beside the town.
            district=r.get(f"{gender}_district") or _row_league(r) or "",
            gender=gender, source=r.get("source", ""),
            locality=r.get("locality", ""))
    return None


def sponsors_sport(name: str, gender: str) -> bool:
    """Does this program field a team in `gender` TODAY? The one question that
    separates a former program from a current one — everything else about them
    (their archive, their pages, their honours) is the same."""
    return any(s.name == name for s in load_schools(gender))


def _rows() -> list[dict]:
    """The raw school records, loaded once. `load_schools` owns the same file and
    the same module-global; this is the unfiltered read behind it."""
    global _schools_cache
    if _schools_cache is None:
        with open(_DATA, encoding="utf-8") as fh:
            _schools_cache = json.load(fh)["schools"]
    return _schools_cache


def _row_league(row: dict) -> str | None:
    """A settled row's ONE league name — girls and boys share it by construction
    (a league belongs to the SCHOOL, drawn once per classification over the
    girls-inclusive superset), so either field names the same string. Prefer
    girls' since it's the superset; fall back for a boys-only sponsor."""
    return row.get("girls_district") or row.get("boys_district")


def _playup_league(version: str, rows: list[dict],
                   pmap: dict | None = None) -> dict[str, str]:
    """{school: league} for every played-up program's SHARED league — memoised on the
    play-up fingerprint alone (never per gender), so both genders read the identical
    dict and always land on the identical league. Never call `_compute_playup_league`
    directly; this is the caching wrapper `load_schools` uses."""
    hit = _playup_league_cache.get(version)
    if hit is not None:
        return hit
    fresh = _compute_playup_league(rows, pmap)
    # Compute into a local, publish, return the LOCAL (the gthread rule).
    _playup_league_cache.clear()
    _playup_league_cache[version] = fresh
    return fresh


def _compute_playup_league(rows: list[dict],
                           pmap: dict | None = None) -> dict[str, str]:
    """{school: league} for every played-up program — the ONE league (not one per
    gender) they join in the class they compete in.

    ‼️ ONE LEAGUE PER SCHOOL, NOT PER GENDER (owner rule — a league belongs to the
    SCHOOL, same as an unplayed-up program's). The old version ran once per gender
    and picked independently, which could and did put a program's girls team in one
    league and its boys team in another — invisible unless you compared both team
    pages for the same school. Computed ONCE here, gender-agnostic, and cached on
    the play-up fingerprint alone (`_playup_league` above) so `load_schools("girls")`
    and `load_schools("boys")` are guaranteed to read the identical dict.

    ‼️ GEOGRAPHY IS A PREFERENCE, NEVER A GATE (owner rule). A played-up program
    joins the CLOSEST existing league in its new class — county match first, then
    area match — with no capacity cap and no maximum distance. Real high-school
    sport already crosses state lines this freely (WIAA fields Oregon border
    schools, Oregon fields Washington ones, Nevada and California and Arizona
    programs cross both ways) — there is no rule here stricter than that. District
    size is not a constraint to protect: `run_season` builds each district's double
    round-robin from whoever is actually IN it that year, so a league one program
    larger just plays a longer, still-perfectly-valid season. Nothing overflows,
    nothing needs spreading across leagues, and there is no such thing as "a league
    with no room" — only nearer and farther ones.

    ‼️ THIS CANNOT LEGITIMATELY COME UP EMPTY. `near` is populated from every
    settled (non-played-up) program in the target class; it is empty only if that
    whole classification has no settled programs at all, which cannot happen for a
    real class on this data — so that case raises loudly rather than silently
    parking the program on its OLD league (a one-team league in a double round
    robin is a season with no games, and it used to fail exactly that quietly).

    Settled membership excludes every played-up school, so a school that has moved
    out of a class is not counted as still being in it."""
    settled = [x for x in rows if _row_league(x) and not _plays_up_row(x, pmap)]
    movers = sorted((x for x in rows if _plays_up_row(x, pmap)),
                    key=lambda x: x["name"])          # deterministic order

    out = {}
    for row in movers:
        group = _plays_up_row(row, pmap)              # the RESOLVED target, not
                                                        # always one step up
        near: dict[str, list[int]] = {}
        for x in settled:
            if x["group"] != group:
                continue
            slot = near.setdefault(_row_league(x), [0, 0])
            slot[0] += x["county"] == row["county"]
            slot[1] += x["area"] == row["area"]
        if not near:
            raise ValueError(
                f"{row['name']!r} plays up to {group!r}, but {group} has no "
                "settled league to join at all — a real classification always "
                "has one; check the play-up target and the schools data.")
        best = min(near, key=lambda d: (-near[d][0], -near[d][1], d))
        out[row["name"]] = best
    return out


def _plays_up_row(row: dict, pmap: dict | None = None) -> str | None:
    """The resolved target group, or None — see `plays_up`. `pmap` is the resolved
    play-up map. Omit it ONLY for a one-off question about a single school — without
    it every call costs a database round trip."""
    return plays_up(row["name"], bool(row.get("play_up")), pmap,
                    row.get("classification"))


def districts(gender: str, group: str) -> dict[str, list[School]]:
    d = defaultdict(list)
    for s in load_schools(gender):
        if s.group == group:
            d[s.district].append(s)
    return dict(d)


# --- rosters -----------------------------------------------------------------

def _ceiling(rng: random.Random, group: str, gender: str,
             mod: dict | None = None) -> float:
    """A player's CEILING, drawn independently per player. The ladder is not assigned —
    it emerges from who is actually best, so a great freshman can play number one over a
    senior, which is how high school works.

    `mod` is the program-level modifier (`_program_mod`) applied ON TOP of the
    classification band — it shifts and scales that band, it never replaces it, so a
    blue-blood 3A-1A remains a strong SMALL-SCHOOL program."""
    mean, spread = _TALENT[(group, gender)]
    if mod:
        mean += mod.get("mean", 0.0)
        spread *= mod.get("spread", 1.0)
    draw = rng.gauss(mean, spread)
    if mod and mod.get("kind") == "blue_blood" and rng.random() < BLUE_BLOOD_REDRAW:
        # Draw twice, keep the better — clustering, not just a higher mean. Best-of-two
        # lifts the top of a roster far more than the bottom, which is what a programme
        # with the courts and the feeder network actually produces.
        draw = max(draw, rng.gauss(mean, spread))
    return max(GRADE_FLOOR, min(80.0, draw))


def _gen_seat(school: School, mod: dict, entry: int, seat: int, grade: int,
              salt: str) -> Prospect:
    """One seat's Prospect — pulled out of `build_roster` so a TRANSFER (see
    below) can regenerate the exact same person under the school they actually
    play for now, from the ORIGIN school's identity/program modifiers. `pid`
    stays keyed on `school` here always, whatever roster the caller ultimately
    puts this Prospect on — that is what keeps a transferred player's pid, and
    so their pre-transfer history and awards, resolving to the same person."""
    from generators import make_name_picker
    sex = "male" if school.gender == "boys" else "female"
    # (grade - 9), so a FRESHMAN gets nothing and the bonus compounds over four
    # years. Keyed off 8 it would land on ninth-graders too, and a development
    # program's whole character is that you cannot spot it in its freshmen.
    step = mod.get("mature", 0.0) * (grade - 9)
    if entry >= dev_era():
        # New-era cohorts develop on their own rolled trajectory (see
        # `_dev_maturity`) — an exact point, passed as a degenerate band so
        # `generate_prospect` consumes the SAME one uniform draw either era.
        m = min(DEV_CAP, _dev_maturity(school.key, entry, seat, grade, salt) + step)
        maturity = (m, m)
    else:
        # Legacy lockstep bands — existing cohorts keep their exact numbers.
        lo, hi = _MATURITY[grade]
        maturity = (min(1.0, lo + step), min(1.0, hi + step))
    rng = random.Random(f"{salt}|jhsaa|{school.key}|{entry}|{seat}")
    # Keyed on (school, entry, seat) — the same identity the pid is built from —
    # so a prodigy is the SAME person every one of their four seasons rather than
    # a fresh dice roll each year.
    prng = random.Random(f"{salt}|jhsaa-prodigy|{school.key}|{entry}|{seat}")
    if prng.random() < PRODIGY_RATE:
        lo2, hi2 = PRODIGY_MATURITY
        maturity = (max(maturity[0], lo2), max(maturity[1], hi2))
    # ‼️ EXACTLY ONE draw off the main rng, in BOTH eras — the name stream is a
    # separate rng seeded off it, so widening the name draw cannot shift a single
    # talent/attribute roll for anyone, either side of the cutover.
    nrng = random.Random(rng.randrange(1 << 30))
    if entry >= name_era():
        # New-era draw (owner rule 2026-08): frequency-weighted US head over the
        # untouched curated pools, plus the exchange-student slices. ~90/5/5.
        from generators import draw_us_weighted
        roll = nrng.random()
        if roll < NAME_V2_US:
            nm, country = draw_us_weighted(nrng, sex)
        elif roll < NAME_V2_US + NAME_V2_CANADA:
            nm, country = make_name_picker(nrng, gender=sex,
                                           region_weights={"canada": 1.0})()
        else:
            nm, country = make_name_picker(nrng, gender=sex,
                                           region_weights=_intl_weights())()
        country = country or "US"
    else:
        # Legacy draw, byte-identical — existing cohorts keep their exact names.
        nm, _ = make_name_picker(nrng, gender=sex, region_weights={"us": 1.0})()
        country = "US"
    # ‼️ Always generated AS "US": `generate_prospect` branches on country (talent
    # shift, elite roll, academics, hometown path) and consumes the rng differently,
    # so passing the exchange student's country would shift every attribute roll.
    # The name era must move NAMES ONLY — the flag is stamped on afterwards.
    p = generate_prospect(rng, nm, "US", gender=sex,
                          talent=min(80.0, _ceiling(rng, school.talent_group,
                                                    school.gender, mod)
                                     + mod.get("pot", 0.0)),
                          maturity_range=maturity,
                          # `ident`, never `name` — a pid has to survive a
                          # rename or every archived award points at nobody.
                          pid=make_pid("jhsaa", school.ident, school.gender,
                                       entry, seat))
    p.country = country                  # the flag only — see above
    p.class_year = str(grade)
    p.grade = grade
    p.entry_year = entry
    p.hometown = f"{school.city}, JF"
    p.high_school = school.name
    p.region, p.domestic = "Jefferson", True
    return p


def build_roster(school: School, year: int, salt: str = "") -> list[Prospect]:
    """A program's roster for season `year` — its four classes, grades 9 through 12.

    A player is keyed on the year they ENTERED, not the season being played, so the
    same person carries the same pid, name and ceiling through all four years and simply
    matures: the junior who went 15-5 is the senior on next year's board. That is what
    makes a high-school career real without persisting every player — the world rebuilds
    an identical one from (school, gender, entry year, seat).

    ‼️ OFFSEASON TRANSFERS (owner rule 2027-08) are applied here, on the read: a
    player with a `set_jhsaa_transfer` row is dropped from their ORIGIN school's
    build from the effective year on, and regenerated (via `_gen_seat`, same rng
    draws — same person) onto the DESTINATION school's build instead. No
    eligibility/search logic — the table just says who plays where and when.
    """
    mod = _program_mod(school, year, salt)
    # Resolved ONCE per roster build, not per seat — `transfers()` re-resolves the
    # override table's fingerprint on every call, which is a SQLite connect+query
    # even on a cache hit (the playup-fingerprint trap, `AAR-jhsaa-playup-fingerprint
    # -query-storm.md`). A season builds 1,600+ rosters; per-seat would multiply that
    # by every seat on every one of them.
    tmap = transfers()
    out = []
    fresh9_seats = 0
    for grade in GRADES:
        entry = year - (grade - 9)
        n_seats = _freshman_class_size(school.key, entry, school.classification, salt)
        if grade == 9:
            fresh9_seats = n_seats
        for seat in range(n_seats):
            p = _gen_seat(school, mod, entry, seat, grade, salt)
            rec = tmap.get(p.pid)
            # Somewhere else THIS season — `transfer_school` walks every recorded
            # move and returns where they actually are, so a player who moved away
            # and later moved BACK is on this roster again for the years they
            # returned for, without a second rule saying so.
            if rec and transfer_school(rec, year) != school.name:
                continue
            out.append(p)
    # ‼️ THE HARD FLOOR — see `ROSTER_FLOOR` above. Grown on THIS year's freshman
    # class only, continuing its own seat numbering (`fresh9_seats` on) so it never
    # collides with the seats `_freshman_class_size` already rolled for it.
    if len(out) < ROSTER_FLOOR:
        for seat in range(fresh9_seats, fresh9_seats + (ROSTER_FLOOR - len(out))):
            out.append(_gen_seat(school, mod, year, seat, 9, salt))
    # Incoming: every transfer whose DESTINATION is this school AND this gender,
    # effective by now. School names are shared across a boys' and a girls' program
    # (the display identity is per-team, not per-school), so the name match alone
    # would append a boys' mover to the girls' roster of the same name and vice
    # versa — `_gen_seat` would then place an origin-gender Prospect straight onto
    # the opposite-gender team.
    for pid, rec in tmap.items():
        if rec.get("gender") != school.gender:
            continue
        # ‼️ AND NEVER PULL SOMEBODY THIS SCHOOL ALREADY GENERATED. A player whose
        # moves bring them back to their ORIGIN is produced by the seat loop above
        # (which no longer skips them), so adding them here too would put the same
        # person on the roster twice — the one new failure a multi-move history can
        # cause, and it would read as a phantom team-mate rather than as a bug.
        if (transfer_school(rec, year) != school.name
                or rec.get("from") == school.name):
            continue
        entry = rec.get("entry")
        grade = year - entry + 9
        if grade not in GRADES:
            continue                       # not enrolled anywhere this year (yet, or graduated)
        origin = next((s for s in load_schools(rec.get("gender", school.gender))
                       if s.name == rec.get("from")), None)
        if origin is None:
            continue                       # origin school renamed/removed since the move
        omod = _program_mod(origin, year, salt)
        p = _gen_seat(origin, omod, entry, rec.get("seat"), grade, salt)
        if p.pid != pid:
            continue                       # stale/mismatched record — never invent a player
        p.high_school = school.name
        out.append(p)
    out.sort(key=lambda p: -p.current_overall())
    return out


def _squad(ts: TeamSeason, phase: str, lineup: list | None = None,
           fmt: DualFormat | None = None) -> Team:
    """Dress `lineup` (or the current best nine) for `phase`. Singles take the top;
    doubles is its OWN roster below them (`Team.doubles_players`), so the state
    format's four doubles pairs are eight different players rather than the singles
    re-permuted.

    `fmt` overrides the phase's shape — the JV season plays one of `JV_FORMATS`, which
    is sized per dual rather than per phase, so it cannot be looked up from `phase`."""
    f = fmt or dual_format(phase, ts.school.group)
    r = lineup if lineup is not None else _order(ts)[:lineup_need(phase, ts.school.group)]
    if not r:
        raise ValueError(f"{ts.school.name} has an empty roster")
    def at(i):
        return r[i % len(r)]                       # degrade, never crash, on a short side
    # Prospect -> engine Player, the same conversion ncaa.squad_and_ladder uses.
    singles = [at(i).engine_player() for i in range(f.n_singles)]
    dbl = [at(f.n_singles + i).engine_player() for i in range(2 * f.n_doubles)]
    if archetype(ts.school.name) == "doubles":
        dbl = [_doubles_lift(at(f.n_singles + i), ts.school.name, i)
               for i in range(2 * f.n_doubles)]
    return Team(name=ts.school.name, singles=singles,
                doubles=[(2 * i, 2 * i + 1) for i in range(f.n_doubles)],
                doubles_players=dbl)


def _doubles_lift(prospect, school: str, seat: int):
    """A doubles-school player, lifted on the 20-80 GRADE scale for this match only.

    A doubles program generates normally — the roster is not better, the doubles is. So
    the lift is ephemeral: it is applied to a COPY of the player's current grades on the
    way into the engine, never to the Prospect, which `build_roster` caches globally and
    shares across every save. Mutating that would make a temporary edge permanent and
    leak it into every other league reading the same object.

    It also lands only on `Team.doubles_players` — the separate doubles lineup `_squad`
    already builds — so it is structurally incapable of reaching a singles court, rather
    than merely intended not to.

    (There was no existing per-match modifier to reuse: `coaches.development_multiplier`
    is a growth RATE applied at the rollover, a different thing entirely.)"""
    import copy
    lo, hi = DOUBLES_BOOST
    rng = random.Random(f"{school}|dbl|{prospect.pid}|{seat}")
    lift = rng.uniform(lo, hi)
    clone = copy.copy(prospect)
    clone.current = {a: min(80.0, v + lift) for a, v in prospect.current.items()}
    return clone.engine_player()


_SLOT = re.compile(r"^([SD])(\d+)$")

# Bench rotation (owner rule 2027-08): the lineup is re-set match to match on the BEST
# PERFORMING nine — results first, then OVR, STR last — so a hot bench player earns his
# way in. On top of that, coaches USE the bench in the regular season: most duals a
# reserve or two rotates into the bottom of the lineup, so nobody persisted plays zero
# times across a ~26-dual year (which would be absurd). The POSTSEASON is strict:
# your best nine, no rotation. (No injuries here — the JHSAA has no injury system.)
_ROTATE_ONE = 0.45          # chance the 9th seat goes to a bench player, per dual
_ROTATE_TWO = 0.15          # chance the 8th seat does too

# TALENT-AWARE STAFFING vs. truly bad teams (owner rule 2026-08). Colorado's big
# programs field V2/V3 squads; everywhere else the same depth is exercised by coaches
# SITTING starters against overmatched opponents and moving everyone up a rung. We do
# not model a V2 — instead, in the REGULAR SEASON ONLY, a coach facing a clearly weaker
# side (a strength gap always, plus a .300-or-worse record once the opponent has a real
# sample; before that the gap alone decides) rests one — sometimes two — starters from
# the TOP of the ladder. Everybody shifts up one, so the card still reads as the ladder
# (the clear-ladder requirement) and the bottom seats reach two more bench players than
# the ordinary `_ROTATE_*` churn alone. ‼️ NEVER in the postseason (the Order of
# Ability is frozen and strict) and never at a showcase (the whole point of the weekend
# is playing your best against power programs) — both branches of `_lineup` sit above
# this check by construction. Guarded so a thin roster never rests below the card —
# resting past the bench would wrap the same player onto two lines of one dual.
REST_OPP_PCT = 0.300        # the record that marks an opponent "truly bad"
REST_MIN_SAMPLE = 6         # duals before a record means anything
REST_GAP = 10.0             # OVR gap (top-nine mean) that must ALWAYS hold
REST_RATE = 0.75            # chance a qualifying dual actually rests anyone
REST_TWO = 0.35             # ...and that a second starter sits too


def _rest_count(ts: TeamSeason, opp, rng: random.Random, spare: int) -> int:
    """How many starters sit this dual: 0 most of the time, 1-2 against a truly
    weaker side, never more than the bench can absorb (`spare`)."""
    if opp is None or spare <= 0:
        return 0
    if _strength(ts) - _strength(opp) < REST_GAP:
        return 0
    n = opp.wins + opp.losses
    if n >= REST_MIN_SAMPLE and opp.win_pct > REST_OPP_PCT:
        return 0                       # a real record says they aren't that bad
    if rng.random() >= REST_RATE:
        return 0
    k = 2 if (spare > 1 and rng.random() < REST_TWO) else 1
    return min(k, spare)


# ‼️ A CHALLENGE LADDER IS SEEDED ON ABILITY AND MOVED BY RESULTS — never ranked on a
# win COUNT. This sorted on cumulative wins first (`-w`), with ability third, and that
# is a ratchet rather than a ladder: a win total measures OPPORTUNITY, so dressing earns
# wins, wins earn the next start, and a player who dropped his first two duals — or who
# was ninth in week one and never got a start — can never climb back, because every
# team-mate who kept playing sits above him on a number he is not being allowed to add
# to. Ability was in the key but was unreachable behind it. It also ranked 5-15 above
# 4-0, and doubles credits BOTH partners, so a rotation player racked up wins faster
# than a number one playing the hardest opponent on the card.
#
# Measured over a full boys' season before the fix: on 55 of 400 rosters a top-four
# player finished outside the nine, 21 of them under seven matches all year — a 51-OVR
# senior sitting behind a 28-OVR team-mate on the same team.
#
# So the coach seeds on ability and lets the season move you: `LADDER_SWING` is what a
# perfect record is worth against a winless one, in OVR points, and `LADDER_PRIOR` is
# how much evidence it takes before a record carries about half its weight — which is
# what stops a 1-2 opening week from outranking a whole season, and what leaves a player
# who has not played AT HIS SEED instead of at the bottom.
LADDER_SWING = 14.0         # a season-long perfect record ≈ +7 OVR, winless ≈ -7
LADDER_PRIOR = 8.0          # matches before results carry ~half their weight


def ladder_score(p, record: list[int] | None) -> float:
    """Where the coach ranks `p` — ability, adjusted by what he has actually done."""
    w, l = record or (0, 0)
    n = w + l
    if not n:
        return p.current_overall()
    return p.current_overall() + LADDER_SWING * (w / n - 0.5) * n / (n + LADDER_PRIOR)


def _order(ts: TeamSeason) -> list:
    """The ladder as the coach reads it: ability, moved by results, then STR."""
    return sorted(ts.roster,
                  key=lambda p: (-ladder_score(p, ts.records.get(p.pid)),
                                 -p.str_value()))


# --- the ORDER OF ABILITY (owner rule 2027-08, docs/AAR-jhsaa-order-of-ability.md) ---
#
# NFHS-style anti-stacking, the association's own hybrid of real state models
# (North Carolina / Kentucky assessed-ability, West Alameda ladder arithmetic,
# Texas round-to-round movement limits):
#
#   * The association does NOT tell leagues how to build a regular-season lineup —
#     league play keeps the live ladder and the bench rotation. The Order of
#     Ability becomes BINDING for JHSAA championship competition.
#   * Before a program's first postseason dual its Order of Ability is
#     ESTABLISHED from the ladder as it stands (ability seeded, season results
#     stabilising it — `ladder_score`) and then FROZEN for the whole postseason:
#     a mid-bracket hot streak cannot re-rank the roster between rounds (Texas's
#     movement rule, taken to its simplest form).
#   * The nine who dress are the frozen order's top nine, S1 and D1 must consume
#     ranks #1-#3 (no top-three player may appear at D2-D4), and the remaining
#     pairs are ordered on COMBINED LADDER RANK — the anti-stacking boundary.
#   * Two-stage legality, deliberately: the rank sum is the BOUNDARY, not the
#     final sporting judgment. Doubles ability is not singles rank (Iowa's
#     point), so within `PAIR_SUM_TOL` of each other, pairs order on the
#     engine's real `doubles_rating`; beyond it, ladder arithmetic wins no
#     matter the chemistry. #5+#8 outplaying #4+#7 is a lineup; #2 hiding at D4
#     is stacking.
#
# The coach USES the freedom the rule leaves: which of the top three plays
# singles (the other two are D1), and how #4-#9 partner up, are chosen to
# maximise the team the rule allows — so the postseason Flip is solved with the
# roster, never by burying it.
PAIR_SUM_TOL = 2            # rank-sum gap within which real doubles ability decides


def _pair_partitions(pool: list):
    """Every way to split an even-length `pool` into unordered pairs — (2n-1)!!
    of them (15 for 6 players). Used by `_arrange_state` (D2-D4, a small
    postseason qualifying field) to search for the best pairing. `_arrange_regular`
    (the 3S/4D D-pool, 8 players — 105 partitions) used to share this for the
    same kind of search, but that ran on every regular-season dual for the
    whole association and the search was never worth its cost (owner
    correction 2027-08, see the AAR) — it now decides directly instead."""
    if not pool:
        yield []
        return
    a = pool[0]
    for k in range(1, len(pool)):
        b = pool[k]
        for tail in _pair_partitions(pool[1:k] + pool[k + 1:]):
            yield [(a, b)] + tail


def _arrange_state(nine: list, sibling_ids: dict | None = None) -> list:
    """Arrange a frozen-order top nine into SLOT ORDER for the 1S/4D card:
    [S1, D1a, D1b, D2a, D2b, D3a, D3b, D4a, D4b]. `_squad` dresses by position
    and `_slot_players` reads it back the same way, so this list IS the lineup.
    Anything short of nine (a degraded side) plays the plain order."""
    if len(nine) < 9:
        return nine
    from engine.doubles import doubles_rating
    eng = {p.pid: p.engine_player() for p in nine}
    rank = {p.pid: i + 1 for i, p in enumerate(nine)}          # frozen OoA rank

    sibs = sibling_ids or {}

    def pair_rating(a, b):
        r = doubles_rating(eng[a.pid], eng[b.pid])
        # Siblings partner SOMETIMES. `FAMILY_CHEMISTRY` is ~1/4 sd of the observed
        # pair-rating spread, so it settles a near-tie and never overrides a real
        # difference — and `_order_pairs` still enforces the anti-stacking rank-sum
        # boundary afterwards, so this cannot produce an illegal lineup.
        if b.pid in sibs.get(a.pid, ()):
            r += FAMILY_CHEMISTRY
        return r

    # S1 + D1 consume ranks #1-#3: the coach picks which of the three plays
    # singles by what it does for the two points those players cover.
    top3, rest = nine[:3], nine[3:]
    def cfg_score(i):
        s = top3[i]
        d = [p for j, p in enumerate(top3) if j != i]
        return eng[s.pid].overall + pair_rating(d[0], d[1])
    s_i = max(range(3), key=lambda i: (cfg_score(i), -i))      # tie: higher rank plays S1
    s1 = top3[s_i]
    d1 = [p for j, p in enumerate(top3) if j != s_i]

    # D2-D4: every partition of #4-#9 into three pairs (15 of them), best total
    # doubles ability wins; ties break toward ladder-natural pairing.
    def part_key(part):
        return (-sum(pair_rating(a, b) for a, b in part),
                [rank[a.pid] + rank[b.pid] for a, b in part])
    pairs = min(_pair_partitions(rest), key=part_key)

    pairs = _order_pairs(pairs,
                         {_pk(pr): rank[pr[0].pid] + rank[pr[1].pid] for pr in pairs},
                         {_pk(pr): pair_rating(*pr) for pr in pairs})
    out = [s1] + list(d1)
    for a, b in pairs:
        out += [a, b]
    return out


def _arrange_1a_postseason(eight: list, sibling_ids: dict | None = None) -> list:
    """1A's PILOT road-to-State shape (owner rule 2026-08): arrange a frozen-order
    top EIGHT into SLOT ORDER for the 2S/3D card: [S1, S2, D1a, D1b, D2a, D2b,
    D3a, D3b]. Same contract as `_arrange_state`: `_squad` dresses by position,
    `_slot_players` reads it back the same way.

    ‼️ THE SAME MECHANISM AS 1S/4D's, GENERALISED — NOT A DIFFERENT RULE (owner
    correction 2026-08). `_arrange_state` pools the top THREE and searches which
    ONE plays singles (the other two form D1) — the association's best player is
    NOT pinned to S1; a team can pair its #1 into D1 and start #2 or #3 at
    singles if that scores better. 2S/3D pools the top FOUR and searches which
    TWO play singles (the other two form D1) — same idea, one seat wider. The
    real, and only, difference 2S/3D adds is a genuine SECOND singles court: a
    real player from the top-four pool starts there, not the tenth-best kid on
    the roster forced into a doubles-adjacent role. D2/D3 replay `_arrange_state`'s
    own logic on the remaining four (#5-#8): a search over the three ways to pair
    them, best total doubles ability wins, then `_order_pairs`'s rank-sum
    boundary. Anything short of eight (a degraded side) plays the plain order."""
    if len(eight) < 8:
        return eight
    from engine.doubles import doubles_rating
    eng = {p.pid: p.engine_player() for p in eight}
    rank = {p.pid: i + 1 for i, p in enumerate(eight)}

    sibs = sibling_ids or {}

    def pair_rating(a, b):
        r = doubles_rating(eng[a.pid], eng[b.pid])
        if b.pid in sibs.get(a.pid, ()):
            r += FAMILY_CHEMISTRY
        return r

    # S1 + S2 + D1 consume ranks #1-#4: every way to pick TWO of the four for
    # singles, the other two pairing for D1 — the direct generalisation of
    # `_arrange_state`'s "pick ONE of three for S1" search.
    top4, rest = eight[:4], eight[4:8]
    combos = list(itertools.combinations(range(4), 2))

    def cfg_score(combo):
        s = [top4[i] for i in combo]
        d = [top4[i] for i in range(4) if i not in combo]
        return sum(eng[x.pid].overall for x in s) + pair_rating(d[0], d[1])
    # tie: prefer the combo drawing on the higher-ranked (lower-index) pool
    # members for singles, same spirit as `_arrange_state`'s `-i` tiebreak.
    combo = max(combos, key=lambda c: (cfg_score(c), -sum(c)))
    singles = sorted((top4[i] for i in combo), key=lambda p: rank[p.pid])
    s1, s2 = singles
    d1 = [top4[i] for i in range(4) if i not in combo]

    def part_key(part):
        return (-sum(pair_rating(a, b) for a, b in part),
                [rank[a.pid] + rank[b.pid] for a, b in part])
    pairs = min(_pair_partitions(rest), key=part_key)

    pairs = _order_pairs(pairs,
                         {_pk(pr): rank[pr[0].pid] + rank[pr[1].pid] for pr in pairs},
                         {_pk(pr): pair_rating(*pr) for pr in pairs})
    out = [s1, s2] + list(d1)
    for a, b in pairs:
        out += [a, b]
    return out


def _order_pairs(pairs: list, rank_sum: dict, rating: dict) -> list:
    """Order the D2-D4 pairs: real doubles ability first, then the
    anti-stacking boundary — a pair whose rank sum beats the ONE ABOVE IT by
    more than `PAIR_SUM_TOL` moves up, chemistry or not.

    ‼️ The boundary is ADJACENT-SEAT ONLY, by owner ruling (2027-08). A review
    flagged that the tolerance can CHAIN — sums 15 / 13 / 11 each clear their
    neighbour check by exactly the tolerance while D2 sits four rank-points
    above D4 — and proposed enforcing the boundary across every earlier/later
    pairing. The owner kept the chain deliberately: "chemistry matters to me
    more than policing pairings at that fidelity." A step-by-step-defensible
    ladder is legal even when its ends drift apart; what the rule stops is one
    pair leapfrogging its NEIGHBOUR. Do not globalise this check — a test pins
    the chained case as legal.

    `rank_sum` and `rating` are keyed by `_pk(pair)` (Prospects are unhashable
    dataclasses, so the pair itself cannot key a dict)."""
    pairs = sorted(pairs, key=lambda pr: -rating[_pk(pr)])
    changed = True
    while changed:
        changed = False
        for i in range(len(pairs) - 1):
            if rank_sum[_pk(pairs[i])] > rank_sum[_pk(pairs[i + 1])] + PAIR_SUM_TOL:
                pairs[i], pairs[i + 1] = pairs[i + 1], pairs[i]
                changed = True
    return pairs


def _pk(pair) -> tuple:
    """A hashable key for a doubles pair — the pids (or the members themselves
    for plain-value test stubs)."""
    return tuple(getattr(p, "pid", p) for p in pair)


# --- regular-season lineup STRATEGY (owner rule 2027-08) ----------------------
#
# League play is free — "regular season can do what it wants" — and the regular
# season plays the doubles-forward 3S/4D card (owner rule 2027-08, swapped with
# the early non-district window's 5S/2D — see `EARLY_FORMAT_PHASE`). The LINEUP
# ALLOCATION for that card is fixed, never a coaching choice: S1 is always the
# top seed, the doubles pool is always exactly #2-#9, and S2/S3 are always
# exactly #10-#11 (see `_arrange_regular`). What a program's strategy actually
# decides is how the fixed 8-player pool pairs up into D1-D4:
#
#   maximize      snake-pair the pool by serve-vs-return skew (best server with
#                 best returner, and so on) — a cheap stand-in for the engine's
#                 coverage synergy term (`engine.doubles._pair_synergy`), picked
#                 directly rather than searched for.
#   balanced      snake-pair by overall ability (strongest with weakest, and so
#                 on) — spreads strength evenly across all four doubles courts
#                 for a coach who would rather have four solid pairs than one
#                 great one and three ordinary ones.
#   traditional   adjacent-ladder pairing of the fixed pool — D1=#2+#3,
#                 D2=#4+#5, D3=#6+#7, D4=#8+#9. The classic card, and the only
#                 shape the generator used to produce before this rule existed.
#
# ‼️ NONE OF THESE SEARCH (owner correction 2027-08). The first cut of
# `maximize`/`balanced` scored all 105 ways to split the 8-player pool into
# pairs, on EVERY regular-season dual, for every program in the association —
# real coaches do not run a permutation search before a match, they just pair
# people up, and `doubles_rating`'s synergy term is capped tiny (`SYNERGY_CAP`
# in `engine/doubles.py`) specifically so it stays a minor factor, not
# something worth 105-way scoring for. Each strategy is now one direct,
# ability-ordered decision. See `_arrange_regular`.
#
# The strategy is a durable PROGRAM trait (hashed off the school key, like a
# coaching tradition — not per-dual dice, so a program's card is recognisable
# all season), with a small per-dual flip so a coach occasionally tries a
# different one.
_STRATEGIES = ("maximize", "balanced", "traditional")
_PHILOSOPHY_FLIP = 0.15        # per-dual chance the coach tries a different strategy


def _coach_strategy(school_key: str) -> str:
    h = int(hashlib.blake2s(f"jh-strategy|{school_key}".encode(),
                            digest_size=4).hexdigest(), 16)
    return _STRATEGIES[h % len(_STRATEGIES)]


def _flip_strategy(strategy: str) -> str:
    """The next strategy in a fixed cycle — deterministic given which one the
    program normally runs, so a flip is reproducible from the same seed."""
    i = _STRATEGIES.index(strategy)
    return _STRATEGIES[(i + 1) % len(_STRATEGIES)]


def _arrange_regular(eleven: list, strategy: str,
                     sibling_ids: dict | None = None) -> list:
    """The 3S/4D card under `strategy`, in SLOT ORDER
    [S1, S2, S3, D1a, D1b, D2a, D2b, D3a, D3b, D4a, D4b] — same contract as
    `_arrange_state`: `_squad` dresses by position, `_slot_players` reads it
    back identically. Short sides play the plain order.

    ‼️ THE ALLOCATION IS FIXED, NEVER SEARCHED (owner rule 2027-08): S1 is
    always the top seed, the doubles pool is always exactly #2-#9, and S2/S3
    are always exactly #10-#11. A coach does not get to decide whether the
    team's 2nd-9th best players play singles or doubles — that's already
    settled by the format. The only real decision, and the only thing
    `strategy` affects, is how the fixed 8-player pool pairs up into D1-D4.

    ‼️ THE PAIRING ITSELF IS A CHEAP, DIRECT CALL — NOT A SEARCH (owner
    correction 2027-08, after the first cut exhaustively enumerated all 105
    ways to split the 8-player pool and scored each one against every other
    program's pool, every regular-season dual, all season: real-life coaches
    do not run a permutation search before every match, they just pair people
    up, and the payoff was never there to justify it anyway — `doubles_rating`'s
    own docstring caps the synergy term at `SYNERGY_CAP` (0.06) specifically so
    individual quality stays the primary factor, i.e. the thing 105 partitions
    were being searched to eke out is capped tiny by design. `maximize` and
    `balanced` now each make ONE direct decision (a sort, snake-paired or
    skew-paired) instead of scoring every partition; only the final "strongest
    pair plays D1" ordering still touches the real engine rating, and that's 4
    calls, not 420."""
    if len(eleven) < 11:
        return eleven
    s1, pool, s23 = eleven[0], eleven[1:9], eleven[9:11]
    if strategy == "traditional":
        pairs = [(pool[0], pool[1]), (pool[2], pool[3]),
                 (pool[4], pool[5]), (pool[6], pool[7])]
    else:
        from engine.doubles import doubles_rating, serve_rating, return_rating
        eng = {p.pid: p.engine_player() for p in eleven}

        sibs = sibling_ids or {}

        def dr(a, b):
            r = doubles_rating(eng[a.pid], eng[b.pid])
            if b.pid in sibs.get(a.pid, ()):
                r += FAMILY_CHEMISTRY      # see `_arrange_state` — a tiebreak only
            return r

        if strategy == "balanced":
            # Snake-pair strongest with weakest, next-strongest with
            # next-weakest, and so on -- spreads ability evenly across the
            # four courts without scoring a single combination.
            ranked = sorted(pool, key=lambda p: -eng[p.pid].overall)
        else:  # "maximize"
            # A cheap stand-in for the engine's coverage synergy (pairing the
            # better server with the better returner): rank the pool by
            # serve-minus-return skew and snake-pair across it, so a
            # serve-heavy player lands with a return-heavy one instead of
            # searching for the combination that scores best.
            ranked = sorted(pool, key=lambda p: (serve_rating(eng[p.pid])
                                                 - return_rating(eng[p.pid])),
                            reverse=True)
        pairs = [(ranked[0], ranked[7]), (ranked[1], ranked[6]),
                 (ranked[2], ranked[5]), (ranked[3], ranked[4])]
        pairs = sorted(pairs, key=lambda pr: -dr(*pr))  # strongest pair plays D1
    out = [s1] + s23
    for a, b in pairs:
        out += [a, b]
    return out


def _postseason_nine(ts: TeamSeason, phase: str = "state") -> list:
    """The frozen Order of Ability's top N for `phase` (nine, or 1A's pilot
    eight — see `dual_format`), freezing the ORDER on first use — the
    association establishes it before a program's first postseason dual and it
    binds until the season ends. Stored as pids on the TeamSeason (the archive
    never sees it; lineups are recorded per dual as always). Freezing the full
    ladder rather than a fixed-length slice is what lets 1A's road (eight) and
    its TOC entry (nine, back to 1S/4D — see `dual_format`) read the SAME
    frozen order at different slice lengths without a second freeze."""
    if not ts.order_of_ability:
        ts.order_of_ability = [p.pid for p in _order(ts)]
    by_pid = {p.pid: p for p in ts.roster}
    ranked = [by_pid[pid] for pid in ts.order_of_ability if pid in by_pid]
    return ranked[:lineup_need(phase, ts.school.group)]


def _lineup(ts: TeamSeason, phase: str, rng: random.Random, opp=None) -> list:
    """The nine (or, for 1A's road to State, eight) who dress for THIS dual, in
    slot order. `opp` (the opposing TeamSeason, regular season only) lets the
    coach rest starters against a truly weaker side — see `_rest_count`."""
    if phase in POSTSEASON:                        # strict, frozen, arranged
        pool = _postseason_nine(ts, phase)
        if ts.school.group in PILOT_GROUPS and phase != "toc":
            return _arrange_1a_postseason(pool, ts.sibling_ids)
        return _arrange_state(pool, ts.sibling_ids)
    if phase in SHOWCASE:
        # ‼️ A SHOWCASE MUST NOT FREEZE THE ORDER OF ABILITY. The freeze is the
        # association's anti-stacking rule and it binds from a program's first
        # POSTSEASON dual — a showcase is regular season, in the middle of it, and
        # freezing here would bind a program's championship lineup to its April
        # ladder and hand the rule a month of drift it was written to prevent.
        # So: the LIVE ladder, with the league's bench rotation (a showcase is
        # where a coach tries people), arranged onto the 1S/4D card by the same
        # anti-stacking arrangement the postseason uses.
        order = _order(ts)
        need = lineup_need(phase)
        nine, bench = order[:need], order[need:]
        if bench and rng.random() < _ROTATE_ONE:
            nine[-1] = bench[rng.randrange(len(bench))]
        return _arrange_state(nine, ts.sibling_ids)
    order = _order(ts)
    need = lineup_need(phase)
    # Talent-aware staffing: sit 1-2 from the TOP against a truly weaker side and
    # shift everyone up a rung — the ladder ORDER is untouched, so the card still
    # reads as the ladder. Regular-season phases only (this branch).
    rest = _rest_count(ts, opp, rng, len(order) - need)
    if rest:
        order = order[rest:]
    nine, bench = order[:need], order[need:]
    if bench:
        if rng.random() < _ROTATE_ONE:
            nine[-1] = bench[rng.randrange(len(bench))]
        if len(bench) > 1 and rng.random() < _ROTATE_TWO:
            pick = bench[rng.randrange(len(bench))]
            if pick is not nine[-1]:
                nine[-2] = pick
    # League policy: the program's strategy decides how the 3S/4D card's doubles
    # pool pairs up — but `_arrange_regular` is built for THAT card's eleven
    # positions (S1/S2-S3/D1-D4) specifically, and only applies to `phase ==
    # "regular"`. The early window plays the OTHER shape (5S/2D, swapped with
    # regular — see `EARLY_FORMAT_PHASE`) and gets the plain ladder order, same
    # as `_squad`'s default positional mapping always did for that shape.
    if phase == "regular":
        # the per-dual flip draw runs either way, so the rng stream stays aligned.
        flip = rng.random() < _PHILOSOPHY_FLIP
        strategy = _coach_strategy(ts.school.key)
        if flip:
            strategy = _flip_strategy(strategy)
        return _arrange_regular(nine, strategy, ts.sibling_ids)
    return nine


def _slot_players(lineup: list, phase: str, slot: str,
                  fmt: DualFormat | None = None) -> list:
    """The players who played `slot` ("S3", "D2"), by the SAME indexing the squad was
    dressed with — never a second opinion on who was on court.

    `fmt` overrides the phase's shape, exactly as in `_squad` and for the same reason:
    a JV dual's format is sized per DUAL off the thinner roster, so it cannot be looked
    up from `phase`. ‼️ It must be the same override `_squad` was given — the doubles
    base is `f.n_singles + 2*(i-1)`, so resolving D2 against the varsity singles count
    while the squad was dressed on the JV one names the wrong players and raises
    nothing."""
    m = _SLOT.match(slot or "")
    if not m or not lineup:
        return []
    kind, i = m.group(1), int(m.group(2))
    f = fmt or dual_format(phase)
    at = lambda k: lineup[k % len(lineup)]                        # noqa: E731
    if kind == "S":
        return [at(i - 1)]
    base = f.n_singles + 2 * (i - 1)
    return [at(base), at(base + 1)]


def _credit(ts: TeamSeason, lineup: list, phase: str, slot: str, won: bool,
            opp_lineup: list | None = None, opp_school: str = "",
            opp_group: str | None = None) -> None:
    """Credit a line to the players who played it — and LOG the match.

    The W-L counters alone cannot answer any of the questions the awards ask
    (`jhsaa_awards`): who you beat, from which court, and when. So each
    appearance also records the opponent's pids, the slot and the phase — a
    résumé, not a record. Kept as a tuple rather than a dict because a gender's
    season logs ~100k of these.

    ‼️ `_slot_players` MUST be told the shape THIS side was dressed with — see
    its own docstring. `ts.school.group`/`opp_group` are threaded through so a
    1A postseason dual (2S/3D) resolves D-slots against 2 singles, not the
    1S/4D default `dual_format(phase, None)` would silently fall back to."""
    mates = _slot_players(lineup, phase, slot, dual_format(phase, ts.school.group))
    opps = (tuple(p.pid for p in _slot_players(opp_lineup, phase, slot,
                                               dual_format(phase, opp_group)))
            if opp_lineup else ())
    for p in mates:
        rec = ts.records.setdefault(p.pid, [0, 0])
        rec[0 if won else 1] += 1
        ts.by_pid.setdefault(p.pid, p)
        partner = next((q.pid for q in mates if q.pid != p.pid), "")
        ts.matches.setdefault(p.pid, []).append(
            (slot, bool(won), phase, opps, partner, opp_school))


def _score_str(ln) -> str:
    res = getattr(ln, "result", None)
    sets = getattr(res, "set_scores", None) or []
    return ", ".join(f"{h}-{w}" for h, w in sets)


def _dual_margin(res) -> tuple[int, int, int, int]:
    """(home sets, away sets, home games, away games) across every court of a dual,
    read off the engine result. `set_scores` is oriented (home, away) per set, which
    is the same orientation `_score_str` stores."""
    hs = aws = hg = ag = 0
    for ln in res.lines:
        for h, w in (getattr(getattr(ln, "result", None), "set_scores", None) or ()):
            hg += h
            ag += w
            if h > w:
                hs += 1
            elif w > h:
                aws += 1
    return hs, aws, hg, ag


def jv_outcome(res) -> int:
    """1 home won, -1 away won, 0 a TIE — the JHSAA's first drawn match.

    ‼️ NEVER READ `res.winner` FOR A JV DUAL. The engine computes it as
    `0 if points[0] > points[1] else 1`, so on a level dual it silently reports an
    AWAY win. Every varsity format in this association has an odd court count and can
    never draw, which is why that has always been safe and why it would not be here:
    three of the eight `JV_FORMATS` are even, and 2S/2D — the most common single shape
    on the slate — is one of them. Left alone, roughly a fifth of drawn JV duals would
    have been recorded as away wins with nothing to show for it.

    The ladder is the owner's (2026-08): points, then SETS across every court, then
    GAMES, and a dual still level after that is a tie. Sets before games because a
    6-0 6-0 win and a 7-6 7-6 win are the same one court won; the set count is the
    coarser and more meaningful of the two, so it is asked first."""
    if res.home_points != res.away_points:
        return 1 if res.home_points > res.away_points else -1
    hs, aws, hg, ag = _dual_margin(res)
    if hs != aws:
        return 1 if hs > aws else -1
    if hg != ag:
        return 1 if hg > ag else -1
    return 0


def play_jv_dual(a: JVTeam, b: JVTeam, *, seed: int, phase: str = "regular",
                 district: bool = False) -> None:
    """One JV dual. The shape is the SMALLER side's capacity (`jv_dual_format`); a
    side that cannot field five spare never reaches here.

    ‼️ IT WRITES NOTHING TO THE VARSITY SEASON. No `_credit`, so nothing reaches
    `records` (the ladder) or `matches` (the awards). That is not restraint on this
    function's part — `JVTeam` simply has nowhere to put them, which is why it is a
    separate type.

    `lines` carries the per-court BOX SCORE (owner rule 2026-08) — who played S1, who
    played D2, and what they won — because a JV schedule that cannot be opened up is
    the varsity page with the interesting half removed. `played` stays beside it as the
    participation list the career ledger's JV column folds; it is derivable from `lines`
    now, and is kept because that column should not depend on parsing court detail it
    does not use.

    ‼️ EVERY READER OF `lines` MUST NOW FILTER ON `level`. While JV rows carried none,
    `state._jh_line_records` / `_jh_slot_records` / `world.jhsaa_underplayed` were blind
    to JV as a property of the data; they are not any more, and all three take a whole
    schedule from callers that pass both levels."""
    fmt = jv_dual_format(jv_spare(a.team), jv_spare(b.team))
    if fmt is None:
        return
    need = jv_lineup_need(fmt)
    la, lb = jv_pool(a.team)[:need], jv_pool(b.team)[:need]
    mf = match_format(phase)
    res = simulate_dual(_squad(a.team, phase, la, fmt), _squad(b.team, phase, lb, fmt),
                        seed=seed, play_all=True, fidelity=FIDELITY, dual_fmt=fmt,
                        singles_fmt=mf, doubles_fmt=mf)
    out = jv_outcome(res)
    a.points_for += res.home_points
    a.points_against += res.away_points
    b.points_for += res.away_points
    b.points_against += res.home_points
    shape = f"{fmt.n_singles}S/{fmt.n_doubles}D"
    # ‼️ NO `_credit` (owner rule 2026-08). The lines are recorded for the BOX SCORE and
    # nothing else — they never reach `records` (the ladder), `matches` (the awards) or
    # TOSS. That is the whole difference from `play_dual`, which credits as it builds.
    # ‼️ `fmt` MUST be passed to `_slot_players` — the same override `_squad` was
    # dressed with. Without it D-slots resolve against the varsity singles count.
    lines = []
    for ln in res.lines:
        hw = getattr(ln, "home_won", None)
        if hw is None:
            continue
        slot = getattr(ln, "slot", "")
        lines.append({"slot": slot,
                      "home": [x.name for x in _slot_players(la, phase, slot, fmt)],
                      "away": [x.name for x in _slot_players(lb, phase, slot, fmt)],
                      "score": _score_str(ln), "home_won": bool(hw)})
    a.schedule.append({"opp": b.school.name, "home": True, "phase": phase,
                       "pf": res.home_points, "pa": res.away_points,
                       "won": out > 0, "tied": out == 0, "district": district,
                       "level": LEVEL_JV, "shape": shape, "lines": lines,
                       "played": [p.name for p in la]})
    b.schedule.append({"opp": a.school.name, "home": False, "phase": phase,
                       "pf": res.away_points, "pa": res.home_points,
                       "won": out < 0, "tied": out == 0, "district": district,
                       "level": LEVEL_JV, "shape": shape, "lines": lines,
                       "played": [p.name for p in lb]})
    if out > 0:
        a.wins += 1
        b.losses += 1
    elif out < 0:
        b.wins += 1
        a.losses += 1
    else:
        a.ties += 1
        b.ties += 1


def play_dual(a: TeamSeason, b: TeamSeason, *, seed: int, phase: str = "regular",
              district: bool = False, challenge: bool = False):
    """One dual. Always to completion — high school has no clinch. `district` marks it
    as counting toward district place as well as the overall record.

    `challenge` is a LABEL on a non-district dual, not a phase: the mid-season challenge
    is played under the ordinary 3S/4D regular-season rules and counts everywhere a
    non-district dual counts (overall record, TOSS, at-large selection). Making it a
    `phase` would have quietly changed its dual format and dropped it out of the rating,
    which is the opposite of why it exists.

    It is deliberately IN-MEMORY ONLY and is not archived to `world_jhsaa_dual`: the
    owner does not want the challenge distinguished on a card, so after persistence it
    reads as the ordinary non-district dual it is. The flag exists so the scheduler can
    keep the window's one paired-on-results dual apart from the window's ordinary ones,
    and so the tests can assert it never reaches a district record. If a view ever needs
    to mark it, the column comes first — do not infer it from position in the card."""
    lrng = random.Random(f"lineup|{seed}")
    la, lb = _lineup(a, phase, lrng, b), _lineup(b, phase, lrng, a)
    fmt = match_format(phase)
    # `a`/`b` share a classification in every postseason pairing (a bracket never
    # crosses groups), so either side's group is the right one to resolve the
    # shape from — see `dual_format`'s 1A-pilot branch.
    res = simulate_dual(_squad(a, phase, la), _squad(b, phase, lb), seed=seed,
                        play_all=True, fidelity=FIDELITY,
                        dual_fmt=dual_format(phase, a.school.group),
                        singles_fmt=fmt, doubles_fmt=fmt)
    lines = []
    for ln in res.lines:                       # individual records, for awards
        hw = getattr(ln, "home_won", None)
        if hw is None:
            continue
        slot = getattr(ln, "slot", "")
        _credit(a, la, phase, slot, bool(hw), lb, b.school.name, b.school.group)
        _credit(b, lb, phase, slot, not hw, la, a.school.name, a.school.group)
        lines.append({"slot": slot,
                      "home": [x.name for x in
                               _slot_players(la, phase, slot,
                                            dual_format(phase, a.school.group))],
                      "away": [x.name for x in
                               _slot_players(lb, phase, slot,
                                            dual_format(phase, b.school.group))],
                      "score": _score_str(ln), "home_won": bool(hw)})
    a.points_for += res.home_points
    a.points_against += res.away_points
    b.points_for += res.away_points
    b.points_against += res.home_points
    # DualResult.winner is an INT — 0 home, 1 away. Comparing it to "home" silently
    # credits the away team every dual; under the home-and-home schedule this used to
    # run, that left every side at exactly .500 with correct-looking point
    # differentials. Cost an hour.
    # `level` is stamped on every VARSITY row too, not only on JV rows: the archive
    # column is not nullable-by-convention, and a row that merely OMITS the marker is
    # indistinguishable from one written before the column existed.
    a.schedule.append({"opp": b.school.name, "home": True, "phase": phase,
                       "pf": res.home_points, "pa": res.away_points,
                       "won": res.winner == 0, "district": district,
                       "level": LEVEL_VARSITY,
                       "challenge": challenge, "lines": lines})
    b.schedule.append({"opp": a.school.name, "home": False, "phase": phase,
                       "pf": res.away_points, "pa": res.home_points,
                       "won": res.winner == 1, "district": district,
                       "level": LEVEL_VARSITY,
                       "challenge": challenge, "lines": lines})
    if res.winner == 0:
        a.wins += 1
        b.losses += 1
        if district:
            a.dwins += 1
            b.dlosses += 1
    else:
        b.wins += 1
        a.losses += 1
        if district:
            b.dwins += 1
            a.dlosses += 1
    return res


# --- the season --------------------------------------------------------------

def run_district(schools: list[School], year: int, *, seed: int,
                 salt: str = "") -> list[TeamSeason]:
    """A district's regular season: DOUBLE round-robin, 3S/4D, every match completed.
    Returns its teams ordered by finish (win %, then point differential).

    You meet every league opponent at least once, and rematch as many as fit under
    `DISTRICT_DUAL_CAP` (owner rule 2026-08 — a league of 10 or fewer still plays the
    full home-and-away double; a bigger one plays pass 1 complete plus a truncated
    second leg, capped at 16-18 district duals). The rest of the card is
    out-of-district, in `_crossover`.

    Split from `district_teams` so `run_season` can play the NON-district card first —
    see `_crossover`. Standalone (tests, a single district) this still does both."""
    teams = district_teams(schools, year, salt)
    play_district(teams, year, salt)
    return teams


def district_teams(schools: list[School], year: int, salt: str = "") -> list[TeamSeason]:
    """A district's programs with this year's rosters, before a ball is struck."""
    fam = families()          # resolved ONCE here, never per team and never per dual
    out = []
    for s in schools:
        roster = build_roster(s, year, salt)
        # ‼️ SIBLINGS, not the household — `{pid: {sibling pids}}`. This used to carry
        # the family ID and the arrangers compared two of them, which gave cousins
        # (and anyone merely reachable through a third member's tie) the partnering
        # bonus. Still resolved once per team from the one `families()` read.
        sibs = {}
        for p in roster:
            if p.pid not in fam:
                continue
            kin = {q for l in family_links(fam[p.pid][1])
                   if l.get("relation") == "sibling" and p.pid in (l.get("a"), l.get("b"))
                   for q in (l.get("a"), l.get("b")) if q != p.pid}
            if kin:
                sibs[p.pid] = kin
        out.append(TeamSeason(school=s, roster=roster, sibling_ids=sibs))
    return out


# --- the district round robin ------------------------------------------------
#
# ⚠️ A DOUBLE round robin is TWO SEPARATED PASSES, not a home-and-home series.
#
# This used to be `for a: for b: for leg in (0, 1)` — which plays a program's two
# meetings with an opponent on consecutive dates, all season long:
#
#     Mar 10  at Alder Landing        Mar 15  at Altamonte
#     Mar 12  vs Alder Landing        Mar 17  vs Altamonte
#
# Every card in the association read like that. It is a correct double round robin and
# a schedule no high school has ever played. The fix is structural, not cosmetic: the
# league is generated as ROUNDS (the circle method — every team plays exactly once per
# round), the first pass runs the rounds forward, the mid-season window goes in the
# middle, and the second pass runs them back the other way with the venue flipped. So a
# team meets its opponents A → B → … → G, breaks, then G → … → B → A, and the return
# match falls most of a season after the first one.
#
# `_rr_rounds` returns unordered pairs and `_orient` decides venue SEPARATELY, because
# the two are different constraints: the rounds fix WHO plays WHEN, the orientation bit
# fixes WHERE. One bit per pairing serves both meetings (pass 2 is its inverse), so
# "the return match reverses venue" holds by construction and cannot be broken by the
# home/away balancing, which only ever flips that one bit.

def _rr_rounds(n: int) -> list[list[tuple[int, int]]]:
    """Single round robin over 0..n-1 as ROUNDS, by the circle method.

    Every team appears at most once per round, so no program plays the same opponent on
    consecutive dates. An odd `n` gets a phantom entry whose pairing is dropped, which
    is the bye — that team simply has one fewer league date in the pass."""
    ix = list(range(n)) + ([None] if n % 2 else [])
    m = len(ix)
    rounds = []
    for _ in range(max(0, m - 1)):
        pairs = [(ix[i], ix[m - 1 - i]) for i in range(m // 2)]
        rounds.append([(min(a, b), max(a, b)) for a, b in pairs
                       if a is not None and b is not None])
        ix = [ix[0], ix[-1]] + ix[1:-1]           # rotate all but the fixed first seat
    return rounds


def _mirror_orders(n_rounds: int) -> list[list[int]]:
    """Candidate round orders for the SECOND pass, best separation first.

    ⚠️ A plain reverse is the obvious mirror and it is wrong at the fold. If pass 2 runs
    the rounds backwards, the LAST opponent of pass 1 is the FIRST of pass 2 — the two
    meetings land on consecutive league dates, which is the exact back-to-back pairing
    this whole rewrite exists to remove. It is invisible in a per-team card until you
    measure the gaps: eleven opponents beautifully spread, and one played twice in a row.

    So the second pass is a ROTATED mirror, and the rotation is chosen by measuring. A
    pair met in round `i` of pass 1 and round `j` of pass 2 (`order[j] == i`) is
    separated by `R + j - i` league dates. Every rotation of both families is scored by
    its WORST pair, and everything clearing HALF A PASS is kept:

      * serpentine  `rev`: pass 2 runs backwards, rotated — G → F → … → A
      * mirrored    `fwd`: pass 2 runs forwards, rotated  — A → B → … → G

    Un-rotated `fwd` is the textbook mirrored double round robin and scores a flat `R`,
    the maximum; the best serpentine reaches about `R/2`, which is still a return match
    half a season plus the whole mid-season window after the first meeting. Both clear
    the floor, so `district_rounds` draws from the band on the season seed and a
    program's opponent order genuinely differs year to year — which is the ask, since
    the second pass "does not need to be a perfect reverse every season". What does not
    vary is the floor."""
    R = n_rounds
    if R <= 1:
        return [list(range(R))]
    floor = (R + 1) // 2
    cands, seen = [], set()
    for family in ("rev", "fwd"):                 # serpentine first: it is the house shape
        for k in range(R):
            order = ([(R - 1 - j + k) % R for j in range(R)] if family == "rev"
                     else [(j + k) % R for j in range(R)])
            pos = {r: j for j, r in enumerate(order)}
            if min(R + pos[i] - i for i in range(R)) < floor:
                continue
            key = tuple(order)
            if key not in seen:                   # several k collapse at small R
                seen.add(key)
                cands.append(order)
    return cands or [list(range(R))]


def _venue_cost(seq: list[bool]) -> int:
    """How bad one team's home/away sequence is. Runs longer than two are penalised
    quadratically (three straight road dates is a real complaint; six is a different
    kind of complaint), plus a linear penalty for an unbalanced card. Round-robin
    scheduling treats both as first-class constraints rather than as an afterthought."""
    cost = run = 0
    for prev, cur in zip(seq, seq[1:]):
        run = run + 1 if prev == cur else 0
        if run >= 2:                               # a run of 3+ dates
            cost += (run - 1) ** 2
    return cost + abs(2 * sum(seq) - len(seq))


def _orient(order: list[list[tuple[int, int]]], mirror: list[int], n: int,
            rng: random.Random) -> dict[tuple[int, int], bool]:
    """Choose, per PAIRING, which meeting is at home — one bit that serves both passes.

    Seeded from the round/seat parity (a decent first cut), then greedily improved: flip
    any single bit that lowers the total venue cost, sweeping until nothing helps. Small
    districts make this trivial and a 12-team district has 66 bits, so a handful of
    sweeps is nothing next to simulating the duals themselves."""
    flip = {p: bool((r + i) % 2) for r, rnd in enumerate(order) for i, p in enumerate(rnd)}

    def sequences() -> dict[int, list[bool]]:
        seq: dict[int, list[bool]] = {t: [] for t in range(n)}
        for pass_no in (0, 1):
            rounds = order if pass_no == 0 else [order[i] for i in mirror]
            for rnd in rounds:
                for a, b in rnd:
                    home_is_a = flip[(a, b)] if pass_no == 0 else not flip[(a, b)]
                    seq[a].append(home_is_a)
                    seq[b].append(not home_is_a)
        return seq

    def total() -> int:
        return sum(_venue_cost(s) for s in sequences().values())

    pairs = [p for rnd in order for p in rnd]
    rng.shuffle(pairs)                             # deterministic, but not index-ordered
    best = total()
    for _ in range(4):
        improved = False
        for p in pairs:
            flip[p] = not flip[p]
            cost = total()
            if cost < best:
                best, improved = cost, True
            else:
                flip[p] = not flip[p]
        if not improved:
            break
    return flip


#: ‼️ THE DISTRICT SEASON IS CAPPED (owner rule 2026-08, REVERSING the earlier
#: "never cut the second league leg"): "double round robins are bad when leagues
#: are more than 10 teams… i don't want teams playing more than 16-18 district
#: matches in a year." A 12-team league's full double round robin is 22 league
#: duals — too many. So: a league whose full double fits under this cap plays it
#: unchanged (10 teams = 18, exactly at the line); a bigger league plays pass 1
#: COMPLETE — everyone still meets everyone, which is what a league season IS —
#: and then only the first rounds of the mirrored pass 2 until the cap is
#: reached. The second leg becomes UNBALANCED (you rematch some opponents, not
#: all), which is exactly how real oversized high-school leagues schedule; the
#: tiebreak ladder already reads head-to-head and series aggregate off the
#: meetings actually played, so 1-vs-2 meetings need no special casing.
DISTRICT_DUAL_CAP = 18


def district_pass1_rounds(n: int) -> int:
    """Rounds in the FIRST pass of an n-team district card — n-1 for even n, n
    for odd (each odd-n round sits one team out). This is the split point
    `play_regular_season` puts the mid-season window at; `len(rounds) // 2` is
    no longer that point once the cap truncates the second pass."""
    return n if n % 2 else n - 1


def district_rounds(teams: list[TeamSeason], year: int, salt: str = "") -> list[list[tuple]]:
    """The district's league card as an ordered list of ROUNDS of (home, away) teams —
    the first pass, then the second pass mirrored with venues reversed, the second
    pass truncated where the full double would exceed `DISTRICT_DUAL_CAP`.

    The caller decides what goes BETWEEN the two passes (`run_season` puts the
    mid-season window there — the split point is `district_pass1_rounds`, NOT
    `len // 2`, which lands mid-pass-1 on a capped league); playing the list
    straight through is the league season. The pass-2 rotation varies by season so
    a program's opponent order is not the same every year, and every variant is
    reproducible from the save seed. Because pass 2 is truncated from its own
    seasonally-rotated order, WHICH opponents a program meets twice also varies by
    year rather than freezing one privileged rematch set."""
    n = len(teams)
    if n < 2:
        return []
    dname = teams[0].school.district
    rng = random.Random(f"{salt}|rr|{year}|{teams[0].school.gender}|{dname}")
    order = _rr_rounds(n)
    rng.shuffle(order)                    # which round leads varies by season
    variants = _mirror_orders(len(order))
    mirror = variants[rng.randrange(len(variants))]
    flip = _orient(order, mirror, n, rng)
    passes = [order, [order[i] for i in mirror]]
    # The cap: pass 1 always plays out in full (n-1 duals per team); pass 2 only
    # until the per-team total reaches DISTRICT_DUAL_CAP. Even n: exactly the cap.
    # Odd n: each kept round sits one team out, so totals land at cap or cap-1 —
    # inside the owner's 16-18 window, never over it.
    if 2 * (n - 1) > DISTRICT_DUAL_CAP:
        passes[1] = passes[1][:max(0, DISTRICT_DUAL_CAP - (n - 1))]
    out = []
    for pass_no, rounds in enumerate(passes):
        for rnd in rounds:
            date = []
            for a, b in rnd:
                home_is_a = flip[(a, b)] if pass_no == 0 else not flip[(a, b)]
                date.append((teams[a], teams[b]) if home_is_a else (teams[b], teams[a]))
            out.append(date)
    return out


def play_rounds(rounds: list[list[tuple]], year: int, salt: str, tag: str = "") -> None:
    """Play a list of rounds in order.

    ⚠️ The dual seed is derived from the PAIRING, never from its position in the list.
    A double round robin plays each unordered pair twice with the venue reversed, so the
    ORDERED pair (home, away) already identifies a dual uniquely — no round or seat index
    is needed, and including one would be a bug rather than extra entropy. The caller
    slices this list: `play_regular_season` plays `rounds[:half]`, runs the mid-season
    window, then plays `rounds[half:]`, and a local `enumerate` restarts at zero on the
    second call. Every second-pass dual would then be seeded differently from the same
    district played straight through by `play_district`, so a standalone run or a
    calibration script would produce different results for identical inputs. Keying on
    the pairing also makes a result independent of which rotation the season drew, which
    is the property you actually want: who wins depends on who is playing."""
    for date in rounds:
        for h, a in date:
            seed = int(hashlib.blake2s(
                f"{salt}|d|{year}|{tag}|{h.school.key}|{a.school.key}".encode(),
                digest_size=4).hexdigest(), 16)
            play_dual(h, a, seed=seed, phase="regular", district=True)


# --- district standings ------------------------------------------------------
#
# Place is district win %, and the TIEBREAK LADDER is the association's (owner rule
# 2027-08), in order:
#
#   1. HEAD-TO-HEAD record among the tied teams — a mini-league, so it settles a
#      three-way tie the same way it settles a two-way one.
#   2. If they split, the AGGREGATE of those meetings — courts won minus courts lost
#      across the season series, so a 6-1 / 3-4 split beats a 4-3 / 1-6 one.
#   3. Overall season record — the whole card, non-district included, deliberately.
#   4. Power Index (TOSS).
#   5. OOWP — opponents' opponents' win %, the deepest strength-of-schedule term.
#
# ⚠️ Every LEAGUE figure here is read off the district schedule entries, never off
# `points_for`/`points_against`. Those two fields accumulate over EVERY dual a team
# plays, non-district included, so using them to break a league tie lets a blowout in
# the early non-district window decide a district title. They are the right numbers for
# an overall margin and the wrong ones for anything labelled "district".

def _district_duals(t: TeamSeason, against: set[str] | None = None) -> list[dict]:
    """A team's league duals, optionally only those against a given set of schools."""
    return [x for x in t.schedule
            if x.get("district") and x.get("phase") == "regular"
            and (against is None or x["opp"] in against)]


def district_oowp(teams: list[TeamSeason]) -> dict[str, float]:
    """{school: opponents' opponents' win %} over the pool given.

    The last rung of the ladder, and the one that only ever matters when four teams have
    matched each other on everything else. Computed on overall win %, which is what OOWP
    means — the depth of a schedule is not a league-only property."""
    by = {t.school.name: t for t in teams}
    # ‼️ Every non-postseason, non-showcase dual — never just `phase == "regular"`.
    # The early non-district window (`EARLY_FORMAT_PHASE`) is still a regular-season
    # opponent for OOWP's purposes; filtering to "regular" only would silently drop
    # every program's early-window opponents from its opponents' opponents' win %.
    opps = {t.school.name: [x["opp"] for x in t.schedule
                            if x.get("phase") not in POSTSEASON
                            and x.get("phase") not in SHOWCASE]
            for t in teams}

    def owp(name: str) -> float:
        seen = [by[o].win_pct for o in opps.get(name, ()) if o in by]
        return sum(seen) / len(seen) if seen else 0.0

    cache = {n: owp(n) for n in by}
    out = {}
    for name in by:
        seen = [cache[o] for o in opps.get(name, ()) if o in cache]
        out[name] = sum(seen) / len(seen) if seen else 0.0
    return out


def _tiebreak(group: list[TeamSeason], oowp: dict[str, float]) -> list[TeamSeason]:
    """Order teams that finished level on district win %, by the ladder above."""
    names = {t.school.name for t in group}
    h2h: dict[str, tuple[float, int]] = {}
    for t in group:
        met = _district_duals(t, names - {t.school.name})
        wins = sum(1 for x in met if x["won"])
        margin = sum(x["pf"] - x["pa"] for x in met)
        h2h[t.school.name] = (wins / len(met) if met else 0.0, margin)
    return sorted(group, key=lambda t: (
        -h2h[t.school.name][0],            # 1. head-to-head record
        -h2h[t.school.name][1],            # 2. aggregate of those meetings
        -t.win_pct,                        # 3. overall season record
        -t.power,                          # 4. Power Index (0.0 before it is computed)
        -oowp.get(t.school.name, 0.0),     # 5. OOWP
        t.school.name))


def settle_district(teams: list[TeamSeason],
                    oowp: dict[str, float] | None = None) -> list[TeamSeason]:
    """Sort by district win % with the tiebreak ladder, and stamp `district_place`.

    Split out of `play_district` so `run_season` can settle AFTER the Power Index exists
    — rung 4 of the ladder reads `t.power`, which is only stamped once the whole gender's
    regular season is finished. Settling earlier is not wrong, it just resolves that one
    rung as a tie and falls through to OOWP.

    A tie is resolved as a GROUP, not pairwise: head-to-head among three level teams is a
    mini-league, and a pairwise comparator on it would not even be transitive."""
    oowp = district_oowp(teams) if oowp is None else oowp
    teams.sort(key=lambda t: -t.district_pct)
    out: list[TeamSeason] = []
    i = 0
    while i < len(teams):
        j = i
        while j < len(teams) and teams[j].district_pct == teams[i].district_pct:
            j += 1
        out += _tiebreak(teams[i:j], oowp) if j - i > 1 else teams[i:j]
        i = j
    teams[:] = out
    for k, t in enumerate(teams, 1):
        t.district_place = k
    return teams


def play_district(teams: list[TeamSeason], year: int, salt: str = "") -> list[TeamSeason]:
    """Play the double round-robin straight through and settle district place. The
    standalone path (a single district, tests, calibration); `run_season` drives the two
    passes itself so it can put the mid-season window between them."""
    play_rounds(district_rounds(teams, year, salt), year, salt,
                teams[0].school.district if teams else "")
    power = power_index(teams)
    for t in teams:
        r = power.get(t.school.name)
        if r is not None:
            t.power = r.pi_raw
    return settle_district(teams)


# --- the Power Index (TOSS) ------------------------------------------------------
# At-large selection and seed order run on the POWER INDEX, not on raw win-loss.
# The model is TOSS — the Tennis Opponent-Strength System, oregontennis.org's
# three-part composite for rating high school programs statewide, and the same one
# `app.rating` already runs for the college league:
#
#     Power Index = 0.40 APR + 0.40 FQI + 0.20 oGS
#
#   APR  strength of schedule (RPI: 25% win% + 50% opponents' + 25% opponents'-opponents')
#   FQI  flight-weighted share of lines won, scaled by opponent APR / league median
#   oGS  share of GAMES won, scaled by the same opponent multiplier
#
# So beating a strong card across every flight rates above running up a record on a
# weak one, and a 4-3 win where you took the premier flights rates above a 4-3 win
# where you took the bottom of the lineup.
#
# Flight weights for the JHSAA's dual shapes (owner rule 2027-08). One table shared
# across all three cards — early 5S/2D, regular-season 3S/4D, state/showcase 1S/4D —
# since only the SLOT is weighted, never the dual shape it was played under; see
# `dual_format`/`FORMATS` for which shape a given phase plays.
# #1 singles and #1 doubles carry EQUAL top weight, and the tail is deliberately steep:
# a team that wins the two premier flights has done most of the work, while depth at
# #4/#5 singles moves the number very little.
#
# These are the association's own numbers, not the college table (flatter across
# singles, doubles below #1 singles) and not Oregon's (a 4S/4D format that does not
# map). They are the only flight numbers in the pipeline — nothing else hard-codes one.
FLIGHT_WEIGHTS = {
    "S1": 1.00, "S2": 0.75, "S3": 0.25, "S4": 0.10, "S5": 0.10,
    "D1": 1.00, "D2": 0.50,
    # D3/D4 appear in every 1S/4D dual (postseason + showcases) AND, since the
    # 2027-08 regular-season swap to 3S/4D, in EVERY ordinary league dual too —
    # they used to be rated only by the in-postseason recomputes and the showcase
    # cutoff table (`SHOWCASE_RATED`); now they are load-bearing for the whole
    # regular season, not just those two carve-outs. Same decay as above.
    "D3": 0.25, "D4": 0.10,
}
# ‼️ NOT a shared denominator FQI divides by, and NOT the max for any one dual shape
# any more (the three cards — 5S/2D early, 3S/4D regular, 1S/4D state/showcase — each
# contest a different weight total now that D3/D4 are load-bearing everywhere).
# `rating._flight_score` totals the weight actually CONTESTED in each dual and
# normalises per-dual, so every shape contributes a 0..1 share to the same table
# without either being over- or under-counted. This constant is historical/
# documentary only — the 5S/2D-era max — and nothing in the pipeline reads it.
MAX_FLIGHT_WEIGHT = 3.70


def _games(score: str) -> tuple[int, int]:
    """Games won by each side, parsed out of a line's score string ("6-4, 3-6, 7-5").

    Read back from the STRING rather than persisted alongside it: the archive already
    holds the score, so the opponent-weighted game share works on seasons that were
    played before the Power Index existed, and `world_jhsaa_dual` doesn't grow a column
    that would only ever restate what is already there."""
    h = a = 0
    for st in (score or "").split(","):
        bits = st.strip().split("-")
        if len(bits) != 2:
            continue
        try:
            h += int(bits[0]); a += int(bits[1])
        except ValueError:
            continue
    return h, a


def rating_duals(teams, prestate: bool = False) -> list[dict]:
    """Every ratable dual once, in the shape `rating.compute_ratings` consumes.

    A dual sits on BOTH sides' schedules, so only the home side's copy is taken —
    counting each meeting twice would flatten strength of schedule toward .500.

    Default (the CUTOFF TOSS — seeding, district tiebreak, protection): the regular
    season only, every postseason phase excluded. `prestate=True` (the in-postseason
    recomputes: recovery-field seeding after Zonals, State seeding after Semi-State)
    additionally includes every completed pre-state stage — sectional/ward/regional/
    zonal and, once played, super_regional/semi_state — and still excludes state and
    the TOC.

    The mid-season SHOWCASES are IN, in both (`SHOWCASE_RATED`). A showcase dual is a
    real result against a program you would otherwise never play, and a different dual
    shape does not make it less real — it is exactly the cross-league edge an
    opponent-strength rating is starved of. `_flight_score` normalises per dual, so the
    1S/4D shape sits in the same table without being over- or under-counted."""
    drop = ("state", "toc") if prestate else POSTSEASON
    if not SHOWCASE_RATED:
        drop = tuple(drop) + SHOWCASE
    out = []
    for t in teams:
        for d in t.schedule:
            if not d.get("home") or d.get("phase") in drop:
                continue
            lines = []
            for ln in d.get("lines") or ():
                hg, ag = _games(ln.get("score", ""))
                lines.append({"slot": ln.get("slot", ""), "home_won": ln.get("home_won"),
                              "home_games": hg, "away_games": ag})
            out.append({"home": t.school.name, "away": d["opp"], "home_won": d["won"],
                        "home_points": d["pf"], "away_points": d["pa"], "lines": lines})
    return out


# --- format profile: 3S/4D regular season vs the mid-season 1S/4D SHOWCASES ----
# A team's regular season is played 3S/4D (owner rule 2027-08, swapped from the
# original 5S/2D); the mid-season showcases and the whole postseason are played
# 1S/4D. Doubles is 1.85 of 3.85 possible weighted points in the regular shape and
# up to 1.85 of 2.85 in the showcase/postseason shape — roughly 48% vs 65% of the
# dual. That gap is real but far narrower than it was pre-swap (the old 5S/2D
# regular card carried only 1.5 of 3.70, ~41%): the two shapes are now much closer
# in character, so this metric mostly measures how a team performs at ONE singles
# line and full doubles depth versus THREE singles lines and full doubles depth,
# not the old singles-vs-doubles flip. A team that lives off a deep #4-#9 doubles
# bench can still look different at the extra singles court the showcases drop to
# one — the showcases exist so that still shows up BEFORE State does.
#
# ‼️ DISPLAY ONLY, computed fresh every call off `t.schedule` — never archived, never
# read back into TOSS/ATR or any seeding decision. It works whether or not showcase
# results are ever folded into TOSS (`SHOWCASE_RATED`); that flag decides who plays
# whom, this decides what a coach or a reader sees about how they'll play. Takes a
# plain schedule (list of the same dicts `t.schedule` and `world.jhsaa_schedule` both
# already produce), so it reads a live season or an archived one without a wrapper.
def _weighted_lines(d: dict) -> tuple[float, float, float, float]:
    """(singles weighted won, singles weighted played, doubles weighted won, doubles
    weighted played) for ONE dual, from the schedule OWNER's side — `d["home"]` says
    whether they were the dual's home team, which is what a line's `home_won` is
    relative to."""
    sw = sp = dw = dp = 0.0
    is_home = bool(d.get("home"))
    for ln in d.get("lines") or ():
        slot = ln.get("slot", "")
        w = FLIGHT_WEIGHTS.get(slot)
        hw = ln.get("home_won")
        if w is None or hw is None:
            continue
        won = hw if is_home else not hw
        if slot.startswith("S"):
            sp += w; sw += w if won else 0.0
        elif slot.startswith("D"):
            dp += w; dw += w if won else 0.0
    return sw, sp, dw, dp


def _fmt_sample(schedule: list[dict], *, showcase: bool) -> list[dict]:
    """The 3S/4D regular-season duals (`showcase=False`) or the mid-season 1S/4D
    SHOWCASE duals (`showcase=True`) out of one team's schedule. The postseason plays
    1S/4D too but is deliberately excluded from both samples — it is the event these
    numbers exist to help a team prepare FOR, not more data to fold into the same
    average, and it has its own bracket-round display already.

    The early non-district window (`EARLY_FORMAT_PHASE`) is EXCLUDED from the regular
    sample too, for the same reason — it plays its own 5S/2D shape (the old regular-
    season card, pre-2027-08), not the 3S/4D card this metric means by "regular
    season". Folding it in would quietly average two different formats into one
    number and call it the team's regular-season baseline."""
    if showcase:
        return [d for d in schedule if d.get("phase") in SHOWCASE]
    return [d for d in schedule
            if d.get("phase") not in SHOWCASE and d.get("phase") not in POSTSEASON
            and d.get("phase") != EARLY_FORMAT_PHASE]


def _fmt_split(sample: list[dict]) -> dict:
    """One format sample, summarised. `weighted_pct` is the share of contested flight
    weight the team actually won — a truer margin than the dual W-L, since a 5-0 sweep
    and a 3-2 squeaker both just say "won" in the record. `doubles_win_share` is the
    share of the team's WEIGHTED WINS that came from doubles specifically — how much
    of this team's success in this sample is doubles-driven, which is the number that
    is expected to jump between the two formats."""
    if not sample:
        return {"n": 0, "wins": 0, "losses": 0, "weighted_pct": None,
                "doubles_win_share": None}
    wins = sum(1 for d in sample if d.get("won"))
    sw = sp = dw = dp = 0.0
    for d in sample:
        a, b, c, e = _weighted_lines(d)
        sw += a; sp += b; dw += c; dp += e
    total_w, total_p = sw + dw, sp + dp
    return {"n": len(sample), "wins": wins, "losses": len(sample) - wins,
            "weighted_pct": total_w / total_p if total_p else None,
            "doubles_win_share": dw / total_w if total_w else None}


def _fmt_delta(reg: dict, sc: dict, key: str) -> dict | None:
    """`sc[key] - reg[key]`, carrying the SHOWCASE sample's own `n` — `None` if the
    showcase sample can't support the comparison. A delta computed on n=1 is not a
    trend, it is one dual with a sign on it; every caller must show `n` beside it
    rather than the delta alone, so a coach doesn't read a single result as a pattern."""
    if not sc["n"] or reg[key] is None or sc[key] is None:
        return None
    return {"n": sc["n"], "delta": sc[key] - reg[key]}


#: How many showcase duals it takes before a difference is read at ~half its face
#: value. A showcase sample is 3-8 duals; at n=3 a raw difference is mostly noise —
#: the 8A table had an 18-18 team ranked 52nd posting the largest format swing in the
#: classification off four duals. Damping is the same shape `ladder_score` already
#: uses on a player's record: multiply by n/(n+k), so evidence has to accumulate
#: before the number moves. Nothing is hidden and no threshold is imposed; a thin
#: sample simply reads closer to "no difference", which is what it actually shows.
FORMAT_PRIOR = 4.0


def _damped(delta: float | None, n: int) -> float | None:
    """`delta` pulled toward 0 by how little evidence stands behind it."""
    if delta is None or not n:
        return None
    return delta * n / (n + FORMAT_PRIOR)


def _fmt_index(reg: dict, sc: dict, key: str) -> dict | None:
    """A normalized 100-baseline index — the ERA+/OPS+ shape, not a difference. `100`
    means the showcase sample matched the team's own regular-season `key` exactly;
    above 100 means MORE of it under the showcase's 1S/4D card, below means less.
    `None` if the showcase sample can't support the comparison OR the regular-season
    baseline is exactly zero (a ratio to a zero baseline is undefined, the same
    reason a 0.00 ERA can't produce a real ERA+ either — showing a dash beats a
    fabricated infinity).

    Ratio, not delta, on purpose: a baseball rate stat isn't indexed by subtracting
    the league average, it's indexed by DIVIDING by it, so a below-average player
    reads as "80% of league average" rather than "-.020 points" — this is that
    convention applied to a team's own regular season as its baseline instead of the
    league's. Like `_fmt_delta`, a caller must show `n` beside it; one showcase dual
    is not a sample size an index should be read as a trend from."""
    if not sc["n"] or not reg.get(key) or sc[key] is None:
        return None
    return {"n": sc["n"], "index": round(100 * sc[key] / reg[key])}


def _fmt_volatility(sample: list[dict]) -> dict | None:
    """How much a team's weighted win share swings dual to dual within one sample —
    the standard deviation of per-dual weighted win share. 1S/4D is five contested
    points instead of nine, so one line flipping swings a much larger share of a
    showcase dual than of a regular-season one; this is what shows that up. `None`
    under two duals — a spread needs at least two points to mean anything."""
    margins = []
    for d in sample:
        sw, sp, dw, dp = _weighted_lines(d)
        played = sp + dp
        if played:
            margins.append((sw + dw) / played)
    if len(margins) < 2:
        return None
    mean = sum(margins) / len(margins)
    var = sum((x - mean) ** 2 for x in margins) / len(margins)
    return {"n": len(margins), "stdev": var ** 0.5}


def format_profile(schedule: list[dict]) -> dict:
    """A team's format-transition profile, comparing its 3S/4D regular season against
    its mid-season 1S/4D SHOWCASES: `regular` / `showcase` (`_fmt_split`, each with its
    own `n`), `shift` (`_fmt_delta` on `weighted_pct` — a plus/minus MARGIN swing, the
    "temperature" reading), `doubles_index` (`_fmt_index` on `doubles_win_share` — an
    ERA+/OPS+-style 100-baseline RATIO, not a delta: 100 is the team's own regular
    season, above/below is more/less doubles-driven under 1S/4D), and
    `regular_volatility` / `showcase_volatility` (`_fmt_volatility`). Every number
    that can be computed on a thin sample carries its own `n`; a caller must show it,
    not hide behind a lone number.

    Read-only and archives nothing — see the module note above. Callable on a live
    `TeamSeason.schedule` or on `world.jhsaa_schedule(...)`'s archived rows; both are
    the same dict shape."""
    reg, sc = _fmt_sample(schedule, showcase=False), _fmt_sample(schedule, showcase=True)
    r, s = _fmt_split(reg), _fmt_split(sc)
    return {"regular": r, "showcase": s,
            "shift": _fmt_delta(r, s, "weighted_pct"),
            # The doubles reading as a SIGNED DIFFERENCE beside the ratio index. Both
            # describe the same thing; the difference is the one a reader can state
            # ("doubles carries six points more of the win under 1S/4D") and the ratio
            # is the one nobody could ("Dbl+ 155").
            "doubles_shift": _fmt_delta(r, s, "doubles_win_share"),
            "doubles_index": _fmt_index(r, s, "doubles_win_share"),
            "regular_volatility": _fmt_volatility(reg),
            "showcase_volatility": _fmt_volatility(sc)}


def _flat_format_profile(schedule: list[dict]) -> dict:
    """`format_profile`, flattened to the plain numeric fields a standings row can
    carry (JSON, sortable, no nested dicts): `sc_n` / `sc_pct` (the showcase sample and
    its weighted win share, 0-1 — the rankings page scales this to a 0-10 SC RATING for
    display), `fmt_shift` (the margin delta, `None` under one showcase dual — displayed
    as a temperature gauge), `dbl_plus` (the ERA+/OPS+-style 100-baseline doubles index,
    `None` under one showcase dual OR a zero regular-season baseline), `sc_stdev`
    (showcase volatility, `None` under two). Missing keys read back as `None` through
    `.get`, exactly like a pre-ATR season's `atr`."""
    p = format_profile(schedule)
    n = p["showcase"]["n"]
    return {"sc_n": n, "sc_pct": p["showcase"]["weighted_pct"],
            "fmt_shift": (p["shift"] or {}).get("delta"),
            "dbl_shift": (p["doubles_shift"] or {}).get("delta"),
            "dbl_plus": (p["doubles_index"] or {}).get("index"),
            "sc_stdev": (p["showcase_volatility"] or {}).get("stdev"),
            # What the RANKINGS TABLE shows: both readings damped by sample size and
            # centred on 0, so the column means "what the format does to this team"
            # rather than "how well it happened to do in three duals".
            "fmt_pts": _damped((p["shift"] or {}).get("delta"), n),
            "dbl_pts": _damped((p["doubles_shift"] or {}).get("delta"), n)}


def power_index(teams, *, prestate: bool = False) -> dict:
    """Power Index for every program in a gender, keyed by school name.

    Run over the WHOLE gender rather than a classification at a time: non-district
    play crosses classifications, so a 7A team's schedule strength depends on the 6A
    teams it played, and rating each class in isolation would cut those edges out of
    the results graph. `prestate=True` is the in-postseason recompute — same graph
    plus every completed pre-state match (see `rating_duals`)."""
    from .rating import compute_ratings
    return compute_ratings(rating_duals(teams, prestate=prestate),
                           weights=FLIGHT_WEIGHTS)


def _power_key(power: dict | None):
    """Sort key factory: Power Index order when we have one (`power`, from
    `power_index`), win rate for a caller running a district in isolation. Shared by
    every postseason-field function so protected/unprotected/seed order all agree."""
    def key(t: TeamSeason):
        if power is not None and t.school.name in power:
            return (-power[t.school.name].pi_raw, t.school.name)
        return (-t.win_pct, -(t.points_for - t.points_against), t.school.name)
    return key


def sectional_field(group: str, standings: dict[str, list[TeamSeason]],
                     power: dict | None = None
                     ) -> tuple[list[TeamSeason], list[TeamSeason]]:
    """(protected, entrants) for `group` — every program in the classification.

    Protected (`PROTECTED` seats, enter at Regionals): district champions
    first, then the best remaining cutoff TOSS until the seats are filled. Everyone
    else enters Sectionals. Both lists come back cutoff-TOSS ordered."""
    key = _power_key(power)
    champs = sorted((ts[0] for ts in standings.values() if ts), key=key)
    rest = sorted((t for ts in standings.values() for t in ts[1:]), key=key)
    fill = max(0, PROTECTED - len(champs))
    protected = sorted(champs + rest[:fill], key=key)
    return protected, rest[fill:]


def _elim_round(pool: list[TeamSeason], byes: int, *, rng: random.Random,
                 phase: str) -> tuple[list[TeamSeason], list[dict]]:
    """One round of single elimination over `pool` (already strength-ordered,
    strongest first, e.g. by `_power_key`): the top `byes` entries advance without
    playing, and the rest pair strongest-vs-weakest among THEMSELVES and every match
    is actually played. Returns (survivors, games) — survivors strength-ordered
    (byes first, then winners in the order their matches were seeded), ready to feed
    the next round or seed the next stage."""
    protected, playing = pool[:byes], pool[byes:]
    games, winners = [], []
    n = len(playing)
    for i in range(n // 2):
        a, b = playing[i], playing[n - 1 - i]
        res = play_dual(a, b, seed=rng.randrange(1 << 30), phase=phase)
        win = a if res.winner == 0 else b
        games.append({"home": a.school.name, "away": b.school.name,
                      "home_points": res.home_points, "away_points": res.away_points,
                      "winner": win.school.name})
        winners.append(win)
    return protected + winners, games


def run_sectional(entrants: list[TeamSeason], target: int, *, seed: int
                  ) -> tuple[dict, list[TeamSeason]]:
    """Reduce `entrants` (cutoff-TOSS ordered) to EXACTLY `target` survivors — the
    Ward field — via real single-elimination duals (phase "sectional").

    Flexible by design: ordinary rounds halve the field (a bye only to fix an odd
    remainder); once halving would overshoot below `target`, the final round trims
    precisely (`byes = 2*target - size`, byes to the top seeds). 48 entrants →
    16 byes, 16 matches, 32 out; 57 → 7 byes, 25 matches, 32 out. This is the only
    stage where byes exist.

    When the stage needs more than one round, the rounds before the last are
    called AREAS (owner rule) — the final round is always the one named
    Sectionals.

    Returns (archive_dict, survivors): the JSON-safe `{field, rounds, survivors,
    round_names}` for the archive, and the live `TeamSeason` list for Wards."""
    rng = random.Random(seed)
    cur = list(entrants)
    rounds = []
    while len(cur) > target:
        size = len(cur)
        byes = size % 2 if size // 2 >= target else 2 * target - size
        cur, games = _elim_round(cur, byes, rng=rng, phase="sectional")
        rounds.append(games)
    names = ["Areas"] * (len(rounds) - 1) + ["Sectionals"] if rounds else []
    # Every dual is a numbered UNIT within its class and gender (owner rule) —
    # "7A Boys Area 1", "Section 1" — restarting at 1 for each classification,
    # never numbered across the state, so each one can be identified.
    for i, games in enumerate(rounds):
        prefix = "Area" if i < len(rounds) - 1 else "Section"
        for j, gm in enumerate(games):
            gm["unit"] = f"{prefix} {j + 1}"
    return ({"field": [t.school.name for t in entrants], "rounds": rounds,
            "survivors": [t.school.name for t in cur],
            "round_names": names}, cur)


_STAGE_NAMES = {"ward": "Wards", "regional": "Regionals", "zonal": "Zonals"}


def run_rounds(field: list[TeamSeason], phases: tuple[str, ...], *, seed: int
               ) -> tuple[dict, list[TeamSeason]]:
    """A seeded draw played for `len(phases)` rounds — one phase per round,
    positional between rounds (no reseeding). `field` is a power of two in normal
    play, so every round halves it exactly and nobody gets a bye. Used for Wards
    (one round) and Regionals+Zonals (two rounds of one 32-draw).

    Returns (archive_dict, survivors) like `run_sectional`.

    ‼️ AN EMPTY FIELD RAISES, LOUDLY. `size` starts at 1, so a field of 0 (or 1)
    produced a one-slot draw and the pairing loop read `slots[i + 1]` off the end:
    a bare `IndexError: list index out of range` twenty frames down, naming
    neither the classification nor the stage. It means the ladder was fed nothing
    — a pool at or below `PROTECTED` leaves Sectionals no entrants at all — which
    is a broken pool, not a format to accommodate (the no-scaling rule), so the
    caller must stop with something it can act on."""
    if len(field) < 2:
        raise RuntimeError(
            f"JHSAA {phases[0]}: field of {len(field)} — the ladder was fed an "
            f"empty or single-team pool. A classification with no more than "
            f"PROTECTED ({PROTECTED}) programs leaves Sectionals no entrants.")
    rng = random.Random(seed)
    size = 1
    while size < len(field):
        size *= 2
    from engine.tournament import seeded_draw
    slots: list[TeamSeason | None] = [None if r is None else field[r]
                                      for r in seeded_draw(len(field), size,
                                                           len(field), rng)]
    rounds = []
    for phase in phases:
        nxt, games = [], []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None or b is None:
                nxt.append(a or b)
                continue
            res = play_dual(a, b, seed=rng.randrange(1 << 30), phase=phase)
            win = a if res.winner == 0 else b
            # The numbered UNIT within its class and gender (owner rule): Wards
            # and Regionals count from 1, Zonals letter A, B, C…
            n = len(games)
            unit = (f"Zonal {chr(65 + n)}" if phase == "zonal"
                    else f"{_STAGE_NAMES[phase][:-1]} {n + 1}")
            games.append({"home": a.school.name, "away": b.school.name,
                          "home_points": res.home_points, "away_points": res.away_points,
                          "winner": win.school.name, "unit": unit})
            nxt.append(win)
        rounds.append(games)
        slots = nxt
    survivors = [t for t in slots if t is not None]
    return ({"field": [t.school.name for t in field], "rounds": rounds,
             "survivors": [t.school.name for t in survivors],
             "round_names": [_STAGE_NAMES[p] for p in phases]}, survivors)


# --- the RECOVERY ROUNDS (owner rule 2027-08): Super Regionals -> Semi-State ---

# ⚠️ DIVISIONAL_NAME is the only place the round is named; change it here and
# every surface follows. PLURAL and no "Round" — the stage headings read
# "7A Areas", "7A Wards", "7A Super Regionals", so "7A Divisionals" matches and
# "7A Divisional Round" did not (owner, 2027-08). The per-dual UNIT keeps the
# singular "Division N", the same way a Ward dual sits in "Ward 4".
DIVISIONAL_NAME = "Divisionals"
#: The CONDITIONAL last rung (owner rule 2027-08). Divisionals fills every berth
#: on the current membership, but `berths` moves with the district-champion count
#: and with the association's size, so a year that comes up short must not ship a
#: short State field. The CONFERENCE round pairs the best-TOSS DIVISIONAL LOSERS
#: against the best-qualified DISTRICT LOSERS (owner rule 2027-08) — the only
#: recovery round drawn from two pools and paired across them. In the owner's
#: words, "it can be like other rounds where if we don't need it, it doesn't
#: trigger": it convenes only when berths remain, exactly the way the Divisional
#: round already declines to convene at `L = 0`. On today's membership it never
#: fires in either gender, which is the intended resting state, not dead code.
#: ‼️ ATR — AVERAGE TEAM RATING (owner metric 2027-08). TOSS blended with win
#: percentage, and the ONE place the association rates a team on anything but
#: TOSS. TOSS is an opponent-strength composite, so a middling team in a brutal
#: district is propped up by the company it keeps while a 20-win season against
#: an ordinary schedule rates below it. That trade is right for SEEDING a draw
#: and wrong for the last seat in the tournament: "i'd take a 18-20+ win team
#: regardless of schedule strength if they win a post-season game of consequence
#: over a middling team in a hard district propped in TOSS by their opponents."
#: Both terms are already 0-1, so the blend is a straight weighted mean.
ATR_TOSS_WEIGHT = 0.5


def atr_of(pi: float, win_pct: float) -> float:
    """ATR from its two raw terms — the ONE formula, so the number archived on a
    standings row and the number the Conference pool is ranked on cannot drift."""
    return ATR_TOSS_WEIGHT * pi + (1.0 - ATR_TOSS_WEIGHT) * win_pct


def atr(team: TeamSeason, power: dict | None) -> float:
    """The Average Team Rating: `ATR_TOSS_WEIGHT` TOSS + the rest win percentage.

    `power` maps school -> `rating.RatingLine`, so the TOSS term is `pi_raw` —
    the SAME full-precision value the seeds are drawn from (`_power_key`), never
    a rounded or re-derived one. A team the rating does not know contributes its
    win percentage alone rather than defaulting to a zero it did not earn."""
    line = (power or {}).get(team.school.name)
    if line is None:
        return team.win_pct
    return atr_of(line.pi_raw, team.win_pct)


def _atr_key(power: dict):
    """Sort key: best ATR first, school name breaking ties (never a raw float
    comparison on equal ratings — the order has to be reproducible)."""
    return lambda t: (-atr(t, power), t.school.name)


CONFERENCE_NAME = "Conference"
#: ‼️ THE SEMI-CONFERENCE — the qualifying round in front of the Conference (owner
#: rule 2027-08). The Conference awards the single largest block of berths in
#: recovery (14 of 40 in a 40-field class), and 22 of its 28 entrants used to walk in
#: off a loss having played NO recovery dual at all, level with Divisional losers who
#: had fought through three rounds. Owner: Ward teams "should have to play a qualify
#: match rather than giving the teams direct access when other teams will have played
#: several matches where they've gotten wins before making it to that round."
#:
#: So everyone except the Divisional losers now qualifies for the Conference on court.
#: It is deliberately NOT the retired Ward-playback rule: it grants ZERO extra bites
#: at a berth (the Conference is still the only berth-bearing round these teams see),
#: only one extra dual to earn the seat. Byeless like every recovery round, and
#: conditional on the same trigger as the Conference — dormant wherever the ladder's
#: own losers already fill the field (the 24-field classes).
SEMI_CONFERENCE_NAME = "Semi-Conference"
_RECOVERY_NAMES = {"super_regional": "Super Regionals", "semi_state": "Semi-State",
                   "divisional": DIVISIONAL_NAME,
                   "semi_conference": SEMI_CONFERENCE_NAME,
                   "conference": CONFERENCE_NAME}
_RECOVERY_UNITS = {"super_regional": "Super Regional", "semi_state": "Semi-State",
                   "divisional": "Division",
                   "semi_conference": SEMI_CONFERENCE_NAME,
                   "conference": "Conference"}


def renumber_divisions(season: dict, start: int = 1) -> int:
    """Number this gender's Divisions and return the next number.

    ‼️ DIVISIONS ARE NUMBERED STATEWIDE, not within a classification (owner rule
    2027-08) — every other unit counts inside its own class ("Region IX" exists
    once per classification), but there is exactly one Division 1 in Jefferson
    each year. The sequence runs **girls first, then boys**, and **bottom-up by
    classification** (1A up to 9A), continuing across both, so 1A girls hold
    Division 1 and the highest number lands on 9A boys — "(9A) Division 11", if
    the state played that many that year. How many there are
    depends on how many Divisional duals the berths actually require, which
    varies by year, so the numbers are assigned here — once both genders are
    known — rather than inside the round that plays them.

    Idempotent: the number is always recomputed and overwritten, so re-running
    against a memoised season cannot double-count."""
    n = start
    # Bottom-up, DELIBERATELY: reversed(GROUPS) runs Division 2, Division 1,
    # then 1A up to 9A — the Great Basin pair (appended after 1A) leads the
    # sequence as the "newest/smallest" block. Any deterministic documented
    # order satisfies the invariant; this is the one we ship. (The unit label
    # "Division {n}" renders as ROMAN numerals on honours chips via
    # `world._unit_honour` — "Division XI" — so it stays visually distinct from
    # the GROUP names "Division 1"/"Division 2", which keep arabic digits.)
    for g in reversed(GROUPS):
        dv = ((season.get("groups") or {}).get(g) or {}).get("divisional") or {}
        for games in dv.get("rounds") or ():
            for gm in games:
                gm["unit"] = f"Division {n}"
                n += 1
    return n


def _rev_letters(i: int) -> str:
    """The i-th label of the reverse alphabet, 0-based: Z, Y … A, then ZZ, ZY …
    (bijective base-26 on the reversed alphabet, so letters NEVER recycle however
    many Conferences a year needs — full size plays ~140)."""
    i += 1
    out = ""
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(ord("Z") - r) + out
    return out


def reletter_conferences(season: dict, start: int = 0) -> int:
    """Letter this gender's Conferences and return the next index.

    ‼️ CONFERENCES ARE LETTERED STATEWIDE, BACKWARDS FROM Z (owner rule 2027-08),
    and the unit carries its OWN classification: "6A-Z Conference", "6A-Y
    Conference"… Like the Divisions the count is statewide — letters are never
    recycled across classifications — and the sequence runs the same order:
    girls first, then boys, classifications bottom-up (1A → 9A). Z opening
    the sequence instead of A is the point: the Conference is the LAST rung, and
    its labels read like it. Past A the sequence doubles (ZZ, ZY, …) rather than
    recycling. Assigned here, after both genders are known, for the Divisions'
    reason exactly; idempotent the same way (always recomputed, memoised season
    safe)."""
    n = start
    for g in reversed(GROUPS):        # Division 2, Division 1, then 1A up to 9A
        cf = ((season.get("groups") or {}).get(g) or {}).get("conference") or {}
        for games in cf.get("rounds") or ():
            for gm in games:
                gm["unit"] = f"{g}-{_rev_letters(n)} Conference"
                n += 1
    return n


def _losers(stage: dict, round_ix: int) -> list[str]:
    """School names eliminated in round `round_ix` of an archived stage dict."""
    out = []
    for gm in (stage.get("rounds") or [[]] * (round_ix + 1))[round_ix]:
        out.append(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
    return out


def _last_opponent(ts: TeamSeason) -> str:
    return ts.schedule[-1]["opp"] if ts.schedule else ""


def _pair_penalty(a: TeamSeason, b: TeamSeason) -> int:
    """How bad a recovery pairing is: replaying the opponent that JUST eliminated
    you is the hard rule; a same-league pairing is a soft preference."""
    p = 0
    if _last_opponent(a) == b.school.name or _last_opponent(b) == a.school.name:
        p += 10                                        # the just-played opponent
    if (a.school.group, a.school.district) == (b.school.group, b.school.district):
        p += 1                                         # same league, if avoidable
    return p


def _recovery_pairs(playing: list[TeamSeason], rng: random.Random) -> list[tuple]:
    """Pair a recovery round's playing set, strongest-vs-weakest — then repair
    the draw around the owner's rematch rule. A handful of swap passes over the
    bottom half is enough at these sizes; TOSS order is otherwise preserved."""
    n = len(playing)
    # Small sets get an EXACT answer: a tight must-play round leaves the greedy
    # repair no room (offenders survived in every class), and a perfect
    # matching over <=8 teams is at most 105 candidates. Score = total penalty,
    # then closeness to the strongest-vs-weakest ideal.
    if 2 <= n <= 8:
        import itertools
        rank = {t.school.name: i for i, t in enumerate(playing)}
        def matchings(items):
            if not items:
                yield []
                return
            a = items[0]
            for k in range(1, len(items)):
                rest = items[1:k] + items[k + 1:]
                for m in matchings(rest):
                    yield [(a, items[k])] + m
        ideal = {i: n - 1 - i for i in range(n)}
        best, best_key = None, None
        for m in matchings(list(playing)):
            pen = sum(_pair_penalty(x, y) for x, y in m)
            drift = sum(abs(ideal[rank[x.school.name]] - rank[y.school.name])
                        for x, y in m)
            key = (pen, drift)
            if best_key is None or key < best_key:
                best, best_key = m, key
        return best
    top, bottom = playing[:n // 2], list(reversed(playing[n - n // 2:]))
    for _ in range(4):
        improved = False
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                cur = _pair_penalty(top[i], bottom[i]) + _pair_penalty(top[j], bottom[j])
                alt = _pair_penalty(top[i], bottom[j]) + _pair_penalty(top[j], bottom[i])
                if alt < cur:
                    bottom[i], bottom[j] = bottom[j], bottom[i]
                    improved = True
        if not improved:
            break
    # Last resort for a HARD rematch the bottom-half swaps cannot reach (small
    # pools under a tight must-play set leave them no room): break the
    # strongest-vs-weakest partition for exactly the pair that needs it.
    for i in range(len(top)):
        if _pair_penalty(top[i], bottom[i]) >= 10:
            for j in range(len(top)):
                if i == j:
                    continue
                cur = _pair_penalty(top[i], bottom[i]) + _pair_penalty(top[j], bottom[j])
                alt = _pair_penalty(top[i], top[j]) + _pair_penalty(bottom[i], bottom[j])
                if alt < cur:
                    top[j], bottom[i] = bottom[i], top[j]
                    break
    return list(zip(top, bottom))


def _recovery_round(pool: list[TeamSeason], *, phase: str,
                    rng: random.Random) -> tuple[dict, list[TeamSeason]]:
    """One recovery round: pair the WHOLE field and return the winners.

    ‼️ NO BYES IN RECOVERY (owner rule 2027-08, and the point of the whole
    design): "my goal is ultimately to keep people from earning their way to
    state with a bye — basically that's what I don't want." Three separate
    reports were the same bug wearing different hats, because the rounds used
    to be CUTS sized to whatever the pool happened to be, which left byes over.
    A round now plays every team in its field, so a bye is not something the
    rules forbid — it is something that cannot occur. `_recovery` sizes the
    pools even and lets the DIVISIONAL round absorb the leftover berths.

    An odd field is the one thing that would force a bye, so `_recovery` never
    passes one; the assertion says so rather than silently sitting somebody."""
    if len(pool) % 2:
        raise RuntimeError(
            f"JHSAA {phase}: odd field ({len(pool)}) would force a bye — "
            f"`_recovery` must size every recovery field even.")
    games, winners = [], []
    for n, (a, b) in enumerate(_recovery_pairs(pool, rng)):
        res = play_dual(a, b, seed=rng.randrange(1 << 30), phase=phase)
        win = a if res.winner == 0 else b
        games.append({"home": a.school.name, "away": b.school.name,
                      "home_points": res.home_points, "away_points": res.away_points,
                      "winner": win.school.name,
                      "unit": f"{_RECOVERY_UNITS[phase]} {n + 1}"})
        winners.append(win)
    return ({"field": [t.school.name for t in pool], "rounds": [games],
             "survivors": [t.school.name for t in winners],
             "round_names": [_RECOVERY_NAMES[phase]]}, winners)


def _recovery(group: str, by_name: dict, sectionals: dict, wards: dict,
              prestate: dict, zonal_champs: list, district_champs: list[str],
              power: dict, *,
              seed: int) -> tuple[dict, dict, dict, dict, dict,
                                  list, list[str], dict]:
    """The whole recovery path for one group: who still needs a berth, who gets
    another chance, and the FOUR rounds that decide it.

    Returns (super_regional, semi_state, divisional, semi_conference, conference,
    qualifiers, district_qualifiers, atr_used).

    ‼️ NOBODY REACHES STATE ON A BYE (owner rule 2027-08 — the goal the whole
    design serves). Every recovery round pairs its ENTIRE field, so a bye is
    structurally impossible rather than merely disallowed; the DIVISIONAL
    round exists to absorb the berths that would otherwise have to be handed
    out as byes, and it fixes a real inequity at the same time. A Regional
    loser used to get Super Regionals plus a readmission; a Zonal loser — a
    BETTER team, it got further — entered at Semi-State, lost once and was
    out. Now everyone in recovery gets two live chances.

    The shape, all of it byeless:

        Super Regionals   P teams (even)          -> P/2 winners
        Semi-State        S = P/2 + Z + readmits  -> S/2 winners  (berths)
        Divisionals       2L best Semi-State losers      -> L winners  (berths)
        Semi-Conference   2B bodies                      -> B winners  (no berths)
        Conference        Divisional losers + those B    -> berths     (berths)

    with `L = berths - S/2`, which forces `4*berths/3 <= S <= 2*berths`. Bodies
    are found in preference order — readmitted Super Regional LOSERS first
    (the best-qualified pool left, and they already fought through Regionals),
    then a walk back down the ladder through Ward, Sectional and Area losers,
    best TOSS within each tier. A body is a chance to PLAY, never a berth.
    """
    # ‼️ THERE IS NO DISTRICT GUARANTEE — YOU WIN YOUR WAY INTO THE FIELD (owner
    # rule 2027-08, REVERSING the earlier guarantee). Winning a district buys a
    # PROTECTED seat (entry at Regionals, skipping Sectionals and Wards) and
    # nothing else: it is access to the ladder, not access to State. The old rule
    # let a district champion lose at Regionals, lose again, and still be handed a
    # berth — "a district champion could keep losing and automatically get into
    # the field at state, and that's not what I want at all." So a district
    # champion that loses now falls into the SAME recovery pools as everybody
    # else and earns its berth on court, or does not go.
    #
    # `district_qualifiers` is kept in the return and the archive as an EMPTY
    # list: seasons archived under the guarantee still carry their names, and
    # every reader (`jhsaa_postseason_result`, the ledger chip) already handles
    # the key, so retiring the rule does not have to rewrite history.
    district_qualifiers: list[str] = []
    berths = max(0, state_field_size(group) - len(zonal_champs))
    reg_losers = [by_name[n] for n in _losers(prestate, 0)]
    zon_losers = [by_name[n] for n in _losers(prestate, 1)]
    # Walk back down the ladder for bodies: Ward, then Sectional, then Area
    # losers, best TOSS within each tier, tiers consumed nearest-round first.
    sec_rounds = sectionals.get("rounds") or []
    tiers = [_losers(wards, 0)]
    for ix in range(len(sec_rounds) - 1, -1, -1):     # Sectionals, then Areas
        tiers.append(_losers(sectionals, ix))
    taken = {t.school.name for t in reg_losers} | {t.school.name for t in zon_losers}
    bodies: list[TeamSeason] = []
    for tier in tiers:
        pick = sorted((by_name[n] for n in tier
                       if n in by_name and n not in taken),
                      key=_power_key(power))
        bodies += pick
        taken |= {t.school.name for t in pick}
    # ‼️ `bodies` STARTS AT WARDS, which is exactly why it cannot be the whole
    # Semi-Conference pool: `taken` excludes every Regional and Zonal loser, so a
    # team the ladder dropped LATER than a Ward loser is in no tier at all and can
    # be walked straight past. The two orphan tiers that belong ahead of it —
    # Semi-State losers the Divisionals did not take, and Super Regional losers
    # Semi-State did not readmit — are assembled below, where those rounds are
    # actually played. See `_sc_tiers`.

    # ‼️ NO WARD PLAYBACKS (owner rule 2027-08). Ward losers used to be drafted
    # into the Super Regional pool as bodies, which handed them TWO OR THREE bites
    # — Super Regionals, then a readmission to Semi-State, then Divisionals — while
    # a Zonal loser got one. They now enter at CONFERENCE and nowhere else: one
    # last shot, as the true last-resort clubs they are, and berths stop being
    # earned off them in the earlier rounds. Recovery proper is the ladder's OWN
    # losers.
    z = len(zon_losers)
    need = -(-4 * berths // 3)                  # ceil(4*berths/3): the S floor
    need += need % 2                            # ...and Semi-State is byeless, so EVEN
    # ‼️ ROUND THE FLOOR TO EVEN BEFORE SIZING THE RESERVOIR, not after. Semi-State
    # pairs its whole field, so an odd floor is really the next even number — but
    # the pool below is grown only until `P + z` reaches the floor, and the window
    # is then capped by exactly that (`len(ss_pool) + len(sr_losers)` IS `P + z`).
    # Rounding afterwards therefore asked for one pair more than had been gathered,
    # the cap refused it, and the odd-drop took a pair back off: measured at full
    # size, 4A wanted a 39 window, got 38, and finished ONE berth short of a 40
    # field with every other classification full. An odd floor is the only case,
    # which is why it went unseen for so long.
    # P must reach the floor even after readmitting every Super Regional loser
    # (max S = P + z), and must be even so Super Regionals is byeless.
    sr_pool = sorted(reg_losers, key=_power_key(power))
    if len(sr_pool) % 2:                        # reservoir dry: the weakest sits out
        sr_pool = sr_pool[:-1]
    rng = random.Random(seed)
    sr_arc, sr_winners = _recovery_round(sr_pool, phase="super_regional", rng=rng)

    # Semi-State: winners + Zonal losers + as many readmitted Super Regional
    # losers as the window needs, sized EVEN.
    won = {id(t) for t in sr_winners}
    sr_losers = sorted((t for t in sr_pool if id(t) not in won), key=_power_key(power))
    ss_pool = list(sr_winners) + zon_losers
    target = max(need, len(ss_pool))
    target = min(target, 2 * berths, len(ss_pool) + len(sr_losers))
    if target % 2:
        target += 1
    while sr_losers and len(ss_pool) < target:
        ss_pool.append(sr_losers.pop(0))
    if len(ss_pool) % 2:
        ss_pool = ss_pool[:-1] if len(ss_pool) > 2 * berths - len(ss_pool) else ss_pool
    ss_pool = sorted(ss_pool, key=_power_key(power))
    if len(ss_pool) % 2:                        # still odd: drop the weakest
        ss_pool = ss_pool[:-1]
    ss_arc, ss_winners = _recovery_round(ss_pool, phase="semi_state", rng=rng)

    # Divisionals: the berths Semi-State could not fill, contested by the best
    # Semi-State losers. `L = 0` is legal and means the round did not convene.
    ss_won = {id(t) for t in ss_winners}
    ss_losers = sorted((t for t in ss_pool if id(t) not in ss_won),
                       key=_power_key(power))
    dv_n = max(0, berths - len(ss_winners))
    dv_pool = ss_losers[:2 * dv_n]
    if len(dv_pool) % 2:
        dv_pool = dv_pool[:-1]
    if dv_pool:
        dv_arc, dv_winners = _recovery_round(dv_pool, phase="divisional", rng=rng)
    else:
        dv_arc, dv_winners = {"field": [], "rounds": [[]], "survivors": [],
                              "round_names": [_RECOVERY_NAMES["divisional"]]}, []
    qualifiers = list(ss_winners) + list(dv_winners)

    # ‼️ THE CONFERENCE ROUND — the last rung, and the one that fills every berth
    # the ladder's own losers could not (owner rule 2027-08). It is ONE POOL,
    # reseeded and paired like every other recovery round.
    #
    # ‼️ ONLY DIVISIONAL LOSERS ENTER IT DIRECTLY (owner rule 2027-08). They fought
    # to the last berth-bearing round; everybody else qualifies for it on court, in
    # the SEMI-CONFERENCE below. The Conference used to admit its whole pool
    # directly, so 22 of 28 entrants in a 40-field class walked in off a loss
    # having played no recovery dual at all, level with teams that had won one —
    # and it awards the largest single block of berths in recovery.
    #
    # ‼️ RANKED ON ATR, NOT TOSS — the only place in the association that is
    # true. The last seat should reward a 20-win season, not a middling team a
    # hard district propped up in an opponent-strength composite.
    #
    # It convenes ONLY when berths remain — "if we don't need it, it doesn't
    # trigger" — and takes twice the outstanding berths so every entrant plays
    # exactly once and exactly that many winners come out. Byeless like the rest.
    cf_n = max(0, berths - len(qualifiers))
    cf_seats = 2 * cf_n
    dv_won = {id(t) for t in dv_winners}
    placed = ({t.school.name for t in qualifiers}
              | {t.school.name for t in zonal_champs})
    seen: set[str] = set()

    def _rank(tier, out: list) -> None:
        """Append `tier`'s unplaced teams to `out`, best ATR first. Membership is
        strict tier priority; ATR only orders WITHIN a tier."""
        for t in sorted(tier, key=_atr_key(power)):
            if t.school.name in placed or t.school.name in seen:
                continue
            seen.add(t.school.name)
            out.append(t)

    cf_direct: list[TeamSeason] = []
    _rank([t for t in dv_pool if id(t) not in dv_won], cf_direct)
    cf_direct = cf_direct[:cf_seats]

    # ‼️ THE SEMI-CONFERENCE POOL — district champions first, then the ladder walked
    # back IN ROUND ORDER, and a survivor of a later round is never skipped.
    #   1. DISTRICT CHAMPIONS still outside the field — what is left of the retired
    #      guarantee: a district title earns you ONE more dual, not a berth.
    #   2. SEMI-STATE LOSERS the Divisionals did not take, then
    #   3. SUPER REGIONAL LOSERS Semi-State did not readmit. Both are usually empty
    #      (the Divisionals take every Semi-State loser and Semi-State readmits
    #      every Super Regional loser at full size) — but not always, and until now
    #      they were in NO tier: `bodies` starts at Wards and `taken` excludes every
    #      Regional and Zonal loser, so an orphan could never re-enter while a Ward
    #      loser walked past it. It is live in the 24-field classes already, where
    #      the Divisionals take 10 of 11 Semi-State losers; it goes unseen only
    #      because those classes never convene a Conference for the orphan to enter.
    #      They also belong ahead on merit: an orphan has had ONE berth-bearing
    #      round where a Divisional loser had two, and a Ward loser has had none.
    #   4-6. the top WARD, then Sectional, then Area losers — the true last-resort
    #      clubs, and the reason this round exists.
    sc_rank: list[TeamSeason] = []
    for tier in ([by_name[n] for n in district_champs if n in by_name],
                 ss_losers[len(dv_pool):],
                 list(sr_losers),
                 bodies):
        _rank(tier, sc_rank)

    # ‼️ SNAPSHOT THE ATR THAT RANKED THESE POOLS, at this moment. `t.power` is the
    # regular-season stamp and `t.win_pct` keeps moving until the last state dual,
    # so re-deriving ATR on read gives a number that did not select anybody — the
    # archived-not-recomputed rule the Power Index already follows, and it binds
    # harder here because these ARE the ranks the rounds were built from.
    atr_used = {t.school.name: atr(t, power) for t in by_name.values()}

    # Body seats, and how many of them the Semi-Conference can contest. With a
    # healthy reservoir every body plays in (`sc_n == body_seats`, `sc_head` empty).
    # ‼️ `sc_head` IS A DEGRADATION PATH, NOT A PRIVILEGE TIER. A class whose
    # reservoir cannot fill `2 * body_seats` would otherwise ship a short State
    # field, which the format does not allow, so the best-ATR surplus is admitted
    # directly and the rest play for what is left. It should never fire: the
    # reservoir is a DATA invariant (`sponsor_floor`, reported per class-gender by
    # `scripts/jhsaa_reclassify.py`), which is why a non-empty head is logged as
    # loudly as an unfilled field.
    body_seats = max(0, cf_seats - len(cf_direct))
    sc_field = _even(min(2 * body_seats, 2 * max(0, len(sc_rank) - body_seats)))
    sc_head = sc_rank[:body_seats - sc_field // 2]
    sc_pool = sc_rank[len(sc_head):len(sc_head) + sc_field]
    if cf_n and sc_pool:
        sc_pool = sorted(sc_pool, key=_atr_key(power))
        sc_arc, sc_winners = _recovery_round(sc_pool, phase="semi_conference",
                                             rng=rng)
    else:
        sc_arc, sc_winners = {"field": [], "rounds": [[]], "survivors": [],
                              "round_names": [_RECOVERY_NAMES["semi_conference"]]}, []
    if cf_n and sc_head:
        log.warning("JHSAA %s semi-conference short: %d of %d body seats admitted "
                    "directly (reservoir %d, floor %d) — the sponsor floor is "
                    "breached", group, len(sc_head), body_seats, len(sc_rank),
                    sponsor_floor(group))

    cf_pool = cf_direct + list(sc_head) + list(sc_winners)
    cf_pool = cf_pool[:cf_seats]
    if len(cf_pool) % 2:
        cf_pool = cf_pool[:-1]
    if cf_n and cf_pool:
        cf_pool = sorted(cf_pool, key=_atr_key(power))
        cf_arc, cf_winners = _recovery_round(cf_pool, phase="conference", rng=rng)
    else:
        cf_arc, cf_winners = {"field": [], "rounds": [[]], "survivors": [],
                              "round_names": [_RECOVERY_NAMES["conference"]]}, []
    qualifiers += list(cf_winners)

    if len(qualifiers) != berths:
        log.warning("JHSAA %s recovery filled %d of %d berths (pool %d, "
                    "semi-state %d, divisional %d, semi-conference %d, "
                    "conference %d)", group,
                    len(qualifiers), berths, len(sr_pool), len(ss_pool),
                    len(dv_pool), len(sc_pool), len(cf_pool))
    return (sr_arc, ss_arc, dv_arc, sc_arc, cf_arc,
            qualifiers, district_qualifiers, atr_used)


def _recovery_24(group: str, by_name: dict, prestate: dict, zonal_champs: list,
                 district_champs: list[str], power: dict, *,
                 seed: int) -> tuple[dict, dict, dict, dict, dict,
                                     list, list[str], dict]:
    """The FIXED 24-team recovery/qualification shape — 1A alone (owner rule
    2027-08; 2A left it for the standard ladder in the 2033 realignment, which
    took it to 95 programs and a 40-team field). Zonal champions are an automatic State berth here exactly as in
    every other class (`zonal_champs` — the caller seeds them 1-8, same as
    `_recovery`'s callers do) — this function returns only the 16 EARNED
    qualifiers on top of those 8. Every named round stays in play; what moves
    is which Regional losers reach which recovery round:

        Zonal            16 (Regional winners) -> 8 qualify (handled by caller), 8 losers -> Super Regional

        Regional losers  16, split by PREFERRED recovery priority:
          preferred (8):  district-champion Regional losers first (best-TOSS
                          if more than 8), then highest-TOSS other Regional
                          losers to fill out 8 -> Super Regional
          held back (8):  everyone else                           -> Semi-State

        Super Regional   16 = 8 Zonal losers + 8 preferred Regional losers -> 8 qualify, 8 -> Semi-State
        Semi-State       16 = 8 held-back Regional losers + 8 Super Regional losers
                              -> 8 -> Divisional, 8 -> Semi-Conference
        Divisional       8 (Semi-State winners)                -> 4 qualify, 4 -> Conference
        Semi-Conference  8 (Semi-State losers)                 -> 4 -> Conference (no berths)
        Conference       4 Divisional losers + 4 Semi-Conference winners -> 4 qualify

    8 (Zonal) + 8 (Super Regional) + 4 (Divisional) + 4 (Conference) = 24. This
    gives district champions the strongest recovery protection (first crack at
    the Super Regional slots) without making them automatic State qualifiers —
    they still have to win their way through. `district_qualifiers` stays in
    the return as an empty list purely for archive-shape compatibility with
    `_recovery`'s callers."""
    district_qualifiers: list[str] = []
    rng = random.Random(seed)
    reg_losers = [by_name[n] for n in _losers(prestate, 0)]
    zon_losers = [by_name[n] for n in _losers(prestate, 1)]

    dc_names = set(district_champs)
    dc_losers = sorted((t for t in reg_losers if t.school.name in dc_names),
                       key=_power_key(power))
    other_losers = sorted((t for t in reg_losers if t.school.name not in dc_names),
                          key=_power_key(power))
    preferred = list(dc_losers[:8])
    if len(preferred) < 8:
        need = 8 - len(preferred)
        preferred += other_losers[:need]
        held_back = other_losers[need:]
    else:
        held_back = dc_losers[8:] + other_losers

    sr_pool = sorted(list(zon_losers) + preferred, key=_power_key(power))
    sr_arc, sr_winners = _recovery_round(sr_pool, phase="super_regional", rng=rng)
    sr_won = {id(t) for t in sr_winners}
    sr_losers = [t for t in sr_pool if id(t) not in sr_won]

    ss_pool = sorted(list(held_back) + list(sr_losers), key=_power_key(power))
    ss_arc, ss_winners = _recovery_round(ss_pool, phase="semi_state", rng=rng)
    ss_won = {id(t) for t in ss_winners}
    ss_losers = sorted((t for t in ss_pool if id(t) not in ss_won),
                       key=_atr_key(power))

    dv_pool = list(ss_winners)
    if dv_pool:
        dv_arc, dv_winners = _recovery_round(dv_pool, phase="divisional", rng=rng)
    else:
        dv_arc, dv_winners = {"field": [], "rounds": [[]], "survivors": [],
                              "round_names": [_RECOVERY_NAMES["divisional"]]}, []
    dv_won = {id(t) for t in dv_winners}
    dv_losers = [t for t in dv_pool if id(t) not in dv_won]

    sc_pool = sorted(ss_losers, key=_atr_key(power))
    if sc_pool:
        sc_arc, sc_winners = _recovery_round(sc_pool, phase="semi_conference",
                                             rng=rng)
    else:
        sc_arc, sc_winners = {"field": [], "rounds": [[]], "survivors": [],
                              "round_names": [_RECOVERY_NAMES["semi_conference"]]}, []

    cf_pool = sorted(list(dv_losers) + list(sc_winners), key=_atr_key(power))
    if cf_pool:
        cf_arc, cf_winners = _recovery_round(cf_pool, phase="conference", rng=rng)
    else:
        cf_arc, cf_winners = {"field": [], "rounds": [[]], "survivors": [],
                              "round_names": [_RECOVERY_NAMES["conference"]]}, []

    qualifiers = list(sr_winners) + list(dv_winners) + list(cf_winners)
    atr_used = {t.school.name: atr(t, power) for t in by_name.values()}
    earned = state_field_size(group) - len(zonal_champs)
    if len(qualifiers) != earned:
        log.warning("JHSAA %s (24-team) recovery filled %d of %d earned berths "
                    "(super regional %d, semi-state %d, divisional %d, "
                    "semi-conference %d, conference %d)", group, len(qualifiers),
                    earned, len(sr_pool), len(ss_pool),
                    len(dv_pool), len(sc_pool), len(cf_pool))
    return (sr_arc, ss_arc, dv_arc, sc_arc, cf_arc,
            qualifiers, district_qualifiers, atr_used)


def run_state(field: list[TeamSeason], *, seed: int, champions: int = 8) -> dict:
    """The State Tournament: a fresh seeded draw (24 teams in the three largest
    classes, 40 elsewhere — Zonal champions first, then the district-guarantee and
    Semi-State qualifiers in post-recovery TOSS order) played to a champion.

    `champions` is how many Zonal champions lead the field (the caller's `len(zc)`,
    scaled with the ladder) — the draw's bye budget, and the count that decides
    whether the field is EXPANDED. A field whose padding byes are exactly the
    champions (24 in 32 slots) plays one fixed draw. A larger field — 40 — is
    that same draw with a
    QUALIFIERS ROUND in front: the champions take a double bye while everyone else
    plays the Qualies and then the First Round down to `champions` survivors, and
    the survivors join them in a fresh draw — exactly how a tour event's qualifying
    feeds its main draw, which is why there is no bracket path from a Qualies slot
    to a main-draw slot.

    The draw is SEEDED (`engine.tournament.seeded_draw`): entrants go to the
    standard bracket anchors so the top seeds can only meet late, then the bracket
    is FIXED — no reseeding between rounds (owner rule 2027-08). Within a seed tier
    the anchors are shuffled, so pairings vary by seed while the tiers never do.
    A non-power-of-two field (a standalone caller) pads up with byes to the top
    seeds, same as the college championship.

    It used to pad the field with `None` at the END of the slot list, which is not a
    draw at all: the Nones paired off with each other and vanished, nobody got a bye,
    and — because slot order was just finishing order — **the first round paired seed 1
    against seed 2**, seed 3 against seed 4, and so on. Every state tournament in the
    association was decided by a ladder that put its two best teams against each other
    first."""
    rng = random.Random(seed)
    from engine.tournament import seeded_draw

    def _play(slots, rounds):
        nxt, games = [], []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None or b is None:              # bye
                nxt.append(a or b)
                continue
            res = play_dual(a, b, seed=rng.randrange(1 << 30), phase="state")
            win = a if res.winner == 0 else b
            games.append({"home": a.school.name, "away": b.school.name,
                          "home_points": res.home_points, "away_points": res.away_points,
                          "winner": win.school.name})
            nxt.append(win)
        if games:
            rounds.append(games)
        return nxt

    rounds: list = []
    names: list[str] = []
    entrants = list(field)
    c = max(1, min(champions, len(field)))
    size = 1
    while size < len(field):
        size *= 2

    if len(field) > 2 * c and size - len(field) != c:
        # THE EXPANDED FIELD. The top `c` seeds are the Zonal champions and sit
        # out the whole preliminary — the double bye; everyone else plays the
        # Qualifiers Round and then the First Round, and the `c` who survive
        # both join them. After the Qualies the alive count IS the other
        # classes' field (40 → 24 at full size), so both shapes converge.
        champs, rest = field[:c], field[c:]
        sub = 1
        while sub < len(rest):
            sub *= 2
        slots: list[TeamSeason | None] = [
            None if r is None else rest[r]
            for r in seeded_draw(len(rest), sub, len(rest), rng)]
        while sum(1 for t in slots if t is not None) > c:
            slots = _play(slots, rounds)
        # The LAST preliminary round is the First Round; everything before it
        # is the Qualies (two rounds at every real size — rest is always 4×c).
        names = [QUALIFIER_NAME] * (len(rounds) - 1) + ["First Round"] \
            if len(rounds) > 1 else [QUALIFIER_NAME] * len(rounds)
        # Survivors re-enter the main draw at their ORIGINAL seeds, not their
        # qualifying-bracket positions. `slots` is in sub-draw slot order, and
        # feeding that to `seeded_draw` would let it read the positional order
        # as seed ranks c+1… — seed 16 could take the second qualifier anchor
        # while the archive and every page still label it No. 16.
        order = {id(t): i for i, t in enumerate(field)}
        entrants = champs + sorted((t for t in slots if t is not None),
                                   key=lambda t: order[id(t)])

    size = 1
    while size < len(entrants):
        size *= 2
    # `n_seeds = len(entrants)`: the whole field is ranked, so every entrant is
    # placed on its own anchor rather than drawn at random.
    slots = [None if r is None else entrants[r]
             for r in seeded_draw(len(entrants), size, len(entrants), rng)]
    while len(slots) > 1:
        slots = _play(slots, rounds)
    return {"champion": slots[0].school.name if slots and slots[0] else None,
            "rounds": rounds, "round_names": names,
            "field": [t.school.name for t in field]}


def run_toc(champions: list[TeamSeason], *, seed: int) -> dict:
    """The TOURNAMENT OF CHAMPIONS — one dual-team champion for all of Jefferson.

    ONE champion per classification and nobody else — nine teams now that every
    classification, including 1A and 2A, crowns separately. The field is not a
    `FIELD` size and never has been: it is exactly
    `len(GROUPS)`, and it grows or shrinks only when the association adds or merges a
    championship. (`FIELD` is the STATE tournament's bracket size per classification and
    has nothing to do with this event.)

    Seeded on the TOSS Power Index they finished the regular season with (`t.power`,
    already stamped by `play_regular_season`), NOT on classification: a 4A champion that
    rated above the 6A one is the higher seed, which is the whole reason the event is
    interesting.

    Six into a four-team semifinal, so the two lowest-rated pairs play in and the top two
    sit out; five would give one play-in and three byes. Then the semifinals and the
    final, under the state format (1S/4D) like the events that fed it.

    Returned in the same shape `run_state` uses, so it renders on the shared bracket tree
    with no new geometry."""
    field = sorted(champions, key=lambda t: (-t.power, t.school.name))
    if len(field) < 2:
        return {"champion": field[0].school.name if field else None,
                "rounds": [], "field": [t.school.name for t in field]}
    rng = random.Random(seed)

    def play(a: TeamSeason, b: TeamSeason) -> tuple[TeamSeason, dict]:
        # phase "toc", not "state": the shape and the lineup rules are the state
        # event's, but the dual has to be TELLABLE APART in `world_jhsaa_dual`, which
        # is all a program page has to read a TOC appearance back off.
        res = play_dual(a, b, seed=rng.randrange(1 << 30), phase="toc")
        win = a if res.winner == 0 else b
        return win, {"home": a.school.name, "away": b.school.name,
                     "home_points": res.home_points, "away_points": res.away_points,
                     "winner": win.school.name}

    # ‼️ A "FIRST FOUR" PLAY-IN FOR AN OVERSIZED FIELD (owner rule 2027-08, nine
    # classifications). `champions` grew from eight to nine at the 1A/2A split;
    # the cut-to-four math below was written and only ever exercised at exactly
    # eight (`2*(n-4)` play-in slots fits an n-team field only for n<=8). Rather
    # than reworking that math for an odd field, this reduces any field bigger
    # than eight the real-bracket way: the lowest TWO seeds play ONE game, and
    # the winner takes the vacated 8-seed slot — so an 8/9 upset means the
    # winner faces the 1-seed next, same as if they'd been the 8-seed all
    # along. Everything below this is completely unchanged from the original
    # eight-team design and is never asked to handle more than eight again.
    rounds: list[list[dict]] = []
    alive = list(field)
    while len(alive) > 8:
        w, gm = play(alive[-2], alive[-1])
        rounds.append([gm])
        alive = alive[:-2] + [w]

    # Cut to four, then semifinals, then the final: 6 -> 4 -> 2 -> 1. The play-in
    # takes the bottom 2*(n-4) seeds and pairs them highest-against-lowest, so at
    # six the top two sit out while 3v6 and 4v5 play, and at five only 4v5 does. Playing
    # a single play-in regardless left five teams standing and produced a 6 -> 5 -> 3 -> 1
    # ladder — a three-team "semifinal" and a bye nobody earned.
    if len(alive) > 4:
        n_in = 2 * (len(alive) - 4)
        block, byes = alive[-n_in:], alive[:-n_in]
        games, won = [], []
        for i in range(n_in // 2):
            w, gm = play(block[i], block[n_in - 1 - i])
            games.append(gm)
            won.append(w)
        rounds.append(games)
        alive = byes + won
    while len(alive) > 1:
        games, nxt = [], []
        for i in range(len(alive) // 2):
            w, gm = play(alive[i], alive[len(alive) - 1 - i])   # 1 v lowest, 2 v next
            games.append(gm)
            nxt.append(w)
        if len(alive) % 2:
            nxt.append(alive[len(alive) // 2])
        rounds.append(games)
        alive = nxt
    nxt = alive
    return {"champion": nxt[0].school.name if nxt else None,
            "rounds": rounds, "field": [t.school.name for t in field],
            "seeds": {t.school.name: i + 1 for i, t in enumerate(field)}}


# 9A=0 … 1A=8, so |i-j| = classes apart on the enrollment ladder. The Great Basin
# groups (2046) are NOT ladder rungs — enumerating GROUPS raw put Division 1 at 9,
# "one apart" from 1A, i.e. a 2,500-enrollment school gated onto 100-student
# opponents. They get FRACTIONAL positions on the same scale instead, chosen from
# their enrollment midpoints so the existing |i-j| <= 1 gate does the right thing:
# Division 1 (845-2556, mid ≈ 6A/5A) at 3.5 pairs with 6A, 5A and Division 2;
# Division 2 (57-836, mid ≈ 5A/4A boundary) at 4.5 pairs with 5A, 4A and Division 1.
# Crucially the two are exactly 1.0 apart, so the Great Basin pair can always meet
# non-district — which geography (their own three areas) makes the common case.
_GROUP_IX = {g: i for i, g in enumerate(LADDER_GROUPS)}
_GROUP_IX["Division 1"] = 3.5
_GROUP_IX["Division 2"] = 4.5

# How a non-district opponent is chosen (owner rule 2027-08): geography first — you do
# not bus across Jefferson for a non-league dual — then talent, so a weak program isn't
# fed to teams that beat it every week. Because talent is read off THIS year's roster,
# the pairings re-form each season as programs rise and fall.
GEO_WEIGHT = 8.0          # per step of distance: same county 0, same area 1, else 2
SHORTLIST = 6             # score the candidates, then draw at random from the best few


def _strength(ts: TeamSeason) -> float:
    """Team talent: the mean current overall of the nine who'd dress. Read off the
    roster, not the record, so it doesn't depend on who happens to be scheduled yet."""
    top = sorted((p.current_overall() for p in ts.roster), reverse=True)[:9]
    return sum(top) / len(top) if top else 0.0


def _geo_gap(a: School, b: School) -> int:
    return 0 if a.county == b.county else (1 if a.area == b.area else 2)


def _nondistrict_pairs(teams: list[TeamSeason], rng: random.Random,
                       owed: dict[int, int], played: dict[int, set[str]]) -> list[tuple]:
    """PAIR the non-district card — it does not play it.

    Pairing and playing are separate because the season is no longer "all the
    non-district duals, then all the league ones". A card opens non-district, runs the
    league, breaks for a mid-season window and runs the league back; the same matcher
    fills each of those windows, so it has to be able to hand back pairs and let the
    caller decide when they happen.

    Opponents are drawn on the three things that actually decide a real non-league card:
      1. GEOGRAPHY  — same county, then same area, then anywhere (`GEO_WEIGHT`).
      2. TALENT     — nearest team strength, so the draw is competitive both ways.
      3. AVAILABILITY — both schools still owe duals this window, and haven't met.
    Classification is a gate on top: same level or ONE level apart, never further, so a
    7A card mixes 7A and 6A and never lands on 1A.

    `owed` and `played` are the CALLER'S dicts and are mutated in place, so quotas and
    the no-rematch rule carry across windows instead of each window rediscovering them."""
    strength = {id(t): _strength(t) for t in teams}
    short = lambda: [t for t in teams if owed.get(id(t), 0) > 0]          # noqa: E731
    pairs: list[tuple] = []
    need = short()
    guard = 0
    while len(need) > 1 and guard < 200000:
        guard += 1
        a = need[rng.randrange(len(need))]
        ga, sa = _GROUP_IX[a.school.group], strength[id(a)]
        cands = [t for t in need if t is not a
                 and (t.school.group, t.school.district)
                 != (a.school.group, a.school.district)
                 and t.school.name not in played[id(a)]
                 and abs(_GROUP_IX[t.school.group] - ga) <= 1]
        if not cands:
            owed[id(a)] = 0            # can't be topped up; drop it, don't stall the run
            need = short()
            continue
        cands.sort(key=lambda t: (GEO_WEIGHT * _geo_gap(a.school, t.school)
                                  + abs(strength[id(t)] - sa), t.school.name))
        b = cands[rng.randrange(min(SHORTLIST, len(cands)))]
        pairs.append((a, b))
        for x, y in ((a, b), (b, a)):
            owed[id(x)] -= 1
            played[id(x)].add(y.school.name)
        need = short()
    return pairs


def _play_pairs(pairs: list[tuple], rng: random.Random, *, challenge: bool = False,
                phase: str = "regular") -> None:
    """Play a window's non-district pairs. Never district, so district place is
    untouched whatever else these results feed. `phase` defaults to the ordinary
    3S/4D card; the early window passes `EARLY_FORMAT_PHASE` for the 5S/2D one."""
    for a, b in pairs:
        play_dual(a, b, seed=rng.randrange(1 << 30), phase=phase,
                  district=False, challenge=challenge)


def play_regular_season(by_group: dict, year: int, gender: str,
                        salt: str = "") -> list[TeamSeason]:
    """Play a whole gender's regular season IN CALENDAR ORDER, and settle district place.

        early non-district → district pass 1 → mid-season window → district pass 2
                           → late non-district tune-up

    A dual's position in `schedule` is the only clock this association has — there is no
    date in the sim — so playing in this order IS the schedule. Every phase runs across
    the WHOLE gender before the next begins, which is what keeps one program's card in
    step with another's.

    `by_group` is {group: {district: [TeamSeason]}}. Takes a subset happily, which is how
    the schedule tests exercise this path rather than a re-implementation of it."""
    every_team = [t for st in by_group.values() for ts in st.values() for t in ts]
    xrng = random.Random(f"{salt}|xover|{gender}|{year}")

    # The non-district ALLOWANCE, split into windows up front. `owed`/`played` are shared
    # across every window, so a program's total card is the allowance it drew and no
    # pairing can quietly recreate a home-and-home that only the league is meant to have.
    quota = {id(t): NONDISTRICT_MIN + xrng.randrange(NONDISTRICT_MAX - NONDISTRICT_MIN + 1)
             for t in every_team}
    played: dict[int, set[str]] = {id(t): set() for t in every_team}
    reserved = MID_NONDISTRICT + (1 if CHALLENGE_ENABLED else 0)
    owed = {k: max(1, round((v - reserved) * EARLY_SHARE)) for k, v in quota.items()}
    # The early window plays 5S/2D (owner rule 2027-08, `EARLY_FORMAT_PHASE`) — the
    # ONLY block of the season that does. Everything from district pass 1 on, including
    # the mid-season non-district window and the late tune-up below, is back to the
    # ordinary 3S/4D `phase="regular"` because district play has already started by then.
    _play_pairs(_nondistrict_pairs(every_team, xrng, owed, played), xrng,
               phase=EARLY_FORMAT_PHASE)

    # The mid-season window sits at the END OF PASS 1 — `district_pass1_rounds`,
    # never `len // 2`: on a cap-truncated league (DISTRICT_DUAL_CAP) the list is
    # asymmetric, and a halfway split would break pass 1 in the middle while
    # gluing its tail onto pass 2.
    rounds, half = {}, {}
    for g, st in by_group.items():
        for d, teams in st.items():
            rounds[(g, d)] = district_rounds(teams, year, salt)
            half[(g, d)] = district_pass1_rounds(len(teams))
    for key, rr in rounds.items():
        play_rounds(rr[:half[key]], year, salt, key[1])

    # --- the mid-season window: a non-district date, then the challenge ---
    owed = {id(t): MID_NONDISTRICT for t in every_team}
    _play_pairs(_nondistrict_pairs(every_team, xrng, owed, played), xrng)
    if CHALLENGE_ENABLED:
        _play_pairs(_challenge_pairs(by_group, year, salt, played), xrng, challenge=True)

    # --- the mid-season MATCH SHOWCASES: 6-8 weekend windows of 1S/4D duals ---
    # They sit here for the same reason the challenge does — a showcase field is cut on
    # how the season has actually gone, which needs a league pass behind it — and
    # because this is where the calendar has open weekends. See the SHOWCASE section.
    traded = play_showcases(
        showcase_schedule(every_team, year, gender, salt, played), xrng)

    for key, rr in rounds.items():
        play_rounds(rr[half[key]:], year, salt, key[1])

    # --- the late tune-up: whatever the allowance has left ---
    # ‼️ SPENT COUNTS INVITATIONALS, NOT SHOWCASES. Both are non-district, but the
    # allowance is a card of ordinary weekday duals and a showcase is a weekend event
    # held beside it: counted here, a program's three pod duals would eat its whole
    # remaining allowance and it would finish the season short of the association's
    # minimum. What a showcase DOES cost is the trade — a 2-day block is played on a
    # Friday and takes one standard weekday date back with it (owner spec), which is
    # `traded`. A 1-day pod is an open Saturday and costs nothing.
    spent = {id(t): sum(1 for s in t.schedule
                        if not s["district"] and s["phase"] not in SHOWCASE)
             for t in every_team}
    owed = {id(t): max(0, quota[id(t)] - spent[id(t)] - traded.get(id(t), 0))
            for t in every_team}
    _play_pairs(_nondistrict_pairs(every_team, xrng, owed, played), xrng)

    # Power Index BEFORE settling: rung 4 of the tiebreak ladder reads `t.power`, and it
    # is a function of the whole pool's results graph, so it cannot exist until every
    # regular-season dual is played. Computed once here and handed back, so `run_season`
    # does not recompute a ~5,000-dual rating it already has.
    power = power_index(every_team)
    for t in every_team:
        r = power.get(t.school.name)
        if r is not None:
            t.power = r.pi_raw
    oowp = district_oowp(every_team)
    for st in by_group.values():
        for teams in st.values():
            settle_district(teams, oowp)
    return every_team, power


# --- the JV season ------------------------------------------------------------
#
# Order of play, and as everywhere else in this association the ORDER IS THE SCHEDULE:
#
#     district single round robin -> invitationals to the cap -> one showcase
#
# It sits AFTER the varsity regular season in `run_season` for one concrete reason:
# `jv_pool` reads `_order`, the results-moved ladder, so playing JV first would size
# and staff every JV dual off a ladder that was still at its opening seeds.
#
# ‼️ AND IT NEVER TOUCHES THE VARSITY CALENDAR (owner rule 2026-08). JV rows are kept
# out of the varsity round allocator entirely — `world.jhsaa_match_dates` advances its
# per-school cursor on every distinct key, so a JV dual sharing a school with a varsity
# one would take a later round and serialise the two seasons, overrunning the season
# window while every individual card still read correctly. JV gets its own date pass,
# on its own day pattern, and it may use SUNDAYS, which varsity never does.


def jv_teams(by_group: dict) -> dict[str, JVTeam]:
    """A JV team per program, hanging off its varsity `TeamSeason`."""
    return {t.school.name: JVTeam(team=t)
            for st in by_group.values() for ts in st.values() for t in ts}


def _jv_can_play(a: JVTeam, b: JVTeam) -> bool:
    return jv_dual_format(jv_spare(a.team), jv_spare(b.team)) is not None


def jv_district_slate(by_group: dict, jv: dict[str, JVTeam], year: int,
                      salt: str) -> None:
    """Every league's JV round robin — played ONCE, not home-and-away.

    The varsity league is a double round robin under `DISTRICT_DUAL_CAP`; the JV plays
    a single pass, which lands a typical 10-12 team league at 9-11 duals and leaves
    the invitational window to fill toward `JV_DUAL_CAP`. Generated as ROUNDS
    (`_rr_rounds`) for the same reason varsity is: a round is a set of duals with no
    team in common, which is what the display calendar packs onto a day."""
    for group, dists in sorted(by_group.items()):
        for dname, teams in sorted(dists.items()):
            squad = [jv[t.school.name] for t in teams]
            for rnd in _rr_rounds(len(squad)):
                for i, j in rnd:
                    a, b = squad[i], squad[j]
                    if not _jv_can_play(a, b):
                        continue
                    # The seed comes off the PAIRING, never its position — the same
                    # rule `play_rounds` follows, and for the same reason: a caller
                    # that slices the round list would otherwise restart an index and
                    # replay identical inputs to different results.
                    seed = abs(hash((salt, "jv-district", year, group, dname,
                                     a.school.name, b.school.name))) % (1 << 30)
                    play_jv_dual(a, b, seed=seed, district=True)


def jv_invitational_pairs(jv: dict[str, JVTeam], played: dict[str, set],
                          rng: random.Random) -> list[tuple]:
    """One window of JV invitationals: sort on JV strength, walk the list, pair each
    team with the next one still free.

    Talent-ordered and nothing else — no search, no geography term, no scoring. This
    was a windowed scorer first and that was precision spent on a decision that does
    not matter, the same mistake `_showcase_groups` already made and had removed
    (owner rule 2026-08): at JV it is whoever has somebody, and a talent sort already
    puts comparable teams next to each other. A league-mate is refused because they
    have met in the round robin.
    """
    free = sorted(jv.values(), key=lambda t: (-jv_strength(t.team), t.school.name))
    taken: set[str] = set()
    pairs = []
    for i, a in enumerate(free):
        if a.school.name in taken:
            continue
        for b in free[i + 1:]:
            if b.school.name in taken or b.school.name in played[a.school.name]:
                continue
            if _dkey(a) == _dkey(b) or not _jv_can_play(a, b):
                continue
            taken.add(a.school.name)
            taken.add(b.school.name)
            played[a.school.name].add(b.school.name)
            played[b.school.name].add(a.school.name)
            pairs.append((a, b) if rng.random() < 0.5 else (b, a))
            break
    return pairs


def jv_showcase(jv: dict[str, JVTeam], year: int, salt: str,
                played: dict[str, set], rng: random.Random) -> None:
    """The JV Showcase Weekend — four programs, a full round robin, three duals, once
    per program at the END of the season.

    Reuses the varsity `_showcase_groups` wholesale (owner rule 2026-08: "yes reuse"),
    including its hard district guardrail; `JVTeam` exposes `.school`, which is all that
    helper reads. Played after the invitational cap has bound, and outside it."""
    pool = [t for t in jv.values() if _jv_can_play(t, t)]
    seen = {id(t): played[t.school.name] for t in pool}
    for grp in _showcase_groups(pool, 4, seen, rng):
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                a, b = grp[i], grp[j]
                if not _jv_can_play(a, b):
                    continue
                seed = abs(hash((salt, "jv-showcase", year,
                                 a.school.name, b.school.name))) % (1 << 30)
                # The POD phase, not "regular": a phase is the archive's identity for
                # an EVENT, and without it a showcase dual is indistinguishable from an
                # invitational on the card and in the cap arithmetic. It also picks up
                # `match_format`'s 8-game pro set, which is what a pod plays.
                play_jv_dual(a, b, seed=seed, phase="showcase_pod", district=False)


def play_jv_season(by_group: dict, year: int, gender: str,
                   salt: str) -> dict[str, JVTeam]:
    """The whole JV season for one gender. Returns {school name -> JVTeam}."""
    jv = jv_teams(by_group)
    jv_district_slate(by_group, jv, year, salt)
    rng = random.Random(f"{salt}|jv|{gender}|{year}")
    played: dict[str, set] = {name: set() for name in jv}
    for name, t in jv.items():                       # league-mates already met
        played[name] |= {d["opp"] for d in t.schedule}
    # Invitational windows until the cap binds. Bounded by a window count rather than
    # "until nobody can be paired": the pool thins as programs reach the cap and the
    # tail would otherwise spin over an unpairable remainder.
    for _ in range(JV_DUAL_CAP):
        under = {n: t for n, t in jv.items() if len(t.schedule) < JV_DUAL_CAP}
        if len(under) < 2:
            break
        pairs = jv_invitational_pairs(under, played, rng)
        if not pairs:
            break
        for a, b in pairs:
            seed = abs(hash((salt, "jv-invite", year,
                             a.school.name, b.school.name))) % (1 << 30)
            play_jv_dual(a, b, seed=seed, district=False)
    jv_showcase(jv, year, salt, played, rng)
    return jv


def _challenge_pairs(by_group: dict, year: int, salt: str,
                     played: dict[int, set[str]]) -> list[tuple]:
    """The mid-season challenge slate, paired on how the season has actually gone.

    Run at the break, AFTER the first league pass, which is the whole idea: rank each
    district by its league record so far and match a #3 against another district's #3.
    That is a useful dual; the same programs paired in February on roster strength would
    have been another arbitrary non-league date.

    The early non-district card cannot work this way and must not be changed to — it is
    seeded on roster strength precisely so it can run BEFORE any results exist. This
    window is the one place in the season where a pairing reads results, and it can only
    exist because it sits after a pass.

    Pairing is greedy over (place gap, travel, level gap), gated to the same
    classification or one apart and never a rematch. Hosting alternates on a stable hash
    of the two school names and the year, so a program is not systematically at home."""
    slate: list[tuple] = []
    for group, dists in by_group.items():
        # Provisional standing INSIDE each district, on league results only.
        # LEAGUE results only, and the margin comes off the district duals — not
        # `points_for`/`points_against`, which accumulate over the early non-district
        # window too. Reading those here would let a February blowout against another
        # district decide who a program draws in the challenge, in a pairing whose whole
        # premise is "how the LEAGUE season has gone".
        ranked: list[tuple[int, TeamSeason]] = []
        for teams in dists.values():
            order = sorted(teams, key=lambda t: (
                -t.district_pct,
                -sum(x["pf"] - x["pa"] for x in _district_duals(t)),
                t.school.name))
            ranked += [(i, t) for i, t in enumerate(order, 1)]
        pool = sorted(ranked, key=lambda r: (r[0], r[1].school.name))
        taken: set[int] = set()
        for place, a in pool:
            if id(a) in taken:
                continue
            best = None
            for pl, b in pool:
                if id(b) in taken or b is a:
                    continue
                if b.school.district == a.school.district:
                    continue
                if abs(pl - place) > CHALLENGE_PLACE_SLACK:
                    continue
                if b.school.name in played[id(a)]:
                    continue
                score = (abs(pl - place) * 10.0
                         + CHALLENGE_GEO_WEIGHT * _geo_gap(a.school, b.school))
                if best is None or score < best[0]:
                    best = (score, b)
            if best is None:
                continue
            b = best[1]
            taken.add(id(a)); taken.add(id(b))
            # Host alternates on the pairing + the year, not on who was listed first.
            key = "|".join(sorted((a.school.name, b.school.name)))
            h = int(hashlib.blake2s(f"{salt}|chal|{year}|{group}|{key}".encode(),
                                    digest_size=4).hexdigest(), 16)
            slate.append((a, b) if h % 2 == 0 else (b, a))
            for x, y in ((a, b), (b, a)):
                played[id(x)].add(y.school.name)
    return slate


# --- the mid-season MATCH SHOWCASES -------------------------------------------
#
# The constants and the reasoning are at the top of the module. This is the scheduler:
# who attends, how often, who they are grouped with, and who they play. It produces
# EVENTS — a kind, a window, a field and a list of rounds — and `play_showcases` plays
# them. Nothing here ranks, advances or eliminates anybody.


def _dkey(t: TeamSeason) -> tuple:
    """A program's district identity. ‼️ A DISTRICT IS `(CLASSIFICATION, name)` — the
    association reuses its geographic district names at every level, so comparing the
    name alone would call two programs league-mates that have never met."""
    return (t.school.group, t.school.district)


def _showcase_rank(teams: list[TeamSeason]) -> list[TeamSeason]:
    """The provisional statewide order, best first, as it stands at the break.

    Not TOSS: TOSS is computed once on the FINISHED regular season (it is both the
    seeding input and rung 4 of the district tiebreak), and this runs in the middle of
    one. So it is the two things that exist mid-season — how the program has actually
    gone, then how good the nine who dress are. It decides two things only: which
    programs get the scarce multi-event seats, and which tier a 2-day entrant lands in.
    Nothing is crowned off it."""
    return sorted(teams, key=lambda t: (
        -(t.wins / (t.wins + t.losses)) if (t.wins + t.losses) else 0.0,
        -_strength(t), t.school.name))


def showcase_entries(teams: list[TeamSeason], rng: random.Random,
                     ranked: list[TeamSeason]) -> dict[int, int]:
    """How many showcases each program attends this season, {id(team): 1..3}.

    About half the association attends (`SHOWCASE_SHARE`) and nearly all of those
    attend once. The multi-event seats are scarce and DELIBERATELY not spread evenly:
    the whole return on a showcase is 1S/4D evidence, and evidence from the programs
    that will still be playing in late May is worth more than evidence from the ones
    that will not — so the Top 25 (`SHOWCASE_ELITE`) get first call on them, and only
    two or three programs statewide attend three."""
    n = int(round(len(teams) * SHOWCASE_SHARE))
    if n < POD_SIZE:
        return {}
    field = rng.sample(teams, n)
    quota = {id(t): 1 for t in field}
    inside = {id(t) for t in field}
    # Elite first, then anyone else attending — an elite program that drew no seat in
    # the participation sample cannot be handed a second one it is not at.
    order = ([t for t in ranked[:SHOWCASE_ELITE] if id(t) in inside]
             + [t for t in ranked[SHOWCASE_ELITE:] if id(t) in inside])
    threes = min(SHOWCASE_THREE_MAX, max(1, int(round(len(field) * 0.01))))
    twos = int(round(len(field) * SHOWCASE_TWO_SHARE))
    for t in order[:threes]:
        quota[id(t)] = 3
    for t in order[threes:threes + twos]:
        quota[id(t)] = 2
    return quota


def _showcase_groups(pool: list[TeamSeason], size: int, played: dict[int, set[str]],
                     rng: random.Random) -> list[list[TeamSeason]]:
    """Shuffle the pool and DEAL groups of `size` off it, in one pass.

    ‼️ DELIBERATELY DUMB, and it replaced a constraint solver that was not (owner,
    2026-08: "just randomly match people and be done"). The first version treated
    group formation as a placement problem — seed a group, scan the whole remaining
    pool for members that fit, pop the seed and rescan when it could not be filled —
    which is quadratic in the pool for every tier of every window, and the JHSAA rung
    stopped finishing.

    A showcase field is already a rank-ordered slice of one tier, so who lands in
    which group inside that slice carries almost no information: the tier cut is what
    makes the duals worth playing, and dealing at random inside it is as good and is
    linear. The ONE rule that survives is the hard district guardrail — a team that
    would join a league-mate is set aside and dealt into a later group instead, which
    is the spec's "swap across pods" done in a single pass rather than by repair.

    A trailing part-group is not played: a showcase is a fixed number of duals, so a
    short field is dropped rather than fielded."""
    teams = list(pool)
    rng.shuffle(teams)
    groups: list[list[TeamSeason]] = []
    cur: list[TeamSeason] = []
    held: list[TeamSeason] = []

    def offer(t: TeamSeason) -> None:
        nonlocal cur
        if any(_dkey(t) == _dkey(o) for o in cur):   # league-mate: deal it later
            held.append(t)
            return
        cur.append(t)
        if len(cur) == size:
            groups.append(cur)
            cur = []

    for t in teams:
        offer(t)
    for t in list(held):                             # one retry pass, then done
        held.remove(t)
        offer(t)
    for grp in groups:                               # every pair meets, so book them
        for a in grp:
            for b in grp:
                if a is not b:
                    played[id(a)].add(b.school.name)
    return groups


def _showcase_rounds(grp: list[TeamSeason], duals: int, year: int,
                     salt: str) -> list[list[tuple]]:
    """A group's SESSIONS: `duals` rounds, every member playing in every one.

    A pod (4 teams, 3 duals) is a complete round robin. A tier group (6 teams, 4 duals)
    is the first four rounds of one — four perfect matchings, so both days are full and
    nobody sits out a session. Hosting is drawn on the pairing and the year, never on
    who was listed first, so no program is systematically at home for its showcase."""
    out = []
    for rnd in _rr_rounds(len(grp))[:duals]:
        date = []
        for i, j in rnd:
            a, b = grp[i], grp[j]
            key = "|".join(sorted((a.school.name, b.school.name)))
            h = int(hashlib.blake2s(f"{salt}|show|{year}|{key}".encode(),
                                    digest_size=4).hexdigest(), 16)
            date.append((a, b) if h % 2 == 0 else (b, a))
        out.append(date)
    return out


def showcase_schedule(teams: list[TeamSeason], year: int, gender: str, salt: str,
                      played: dict[int, set[str]]) -> list[dict]:
    """The season's showcase slate: a list of events in window order.

    An event is `{kind, phase, window, tier, teams, rounds}` — a field and its fixed
    matchups, with no bracket anywhere in it. `played` is the caller's no-rematch
    ledger and is mutated in place, exactly as `_nondistrict_pairs` uses it, so the
    showcases share one view of who has met whom with the rest of the card."""
    if not SHOWCASE_ENABLED or len(teams) < POD_SIZE:
        return []
    rng = random.Random(f"{salt}|showcase|{gender}|{year}")
    ranked = _showcase_rank(teams)
    quota = showcase_entries(teams, rng, ranked)
    if not quota:
        return []
    n_win = SHOWCASE_WINDOWS_MIN + rng.randrange(
        SHOWCASE_WINDOWS_MAX - SHOWCASE_WINDOWS_MIN + 1)
    # Half the blocks of each kind, pods leading. An odd window count gives the extra
    # block to the pods — the cheaper event, one day and no weekday dual traded away.
    kinds = ["pod" if i % 2 == 0 else "tiered" for i in range(n_win)]
    # Which windows each program attends. A program is at one event per window at most,
    # which is what makes "3 duals in a day" and "2 a day for two days" true of the
    # program and not merely of the event.
    #
    # ⚠️ Membership is by id, never by value: `TeamSeason` is a dataclass, so `in` on a
    # list of them compares ROSTERS field by field — slow, and equal for two programs
    # whose seasons happen to look alike.
    entered: list[set[int]] = [set() for _ in range(n_win)]
    for t in ranked:                                   # rank order, so it is stable
        q = quota.get(id(t))
        if not q:
            continue
        for w in rng.sample(range(n_win), min(q, n_win)):
            entered[w].add(id(t))

    events = []
    for w, kind in enumerate(kinds):
        pool = [t for t in ranked if id(t) in entered[w]]   # statewide rank order
        phase = "showcase_pod" if kind == "pod" else "showcase_tiered"
        if kind == "pod":
            # A pod is not tiered, but it is not a lottery either: filling from a rank
            # order puts comparable programs in a pod, which is what makes the three
            # duals worth playing.
            fields = [(None, pool)]
        else:
            # THE TIERS: the field cut into three by statewide standing, top down and
            # classification-blind. Cut before grouping, so an Open-tier program is
            # never grouped with a C-tier one to make the arithmetic come out.
            k = len(pool) // 3
            fields = list(zip(SHOWCASE_TIERS,
                              (pool[:k], pool[k:2 * k], pool[2 * k:])))
        size = POD_SIZE if kind == "pod" else TIER_SIZE
        duals = POD_DUALS if kind == "pod" else TIER_DUALS
        for tier, field in fields:
            for grp in _showcase_groups(field, size, played, rng):
                events.append({"kind": kind, "phase": phase, "window": w,
                               "tier": tier, "teams": grp,
                               "rounds": _showcase_rounds(grp, duals, year, salt)})
    return events


def showcase_conflicts(events: list[dict]) -> list[tuple]:
    """Every same-district pairing in the slate — the spec's
    `ensure_zero_district_conflicts`, as a report rather than an assert so a caller
    can name the offenders. It must always be empty; the district check in
    `_showcase_groups` is what makes it so."""
    return [(e["kind"], a.school.name, b.school.name)
            for e in events for rnd in e["rounds"] for a, b in rnd
            if _dkey(a) == _dkey(b)]


def play_showcases(events: list[dict], rng: random.Random) -> dict[int, int]:
    """Play the slate in window order, SESSION BY SESSION across every event.

    Returns {id(team): weekday duals traded away} — a 2-day showcase is played on a
    Friday and a Saturday and the association takes a standard weekday non-district
    date back for it (owner spec), so the caller shortens that program's remaining
    allowance by one. A 1-day pod is played on an open Saturday and costs nothing.

    Playing session by session rather than event by event is what lets the display
    calendar land a window on one weekend: every event's first session is played
    before any event's second, so the whole window occupies one block of the play
    order (see `world.jhsaa_match_dates`)."""
    bad = showcase_conflicts(events)
    if bad:
        raise ValueError(f"showcase slate has same-district pairings: {bad[:5]}")
    traded: dict[int, int] = {}
    for w in sorted({e["window"] for e in events}):
        win = [e for e in events if e["window"] == w]
        for s in range(max((len(e["rounds"]) for e in win), default=0)):
            for e in win:
                if s >= len(e["rounds"]):
                    continue
                for a, b in e["rounds"][s]:
                    play_dual(a, b, seed=rng.randrange(1 << 30), phase=e["phase"],
                              district=False)
        for e in win:
            if e["kind"] == "tiered":
                for t in e["teams"]:
                    traded[id(t)] = traded.get(id(t), 0) + 1
    return traded


# --- awards -------------------------------------------------------------------
# The selection model lives in `app/jhsaa_awards.py` (owner SOP 2027-08): All-State
# First/Second/Third — plus a Fourth in 7A — then Honorable Mention, a District
# Player of the Year and one wide All-District team per district, all chosen from
# the season's MATCH LOG rather than from ability ratings. Re-exported here so
# `run_season` and every existing caller keep one import.
from .jhsaa_awards import (season_awards, region_awards, build_pool,   # noqa: E402,F401
                           honors_for)


_season_cache: dict = {}


def run_season(gender: str, year: int, *, seed: int = 0, salt: str = "") -> dict:
    """One full JHSAA season for `gender`: every district's regular season, the
    crossover schedule, the awards, and each classification's postseason ladder
    (Sectionals → Wards → Regionals → Zonals → Super Regionals → Semi-State →
    State — see the postseason constants above).

    Memoized per (salt, gender, year, seed) — a season is deterministic, and both the
    recruit hand-off and any page that wants standings would otherwise re-simulate
    thousands of duals. Computed into a local and published, never returned out of the
    dict, per the threaded-worker rule in CLAUDE.md."""
    from app import overrides as _ov
    # ‼️ BOTH override tables key the cache. An archetype changes how good a program
    # is; a PLAY-UP changes which championship it enters, so it moves the leagues,
    # the ladder, the State field and All-State. Leaving it out would serve a cached
    # season built from the old classification map with no sign anything had changed.
    ck = (salt, gender, year, seed,
          _ov.jhsaa_archetype_version(), _ov.jhsaa_playup_version())
    hit = _season_cache.get(ck)
    if hit is not None:
        return hit
    out = {"year": year, "gender": gender, "groups": {}, "teams": {}, "awards": {}}
    # ORDER OF PLAY, and it is the shape of the season (owner rule 2027-08):
    #
    #   early non-district → district pass 1 → MID-SEASON WINDOW → district pass 2
    #                      → late non-district → district/state postseason
    #
    # It used to be "all the non-district duals, then the whole double round-robin", and
    # inside that round-robin every opponent was played home-and-away on back-to-back
    # dates. Both halves of that were wrong for a high-school card, and the second half
    # was the visible one. The league is now two SEPARATED passes (`district_rounds`)
    # with the non-district card spread around and through them.
    #
    # A dual's ORDER IN `schedule` is the only clock this association has — there is no
    # date in the sim, and `state._jh_dates` lays the persisted order on a spring
    # calendar — so playing in this order IS the schedule. Everything here plays a whole
    # phase across the WHOLE gender before moving on, which is what keeps every
    # program's card in step with every other one's.
    #
    # Non-district pairing still seeds on ROSTER STRENGTH, not results, so the early
    # window can lead. The one exception is the mid-season challenge, which is paired at
    # the break precisely because by then there are results worth pairing on.
    by_group = {group: {dname: district_teams(schools, year, salt)
                        for dname, schools in sorted(districts(gender, group).items())}
                for group in GROUPS}
    # THE INDIVIDUAL STATE TOURNAMENTS — six flighted draws (No. 1-3 singles,
    # No. 1-3 doubles) per classification, played HERE: before a league dual, and
    # for exactly that reason. Entries are selected off the ability ladder, which
    # would violate "you win your way in" at any later point in the year; run
    # preseason there are no results yet, so ability is the only input there is.
    #
    # It is therefore an INPUT to the season and not a summary of it. `credit_draw`
    # writes into the same `records` and `matches` every league court does, so a
    # deep run moves a player up `ladder_score` before the first dual and lands on
    # the awards résumé the same way a court does. That full credit needed no new
    # machinery: the flight names ARE the dual slot names, so `FLIGHT_WEIGHTS`
    # already prices them, and the phase is deliberately outside `POSTSEASON`, so
    # `jhsaa_awards._phase_weight` treats them as ordinary matches.
    #
    # ‼️ MIXED DOUBLES IS NOT HERE. A mixed pair is one player from each gender and
    # this function only ever sees one, so that event cannot be assembled until
    # both seasons exist — it runs at the world rung (`jhsaa_individuals.
    # run_mixed_season`), which is also where it belongs on the calendar, in the
    # summer. It credits nothing to anybody.
    from .jhsaa_individuals import run_preseason as _run_individuals
    out["individuals"] = _run_individuals(by_group, gender, year, seed=seed)
    every_team, power = play_regular_season(by_group, year, gender, salt)
    # THE JV SEASON, played here and nowhere else. It runs BEFORE the postseason
    # because that is where it sits on the calendar (April-May against the varsity
    # league season) — and because the postseason FREEZES the Order of Ability, which
    # is a varsity rule the JV has no business either reading or tripping.
    #
    # ‼️ IT RUNS AFTER THE WHOLE VARSITY REGULAR SEASON, AND THAT IS A SHORTCUT, NOT A
    # REQUIREMENT. `jv_pool` reads `_order`, the results-moved ladder, so running it
    # first would staff every JV dual off opening seeds — but the alternative to "all
    # at the start" is not "all at the end", it is INTERLEAVED, one JV block per
    # varsity block at this function's own seams (early → pass 1 → mid-season → pass 2
    # → tune-up). Playing it all here means the JV pool is cut ONCE, from the finished
    # ladder, and every JV dual of the year uses that same cut however it is dated.
    # Measured cost: 4.1% of the JV pool differs from a ladder read early in the season
    # (13 of 408 players over 42 programs), median rank change 0 places — small only
    # because `LADDER_SWING` is 7 and the ladder is deliberately sticky. Raise that and
    # this needs the interleave. See `jv_pool`.
    #
    # It writes nothing any line below this can see: no `records`, no `matches`, no
    # `power`, no standings row. That is `JVTeam`'s doing, not this call's.
    out["jv"] = play_jv_season(by_group, year, gender, salt)
    # TOSS was computed over the whole gender inside `play_regular_season` — once, on the
    # finished regular season, before any state tournament, since it is both the seeding
    # input and rung 4 of the district tiebreak. Across all classifications together
    # because non-district play crosses them: rating a class in isolation would cut those
    # edges out of the results graph.
    out["power"] = power
    # THE POSTSEASON IS PLAYED OUT BEFORE ANY RECORD IS WRITTEN DOWN. A record is a
    # record — the NCAA and the NFHS both carry the postseason in the season total, and
    # nobody publishes a program's regular season as though it were the year. So every
    # classification's state tournament runs, then the Tournament of Champions runs, and
    # only THEN is `t.record` snapshotted into the standings.
    #
    # This used to snapshot inside the same loop that played each state draw, which was
    # right for state (that group's duals were done) and silently wrong for the TOC —
    # it needs every group's champion, so it cannot run until the loop is over, and the
    # six programs in it therefore had their last one or two duals archived on their
    # SCHEDULE but missing from their RECORD. Measured: 131 of 137 programs archived
    # every dual they played, and the six that did not were exactly the TOC field.
    # The qualification ladder, every group, before any recovery round: the
    # recovery fields are seeded on a TOSS recomputed over ALL completed
    # pre-state matches, and TOSS runs over the whole gender at once, so every
    # group's Zonals must be done before any group's Super Regionals can start.
    sectionals, wards, prestates, protecteds, zonal_champs = {}, {}, {}, {}, {}
    district_champs = {}
    for group in GROUPS:
        standings = by_group[group]
        protected, entrants = sectional_field(group, standings, power)
        protecteds[group] = [t.school.name for t in protected]
        district_champs[group] = [ts[0].school.name
                                  for ts in standings.values() if ts]
        gseed = seed + hash(group) % 9973
        sectionals[group], ward_field = run_sectional(entrants, WARD_FIELD,
                                                       seed=gseed)
        ward_field = sorted(ward_field, key=_power_key(power))
        wards[group], ward_champs = run_rounds(ward_field, ("ward",),
                                               seed=gseed + 4111)
        reg_field = sorted(protected + ward_champs, key=_power_key(power))
        prestates[group], zonal_champs[group] = run_rounds(
            reg_field, ("regional", "zonal"), seed=gseed + 8219)
    post_power = power_index(every_team, prestate=True)
    # The RECOVERY rounds (Super Regionals -> Semi-State), every group, before
    # any State draw: the remaining berths are earned on court, and the State
    # seeding TOSS is recomputed once more AFTERWARD so it includes them.
    super_regionals, semi_states, divisionals = {}, {}, {}
    semi_conferences, conferences = {}, {}
    atr_snap: dict[str, float] = {}
    recovery_q, district_q = {}, {}
    for group in GROUPS:
        by_name_g = {t.school.name: t
                     for ts in by_group[group].values() for t in ts}
        if state_field_size(group) == 24:
            sr, ss, dv, sc, cf, quals, dq, atr_used = _recovery_24(
                group, by_name_g, prestates[group], zonal_champs[group],
                district_champs[group], post_power,
                seed=seed + hash(group) % 9973 + 16223)
        else:
            sr, ss, dv, sc, cf, quals, dq, atr_used = _recovery(
                group, by_name_g, sectionals[group], wards[group], prestates[group],
                zonal_champs[group], district_champs[group], post_power,
                seed=seed + hash(group) % 9973 + 16223)
        super_regionals[group], semi_states[group] = sr, ss
        divisionals[group], semi_conferences[group] = dv, sc
        conferences[group] = cf
        recovery_q[group], district_q[group] = quals, dq
        atr_snap.update(atr_used)
    final_power = power_index(every_team, prestate=True)
    states = {}
    for group in GROUPS:
        by_name_g = {t.school.name: t
                     for ts in by_group[group].values() for t in ts}
        # ‼️ ZONAL CHAMPIONS ARE THE TOP SEEDS — the whole privileged path, and
        # it is a SEEDING guarantee in its own right, not a side effect of byes
        # (owner clarification 2027-08). Winning a Zonal buys seeds 1-8 in every
        # classification: in a 24-team field that also hands them the eight
        # first-round byes, but a 40-team field gives them a DOUBLE bye through
        # the Qualifiers Round, and a power-of-two draw would give them neither —
        # the guarantee is that they are seeded 1-8, whatever the shape.
        #
        # TWO WAYS IN AND NO OTHERS (owner rule 2027-08): win a Zonal, or win
        # your way through recovery. Everyone below the champions is a recovery
        # survivor, seeded in post-recovery TOSS order. This holds for 1A's
        # fixed 24-team shape too (`_recovery_24`) — Zonal champions are an
        # automatic State berth there exactly like every other class; only the
        # RECOVERY ladder underneath them is wired differently. `champions=
        # len(zc)` (8) on a 24-team field lands on `run_state`'s single-draw
        # branch (no Qualifiers Round), so "seeds 1-8 bye" falls out for free.
        zc = sorted(zonal_champs[group], key=_power_key(final_power))
        rest = sorted(recovery_q[group], key=_power_key(final_power))
        states[group] = run_state(zc + rest, champions=len(zc),
                                  seed=seed + hash(group) % 9973 + 12281)
    champs = [t for group, st in states.items()
              for ts in by_group[group].values() for t in ts
              if t.school.name == st["champion"]]
    out["toc"] = run_toc(champs, seed=seed + 7717)

    # ‼️ AWARDS ARE SELECTED AFTER EVERY DUAL HAS BEEN PLAYED — the same rule the
    # RECORD snapshot below runs on, and it was broken here in the same way. The
    # selection used to sit in the qualification loop above, which meant it ran
    # BEFORE Sectionals, so criterion 7 of the SOP ("Sectionals through State count
    # for more") weighted a postseason nobody had played yet: `PHASE_WEIGHT` never
    # applied to a single match, a state run added nothing to a résumé, and — worse,
    # because it is silent — the 1S/4D postseason moves most of a roster into
    # doubles, so the singles/doubles participation split the category rule reads
    # (`_primary_discipline`) was taken with a third of the season missing. Nothing
    # errored; the teams just quietly described the regular season.
    # ONE rating pass over the WHOLE GENDER, then the per-class slates off it.
    # Non-district play crosses classifications, so rating a class in isolation
    # cuts those edges out of the opponent graph — the same reason TOSS is
    # computed gender-wide. It is also what All-Region needs, because that honour
    # is REGION-WIDE AND CLASS-BLIND: there is no 7A All-Region team, there is a
    # Gold Valley All-Region team, drawn from every program in Gold Valley.
    pool = build_pool([t for g in GROUPS for ts in by_group[g].values() for t in ts])
    for group in GROUPS:
        out["awards"][group] = season_awards(
            [t for ts in by_group[group].values() for t in ts], pool=pool)
    region = region_awards(pool)
    out["all_region"] = region["teams"]
    out["all_region_flight_check"] = region["flight_check"]

    for group in GROUPS:
        standings = by_group[group]
        state = states[group]
        out["groups"][group] = {
            # `drecord`/`place` are archived alongside the overall record so a program's
            # year-by-year history reads like a college team's, without re-simulating.
            # `pi` is the TOSS Power Index the season was SEEDED on — archived, never
            # recomputed on read. The rating is a function of the whole gender's results
            # graph, so a later read could only reproduce it by chance, and a ranking
            # that drifts away from the seeds it produced is the NCAA bracket's
            # region-drift bug in a new league.
            #
            # Stored at FULL precision, deliberately. It was rounded to 6dp once, which
            # looks harmless — nothing displays more than 3 — but `sectional_field`
            # seeds on `pi_raw` while `world.jhsaa_group_ranking` re-sorts these stored
            # values and breaks ties by school name. Two teams inside 1e-6 of each
            # other (measured gaps get to 1.0e-06) collapse to the same stored number
            # and the ranking then contradicts the seeds it is supposed to explain.
            # Round for the eye, in the template; never in the archive.
            "standings": {d: [{"school": t.school.name, "record": t.record,
                               "drecord": t.district_record, "place": t.district_place,
                               "pf": t.points_for, "pa": t.points_against,
                               "pi": t.power,
                               # ATR beside the TOSS it is half of — ARCHIVED,
                               # not recomputed on read, exactly like `pi`: it is
                               # the number the Conference pool was ranked on.
                               "atr": atr_snap.get(t.school.name,
                                                   atr_of(t.power, t.win_pct)),
                               # `format_profile` FLATTENED onto the row, same rule as
                               # `pi`/`atr`: computed once here, off the finished season's
                               # schedule, and read back — never rebuilt on a rankings-page
                               # request. See the module note above `format_profile`.
                               **_flat_format_profile(t.schedule)}
                              for t in ts] for d, ts in standings.items()},
            "protected": protecteds[group],
            "sectional": sectionals[group],
            "ward": wards[group],
            "prestate": prestates[group],
            "super_regional": super_regionals[group],
            "semi_state": semi_states[group],
            "divisional": divisionals[group],
            "semi_conference": semi_conferences[group],
            "conference": conferences[group],
            # The names admitted by the DISTRICT GUARANTEE alone (champions who
            # did not win a Zonal) — access without a bye. Replaces the retired
            # TOSS wild cards; old archives keep their "wildcards" key.
            "district_qualifiers": district_q[group],
            "state": state,
        }
        for ts in standings.values():
            for t in ts:
                out["teams"][t.school.name] = t
    _season_cache[ck] = out
    return out


# --- the hand-off to the college recruit board --------------------------------

def graduating_class(gender: str, year: int, *, seed: int = 0, salt: str = "",
                     limit: int | None = None) -> list[Prospect]:
    """Jefferson's entry into the college recruit rankings: this year's JHSAA seniors,
    ranked by what they actually did, carrying their high-school record.

    Roughly 780 girls and 670 boys graduate a year against ~188 board slots per gender,
    so `limit` takes the best of them and the rest simply don't play college tennis —
    which is what happens. Selection is on RESULTS; nothing here touches a player's
    hidden ceiling, so who develops is still unknown.
    """
    season = run_season(gender, year, seed=seed, salt=salt)
    grads = []
    # All-Region is GENDER-WIDE, so it is merged into each class's slate for the
    # honours lookup rather than living inside one — `honors_for` reads by pid.
    region = season.get("all_region") or {}
    for name, ts in season["teams"].items():
        awards = {**season["awards"].get(ts.school.group, {}), "all_region": region}
        ladder = {p.pid: i + 1 for i, p in enumerate(ts.roster)}
        for p in [x for x in ts.roster if x.grade == 12]:
            w, l = ts.records.get(p.pid, [0, 0])
            p.high_school = name
            p.jhsaa = {
                "school": name, "district": ts.school.district,
                "group": ts.school.group, "classification": ts.school.classification,
                "team_record": ts.record, "district_record": ts.district_record,
                "ladder": ladder.get(p.pid, 0), "year": year,
                "record": f"{w}-{l}", "wins": w, "losses": l,
                "honors": honors_for(p.pid, awards, ts.school.group),
                "state_champion": season["groups"][ts.school.group]["state"]["champion"] == name,
            }
            grads.append(p)
    # best first: team strength then ladder position — a #1 at a strong 7A program
    # outranks a #1 at a thin 3A one, which is the whole point of classifications.
    grads.sort(key=lambda p: -p.current_overall())
    return grads[:limit] if limit else grads


def apply_to_class(klass, gender: str, grad_year: int, salt: str) -> int:
    """Replace the Jefferson recruits in an already-generated national class with the
    JHSAA seniors who actually just graduated. Returns how many were swapped.

    Identity swap only — the class SIZE, the Jefferson slot count and the RNG stream
    are all untouched, so `US_JUNIOR_TENNIS_ORIGIN_WEIGHTS["JF"]` still decides HOW MANY
    Jefferson kids reach the board and this decides WHICH ones and what they have done.
    pids are preserved too, so `world_signing` / `world_roster` lookups keyed on the
    slot still resolve.

    Ability comes across, but nothing here touches a recruit's hidden ceiling, so a
    four-year high-school record still tells you who is good TODAY and not who grows.
    """
    slots = [p for p in klass.recruits if getattr(p, "region", "") == "Jefferson"]
    if not slots:
        return 0
    grads = graduating_class(_GENDER[gender], grad_year, salt=salt, limit=len(slots))
    # Rank-match: the best Jefferson senior becomes the best Jefferson recruit, and so
    # on down. IDENTITY and RECORD transfer; ABILITY does not.
    #
    # Copying the graduate's grades across looked obvious and was wrong: the national
    # class has already decided how many Jefferson recruits there are and how they
    # spread across the talent range, and overwriting that re-calibrated the whole
    # board — Jefferson's median recruit jumped to #278 of 2500 and the state swamped
    # the national top 10%. The high-school bands only have to make high-school tennis
    # look right; they are not a second opinion on the recruit curve.
    slots.sort(key=lambda p: -p.current_overall())
    for slot, grad in zip(slots, grads):
        slot.name = grad.name
        slot.hometown = grad.hometown
        slot.high_school = grad.high_school
        slot.jhsaa = grad.jhsaa          # a real Prospect field, so it survives signing
    return min(len(slots), len(grads))


_GENDER = {"men": "boys", "male": "boys", "boys": "boys",
           "women": "girls", "female": "girls", "girls": "girls"}


def mark(school: School, size: int = 72) -> str:
    """The school's athletic crest as inline SVG (see app/jhsaa_marks.py). The ported
    generator takes prep-network's raw record shape, so adapt rather than fork it."""
    from .jhsaa_marks import school_mark
    return school_mark({"name": school.name, "mascot": school.mascot,
                        "colors": school.colors}, size)


def career(school_name: str, gender: str, name: str, grad_year: int,
           salt: str = "") -> list[dict]:
    """A player's four high-school seasons, grade 9 through 12.

    Rebuilt on demand rather than stored: a career is deterministic from (school,
    gender, entry year, seat), so replaying it costs a roster build per year — no duals,
    no persistence, milliseconds. Returns [] if the player can't be resolved (the school
    no longer sponsors, or the name isn't on those rosters).
    """
    g = _GENDER.get(gender, gender)
    school = next((s for s in load_schools(g) if s.name == school_name), None)
    if school is None:
        return []
    out = []
    for grade in GRADES:
        year = grad_year - (12 - grade)
        roster = build_roster(school, year, salt)
        for i, p in enumerate(roster, 1):
            if p.name == name:
                out.append({"year": year, "grade": grade, "ladder": i,
                            "ovr": round(p.current_overall(), 1),
                            "str": p.str_value(), "school": school_name,
                            "classification": school.classification,
                            "district": school.district})
                break
    return out


# --- FAMILY TIES (owner rule 2026-08) ----------------------------------------
# Siblings on a high-school tennis team are unusually common in life, including as
# doubles partners, and a save run long enough eventually rosters a former player's
# child. A tie is narrative METADATA over two pids that already exist.
#
# ‼️ NEVER A NAMING MECHANIC, and never a dice roll. Two rules, both owner-stated:
#   * A tie does not touch a name. `world_jhsaa_dual.lines` archives player NAMES
#     rather than pids and `_jh_line_records` keys off them, so rewriting a surname
#     would silently zero that player's archived record. Metadata makes that
#     impossible rather than fixing it — and needs no era gate (unlike `name_era`),
#     since nothing about generation changes.
#   * There is NO candidate search, suggestion pass or "likely siblings" scan, and
#     none may be added. The owner decides who is related and associates them by
#     hand; the sim's whole job is to store the tie and show it.
#
# Because a tie is just two pids, and a pid is f(school, gender, entry, seat) over
# deterministic rosters, it works unchanged across GENDERS (a brother and sister on
# the school's two teams), across SCHOOLS, and across ERAS — a 2052 freshman can be
# tied to their parent's 2027 pid. A parent tie usually will NOT share a surname,
# which is the last argument for the relationship being explicit.

#: What a tie can be. `twin` is not offered separately — it is DERIVED, since two
#: members sharing an entry year are in the same grade all four years.
FAMILY_RELATIONS = ("sibling", "cousin", "parent")

#: The doubles nudge. Siblings partner SOMETIMES, never by mandate: measured over an
#: eight-player doubles pool `doubles_rating` runs 0.36-0.75 with sd 0.10, so this is
#: about a quarter of a standard deviation — enough to settle a near-tie and nothing
#: more. Applied in the pair SCORING both arrangers already run, so it adds a
#: constant to a pair's score and mutates no Prospect (unlike the `doubles`
#: archetype, which needs a clone). `_order_pairs`'s rank-sum boundary still runs
#: afterwards, so the anti-stacking rule cannot be violated by this.
FAMILY_CHEMISTRY = 0.025


def _family_map(version: str) -> dict:
    """{pid: (family_id, family)}, memoised on the override table's fingerprint —
    the `_transfer_map` shape exactly."""
    hit = _family_cache.get(version)
    if hit is not None:
        return hit
    from app import overrides as ov
    fresh = {}
    for fid, fam in ov.get_jhsaa_families().items():
        for m in fam.get("members") or ():
            if m.get("pid"):
                fresh[m["pid"]] = (fid, fam)
    _family_cache.clear()
    _family_cache[version] = fresh
    return fresh


def families() -> dict:
    """{pid: (family_id, family)} — the fingerprint is resolved HERE, once, never
    inside a per-school or per-player loop (`AAR-jhsaa-playup-fingerprint-query-
    storm.md`: a memo is only as cheap as its key)."""
    from app import overrides as ov
    return _family_map(ov.jhsaa_family_version())


def family_links(fam: dict) -> list[dict]:
    """The family's TIES, as `{a, b, relation}` — one per PAIR the owner actually
    stated, never one per household.

    ‼️ A RELATION BELONGS TO TWO PEOPLE, NOT TO A FAMILY (owner rule 2026-08). It was
    stored once on the family, so a household begun as cousins made every later member
    a cousin of everyone — "it doesn't let you connect siblings if the cousin
    relationship was started". Real families are mixed: siblings, their cousins, a
    parent. Each `family_add` now records the ONE pair it was told about.

    Families written before links existed carry only `relation`, which is exactly what
    they displayed for every pair — so they read back as the complete graph at that
    relation. Derived on READ rather than migrated: the same call the rest of this
    section makes, and the next shape change needs no migration either.

    ‼️ THE LEGACY TEST IS AN ABSENT KEY, NEVER AN EMPTY LIST. A new-format family can
    legitimately hold NO stated ties — remove the middle member of A-B-C and what is
    left is two people who were never tied to each other — and a truthiness check read
    that as "legacy", synthesised a tie nobody stated, and then refused the real one as
    a duplicate when the owner tried to add it."""
    if "links" in fam:
        return [dict(l) for l in (fam.get("links") or ())]
    rel = fam.get("relation", "sibling")
    pids = [m.get("pid") for m in (fam.get("members") or ()) if m.get("pid")]
    return [{"a": pids[i], "b": p, "relation": rel}
            for i in range(len(pids)) for p in pids[i + 1:]]


def _link_between(fam: dict, a: str, b: str) -> dict | None:
    """The stated tie between two members, whichever order it was stated in."""
    for l in family_links(fam):
        if {l.get("a"), l.get("b")} == {a, b}:
            return l
    return None


def family_for(pid: str) -> dict | None:
    """This player's family, or None. The returned dict carries `family_id` and a
    `others` list — every OTHER member, with the relation each bears to `pid`."""
    hit = families().get(pid)
    if not hit:
        return None
    fid, fam = hit
    members = fam.get("members") or []
    me = next((m for m in members if m.get("pid") == pid), None)
    # ‼️ `others` SPLITS INTO STATED AND IMPLIED. A tie is between two people, so a
    # member this player was never tied to directly is in the household and nothing
    # more — claiming a relation for them would be inventing one (A's sibling's
    # cousin is not A's cousin). The page lists the stated ties with their word and
    # the rest as "also in this family", which is exactly what is known.
    others, kin = [], []
    for m in members:
        if m.get("pid") == pid:
            continue
        rel = _relation_from(fam, me, m)
        (others if rel else kin).append({**m, "relation": rel})
    return {"family_id": fid, "label": fam.get("label", ""),
            "relation": fam.get("relation", "sibling"), "note": fam.get("note", ""),
            "members": members, "others": others, "kin": kin,
            "links": family_links(fam)}


def _relation_from(fam: dict, me: dict | None, them: dict) -> str:
    """What `them` IS to `me` — 'sibling', 'cousin', or the parent/child direction.

    ‼️ NO older/younger/twin (owner rule 2026-08). It was derived from entry years,
    which is right — an earlier entry year is the older player — and it still read
    backwards on the page, because the derivation describes THEM while the sentence
    around it ("older sibling of Jane") describes the page's player. Seniority is not
    worth a label that inverts depending on which end of the tie you are standing on,
    and the owner does not want it stated at all: two siblings are siblings.

    PARENT still resolves its direction, because that asymmetry is the whole content
    of the tie — but it is now rendered ON the other member ("Jane Doe · parent"),
    never as an "X of Y" sentence that has the same perspective trap."""
    if me is None:
        return ""
    link = _link_between(fam, me.get("pid", ""), them.get("pid", ""))
    if link is None:
        return ""                       # in the family, but never tied to directly
    rel = link.get("relation", "sibling")
    if rel != "parent":
        return rel
    a, b = me.get("entry"), them.get("entry")
    if a is None or b is None:
        return rel
    # An earlier entry year is the earlier cohort, so `them` is the parent.
    return "parent" if b < a else "child"


def _family_pairs(a_pid: str, b_pid: str, fam_map: dict | None = None) -> bool:
    """True when these two are SIBLINGS — the doubles nudge's only question.
    Takes a PRE-RESOLVED map so a lineup call never re-resolves the fingerprint.

    ‼️ SIBLINGS, NOT THE HOUSEHOLD (owner rule 2026-08: "only siblings get the bonus
    NOT family connections at all"). It asked whether two pids shared a family id,
    which under the per-pair model means cousins — and second cousins reachable only
    through somebody else's tie — drew a partnering bonus nobody asked for. The
    stated link is the fact; anything else is the graph being over-read."""
    m = families() if fam_map is None else fam_map
    ha, hb = m.get(a_pid), m.get(b_pid)
    if not (ha and hb and ha[0] == hb[0]):
        return False
    link = _link_between(ha[1], a_pid, b_pid)
    return bool(link and link.get("relation") == "sibling")


def family_add(pid_a: str, pid_b: str, relation: str = "sibling",
               label: str = "", note: str = "", *, salt: str | None = None,
               where_a: dict | None = None, where_b: dict | None = None) -> dict:
    """Associate two players. Creates a family, or joins `pid_b` to whichever
    family `pid_a` already belongs to (and vice versa). Returns a result dict
    {ok, msg, family_id}; it never raises on a bad input, because every caller
    wants to report the reason rather than 500.

    ‼️ NO same-school and NO same-surname rule. Siblings at different schools are
    ordinary, a brother and sister sit on two different teams, a parent played
    twenty seasons ago, and siblings routinely do not share a surname. The only
    hard rule is that both pids resolve to real players.

    ‼️ EVERY CALL RECORDS ONE PAIR (owner rule 2026-08). The relation is stored on
    the LINK, not on the household, so a family can hold siblings and their cousins
    and a parent at once — and the same person can be tied again and again, which
    was refused outright before ("already in the same family"). Two people who each
    already have a family MERGE them: that is what discovering a tie between two
    households means, and refusing it left the owner with no way to state it.

    ‼️ EACH MEMBER CARRIES ITS OWN `where` — {gender, year, school} — and they are
    NOT interchangeable. A single (gender, year) for both is wrong in exactly the
    two cases this feature exists to serve: a cross-GENDER tie has one member on
    the girls' roster and one on the boys', and a cross-ERA tie (a former player's
    child) has one member in this season and one twenty seasons back, whose seat
    need not exist in the other's year at all. Sharing the context does not
    misresolve, it simply fails to find the second member."""
    from app import overrides as ov
    if relation not in FAMILY_RELATIONS:
        return {"ok": False, "msg": f"unknown relation {relation!r}", "family_id": ""}
    if not pid_a or not pid_b or pid_a == pid_b:
        return {"ok": False, "msg": "need two different players", "family_id": ""}
    m = families()
    fa, fb = m.get(pid_a), m.get(pid_b)
    if fa and fb and fa[0] == fb[0]:
        # ANOTHER tie inside one household — the case that used to be refused. A
        # relation is a fact about two people, so stating a second one adds a link
        # and no member.
        fid, fam = fa
        if _link_between(fam, pid_a, pid_b):
            return {"ok": False, "msg": "those two are already tied",
                    "family_id": fid}
        ov.set_jhsaa_family(fid, {**fam, "links": family_links(fam) + [
            {"a": pid_a, "b": pid_b, "relation": relation}]})
        return {"ok": True, "msg": f"{relation} tie recorded", "family_id": fid}
    if fa and fb:
        # TWO HOUSEHOLDS, now known to be one. Union the members and the stated
        # ties, add the new one, and drop the row that was absorbed — a pid must
        # still resolve to exactly one family, or `families()` picks whichever it
        # met last and half the household disappears.
        (fid, fam), (other_id, other) = fa, fb
        seen = {mm.get("pid") for mm in (fam.get("members") or ())}
        merged = list(fam.get("members") or []) + [
            mm for mm in (other.get("members") or []) if mm.get("pid") not in seen]
        links = family_links(fam) + family_links(other)
        links.append({"a": pid_a, "b": pid_b, "relation": relation})
        ov.set_jhsaa_family(fid, {**fam, "members": merged, "links": links,
                                  "note": fam.get("note") or other.get("note", "")})
        ov.clear_jhsaa_family(other_id)
        return {"ok": True,
                "msg": f"merged the {other.get('label') or 'other'} family into "
                       f"{fam.get('label') or 'this one'}",
                "family_id": fid}
    wa, wb = where_a or {}, where_b or {}
    info = {pid_a: _resolve_member(pid_a, salt=salt, **_where(wa)),
            pid_b: _resolve_member(pid_b, salt=salt, **_where(wb))}
    for p, rec in info.items():
        if rec is None:
            return {"ok": False, "msg": f"no player found for pid {p}", "family_id": ""}
    existing = fa or fb
    if existing:
        fid, fam = existing
        joiner = pid_b if fa else pid_a
        # The new member arrives WITH the tie that brought them: the pair the owner
        # named, at the relation they named. Everyone else in the household is
        # simply family until somebody says otherwise.
        fam = {**fam, "members": list(fam.get("members") or []) + [info[joiner]],
               "links": family_links(fam) + [{"a": pid_a, "b": pid_b,
                                              "relation": relation}]}
        ov.set_jhsaa_family(fid, fam)
        return {"ok": True, "msg": f"added to the {fam.get('label') or 'family'}",
                "family_id": fid}
    fid = uuid.uuid4().hex[:12]        # opaque — NEVER a slug built from a school name
    if not label:
        # Default to the shared surname when there is one, else both surnames.
        sa = info[pid_a]["name"].split(" ", 1)[-1]
        sb = info[pid_b]["name"].split(" ", 1)[-1]
        label = sa if sa == sb else f"{sa}-{sb}"
    # `relation` is kept at the family level for the pages and saves that read it as
    # the household's default; the LINK is what the section actually renders.
    fam = {"label": label, "relation": relation, "note": note,
           "members": [info[pid_a], info[pid_b]],
           "links": [{"a": pid_a, "b": pid_b, "relation": relation}]}
    ov.set_jhsaa_family(fid, fam)
    return {"ok": True, "msg": f"{label} family created", "family_id": fid}


def family_remove(family_id: str, pid: str = "") -> dict:
    """Drop one member, or the whole family when `pid` is empty. A family that
    falls below two members is deleted outright — a tie needs two ends."""
    from app import overrides as ov
    fams = ov.get_jhsaa_families()
    fam = fams.get(family_id)
    if fam is None:
        return {"ok": False, "msg": "no such family"}
    if not pid:
        ov.clear_jhsaa_family(family_id)
        return {"ok": True, "msg": "family removed"}
    members = [m for m in (fam.get("members") or []) if m.get("pid") != pid]
    if len(members) < 2:
        ov.clear_jhsaa_family(family_id)
        return {"ok": True, "msg": "family removed (a tie needs two)"}
    # ‼️ THE DEPARTING MEMBER'S TIES GO WITH THEM. A link naming a pid that is no
    # longer a member is a tie to nobody: `_link_between` would keep matching it and
    # a re-added member would silently inherit the old relation.
    links = [l for l in family_links(fam) if pid not in (l.get("a"), l.get("b"))]
    # ‼️ AND THE HOUSEHOLD MAY NO LONGER BE ONE. A family IS the connected component
    # of the tie graph, so removing a BRIDGE splits it: take A-B, B-C, C-D and drop B
    # and only C-D still holds anything together. Left in one row, A went on being
    # presented as D's family — and shared a family id with them, which is the only
    # thing `_family_pairs` looks at. A member with no ties left is not a household
    # of one; they are simply out.
    parts = _components(members, links)
    if not parts:
        ov.clear_jhsaa_family(family_id)
        return {"ok": True, "msg": "family removed (no ties left)"}
    keep_members, keep_links = parts[0]
    ov.set_jhsaa_family(family_id, {**fam, "members": keep_members,
                                    "links": keep_links})
    # Every other surviving component becomes a family in its own right, under a new
    # id: one pid, one family, whatever the tie graph does.
    for split_members, split_links in parts[1:]:
        ov.set_jhsaa_family(uuid.uuid4().hex[:12],
                            {**fam, "members": split_members, "links": split_links})
    if len(parts) > 1:
        return {"ok": True,
                "msg": f"member removed — the family split into {len(parts)}"}
    return {"ok": True, "msg": "member removed"}


def _components(members: list, links: list) -> list[tuple[list, list]]:
    """The tie graph's connected components, as `(members, links)` pairs, largest
    first — dropping anyone left with no ties at all.

    A family is a component by definition, so this is what makes a removal honest:
    the alternative is a row whose members are only "related" through somebody who
    is no longer in it."""
    adj: dict = {}
    for l in links:
        a, b = l.get("a"), l.get("b")
        if a and b:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    seen, out = set(), []
    for m in members:
        start = m.get("pid")
        if not start or start in seen or start not in adj:
            continue                    # no ties left: not a household of one
        group, stack = set(), [start]
        while stack:
            cur = stack.pop()
            if cur in group:
                continue
            group.add(cur)
            stack.extend(adj.get(cur, ()))
        seen |= group
        out.append((
            [mm for mm in members if mm.get("pid") in group],
            [l for l in links if l.get("a") in group and l.get("b") in group]))
    out.sort(key=lambda part: -len(part[0]))
    return out


def _where(w: dict) -> dict:
    """Normalise one member's lookup context to `_resolve_member`'s keywords."""
    return {"gender": w.get("gender", ""), "year": w.get("year"),
            "school": w.get("school", "")}


def _resolve_member(pid: str, *, gender: str = "", year: int | None = None,
                    salt: str | None = None, school: str = "") -> dict | None:
    """The stored member record for a pid: identity plus the DENORMALISED name,
    school and entry year a tie is rendered from.

    ‼️ Denormalised on purpose. A member may not be enrolled at all — a parent from
    twenty seasons back, or a graduate — so a tie has to render without finding them
    on any current roster. That is safe precisely BECAUSE a tie never rewrites a
    name: a stored name cannot drift from the generated one.

    ‼️ THE SALT IS NOT OPTIONAL AND IS NEVER DEFAULTED TO "". `make_pid` does NOT
    fold in the salt but `_gen_seat`'s NAME draw and `_freshman_class_size` both do,
    so resolving under the wrong salt does not fail — it finds the same pid attached
    to a DIFFERENT PERSON, and stores that stranger's name on the tie (measured:
    "Janet Allister" stored for Kanika McNeal), or misses a seat the real roster has.
    Silent wrong data, which is the failure this codebase keeps relearning. So an
    unset salt is resolved from the WORLD here rather than assumed; pass one
    explicitly only in a test with its own world."""
    if salt is None:
        from app import world as _wd
        salt = _wd.active_salt(_wd.DEFAULT_SEED)
    if not year:
        return None                     # a season is required to build a roster
    genders = (gender,) if gender in ("girls", "boys") else ("girls", "boys")
    for g in genders:
        schools = load_schools(g)
        # The caller almost always knows the team (it is the roster the picker was
        # showing), which turns a whole-association scan into one roster build.
        if school:
            schools = sorted(schools, key=lambda s: s.name != school)
        for sc in schools:
            for p in build_roster(sc, year, salt):
                if p.pid == pid:
                    return {"pid": pid, "gender": g, "school": sc.name,
                            "name": p.name, "entry": p.entry_year}
    return None

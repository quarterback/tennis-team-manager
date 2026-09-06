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
‼️ GROUP 2 (JHSAA rule 2026-09, `docs/AAR-jhsaa-group2-3s3d-postseason-deciders.md`):
Group 2 ALONE plays 3 singles / 3 doubles → 6 points on its road to State (TOC
excepted, like every other pilot). Six is EVEN, so a postseason dual can finish 3-3;
it is then decided by THREE CONCURRENT 10-point tiebreakers — No. 1 singles, No. 1
doubles and No. 2 doubles, the same players who played those flights — and the side
that wins two of the three advances (`_deciding_tiebreaks`). Every other varsity
total is odd and cannot tie; a regular-season dual that ever did would use the JV
ladder (`jv_outcome`: points, sets, games, then a draw) and NEVER the deciders.
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
from engine.fast import HS_PROFILE
from engine.format import PRESETS
from . import injuries as _injuries
from .development import Prospect, generate_prospect, make_pid, overall_to_str
from .player_attributes import GRADE_CEIL, clamp_grade

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "jhsaa", "schools.json")

GROUPS = ("9A", "8A", "7A", "6A", "5A", "4A", "3A", "2A", "1A",
          "Group 1", "Group 2", "Group 3")

# ‼️ GROUPS IS NO LONGER ONE ORDERED LADDER (2046 expansion, extended by the
# Heritage Valley migration). The first nine entries are the enrollment LADDER,
# biggest to smallest; the three "Group" groups (Great Basin + Heritage Valley) are
# their OWN size ordering, big to small ("think of them more as 10A/11A/12A than
# thinking of them as anything weird" — more classifications, but NOT rungs above or
# below 1A). Heritage Valley's eastern arrivals joined this pool rather than the
# ladder because they play in the SAME three geographic areas (Silver Basin/Snake
# River Plain/Bear River Country) the original Great Basin counties already stood
# on — one shared Group system for one shared footprint, split three ways once the
# combined population (222) supported it. Anything that walks GROUPS as a single
# size ordering — play-up, "classes apart" pairing gates, "every class above mine"
# menus — must use LADDER_GROUPS and treat GB_GROUPS separately; plain enumeration
# (archiving, scope bars, renumbering passes) may keep iterating GROUPS.
LADDER_GROUPS = GROUPS[:9]                       # 9A … 1A, a real size ordering
GB_GROUPS = GROUPS[9:]                     # ("Group 1", "Group 2", "Group 3")
assert LADDER_GROUPS[-1] == "1A" and GB_GROUPS == ("Group 1", "Group 2", "Group 3")

#: DISPLAY-only abbreviation (owner, 2026-08). "Group 1"/"Group 2"/"Group 3" is the
#: STORED identity — it keys the standings dict, the archive, `School.group`, and
#: every URL's `group=` argument — and none of that changes here. Every ladder class
#: (9A…1A) is already <= 2 characters and every narrow column/chip in the section
#: was sized for that; "Group 1" is 8, so it wrapped a 46px Class column and ran
#: off a pill-shaped chip. `group_short` is read at RENDER time only.
GROUP_SHORT = {"Group 1": "G1", "Group 2": "G2", "Group 3": "G3"}


def group_short(group: str) -> str:
    """The short form for a tight space (a table column, a chip). Any ladder class
    is already short and passes through unchanged."""
    return GROUP_SHORT.get(group, group)


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
    # 8A/9A's pilot shape (owner rule 2070) — see `dual_format()` and `WIDE_GROUPS`.
    "state_4s5d": DualFormat(n_singles=4, n_doubles=5, doubles_team_point=False),
    # Group 2's postseason shape (JHSAA rule 2026-09) — the association's ONE even
    # dual; a 3-3 is settled by `_deciding_tiebreaks`. See `THREE_THREE_GROUPS`.
    "state_3s3d": DualFormat(n_singles=3, n_doubles=3, doubles_team_point=False),
}
PILOT_GROUPS = ("1A",)          # groups whose road-to-State plays `state_1a`
#: Groups whose road-to-State plays `state_3s3d` (JHSAA rule 2026-09). Scoped like
#: the 1A pilot: the road only (never the TOC, which fields every champion at one
#: shape), never the league season, the early window or the showcases.
THREE_THREE_GROUPS = ("Group 2",)
#: The flights whose 10-point tiebreakers decide a level `state_3s3d` dual, in the
#: order they are reported. Best two of three; the players are the ones who played
#: those flights in the dual itself (owner: "3 concurrent tiebreakers").
DECIDER_FLIGHTS = ("S1", "D1", "D2")
DECIDER_TARGET = 10

# ‼️ 8A/9A PLAY 4S/5D — NINE POINTS (owner rule 2070), AND 7A JOINED THE PILOT
# (JHSAA-approved 7A pilot, owner rule 2026-09 — membership in `WIDE_GROUPS` is the
# whole change; every consumer keys off it). The association's deepest
# classifications play a wider dual than the rest: their whole road to State (and the
# State draw itself) plays 4 singles / 5 doubles instead of 1S/4D, and their EARLY
# non-district window plays it too instead of 5S/2D — the same reasoning that put the
# early window on a different shape in the first place, which is that the window is
# where a program rehearses the card it will have to win with. Fourteen on court.
#
# Everything else about these two classes is untouched: the league season is still
# 3S/4D, the mid-season showcases are still 1S/4D, the TOC is still 1S/4D (it fields
# every classification's champion at ONE shape — the 1A pilot's own carve-out, for the
# same reason), and the individual state tournaments are still 3S+3D and read no dual
# format at all. Nine courts is odd, so a 4S/5D dual cannot tie and no tie-breaking
# logic is needed anywhere; high school has no clinch, so all nine are always played.
WIDE_GROUPS = ("7A", "8A", "9A", "Group 1")  # groups whose road-to-State AND early window play 4S/5D

# ‼️ THE PARASTATE GROUPS (owner spec 2026-09, resized 2026-09): the road still
# qualifies exactly 32 by the existing ladder (UNTOUCHED — `STATE_FIELD` is 32 for
# every one of them), and the at-large committee (`jhsaa_committee`) adds
# `AT_LARGE_BIDS[group]` more, ALWAYS seeded below every road qualifier. The
# Parastate is the opening round the at-larges play into: the `2 × bids` lowest
# seeds pair high-low and the rest bye to the Round of 32, so the Parastate is
# exactly the boundary between reaching the State structure and entering the
# ordinary 32-team championship bracket, whatever the bid count.
#
#   8A / 9A / Group 1 — 48 = 32 road + 16 at-large; 16-dual Parastate (17-48),
#                        seeds 1-16 bye.
#   7A                — 40 = 32 road +  8 at-large;  8-dual Parastate (25-40),
#                        seeds 1-24 bye. 7A carried 16 first; the owner's own
#                        history had it missing ~3-4 TOSS top-32 teams a
#                        gender-season, so 8 rescues the obvious omissions
#                        without a committee "searching for reasons to fill
#                        the back half". Same mechanism, field sized to the
#                        depth of the class.
#
# A district champion who missed the road CONSUMES one of the bids rather than
# adding a berth (`jhsaa_committee.select`). All four are in `WIDE_GROUPS`, so
# every State round including the Parastate plays 4S/5D. See
# `run_state_parastate` and `docs/AAR-jhsaa-computer-ratings-and-at-large-committee.md`.
AT_LARGE_BIDS: dict[str, int] = {"7A": 8, "8A": 16, "9A": 16, "Group 1": 16}
ATLARGE_GROUPS = tuple(AT_LARGE_BIDS)
#: The opening round's name — the at-larges' round. Named in `round_names`, which
#: is what makes `state._jh_split_state` render it as its own tree (no bracket
#: path from a Parastate slot to a main-draw slot the positional canvas could
#: invent).
PARASTATE_NAME = "Parastate"


def at_large_bids(group: str | None) -> int:
    """How many committee at-larges `group` adds on top of its 32 road
    qualifiers — 0 for every class outside the Parastate groups."""
    return AT_LARGE_BIDS.get(group or "", 0)

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
# "epiregional" is the Zonal champions' PLAY-IN (owner rule 2026-09): the eight
# champions of a class play one round among themselves, and the four winners hold
# the State draw's first four bye lines. It sits right after "zonal" so the calendar
# lane, the lineup freeze, the dual shape and the TOSS exclusion all fall out of
# membership, exactly as they do for every other rung.
POSTSEASON = ("sectional", "ward", "regional", "zonal", "epiregional",
              "super_regional", "semi_state", "divisional", "semi_conference",
              "conference", "special_challenger", "state_special", "state", "toc")

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
    through State) plays `state_1a`. Its SHOWCASES play it too (owner rule
    2026-09 — the showcases rehearse the class's own state format, so 1A's are
    2S/3D and Group 2's are 3S/3D, as the 1S/4D classes rehearse 1S/4D). A
    Group 2 showcase can finish level; it is regular season, so it takes the JV
    ladder and can be a TIE — the one place a varsity draw is reachable.

    ‼️ 8A/9A's PILOT (`WIDE_GROUPS`, owner rule 2070) covers the road-to-State on
    the same terms AND the EARLY non-district window, which is the one pilot branch
    that reaches a phase where the two sides of a dual can be in DIFFERENT groups
    (the early window pairs on geography within one classification of each other).
    A dual has one shape, so resolve it with `shape_group` and pass THAT — never
    one side's own group — anywhere a real dual is being played."""
    wide = group in WIDE_GROUPS
    road = phase in POSTSEASON and phase != "toc"
    if wide and (road or phase == EARLY_FORMAT_PHASE):
        return FORMATS["state_4s5d"]
    # ‼️ A SHOWCASE PLAYS THE CLASS'S OWN STATE FORMAT (owner rule 2026-09): the
    # showcases exist to rehearse the lineup a program must win with, so 1A's play
    # 2S/3D and Group 2's play 3S/3D, exactly as the 1S/4D classes rehearse 1S/4D.
    # A Group 2 showcase can therefore finish 3-3 — it is regular season, so it
    # falls to the JV ladder (sets, games, then a TIE), never the deciders.
    rehearsal = road or phase in SHOWCASE
    if group in PILOT_GROUPS and rehearsal:
        return FORMATS["state_1a"]
    # Group 2's 3S/3D (JHSAA rule 2026-09): the road and the showcases, the TOC
    # excepted. The one EVEN shape; `play_dual` settles a postseason 3-3.
    if group in THREE_THREE_GROUPS and rehearsal:
        return FORMATS["state_3s3d"]
    if phase in POSTSEASON or phase in SHOWCASE:
        return FORMATS["state"]
    if phase == EARLY_FORMAT_PHASE:
        return FORMATS["early"]
    return FORMATS["regular"]


def shape_group(phase: str, a_group: str | None, b_group: str | None) -> str | None:
    """The group whose shape governs a dual between programs in `a_group` and
    `b_group` — what to hand `dual_format`, `lineup_need`, `_squad`, `_lineup` and
    `_slot_players` for that dual.

    ‼️ A DUAL HAS ONE SHAPE, AND THE TWO SIDES NEED NOT AGREE ON WHICH. Every pilot
    before 2070 was scoped to the postseason, where a bracket never crosses a
    classification, so resolving the shape from the home side's group was always
    right and `play_dual` said so in a comment. 8A/9A's early window breaks that: the
    early non-district draw pairs a program with one in its own classification OR one
    apart, so an 8A-vs-7A early dual has one side wanting 4S/5D and the other 5S/2D.
    Read off ONE side, the other dresses for a card it is not playing —
    `_squad`/`_slot_players` WRAP rather than raise, so the same player takes two
    courts and the box score still looks plausible.

    ‼️ THE WIDER CARD WINS (owner rule 2070). It does NOT fall back to the narrower
    shape when the two disagree: every program in this association carries the bench
    for a nine-court dual (`ROSTER_SIZE_BAND_BY_CLASS` puts 7A/6A at 19-22 and
    `ROSTER_FLOOR` is a hard 16, against fourteen on court), so a 7A team meeting an
    8A one in the early window simply plays 4S/5D. Forcing the dual down to 5S/2D
    would be defending a roster constraint that does not exist here."""
    fa, fb = dual_format(phase, a_group), dual_format(phase, b_group)
    if fa is fb:
        return a_group
    return a_group if _courts(fa) >= _courts(fb) else b_group


def _courts(f: DualFormat) -> int:
    return f.n_singles + f.n_doubles


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
    return f.n_singles + 2 * f.n_doubles          # 3+8=11 regular, 1+8=9 state, 2+6=8 1A, 3+6=9 Group 2


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

#: ‼️ THE JV TEAM STATE TOURNAMENT IS A PILOT, and this is the season it starts
#: (JHSAA 2068). A year gate rather than a feature flag, for the reason the 1A
#: 2S/3D pilot is gated on its class: archived seasons must keep reading as the
#: years they actually were, and an event that back-applied itself would rewrite
#: them. See `app/jhsaa_jv_state.py`.
JV_STATE_FROM = 2068

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
    # 2046 Great Basin groups, retiered three ways by the Heritage Valley
    # migration (which pooled the original 184 Group 1/2 schools with 38
    # eastern arrivals and re-cut the enrollment-sorted 222 into three even
    # bands rather than two): each spans a wide enrollment range rather than
    # one rung, so the bands blend the ladder classes they cover — Group 1
    # (1066-2556, roughly 6A-9A) blends the 7A/6A bands; Group 2 (407-1059,
    # roughly 3A-5A) blends the 5A/4A bands; Group 3 (57-396, roughly 1A-2A)
    # blends the 2A/1A bands.
    "Group 1": (19, 22),
    "Group 2": (17, 20),
    "Group 3": (14, 17),
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
                         salt: str = "", extra: int = 0) -> int:
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
    roll pretending to be one.

    `extra` is a high-turnout program's additional roster spots (`turnout_extra`),
    spread across the four grades like the rest of the target rather than dropped on
    one cohort — a program that gets a lot of kids out gets them out every year.

    ‼️ IT WIDENS THE DRAW AS WELL AS SHIFTING IT, because the spread is a FRACTION of
    the target (0.35): a deeper program has more year-to-year variation in cohort size
    in absolute terms, which is right — a big turnout is a bigger number to vary. It
    is applied to the target BEFORE the roll for that reason, never added to the
    result afterwards, which would have shifted the mean and left the variance where
    a small program's was."""
    target = (roster_size(classification, school_key, salt) + extra) / len(GRADES)
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
#      best remaining ATR until the seats are filled (owner rule 2070 — every
#      postseason seeding sort runs on ATR, never raw TOSS; see `_atr_key`).
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
# `STATE_FIELD`: the owner's field table below. Most classes crown from 40, but
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
#
# The 2046 expansion re-tiered the table on TALENT, not just headcount (owner
# rule 2026-08): the big-school classes legitimately carry more playoff-worthy
# programs, the smallest carry fewer whatever their size. Tiers, as of the
# Heritage Valley migration:
#   9A/8A/7A — 32, the byeless full bracket (Zonal champions seeded 1-8 with
#     nobody sitting out — the seeding guarantee, not a bye rule, exactly as
#     `test_zonal_champions_are_the_top_seeds_byes_or_not` pins it). The Great
#     Basin departure thinned them under the 40-field's 76-sponsor floor
#     (9A 73/65, 8A 74/72, 7A 81/73 G/B) but a 32-field's floor is only 44,
#     which all three clear comfortably.
#   4A/3A — the full 40 (86/83 and 93/84 G/B, well clear of the 76 floor).
#   ‼️ 6A/5A JOINED 9A/8A/7A ON THE 32-FIELD IN THE HERITAGE VALLEY MIGRATION
#     -- the SAME retune, for the SAME reason, one class-band lower than
#     where it first landed. 24 MOVES + 14 RETIRE_AND_REPLACE schools left
#     the 1A-9A ladder for the new Group 3, and 6A/5A's boys sponsorship
#     (71/71) fell under the 40-field's 76 floor -- a real geographic cost
#     of the realignment, not something to paper over by re-cutting bands.
#     Following the exact precedent this table already set for 9A/8A/7A: a
#     class thinned under its current field's floor moves DOWN a field size
#     rather than degrading loudly (`sc_head`), the moment it clears the
#     smaller field's floor with real room -- 6A/5A sit at 80-81 girls',
#     71 boys' against the 32-field's 44 floor, the same comfortable margin
#     9A/8A/7A clear it by. Do NOT "fix" this back to 40 without re-checking
#     sponsor counts first; a future realignment that refills 6A/5A above 76
#     is the only thing that should move it back.
#   2A/1A — 24 on the fixed `_recovery_24` shape: "the talent really degrades
#     at that level and there's no point even with a lot of teams" (owner).
#     2A returns to the 24 it left in 2033; 1A never left it. This is a
#     TALENT decision, not a headcount one -- 2A/1A sit at 77-87 sponsors,
#     far past any floor, and stay on 24 anyway.
# `_recovery_24` keys on the FIELD SIZE, so the table move is the whole change —
# the "a class could be moved back without touching anything else" promise above.
               # 3A/4A came down 40 -> 32 with the 2056 closures (owner rule
               # 2026-08): at 81/80 sponsors they were under strain as 76-floor
               # classes, and their Specials audits showed the largest,
               # noisiest bubble pools in the state (their brief wider
               # CHALLENGE_SLOTS cap retired with this retune: at the standard
               # shape they run the standard 2). Same retune as Group 1/2
               # below: down a field size, never a smaller version of the 40
               # ladder. In the SAME batch, 9A and 8A went back UP to 40 (owner
               # rule 2026-08, "the last switch") — the association's deepest
               # classes crown from the big field again. 8A clears the
               # 40-field's 76 floor (86/86); ‼️ 9A does NOT (64/64 after the
               # closures, 12 short per gender), so its Semi-Conference
               # degrades LOUDLY every season by design (`sc_head` — the best
               # bodies enter the Conference directly and a warning names the
               # class). That is the documented under-floor behaviour, accepted
               # with the switch; the repair, if ever wanted, is more 9A
               # programs, never a smaller field.
               # 2A joined the 32-field classes in the same 2026-08 batch
               # (owner rule): the 2033 realignment took it to ~95 programs
               # and 93/90 sponsors, its playoff was already meant to "mirror
               # every other classification", and only the FIELD still said
               # otherwise — `state_field_size(group) == 24` is what routes a
               # class to the fixed `_recovery_24` wiring, so this is also
               # what moves 2A onto the dynamic ladder every other class runs.
               # 1A is now the only A-class left on the 24 (with Group 3).
               # ‼️ 9A AND 8A ARE ROAD-32 PARASTATE CLASSES (JHSAA rule 2026-09):
               # they adopted 7A's structure — the road qualifies 32 (this
               # table), the at-large committee adds `AT_LARGE_BIDS` (16) on
               # top, and the Parastate is the opening round — so this table
               # says 32 for them, not 48. The 40-field's `sc_head` degrade 9A
               # used to run every season goes away with it (its 64 sponsors
               # clear the 32-field's 44 floor). No class is on the 40 road any
               # more; the table keeps the shape for the day one is.
STATE_FIELD = {"9A": 32, "8A": 32, "7A": 32, "6A": 32, "5A": 32,
               "4A": 32, "3A": 32, "2A": 32, "1A": 24,
               # 2046 expansion (owner rule): the Great Basin groups are more
               # classifications, full stop -- "think of them more as 10A and
               # 11A than thinking of them as anything weird." Group 1/Group 2
               # each carried 92 sponsors and cleared the dynamic-ladder floor
               # comfortably (76 required at a 40-field) before the Heritage
               # Valley migration re-cut that same 184-school pool (plus 38
               # eastern arrivals) into THREE even bands of 74. That drops
               # both under the 40-field's 76 floor (Group 1 74/66, Group 2
               # 74/71 G/B) -- but BOTH clear a 32-field's 44 floor with the
               # same comfortable margin as 9A/8A/7A/6A/5A, so they take the
               # SAME retune rather than degrading loudly: down a field size,
               # not a reported-and-ignored floor breach. Group 3's 57-396
               # enrollment band sits far enough down the ladder that it
               # plays the BYELESS 24-field shape instead (`_recovery_24`,
               # 1A/2A's own format, a TALENT decision like theirs) --
               # 74/69 sponsors against the 24-field's 48 floor, comfortable
               # either way.
               "Group 1": 32, "Group 2": 32, "Group 3": 24}
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
    # ‼️ THE RECOVERY BLOCKS ARE EQUAL, AND THE LADDER'S OWN GEOMETRY MAKES THEM
    # SO (owner rule 2026-08, the rebalance the Specials were supposed to bring
    # and never got). Semi-State is EXACTLY the Super Regional winners plus the
    # Zonal losers — no readmission — so it is `sr_w + zon_losers` teams and
    # delivers `champions` berths; the Divisionals then take its losers PLUS the
    # Super Regional losers (the readmission moved here), so they are the same
    # size and deliver the same block. Every rung halves: 16 -> 16 -> 16 -> 16.
    #
    # It used to run on a `ceil(4*berths/3)` Semi-State FLOOR, which made that one
    # round the big one — 24 teams, 12 of a 32-field's 24 recovery berths, half
    # the field through a single rung — against 6 from the Divisionals and 6 from
    # the Conference. Owner: "having that many teams get through via semi-state
    # doesn't make any sense." At a 32 field this is now exactly 8 Zonal + 8
    # Semi-State + 8 Divisional + 8 Conference (whose winners play the Specials
    # for those last 8 berths); a 40 field is 8 + 8 + 8 + 16, the Conference
    # absorbing the remainder as it always has.
    ss = _even(sr_w + zon_losers)
    ss_w, ss_l = ss // 2, ss - ss // 2

    # ‼️ THE DIVISIONALS TAKE AT MOST ONE BLOCK, and the Conference takes the
    # rest — capping at `champions` is what makes the three field sizes come out
    # as the owner specified them: a 24 splits its 8 remaining berths 4/4, a 32
    # splits 16 as 8/8, and a 40's 24 go 8/16. Without the cap a 24 field would
    # hand the Divisionals all 8 and never convene a Conference at all.
    dv = _even(min(ss_l + sr_l,
                   2 * min(champions, max(0, berths - ss_w) // 2)))
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

    ‼️ ONE FORMULA FOR EVERY CLASS (2026-08). The 24-field classes used to
    short-circuit to `PROTECTED + WARD_FIELD` because `_recovery_24`'s round
    sizes were fixed and it never convened a Conference with a body reservoir
    to run dry. They now run the same dynamic ladder as everyone else, so they
    take the same two gates — and the answer is unchanged at 48, because a
    24-field Semi-Conference wants only 8 bodies and the ward gate dominates."""
    shape = recovery_shape(group)
    # ‼️ THE WARD GATE IS A FLOOR OF ITS OWN (2026-08). The body-reservoir term
    # alone returned 44 for a 32-field class — but 44 sponsors minus PROTECTED
    # leaves 28 Sectional entrants for a 32-team Ward field, so Wards ran SHORT
    # and an odd field silently sat a team every round after. `run_sectional`
    # cannot manufacture entrants; a class must clear BOTH gates: enough sponsors
    # to fill Wards (PROTECTED + WARD_FIELD) and enough eliminated bodies for the
    # Semi-Conference. The 40-field's 76 already dominated the ward gate, which
    # is why the miss was invisible until the 32 retune created a shape where the
    # reservoir term was the smaller of the two.
    if not shape["conference"]:
        return 0
    return max(PROTECTED + WARD_FIELD, WARD_FIELD + shape["semi_conference"])


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
    # 2046 Great Basin groups, retiered three ways by the Heritage Valley
    # migration (see the ROSTER_SIZE_BAND_BY_CLASS note above — same enrollment
    # ranges). Each classification spans several ladder classes' worth of
    # enrollment, so the band is a BLEND of the classes it covers, per the
    # section rule (smaller = thinner mean, wider spread): Group 1
    # (1066-2556 ≈ a 6A-9A mix) sits between 7A and 6A; Group 2 (407-1059 ≈
    # a 3A-5A mix) sits between 5A and 4A; Group 3 (57-396 ≈ a 1A-2A mix) sits
    # between 2A and 1A. `classification` on these schools IS
    # "Group 1"/"Group 2"/"Group 3", so `School.talent_group` reads these
    # keys — without them every Great Basin/Heritage Valley roster build
    # KeyErrors.
    ("Group 1", "boys"): (57.0, 15.0), ("Group 1", "girls"): (52.0, 14.0),
    ("Group 2", "boys"): (48.5, 18.5), ("Group 2", "girls"): (44.0, 17.5),
    ("Group 3", "boys"): (38.5, 21.5), ("Group 3", "girls"): (34.5, 20.5),
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
#   coaching     generates NOTHING extra: same ceiling, same arrival, same spread. The
#                only edge is that its players are likelier to REACH the ceiling they
#                already had — the same governor `neglect` runs negative, over a WIDE
#                per-program band so tagged programs differ; see `coaching_quality()`
#   turnout      generates the same players, just MORE of them — a deep squad, most
#                useful in the small classifications; see `turnout_extra()`
#   neglect      generates normal CEILING but develops it SLOWER — the same governor,
#                run in reverse; see `neglect_severity()`
#   upstart      a TEMPORARY multi-year run, rolled per world — see `upstarts()`
#   (untagged)   normal
#
# ‼️ RETIRED, AND KEPT ONLY SO EXISTING TAGS STILL RESOLVE (owner, 2026-08): both
# `development` and `doubles` DISTORTED THE FIELD and the owner stopped using them.
# They are out of `EDITABLE_ARCHETYPES`, so nothing can be newly tagged with either,
# and the seed file ships with no program carrying one — but the rows stay, because
# `_program_mod` reads this table by name and a save that still holds one of these as
# a per-save override must keep generating the roster it has been generating rather
# than silently reverting to untagged.
#
#   development  RETIRED — it raised POTENTIAL (`pot` +6.0) and widened the spread on
#                top of accelerating maturity, so it did expand what a player could
#                become. `coaching` is its replacement and deliberately does neither:
#                "it doesn't expand a player's skillset, just makes them potentially
#                more likely to reach [their ceiling]" (owner).
#   doubles      RETIRED — a per-match lift on the doubles lineup alone, which moved
#                too much of a dual for a program trait nothing else could see.
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
                    "label": "Development program (retired)"},
    "doubles":     {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Doubles school (retired)"},
    # ⚠️ COACHING (owner rule 2026-08) — good coaching, and NOTHING ELSE. It is the
    # replacement for the retired `development`, and the whole point of the rewrite is
    # what it does NOT do: "it doesn't expand a player's skillset, just makes them
    # potentially more likely to reach" their ceiling. So `mean`, `spread` and `pot`
    # are all untouched — a well-coached program draws exactly the same players, with
    # exactly the same ceilings and the same variance, as an untagged one. Only the
    # RATE at which a player closes on the ceiling they already had moves, which is
    # the same `mature` governor `neglect` runs negative.
    #
    # ‼️ AND IT CANNOT OVERSHOOT, which is what makes "more likely to REACH" literally
    # true rather than a description of something stronger. `_gen_seat` clamps the
    # result to `DEV_CAP` (0.98), so the lift saturates against the ceiling: a player
    # already finishing near it gains almost nothing, and the ones it actually moves
    # are those who would otherwise have left high school well short of what they had.
    # A coaching program cannot make anybody better than they could have been.
    #
    # Like `neglect`, the real per-school number is drawn by `coaching_quality()` and
    # this row's `mature` is a 0.0 placeholder.
    "coaching":    {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Well-coached program"},
    # ⚠️ TURNOUT (owner rule 2026-08) — a program that simply gets a lot of kids out
    # for the team. It changes NOTHING about who those kids are: `mean`, `spread`,
    # `pot` and `mature` are all untouched, so the extra players are drawn from the
    # same distribution as everyone else's. "Not necessarily all talented, but depth
    # helps" (owner) is the exact spec, and it is the third distinct thing an
    # archetype can move — `blue_blood` changes the DRAW, `coaching`/`neglect` change
    # the RATE, this changes the COUNT.
    #
    # It matters most in the small classifications, which is why it exists: "some
    # schools even at the small school level have big school sized squads". A 1A
    # program bands at 14-16 and a 9A at 20-24, so a tagged 1A can carry a squad the
    # size of a big school's while still generating 1A players.
    #
    # ‼️ IT IS NOT A FREE STRENGTH BONUS, BUT IT IS NOT NOTHING EITHER, and the
    # difference is order statistics rather than a thumb on the scale: more draws from
    # the same distribution means a slightly better best player and a much deeper
    # bench. That is what depth is, and it is why the tag is worth having — a bigger
    # squad fills the JV season, survives the rest/rotation rules, and cannot be
    # thinned below a playable lineup by a bad `_freshman_class_size` roll.
    #
    # The real per-school number is drawn by `turnout_extra()`; this row's placeholder
    # is 0.0 like `neglect`'s and `coaching`'s, for the same reason.
    "turnout":     {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "High turnout"},
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


# COACHING — the positive half of the same per-grade maturity governor `neglect` runs
# negative.
#
# ‼️ A WIDE BAND, DELIBERATELY WIDER THAN NEGLECT'S (owner rule 2026-08). The first
# version mirrored `NEGLECT_MATURE` exactly, on a symmetry argument — good programs and
# bad ones pulling on one lever by the same amount so the association's level does not
# drift. That was tidy and it was the wrong shape for what this tag is FOR: a narrow
# band makes every well-coached program develop at nearly the same rate, so tagging
# twenty of them produces twenty copies of one trajectory. The owner's point is that
# the tag should be worth applying broadly — "a very small set of dev gains to very
# large and obviously lots of in-between" — which needs the SPREAD, not the mean.
#
# So the low end is deliberately near-nothing (a program that is a bit better organised
# than average, worth under an OVR point on a senior) and the high end is genuinely
# program-defining. Uniform across it, so the in-between is where most tagged programs
# land. `neglect` keeps its own narrower band: dampening has a hard floor that
# accelerating does not (see `NEGLECT_MATURE` — past `DEV_MIN_STEP` it would reverse
# development rather than slow it), so the two are not symmetric in what they CAN do.
#
# ‼️ WHAT KEEPS THE TOP END HONEST IS `DEV_CAP` (0.98), NOT THE CONSTANT. The step is
# added once per grade elapsed, so at the top of this band a senior carries +0.18
# maturity — and `_gen_seat` clamps the result, so the lift saturates against the
# ceiling the player already had. A kid on track to finish at 0.90 of their ceiling
# gains a little; one on track for 0.70 gains a lot; nobody exceeds what they could
# have been. That is the whole rule ("doesn't expand a player's skillset, just makes
# them potentially more likely to reach"), and it is enforced by the clamp rather than
# by keeping the number small.
COACHING_MATURE = (0.004, 0.060)


# TURNOUT — how many EXTRA players a high-turnout program carries on top of whatever
# its classification band gave it. A range for the same reason coaching's is: a program
# with a big turnout is not one fixed size, and the tag should be worth applying to
# many schools without producing many identical squads.
#
# Sized against the ladder rather than picked for feel: the classification bands run
# 14-16 at 1A up to 20-24 at 9A, a spread of about ten. So the bottom of this band is a
# noticeably deeper squad and the top lifts a 1A clear past a typical 9A — which is the
# case the owner named. Real rosters already run 12-36 without it (`ROSTER_FLOOR` has
# no ceiling above it, deliberately), so even the top of this band stays inside the
# range the association already produces.
TURNOUT_EXTRA = (4, 12)


def turnout_extra(school_name: str, salt: str = "") -> int:
    """Extra roster spots for a high-turnout program — drawn once and durable, the
    `neglect_severity` / `coaching_quality` idiom. Seeded on the school alone, never
    the year: a program's turnout is a durable community fact, not something that
    reshuffles season to season."""
    return random.Random(f"{salt}|jhsaa-turnout|{school_name}").randint(*TURNOUT_EXTRA)


def coaching_quality(school_name: str, salt: str = "") -> float:
    """This program's stable per-grade maturity BONUS — positive, drawn once from
    `COACHING_MATURE` and durable for as long as the school is tagged `coaching`.

    Seeded on the school alone, never the year or the player: a coaching staff and a
    development culture are durable program traits, so this must not reshuffle on
    read or drift season to season. The exact `neglect_severity` idiom, one sign over."""
    return random.Random(f"{salt}|jhsaa-coaching|{school_name}").uniform(*COACHING_MATURE)


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
           # Extra roster SPOTS, not a change to who fills them — the one lever here
           # that moves a count rather than a player. See `turnout_extra`.
           "roster": 0, "kind": kind}
    if kind == "neglect":
        # The table row is a 0.0 placeholder (see ARCHETYPES) — the real, per-school
        # number lives here, same reason `upstart`'s lift is layered on below rather
        # than read off the table.
        mod["mature"] += neglect_severity(school.name, salt)
    elif kind == "coaching":
        # The same governor, the other sign. Nothing else about the program's draw
        # moves — that is the whole distinction from the retired `development`.
        mod["mature"] += coaching_quality(school.name, salt)
    elif kind == "turnout":
        # More seats, same players. Nothing that shapes a DRAW is touched here.
        mod["roster"] += turnout_extra(school.name, salt)
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
    # ‼️ OUT-OF-STATE AFFILIATE MARKER (owner rule -- JHSAA's first affiliate
    # members, the same as OSAA/WIAA/CIF/AZ/NV admitting border schools).
    # Empty for every ordinary Jefferson school. A real state name (e.g.
    # "Oregon", "Wyoming") means this program's REAL geography is that city/
    # state, not a Jefferson city/county -- `area`/`county` on an affiliate
    # exist ONLY for internal district/league-draw clustering and are NEVER
    # shown; the display layer must show the real `city`/`state` and "Out of
    # State" instead of the ordinary Jefferson county line. NEVER append a
    # state suffix to `name` anywhere (standings, brackets, awards, title
    # board...) -- "Bend Senior High", never "Bend Senior High (OR)". These
    # schools are ordinary members competitively (classification, leagues,
    # districts, rankings, honors, postseason, TOSS) -- only their GEOGRAPHY
    # display differs. See `scripts/jhsaa_promotions_and_affiliates.py`.
    state: str = ""

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
    # A DRAWN regular-season dual (JHSAA rule 2026-09). Unreachable on today's
    # shapes — every varsity regular-season format is odd — and kept so the rule
    # the owner restated ("cumulative sets, cumulative games, and if still tied it
    # remains a tie", the JV ladder) has somewhere to land if a shape ever changes.
    # A POSTSEASON dual is never drawn: a level one is settled by the deciders.
    ties: int = 0
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
    # {(pid, pid) sorted: [lines together, wins together]} — how often two players
    # have PARTNERED this season and how it went, written by `_credit` on every
    # doubles line. The whole input to partner continuity (owner rule 2026-09):
    # pairs that have worked together are more likely to stay together — see
    # `_established_units` / `partner_chemistry`. Season-scoped by construction
    # (a TeamSeason lives one season), so nothing persists across years.
    pair_counts: dict = field(default_factory=dict)
    # ‼️ INJURIES (owner rule 2026-08, ported off the college model — see
    # `app/injuries.py`). VARSITY ONLY: `play_dual` rolls these, `play_jv_dual`
    # never touches this dict — JV is deliberately injury-blind (`jv_pool`),
    # because the whole point of JV is more of the roster getting real minutes,
    # not fewer.
    #
    # `injuries`: pid -> duals remaining out. A healthy player has NO key (never
    # 0 — recovery deletes the row), so `pid in ts.injuries` is the whole
    # availability check. `injuries.SEASON_ENDING` (-1) is stored for a
    # season-ending injury and never ticks down.
    #
    # `injury_log`: the archived record — one row per injury actually rolled,
    # `{pid, name, dual_index, duals_out, season_ending}` — `dual_index` is this
    # team's OWN dual count (`len(ts.schedule)`) at the moment it happened, an
    # ordinal within their season, not a calendar week (the JHSAA has no clock
    # inside a season — see `world.jhsaa_match_dates`). Kept as a list of dicts,
    # like `matches`, because a season logs one of these per injury, not per
    # player. Never on the Prospect — see `injuries.py`'s own note on cached,
    # globally-shared Prospects.
    injuries: dict = field(default_factory=dict)
    injury_log: list = field(default_factory=list)

    @property
    def record(self) -> str:
        # W-L-T only when a T exists — the JV record's own rule, so every archived
        # varsity record (none of which can carry a tie) reads exactly as before.
        return (f"{self.wins}-{self.losses}-{self.ties}" if self.ties
                else f"{self.wins}-{self.losses}")

    @property
    def district_record(self) -> str:
        return f"{self.dwins}-{self.dlosses}"

    @property
    def win_pct(self) -> float:
        n = self.wins + self.losses + self.ties
        return (self.wins + 0.5 * self.ties) / n if n else 0.0   # a T is a half, as JV

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


def jv_postseason_cut(group: str | None = None) -> int:
    """Where the ladder cut sits for the JV STATE TOURNAMENT's eligibility freeze.

    ‼️ THE JV SEASON'S OWN CUT NEVER MOVES (owner rule 2070). `jv_pool` is rank #12
    down for every classification, 8A/9A included — the JV league season is staffed
    off the 3S/4D varsity eleven and nothing about the 4S/5D pilot touches it. What
    moves is the POSTSEASON freeze: 8A/9A dress FOURTEEN in the varsity playoffs, so
    their JV playoff field is frozen below that, at rank #15 down.

    ‼️ AND IT IS NOT AN EXCLUSION. A player may be in the varsity playoff fourteen
    AND the JV championship squad — the owner is explicit that the overlap does not
    matter — so this is where the JV bracket's own line is drawn, not a rule about
    who is spoken for. Derived from `lineup_need` rather than typed, so it follows
    the pilot's shape if the shape ever moves."""
    return max(lineup_need("regular", group),
               lineup_need(EARLY_FORMAT_PHASE, group),
               lineup_need("state", group))


def jv_state_pool(ts: TeamSeason) -> list:
    """`jv_pool` for the JV STATE TOURNAMENT — cut at `jv_postseason_cut`."""
    return _order(ts)[jv_postseason_cut(ts.school.group):]


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
# (version, year) -> the ENROLLED slice of the ledger + its inbound index; see
# `enrolled_transfers`. Dropped whenever `_transfer_map` re-reads the table.
_transfer_year_cache: dict = {}
# (salt, pid) -> the mover's name. A pid names one person for the life of a save,
# so this is never invalidated by a transfer edit — only by `reset_schools()`,
# because the name draw is era-gated.
_transfer_name_cache: dict = {}
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
    """Old display name -> the name that school goes by now.

    ‼️ THIS IS TWO SOURCES MERGED, and the second one is the only one a rename
    applied straight to `data/jhsaa/schools.json` ever reaches.

    The FILE half is generated from the git history of `import_jhsaa.RENAMES`
    (`scripts/jhsaa_former_names.py`) and covers every rename that went through the
    importer. But the association is also renamed by one-time transform scripts that
    edit the committed data directly — the whole 2026-08 batch did — and those never
    touch `RENAMES`, so they produce no row in that file. An archived season then
    keeps reading under the OLD name with nothing to relabel it: the program page
    under the NEW name shows no pre-rename seasons and career totals that silently
    start at the rename, while the old name is no longer a school and 404s. That is
    exactly the fault this table exists to prevent, arriving through the door the
    table's generator cannot see.

    The LIVE half closes it, and needs no new store: **a JHSAA display rename MUST
    stamp `School.source` with the pre-rename name** (generation keys pids on
    `source or name`), so the mapping is already in the data — `source` IS the old
    display name and `name` is what the school goes by now. Reading it here is a
    PROJECTION of a fact the rows already carry, not a second source of truth.

    ‼️ A LIVE NAME ALWAYS WINS, so a `source` that is ALSO some school's current
    display name is dropped rather than aliased — 6 of them exist (Ashbury Central,
    River Plain, Breakwater, Goodman, Canal View, Treasure Valley are each one
    school's former identity and a DIFFERENT school's live name). Aliasing those
    would file the live school's own archived seasons under its neighbour, which is
    the reissued-name trap `current_name` was written for one level up.

    Read over ALL rows, both genders: an alias is a fact about the SCHOOL, and the
    two gender fields carry the same `name`/`source` strings."""
    global _former_cache
    if _former_cache is None:
        try:
            with open(_FORMER, encoding="utf-8") as fh:
                built = dict(json.load(fh)["former_names"])
        except (FileNotFoundError, ValueError, KeyError):
            built = {}
        rows = _rows()
        live = {r["name"] for r in rows}
        for r in rows:
            src = r.get("source")
            if src and src != r["name"] and src not in live:
                built[src] = r["name"]
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
    _talent_era_cache.clear()
    _career_era_cache.clear()
    _expo_cache.clear()
    _expo_world.clear()
    _transfer_name_cache.clear()
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


def _resolve_era(setting: str, cache: dict) -> int:
    """Shared resolver for the four era gates (`name_era`, `dev_era`,
    `talent_era`, `career_era`). They all answer the same question — what is the
    first entry year built the NEW way — and self-configure identically: an
    explicit `worldconfig` value wins; otherwise a save with an archive sets the
    era to the first cohort not yet in the building, and a fresh save gets 0, so
    everything is new.

    ‼️ `world_jhsaa.year` is the ZERO-BASED WORLD INDEX (the DB key) while an
    entry year is a CALENDAR year — the conversion `world.jhsaa_season_year`
    makes. Stored raw, an era would be e.g. 5 and EVERY existing cohort would
    satisfy `entry >= era`, which is the archive-wide rewrite these gates exist
    to prevent. The newest archive's season is BASE_YEAR + index + 1 and its
    freshmen entered that year, so the first unseen cohort is +2.

    ‼️ Memoised on the DB path and cleared by `reset_schools()`. Never resolve it
    per seat: it opens a SQLite connection on a miss and a roster build would
    touch it once per player (the fingerprint-in-a-loop trap,
    docs/AAR-jhsaa-playup-fingerprint-query-storm.md)."""
    from .dbpath import resolve_db_path
    key = resolve_db_path()
    got = cache.get(key)
    if got is not None:
        return got
    from . import worldconfig
    raw = worldconfig.get(setting)
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
                from .world import BASE_YEAR
                era = BASE_YEAR + int(r[0]) + 2
        except sqlite3.Error:
            era = 0                      # no archive yet — a fresh save, all new
        worldconfig.set(setting, str(era))
    cache[key] = era
    return era


def name_era() -> int:
    """The first entry year that draws new-era names for this save (see above)."""
    return _resolve_era("jhsaa_name_era", _name_era_cache)


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
    """The first entry year that develops on the per-player curve model
    (`_dev_maturity`). Superseded from `career_era()` on — see §22."""
    return _resolve_era("jhsaa_dev_era", _dev_era_cache)


_talent_era_cache: dict = {}


def talent_era() -> int:
    """The first entry year whose talent CEILINGS are compressed
    (`development.compress_talent` — owner rule 2026-08).

    ‼️ BOUNDED ABOVE BY `career_era()`: the career model frees the high-school
    scale (§24), so compression applies only to cohorts in the window BETWEEN
    the two eras. `_gen_seat` owns that test — see `_compresses()`."""
    return _resolve_era("jhsaa_talent_era", _talent_era_cache)


def _compresses(entry: int) -> bool:
    """Whether this cohort's ceilings are squashed. Compression existed to stop
    high-school ceilings overrunning the COLLEGE scale; the career model separates
    the two scales instead and translates at graduation, so it stops here."""
    return talent_era() <= entry < career_era()


_career_era_cache: dict = {}


def career_era() -> int:
    """The first entry year built on the CAREER model (starting ability / career
    peak / yearly capacity — proposal §22), on a FREE high-school scale (§24).

    The `dev_era()` / `talent_era()` idiom exactly, and for the same reason:
    players are regenerated from seed, so an ungated change re-rates every
    archived roster's ladder, player cards and awards. Pre-era cohorts keep the
    maturity-curve model and the compressed ceilings byte-for-byte; the
    association converges over one four-year graduating cycle."""
    return _resolve_era("jhsaa_career_era", _career_era_cache)


# --- THE CAREER MODEL (owner rule 2026-08, proposal §22-§24) ------------------
#
# Replaces "age reveals a fixed ceiling" outright. A player is four things drawn
# once at entry, and grade only says which point of their own path to read:
#
#   STARTING ABILITY   where they are on day one
#   CAREER PEAK        the best they could be DURING HIGH SCHOOL — not a debt the
#                      engine owes them by senior year, and not an adult ceiling
#   YEARLY CAPACITY    four independent draws: how much they can realise a year
#   EXPOSURE           what they actually played, scaling realisation (not wired
#                      yet — `exposure` defaults to full; proposal §7)
#
# ‼️ START IS A FRACTION OF PEAK, DRAWN GRADE-FREE. That is the whole break from
# `_dev_maturity`: nothing here reads the grade to decide how much of a player is
# visible, so a freshman may legitimately arrive at 61 with a peak of 63 while a
# team-mate arrives at 38 with a peak of 64. Career shapes — ready, early,
# steady, late, spike, stagnant, high-peak-never-realised — are EMERGENT from the
# capacity draws and are never labelled or stored.
#
# ‼️ NEVER blend a peak-anchored start with an independent population draw and
# clamp the result at peak. That clamp fires constantly for low-peak players,
# silently sets start = peak, and manufactured a 26% "already finished" share and
# 53% of players with no growth year in a first parameterisation — an artefact of
# the clamp presented as a design outcome. Multiply a fraction instead; nothing
# is clamped at generation.
#
# ‼️ THE SENIOR TAPER IS PRODUCED BY THE PEAK CLAMP, NOT BY ANY AGE RULE.
# Capacity is drawn identically in all four years. Late years grow less only
# because most players have already reached their peak and a big late draw has
# nowhere to land — which is what the owner asked for ("breakouts are usually
# sophomore and junior; senior year tends to be incremental"). `CAREER_OVERFLOW`
# is therefore load-bearing in BOTH directions: at 0.0 peak is a hard wall, and
# at 1.0 the taper disappears entirely and a senior year gains exactly as much as
# a freshman year. Swept 0.00/0.15/0.30/0.50/1.00, the year-3-over-year-1 gain
# ratio runs 0.62 / 0.69 / 0.75 / 0.82 / 1.00.
CAREER_PEAK_BAND = (0.85, 1.10)     # career peak as a multiple of the drawn ceiling
CAREER_START_BAND = (0.40, 0.95)    # starting ability as a share of career peak
CAREER_BIG_RATE = 0.30              # chance a given year is a BIG development year
CAREER_BIG_BAND = (7.0, 15.0)       # a big year, in OVR points
CAREER_STEP_BAND = (0.0, 3.5)       # an ordinary year
CAREER_OVERFLOW = 0.20              # share of a gain that lands PAST career peak


def _career_plan(school_key: str, entry: int, seat: int, salt: str,
                 ceiling: float) -> tuple[float, float, list[float]]:
    """(starting ability, career peak, four yearly capacities) for one player.

    Deterministic from the same identity the pid is built from, so the whole
    four-year path is fixed at entry and each season just reads it off. Rolled on
    its OWN rng stream (`jhsaa-career`), like the prodigy and dev rolls — never
    off the main roster rng, which would shift every subsequent draw and
    regenerate everyone."""
    r = random.Random(f"{salt}|jhsaa-career|{school_key}|{entry}|{seat}")
    peak = ceiling * r.uniform(*CAREER_PEAK_BAND)
    start = peak * r.uniform(*CAREER_START_BAND)
    caps = [r.uniform(*CAREER_BIG_BAND) if r.random() < CAREER_BIG_RATE
            else r.uniform(*CAREER_STEP_BAND) for _ in range(4)]
    return start, peak, caps


#: How a program's per-grade `mature` bonus/drag (`coaching_quality`,
#: `neglect_severity`) becomes a career-model number.
#:
#: ‼️ THE PROGRAM LEVER HAS TO BE TRANSLATED, NOT REUSED. `mature` is a share of a
#: FIXED CEILING that has surfaced by a given grade — the legacy model's only
#: currency, and a concept the career model does not have: here a player is a start,
#: a peak and four yearly capacities, and `_apply_career` overwrites current ability
#: outright. A `mature` bonus therefore reaches a career-era player through NOTHING,
#: which is exactly what happened: `coaching` and `neglect` were both silently inert
#: for every cohort in a fresh save, because `_gen_seat` passes `maturity_range=(1.0,
#: 1.0)` on that path and never hands `mod` to `career_ability` at all.
#:
#: The career-model equivalent of "reaches more of what they had" is realising more of
#: each YEAR'S CAPACITY — the same quantity `exposure` scales, and for the same reason
#: (a season's development is what you got out of it). So it multiplies `gain`.
#:
#: ‼️ AND THE PEAK IS STILL THE PEAK. `career_ability` clamps gains at `peak` with
#: `CAREER_OVERFLOW` past it, so a coaching program moves a player UP THEIR OWN CURVE
#: faster and cannot lift them past the career they were drawn — the career model's
#: own expression of "doesn't expand a player's skillset". `DEV_CAP` does that job on
#: the legacy path; this is the same guarantee, enforced by machinery that was already
#: there.
#:
#: CALIBRATED, not chosen: swept 5-30 against the two things that matter, the senior
#: OVR gain and the ceiling drift. The career model damps this lever much harder than
#: the legacy one did (the peak clamp is doing most of the work), so matching the
#: legacy path's measured +1.5/+3.8/+7.0 takes a much larger multiplier here than the
#: naive 1:1 reading of `mature` would suggest — which is the whole reason this is a
#: translation constant rather than the raw number. At 20 a career-era senior gains
#: ~+3.2 OVR across the band against the legacy path's ~+3.8, and displayed ceilings
#: drift +0.35 on a ~66 mean (0.5%) — the residual from reaching peak a year sooner
#: and therefore spending longer in the overflow regime, which no constant removes.
#: One constant, one per-school draw, both models — never a second band to keep in
#: step by hand.
CAREER_COACH_K = 20.0

#: ‼️ THE DRAG GETS ITS OWN, GENTLER CONSTANT. The two bands were authored against
#: the LEGACY model's floor rule, not against each other: `NEGLECT_MATURE` is narrow
#: because a per-grade drag past `DEV_MIN_STEP` would REVERSE development, while
#: `COACHING_MATURE` is wide because the owner wants tagged programs to differ. Run
#: through one multiplier those become lopsided in the career model — measured, the
#: harshest neglect took a senior -8.3 OVR against the strongest coaching's +6.5, so
#: the same code would have made an untouched archetype markedly harsher than the one
#: being added. At 15 the drag means **-2.3 OVR** and bottoms at -4.5, against
#: coaching's +2.4 mean; coaching keeps the longer tail, which is the difference the
#: owner asked for and not one this constant should invent.
#:
#: ‼️ NEGLECT WAS EQUALLY BROKEN BEFORE THIS, and that is why it is being calibrated
#: at all: it rides the same `mature` lever, so it too did nothing for any career-era
#: cohort. Fixing only the new archetype would have left its own mirror inert.
CAREER_NEGLECT_K = 15.0


def coach_factor(mature: float) -> float:
    """A program's `mature` bonus/drag as a multiplier on yearly capacity.

    1.0 for an untagged program, so the whole association is unchanged by this
    existing. Floored well above zero: a drag must never stop development outright,
    which is `neglect`'s own founding rule ("doesn't mean players won't get what they
    get normally, it just dampens it")."""
    k = CAREER_COACH_K if mature >= 0 else CAREER_NEGLECT_K
    return max(0.25, 1.0 + mature * k)


def career_ability(school_key: str, entry: int, seat: int, grade: int,
                   salt: str, ceiling: float,
                   exposure: dict | None = None, coach: float = 1.0) -> float:
    """This player's ability at `grade` under the career model.

    `exposure` maps a GRADE to how much of that year's capacity the player
    actually realised (1.0 = a full varsity season). Absent, every year realises
    in full — the pre-odometer behaviour, and what a world with no archived
    participation must read.

    `coach` is the program's development multiplier (`coach_factor`) — 1.0 for an
    untagged program. It scales the same yearly capacity `exposure` does, because
    they are the same kind of thing: how much of a year's available development a
    player actually banked."""
    start, peak, caps = _career_plan(school_key, entry, seat, salt, ceiling)
    v = start
    for i, g in enumerate(range(10, grade + 1)):
        base = caps[i] * ((exposure or {}).get(g - 1, 1.0))
        # ‼️ COACHING ACCELERATES TOWARD THE PEAK AND NEVER PAST IT. The multiplier
        # is applied to the run UP to `peak`; the overflow a year earns beyond it is
        # the UNCOACHED amount. Applied to the whole gain instead, a coaching program
        # would push players further past their own drawn career — and because
        # `_apply_career` lifts displayed potential to meet ability whenever a player
        # overflows (the POT-never-below-OVR display rule), that surfaced as tagged
        # programs' CEILINGS drifting up: measured +0.23 OVR with 80 of 300 seniors'
        # ceilings raised, and worse the harder the tag was pushed. "Doesn't expand a
        # player's skillset, just makes them potentially more likely to REACH" is a
        # rule about exactly this line, and reach is not exceed.
        gain = base * coach
        if v >= peak:
            gain = base * CAREER_OVERFLOW
        elif v + gain > peak:
            gain = (peak - v) + max(0.0, v + base - peak) * CAREER_OVERFLOW
        v += gain
    return v


# --- THE EXPOSURE ODOMETER (proposal §7 / §22.2) ------------------------------
#
# Playing contributes to development because participation is developmental
# exposure — the system never cares whether the player WON (no wins, no records,
# no TOSS, no opponent quality; §4.1). Appearances accumulate as varsity-
# equivalent units (a JV dual is worth `EXPO_JV_UNIT` of a varsity one), the
# total SATURATES at `EXPO_CAP`, and the season's realisation factor runs from
# `EXPO_FLOOR` (never dressed — adolescence happens anyway) to 1.0 (a full
# varsity season). Split-time players land between the levels with no category
# of their own, and a JV No. 1 who plays every dual banks more than a JV player
# who barely appears — the JV ladder matters (owner, 2026-08).
#
# On these constants a full ~16-dual JV season lands ≈0.81 and an 8-JV/6-varsity
# split ≈0.87 — the proposal's illustrative 0.80 / 0.90 table, produced by one
# continuous rule instead of five buckets.
#
# ‼️ A season with NO archive reads as FULL realisation, not as the floor. That
# is what a fresh world's year 0, every pre-odometer season, and the calibration
# scripts must see — the factor only ever applies where participation was
# actually recorded. (`career_ability` treats a missing grade the same way.)
EXPO_FLOOR = 0.55                 # realisation for a rostered kid who never dressed
EXPO_JV_UNIT = 0.5                # a JV appearance, in varsity-equivalent units
EXPO_CAP = 14.0                   # units at which a season counts as fully played

_expo_cache: dict = {}
_expo_world: dict = {}
_EXPO_MISS = object()
#: Per (school, season) entries are ~20 names each, so this bounds memory without
#: thrashing: a full-association pass touches ~860 schools x 3 seasons a gender.
_EXPO_CACHE_MAX = 8192


def _expo_world_id(db_path: str):
    """THE world's row id, for scoping the archive read.

    One real world per save (`world.start_new` resets before creating), so this
    binds to the OLDEST row — `gtt_seasonmode._active_world_seed`'s rule, for the
    same reason: any later row is a stray artifact and must never be read as the
    player's game. Resolved once per save."""
    got = _expo_world.get(db_path, _EXPO_MISS)
    if got is not _EXPO_MISS:
        return got
    import sqlite3
    wid = None
    try:
        conn = sqlite3.connect(db_path)
        try:
            r = conn.execute("SELECT id FROM world ORDER BY id ASC LIMIT 1").fetchone()
            wid = r[0] if r else None
        except sqlite3.Error:
            wid = None
        finally:
            conn.close()
    except sqlite3.Error:
        wid = None
    _expo_world[db_path] = wid
    return wid


def school_exposure(gender: str, school_name: str, season_years) -> dict:
    """{season_year: {player name: appearance units}} for ONE school's archived
    seasons — or the year mapped to None where that season has no archive.

    ‼️ SCOPED TO (world_id, year, gender, school) — every column of
    `ix_jhsaa_dual`, in order. An earlier version selected a whole gender-season
    with no `world_id` at all: the index leads on `world_id`, so nothing could
    use it and each call FULL-SCANNED the largest table in the save (~13k duals
    a gender-season, every one carrying a `lines` blob to parse) three times per
    roster build. It was also plainly wrong — unscoped, it read every world's
    archive at once. A roster build needs the ~26 rows belonging to one school.
    All three seasons come back in ONE query.

    Keyed by NAME because that is what the dual archive carries
    (`state._jh_line_records`' contract). Varsity units come off the `lines` a
    player actually dressed in — one unit per DUAL, however many courts — and JV
    units off the JV rows' `played` list at `EXPO_JV_UNIT`.

    A season with NO rows for this school reads as None (full realisation), not
    as the floor: that covers a fresh world, pre-odometer seasons and a program
    that did not yet exist, and it is the only safe default. Once a season HAS
    rows, a player absent from all of them was rostered and never dressed, which
    is the floor — that distinction is the point of returning None rather than
    an empty dict."""
    from .dbpath import resolve_db_path
    db = resolve_db_path()
    years = tuple(season_years)
    key = (db, gender, school_name, years)
    got = _expo_cache.get(key, _EXPO_MISS)
    if got is not _EXPO_MISS:
        return got
    from .world import BASE_YEAR
    wid = _expo_world_id(db)
    out = {y: None for y in years}
    idx_of = {y - BASE_YEAR - 1: y for y in years if y - BASE_YEAR - 1 >= 0}
    if wid is not None and idx_of:
        import sqlite3
        rows = []
        try:
            conn = sqlite3.connect(db)
            try:
                q = ("SELECT year, home, lines, level, played"
                     " FROM world_jhsaa_dual"
                     " WHERE world_id=? AND gender=? AND school=?"
                     " AND year IN (%s)" % ",".join("?" * len(idx_of)))
                rows = conn.execute(q, (wid, gender, school_name,
                                        *idx_of.keys())).fetchall()
            except sqlite3.Error:
                rows = []                      # table not created yet
            finally:
                conn.close()
        except sqlite3.Error:
            rows = []
        for year_idx, home, lines, level, played in rows:
            season = idx_of.get(year_idx)
            if season is None:
                continue
            units = out.get(season)
            if units is None:
                units = out[season] = {}
            if (level or "v") == "v":
                side = "home" if home else "away"
                dressed = set()
                for ln in json.loads(lines or "[]"):
                    dressed.update(ln.get(side) or ())
                for nm in dressed:             # one unit per DUAL, not per line
                    units[nm] = units.get(nm, 0.0) + 1.0
            else:
                for nm in json.loads(played or "[]"):
                    units[nm] = units.get(nm, 0.0) + EXPO_JV_UNIT
    if len(_expo_cache) >= _EXPO_CACHE_MAX:
        _expo_cache.pop(next(iter(_expo_cache)))
    _expo_cache[key] = out
    return out


def _expo_factor(units_map, name: str) -> float | None:
    """One season's realisation factor for one player, or None for full
    realisation (that season was never archived for this school)."""
    if units_map is None:
        return None
    u = units_map.get(name, 0.0)
    return EXPO_FLOOR + (1.0 - EXPO_FLOOR) * min(1.0, u / EXPO_CAP)


#: Playing up is a SMALL-SCHOOL mechanism (owner correction 2027-08): eligible at this
#: championship group and below. Mirrors `scripts/import_jhsaa.PLAY_UP_MAX_GROUP`, which
#: seeds the file — but the rule has to live HERE too, because the seed list is not the
#: only way a program can be promoted. The editor is, and until this constant existed at
#: runtime nothing checked it: `/editor/jhsaa-playup` would happily move an 8A program
#: into 9A, which is not playing up, it is a big school in a slightly bigger class.
#: 9A's exclusion falls out of the same rule (it has nothing above it).
PLAY_UP_MAX_GROUP = "4A"

#: ‼️ THE SMALLEST LEAGUE A PLAY-UP MAY JOIN — a FLOOR, and there is deliberately no
#: matching ceiling (owner rule 2026-09: "no league can get below 6", and separately
#: "the 10 is not a hard cap, it's just a guide, if it needs to go bigger it always
#: can"). A play-up JOINS a league; it must never bring one into existence, and the
#: only way to guarantee that is to refuse a league too small to be one. Measured
#: across the shipped association, every live league runs 8-10, so 6 leaves room for a
#: league that has lost a sponsor or two without ever admitting the one-, two- or
#: four-team "conference" the owner is ruling out.
#:
#: ‼️ DO NOT READ THIS AS A CAPACITY RULE and do not add its mirror. `MAX_DISTRICT`
#: was deliberately removed from this path (a test asserts the constant is not even
#: importable here): a league one program larger just plays a longer, perfectly valid
#: double round robin, and the import script's `DISTRICT_TARGET` 10 is a drawing guide
#: for a fresh map, not a limit anything enforces at runtime.
PLAY_UP_LEAGUE_MIN = 6


def can_play_up(classification: str) -> bool:
    """Whether a program of this size is allowed to play up at all.

    ‼️ SCOPED TO THE 1A-9A LADDER (2046 expansion). The Great Basin's Group
    1/Group 2 are a geographic PAIR appended after 1A in `GROUPS`, not rungs
    on the size ladder — a naive `GROUPS.index` test read them as "below 4A" and
    would have promoted a 2,500-enrollment Group 1 program "up" into 1A.
    Play-up does not exist in the Group system at all."""
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
    if g not in LADDER_GROUPS:      # Group 1/2: no ladder above or below them
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
    _transfer_year_cache.clear()          # derived from the map: falls with it
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


def is_enrolled(rec: dict, season_year: int) -> bool:
    """Whether the record's player is in high school in `season_year` — grades
    9-12 are the four seasons from their entry year."""
    entry = rec.get("entry")
    return isinstance(entry, int) and entry <= season_year <= entry + len(GRADES) - 1


def enrolled_transfers(season_year: int) -> tuple[dict, dict]:
    """The slice of the ledger that can touch a roster in `season_year`, memoised
    per (table version, year):

      * `active`  — {pid: rec} for every mover still ENROLLED that season
      * `inbound` — {(gender, school): [(pid, rec), …]} for the movers who are
        away from their origin that season, keyed by where they are

    ‼️ A TRANSFER STOPS MATTERING WHEN THE PLAYER GRADUATES (owner, 2026-09).
    `build_roster` used to walk the WHOLE ledger once per program — every move
    ever recorded, 40 seasons of them — asking each record whether it lands on
    this roster this year. On an 11,000-move save that was 11,000 dict walks per
    roster, ~900 rosters per gender build, and the answer for the ~95% of records
    whose player left years ago was always no. Only the four enrolled cohorts can
    be on any roster, and only records whose player is somewhere other than
    their origin can be INBOUND anywhere, so both lookups are cut once per season
    here and every roster build reads its own school's list. Everything a build
    reads for an ARCHIVED season (a player card, a history page) is the slice for
    THAT year, so old seasons still regenerate exactly as they were played."""
    from app import overrides as ov
    key = (ov.jhsaa_transfer_version(), season_year)
    got = _transfer_year_cache.get(key)
    if got is not None:
        return got
    full = _transfer_map(key[0])
    active: dict = {}
    inbound: dict = {}
    for pid, rec in full.items():
        if not is_enrolled(rec, season_year):
            continue
        active[pid] = rec
        where = transfer_school(rec, season_year)
        if where and where != rec.get("from"):
            inbound.setdefault((rec.get("gender", ""), where), []).append((pid, rec))
    out = (active, inbound)
    # Bounded: a page walks a few seasons, a rung one. Never a global clear
    # (a career page loops a player's four years — the quadratic-recompute rule).
    if len(_transfer_year_cache) > 16:
        for k in [k for k in _transfer_year_cache if k[0] != key[0]]:
            _transfer_year_cache.pop(k, None)
    _transfer_year_cache[key] = out
    return out


def _seat_name(school: School, entry: int, seat: int, salt: str) -> str:
    """The name `_gen_seat` would give this seat — the same rng, the same single
    draw, and NOTHING else: no attributes, no career model, no prospect. The
    ledger only needs to print who moved, and regenerating a whole Prospect per
    row (~2 ms) was most of what made the transfers page cost seconds."""
    rng = random.Random(f"{salt}|jhsaa|{school.key}|{entry}|{seat}")
    return _draw_name(rng, school, entry)[0]


def transfer_ledger() -> list[dict]:
    """Every recorded move as a row — ONE ROW PER MOVE, not per player: the
    ledger is the record of what happened, and a career with three schools
    happened three times. Each row's `from` is where they were BEFORE that move
    (the previous destination, or the origin for the first), which is the only
    reading that makes a multi-move career legible — and the only one where a
    move back to the old school does not read as a move from itself.

    Names are NOT resolved here (`name` is ""): that is the one per-row cost
    worth paying only for the rows a page actually shows —
    `resolve_transfer_names`. Cheap enough to call on every page load at any
    ledger size (a dict walk, no generation, no per-row database read)."""
    rows = []
    for pid, rec in transfers().items():
        moves = transfer_moves(rec)
        where = rec.get("from")
        for i, m in enumerate(moves):
            rows.append({"pid": pid, "name": "", "gender": rec.get("gender", ""),
                         "from": where, "to": m.get("to"), "year": m.get("year"),
                         "entry": rec.get("entry"), "origin": rec.get("from"),
                         "seat": rec.get("seat"),
                         "step": i + 1, "steps": len(moves)})
            where = m.get("to")
    rows.sort(key=lambda r: (-(r["year"] or 0), r["pid"]))
    return rows


def resolve_transfer_names(rows: list[dict], salt: str) -> list[dict]:
    """Fill `name` on ledger rows (in place; returned for chaining) and re-sort
    them by season then name. Player identity is regenerated rather than stored,
    same as everywhere else in JHSAA — but only the NAME draw (`_seat_name`), and
    memoised per (salt, pid) because a pid names one person for the life of a
    save. `salt` MUST be the world's real salt: the name draw is salted while the
    pid is not, so the wrong salt resolves the same pid to a different person and
    prints a stranger's name (`_resolve_member`'s documented trap — the old
    ledger did exactly this with a hard-coded "")."""
    by_name: dict = {}
    for r in rows:
        if r.get("name"):
            continue
        ck = (salt, r["pid"])
        name = _transfer_name_cache.get(ck)
        if name is None:
            g = r["gender"]
            if g not in by_name:
                by_name[g] = {s.name: s for s in load_schools(g)} if g else {}
            origin = by_name[g].get(r["origin"])
            name = ""
            entry, seat = r.get("entry"), r.get("seat")
            if (origin is not None and isinstance(entry, int) and isinstance(seat, int)
                    and make_pid("jhsaa", origin.ident, origin.gender, entry, seat) == r["pid"]):
                name = _seat_name(origin, entry, seat, salt)
            _transfer_name_cache[ck] = name
        r["name"] = name or "(unresolved)"
    rows.sort(key=lambda r: (-(r["year"] or 0), r["name"]))
    return rows


def transfer_rows(salt: str = "") -> list[dict]:
    """Every recorded transfer with the mover's name — the whole ledger. Fine for
    a test or a script; a PAGE should take `transfer_ledger()` and resolve names
    only for the rows it renders."""
    return resolve_transfer_names(transfer_ledger(), salt)


# --- batch transfers (owner tool, 2026-08) ------------------------------------
# The owner is this league's only market maker: every offseason ~40-50 buried
# players are redistributed by hand, one player card at a time. The batch path
# accepts the artifact that analysis already produces — (pid, destination) pairs
# — validates every row, and writes the same `set_jhsaa_transfer` rows the player
# card does, so nothing downstream changes. Rows are DECLARATIVE (applied on read
# by `build_roster` from the effective year on), so "apply" is just writing them.

_pid_idx_cache: dict = {}

# Per-key build locks for the module's heavy memo fills (the pid index, the
# cohort finder). Two threads observing the same cold key — a double-click, a
# retry, the boot warmer racing a deferred job — would otherwise each run the
# full-gender build on the one GIL. Acquire the key's lock, RECHECK the cache,
# then build; waiters land on the published result.
_build_locks: dict = {}
_build_meta_lock = __import__("threading").Lock()


def _build_lock(key):
    with _build_meta_lock:
        return _build_locks.setdefault(key, __import__("threading").Lock())


def _build_lock_done(key):
    with _build_meta_lock:
        _build_locks.pop(key, None)


def roster_pid_index(gender: str, year: int, salt: str = "") -> dict:
    """pid -> (school name, entry year, grade, player name) for everyone enrolled
    in season `year`, over the whole gender — the lookup a bare (pid, destination)
    pair needs. A full-association roster build (~7s cold), so it is memoised;
    the transfer fingerprint is resolved ONCE here, never per row."""
    from app import overrides as ov
    from .dbpath import resolve_db_path
    version = ov.jhsaa_transfer_version()
    key = (resolve_db_path(), gender, year, salt)
    got = _pid_idx_cache.get(key)
    if got is not None and got["version"] == version:
        return got["idx"]
    with _build_lock(key):
        got = _pid_idx_cache.get(key)        # a waiter finds it published
        if got is not None and got["version"] == version:
            return got["idx"]
        # ‼️ INCREMENTAL ACROSS TRANSFER EDITS (2026-09). The key used to carry
        # the transfer fingerprint, so every Move, Cancel and Apply threw the
        # whole index away and the next page load re-generated every roster in
        # the association (~12s a gender) — in the owner's workflow that is
        # every batch, all offseason. A transfer only changes the rosters of the
        # schools it NAMES (origin, every destination — `build_roster` reads no
        # other record for a school), so an index built at one version is
        # patched to the next by rebuilding just those programs. Records of
        # players not enrolled in `year` cannot touch it and are skipped.
        recs = {pid: rec for pid, rec in transfers().items()
                if rec.get("gender") == gender and is_enrolled(rec, year)}
        schools = load_schools(gender)
        if got is None:
            idx: dict = {}
            todo = schools
        else:
            old = got["recs"]
            touched: set = set()
            for pid in set(old) | set(recs):
                if old.get(pid) != recs.get(pid):
                    for rec in (old.get(pid), recs.get(pid)):
                        if rec:
                            touched.add(rec.get("from"))
                            touched.update(m.get("to") for m in transfer_moves(rec))
            idx = {pid: v for pid, v in got["idx"].items() if v[0] not in touched}
            todo = [s for s in schools if s.name in touched]
        for school in todo:
            for p in build_roster(school, year, salt):
                idx[p.pid] = (school.name, p.entry_year, p.grade, p.name)
        # Prune THIS (db, gender)'s stale entries only — a global clear() would
        # evict the sibling gender between the two builds one batch call makes,
        # so every preview→apply round would pay all four builds again.
        for k in [k for k in _pid_idx_cache if k[:2] == key[:2] and k != key]:
            _pid_idx_cache.pop(k, None)
        _pid_idx_cache[key] = {"version": version, "recs": recs, "idx": idx}
    _build_lock_done(key)
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


# --- opportunity-clearing proposals (owner tool, 2026-08) ---------------------
# The generator half of the bulk-transfer workflow: given the underplayed board's
# candidates, PROPOSE a destination for each, per the clearing-market brief
# (docs/reports/BRIEF-jhsaa-opportunity-clearing-market.md) — search LATERALLY
# first (own class, then the class sharing its competitive level), and only move
# down a real competitive step when the current level has no home. It writes
# NOTHING: the output is a slate the owner previews, edits and applies through
# the same `transfer_batch` every other path uses.

#: The brief's competitive ladder — NOT nine equal steps. 9A/8A are one level and
#: so are 7A/6A; every boundary below is real. `GB_GROUPS` are deliberately absent
#: (they are their own association rung, lateral-only — see GROUPS above).
CLEARING_LEVELS = (("9A", "8A"), ("7A", "6A"), ("5A",), ("4A",), ("3A",),
                   ("2A",), ("1A",))


def _propose_destinations(cands: list[dict], ladders: dict, groups: dict, *,
                          next_ovr: dict | None = None, max_per_school: int = 2,
                          max_drop: int = 2, top_slot: int | None = None) -> list[dict]:
    """The pure matcher behind `clearing_proposals` — separable so it can be
    tested without a full-gender roster build.

    `cands` are underplayed-board rows ({pid, name, school, group, grade, ovr});
    `ladders` maps school -> DESC-sorted next-season varsity-pool OVRs (the
    projection that makes the market FRESHMAN-AWARE: an incoming class that would
    bury the arrival is already in the list); `groups` maps school -> group;
    `next_ovr` maps pid -> the candidate's own projected next-season OVR (their
    development roll — falls back to the board's current OVR).

    Rules, straight from the brief: a candidate is placed at the HIGHEST level
    with a genuinely useful role — a projected ladder slot inside the varsity
    lineup (`top_slot`, default `lineup_need("regular")`). Own class outranks
    the lateral class-mate, which outranks a drop; a DROP destination where the
    arrival would be the outright new #1 is skipped (dominance is not the goal —
    lateral #1s are fine, a weak same-level program is exactly who should get
    them). Within a tier the pick is the slot nearest the middle of the lineup.
    Arrivals stack: each placement counts against the destination's ladder and
    its `max_per_school` allowance, so a wave cannot pile onto one program."""
    from collections import defaultdict
    top_slot = top_slot or lineup_need("regular")
    next_ovr = next_ovr or {}
    lvl = {}
    for i, band in enumerate(CLEARING_LEVELS):
        for grp in band:
            lvl[grp] = i
    by_level: dict[int, list] = defaultdict(list)
    lateral_only: dict[str, list] = defaultdict(list)   # GB / unladdered groups
    for s, grp in groups.items():
        if grp in lvl:
            by_level[lvl[grp]].append(s)
        else:
            lateral_only[grp].append(s)
    arrivals: dict[str, list] = defaultdict(list)
    out = []
    # Best first, the order every market here clears in — the strongest surplus
    # gets the scarce high-level seats before weaker candidates fill them.
    for c in sorted(cands, key=lambda r: -r["ovr"]):
        home = c["group"]
        ovr = next_ovr.get(c["pid"], c["ovr"])
        tiers: list[tuple[int, list]] = []                  # (drop steps, schools)
        if home in lvl:
            base = lvl[home]
            tiers.append((0, [s for s in by_level[base] if groups[s] == home]))
            tiers.append((0, [s for s in by_level[base] if groups[s] != home]))
            for step in range(1, max_drop + 1):
                if base + step < len(CLEARING_LEVELS):
                    tiers.append((step, by_level[base + step]))
        else:
            tiers.append((0, lateral_only[home]))
        best = None
        for step, tier in tiers:
            picks = []
            for s in tier:
                if s == c["school"] or len(arrivals[s]) >= max_per_school:
                    continue
                lad = ladders.get(s)
                if lad is None:
                    continue
                above = (sum(1 for v in lad if v >= ovr)
                         + sum(1 for v in arrivals[s] if v >= ovr))
                slot = above + 1
                if slot > top_slot:
                    continue
                # Becoming the outright #1 on a DROP is dominance, not
                # opportunity — a last resort within the tier, never a bar
                # (the market guarantees everyone a home).
                dominant = 1 if (step > 0 and slot == 1) else 0
                picks.append((dominant, abs(slot - 7), slot, s))
            if picks:
                _, _, slot, s = min(picks)
                best = (s, slot, step)
                break
        row = {"pid": c["pid"], "name": c["name"], "from": c["school"],
               "from_group": home, "grade": c["grade"], "ovr": c["ovr"],
               "to": "", "to_group": "", "slot": None, "drop": 0}
        if best:
            s, slot, step = best
            arrivals[s].append(ovr)
            row.update(to=s, to_group=groups[s], slot=slot, drop=step)
        out.append(row)
    return out


def clearing_proposals(gender: str, year: int, salt: str = "",
                       candidates: list[dict] | None = None,
                       max_per_school: int = 2, max_drop: int = 2,
                       top_slot: int | None = None) -> list[dict]:
    """Propose a destination for each underplayed candidate, effective season
    `year` (the NEXT season — an offseason move). Projections run against every
    program's `year` roster, which `build_roster` already develops and tops up
    with that year's incoming freshman class, so 'would they actually play' is
    answered against the roster the arrival will really meet, not the one that
    just finished. A full-gender roster build (~seconds) — call it from an
    explicit button, never on a default page load."""
    ladders, groups, next_ovr = {}, {}, {}
    for school in load_schools(gender):
        roster = build_roster(school, year, salt)
        ovrs = sorted((round(p.current_overall(), 1) for p in roster), reverse=True)
        ladders[school.name] = ovrs
        groups[school.name] = school.group
        for p in roster:
            next_ovr[p.pid] = round(p.current_overall(), 1)
    return _propose_destinations(candidates or [], ladders, groups,
                                 next_ovr=next_ovr, max_per_school=max_per_school,
                                 max_drop=max_drop, top_slot=top_slot)


# --- reserve-cohort finder (owner tool, 2026-08) ------------------------------
# The read-only half of reserve-cohort mobility
# (docs/reports/BRIEF-jhsaa-reserve-cohort-mobility.md): find the programs whose
# RESERVE group — the players below the league lineup — is itself a
# varsity-caliber team ("Rockridge B"), and the weak hosts a cohort like that
# could spend a varsity season at. It writes nothing and decides nothing: the
# owner reads it, and can send a cohort into the transfer batch by hand. The
# loan LIFECYCLE (recall rights, one-season presumption) is deliberately NOT
# built — a move made from here is an ordinary permanent transfer.

#: How many reserves make a cohort by default — the brief's 7-10 band.
RESERVE_COHORT_SIZE = 8
#: A team's strength for comparisons is its best-nine mean (the `REST_GAP`
#: basis), not the full 11 — S2/S3 seat ranks #10-#11 by construction.
VARSITY_CORE = 9


def _find_cohorts(rosters: dict, groups: dict, *, cohort_size: int = RESERVE_COHORT_SIZE,
                  min_reserves: int = 6, hosts_per_class: int = 8) -> dict:
    """The pure finder behind `reserve_cohorts` — separable so it is testable
    without a full-gender roster build.

    `rosters` maps school -> DESC-ability list of {pid, name, grade, ovr};
    `groups` maps school -> group. Returns:

    - `sources`: programs whose top `cohort_size` reserves (ranks below the
      league lineup) average to a varsity-caliber unit — `plays_like` is the
      HIGHEST class whose median team strength the cohort's mean clears, walked
      down `LADDER_GROUPS` (a GB group compares within itself only). Each
      carries its cohort players and up to three suggested hosts in the fit
      class and the one below: the class's weakest programs, with the COMBINED
      best-nine (cohort + the host's whole roster) ranked against that class's
      real field.
    - `hosts`: per class, the weakest programs by best-nine mean, each with a
      `shape` per the brief — `rebuild` (≤1 player at class level), `core + void`
      (2-4 real varsity players, then the cliff a cohort fills), else `middling`.
    - `medians`: per class, the median team best-nine mean — the yardstick
      every column above is read against.
    """
    from statistics import median
    cut = lineup_need("regular")
    def _mean(vals):
        return round(sum(vals) / len(vals), 1) if vals else 0.0
    team_mean = {s: _mean([p["ovr"] for p in r[:VARSITY_CORE]])
                 for s, r in rosters.items()}
    by_group: dict[str, list] = {}
    for s, grp in groups.items():
        by_group.setdefault(grp, []).append(s)
    medians = {grp: round(median(team_mean[s] for s in ss), 1)
               for grp, ss in by_group.items()}
    ranked = {grp: sorted((team_mean[s] for s in ss), reverse=True)
              for grp, ss in by_group.items()}

    def _rank(grp: str, mean: float) -> int:
        return 1 + sum(1 for v in ranked[grp] if v > mean)

    hosts: dict[str, list] = {}
    # Ladder order for the reader, GB groups after — never dict-arrival order.
    grp_order = ([g for g in GROUPS if g in by_group]
                 + sorted(g for g in by_group if g not in GROUPS))
    for grp in grp_order:
        ss = by_group[grp]
        rows = []
        for s in sorted(ss, key=lambda s: team_mean[s])[:hosts_per_class]:
            core = sum(1 for p in rosters[s][:cut] if p["ovr"] >= medians[grp])
            rows.append({"school": s, "group": grp, "mean": team_mean[s],
                         "gap": round(medians[grp] - team_mean[s], 1),
                         "core": core,
                         "shape": ("rebuild" if core <= 1 else
                                   "core + void" if core <= 4 else "middling")})
        hosts[grp] = rows

    sources = []
    for s, roster in rosters.items():
        reserves = roster[cut:]
        if len(reserves) < min_reserves:
            continue
        cohort = reserves[:cohort_size]
        c_mean = _mean([p["ovr"] for p in cohort])
        grp = groups[s]
        # The highest class the cohort would be an average-or-better varsity in.
        walk = ([g for g in LADDER_GROUPS if g in medians]
                if grp in LADDER_GROUPS else [grp])
        plays_like = next((g for g in walk if medians[g] <= c_mean), None)
        if plays_like is None:
            continue
        fit_classes = walk[walk.index(plays_like):walk.index(plays_like) + 2]
        c_ovrs = [p["ovr"] for p in cohort]
        suggested = []
        for fg in fit_classes:
            for h in hosts[fg][:3]:
                if h["school"] == s:
                    continue
                combined = _mean(sorted(
                    c_ovrs + [p["ovr"] for p in rosters[h["school"]]],
                    reverse=True)[:VARSITY_CORE])
                suggested.append({**h, "combined": combined,
                                  "rank": _rank(fg, combined),
                                  "n": len(by_group[fg])})
        sources.append({"school": s, "group": grp, "varsity": team_mean[s],
                        "class_median": medians[grp],
                        "strong_varsity": team_mean[s] >= medians[grp],
                        "cohort_mean": c_mean, "cohort": cohort,
                        "reserves": len(reserves), "roster": len(roster),
                        "plays_like": plays_like, "hosts": suggested})
    sources.sort(key=lambda r: (-r["cohort_mean"], r["school"]))
    return {"sources": sources, "hosts": hosts, "medians": medians}


_cohort_cache: dict = {}


def reserve_cohorts(gender: str, year: int, salt: str = "",
                    cohort_size: int = RESERVE_COHORT_SIZE) -> dict:
    """The finder over season `year`'s real rosters — pass NEXT season for an
    offseason read, so graduation and the incoming freshman class are already
    in every ladder (the `clearing_proposals` rule). A full-gender roster build
    (~13s on a deep save): call from an explicit button, never a default page
    load — and MEMOISED, because the page's pagination and filter links all
    carry `find=1`, so without a cache every page flip re-paid the whole
    build. Module-global cache under the threaded worker: compute into a
    local, publish, return the local; read with .get(); prune per
    (db, gender), never a global clear."""
    from app import overrides as ov
    from .dbpath import resolve_db_path
    key = (resolve_db_path(), gender, year, salt, cohort_size,
           ov.jhsaa_transfer_version(), ov.jhsaa_archetype_version(),
           ov.jhsaa_playup_version())
    got = _cohort_cache.get(key)
    if got is not None:
        return got
    with _build_lock(key):
        got = _cohort_cache.get(key)         # a waiter finds it published
        if got is not None:
            return got
        out = _build_reserve_cohorts(gender, year, salt, cohort_size)
        for k in [k for k in _cohort_cache if k[:2] == key[:2]]:
            _cohort_cache.pop(k, None)
        _cohort_cache[key] = out
    _build_lock_done(key)
    return out


def _build_reserve_cohorts(gender: str, year: int, salt: str,
                           cohort_size: int) -> dict:
    rosters, groups = {}, {}
    for school in load_schools(gender):
        roster = build_roster(school, year, salt)
        rows = [{"pid": p.pid, "name": p.name, "grade": p.grade,
                 "ovr": round(p.current_overall(), 1)} for p in roster]
        rows.sort(key=lambda r: -r["ovr"])
        rosters[school.name] = rows
        groups[school.name] = school.group
    return _find_cohorts(rosters, groups, cohort_size=max(4, min(12, cohort_size)))


#: The archetypes an owner can ASSIGN. `upstart` is deliberately absent: it is a
#: temporary run the world rolls from the salt and expires by itself, and storing one
#: would make it permanent — the one thing an upstart must never be.
#: What the editor may ASSIGN. ‼️ `development` and `doubles` are deliberately absent
#: (owner, 2026-08): both distorted the field and are retired, `coaching` replaces the
#: first, and nothing replaces the second. Their rows stay in `ARCHETYPES` so a save
#: still holding one as an override keeps generating the roster it has — this list is
#: what can be newly applied, not what can be read. `upstart` is excluded for its own
#: older reason: it is a rolled, expiring run, and storing one would make it permanent.
EDITABLE_ARCHETYPES = ("blue_blood", "coaching", "turnout", "neglect")


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
        # Ladder only: Group 1/2 are not "above" anything (can_play_up is
        # False there, and the slice must never hand a Group as a target).
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
            state=r.get("state", ""),
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
            locality=r.get("locality", ""), state=r.get("state", ""))
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


def _sponsors_any(row: dict) -> bool:
    """Does this school field a tennis team AT ALL? A program that has stopped
    sponsoring keeps its data row (`former_school`, owner rule 2026-08) but is no
    longer part of any league that gets played, so anything reading `_rows()` to
    reason about the season — rather than about the school's page — must ask this.
    Either gender counts: sponsorship is per sport per gender and a girls-only
    program is a real member of its league."""
    return bool(row.get("girls") or row.get("boys"))


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
    out of a class is not counted as still being in it.

    ‼️ AND IT EXCLUDES A SCHOOL THAT NO LONGER SPONSORS TENNIS. A candidate league
    is only a league if somebody actually PLAYS in it, and since the `former_school`
    rule (2026-08) a program that stops sponsoring keeps its data row while dropping
    out of `load_schools` — so a league can be fully populated in `rows` and
    completely empty on the field. Ten of them are, across six classifications.
    Reading raw rows, this function counted those ghosts as settled members and
    could place a played-up program into a league with nobody in it, arriving at the
    exact one-team league the guard above exists to prevent: Copperview (3A, sponsors
    neither gender) is the lone member of Coastal Range League and sits in Puerto
    Alma's own county, so it beat every real 3A league on the county term and Puerto
    Alma played a 2-12 season with no league games and a district title in a league
    of one. `load_schools`'s sponsorship filter is what makes a program real; any
    function reading `_rows()` to answer a question about who PLAYS has to apply it
    too. Gender-agnostic (`_sponsors_any`), because the placement is — a girls-only
    sponsor is a live league member."""
    settled = [x for x in rows if _row_league(x) and _sponsors_any(x)
               and not _plays_up_row(x, pmap)]
    # The target is resolved ONCE per school and carried, never re-resolved inside the
    # placement loop — `_plays_up_row` is the expensive call on this path.
    movers = sorted(({**x, "_target": _plays_up_row(x, pmap)} for x in rows
                     if _plays_up_row(x, pmap)), key=lambda x: x["name"])
    by_name = {x["name"]: x for x in movers}

    out = {}
    for row in movers:
        group = row["_target"]                       # the RESOLVED target, not
                                                        # always one step up
        near: dict[str, list[int]] = {}
        for x in settled:
            if x["group"] != group:
                continue
            slot = near.setdefault(_row_league(x), [0, 0, 0])
            slot[0] += x["county"] == row["county"]
            slot[1] += x["area"] == row["area"]
            slot[2] += 1                             # live members, the size gate
        # Movers already placed count toward the size of the league they joined, so a
        # run of play-ups cannot each look at the same league as though the others had
        # not gone there (the one-pass rule, one bullet up).
        for other, league in out.items():
            if league in near and by_name[other]["_target"] == group:
                near[league][2] += 1
        if not near:
            raise ValueError(
                f"{row['name']!r} plays up to {group!r}, but {group} has no "
                "settled league to join at all — a real classification always "
                "has one; check the play-up target and the schools data.")
        # ‼️ SIZE GATES, GEOGRAPHY ONLY ORDERS. A play-up JOINS a league; it must
        # never bring one into existence. Anything under `PLAY_UP_LEAGUE_MIN` is not
        # a league to join, it is a league this placement would be inventing, so it
        # is not a candidate at all and the program travels instead — owner rule
        # 2026-09: "future play-ups should just put a team in a bigger league if
        # needed, it should never invent a one-team or two-team or 4-team or whatever
        # conference … none of this is real so they can be wherever." Distance is
        # cosmetic here and is never a reason to pick a league that is not real.
        real = [d for d in near if near[d][2] >= PLAY_UP_LEAGUE_MIN]
        if not real:
            # Nothing clears the floor (a class the owner has moved most of the way
            # out). Take the BIGGEST — literally "a bigger league if needed" — never
            # the nearest, and never a new one. Ties fall to geography below.
            top = max(near[d][2] for d in near)
            real = [d for d in near if near[d][2] == top]
        best = min(real, key=lambda d: (-near[d][0], -near[d][1], d))
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
             mod: dict | None = None, cap: float = 80.0) -> float:
    """A player's CEILING, drawn independently per player. The ladder is not assigned —
    it emerges from who is actually best, so a great freshman can play number one over a
    senior, which is how high school works.

    `mod` is the program-level modifier (`_program_mod`) applied ON TOP of the
    classification band — it shifts and scales that band, it never replaces it, so a
    blue-blood 3A-1A remains a strong SMALL-SCHOOL program.

    `cap` is the top of the scale this cohort is drawn on. It is 80 (the college
    reference) for pre-`career_era` cohorts and `GRADE_CEIL` for the free
    high-school scale — see §24: high school stops being held down to fit a
    scale it does not play on, and graduation translates instead."""
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
    return max(GRADE_FLOOR, min(cap, draw))


def _apply_career(p: Prospect, school_key: str, entry: int, seat: int,
                  grade: int, salt: str, exposure: dict | None = None,
                  coach: float = 1.0) -> Prospect:
    """Set a career-era player's CURRENT ability from their career plan.

    The prospect arrives generated AT its ceiling (maturity 1.0), so this scales
    every attribute by one factor — `overall` is a weighted mean, so scaling all
    attributes scales it exactly, and the play-style SHAPE survives untouched.

    ‼️ The ceiling is summed from `p.potential` DIRECTLY, never via
    `p.ceiling_overall()`, which constructs a whole `PlayerAttributes` per call.
    This runs once per generated player and a season builds ~1,600 rosters — the
    same cost-class trap `trim_prospect_ceiling` documents.
    """
    from .player_attributes import OVERALL_WEIGHTS, _WEIGHT_TOTAL
    ceiling = sum(OVERALL_WEIGHTS[a] * v
                  for a, v in p.potential.items()) / _WEIGHT_TOTAL
    if ceiling <= 0:
        return p
    target = career_ability(school_key, entry, seat, grade, salt, ceiling,
                            exposure, coach)
    factor = target / ceiling
    for a, ceil_v in p.potential.items():
        p.current[a] = clamp_grade(ceil_v * factor)
    # A career peak may sit ABOVE the drawn ceiling (`CAREER_PEAK_BAND` tops out
    # at 1.10) and overflow may carry a player past it, so `factor` can exceed 1.
    # Keep the displayed ceiling at or above the displayed ability — a player
    # card reading POT below OVR is a presentation bug, not a design statement.
    if factor > 1.0:
        for a, cur_v in p.current.items():
            if p.potential[a] < cur_v:
                p.potential[a] = cur_v
    p.recruit_stars = p.star_rating()
    return p


def _draw_name(rng: random.Random, school: School, entry: int) -> tuple[str, str]:
    """The seat's (name, country) — ‼️ EXACTLY ONE draw off the main rng, in BOTH
    eras: the name stream is a separate rng seeded off it, so widening the name
    draw cannot shift a single talent/attribute roll for anyone, either side of
    the cutover. Shared by `_gen_seat` (the roster) and `_seat_name` (the
    transfer ledger, which needs the name and nothing else), so the two can never
    disagree about who a seat is."""
    from generators import make_name_picker
    sex = "male" if school.gender == "boys" else "female"
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
        return nm, (country or "US")
    # Legacy draw, byte-identical — existing cohorts keep their exact names.
    nm, _ = make_name_picker(nrng, gender=sex, region_weights={"us": 1.0})()
    return nm, "US"


def _gen_seat(school: School, mod: dict, entry: int, seat: int, grade: int,
              salt: str, expo_years: dict | None = None) -> Prospect:
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
    nm, country = _draw_name(rng, school, entry)
    # ‼️ Always generated AS "US": `generate_prospect` branches on country (talent
    # shift, elite roll, academics, hometown path) and consumes the rng differently,
    # so passing the exchange student's country would shift every attribute roll.
    # The name era must move NAMES ONLY — the flag is stamped on afterwards.
    # ‼️ THE FREE HIGH-SCHOOL SCALE (§24). From `career_era()` on, ceilings are
    # drawn on the JHSAA's own scale (`GRADE_CEIL`) rather than being held under
    # the college NORMALISATION reference of 80. High school is the top level
    # this association plays at; `jhsaa.apply_to_class` translates at graduation
    # by RANK, and never carries a high-school grade into the college game, so
    # nothing downstream reads these numbers on the college scale.
    free = entry >= career_era()
    cap = float(GRADE_CEIL) if free else 80.0
    talent = min(cap, _ceiling(rng, school.talent_group, school.gender, mod,
                               cap=cap) + mod.get("pot", 0.0))
    compress = _compresses(entry)
    elite_key = ("jhsaa-elite", school.ident, school.gender, entry, seat)
    if compress:
        # Ceiling compression (owner rule 2026-08) — a TRANSFORM on the value
        # already drawn, so the main rng consumes exactly the same draws either
        # side of the era; the 1-in-500 elite exemption rolls on blake2s off the
        # pid's own identity, so it shifts nobody else and holds all four years.
        from .development import compress_talent
        talent = compress_talent(talent, sex, key=elite_key)
    p = generate_prospect(rng, nm, "US", gender=sex,
                          talent=talent,
                          # ‼️ The career model derives current ability itself,
                          # so it generates AT the ceiling and scales down after
                          # (`_apply_career`). A degenerate band still consumes
                          # exactly ONE uniform draw, so the main rng stream is
                          # identical either side of the era.
                          maturity_range=(1.0, 1.0) if free else maturity,
                          # `ident`, never `name` — a pid has to survive a
                          # rename or every archived award points at nobody.
                          pid=make_pid("jhsaa", school.ident, school.gender,
                                       entry, seat),
                          ceiling_max=cap)
    if free:
        # The odometer: each PRIOR grade's realisation factor, looked up in that
        # season's archive by (school, name) — the name exists only now, which
        # is why this cannot live in `build_roster`. A grade whose season has no
        # archive is simply absent, and `career_ability` reads absent as full.
        exposure = None
        if expo_years:
            exposure = {}
            for pg in range(9, grade):
                f = _expo_factor(expo_years.get(entry + (pg - 9)), p.name)
                if f is not None:
                    exposure[pg] = f
        # ‼️ `mod` REACHES THE CAREER MODEL HERE AND NOWHERE ELSE. On this path
        # `maturity_range` is the degenerate (1.0, 1.0) and `_apply_career`
        # overwrites current ability outright, so the `step` computed from
        # `mod["mature"]` above is consumed by the LEGACY branch only. Without
        # this argument a program archetype that develops players — `coaching`
        # and `neglect` alike — is silently inert for every cohort in a fresh
        # save, which is exactly the state this was found in.
        _apply_career(p, school.key, entry, seat, grade, salt,
                      exposure or None, coach_factor(mod.get("mature", 0.0)))
    elif compress:
        # The guarantee half: attribute noise lifts displayed ceilings past the
        # squashed centre, so the visible number is trimmed after generation.
        from .development import trim_prospect_ceiling
        trim_prospect_ceiling(p, sex, key=elite_key)
    p.country = country                  # the flag only — see above
    p.class_year = str(grade)
    p.grade = grade
    p.entry_year = entry
    # ‼️ AN AFFILIATE'S KIDS ARE BORN AT HOME, NOT IN JEFFERSON. `school.state`
    # is empty for every ordinary Jefferson program (hometown "City, JF",
    # region "Jefferson" — the pre-affiliate behaviour, unchanged) and a real
    # state name for an out-of-state affiliate (`School.state`'s docstring):
    # Bend Senior High's players are from Bend, OREGON, the same convention
    # `development._gen_hometown`/`juniors._roll_hometown` use elsewhere
    # (`f"{city}, {abbr}"`) — never `f"{school.city}, JF"` regardless of where
    # the school actually is. `region` drives `juniors.state_players` (a
    # domestic recruit's home-state filter), so an affiliate's kids must read
    # as their real state there too, or an Oregon recruiter's board would show
    # nobody home-grown from Bend and Jefferson's own board would over-count.
    p.hometown = f"{school.city}, {_state_abbr(school.state)}"
    p.high_school = school.name
    p.region, p.domestic = (school.state or "Jefferson"), True
    return p


_US_STATE_ABBR: dict[str, str] | None = None


def _state_abbr(state: str) -> str:
    """The postal abbreviation for a real state name, or "JF" for an
    ordinary (non-affiliate) Jefferson program — see `School.state`."""
    global _US_STATE_ABBR
    if not state:
        return "JF"
    if _US_STATE_ABBR is None:
        from . import juniors
        _US_STATE_ABBR = dict(juniors.US_STATES)
    return _US_STATE_ABBR.get(state, state)


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
    # Resolved ONCE per roster build, not per seat — the override table's
    # fingerprint is a SQLite connect+query even on a cache hit (the
    # playup-fingerprint trap, `AAR-jhsaa-playup-fingerprint-query-storm.md`). A
    # season builds 1,600+ rosters; per-seat would multiply that by every seat.
    # ‼️ And only the ENROLLED slice of the ledger (`enrolled_transfers`): every
    # pid this build generates has an entry year inside this season's four
    # grades, so the slice answers the outbound question exactly, and the inbound
    # list is this school's own — never a walk over every move ever recorded.
    tmap, inbound = enrolled_transfers(year)
    # The three seasons a four-grade roster can have already played, resolved
    # ONCE per build and threaded down (never per seat — the query-storm rule).
    # ‼️ Deliberately NOT passed to the transfer paths below: a mover's prior
    # seasons are archived under the school they actually played at, so a
    # (this-school, name) lookup would misread their played years as sitting.
    # Transfers are rare owner-authored overrides; they realise in full.
    expo_years = school_exposure(school.gender, school.name,
                                 (year - 1, year - 2, year - 3))
    out = []
    fresh9_seats = 0
    for grade in GRADES:
        entry = year - (grade - 9)
        n_seats = _freshman_class_size(school.key, entry, school.classification,
                                       salt, mod.get("roster", 0))
        if grade == 9:
            fresh9_seats = n_seats
        for seat in range(n_seats):
            p = _gen_seat(school, mod, entry, seat, grade, salt, expo_years)
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
            out.append(_gen_seat(school, mod, year, seat, 9, salt, expo_years))
    # Incoming: every transfer whose DESTINATION is this school AND this gender,
    # effective by now. School names are shared across a boys' and a girls' program
    # (the display identity is per-team, not per-school), so the name match alone
    # would append a boys' mover to the girls' roster of the same name and vice
    # versa — `_gen_seat` would then place an origin-gender Prospect straight onto
    # the opposite-gender team.
    # `inbound` is keyed by (gender, school) on where `transfer_school` puts the
    # player THIS season, and holds only records whose player is away from their
    # origin — so the gender match, the "is it here" test and the "never pull
    # somebody this school already generated" guard (a player whose moves bring
    # them back to their ORIGIN is produced by the seat loop above, which no
    # longer skips them; adding them here too would roster the same person
    # twice) are all properties of the list, not checks per record.
    for pid, rec in inbound.get((school.gender, school.name), ()):
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
           fmt: DualFormat | None = None, lift: float = 0.0) -> Team:
    """Dress `lineup` (or the current best nine) for `phase`. Singles take the top;
    doubles is its OWN roster below them (`Team.doubles_players`), so the state
    format's four doubles pairs are eight different players rather than the singles
    re-permuted.

    `fmt` overrides the phase's shape — the JV season plays one of `JV_FORMATS`, which
    is sized per dual rather than per phase, so it cannot be looked up from `phase`.

    `lift` is a per-dual grade bonus applied to EVERY player dressed — home court, and
    nothing else uses it. It is a parameter rather than something read in here because
    only the caller knows which side is at home: `_squad` is handed one team and has no
    opponent to be at home against."""
    f = fmt or dual_format(phase, ts.school.group)
    r = lineup if lineup is not None else _order(ts)[:lineup_need(phase, ts.school.group)]
    if not r:
        raise ValueError(f"{ts.school.name} has an empty roster")
    def at(i):
        return r[i % len(r)]                       # degrade, never crash, on a short side
    # Prospect -> engine Player, the same conversion ncaa.squad_and_ladder uses.
    singles = [_lifted(at(i), lift) for i in range(f.n_singles)]
    dbl = [_lifted(at(f.n_singles + i), lift) for i in range(2 * f.n_doubles)]
    if archetype(ts.school.name) == "doubles":
        # RETIRED and unassignable; still honoured for a save that holds the tag.
        dbl = [_doubles_lift(at(f.n_singles + i), ts.school.name, i, lift)
               for i in range(2 * f.n_doubles)]
    return Team(name=ts.school.name, singles=singles,
                doubles=[(2 * i, 2 * i + 1) for i in range(f.n_doubles)],
                doubles_players=dbl)


# --- HOME COURT (owner rule 2026-08) -----------------------------------------
#
# A small one-time lift for the host, rolled per DUAL rather than per player: "a
# one-time boost to the home team, not exceeding n but it can roll anywhere from 1 to
# n". So every player the home side dresses gets the SAME number that day — a home
# court is a property of the afternoon, not of an individual — and the number varies
# dual to dual, which is what keeps it from reading as a flat handicap the standings
# could be corrected for.
#
# On the 20-80 grade scale, the same scale the retired `DOUBLES_BOOST` used. Small
# against that: the classification bands are ~4-8 points apart at the top, so the
# strongest roll here is worth less than one classification step and the weakest is
# nearly nothing.
HOME_COURT = (1.0, 4.0)

#: ‼️ NOT EVERY DUAL HAS A HOST. A neutral-site event has no home team, and handing
#: one side a lift because the archive happens to store it first would invent an
#: advantage nobody has — worst of all in the two rounds that decide the association's
#: championships. The showcases are multi-team weekends at one venue; State and the
#: TOC are central-site championships. Everything else — the league season, the
#: invitationals, and the whole road to State — IS hosted (the association's own rules
#: say so: the Specials' winner hosts, the Challengers' holder hosts), so those keep
#: the advantage a real host has.
NEUTRAL_PHASES = frozenset(SHOWCASE) | {"state", "toc"}


def home_court(seed: int, phase: str = "regular") -> float:
    """The host's lift for ONE dual, in 20-80 grade points — 0.0 where nobody is home.

    Rolled off the DUAL'S OWN SEED, so it is part of the same deterministic stream as
    the result it shades: replaying a season reproduces the same afternoon, and a
    stored dual can be re-derived. Its own `random.Random` rather than a draw off the
    caller's, for the reason every other side-roll in this module has one — consuming
    from the shared stream would shift every match seed after it and re-simulate the
    whole association."""
    if phase in NEUTRAL_PHASES:
        return 0.0
    return random.Random(f"{seed}|jhsaa-home").uniform(*HOME_COURT)


def _lifted(prospect, lift: float):
    """`prospect` as an engine player, with `lift` added to every current grade.

    ‼️ THE LIFT LANDS ON A COPY, NEVER THE PROSPECT. `build_roster` caches Prospects
    globally and shares them across saves, so mutating one would make an afternoon's
    home advantage permanent and leak it into every other league reading the same
    object. The retired `_doubles_lift` learned this first; it is the rule for any
    per-match modifier here.

    A zero lift returns the player untouched — not a copy of them — so the away side
    and every neutral-site dual take exactly the code path they took before home
    court existed.

    ‼️ CLAMPED WITH `clamp_grade` (`GRADE_CEIL`, 100), NEVER TO 80. From
    `career_era()` on, JHSAA ceilings are drawn on the association's OWN free scale
    rather than being held under the college normalisation reference of 80 — so a
    `min(80.0, …)` here does not cap a lift, it DELETES ability: an elite career-era
    player sitting at 88 came out at 80, and playing at home made them nine points
    worse. A lift that can reverse the advantage it exists to give is worse than no
    lift, and it would have shown up as nothing more than the occasional strange
    home loss."""
    if not lift:
        return prospect.engine_player()
    import copy
    clone = copy.copy(prospect)
    clone.current = {a: clamp_grade(v + lift) for a, v in prospect.current.items()}
    return clone.engine_player()


def _doubles_lift(prospect, school: str, seat: int, extra: float = 0.0):
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
    # `extra` is the home-court lift, which applies to everyone the host dresses —
    # it is added here rather than in a second copy so a doubles player at home is
    # lifted once, by the sum, instead of being cloned twice.
    lift = rng.uniform(lo, hi) + extra
    clone = copy.copy(prospect)
    # Same free-scale reason as `_lifted` — this is the other per-match lift, and
    # `min(80.0, …)` would demote a career-era player rather than boost them.
    clone.current = {a: clamp_grade(v + lift) for a, v in prospect.current.items()}
    return clone.engine_player()


_SLOT = re.compile(r"^([SD])(\d+)$")

# Bench rotation (owner rule 2027-08): the lineup is re-set match to match on the BEST
# PERFORMING nine — results first, then OVR, STR last — so a hot bench player earns his
# way in. On top of that, coaches USE the bench in the regular season: most duals a
# reserve or two rotates into the bottom of the lineup, so nobody persisted plays zero
# times across a ~26-dual year (which would be absurd). The POSTSEASON is strict:
# your best nine, no rotation — an injury there SUBSTITUTES within the frozen order
# rather than reopening it (see `_healthy`, `_postseason_nine`); it never adds a
# second rotation on top.
_ROTATE_ONE = 0.45          # chance the 9th seat goes to a bench player, per dual
_ROTATE_TWO = 0.15          # chance the 8th seat does too

# TALENT-AWARE STAFFING vs. truly bad teams (owner rule 2026-08, rest count expanded
# 2026-08 alongside injuries). Colorado's big programs field V2/V3 squads; everywhere
# else the same depth is exercised by coaches SITTING starters against overmatched
# opponents and moving everyone up a rung. We do not model a V2 — instead, in the
# REGULAR SEASON ONLY, a coach facing a clearly weaker side (a strength gap always,
# plus a .300-or-worse record once the opponent has a real sample; before that the gap
# alone decides) rests a run of starters from the TOP of the ladder. Everybody shifts
# up, so the card still reads as the ladder (the clear-ladder requirement) and the
# bottom seats reach several more bench players than the ordinary `_ROTATE_*` churn
# alone — same goal injuries serve, one more lever pulling the bench onto real courts.
# ‼️ NEVER in the postseason (the Order of Ability is frozen and strict) and never at a
# showcase (the whole point of the weekend is playing your best against power
# programs) — both branches of `_lineup` sit above this check by construction. Guarded
# so a thin roster never rests below the card — resting past the bench would wrap the
# same player onto two lines of one dual. Composes with injuries for free: `_lineup`
# filters hurt players out BEFORE this runs, so `spare` is already healthy bench only.
REST_OPP_PCT = 0.300        # the record that marks an opponent "truly bad"
REST_MIN_SAMPLE = 6         # duals before a record means anything
REST_GAP = 10.0             # OVR gap (top-nine mean) that must ALWAYS hold
REST_RATE = 0.75            # chance a qualifying dual actually rests anyone
REST_TWO = 0.35             # chance a 2nd starter sits, same calibration as before
REST_FALLOFF = 0.45         # chance each SEAT BEYOND the 2nd also sits — a further
                             # roll per seat, so the count decays rather than jumping
                             # straight to the cap
REST_MAX = 6                # never rest more than this many starters in one dual


def _rest_count(ts: TeamSeason, opp, rng: random.Random, spare: int) -> int:
    """How many starters sit this dual: 0 most of the time, a handful (up to
    `REST_MAX`, tapering off) against a truly weaker side, never more than the
    healthy bench can absorb (`spare`)."""
    if opp is None or spare <= 0:
        return 0
    if _strength(ts) - _strength(opp) < REST_GAP:
        return 0
    n = opp.wins + opp.losses
    if n >= REST_MIN_SAMPLE and opp.win_pct > REST_OPP_PCT:
        return 0                       # a real record says they aren't that bad
    if rng.random() >= REST_RATE:
        return 0
    k, cap = 1, min(REST_MAX, spare)
    while k < cap:
        chance = REST_TWO if k == 1 else REST_FALLOFF
        if rng.random() >= chance:
            break
        k += 1
    return k


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


def _healthy(ts: TeamSeason, order: list) -> list:
    """`order` with any currently-injured player skipped — a SUBSTITUTION within
    the given priority order, never a re-rank: the postseason's frozen Order of
    Ability stays exactly as frozen, an injured player just steps aside for the
    next name on the same list. Called at dress time only (`_lineup`,
    `_postseason_nine`), never inside `_order` itself — `jv_pool` reads `_order`
    straight, and JV is deliberately injury-blind (owner rule 2026-08): the
    whole point of JV is more of the roster getting real minutes, not fewer."""
    if not ts.injuries:
        return order
    return [p for p in order if p.pid not in ts.injuries]


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


def _arrange_state(nine: list, sibling_ids: dict | None = None,
                   pair_counts: dict | None = None) -> list:
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
        # Partner continuity (owner rule 2026-09): a near-tie settles toward the
        # pair that has been playing together this season. Same scale as the
        # sibling nudge; `_order_pairs`'s boundary still binds afterwards.
        return r + partner_chemistry(pair_counts, a.pid, b.pid)

    # S1 + D1 consume ranks #1-#3: the coach picks which of the three plays
    # singles by what it does for the two points those players cover.
    top3, rest = nine[:3], nine[3:]
    forced = _sibling_units(nine, sibs)
    def cfg_score(i):
        s = top3[i]
        d = [p for j, p in enumerate(top3) if j != i]
        return eng[s.pid].overall + pair_rating(d[0], d[1])
    # Two siblings inside the top three ARE D1 — the third plays S1, and there is
    # nothing left to choose. Anything else and the coach's search decides.
    tp = {p.pid for p in top3}
    sib_top = [f for f in forced if {f[0].pid, f[1].pid} <= tp]
    if sib_top:
        s_i = next(i for i, p in enumerate(top3) if p.pid not in
                   {sib_top[0][0].pid, sib_top[0][1].pid})
    else:
        s_i = max(range(3), key=lambda i: (cfg_score(i), -i))  # tie: higher rank plays S1
    s1 = top3[s_i]
    d1 = [p for j, p in enumerate(top3) if j != s_i]

    # D2-D4: every partition of #4-#9 into three pairs (15 of them), best total
    # doubles ability wins; ties break toward ladder-natural pairing. A sibling pair
    # inside #4-#9 is a CONSTRAINT on the search, not a bonus inside it: the
    # partitions that split it are dropped and the best of what remains is played.
    def part_key(part):
        return (-sum(pair_rating(a, b) for a, b in part),
                [rank[a.pid] + rank[b.pid] for a, b in part])
    pairs = min(_legal_partitions(rest, forced), key=part_key)

    pairs = _order_pairs(pairs,
                         {_pk(pr): rank[pr[0].pid] + rank[pr[1].pid] for pr in pairs},
                         {_pk(pr): pair_rating(*pr) for pr in pairs})
    out = [s1] + list(d1)
    for a, b in pairs:
        out += [a, b]
    return out


def _arrange_wide(players: list, n_singles: int,
                  sibling_ids: dict | None = None,
                  pair_counts: dict | None = None) -> list:
    """`_arrange_state`'s mechanism at ANY singles width — the general form of the
    postseason arrangement, used by 1A's 2S/3D pilot and 8A/9A's 4S/5D one.

    Arrange a frozen-order top `n_singles + 2*n_doubles` into SLOT ORDER:
    [S1..Sn, D1a, D1b, D2a, D2b, …]. Same contract as `_arrange_state`: `_squad`
    dresses by position and `_slot_players` reads it back the same way, so this
    list IS the lineup. Anything short of the full card plays the plain order.

    ‼️ ONE MECHANISM, NOT A REGIME PER SHAPE (owner correction 2026-08).
    `_arrange_state` pools the top THREE and searches which ONE plays singles (the
    other two form D1) — the association's best player is NOT pinned to S1; a team
    can pair its #1 into D1 and start #2 or #3 at singles if that scores better.
    Every wider card is the same search one seat wider: pool the top
    `n_singles + 2`, pick `n_singles` of them for the singles seats, the remaining
    two are D1. 2S/3D pools four and picks two; 4S/5D pools six and picks four. The
    rest of the card replays `_arrange_state`'s own logic on the players below the
    pool: a search over every way to pair them, best total doubles ability wins,
    then `_order_pairs`'s anti-stacking rank-sum boundary.

    ‼️ The FLIGHT WEIGHT TABLE is what makes the search mean something at 4S/5D
    (`FLIGHT_WEIGHTS_4S5D`): the association prices S1 and D1 at 2.00 and the tail
    at 0.30/0.20/0.10, so where a coach spends the top six is the whole decision."""
    top_n = n_singles + 2
    if len(players) < top_n or (len(players) - top_n) % 2:
        return players
    from engine.doubles import doubles_rating
    eng = {p.pid: p.engine_player() for p in players}
    rank = {p.pid: i + 1 for i, p in enumerate(players)}

    sibs = sibling_ids or {}

    # MEMOISED on the pid pair: the partition search below is 105 partitions at
    # 4S/5D and every one of them re-asks about pairs drawn from the same 28, so
    # `doubles_rating` would be called 420 times to answer 28 questions. Identical
    # results, ~10x less work on the association's biggest postseason.
    _pr: dict = {}

    def pair_rating(a, b):
        key = _pk((a, b))
        if key not in _pr:
            r = doubles_rating(eng[a.pid], eng[b.pid])
            if b.pid in sibs.get(a.pid, ()):     # the map is symmetric by construction
                r += FAMILY_CHEMISTRY
            # Partner continuity — see `_arrange_state`'s note.
            _pr[key] = r + partner_chemistry(pair_counts, a.pid, b.pid)
        return _pr[key]

    # The singles seats + D1 consume the top `n_singles + 2`: every way to pick
    # `n_singles` of them for singles, the other two pairing for D1.
    top, rest = players[:top_n], players[top_n:]
    combos = list(itertools.combinations(range(top_n), n_singles))
    forced = _sibling_units(players, sibs)
    # A sibling pair inside the pool must not be SPLIT across the singles seats and
    # D1 — the two of them either both start at singles or they are D1. If nothing
    # survives the constraint the search runs unconstrained rather than failing a
    # lineup.
    tp = {p.pid: i for i, p in enumerate(top)}
    units = [tuple(tp[p.pid] for p in f) for f in forced
             if f[0].pid in tp and f[1].pid in tp]
    legal = [c for c in combos
             if all(len({i, j} & set(c)) != 1 for i, j in units)]
    combos = legal or combos

    def cfg_score(combo):
        s = [top[i] for i in combo]
        d = [top[i] for i in range(top_n) if i not in combo]
        return sum(eng[x.pid].overall for x in s) + pair_rating(d[0], d[1])
    # tie: prefer the combo drawing on the higher-ranked (lower-index) pool
    # members for singles, same spirit as `_arrange_state`'s `-i` tiebreak.
    combo = max(combos, key=lambda c: (cfg_score(c), -sum(c)))
    singles = sorted((top[i] for i in combo), key=lambda p: rank[p.pid])
    d1 = [top[i] for i in range(top_n) if i not in combo]

    def part_key(part):
        return (-sum(pair_rating(a, b) for a, b in part),
                [rank[a.pid] + rank[b.pid] for a, b in part])
    pairs = min(_legal_partitions(rest, forced), key=part_key)

    pairs = _order_pairs(pairs,
                         {_pk(pr): rank[pr[0].pid] + rank[pr[1].pid] for pr in pairs},
                         {_pk(pr): pair_rating(*pr) for pr in pairs})
    out = list(singles) + list(d1)
    for a, b in pairs:
        out += [a, b]
    return out


def _arrange_1a_postseason(eight: list, sibling_ids: dict | None = None,
                           pair_counts: dict | None = None) -> list:
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
    return _arrange_wide(eight, 2, sibling_ids, pair_counts)


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


def _legal_partitions(pool: list, forced: list):
    """`_pair_partitions(pool)`, keeping only the partitions that pair every sibling
    unit sitting wholly inside `pool`. Never empty: any set of disjoint pairs extends
    to a perfect matching of an even pool, so the constraint always leaves the search
    something to choose from."""
    have = {p.pid for p in pool}
    want = {frozenset((a.pid, b.pid)) for a, b in forced
            if a.pid in have and b.pid in have}
    if not want:
        return _pair_partitions(pool)
    return (part for part in _pair_partitions(pool)
            if want <= {frozenset((a.pid, b.pid)) for a, b in part})


def _sibling_units(players: list, sibs: dict) -> list[tuple]:
    """The DISJOINT sibling pairs inside `players`, in ladder order.

    ‼️ SIBLINGS ON ONE TEAM PARTNER, FULL STOP (owner rule 2026-09). This used to be
    `FAMILY_CHEMISTRY` alone — ~1/4 sd of the pair-rating spread, so two brothers
    partnered when the ratings were already close and not otherwise, which meant a
    coach who wanted to see them together had to check every dual of every program to
    find out whether they had been. Owner: "the sibling thing on the same team should
    be paired automatically because i can't track them all the time and it's easier to
    see it that way." The bonus stays and still decides which COURT the pair takes;
    what changed is that whether they are a pair is no longer a rating question.

    `sibs` is `TeamSeason.sibling_ids` — SIBLINGS, never the household (`_family_pairs`).
    Three siblings on one roster cannot all partner, so the ladder decides: the higher
    pair up and the third plays on. A pair straddling a boundary the format fixes (the
    top-three pool and the D2-D4 pool of the 1S/4D lineup, or S1 and the doubles pool of
    the 3S/4D one) is simply not honoured — the anti-stacking rule outranks this, and a
    lineup is never rewritten to put two siblings together."""
    used: set[str] = set()
    out = []
    for i, a in enumerate(players):
        if a.pid in used:
            continue
        kin = sibs.get(a.pid) or ()
        for b in players[i + 1:]:
            if b.pid in kin and b.pid not in used:
                out.append((a, b))
                used |= {a.pid, b.pid}
                break
    return out


#: Partner continuity (owner rule 2026-09): "when partners work together they should
#: be more likely to stay together." Season-to-season only — the evidence lives on
#: `TeamSeason.pair_counts`, which lives one season — and it must never hurt the
#: team, so it arrives by the two doors the sibling rule already opened:
#:   (1) an ESTABLISHED pair — `PARTNER_ESTABLISHED_MIN` doubles lines together this
#:       season at a non-losing share — is kept together by the DIRECT arrangers
#:       (`_arrange_regular`, `_arrange_early`) the way a sibling pair is, via
#:       `_force_pairs`; siblings outrank continuity where the two conflict. A pair
#:       LOSING together is never protected: the coach breaks it up, which is the
#:       realism, and is what keeps the mandate from ever costing the team.
#:   (2) the SEARCHING arrangers (`_arrange_state`, `_arrange_wide` — the postseason,
#:       where the stakes argue against a mandate) take continuity as a CHEMISTRY
#:       BONUS on the pair score, evidence-weighted and capped at `PARTNER_CHEMISTRY`
#:       — the `FAMILY_CHEMISTRY` scale exactly (~1/4 sd of the pair-rating spread),
#:       so it settles a near-tie toward the pair that has been playing together and
#:       never overrides a real ability difference. `_order_pairs`'s anti-stacking
#:       rank-sum boundary still runs afterwards, so no lineup this produces can be
#:       illegal.
PARTNER_CHEMISTRY = 0.025
PARTNER_ESTABLISHED_MIN = 6   # lines together before a pair is "established" —
                              # the awards' own `MIN_PAIR_MATCHES` bar, which is the
                              # module that first separated a partnership from two
                              # people put together once.
PARTNER_PRIOR = 6             # evidence weighting: 6 lines → half the bonus


def partner_chemistry(pair_counts: dict, a_pid: str, b_pid: str) -> float:
    """The continuity bonus for a candidate pair — 0.0 for two players who have
    never partnered, ramping toward `PARTNER_CHEMISTRY` with lines played together
    (`n/(n+PARTNER_PRIOR)`, the `ladder_score` evidence-weighting idiom)."""
    n = (pair_counts or {}).get(tuple(sorted((a_pid, b_pid))), (0, 0))[0]
    return PARTNER_CHEMISTRY * n / (n + PARTNER_PRIOR)


def _established_units(players: list, pair_counts: dict, forced: list) -> list[tuple]:
    """The disjoint ESTABLISHED pairs inside `players` — most lines together first,
    ties on the pid key (deterministic) — skipping anyone a `forced` (sibling) unit
    already claims: siblings outrank continuity. A pair qualifies on
    `PARTNER_ESTABLISHED_MIN` lines together AND a non-losing record together."""
    if not pair_counts:
        return []
    used = {p.pid for pr in forced for p in pr}
    by_pid = {p.pid: p for p in players}
    cands = [(rec[0], key) for key, rec in pair_counts.items()
             if rec[0] >= PARTNER_ESTABLISHED_MIN and 2 * rec[1] >= rec[0]
             and key[0] in by_pid and key[1] in by_pid]
    out = []
    for _, (a, b) in sorted(cands, key=lambda t: (-t[0], t[1])):
        if a in used or b in used:
            continue
        out.append((by_pid[a], by_pid[b]))
        used |= {a, b}
    return out


def _force_pairs(pairs: list, forced: list) -> list:
    """Rewrite a perfect matching so every pair in `forced` sits together, by SWAPPING
    partners — the two players displaced take each other's seats and nothing else in
    the lineup moves. Used where the pairing is constructed directly rather than
    searched (`_arrange_regular`, by owner rule); the searching arrangers filter their
    partitions instead, which keeps the best LEGAL arrangement rather than repairing an
    illegal one."""
    out = [list(p) for p in pairs]
    at = {p.pid: (i, j) for i, pr in enumerate(out) for j, p in enumerate(pr)}
    for a, b in forced:
        (ia, ja), (ib, jb) = at[a.pid], at[b.pid]
        if ia == ib:
            continue
        odd = out[ia][1 - ja]               # a's current partner, displaced to b's seat
        out[ia][1 - ja], out[ib][jb] = b, odd
        at[b.pid], at[odd.pid] = (ia, 1 - ja), (ib, jb)
    return [tuple(p) for p in out]


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
                     sibling_ids: dict | None = None,
                     pair_counts: dict | None = None) -> list:
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
    # Siblings inside the doubles pool partner whatever the strategy would have done
    # (owner rule 2026-09) — applied as a partner SWAP after the strategy has paired
    # the pool, so `traditional` stays a ladder pairing and `balanced`/`maximize` keep
    # their one direct decision. A sibling at S1 or in the S2/S3 seats is out of reach:
    # the 3S/4D allocation is fixed and is never rearranged for this.
    forced = _sibling_units(pool, sibling_ids or {})
    # Partner continuity (owner rule 2026-09): an established pair rides the same
    # swap machinery the sibling rule uses, after siblings have claimed their seats.
    forced = forced + _established_units(pool, pair_counts or {}, forced)
    if strategy == "traditional":
        pairs = [(pool[0], pool[1]), (pool[2], pool[3]),
                 (pool[4], pool[5]), (pool[6], pool[7])]
        pairs = _force_pairs(pairs, forced)
    else:
        from engine.doubles import doubles_rating, serve_rating, return_rating
        eng = {p.pid: p.engine_player() for p in eleven}

        sibs = sibling_ids or {}

        def dr(a, b):
            r = doubles_rating(eng[a.pid], eng[b.pid])
            if b.pid in sibs.get(a.pid, ()):
                r += FAMILY_CHEMISTRY      # see `_arrange_state` — a tiebreak only
            return r + partner_chemistry(pair_counts, a.pid, b.pid)

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
        pairs = _force_pairs([(ranked[0], ranked[7]), (ranked[1], ranked[6]),
                              (ranked[2], ranked[5]), (ranked[3], ranked[4])], forced)
        pairs = sorted(pairs, key=lambda pr: -dr(*pr))  # strongest pair plays D1
    out = [s1] + s23
    for a, b in pairs:
        out += [a, b]
    return out


def _arrange_early(nine: list, sibling_ids: dict | None = None,
                   group: str | None = None,
                   pair_counts: dict | None = None) -> list:
    """The early window's 5S/2D card in SLOT ORDER [S1-S5, D1a, D1b, D2a, D2b] —
    or 8A/9A's 4S/5D one, [S1-S4, D1a, D1b, … D5a, D5b] (owner rule 2070), which is
    the same plain-order allocation at a different width: pass the dual's `group`.

    That order IS the plain ladder — the allocation is fixed by the shape (the top five
    play singles, #6-#9 are the doubles pool) and there is no strategy here, which is
    why this window never had an arranger at all. The ONE thing that moves a player is
    the sibling swap: without it, siblings sitting at #6 and #8 draw different partners
    in every early dual while partnering everywhere else in varsity play, which is
    exactly the "sometimes" the rule was written to remove.

    A pair straddling the singles seats and the doubles pool is not honoured, for the
    same reason it is not in `_arrange_regular`: the allocation is the format's, and a
    lineup is never rearranged to put two siblings together."""
    need = lineup_need(EARLY_FORMAT_PHASE, group)
    if len(nine) < need:
        return nine
    n_s = dual_format(EARLY_FORMAT_PHASE, group).n_singles
    singles, pool = nine[:n_s], nine[n_s:need]
    forced = _sibling_units(pool, sibling_ids or {})
    # Partner continuity (owner rule 2026-09) — same swap, after siblings. In
    # practice the early window is the season's FIRST block, so pairs are rarely
    # established yet and this is usually empty; it matters when the window is
    # revisited by a degraded schedule or a test.
    forced = forced + _established_units(pool, pair_counts or {}, forced)
    if not forced:
        return nine                          # byte-identical to the pre-rule lineup
    # Swapped in place, so D1 is still the higher pair of the pool and nothing but the
    # two displaced players moves.
    pairs = _force_pairs([(pool[i], pool[i + 1]) for i in range(0, len(pool), 2)],
                         forced)
    out = list(singles)
    for a, b in pairs:
        out += [a, b]
    return out + list(nine[need:])


#: Sentinel for "this program's own group" — distinct from `None`, which is a real
#: value meaning the classification-blind shape for the phase (see `shape_group`).
_OWN_GROUP = object()


def _postseason_nine(ts: TeamSeason, phase: str = "state", group=_OWN_GROUP) -> list:
    """The frozen Order of Ability's top N for `phase` (nine, or 1A's pilot
    eight — see `dual_format`), freezing the ORDER on first use — the
    association establishes it before a program's first postseason dual and it
    binds until the season ends. Stored as pids on the TeamSeason (the archive
    never sees it; lineups are recorded per dual as always). Freezing the full
    ladder rather than a fixed-length slice is what lets 1A's road (eight) and
    its TOC entry (nine, back to 1S/4D — see `dual_format`) read the SAME
    frozen order at different slice lengths without a second freeze. It is also
    what lets 8A/9A dress FOURTEEN on their road and nine at the TOC off one
    order (owner rule 2070).

    `group` is the group whose SHAPE this dual is being played at — pass
    `shape_group`'s answer, not a side's own group, wherever two programs are
    actually meeting; it defaults to this program's own."""
    if not ts.order_of_ability:
        ts.order_of_ability = [p.pid for p in _order(ts)]
    by_pid = {p.pid: p for p in ts.roster}
    ranked = [by_pid[pid] for pid in ts.order_of_ability if pid in by_pid]
    # An injury SUBSTITUTES within the frozen order rather than reopening it — the
    # rest of the order does not move, an unavailable name is simply skipped.
    ranked = _healthy(ts, ranked)
    g = ts.school.group if group is _OWN_GROUP else group
    return ranked[:lineup_need(phase, g)]


def _arrange_postseason(pool: list, fmt: DualFormat, sibling_ids: dict | None,
                        pair_counts: dict | None = None) -> list:
    """Arrange a frozen-order pool onto `fmt`'s card. Keyed on the SHAPE, never on
    the group: the shape is what the arrangement is about, and one dual has one
    shape however its two sides are classified (see `shape_group`)."""
    if fmt.n_singles == 1:
        return _arrange_state(pool, sibling_ids, pair_counts)
    return _arrange_wide(pool, fmt.n_singles, sibling_ids, pair_counts)


def _lineup(ts: TeamSeason, phase: str, rng: random.Random, opp=None,
            group=_OWN_GROUP) -> list:
    """The nine — or eight on 1A's road to State, fourteen on 8A/9A's — who dress
    for THIS dual, in slot order. `opp` (the opposing TeamSeason, regular season
    only) lets the coach rest starters against a truly weaker side — see
    `_rest_count`. Every branch pulls from a HEALTHY pool first (`_healthy`) — an
    injured player is skipped, and depth steps up, without changing anyone's rank.

    `group` is the group whose SHAPE this dual is played at (`shape_group`), which
    is not necessarily either side's own — see `dual_format`."""
    if phase in POSTSEASON:                        # strict, frozen, arranged
        pool = _postseason_nine(ts, phase, group)
        g = ts.school.group if group is _OWN_GROUP else group
        return _arrange_postseason(pool, dual_format(phase, g), ts.sibling_ids,
                                   ts.pair_counts)
    if phase in SHOWCASE:
        # ‼️ A SHOWCASE MUST NOT FREEZE THE ORDER OF ABILITY. The freeze is the
        # association's anti-stacking rule and it binds from a program's first
        # POSTSEASON dual — a showcase is regular season, in the middle of it, and
        # freezing here would bind a program's championship lineup to its April
        # ladder and hand the rule a month of drift it was written to prevent.
        # So: the LIVE ladder, with the league's bench rotation (a showcase is
        # where a coach tries people), arranged onto the 1S/4D card by the same
        # anti-stacking arrangement the postseason uses.
        # ...at the DUAL's shape (`shape_group`): a showcase plays the class's own
        # state format (owner rule 2026-09), and a pod mixes classes.
        g = ts.school.group if group is _OWN_GROUP else group
        order = _healthy(ts, _order(ts))
        need = lineup_need(phase, g)
        nine, bench = order[:need], order[need:]
        if bench and rng.random() < _ROTATE_ONE:
            nine[-1] = bench[rng.randrange(len(bench))]
        return _arrange_postseason(nine, dual_format(phase, g), ts.sibling_ids,
                                   ts.pair_counts)
    order = _healthy(ts, _order(ts))
    g = ts.school.group if group is _OWN_GROUP else group
    need = lineup_need(phase, g)
    # Talent-aware staffing: sit a run of starters from the TOP against a truly
    # weaker side and shift everyone up a rung — the ladder ORDER is untouched, so
    # the card still reads as the ladder. Regular-season phases only (this branch).
    # `order` is already injury-filtered, so `spare` here is healthy bench only.
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
    # as `_squad`'s default positional mapping always did for that shape. 8A/9A's early
    # window plays 4S/5D (owner rule 2070) and takes the same plain-order path — the
    # allocation is the format's there too.
    if phase == "regular":
        # the per-dual flip draw runs either way, so the rng stream stays aligned.
        flip = rng.random() < _PHILOSOPHY_FLIP
        strategy = _coach_strategy(ts.school.key)
        if flip:
            strategy = _flip_strategy(strategy)
        return _arrange_regular(nine, strategy, ts.sibling_ids, ts.pair_counts)
    if phase == EARLY_FORMAT_PHASE:
        return _arrange_early(nine, ts.sibling_ids, g, ts.pair_counts)
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
            fmt: DualFormat | None = None) -> None:
    """Credit a line to the players who played it — and LOG the match.

    The W-L counters alone cannot answer any of the questions the awards ask
    (`jhsaa_awards`): who you beat, from which court, and when. So each
    appearance also records the opponent's pids, the slot and the phase — a
    résumé, not a record. Kept as a tuple rather than a dict because a gender's
    season logs ~100k of these.

    ‼️ `_slot_players` MUST be told the shape THE DUAL WAS PLAYED AT — see its own
    docstring. `fmt` is threaded through from `play_dual` so a 1A postseason dual
    (2S/3D) resolves D-slots against 2 singles and an 8A/9A one (4S/5D) against 4,
    rather than the 1S/4D default `dual_format(phase, None)` would silently fall
    back to. It is ONE shape for both sides — a dual has one card, and taking it
    from each side's own group is what `shape_group` exists to prevent."""
    f = fmt or dual_format(phase, ts.school.group)
    mates = _slot_players(lineup, phase, slot, f)
    opps = (tuple(p.pid for p in _slot_players(opp_lineup, phase, slot, f))
            if opp_lineup else ())
    if len(mates) == 2 and mates[0].pid != mates[1].pid:
        # Partner continuity's evidence (owner rule 2026-09) — a doubles line is a
        # pair working together, whatever the phase. The `!=` guard keeps a degraded
        # side's wrapped lineup (`_slot_players` wraps rather than raises) from
        # crediting a player as their own partner.
        pc = ts.pair_counts.setdefault(
            tuple(sorted((mates[0].pid, mates[1].pid))), [0, 0])
        pc[0] += 1
        if won:
            pc[1] += 1
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


def _deciding_tiebreaks(home: Team, away: Team, la: list, lb: list, phase: str,
                        shape: DualFormat, seed: int) -> tuple[list[dict], int]:
    """THE DECIDERS (JHSAA rule 2026-09) — how a level postseason dual is settled
    in the association's one even shape, Group 2's 3S/3D: THREE CONCURRENT
    10-point tiebreakers, at No. 1 singles, No. 1 doubles and No. 2 doubles
    (`DECIDER_FLIGHTS`), played by the SAME players who played those flights in
    the dual (`home`/`away` are the dressed engine Teams — home court lift and
    all), and the side that wins two of the three advances. Returns the three
    box-score rows and the winner (0 home, 1 away).

    Scored by the engine's own fast tiebreak dice: `engine.fast._tb_prob` for the
    singles decider and the doubles fast model's tiebreak logit for the pairs,
    both under `HS_PROFILE`, with `_mtb_score` turning the draw into a real
    `10-7` rather than `1-0` (owner: "1-0 doesn't tell me anything"). Its OWN rng
    stream off the dual's seed — drawing from the dual's stream would shift every
    later match in the association.

    ‼️ A decider is NOT a match: nothing is credited to `records`/`matches`
    (awards, the ladder), it never reaches `lines` (records, flight boxes, court
    totals, TOSS), and it rides its own `tiebreak` key and archive column. It is
    regular-season-blind by construction — `play_dual` only asks for it in a
    POSTSEASON phase; a drawn league dual uses `jv_outcome`."""
    from engine.fast import TUNE, _edges, _logistic, _mtb_score, _tb_prob, effective_gap
    from engine.doubles import doubles_rating
    from engine.state import MatchContext
    rng = random.Random(f"{seed}|jhsaa-decider")
    tune = {**TUNE, **HS_PROFILE}
    ctx = MatchContext()
    out: list[dict] = []
    home_wins = 0
    for slot in DECIDER_FLIGHTS:
        kind, i = slot[0], int(slot[1:]) - 1
        if kind == "S":
            p0, p1 = home.singles[i % len(home.singles)], away.singles[i % len(away.singles)]
            p = _tb_prob(p0, p1, ctx, _edges(p0), _edges(p1), True, tune)
        else:
            hd, ad = home.doubles_players or home.singles, away.doubles_players or away.singles
            h2 = [hd[k % len(hd)] for k in (2 * i, 2 * i + 1)]
            a2 = [ad[k % len(ad)] for k in (2 * i, 2 * i + 1)]
            gap = doubles_rating(*h2) - doubles_rating(*a2)
            p = _logistic(tune["d_tb_slope"]
                          * effective_gap(gap, tune["gap_knee"], tune["gap_accel"],
                                          tune.get("gap_bands", False)))
        r = rng.random()
        win = 0 if r < p else 1
        hs, as_ = _mtb_score(win, r, p, DECIDER_TARGET)
        home_wins += win == 0
        out.append({"slot": slot,
                    "home": [x.name for x in _slot_players(la, phase, slot, shape)],
                    "away": [x.name for x in _slot_players(lb, phase, slot, shape)],
                    "score": f"{hs}-{as_}", "home_won": win == 0})
    return out, 0 if home_wins * 2 > len(DECIDER_FLIGHTS) else 1


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
    # The JV season is hosted like the varsity one — its own league round robin and
    # invitationals have a home side — so it takes the same lift. Its one showcase is
    # a `showcase_pod`, which `home_court` already reads as neutral.
    res = simulate_dual(_squad(a.team, phase, la, fmt, lift=home_court(seed, phase)),
                        _squad(b.team, phase, lb, fmt),
                        seed=seed, play_all=True, fidelity=FIDELITY, dual_fmt=fmt,
                        singles_fmt=mf, doubles_fmt=mf, profile=HS_PROFILE)
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


def _injury_tick_and_roll(ts: TeamSeason, dressed: list, dual_index: int) -> None:
    """After one VARSITY dual: tick every hurt player's clock down, then roll
    fresh injuries on exactly the players who dressed (`dressed`) — the same dice
    every league uses (`injuries.roll_injury`), so the autouse test fixture that
    disables them for the whole suite (determinism) disables them here too, and
    production ships on real entropy same as everywhere else in the engine.

    Never called for a JV dual — see `TeamSeason.injuries`."""
    if not _injuries.is_enabled():
        return
    for pid in list(ts.injuries):
        n = ts.injuries[pid]
        if n == _injuries.SEASON_ENDING:
            continue
        n -= 1
        if n <= 0:
            del ts.injuries[pid]
        else:
            ts.injuries[pid] = n
    if not dressed:
        return
    # Team-level calibration, same rule as the college model: BASE_RATE is tuned on
    # six competitors a dual, so a bigger card (the 3S/4D format dresses 11) scales
    # each roll down to keep the TEAM's injury volume where it was tuned.
    scale = min(1.0, _injuries.EXPOSURE_BASELINE / len(dressed))
    for p in dressed:
        if p.pid in ts.injuries:
            continue
        out = _injuries.roll_injury(p, scale)
        if not out:
            continue
        season_ending = out == _injuries.SEASON_ENDING
        ts.injuries[p.pid] = _injuries.SEASON_ENDING if season_ending else out
        ts.injury_log.append({
            "pid": p.pid, "name": p.name, "dual_index": dual_index,
            "duals_out": 0 if season_ending else out,
            "season_ending": season_ending,
        })


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
    # ‼️ ONE SHAPE PER DUAL, resolved from BOTH sides. `a`/`b` share a classification in
    # every postseason pairing (a bracket never crosses groups), so this used to read
    # the home side's group and say so — but 8A/9A's pilot reaches the EARLY window
    # (owner rule 2070), which pairs across one classification, so the two sides need
    # not want the same card. See `shape_group`: mismatch falls back to the phase's
    # classification-blind shape rather than dressing one side short.
    grp = shape_group(phase, a.school.group, b.school.group)
    shape = dual_format(phase, grp)
    la, lb = _lineup(a, phase, lrng, b, grp), _lineup(b, phase, lrng, a, grp)
    fmt = match_format(phase)
    # `a` is the home side by construction (it is `a` whose schedule row says so a few
    # lines down), so the host's lift goes on `a` and nothing goes on `b`. The two
    # dressed Teams are kept: a level dual's deciders are played by the SAME engine
    # players (lift included) who played the flights.
    home_team = _squad(a, phase, la, shape, lift=home_court(seed, phase))
    away_team = _squad(b, phase, lb, shape)
    res = simulate_dual(home_team, away_team, seed=seed,
                        play_all=True, fidelity=FIDELITY,
                        dual_fmt=shape,
                        singles_fmt=fmt, doubles_fmt=fmt, profile=HS_PROFILE)
    lines = []
    for ln in res.lines:                       # individual records, for awards
        hw = getattr(ln, "home_won", None)
        if hw is None:
            continue
        slot = getattr(ln, "slot", "")
        _credit(a, la, phase, slot, bool(hw), lb, b.school.name, shape)
        _credit(b, lb, phase, slot, not hw, la, a.school.name, shape)
        lines.append({"slot": slot,
                      "home": [x.name for x in _slot_players(la, phase, slot, shape)],
                      "away": [x.name for x in _slot_players(lb, phase, slot, shape)],
                      "score": _score_str(ln), "home_won": bool(hw)})
    a.points_for += res.home_points
    a.points_against += res.away_points
    b.points_for += res.away_points
    b.points_against += res.home_points
    # ‼️ A LEVEL DUAL (JHSAA rule 2026-09). Only Group 2's 3S/3D postseason shape
    # can produce one today (every other varsity total is odd) and `res.winner`
    # is WRONG for it — the engine reports `0 if points[0] > points[1] else 1`,
    # i.e. an AWAY win on a draw (the `jv_outcome` trap). A POSTSEASON dual is
    # settled by three concurrent 10-point tiebreakers — S1, D1, D2, best two of
    # three, the same players who played those flights (`_deciding_tiebreaks`);
    # a REGULAR-SEASON dual (unreachable today) uses the JV ladder — points,
    # sets, games — and a dual still level after that is a TIE, recorded as one.
    deciders: list = []
    tied = False
    if res.home_points == res.away_points:
        if phase in POSTSEASON:
            deciders, dec_winner = _deciding_tiebreaks(
                home_team, away_team, la, lb, phase, shape, seed)
            res.winner = dec_winner
        else:
            out = jv_outcome(res)
            tied = out == 0
            res.winner = 0 if out > 0 else 1
    # DualResult.winner is an INT — 0 home, 1 away. Comparing it to "home" silently
    # credits the away team every dual; under the home-and-home schedule this used to
    # run, that left every side at exactly .500 with correct-looking point
    # differentials. Cost an hour.
    # `level` is stamped on every VARSITY row too, not only on JV rows: the archive
    # column is not nullable-by-convention, and a row that merely OMITS the marker is
    # indistinguishable from one written before the column existed.
    # `tiebreak` is the deciders' box score — its OWN key and its own archive
    # column, never entries in `lines`: every reader of `lines` (records, flight
    # boxes, court totals, the research export's shape inference) would count a
    # 10-point decider as a match, and a tiebreaker is not one (nothing is
    # credited to a player record for it).
    a.schedule.append({"opp": b.school.name, "home": True, "phase": phase,
                       "pf": res.home_points, "pa": res.away_points,
                       "won": res.winner == 0 and not tied, "tied": tied,
                       "district": district, "level": LEVEL_VARSITY,
                       "challenge": challenge, "lines": lines,
                       "tiebreak": deciders})
    b.schedule.append({"opp": a.school.name, "home": False, "phase": phase,
                       "pf": res.away_points, "pa": res.home_points,
                       "won": res.winner == 1 and not tied, "tied": tied,
                       "district": district, "level": LEVEL_VARSITY,
                       "challenge": challenge, "lines": lines,
                       "tiebreak": deciders})
    if tied:
        a.ties += 1
        b.ties += 1
    elif res.winner == 0:
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
    # Injuries roll last, on the lineups that actually took the court — after the
    # schedule rows above, so `len(a.schedule)`/`len(b.schedule)` are this dual's
    # own ordinal in each team's season.
    _injury_tick_and_roll(a, la, len(a.schedule))
    _injury_tick_and_roll(b, lb, len(b.schedule))
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
    # D5 is contested in NO shape on this table — it exists so that a generic
    # per-slot reader (the awards résumé weighting) ranks 8A/9A's fifth doubles
    # court BELOW its fourth instead of taking a bare `.get(slot, 0.25)` default
    # and pricing the card's last court above four of its others. The weight a
    # 4S/5D dual is actually RATED on is the association's own, below.
    "D5": 0.05,
}

#: ‼️ THE 4S/5D TABLE IS THE ASSOCIATION'S OWN AND IS SEPARATE (owner rule 2070).
#: 8A/9A's nine-court card is not the 1S/4D table with two rows bolted on: the
#: association re-priced the whole thing, S1 and D1 at 2.00 each and a steep decay
#: to 0.10 at D5, max 7.50. So the same flight NAME is worth different amounts in
#: different shapes, which is why the table is resolved per DUAL (`flight_weights`)
#: rather than being one module constant — and why nothing may merge the two.
#:
#: `rating._flight_score` normalises by the weight actually CONTESTED in each dual,
#: so a 7.50-max shape and a 3.85-max one each contribute a 0-1 share to the same
#: TOSS table; that is the same property that already lets 5S/2D, 3S/4D and 1S/4D
#: share one rating graph, and it is what makes a per-dual table safe here.
FLIGHT_WEIGHTS_4S5D = {
    "S1": 2.00, "S2": 1.00, "S3": 0.65, "S4": 0.30,
    "D1": 2.00, "D2": 0.80, "D3": 0.45, "D4": 0.20, "D5": 0.10,
}


def flight_weights(phase: str, group: str | None = None) -> dict:
    """The flight weight table for a dual of `phase` at `group`'s shape.

    ‼️ KEYED ON THE SHAPE, NOT THE CLASSIFICATION. 8A/9A's league season is 3S/4D
    like everybody's and rates on the ordinary table; only the shapes that actually
    play nine courts — their road to State and their early window — use
    `FLIGHT_WEIGHTS_4S5D`. Pass `shape_group`'s answer for a real dual."""
    return (FLIGHT_WEIGHTS_4S5D
            if dual_format(phase, group) is FORMATS["state_4s5d"]
            else FLIGHT_WEIGHTS)
# ‼️ NOT a shared denominator FQI divides by, and NOT the max for any one dual shape
# any more (the three cards — 5S/2D early, 3S/4D regular, 1S/4D state/showcase — each
# contest a different weight total now that D3/D4 are load-bearing everywhere).
# `rating._flight_score` totals the weight actually CONTESTED in each dual and
# normalises per-dual, so every shape contributes a 0..1 share to the same table
# without either being over- or under-counted. This constant is historical/
# documentary only — the 5S/2D-era max — and nothing in the pipeline reads it.
MAX_FLIGHT_WEIGHT = 3.70


# The REAL-WORLD scoreline target the HS match profile was calibrated against
# (engine.fast.HS_PROFILE): five seasons of actual Oregon high-school tennis,
# boys + girls 2021-25, 41,932 varsity matches / 84,238 completed standard sets
# (github.com/quarterback/or-tennis-data). ONE authority — the in-game realism
# view (/jhsaa/realism) and scripts/jhsaa_scoreline_benchmark.py both read
# these; see docs/AAR-jhsaa-scoreline-realism.md before "correcting" a number.
OREGON_SET_TARGET = {"6-0": 26.4, "6-1": 21.5, "6-2": 17.4, "6-3": 13.4,
                     "6-4": 12.3, "7-5": 5.1, "7-6": 3.9}
OREGON_THREE_SET = 13.8   # % of best-of-3 matches reaching a third set


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
    teams = list(teams)                      # iterated twice: the group map, then the duals
    _group_of = {t.school.name: t.school.group for t in teams}
    for t in teams:
        for d in t.schedule:
            if not d.get("home") or d.get("phase") in drop:
                continue
            lines = []
            for ln in d.get("lines") or ():
                hg, ag = _games(ln.get("score", ""))
                lines.append({"slot": ln.get("slot", ""), "home_won": ln.get("home_won"),
                              "home_games": hg, "away_games": ag})
            # ‼️ THE WEIGHT TABLE RIDES ON THE DUAL, because 8A/9A's road and early
            # window play a shape with its OWN prices for the same flight names
            # (`FLIGHT_WEIGHTS_4S5D`). Resolved from BOTH sides via `shape_group`,
            # exactly as `play_dual` resolved the shape it was played at — reading
            # the home side alone would rate a mixed-classification early dual on a
            # table nobody played.
            grp = shape_group(d.get("phase") or "regular", t.school.group,
                              _group_of.get(d["opp"]))
            out.append({"home": t.school.name, "away": d["opp"], "home_won": d["won"],
                        "home_points": d["pf"], "away_points": d["pa"], "lines": lines,
                        "weights": flight_weights(d.get("phase") or "regular", grp)})
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


def sectional_field(group: str, standings: dict[str, list[TeamSeason]],
                     power: dict | None = None
                     ) -> tuple[list[TeamSeason], list[TeamSeason]]:
    """(protected, entrants) for `group` — every program in the classification.

    Protected (`PROTECTED` seats, enter at Regionals): district champions
    first, then the best remaining ATR until the seats are filled (owner rule
    2070 — postseason seeding runs on ATR, see `_atr_key`). Everyone else enters
    Sectionals. Both lists come back ATR ordered."""
    key = _atr_key(power)
    champs = sorted((ts[0] for ts in standings.values() if ts), key=key)
    rest = sorted((t for ts in standings.values() for t in ts[1:]), key=key)
    fill = max(0, PROTECTED - len(champs))
    protected = sorted(champs + rest[:fill], key=key)
    return protected, rest[fill:]


def _elim_round(pool: list[TeamSeason], byes: int, *, rng: random.Random,
                 phase: str) -> tuple[list[TeamSeason], list[dict]]:
    """One round of single elimination over `pool` (already strength-ordered,
    strongest first, e.g. by `_atr_key`): the top `byes` entries advance without
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


# --- THE EPIREGIONAL — the Zonal champions' play-in (owner rule 2026-09) ---------

#: The round's heading (plural, no "Round", like every other stage heading —
#: "7A Epiregionals"). The per-dual UNIT is a REGION NAME drawn from the NCAA
#: tournament's cosmetic pool (`app.regions.LEAGUE_NAMES`) — "Cascade Epiregional".
EPIREGIONAL_NAME = "Epiregionals"
#: ‼️ THE SEEDING ATR — the number the State draw is ordered on (owner rule
#: 2026-09: "ATR not TOSS for seeding!"). Deliberately a SECOND formula beside
#: `atr`/`ATR_TOSS_WEIGHT` above: that one ranks the Semi-Conference and Conference
#: pools, is archived on every standings row, and retuning it would move the
#: recovery ladder. This one is a z-score blend WITHIN one class-gender State
#: field, so both terms are on the same scale before they are weighted — the raw
#: 0-1 blend lets TOSS's narrow spread be swamped by win percentage's wide one.
#: Measured over 2065-2068 in 8A/9A: TOSS alone seeded a 22-11 above a 24-3 in 8A
#: every season, while 9A picked the same four either way. TOSS stays dominant at
#: 0.6 so a bye still needs a real schedule; record decides those 8A cases.
#: Tuning constants, not derived values — retune here, nowhere else.
SEED_ATR_TOSS_WEIGHT = 0.6
SEED_ATR_WIN_WEIGHT = 0.4


def seed_atr(teams: list, power: dict | None) -> dict[str, float]:
    """{school: seeding ATR} over exactly `teams` — the z-score blend above,
    standardised WITHIN this list (a class-gender State field, or the eight Zonal
    champions), never over the gender. Standardising within the field is what makes
    the two weights mean what they say: 0.6 of a TOSS standard deviation against
    0.4 of a win-percentage one. A one-team or all-equal list gets zeros (no
    spread to standardise), so the caller's name tie-break decides.

    `power` maps school -> `rating.RatingLine`; the TOSS term is `pi_raw`, the same
    full-precision value every other seed in the association is drawn from. A
    team the rating does not know contributes the field mean (a z of zero) on that
    term rather than a zero it did not earn."""
    if not teams:
        return {}
    known = [(power or {}).get(t.school.name) for t in teams]
    pis = [ln.pi_raw for ln in known if ln is not None]
    mean_pi = sum(pis) / len(pis) if pis else 0.0
    xs = [(ln.pi_raw if ln is not None else mean_pi) for ln in known]
    ys = [t.win_pct for t in teams]

    def _z(vals):
        n = len(vals)
        m = sum(vals) / n
        var = sum((v - m) ** 2 for v in vals) / n
        sd = var ** 0.5
        return [((v - m) / sd if sd > 1e-12 else 0.0) for v in vals]

    zx, zy = _z(xs), _z(ys)
    return {t.school.name: SEED_ATR_TOSS_WEIGHT * a + SEED_ATR_WIN_WEIGHT * b
            for t, a, b in zip(teams, zx, zy)}


def _seed_atr_key(satr: dict[str, float]):
    """Sort key: best seeding ATR first, school name breaking ties — the order has
    to reproduce, never a raw float comparison alone."""
    return lambda t: (-satr.get(t.school.name, 0.0), t.school.name)


def epiregional_names(gender: str, year: int, group: str, salt: str = "") -> list[str]:
    """Four cosmetic region names for a class-gender's Epiregional duals — the NCAA
    tournament's own generator (`app.regions.region_names`), fed a stable digest
    so the names rotate year to year and differ class to class while an archived
    season reproduces after a restart (blake2s, never `hash()`: these units are
    archived and honoured). Labels only: a "Cascade Epiregional" carries no
    geography, exactly as the college regions do not."""
    from .regions import region_names
    digest = hashlib.blake2s(f"epiregional|{gender}|{year}|{group}|{salt}".encode(),
                             digest_size=8).digest()
    return region_names(int.from_bytes(digest, "big"), 4)


def run_epiregional(champs: list[TeamSeason], power: dict | None,
                    prestate: dict, names: list[str], *,
                    seed: int) -> tuple[dict, list[TeamSeason], list[TeamSeason]]:
    """THE EPIREGIONAL (owner rule 2026-09): the eight Zonal champions of a class
    play ONE round among themselves, and the four winners take the State draw's
    first four bye lines. It decides PLACEMENT only — all eight are already in
    State, and a loser here drops into the merit pool with everyone else (where it
    may still earn a bye on its own ATR).

    Why it exists: a Zonal title used to buy seeds 1-8 outright, and Zonals vary a
    lot in strength. Measured on 2068 across all 24 class-genders, the worst-placed
    team in a State field carried seed 8 in 20 of them and ranked 19th-27th in its
    own class; girls' 8A's rank-1 team was seeded 12th because it did not win its
    Zonal, and that field was won by a 31 seed. Qualification is earned on court;
    seed placement now is too.

    Pairing is 1v8, 2v7, 3v6, 4v5 on the seeding ATR (`seed_atr`) AMONG THESE EIGHT
    — a separate pass from the State draw's own seeding over the whole field. The
    higher seed HOSTS. Rematch rule: never immediately replay a road opponent.
    Two Zonal champions came out of different Zonals, and Regionals feed Zonals
    positionally, so a rematch is impossible by construction — the swap repair is
    kept so the rule is stated in code rather than assumed of the draw upstream.

    Each dual is a named UNIT — one of `names`, the four cosmetic region names —
    so a winner's honours chip reads "Cascade Epiregional", never a number.

    Returns (archive_dict, winners, losers) in the `run_rounds` archive shape.
    `field` is the seed order among the eight (`state._jh_seeds` labels off it)."""
    field = list(champs)
    if len(field) < 2:
        return ({"field": [t.school.name for t in field], "rounds": [[]],
                 "survivors": [t.school.name for t in field],
                 "round_names": [EPIREGIONAL_NAME], "names": []}, field, [])
    satr = seed_atr(field, power)
    order = sorted(field, key=_seed_atr_key(satr))
    n = len(order)
    if n % 2:
        # Never at association size (the ladder halves 32 -> 16 -> 8). A scaled
        # fixture could hand over an odd count; the last seed sits out and stays
        # a plain field member, never a winner.
        order, odd = order[:-1], order[-1:]
    else:
        odd = []
    n = len(order)
    pairs = [[order[i], order[n - 1 - i]] for i in range(n // 2)]
    met = set()
    for games in (prestate or {}).get("rounds") or ():
        for gm in games:
            met.add(frozenset((gm.get("home"), gm.get("away"))))
    # One swap of the LOWER seeds between adjacent pairs repairs a rematch without
    # touching the top-seed side of either pairing.
    for i in range(len(pairs)):
        a, b = pairs[i]
        if frozenset((a.school.name, b.school.name)) in met:
            for j in range(len(pairs)):
                if j == i:
                    continue
                c, d = pairs[j]
                if (frozenset((a.school.name, d.school.name)) not in met
                        and frozenset((c.school.name, b.school.name)) not in met):
                    pairs[i][1], pairs[j][1] = d, b
                    break
    rng = random.Random(seed)
    games, winners, losers = [], [], []
    for k, (hi, lo) in enumerate(pairs):
        res = play_dual(hi, lo, seed=rng.randrange(1 << 30), phase="epiregional")
        win, lose = (hi, lo) if res.winner == 0 else (lo, hi)
        unit = f"{names[k]} Epiregional" if k < len(names) else f"Epiregional {k + 1}"
        games.append({"home": hi.school.name, "away": lo.school.name,
                      "home_points": res.home_points,
                      "away_points": res.away_points,
                      "winner": win.school.name, "unit": unit})
        winners.append(win)
        losers.append(lose)
    losers += odd
    return ({"field": [t.school.name for t in order + odd], "rounds": [games],
             "survivors": [t.school.name for t in winners],
             "round_names": [EPIREGIONAL_NAME], "names": list(names)},
            winners, losers)


#: How many bye lines the State draw holds — four to the Epiregional winners and
#: four on merit. `run_state`'s `champions` is this count: it sizes the bye budget
#: and decides whether a field expands (a 40's Qualifiers Round), and it must stay
#: at the ladder's Zonal count so every draw keeps exactly the shape it had.
STATE_BYES = 8
EPIREGIONAL_BYES = 4


def state_seed_order(zonal_champs: list[TeamSeason], epi_winners: list[TeamSeason],
                     rest: list[TeamSeason], power: dict | None
                     ) -> tuple[list[TeamSeason], list[str]]:
    """The State field in SEED ORDER (owner rule 2026-09), and the bye holders.

    Bye lines 1-8: the `EPIREGIONAL_BYES` Epiregional winners plus the best
    `STATE_BYES - EPIREGIONAL_BYES` teams among EVERYONE ELSE on the seeding ATR
    (`seed_atr`, standardised over this whole field). An Epiregional loser is
    eligible for a merit bye — in a season where the Zonal champions really are
    the eight strongest teams they take all eight, which is the right answer.
    The eight are then seeded 1-8 AMONG THEMSELVES on ATR (an Epiregional win
    guarantees a top-eight line, not a top-four one), and everyone else 9+ on ATR
    regardless of how they qualified.

    In a 24 the first eight lines are the single byes; in a 40 the double byes;
    in a 32 there are no byes and this is placement only. `run_state` derives all
    three from the ORDER, so the shape is untouched."""
    field = list(zonal_champs) + list(rest)
    satr = seed_atr(field, power)
    key = _seed_atr_key(satr)
    win_names = {t.school.name for t in epi_winners}
    winners = [t for t in field if t.school.name in win_names]
    others = sorted((t for t in field if t.school.name not in win_names), key=key)
    merit = others[:max(0, STATE_BYES - len(winners))]
    byes = sorted(winners + merit, key=key)
    tail = sorted(others[len(merit):], key=key)
    return byes + tail, [t.school.name for t in byes]


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
    the SAME full-precision value the seeding key blends in (`_atr_key`), never
    a rounded or re-derived one. A team the rating does not know contributes its
    win percentage alone rather than defaulting to a zero it did not earn."""
    line = (power or {}).get(team.school.name)
    if line is None:
        return team.win_pct
    return atr_of(line.pi_raw, team.win_pct)


def _atr_key(power: dict | None):
    """Sort key: best ATR first, school name breaking ties (never a raw float
    comparison on equal ratings — the order has to be reproducible).

    ‼️ THE ONE POSTSEASON SEEDING KEY (owner rule 2070). Every postseason-field
    sort — the protected fill, the Ward and Regional field seedings, every
    recovery pool, the Divisional tiers, the Conference pools — ranks on ATR now,
    never on raw TOSS. It replaced the retired `_power_key` (pure `pi_raw`): with
    1A's road at 2S/3D and 8A/9A's whole postseason and early window at 4S/5D,
    three dual shapes feed one TOSS graph, and an opponent-strength composite
    folded across formats distorts exactly the comparisons a seed order is made
    of. ATR's win term is format-blind, which is what damps the distortion. The
    STATE draw itself already seeds on `seed_atr` (the Epiregional's z-blend) and
    the district tiebreak ladder still reads TOSS at rung 4 — that is a LEAGUE
    decision, not state seeding, and it did not move.

    Shared by every postseason-field function so protected/unprotected/pool order
    all agree. Without a `power` table (a caller running a district in isolation),
    ATR degrades to win percentage and the old point-differential tiebreak keeps
    the order reproducible."""
    def key(t: TeamSeason):
        if power is None:
            return (-t.win_pct, -(t.points_for - t.points_against), t.school.name)
        return (-atr(t, power), t.school.name)
    return key


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
#: ‼️ THE REQUIRED FINAL ROUND OF THE ROAD (owner rule 2026-08, superseding the
#: reconciliation-only design). Conference winners no longer qualify for State
#: directly — the data showed losing-record teams reaching the playoffs through
#: the Conference's automatic access — they advance to STATE SPECIALS, where each
#: one must beat a CHALLENGER: the best remaining REGULAR-SEASON teams drawn from
#: the ENTIRE classification (anyone not already qualified and not a Conference
#: winner, wherever or whether they were eliminated). `bids = len(conference_
#: winners)`, one dual per bid, winners qualify, losers finish at Specials — so
#: the arithmetic closes every field size by construction. See
#: `_state_specials_round`; `_state_specials` remains the emergency
#: reconciliation behind it, only if the played round still leaves State short.
STATE_SPECIAL_NAME = "State Specials"
#: The FINISH a Specials loser carries (owner, 2026-08: "a specials loser ends at
#: Specials, not State Specials") — the event heading keeps the full name; the
#: ledger/finish string is the short one, the way "Semi-State" is not "the
#: Semi-State Round".
STATE_SPECIAL_FINISH = "Specials"
#: ‼️ THE SPECIAL CHALLENGERS — the bridge round in FRONT of the State Specials
#: (owner rule 2026-08, extending the Specials design in
#: `docs/AAR-jhsaa-state-specials.md`; this round's own AAR is
#: `docs/AAR-jhsaa-special-challengers.md`). The Specials' challenger side is
#: SELECTED by regular-season record, which leaves one narrow leak: a genuinely
#: State-caliber team that lost once in an early local round (a Wards exit) and
#: whose record misses the formula cut has NO road back — the data found ~40
#: such profiles over four seasons. So the weakest formula-selected challenger
#: seats are now DEFENDED ON COURT: eligible early exits (rank/TOSS/district-
#: title gated, capped per class) each play one dual against a weakest-selected
#: challenger, and the winner takes that seat INTO the State Specials. It grants
#: zero extra berths — the Specials field size and the Conference winners are
#: untouched — it only decides who holds the challenger seats, which is exactly
#: what separates it from a loser's bracket.
SPECIAL_CHALLENGER_NAME = "Special Challengers"
#: The FINISH a bridge-round loser carries on the ledger (owner, 2026-08:
#: "Challengers" — CHALLENGE on the schedule chip); the event heading keeps the
#: full name, the way "Specials" is not "the State Specials Round".
SPECIAL_CHALLENGER_FINISH = "Challengers"

_RECOVERY_NAMES = {"super_regional": "Super Regionals", "semi_state": "Semi-State",
                   "divisional": DIVISIONAL_NAME,
                   "semi_conference": SEMI_CONFERENCE_NAME,
                   "conference": CONFERENCE_NAME,
                   "special_challenger": SPECIAL_CHALLENGER_NAME,
                   "state_special": STATE_SPECIAL_NAME}
_RECOVERY_UNITS = {"super_regional": "Super Regional", "semi_state": "Semi-State",
                   "divisional": "Division",
                   "semi_conference": SEMI_CONFERENCE_NAME,
                   "conference": "Conference",
                   "special_challenger": "Challenge",
                   "state_special": "State Special"}


def renumber_divisions(season: dict, start: int = 1) -> int:
    """Number this gender's Divisions and return the next number.

    ‼️ DIVISIONS ARE NUMBERED STATEWIDE, not within a classification (owner rule
    2027-08) — every other unit counts inside its own class ("Region IX" exists
    once per classification), but there is exactly one Group 1 in Jefferson
    each year. The sequence runs **girls first, then boys**, and **bottom-up by
    classification** (1A up to 9A), continuing across both, so 1A girls hold
    Group 1 and the highest number lands on 9A boys — "(9A) Group 11", if
    the state played that many that year. How many there are
    depends on how many Divisional duals the berths actually require, which
    varies by year, so the numbers are assigned here — once both genders are
    known — rather than inside the round that plays them.

    Idempotent: the number is always recomputed and overwritten, so re-running
    against a memoised season cannot double-count."""
    n = start
    # Bottom-up, DELIBERATELY: reversed(GROUPS) runs Group 2, Group 1,
    # then 1A up to 9A — the Great Basin pair (appended after 1A) leads the
    # sequence as the "newest/smallest" block. Any deterministic documented
    # order satisfies the invariant; this is the one we ship. (The unit label
    # "Division {n}" renders as ROMAN numerals on honours chips via
    # `world._unit_honour` — "Division XI" — so it stays visually distinct from
    # the GROUP names "Group 1"/"Group 2", which keep arabic digits.)
    for g in reversed(GROUPS):
        dv = ((season.get("groups") or {}).get(g) or {}).get("divisional") or {}
        for games in dv.get("rounds") or ():
            for gm in games:
                gm["unit"] = f"Division {n}"
                n += 1
    return n


def renumber_state_specials(season: dict, start: int = 1) -> int:
    """Number this gender's State Special duals and return the next number.

    ‼️ NUMBERED STATEWIDE FOR THE SEASON, STARTING AT 1 (owner rule 2026-08) — the
    Divisions' pattern exactly, and for the Divisions' reason: how many there are
    depends on how many berths the road failed to deliver that year (usually
    zero), so the numbers are assigned once both genders are known, never inside
    the round that plays them. Same order: girls first, then boys, classifications
    bottom-up, continuing across both.

    Idempotent: recomputed and overwritten, so a re-run cannot double-count."""
    n = start
    for g in reversed(GROUPS):
        sp = ((season.get("groups") or {}).get(g) or {}).get("state_special") or {}
        for games in sp.get("rounds") or ():
            for gm in games:
                gm["unit"] = f"State Special {n}"
                n += 1
    return n


def renumber_special_challenges(season: dict, start: int = 1) -> int:
    """Number this gender's Special Challenger duals and return the next number.

    The State Specials' pattern exactly (and the Divisions' before them): how many
    there are depends on how many eligible early exits each class produced that
    year, so the numbers are assigned statewide once both genders are known —
    girls first, then boys, classifications bottom-up, continuing across both.

    Idempotent: recomputed and overwritten, so a re-run cannot double-count."""
    n = start
    for g in reversed(GROUPS):
        ch = ((season.get("groups") or {}).get(g) or {}).get("special_challenger") or {}
        for games in ch.get("rounds") or ():
            for gm in games:
                gm["unit"] = f"Challenge {n}"
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
    for g in reversed(GROUPS):        # Group 2, Group 1, then 1A up to 9A
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

        Super Regionals   P Regional losers (even)       -> P/2 winners
        Semi-State        P/2 winners + Z Zonal losers   -> half  (berths)
        Divisionals       HALF its losers, HALF the SR losers -> half (berths)
        Semi-Conference   2B bodies                      -> B winners (no berths)
        Conference        Divisional losers + those B    -> half  (berths)

    ‼️ EQUAL BLOCKS (owner rule 2026-08). Every rung is the same size and every
    berth-bearing rung delivers the same number of berths, because the geometry
    does it for free: P/2 + Z is 16 at full size, its losers plus the P/2 Super
    Regional losers are 16 again, and the Conference takes twice whatever is
    still outstanding. A 32 field is therefore 8 Zonal + 8 Semi-State + 8
    Divisional + 8 Conference (the last through the Specials); a 40 field is
    8 + 8 + 8 + 16. Semi-State used to run on a `ceil(4*berths/3)` floor that
    made it the big round — 12 of a 32's 24 recovery berths — and the Super
    Regional losers were readmitted into IT rather than into the Divisionals.
    ‼️ The Divisional field is RESERVED HALF AND HALF between its two tiers
    (owner rule 2026-08): at a 24 field it holds only 8, so ranking them as one
    list let the Semi-State losers take every slot and cut the Super Regional
    losers out of the round completely.
    Bodies still enter at the Semi-Conference only: a walk back down the ladder
    through Ward, Sectional and Area losers, best TOSS within each tier. A body
    is a chance to PLAY, never a berth.
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
                      key=_atr_key(power))
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
    # ‼️ EQUAL RECOVERY BLOCKS (owner rule 2026-08) — see `recovery_shape`, which
    # projects this same arithmetic. Semi-State takes the Super Regional winners
    # and the Zonal losers and NOBODY ELSE; the Super Regional losers are
    # readmitted one rung later, into the Divisionals, so both rounds are the
    # same size and deliver the same block of berths. The old `ceil(4*berths/3)`
    # Semi-State floor (and the readmission window it sized) is gone with it.
    sr_pool = sorted(reg_losers, key=_atr_key(power))
    if len(sr_pool) % 2:                        # reservoir dry: the weakest sits out
        sr_pool = sr_pool[:-1]
    rng = random.Random(seed)
    sr_arc, sr_winners = _recovery_round(sr_pool, phase="super_regional", rng=rng)

    # Semi-State: the Super Regional winners and the Zonal losers, and nobody
    # else. Byeless, so an odd pool drops its weakest — which cannot happen at
    # full size (both halves are even by construction).
    won = {id(t) for t in sr_winners}
    sr_losers = sorted((t for t in sr_pool if id(t) not in won), key=_atr_key(power))
    ss_pool = sorted(list(sr_winners) + zon_losers, key=_atr_key(power))
    if len(ss_pool) % 2:
        ss_pool = ss_pool[:-1]
    ss_arc, ss_winners = _recovery_round(ss_pool, phase="semi_state", rng=rng)

    # Divisionals: the berths Semi-State could not fill, contested by the best
    # Semi-State losers. `L = 0` is legal and means the round did not convene.
    ss_won = {id(t) for t in ss_winners}
    ss_losers = sorted((t for t in ss_pool if id(t) not in ss_won),
                       key=_atr_key(power))
    # At most ONE block here; the Conference takes whatever is left (see
    # `recovery_shape`). 24 -> 4, 32 -> 8, 40 -> 8.
    dv_n = min(len(zonal_champs), max(0, berths - len(ss_winners)) // 2)
    # ‼️ THE DIVISIONAL FIELD IS SPLIT IN HALF, ONE BUCKET PER TIER (owner rule
    # 2026-08): the best `half` Semi-State losers and the best `half` Super
    # Regional losers, ranked inside each bucket and nothing else. No
    # weighting, no alternating.
    #
    # It was strict tier priority — all the Semi-State losers first — and that
    # is correct at 32 and 40, where both tiers are 8 and all 16 fit anyway,
    # but SILENTLY WRONG at 24: the field is 8 there, the 8 Semi-State losers
    # consumed every slot, and NO Super Regional loser ever reached the round.
    # That deleted a whole stage of the recovery ladder for them — a Regional
    # loser got Super Regionals and then nothing berth-bearing until the
    # Conference, while a Zonal loser got three. Reserved halves make the
    # promise true at every field size: a Regional loser gets Super Regionals
    # then the Divisionals, a Zonal loser Semi-State then the Divisionals.
    dv_seats = 2 * dv_n
    half = dv_seats // 2
    dv_pool = ss_losers[:half] + sr_losers[:half]
    if len(dv_pool) < dv_seats:
        # Thin-world DEGRADATION, not policy: a bucket that cannot fill its
        # half is topped up from the other so the round stays byeless. At
        # association size both buckets are exactly `half` and this is dead.
        spare = ss_losers[half:] + sr_losers[half:]
        dv_pool += spare[:dv_seats - len(dv_pool)]
    if len(dv_pool) % 2:
        dv_pool = dv_pool[:-1]
    # Orphans in tier order — whoever neither bucket took (`dv_pool` is no
    # longer a prefix of the ranking, so this cannot be a slice).
    _dv_taken = {id(t) for t in dv_pool}
    dv_orphans = [t for t in list(ss_losers) + list(sr_losers)
                  if id(t) not in _dv_taken]
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
    #   3. SUPER REGIONAL LOSERS the Divisionals did not take either (they are
    #      readmitted THERE now, not into Semi-State). Both are usually empty
    #      (at full size the Divisionals take every one of both) — but not
    #      always, and until now
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
    # `dv_orphans` is already Semi-State losers then Super Regional losers, in
    # tier order, so it IS tiers 2 and 3 in the right sequence.
    for tier in ([by_name[n] for n in district_champs if n in by_name],
                 dv_orphans,
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
    """‼️ RETIRED AND UNWIRED (owner rule 2026-08) — kept only because archived
    seasons were played under it and this docstring is what explains them.
    `run_season` now sends EVERY class through `_recovery`: the owner's pathway
    is the same rungs for every field size with only the counts changing, and
    the berths in this shape came out of SUPER REGIONALS while Semi-State
    awarded none, where the spec is 8 Zonal + 8 Semi-State + 4 Divisional + 4
    Specials. The dynamic ladder produces exactly that at a 24 field once the
    Divisionals are capped at one block. Do not re-wire this without the owner
    saying so; if you do, the district-champion priority split below is the
    thing it has that `_recovery` does not.

    The FIXED 24-team recovery/qualification shape — every 24-field class:
    2A and 1A (owner rule 2026-08 — the talent degrades at that level, so both
    smallest classes crown from 24 whatever their headcount; 2A returns to the
    shape it left in the 2033 realignment). Zonal champions are an automatic State berth here exactly as in
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
                       key=_atr_key(power))
    other_losers = sorted((t for t in reg_losers if t.school.name not in dc_names),
                          key=_atr_key(power))
    preferred = list(dc_losers[:8])
    if len(preferred) < 8:
        need = 8 - len(preferred)
        preferred += other_losers[:need]
        held_back = other_losers[need:]
    else:
        held_back = dc_losers[8:] + other_losers

    sr_pool = sorted(list(zon_losers) + preferred, key=_atr_key(power))
    sr_arc, sr_winners = _recovery_round(sr_pool, phase="super_regional", rng=rng)
    sr_won = {id(t) for t in sr_winners}
    sr_losers = [t for t in sr_pool if id(t) not in sr_won]

    ss_pool = sorted(list(held_back) + list(sr_losers), key=_atr_key(power))
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


def _reg_season_record(t: TeamSeason) -> tuple[int, int]:
    """Regular-season W-L ONLY (owner rule 2026-08): every dual played outside the
    `POSTSEASON` phases — district play, invitationals, showcases, the early
    window. The State Specials challenger ranking must not see postseason results:
    the round exists because Conference access was letting losing-record teams in,
    and a challenger's claim is what they did across the season, not how far the
    bracket happened to carry them."""
    w = sum(1 for e in t.schedule
            if e.get("phase") not in POSTSEASON and e.get("won"))
    l = sum(1 for e in t.schedule
            if e.get("phase") not in POSTSEASON and not e.get("won"))
    return w, l


def _challenger_key(power: dict):
    """The State Specials challenger ranking (owner rule 2026-08), best first:
    regular-season winning percentage, then regular-season wins, then ATR as the
    final tiebreak (with `_atr_key`'s name tiebreak keeping it reproducible)."""
    def key(t: TeamSeason):
        w, l = _reg_season_record(t)
        pct = w / (w + l) if w + l else 0.0
        return (-pct, -w) + _atr_key(power)(t)
    return key


def _select_challengers(by_name: dict, conference_winners: list,
                        qualified: set[str], power: dict) -> list:
    """The State Specials challenger side, best first: the `len(conference_winners)`
    best regular-season teams in the classification not already qualified and not
    Conference winners — the ENTIRE classification, wherever (or whether) they were
    eliminated (`_challenger_key`, owner rule 2026-08). Split out of
    `_state_specials_round` so the Special Challengers bridge round can contest the
    weakest seats before the Specials are played."""
    excluded = set(qualified) | {t.school.name for t in conference_winners}
    pool = [t for n, t in by_name.items() if n not in excluded]
    return sorted(pool, key=_challenger_key(power))[:len(conference_winners)]


#: Special Challenger seats contested per class (owner rule 2026-08): two by
#: default, FOUR in the 40-field classes — the wider valve is a property of
#: the big-field shape, not of any named class, and it has moved with the
#: shape once already: 3A/4A carried the 4 while they were the 40-field
#: holdouts (the largest, noisiest Specials bubble pools in the state),
#: dropped to the standard 2 when their fields came down to 32, and 8A/9A
#: inherited the 4 when they went back up to 40 in the same batch. A 40-field
#: Conference sends 14 to the Specials against the 32-shape's 6, so its
#: formula-selected tail is both longer and softer — that is what the two
#: extra contested seats answer. ‼️ A QUOTA, NOT A CAP (owner rule 2026-08,
#: "there should always be challenger specials"): the round convenes EVERY
#: season in every class, and only a class with fewer teams than seats (a tiny
#: test world) plays fewer.
#: Empty since 2026-09: 8A/9A left the 40 road for the Parastate structure (road
#: 32 + 16 at-large), and the wider valve is a property of the 40 road, not of the
#: class — it moved with the field every time and it moves with it now. The dict
#: stays the dispatch so the day a class goes back to a 40 road it is one entry.
CHALLENGE_SLOTS: dict[str, int] = {}
CHALLENGE_SLOTS_DEFAULT = 2


def _special_challengers_round(group: str, by_name: dict, challengers: list,
                               district_champs: list[str],
                               taken: set[str], power: dict, *,
                               seed: int) -> tuple[dict, list]:
    """‼️ THE SPECIAL CHALLENGERS — the bridge round in front of the State
    Specials, and IT ALWAYS CONVENES (owner rule 2026-08, "there should always
    be challenger specials"; `docs/AAR-jhsaa-special-challengers.md`).

    The Specials' challenger side is picked by FORMULA (`_select_challengers`:
    the best `len(conference_winners)` regular-season teams in the class), and
    its LAST few rows are the weakest claim in the whole event — weaker than
    the teams sitting just outside the cut, who are separated from them by a
    game or two of record and nothing else. So the round is exactly the
    owner's spec, with no conditions of its own:

        seats      = CHALLENGE_SLOTS[group]  (2; 4 in the 40-field classes)
        holders    = the `seats` WEAKEST selected challengers — the teams that
                     would otherwise walk into the Specials on the formula's
                     last rows
        contenders = the `seats` BEST teams outside the pool: the next names
                     down the SAME `_challenger_key` ranking that drew the
                     challenger cut (reg-season pct, wins, ATR), taken from
                     everyone not qualified and not already on the slate
        pairing    = best contender vs weakest holder, second vs second, … —
                     the pairing IS the seeding, the Specials' own rule. The
                     seat-holder hosts.
        winner     = holds that challenger seat into the State Specials.

    ‼️ NO ELIGIBILITY GATES (owner rule 2026-08, correcting two drafts of
    mine). A TOSS floor, a class-rank cut, a district-title gate and a
    sub-.500 exclusion were all tried and are all gone: "just leave it to
    anyone who qualifies … it's not as conditional as you kept gating it to
    be." The gates did real damage — the challenger cut already takes the best
    non-qualified teams by record, so the pool BEHIND it is the weak tail of
    the class by construction, and a sub-.500 exclusion therefore emptied the
    contender pool in exactly the classes where the ladder had absorbed most
    of the good teams. The round fired in some classifications and not others
    with nothing in the data to explain it. Ranking alone is the screen: the
    best teams outside the pool are, by definition, the ones worth the dual.

    It grants ZERO extra berths and changes no Conference winner's path — the
    Specials field is the same size with the same bids; only who holds the
    contested challenger seats is decided on court instead of by the formula's
    last few rows. Nobody churns through extra chances, and a team that wins
    the bridge still has to win its Special."""
    empty = {"field": [], "rounds": [[]], "survivors": [],
             "round_names": [SPECIAL_CHALLENGER_NAME], "head": []}
    if not challengers:
        return empty, challengers
    ch_names = {t.school.name for t in challengers}
    out_of_reach = set(taken) | ch_names
    slots = CHALLENGE_SLOTS.get(group, CHALLENGE_SLOTS_DEFAULT)
    # ‼️ DISTRICT CHAMPIONS GET FIRST CLAIM (owner rule 2026-08): a champion
    # that lost early is RECONSIDERED here ahead of the rest of the field.
    # A PRIORITY, not a gate — the tier is ordered by the same challenger
    # ranking as everyone else, and once the champions are exhausted the
    # seats go straight on down the list. Being in this pool already means
    # the champion did not qualify and holds no Specials seat, so "lost
    # early" needs no test of its own; adding one would be a gate again.
    champs = set(district_champs or ())
    ck = _challenger_key(power)
    # The next `slots` names down the ranking the challenger cut was drawn on
    # — literally the teams that just missed the Specials slate.
    eligible = sorted((t for nm, t in by_name.items() if nm not in out_of_reach),
                      key=lambda t: (t.school.name not in champs,) + ck(t))[:slots]
    n = min(slots, len(eligible), len(challengers))
    if n <= 0:
        return empty, challengers
    challengers = list(challengers)
    # ‼️ `field` IS THE SEED ORDER — `state._jh_seeds` labels a school by its
    # index here, so the entrants are stored strongest first: the defending
    # seat-holders in challenger-selection order, then the contenders in
    # theirs (both off `_challenger_key`, one continuous ranking).
    # Built from the PAIRING instead (first home = the weakest holder), the
    # schedule card labelled the weakest holder #1 and the best contender
    # #(n+1). Captured before the duals play, since a loser leaves the list.
    field = ([challengers[len(challengers) - n + i].school.name
              for i in range(n)]
             + [t.school.name for t in eligible[:n]])
    rng = random.Random(seed)
    games = []
    for i in range(n):
        seat = len(challengers) - 1 - i          # weakest seat first
        holder, contender = challengers[seat], eligible[i]
        res = play_dual(holder, contender, seed=rng.randrange(1 << 30),
                        phase="special_challenger")
        win = holder if res.winner == 0 else contender
        games.append({"home": holder.school.name, "away": contender.school.name,
                      "home_points": res.home_points,
                      "away_points": res.away_points,
                      "winner": win.school.name,
                      "unit": f"{_RECOVERY_UNITS['special_challenger']} {i + 1}"})
        challengers[seat] = win
    return ({"field": field, "rounds": [games],
             "survivors": [g["winner"] for g in games],
             "round_names": [SPECIAL_CHALLENGER_NAME], "head": []}, challengers)


def _state_specials_round(group: str, conference_winners: list,
                          challengers: list, power: dict, *,
                          seed: int) -> tuple[dict, list]:
    """‼️ THE REQUIRED FINAL ROUND OF THE ROAD (owner rule 2026-08). Conference
    winners do NOT qualify for State — they advance here and must beat a
    challenger for the berth. The rule, exactly:

        specials_bids = len(conference_winners)
        challengers   = the `specials_bids` best REGULAR-SEASON teams in the
                        classification not already qualified and not Conference
                        winners — drawn from the ENTIRE classification, wherever
                        (or whether) they were eliminated (`_select_challengers`;
                        the weakest seats may since have been contested and won
                        on court in the Special Challengers bridge round, which
                        is why the list arrives as a PARAMETER here)
        one dual per bid; every winner qualifies; every loser is eliminated

    Bids derive from the actual Conference winners, so the arithmetic closes any
    field size by construction: the 32-shape's 8 Zonal + 12 Semi-State + 6
    Divisional + 6 Specials winners = 32; the 40's Conference sends 14; the fixed
    24's sends 4. It knows nothing about 24, 32 or 40.

    Pairing is SEEDED, best-vs-worst (owner rule 2026-08): the best-ranked
    challenger plays the weakest Conference winner by ATR. The Conference winner
    hosts. ‼️ Deliberately NO rematch repair here — the pairing is the seeding,
    and a Conference winner drawing the strong team it beat last round is the
    point of the exercise, not a defect to rotate away.

    A challenger pool smaller than the bids (a tiny test world — statewide it is
    every non-qualified team, hundreds deep) direct-admits the unpaired
    Conference winners with a loud warning: a short State field is the one
    outcome worse than an uncontested berth."""
    empty = {"field": [], "rounds": [[]], "survivors": [],
             "round_names": [STATE_SPECIAL_NAME], "head": []}
    cw = list(conference_winners)
    if not cw:
        return empty, []
    challengers = list(challengers)[:len(cw)]
    # weakest Conference winner first, so zip pairs them with the BEST challenger
    cw_weak_first = sorted(cw, key=_atr_key(power))[::-1]
    head = cw_weak_first[len(challengers):]        # unpaired: dry pool only
    if head:
        log.warning("JHSAA %s State Specials short of challengers: %d of %d "
                    "Conference winner(s) admitted unopposed", group,
                    len(head), len(cw))
    rng = random.Random(seed)
    games, winners = [], []
    for n, (ch, w_) in enumerate(zip(challengers, cw_weak_first)):
        res = play_dual(w_, ch, seed=rng.randrange(1 << 30),
                        phase="state_special")
        win = w_ if res.winner == 0 else ch
        games.append({"home": w_.school.name, "away": ch.school.name,
                      "home_points": res.home_points,
                      "away_points": res.away_points,
                      "winner": win.school.name,
                      "unit": f"{_RECOVERY_UNITS['state_special']} {n + 1}"})
        winners.append(win)
    field = [t.school.name for t in cw_weak_first] \
        + [t.school.name for t in challengers]
    return ({"field": field, "rounds": [games],
             "survivors": [t.school.name for t in head]
             + [t.school.name for t in winners],
             "round_names": [STATE_SPECIAL_NAME],
             "head": [t.school.name for t in head]}, head + winners)


def _state_specials(group: str, by_name: dict, stages: list[dict],
                    taken: set[str], power: dict, *,
                    seed: int) -> tuple[dict, list]:
    """‼️ THE EMERGENCY RECONCILIATION (owner rule 2026-08), field-size agnostic.

    Since the Conference-winners rule, the PLAYED State Specials round is
    `_state_specials_round` above; this remains behind it for the one case the
    spec keeps it for — the completed round still leaving the State field short
    (the Conference itself under-delivered winners, or a tiny world ran dry).

    The normal Road to State should fill the field; this round exists only when it
    does not. The rule is exactly the owner's:

        missing = STATE_FIELD[group] - qualified
        if missing > 0:
            take 2 × missing eligible eliminated teams
            play `missing` State Specials duals
            the winners take the missing berths

    It knows NOTHING about 24, 32 or 40 — 28-of-32 is 8 teams playing for 4 bids,
    35-of-40 is 10 for 5, and a future 64 would reconcile the same way. State never
    has to care why a team qualified, and `run_state` never again turns missing
    qualifiers into byes (the fault that shipped: a 9A bracket with four teams
    advancing unplayed round after round — the ladder had delivered 20 of its 24
    earned berths and the draw padded the difference).

    SELECTION walks the postseason BACKWARD by latest elimination — Conference
    losers first, then Semi-Conference, and only then the earlier rounds — with ATR
    ordering teams WITHIN a tier, never across one (`stages` is ladder order,
    shallowest first, and a team's tier is the deepest stage it appeared in). ATR is
    the recovery ladder's own body-ranking rule: this decides who gets one final
    chance to play for a berth, not a seed.

    ‼️ THE POOL CAN GENUINELY RUN DRY only when the classification has fewer
    postseason teams than the field wants (a broken fixture, or a two-district test
    world). Then the best `2·missing − pool` enter DIRECTLY with a loud warning —
    the `sc_head` idiom — because a short State field is the one outcome worse than
    an unearned entry. At full association size the pool is always deep enough and
    the head is empty."""
    target = state_field_size(group)
    missing = target - len(taken)
    empty = {"field": [], "rounds": [[]], "survivors": [],
             "round_names": [STATE_SPECIAL_NAME]}
    if missing <= 0:
        return empty, []
    # ‼️ FIRING AT ALL IS A SIGNAL, so it logs every time (owner, 2026-08): the
    # Conference is supposed to fill the field, and in a healthy class the
    # arithmetic cannot come up short. Once every several years — membership,
    # parity and qualification lining up badly — is the round doing its job;
    # firing regularly means an upstream rung is losing berths (a candidate pool
    # built too small, an eligibility walk skipping a loser tier, a parity trim
    # eating a bid) and THAT is what needs diagnosing, not this.
    log.warning("JHSAA %s road delivered %d of %d — State Specials convene for "
                "%d berth(s)", group, len(taken), target, missing)
    depth: dict[str, int] = {}
    for i, arc in enumerate(stages):
        for rd in (arc or {}).get("rounds") or ():
            for gm in rd:
                for nm in (gm.get("home"), gm.get("away")):
                    if nm and nm in by_name and nm not in taken:
                        depth[nm] = i          # ladder order: later stage wins
    ranked = sorted(depth, key=lambda nm: (-depth[nm],) + _atr_key(power)(by_name[nm]))
    pool = [by_name[nm] for nm in ranked[:2 * missing]]
    # d direct entries leave pool-d playing for missing-d bids: d = 2·missing − pool.
    direct = max(0, 2 * missing - len(pool))
    head, playing = pool[:direct], pool[direct:]
    if head:
        log.warning("JHSAA %s State Specials short of bodies: %d of %d berths "
                    "granted directly (pool %d)", group, len(head), missing,
                    len(pool))
    rng = random.Random(seed)
    if len(playing) >= 2:
        arc, winners = _recovery_round(playing, phase="state_special", rng=rng)
    else:
        arc, winners = dict(empty), []
        head += playing                        # a lone leftover cannot pair
    arc["field"] = [t.school.name for t in head] + arc["field"]
    arc["survivors"] = [t.school.name for t in head] + arc["survivors"]
    arc["head"] = [t.school.name for t in head]
    return arc, head + winners


def run_state(field: list[TeamSeason], *, seed: int, champions: int = 8) -> dict:
    """The State Tournament: a fresh seeded draw (24 / 32 / 40 teams by class,
    handed over in SEED ORDER — `state_seed_order`: the eight bye lines first,
    then everyone else on the seeding ATR) played to a champion.

    `champions` is how many entrants lead the field on the bye lines (the caller's
    `STATE_BYES`; it was the Zonal-champion count before the Epiregional, owner
    rule 2026-09) — the draw's bye budget, and the count that decides
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

    # ‼️ A FIELD THAT FITS ONE DRAW PLAYS ONE DRAW. The qualifying expansion exists
    # only because a 40 will not fit a bracket whose byes are the champions'
    # privilege — it is not a shape to reach for whenever the field is not exactly
    # 24. The test used to be `size - len(field) != c`, which is TRUE of a 32-team
    # field (a bracket exactly full, zero byes) and of every short field, so five
    # classifications and every under-filled draw were sent through a Qualifiers
    # Round they should never have played.
    #
    # A 32 is straightforward and needs nothing added: **32 → 16 → 8 → 4 → 2 with
    # the Zonal champions as the top eight SEEDS** (owner, 2026-08 — "32 can happen
    # with no byes… people just play"). The champions' privilege is a SEEDING
    # guarantee; the eight byes of a 24-field are a consequence of that field's
    # shape, not the rule itself (`test_zonal_champions_are_the_top_seeds_byes_or_not`
    # pins both shapes).
    #
    # So the condition is the rule stated directly: expand only when the padding
    # byes would OUTNUMBER the champions, i.e. when they could not all be the
    # champions' own. 24 → 8 byes, plain. 32 → 0 byes, plain. 28 → 4 byes to the top
    # four seeds, plain. 40 → 24 byes in a 64 bracket, and only then does the
    # Qualifiers Round earn its place.
    if len(field) > 2 * c and size - len(field) > c:
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


def run_state_parastate(seeds: list[TeamSeason], *, byes: int, seed: int) -> dict:
    """The Parastate State event for `ATLARGE_GROUPS` (owner spec 2026-09,
    resized 2026-09 — 48 for 8A/9A/Group 1, 40 for 7A).

    `seeds` is the WHOLE field in seed order: the road's 32 first (1-8 the
    earned bye lines — Epiregional winners, Epiregional losers, then the best
    non-champion road qualifiers, all ordered by the seeding ATR — then the rest
    of the road by ATR), and the committee's at-larges after them by Borda. An
    at-large can NEVER be seeded above a road qualifier: the floor is structural
    (they arrive after the 32 road seeds in this list), not a sort key.

    `byes` is how many top seeds sit the Parastate out — `road − bids`, so the
    Parastate is exactly the `2 × bids` lowest seeds: a 48 (16 bids) byes 1-16
    and plays 17v48 … 32v33; a 40 (8 bids) byes 1-24 and plays 25v40 … 32v33.
    Pairs are pinned high-low, the higher seed hosts. Winners RETAIN their
    original seed; they and the byes enter a fresh 32 draw played by `run_state`
    itself (`champions=byes` on a full 32 lands on the plain single-draw
    branch), so the Round of 32 onward is the association's ordinary seeded
    bracket. The Parastate is named in `round_names`, which is exactly what
    makes `state._jh_split_state` draw it as its own tree — there is no bracket
    path from a Parastate slot to a main-draw slot.

    Short fields (tiny worlds, a road that ran dry) degrade generically: the
    first `byes` seeds bye, the rest fold high-low, an odd team advances
    unplayed. The table shapes are the only ones the association plays at full
    size."""
    rng = random.Random(seed)
    n_byes = max(0, min(byes, len(seeds)))
    byes_, rest = list(seeds[:n_byes]), list(seeds[n_byes:])
    para_games = []
    alive = set()
    for i in range(len(rest) // 2):
        a, b = rest[i], rest[len(rest) - 1 - i]
        res = play_dual(a, b, seed=rng.randrange(1 << 30), phase="state")
        win = a if res.winner == 0 else b
        para_games.append({"home": a.school.name, "away": b.school.name,
                           "home_points": res.home_points,
                           "away_points": res.away_points,
                           "winner": win.school.name})
        alive.add(win.school.name)
    if len(rest) % 2:                              # degraded odd field only
        alive.add(rest[len(rest) // 2].school.name)
    survivors = byes_ + [t for t in rest if t.school.name in alive]
    inner = run_state(survivors, champions=max(1, len(byes_)),
                      seed=rng.randrange(1 << 30))
    rounds = ([para_games] if para_games else []) + inner["rounds"]
    names = ([PARASTATE_NAME] if para_games else []) + list(inner["round_names"])
    return {"champion": inner["champion"], "rounds": rounds,
            "round_names": names,
            "field": [t.school.name for t in seeds]}


def run_state_48(seeds: list[TeamSeason], *, seed: int) -> dict:
    """The original 48 shape (16 bids, seeds 1-16 bye) — `run_state_parastate`
    at `byes=16`. Kept as the name the 2026-09 spec and its AAR use."""
    return run_state_parastate(seeds, byes=16, seed=seed)


def run_toc(champions: list[TeamSeason], *, seed: int) -> dict:
    """The TOURNAMENT OF CHAMPIONS — one dual-team champion for all of Jefferson.

    ONE champion per classification and nobody else — twelve teams now that every
    classification, the Great Basin groups included, crowns separately. The field
    is not a `FIELD` size and never has been: it is exactly
    `len(GROUPS)`, and it grows or shrinks only when the association adds or merges a
    championship. (`FIELD` is the STATE tournament's bracket size per classification and
    has nothing to do with this event.)

    Seeded on the TOSS Power Index they finished the regular season with (`t.power`,
    already stamped by `play_regular_season`), NOT on classification: a 4A champion that
    rated above the 6A one is the higher seed, which is the whole reason the event is
    interesting.

    ‼️ A REAL FIXED BRACKET ON STRICT SEED LINES (owner rule 2026-08 — "it's not
    complicated"). The field goes onto the standard seed-line slots of the next
    power of two, byes fall to the top seeds because their round-one opponents
    (the highest slot numbers) do not exist, and the bracket is then FIXED: a
    winner takes the beaten seed's LINE, and no round is ever re-paired ("if 11
    beats 6, they take the 6-seed line"). So 12 teams is exactly 5v12 · 6v11 ·
    7v10 · 8v9 with seeds 1-4 sitting; a 14 would add 4v13 and 3v14; a 15 would
    put 2 against 15; a 9 is the lone 8v9 game whose winner meets the 1 seed —
    every one of those is the SAME rule at a different count, never a special
    case. This replaced a two-tier "cut to eight, then cut to four" that
    re-paired the survivors best-vs-worst between rounds — reseeding by another
    name, which no real dual-team bracket does.

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

    # The standard seed-line order: seed s meets seed (m+1-s) in round one, and
    # the quarters/halves nest so 1 and 2 can only meet in the final. For 16:
    # (1,16)(8,9)(4,13)(5,12) | (2,15)(7,10)(3,14)(6,11).
    order = [1]
    while len(order) < len(field):
        m = 2 * len(order)
        order = [s for a in order for s in (a, m + 1 - a)]
    slots: list[TeamSeason | None] = [
        field[s - 1] if s <= len(field) else None for s in order]
    rounds: list[list[dict]] = []
    while len(slots) > 1:
        games, nxt = [], []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None or b is None:
                nxt.append(a or b)      # a missing slot is the top seed's bye
                continue
            w, gm = play(a, b)
            games.append(gm)
            nxt.append(w)
        if games:
            rounds.append(games)
        slots = nxt
    return {"champion": slots[0].school.name if slots else None,
            "rounds": rounds, "field": [t.school.name for t in field],
            "seeds": {t.school.name: i + 1 for i, t in enumerate(field)}}


# 9A=0 … 1A=8, so |i-j| = classes apart on the enrollment ladder. The Great Basin
# groups (2046, retiered three ways by the Heritage Valley migration) are NOT ladder
# rungs — enumerating GROUPS raw put Group 1 at 9, "one apart" from 1A, i.e. a
# 2,500-enrollment school gated onto 100-student opponents. They get FRACTIONAL
# positions on the same scale instead, chosen from their enrollment midpoints so the
# existing |i-j| <= 1 gate does the right thing: Group 1 (1066-2556, mid ≈ 7A/6A) at
# 2.5 pairs with 7A, 6A and Group 2; Group 2 (407-1059, mid ≈ 5A/4A) at 3.5 pairs
# with 6A, 5A, 4A and its neighbours; Group 3 (57-396, mid ≈ 2A/1A) at 4.5 pairs with
# 5A, 4A and Group 2. Each pair of neighbours is exactly 1.0 apart, so Group 1/2/3
# can always meet each other non-district — though geography (their own three
# areas — Silver Basin/Snake River Plain/Bear River Country, the SAME ground the
# original Great Basin counties stood on) makes that the common case regardless.
_GROUP_IX = {g: i for i, g in enumerate(LADDER_GROUPS)}
_GROUP_IX["Group 1"] = 2.5
_GROUP_IX["Group 2"] = 3.5
_GROUP_IX["Group 3"] = 4.5

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


# --- CROSS-TOWN RIVALRIES (owner rule 2026-09) -------------------------------
#
# ‼️ A CROSS-TOWN RIVALRY IS AN ANNUAL FIXTURE, NOT A PREFERENCE. The non-district
# matcher above draws on geography and talent, which gets the AVERAGE card right and
# the rivalries wrong: it is a weighted draw over a shortlist, so the three Cherry
# Hill schools met in some seasons and not others, and Port Meridian's nine programs
# — one town, nine tennis teams, six different leagues — mostly never played each
# other at all. Every real association has the opposite property: whatever else moves,
# the crosstown game is on the schedule every year. Owner: "none of the cherry hill
# schools or port meridian schools play each other much/enough and that's not
# realistic."
#
# So the pairs are CODIFIED — derived once from the school list, then scheduled
# unconditionally ahead of the ordinary draw — and a rivalry dual is an ordinary
# non-district dual in every other respect (`phase="regular"`, counts to the record,
# to TOSS and to the allowance; see `play_regular_season`).
#
# ‼️ IT OUTRANKS THE CLASSIFICATION GATE, deliberately. `_nondistrict_pairs` refuses a
# pairing more than one class apart, which is right for a draw over the whole state and
# wrong here: Port Meridian's town rivals span 9A to 3A, and a rivalry is a fact about
# two programs rather than about their enrollments — the same doctrine that already
# makes `import_jhsaa.RIVALRIES` outrank reclassification, league assignment and
# playing up. The CAP is what keeps that from producing absurdities: each program takes
# the `RIVALS_PER_PROGRAM` nearest town programs by class, so a 9A meets the 3A across
# town only in a town that holds nothing closer.
RIVALS_PER_PROGRAM = 2

# The kill switch and the FIRST diagnostic (`SHOWCASE_ENABLED`'s idiom): checked at the
# top of `_rivalry_pairs`, so off it returns before touching a team and the season runs
# exactly the pre-feature code. The fixtures add ~260 duals to a gender's ~5,100 (~5%)
# and take none of them out of the allowance, so if a rung is slow with this off, these
# were never the cause.
RIVALRIES_ENABLED = True

# ‼️ THE GATE IS RELAXED, NOT REMOVED. `_nondistrict_pairs` refuses a pairing more than
# ONE class apart; a rivalry reaches three, which is what a town actually looks like
# (Port Meridian's two 3A privates take the 5A private across town, two classes off)
# and still refuses the pairing nobody would schedule twice. Measured before it
# existed: the cap alone left the STRAGGLERS of a big town to each other, so
# Valderra's 9A drew the 1A across an 18-school city — the two programs nothing closer
# had room for, which is the opposite of a rivalry. A program with nothing in range
# simply has no town rival; that is a real answer, not a gap to fill.
# `RIVAL_OVERRIDES` is exempt — an owner-declared rivalry answers to no gate.
RIVAL_MAX_GAP = 3

# Hand-authored pairs, always rivals whatever the derivation would have said — the
# owner's override, the `OWNER_EDICTS` idiom. They are placed FIRST and take a seat
# like any other rivalry: a named pair is the town's primary rivalry, not a third one
# bolted onto two derived ones. Both names must be sponsoring programs this season or
# the entry is simply inert (a school can stop fielding a team).
#
# ‼️ EVERY `import_jhsaa.RIVALRIES` PAIR MUST APPEAR HERE. The two tables state the
# same fact for two different mechanisms — that one keeps a pair in the same
# CLASSIFICATION at import, this one puts them on the schedule every season — and the
# app cannot read `scripts/`, so they are separate lists and the agreement is asserted
# instead (`tests/test_jhsaa_rivalries.py`). Without the entry the derivation quietly
# breaks the named pair whenever a third program in town has a better claim: Alameda
# and Condotti Vanguard Academy are both Ashbury 7A, so on class alone Alameda takes
# the seat and the association's oldest rivalry stops being played.
RIVAL_OVERRIDES: list[tuple[str, str]] = [
    ("Condotti Vanguard Academy", "Romero-Finniski"),
    # The three-campus towns are full round robins (owner rule 2026-09,
    # "they are all rivals with each other") — a triangle gives each member
    # exactly `RIVALS_PER_PROGRAM` seats. Deliberately NOT in
    # `import_jhsaa.RIVALRIES`: these campuses sit in different
    # classifications on purpose, and that table would weld them into one.
    # Both Norths sponsor no tennis this season, so their pairs are inert
    # until one fields a team again — then the triangle plays by itself.
    ("Port Meridian Central", "Port Meridian North"),
    ("Port Meridian Central", "Port Meridian South"),
    ("Port Meridian North", "Port Meridian South"),
    ("Cherry Hill East", "Cherry Hill North"),
    ("Cherry Hill East", "Cherry Hill South"),
    ("Cherry Hill North", "Cherry Hill South"),
    # …and the two returned Norths are rivals with each other (owner rule
    # 2026-09: both play 2A now — see scripts/jhsaa_norths_to_2a.py). An
    # override is city-blind, so the cross-town pair needs no machinery.
    ("Port Meridian North", "Cherry Hill North"),
    # The Central triangle consumed the seats that used to pair Westside
    # Christian into town, leaving the metro's other 9A with nobody in
    # range and room — so the two religious schools hold each other's
    # fixture, which is the rivalry that town would actually have.
    ("Holy Cross", "Westside Christian"),
]

#: Directional and ordinal words a town hangs on ONE stem to name its several high
#: schools — "Cherry Hill East" / "Cherry Hill North" / "Cherry Hill South". Sharing a
#: stem is the strongest crosstown signal there is (it is the same school district
#: naming its campuses), so stem-mates take each other before anything else in town.
_STEM_WORDS = {"north", "south", "east", "west", "central", "northeast", "northwest",
               "southeast", "southwest", "heights", "valley", "park", "hills"}


def _name_stem(name: str) -> str:
    """The shared stem of a compass-named campus, or "" for a name that has none.
    "Cherry Hill East" -> "cherry hill"; "Bell" -> "" (a bare name is nobody's stem,
    and treating it as one would make every one-word school in town a stem-mate)."""
    parts = name.split()
    if len(parts) < 2 or parts[-1].lower() not in _STEM_WORDS:
        return ""
    return " ".join(parts[:-1]).lower()


def _rival_priority(a: School, b: School) -> tuple:
    """How strong a claim these two have on each other's rivalry seats, best first:
    a shared campus stem, then the same locality (the settlement inside the metro —
    two programs in one CDP are neighbours in a way two ends of Port Veles are not),
    then the nearest classification, then the names so the draw is stable."""
    stem = _name_stem(a.name)
    return (0 if stem and stem == _name_stem(b.name) else 1,
            0 if a.locality and a.locality == b.locality else 1,
            abs(_GROUP_IX[a.group] - _GROUP_IX[b.group]),
            *sorted((a.name, b.name)))


def rival_map(schools: list[School]) -> dict[str, frozenset[str]]:
    """{school name: the programs it plays every year}, derived from the town.

    Candidates are the other SPONSORING programs in the same city — the town is the
    city and not the locality, so a metro's core-city schools and its CDP schools are
    one pool with locality-mates merely preferred (`_rival_priority`). Pairs are then
    accepted best-claim-first while both sides are under `RIVALS_PER_PROGRAM`, which is
    what stops Port Veles's 41 programs from becoming an 820-dual round robin.

    ‼️ LEAGUE-MATES COUNT AGAINST THE CAP BUT ARE NOT SCHEDULED HERE. A town rival
    already in your league is your rivalry — you play it home and away — so it takes a
    seat like any other; `play_regular_season` skips it because a double round robin
    has already scheduled it, not because it is not a rivalry. Dropping league-mates
    from the derivation instead would hand a program a THIRD-nearest town rival to make
    up the number, which is a rivalry nobody in that town would recognise."""
    by_city: dict[str, list[School]] = {}
    for s in schools:
        by_city.setdefault(s.city, []).append(s)
    out: dict[str, set[str]] = {s.name: set() for s in schools}
    live = set(out)
    for a, b in RIVAL_OVERRIDES:            # inert for a program not fielding a team
        if a in live and b in live:
            out[a].add(b)
            out[b].add(a)
    cands = []
    for town in by_city.values():
        town = sorted(town, key=lambda s: s.name)
        for i, a in enumerate(town):
            for b in town[i + 1:]:
                if abs(_GROUP_IX[a.group] - _GROUP_IX[b.group]) > RIVAL_MAX_GAP:
                    continue
                cands.append((_rival_priority(a, b), a.name, b.name))
    for _p, a, b in sorted(cands):
        if len(out[a]) < RIVALS_PER_PROGRAM and len(out[b]) < RIVALS_PER_PROGRAM:
            out[a].add(b)
            out[b].add(a)
    return {k: frozenset(v) for k, v in out.items()}


def are_rivals(a: str, b: str, rivals: dict[str, frozenset[str]]) -> bool:
    """Is this dual a codified rivalry? A pure question about the school list, which
    is why no rivalry column was added to `world_jhsaa_dual`: the answer is a
    PROJECTION of a layer the archive already has, so a card reads the same for a
    season played before this existed and for one played after."""
    return b in rivals.get(a, ())


def _rivalry_pairs(teams: list[TeamSeason], year: int,
                   played: dict[int, set[str]]) -> list[tuple]:
    """RESERVE this season's rivalry duals, in a stable order — it does not play them.
    Marking `played` here is what takes each pair off the ordinary matcher's board, so
    this must run BEFORE the first draw of the season even though the duals themselves
    are played in the mid-season window (see `play_regular_season`). Skips a pair
    sharing a league (the double round robin plays it twice) and one that has somehow
    already met. Never touches `owed`: the fixture is annual and
    is not drawn from the allowance — it is COUNTED against it afterwards, by the
    `spent` fold in `play_regular_season`, so a program's total card is unchanged.

    ‼️ THE VENUE ALTERNATES ON THE YEAR. `play_dual` makes its first argument the home
    side and `home_court` gives the host a real lift, so a fixed order would hand one
    school of every rivalry the home advantage for as long as the save runs — the one
    thing a genuine annual series never does."""
    if not RIVALRIES_ENABLED:
        return []
    rivals = rival_map([t.school for t in teams])
    by_name = {t.school.name: t for t in teams}
    pairs = []
    for t in sorted(teams, key=lambda t: t.school.name):
        for other in sorted(rivals.get(t.school.name, ())):
            o = by_name.get(other)
            if o is None or o.school.name < t.school.name:
                continue                    # each pair once, from the earlier name
            if (t.school.group, t.school.district) == (o.school.group, o.school.district):
                continue                    # league-mates: already home and away
            if o.school.name in played[id(t)]:
                continue                    # the early window got there first
            pairs.append((o, t) if year % 2 else (t, o))
            for x, y in ((t, o), (o, t)):
                played[id(x)].add(y.school.name)
    return pairs


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

    # ‼️ THE RIVALRIES ARE RESERVED BEFORE THE FIRST DRAW, AND PLAYED LATER. Deriving
    # them here marks them in `played`, so the early matcher cannot take one — it is
    # allowed to (a town rival inside the ±1 gate is an ordinary candidate to it), and
    # when it did, that random draw BECAME the annual fixture and quietly lost both
    # things the fixture is for: it was played at the early window's 5S/2D shape rather
    # than the league's, and the host was whichever side the matcher happened to put
    # first, so the venue could stay with one school two seasons running. A fixture
    # that the draw can pre-empt is a fixture only when the draw does not.
    rival_pairs = _rivalry_pairs(every_team, year, played)
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

    # --- the CROSS-TOWN RIVALRIES: the annual fixtures, played first in the window ---
    # Reserved above, before any draw; played HERE, after pass 1, because that is where
    # the calendar has the dates and because the fixture must be an ordinary 3S/4D
    # league-shape dual — the fixture is codified, the match is not special. Ahead of
    # the window's own draw so the matcher cannot rematch a pair that has just played.
    # Not drawn from `owed`: the `spent` fold at the tune-up counts them, so a rivalry
    # does not lengthen anybody's card.
    _play_pairs(rival_pairs, xrng)

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


def _jv_wildcards(jv_arc: dict, by_group: dict) -> dict:
    """The JV champions, as varsity No. 3 wild cards (owner rule 2026-09).

    ‼️ THE JV WINNER GETS A SHOT AT THE VARSITY EVENT, IN THE SAME YEAR. The JV
    Singles champion enters that program's classification No. 3 SINGLES draw and the
    JV Doubles champions their No. 3 DOUBLES draw — the flights with the room for it
    (a No. 3 field is 82-107 in a 128 bracket, so 21-46 seats stand open) and the
    right level for a player who was outside their own school's top nine.

    ‼️ IT IS A SECOND ENTRY FROM THAT SCHOOL IN THAT FLIGHT, which the varsity event
    has never had — its whole selection rule is one holder per school per flight. The
    wild card is APPENDED to the selected field rather than selected into it (see
    `run_flight`), so the rule itself is untouched, and the draw is asked to keep the
    two apart. `Entry.key` carries the pids, so they cannot collapse to one index.

    The event is CLASSLESS but the varsity flights are not, so each champion enters
    the draw of their OWN school's classification — which is why this needs the
    school-to-group map rather than just the archive.
    """
    from . import jhsaa_jv_individuals as jvi
    from .jhsaa_individuals import Entry
    group_of = {t.school.name: g
                for g, dists in by_group.items()
                for ts in dists.values() for t in ts}
    out: dict = {}
    for bracket, flight in ((jvi.SINGLES, "S3"), (jvi.DOUBLES, "D3")):
        e = (jv_arc.get("champions") or {}).get(bracket)
        if e is None or group_of.get(e.school) is None:
            continue
        out.setdefault(group_of[e.school], {}).setdefault(flight, []).append(
            Entry(school=e.school, players=e.players, engine=e.engine,
                  rating=e.rating, flight=flight, district=e.district))
    return out


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
    # ‼️ THE JV INDIVIDUAL TOURNAMENTS RUN FIRST, AND PRESEASON (owner rule
    # 2026-09). They used to sit after the JV season, because `jv_pool` reads
    # `_order` and that ladder wants results in it — but the owner wants the JV
    # champion wild-carded into the varsity No. 3 draw IN THE SAME YEAR, and the
    # varsity flights are preseason by design (selecting on ability is only honest
    # before any berth could have been earned on court). A champion crowned after
    # the No. 3 draw was already played and archived can never enter it.
    #
    # So the JV event moves to where its output can be used. Preseason `_order`
    # has no results to read and IS ability order — which is the same basis the
    # varsity flights select on, so this is the honest cut rather than a weaker
    # one. The JV SEASON stays where it is, after the regular season.
    from .jhsaa_jv_individuals import run_jv_individuals as _run_jv_individuals
    out["jv_individuals"] = _run_jv_individuals(by_group, gender, year,
                                                seed=seed)
    from .jhsaa_individuals import run_preseason as _run_individuals
    out["individuals"] = _run_individuals(
        by_group, gender, year, seed=seed,
        wildcards=_jv_wildcards(out["jv_individuals"], by_group))
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
    # ‼️ THE JV TEAM STATE TOURNAMENT — a PILOT from `JV_STATE_FROM` (JHSAA 2068).
    # Gated on the season year exactly as the 1A 2S/3D postseason pilot is gated on
    # its class: a world that has already archived earlier seasons must keep reading
    # them as the years they were, and a pilot that silently back-applied itself
    # would rewrite what those seasons were.
    #
    # It runs AFTER the JV season and reads only its results, so it cannot disturb
    # anything above: `JVTeam` has no `records`/`matches` to reach, and these duals
    # are archived at JV `level` under their own phase.
    if year >= JV_STATE_FROM:
        from .jhsaa_jv_state import run_jv_state
        # ‼️ blake2s, never `hash()` — Python salts str hashes per process and this
        # event is ARCHIVED, so "the same season" has to survive a restart.
        jvs_seed = int(hashlib.blake2s(
            f"{salt}|jvstate|{gender}|{year}".encode(), digest_size=8).hexdigest(), 16)
        out["jv_state"] = run_jv_state(out["jv"], gender=gender, year=year,
                                       seed=jvs_seed % (1 << 30))
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
    epiregionals: dict[str, dict] = {}
    epi_winners: dict[str, list] = {}
    for group in GROUPS:
        standings = by_group[group]
        protected, entrants = sectional_field(group, standings, power)
        protecteds[group] = [t.school.name for t in protected]
        district_champs[group] = [ts[0].school.name
                                  for ts in standings.values() if ts]
        gseed = seed + hash(group) % 9973
        sectionals[group], ward_field = run_sectional(entrants, WARD_FIELD,
                                                       seed=gseed)
        ward_field = sorted(ward_field, key=_atr_key(power))
        wards[group], ward_champs = run_rounds(ward_field, ("ward",),
                                               seed=gseed + 4111)
        reg_field = sorted(protected + ward_champs, key=_atr_key(power))
        prestates[group], zonal_champs[group] = run_rounds(
            reg_field, ("regional", "zonal"), seed=gseed + 8219)
        # ‼️ THE EPIREGIONAL — the Zonal champions' play-in (owner rule 2026-09),
        # straight after the Zonals and BEFORE the recovery rounds, so its duals
        # are in the pre-state results graph the recovery fields are seeded on.
        # Placement only: all eight stay in the field, the four winners hold the
        # first four bye lines (`state_seed_order`). Seeded on blake2s — these
        # duals are archived and their units honoured, and `hash(group)` is the
        # per-process wart this module is told not to copy.
        epi_seed = seed + int.from_bytes(hashlib.blake2s(
            f"jh-epiregional|{group}".encode(), digest_size=4).digest(), "big")
        epiregionals[group], epi_winners[group], _ = run_epiregional(
            zonal_champs[group], power, prestates[group],
            epiregional_names(gender, year, group, salt), seed=epi_seed)
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
        # ‼️ ONE LADDER FOR EVERY CLASS (owner rule 2026-08). The 24-field
        # classes used to branch to `_recovery_24`, whose berths came out of
        # SUPER REGIONALS while Semi-State awarded none. The owner's pathway
        # is the same rungs everywhere with only the counts changing —
        # 8 Zonal + 8 Semi-State + 4 Divisional + 4 Specials at 24, 8/8/8/8 at
        # 32, 8/8/8/16 at 40 — and the dynamic ladder produces all three
        # exactly once the Divisionals are capped at one block. See
        # `_recovery_24`, kept unwired for the archive it explains.
        sr, ss, dv, sc, cf, quals, dq, atr_used = _recovery(
            group, by_name_g, sectionals[group], wards[group], prestates[group],
            zonal_champs[group], district_champs[group], post_power,
            seed=seed + hash(group) % 9973 + 16223)
        super_regionals[group], semi_states[group] = sr, ss
        divisionals[group], semi_conferences[group] = dv, sc
        conferences[group] = cf
        recovery_q[group], district_q[group] = quals, dq
        atr_snap.update(atr_used)
    states, state_specials = {}, {}
    special_challengers: dict[str, dict] = {}
    state_pools: dict[str, list] = {}
    for group in GROUPS:
        by_name_g = {t.school.name: t
                     for ts in by_group[group].values() for t in ts}
        # ‼️ CONFERENCE WINNERS DO NOT QUALIFY (owner rule 2026-08): they advance
        # to the STATE SPECIALS and must beat a challenger — the best remaining
        # regular-season teams from the WHOLE classification — for the berth.
        # Every other berth-bearing round is untouched: Zonal champions,
        # Semi-State and Divisional qualifiers (Super Regional winners on the
        # fixed 24) enter State automatically, exactly as before. Bids derive
        # from the actual Conference winners, so the count closes every field
        # size by construction (a Conference winner's seat became a Specials
        # dual, one-for-one).
        zc_names = {t.school.name for t in zonal_champs[group]}
        cw_names = set(conferences[group].get("survivors") or ())
        cw = [t for t in recovery_q[group] if t.school.name in cw_names]
        auto = [t for t in recovery_q[group] if t.school.name not in cw_names]
        qualified = zc_names | {t.school.name for t in auto}
        challengers = _select_challengers(by_name_g, cw, qualified, post_power)
        # ‼️ THE SPECIAL CHALLENGERS BRIDGE ROUND plays FIRST (owner rule
        # 2026-08): rank/TOSS/district-title-gated early exits contest the
        # WEAKEST formula-selected challenger seats on court, and the winners
        # hold those seats into the Specials. Zero extra berths — only who sits
        # on the challenger side moves. Seeded on blake2s, not `hash()` — the
        # sibling seeds' `hash(group)` is a pre-existing wart this module is
        # explicitly told not to copy (per-process salting; these duals are
        # archived).
        ch_seed = seed + int.from_bytes(hashlib.blake2s(
            f"jh-challenge|{group}".encode(), digest_size=4).digest(), "big")
        ch_arc, challengers = _special_challengers_round(
            group, by_name_g, challengers, district_champs[group],
            qualified | cw_names, post_power, seed=ch_seed)
        special_challengers[group] = ch_arc
        sp_arc, sp_winners = _state_specials_round(
            group, cw, challengers,
            post_power, seed=seed + hash(group) % 9973 + 4409)
        rest = auto + sp_winners
        if len(zc_names) + len(rest) < state_field_size(group):
            # ‼️ THE EMERGENCY RECONCILIATION, kept ONLY for a played Specials
            # round that still leaves State short (the Conference itself
            # under-delivered winners, or a tiny world ran dry) — the original
            # 2·missing-latest-eliminated rule, over a pool that now includes
            # the Specials' own losers. Merged into the ONE state_special arc:
            # a phase is the archive's identity for an event, and this is the
            # same event finishing its job.
            e_arc, e_winners = _state_specials(
                group, by_name_g,
                [sectionals[group], wards[group], prestates[group],
                 super_regionals[group], semi_states[group], divisionals[group],
                 semi_conferences[group], conferences[group],
                 special_challengers[group], sp_arc],
                zc_names | {t.school.name for t in rest},
                post_power, seed=seed + hash(group) % 9973 + 6733)
            sp_arc = {"field": sp_arc["field"] + e_arc["field"],
                      "rounds": [sp_arc["rounds"][0] + e_arc["rounds"][0]],
                      "survivors": sp_arc["survivors"] + e_arc["survivors"],
                      "round_names": [STATE_SPECIAL_NAME],
                      "head": (sp_arc.get("head") or [])
                      + (e_arc.get("head") or [])}
            rest = rest + e_winners
        state_specials[group] = sp_arc
        state_pools[group] = rest
        if len(zc_names) + len(rest) != state_field_size(group):
            # Only a pool that genuinely ran dry lands here (a class with fewer
            # teams than the field wants — a broken fixture or a tiny test
            # world). Both specials paths direct-admit before they under-fill,
            # so at association size this warning cannot fire.
            log.warning("JHSAA %s State starts short: %d of %d after State "
                        "Specials", group, len(zc_names) + len(rest),
                        state_field_size(group))
    # ‼️ THE FINAL TOSS RECOMPUTE COMES AFTER THE SPECIALS, for every group —
    # `rating_duals(prestate=True)` drops only ("state", "toc"), so the State
    # Specials duals ARE part of the pre-State results graph, and seeding off a
    # rating frozen before they were played would ignore the road's own final
    # round (the archived-not-recomputed rule cuts the other way here: the seeds
    # are the DECISION, and they must be taken off the complete input).
    final_power = power_index(every_team, prestate=True)
    # THE COMPUTER-RATINGS LAYER (owner spec 2026-09, `jhsaa_ratings`) — nine
    # independent systems + composite, per group, for EVERY group and gender
    # whether or not it selects at-large. Computed HERE, on the complete
    # pre-State results graph (the same posture as `final_power` above), and
    # ARCHIVED with the season — a page never recomputes them, the `pi` rule.
    # Parallel to TOSS/ATR, feeding neither.
    from .jhsaa_ratings import group_ratings as _group_ratings
    from . import jhsaa_committee as _jc
    ratings_by_group = {
        group: _group_ratings([t for ts in by_group[group].values() for t in ts])
        for group in GROUPS}
    committee_by_group: dict[str, dict | None] = {}
    for group in GROUPS:
        # ‼️ ZONAL CHAMPIONS ARE THE TOP SEEDS — the whole privileged path, and
        # it is a SEEDING guarantee in its own right, not a side effect of byes
        # (owner clarification 2027-08). Winning a Zonal buys seeds 1-8 in every
        # classification: in a 24-team field that also hands them the eight
        # first-round byes, but a 40-team field gives them a DOUBLE bye through
        # the Qualifiers Round, and a power-of-two draw would give them neither —
        # the guarantee is that they are seeded 1-8, whatever the shape.
        #
        # THE WAYS IN (owner rule 2026-08): win a Zonal, win an AUTOMATIC
        # recovery round (Semi-State/Divisionals — Super Regionals on the fixed
        # 24), or win your State Specials dual (Conference winners and their
        # challengers alike). Everyone below the champions is seeded in
        # post-recovery TOSS order. This holds for 1A's
        # fixed 24-team shape too (`_recovery_24`) — Zonal champions are an
        # automatic State berth there exactly like every other class; only the
        # RECOVERY ladder underneath them is wired differently. `champions=
        # len(zc)` (8) on a 24-team field lands on `run_state`'s single-draw
        # branch (no Qualifiers Round), so "seeds 1-8 bye" falls out for free.
        # ‼️ SEED PLACEMENT IS MERIT, NOT THE ZONAL TITLE (owner rule 2026-09).
        # A Zonal title still buys the berth; the first eight lines now go to the
        # four EPIREGIONAL winners plus the best four of everyone else on the
        # seeding ATR (an Epiregional loser included), the eight ordered 1-8 on
        # ATR among themselves and the rest 9+ on ATR whatever their door in.
        # `champions=STATE_BYES` keeps `run_state`'s bye budget and expansion
        # rule exactly where they were, so every draw keeps its shape: 8 single
        # byes in a 24, 8 double byes in a 40, placement only in a 32.
        if group in ATLARGE_GROUPS:
            # THE PARASTATE FIELD (owner spec 2026-09; 8A/9A joined and 7A went
            # to 8 bids 2026-09). The road is untouched — its 32 qualifiers are
            # exactly `zonal_champs + state_pools` — and the seeds are all
            # EARNED: 1-4 Epiregional winners, 5-8 Epiregional losers, then the
            # non-champion road qualifiers, all on the EXISTING seeding ATR
            # (`seed_atr`, unchanged); the committee's `AT_LARGE_BIDS[group]`
            # at-larges follow by Borda. The committee may pick ANY team
            # outside the road field — a district champion who missed the road
            # is automatic and consumes a bid — but its picks are always seeded
            # below every road qualifier.
            bids = AT_LARGE_BIDS[group]
            field32 = list(zonal_champs[group]) + list(state_pools[group])
            satr = seed_atr(field32, final_power)
            key = _seed_atr_key(satr)
            win_names = {t.school.name for t in epi_winners[group]}
            epi_w = sorted((t for t in zonal_champs[group]
                            if t.school.name in win_names), key=key)
            epi_l = sorted((t for t in zonal_champs[group]
                            if t.school.name not in win_names), key=key)
            others = sorted(state_pools[group], key=key)
            road_seeds = epi_w + epi_l + others
            road_names = {t.school.name for t in road_seeds}
            g_teams = [t for ts in by_group[group].values() for t in ts]
            atr_map = {t.school.name: atr(t, final_power) for t in g_teams}
            sel = _jc.select(ratings_by_group[group], road_names,
                             district_champs[group], atr=atr_map, seats=bids)
            committee_by_group[group] = sel
            by_name_g = {t.school.name: t
                         for ts in by_group[group].values() for t in ts}
            at_large = [by_name_g[n] for n in sel["selected"] if n in by_name_g]
            # Byes = the road field less the bids, so the Parastate is exactly
            # the at-larges and their `bids` road opponents (a 48: 1-16 bye; a
            # 40: 1-24 bye). Off the TABLE size, never `len(road_seeds)`: a
            # short road (tiny world) still byes the right lines.
            arc = run_state_parastate(
                road_seeds + at_large, byes=state_field_size(group) - bids,
                seed=seed + hash(group) % 9973 + 12281)
            arc["at_large"] = [t.school.name for t in at_large]
            states[group] = arc
            continue
        committee_by_group[group] = None
        ordered, _byes = state_seed_order(zonal_champs[group], epi_winners[group],
                                          state_pools[group], final_power)
        states[group] = run_state(ordered, champions=STATE_BYES,
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
            # THE EPIREGIONAL — the Zonal champions' play-in (owner rule 2026-09),
            # its own key and its own panel on the bracket page: four duals
            # producing four placements is not a halving, so it must never be
            # rendered as a column of the tree. `.get` on read — seasons archived
            # before it existed carry no key.
            "epiregional": epiregionals[group],
            "super_regional": super_regionals[group],
            "semi_state": semi_states[group],
            "divisional": divisionals[group],
            "semi_conference": semi_conferences[group],
            "conference": conferences[group],
            # THE SPECIAL CHALLENGERS bridge round — present and empty in the
            # (usual) year no eligible early exit existed, the Semi-Conference's
            # convention; readers `.get` it, since seasons archived before it
            # existed carry no key.
            "special_challenger": special_challengers[group],
            "state_special": state_specials[group],
            # The names admitted by the DISTRICT GUARANTEE alone (champions who
            # did not win a Zonal) — access without a bye. Replaces the retired
            # TOSS wild cards; old archives keep their "wildcards" key.
            "district_qualifiers": district_q[group],
            "state": state,
            # THE COMPUTER-RATINGS LAYER + COMMITTEE (owner spec 2026-09):
            # archived like `pi` — computed once on the pre-State graph, read
            # back, never rebuilt on a page request. `committee` is None for
            # the ten groups that keep a 32/24 field; readers `.get` both
            # (seasons archived before they existed carry no key).
            "ratings": ratings_by_group[group],
            "committee": committee_by_group.get(group),
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
    _stamp_graduation(grads)
    return grads[:limit] if limit else grads


def _stamp_graduation(grads: list[Prospect]) -> None:
    """‼️ THE GRADUATION RECORD (proposal §24.3). The high-school scale is free
    and the college hand-off translates by RANK (`apply_to_class`), so the exit
    rating and the percentile it earned are stamped here — over the WHOLE
    graduating class, before any `limit`, because a percentile is a function of
    the population and re-deriving it later would only match by chance (the
    archived-TOSS rule). The player stays a 96-rated Jefferson monster on the
    record while college receives a properly scaled recruit. `grads` must
    already be sorted best-first."""
    n = len(grads)
    for i, p in enumerate(grads):
        p.jhsaa["hs_exit_ovr"] = p.current_overall()
        p.jhsaa["hs_percentile"] = round(100.0 * (n - i) / n, 1)


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
        # A real Prospect field, so it survives signing — carrying the §24.3
        # translation record whole: `hs_exit_ovr`/`hs_percentile` were stamped
        # on the FREE scale at graduation, and `college_entry_ovr` is what the
        # rank-match hands the college game. The rank-match IS the translator
        # (percentile-primary by construction — the best Jefferson senior takes
        # the best Jefferson slot), so no second mapping exists to version.
        slot.jhsaa = {**grad.jhsaa, "college_entry_ovr": slot.current_overall()}
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

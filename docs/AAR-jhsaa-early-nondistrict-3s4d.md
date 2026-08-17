# AAR — the early non-district window plays 3S/4D

## The report

Owner (2027-08): JHSAA rosters carry 12 players, but the league's 5S/2D card only gives
nine of them a real match. Real high-school programs use JV, exhibition and early
non-league dates to play deeper into a roster; this association has no separate JV
system to model that with. Requested fix: the **first 2-3 non-district duals of the
season** play **3 singles / 4 doubles** instead of 5S/2D — so roster spots #10-11 get
real competitive minutes and a program banks doubles reps before the postseason. All
seven courts are real results scored on the existing `FLIGHT_WEIGHTS` table; D4's low
weight (0.10) keeps the extra developmental court from moving TOSS much. Scope,
stated explicitly: **only** the early window. District duals stay 5S/2D. Any
Invitational a team plays once the league schedule has started stays 5S/2D. The
mid-season Match Showcases and the postseason stay 1S/4D as always, untouched.

## Why this mapped onto existing scheduling almost exactly

`play_regular_season` already plays a gender's regular season in five ordered blocks:

    early non-district → district pass 1 → mid-season window → district pass 2
                       → late non-district tune-up

The "early non-district" block is a single `_play_pairs` call, played BEFORE any
district round, and it already runs `owed = max(1, round((quota - reserved) *
EARLY_SHARE))` per team — with `NONDISTRICT_MIN/MAX` = 4-8 and `EARLY_SHARE` = 0.55,
that lands almost every program at 1-3 early duals, which is the "first 2-3" the
owner asked for without touching any of those constants. So the whole feature is:
give that one block its own `phase` and format, and leave the other four blocks
(mid-season non-district, and the late tune-up — both scheduled AFTER district play
has begun) exactly as they were.

## The mechanism: a new `phase`, not a new axis

`dual_format(phase)` already dispatches on `phase` for the postseason and the two
showcase phases. A third case (`EARLY_FORMAT_PHASE = "early"`) does the same thing:

    FORMATS = {
        "early":   DualFormat(n_singles=3, n_doubles=4, doubles_team_point=False),
        "regular": DualFormat(n_singles=5, n_doubles=2, doubles_team_point=False),
        "state":   DualFormat(n_singles=1, n_doubles=4, doubles_team_point=False),
    }

3+4 and 5+2 are both 7 total courts — the early window doesn't change how many
players a program fields relative to a league dual, only the split between singles
and doubles, and `lineup_need("early")` (3 + 2×4 = 11) is exactly what puts spots
#10-11 on court. `_play_pairs` grew a `phase` kwarg (default `"regular"`, unchanged
for every other caller) and the one early-window call site passes
`phase=EARLY_FORMAT_PHASE`. Everything downstream that already worked off `phase` —
`_squad`, `match_format`, `lineup_need`, `_slot_players`, `_credit` — needed no
further changes, because none of it hardcodes a slot count.

## The one place the plain ladder order needed protecting

`_lineup`'s regular-season branch applies an optional program-philosophy overlay
(`_arrange_regular`) that rearranges a 5S/2D nine into a doubles-forward shape. That
function assumes exactly nine players at fixed S1-S5/D1/D2 positions — it would
silently misindex an eleven-player 3S/4D lineup (or crash on `IndexError` past the
line where it slices into positions the 5S/2D card doesn't have room for past nine).
The early 3S/4D card needs no such overlay in the first place: the top three players
landing on S1-S3 and the next eight on D1-D4 in plain ladder order **is** the format's
point — that's what gets #10-11 real minutes rather than benched behind a
philosophy shuffle. So the overlay (and the per-dual philosophy-flip RNG draw that
decides whether to apply it) is now gated on `phase == "regular"` specifically,
not "not postseason and not showcase" as it read before this change.

## Two read paths that needed to see the new phase, one that must NOT

- **`district_oowp`** built its opponents list off `phase == "regular"` — an
  inclusion filter. A new `phase` value only OOWP didn't know about would have
  silently dropped every program's early-window opponents from its opponents'
  win %, undercounting the "depth of schedule is not a league-only property" figure
  the function's own docstring insists on. Changed to the exclusion form
  (`phase not in POSTSEASON and phase not in SHOWCASE`) already used elsewhere in
  the file, so a future new phase can't repeat this.
- **`rating_duals`** (TOSS) already worked by exclusion (`drop = POSTSEASON`, plus
  `SHOWCASE` unless `SHOWCASE_RATED`) — a phase it has never heard of is rated by
  default, which is correct here without any change: the owner was explicit that
  every early-window court is a real result on the real flight-weight table.
- **`_fmt_sample`** (the Showcase-vs-regular format-profile metrics on the rankings
  page) is the one place the new phase had to be actively EXCLUDED from the
  "regular" bucket rather than left to fall in by default. That metric exists to
  compare a team's *actual 5S/2D card* against its 1S/4D showcases; silently
  averaging 3S/4D and 5S/2D duals into one "regular" number would have quietly
  changed what the number means without anybody deciding that on purpose. Verified
  on a played sample that `format_profile(schedule)["regular"]["n"]` counts only
  `phase == "regular"` duals, never `"early"` ones.

## Display

A non-district dual already renders as an "INVITE" tag (`_KIND.get(phase, "DIST" if
district else "INVITE")` — `"early"` isn't a `_KIND` key and isn't district, so it
falls through to INVITE with no template change needed). The one addition: the
`d.round` chip that a showcase already uses to name its event ("Pod" / "Tiered")
now also fires for an early-window dual, showing "3S/4D" beside the INVITE tag, so a
reader isn't left counting lines to work out why one Invitational dual has a
different shape from another.

## Verified end-to-end on a played sample (24 schools, mixed districts)

- Early duals play `S1-S3, D1-D4` (7 lines, odd total, no tie); regular duals play
  `S1-S5, D1-D2`.
- `format_profile(...)["regular"]["n"]` excludes early duals.
- `district_oowp` and `rating_duals` both run without error over a pool that
  includes early-phase duals.
- Roster size (12) comfortably covers `lineup_need("early")` (11).

Not run: a full-scale multi-classification season and the existing JHSAA test suite
(pytest) — this AAR documents the design and the targeted verification above; a full
suite pass is still owed before this is considered fully proven at scale.

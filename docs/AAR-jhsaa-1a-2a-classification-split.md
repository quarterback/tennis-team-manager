# AAR — splitting 2A-1A into 1A and 2A, and the fixed 24-team postseason shape it needed

## The ask

Owner: "should 2A-1A be split?" The honest answer, checked against real sponsor
counts, was **no under the existing 40-team dynamic format** — 2A alone (56-60
sponsors) and 1A boys (71) both fail `jhsaa.sponsor_floor`'s 76-per-gender floor
for the Semi-Conference/Conference recovery rounds to convene without degrading.
Combined, 2A-1A sits at 127-138, comfortably clear.

That answer only holds for the *existing* format, though — the owner's follow-up
was to design a smaller, fixed-size postseason shape specifically for the two
classes, rather than accept the combined group as permanent. This AAR is that
shape, `_recovery_24`, and the classification split it made viable.

## The shape, and why it needed its own function rather than a parameter

The existing `_recovery` (the 40-team dynamic shape used by every other class) is
a chain: Super Regional feeds Semi-State, and berths flow downstream based on how
many the earlier rounds filled, with the whole thing sized off `state_field_size(group)`.
Feeding it `24` directly does NOT reproduce what was wanted here — the new format's
Super Regional needed to be an independent, direct-qualifying gate, which `_recovery`
never does (there, only Semi-State and Divisional winners enter the State field
directly; Super Regional is purely a feeder). So the correct move was a second,
parallel function reusing every proven primitive (`_recovery_round`'s byeless
pairing, `_power_key`/`_atr_key` ordering, `_RECOVERY_NAMES`/`_RECOVERY_UNITS`)
rather than branching inside `_recovery` itself, which would have risked leaking
new behavior into the classes that must keep the old one.

**Design went through two real iterations, not one, and the first shipped, was
playtested, and was explicitly rejected** — worth recording plainly because it's
the more instructive failure. Attempt 1 retired the Zonal-champion automatic
State berth entirely for 1A/2A (a Zonal win only advanced a team to Super
Regional, same as everyone else). That was implemented, tested against the
actual live game by the owner, and rejected: *"having tested this out, i do not
like that both zonal winners and losers go on to super regionals... i would
prefer to bring back the zonal[ ]8 bids."* The lesson isn't "the first design was
wrong on paper" — the arithmetic in attempt 1 was internally consistent and
matched what had been specified in conversation. It was wrong once tried, because
losing the Zonal-championship guarantee for exactly two classes (while every
other class keeps it) didn't feel right in play, and that's not something prose
specification surfaced ahead of time.

**The shape that shipped** (`app/jhsaa.py::_recovery_24`) restores the Zonal
guarantee — 1A/2A Zonal champions are an automatic State berth and top-8 seed
exactly like every other class — and changes only which Regional losers reach
which recovery round:

```
Regional (32 in: PROTECTED 16 + Ward champs 16) -> 16 winners, 16 losers
  Regional winners play Zonal -> 8 winners AUTOMATIC State berths (top 8 seeds,
                                  same guarantee every other class has)
                               -> 8 losers -> Super Regional

  Regional losers (16), split by recovery PRIORITY:
    preferred (8):  district-champion Regional losers first (best-TOSS if
                    more than 8 of them lost), then highest-TOSS other
                    Regional losers to fill out 8      -> Super Regional
    held back (8):  everyone else                       -> Semi-State

Super Regional  16 (8 Zonal losers + 8 preferred Regional losers)
                -> 8 qualify for State, 8 losers -> Semi-State
Semi-State      16 (8 held-back Regional losers + 8 Super Regional losers)
                -> 8 -> Divisional, 8 -> Semi-Conference
Divisional       8 (Semi-State winners)   -> 4 qualify for State, 4 losers -> Conference
Semi-Conference  8 (Semi-State losers)    -> 4 winners -> Conference (no berths)
Conference       8 (4 Divisional losers + 4 Semi-Conference winners) -> 4 qualify

8 (Zonal) + 8 (Super Regional) + 4 (Divisional) + 4 (Conference) = 24
```

This gives district champions the strongest recovery protection available (first
claim on the Super Regional slots) without making them automatic qualifiers —
they still have to win. Every named round stays in play; nothing was deleted,
only re-plumbed. `_recovery_24` now returns only the 16 EARNED qualifiers (not
24) — the caller adds the 8 automatic Zonal champions on top, using the exact
same seeding code path every other class already uses (`zc + rest,
champions=len(zc)`), so the special-cased "1A/2A has no Zonal guarantee" branch
that attempt 1 needed in the State-seeding loop was deleted along with it.

## ‼️ Every round size here is a CONSTANT, not a function of sponsor count

This is the property that makes the shape safe at 1A/2A's real numbers (56-78
sponsors) without any of `_recovery`'s dynamic sizing, readmission windows, or
Semi-Conference reservoir degradation logic. `PROTECTED=16` and `WARD_FIELD=32`
are flat module constants applied to every class regardless of size (`"THERE IS
NO SCALING"`, `app/jhsaa.py:305-309`) — so Regional's 32-team field, and
everything downstream of it (16/16/8/8/8), is **fixed by construction**, not
derived from how many schools that class actually has. `sponsor_floor` for this
shape is therefore just `PROTECTED + WARD_FIELD = 48` — comfortably under 1A/2A's
worst case (56) — not the dynamic shape's 76-body reservoir formula, which
doesn't apply here at all (`app/jhsaa.py::sponsor_floor`, the new `state_field_size(group)
== 24` branch).

## What actually changed

- **`_recovery_24`** (`app/jhsaa.py`, new function beside `_recovery`) — the
  shape above, dispatched by `state_field_size(group) == 24` in the recovery
  loop only. The State-seeding loop needed NO 1A/2A branch at all in the end —
  it uses the exact same code every other class does (`zc = zonal champs
  sorted by TOSS; run_state(zc + rest, champions=len(zc))`). `run_state` itself
  needed ZERO changes: for a 24-team field with `champions=8`, `size -
  len(field) == champions` (32-24==8) already selects `run_state`'s plain
  single-seeded-draw branch, not the Qualifiers-Round expansion, so "seeds 1-8
  bye, 9-24 play in" falls out of existing code for free.
- **`GROUPS`** (`app/jhsaa.py` and its independent duplicate in
  `scripts/import_jhsaa.py`) went from 8 entries ending `..., "3A", "2A-1A"` to
  9 ending `..., "3A", "2A", "1A"`. `champ_group()` in both files is now an
  identity fold (every real classification has its own group).
- **`STATE_FIELD["2A"]`/`["1A"] = 24`**, replacing the `"2A-1A": 40` entry.
  `STATE_FIELD_DEFAULT = 24` had existed for years as dead code (`.get(group,
  24)` never fired — every real group was in the dict at 40) and the 24-team
  branch of `run_state`/`recovery_shape` was live machinery nobody exercised.
  This is the first time it's actually load-bearing.
- **`_TALENT`** gained separate `("2A", gender)`/`("1A", gender)` bands,
  interpolated between the old combined entry and `"3A"`, continuing the
  existing "mean falls, spread widens" curve one step further down.
- **Data**: `data/jhsaa/schools.json`'s `group` field flipped from `"2A-1A"` to
  each school's own `classification` for the 138 affected schools — a single
  targeted field patch, not a re-import. Districts/leagues were never combined
  in the first place (a district is already `(classification, name)`, so 1A and
  2A already play separate regular seasons today) — only the championship
  bracket merged them, so nothing about the regular season, rivalries, or
  league identity needed to move.
- Owner also added **Oscar Michaeux HS** as a new 1A tennis sponsor in the same
  pass (girls + boys), a plain data addition unrelated to the postseason engine
  itself — noted here only because it landed in the same session.
- Templates (`research_export.html`, `data_portal.html`), `research_export.py`'s
  domain-rules copy, CSS classification-color rules (`jhsaa.css` needed a new
  rule per classification, per its own comment — added `.c-1A`/`.c-2A`), and
  the tests that hardcoded the old 8-group tuple or asserted the old combined
  behavior (`test_jhsaa_playup.py`, `test_jhsaa_archetypes.py`,
  `test_research_export.py`) were all updated to match.
- **Existing archived seasons were explicitly out of scope** — owner does not
  keep saves across changes like this, so no migration path for old
  `world_jhsaa` rows keyed on the group `"2A-1A"` was built. If that ever
  matters again, don't assume it's covered.

## What this AAR is really documenting

Two different lessons, from two different phases of the same feature.

**Getting the arithmetic right is necessary but not sufficient.** Before
`_recovery_24` was implemented at all, three successive prose specs for the
"which pool feeds which round" question looked equally plausible in English and
only one of them summed to 24 under a consistent rule — checking that round
sizes actually add up to the stated field total, by hand, before writing code,
caught that.

**But the arithmetic checking out doesn't mean the design is right.** Attempt 1
(no Zonal guarantee for 1A/2A) was internally consistent, matched what had been
specified, passed every hand-check — and was still wrong, discovered only once
it was actually playtested. Retiring an owner rule that holds for every other
class, even for a well-reasoned structural reason (sponsor floors), is the kind
of change whose correctness is a JUDGMENT CALL under play, not a fact derivable
from the spec alone. The second design — same underlying goal (give district
champions strong recovery protection without an automatic bid), same "every
round stays in play" constraint, different plumbing — is what actually felt
right once tried. Where a change touches something players *experience*
directly (does winning your Zonal mean something, not just "is the bracket math
consistent"), plan for a design to need a real playtest before it's done, even
after every number has been checked twice.

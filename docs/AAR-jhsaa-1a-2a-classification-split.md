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
Feeding it `24` directly does NOT reproduce what was wanted here, for two reasons
that only surfaced by tracing the arithmetic by hand against real numbers rather
than assuming a smaller field is just the same formula scaled down:

1. In `_recovery`, **Super Regional never grants a direct State berth** — its
   winners simply feed into Semi-State's pool. Only Semi-State and Divisional
   winners enter the State field directly. The new format wants Super Regional
   to be an independent, direct-qualifying gate.
2. In `_recovery`, **a Zonal championship is a separate, automatic State-berth
   guarantee** (`app/jhsaa.py:3713-3724`, "a SEEDING guarantee, not a side effect
   of byes") — Zonal champions are pulled out of the recovery pool entirely and
   seeded 1-8 regardless of anything downstream. The new format explicitly
   retires this for 1A/2A: a Zonal win only advances a team to Super Regional.

Both of those are load-bearing owner rules for the OTHER seven classes (one is a
pinned test, `test_zonal_champions_are_the_top_seeds_byes_or_not`) — so the
correct move was a second, parallel function reusing every proven primitive
(`_recovery_round`'s byeless pairing, `_power_key`/`_atr_key` ordering,
`_RECOVERY_NAMES`/`_RECOVERY_UNITS`) rather than branching inside `_recovery`
itself, which would have risked leaking the new behavior into the classes that
must keep the old one.

**The final shape** (`app/jhsaa.py::_recovery_24`), confirmed field-by-field
against the owner before writing any code — three separate designs were
proposed and revised in conversation before this one locked, because the
arithmetic only closes at exactly 24 under one specific reading of where each
round's LOSERS (not winners) go next:

```
Regional (32 in: PROTECTED 16 + Ward champs 16) -> 16 winners, 16 losers
  Regional winners play Zonal -> 8 Zonal winners + 8 Zonal losers
    both together (16)                -> SUPER REGIONAL
  Regional losers (16, never played Zonal) -> SEMI-STATE

Super Regional  16 -> 8 qualify for State, 8 losers -> Divisional
Semi-State      16 -> 8 qualify for State, 8 losers -> Semi-Conference
Divisional       8 -> 4 qualify for State, 4 losers -> Conference
Semi-Conference  8 -> 4 winners -> Conference (no berths, same as `_recovery`)
Conference       8 (4 Divisional losers + 4 Semi-Conference winners) -> 4 qualify

8 + 8 + 4 + 4 = 24
```

`Zonal` therefore keeps existing as a real round — it still plays a match and
still determines seeding weight going forward — it simply stopped being a
State-berth gate. District champions still enter at Regionals (`PROTECTED`,
unchanged) — that rule was never in question, only the Zonal guarantee was.

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
  shape above, dispatched by `state_field_size(group) == 24` in both the
  recovery loop and the State-seeding loop (`run_state` needed ZERO changes —
  traced by hand: for a 24-team field with `champions=8`, `size - len(field) ==
  champions` (32-24==8) already selects `run_state`'s plain single-seeded-draw
  branch, not the Qualifiers-Round expansion, so "seeds 1-8 bye, 9-24 play in"
  falls out of existing code for free).
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

This wasn't a case of a bug hiding in the code — it's a record of the DESIGN
being genuinely ambiguous in prose until the arithmetic was worked through
against concrete numbers. Three successive spec revisions in conversation (an
independent three-gate design, then a version where Super Regional/Semi-State
fed into a single downstream chain, then the final parallel-gates version)
looked equally plausible in English and only one of them summed to 24 under a
consistent rule for "which pool feeds which round." The lesson for next time:
when a postseason topology is specified in prose, checking that the round
sizes actually sum to the stated field total — by hand, before writing any
code — surfaces the real ambiguity faster than implementing a plausible
reading and finding out later it doesn't add up.

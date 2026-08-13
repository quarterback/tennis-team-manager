# AAR — the JHSAA postseason ladder: Sectionals → Wards → Regionals → Zonals → State

**Date:** 2026-08-13
**Status:** Landed. Owner rule, ladder expansion.
**Scope:** `app/jhsaa.py` (`POSTSEASON`, `AUTO_PER_DISTRICT`, `ladder_entry`,
`sectional_field` — replaces `qualifiers` — `_power_key`, `_elim_round`,
`run_sectional`, `run_state` (docstring only), `run_season`), `app/world.py`
(`_round_label` / `_finish_label` / `_ladder_stage`, `jhsaa_state_rounds`,
`jhsaa_state_result`, `jhsaa_sectional_result` (new), `jhsaa_postseason_result`
(new), `run_jhsaa`, `_season_row`), `app/web/state.py` (`jhsaa_school_view`'s
`kinds`/`opp_seed`), `templates/jhsaa_school.html`, `tests/test_jhsaa_ladder.py`
(new).

## The owner's decision

Real state associations don't cut straight from district standings to a fixed
24/32-team bracket the way the old model did — most run a real ladder: district →
regional/sectional → state, with the early rounds open to nearly everyone and the
field narrowing as it goes. The old model also had a specific, measured problem:
2A-1A, the association's biggest classification, was also its hardest to qualify
from — a handful of automatic bids left too few at-large spots for a field that
size, which is backwards for the level that's supposed to be the sprawling,
everybody-plays one (`docs/AAR-jhsaa-high-school-season.md` already flagged this
once; reclassification and sponsorship growth since then made the shape worse, not
better).

The fix is five stages instead of one:

| Stage | What it is |
|---|---|
| **Sectionals** | Broad access. Everyone not protected plays in — not a pre-cut subset, the whole rest of the classification. |
| **Wards** | Only exists for classifications big enough to need it. Protected teams join the Sectional survivors here. |
| **Regionals** | The round where 32 teams enter, always. |
| **Zonals** | The round where 16 teams enter, always. |
| **State** | Round of 8 → Quarterfinal → Semifinal → Final. The only rounds formally called the state tournament. |

**Protection is narrow and stays narrow.** A district's automatic bids (7A: top
two per district; everyone else, the champion — unchanged from the old model) are
PROTECTED, meaning they skip Sectionals. That is the entire extent of it — nobody
skips Regionals or Zonals on a district title, and from Wards on the bracket is
byes-free straight single elimination, so a protected team is exactly as exposed
as anyone else the moment it enters the ladder. `AUTO_PER_DISTRICT` (unchanged)
still decides who's protected; nothing upstream of Sectionals changed.

## Why byes-free was the actual design constraint

The build started from a fixed spec (pod-based Regionals/Zonals, hand-picked field
sizes per classification) and simplified twice during design, both times toward
less machinery: pods turned out to reduce to nothing more than "a normal
single-elimination bracket, labeled by round size" once you actually work out what
they do, so they're gone — Regionals/Zonals/State are just rounds of ONE bracket,
not a separate pod concept. And the field-size table got replaced with
`ladder_entry(n_teams)`, computed from the real roster instead of hardcoded, because
the association's classification sizes have already drifted twice this cycle
(reclassification, `ALWAYS_EXTRA` growth) and a hardcoded table would be stale again
by the next one.

What didn't simplify away: **byes only happen in Sectionals.** That was the one
hard requirement — "make everyone earn their way in" — and it's the actual reason
the architecture looks the way it does:

- `ladder_entry(n_teams)` picks the largest power of two ≤ `n_teams` (floored at 8).
  Since it's a power of two, the field from Wards/Regionals on halves EXACTLY every
  round — no odd remainders, no byes, ever. This is the whole trick: push all the
  "real team counts aren't powers of two" awkwardness into the ONE stage that's
  supposed to have it.
- `sectional_field` splits the classification into (protected, unprotected).
  `run_sectional` trims the unprotected pool down to exactly `ladder_entry(n) -
  len(protected)` survivors, so `protected + survivors` recombines to precisely
  `ladder_entry(n)` teams. Ordinary rounds inside Sectionals halve the field (a bye
  only to fix an odd remainder — nearly everyone plays); the LAST round trims
  precisely via the same "byes to the top seeds" idea `run_state` already used for
  a non-power-of-two field, just aimed at an arbitrary target instead of the next
  power of two up.
- The recombined field then goes straight into `run_state` **completely
  unchanged** — no new code, no special-casing. Since the field is already exactly
  a power of two, `run_state`'s own "pad to the next power of two with byes"
  branch never actually fires in normal play; it's only still there because a
  caller running one classification standalone (tests, calibration) might hand it
  a field that isn't. That's not new logic invented for this — it's the same
  reasoning `engine.tournament.seeded_draw` already gives the college championship.

Measured on the real 513-school association (not the test fixture): every
classification's Wards-through-Final rounds play at **zero byes**, confirmed for
all six groups × both genders. 4A boys (the smallest classification, 63 boys
programs) is the one case where `ladder_entry` lands on 32 rather than 64 — no
separate Wards round, Sectionals feeds straight into Regionals — which is the
intended degenerate case, not a special case that needed its own code path.

## Two archived halves, not one bracket dict

`run_state`'s `{field, rounds, champion}` shape is unchanged and still flows
through every existing reader (`jhsaa_state_rounds`, `_jh_bracket_cols`,
`_bracket_canvas`, the bracket templates, `jhsaa_state_result`) with **zero
changes to any of them** — the whole ladder redesign turned out not to need the
downstream stack rewritten, because `jhsaa_state_rounds`'s `alive`-countdown
already handles any number of rounds generically. What's new is a SECOND archived
dict per classification, `season["groups"][g]["sectional"]`
(`{field, rounds, survivors}` — no single champion, since Sectionals produces many
survivors, not one), stored beside `"state"` under a `"sectionals"` key in
`world_jhsaa.data` alongside the existing `"brackets"` key.

Two dicts because they're genuinely different shapes with a different question
each answers — "how far did this team get on the byes-free ladder" vs. "did this
team survive Sectionals at all" — and a program eliminated in Sectionals never
appears in the `"state"` dict's field, which is correct: it didn't reach the
ladder proper. `jhsaa_state_result` (unchanged) answers the first;
`jhsaa_sectional_result` (new) the second; `jhsaa_postseason_result` (new) is the
one call a program page or season-ledger row actually wants — state result if the
team made it, Sectionals result if not, so `state_finish` on a season ledger row
now reads "Sectionals" for a team that lost there instead of going blank, the same
promise `toc_finish` already made for a team that missed the Tournament of
Champions.

**Round names above the existing Quarterfinalist/Semifinalist/Runner-up/Champion
bands** (`world._ladder_stage`): keyed on how many teams ENTER a round —
alive==32 is always "Regionals", alive==16 always "Zonals" (the ladder always
funnels through both), anything above 32 is "Wards" (covers 64 today; the name
shouldn't silently revert to "Round of N" if the association ever grows into a
bigger one). Below 16 the existing bands were already right and are untouched —
they didn't change just because more rounds now lead into them.

## What this did NOT touch

`run_toc`'s assumption — six classification champions feed the Tournament of
Champions — is still exactly true, because State still funnels down to one
champion per classification the same way it always did; the ladder only changed
how a team GETS to be in the state field, not what State itself produces.
`run_state`, `_jh_bracket_cols`, `_bracket_canvas`, every bracket template, and
every TOSS/`dual_format`/lineup-strictness rule keyed on `POSTSEASON` needed no
code changes — "sectional" was simply added to that tuple, which pulled Sectionals
into the same 1S/4D shape, strict-best-nine lineup, and TOSS exclusion the rest of
the postseason already had, for free.

## Verification

- 97 pre-existing JHSAA tests pass unmodified — the shared bracket-dict contract
  meant nothing downstream needed to change to keep working.
- `tests/test_jhsaa_ladder.py` (new, 12 tests): the ladder is byes-free from Wards
  on; the state field is always a power of two and matches `ladder_entry`;
  protected teams never appear in the Sectional field; survivors + protected
  recombine to exactly the state field; Regionals/Zonals/Wards name the right
  rounds; both halves of `jhsaa_postseason_result` read correctly; Sectional duals
  are archived under their own phase and stay out of TOSS; and the
  historically-buggy invariant (`docs/AAR-jhsaa-district-schedule-passes.md`'s
  131/137 bug class) still holds with a whole new postseason stage in front of the
  old one — every dual on a program's schedule is reflected in its record.
- Measured directly against the real 513-school association (not the test
  fixture): zero byes across all Wards/Regionals/Zonals/State rounds, every
  classification; 4A boys correctly skips the Wards round; a district champion who
  lost in its very first ladder game (Regionals) confirmed protection doesn't
  extend past Sectionals; every `/jhsaa*` route renders against a real archived
  season, including the school page's new "Sectionals" and "postseason ladder"
  schedule segments.

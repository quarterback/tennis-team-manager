# AAR — the Special Challengers: a bridge round in front of the State Specials

**Date:** 2026-08
**Status:** Owner rule, 2026-08
**Extends:** `docs/AAR-jhsaa-state-specials.md` (read that first — this round is a
patch on that design, not a replacement)
**Naming (owner):** formally **Special Challengers**; **Challengers** on the
ledger/finish, **CHALLENGE** as the schedule chip.

## Background

State Specials made the Conference winners earn their berths on court against the
best remaining regular-season teams, and the follow-up data (2053–2056, both
genders) says it is doing its job: of the 30 district champions that missed State
in those seasons, 24 at least reached the Specials — the intended last crack.

The same data measured the leak that remained, and it is narrow. Across ~2,990
teams eliminated in Areas/Wards/Sectionals without reaching State:

| "Good team" definition | Early-exit non-State teams |
| --- | ---: |
| Class rank top 16 | 1 |
| Class rank top 24 | 12 |
| TOSS .700+ | 4 |
| Win pct .650+ | 7 |

Widening to everyone eliminated before the Specials (Semi-Conference and
Conference exits included), top-24 profiles rise to ~40 and .700+ TOSS teams to
22 over four seasons. The failure case is a team like 2056 boys Irrigon (2A,
16–8, .720 TOSS, class No. 16) losing once in Wards: the Specials' challenger
side is selected on **regular-season record** (pct → wins → ATR), so a
high-TOSS, high-rank team whose record misses the formula cut has no route back
— the last-chance mechanism never sees it.

So the fix is deliberately narrow too: not a bigger State field, not a
ranking-based rescue, not a loser's bracket. The weakest formula-selected
challenger **seats** are now **defended on court**.

## The rule (owner spec, exactly)

For each classification and gender, after the Conference and before the
Specials (`jhsaa._special_challengers_round`):

```
eligible = eliminated before the Specials (appears in an archived
           pre-Specials stage; holds no berth and no Specials seat)
           AND (class TOSS rank <= 24            (CHALLENGE_RANK_CUT)
                OR TOSS >= .700                  (CHALLENGE_TOSS_FLOOR)
                OR district champion)
           AND (no losing regular-season record, unless TOSS >= .700)

n       = min(CHALLENGE_SLOTS[class], #eligible, #challengers)
          — 2 per class, 4 in the 40-field classes (see the cap section)

pairing = best eligible (by TOSS) vs the WEAKEST selected challenger,
          second-best vs second-weakest, … the seat-holder hosts, no
          rematch repair — the pairing IS the seeding (the Specials' rule)

winner  = holds that challenger seat INTO the State Specials
```

**Zero extra berths.** The Specials field is the same size with the same bids;
Conference winners are untouched; a bridge winner still has to win its Special.
The design distinction from the parent AAR holds one level down:

- **Specials = the final State bubble.**
- **Special Challengers = access to a seat on that bubble.**

## Why 2, and why 4 in the 40-field classes (owner rationale, 2026-08)

The default cap is two contested seats per class because the early-exit
recovery problem is rare in most classes. The 40-field classes carry four,
because the wider valve is a property of the BIG-FIELD SHAPE, not of any
named class: a 40 Conference sends 14 teams to the Specials against the
32-shape's 6, so its formula-selected tail is both longer and softer — the
largest and noisiest bubble pools in every Specials audit, the highest
concentration of low-ranked entrants and credible early-exit misses. The
higher cap is a targeted correction for that boundary volatility, not a
general expansion of the postseason.

The session's own field retunes proved the rule by moving it twice: 3A/4A
carried the 4 while they were the 40-field holdouts, dropped to the standard
2 the moment their fields came down to 32 ("3A/4A can match the rest of the
state with only the 2 worst qualifiers"), and 8A/9A inherited the 4 when they
went back up to 40 ("they can inherit the 4 state challengers spots that
3A/4A had"). If a field size moves again, move the cap with it.

The design goal is **proportional correction, not symmetry**:

```
2 = normal recovery valve
4 = expanded recovery valve for the classes with the dirtiest bubble
```

If every class got 4, the bridge would contest too much of the Specials field
in classes where the data showed one or two meaningful stranded teams across
seasons — heavier than the problem, and in a 24-shape class (4 bids) it would
put the ENTIRE formula-selected side up for grabs, tilting the Specials'
regular-season currency back toward TOSS. If every class got 2, 3A/4A would
keep their edge-field problem: more low-end qualifier noise, more room for a
good-but-stranded team to fall through. The round is supposed to test the
softest part of the qualification model, never rewrite it — the caps protect
that, alongside the untouched berth arithmetic and Conference winners.

## Deliberate boundaries

- **Only postseason entrants are eligible.** The formula pool already reaches a
  team that never entered the road; the bridge exists for the one-early-loss
  case. Admitting non-entrants would make it a second at-large selection.
- **Conference winners' seats are never contested.** They earned their Specials
  entry on court through the whole ladder; the formula-selected side is the one
  a formula-eligible team may contest.
- **The cap is a cap, not a quota.** A class with no eligible early exits plays
  no bridge duals — the usual case, by design — and the arc is archived present
  and empty (the Semi-Conference's convention).
- **A losing record stays home** unless the .700 TOSS clears it: the round must
  not let bad teams churn through extra matches.

## Wiring (a phase is the archive's identity for an event)

- New phase **`special_challenger`**, in `jhsaa.POSTSEASON` between
  `conference` and `state_special` — which for free gives it: 1S/4D (2S/3D in
  1A, whose road plays the pilot shape), the order-of-ability freeze,
  exclusion from the cutoff TOSS and from `_reg_season_record`, inclusion in
  the prestate recomputes (its duals ARE part of the pre-State results graph,
  like the Specials'), the awards `PHASE_WEIGHT`, and its calendar-lane slot.
- `_select_challengers` is split out of `_state_specials_round`, which now
  takes the (possibly contested) challenger list as a parameter.
- Archived per group under `special_challenger`; readers `.get` it (pre-2056
  archives carry no key). Duals numbered statewide
  (`renumber_special_challenges`, "Challenge N" — the Specials' pattern).
- Finish string **"Challengers"** for both losers, superseding the rung that
  sent them in; `jh_road_ladder` ranks it between Conference and Specials.
  Title board column **CHAL** (a Challenge win is a contested seat, never a
  berth). Schedule chip **CHALLENGE** (`web/state.py::_KIND`).
- The bridge arc joins the emergency `_state_specials` stage walk, so its
  losers are latest-eliminated bodies if the field still runs short.
- Seeded on **blake2s**, not `hash()` — the sibling seeds' `hash(group)` is
  the acknowledged wart this module is told not to copy.

## Lessons

- **The bridge decides who holds a seat, so it must run BEFORE the Specials
  selection is consumed** — which forced the challenger selection out of
  `_state_specials_round` into `_select_challengers`. A round that reorders
  another round's inputs cannot live downstream of it.
- **"Special entrants" needed narrowing.** The spec said the N weakest
  entrants; contesting a Conference winner's seat would have broken the
  parent AAR's `bids = len(conference_winners)` arithmetic and the "a team
  that survives Conference has earned the right to play for State" principle.
  The formula-selected side is the challengeable one.
- **The measured caseload (≈a dozen meaningful rescues over four seasons)
  is the argument for the tight gate**, not against the feature: track the
  same follow-up metrics the parent AAR lists, plus how often a bridge
  winner then wins its Special.

Pinned by `tests/test_jhsaa_special_challengers.py`;
`tests/test_jhsaa_state_specials.py` carries the refactored call shape.

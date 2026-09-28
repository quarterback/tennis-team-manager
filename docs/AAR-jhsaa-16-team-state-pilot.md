# AAR — the 16-team State pilot (JHSAA rule 2099)

Owner rule 2026-09. Spec: `docs/reports/SPEC-jhsaa-16-team-state-pilot.md`. Data:
`docs/reports/REPORT-jhsaa-zonal-champions-and-the-recovery-road.md`.
Code: `app/jhsaa.py` (`SIXTEEN_STATE_GROUPS`, `sixteen_state`, `sixteen_state_era`,
the year-aware table helpers, `_recovery`'s pilot return, `sixteen_state_seeds`,
`run_state_sixteen`, `seed_line_slots`), `app/web/state.py` (committee switcher,
seed-line labels), `app/research_export.py` (manifest), `tests/conftest.py`,
`tests/test_jhsaa_sixteen_state.py`.

## What the pilot is

In **4A, 3A, 2A, 1A and Group 3**, both genders, from the first unplayed season
(2099 on the owner's save), State is **sixteen teams: the eight Zonal champions and
the eight Semi-State winners**. Recovery ends at Semi-State. The Divisionals,
Semi-Conference, Conference, Special Challengers, State Specials, Metastate and
Parastate do not run, and the at-large committee selects nothing (`committee` is
None). Seeds 1-8 are the Zonal champions in Epiregional order, 9-16 the Semi-State
winners on the seeding ATR, and the draw is a plain 16 from the Octofinals.

Across 2093-2096 those two doors produced every State champion and all but two
semifinalists in these classes; everyone else filled seeds 17-32/36 and almost
never survived the Octofinals.

## How it is built

- **One question, asked with the season.** `sixteen_state(group, year)` is
  membership in an explicit tuple AND `year >= sixteen_state_era()`. Every table
  helper that describes a class's postseason — `state_field_size`, `at_large_bids`,
  `metastate_bids`, `parastate_byes`, `recovery_shape`, `sponsor_floor`,
  `parastate_summary`/`parastate_blurb` — takes `year=`. **`year=None` returns the
  owner's tables and never touches the database**, which keeps the import-time
  asserts (and every pre-pilot caller) exactly as they were.
- **The era is `_resolve_era`** (`jhsaa_sixteen_state_era`, in `ERA_SETTINGS`,
  cleared by `reset_schools`/`reset_eras`): the first season the save has not
  archived, 0 on a fresh save, pinnable through worldconfig. It is also in the
  `run_season` memo key.
- **Recovery ends by an explicit return, not by arithmetic.** With eight berths
  `_recovery`'s own equations already size the Divisionals and Conference at zero —
  but only while Semi-State delivers all eight. A thin Semi-State would leave
  berths outstanding and the same equations would quietly reopen the Divisionals.
  A class too thin to FILL a Semi-State skips it; the Super Regional winners
  qualify instead (owner rule).
  The pilot branch returns straight after Semi-State with the three later arcs in
  their "did not convene" shape, so callers do not branch and the archive shape is
  unchanged.
- **The Specials loop and the committee loop skip pilot classes** before any rng
  is drawn for them; `special_challenger`/`state_special` archive as empty arcs,
  `metastate` as None.
- **The draw is strict** (owner decision, see below): `run_state_sixteen` puts the
  field on `seed_line_slots` — the helper `run_toc` now also uses (a pure extraction;
  the TOC is unchanged) — so 1v16, 8v9, 4v13, 5v12 | 2v15, 7v10, 3v14, 6v11. A short
  field leaves the highest lines empty, so its byes fall to the top seeds.
- **The UI and finish walk needed almost nothing**, because they read the archive:
  a Semi-State loser that is in no later field already reads "Semi-State", a Super
  Regional loser "Super Regionals"; a 16 field with no `round_names` is labelled
  Octofinals by `world._round_label`; the bracket page treats a power-of-two field as
  byeless. Two real changes: the committee page's group switcher now drops pilot
  classes for the season on screen (it listed `ATLARGE_GROUPS` from the constant),
  and the seed-line panel labels lines 1-8 "Zonal champion" in a pilot draw as it
  does in a Parastate one. The research export's committee JSON already dropped a
  None committee; its manifest now describes the pilot for a pilot season.

## Two points where the spec could not be followed as written

Both were put to the owner before building.

1. **"1 plays 16 and 8 plays 9."** The State draw (`seeded_draw`) fixes seeds 1-2 and
   shuffles within tiers, so seed 1 draws a random 9-16 — and CLAUDE.md records the
   owner's decision that State stays tiered while only the TOC is strict. The first
   prototype run paired 1v12, 8v16, 6v9. **Owner: strict lines for the pilot only.**
   Every non-pilot State draw is still tiered; CLAUDE.md now names the exception.
2. **"Non-pilot classes byte-identical in 2099."** Not achievable. The State seeding
   TOSS (`final_power`) is recomputed over the WHOLE gender after recovery, and
   non-district play links the classes, so removing the pilot classes' Divisional,
   Conference and Specials duals nudges everyone's final rating. On a scaled girls
   season all seven non-pilot classes had identical roads, identical State fields and
   identical committee selections; **8A, 5A and Group 1 had their State seed ORDER
   move**, and with it their State results, records, the awards and the TOC. **Owner:
   accept, and scope the test** to the road, the field's membership and the
   committee. The rejected alternative — seeding non-pilot draws off a TOSS that
   ignores pilot duals — would still not be identical to a no-pilot run, and would
   change how every other class is seeded.

Also noted: the spec routes 1A and Group 3 through `_recovery_24`. That function has
been **unwired since 2026-08** — every class, 1A and Group 3 included, runs
`_recovery` — so there is one pilot branch, in `_recovery`, and it covers all five.

## Verified

- **Archived seasons are byte-identical.** The same scaled girls season, played on
  the pre-change code (a worktree at the parent commit) and on this branch with the
  gate closed, digests identically — groups, TOC, awards, All-Region, TOSS and the
  incumbency standing — at season 2027 and at season 2098 with the era at 2099.
  `PYTHONHASHSEED=0` on both, since `run_season` still seeds several rounds off
  `hash(group)`.
- `tests/test_jhsaa_sixteen_state.py` (one archived pilot season, both genders, plus
  the same girls season with the gate closed): every pilot field is exactly the eight
  Zonal champions then the eight Semi-State winners; rounds 8/4/2/1 labelled from
  the Octofinals on strict lines; no removed round and no committee in a pilot class,
  and no pilot-class dual in any removed phase; every pilot finish reads the round the
  team lost in (Semi-State / Super Regionals, never Conference, Specials, Parastate,
  Round of 32/24); `recovery_shape(g, year)` matches the played season; the non-pilot
  scoped identity; the gate-closed season still plays the full ladder; a class too
  thin to fill a Semi-State (two Zonals voided) skips it and qualifies its Super
  Regional winners, reopening nothing (owner rule — unreachable at real size);
  the bracket page renders, the committee page lists no pilot class, the export's
  committee JSON omits them.
- `tests/conftest.py` replaces the era resolver for every other suite: a fresh test
  database resolves the era to 0, which would have put every season-2027 fixture on
  the pilot. It REPLACES rather than pins because `world.reset()` clears every era
  setting mid-run.

## Open at push

`test_non_pilot_classes_match_the_same_season_without_the_pilot` FAILS as committed:
its two comparison seasons are played in one process with coaching staffs attached,
and they differ in the REGULAR season (6A/Group 1 Sectional fields), before any
pilot code runs. The same comparison with no staff/prior (a standalone script)
matched exactly through the road. Either run the pair without staff, or find the
in-process state that makes two staff-attached seasons differ — that is not this
pilot's code. The other 17 tests in the module pass.

## Left as it is

- The title board keeps its DIV/S-CON/CON/CHAL/SPEC columns; pilot classes show 0.
- The import preflight reads `sponsor_floor(group)` without a season, i.e. the
  standing tables (the stricter floor). The pilot's own floor is the ward gate,
  `PROTECTED + WARD_FIELD` (48); returning 0 for "no Conference" would have dropped it.
- `docs/JHSAA-road-to-state.md` has a pilot section; the rest of that explainer was
  already behind the tables before this change and was not rewritten here.
- Calendar dates of the removed rounds simply go unused (out of scope by the spec).

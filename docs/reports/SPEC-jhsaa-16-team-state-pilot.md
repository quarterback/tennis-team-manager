# SPEC: the 16 team State pilot (JHSAA rule 2099)

Owner rule, 2026-09. Background and data: `docs/reports/REPORT-jhsaa-zonal-champions-and-the-recovery-road.md`.

## The rule

In the pilot classes, State is 16 teams: the 8 Zonal champions and the 8 Semi-State winners. Nothing else qualifies.

Pilot classes: 4A, 3A, 2A, 1A and Group 3, both genders. Every other class keeps the current format unchanged.

It starts with the first unplayed season, 2099. The sim is through 2098.

## Why

Across 2093 to 2096, Zonal champions and Semi-State winners produced every State champion and all but two semifinalists in these five classes. The Divisional, Specials and at large entrants filled seeds 17 through 32 or 36 and almost never survived the Octofinals. The pilot tests whether a smaller, harder to make State works before it goes association wide.

## What stays exactly as it is

1. Areas, Sectionals, Wards, Regionals and Zonals, including protected seats and district champions entering at Regionals.
2. Epiregionals. They still seed the 8 Zonal champions 1 through 8.
3. Super Regionals and Semi-State. Semi-State is still the Super Regional winners against the Zonal losers.
4. State seeding for seeds 9 through 16. The Semi-State winners are ordered the way the current seeding orders them.
5. Every dual format, lineup freeze and calendar lane.
6. The Tournament of Champions.
7. JV, the JV Team State Tournament and split squads.
8. The definition of a State appearance: a team in the State draw's field. The pilot only makes State harder to make. Career appearance totals need no special handling or annotation.

## What changes in the pilot classes

### Recovery ends at Semi-State

1. Semi-State winners qualify for State. That is 8 berths, the same as now.
2. Semi-State losers are done. Their finish reads Semi-State.
3. Super Regional losers are done. Their finish reads Super Regionals. They are no longer readmitted anywhere.
4. Ward, Sectional and Area losers are done at their first loss. They no longer feed the Semi-Conference. Their finish reads the round they lost in, as it would today for a team that never reached the Semi-Conference.
5. District champions keep their protected seat and nothing else. A district champion that loses its Regional goes to Super Regionals like any Regional loser. There is no extra dual for being a district champion.

### Rounds that do not run in the pilot classes

Divisionals, Semi-Conference, Conference, State Specials and their challengers (`special_challenger`), Metastate, Parastate.

### No committee

The pilot classes get no at large bids. The at large committee does not select, seed or publish anything for them. TOSS and ATR still seed.

### The State draw

1. Field: 16 teams, no byes and no Qualifiers Round.
2. Seeds 1 through 8 are the Zonal champions in Epiregional order. Seeds 9 through 16 are the Semi-State winners.
3. The first round is the Octofinals, then Quarterfinals, Semifinals and Final. The draw uses the standard seeded anchors, so 1 plays 16 and 8 plays 9.
4. Finishes read Octofinalist, Quarterfinalist, Semifinalist, Finalist and Champion. No team in a pilot class can finish "Round of 32", "Round of 24" or "Parastate".

## Implementation notes

Follow the existing idioms. Each of these has a precedent in `app/jhsaa.py`.

1. Membership is an explicit tuple. Add `SIXTEEN_STATE_GROUPS = ("4A", "3A", "2A", "1A", "Group 3")`. Do not derive it from road size or field size; the Metastate uses a tuple for the same reason.
2. Gate it by season. Add a `sixteen_state_era()` resolver on the `_resolve_era` idiom, as `jv_qualifying_era()` does, first season 2099. It must also be pinnable through `worldconfig`. Archived seasons must reproduce byte for byte, and non-pilot classes must stay byte identical in every season.
3. Field size. From the era onward, `state_field_size(group)` returns 16 for pilot groups. `at_large_bids(group)` and `metastate_bids(group)` return 0 for them. Check that the asserts binding `AT_LARGE_BIDS` to `STATE_FIELD` still hold when a pilot group has no bids.
4. Recovery. 1A and Group 3 go through `_recovery_24`; 4A, 3A and 2A go through `_recovery`. Both need a pilot branch that runs Super Regionals and Semi-State, takes the Semi-State winners as the only recovery qualifiers, and returns empty results for the Divisional, Semi-Conference and Conference rounds. Keep the return shape identical so callers do not branch.
5. Skip the Specials and the committee path. Near `run_state_parastate` in the season runner, pilot groups skip the Specials, `special_challenger`, Metastate and Parastate entirely and hand the 16 straight to `run_state`.
6. `run_state`. Call it with the 16 in seed order and `champions=8`. Confirm a 16 field with 8 champions produces a plain 16 draw with no padding byes and no Qualifiers Round, and that the round labels start at Octofinals.
7. `recovery_shape(group)` must project the pilot shape for pilot groups: Super Regionals and Semi-State only, 8 recovery berths. `tests/test_jhsaa_ladder.py` binds this projection to a played season, and the import preflight and `sponsor_floor` read it.
8. Finish walk. In `app/world.py`, the finish walk must label Semi-State losers "Semi-State" and Super Regional losers "Super Regionals" for pilot groups. Nothing may fall through to "Conference", "Specials" or "Parastate".
9. UI. `app/web/state.py` must render a 16 draw for pilot groups with no Parastate tree. The Road to State page must show the ladder ending at Semi-State for those classes. The committee page must show nothing for them.
10. Export. The research export's committee JSON must omit the pilot groups or emit them empty, and `jhsaa_program_history` must carry the new finishes without schema changes.
11. Docs. Add a short section to `docs/JHSAA-road-to-state.md` describing the pilot shape and its classes, and write an AAR when it ships.

## Tests

1. Seasons before 2099 are byte identical in every class.
2. Non-pilot classes in 2099 are byte identical to the same season run without the pilot.
3. Every pilot State field has exactly 16 teams: 8 with a Zone title and 8 with a Semi-State title.
4. No pilot dual carries the removed phases: `divisional`, `semi_conference`, `conference`, `state_special`, `special_challenger`, `metastate` or `parastate`.
5. The first State round in a pilot class is the Octofinals, and seed 1 plays seed 16.
6. No pilot class team finishes "Round of 32", "Round of 24", "Parastate", "Conference", "Specials", "Semi-Conference" or "Divisional".
7. `recovery_shape` matches the played season for every pilot group, in both the `_recovery` and `_recovery_24` paths.
8. A thin pool degrades cleanly. If a Semi-State produces fewer than 8 winners, the field runs short with byes to the top seeds. Nothing reopens the removed rounds to fill it.

## Not in scope

Changing the dates of State or anything else on the calendar. The removed rounds' dates simply go unused. Moving any other class onto the pilot, which waits until the pilot seasons are measured.

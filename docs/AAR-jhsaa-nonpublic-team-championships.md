# AAR — The Non-Public team championships (10B / 11B), 2026-09

## What changed
Private programs stay in the ordinary JHSAA for the league season, district
honours, TOSS, All-State, All-District, All-Region, the individual flights and the
JV season. When the TEAM championship road begins they leave the public bracket
and play the same full ladder (Areas → Sectionals → Wards → Regionals → Zonals →
Epiregional → recovery → Specials → a 24-team State) in one of two ROAD classes:
**10B** (enrollment ≥ `NONPUBLIC_CUT` 550, or a named play-up) and **11B** (below
it). The TOC takes all fourteen champions plus two TOC Qualifier winners (below).
Owner decisions, in order: split only the
team road; cut at 550; `NONPUBLIC_PLAYUP` forces Condotti Vanguard Academy and
Romero-Finniski into 10B ("as they've done their entire lives"); full ladder, the
24-team State 1A plays ("the talent in this classification justifies a real road,
not one using math to determine who gets in"); a private league champion's
protected seat passes to the league's best public finisher; 10B plays 4S/5D
(`WIDE_GROUPS`), 11B the 1S/4D default.

## Where it lives
- `jhsaa.road_group(school, year)` is the ONE authority; `NONPUBLIC_GROUPS`,
  `ROAD_GROUPS = GROUPS + NONPUBLIC_GROUPS`, `nonpublic_era()` (in `ERA_SETTINGS`,
  the `sixteen_state_era` idiom, cleared by `reset_schools`, in the `run_season`
  memo key).
- `run_season` re-deals `by_group` into `road_by_group` after the regular season
  and runs every championship loop over `ROAD_GROUPS`. A public class keeps its
  districts minus the privates (lists stay in district-place order, so `ts[0]` is
  the best public and takes the protected seat); a Non-Public class is one
  pseudo-district with protected = best 16 on ATR and no district champions.
  Awards, standings, individuals, JV read `by_group` as before.
- `TeamSeason.road_group`; `play_dual` resolves a ROAD dual's shape from it (the
  TOC and every regular-season phase still read the league class).
- Archive: `out["groups"]["10B"/"11B"]` carry every road key, `standings: {}` and
  a `members` list; the season blob carries `road: {school: class}`. Readers go
  through `world.jh_road_group(arc, school, league_group)` (`_season_row`, whose
  row gained `road_group` — `_SEASON_ROW_VERSION` 2; `_jh_school_groups`, so
  10B/11B are their own calendar lanes). The title board and the coefficient walk
  `brackets` by key and needed no change; the coefficient ranks a private in its
  road class (`fold`'s `current_group`).
- Pages: the bracket and computer-ratings views take `ROAD_GROUPS` (the rail shows
  fourteen there); the school header shows the road class beside PRIVATE when it
  differs; `.c-10B/.c-11B` in `jhsaa.css`. Export: `programs.csv` `road_group`,
  `jhsaa_championships.json` over `ROAD_GROUPS`.
- Membership: 33 programs added and 15 private rows switched on
  (`scripts/jhsaa_nonpublic_expansion.py`, tables in `import_jhsaa`), taking 10B/11B
  to 60/56 girls and 57/55 boys against the 48 floor. Alderwold 72 → 80 %, Belmonte
  Metro 75 → 89 %; no saturated area touched; one fictional 8A (Antler Valley,
  Blackpine) by owner rule.

## All-Region after the expansion
No redraw: All-Region is selected per area from whoever plays, and its tiers are
program-count thresholds. Belmonte Metro (36 → 47) and Halbrook Basin (42 → 46) now
field a First and Second Team. `AR_HM_MIN_PROGRAMS` moved 100 → 90 (owner: "the
100 was arbitrary") so Gold Valley (103 / 99) and Selquah (96 / 91) both carry an
Honorable Mention in both genders; the next region is 66.

## Lessons
- **The importer's `draw_districts` scattered the 2052 affiliate leagues.** It
  walks prep-network's geographic ORDER, which the Oregon/Washington/Idaho rows are
  not in. `app.jhsaa_districting.redraw_classes` (real coordinates, floor 8, cap 11)
  is the redraw every offseason cycle uses; use it for any membership change.
- **prep-network is a hundred seasons stale on public/private.** The repo retired
  its religious naming layer in 2065; most "absent private candidates" were those
  retired schools under their old names. The repo is the source of truth; source
  data is a list of buildings.
- **A new row's `area` must come from the rows already in its town**, not
  `AREA_RENAMES` (Belmonte Metro and Boise Frontier were split off after it).
- **A cut that lands the bands even is not the right cut if it demotes the class's
  best programs.** 550 puts the two 3A-sized 9A-talent privates in 11B; the fix is
  a named play-up, not a different cut.
- Smoke, not the suite (owner): one scaled season with every private included —
  privates on no public road, each on exactly one Non-Public road, 24-team States,
  every rung played, 16-team TOC, nine flights in 10B and five in 11B, ledger/title
  board/coefficient/export reading the road class. `tests/conftest.py` keeps the
  split OFF for every other suite; `tests/test_jhsaa_nonpublic.py` opts in.

## Addendum — the TOC Qualifier (JHSAA rule 2026-09, adopted)
A 14-team TOC gave seeds 1-2 a bye. The association adopted the finalist-qualifier
compromise (`docs/reports/REPORT-jhsaa-toc-16-team-finalist-qualifier-proposal.md`,
"hotly debated, but ultimately passed"): the **9A and 8A State runners-up** play one
dual, the **10B and 11B State runners-up** play one dual, and the two winners take
the last two TOC seats — a byeless sixteen, one more public and one more private.
- `TOC_QUALIFIER_PAIRS`, `TOC_QUALIFIER_PHASE` (`"toc_qualifier"`, in `POSTSEASON`
  directly before `"toc"`), `TOC_PHASES`. Every "is this the TOC?" branch reads
  `TOC_PHASES`, never the string `"toc"`: the road-shape check in `dual_format`/
  `play_dual`, `NEUTRAL_PHASES` (played at the TOC site, no host), `rating_duals`
  (excluded from TOSS like the TOC), the calendar lanes, the schedule tag.
- The round is played at the TOC's 1S/4D, the higher-TOSS side listed first,
  `run_toc_qualifier` — the `_state_specials_round` archive shape under
  `toc["qualifier"]` (`field`, one round, `survivors`, `round_names`), read with
  `.get` so a 14-team season still renders. A missing side (a class with no final
  in a small world) skips that pair; nothing is padded.
- **A qualifier loser is treated like the other TOC entrants (owner rule 2026-09:
  "why would we treat those teams any different than the other 12?").** Its State
  finalist appearance stays its State honour, and beside it `jhsaa_toc_result`
  gives a TOC appearance (`made_toc` True) with the finish **"TOC Qualifier"**,
  placed one rung below everyone in the draw (`toc_place` = field + 1, no seed).
  `toc_qualifier` is True for anyone who PLAYED the round, winners included (it
  says how they got in). The team honour is the ordinary "Tournament of Champions
  — Qualifier" line without a seed; the school page shows the TOC chip. A first
  draft used the Metastate posture (a qualifier exit is not a TOC appearance) and
  the owner reversed it. `_SEASON_ROW_VERSION` 3.
- Winners enter the TOC seeded on TOSS with everyone else (measured in the smoke
  season: seeds 7-10), so the qualifier buys a seat, never a line.
- Smoke (scaled season, both genders): two qualifier duals among exactly the four
  runners-up, TOC field 16 with eight first-round games and no byes, losers off
  the draw with finish "TOC Qualifier" (a TOC appearance, place 17), schedule
  rows at phase `toc_qualifier`.

## Addendum — the Non-Public RANKING (owner question 2026-09)
"Despite them playing matches in their regular class schedules, you do have the
rankings still be calculated for these classes correct?" TOSS and ATR were always
there — computed gender-wide, archived on each private's LEAGUE-class standings row
— but nothing showed a 10B or 11B ranking: `jhsaa_group_ranking` read
`standings[group]`, which a Non-Public class does not have, and the Rankings page and
class hub listed `GROUPS` only. Now `jhsaa_group_ranking` recognises a
`NONPUBLIC_GROUPS` key, takes the members off the archive's `road` map, pools their
league rows and re-ranks them on the archived `pi` (nothing recomputed; the row's
`district` reads "7A Metro League" so the pooled table says where the league season
was played), and both pages take `ROAD_GROUPS` on their rail. A 10B hub shows its
State draw, ranking and champion with an empty district index (no leagues) and blank
award panels (All-State is a league-class honour). Pinned by
`test_a_nonpublic_class_has_a_ranking_pooled_from_its_members_league_rows`.

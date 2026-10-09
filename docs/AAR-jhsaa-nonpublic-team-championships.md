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
⚠️ **The pairs changed (owner rule 2026-10): 9A v 10B and 8A v 11B**, each public
against private — see `docs/AAR-jhsaa-toc-qualifier-pairings.md`. Everything else in
this addendum stands.
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
- ~~Winners enter the TOC seeded on TOSS with everyone else (measured in the smoke
  season: seeds 7-10), so the qualifier buys a seat, never a line.~~ **SUPERSEDED
  (owner rule 2026-10, `jhsaa.toc_seed_order`).** On the owner's 2032 save the
  qualifier winners were seeding well up the draw on TOSS — a State runner-up
  landing on a line a champion earned, and "a terrible matchup for whoever has to
  play them as a highly seeded team, but they shouldn't be able to float in the
  bracket." The rule now:
  - **The two qualifier winners are ALWAYS the two lowest seeds** (15 and 16 in the
    full sixteen; n+1 and n+2 at any count), whatever their TOSS. The champions
    take 1..14 on TOSS exactly as before. `run_toc(champions, qualifiers=)` takes
    them APART from the champions — the rung no longer appends them to `entrants`.
  - **A champion is POWER-PROTECTED from its own runner-up until the final.** On
    strict seed lines seed 16 is in the 1-seed's half and 15 in the 2-seed's, so the
    qualifiers are first dealt to whichever of the two seats puts each opposite
    its own class champion (the class is `TeamSeason.road_group`). If one still
    shares a half with its champion — both champions drawn into the same half — THE
    CHAMPION moves, swapped with the nearest unprotected champion seed on the other
    half, which on strict lines is its mirror seed (2k-1 ↔ 2k), one line away. The
    qualifiers never leave the last two seats, and a field with no qualifiers is
    byte-identical to the pure TOSS order.
  - Measured on constructed fields: qualifiers rated above every champion still seed
    15/16 with no champion moved; 9A at 1 and 10B at 4 (both top) moves the 10B
    champion to 3 and nothing else; with both champions already on opposite halves
    nothing moves. `_toc_half` is the one place that knows which seed lines share a
    half, computed off `seed_line_slots`, never typed.
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

## Addendum — PODS, the OLD LEAGUE and the All-Star teams (owner rule 2026-09)
The owner's second pass on the split: "remove the privates from the All-State teams
in their classes and start All-Star teams, 1st and 2nd, for both 10B and 11B", and
"give them their own districts". This supersedes the pooled-ranking addendum above
for every season played from the pods on (that read path stays as the fallback for
a season archived before them).

- **A private program's `group` IS its Non-Public class now, in the seed file.**
  `scripts/jhsaa_nonpublic_pods.py` moved all 116 private rows: `group` 10B/11B
  (the 550 cut plus the two named play-ups), `old_group`/`old_league` recording the
  public class and league each row held, and both gender district fields set to
  the POD. The pods' MEMBERSHIP is the owner's (`POD_MAP`, 8-10 schools each — 7
  pods in 10B, 6 in 11B; a first draft at target six was too small and was
  resubmitted); only the pod NAMES were drawn here, from the league bank under
  `redistrict`'s rules. So `districts(gender, "10B")` returns pods, `run_season`
  builds `by_group` over `ROAD_GROUPS`, and standings, a league title, All-District,
  a District POY, the individual flights and the JV season all fall out of the
  ordinary class machinery — the pseudo-district branch and the road re-deal now
  only fire on a pre-pod seed file (a class with no leagues).
- **Public leagues are publics only, home and away.** No redraw: they keep their
  names and their remaining members. Three came out thin — 1A Marble Valley League
  (5), 1A Old Jefferson Athletic Association (5), 7A River Valley League (4) — and
  the owner chose CONSOLIDATION: Marble Valley folds into Old Jefferson Athletic
  Association (10), River Valley into Three Rivers League (12, the cap). No public
  league is under five in either gender.
  ‼️ **THE FOLD IS A STANDING RULE, NOT AN EDIT THE MAP CAN OUTVOTE.** It lives in
  `data/jhsaa/districting.json` (`consolidated_leagues`, read by
  `jhsaa_districting.consolidations`) and `jhsaa._rows()` applies it on every load,
  AFTER the realignment re-apply. Written into the seed file alone it could not
  survive: a committed reclassification cycle records every school's league as it
  stood at commit time, so `rc.reapply` put all 33 schools back into leagues that no
  longer exist (measured on the owner's save — it read as the 10B/11B districts
  being broken). ‼️ Narrowing the re-apply to MOVED schools only was tried first and
  is worse: a touched class then carried BOTH league names at once, because a redraw
  legitimately moves the leagues of members whose class never changed. ‼️ A retired
  name also leaves the naming bank (`districting_config`) — re-issued to a new
  league, the fold would swallow it the moment it was drawn and the class would
  silently lose a league. The script states the pairs once by READING that data, so
  there is one authority; `tests/test_jhsaa_reclass.py` pins the fold surviving a
  re-apply and the bank exclusion.
- **The old-league duals** (`_old_league_pairs`): every private plays every public
  in its old league ONCE — `phase="regular"`, `district=False`, so it counts to the
  record and to TOSS and to neither side's standings. Reserved before the first
  draw (the rivalry rule, so the early matcher cannot pre-empt one), played in two
  halves after league pass 1 and pass 2 — the dates the public school lost from its
  league schedule when the private left — venue alternating on the year. Not drawn
  from the allowance: the `spent` fold counts them, and the early window's share
  shrinks by what they take. A public league that lost a private plays that private
  once instead of twice, and its `SEASON_DUAL_TARGET` backfill covers the rest.
- **The old league resets at every realignment.** `jhsaa_districting.redraw_classes`
  lends each private whose `old_group` is the class being drawn into that draw
  (wearing its old league name; its pod name is passed as `extra_foreign` so no
  public league can take it), writes the league it lands in to `old_league`, and
  pulls it back out. `jhsaa_reclass._move` moves a private's `classification` and
  `old_group` and never its `group`; `_snapshot`/`reapply` carry `og`/`ol`. The
  pods themselves are not redrawn by a cycle (`pod_nonpublic` exists for when the
  owner wants that — it clusters at `POD_CAP` 10 and names from the bank).
- **All-Star, not All-State.** `jhsaa_awards.AS_TIERS["10B"/"11B"] = 2` and
  `slate_label(group)` is the one place the word lives: the honour line
  (`_season_row`), the Honors page heading and the school page read it. The
  Honors, Individual State, District and school pages take `ROAD_GROUPS` on their
  class rail; the school header shows an OLD LEAGUE chip; `programs.csv` carries
  `old_group`/`old_league`.
- **The 10B/11B ranking is its pod rows** on the archived TOSS, like any class;
  `jhsaa_group_ranking` pools league rows only when the class has no standings.
- Smoke (scaled season, both genders, `smoke_pods.py`): no private on any public
  standings row; every pod's champion in the protected tier; every private's
  league duals all against pod mates and one dual against each old-league public;
  every public league dual public-vs-public; All-Star First and Second Team and a
  POY in both Non-Public classes; TOC still a byeless sixteen with the qualifier.


## Addendum — the two classes' dual formats (owner rule 2026-09)

Asked "we never said what format 10B/11B would play, what are they set to do right
now", and the honest answer was that one of the two had been decided by an agent and
the other had not been decided at all.

**What was running:** 10B's road and State at 4S/5D (in `WIDE_GROUPS`), 11B's at the
bare 1S/4D default. Both on the universal 5S/2D early window, both on 3S/4D in the
pod/league season, both reverting to 1S/4D at the TOC — those three fall out of rules
that already existed and were never a Non-Public decision.

**11B moved to 6A's continuity pilot** (`LEAGUE_SHAPE_GROUPS`): its league 3S/4D now
carries through the road and State. Eleven on court from the first dual to the last,
the TOC excepted.

- **Membership is the whole change, and this time that is verifiable rather than
  asserted.** `_arrange_postseason` dispatches on the FORMAT — `n_singles == 1` goes
  to `_arrange_state`, everything else to `_arrange_wide(pool, fmt.n_singles)` — so
  the anti-stacking arrangement follows the shape with no second list to join. 11B's
  postseason gets `_arrange_wide(pool, 3)`, byte-for-byte what 6A gets.
- **`jv_postseason_cut` did not move** (11 before and after): it is derived from
  `lineup_need`, and the league's eleven already dominated 1S/4D's nine. The JV
  individual rank guard stays 14.
- **The flight weights needed nothing**: 3S/4D's S1-S3 / D1-D4 are the league
  season's own flights, already priced and already rated.

> ‼️ **A LITERAL IN A TEST DEFEATS THE MECHANISM EVERY ONE OF THESE PILOTS USES.**
> `test_the_road_shape_is_the_road_class_not_the_league_class` pinned 11B's road at `{5}` flights, so
> a membership change — the *only* thing any of these pilots ever changes — broke a
> test whose actual claim is "the road plays the class's OWN shape". It now derives the
> count from `dual_format`, and the next move needs no test edit.

> ‼️ **AND TWO COMMENTS WERE WRONG IN THE SAME NEIGHBOURHOOD.** `WIDE_GROUPS` credited
> 10B's 4S/5D to the owner, who had not been asked — it was an agent's inference from
> "most of 10B is 7A-9A privates", and it is now labelled as one. It STANDS as the
> shape 10B plays and it is flagged as open: 10B's membership is an enrollment cut at
> 550, so its smallest member is nothing like a 9A, while 4S/5D was chosen for the
> association's deepest classes. The same block also still claimed the wide classes'
> EARLY window plays 4S/5D, which the 2026-09 reversal ("I don't want 5/2 tennis to go
> away") had already ended — `rehearsal` in `dual_format` is `road or SHOWCASE` and
> excludes `EARLY_FORMAT_PHASE`, so the comment described a shape the code had stopped
> playing. **A stale comment inside a format explanation is the one this section keeps
> paying for.**


## Addendum (2026-10): no pods — 10B/11B are ordinary classes, and the split is a standing rule

The owner's real save played its 2029 and 2030 seasons on a map that an old
committed realignment cycle had written back over the Non-Public split (the
`reapply` fault fixed in 0831d8d, after the file had already been rewritten on
disk). Most privates were back in public leagues; the 11B boys' leagues that
remained held three to five teams; and Condotti Vanguard Academy and
Romero-Finniski — the association's one codified rivalry pair, which every
mechanism keeps together, so any leftover of two is always them — sat alone in a
two-team 10B district carrying the 8A Sunkist League's name. Nothing raised:
a district of two clears `MIN_DISTRICT`, and the standings were honest for the
league they described.

Owner (2026-10): "just remove them as pods and make the real districts like all
the others and move those programs all to the 11b 10b places they belong like all
other teams and that should fix all of this once and for all."

- `POD_MAP`, `POD_CAP` and `pod_nonpublic` are gone. 10B and 11B leagues are drawn
  by `redistrict` with the association's own `district_count` and cap over the
  programs that sponsor a team — six leagues of 8-11 in each class, same as a
  public class. `scripts/jhsaa_nonpublic_leagues.py` is the forced redraw.
- The split is a STANDING RULE applied on every load, the `consolidated_leagues`
  idiom: `jhsaa_districting.ensure_nonpublic` (called from `jhsaa._rows()`) moves
  any private found in a public group into its Non-Public class (recording the
  league it sat in as its old league), redraws a Non-Public class whose leagues are
  unnamed, thinner than `min_district_size`, split across the gender fields or
  wearing a public league's name, and the loader rewrites the file. A healthy file
  is a no-op; the repair is idempotent. Whatever a cycle, a checkout or a hand edit
  leaves in `schools.json`, the save plays on the right map.
- Archived seasons are not touched; the 2029 and 2030 standings read as they were
  played.
- **All-State, not All-Star (owner correction 2026-10).** The 2026-09 addendum's
  two-team "All-Star" slate was an agent's misreading; the Non-Public classes
  follow the exact naming conventions of every other classification — All-State,
  All-Region, All-District — at the default three teams. `slate_label` answers
  All-State for every class, `AS_TIERS` carries no 10B/11B entry, and
  `_SEASON_ROW_VERSION` is bumped so archived honour lines re-derive with the
  right name. Seasons archived with two teams render as All-State First and
  Second Team.

## Addendum — the two-team "11B Sunkist League" was the PLAY-UP map, not the district map (2026-10)

**Report.** "Despite all the fixes on the repo IT STILL KEEPS PUTTING CONDOTTI VANGUARD
AND ROMERO FINNISKI IN THEIR OWN DISTRICT." The 2033 girls' 11B rankings showed all
58 programs, with the two at 2-0 and 0-2 in district: a two-team league, in a class
whose repair (`ensure_nonpublic`) redraws any Non-Public league under eight.

**Why every map repair missed it.** The repair, the reclass re-apply and the
consolidations all run on the ROWS in `_rows()`, and the rows were right: both
schools in the ten-team Cape-Meridian League. The fault was one step later.
`load_schools` builds School objects, and its league is
`moved.get(name, row["<gender>_district"])`, where `moved` is the PLAY-UP league map:
`_compute_playup_league` places every program the play-up read names into the
closest league of its target class, by NAME. It ran `_plays_up_row` on every row,
privates included, and `load_schools` refused to move a private's GROUP but still
took its LEAGUE from that map. A stale `jhsaa_playup` override row for the two
(they were pinned to 10B by name in 2026-09 and that pin is long retired, but the
per-save override table never forgot) resolved to a public target, the placement
chose the nearest league in that class — the 8A Sunkist League — and the School came
out `group=11B, district="Sunkist League"`: a league no row carried, holding exactly
the two programs the override named, every season, through every repair. Reproduced
on the repo data with one override each: both landed in "Summit League" under 11B.

**Fix.** `_plays_up_row` answers None for any row whose `group` is Non-Public, so
neither the mover list nor the loader's target can name a private; `load_schools`
reads a private's league from the row alone. Pinned by
`test_a_stale_play_up_override_never_moves_a_private_or_its_league`. The stale
override rows are ignored rather than deleted (the explorer can still show and clear
them); nothing in a map file needed to change, and killing the Sunkist NAME would
have changed nothing — the next closest 8A league would have taken its place.

**Lesson.** Three layers decide a program's league here — the seed file, the standing
repairs on the rows, and the per-save overlays in `load_schools` — and a guard on one
layer cannot see a fault in the next. When a league exists that no row carries, look
at what `load_schools` ADDS to the rows, not at what wrote them.


## Addendum 2026-10 — the old-league fixtures are retired (JHSAA season 2111, world year 2037)

The old-league duals existed to carry the privates' public rivalries through the
2026-09 Non-Public split. By the 2111 season the realignment had settled long enough
that they were no longer necessary, and the association dropped them.

What surfaced it: the owner reported 10B/11B programs opening the season straight
into league play while 9A still had its early invitationals. `_old_league_pairs`
reserved 6-12 fixtures per private and deducted them from the non-district quota
(6-8) BEFORE the early share was cut, so `owed` rounded to zero — measured 113 of
139 girls' and 109 of 135 boys' privates, plus the publics in leagues that had lost
several. Asked, the owner dropped the fixtures entirely rather than re-balance them.
`_old_league_pairs` is unwired; `old_group`/`old_league` remain realignment data;
seasons archived with the fixtures stay as played. Pinned by
`test_a_private_still_opens_with_the_early_window`.

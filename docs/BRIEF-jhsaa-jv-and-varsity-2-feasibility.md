# BRIEF — a concurrent JHSAA JV season: feasibility

**Status: INVESTIGATION ONLY. Nothing is built, no code changed, no tests written.**

**Everything labelled MEASURED comes from the real 2038 save** (research exports
`playtoclinchjhsaa2038boys` / `…girls` — 864 girls' and 780 boys' programs, 31,766
players, 21,419 duals, 446k line appearances). GENERATED means `jhsaa.build_roster` on
a synthetic world, used only where the real save cannot answer. PROJECTED means
arithmetic on top of the real save — clearly derived, not simulated.

---

## 0. Owner decisions (2026-08) — settled

1. **ONE ROSTER, ONE LADDER, BEST ELEVEN PLAY.** There is no varsity squad and no JV
   squad. `_order(ts)` ranks the roster; the top 11 dress varsity and **everyone below
   is JV that day**. A JV player who gets good enough walks into the varsity lineup —
   which is how it works in life, and, with no injuries or fatigue in this association,
   is where the season's variability comes from. The existing `_order` / `_lineup` /
   `_rest_count` / `_ROTATE_*` machinery is the whole mechanism; nothing new is needed
   to make it porous. Late-season the ladder settles on its own, which is also real.
2. **"Available that day" = the per-program constant.** Top 11 go varsity, the rest are
   JV. No absence or attendance model — the JHSAA has none and is not getting one.
3. **The JV lineup is ELASTIC — fit to what the program has, never dogmatic:**

   | available | JV format | players | courts |
   |---:|---|---:|---:|
   | 5 | 1S/2D | 5 | 3 |
   | 6 | 2S/2D | 6 | **4 — even** |
   | 7 | 3S/2D | 7 | 5 |
   | 8 | 2S/3D | 8 | 5 |
   | 9 | 3S/3D | 9 | **6 — even** |
   | 10 | 4S/3D | 10 | 7 |
   | 11 | 3S/4D | 11 | 7 |
   | 12+ | 4S/4D | 12 | **8 — even** |

4. **Ties are accepted.** Even-court formats can draw; broken on sets, then games, and
   **a dual still level after that is a TIE**. This is the association's first tie —
   nothing in `jhsaa` has tie logic today, by explicit design.
5. **`ROSTER_FLOOR` rises from 12 to 16** (decided after §3: 15 was one player short of
   the elastic table's smallest entry and would have left 105 girls'/89 boys' programs
   unable to field a JV at all). At 16, **every program in the association can field a
   JV**.
6. **The JV calendar:** season **starts in April**; **invitationals in March**; **one
   showcase in May**; **district round robin once**, which lands at or near 16.
   **16 is a LIMIT, not a floor.** Showcases **do not** count against the 16, and a
   program gets **one showcase per season**. ‼️ See §4 — "April" is a spring-calendar
   instruction and the boys play in the fall.
   **Rationale (owner):** April is chosen so the March 5S/2D invitational window is
   already finished and cannot preclude the JV schedule. §4 shows this does more work
   than expected.
7. **‼️ JV NEVER HOLDS UP THE SCHEDULE.** JV dates are assigned independently of
   varsity: the scheduler must not care how JV duals bunch, must never make a varsity
   dual wait on a JV one, and JV may be played **whenever and wherever** — the next
   day, or **on Sundays**, which varsity never uses. They just have to happen.
8. **JV counts for nothing.** No TOSS, no rankings, no awards, no seeding, no
   postseason. Varsity is untouched. Real associations agree — see §6.
9. **JV showcases reuse the varsity showcase machinery**, same material tool.
10. **The JV tab lives on the school's own page**, showing that program's JV schedule.
11. **‼️ A JV RECORD IS KEPT AND SHOWN.** "We're playing the games, so why not" — and it
    is narrative: a program whose varsity is poor while its JV wins is a program about
    to get good, and that story is only legible if the JV record is on the page. This
    does **not** reopen decision §0.8: a RECORD is not a RATING. No TOSS, no power
    index, no seeding, no awards, no postseason — just W-L-T.
12. **‼️ JV MATCH DATA IS NOT ARCHIVED — it goes away after the season.** Only the
    RECORD persists, on the program page, and only if that is easy. It is (§8a).
    ‼️ This collides with an earlier decision — see §8a — because in the JHSAA there
    is no "current season" to read from: every page reads the archive.
13. **The opponent reads `San Borrego (JV)`** — parentheses, not OSAA's `[JV]` brackets.
11. **No Varsity 2.** Dropped — see §7 for why the numbers agreed.
12. **Results→development stays out of scope.** (Flagged because today *no* JHSAA
    result affects development at all: `_dev_maturity` rolls a four-year trajectory at
    entry and `build_roster` regenerates deterministically. That is a separate and much
    larger feature needing persisted per-player state.)
13. `world.jhsaa_underplayed` stays as it is (varsity appearances only), and
    `_rest_count` stays — using these players in varsity duals sometimes is realistic.

---

## 1. The problem, measured

**MEASURED — matches actually played in 2038, by roster rank** (ordered by matches
played, i.e. effective usage, not the seeded ladder):

| rank | 1–9 | 10 | 11 | 12 | 13 | 14–15 | 16–19 | 20+ |
|---|---|---|---|---|---|---|---|---|
| median matches (girls) | 25–28 | 18 | 12 | **4** | **3** | **2** | **1** | **0** |
| median matches (boys) | 24–27 | 17 | 12 | **4** | **3** | **2** | **1** | **0** |

| | girls | boys |
|---|---|---|
| players | 16,564 | 15,202 |
| zero matches all season | 1,352 (8.2%) | 1,496 (9.8%) |
| **≤5 matches** | **6,752 (40.8%)** | **6,431 (42.3%)** |
| **seniors playing ≤5 in their final year** | **749 of 4,125 (18%)** | **741 of 3,852 (19%)** |
| best zero-match player, `current_grade` | 60 | 65 |

~750 seniors a gender reach the college hand-off with no résumé — `graduating_class`
writes `Prospect.jhsaa` off `ts.records`, so they arrive on the recruit board at 0-0.
And zero-match players are not all filler: median `current_grade` 30/33 against a
population median of 38/41, but the tail reaches 60/65.

---

## 2. ‼️ The elastic lineup is what makes this work

A *fixed* JV format has to be fielded by **both** schools, so its reach is the product
of two roster constraints and it collapses — measured on the real save as a share of
league dates where both sides could field: 3S/4D **7–9%**, 2S/3D 32–36%, 2S/2D 61–64%,
1S/2D 78–79%. The elastic table has no product: the format drops to whatever the
thinner side can dress, so a dual happens whenever both sides clear five.

### MEASURED — the design as specified in §0.6

District single round robin, capped at 16, invitationals filling the rest, opponents
within one classification, format = the **smaller** side's capacity capped at 12:

| | JV programs | duals (RR + invit) | card | **zero-match** | **≤5 matches** |
|---|---|---|---|---|---|
| girls — baseline | — | — | — | 8.2% | **40.8%** |
| girls, floor 15 | 759/864 (88%) | 6,058 (3,050 + 3,008) | median 16 | 0.9% | **5.8%** |
| **girls, floor 16** | **864/864 (100%)** | 6,897 (3,896 + 3,001) | median 16 | **0.8%** | **4.5%** |
| boys — baseline | — | — | — | 9.8% | **42.3%** |
| boys, floor 15 | 691/780 (89%) | 5,513 (2,501 + 3,012) | median 16 | 1.2% | **6.2%** |
| **boys, floor 16** | **780/780 (100%)** | 6,227 (3,184 + 3,043) | median 16 | **1.2%** | **5.0%** |

**The problem goes away.** 41% of the state at ≤5 matches becomes 4.5–5.0%. The
district round robin supplies about half the card and the March invitational window
supplies the rest, which is exactly the shape §0.6 describes.

**MEASURED cost.** A gender's season today is **146.6s / 12,271 duals** — the rung is
~5 minutes for both genders, not the 19s in `DESIGN-jhsaa-high-school-season.md:280`,
which is badly stale. Per-dual: 3S/4D regular 10.44 ms, 1S/4D 9.93 ms, 5S/2D 7.25 ms,
prototyped 2S/3D 8.25 ms. The JV slate averages ~4.5 courts under floor 16, so ~7.5 ms
× ~6,500 duals ≈ **+49s/gender**. **Rung ~5 min → ~6.5 min.**

---

## 3. ‼️ A floor of 15 changes nothing; 16 is the number

`ROSTER_FLOOR` guarantees the roster, and the JV needs **five spare on top of varsity's
eleven**. 11 + 5 = **16**. A 15-player program has four spare, which is below the
elastic table's smallest entry.

**MEASURED, real 2038 roster histogram:**

| roster | 12 | 13 | 14 | **15** | 16 | 17 | 18 |
|---|---:|---:|---:|---:|---:|---:|---:|
| girls programs | 4 | 11 | 29 | **61** | 91 | 112 | 92 |
| boys programs | 3 | 14 | 30 | **42** | 73 | 79 | 99 |

| `ROSTER_FLOOR` | programs raised (g/b) | **still cannot field a JV** (g/b) |
|---|---|---|
| 12 (today) | 0 / 0 | 105 / 89 (12% / 11%) |
| **15 (as decided)** | 44 / 47 | **105 / 89 — unchanged** |
| **16** | 105 / 89 | **0 / 0** |
| 17 | 196 / 162 | 0 / 0 |

Fifteen raises 44 girls' programs from 12–14 up to 15 and leaves **every one of them
still unable to field a JV**, joining the 61 that were already sitting at exactly 15.
Sixteen touches 105 programs and takes JV participation to 100%.

Sixteen is also cheap: 61 of the 105 girls' programs are already at 15, so the median
program is unaffected, and the raised programs concentrate in 4A/3A/2A (22/24/19
girls'), which are the classes currently worst served. Recommendation: **make it 16**.

One knock-on worth naming: floor 16 pushes the 1S/2D share of JV duals from 22% to
**39%** (girls), because every newly-floored program has exactly five spare. That also
drops the tie rate — see §5.

---

## 4. ‼️ "April" is a spring-calendar instruction; the boys play in the fall

`world._JH_SEASON_OPEN` is `{"boys": (8, 1), "girls": (3, 1)}` and `_JH_SEASON_CLOSE`
is `{"boys": (10, 31), "girls": (6, 7)}`. So the decision in §0.6 maps cleanly onto the
girls' calendar and has no meaning on the boys':

| | girls (Mar 1 – Jun 7) | boys (Aug 1 – Oct 31) |
|---|---|---|
| invitational window | March | **August?** |
| JV season / district RR opens | April | **September?** |
| showcase | May | **October?** |

The obvious reading is *month 1 = invitationals, month 2 = league, month 3 = showcase*,
which is what the table above assumes. **Confirm before anyone builds it** — the
alternative (JV runs on literal calendar months for both genders) would put the boys'
JV season after their varsity season has finished.

### ‼️ JV IS SCHEDULED OUTSIDE THE VARSITY ALLOCATOR ENTIRELY (decision §0.7)

`jhsaa_match_dates` packs duals into rounds where **no team appears twice**, advancing
`nxt[home]`/`nxt[away]` on **every distinct key**. So a JV dual sharing a school with a
varsity dual takes a *later round*, and the two seasons serialise: the calendar
overruns its window, `_jh_pattern` degrades to a six-day week, and every individual
card still reads correctly — only the *span* is wrong, which is exactly how the
postseason-lane bug (`AAR-jhsaa-postseason-calendar-lanes.md`) hid for as long as it
did.

Two ways out, and the owner has chosen the second:

* **Coalesce** — give a JV dual the date of its varsity dual (JV at 4:30, varsity at
  7). This is what a mirrored JV schedule would need, and it is *not* free: adding a
  level to `jh_match_key` makes the keys distinct, which is necessary but does the
  opposite of co-dating on its own. It needs an explicit varsity-date lookup.
* **‼️ Schedule JV independently (decided).** JV rows never enter the varsity round
  pool at all. They get their own date pass with their own day pattern, and **that
  pattern may use Sunday** — weekday 6, which varsity's `_JH_PATTERNS` excludes by
  construction and which is therefore free real estate. Duals bunching is explicitly
  fine. A varsity dual may never wait on a JV one.

The second is both what the owner wants and strictly less work: no coalescing, no
lookup, and the varsity calendar is provably untouched because JV never enters it. The
`level` in `jh_match_key` is still required — for archive identity, not for dating.

### The 9-vs-11 availability trap (real, and the April start closes it)

`lineup_need` is **11** for the regular 3S/4D format but **9** for the early 5S/2D
window. Under decision §0.1 — JV is whoever is below that day's varsity lineup — an
early-window date leaves **two more** players available, which would pull 14- and
15-player programs into JV eligibility on those dates only, and shift every other
program's format up a step.

**MEASURED — this does not arise, because of the April start:** every early-phase dual
in 2038 falls in **March** (girls, all 950) or **August** (boys, all 871) — month 1 of
each season, before JV begins. So varsity always dresses 11 on a date JV is played, and
the `roster − 11` arithmetic used throughout this brief is correct *for this calendar*.

⚠️ **One premise correction.** The rationale for April was partly "most teams don't go
to those anyway" — that is not what the data says. **Every program plays the early
window**: 864 of 864 girls' and 780 of 780 boys' programs, median 2 duals, max 3. It is
universal but *short* (7.7% / 8.1% of all duals) and *confined to month 1*. So April
does real work — it steps past a window everyone plays, not a window few attend — and
the conclusion stands for a firmer reason than the one given.

‼️ If JV is ever allowed into the early window, the availability arithmetic changes and
this section is the tripwire.

---

## 5. Ties are a quarter to a third of the JV season

**MEASURED format mix under the §2 design:**

| format | courts | girls (floor 16) | boys (floor 16) |
|---|---:|---:|---:|
| 1S/2D | 3 | 39% | 36% |
| 2S/2D | **4 — even** | 18% | 13% |
| 3S/2D | 5 | 12% | 15% |
| 2S/3D | 5 | 11% | 11% |
| 3S/3D | **6 — even** | 9% | 8% |
| 4S/3D | 7 | 5% | 8% |
| 4S/4D | **8 — even** | 4% | 5% |
| 3S/4D | 7 | 3% | 4% |
| **even-court total (a tie is possible)** | | **31%** | **27%** |

(At floor 15 it is 39% / 34% — the extra 1S/2D duals floor 16 creates are odd-court,
so raising the floor also reduces ties.)

Still not a corner case. What it implies:

* `TeamSeason` carries `wins`/`losses` only — a JV one needs `ties`, and `record`
  becomes `W-L-T`.
* The tiebreak ladder (sets → games → tie) has no implementation anywhere.
  `jhsaa._games` already parses games out of an archived score string; **sets are
  counted nowhere** and would be new.
* `world_jhsaa_dual.won` is an INTEGER boolean — a tie has no representation.
* `win_pct` / `district_pct` assume `wins + losses` is the denominator.

---

## 6. How real systems render JV (research, 2026-08)

Consistent across football, basketball, volleyball and soccer — **the level is a
property of the program page, not of the sport**.

**OSAA** (from the program pages themselves): the program page carries top-level tabs
**Varsity · Junior Varsity · Junior Varsity 2 · Freshman**, and each level has its own
sub-tabs. Varsity's are **Schedule · Ranking · Roster · Team Photo**; the JV level shows
**Schedule · Roster · Team Photo** — **no Ranking tab**. The Team Staff block lists
*JV Head Coach / JV Asst. Coach / FR Head Coach / FR Asst. Coach* separately from the
varsity staff. JV schedule rows suffix the opponent **"[JV]"**, carry the same
Non-League / League / Tournament / Neutral-Site detail chips as varsity, and show
status **"Done"** with **no score** for most rows — a score only where someone reported
one. The varsity-only furniture (Varsity Contests progress bar, RPI/Colley ratings,
OSAA Rank, Ranking Frozen timestamp) does not appear at JV.

**MaxPreps**: a level **switcher** (Varsity / JV / Freshman) plus a season selector,
each level a separate page with tabs Home · Schedule · Roster · Standings · News. A JV
page shows **Overall** and **League** records — including a league *place* — but **no
rankings**. Where a JV opponent has no page of its own, MaxPreps schedules against a
**pseudo team**: "JV Opponent", "Freshman Opponent", "Non-Varsity Opponent",
"Non-JV Opponent".

**Policy, and it matches decision §0.8 exactly:**

* OSAA: cross-level contests (varsity versus sub-varsity) are **not included in
  rankings calculations**.
* NCHSAA: "Contests against 'pseudo teams' cannot be included in the NCHSAA RPI
  calculations" — JV Opponent, Freshman Opponent, Non-Varsity Opponent and Non-JV
  Opponent are all excluded from RPI and seeding. Its published contest limits
  (basketball/soccer 24, volleyball 22, football 10; tennis unlimited) are stated for
  **varsity only** — sub-varsity limits are not published at association level.
* MIAA does not sanction or sponsor any sub-varsity tournament competition.

**What this says for the design:** OSAA's shape is the closer match to decision §0.10 —
one program page, a JV tab, Schedule and Roster under it and **no Ranking**. MaxPreps'
league-place-on-a-JV-page is the one thing to *avoid*, since a JV league table is one
step from the standing nobody wants. The "[JV]" opponent suffix is worth copying: it is
how a reader tells a JV card from a varsity one at a glance.

Sources: [OSAA Teams](https://www.osaa.org/demo/teams/62007) ·
[OSAA Rankings FAQ](https://www.osaa.org/help/rankings) ·
[MaxPreps Pseudo Teams](https://support.maxpreps.com/hc/en-us/articles/9316813333787-Pseudo-Teams) ·
[MaxPreps JV Football page](https://www.maxpreps.com/ca/los-angeles/los-angeles-romans/football/jv/) ·
[NCHSAA Contest Limitations](https://www.nchsaa.org/contest-limitations-playoff-and-seeding-format/) ·
[GHSA Constitution](https://www.ghsa.net/constitution-section-2025-2026-basketball)

---

## 7. Why Varsity 2 was dropped (and the numbers agreed)

**MEASURED, real 2038 rosters:**

| roster ≥ | statewide (g/b) | 9A/8A/7A only (g/b) |
|---|---|---|
| 26 | 45 / 55 | 37 / 40 |
| **27** (the proposed line) | **28 / 33** | **22 / 25** |
| 28 | 19 / 21 | 13 / 15 |
| 30 | 3 / 8 | 3 / 8 |

Two dozen programs a gender, and fragile: 28 halves it, 30 kills it. The proposed 27 is
also benchless arithmetic (11 + 8 + 8), stripping varsity of the spare `ROSTER_FLOOR`
exists to guarantee. And a V2 is not a school: every surface here keys on a unique
display name (`world_jhsaa_dual.school`, the routes, the pids, the crest lookup,
`_jh_school_groups`), so a V2 appearing as an opponent on a 3A program's card would 404
its program page and blank its crest, quietly. The elastic JV reaches 100% of programs
under floor 16 and takes ≤5-match players from 41% to under 5%. Correctly dropped.

---

## 8. What still needs building

* **A `level` axis on the archive.** `world_jhsaa_dual` (world.py:213) has none. It must
  be a level, **not a phase** — phase is the archive's identity for an EVENT and it
  selects the dual format and the postseason lane, but JV plays inside its own league
  and its invitationals alike. There is an `ALTER TABLE` idiom already (world.py:264).
* **‼️ `jh_match_key` will break silently.** It is `(phase, district, home, away)`
  (world.py:4024). A JV dual against the same opponent in the same phase yields the
  **identical key**, which puts a self-edge into `_jh_global_order`'s topological sort,
  drops it into the cycle fallback, and quietly degrades the whole gender's calendar.
  Level has to be in the key for **archive identity** — and separately, per §4, JV rows
  must be kept out of the varsity round allocator altogether. Adding the level to the
  key does not by itself co-date anything; it makes the keys distinct, which is the
  opposite. Getting only half of this is the failure mode.
* **A JV date pass of its own**, with a day pattern that may include Sunday (§0.7).
* **Reader surface — small, but must be complete.** Four SQL readers of
  `world_jhsaa_dual` (world.py:3888 `jhsaa_underplayed`, :3942 `_schedule_rows`, :4170
  `jhsaa_match_dates`, :5037 `jhsaa_history_rows`) plus `research_export.py:62`; about
  eight in-memory `t.schedule` readers (`rating_duals` jhsaa.py:3156, `_district_duals`
  :2998, `district_oowp` :3014, the non-district `spent` tally :4487,
  `_flat_format_profile` :5015, `_last_opponent` :3699).
* **‼️ The one that bites silently:** `_jh_line_records` (web/state.py:3626) builds a
  player's season record by **matching NAMES inside the archived `lines`** of that
  school's card. Miss it and JV lines merge into the varsity player card with no error
  anywhere — the same name-keying fragility already flagged for family ties.
* **Ties** — §5.
* **`ROSTER_FLOOR` 12 → 16** — §3.
* **The band comment.** `ROSTER_SIZE_BAND_BY_CLASS` (jhsaa.py:193) says the bands are
  deep *because* "varsity AND a JV feeder blur into one deeper roster here, since the
  association has no separate JV system to model with." That rationale is now spent.
* **The showcase reuse.** `showcase_schedule` currently draws tiers off a provisional
  mid-season rank and allots 1–3 events per program; the JV version needs **exactly one
  per program** and must not count against the 16.

**What the JV does NOT fix:** throttling. **46% of side-appearances** have the school's
own depth cut down by a thinner opponent, and the 12-player cap means a 25-roster
program still dresses only 23. Ranks ~20+ are the residual. That is the price of the
elastic table taking the smaller side, and it is the right price.

---

## 8a. ‼️ What "don't archive JV match data" costs — THERE IS NO LIVE SEASON

Decision §0.12 says JV match data is not archived. Decision §0.10 says the school page
carries a JV tab showing that program's **JV schedule**, and an earlier decision put a
JV tab on the **player** page. Those cannot all hold, for a reason specific to this
association:

**‼️ THE JHSAA HAS NO LIVE SEASON TO READ.** The whole thing runs in one rung at world
week 0 and every surface — hub, standings, school page, player card, rankings, brackets
— reads `world_jhsaa` / `world_jhsaa_dual`. `run_season`'s `_season_cache` is an
in-process memo, not persistence: it dies on restart and is keyed on salt/year/override
fingerprints. So a JV dual that is not written to the archive **cannot be displayed at
all** — not next season, and not the day it is played. The only way to show it would be
to re-simulate on a page request, which is precisely the fault
`docs/AAR-jhsaa-research-export-resimulation-hang.md` exists to prevent.

So the choice is what to write, and it is a three-way, not a yes/no:

| | what persists | what the pages can show | **cost/season** (both genders) |
|---|---|---|---|
| **A** — full rows | dual + per-court `lines` | JV schedule · JV record · **JV player tab** (per-court W-L by name) | **15.3 MB** |
| **B** — rows, `lines=[]` | dual only (opp, home, phase, pf/pa, won) | JV schedule · JV record · **no player tab** | **2.6 MB** |
| **C** — record only | a `jvrecord` field on the existing standings rows | **JV record only — no schedule anywhere** | **0.07 MB** |

Varsity today is 40.0 MB/season by the same measure (MEASURED: 22,983 duals, mean 875
bytes of `lines` JSON per dual, stored twice because a dual sits on both schools'
schedules).

**B is almost certainly what §0.12 means.** "Match data" naturally reads as the
per-court detail — the thing that is genuinely voluminous — and dropping it kills only
the JV *player* tab. The JV *schedule* survives, at 6% of the cost of A and ~6.5% of
what varsity already spends. C is the literal reading and it retires the JV schedule
tab that §0.10 asks for.

**C is trivially easy either way**, which answers the "only if it can be done easily"
condition: the JV record rides on the standings rows already in `world_jhsaa`'s summary
blob (beside `record` / `drecord` / `place` / `pi`), so it needs **no new table, no new
read, and no new query** — the program page and its season-by-season history already
walk exactly those rows. Note it must be STORED rather than derived, which is the one
place this feature legitimately departs from the "a fold, not a store" rule
(`jhsaa_school_history`): with no JV duals archived there is nothing to fold.

Under B or C, `jhsaa_underplayed` keeps counting varsity appearances only for free —
it counts names inside `lines`, and JV rows carry none.

---

## 9. Open questions

1. **The boys' JV calendar** — confirm the month-offset reading in §4 (Aug
   invitationals / Sep league / Oct showcase), or state the real intent. The 2038 data
   supports it: every boys' early-window dual falls in August, exactly parallel to the
   girls' March, so "month 1 = the 5S/2D window, month 2 = JV opens" holds on both
   calendars.
2. ~~`ROSTER_FLOOR` 15 or 16~~ — settled: **16**, so every program can field a JV.
3. **‼️ A, B or C in §8a?** Decision §0.12 (no archived JV match data) and decision
   §0.10 (a JV schedule tab) cannot both hold, because the JHSAA has no live season to
   read from. B keeps the JV schedule and drops the per-court detail for 2.6 MB a
   season; C is the literal reading and retires the schedule tab. This is the last
   blocking decision.
4. **If B: does a JV schedule row show a SCORE?** A dual-level `pf-pa` (5-2) comes
   free with the row; OSAA mostly shows a bare "Done". Per-court scorelines are the
   thing B drops.
5. ~~JV opponent suffix~~ — settled: `San Borrego (JV)`, parentheses.
6. **Invitational pairing rule** — the §2 model pairs within one classification and
   prefers the same area. Same rule as varsity's `_nondistrict_pairs` (geography then
   talent), or simpler?

---

## Appendix — method

* Real-save figures read directly from `programs.csv`, `players.csv`, `duals.csv`,
  `line_players.csv`, `jhsaa_standings.csv`. Match counts are `line_players.csv` rows
  per `player_id` — the same appearance-by-line basis `_jh_line_records` and
  `jhsaa_underplayed` use.
* Roster ability order is `players.csv` by `current_grade` descending — the seed
  `jhsaa._order` starts from, before results move it.
* The §2 model plays a single round robin inside each existing `(classification,
  district)`, capped at 16 per program, then fills remaining slots with invitational
  pairings within one classification, preferring the same area. Format is the smaller
  side's capacity capped at 12. Floor-raised programs contribute new players with no
  prior match count.
* Season timing and per-dual cost: `jhsaa.run_season("girls", 0)` on a throwaway DB,
  plus a direct `play_dual` microbenchmark over 9A/8A teams with a prototyped
  `DualFormat(2, 3, False)`.
* Generated-roster comparison: `build_roster` at world years 0 and 13 under two salts,
  to separate save-specific drift from year-to-year noise.
* The payoff projection is arithmetic, not a simulation. It does not model rest days
  shrinking the JV pool, JV bench rotation, or the May showcase — the first would lower
  the numbers slightly, the other two would raise them.

# BRIEF — a concurrent JHSAA JV season: feasibility

**Status: INVESTIGATION ONLY. Nothing is built, no code changed, no tests written.**

**Everything labelled MEASURED comes from the real 2038 save** (research exports
`playtoclinchjhsaa2038boys` / `…girls` — 864 girls' and 780 boys' programs, 31,766
players, 21,419 duals, 446k line appearances). GENERATED means `jhsaa.build_roster`
on a synthetic world, used only where the real save cannot answer. PROJECTED means
arithmetic on top of the real save — clearly derived, not simulated.

---

## 0. Owner decisions already taken (2026-08)

These are settled and the rest of this brief is written under them.

1. **The JV lineup is ELASTIC — fit to what the school has that day, never dogmatic.**

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

2. **Ties are accepted.** Even-court formats can draw; broken on sets, then games,
   and **a dual still level after that is a TIE**. This is the association's first tie
   — nothing in `jhsaa` has tie logic today, by explicit design.
3. **A roster is not a lineup.** JV is a *daily slice of one ladder*, not a standing
   squad: whoever sits below the varsity lineup that day is JV. If varsity rests two
   starters, #12 and #13 move up and JV starts at #14. Porousness is therefore
   structural, not a feature to add.
4. **No Varsity 2.** Dropped — see §6 for why the numbers agreed.
5. **JV has its own `TeamSeason` and its own page.** Standings and player pages get a
   **JV tab** alongside varsity; a player with no JV results has an empty tab.
6. **JV counts for nothing.** No TOSS, no rankings, no awards, no seeding, no
   postseason. Varsity is untouched.
7. **JV season capped at ~16 duals.**
8. **Scheduling is flexible** — mirror the varsity opponent, or give JV its own
   districts; whichever is easier. The only requirement is opponents **near their own
   class**, plus **JV showcase events** for out-of-class play.
9. `world.jhsaa_underplayed` stays as it is (varsity appearances only).
10. `_rest_count` (weak-opponent starter resting) stays — it is realistic to use these
    players in varsity duals sometimes.

---

## 1. The problem, measured

**MEASURED — matches actually played in 2038, by roster rank** (rank ordered by
matches played, i.e. effective usage, not the seeded ladder):

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

Two consequences worth naming. **~750 seniors a gender reach the college hand-off with
no résumé** — `graduating_class` writes `Prospect.jhsaa` off `ts.records`, so they
arrive on the recruit board at 0-0. And zero-match players are not all filler: their
median `current_grade` is 30/33 against a population median of 38/41, but the tail
reaches 60/65.

---

## 2. ‼️ The elastic format is the whole ballgame

A fixed JV format has to be fielded by **both** schools, so its reach is the *product*
of two roster constraints, and it collapses. The elastic table has no such product:
the format simply drops to whatever the thinner side can dress, so a dual happens
whenever both sides have **five spare players**.

**MEASURED — programs that can field a JV at all (roster ≥ 16):**

| | girls | boys |
|---|---|---|
| can field any JV | **759 of 864 (88%)** | **691 of 780 (89%)** |
| by class (girls) | 9A 89/92 · 8A 80/87 · 7A 87/95 · 6A 107/114 · 5A 88/102 · 4A 81/103 · 3A 71/95 · 2A 76/95 · **1A 80/81** | |
| spare players (roster − 11) | median 8, p90 13, max 22 | median 9, p90 14, max 25 |

Compare against fixed formats, measured on the same save as a share of **real league
dates where both sides could field**: 3S/4D 7–9% · 2S/3D 32–36% · 2S/2D 61–64% ·
1S/2D 78–79%. The elastic table replaces all of that with **88–89% of programs, and a
dual whenever both sides clear five**.

Note 1A: 80 of 81 girls' programs can field a JV — the *highest* rate in the state.
See §3.

### PROJECTED payoff

Model: JV lineup = the players below varsity's 11, by ability; format = the **smaller**
side's capacity, capped at 12; each JV player takes one line per dual; 16-dual cap.

| scenario | JV duals | card/program | **zero-match** | **≤5 matches** |
|---|---|---|---|---|
| girls — baseline | — | — | 8.2% | **40.8%** |
| **A: JV plays the varsity opponent's JV** | 5,806 | median 16 | **0.9%** | **5.7%** |
| B: JV plays its own same-class league | 5,430 | median 16 | 1.5% | 9.0% |
| boys — baseline | — | — | 9.8% | **42.3%** |
| **A: mirror the varsity opponent** | 5,231 | median 16 | **1.2%** | **6.1%** |
| B: own same-class league | 4,914 | median 16 | 2.0% | 9.4% |

**The problem goes away.** 41% of the state at ≤5 matches becomes 6%.

**Scenario A wins on every axis** and should be the default: it is more complete (5.7%
vs 9.0%), it needs no new league structure, its opponents are already class-appropriate
(district play is same-class, invitationals are ±1), and — see §5 — **the dates come
free**. Scenario B loses ground only because own-class league blocks strand small pools
in thin classes. Showcases can be added to either for out-of-class play.

The **16-dual cap binds, feasibility does not**: 707 of 759 JV-capable girls' programs
have ≥16 eligible dates on their varsity card. So the design question is not "can they
find games", it is **which 16**.

---

## 3. Roster depth: the real save is not the design bands

**MEASURED (real 2038) vs GENERATED (`build_roster`, medians stable across world years
0 and 13 under two salts):**

| class | `ROSTER_SIZE_BAND_BY_CLASS` | generated median | **real 2038 median (g/b)** | real min (g) |
|---|---|---|---|---|
| 9A | 20–24 | 22 | 22 / 22 | 14 |
| 8A | 20–24 | 22 | 20 / 22 | 12 |
| 7A | 19–22 | 20 | 19 / 21 | 12 |
| 6A | 19–22 | 20 | 20 / 20 | 14 |
| 5A | 18–20 | 19 | 18 / 18 | 13 |
| 4A | 18–20 | 19 | 18 / 18 | 12 |
| 3A | 17–19 | 18 | 17 / 18 | 12 |
| 2A | 15–17 | 16 | **18 / 17** | 13 |
| 1A | 14–16 | 15 | **19 / 19** | **15** |

1A and 2A run **3–4 players deeper than the generator produces**, and 1A's *minimum*
(15) sits above its generated median. Big classes are on band. The likely cause is the
documented one — the portal appends without a check and the owner reallocates by hand
(`ROSTER_SIZE_BAND_BY_CLASS`'s "no ceiling, deliberately") — but this brief does not
prove it. It is why 1A has the state's best JV coverage, and it means **JV feasibility
rests on real depth, not on the bands**.

---

## 4. ‼️ Ties are a third of the JV season, not a corner case

**MEASURED format mix over the projected slate** (scenario A):

| format | courts | girls | boys |
|---|---:|---:|---:|
| 2S/2D | **4 — even** | 23% | 17% |
| 1S/2D | 3 | 22% | 19% |
| 3S/2D | 5 | 15% | 19% |
| 2S/3D | 5 | 14% | 14% |
| 3S/3D | **6 — even** | 12% | 10% |
| 4S/3D | 7 | 6% | 10% |
| 4S/4D | **8 — even** | 5% | 6% |
| 3S/4D | 7 | 3% | 4% |
| **even-court total (a tie is possible)** | | **40%** | **33–34%** |

So this is not "build ties for the rare 4S/4D". A third to two-fifths of every JV dual
can end level, and the most common single format (2S/2D) is one of them. What that
implies:

* `TeamSeason` carries `wins`/`losses` only — a JV one needs `ties`, and `record`
  becomes `W-L-T`.
* The tiebreak ladder (sets → games → tie) has no implementation anywhere.
  `jhsaa._games` already parses games out of an archived score string; **sets are not
  counted anywhere** and would be new.
* `world_jhsaa_dual.won` is an INTEGER boolean — a tie has no representation in the
  archive.
* Everything downstream that computes a win % (`win_pct`, `district_pct`) assumes
  `wins + losses` is the denominator.

None of this is hard. It is just genuinely new, and it is the one place where "JV
counts for nothing" does not spare us work.

**Escape hatch if you want it:** every even format has an odd alternative at the same
player count (6 → 4S/1D, 9 → 5S/2D, 12 → 6S/3D), which would remove ties entirely.
Flagged, not recommended — the table as written is more tennis-like.

---

## 5. What is cheap

**One ladder, two lineups.** `_order(ts)` already produces the ranked ladder and
`_lineup` already slices it: varsity takes 11 (after `_rest_count` shifts and
`_ROTATE_*` swaps), JV takes what is left. Decision 3 falls out of the existing code
almost for free — JV is a second slice of the same `_order` call, not a second ladder.

**The dual format is already data.** `DualFormat(n_singles=S, n_doubles=D,
doubles_team_point=False)` — the whole elastic table is eight tuples. `FLIGHT_WEIGHTS`
already carries S1–S5 and D1–D4, which covers every cell.

**The dates are free in scenario A.** `jhsaa_match_dates` packs duals into rounds; if
a JV dual takes its varsity dual's date — which is what really happens, same afternoon
— it needs **zero extra rounds**, so no pressure on the fitted Oct-31 / Jun-7 window
(`_JH_SEASON_CLOSE`) and no risk of tripping `_jh_pattern` into a denser day pattern.
Scenario B would need its own rounds and would push on that window.

**MEASURED cost.** A gender's season today is **146.6s / 12,271 duals** — the rung is
~5 minutes for both genders, not the 19s in `DESIGN-jhsaa-high-school-season.md:280`,
which is badly stale. Per-dual: 3S/4D regular 10.44 ms, 1S/4D 9.93 ms, 5S/2D 7.25 ms,
prototyped 2S/3D 8.25 ms. The projected JV slate averages **4.8 courts**, so ~7.9 ms ×
5,800 duals ≈ **+46s/gender**. **Rung ~5 min → ~6.5 min.**

---

## 6. Why Varsity 2 was dropped (and the numbers agreed)

**MEASURED, real 2038 rosters** — programs by roster threshold:

| roster ≥ | statewide (g/b) | 9A/8A/7A only (g/b) |
|---|---|---|
| 26 | 45 / 55 | 37 / 40 |
| **27** (the proposed line) | **28 / 33** | **22 / 25** |
| 28 | 19 / 21 | 13 / 15 |
| 30 | 3 / 8 | 3 / 8 |

Two dozen programs a gender, and **fragile**: 28 halves it, 30 kills it. The proposed
27 is also benchless arithmetic — 27 = 11 + 8 + 8 leaves varsity with no spare, which
is exactly what `ROSTER_FLOOR = 12` exists to guarantee and what `_rest_count` and
`_ROTATE_*` need to move. And a V2 is not a school: every surface here keys on a unique
display name (`world_jhsaa_dual.school`, the routes, the pids, the crest lookup,
`_jh_school_groups`), so a V2 appearing as an opponent on a 3A program's card would
404 its program page and blank its crest, quietly.

The elastic JV reaches 88% of programs and takes ≤5-match players from 41% to 6%. V2
would have added ~25 programs a gender for the largest structural cost in the proposal.
Correctly dropped.

---

## 7. What still needs building

* **A `level` axis on the archive.** `world_jhsaa_dual` (world.py:213) has none. It
  must be a level, **not a phase** — phase is the archive's identity for an EVENT and
  it selects the dual format and the postseason lane, but JV plays inside `early` and
  `regular` alike. There is an `ALTER TABLE` idiom already (world.py:264).
* **‼️ `jh_match_key` will break silently.** It is `(phase, district, home, away)`
  (world.py:4024). A JV dual against the same opponent in the same phase yields the
  **identical key**, which puts a self-edge into `_jh_global_order`'s topological sort,
  drops it into its cycle fallback, and quietly degrades the whole gender's display
  calendar. Level has to be in the key.
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
* **Ties** — see §4.
* **The 16-dual selection rule.** The cap binds for 93% of JV-capable programs, so
  *which* 16 is a real decision. Taking the first 16 in play order (what the projection
  models) ends a program's JV season in mid-March.
* **The band comment.** `ROSTER_SIZE_BAND_BY_CLASS` (jhsaa.py:193) says the bands are
  deep *because* "varsity AND a JV feeder blur into one deeper roster here, since the
  association has no separate JV system to model with." That rationale is now spent
  and the comment should be rewritten, whatever the bands end up doing.

**What the JV does NOT fix:** throttling. **46% of side-appearances** have the school's
own depth cut down by a thinner opponent, and a 12-player JV cap means a 25-roster
program still dresses only 23 of its players. Ranks ~20+ remain the residual — 65–100
players per rank still at ≤5 matches. That is the price of the elastic table choosing
the smaller side, and it is almost certainly the right price.

---

## 8. Open questions

1. **Does a JV result move the ladder?** `ladder_score` is `ovr + LADDER_SWING ×
   (pct − ½) × n/(n + LADDER_PRIOR)`, read off `ts.records`. With JV on its own
   `TeamSeason`, the varsity ladder never sees JV form, so a JV player can only climb
   on ability — which is not really porous. If JV wins *do* feed it, JV results are
   deciding varsity lineups, which brushes against "JV counts for nothing". This is the
   single biggest unresolved design point.
2. **What does "available that day" mean?** The JHSAA has no injuries and no absence
   model, so available = roster − varsity's 11 − rested starters, which is **constant
   all season**: a 19-roster program would play 2S/3D in every JV dual it ever plays,
   and all the observed elasticity comes from the *opponent*. Do you want real
   day-to-day availability variance (a new mechanic, and the association's first
   non-determinism), or is per-program-constant fine?
3. **Format = the smaller side's capacity?** Assumed throughout. Confirm — the
   alternative (bigger school plays its shape, thin school forfeits lines) is worse but
   it is a choice.
4. **Which 16?** First 16 chronologically, evenly spread across the season, or
   district dates first with invitationals filling in?
5. **Ties: recorded as `W-L-T`, or something else on the page?** And does a JV tie
   need to be distinguishable in the archive from a JV dual that was not played?
6. **Development.** "It can be part of development if that matters" — flagging that
   **today no JHSAA result affects any player's development at all**, varsity results
   included. `_dev_maturity` rolls a four-year trajectory at entry and `build_roster`
   regenerates deterministically, so results→growth would be a separate and much larger
   feature needing persisted per-player state. Confirm that is understood and out of
   scope for now.
7. **JV showcases** — reuse the varsity showcase machinery (`showcase_schedule`, tiers,
   pod/tiered), or something simpler? And do showcase duals count against the 16?
8. **Does JV have district standings**, or only a program's overall JV record? A JV tab
   showing a league table implies a JV district place, which is one step from a
   standing nobody wanted.

---

## Appendix — method

* Real-save figures read directly from `programs.csv`, `players.csv`, `duals.csv`,
  `line_players.csv`, `jhsaa_standings.csv`. Match counts are `line_players.csv` rows
  per `player_id` — the same appearance-by-line basis `_jh_line_records` and
  `jhsaa_underplayed` use.
* Roster ability order is `players.csv` by `current_grade` descending — the seed
  `jhsaa._order` starts from, before results move it.
* Scenario A plays a JV dual on every real `regular`/`early` varsity dual where both
  sides have ≥5 spare, in archive order, until either side hits 16. Scenario B groups
  JV-capable programs of one class into ~10-team blocks by area/county/district and
  plays a truncated double round robin to the same cap.
* Season timing and per-dual cost: `jhsaa.run_season("girls", 0)` on a throwaway DB,
  plus a direct `play_dual` microbenchmark over 9A/8A teams with a prototyped
  `DualFormat(2, 3, False)`.
* Generated-roster comparison: `build_roster` at world years 0 and 13 under two salts,
  to separate save-specific drift from year-to-year noise.
* The payoff projection is arithmetic, not a simulation. It does not model rest days
  shrinking the JV pool, JV bench rotation, or JV showcases — the first would lower the
  numbers slightly, the other two would raise them.

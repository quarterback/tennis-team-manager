# AAR — Conference realignment, a 96-team D1 bracket, and a UTR-true talent scale

A single arc this session: reshape the college landscape (conferences + which
programs play where), grow the D1 national tournament to fit it, and then fix
the thing that made every match feel like a coin flip — the talent scale —
by calibrating it to real UTR.

## 1. Conference realignment (data/ncaa/*.json)
A long run of user-directed moves rebuilt the map. Every step was validated to
keep each division's rosters summing correctly with no school double-listed.

**New / revived leagues**
- **Pac-16** — revived the classic Pac twelve + Boise State, Colorado State,
  Gonzaga, San Diego State; power-tier prestige, back in the P5 display set.
- **Yankee Conference** — BC, Syracuse, Rutgers, Pitt, West Virginia, Virginia
  Tech, Louisville, Temple, Notre Dame, UConn, Penn State (Cincinnati later to
  the ACC). Strong mid-major prestige.
- **Heritage League** — the merged SWAC + MEAC (HBCU) conference.
- **Constellation Intercollegiate Conference (CIC)** — the renamed American.
- **Meridian League** — a fun, non-geographic group: five upstate-NY D1-hockey
  schools (Clarkson, RPI, Union, St. Lawrence, RIT) promoted from D3 + Minnesota
  State, Grand Valley State, Bemidji State, Michigan Tech (D2) and Rowan (D3).

**Cross-division promotions** — University of Chicago (D3→D1 Big Ten); the UAA
plus Colorado College (D3→D1, 8-team academic league); Johns Hopkins (D3→Big
Ten); Occidental (D3→WCC); Tampa, Valdosta State, Rollins (D2→D1 ASUN); Alaska
Anchorage (D2→D1 WAC).

**Geographic cleanups** — Chicago State out of the NEC to the Horizon; NJIT to
the NEC; Sacramento State out of CUSA to the WAC; the WAC's Deep-South / KY-TN /
Arkansas misfits sent to the ASUN / OVC / Southland, with Utah Valley + Southern
Utah + Utah Tech pulled in (which also made the Big West all-California). Plus a
data fix: "Massachusetts" and "UMass" were the same school listed twice —
collapsed into one (UMass, to the CIC), and a pre-existing Rochester
double-listing was cleaned up on promotion. The thinned Liberty League remnant
was merged into the NESCAC.

**Final shape:** D1 = 34 conferences / 390 schools; D2 = 287; D3 = 407.

## 2. Realistic schedules (app/seasonmode.py)
Rebuilt the regular-season generator so every team plays toward a **25-dual**
slate that's **~60% conference**. Conferences under 10 teams play a double
round-robin; bigger ones a single round-robin, padded with extra
intra-conference duals where needed to hit the share; non-conference fills the
rest. The old random-dart non-conf matcher (which left teams short — league
averaged ~17 duals) was replaced by a deterministic greedy that reliably fills
each team's target, keeping the cupcake-scheduling flavor as a preference rather
than a hard reject. Conference play is gated behind each team's own last
non-conf week (not a global barrier) and up to a 3-dual week is allowed, so the
season packs into ~12 weeks.

## 3. A 96-team D1 NCAA tournament with a play-in (app/bracket.py, seasonmode.py)
With 34 autobid conferences, a 64 field was almost all AQs. D1 now seats **96**
(D2/D3 stay 64). The live engine only ran clean power-of-two brackets, so a
play-in was added: the **top 32 seeds (by Power Index) get byes**, the lowest 64
(seeds 33–96) play a First Round, and the winners join the byes for the 64-team
main draw. Seeding is pure Power Index, so the play-in is simply the weakest 64
of the field — a mix of low-major autobid champions and bubble at-large teams —
exactly how the real First Four works.

## 4. The big one: a UTR-true talent scale (app/ncaa.py)
**The problem.** On-court strength derived from a *compressed* strength→talent
slope: the whole conference-prestige band collapsed into ~5 talent points, so
matches were near coin-flips and no team was clearly better than another.

**The journey.** Widening the slope helped, but exposed a second issue — the
talent sat jammed in the top of the 20–80 scouting scale, and on the UTR mapping
(`grade 20 ≈ UTR 1.0`, `grade 80 ≈ UTR 16.5`, ~0.26 UTR/grade) ordinary college
teams were landing near **Grand Slam level**. UTR 16.5 is a Slam-caliber pro;
the best college players in the country today are only ~**14.3** (men) and
~**11.5** (women), all bunched within a fraction of a UTR with the **decimals**
doing the differentiating.

**The fix (calibrated to real UTR ladders).**
- Lowered the division bases and kept a wide spread so talent uses the *whole*
  scale, with realistic cross-division overlap at the edges.
- **Tightened the within-conference draw** (gauss SD 0.11 → 0.06) so programs
  cluster near their conference prior — the top of the field stays a *tight
  band* instead of spraying into pro range. Variety among similar players now
  comes from the STR rating's decimals through play, not big talent gaps.

**Result (player UTR vs. the real ladder):**

| | top | 99th | median | floor |
|---|---|---|---|---|
| Men D1 | 14.3 | 13.2 | 8.5 | 4.3 |
| Men D2 | 9.3 | 8.3 | 5.6 | 2.0 |
| Men D3 | 8.1 | 7.0 | 4.1 | 2.0 |
| Women D1 | 11.7 | 11.0 | 6.7 | 2.3 |
| Women D2 | 7.6 | 6.6 | 4.1 | 2.0 |
| Women D3 | 6.3 | 5.1 | 2.6 | 2.0 |

Men top **14.3** and women top **11.7** match the real data; nobody hits the
Grand Slam ceiling; average D3 / a bad D2 sit at ~**UTR 3–4**. The STR↔UTR map
is unified (1 UTR ≈ 1.68 STR), so women read up to ~STR 49 at the very top —
calibrated to the pasted UTR ladders rather than to an STR target.

**Calibration reference (grade → STR → UTR):**
`UTR = 1.0 + (grade − 20) × 0.2583`; `STR = 31 + (grade − 20) × 26/60`. So grade
50 ≈ STR 44 ≈ UTR 8.8; grade 70 ≈ STR 53 ≈ UTR 14.

## Prestige, decoupled
Worth recording: **on-court strength** (the `_TALENT` bases/spread + the
conference strength prior) is separate from **recruiting prestige** (the
`DIVISION_PRESTIGE` + `CONF_PRESTIGE` + per-school bumps that decide where talent
signs). All the talent-scale work above moved strength only; the recruiting
tiers tuned in earlier sessions were left intact. The elite academic D3s were
also given a clear recruiting-prestige tier so they read as the "power programs"
of that level.

## Verification
- Every realignment step: rosters sum per division, no double-listing, both
  genders load.
- A full D1 season runs the 96-team play-in → Round of 64 → … → Final to a
  crowned champion; D2/D3 run a clean 64.
- League-wide schedule check: every team plays exactly 25 duals, ~60%
  conference, ~12-week season.
- Talent: player-UTR distributions measured against the real men's/women's
  college ladders (above).
- Test suites green (season, seasonmode, world model, recruiting). The old
  `test_higher_seeds_usually_advance` was reframed to `test_bracket_is_not_pure_noise`
  — we want the *best* team to win, and a high seed losing is fine; the test now
  only guards against a pure coin-flip bracket.

## Files
- `data/ncaa/d1_*.json`, `d2_*`, `d3_*` — all realignment + promotions.
- `app/ncaa.py` — conference prestige priors; `_TALENT` bases/spread;
  `_latent_strength` within-conf SD; D3 academic recruiting tier.
- `app/bracket.py` — `field_for_division` (D1=96, else 64).
- `app/seasonmode.py` — 25-dual conference-heavy scheduler; the play-in
  (`_ncaa_seeds`, `_advance_ncaa_round`) and field-size threading.
- `app/web/state.py`, `server.py` — bracket views default to the division field.
- `tests/test_season.py` — reframed bracket test.

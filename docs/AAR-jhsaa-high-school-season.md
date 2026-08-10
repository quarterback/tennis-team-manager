# AAR — The JHSAA: a simulated high-school season inside the college sim

## Context

The Jefferson integration (`docs/AAR-jefferson-state-integration.md`) made the fictional
state a first-class recruiting state, but its recruits were invented names. The owner's
actual want was immersion — follow Jefferson the way you follow the colleges, watch a kid
play four years at a real school, then sign them — plus a live high-school league to test
the `cheesybook` tool against, since real Oregon HS tennis can't be simulated.

So the JHSAA (Jefferson High School Activities Association) is now a real, simulated,
browsable league: ~335 girls' and ~292 boys' programs, 57 districts, ten state
tournaments, awards, archives, and a graduating class that IS Jefferson's entry into the
college recruit rankings. Design record: `docs/DESIGN-jhsaa-high-school-season.md`.
This AAR records what was learned building it.

## What exists

| Piece | Where |
|---|---|
| Schools + districts data | `data/jhsaa/schools.json`, built by `scripts/import_jhsaa.py` |
| Season engine (rosters, duals, districts, state, awards) | `app/jhsaa.py` |
| Generated SVG crests (ported from prep-network) | `app/jhsaa_marks.py` |
| The advance-ladder rung + archive | `world.run_jhsaa` / `world_jhsaa` / `world_jhsaa_dual` |
| Recruit hand-off | `jhsaa.apply_to_class`, called in `world.recruit_class` |
| UI | `/jhsaa` hub, `/jhsaa/school/<name>`, `/jhsaa/champions`; High School panels on recruit + player pages |

Owner rules baked in: **5S/2D** regular season, **1S/4D** state tournament, every match
to completion, no clinch; both totals odd so a tie is structurally impossible. Season
limit **28–33 duals**, postseason exempt. Fields 32/24/24/16/8 with 7A taking the top
two per district. Grades 9–12 only. High school runs at `fast` fidelity.

## The run of it

The rung fires at **week 0, before anything college** — deliberately not gated on
`year > 0`, so a brand-new save plays the high-school season before its first college
dual and the seniors are on the board when recruiting opens. It marks itself done by the
`world_jhsaa` rows it writes, the cups' pattern. ~19s for both genders.

Jefferson recruits then compete on **both** résumés: the identity swap leaves them
ordinary members of the national class, so `board_class` gives them junior-circuit
tournaments like anyone else. Measured 134 of 202 carrying a JHSAA record AND a junior
draw history. (This was assumed impossible during design; it needed zero work.)

## Lessons — each of these cost real time

1. **`DualResult.winner` is an int (0 home, 1 away).** Comparing it to `"home"` credited
   the away side of every dual, leaving every team in a home-and-home round-robin at
   exactly .500 with plausible point differentials. Eleven teams all 10-10 is the tell.

2. **`talent` on `generate_prospect` is the CEILING, not current.** Current is
   maturity-derived. So high-school talent bands look absurdly high next to the college
   `_TALENT` means (which ARE current) — a 7A band of 58 yields kids who PLAY at ~30.
   Maturity is the aging model too: `_MATURITY` 0.40→0.78 across grades 9–12 is why the
   same player's current rises every season. Do not "fix" the bands downward.

3. **A career is a keying decision, not a persistence feature.** Rosters keyed on the
   season being played regenerate strangers every year. Keyed on the year the player
   ENTERED, the same person carries one pid/name/ceiling through four years and matures —
   and nothing needs storing, because the career rebuilds deterministically
   (`jhsaa.career`, ~16ms).

4. **The hand-off swaps IDENTITY ONLY.** Copying graduates' grades onto their recruit
   slots re-calibrated the national board — Jefferson's median recruit hit #278 of 2,500.
   The national class decides how many Jefferson recruits exist and their talent spread;
   the JHSAA decides who they are and what they did. Verified byte-identical ability
   curve and pids after the swap.

5. **`Prospect.jhsaa` must be a real dataclass field.** `world.prospect_to_dict` is
   `asdict()`; an ad-hoc attribute silently vanishes the moment a recruit signs — the
   entire high-school past, gone. Field now; survives signing, JSON, `world_roster`.

6. **`fast` fidelity for high school, always.** Full point-by-point resolution made the
   first recruit-class build a 103-second request-thread operation — the documented
   outage class. Fast is 6.7× cheaper and changes no winner, score, or individual
   record. 103s → 19s, measured. The college season keeps `full`.

7. **`season.dual_between` is NOT reusable for a new league.** It hard-wires
   `dual_fmt=ncaa.dual_format(a.division)` (unknown division → silent 6S/3D fallback)
   and only enables `play_all` for D3/D4. `jhsaa.play_dual` calls
   `engine.dual.simulate_dual` directly. The ENGINE is the reusable layer; the college
   season helpers are not. Likewise `bracket.build_bracket` / `Matchup.bye` do not
   exist — `run_state` runs its own draw with `None`-slot byes.

8. **prep-network's sponsorship flags are a generator artifact.** Boys- and girls-tennis
   were rolled independently per school (202/441, only 117 both, 20 one-team leagues).
   Re-derived: girls the superset, boys an ~88% subset — 335/292, 43 girls-only, none
   boys-only. And its 99 all-sport conferences span classifications, so tennis draws its
   own district map (per classification, ≤12, contiguous, named from areas/counties).

9. **Individual awards need per-line attribution at dual time.** `_credit` books every
   line's result to the players `_squad` dressed — the same indexing, never a second
   opinion. That record is what All-District / All-State / POY rank on, and what a
   recruit's `record` field carries to college.

10. **Match-by-match belongs in its own table.** `world_jhsaa_dual` (~10k rows/gender/
    year, indexed by school) rather than a blob on the summary row — a school's schedule
    page reads its own rows and every summary read stays light.

## Archives — yes, like college

- **Past champions**: `/jhsaa/champions` — every archived year × classification, with
  Players of the Year. `world_jhsaa` accumulates a row per year per gender; nothing is
  overwritten.
- **School pages**: `/jhsaa/school/<name>` — crest, roster with grades, the season match
  by match (home/away, score, DIST/NON-DIST/STATE), and a **program history** of titles,
  state appearances and individual honours that grows on its own as years roll
  (`world.jhsaa_school_history`).
- **Players**: a Jefferson recruit's page shows the four-year career; a Jefferson
  college player's Journey panel shows school, district, record, honours and state
  titles for the rest of their career.

## Not done / future

- District tournaments (standings feed state selection directly; a bracket between
  district play and state is a small addition to `run_district`).
- JHSAA honours are not in the college Hall of Fame or awards archive — they live on
  player pages and the JHSAA pages only.
- The bench (seats 10–12) never plays; no rotation, so no award can reach them.
- `simulate_cross`-style interstate high-school play: out of scope, Jefferson is the
  only simulated association.

# AAR — One STR (results-based stat); OVR/attributes are card-only evaluation

**Date:** 2026-06-28
**Status:** ✅ Implemented. Branch `claude/tennis-sim-engine-tests-tpbdfx` (PR #119).
Sequel to `AAR-str-semantics-results-only-overall-static.md` (which unified the
Bureau/Lineup Lab on results STR). This round nailed down the owner's full model
and applied it to the **public surfaces and the player/recruit cards** — and
corrected a wrong turn made mid-stream.

## The model (owner, definitive)
- **STR is ONE number: the results-based, fluctuating performance rating** (like
  UTR). It is the universal stat, shown everywhere — leaderboards, rankings,
  profiles. It is *not* an indicator of talent per se; it's a performance metric
  that moves with how a player is actually doing.
- **The overall→STR conversion (`overall_to_str`) was never meant to be canonical.**
  It exists as an internal reference/seed only. There must never be two STR numbers.
- **OVR + attributes are ground-truth talent** (this is a simulation, so we *have*
  the truth). They answer "how good is this player really" and belong **only on the
  individual player/recruit card**, for evaluating that player — **never as a
  leaderboard column.** (In real life you'd reverse-engineer talent from STR; here
  we can show both.)

## The wrong turn (and the correction)
Mid-stream I over-applied "talent = OVR" and swapped OVR *onto leaderboards*
(recruiting board, the player profile's rank panel) and stripped STR there. That
inverted the intent. Owner: "OVR is just on player cards… it's not a leaderboard
metric. STR, like it's been shown, [stays] the stat." Reverted: leaderboards show
the **results STR**; OVR appears only on cards.

> Lesson for the next agent: "talent boards" still rank/display by **STR**. OVR is a
> *card* detail, not a ranking key. The only exception is the god-mode Bureau (below).

## What shipped
**Leaderboards / ranks → results STR:**
- `state.player_ranks` now ranks on and returns the **live results STR**
  (`season_player_str`), not the ability conversion. Unplayed players fall back to
  the ability prior (the same seed `converge_ids` blends toward), so early-season
  ranks ≈ talent and shift as matches accrue. The player-card panel is "STR Rating"
  again (results-based).
- Recruiting board (`recruiting.html`) and team recruiting (`team_recruiting.html`)
  show the recruit's **results-based junior-circuit STR** (`junior_str`) — the
  recruits' performance metric — not `str_value()` (ability) and not OVR. Shows "—"
  before any circuit results.

**Player/recruit cards → gain OVR for evaluation:**
- College player card (`player.html`): header now shows **OVR (+ ceiling)** beside
  STR, and a new **Attributes panel**. The page previously rendered from a
  lightweight pid-index dict, so it never had the grades — `_pid_index` now carries
  `overall`/`ceiling`, and the route fetches the Prospect (`ncaa.player_by_pid`) to
  build `scout_bars`. (Recruit cards already had attributes; the omission on player
  cards was incidental, not intentional — that was the owner's question.)
- Recruit card (`recruit.html`): hero leads with **OVR (+ ceiling)** and the
  match-based **junior STR** (no more `p.str_value()` ability STR). The
  CURRENT/DEPTH/4-YR breakdown reads in **OVERALL units** (`recruit_profile` stopped
  wrapping the scouting reads in `overall_to_str`).

**Internal-only:** `overall_to_str` survives solely as the `season_player_str`
prior and the unplayed-player fallback — never a displayed STR.

## The one judgment call: the Bureau
The Analytics Bureau / Lineup Lab show results STR **and** OVR (as a talent lens).
Left as-is: that tool's stated purpose is god-mode evaluation ("reads the engine's
hidden truth — every player's true talent ceiling"), which is exactly the owner's
use for OVR ("I want to see it for evaluating players"). If the Bureau should be
STR-only like the public leaderboards, that's a follow-up — flagged to the owner,
not assumed.

## Not changed (and why)
- Aggregate/internal `str_value()` uses — team-strength estimate (`state.py:228`),
  recruiting class-score formula (`:712`) — are computations, not displayed STR;
  left alone.
- God-mode editor surfaces (`editor_roster`, editor move list) show both overall
  and str; left as a management tool, like the Bureau.
- Career-by-season STR column already shows the recorded results STR.

## Validation
- Player, recruiting board, and recruit pages render 200 with the right fields
  (OVR header + Attributes + "STR Rating" panel on the player card; STR column on
  the recruiting board; OVR hero on the recruit card).
- Caught + fixed a `NameError` (missing `import app.world` in `player_ranks`) before
  it shipped.

## Footnote: the "database is locked" red herring
Every standalone repro in this session intermittently threw `sqlite3.OperationalError:
database is locked`. Root cause: parallel world-gen (`app/parallel.py`) spawns
`multiprocessing` workers that **re-import the running script**; unguarded repro
scripts re-ran their own top-level body in each worker, racing the DB. Fix is purely
in the test scripts — wrap the body in `if __name__ == "__main__":`. **No app code
was implicated.** Worth knowing for anyone writing throwaway scripts that touch
`world.get_or_create()`.

## Files touched
- `app/seasonmode.py` (`_pid_index` carries overall/ceiling),
  `app/web/state.py` (`player_ranks` → results STR; `recruit_profile` scouting reads
  → OVR units), `app/web/server.py` (player route fetches Prospect + scout_bars),
  `app/web/templates/{player,recruit,recruiting,team_recruiting}.html`.

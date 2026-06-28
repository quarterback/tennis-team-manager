# AAR — STR is results-only; OVERALL is the static talent number (two-STR defect)

**Date:** 2026-06-28
**Status:** ✅ **RESOLVED — implemented.** The "defect (current state)" section
below is the *pre-fix* state, kept for the record; see **Resolution** at the
bottom for what shipped. Branch `claude/tennis-sim-engine-tests-tpbdfx`.

## The realization (owner's call)
There should **not be two STR numbers**. There should be exactly two ratings, with
distinct jobs:

- **OVERALL** — the *static* "how good is this player" rating, derived from the
  attribute table (the 49 graded attributes → `current_overall`, 20–80). Stable,
  legible, correlated to STR but easier to reason about. This is talent.
- **STR** — the *dynamic* rating. UTR-style, **results-based**, noisy, recency-
  weighted, prone to who's hot / who's slumping / schedule / luck. STR was never
  meant to be a static readout of ability — that's what OVERALL is for. STR is
  supposed to move. It is, in the owner's words, "the only signal" for *form*.

The corollary: a player's *displayed* STR should come **only** from results
(`str_rating` / `season_player_str`). The ability→STR map (`overall_to_str`) must
be demoted to what it actually is — an internal **prior/seed**, never a number we
show as "STR."

## The defect (current state)
"STR" is shown to mean **two different things** on different surfaces, under one
label:

| Surface | What it shows as "STR" | Source |
|---|---|---|
| Rankings / live results views | **results STR** (dynamic) | `seasonmode.season_player_str(sid)` (`state.py:341,444`) |
| Lineups (coach AI) | **results STR** (dynamic) | `season_player_str` → `season.coach_lineup` ("results so far drive this week's lineups", `season.py:774`) |
| Analytics Bureau (Underplaced/Buried/etc.) | **ability prior** (static) | `scout_intel.scan`: `cur_str = overall_to_str(cur_o)` |
| Lineup Lab | **ability prior** (static) | same `scan` field |

So the engine **already computes and uses the real (results) STR** — it drives
lineups every week — but the god-mode analytics views surface the static
`overall_to_str` *seed* instead and call it "STR." That's why it looked like the
dynamic STR "wasn't anywhere": the owner was seeing the prior, not the rating.

This also **contradicts the design doc**, which already states STR is results-based:
`docs/match-engine-and-ratings.md` §3 — "STR is an output (it then orders lineups
and rankings); it does not feed match probability… results-based." The Bureau/Lineup
Lab implementation drifted from that.

## Why this is the right model (not just preference)
- **The match engine is driven by `overall`, not STR** (`engine/fast.py`: the hold
  probability is a logistic in the `overall` gap; STR never enters). So STR is free
  to be a pure *description of results* without affecting outcomes — exactly what a
  dynamic, form-tracking rating should be.
- **Results STR is already seeded by the ability prior** (`season_player_str` passes
  `priors = {pid: pr.str_value()}` into `converge_ids`). So OVERALL and STR are
  *correlated by construction* (thin/preseason records sit at the prior, then earn
  their way off it) — which is precisely the "correlated but STR moves" relationship
  the owner described. Keeping `overall_to_str` as the prior is correct; showing it
  as "STR" is the error.
- **Lineups should follow form.** You often start the hot hand over the nominally
  "better" player. The coach AI already does this (uses results STR); the analytics
  layer should reflect the same truth instead of a static talent readout.

## "true_str" is incoherent under this model
`scan` also exposes `true_str = overall_to_str(ceiling_overall)` — a *potential*
expressed as STR. A ceiling is a talent projection, not a results rating, so it
should be **potential OVERALL**, not a STR. Fold it into the OVERALL axis when this
is implemented.

## Direction for the eventual implementation (NOT yet done)
1. **Surface results STR** in the Bureau and Lineup Lab: plumb
   `season_player_str(sid)` into `scout_intel.scan` per (division, gender) — the
   per-division season + live STR map is already reachable
   (`web/state.get_season` / `season_player_str`; the Bureau iterates divisions
   already). Unplayed/preseason players fall back to the prior (≈ability) — expected.
2. **Show OVERALL** as the static talent number on those surfaces (the 20–80
   `current_overall`, the same scale as the attribute panel), and ship the
   **STR (form) ⇄ OVERALL (talent)** toggle the owner asked for on the Lineup Lab.
3. **Audit every "STR" label app-wide** and unify it on results STR. Anywhere a
   *static* number is wanted, use OVERALL.
4. **Demote `overall_to_str`** to prior/seed + preseason fallback only; it is never
   a user-facing "STR."
5. Re-express `true_str` as **potential OVERALL** (drop the potential-as-STR field).

## Caveats to handle at build time
- The Bureau is world-wide/cross-division god mode; results STR is per-season
  (per universe). scan must pull each universe's `season_player_str` and key its
  cache on results progress (the str cache already keys on count-of-finals, so it
  refreshes as duals complete — pair this with the roster-override stamp fix from
  `AAR-bureau-lineup-stale-after-fall-portal.md`).
- Preseason / brand-new recruits have no results → STR == prior. That's correct,
  but copy/UX should not imply they've "earned" it yet (reliability is already
  tracked by `str_rating`).

## Files implicated (for the future change — none changed here)
- `app/scout_intel.py` (`scan`: cur_str/true_str), `app/web/templates/intel_lineups.html`
  and the Bureau templates, `app/development.py` (`str_value`/`overall_to_str` role),
  `app/seasonmode.py` (`season_player_str`), `docs/match-engine-and-ratings.md` (§3,
  reconcile once code matches).

---

## Resolution (implemented)
The "two STR numbers" defect is gone. The single rule now holds across the Bureau
and Lineup Lab: **STR = live results (`season_player_str`); talent = OVERALL (20–80);
`overall_to_str` is only a seed/preseason fallback, never a displayed "STR."**

**`scout_intel.scan`** now pulls each division's live results STR
(`season_player_str` for that (division, gender) season) and carries it on every
`Intel` as `live_str` (+ `live_rel`). The `Intel` STR-from-ability fields
(`cur_str`/`true_str`/`upside`) were removed; talent is carried by `cur_overall`/
`true_overall`/`ovr_upside`. Unplayed players fall back to the ability prior (which
is also the seed `converge_ids` blends toward), so STR == "talent so far" until
results accumulate. The displayed singles **ladder now orders by live STR (form)** —
the same signal the coach AI sets lineups by — so the Lineup Lab mirrors who'd
actually play, not a static talent order. (The program-level metric behind the
"deserved program" ladder stays on OVERALL — it's a talent comparison.)

**Surfaces:**
- *Underplaced board* — **TALENT** = OVERALL ceiling (20–80); **STR** = live results
  (the column whose label already promised "this season's results").
- *Bureau hub* (Buried Talent / Scholarship Watch) — **OVR** columns; explainer
  rewritten to distinguish static OVR from dynamic STR.
- *Fit Finder* — TRUE TALENT shown as OVERALL; **STR (now)** = live results; GROWTH =
  OVERALL headroom; **TEAM OVR** replaces "Team STR".
- *Playing-time watch* — current-ability column relabelled **OVR**.
- *Lineup Lab* — ladder/plot/tables show live STR; the lens toggle is now
  **STR | UTR | OVR** (UTR is the STR remapped to real-world units; OVR is static
  talent, a different value so dots reposition). Each datapoint carries both
  `str` and `ovr`; team aggregates provided in both.

**Caching:** `scan`'s stamp already ticks with the world week, and live STR is keyed
on completed-dual count, so results refresh as the season advances (paired with the
roster-override stamp fix in `AAR-bureau-lineup-stale-after-fall-portal.md`).

**Validation:** all five Bureau pages + Fit render 200 with live STR; headless
Chromium confirms the OVR lens repositions dots, re-domains the axis (STR ticks
35→OVR 32+) and flips every table cell (43.3 STR → 48 OVR) with no JS errors;
`test_intel_bureau_live` + web suites green (10 passed). `overall_to_str` retained
**only** as the `season_player_str` prior and the unplayed-player fallback.

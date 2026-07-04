# AAR — Underplaced Talent "FITS" diversity (calibre-band by grade)

> **Status:** shipped. The Analytics Bureau → **Underplaced Talent** board's `FITS`
> column now surfaces a **diverse, calibre-appropriate** program per player instead of
> repeating the same four blue-bloods down the whole list.

---

## 1. The complaint (owner)

On the Underplaced Talent board, the **FITS** column (the program a buried talent
"deserves") showed the **same 4–5 major programs** — Georgia, Texas A&M, Stanford, Wake
Forest, Notre Dame — for nearly every row. Two clarifications from the owner:

1. **Diversity, not precision.** "The goal here is diversity… a diverse array snapshot of
   all the tiers of schools cross-division who could use this player, as opposed to picking
   the same schools for each option." A school showing up 2–3 times is fine; the same four
   repeated for 50 rows is not.
2. **Any tier that matches, not just major.** "It doesn't have to just be major tier — it
   can be any tier where it matches. There are 300+ D1 programs." The fit should roam the
   whole range of programs a talent genuinely slots into, across divisions.

---

## 2. Root cause (`app/scout_intel.py::scan`)

`deserved_school` was the **single** program at the player's exact talent percentile on the
cross-division level ladder:

```python
idx = round((1 - r.talent_pct) * (n_t - 1))
d = ladder[idx]                     # one school — every same-calibre player collapses to it
```

Every player of similar talent mapped to the **identical** `ladder[idx]`, so the column
repeated one school per calibre band. No spread, no sense of the real range.

---

## 3. The fix — a calibre BAND, one pick by stable hash

Instead of the single closest program, draw the fit from a **band** of programs the talent
would genuinely fit, and pick ONE by a **stable per-player hash** so different players land
on different schools while each player's fit stays put:

```python
d = band[zlib.crc32(r.pid.encode()) % len(band)]
```

- **Stable + deterministic:** `crc32(pid)` (not Python's salted `hash`) → same player always
  shows the same fit; it never reshuffles on reload, and the seed-deterministic world stays
  reproducible.
- **The scan is cached** per world snapshot, so this is computed once.
- **Covers all three sorts** (Most underplaced / Best right now / Highest ceiling) — they all
  read `deserved_school`.
- The per-row **Fit Finder** link (`intel_fit` → `fit_targets`) still lists a player's full
  ranked fit set; this only diversifies the one-line board summary.

### 3a. Why the band is by GRADE, not ladder percentile (the key iteration)

First cut used a fixed ±N **ladder-index** window, then a **percentile** window (±0.30). Both
were wrong at the extremes:

- A tight index window kept blue-chips pinned to the **top ~25** programs — still "major only."
- A wide percentile window (±0.30 of a **1,112-program** ladder ≈ 333 rows) pushed talent-75
  **blue-chips onto D3/D4** teams — "where they'd dominate," not "where they match."

The ladder blends all divisions (D1 379 · D2 306 · D3 233 · D4 194 = 1,112), so a *percentile*
span crosses divisions unevenly. The fix is to band by **calibre in OVR grade points**, since
`team_level` (a program's top-6 **ceiling** average) and a player's `true_overall` are both on
the **20–80** scale:

```python
_FIT_UP   = 3.0     # OVR a fit may reach ABOVE their talent (a slight reach; more and they'd sit)
_FIT_DOWN = 15.0    # OVR BELOW — the range where they're still a real fit/upgrade
asc      = ladder[::-1]                       # ascending by team_level
asc_lvls = [t["team_level"] for t in asc]
...
i0 = bisect.bisect_left (asc_lvls, r.true_overall - _FIT_DOWN)
i1 = bisect.bisect_right(asc_lvls, r.true_overall + _FIT_UP)
band = asc[i0:i1] or [closest-by-level fallback]
```

Grade-banding is **self-scaling by tier**:

- A **blue-chip** (talent ~75) → band `team_level ∈ [60, 78]` = the whole of **D1** (top → low),
  never D3/D4.
- A **mid** talent (~60) → band `[45, 63]` = the **D1/D2/D3 boundary** — cross-division emerges
  naturally, exactly where it should.

`bisect` on the pre-sorted level array keeps each player's band lookup **O(log n)**.

---

## 4. Result

| | Before | After |
|---|---|---|
| Distinct fit schools in the top 50 | ~5 | **41** (women) / **34+** (men) |
| Most-repeated school | ~10–15× | **3×** |
| Blue-chip fit range | top ~25 (major only) | **full D1** (#3 → #150+) |
| Lower-talent fit | same majors | **D2/D3/D4** where they match |

The column now "rolls up the entirety of the section" — a diverse snapshot across every tier a
talent genuinely fits, each fit stable and calibre-appropriate. Intel Bureau tests pass.

## 5. Tuning knobs (`app/scout_intel.py`)

- **`_FIT_UP`** (default 3.0) — how far above their level a fit may reach. Higher = more
  "reach" fits where they'd be a mid-lineup piece; 0 = only at-or-below their level.
- **`_FIT_DOWN`** (default 15.0) — how far below. Widen to let top talents dip toward D2 (more
  cross-division spread); tighten to keep fits closer to their exact calibre.

## 6. Files touched

- `app/scout_intel.py` — `import bisect`/`zlib`; the `deserved_school` calibre-band pick in
  `scan()`.

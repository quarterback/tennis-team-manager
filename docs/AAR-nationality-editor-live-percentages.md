# AAR — Nationality editor: live percentages + the US "multiplier" no-op

## Context / problem

The onboarding nationality editor let players set a per-region **× multiplier**, but
it was confusing and partly a lie:

- Cranking **US ×8 did nothing.** The engine **never uses the `us` region weight** for
  the US-vs-world balance — it strips/overrides it in both generation paths:
  - **Recruits** (`app/juniors.generate_class`): `intl_weights` drops `"us"`; the
    domestic share is `1 − worldconfig.intl_share()` (default 0.30 → 70% US).
  - **Base rosters** (`app/ncaa.region_weights_for`): `out["us"] = 1 − intl_share_for(
    division, gender, prestige, academics)`; the band's `us` weight is discarded.
  So the region weight only ever decides **which foreign nations the international slice
  is split among** — never how big the US slice is.
- The editor showed each region's **static band-share** (`base_pct`), which (a) was
  blank for many regions (`{% if r.base_pct %}`), and (b) wasn't the region's real
  share of the world once `intl_share` rescaled everything. So the **× had no visible
  effect** and the numbers didn't add up to anything a player could reason about.

The actual US-vs-world lever — `worldconfig.intl_share()` (choices 0.30–0.80) — already
existed but sat in a separate "International recruits" dropdown, disconnected from the
editor.

## Fix

Make the editor show **live effective percentages** that mirror the engine math, and
make the real lever obvious.

- **`app/worldconfig.py` — `region_groups()._row`:** each row now also carries the raw
  band `weight`, `in_band`, and `is_domestic` so the client can recompute shares.
- **`app/web/server.py` — `/start`:** passes `band_weights` (every band's
  `{region: weight}` map) and `intro_floor` to the template, so percentages recompute
  even when the player switches **band**, not just multipliers.
- **`app/web/templates/onboarding.html`:**
  - Renamed the `intl_share` field to **"US vs. world split"** (e.g. "60% US / 40%
    international") and clarified that *this*, not the multipliers, sets the US share.
  - Each region row shows a live **effective %** chip (`.ob-reff`) updated by JS on any
    change to the split, band, or a multiplier. The math mirrors the engine exactly:
    a region absent from the band surfaces only at `INTRO_FLOOR·mult` when mult≠1; the
    **US row is `1 − intl_share`**; the rest of the world is scaled to fill the
    international slice (`intl · weight_i / Σ weights`).
  - The **US row's multiplier is removed** (shown as a fixed "auto" chip) because the
    engine ignores it — no more pretending US ×8 does something.

Net: the percentages are visible and trustworthy, and it's clear the US share is the
"US vs. world split" knob while the multipliers only re-slice the international pool
(e.g. Canada ×2 ≈ 5–6% of the class at a 60/40 split).

## Verify

- `GET /start` renders 200 with the live-% scaffolding (`ob-band-weights`, `data-eff`,
  US row `data-domestic="1"`).
- Cross-check the JS formula against `ncaa.region_weights_for`: at `tennis_global`,
  `intl_share 0.40`, no multipliers → US 60%, Canada ≈ 2.9%, non-US shares sum to 40%.
- `python3 -m pytest -q tests/test_web_recruiting.py tests/test_web_coaches.py
  tests/test_world_single_gender.py` (server-touching web tests).

> Note: `tests/test_web_coaches.py::test_coach_honors_persist_and_follow_id` is a
> season-simulation test that has shown cross-test state-bleed flakiness in combined
> runs; it passes in isolation. Not related to this change.

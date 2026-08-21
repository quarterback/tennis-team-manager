# AAR — frequency-weighted names with a mid-save era cutover

## The report

Owner, 2026-08, with two exported 2030 JHSAA seasons attached: *"the naming
generator needs to be broader and do like OOTP and other games do where more
common names come first rather than a lot of people repeating with uncommon
surnames and first names"* — plus a small international window ("IRL there are
exchange students who play HS for a year"), Canada getting its own ~5%, and the
hard constraint: *"i want to be able to implement it into the save right now …
i'm 4-5 years in"*. A follow-up sharpened the scope: **do not remove the
existing pools** — reorder and broaden, don't replace.

Measured on the exports, the complaint was exact: 15,113 boys shared the load so
evenly that the TOP first name appeared 53 times (0.35%) and 5,500 distinct
surnames averaged 2.7 uses each — rare hyphenated surnames repeating exactly as
often as Smith, because the flat `rng.choice` inside `make_name_picker` gives
every name in a bucket identical odds. Real name distributions are steeply
head-heavy; the missing head-heaviness is what made the league read as a
generator.

## What was built

**1. `generators/data/names/us_freq.json`** (built by
`scripts/build_us_name_freq.py`, committed so runtime never touches the
network — the `build_hometowns.py` pattern): real US Census 2010 surname counts
(top 20,000, recased — O'Brien, De La Cruz, Mc*) and SSA top-1000 first names
per sex for birth years 2010-2018 (via a GitHub mirror; ssa.gov blocks
non-browser fetches), with counts reconstructed from ranks through the real SSA
rank-share curve (log-log interpolation). Regenerate with the script, never
hand-edit; the name scrubber never touches this file.

**2. `generators.names.draw_us_weighted(rng, gender)`** — `US_FREQ_SHARE`
(0.80) of draws come off the frequency tables (cumulative-weight arrays,
`rng.choices`), the rest fall through to the ordinary flat curated draw. The
curated pools are **untouched underneath** — the weighted head gives common
names their real prominence, the legacy tail keeps every curated name alive.
Do not "dedupe" the curated buckets against the freq file.

**3. The JHSAA mix** (`jhsaa._gen_seat`): new-era players draw ~**90%**
weighted-US / **5%** Canada / **5%** international (the exchange students —
`tennis_global` preset minus us/canada). Measured on 7,673 new-era players:
Emma/Sophia/Isabella lead the firsts, Smith/Johnson/Brown the surnames,
countries 90.2 / 5.1 / 4.7.

## ‼️ The era cutover — why entry year, and why the rng discipline

JHSAA players are **regenerated deterministically** from (school, entry, seat);
nothing about them is persisted. Change the draw naively and every archived
season's rosters are silently RENAMED — awards, brackets and school pages all
point at strangers, on a save the owner is five years into.

So the new draw is gated on **entry year**: `jhsaa.name_era()` self-configures
ONCE per save to (latest archived JHSAA season year + 1) — every cohort the
save has already seen keeps its exact names, only future freshman classes
broaden — persists in `worldconfig`, and is memoised keyed on the DB path,
cleared by `reset_schools()` (never resolved per seat — the play-up
fingerprint-query-storm rule). A fresh save with no archive gets era 0:
everything is new anyway.

Two rules make the gate actually safe, both verified by byte-comparing rosters
across the change (0 attribute mismatches, 0 pre-cutover renames):

- **Exactly ONE main-rng draw for naming, in both eras.** The name stream is a
  child rng seeded off one `rng.randrange(1 << 30)`; all new-era dice come off
  the child, so widening the name draw cannot shift a single talent roll.
- **`generate_prospect` always gets country "US"; the real country is stamped
  on afterwards.** The first version passed the drawn country through and 9% of
  players changed attributes: `generate_prospect` branches on country (talent
  shift, elite roll, academics, hometown path) and consumes the rng
  differently. The era moves NAMES ONLY; the flag is display.

## What to check first if this looks wrong later

- Archived players renamed → something bypassed `name_era()` or reset the
  persisted `jhsaa_name_era` key downward.
- Same-class attribute drift after a naming change → someone let the name
  branch touch the main rng, or passed a non-US country into
  `generate_prospect`. Re-run the byte-compare (era forced high vs the old
  code).
- Names suddenly ALL common / the curated flavor gone → `US_FREQ_SHARE` crept
  toward 1.0 or the legacy fallthrough was removed. The blend is the design.
- College/pro names unchanged is CORRECT — only the JHSAA draw adopted
  `draw_us_weighted` so far; the college pipeline still draws its own mixes.

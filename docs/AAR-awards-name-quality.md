# AAR — Awards-list name quality (gender pools, junk surnames, list length)

## What it was before
The 2027 D1 Women awards archive read wrong in three ways:

1. **Male names on women.** The first-name pools leaked across genders — the
   women's pool contained outright male names (the giveaway was "Phil Earps"
   on a women's All-American list). 414 names appeared in *both* the male and
   female pools, and many were not genuinely unisex — they were male names that
   had drifted into the women's bucket.
2. **Junk surnames.** A German *city*, "Mönchengladbach", was sitting in the
   surname pool across 8 regions (a scrape artifact), so players could be
   surnamed after a football club's hometown.
3. **The All-Conference list was too long.** The archive rendered First + Second
   team flat for every one of ~30 conferences — one endless wall of names with
   no way to scan to the league you cared about.

## What changed
**Gender de-contamination (`generators/data/names/{male,female}_first.json`).**
Built a name→gender map from the MatthiasWinkelmann firstname database
(`name;gender` with M/F/?/?M/?F codes), aggregating *all* rows per name so a
name with both male and female evidence is treated as unisex and kept in both
pools (Jane, Karen, Andrea, Jordan, Frances all correctly survive). A name is
removed from the women's pool only when the data is **exclusively male**, and
from the men's pool only when **exclusively female**. A small allowlist
protects modern unisex names common in women's college sports (Taylor, Riley,
Harper, Quinn, Cameron, Morgan, Avery, Peyton, …) so we didn't strip the
legitimately-androgynous ones. Result: 165 distinct male names left the women's
pool, 107 distinct female names left the men's pool, overlap fell 414 → 278
(now genuinely unisex), and "Phil" is gone from the women's pool while "Taylor"
stays.

**Junk surname removed (`generators/data/names/surnames.json`,
`scripts/scrub_name_pools.py`).** Stripped "Mönchengladbach" from all 8 regions.
The pool scrubber had actually *whitelisted* it (`SURNAME_CITY_KEEP`), which is
why it kept reappearing — removed it from that keep-list so the scrubber now
enforces its removal instead of preserving it. Running the scrubber also cleared
the city "Sétif" (Algerian city in the birthplace pool, never a surname), which
had been failing the `test_name_pool_clean` guard. Conversely "Leone" — a
genuine common Italian surname that the city sweep was false-flagging — was added
to the keep-list rather than stripped. The guard test is green again.

**All-Conference collapses per league (`app/web/awards.py`,
`awards_archive.html`).** `awards_archive` now groups All-Conference by
conference — `{conf, count, teams:[{tier, players}]}` — instead of a flat list
of teams. The template renders each conference as a collapsed `<details>`
showing the league name and honoree count; tap to expand its First/Second
team. The page header reads "N conferences · tap to open". The page is short
by default and you jump straight to the league you want.

## Why this is better
- Women's rosters read female and men's read male, without losing the truly
  unisex names — the de-contamination is evidence-based, not a blunt cut.
- No more city/club surnames masquerading as players.
- The awards archive is scannable: a list of conferences instead of a wall of
  every team in the country.

## Verification
- `make_name_picker` for the `americas_pro` preset yields clean,
  gender-appropriate names in both genders; "Phil" absent from women, "Taylor"
  retained.
- All three name JSONs reparse; re-dumped at the repo's `indent=2` so the diff
  is pure deletions (female −165 distinct, male −107 distinct, surnames −1).
- `awards_archive.html` compiles; `awards_archive` returns the grouped shape.
- `tests/test_web_awards.py`, `tests/test_honors.py`, the name/region suites
  (`test_names.py`, `test_name_regions.py`, `test_world_model.py`), and the
  `test_name_pool_clean` scrubber guard all pass. (The lone remaining suite
  failure, `test_season.py::test_higher_seeds_usually_advance`, is a borderline
  statistical assertion that fails on clean HEAD too — pre-existing and
  unrelated to this work.)

## Files
- `generators/data/names/female_first.json`, `male_first.json` — gender cleanup.
- `generators/data/names/surnames.json` — removed "Mönchengladbach".
- `app/web/awards.py` — `awards_archive` groups All-Conference by conference.
- `app/web/templates/awards_archive.html` — collapsible per-conference groups.

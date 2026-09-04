# AAR — ATR seeds the postseason; TOSS keeps the rating (owner rule 2070)

The JHSAA decided that **ATR determines state seeding instead of TOSS**. The reason
is the format pilots: 1A's road plays 2S/3D and 8A/9A's postseason and early window
play 4S/5D, so three dual shapes feed one TOSS graph — and an opponent-strength
composite whose per-dual shares are folded across formats distorts exactly the
comparisons a seed order is made of. ATR (`atr_of`: 0.5 TOSS + 0.5 win percentage)
damps that, because the win term is format-blind.

## What moved

One key: `jhsaa._power_key` — the pure-`pi_raw` sort every postseason-field function
shared — is **retired**, and `jhsaa._atr_key` (which the Semi-Conference and
Conference pools already used) is now THE ONE postseason seeding key, at all twelve
call sites:

* the **protected fill** (`sectional_field` — district champions first, then best
  remaining ATR to `PROTECTED` seats) and its ordering;
* the **Sectional/Area** bye ordering (`_elim_round` fields arrive strongest-first);
* the **Ward field** and the **Regional field** seedings;
* every **recovery pool** in `_recovery` AND `_recovery_24`: the Super Regional
  pool, the Semi-State pool, the losers orderings between rounds, and the Divisional
  tier picks.

`_atr_key` keeps `_power_key`'s no-`power` fallback (win pct → point differential →
name, for a caller running a district in isolation) so an isolated sort is still
reproducible.

## What deliberately did NOT move

* **The State draw itself** — already seeded on `seed_atr` (the Epiregional's
  z-blend, `SEED_ATR_TOSS_WEIGHT` 0.6) since the Epiregional change. Untouched.
* **The TOC** — still seeds on TOSS (`run_toc`, `t.power`). The decree named state
  seeding; the TOC is the rung above it. Flagged to the owner as the one remaining
  raw-TOSS seed, and it is arguably the place the cross-format distortion bites
  hardest (twelve champions from three formats in one draw).
* **The district tiebreak ladder** — rung 4 still reads TOSS. That is a LEAGUE
  decision, not state seeding.
* **TOSS itself** — computation, archiving (`pi` on the standings rows), the
  rankings page, the per-dual weight tables: all unchanged. TOSS remains the
  association's rating; ATR is what orders a postseason field.
* **The Specials/Challengers** — already ranked on their own keys (regular-season
  record ladders, ATR pairings); nothing there read `_power_key`.

## Measured (the owner's own 2069 + 2070 saves, both genders)

Ordering every classification by archived `pi` vs by ATR recomputed from the same
rows: **~85% of programs change class rank** (girls 770-787/912, boys 735-756/875),
mean shift 2-4 places, and the top-eight of a class churns by 2-6 programs in most
classes. The pilot classes sit at the top of the shift table — 1A 2.8-4.0, 8A
2.9-3.5, 9A 3.2-4.1 mean places against 7A's 1.6-2.6 — which is the distortion the
decree names, visible in the data.

## Traps for the next pass

* `_atr_key`'s docstring is the rule of record: **no postseason field may sort on
  raw TOSS again.** Adding a round means seeding it through `_atr_key` (a pool) or
  `seed_atr` (a draw), never `pi_raw`.
* The guide and the rankings page microcopy said "the season was seeded from" TOSS;
  both now say TOSS rates and ATR seeds. Archived pre-2070 seasons were genuinely
  seeded on TOSS — the archive stores its seeds, so nothing re-reads wrong.

## Files

`app/jhsaa.py` (`_atr_key` absorbs `_power_key`, 12 call sites, ladder comments) ·
`app/web/templates/guide.html`, `jhsaa_rankings.html` (microcopy) · `CLAUDE.md`.

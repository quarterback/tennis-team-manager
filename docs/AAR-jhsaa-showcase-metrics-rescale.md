# AAR — rescaling the showcase-vs-regular columns (SC Rating / Fmt° / Dbl+)

## The report

The format-transition columns shipped this session (`docs/BLOG-toss-in-a-third-format.md`
era work) rendered every number as a raw `0.xxx` decimal — `sc_pct` (0-1), `fmt_shift`
(a delta typically ±0.3), `dbl_shift` (the same delta on doubles win share). Functional,
but the owner flagged it wasn't a scannable shape: "are they just .000 percentages? i
might want them to look differently." Three separate re-asks, one per column:

1. **SC Wtd%** → scaled 1-10.
2. **Fmt Shift** → "set like a temperature scale."
3. **Dbl Shift** → "more like ERA+ or OPS+ (create a normalized 100-baseline index)."

Two rounds of correction arrived once a first pass was mocked up: "not a gauge just a
number" (no thermometer bar/marker widget — a styled number only) and "i don't want
fancy design i want something i can scan quickly" (drop the SC Rating meter too). Final
shape for all three: plain, tabular-nums text, colored only where the sign/side of a
baseline actually means something — same as every other shift column already did.

## What changed, and what didn't

**SC Wtd% → SC Rating** is a pure rescale. `sc_pct` is unchanged (still 0-1, still
`weighted_pct` off the showcase sample) — the template now multiplies by 10 at render
(`'%.1f'|format(r.sc_pct * 10)`). No backend change, because the underlying number
already meant "a rate between 0 and 1"; a review-site-style 0-10 read is just a
different unit on the same fact.

**Fmt Shift → Fmt°** is also a pure rescale + relabel, not a new formula. Still
`sc.weighted_pct - reg.weighted_pct` from `_fmt_delta`; the template multiplies by 100
and appends `°` (`'%+.0f°'|format(r.fmt_shift * 100)`) instead of `%+.3f`. "Temperature"
here is a READING convention (positive = warmer = plays UP under 1S/4D, negative =
colder = plays down), not a unit conversion to anything physical — there's no
Celsius/Fahrenheit-style scale being invented, just a signed integer with a degree
symbol and the same `--pos`/`--neg` coloring every shift column in this table already
used. The mockup's first pass built an actual gradient-track gauge with a marker; that
whole widget was cut on "not a gauge just a number" — the CSS class `.jh-temp` now
styles text only.

## Dbl+ is a REAL formula change, not a rendering tweak

This is the one that isn't cosmetic. "ERA+/OPS+-style… normalized 100-baseline index"
is a specific, well-defined convention in sabermetrics, and it is a RATIO to a
baseline, not a DIFFERENCE from one — a below-average player reads "80% of league
average," not "-.020 points off league average." `_fmt_delta` (subtraction) cannot
produce that shape; a new function was needed:

    def _fmt_index(reg: dict, sc: dict, key: str) -> dict | None:
        if not sc["n"] or not reg.get(key) or sc[key] is None:
            return None
        return {"n": sc["n"], "index": round(100 * sc[key] / reg[key])}

Applied to `doubles_win_share`: `100 * showcase_share / regular_share`. 100 means a
team's doubles reliance is identical in showcases to its regular season; above/below
means doubles is carrying MORE/LESS of the team's wins under 1S/4D than it normally
does. `format_profile()`'s `doubles_shift` key became `doubles_index`;
`_flat_format_profile()`'s `dbl_shift` became `dbl_plus`, propagated through
`world.jhsaa_group_ranking` and `state.py`'s `SORTABLE` map — no other reader of the
old key existed, confirmed by grep before renaming rather than leaving a dead alias.

**The guard that matters**: a ratio to a zero baseline is undefined. A team that won
none of its regular-season weighted points on doubles (`reg["doubles_win_share"] ==
0`) can't be indexed — `100 * anything / 0` is either a crash or a fabricated infinity,
neither of which belongs on a rankings page. `_fmt_index` returns `None` in that case
(`not reg.get(key)` catches both `0` and `None`), rendering as a dash — the same
reasoning a real 0.00 ERA can't produce a real ERA+ either. Verified directly: a
fabricated schedule where the regular season's only doubles lines are losses produces
`dbl_plus is None`, not an exception.

## Reading Dbl+ requires Fmt° beside it — this took several follow-up turns to land

Dbl+ measures *composition* (where wins come from), not *quality* (whether that's
good). Unlike OPS+, where higher is unambiguously better, a high Dbl+ is only good
news paired with a warm Fmt°:

- **Dbl+ high + Fmt° warm** — real doubles depth is propping the team up under a
  format that rewards it. The green-light read.
- **Dbl+ high + Fmt° cold** — looks identical in the Dbl+ column but means the
  opposite: doubles' SHARE went up only because the team's single S1 line (1S/4D has
  exactly one) lost, shrinking the denominator the rest of the dual is measured
  against — not a doubles strength story at all.

Neither number resolves this alone; the two-turn back-and-forth ("so what would a good
Dbl+ be") landed on: Dbl+ tells you WHERE to look, Fmt° tells you whether that's a
strength or a collapse. This isn't a code change but is worth carrying forward if the
column ever gets a tooltip rewrite — the current tooltip states the formula but not
this reading pattern.

## Verified

- `_fmt_index` math confirmed against a hand-built sample (regular doubles share
  0.431, showcase 1.0 → index 232) and the zero-baseline guard confirmed to return
  `None` rather than raising or producing `inf`.
- `world.jhsaa_group_ranking` round-trips a fabricated archive row carrying the new
  `dbl_plus` key correctly (rated and unrated/`None` rows both).
- Template parses and renders the three columns as plain colored text — no gauge
  markup shipped.
- Full pytest suite not run this pass (screen-share only, no data-scale season played)
  — same caveat as `docs/AAR-jhsaa-early-nondistrict-3s4d.md`.

See also: `docs/AAR-jhsaa-early-nondistrict-3s4d.md` (the 3S/4D early window this
session's Fmt Shift/Dbl Shift columns were originally built to help evaluate) and
`docs/BLOG-toss-in-a-third-format.md`.

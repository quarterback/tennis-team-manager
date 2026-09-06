# AAR — the second type raise, and the program page becoming an HQ

Owner session, 2026-09. Two asks that arrived as one complaint ("consider another
visual pass at making the UI more readable") and then sharpened into two different
problems:

1. **The type was still too small.** The 2027-08 raise (see
   `AAR-design-port-readability-and-suite-hermeticity.md`) moved the scale a step
   and it was not enough — "the type is really hard to read, the readability is
   the cheapest fix for sure."
2. **The program page treated the program as a collection of archival lists.**
   "When I click a school/program, I should feel like I have entered that
   program's HQ… Use Football Manager's club experience as the closest
   interaction model. Do not copy Football Manager visually. Copy the
   information architecture."

## 1. The second raise — same mechanics as the first, one step further

Asked directly how far to go, the owner picked "match the canvases" (their design
mockups): body ~18px, dense tables ~15-16px. The sweep is the 2027-08 playbook
re-run, and both of its rules held:

- **Literals and tokens move together or the hierarchy inverts.** 767 px literals
  swept on a monotone whole-pixel mapping; `tokens/typography.css` and the legacy
  `--fs-*` aliases in `tokens/colors.css` raised in the same step.
- **Fixed boxes are exempt and clip.** The crest sizes did not move.
- **Fixed columns are sized against the type they were designed with.** The
  program-history ledger's header widths clipped ("SEASO", "RECOR") and had to
  grow; the ledger/repeat min-widths grew with them. Any future raise should
  budget a pass over `style="width:…px"` table headers.

New this time:

- **`--text-faint` is now a mix, not a raw slot.** It read `--gray-400` raw
  (~3:1), which is where "too low-contrast" metadata came from. It now mixes
  gray-500 into gray-400 **in the alias layer**, so all ten schemes lift at once
  — a scheme overrides layers 1-2 only and never touches the alias.
- **Density moved with the type**: one step more vertical padding on the JHSAA
  tables, group gaps 14→18px, chip height 19→22px. "Tables should still be
  compact, but not cramped."

## 2. The program HQ

The old `/jhsaa/school/<school>` rendered everything the program has ever done on
one conceptual level. It is now one persistent context — crumb, identity block,
HQ nav — over six internal destinations:

- **Overview** (default, light): this season's postseason path, the top of the
  ladder, this season's honours, a six-line all-time glance. Orientation, not
  statistics — the owner explicitly rejected both a metric-tile wall and a
  generated prose summary.
- **Team** · **Season** · **History** · **Honors** · **Champions & Records** own
  the archives the old page stacked.

Mechanics worth keeping:

- **The destination is a QUERY ARG (`?view=…`), not a route.** `jh_scope_url`
  re-emits the page's own query state, so a gender or season switch keeps the
  view you were reading — the HQ inherits the scope bar's "stay here" behaviour
  for free. Unknown values fall back to Overview.
- **No counts on the HQ nav.** Tabs wearing "104 · 347 · 56" are what made the
  old page read as adjacent database dumps.
- **Progressive disclosure in History** reuses the schedule's `has-lines` row
  idiom: a season row shows a COUNT of honours and expands to the names and unit
  chips. The ledger's honours column no longer sprays names across the row.
- **Single-table views are width-capped** (`.jh-hqnarrow`, 1000px): a schedule
  row with 400px of nothing between opponent and result is not more readable.
- **Tests followed the content to the view that owns it.** The TOC-run,
  title-banner and JV-toggle assertions now fetch `?view=season` / `?view=honors`
  — the invariants are unchanged; the page that carries them moved by owner
  request. `test_every_jhsaa_page_renders_against_a_real_season` renders all six
  destinations.

## 3. The context shell was already consistent — measure before rebuilding

The owner also asked that Championship/Rankings/Honors/Districts/History/Programs
"feel like different views of the same association context". Audited: every JHSAA
surface already renders `jh_header` (scope bar + section tabs) inside `jh-shell`
except the Match Center (`jhsaa_dual`, a leaf detail page with a back pill) and
two tool pages. The shell the ask describes exists; what had drifted was the
TYPE and the program page, which is where the work went. Don't rebuild a shell
that is already there.

## Preview harness

A JHSAA-only lab world (`get_or_create(skip_college=True)` + the
`test_jhsaa_toc` small-association cut) serves the real app against a scratch DB
in ~2 minutes, and Playwright screenshots against it were what caught the
clipped ledger headers and the dead middle of full-width tables. Two traps:
spawn workers re-import `__main__`, so a serving script needs the
`if __name__ == "__main__"` guard or `get_or_create` fork-bombs; and
`pkill -f <script>` matches the compound shell command carrying the same string.

# AAR — the Preseason NIT is now the same bracket as the NCAA tournament

**Asked for:** "I want the preseason NIT to use the same bracketing structure and
design as the NCAA tournament so it's easier to view, and to improve the view of the
KO parts too."

---

## What the page was

`/season/ita` was two flat lists:

* **The Indoor** — round panels (`bl-rounds-sim`), one column per round, each column an
  unordered pile of matchups. Nothing connected a matchup to the one it fed, so
  answering "who does the Kickoff winner play next?" meant reading two columns over and
  matching names by eye — the exact complaint that had already been fixed on the NCAA
  page (`docs/AAR-ncaa-bracket-region-drift.md` §2) and never carried over here.
* **The Kickoff Weekend (KO)** — a `repeat(auto-fill, 260px)` grid of bordered boxes,
  each holding two semifinal rows, the word "Final", and one more row. A four-team
  single-elim rendered as a list of three lines.

No seeds anywhere. No champion path. No zoom, no team highlight, no print, no season
picker. The NCAA page had all of it.

## What it is now

The NIT has the NCAA bracket's shape one tier down, so it uses the same machinery:

| NCAA | Preseason NIT |
|---|---|
| four S-curve regions, each a ladder | sixteen four-team **Kickoff sites**, each a ladder |
| region champion → Final Four | site champion → the **National Team Indoor** draw |
| `_bracket_canvas` tree + SVG elbows | the same `_bracket_canvas` |

* `state.ita_bracket_view()` shapes `sm.ita_view()` into the canvas contract
  (`{cards, links, columns, width, height, card_w, card_h}`) — one canvas per Kickoff
  site, one for the Indoor.
* `templates/_bracket.html` is new: `brk_row` / `brk_canvas` / `brk_toolbar` /
  `brk_script`, lifted verbatim out of `ncaa_bracket.html` so both pages draw from one
  source. The `.brk-*` CSS moved to `static/css/bracket.css` for the same reason.
* `_bracket_canvas` grew keyword-only geometry (`card_w`/`card_h`/`gutter`/`leaf_gap`).
  A four-team site is a small tree and wants smaller cards; sizing it in CSS instead
  would break the shared coordinate system the elbows depend on.
* The NIT page inherits the whole viewer: tabs (Full bracket / Kickoff Weekend / Team
  Indoor), zoom + fit, seeds/scores toggles, highlight-a-team's-path, print, division
  pills and a **season picker** over past years.

## Two decisions worth keeping

**1. Seeds are read off the DRAW, never re-derived.** A site's two openers are 1v4 and
2v3 by construction (`ita.site_pairs`), in `bpos` order; the Indoor's round-1 slots are
`bracket._seed_positions`. So the seed line is recovered from the fixtures that were
persisted. The tempting alternative — call `_ita_ranking` again — is the NCAA
region-drift bug rebuilt: that ranking is a live Power Index that every NIT, CT and
regular-season dual keeps moving, so a bracket drawn in week 1 would relabel itself all
season. The bracket would stay correct and only the labels would lie, which is what made
that failure hide for so long.

**2. Undrawn rounds render as TBD cards.** The draw only writes a round once its feeders
have played (`_advance_indoor_round`), so a partly-played bracket used to just stop at
the round on the board. `_nit_pad` extends each ladder to its final with faded
placeholder cards, so the shape of the tree is visible from the moment the draw is made
— including the full sixteen-team Indoor while the Kickoff is still being played. This
is NIT-only on purpose: the NCAA page's 96-team ladders are large enough that padding
them is noise, and its tests count cards.

## Don't

* Don't fork the bracket markup again. Both pages import `_bracket.html`; a third
  bracket should too.
* Don't set a card's position or size in CSS. Cards and elbows share one server-side
  coordinate system — resize through `_bracket_canvas`'s geometry arguments.
* Don't re-seed the NIT from a live ranking. See decision 1.

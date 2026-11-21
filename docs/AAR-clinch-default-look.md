# AAR: the canvas design becomes the game's default look

Owner, 2026-11: "do all 3 yes it becomes the new default look". The three parts
were the palette, the type, and the high school section, which had never been
part of the redesign and still looked as it did before.

## 1. Palette (`tokens/colors.css`, `server.SCHEMES`, `shell.css`)

- `:root` now carries the owner's palette, named **Clinch** in the picker:
  midnight violet `#2d1e2f`, flag red `#c1292e`, dust grey `#e4dfda`, emerald
  `#2fbf71`, carrot orange `#f18f01`.
- Two colours were derived so text holds AA on the grey ground: pine `#186038`
  (5.7:1, links and the secondary text tiers) and deep red `#ae2529` (5.1:1,
  the live accent and chips). Flag red at 4.4:1 stays a fill and rule colour.
- Orange and emerald are 6.5:1 under ink, but read harsh as large fields, so
  `--linen` is the orange tint `#e8c799` and the hover wash is an emerald tint.
- The previous default moved, unchanged, to `[data-theme="ensign"]`, with its
  own swatch. Every scheme was checked for a full set of slot overrides, so
  none of them inherits the new default's values.
- Five alias tints mixed toward `white` now mix toward `var(--paper)`. On a
  white ground that is identical; on the grey ground it stops near-white boxes
  appearing.
- The top bar now sits on each scheme's mast colour with its light type and
  mast rule underneath, the way the canvas header does. The advance button
  reads a new pair of slots, `--mast-action`/`--on-mast-action`: ink on carrot
  in Clinch, ink on the scheme's light mast type everywhere else.

## 2. Type (`tokens/fonts.css`, both type-role blocks)

- Author for display (the bold weight was added), Hanken Grotesk for text and
  labels (OFL variable font, self-hosted in three script subsets, licence beside
  the files), RX100 for numbers as `--font-num`.
- RX100 has one weight. Every rule that sets it turns `font-synthesis` off, so
  numbers never render faux bold. It replaced Azeret Mono on the high school
  figure roles and covers ranks, records, indexes and scores in `app.css` and
  `bracket.css`.
- Crests stay on the text face: four letters of serif do not fit a 20px box.

## 3. The high school section (`jhsaa.css`)

- The section header is the orange tint hero band with a large display title.
- Sport, class, page, sub-rail, round, layout and pane controls were pill rows
  and framed segmented controls. They are tab rows now: plain words, the chosen
  one underlined in ink. The per-class fill on the selected class pill is gone,
  and so is the white-on-white trap it existed to prevent. Class chips keep their
  colours.
- The champion is a headline on the page instead of a dark gradient panel; the
  finalist and semifinalist cards, program metric tiles, school identity card
  and program tabs are open rows.
- The front page lost its two ink rules (facts strip, doors) and its stat panel.
- Below 720px the tab rows scroll sideways instead of wrapping, and the
  champion's scoreline drops under the name.

## Checked

Rendered against a scaled association season in Chrome at 1440px (class hub,
front page, program, rankings, honors) and at 390px (class hub). College pages
were not rendered: the scratch world had no college season, and building one
was out of scope. No tests run, by request.

## Not done

`prep-network/site/style.css` shares the scheme list and was not changed.

# AAR: AP style and humanizer pass on the interface

## What was asked

The owner saw "The 2027 Season" as a page title with the season named again
right beside it, and menus that said the same thing two and three times. The
ask was to run AP style and the humanizer rules
(github.com/blader/humanizer) against the whole interface.

## What was wrong

The repetition came from layers that each restated context someone else
already showed.

- **High school header (42 pages).** Every page carried an eyebrow with the
  association's full name, then a title that often named the season or class,
  then readouts for Season and Class beside the title, then the Sport, Class
  and Season controls in the scope bar. On the class hub, 9A appeared four
  times above the fold: the title "JHSAA 9A", the Class readout, the class
  rail, and the "9A Draw" tab. The champion label read "2027 JHSAA 9A STATE
  CHAMPIONS" under all of that.
- **Season page.** The masthead's Universe picker, a second Division picker
  on the page, and "2026 Season · D1 Men" named the division three times. A
  stage line repeated the masthead's stage, and Standings, NIT and Bracket
  pills linked to the same pages as the tabs directly below them.
- **World page.** A Season / Week / Class signed scoreboard repeated the
  masthead word for word.
- **Menus.** The Juniors menu listed "HS Schools" and "HS Programs", which
  are tabs of the High school section it also linked. "Junior Rankings",
  "Junior Tour" and "Junior Setup" sat under a heading that already says
  Juniors. Three different words (Hub, HQ, Overview) named the first page of
  a section.
- **Case and prose.** Headings, tabs and menu items were in title case. AP
  headline style is sentence case. Subheads and empty states used em dashes
  as the default connector, plus contrastive frames ("never a replacement",
  "a baseline, not a target"), ALL CAPS emphasis and "&" in prose.

## What changed

- **Header macro (`_jhsaa.html`).** The eyebrow is gone; the Front page tab
  already links home. The macro drops any Season, Class or Sport readout, so
  no caller can bring them back. The front page title is "JHSAA", with the
  full name as its subhead. "9A Draw" became "Draw". In-page labels lost
  their year, class and "JHSAA" prefixes.
- **Season page.** The toolbar is gone. The Schedule link moved to the
  results panel, and the "Full schedule" link that duplicated it was removed.
  With no world yet, no tab is marked Now. It used to mark Regular season
  while the world page marked Preseason NIT.
- **World page.** The scoreboard is gone, and the season tabs now sit inside
  the board, aligned with the content.
- **Menus (`server.NAV_GROUPS`).** Labels are sentence case. The two high
  school duplicates are removed; their URLs now highlight High school. The
  Juniors prefixes are dropped. Season Hub became "Season" and World Hub
  became "All divisions". The first page of Analytics Bureau and of the pro
  tour is "Overview". College Bracket became "Custom bracket", so it no
  longer reads like the NCAA bracket. "Conf tournaments" is spelled out.
- **Headings everywhere.** A script converted them, with a protected list of names: Preseason NIT,
  Tournament of Champions, Player of the Year, All-State, Hall of Fame, Power
  Index, State as the event name, Lineup Lab, Analytics Bureau, Clinch Report,
  The Wire, and acronyms. Panel titles, h1 to h3, tabs, subrails and labels
  are now sentence case, and "&" became "and". The guide's table of contents
  now shows each section's actual heading.
- **Flight names.** "No. 1 Singles" became "No. 1 singles" (and so on, JV
  included). This matches the repo's own tennis vocabulary rule. They are
  display strings only; nothing keys on them.
- **Front page deks (`jhsaa_desk.py`).** These no longer start with
  "Boys" / "Girls 8A". The chips above each story already carry gender and
  class.
- **Prose.** About 140 visible strings were rewritten by hand: dashes became
  periods, colons or commas, contrastive frames were cut, and ALL CAPS
  emphasis was lowered. "Colour" became "color", and "neighbouring" became
  "neighboring".

## What was not done

- **The guide's body prose.** It keeps its 135 dashes. An automatic pass
  (dash pairs to parentheses, single dashes to colons) nested parentheses
  wrongly in at least two places, so that pass was reverted and only the
  guide's headings, table of contents and lede changed. The guide also
  states facts that are out of date. For example, it says State is 32 teams
  in 7A and 24 everywhere else; the field sizes have changed since. A rewrite
  should fix the content and the prose together.
- **Browser tab titles** (`{% block title %}`) still carry full context, on
  purpose. A tab has nothing else around it to supply that context.
- **Comments** were left alone.

## Lessons

- **Repetition grows one layer at a time.** Each layer (masthead, title,
  readout, scope bar, rail, card label) was added to make a page stand on its
  own. None of them checked what the layers above already said. The fix that
  lasts is in the shared macro: the header now refuses to print a readout the
  scope bar owns.
- **A mechanical prose fix needs a balance check.** A dash-to-parentheses
  pass looks fine in a diff sample and still breaks a sentence that already
  had a parenthesis. The pass was checked with a per-paragraph count of
  opening and closing parentheses. When that check failed for the guide, the
  guide was reverted rather than patched by hand.

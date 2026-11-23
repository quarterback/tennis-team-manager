# Prep-sports style corpus — collector brief

GOAL: collect real high-school sports newspaper writing from roughly 1980-1999
(early 2000s acceptable; today's short web capsules are NOT wanted) so a style
guide can be written for an agent that will generate local-paper coverage of a
simulated high-school tennis league. We need the VOICE AND CADENCE of prep
journalism across ALL sports; weight tennis (aim ~30% tennis: duals, district/
state tournaments, season previews) but football, basketball, wrestling,
track, baseball, softball, volleyball, golf, cross country all count.

WANTED story types (get a spread): game story ("gamer"), multi-game roundup
("prep roundup"/"area roundup"), notebook, preview / season preview, player or
coach feature, column, athlete of the week, all-area / all-league team story,
state-tournament coverage, agate (box scores, results lists, standings).

WANTED desks (tag each): local (one town's paper on its own school), beat
(sustained coverage of one program), area (a region or league), statewide.
Small-town and rural papers matter most.

HOW:
- Use WebSearch (try allowed_domains for a known archive) and fetch pages with
  curl -s -L -m 25 -A 'Mozilla/5.0 (compatible; research-reader)'. Be polite:
  sequential requests, about one per second, no bulk crawling.
- Save each article's extracted plain text to <your dir>/raw/<id>.txt. These raw
  files are working copies only and will not be published.
- Append ONE JSON object per article to <your dir>/articles.jsonl with keys:
  id, paper, city, state, date (YYYY-MM-DD or YYYY), url, sport, desk,
  story_type, headline, word_count, byline_style (e.g. "By NAME, Staff Writer"
  / "staff reports" / none), dateline (if any),
  lede (the first sentence VERBATIM, max 45 words), lede_type (e.g. score-first,
  player-first, scene, stat, quote, delayed),
  structure (ordered list of what each paragraph or block does, e.g.
  ["lede: winner+score", "how it was decided", "coach quote", "position-by-
  position results", "records + next match"]),
  quotes (count), attribution (verbs used: said / noted / ...),
  score_style (how scores and records are written, verbatim examples),
  vocabulary (nicknames, period terms, verbs for winning/losing — verbatim),
  excerpts (up to 5 SHORT verbatim passages, each under 25 words, that show the
  voice), agate_sample (up to 4 verbatim lines if the piece has agate),
  notes (what makes this read like its time and place).
- Only record text you actually fetched and read. Never invent an article, a
  quote or a date. If a source is paywalled or blocked (402/403), skip it.
- Do not put any personal or project details in requests.
- Stop at about 40 articles or when your sources run dry. No tests, no code
  beyond small fetch/extract helpers kept in your dir.

FINISH: write <your dir>/FINDINGS.md (under 500 words): what the sources were,
counts by state / sport / story type / decade, the recurring conventions you
saw (leads, paragraph order, quote habits, score formats, headline style,
vocabulary), how tennis specifically is written, and what you could NOT get.
Your final message should be that FINDINGS text.

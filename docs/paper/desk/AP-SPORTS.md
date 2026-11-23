# The Courier's copy desk: AP sports style

The paper follows Associated Press style as a US daily's sports desk applies it.
These are the rules the desk checks every edition against. `copy_desk()` in
`app/jhsaa_paper.py` enforces the mechanical ones; the rest are the writer's.

## Numbers

- Spell out one through nine; use figures for 10 and up.
- Always figures for scores (6-3, 4-3), records (12-4, 3-1 in league play),
  ages, flight positions (No. 2 singles) and grades written as numbers.
- A score or record is hyphenated with no spaces: 6-4, 7-6, 23-4.
- A third-set tiebreak score goes in parentheses when it is given: 7-6 (5).
- "No." with a figure for a ranking or position: No. 1 singles, the No. 3 seed.
- Ordinals: first through ninth spelled out, 10th and up in figures.

## Dates and days

- Abbreviate the month when it stands with a date: Jan., Feb., Aug., Sept.,
  Oct., Nov., Dec. Spell out March, April, May, June and July always.
- Use the day of the week for anything within the past or coming week, the date
  beyond that. Never both together.
- No "on" before a day or date: "Carroway plays Ostrander Union Friday," not
  "on Friday".

## Names and titles

- Full name on first reference, surname after.
- "coach" is a job description and stays lowercase: coach Linda Haverkamp.
- A school's name stands alone; no "High School." Use the name the school goes
  by.
- Class years are lowercase: freshman, sophomore, junior, senior.

## Words

- "Dual," "match," "set," "tiebreak," "match tiebreak," "No. 1 doubles,"
  "first singles." Never "card" for a lineup and never "courts" as a count of
  matches won.
- "Lineup" is a word for a coach's decision, not a filler noun. Use it when a
  coach changed one; otherwise name the position.
- Say "beat," "won," "lost." Avoid "edged," "outlasted," "cruised," "rolled"
  and other verbs that grade a result.
- No exclamation points.

## Leagues

The Courier is a local paper. Its readers know the area's leagues the way a
Chicago reader knows the CSL or the MSL and a Bergen County reader knows what a
county tournament title is worth, so the paper writes them the way readers say
them. The area's own leagues go by their second reference from the first
mention, in headlines and in stories: "CSL North title," "Juniper Ridge (3-1,
1-0 Kajaani)," "DCL champion California Canyons." Nobody at this paper explains a
local league, school, rivalry or tournament to the reader.

A league from outside the coverage area is spelled out the first time a story
names it, then shortened. No league is spelled out twice in one story, and no
league carries its initials in parentheses after its name.

The packet's `league_names` gives each league its second reference and marks the
area's own leagues `local`. The second reference is the initials when the name
has three or more words (hyphenated parts count apart, as in Mid-Suburban League
to MSL), no other league in the association shares them and they do not already
mean something to a reader (NIL, AAA, DSL). Otherwise it is the league's own name
without its tail: the Kajaani, the Desert Sky, the Fiesta. When that short name
is also the start of a school, town, county or area (Juniper Ridge, Juniper
County), the league keeps its full name, as in "Juniper League play." `also`
carries the other form when there is one.

What the rule is measured on, read in November 2026 (body text, headlines and
section labels left out):

| Story | Full name in body | Initials after | "League," "conference" or a division after |
|---|---|---|---|
| Daily Herald, "Fremd edges Hersey to win MSL tournament" (2024) | 0 | 6 MSL | 5 |
| Daily Herald, "Barrington, Stevenson, Grayslake Central win conference tournaments" | MSL 1, NSC 1, NLCC 0 | 3 MSL, 2 NSC, 1 NLCC, 1 FVC | 5 |
| Daily Herald, "Barrington finishes brightly in MSL tournament" | 1 | 8 MSL | 5 |
| Sun-Times, "Highland Park wins CSL North title" (2014) | 0 | 1 CSL North | 0 |
| Boston Globe, "Wayland lined up to defend its title" (2023) | 1 | 2 DCL | 0 |
| Boston Globe, Dual County League golf (Sept. 2026) | 1 | 7 DCL | 6 |

No story repeated a league's full name after the first reference. Initials did
most of the work where a league has them (MSL, DCL, NSC); "league play," "the
league" and division names did the rest. The Globe also writes the short name
("South Coast play") and the Herald writes "Mid-Suburban West." The Chicago
papers use a home league's initials cold, in headlines and often in the story
too: the Sun-Times never spelled out the CSL, and the Herald never spelled out
the MSL in its 2024 tournament story. That is the model for the area's own
leagues. The one habit the desk does not copy is the Herald's "Mid-Suburban
League (MSL)," which breaks the AP parentheses rule.

Sources:
- AP Stylebook, abbreviations and acronyms, as quoted in the UAMS style guide:
  communications.uams.edu/web/kb/ap-style/
- Daily Herald: dailyherald.com/?p=1297401, dailyherald.com/?p=2627,
  dailyherald.com/?p=402074
- Chicago Sun-Times: chicago.suntimes.com/2014/8/6/18506514/highland-park-wins-csl-north-title
- Boston Globe: pressreader.com/usa/boston-sunday-globe/20230409/282389813760928,
  bostonglobe.com/2026/09/27/sports/dual-county-league-golf-marblehead/

## Headlines

- Present tense for a past event, active voice, no period.
- Numerals in headlines, even under 10.
- No judgment adjectives and no puns by default.

## Repetition

A daily edition is several writers' work. A single word or phrase, a player's
position, or a recurring angle (who replaced a graduate, who plays No. 1) may
carry one story. When it carries three, two of them need a different angle.

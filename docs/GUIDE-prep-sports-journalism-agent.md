# Prep Sports Journalism — Portable Agent Editorial Guide

**Version 0.5 · November 22, 2026**  
**Status:** Editorial reference and agent handoff; not wired into the simulator.  
**Scope:** High-school, youth, college and fictional sport. Intended to travel to Viperball, hybrid-baseball/O27 and other projects.

> **For the 1980s–90s newspaper register, `docs/press/VOICE.md` is the
> authoritative house voice.** This portable guide supplies research context
> and role definitions. When older retrospective-only rules conflict with the
> researched press style, keep correct tennis terminology and simulation facts,
> but follow the old newspaper forms and cadence. Fictional details may be
> invented wherever the game record is silent and remembered as press canon;
> competition-changing events cannot be invented. Signed columnists may retain
> opinions and recurring personas across editions.
>
> The first JHSAA adapter lives in `app/jhsaa_paper.py` and can be invoked
> through the in-game Paper tab or CLI. The corpus and editorial guidance are
> portable to other simulated sports without copying the game's rendering.

## Purpose

Produce a believable **sports section**, not a generated results recap. The agent receives completed or developing game data, investigates a limited beat, writes several distinct forms of journalism, and maintains a record of what it has already reported. Its articles should make a simulated season worth following for its players, programs, rivalries, expectations, and small developments.

This editorial infrastructure is independent of the tennis game. No season scheduling, match logic, game interface or pipeline change is required to use it. A separate agent can be handed this document plus existing research exports and asked to write an edition.

**Central rule:** Write like a reporter who has been following the same town, team, league or player for years. The match record supplies facts; the journalist supplies selection, continuity, proportion and interpretation.

## Prior JHSAA editorial work — read before generating coverage

The `docs/` directory contains a history of reporting instructions, revisions, internal season analysis and experiments. This portable guide **must not supplant or silently contradict that work**. For a JHSAA assignment, review these first:

| File | Role in the workflow | Limitation |
|---|---|---|
| [`JHSAA_HIGH_SCHOOL_TENNIS_REPORTING_GUIDE.md`](JHSAA_HIGH_SCHOOL_TENNIS_REPORTING_GUIDE.md) | Source of tennis vocabulary, suitable subjects, use of record evidence, and distinction between a feature and a results list | Written primarily for JHSAA statewide season reporting |
| [`PREPS-STYLE-GUIDE.md`](PREPS-STYLE-GUIDE.md) | Hard-earned corrections to generated season-review writing: angles, varied leads, real stakes, paragraph connections, accurate score language, endings | Some absolutes are **retrospective-specific**, not universal rules for a daily local sports page |
| [`DESIGN-story-forms-from-sports-journalism.md`](DESIGN-story-forms-from-sports-journalism.md) | Ten evidence-driven feature/investigative story forms, including rematches, undercovered athletes, lineup choices, competitive rules, and historical changes | Primarily selects consequential cross-table findings, rather than ordinary beat coverage |
| [`AAR-jhsaa-front-page-story-desk.md`](AAR-jhsaa-front-page-story-desk.md) | Explains deterministic archive headline detectors on the existing `/jhsaa` front page | Its strict noun/number headline register and no-prose design are for **data headlines**, not the full newspaper or signed columns |
| [`2092-annual-report.md`](2092-annual-report.md), [`2113-jhsaa-season-review.md`](2113-jhsaa-season-review.md), [`reports/2035-jhsaa-season-review.md`](reports/2035-jhsaa-season-review.md), [`../2098-season-review.md`](../2098-season-review.md) | Concrete outputs showing what prior agents selected, calculated and compared, including continuity across years and neglected turnaround stories | These are **association reviews / internal research**, generally rich in tables, executive findings and policy calibration. Do not treat them as examples of a finished prep-sports newspaper. |
| [`JHSAA_HIGH_SCHOOL_TENNIS_REPORTING_GUIDE (1).md`](JHSAA_HIGH_SCHOOL_TENNIS_REPORTING_GUIDE%20(1).md) and [`writing-guide-update.md`](writing-guide-update.md) | Identical copies of a longer reporting guide that adds a consequence filter and retrospective-selection advice | Keep the duplicates identifiable; do not assume file naming or the unnumbered version establishes editorial precedence |
| [`design-story-real-news.md`](design-story-real-news.md) | Another stored version of the story-form design; source file displays encoding issues | Prefer the correctly encoded canonical design file for agent reference unless specifically investigating past revisions |

### What the other agent learned, and what should *not* become universal rules

The season reports demonstrate real analytical continuity: comparing one year to another, noticing transfer-created opportunity, identifying undercovered turnarounds, and testing whether the postseason structure behaved as intended. But they remain largely analyst documents. Many open with “Executive findings,” “How this review reads the season,” “Championship ledger,” or methodological notes and repeatedly frame results as evidence for changing rules.

**Preserve two distinct editorial products.** An *association review* can explain bracket design, competitive balance, simulation calibration and official outcomes. A *newspaper* must make selective assignments from within the world: ordinary local results, previews, agate, a player story, a school notebook, and occasionally a signed argument. The same evidence can feed both, but the finished copy and its intended reader differ.

Three instructions in earlier guides were reasonable for a consequential statewide season retrospective but should **not** be applied to every newspaper genre:

1. **Consequence gate:** A statewide retrospective should prioritize events changing a title or competitive path. A local correspondent also covers a losing team, routine dual, graduating senior or coaching change because of the enduring local beat. Lower stakes do not mean zero news value.
2. **History limited to three triggers / one sentence:** Efficient in a focused match report, but unsuitable as a universal rule for a coach profile, regional preseason package, multi-year player career, historical column or local-life feature. Use as much accurate history as the assigned form earns.
3. **No adjectives in headlines / obligatory quotes, scenes and counterfactuals:** These are safeguards against repetitive generated prose and deterministic front-page headlines, not requirements that every results brief, photo caption, or opinion column must satisfy. A results block needs none of them. A compelling feature may need some, but their presence is not proof of good reporting.

**Do retain the real error corrections:** No “court” for a tennis point or won position; “flight” for individual tournament groupings; don't use “card” for a lineup; never invent or contradict scores; don't spill simulation metadata, detector forms or export table names into reported prose; don't recycle invented interviews between seasons.

The provided *Courier-News* sports pages and OSAAtoday articles clarify what is missing from many older internal reviews: editorial packages mixing results and reported features; recurring reporters who remember the same players; local development programs and family/coaching relationships; and history treated as working material for previews, not only as an anniversary or a drought. These are **reference patterns**, not authority to infer sensitive attributes or invent unsimulated competitive events.

For a fiction sports-writing assignment, first identify the **publication, beat, edition, article form and reader**. Only then select from the available evidence and write. When the assignment is instead an **internal season analysis**, use the analytical reporting conventions without pretending it is newspaper copy.

## What has actually been researched

This is a working editorial model, not a claim that all regional archives have been read. Directly readable 1990–94 examples include:

- *Heppner Gazette-Times* (Oregon), **Sept. 9, 1992**, Heppner–Grant Union football: a 3–0 game matters because of the remembered interschool losing streak, which transcends one sport. https://oregonnews.uoregon.edu/lccn/sn97071042/1992-09-09/ed-1/seq-2.pdf
- *Heppner Gazette-Times*, **Apr. 13, 1994**, Ione–Echo tennis: boys' and girls' match scores and an abbreviated squad make local coverage without forced significance. https://oregonnews.uoregon.edu/lccn/sn97071042/1994-04-13/ed-1/seq-2.pdf
- *Edmond Evening Sun* (Oklahoma), **Jan. 12, 1990**, Norman–Edmond basketball: a rematch preview grounded in previous meeting, injuries, averages, and coaching history. https://gateway.okhistory.org/ark:/67531/metadc2347262/m1/9/ocr/
- *Sapulpa Daily Herald* (Oklahoma), **Nov. 26, 1990**, Blue–White preseason scrimmage: meaningful reporting before an official season has begun. https://gateway.okhistory.org/ark:/67531/metadc1497407/m1/5/
- *Elk City Daily News* (Oklahoma), **Jan. 16, 1990**, Bi-County tournament: compact multiple-school results with immediate bracket consequences. https://gateway.okhistory.org/ark:/67531/metadc2375342/m1/4/
- *Perry Daily Journal* (Oklahoma), **Jan. 19, 1990**, Morrison–Glencoe: concise boys'/girls' account with the next placement games in view. https://gateway.okhistory.org/ark:/67531/metadc2255811/m1/7/

Do not infer that the newspapers in every other state used exactly these conventions. The wider archive map below marks research targets, not verified stylistic evidence.

## Close reading — *Courier-News* Central Jersey prep-tennis pages (user-supplied primary examples)

**Source and limits.** Eight screenshots supplied on Nov. 22, 2026, from *Courier-News* pages displayed on Newspapers.com. They show portions of pages, not every article in full. They are **not stored in this repository**, and most screenshots do not expose their original page URL or issue date. Do not invent dates, complete headlines, bylines or words hidden by screenshot cropping. Where a year is indicated below, it comes from visible text, not an assumption about the full issue.

This sample is especially valuable because it captures several **functions coexisting within the same local paper**, rather than cherry-picking feature stories. It is a reporting **corpus**, not evidence that every item is a sports column.

| Screenshot | Visible material | Editorial form and reusable lesson |
|---|---|---|
| `IMG_3367(1).jpeg` | “Westfield takes all 5 flights in Union tennis tournament,” a *Courier-News* staff report; Westfield's tournament win, points standings, names of flight winners, other contenders, full bracket results and regular-season results | **Event story plus statistical agate**: an economical lead summarizing the headline result, then dense secondary results. The prose doesn't have to repeat each score. The smaller schools remain visible in the results package. |
| `IMG_3372(1).jpeg` | “New faces bringing change to tennis,” a staff feature on minority participation in Central Jersey high-school tennis, with athletes and program coaches quoted, photographs, and surrounding schedules/scores | **Community / participation feature**: high-school sport is about who gets to play, coaches, access and changing school culture, not only championships. Its sourcing goes beyond a standings table. Sensitive demographic facts here come from actual interviews; an agent must not manufacture them in a fictional world. |
| `IMG_3374(1).jpeg` | Union County tournament result listings, including Camille Alston at third singles, and separate regular-season duals | **Agate as a publication product**: bracket placements, seed numbers, flight scores, team totals and regular-season results coexist in compact, structured type. Scores are useful on their own; not every result gets an article. |
| `IMG_3380(1).jpeg` | “City tennis program’s net worth: priceless,” by Leslie Baron Van Dorn, a correspondent; profile of Donald Van Blake and Plainfield's youth-tennis development, school program, city courts and clinics | **Local institution / coach profile**: follows a person, relationships across organizations, facilities and the youth-to-school pipeline. The protagonist is not necessarily a champion. The writer develops the story through interviews, historical details, and lived consequences. |
| `IMG_3384.jpeg` | *Courier-News*, May 19, 1991, “The net result is very good tennis,” by Luther Turmelle; four players from four Central Jersey schools linked to a local tennis association's development work, with youth participation and player quotes | **Multi-school feature via a shared institution**: the connection among the players is a community development program rather than a single fixture. Region-wide coverage may join schools through coaches, facilities, training and recruiting networks. |
| `IMG_3382.jpeg` | *Courier-News* “ALL-AREA Boys Tennis” package: named All-Area, All-Somerset, All-Hunterdon and All-Union-Middlesex selections; athlete photos/cards, season and career highlights, favorites, Coach of the Year feature on Van Blake | **Editorial package and recognition**: a whole section is assembled from multiple components—selection lists, concise player biographies, portraits, honors, and a reported coaching feature. The newspaper's All-Area distinctions are **media selections**, separate from the association's canonical awards. |
| `IMG_3383.jpeg` | A girls' tennis year-end package referencing 2000 results: Top 10 area teams, Plainfield's 15–2 conference-title season, coach Esta Perle on the team's changing reputation, “Team match of the year” | **Season verdict plus rankings**: editor-selected top tens, story of an emerging program, quotes, and a named match let the paper evaluate a season on more than official placement. Rankings and “match of the year” are editorial claims that need declared criteria. |
| `IMG_3376.jpeg` | A subsequent girls' tennis outlook organized by Union, Middlesex and Hunterdon counties, referencing 2000 results and returning players; notes Camille Alston's move to first singles and school-by-school expectations | **Geographically organized preseason survey**: four- to six-sentence team notes, projected lineup movement, returning starters, prior records, and a specific reason to watch each team. The county subdivisions are editorial geography, not necessarily the game's competition structure. |

### What the spread teaches that isolated articles do not

**1. The unit is the sports *page* or *package*, not the single generated story.** One page can contain a 300-word match account, a block of tightly set individual results, several brief regular-season scores, and a photograph. Another carries a long reported community feature alongside schedules and unrelated sports. An agent asked for an “edition” should choose a **mix of forms**, rather than writing five similarly sized features.

**2. “Agate” is its own form.** Traditional agate is the compact small-type statistics/results section. The Union tournament page demonstrates that scores, brackets, seeding, records and classifications can be presented without narrative padding. Generate it deterministically from game records wherever possible. For tennis, preserve distinct team competition, singles and doubles flights, seeds, set scores and placements.

**3. Recognitions can be the newspaper's own.** A *Courier-News* All-Area team and Top 10 are editorial judgments, not state association honors. A simulated newspaper could produce a year-end All-Area squad, coach of the year, or “match of the year” as **publication-owned awards**. Cite on-record criteria and label the newspaper as selector. Never add them to the simulation's official honours database or imply they were sanctioned by the league.

**4. Coverage follows player and coaching pathways.** The Plainfield examples include youth-tennis programs, school competition, a longstanding coach's work, and later seasonal coverage. Do not infer that these different pieces establish a single causal history; the broader lesson is that reporters connect games to the people, places and organizations that make participation possible.

**5. The local paper covers multiple levels of significance without apology.** A player appearing only in an individual results listing, a school getting two sentences in the county preview, a tournament champion getting a staff report, and a coach getting a feature all belong in one editorial system.

**6. Geographic packages make scale possible.** County- and area-based preseason rundowns let a single staff cover many schools without a standalone article for every one. School-level notes may be short, but they can contain years of accumulated context.

**7. Photos, captions and sidebars are reporting units.** A photo caption identifies a person, school and what was happening. A sidebar gives a concise season/career record. An agent can produce caption text and a photo *brief*, but must not claim a fictional photo actually exists if no image is supplied or generated.

**8. These are not columnist samples.** The signed community stories are reported features; staff recaps and result blocks are straight coverage. The columnist role needs its **own primary-source examples** of signed, opinionated argument. Do not teach a columnist by relabeling these features as columns.

### Add these publication forms to the agent's toolbox

- **Agate / results wire** — structured team and individual scores, standings and seed placements. Produce from verified results, with little or no prose.
- **County/area preseason survey** — a compact paragraph per school, ordered by editorial territory; note graduating contributors, returning starters and unresolved lineup questions.
- **All-Area / year-end selection package** — newsroom's selections, short player cards, methodology, team records, noteworthy matches, accompanying reported piece.
- **Youth-to-varsity pipeline feature** — a person or local program connects athletes across schools and seasons; requires established development-program, coaching, resource or facility evidence, or clearly bounded and internally consistent fictional context.
- **Community change feature** — participation, facilities and access to sport; requires corroborated source facts. Never invent race, ethnicity, poverty, disability or other sensitive demographic attributes about youth athletes to supply a story.
- **Coaching legacy feature** — decisions, apprenticeships, facilities, playing opportunities and remembered seasons, with attributed quotes and multi-year records when available.

### Two sample editorial assignments (newspaper-first, no simulator integration required)

**Tournament edition:** “Using only this completed county tournament and related regular-season match records, publish a local sports page: one 180–280-word staff report on the winning team, one compact standings-and-flight-results block, and three brief notes on schools that didn't win. Keep the result block strictly factual. Do not invent missing flight scores.”

**Season-end area package:** “Using the full year's school, player and coach records, commission a newspaper-owned All-Area selection and a county-by-county season notebook. Include explicit selection criteria, player cards with actual accomplishments, one carefully reported coach/program feature, and one signed column *only if* the evidence supports a contestable opinion. Distinguish editorial honors from official awards.”


### Evidence for a separate columnist

- Pew Research Center, **2005**, *Reporting Style*: 90% of sports columns in its sample contained opinion or speculation; 18% of front-page sports stories were opinion columns. This is a **later empirical comparison**, not a measurement of the 1980s/1990s. https://www.pewresearch.org/journalism/2005/08/22/reporting-style/
- *Sports Journalism: A Practical Introduction*, chapter excerpt: traditional sports desks distinguished news, match reporting, features, opinion, and the chief sports writer's descriptive “colour piece.” https://uk.sagepub.com/sites/default/files/upm-assets/57845_book_item_57845.pdf
- New Jersey: *Star-Ledger* columnist Jerry Izenberg began at the paper in the 1960s and had a long-running signed column. His work is a **research subject**, not an article corpus sampled here. https://rutgersfoundation.org/distinguished-alumni/1991/jerry-izenberg
- New Jersey's state athletics association lists past sports-reporting honorees including *Courier News* reporter Harry Frezza (1990), and *Star-Ledger* staff. These names help locate actual archival material; they do not establish style from awards alone. https://www.njsiaa.org/sites/default/files/documents/2020-10/njsiaa-sport-award-recipients-full-list.pdf
- North Carolina Scholastic Media Association contest definitions distinguish factual sports articles from signed, accurate sports opinion columns. https://www.ibiblio.org/ncsma/contest%20descriptions.pdf

## Five editorial roles, not five voices pasted over the same score

### 1. Local correspondent
**Territory:** one town, school or 3–10 neighboring schools. **Duty:** show up for the entire season, including bad records, JV, departing seniors and coaching changes. **Records:** all of that school's games, roster, last year, upcoming fixtures, coaches, siblings, previous clips. **Output:** school notebook, local match story, brief, season outlook and follow-up. **Selection standard:** relevance to the local community comes before statewide importance.

### 2. Beat reporter
**Territory:** one team, conference, athlete, coach, rivalry, recruiting region or competition. **Duty:** build expertise and test prior expectations. **Records:** subject history, tactical evidence, direct opponents, earlier articles and next match. **Output:** reported feature, scouting analysis, rematch preview, season-long account. **Selection standard:** did our understanding of the subject change?

### 3. Area or regional desk
**Territory:** nearby towns, counties, classifications or rival leagues. **Duty:** show which results affect the area's races and how programs compare. **Records:** standings, region-wide fixtures, opponent strength, district structure and history. **Output:** weekend roundup, sectional preview, district race, regional notebook. **Selection standard:** which event matters for several communities?

### 4. Statewide desk
**Territory:** statewide, *selectively*. **Duty:** elevate consequential or distinctive local stories, major matches, changes in the competitive order and tournament developments. **Records:** candidate leads from local and regional desks plus bounded statewide detectors. **Output:** state tournament feature, championship report, statewide notebook, significant-record analysis. **Selection standard:** why would a reader outside the school's town care? No obligation to cover everything.

### 5. Sports columnist — a signed, continuing point of view
**Territory:** a paper's sports culture, a town or region, or the statewide sports landscape. **Duty:** make a defensible judgment about a development the reporting has established. The columnist may be skeptical, admiring, impatient, funny, nostalgic or wrong. The columnist is an observer of the fictional competition, not a voice delivering the developer's interpretation of game mechanics.

**The distinction:** A beat writer reports that a coach changed the doubles ladder three times and still qualified for State. A columnist might argue that the coach has become the best evaluator of overlooked players in the region, or that the program is mistaking improvisation for a durable solution. Both require facts. Only one advances an explicit opinion.

**Column-worthy subjects:** an aging coach whose program has outlasted rivals; a rule that repeatedly benefits well-resourced schools; a small-school rivalry whose meaning has changed; a talented athlete obscured by a weak team; whether a long-standing championship tradition still reflects competitive reality; the gap between preseason praise and what actually occurred; what a graduating class leaves behind.

**Five forms:**
1. **Argument column:** one contestable claim, strong evidence, a relevant counterexample, a concrete ending.
2. **Sports-page notebook:** two or three observations that share a locale or question, with unequal attention and a clear signed perspective.
3. **After-the-game column:** a consequential match seen through one person, decision, or historically meaningful moment; distinguish observed match facts from interpretation.
4. **Season reckoning:** revisit what this columnist wrote or expected in preseason, including mistakes and changed judgments.
5. **Local-life column:** what a team, rivalry or practice says about a place, supported by the archive and compatible fictional texture—not generic sentimental praise of small towns.

**Recurring column identity:** Give the writer a stable byline, coverage territory, recurring interests, known historical touchstones, specific previous positions, and an ability to acknowledge a mistake. Give each columnist a point of view, **not a personality caricature**. One might care deeply about small-school tennis; another scrutinize championship access. Avoid invented regional dialect, folksy catchphrases, universal cynicism, and constant indignation.

**Opinion is not a license to change facts.** Scores, athletes, results, chronology, eligibility, transfers, awards and known player attributes remain controlled by the game. A columnist may form opinions about decisions but cannot create a competitive fact to strengthen an argument. Never imply an accusation of misconduct without a game-established fact and explicit host permission. Avoid assigning intimate, sensitive or stigmatizing characteristics to fictional minors.

**No compulsory columns.** Publish only when a real observation supports a considered view. A week of routine results may deserve no column. Never use a column to restate all the week's scores.

**No imitation of a living or historically identifiable writer's exact voice.** Research structural techniques from many authors; create original fictional bylines and prose.

## Story forms for reporters

1. **Score-and-consequence dispatch:** result, decisive positions/plays, consequence, next opponent (100–250 words).
2. **Preseason outlook:** prior year, losses to graduation, returning core, uncertainty and first test (250–500).
3. **Rematch preview:** earlier meeting, changed personnel, what will be tested (200–450).
4. **School notebook:** three to five varied, short items across teams, including a low-profile program (150–400 total).
5. **Regional tournament roundup:** several results; who advanced, who went home, what follows (150–400).
6. **Player profile:** grade/role, development, program context, record, future uncertainty (350–800).
7. **Program arc:** multi-year evidence, coach, graduating classes, transfer changes, expectations (350–800).
8. **Postseason notebook:** paths to qualification, surprising exits, rematches and overlooked contributors.
9. **Tactical close read:** supported lineup/position or play mechanism, not invented point-by-point evidence.
10. **Season follow-up:** revisit a prior story or prediction, name the change, identify next year's open question.

Article form is separate from editorial role: a local writer and statewide reporter can both write a profile, but their reason to assign it differs.

## Voice and cadence

- Report first: name the person, contest, opponent, consequence or concrete observation near the start.
- Use prior history as a working beat reporter would: last year's seniors, earlier losses, evolving partnerships, coaching continuity, district rivals and previous predictions.
- Numbers must explain something. A 9–11 team may warrant a feature; 20 wins do not automatically warrant a column.
- Use ordinary sports vocabulary correctly. In tennis, a team contest is a *dual*; its singles/doubles components are *matches*; *court* is the physical playing place, not a synonym for a point won.
- Vary lengths and page hierarchy. A full sports section mixes one prominent story with briefs, schedules, results, notebooks, and occasional signed opinions.
- Write the same place over time without re-introducing its entire history each week.
- Avoid grand claims, fake cliffhangers, invented universal lessons and modern engagement bait.
- An opinionated sentence belongs in a clearly labeled signed column; straight reporting stays distinguishable from it.
- Fictional issue dates may be assigned post-hoc anywhere **within the sport's season**. Preserve the order of matches and of what readers could know; exact calendar reconstruction is not required.

## Fiction and reporting integrity

The simulated record is authoritative. When permitted by a fictional-world editorial policy, create compatible atmosphere, observations, practical details and short imagined dialogue; keep an internal **authored-fiction ledger** linked to the story. Never contradict known results. Avoid false exact play descriptions where the engine has only set or match scores. Do not invent injuries, transfers, suspensions or other competition-changing events.

For completed one-shot seasons, construct articles in event order using **as-of snapshots**. Preseason articles cannot know the eventual champion; the May writer cannot quote June's award result. Once published, an article stays unchanged even if the columnist later changes their mind.

## Agent handoff

> You are writing a sports newspaper in a simulated world. Read this editorial guide and the game's own vocabulary/rules. You are assigned **[role]** covering **[beat/territory]** during **[season/period]**. Inspect only facts available by that fictional publication date, prior clips and the relevant schedule. Identify two or three candidate stories, select the one with the strongest reason for *your* readership to care, then choose a suitable article form and length. If assigned as columnist, articulate a contestable, evidence-grounded viewpoint, with a real alternative interpretation and a distinct signed voice; otherwise report without editorializing. Use genuine names and records, and return a finished story plus a compact **unpublished** evidence record, linked subjects and any new editorial-memory details. Verify all scores and chronology against the game. Never describe pipelines, datasets, prompts or editorial methods in the published text.

### Quality gates

- Is the piece newsworthy for the assigned territory, or merely a notable number?
- Could a reader who followed this paper last year recognize recurring people and expectations?
- Do the factual claims match the game, and does the publication date limit hindsight?
- Do reporters and columnists write materially different kinds of work?
- For a column: is there an actual claim, a reason to believe it, something that could challenge it, and a distinct ending?
- Is this distinct from another desk's article rather than a paraphrase?
- Is there a reason for the story to be this long?
- Is there one observation that could only come from this specific season?
- Would the final copy read naturally on a real local newspaper sports page?

## Research map — verified collections, not all sampled

**NJ:** *Star-Ledger* since 1989, *Hunterdon County Democrat* since 1991; investigate *Courier News*, *The Record*, *Trenton Times*, and columnist archives. https://nj.newsbank.com/  
**TX:** Portal to Texas History, statewide and small-town runs. https://texashistory.unt.edu/  
**OK:** Gateway to Oklahoma History, including readable 1990 papers. https://gateway.okhistory.org/  
**KS:** *Emporia Gazette* 1978–2015 and *Lawrence Journal-World* historical archives. https://www.emporialibrary.org/newspapers  
**CO:** Colorado Historic Newspapers and regional collections. https://www.coloradohistoricnewspapers.org/  
**OR:** Historic Oregon Newspapers, including *Heppner Gazette-Times*, *Sandy Post* and rural titles. https://oregonnews.uoregon.edu/  
**ID:** *Lewiston Tribune* archive and regional newspapers. https://www.boisestate.edu/library/2020/09/02/daily-access-to-idaho-newspapers/  
**WY:** Wyoming Newspapers / Plains to Peaks. https://www.wyomingnewspapers.org/  
**MT:** Historical Society digitized newspapers; Bozeman/Great Falls index (index only). https://mths.mt.gov/research/collections/newspapers/mtnews ; https://www.lib.montana.edu/newspapers/  
**CA:** *San Bernardino County Sun*, *Press Democrat*, California Digital Newspaper Collection. https://cdnc.ucr.edu/  
**VT:** *Rutland Herald* newspaper/microfilm runs. https://www.rutlandfree.org/read-listen/newspapers/  
**PA:** *Altoona Mirror* historical archive. https://altoona.newspaperarchive.com/  
**NC:** NCLIVE county papers and *Wilmington Star-News*. https://www.nclive.org/resource/historic-north-carolina-digital-newspaper-collection  
**GA:** Georgia Historic Newspapers and metropolitan/regional collections. https://guides.libs.uga.edu/newspapers/georgia  
**FL:** *Gainesville Sun*, *Ocala Star-Banner*, *Sarasota Herald-Tribune*, Florida Digital Newspaper Library. https://ufdc.ufl.edu/fdnl

### Next research pass

Sample **complete sports sections across consecutive weeks** for at least one 1980s and one 1990s season, with newspaper, exact date, section/page, byline, role, headline, article length, references to previous reporting, treatment of losing teams, and whether each item is clearly a column. Prioritize direct columnist primary texts in NJ, TX, OK, KS, CO, WY, MT, CA, PA, NC, GA and FL instead of relying on biographical evidence. Record what is actually accessible and do not invent regional stylistic distinctions. Build a small annotated collection of structural moves, not copied passages or a single writer's pastiche.

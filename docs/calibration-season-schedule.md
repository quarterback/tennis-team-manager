# Calibration: NCAA D1 College Tennis Team (Dual-Match) Season & Tournament Scheduling

Numbers-first reference for the team-season simulator. All figures are typical/modal
for NCAA Division I men's & women's **dual-match (team)** play. Individual-only
(fall, NCAA singles/doubles) play is out of scope.

## 1. Season shape & length
- **Window:** spring dual-match season runs ~**January through April** (NCAA team
  championship in May). That is roughly **16-17 calendar weeks**, of which ~**13-14**
  are active dual-match weeks.
- **Total regular-season duals:** typically **~20-25 dual matches** per team
  (regular season, excluding the conference and NCAA tournaments).
- **Sim recommendation:** model a **~12-14 week** spring window with a **25 regular-season dual** target per team (up to a 3-dual weekend).

## 2. Non-conference vs conference
- **Pattern confirmed:** **non-conference duals are front-loaded** (Jan-Feb), then
  **conference play** dominates Mar-Apr.
- **Non-conference volume:** roughly **6-8 non-conference duals** per team.
- **Conference play:** the remainder (~**10-15 duals**), structured as a round-robin
  whose completeness depends on conference size:
  - **Small/mid conferences** (≈8-12 teams): commonly a **single round-robin**
    (play each member once); some smaller leagues run a **double round-robin**
    (home-and-away) because the league is small enough to fit it.
  - **Large conferences** (ACC, SEC, Big Ten, Big 12 at **~14-18 teams**): a full
    double round-robin is infeasible, so they play a **single round-robin or a
    partial/unbalanced single round-robin** (each team plays most but not all
    members once). The ACC historically ran a double round-robin for decades but
    abandoned it after expanding to a 16-team league.
- **Sim recommendation:** every team plays toward a **25-dual** slate aimed at
  **~60% conference** (so standings carry signal): conference = **double round-robin
  for leagues under 10 teams** (it fits), **single round-robin** otherwise, **padded
  with extra intra-conference duals** (not a clean round-robin) where a small league
  can't reach the share. Non-conference fills the rest. Verified ~61% conference,
  exactly 25 duals/team, ~11-12 weeks.

## 3. Conference tournaments
- **Prevalence:** nearly every D1 conference holds a postseason **dual-match
  tournament**; its champion claims the league's NCAA automatic bid.
- **Field size:** varies by league. Large leagues now seat the **full membership**
  (SEC = all **15** men's teams seeded 1-15; ACC = all **16** seeded 1-16). Many
  mid/small leagues take a **top-N cut** (commonly **top 6 or top 8**).
- **Seeding & format:** seeded **strictly by regular-season conference standings**,
  **single-elimination**, with **byes for top seeds** (e.g., SEC top-4 double-bye,
  seeds 5-9 first-round bye; ACC top-4 enter in the quarterfinals).
- **Auto bid:** **yes** — the conference-tournament champion receives the
  conference's **NCAA automatic qualifier (AQ)** bid.
- **Sim recommendation:** single-elimination, **seeded by conference standings**;
  **full-field** bracket for large conferences (≥14), **top-8** (or top-6 for small
  leagues) otherwise; **byes** for top seeds; **champion = NCAA auto bid**.

## 4. NCAA selection
- **Bracket:** **64-team**, single-elimination national championship.
- **Bids:** **27 automatic bids** (one per qualifying conference, to its tournament
  champion) + **37 at-large bids**.
- **At-large & seeding driver:** the selection committee uses a team power
  index — primarily **ITA team rankings**, plus win-loss record, strength of
  schedule, head-to-head vs tournament teams, and conference finish. Top **16
  seeds** are protected and host early rounds.
- **Eligibility floor:** a team must be at least **.500** vs Division I opponents.
- **Sim recommendation:** **64-team** bracket = **~27 AQs + ~37 at-large**; rank
  teams by an **ITA-style power index** to pick at-large teams and to **seed the top 16** (protected/hosting seeds).

## 5. Weekly cadence
- **Typical load:** **1-2 duals per week**. Single mid-week match is common early;
  the modal pattern is a **weekend pair** (e.g., **Fri + Sun** or **Sat + Sun**).
- Conference weekends frequently pair two league opponents on back-to-back days.
- **Sim recommendation:** **~1.5 duals/week** on average — model most weeks as a
  **weekend doubleheader** (2 duals) with occasional single-match weeks.

## Sources
- https://www.tm3sports.com/frequently-asked-questions (matches per season; non-conf/conf split)
- https://shoprestring.com/blogs/news/ncaa-college-tennis-season (Jan-Apr/May season window)
- https://www.collegepipe.com/blog/82/college-tennis-rules-dual-match-formats (3-6 dual format)
- https://en.wikipedia.org/wiki/Atlantic_Coast_Conference (ACC double round-robin history)
- https://www.secsports.com/sec-mens-tennis-tournament (SEC tournament: 15 teams, seeding, byes, single-elim, auto bid)
- https://theacc.com/feature/mens-tennis-championship (ACC tournament: 16 teams, seeded single-elim)
- https://theacc.com/news/2026/4/13/virginia-wake-forest-win-regular-season-title-bracket-set-for-2026-acc-mens-tennis-championship.aspx (ACC bracket/seeding by standings)
- https://www.ncaa.com/news/tennis-men/article/2026-04-27/teams-announced-2026-ncaa-divison-i-mens-tennis-championship (NCAA 64-team field)
- https://blog.rallyfuel.com/2026-conference-tennis-champions-ncaa-tournament/ (27 auto bids + 37 at-large; AQ to conf champ)
- https://wearecollegetennis.com/ita-rankings/ (ITA rankings as selection/seeding driver)
- https://bucknellbison.com/news/2026/1/22/mens-tennis-hosts-mount-st-marys-saturday-sundays-match-vs-saint-francis-postponed (weekend Fri/Sun cadence example)

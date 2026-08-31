# JHSAA Player Development: The Full Record, 2027–2062

**Author's desk note.** This reads every season export from 2027 through 2062, with no gaps and tracks the same handful of player-development signatures across all of them, so the 2060 engine can be judged against the entire history of the association rather than against one prior season. Source panel: `era_panel.csv`, one row per season per gender, ~66 season-genders, ~1.1M player-seasons.

## The five eras the data actually shows

The exports reveal more than one development regime. Read purely from the numbers, with no reference to the changelog, the association has lived under five distinct development behaviors:

| Era | Seasons | Fresh. arrival | Arrival spread (sd) | Senior finish | Ready-freshman rate | Fresh. share of top-9 | YoY dev sd | First-time champs / yr | POY underclassmen |
|---|---|---|---|---|---|---|---|---|---|
| 1. Original lockstep | 2027–33 | 50.2% | 11.5 | 75.2% | 1.4% | 10.6% | 2.44 | 7.8 | 0% |
| 2. Arrival lifted | 2034–36 | 60.8% | 12.5 | 75.2% | 6.9% | 18.8% | 2.85 | 6.7 | 0% |
| 3. Finish lifted (long plateau) | 2037–53 | 60.9% | 12.5 | 87.1% | 2.9% | 15.1% | 3.70 | 4.2 | 8% |
| — Transition turbulence | 2054–57 | 61.0% | 12.6 | 78.1% | 2.9% | 14.9% | 4.42 | 5.1 | 22% |
| — Calm before (Era 3 behavior) | 2058–59 | 61.1% | 12.6 | 86.9% | 1.5% | 12.5% | 3.35 | 5.8 | 6% |
| 4. Per-player trajectories | 2060–62 | **68.4%** | **15.6** | 87.1% | **14.3%** | **21.7%** | 3.43 | 6.8 | **100%** |

Column definitions:
- **Freshman arrival** — mean `current_grade / potential_grade` for 9th graders. How ready a freshman is relative to their own ceiling.
- **Arrival spread** — standard deviation of that ratio. How *different* freshmen are from one another on entry.
- **Senior finish** — same ratio for 12th graders. Where careers end up.
- **Ready-freshman rate** — share of freshmen whose `current_grade` exceeds the best senior on their own roster. The direct measure of ladder reordering.
- **Freshman share of top-9** — share of each roster's nine best (by ability) who are freshmen.
- **YoY dev sd** — standard deviation of one-year `current_grade` change across all carryover players. How *unevenly* players develop.
- **POY underclassmen** — share of Player of the Year awards won by 9th–11th graders.

## What each era did

**Era 1 (2027–33): the lockstep bands.** Freshmen arrived at half their ceiling, seniors finished at three-quarters, and everyone climbed the same four steps. The ready-freshman rate was 1.4%: a freshman better than every senior on his own team was a 1-in-70 event. Freshmen filled about one in ten top-nine slots. Development variance (YoY sd 2.44) was the lowest in the archive — nobody grew differently from anybody else. The one thing this era did produce was competitive churn at the top: nearly 8 first-time champions per year per gender, because with everyone developing identically, a program's fortunes tracked its graduation cycle almost mechanically.

**Era 2 (2034–36): arrival lifted, finish not.** Freshman arrival jumped ten points to ~61% in a single year while seniors still finished at 75%. The immediate effect was the biggest one-year freshman surge in the record: ready-freshman rate quintupled to 7%, freshmen took 22% of top-nine slots in 2034. But with the finish band unchanged, that surge *decayed* — 22% → 18.5% → 15.9% across the three seasons — because stronger arrivals were compressing into the same 75% ceiling. Freshmen came in ready and then ran out of room to grow.

**Era 3 (2037–53): finish lifted, seventeen-season plateau.** Senior finish jumped to 87% and stayed there for seventeen years, the longest stable stretch in the archive. Everything else settled: ready-freshman rate ~3%, top-nine share ~15%, YoY sd 3.7. This is the era most of the association's history was written in — the Larchmont Ridge and Fletcher-Garrison Hall dynasties, the Triston Inman and Braelyn Alston careers, the multi-year 8A chaos. It was also the era in which first-time champions fell to ~4 per year per gender: a stable development regime let established programs stay established.

**2054–57: turbulence, not an era.** (2058–59 then snap fully back to Era 3 behavior — senior finish 87%, dev sd ~3.4, ready-freshman rate 1.5% — so the engine landed in 2060 from a stable baseline, not out of chaos.) Senior finish dropped back to 75% for three seasons (2054–56), then snapped to 87% again in 2057. In 2054 the whole field was *re-rated downward* (mean YoY development −1.8 instead of the usual +5), and YoY sd spiked to 5.8, then again to 5.8–6.7 in 2057 — the two most chaotic development years on record. The ready-freshman rate hit a record low of 1.2% (boys) / 0.9% (girls) in 2057 on the eve of the new engine. In hindsight, this whole window reads as two systems fighting: cohorts drawn under old bands aging through one, cohorts under a different regime aging through another, with the whole-field numbers reflecting whichever was larger that year.

**Era 4 (2060–62): rolled per-player trajectories.** Every signature moves at once, and in the intended direction:

- Freshman arrival to **68%**, the highest ever, and the arrival *spread* to 15.6 — the first era where freshmen got more varied, not just stronger.
- Senior finish held at **87%**, identical to Era 3. This is the tell that the engine changed the *path*, not the destination: if the scale had simply been inflated, seniors would have moved too.
- Ready-freshman rate to **14.3%** — five times Era 3, twice Era 2's peak, and, unlike Era 2, it is *not decaying*: 13.4% → 14.0% → 13.5% boys, 13.5% → 14.8% → 16.3% girls. Because the finish band was already lifted, stronger arrivals have room to keep growing.
- Freshman share of top-nine to **21.7%**, and holding, versus Era 2's collapse from 22% to 16% in three years.
- YoY dev sd of 3.43 — *lower* than the plateau era's 3.70. The new engine did not make development noisier. It made it more varied at entry while keeping annual growth steady, which is exactly the difference between "variance" and "randomness."

## The finding I did not expect: Player of the Year

Under every prior regime, Player of the Year went to seniors. In 2059, the last pre-engine season, exactly zero of 24 awards went to underclassmen. Era 1 and Era 2: 0% underclassmen. Era 3: 8%. Even the turbulent 2054–57 window only reached 22%.

**From 2060 forward, all 72 Player of the Year awards across three seasons and both genders went to 9th, 10th, or 11th graders. Every single one.** Not a majority — a hundred percent, three years running.

That is the starkest single signature of the new engine in the data, and it follows directly from the arrival shift: when a meaningful fraction of freshmen and sophomores now arrive ahead of the seniors on their own roster, and the award tracks the best single-season performer, the award migrates to whoever is on the steepest part of their curve — which under rolled trajectories is almost never a senior on the flat end of theirs. Whether a senior *should* ever win POY again under this model is a design question, not a data one, but it is worth knowing that as of three seasons in, the answer in practice is no.

## How competitive order responded

First-time champions per year per gender: Era 3 plateau ~4.2. Year one of the new engine, 2060: 5 boys, **10 girls** — the largest single-season reshuffling of girls champions in the archive. Then 7/7 in 2061 and 6/6 in 2062. The order is re-forming, at roughly Era 1–2 levels of churn rather than Era 3's stability. Three seasons is too early to say where it settles, but the shape — a one-year shock followed by convergence — is the same shape every prior regime change produced.

## What "settled" means, numerically

The engine is stable where it should be and still moving where it plausibly should:

- **Stable at three years:** freshman arrival (68.2 / 68.2 / 68.3 boys), arrival spread, senior finish, boys ready-freshman rate, top-nine share.
- **Still moving:** girls ready-freshman rate (13.5 → 14.8 → 16.3), still climbing at year three while the boys number is flat. Either the girls pool is finding a higher equilibrium or the engine expresses differently by gender; a fourth season will say which.
- **Fully settled on day one:** POY at 100% underclassmen from 2060 onward, with no drift at all.

## One-paragraph version for the blog

Across thirty-three seasons the JHSAA has run four development regimes, and the exports can tell them apart without the changelog. The first three each moved one number — arrival, then finish, then nothing for seventeen years — and every one of them left freshmen climbing the same stairs in the same order. The 2060 engine is the first that changed the *shape* of a career rather than its endpoints: freshmen arrive stronger and, for the first time, more different from each other; the ready-freshman rate quintupled and, unlike the 2034 surge, is not decaying; seniors finish exactly where they always did; and annual development got steadier, not noisier. The one place it overshot the old world completely is Player of the Year, which has not gone to a senior since the engine went live.

---
*Supporting data: `era_panel.csv` (per-season, per-gender panel, all metrics above, 2027–2062 complete).*

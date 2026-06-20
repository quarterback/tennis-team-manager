# AAR — ITA-style rankings (team, singles, doubles) + seeding

## What shipped
Replaced the invented Power Index ordering with an **ITA-style ranking system** for
college, and wired it through the rankings UI and NCAA seeding.

- **Team rankings** order by ITA points and the rankings page shows a **Points**
  column; fixed national field — top 75 (D1/D3), top 50 (D2).
- **Player rankings** as a **Teams / Singles / Doubles** toggle on the same page.
  Singles ranks players; Doubles ranks the *pairs* that play together. Singles top
  125 (D1/D3) / 75 (D2); doubles top 60 / 40; a pair needs ≥3 matches together; only
  entities with a win are ranked (as in the real ITA).
- **NCAA seeding** (selection, seed order, snub board, live bubble/projection) now
  runs on the ITA **team** points instead of the Power Index `seed_score`.

## The algorithm
`score = Σ(best-10 win quality) / (counted wins + loss drag)`, scaled to ~0–92.
- A win's value is the **opponent's quality**, ×1.10 for a road win; only your best
  10 wins count, all losses count.
- **Loss drag is inverse to opponent quality** — losing to a weak team hurts most,
  losing to a ranked team barely dents you (the articles never gave the loss formula,
  so this is the documented modelling choice).
- One shared core (`_ita_score` / `_ita_scale`) serves teams, singles, and doubles.

## The key flaw and fix (synthetic-world tweak)
The faithful **iterate-opponent-quality-to-convergence** version degenerated: a tight
mid-major round-robin (Patriot/CAA) bootstrapped each other to the top — Boston U #1
over Wyoming 23-3. The eigenvector-style fixed point rewards dense interconnection,
not absolute quality. **Fix:** don't iterate to convergence — anchor opponent quality
to the **Power Index's rank-percentile** (one pass). That keeps the ITA shape (best
wins, road bonus, loss drag) while staying anchored to real strength. After the fix
the order is sane (Wyoming, Dayton, then the power conferences), so the Power Index
earns its keep as the stability anchor even though it no longer orders anything.

Player rankings reuse the same trick, anchored to **player STR** percentile (and a
pair's STR = the mean of its two players).

## Data sources
- Teams: the season's dual results (RANKING_ROUNDS), opponent quality = `power_index`.
- Players: every completed singles/doubles line in `lines_json` already carries the
  court's `home_pid`/`away_pid` (and `home_pids`/`away_pids` for doubles), so the
  player-vs-player / pair-vs-pair graphs come straight out of the stored lineups.

## Seeding switch
`select_field` now takes an explicit `{school: seed value}` map; the seasonmode
callers pass `ita_team_points`. Because the ITA points already encode quality wins /
strength of schedule, the earlier explicit **power-conference preference is dropped**.
Verified: NCAA top-8 seeds match the ITA top-8 and the bracket plays to a champion.

## Notes / dials
- **Points steepness** (`_ita_scale` exponent 1.8) and **best-N / road-bonus /
  loss-drag** are easy constants if the spread or weighting wants tuning.
- The real ITA points tail (92 → 7) is steeper than ours (92 → ~50); a bigger
  exponent closes that if desired.
- The Power Index lives on as a secondary rankings column and as the opponent-quality
  anchor — it just no longer orders rankings or seeds the bracket.

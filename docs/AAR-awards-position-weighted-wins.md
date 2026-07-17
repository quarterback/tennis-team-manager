# AAR — Awards select on position-weighted wins (rating removed)

**Date:** 2027-07-17
**Scope:** `app/web/awards.py` — `_POS_W` / `_DBL_W`, `_eligible`,
`_national_order` (+ `NAT_BAND`, `_resume`), `season_awards`, `honor_records`.
All-American, All-Conference, and Player of the Year (national + conference) all
consume the same `_eligible` list, so this one function governs every individual
honor. No schema change; nothing persisted differently.

## The bug this fixes

A player was named **Second Team All-American + Conference Player of the Year** on
a **21-4** record that was padded at the bottom of the lineup — 7-0 at 4th singles,
5-2 at 3rd, only 2-1 / 2-1 at 1st / 2nd. He barely played the top courts, so the
honor didn't reflect real quality.

**Root cause:** the old performance score was
`total_wins × win% × _POS_W[line] × team_factor`, where `line` was the player's
**STR rank on his own team**, *not the line he actually played*. So all 21 wins
were credited at one position weight, and `_POS_W` only tapered 1.00 → 0.75 across
S1–S6. Padding a soft 4th/5th-singles record inflated `total_wins` with no
discount. Rating (STR) otherwise drove nothing but a deep tiebreak.

## Owner's choices (locked)

- **Selection is position-weighted WINS ONLY.** No rating, no win%, no team factor
  in the base score. "It's only wins at the positions."
- **Weights (owner-set):** singles **1.00 / 0.80 / 0.60 / 0.40 / 0.20 / 0.10** for
  lines 1–6; doubles **0.75 / 0.50 / 0.25** for lines 1–3.
- **Wins count at the line ACTUALLY played**, taken from the per-line box record
  (`seasonmode.player_line_records`), not the player's team rank.
- **STR plays no part** in selection. It is carried on each record for display only.
- **National tiebreak (this round's addition):** for **national** honors only,
  when players are within ~10% of each other, the tougher résumé wins the spot —
  **team record + conference prestige**, equal weight, higher-prestige-conference
  players boosted. Per-conference honors keep the raw position-weighted order
  (prestige is constant inside a conference).
- **"Unusually strong team" is handled organically** — no special modifier. A
  lower-line player on an elite team still places because they personally pile up
  wins at a meaningful line, which is exactly what the score rewards.

## How it works

`_eligible` (one pass, min `MIN_MATCHES=4` singles matches):

```
perf = Σ_line (singles_wins_at_line × _POS_W[line])
     + Σ_line (doubles_wins_at_line × _DBL_W[line])
```

Sorted by `(perf, wins, -losses)` desc. Each record also carries `team_wpct`
(from the team's dual record) and `conf_prestige` (from `ncaa.conf_prestige`) for
the national reorder, plus `str` for display and `line` (the primary line played)
for context.

`_national_order` reorders that list for national awards:

```
nat_score = perf × (1 + NAT_BAND × résumé)          NAT_BAND = 0.10
résumé    = 0.5 × team_wpct + 0.5 × conf_prestige   (both in [0,1])
```

Because the boost tops out at `NAT_BAND` (10%) of a player's own `perf`, it can
lift a player over someone **within 10% of them**, but never over a clearly
greater record. Worked example: A `perf 20` weak résumé (nat 20.8) vs B `perf 19`
elite résumé (nat 20.8) → B pulls even and takes the higher spot; C `perf 17`
(15% below A) with a max résumé reaches only 18.6 → cannot catch A. That is the
"within 10%" band, exactly.

- `season_awards` / `honor_records`: All-American tiers + national POTY iterate the
  `_national_order` list (`nat`); All-Conference tiers + conference POTY group from
  the raw `_eligible` list (`players`).

## Verification

On a completed D3-men season: the top All-Americans are all 1st/2nd-singles
players with strong records; **no player whose primary line was S4–S6 lands in
the top 40** (they could before). The near-tie reorder was unit-checked on
synthetic résumés: within-10% swaps happen, >10% gaps never flip.

## Watch-outs / invariants

- **Never reintroduce STR into selection.** It is display-only. If an award again
  starts tracking rating instead of on-court results, this is the regression.
- The base score is **raw** weighted wins — volume beats rate (an 18-12 at 1st
  singles outranks a 15-2 at 1st). This is deliberate per the owner spec; if it
  ever needs rate-sensitivity, fold win% into `perf`, not into the national boost.
- The national boost is **national-only**. Don't apply `_national_order` to the
  per-conference grouping — conference prestige is constant within a conference and
  would only double-count team record.
- Everything reads completed **singles/doubles lines**; a save from before box
  persistence simply contributes fewer per-line rows (older-save tolerance is the
  same as elsewhere).
- Change the weights in ONE place (`_POS_W` / `_DBL_W`); both the live page and the
  stamped honors read them.

# AAR — ITA Kickoff Weekend + National Team Indoor (season opener)

## Problem
The Division I season started cold on the regular-season slate. The real college
year opens with the **ITA Kickoff Weekend** (a regional, draft-seeded team event)
that feeds the **National Team Indoor Championship** — an early-season test of who's
good before conference play. We wanted that opener modeled in season mode: drawn,
played, saved, and counted toward the year's dual-match record, the same way the
conference tournaments and the NCAAs already are.

## What changed
A new **`app/ita.py`** (pure draw logic) plus two new front-of-season phases in
`app/seasonmode.py`:

```
ita_kickoff → ita_indoor → regular → conf_tournaments → selection → ncaa → complete
```

- **Kickoff Weekend** — the top `KICKOFF_FIELD` (60) teams by *prior-year* ranking
  are snake-distributed into `KICKOFF_SITES` (15) cosmetic four-team sites. Each site
  is a seeded single-elim (host = top seed; 1v4 / 2v3). Two rounds (semis → final);
  the 15 site winners advance. Stored as `round='ITAK'`, `conf` = the site label.
- **National Team Indoor** — the 15 site winners + a top-ranked auto-bid host form a
  16-team seeded single-elim, run akin to the NCAAs. Stored as `round='ITAI'`,
  `conf` = the round name. Four rounds → the Indoor champion.

Only D1 runs the ITA (`ita.ITA_DIVISIONS`); other divisions open on `regular` as
before. For D1, `create_season` pushes the regular slate back `ITA_LEAD_WEEKS` (6)
weeks so the ITA truly opens the year, and starts the season in `ita_kickoff`.

### Ranking source
`_ita_ranking` seeds everything off the **prior world-year's final ranking** — the
Power Index over that season's completed duals (the prior season is this year's seed
minus the 1000-per-year stride). In year 0, with no season to rank from, it falls
back to roster **Power 6** (mean of the top-6 STR ×2), which is populated even
preseason.

### Counting toward the record (not the Power Index)
`ITAK`/`ITAI` were added to the default `_completed()` round set, so the ITA shows up
in overall standings, team schedules, player logs/records — exactly like CT/NCAA. It
is deliberately **excluded** from the regular-season Power Index (`_completed_reg_duals`
is untouched), again matching how CT/NCAA results are handled.

### Sites are cosmetic
Per the design, "sites" carry no geography and there is no live draft or home-court
advantage — the host is simply the site's top seed (and hosts as `home`, a label the
engine gives no edge to). Everything is seed-deterministic.

## Surfaces
- CLI: `python3 manage.py ita-kickoff --gender men --seed 2026`.
- Web: a new **/season/ita** page (`ita.html`) renders the 15 site brackets + the
  Indoor bracket; the season hub shows the ITA phase label, the right "Run ITA …"
  advance button, an ITA Indoor champion banner, and an `ITA` pill (D1 only). The
  world status bar's phase order/labels now lead with the two ITA phases.

## Tests
`tests/test_ita.py` — pure draw logic (site partition, 1v4 seeding, indoor field),
the phase wiring (D1 opens on the ITA, non-D1 skips it), the hand-off to the regular
season at the offset first week, the record-but-not-PI counting rule, and
determinism (same seed ⇒ identical ITA brackets).

## Notes / follow-ups
- The ITA does not yet feed a separate "ITA ranking" — it informs seeding only via
  the prior year's final Power Index. If we later want in-season ITA ranking effects,
  that's an additive change to the ratings inputs.
- Field size / site count are module constants (`KICKOFF_SITES`, `KICKOFF_FIELD`,
  `INDOOR_FIELD`), so switching to the 56/14 article shape is a one-line change.

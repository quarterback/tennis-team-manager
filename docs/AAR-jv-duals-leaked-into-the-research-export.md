# AAR — JV duals leaked into the research export

**When:** 2029-08 · **Found by:** the owner's analyst agents, on the 2039 exports
**Blast radius:** every JHSAA research export taken after the JV season landed
**Fix:** one `WHERE` clause in `research_export._load_archived_jhsaa_season`, plus a
`level` column on the exported dual row so the guarantee is visible rather than implied

---

## 1. What happened

The JHSAA JV season archives into **the same table as varsity** —
`world_jhsaa_dual`, separated by a `level` column and nothing else. The research
export's archive loader read that table without filtering, so JV duals flowed
into `duals.csv` alongside varsity ones with **nothing on the row marking which
was which**.

Measured on the owner's own exports:

| | 2038 boys | 2039 boys | 2039 girls |
|---|---|---|---|
| `duals.csv` rows | 10,709 | **18,096** | **20,501** |
| `lines.csv` rows | 70,577 | **107,242** | **121,543** |

Under `phase="regular"` in 2039 boys, 8,600 duals carried 7 lines (the varsity
3S/4D shape) and 5,247 carried 3, 4, 5, 6, 8, 9, 10 or 11 — the elastic
`JV_FORMATS` table. Girls added a 12.

## 2. ‼️ It was already worse than "extra rows"

`aggregate.Bundle` derives each phase's dual shape by taking the **most common
line count** in that phase bucket, and every Fmt / RCI / SCI number is computed
off that. So the question is not whether JV rows are present, it is whether they
outnumber varsity.

- `phase="regular"`: varsity held the mode with only **62%** (boys) / **64%**
  (girls). One JV growth step from inverting.
- `phase="showcase_pod"`: **it had already inverted.** The modal shape was a
  5-line JV shape at 40–46%; only 165 of 1,500 boys' duals were the varsity 7.
  (That bucket is not fed into shape derivation, which is the only reason it did
  no damage — luck, not design.)

And independently of shape: any consumer joining `line_players` → `lines` →
`duals` silently merged JV appearances into varsity player records and program
court totals. A player's record, a program's flight totals, and every record
derived from a schedule were all inflated — while `jhsaa_standings.csv` stayed
varsity-only, so two halves of the same export disagreed, each internally
consistent.

## 3. Root cause

`_load_archived_jhsaa_season` builds each team's schedule straight from
`world_jhsaa_dual`:

```sql
SELECT school, opp, home, phase, pf, pa, won, district, lines, level, tied, shape
FROM world_jhsaa_dual WHERE world_id=? AND year=? AND gender=?
```

It selected `level` and never used it to filter. `build_jhsaa` then walks
whatever schedule it is handed, so the loader was the only thing standing
between the JV season and the export.

**The archive writer knew.** Its own comment says:

> `level` is therefore the ONLY thing keeping a JV appearance out of a varsity
> record; it used to be guaranteed by JV rows having no lines to read, and it is
> not any more. Every reader of `lines` filters on it — see `_jh_line_records`'s
> callers and `jhsaa_underplayed`.

The JV work enumerated the readers it knew about and the export loader was not
among them. This is the repo's own "**grep the whole class in one pass**" lesson
(CLAUDE.md, the cache-invalidation AARs §2 → §2b: fixing one member of a class
and leaving the siblings "for later" is what caused the second outage).

## 4. ‼️ Why the tests were green

Every existing export test **injects** a season (`build_jhsaa(..., season=...)`).
On that path JV lives in `season["jv"]` and can never reach `teams[].schedule`,
so the invariant holds by construction and the tests are true statements about a
path a real export never takes. The archive path — the only one a user's export
uses — had no coverage at all.

The incoming report described a PR #320 test "asserting exports are
byte-identical with and without a JV slate". **No such test exists in the repo.**
Whether it was never written or removed, the effect is the same: nothing guarded
this, and a green suite meant nothing about it.

> **The lesson:** when a builder has an injectable input, the injected path and
> the real path are two different code paths, and coverage on the convenient one
> is not coverage. Test the path that reads the database.

## 5. The fix

**One clause, at the source:**

```sql
AND COALESCE(level, 'v') = 'v'
```

`COALESCE`, not `level = 'v'` — a season archived before the column existed can
read back NULL, and every dual in one of those is varsity. Filtering it out
would silently shorten every pre-JV export, trading one quiet corruption for
another.

This is **option 1** of the two the report offered (restore varsity-only), which
matches the owner's standing rule that analytics never needs to see JV, and is
the smaller change.

**Plus `level` on the exported dual row**, which is the half of option 2 worth
keeping. It is constant `'v'` today and that is the point: it turns an invisible
invariant into an assertable one. If the filter ever regresses, the next export
shows `level=jv` rows and the corruption is visible immediately instead of
showing up as a plausible row count nine months later. It also removes the
temptation to infer JV from "carries no lines" — which is unavailable anyway,
since that is equally what a varsity dual whose lines failed to record looks
like.

**And a belt-and-braces filter in the sidecar** (`aggregate.Bundle`, varsity
only at the single chokepoint everything downstream reads through), so a bad
export cannot corrupt The Clinch Report even if one is produced again.

## 6. Verified

Against a synthetic archive holding one varsity dual (7 lines), one JV dual
against the **same opponent in the same phase** (4 lines), and one legacy row
with `level` NULL:

- the loader hands back varsity only;
- the legacy NULL row survives as varsity;
- `duals.csv` carries a `level` column, every value `v`;
- every exported dual has exactly 7 lines — no elastic JV shape.

## 7. The already-exported 2039 zips

They are not repaired by this and do not need to be (owner's call). They carry
no `level` column, so the sidecar's "missing means varsity" rule cannot separate
JV out of them — **re-export 2039 after this change** and they come out clean.
Reading the existing ones will inflate records and player totals, and their
`showcase_pod` shape is already inverted.

## 8. Standing rule this leaves behind

**A table shared by two competitions is a filter obligation on every reader, and
the list of readers is not static.** When a feature adds a discriminator column
to an existing table, the change is not done when the feature's own readers
filter on it — it is done when `grep` over every consumer of that table has been
walked. Here the missing consumer was in a different module, doing something
that looked unrelated ("build an export"), and it silently republished the whole
problem to anything downstream of a zip.

# AAR — D1 men's scholarship cap bug (not a stale test)

**Date:** 2026-06-21
**Scope:** `app/scholarships.py` `DEFAULT_LIMITS`. Prompted by 10 long-standing test
failures and the question of whether to just delete them.

## The question

Ten tests had been failing on `main` for a while (4 in `test_economy`, 3 in
`test_scholarship_gender`, 1 in `test_scholarships`, 2 in `test_roster`). The
natural assumption was "the game passed them by — edit or delete them."

## What they were actually catching

A real bug, not staleness. `economy.cap_for()` reads the live scholarship limits
through `scholarships.cap()`, and `scholarships.DEFAULT_LIMITS` had:

```python
("D1", "men"): {"count": 8, "rate": 1.00, "cap": 8.0, ...}   # WRONG
("D2", "men"): {"count": 6, "rate": 0.70, "cap": 6.0, ...}   # WRONG
```

D1 men were set to the **women's 8-full-ride headcount** instead of the men's
**4.5 equivalency over ~6 funded players**; D2 men to 6.0 instead of 4.5. This
contradicts the real NCAA rules (men's tennis is an equivalency sport) — the same
rules in the scholarship guide the user supplied. `economy.SCHOLARSHIP_CAPS` already
documented the correct 4.5, but that's only the fallback; the live path read the
wrong limits.

The two `test_roster` failures were downstream of the same bug: with 8 funded D1-men
slots there were 0 walk-ons, so `walk_ons == ROSTER_SIZE − SCHOLARSHIP_SLOTS` (=2)
failed, and the talent-vs-strength check sat on the wrong side of the line.

## The fix

Correct the limits to the real numbers:

```python
("D1", "men"): {"count": 6, "rate": 1.00, "cap": 4.5, "fractional": True}
("D2", "men"): {"count": 6, "rate": 0.70, "cap": 4.5, "fractional": True}
```

D1 women stay 8 headcount; D2 women 6.0; D3/D4 zero. All 10 tests now pass.

## Side effect (intended)

D1/D2 men rosters now carry **6 funded players + 2 walk-ons** (was 8 funded, 0
walk-ons), and the recruiting-budget star plan spends over 6 funded slots — more
realistic, and the correct equivalency model.

## Takeaway

"Failing test → delete it" only after confirming the test is obsolete. Here the
tests were right and the code had drifted; fixing the code was the correct move.

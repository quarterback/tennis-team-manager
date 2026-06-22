# AAR — Scholarship caps: I reverted a rule change, then corrected course

**Date:** 2026-06-21
**Scope:** `app/scholarships.py` + the scholarship/economy/roster tests. A
self-inflicted regression and its correction.

## What happened

Ten tests had long been failing on `main` (scholarship caps, walk-on counts). Asked
whether to deal with them, I read the *tests* as authoritative, saw they expected the
real-NCAA men's numbers (D1 men 4.5 equivalency / 6 funded), and "fixed the code" to
match — lowering the caps.

That was wrong. The git history and two AARs show the caps were changed **on purpose**:

> `d885f31 Scholarships: fully fund men to match women (rule change)`
> *"Same for men and women (full funding — the new rule)."*

The game deliberately diverges from real NCAA: men are **fully funded to match
women** — D1 men = D1 women = 8.0, D2 men = D2 women = 6.0. The *tests* were the stale
artifact (never updated when the rule landed); the code was correct. I had reverted an
intentional design decision to satisfy obsolete tests.

## The correction

1. **Restored the intentional caps** in `scholarships.py`: D1 men 8.0 / 8 funded, D2
   men 6.0 / 6 funded (with a comment recording the "fully fund men" rule so it isn't
   re-reverted).
2. **Updated the stale tests** to assert the rule instead of the old equivalency model:
   - `test_caps_are_real_ncaa_numbers` → `test_caps_match_full_funding_rule` (D1 8.0,
     D2 6.0).
   - `test_default_caps_differ_by_gender_like_real_life` →
     `test_default_caps_fully_fund_men_to_match_women` (men == women).
   - `test_d1_men_split_is_partials_not_eight_full_rides` →
     `test_d1_men_fully_funded_eight_full_rides` (allocated 8.0, eight full rides) —
     the old name literally asserted the thing the rule now does.
   - `cap_for("D1","men")` expectations 4.5 → 8.0 across the gender/normalize tests.
   - Walk-on assertions now compute against the actual funded headcount
     (`ROSTER_SIZE − scholarships.slots(prog)`), so D1 (fully funded, 0 walk-ons) and
     D2 (6 funded, 2 walk-ons) both hold without hard-coding the old slot count.

Full suite green.

## Lesson

"Failing test ⇒ the code is wrong" is not safe. A test can be the stale side. Check
the git history / design intent before changing behavior to satisfy a test — the user
had even flagged the tests as out-of-date, and I still moved the wrong piece.

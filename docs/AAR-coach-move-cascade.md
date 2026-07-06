# AAR — Coach "Move to any program" as a Gender → Conference → School cascade

> **Status:** shipped. The coach page's **Move coach → Move to any program** picker was one
> dropdown listing **every program in the world** (~2,200 options). Replaced it with a
> **Gender → Conference → alphabetical School** cascade.

## 1. The ask (owner)
"Pick by gender, then conference, then an alpha school list" instead of scrolling one dropdown
of ~1,000+ schools.

## 2. The build
- **`state.coach_move_tree()`** — `{gender: [{div, conf, schools:[...]}, ...]}` for both genders,
  ordered by division then conference, schools alphabetical within a conference (reuses
  `conference_schools`). ~102 conference groups per gender across D1–D4.
- **`coach.html`** — the single `dest_school` mega-`<select>` becomes three: **Gender** (defaults to
  the coach's gender), **Conference** (labeled "ASUN Conference · D1" so the division is visible),
  and **Program** (the alpha school list). A tiny inline script (same `<script type="application/json">`
  + vanilla-JS pattern as `onboarding.html`) cascades them: gender → conference options → school
  options, building each `<option>` with `createElement`/`textContent` so school names with `&`
  (Texas A&M, William & Mary) are safe. The school option's value is still `"div|gender|school"`, so
  the existing `coach_move` route is unchanged — it parses that exact format.
- **Coach route** now passes `move_tree` instead of `move_universes`.

## 3. Verified
- Tree builds all 4 divisions × both genders; embedded JSON parses; `&`-schools intact.
- Cascade logic (run in Node against the embedded tree) yields conference labels
  "Big East Conference · D1" and school values `D1|women|Butler`, refreshing schools on both gender
  and conference change.
- Full loop: POSTing the produced `dest_school` moved a coach cross-universe (Duke D1-men assoc →
  Barry D2-women asst) and back — the route consumes the cascade value correctly.

## 4. Not touched (follow-up)
The **Editor** page has the same mega-dropdown in its per-staff-row move form. Left as-is (the
owner flagged the coach page); it still works via `all_programs_by_universe`. Converting it to the
same cascade is a straightforward follow-up (needs per-row-unique select ids sharing one tree).

## 5. Files
- `app/web/state.py` — `coach_move_tree()`.
- `app/web/server.py` — coach route passes `move_tree`.
- `app/web/templates/coach.html` — cascade + inline cascade script.

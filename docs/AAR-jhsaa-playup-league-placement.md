# AAR — a play-up joins a league, it never creates one

Owner report, 2026-09, from a live save (Season 39 / 2065), pasted as a 3A page:

> there is a bug in 3A

The 3A district table:

| League | Champion | District | Overall | To state |
|---|---|---|---|---|
| Assay Athletic Association (10 schools) | Tunnelton | 18-0 | 26-4 | 2 |
| **Coastal Range League (1 schools)** | **Puerto Alma** | **0-0** | **2-12** | **0** |
| Gold Valley League (10 schools) | Bancroft | 14-4 | 21-11 | 4 |
| … | | | | |

A league of one. In a double round robin that is a season with **no league games at
all** — Puerto Alma's 2-12 is its non-district allowance and nothing else — and it was
crowned district champion of it.

---

## What happened

Three correct things composed into a wrong one.

1. **`load_schools` filters on sponsorship; `_rows()` does not.** Since the
   `former_school` rule (owner, 2026-08) a program that stops sponsoring tennis **keeps
   its data row** — it must, or its page and its archived titles 404 — while dropping
   out of `load_schools`. So a league can be fully populated in the rows and completely
   empty on the field.
2. **`_compute_playup_league` reads `_rows()`**, correctly (play-up is a property of the
   SCHOOL, not of a gender's team, so it must be gender-agnostic and cannot read either
   gender's `load_schools`). It counted every row carrying a league name as a settled
   member of it.
3. **Geography scores county first.** **Copperview** — 3A, sponsors *neither* gender —
   is the sole member of Coastal Range League and sits in **San Marcos county /
   Sebastian Cape area**, which is Puerto Alma's own county *and* area. It therefore
   beat every real 3A league on the strongest term the placement has.

Puerto Alma played up into a league whose only member does not exist.

### It was not a 3A problem

Ten leagues have zero sponsoring members, across six classifications:

| Class | League | Members, all non-sponsoring |
|---|---|---|
| 1A | East Cascades League | Ansotegui Siding, Copperton Regional, Juniper Bar, Pine Rim, Reverend City |
| 1A | Vermilion Valley League | Promise Land |
| 2A | Three Rivers League | Juniper Crossing |
| 3A | Coastal Range League | Copperview |
| 3A | Mission League | Alder Cooperative, Mercy Academy Valley |
| 4A | Dual County League | Preston Hollow |
| 4A | Three Rivers League | Northside Christian |
| 5A | Capital Athletic Association | Pascagoula, Rock on the Hill Christian Academy, St. Catherine Academy |
| 6A | Juniper League | Empire Milling |
| 6A | Placer League | Doyle Ridge |

3A is simply where the owner happened to put a play-up next to one.

### ‼️ The guard was already written — it just could not see this

`_compute_playup_league` already raises rather than leave a program in a one-team
league, and its docstring says so in as many words. But it tests whether the class has
**any** settled league, not whether the league it picked is **played in**. A guard
written against "no league at all" cannot catch "a league with nobody in it", and the
outcome is identical.

### ‼️ Why the tests were green

`test_a_played_up_school_joins_a_real_league_of_its_new_class` asserts exactly this
property — and iterates the **seeded** play-ups only. Six programs are actually placed
on this data, and none of them happens to sit near a dead league. The property belongs
to the **placement**, not to the six schools currently exercising it, so it is now swept
over **every one of the 373 eligible schools**.

The association's dead leagues are themselves asserted to still exist
(`test_the_association_really_does_hold_empty_leagues`), so if a future data pass
removes them the sweep announces that it has stopped testing anything rather than
passing vacuously.

---

## The rule the owner actually wanted

The first fix was to filter the candidate pool by sponsorship, which fixes the reported
case. The owner then generalised it, and they were right that the narrow fix was the
smaller half:

> future play-ups should just put a team in a bigger league if needed it should never
> invent a one-team or two-team or 4-team or whatever conference
>
> that's the bigger solve is just to never let new leagues get created because of
> geography — **none of this is real so they can be wherever**
>
> no league can get below 6

So: **size gates, geography only orders.**

* A league under `PLAY_UP_LEAGUE_MIN` (**6**) is not a candidate. The program travels.
* If nothing in the class clears the floor, the **BIGGEST** league takes it — literally
  "a bigger league if needed" — never the nearest, never a new one.
* Movers already placed count toward the league they joined, so a run of play-ups cannot
  each read a league as though the others had not gone there (the existing one-pass
  rule, which only started to matter once size decided something).

**Why 6.** Measured across the shipped association: 95 live leagues, every one of them
**8-10** members, in all twelve groups. 6 absorbs a league that has lost a sponsor or
two without ever admitting the one-, two- or four-team "conference" the owner ruled out.
The owner independently named the same number.

**Geography is now demonstrably cosmetic**, which is what the owner asked for. It orders
the leagues that are real and is never the reason one gets invented — the same posture
the existing "geography is a preference, never a gate" rule takes about *distance*,
extended to the thing distance was quietly overriding.

### ‼️ THE FLOOR HAS NO MIRROR AND MUST NOT GROW ONE

Owner, in the same exchange:

> the 10 is not a hard cap … it's just a guide, if it needs to go bigger it always can

`MAX_DISTRICT` was deliberately removed from this path and a test asserts the constant
is not even importable here. A league one program larger just plays a longer, perfectly
valid double round robin; `DISTRICT_TARGET` 10 is a drawing guide for a fresh map, not a
runtime limit. A same-county league of **14** still beats a smaller one further away,
and that is pinned, because "size gates" is exactly the sentence a future reader would
misread as a capacity rule.

---

## Result

* Puerto Alma → **Gold Valley League** (10 live members).
* A sweep of all **373** eligible schools: every one lands in a league of at least
  **8**; the smallest joined anywhere is Alderton into 2A's Valle Vista League.
* The six seeded play-ups are unchanged.

## The lesson

**`load_schools`'s sponsorship filter is what makes a program real.** Anything reading
`_rows()` to answer a question about who PLAYS — rather than about a school's page — has
to apply it too. `_sponsors_any` is that filter, gender-agnostic because the placement
is: a girls-only sponsor is a live league member.

More generally: `former_school` changed what a data row MEANS without changing its
shape. Every reader kept compiling and kept looking right, and the one that cared about
the difference was three functions away from the change.

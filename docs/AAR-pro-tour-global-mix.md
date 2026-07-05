# AAR — "Pro Tour" global nationality mix + international-share dial

> **Status:** shipped. A one-pick **"Pro Tour — global mix"** nationality preset (ATP/WTA-shaped,
> owner targets baked in) + the onboarding **international-share** slider now also tilts the BASE
> roster — so a globally-representative world is two knobs, not 84 region sliders.

---

## 1. The problem (owner)

Tuning the world's nationality spread meant hand-setting **84 region weights** — "tedious and
difficult to get the tight balance." The owner wanted, à la the ATP/WTA 1000: big Western buckets
but a genuinely global, influential tail, with targets — **UK ≥15%, South America ≥10%, Canada
≥5%, Mexico ~2%**, plus Brazil, Australia, Canada, Philippines, China, Japan, Thailand, Germany,
Italy, Poland all present.

## 2. Two things were in the way

1. **No curated global preset** — the closest, `tennis_global`, is Europe-heavy and doesn't encode
   these targets.
2. **The `intl_share` slider only moved RECRUITS, not the base roster.** The base-roster US/foreign
   split is division-driven (`recruiting._INTL_BASE`: D1 ~51% foreign, D3 ~17%) and ignored the
   onboarding slider — so no matter what you picked, the base world stayed US-heavy. That's why a
   global feel was unreachable.

## 3. The fix

### 3a. `pro_tour` preset (`generators/data/names/regions.json` + `worldconfig.BANDS`)
A curated **foreign-distribution** preset (38 regions) shaped to the owner's priorities: UK a
headline bucket, a strong South America (south_america + brazil), Canada/Mexico present, the
Western-Europe core (Spain/France/Germany/Italy), an Eastern-Europe bloc incl. **Poland**,
Australia, East Asia (China/Japan/Korea), SE Asia (**Thailand/Philippines**), and an
influential-but-smaller Africa. Selectable as band **"Pro Tour — global mix (ATP/WTA-shaped)."**

### 3b. `intl_share` now tilts the base roster (`recruiting.intl_share_for`)
Added an **additive tilt from the 0.30 baseline** so the slider finally moves the whole world:
`intl += (worldconfig.intl_share() − 0.30) × 0.70`. **Default 0.30 = a NO-OP** (zero calibration
change; roster/recruit tests green), higher = global. Recruits already honored the slider via a
separate path, so no double-count. Now it's a clean 2-knob model: **preset = who, intl-share = how
global.**

## 4. Measured (upper-D1 program, prestige 0.6)

| intl_share | US | UK | S.Am | Canada | Mexico | notes |
|---|---|---|---|---|---|---|
| 0.30 (default) | 49% | 8% | 6% | 3% | 1.3% | unchanged base model |
| 0.70 | 21% | 12% | 9.2% | 4.6% | 1.9% | tour-like |
| 0.80 | 14% | 13% | 9.8% | 5.3% | 2.1% | ≈ owner targets |

Germany/Italy/Poland/Australia/East-Asia/SE-Asia all land in the 3–6% range — present and
influential. Shares scale with program prestige (top programs more international).

**Recommended:** pick band **Pro Tour — global mix** + international share **0.70–0.80**.

## 5. Africa + West Indies — represented AND good at tennis (owner)

The first cut gave Africa a weight of 2 and the West Indies **zero**, and Africa's only rated
nation (South Africa) sat *below* neutral. Fixed both levers:

- **Talent (`nation_talent.json`):** raised/added **16 African** and **18 West Indies/Caribbean**
  nations above neutral — Tunisia 74/66 (+3 grade, ~1-in-134 blue-chip), South Africa 66/62,
  Zimbabwe/Egypt/Nigeria/Kenya…; Jamaica 64/58, Cuba 64/58, Bahamas/Barbados/Trinidad/Dominican…
  So players from those nations generate a genuine grade lift + better blue-chip odds — "better
  at tennis" everywhere, not just in this preset.
- **Representation (`pro_tour` weights):** per owner, **cut UK by two-thirds (22→7.3)** and poured
  it into Africa (Sub-Saharan + **North Africa** + cricket nations + islands, weight 3→17) and the
  **West Indies** (caribbean_cricket/dutch + Barbados/Bahamas/Bermuda/Haiti/Cuba/Dominican…, 0→16).

### 5a. Owner rebalance (final)
After seeing Africa+WI at ~23%, the owner dialed it in: **Africa+WI → ~13% combined**, and the
freed weight went **UK +7%, France +3%**; then **−3% from Eastern Europe and −3% from South
America** to **Australia/NZ (+5%) and Oceania (+1%)**. France had no standalone region (it was
~20% of the mixed `europe_western` pool), so a dedicated **`france`** region was added (promoted
out of `europe_western`, same `french` name pool) so it could be weighted directly.

**Resulting mix (upper-D1, intl_share 0.8):** W.Eur-non-FR 16.2 · US 14.7 · UK 10.5 · E.Europe 8.0
· Aus/NZ 7.5 · **West Indies 6.5** · **Africa 6.0** · S.America 5.6 · Canada 4.5 · E.Asia 4.0 ·
France 3.6 · SE.Asia 3.0 · Mexico 1.9 · Nordic 1.5 · Oceania 1.0 % (Africa+WI ≈ 12.5% combined).

### 5b. Un-burying tennis nations (owner: "any others left out like France?")
Several tennis nations had no standalone region — they only lived inside a **mixed** pool, so they
couldn't be weighted directly: **Argentina, Chile** (in `south_america`), **China, Japan** (in
`east_asia`), **Bulgaria** (in `europe_eastern`). Promoted all five to their own single-country
regions (same name pools they used inside the mix) and gave them direct `pro_tour` weight, trimming
the parent pools so the S.America / E.Asia / E.Europe bucket totals held. Also bumped **Greece**
(already standalone) back over **1%** direct.

Now at intl_share 0.8 (upper-D1): Argentina 1.5 · Japan 1.4 · Greece 1.1 · China 0.9 · Chile 0.8 ·
Bulgaria 0.4 % — each individually weightable, with the S.America bucket steady at ~5.8%.

## 6. Files touched

- `generators/data/names/regions.json` — new `pro_tour` preset (owner-tuned mix) + new standalone
  `france` region.
- `generators/data/names/nation_talent.json` — Africa + West Indies nations lifted above neutral.
- `app/worldconfig.py` — `pro_tour` in `BANDS`.
- `app/recruiting.py` — `intl_share_for` base-roster tilt (default-neutral).

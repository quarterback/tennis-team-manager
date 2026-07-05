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

## 5. Files touched

- `generators/data/names/regions.json` — new `pro_tour` preset.
- `app/worldconfig.py` — `pro_tour` in `BANDS`.
- `app/recruiting.py` — `intl_share_for` base-roster tilt (default-neutral).

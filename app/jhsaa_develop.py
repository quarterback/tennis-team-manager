"""The JHSAA attribute-level development model (owner spec 2026-10 — the
"attribute-level developmental capacity and coaching portfolios" addendum of
`docs/reports/JHSAA-development-panel-review-2103-2111.md`; lessons and the full
maths in `docs/AAR-jhsaa-attribute-development-stock.md`).

    Potential becomes a STOCK of developmental capacity, while coaching decides
    WHICH capabilities a player actually acquires.

From `jhsaa.stock_era()` on, a cohort is no longer realised by ONE scalar factor
over all 51 attributes (`jhsaa._apply_career`, which keeps the player's shape and
can only move the whole player up or down their own curve). Each player instead
carries four distinct things, every one deterministic from the seat identity
`(school, entry, seat, salt)` on its OWN rng streams (the main seat rng is never
touched, so nothing else in the roster moves):

  * NATURAL TARGETS   — the attribute levels the old scalar model would have
                        produced: what the kid becomes under ORDINARY coaching.
                        These are the pre-era `p.potential` values, unchanged.
  * TRAINABLE CEILINGS — per attribute, how far unusually effective instruction
                        could take THAT skill for THIS player. Drawn per
                        category above the natural target. Some weaknesses are
                        very trainable, some really are limited. `p.potential`
                        holds these for a stock-era player.
  * DEVELOPMENTAL STOCK — a finite pool, in raw attribute points, that BOTH
                        ordinary growth and coached growth spend from. Natural
                        growth is charged first; coaching spends what is left.
                        It can be unspent at graduation. A weighted-OVR budget
                        sits beside it so spending cheap or heavy attributes
                        cannot game the pool.
  * RESPONSIVENESS     — a stable work ethic, a stable per-category coachability,
                        and a stable player × coach × category FIT. These decide
                        how much ADDITIONAL instruction a player absorbs. Nobody
                        loses ordinary growth for a low work ethic.

Each archived season, every coach on the program's staff THAT season (head and
every assistant, from `jhsaa_coach_history`) makes teaching OFFERS in the
categories of their portfolio (`jhsaa_coaches.teaching_portfolio`). Offers are
allocated under the trainable caps, a per-season rate, the remaining stock, the
OVR budget and headroom; a seeded success check decides whether instruction took;
the head-coach BOND scales the whole staff's offers inside 0.85–1.15. Attributes
move, and OVR and the engine drivers derive from them afterwards — there is NO
match-day buff anywhere in here. Winning never adds a point.

‼️ EVERY CONSTANT BELOW IS A FIRST-PASS CANDIDATE, to be re-measured on the
owner's save after the first stock-era season (the replay script
`scripts/jhsaa_stock_replay.py` is the harness). None is calibrated.
"""
from __future__ import annotations

import random

from .player_attributes import (GRADE_CEIL, GRADE_MIN, OVERALL_WEIGHTS, RICH_ATTRS,
                                _WEIGHT_TOTAL, clamp_grade)

# --- the categories ---------------------------------------------------------
#
# Nine groups covering all 51 attributes. The first eight are COACHED (a staff
# can teach them); `intangibles` grow only on the natural path — nobody coaches
# a kid's heat tolerance or academic fit. The groups are the generator's own
# `_STYLE_CLUSTERS` (so a style's strengths and a coach's portfolio speak the
# same language) plus physical / mental / intangibles over the rest.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "serve":    ("first_serve_power", "first_serve_accuracy", "second_serve_quality",
                 "serve_variety"),
    "return":   ("return_quality", "return_aggression", "return_depth"),
    "baseline": ("forehand_power", "forehand_control", "backhand_power",
                 "backhand_control", "groundstroke_consistency", "shot_tolerance",
                 "rally_patience", "pattern_execution"),
    "net":      ("net_play", "volley_touch", "overhead", "poaching", "doubles_chemistry",
                 "approach_shot", "transition_game"),
    "movement": ("footwork", "speed", "agility", "balance"),
    "touch":    ("drop_touch", "lob_touch", "slice_control", "court_vision",
                 "passing_precision"),
    "physical": ("stamina", "strength", "recovery"),
    "mental":   ("composure", "focus", "clutch", "resilience", "competitiveness",
                 "discipline", "crowd_pressure"),
    # `flexibility` sits here because nothing in the engine reads it (it counts
    # toward the weighted OVR only) — a coached point there would be a display
    # number, which the design forbids.
    "intangibles": ("coachability", "training_drive", "academic_fit", "team_culture",
                    "leadership", "indoor_comfort", "outdoor_comfort", "wind_tolerance",
                    "heat_tolerance", "flexibility"),
}
COACHED = tuple(k for k in CATEGORIES if k != "intangibles")
CATEGORY_OF: dict[str, str] = {a: k for k, attrs in CATEGORIES.items() for a in attrs}
assert sorted(CATEGORY_OF) == sorted(RICH_ATTRS), "every rich attribute sits in one category"

# --- the latent profile (candidates) ----------------------------------------
TRAIN_SPAN = 40.0        # grade points of trainable headroom above the natural target
                         # at trainability 1.0 for an attribute at the bottom of the scale
TRAIN_SKEW = 1.6         # trainability draw u**TRAIN_SKEW: most categories modestly
                         # trainable, a few very (mean ≈ 0.38)
TRAIN_JITTER = 1.5       # per-attribute gauss sd around the category's headroom
ETHIC_DRAW_W = 0.55      # work ethic: this much its own draw, the rest the generated
                         # training_drive / coachability CEILINGS (fixed evidence)
STOCK_REALISE = (0.60, 1.00)   # share of the trainable headroom the stock can fund

# --- the season spend (candidates) ------------------------------------------
TEACH_RATE = 45.0        # raw points a category can gain in one season from one
                         # elite coach at perfect fit, full exposure, ethic 1.0
HEAD_W, ASSISTANT_W = 1.0, 0.8     # the head is the largest single teaching voice
OVERLAP = (1.0, 0.25, 0.10, 0.05)  # two coaches teaching the SAME category: the second
                                   # adds 25% of its offer, the third 10% … (diminishing;
                                   # complementary staffs open MORE than overlapping ones)
D_FLOOR, D_SPAN, D_CURVE = 0.30, 0.60, 1.5   # d(q) = clamp((q − 0.30)/0.60, 0, 1)^1.5:
                                             # a coach under the 30th percentile in the
                                             # category's governing grade teaches nothing
FIT_BAND = (0.6, 1.3)    # stable player × coach × category fit
ETHIC_FLOOR = 0.3        # ethic term = 0.3 + 0.7 × work_ethic
REPS_FLOOR = 0.25        # realisation term = 0.25 + 0.75 × played share: a kid who never
                         # dressed still practises, a full varsity season converts fully
SUCCESS = (0.35, 0.55)   # P(instruction took) = 0.35 + 0.55 × coachability_k × ethic term
ATTR_RATE = 12.0         # max coached raw points on ONE attribute in one season
SEASON_RAW_CAP = 120.0   # max coached raw points across the player in one season
SEASON_OVR_CAP = 7.0     # max coached weighted-OVR gain in one season
BOND_BAND = (0.85, 1.15) # the head-coach bond's whole range

#: Which coach grades govern each category's teaching quality: a weighted blend
#: of the coach's imprinted quantiles (`jhsaa_coaches.GRADES`).
GOVERNING: dict[str, dict[str, float]] = {
    "serve":    {"singles": 0.6, "development": 0.4},
    "return":   {"singles": 0.5, "tactics": 0.2, "development": 0.3},
    "baseline": {"singles": 0.5, "development": 0.5},
    "net":      {"doubles": 0.6, "development": 0.4},
    "movement": {"development": 0.7, "builder": 0.3},
    "touch":    {"tactics": 0.5, "singles": 0.3, "development": 0.2},
    "physical": {"development": 0.5, "builder": 0.5},
    "mental":   {"clutch": 0.5, "changeover": 0.3, "talent_id": 0.2},
}


def weighted(attrs: dict) -> float:
    """The weighted-OVR mean of an attribute dict (what `overall_grade` reads)."""
    return sum(OVERALL_WEIGHTS[a] * attrs[a] for a in RICH_ATTRS) / _WEIGHT_TOTAL


def d_of(q: float) -> float:
    """Teaching quality from a governing quantile — zero under the floor, 1 at elite."""
    t = (q - D_FLOOR) / D_SPAN
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return t ** D_CURVE


def governing_q(grades: dict, category: str) -> float:
    """A coach's governing quantile for one category (`GOVERNING`)."""
    w = GOVERNING[category]
    return sum(grades.get(g, 0.5) * x for g, x in w.items()) / sum(w.values())


# --- the latent profile -------------------------------------------------------

def latent_profile(school_key: str, entry: int, seat: int, salt: str,
                   natural: dict, start_frac: float, peak_frac: float) -> dict:
    """The seat's latent developmental profile — drawn ONCE on its own stream.

    `natural` is the attribute vector the scalar model develops toward (the
    pre-era ceilings); `start_frac`/`peak_frac` are the career plan's start and
    peak as shares of the natural ceiling, so the natural SPEND over a career is
    `Σ natural[a] × (peak_frac − start_frac)`.

    Returns the pinnable record (`world_jhsaa_talent.stock`): the draws AND the
    derived caps and budgets, so a later change to any constant above reaches
    new entrants only."""
    r = random.Random(f"{salt}|jhsaa-stock|{school_key}|{entry}|{seat}")
    # Work ethic: its own draw blended with the generated training_drive and
    # coachability CEILINGS — fixed evidence about the person, never the current
    # (trainable) grade, which would let effort multiply its own growth.
    draw = r.betavariate(2.2, 2.0)
    evidence = ((natural["training_drive"] + natural["coachability"]) / 2.0 - GRADE_MIN) \
        / (GRADE_CEIL - GRADE_MIN)
    ethic = ETHIC_DRAW_W * draw + (1.0 - ETHIC_DRAW_W) * max(0.0, min(1.0, evidence))
    train = {k: r.random() ** TRAIN_SKEW for k in COACHED}
    coach = {k: 0.5 * ethic + 0.5 * r.betavariate(2.0, 2.0) for k in COACHED}
    rho = r.uniform(*STOCK_REALISE)
    caps = {}
    for a in RICH_ATTRS:
        k = CATEGORY_OF[a]
        base = natural[a]
        if k == "intangibles":
            caps[a] = base
            continue
        room = (1.0 - (base - GRADE_MIN) / (GRADE_CEIL - GRADE_MIN))
        room = max(0.0, room) ** 0.5
        cap = base + train[k] * TRAIN_SPAN * room + r.gauss(0.0, TRAIN_JITTER)
        # Rounded for the pin, but never under the natural target by rounding.
        caps[a] = max(base, clamp_grade(round(cap, 3)))
    # The natural path spends `natural × (peak − start)` over a career; the EXTRA
    # the stock can fund is `rho` of the trainable headroom above the natural
    # TARGET (not the career peak: the peak band tops out at 1.10 of the target
    # and measuring headroom from there starved the budget — an elite staff hit
    # it inside three seasons and every staff shape then read the same).
    natural_spend = sum(max(0.0, natural[a] * (peak_frac - start_frac)) for a in RICH_ATTRS)
    extra_raw = rho * sum(max(0.0, caps[a] - natural[a]) for a in RICH_ATTRS)
    extra_ovr = rho * max(0.0, weighted(caps) - weighted(natural))
    return {"ethic": round(ethic, 4), "rho": round(rho, 4),
            "train": {k: round(v, 4) for k, v in train.items()},
            "coach": {k: round(v, 4) for k, v in coach.items()},
            "caps": caps,
            "stock_total": round(natural_spend + extra_raw, 2),
            "extra_raw": round(extra_raw, 2),
            "extra_ovr": round(extra_ovr, 3)}


# --- the season spend -----------------------------------------------------------

def _fit(salt: str, pid: str, coach_id: str, category: str) -> float:
    lo, hi = FIT_BAND
    return random.Random(f"{salt}|jhsaa-fit|{pid}|{coach_id}|{category}").uniform(lo, hi)


def _took(salt: str, pid: str, coach_id: str, category: str, season: int, p: float) -> bool:
    return random.Random(f"{salt}|jhsaa-teach|{pid}|{coach_id}|{category}|{season}").random() < p


def season_offers(pid: str, salt: str, season: int, profile: dict, coaches: list,
                  played: float, bond: float) -> dict:
    """{category: raw points offered this season} from one season's staff.

    `coaches` is `[(coach_id, slot, grades, portfolio)]` for the staff archived
    that season (`jhsaa.staff_coaches_history`); `portfolio` is
    `{category: intensity}`; `played` is the exposure odometer's realisation
    (EXPO_FLOOR..1.0); `bond` the head's bond that season (1.0 neutral)."""
    ethic_term = ETHIC_FLOOR + (1.0 - ETHIC_FLOOR) * profile["ethic"]
    from .jhsaa import EXPO_FLOOR
    share = max(0.0, (played - EXPO_FLOOR) / (1.0 - EXPO_FLOOR))
    reps = REPS_FLOOR + (1.0 - REPS_FLOOR) * min(1.0, share)
    lo, hi = BOND_BAND
    bond = max(lo, min(hi, bond))
    by_cat: dict[str, list] = {k: [] for k in COACHED}
    for coach_id, slot, grades, portfolio in coaches:
        slot_w = HEAD_W if slot == "head" else ASSISTANT_W
        for k, intensity in portfolio.items():
            if k not in by_cat or intensity <= 0:
                continue
            d = d_of(governing_q(grades, k))
            if d <= 0:
                continue
            c_k = profile["coach"].get(k, 0.5)
            p_took = SUCCESS[0] + SUCCESS[1] * c_k * ethic_term
            if not _took(salt, pid, coach_id, k, season, p_took):
                continue
            offer = (TEACH_RATE * slot_w * d * intensity * _fit(salt, pid, coach_id, k)
                     * c_k * ethic_term * reps * bond)
            by_cat[k].append((offer, coach_id))
    out = {}
    for k, offers in by_cat.items():
        if not offers:
            continue
        offers.sort(reverse=True)
        total = 0.0
        parts = []
        for i, (o, cid) in enumerate(offers):
            w = OVERLAP[i] if i < len(OVERLAP) else OVERLAP[-1]
            total += o * w
            parts.append((cid, o * w))
        out[k] = (total, parts)
    return out


def allocate(current: dict, caps: dict, offers: dict, stock_left: float,
             ovr_left: float) -> tuple[dict, dict, float, float]:
    """Spend one season's offers onto attributes.

    Each category's offer is split across its attributes in proportion to
    HEADROOM (cap − current), capped per attribute (`ATTR_RATE`), per season
    (`SEASON_RAW_CAP` raw, `SEASON_OVR_CAP` weighted) and by what the stock and
    the OVR budget have left. Returns (gains by attribute, gains by coach and
    category, stock spent, OVR spent)."""
    gains = {a: 0.0 for a in RICH_ATTRS}
    by_coach: dict = {}
    raw_budget = min(SEASON_RAW_CAP, max(0.0, stock_left))
    ovr_budget = min(SEASON_OVR_CAP, max(0.0, ovr_left))
    if raw_budget <= 0 or ovr_budget <= 0:
        return gains, by_coach, 0.0, 0.0
    # Largest offers first, so a scarce budget goes where the staff is strongest.
    for k, (total, parts) in sorted(offers.items(), key=lambda kv: -kv[1][0]):
        attrs = CATEGORIES[k]
        head = {a: max(0.0, caps[a] - current[a] - gains[a]) for a in attrs}
        room = sum(head.values())
        if room <= 0 or total <= 0:
            continue
        want = min(total, room)
        got_k = 0.0
        for a in attrs:
            if head[a] <= 0:
                continue
            g = min(want * head[a] / room, head[a], ATTR_RATE)
            # The two budgets, in raw and weighted units.
            g = min(g, raw_budget)
            w = OVERALL_WEIGHTS[a] / _WEIGHT_TOTAL
            if w > 0:
                g = min(g, ovr_budget / w)
            if g <= 0:
                continue
            gains[a] += g
            got_k += g
            raw_budget -= g
            ovr_budget -= g * w
        if got_k > 0:
            for cid, part in parts:
                by_coach.setdefault(cid, {})[k] = round(got_k * part / total, 3)
    spent_raw = sum(gains.values())
    spent_ovr = sum(gains[a] * OVERALL_WEIGHTS[a] for a in RICH_ATTRS) / _WEIGHT_TOTAL
    return gains, by_coach, spent_raw, spent_ovr


def apply_stock(p, pid: str, salt: str, profile: dict, baseline: dict,
                start_frac: float, seasons: list) -> dict:
    """Realise a stock-era player's CURRENT attributes.

    `baseline` is the scalar model's attribute vector at the player's current
    grade (natural shape × career factor — the intrinsic path, already
    exposure-aware). `seasons` is the archived prior seasons in order:
    `[(season_year, played, coaches, bond)]`. The intrinsic spend is charged
    first (what the natural path has realised so far), coached gains are
    allocated season by season from what is left, and the player lands at
    `min(cap, baseline + coached)` per attribute. Returns the ledger."""
    caps = profile["caps"]
    natural = {a: p.potential[a] for a in RICH_ATTRS}   # pre-era ceilings = natural
    start_attr = {a: natural[a] * start_frac for a in RICH_ATTRS}
    intrinsic = sum(max(0.0, baseline[a] - start_attr[a]) for a in RICH_ATTRS)
    stock_left = profile["stock_total"] - intrinsic
    ovr_left = profile["extra_ovr"]
    cur = dict(start_attr)
    coached = {a: 0.0 for a in RICH_ATTRS}
    ledger = []
    for season, played, coaches, bond in seasons:
        offers = season_offers(pid, salt, season, profile, coaches, played, bond)
        if not offers:
            continue
        # Headroom is read against the player AS THEY STOOD that season: the
        # intrinsic path's share by then plus what coaching had already added.
        gains, by_coach, raw, ovr = allocate(
            {a: cur[a] + coached[a] for a in RICH_ATTRS}, caps, offers, stock_left, ovr_left)
        if raw <= 0:
            continue
        for a in RICH_ATTRS:
            coached[a] += gains[a]
        stock_left -= raw
        ovr_left -= ovr
        ledger.append({"season": season, "raw": round(raw, 2), "ovr": round(ovr, 3),
                       "by_coach": by_coach})
    for a in RICH_ATTRS:
        # Coaching can never carry an attribute past its trainable cap; the
        # natural path itself is never clipped (a career peak may sit above the
        # natural target, and that overflow is the player's own).
        room = max(0.0, caps[a] - baseline[a])
        p.current[a] = clamp_grade(baseline[a] + min(coached[a], room))
        p.potential[a] = clamp_grade(max(caps[a], p.current[a]))
    p.recruit_stars = p.star_rating()
    coached_ovr = weighted({a: baseline[a] + coached[a] for a in RICH_ATTRS}) - weighted(baseline)
    return {"ledger": ledger,
            "stock_left": round(max(0.0, stock_left), 2),
            "coached_ovr": round(max(0.0, coached_ovr), 3),
            "natural_ovr": round(weighted(natural), 3),
            "trainable_ovr": round(weighted(caps), 3)}

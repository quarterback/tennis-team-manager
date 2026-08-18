"""Small, deterministic sports-desk blurb generators.

No LLM calls — this is a build script you run offline against exported data,
so the "voice" is template prose assembled from the numbers, in the vein of a
beat-writer's notes column: plain declarative sentences, a lede number up
front, understated on adjectives.
"""
from __future__ import annotations


def team_blurb(team: dict) -> str:
    prog = team["program"]
    standing = team["standing"]
    wins, losses = team["wins"], team["losses"]
    total = wins + losses
    name = prog["name"]
    if total == 0:
        return f"{name} has no completed duals on record for this export."
    pct = wins / total
    if pct >= 0.75:
        tone = "one of the stronger programs in this snapshot"
    elif pct >= 0.5:
        tone = "a roughly .500 program in this snapshot"
    else:
        tone = "still finding its footing here"
    district = prog.get("district") or prog.get("conference")
    place = standing.get("district_place") if standing else None
    place_txt = f", sitting {_ordinal(int(place))} in district play" if place else ""
    sched = team["schedule"]
    streak = _streak(sched)
    streak_txt = f" {streak}." if streak else ""
    return (f"{name} is {wins}-{losses} ({pct:.3f}) across {total} duals on record, "
            f"{tone}{place_txt} in {district or 'its league'}.{streak_txt}")


def _streak(schedule: list[dict]) -> str:
    if not schedule:
        return ""
    last = schedule[-3:]
    if not last:
        return ""
    result = last[-1]["won"]
    n = 0
    for s in reversed(schedule):
        if s["won"] == result:
            n += 1
        else:
            break
    if n < 2:
        return ""
    word = "won" if result else "dropped"
    return f"They've {word} {n} straight"


def player_blurb(career: dict) -> str:
    name = career["name"]
    wins, losses = career["wins"], career["losses"]
    total = wins + losses
    if total == 0:
        return f"{name} has no completed matches on record in this export."
    pct = wins / total
    counts = career["position_counts"]
    top_slot, top_n = (counts.most_common(1) or [(None, 0)])[0]
    slot_txt = ""
    if top_slot:
        share = top_n / total
        if share >= 0.7:
            slot_txt = f" — almost exclusively at {top_slot}"
        elif len(counts) > 1:
            slots = ", ".join(s for s, _ in counts.most_common(3))
            slot_txt = f", moving around the lineup ({slots})"
        else:
            slot_txt = f" at {top_slot}"
    seasons = len(career["seasons"])
    span_txt = f" across {seasons} season(s) on record" if seasons > 1 else ""
    return (f"{name} is {wins}-{losses} ({pct:.3f}) in {total} logged matches{span_txt}"
            f"{slot_txt}.")


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"

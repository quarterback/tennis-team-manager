"""The classification report — three questions about a class, not one table.

A classification is the game's biggest structural claim and nothing here could
inspect it. The three questions the owner actually asks about one, in order:

  1. IS 6A ACTUALLY BETTER THAN 5A?  Answerable on court, and only on court:
     league play is inside a class by construction, so the classes meet in
     non-district play and nowhere else. Those duals are the entire evidence
     base, so the report is built from them rather than from a rating (TOSS is
     computed gender-wide but is an opponent-strength composite, so comparing
     two classes' TOSS compares how each class rates ITSELF).

  2. IS THE TALENT SHAPE HOLDING?  The design's thesis is that a bigger school
     does not simply have better players — the top ends sit close together and
     enrollment buys DEPTH, so the steps between classes should widen as you
     go down a lineup. That is a measurable shape (mean OVR at each ladder
     position, per class) and it is worth measuring in a LIVE world rather
     than at generation, because nine seasons of hand transfers move talent in
     bulk and the generator's guarantee says nothing about where it ends up.

  3. IS THE CLASS HEALTHY?  Spread at the top, how many different programs win
     it, how often a dual is close.

‼️ Everything here keys on `championship_group`. A class is who you play.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from . import aggregate

# How deep the "top of the class" is when measuring spread. Sixteen is the
# size of a State draw's business end and roughly the set of programs with a
# plausible claim on the title, which is what the number is about.
TOP_N = 16

# Below this a class has too few programs in the export for a distribution.
MIN_PROGRAMS = 4


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def program_strength(ability_scope, program_id: str, dressed: int | None) -> float | None:
    """Mean OVR of the players a league dual would actually put on court. Not
    the whole roster: rosters run 11 to 36 and a mean over all of them measures
    how many bodies a program carries, not how good it is."""
    board = ability_scope.ladder.get(program_id) or []
    n = dressed or len(board)
    vals = [ability_scope.ovr[p] for p in board[:n] if p in ability_scope.ovr]
    return statistics.fmean(vals) if vals else None


def head_to_head(bundle) -> dict:
    """Cross-class results from the duals where two classes actually met.

    Returns {(class_a, class_b): {"w": int, "l": int}} from A's side, plus the
    same rows mirrored, so a lookup either way works.
    """
    out: dict[tuple, dict] = defaultdict(lambda: {"w": 0, "l": 0})
    for d in bundle.duals_full.values():
        home = bundle.programs.get(d["home_program_id"])
        away = bundle.programs.get(d["away_program_id"])
        if not home or not away:
            continue
        ch, ca = aggregate.program_class(home), aggregate.program_class(away)
        if ch == ca or ch == "—" or ca == "—":
            continue
        home_won = d["winner_program_id"] == d["home_program_id"]
        out[(ch, ca)]["w" if home_won else "l"] += 1
        out[(ca, ch)]["w" if not home_won else "l"] += 1
    return dict(out)


def ladder_shape(bundle, ability_scope, depth: int) -> dict:
    """Mean OVR at each ladder position, per classification.

    {classification: {"positions": [ {pos, mean, sd, n}, ... ],
                      "top", "bottom", "drop"}}

    `drop` is position 1 minus position `depth` — the design says this should
    GROW as classes get smaller (the top ends converge, the depth does not).
    """
    pos_vals: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    for program_id, prog in bundle.programs.items():
        if not int(float(prog.get("scope_member") or 1)):
            continue        # opponents pulled in for context aren't in the class sample
        cls = aggregate.program_class(prog)
        board = ability_scope.ladder.get(program_id) or []
        for i, pid in enumerate(board[:depth], 1):
            v = ability_scope.ovr.get(pid)
            if v is not None:
                pos_vals[cls][i].append(v)

    out = {}
    for cls, positions in pos_vals.items():
        rows = []
        for pos in sorted(positions):
            vals = positions[pos]
            if len(vals) < MIN_PROGRAMS:
                continue
            rows.append({"pos": pos, "mean": statistics.fmean(vals),
                         "sd": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
                         "n": len(vals)})
        if not rows:
            continue
        out[cls] = {"positions": rows, "top": rows[0]["mean"], "bottom": rows[-1]["mean"],
                    "drop": rows[0]["mean"] - rows[-1]["mean"], "depth": rows[-1]["pos"]}
    return out


def class_report(bundle, ability_scope, board, champions_by_class: dict) -> list[dict]:
    """One row per classification: strength, spread, competitiveness, titles."""
    dressed = ability_scope.dressed
    strength: dict[str, list] = defaultdict(list)
    for program_id, prog in bundle.programs.items():
        if not int(float(prog.get("scope_member") or 1)):
            continue
        s = program_strength(ability_scope, program_id, dressed)
        if s is not None:
            strength[aggregate.program_class(prog)].append(s)

    close: dict[str, list] = defaultdict(lambda: [0, 0])   # [close, total] in-class duals
    for d in bundle.duals_full.values():
        home = bundle.programs.get(d["home_program_id"])
        away = bundle.programs.get(d["away_program_id"])
        if not home or not away:
            continue
        ch, ca = aggregate.program_class(home), aggregate.program_class(away)
        if ch != ca:
            continue
        row = close[ch]
        row[1] += 1
        if abs(_f(d.get("home_points"), 0.0) - _f(d.get("away_points"), 0.0)) <= 1:
            row[0] += 1

    rows = []
    for cls, vals in strength.items():
        if len(vals) < MIN_PROGRAMS:
            continue
        vals_sorted = sorted(vals, reverse=True)
        top = vals_sorted[:TOP_N]
        titles = champions_by_class.get(cls, Counter())
        seasons = sum(titles.values())
        # Herfindahl on title counts: 1.0 = one program wins everything,
        # 1/seasons = a different champion every year.
        hhi = sum((c / seasons) ** 2 for c in titles.values()) if seasons else None
        c_close, c_total = close.get(cls, [0, 0])
        rows.append({
            "classification": cls, "programs": len(vals),
            "strength": statistics.fmean(vals),
            "top_strength": statistics.fmean(top) if top else None,
            "spread_top": statistics.pstdev(top) if len(top) > 1 else None,
            "spread_all": statistics.pstdev(vals) if len(vals) > 1 else None,
            "gap_top_to_field": (statistics.fmean(top) - statistics.fmean(vals)) if top else None,
            "seasons": seasons, "distinct_champions": len(titles),
            "title_hhi": hhi,
            "champions": titles.most_common(5),
            "close_duals": c_close, "in_class_duals": c_total,
            "close_rate": (c_close / c_total) if c_total else None,
        })
    rows.sort(key=lambda r: aggregate.classification_sort_key(r["classification"]))
    return rows


def champions(bundles) -> dict:
    """{(family, gender): {classification: Counter(program name -> titles)}}
    across every ingested season, read off the archived draw."""
    out: dict[tuple, dict] = defaultdict(lambda: defaultdict(Counter))
    for b in bundles:
        for cls, data in (b.championships or {}).items():
            champ = (data or {}).get("champion")
            if champ:
                out[(b.family, b.gender)][cls][champ] += 1
    return out


def build(bundles, boards, ability) -> list[dict]:
    """One report per scope: [{scope_id, label, classes, shape, h2h, order}]."""
    champs = champions(bundles)
    reports = []
    for b in bundles:
        sa = ability.ability(b.scope_id)
        if sa is None:
            continue
        depth = sa.dressed or 9
        rows = class_report(b, sa, boards.get(b.scope_id, {}),
                            champs.get((b.family, b.gender), {}))
        if not rows:
            continue
        order = [r["classification"] for r in rows]
        h2h = head_to_head(b)
        matrix = []
        for a in order:
            cells = []
            for other in order:
                rec = h2h.get((a, other))
                total = (rec["w"] + rec["l"]) if rec else 0
                cells.append({"opp": other, "w": rec["w"] if rec else 0,
                              "l": rec["l"] if rec else 0, "n": total,
                              "pct": (rec["w"] / total) if total else None,
                              "self": a == other})
            played = sum(c["n"] for c in cells)
            won = sum(c["w"] for c in cells)
            matrix.append({"classification": a, "cells": cells, "n": played,
                           "w": won, "l": played - won,
                           "pct": (won / played) if played else None})
        reports.append({
            "scope_id": b.scope_id, "label": b.label, "order": order,
            "classes": rows, "shape": ladder_shape(b, sa, depth),
            "matrix": matrix, "depth": depth,
            "any_cross_class": any(m["n"] for m in matrix),
        })
    return reports

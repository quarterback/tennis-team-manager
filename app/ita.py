"""ITA Kickoff Weekend + National Team Indoor Championship — the season opener.

A faithful-but-bounded model of the real ITA preseason events, which differ by
division:

  * **Division I** runs the full **Kickoff Weekend** — the top ``KICKOFF_FIELD``
    teams (by *prior-year* final ranking) are grouped into ``KICKOFF_SITES``
    cosmetic four-team sites, each a seeded single-elim (host = top seed, 1v4 / 2v3);
    the site winners advance to a 16-team **National Team Indoor Championship**.
  * **Divisions II and III** have no Kickoff draft — their **National Team Indoor**
    is simply the **top 8** teams (per gender) by prior-year ranking in a seeded
    single-elim. (Lower stakes; mostly an early-season test / development reps.)

In our world "sites" are purely cosmetic (no geography / no live draft): ordering
is entirely by the prior-year ranking, falling back to roster **Power 6** in year 0
(no prior season to rank from). Everything is seed-deterministic and — once wired
into season mode — counts toward the season dual-match record AND the Power Index,
an early read on who's good.

This module is pure (no DB / no web layer): season mode supplies the ranked list
of schools and persists the resulting brackets.
"""
from __future__ import annotations

KICKOFF_SITES = 15                                  # cosmetic four-team host sites (D1)
TEAMS_PER_SITE = 4
KICKOFF_FIELD = KICKOFF_SITES * TEAMS_PER_SITE      # 60-team draft field (D1)
INDOOR_FIELD = 16                                   # D1 final-16 Indoor draw
SMALL_INDOOR_FIELD = 8                              # D2 / D3 top-8 Indoor draw

KICKOFF_DIVISIONS = {"D1"}                          # only D1 runs the Kickoff Weekend draft
INDOOR_DIVISIONS = {"D1", "D2", "D3"}               # every NCAA division has a Team Indoor


def runs_kickoff(division: str) -> bool:
    """Whether a division runs the Kickoff Weekend (only D1)."""
    return division in KICKOFF_DIVISIONS


def runs_indoor(division: str) -> bool:
    """Whether a division runs a National Team Indoor Championship."""
    return division in INDOOR_DIVISIONS


def runs_ita(division: str) -> bool:
    """Whether a division runs any ITA opener at all (kickoff and/or indoor)."""
    return runs_indoor(division)


def indoor_size(division: str) -> int:
    """Indoor draw size: 16 for D1 (fed by the Kickoff), 8 for the D2/D3 top-8 events."""
    return INDOOR_FIELD if division in KICKOFF_DIVISIONS else SMALL_INDOOR_FIELD


def kickoff_rounds(division: str) -> int:
    """Weeks the Kickoff Weekend occupies (a four-team site is two rounds; 0 if none)."""
    return 2 if runs_kickoff(division) else 0


def indoor_rounds(division: str) -> int:
    """Rounds in the Indoor single-elim (log2 of the draw size: 16→4, 8→3)."""
    return indoor_size(division).bit_length() - 1


def lead_weeks(division: str) -> int:
    """How many weeks the ITA opener pushes the regular-season slate back."""
    return kickoff_rounds(division) + indoor_rounds(division)


def power6(prog) -> float:
    """Power 6 — roster strength from the top-6 singles players' STR (their mean,
    doubled, so it reads on an easy spread-out scale). Available even preseason
    (STR falls back to ability before any results), so it's the year-0 ranking
    metric when there is no prior season to rank from."""
    from .ncaa import build_roster
    s = sorted((p.str_value() for p in build_roster(prog)), reverse=True)[:6]
    return round(sum(s) / len(s) * 2, 1) if s else 0.0


def kickoff_sites(ranked: list[str]) -> list[list[str]]:
    """Group the top ``KICKOFF_FIELD`` ranked schools into ``KICKOFF_SITES`` sites of
    ``TEAMS_PER_SITE``, snake-distributed by tier so the sites stay roughly balanced
    (the strongest host draws the weakest available team in each tier). Each returned
    site is ordered by overall rank — best first — for standard 1v4 / 2v3 seeding,
    so site[0] is the host (top seed)."""
    field = ranked[:KICKOFF_FIELD]
    sites: list[list[str]] = [[] for _ in range(KICKOFF_SITES)]
    for tier in range(TEAMS_PER_SITE):
        chunk = field[tier * KICKOFF_SITES:(tier + 1) * KICKOFF_SITES]
        # Alternate the fill direction each tier (a snake), so a strong host pairs
        # with weaker later-tier draws and total site strength evens out.
        order = (range(KICKOFF_SITES) if tier % 2 == 0
                 else range(KICKOFF_SITES - 1, -1, -1))
        for site_i, team in zip(order, chunk):
            sites[site_i].append(team)
    rank_of = {s: i for i, s in enumerate(field)}
    for site in sites:
        site.sort(key=lambda t: rank_of[t])         # best-first → 1v4 / 2v3
    return sites


def site_pairs(site: list[str]) -> list[tuple[str, str]]:
    """The two opening matches at a four-team site: 1v4 and 2v3 (better seed first
    so it hosts the line). Pairing follows the prior-year ranking, mirroring the
    real draft's seeding rule (the No. 1 host plays the lowest seed at its site)."""
    return [(site[0], site[3]), (site[1], site[2])]


def indoor_field(site_winners: list[str], ranked: list[str], size: int = INDOOR_FIELD) -> list[str]:
    """The ``size``-team National Team Indoor draw, seeded by prior-year ranking. For
    D1 the seed pool is the site winners plus the highest prior-ranked team not already
    through (the auto-bid host); for the D2/D3 top-8 events there are no site winners,
    so the field is simply the top ``size`` ranked teams."""
    field = list(site_winners)
    for s in ranked:                                 # fill to `size` by prior ranking
        if len(field) >= size:
            break
        if s not in field:
            field.append(s)
    rank_of = {s: i for i, s in enumerate(ranked)}
    field.sort(key=lambda t: rank_of.get(t, 10 ** 9))
    return field[:size]

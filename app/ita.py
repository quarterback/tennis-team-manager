"""ITA Kickoff Weekend + National Team Indoor Championship — the season opener.

A faithful-but-bounded model of the real ITA preseason event:

  * **Kickoff Weekend** — the top ``KICKOFF_FIELD`` teams (by *prior-year* final
    ranking) are grouped into ``KICKOFF_SITES`` cosmetic four-team sites. Each
    site is a seeded single-elimination mini-bracket (host = top seed, 1v4 / 2v3);
    the site winners advance.
  * **National Team Indoor Championship** — the site winners plus a top-ranked
    auto-bid host form an ``INDOOR_FIELD``-team seeded single-elim → the Indoor
    champion.

In our world "sites" are purely cosmetic (no geography / no live draft): ordering
is entirely by the prior-year ranking, falling back to roster **Power 6** in year 0
(when there is no prior season to rank from). Everything here is seed-deterministic
and — once wired into season mode — counts toward the season dual-match record,
exactly like the conference tournaments and the NCAAs do.

This module is pure (no DB / no web layer): season mode supplies the ranked list
of schools and persists the resulting brackets.
"""
from __future__ import annotations

KICKOFF_SITES = 15                                  # cosmetic four-team host sites
TEAMS_PER_SITE = 4
KICKOFF_FIELD = KICKOFF_SITES * TEAMS_PER_SITE      # 60-team draft field
INDOOR_FIELD = 16                                   # the final-16 Indoor draw

# A four-team site is two rounds (semifinals → final); the 16-team Indoor draw is
# four (Round of 16 → Quarterfinals → Semifinals → Final). The regular-season
# slate is pushed back this many weeks so the ITA event opens the year.
KICKOFF_ROUNDS = 2
INDOOR_ROUNDS = INDOOR_FIELD.bit_length() - 1       # 4
ITA_LEAD_WEEKS = KICKOFF_ROUNDS + INDOOR_ROUNDS     # 6

ITA_DIVISIONS = {"D1"}                              # the ITA Kickoff/Indoor is a D1 event


def runs_ita(division: str) -> bool:
    """Whether a division runs the ITA Kickoff Weekend + Indoor as its opener."""
    return division in ITA_DIVISIONS


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


def indoor_field(site_winners: list[str], ranked: list[str]) -> list[str]:
    """The ``INDOOR_FIELD``-team National Team Indoor draw: every site winner plus
    the highest prior-ranked team not already through (the auto-bid host), seeded by
    prior-year ranking (best first)."""
    field = list(site_winners)
    for s in ranked:                                 # fill the auto-bid seat(s)
        if len(field) >= INDOOR_FIELD:
            break
        if s not in field:
            field.append(s)
    rank_of = {s: i for i, s in enumerate(ranked)}
    field.sort(key=lambda t: rank_of.get(t, 10 ** 9))
    return field[:INDOOR_FIELD]

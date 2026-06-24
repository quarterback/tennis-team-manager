"""
NCAA 96-team regional bracket structure.

The national field (96 teams for D1) is seeded 1–96 by the Committee Seed Score,
then split into FOUR balanced regions of 24 via an S-curve (serpentine) so each
region is of comparable strength. Region names are PURELY COSMETIC rotating
labels (like basketball's East/West/South/Midwest) — drawn at random per season
from a fixed pool, never used to place teams by geography.

Within a 24-team region the top 8 seeds get byes and seeds 9–24 play an opening
round (9v24, 10v23, … 16v17); the eight winners join the byes to form a standard
16-team region bracket. The four region champions meet in the national semifinals.
"""
from __future__ import annotations

import random

# Region display order in the main draw so the #1 and #2 overall seeds' regions
# sit in opposite halves (region ranks A=1, B=2, C=3, D=4 → semis A/D and B/C).
REGION_LETTERS = ["A", "B", "C", "D"]
MAIN_DRAW_ORDER = [0, 3, 1, 2]            # bracket slot s holds region index MAIN_DRAW_ORDER[s]

# The eight bye seeds (1–8), in standard 16-bracket placement order. Bye seed
# BYE_SEQ[k] meets the opening-round winner of region line (17 − BYE_SEQ[k]).
BYE_SEQ = [1, 8, 5, 4, 6, 3, 7, 2]

# Opening-round pairings inside a region, by SEED LINE: (9,24),(10,23),…,(16,17).
PLAYIN_LINES = [(9 + g, 24 - g) for g in range(8)]

# Cosmetic region-name pool — the Learned League league names. Labels only; a
# "Bayou" or "Pacific" region carries NO geographic meaning.
LEAGUE_NAMES = [
    "Aloha", "Alpine", "Arcadia", "Archipelago", "Arctic", "Aspen", "Atlantic",
    "Aurora", "Avalon", "Badlands", "Bayou", "Beach", "Blue", "Boardwalk",
    "Byzantium", "Canyon", "Cardinal", "Cascade", "Centennial", "Central",
    "Cerulean", "Cherry", "Citadel", "Coastal", "Commonwealth", "Continental",
    "Coral", "Corridor", "Cosmos", "Cove", "Cypress", "Delta", "Denali",
    "Eclipse", "Elysium", "Ember", "Evergreen", "Fjord", "Foothills", "Forest",
    "Foundry", "Frontier", "Galaxy", "Garden", "Geyser", "Glacier", "Grove",
    "Gulf", "Harbor", "Highland", "Hinterland", "Horizon", "Island", "Isthmus",
    "Junction", "Jungle", "Juniper", "Kaleidoscope", "Keystone", "Kookaburra",
    "Labyrinth", "Lagoon", "Laguna", "Laurel", "Lighthouse", "Lyceum",
    "Maelstrom", "Magnolia", "Maritime", "Meadow", "Memorial", "Meridian",
    "Mesa", "Metro", "Midland", "Mojave", "Monolith", "Morningstar", "Mosaic",
    "Mountain", "Nautilus", "Nebula", "Nighthawk", "Nova", "Oasis", "Obsidian",
    "Ocean", "Olive", "Olympic", "Orange", "Orbital", "Orchard", "Orchid",
    "Outback", "Overlook", "Oxbow", "Pacific", "Palisade", "Pampas", "Park",
    "Patagonia", "Peninsula", "Piedmont", "Pioneer", "Plateau", "Plaza",
    "Polaris", "Prairie", "Quarry", "Quay", "Quetzal", "Rainbow", "Rainforest",
    "Ranger", "Ravenna", "Redwoods", "Ridge", "River", "Riviera", "Rubicon",
    "Saguaro", "Sahara", "Sakura", "Savanna", "Seaboard", "Seneca", "Sequoia",
    "Serengeti", "Sierra", "Skyline", "Spring", "Sugarloaf", "Summit", "Sunrise",
    "Sycamore", "Taiga", "Tempest", "Tidewater", "Tranquility", "Tundra",
    "Typhoon", "Union", "Utopia", "Valhalla", "Valley", "Veldt", "Village",
    "Vista", "Volcano", "Waterfront", "Wilderness", "Willow", "Windward",
    "Woodlands", "Xanadu", "Yukon", "Zenith", "Zephyr", "Ziggurat",
]


def scurve_regions(seeds: list, n_regions: int = 4) -> list[list]:
    """Split a national seed list (index 0 = #1) into `n_regions` balanced regions
    by an S-curve. Returns `regions` where `regions[r][line]` is the team at region
    `r`, regional seed `line + 1`. Each region gets one team per seed line, with the
    line's teams handed out left-to-right on odd lines and right-to-left on even
    lines so total strength stays even across regions."""
    regions: list[list] = [[] for _ in range(n_regions)]
    lines = len(seeds) // n_regions
    for line in range(lines):
        group = seeds[line * n_regions:(line + 1) * n_regions]
        order = range(n_regions) if line % 2 == 0 else range(n_regions - 1, -1, -1)
        for r, team in zip(order, group):
            regions[r].append(team)
    return regions


def region_index_of(seeds: list, n_regions: int = 4) -> dict:
    """{team: region_index} for the S-curve split — for labelling/grouping."""
    out = {}
    for r, members in enumerate(scurve_regions(seeds, n_regions)):
        for team in members:
            out[team] = r
    return out


def region_names(seed: int, n_regions: int = 4) -> list[str]:
    """`n_regions` distinct cosmetic region names, drawn deterministically from the
    season seed (stable within a save-year, rotates year to year). Labels only."""
    rng = random.Random(f"ncaa-regions|{seed}")
    return rng.sample(LEAGUE_NAMES, n_regions)

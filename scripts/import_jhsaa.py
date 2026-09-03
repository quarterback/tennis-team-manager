#!/usr/bin/env python3
"""
Build the JHSAA — Jefferson's high-school tennis association — from `prep-network`.

Writes `data/jhsaa/schools.json`: every Jefferson school that sponsors tennis, with its
classification, city/county/area, mascot, colours, and its DISTRICT for each gender.

Two things this does NOT do, deliberately:

  * It does not import prep-network's players. That repo supplies INSTITUTIONS; the
    season is played here by this engine with players generated here.
  * It does not inherit prep-network's `sports` flags for tennis. That generator rolled
    `boys-tennis` and `girls-tennis` independently per school, producing 202 boys teams
    against 441 girls and only 117 schools fielding both — 3A alone has 10 boys teams
    and 81 girls. It is an artifact, and it leaves the boys' season unschedulable (20
    one-team leagues). Sponsorship is re-derived below on the real-world pattern.

Sponsorship: girls-sponsoring is the SUPERSET, boys a ~88% subset of it. Schools that
field girls tennis but not boys are common; the reverse essentially does not happen.
Co-op programs are not modelled — single schools only.

Districts: prep-network's 99 conferences are all-sport geographic groupings and 92 of
them span classifications, so they shatter when filtered to one class and to tennis
sponsors. Tennis draws its own map the way Oregon does — balanced districts of <= 12 per
classification, geographically contiguous, named for a PLACE — area, then county, then
city, then a compound of its two largest towns. Never numbered, and never sharing a
leading word with another district in the same class ("Halbrook Basin" and "Halbrook"
are an area and a county inside it, and read as one league).

Deterministic: seeded, so two runs are identical. Idempotent.

    python3 scripts/import_jhsaa.py [--prep-network ../prep-network] [--dry-run]

See docs/DESIGN-jhsaa-high-school-season.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_OUT_DIR = os.path.join(_REPO, "data", "jhsaa")
_OUT = os.path.join(_OUT_DIR, "schools.json")

SEED = 11
MAX_DISTRICT = 12

# ‼️ A LEAGUE IS AIMED AT `DISTRICT_TARGET`, AND ONLY CAPPED AT `MAX_DISTRICT`
# (owner rule 2026-08). The draw used to take `k = ceil(n / MAX_DISTRICT)` — the
# FEWEST blocks that fit under the cap — which quietly turned a ceiling into a
# target: every class packed its leagues to 11-12 and the cap became the design.
# The owner's correction: "no conference should be over 12 teams like I said
# before, with 40 teams there's no reason for some weird cap on districts when
# smaller ones (around 10 teams) would be fine." So the block count is chosen to
# land near TEN and the cap is what it says it is — a limit that must not be
# exceeded, not a size to fill. A ten-team league plays an 18-dual double round
# robin under `jhsaa.DISTRICT_DUAL_CAP`, which is a full league season.
DISTRICT_TARGET = 10


def district_count(n: int) -> int:
    """How many leagues a pool of `n` schools is cut into.

    Aim at `DISTRICT_TARGET`, never exceed `MAX_DISTRICT`. `round` rather than
    `ceil` because both sides of the target are fine — nine is as good a league as
    eleven — and the max() floor is what keeps the cap a hard one.
    """
    if n <= 0:
        return 0
    return max(round(n / DISTRICT_TARGET), -(-n // MAX_DISTRICT), 1)

# Girls sponsorship rate by classification; boys is a subset of the girls sponsors.
# 2A and 1A are deliberately well above a realistic sponsorship rate (owner rule
# 2027-08). Splitting 3A-1A into two championships left 2A-1A with 18 programs and an
# 8-team state field — 44% of the classification making state, which is not a
# tournament. The fix the owner chose is more programs rather than a smaller field —
# and then MORE again: 2A/1A sponsor at rates no real state would post, because a
# huge, ragged small-school classification is the fun of it. The talent bands say
# what the level is; the roster count says how much of it there is to watch.
GIRLS_RATE = {"9A": 0.90, "8A": 0.88, "7A": 0.85, "6A": 0.80, "5A": 0.74, "4A": 0.66,
              "3A": 0.58, "2A": 0.72, "1A": 0.60}
BOYS_OF_GIRLS = 0.88

# Forced-in schools that field GIRLS tennis only. `always_sponsor()` puts a named
# school in for BOTH genders, which is right for nearly all of them; this is the
# exception list for the rare one that doesn't field a boys team (own-source fact,
# not a random draw the way an unforced girls-only program is). Girls-sponsoring
# being the superset (see the sponsorship note above) means there's no equivalent
# ALWAYS_BOYS_ONLY case to mirror.
ALWAYS_GIRLS_ONLY = {
    
}

# Schools the owner wants in the association without giving them an archetype. The
# archetype seed list is folded in automatically — see `always_sponsor`.
ALWAYS_EXTRA = [
    "Abbey Prep",
    "Annie Springs",
    "Arrieta Treasure Valley",
    "Aurelia",
    "Bahía Leal",
    "Bahía Leal Costa Verde",    # → "Housatonic" in this association (RENAMES)
    "Baptist HS",
    "Beacon Hill",
    "Breakwater",
    "Calderwood School",
    "Caswell Depot High",
    
    "Chaminade",
    "Commonwealth",
    "Condotti Vanguard Academy",
    "Cortland",
    "Crown Hill",
    "Dolores Huerta",
    "Dry Lake",
    
    "Echevarria Foundry High",
    "Elk Bluff",
    "Elk Crossing",
    "Emerson",
    "Ferris Union",
    "Fort Valois",
    "Gagarin School of Public Service",
    "Galena",
    "George Washington Carver",
    "Gold Hollow",
    "Gold Junction",
    "Golden Gate",
    "Gwendolyn Brooks",
    "Halfway House",
    "Harlan Cole",
    "Harrow",
    "Hazel Bennett",
    "High Prairie",
    "Homestead",
    "Jean Lindgren",
    "Keldale",
    "Las Norias",
    "Las Palmas",
    "Latgaway",
    "Lorraine Calder",
    "Mabryville",
    "Marlow County",
    "Mesa Dorada",
    "Montelago",
    "Netherwood",
    "New Leiden",
    "Newark River North",
    
    "Owl Canyon",
    "Pacific Friends School",
    "Paul Robeson",
    "Pinecrest School",
    "Port Meridian Polytechnic",
    "Port Meridian West",
    "Providence Academy",
    "Puerto Gallego",
    "Ransom Spur",
    "Redwood Coast",
    "Romero-Finniski",
    "Sage Point",
    
    "San Borondón",
    "San Cordero",
    "San Tomás",
    "Santa Cruz del Norte",
    "Santa Laura",
    "Santa Laura North",
    "Seafarer High",
    "Selbyville",
    "Silver Glen",
    
    "Snowline",
    "St. Agnes Academy",
    "St. Basil Academy",
    
    
    "St. Norbert Abbey",
    
    "St. Sebastian Prep",
    "St. Vincent School",
    "Steelbridge",
    "Summervale Northwest",
    "Svenja Ekström",
    "Telfair",
    "Telfair Country Day School",
    "Three Saints",
    "Timberline",
    "Treasure Valley",
    "Trinity Catholic",
    "Twin Rivers",
    "Valderra",
    "Valley Christian",
    "Wales City",
    "Westover",
    "Westside Christian",
    "Winifred Booker",
    # ⚠️ CONTINUITY (owner rule 2027-08). prep-network grew from 840 schools to
    # 1,111 and sponsorship is a positional dice draw over the name-sorted list,
    # so schools already in the association — including ones the owner had named
    # a mascot for, Trout Junction among them — fell out of it for no reason but
    # their neighbours' arrival. A school that has played here stays here.
    "Alder Landing Beacon Hill",
    "Alderfield",
    "Alina Belov",
    "Andrés Valera",
    "Aspen Harbor",
    "Belmonte",
    "Bidwell",
    "Draybrook Union",
    "Eleanor Tillman",
    "Elk Prairie",
    "Fort Salish",
    "Garazi Aramburu",
    "Haverly",
    "High Desert Christian",
    "Katherine Davenport",
    "Lev Voronin",
    "Los Robles",
    "Marian Browne",
    "Millport",
    "Orchard Hill",
    "Oskar Bellini",
    "Port Meridian South",
    "Quarmont",
    "Ryken",
    "Sage Meadows",
    "Soren Ekström",
    "Southridge Christian",
    "St. Elian",
    
    "Starlake",
    "Thomas Ekström",
    "Trout Lake",
    "Yarburg",
    "Yarmere",
]

# ‼️ OWNER EDICTS — NAMES THAT ARE NOT UP FOR REVISION (2027-08).
#
# Everything in this file is the owner's map, but these were dictated by NAME
# rather than arrived at by a generator or proposed by an agent. A later pass
# may rename anything else it finds bland; it may NOT "improve" one of these,
# fold it into a naming family, or trade it away to resolve a collision. If one
# of them collides with something, the OTHER thing moves.
#
# This list exists because this map has now been renamed in a dozen sweeps, and
# the failure mode of a sweep is that it treats a deliberate name as noise.

# ‼️ THE PRESIDENTS OF CONGRESS — a naming reservoir the map has barely touched
# (owner, 2026-08: "this list is also undertapped"). Fourteen men presided over the
# Continental Congress and then over Congress Assembled under the Articles, before
# there was a presidency to be first at. They are exactly the kind of name a real
# American high school carries and almost none of them are used here, which makes
# them a better reservoir than another coined terrain word: they are REAL PEOPLE
# with a claim on the founding, so a school named for one reads as an institution
# with a reason rather than as a generator's output.
#
# ‼️ These are REAL PEOPLE. A school given one of these names is thereafter covered
# by the never-rename-a-real-person rule, exactly like the presidents and justices
# already on the map.
PRESIDENTS_OF_CONGRESS = (
    # Continental Congress
    "Peyton Randolph",      # Virginia, 1774 and 1775
    "Henry Middleton",      # South Carolina, 1774
    "John Hancock",         # Massachusetts, 1775-1777 — presided at the Declaration
    "Henry Laurens",        # South Carolina, 1777-1778
    "John Jay",             # New York, 1778-1779
    # Congress Assembled, under the Articles of Confederation
    "Samuel Huntington",    # Connecticut, 1779-1781
    "Thomas McKean",        # Delaware, 1781
    "John Hanson",          # Maryland, 1781-1782
    "Elias Boudinot",       # New Jersey, 1782-1783
    "Thomas Mifflin",       # Pennsylvania, 1783-1784 — presided when the war ended
    "Richard Henry Lee",    # Virginia, 1784-1785
    "Nathaniel Gorham",     # Massachusetts, 1786-1787
    "Arthur St. Clair",     # Pennsylvania, 1787-1788
    "Cyrus Griffin",        # Virginia, 1788-1789
)

OWNER_EDICTS = frozenset({
    # schools
    "Evans Larsen Day", "Chester A. Arthur", "Siskiyou Valley", "Cook City",
    "Fountain Park", "James K. Polk", "Lyndon B. Johnson", "William Howard Taft",
    "Earl Warren", "Sonia Sotomayor", "Ketanji Brown Jackson",
    "Sandra Day O'Connor", "Ruth Bader Ginsburg", "John Quincy Adams",
    "John F. Kennedy", "Western Sky",
    # 2046 expansion (owner edict 2026-08): the new 1A activation in Ransom,
    # Tamarack County — dictated by name after the "Ransom City Union" source
    # name collided with a former name of Ransom Pass.
    "Reverend City",
    # towns
    "Cape Angeles", "Fort Tabor", "New Penzance Island", "Bay Oregon",
    "Carolina Island", "North San Francisco", "California Canyons", "Vonjo City",
    "Galactica Plains", "Simmons", "North Simmons", "South Simmons",
    "East Simmons", "Linden", "Sage Village", "Minnesota City",
    "Seamus Town",
    "Georgia Mills", "Texas Beach", "California Beach", "Jersey City", "Jamaica",
    "Sotkamo", "Kuusamo", "Iisalmi", "Lieksa", "Nurmes", "Raahe",
    # the uplands the owner named outright
    "Mount Clambake", "Mt Jacqueline", "Gruesome Ridge", "Annes Summit",
    "Meridian Passage", "Mount Ruth", "Mount Dylan Lake", "Corey Canyon",
    "Aftdahl Ridge", "Brynildson Hill",
    # NOT "Mount Henson" — that rename was agent work, not an edict, and the owner
    # reversed it (2026-08): the town keeps prep-network's own name, Plainfield.
    # areas
    "Southern Jefferson", "Millersylvania",
    "Salmon Bay",
    "Espoo", "New Bergen", "New Ballard",
})


# ABSORPTION-STYLE RENAMES (owner rule 2027-08) — the same pattern the college
# import uses for programs standing on Jefferson ground (Oregon Tech → Cascade
# Polytechnic): the INSTITUTION comes from prep-network, which stays untouched
# (its published record — seasons, titles, editorial — keeps the source name);
# the tennis association knows the school by the owner's name.
#
# ⚠️ Keyed by SOURCE name and applied ONLY when a row is emitted, never at load:
# the sponsorship dice in `sponsors()` are drawn positionally over the
# name-sorted school list, so renaming before the draw would shift every school
# between the two alphabetical positions onto its neighbour's roll and reshuffle
# a chunk of the association. Everything internal — forcing, dice, district
# drawing — runs on the source name; only the written row carries the new one.
# ‼️ WHAT A SCHOOL USED TO BE CALLED — generated, never hand-edited.
#
# The archive keys on the DISPLAY NAME at the time a season was written, so a
# rename orphans every row a school has already earned: its program page finds
# nothing and the old name 404s. A 2031 state champion disappeared from its own
# page that way. The data was never lost — only the link.
#
# Rebuild with `scripts/jhsaa_former_names.py`, which walks the git history of
# RENAMES. It has to come from git: renaming a school twice REWRITES the target
# in place (the rule — never chain A -> B -> C), so the intermediate name exists
# nowhere in the current table.
#
# ‼️ A LIVE NAME ALWAYS WINS. A former name that is now some OTHER school's live
# name is excluded here, and `jhsaa.resolve_school` checks live names first in any
# case: an alias must never outrank a school that exists.
FORMER_NAMES = {
    "Abbey Vale Orchard Hill":                     "Booker T Washington",
    "Abraham Lincoln":                             "Lincoln",
    "Academy of Arts and Communication":           "Junction",
    "Adams":                                       "Sally Ride",
    "Adela Robles":                                "Biloxi Heights",
    "Adela Robles North":                          "Cliffside",
    "Adela Villaseñor":                            "Cape Jean",
    "Ainhoa Mendizabal":                           "Charles Harbor",
    "Aitor Echevarria":                            "Point Loma",
    "Aitor Zubieta":                               "Borough Beach",
    "Aldecoa Academy of Arts and Letters":         "Coyote Springs",
    "Aldecoa Applied Sciences Institute":          "Deadwood",
    "Aldecoa Depot High":                          "Ulysses Grant",
    "Alder Landing Beacon Hill":                   "Bay Oregon",
    "Alderfield":                                  "Linden",
    "Aldermont":                                   "Cape Angeles",
    "Alejandro Zamora":                            "Morgan Park",
    "Alina Antonov":                               "River Oaks",
    "Alina Belov":                                 "Clear Lake",
    "Alonso Villalba":                             "Los Feliz",
    "Altamonte Civic Leadership Academy":          "Senator Gray",
    "Amaia Aramburu":                              "Ketanji Brown Jackson",
    "Amaia Aramburu North":                        
    "Amaia Echevarria":                            "Redwood Mutual",
    "Amaia Etxeberria":                            "Boyle Heights",
    "Amalia Escobedo":                             "Petoskey Rock",
    "Amelia Freeman":                              "Nanticoke",
    "Amelia Freeman North":                        "Casco",
    "Amos Cross":                                  "Lyndon B. Johnson",
    "Amos Moss":                                   "St. Francis Catholic",
    "Ander Aramburu":                              "Western Sky",
    "Ander Arrieta":                               "Bolinas",
    "Andrew Jackson North":                        "Chaparral",
    "Andrés Ibarra":                               "Monongahela",
    "Andrés Ibarra North":                         "Saddleback Central",
    "Andrés Valera":                               "Basalt Electric",
    "Andrés Valera North":                         "Pawnee",
    "Anneliese Halvorsen":                         "George Washington",
    "Anneliese Ricci":                             "Carondelet",
    "Annie Springs Crater View":                   "Crater View",
    "Ansotegui Siding Commonwealth":               "Pinebluffs",
    "Antler County High":                          "Antler County",
    "Anya Antonov":                                "Mar Vista",
    "Anya Belov":                                  "Arroyo",
    "Anya Belov North":                            "Preston Hollow",
    "Anya Orlov":                                  "Riviere Salee",
    "Archbishop Doyle Prep North":                 "Doyle Ridge",
    "Arrieta Treasure Valley":                     "Canyonlands",
    "Arroyo Water District":                       "Arroyo",
    "Ashbury Central North":                       "Kishwaukee",
    "Ashbury East":                                "Alameda",
    "Ashbury Heights":                             "Ashbury Central",
    "Ashbury West":                                "Laurel Park",
    "Ashfield":                                    "California Beach",
    "Ashwood":                                     "Gruesome Ridge",
    "Aspen Harbor":                                "East Simmons",
    "Astrid Ricci":                                "Jesuit",
    "Aurelia Classical Academy":                   "Goodman",
    "Baptist HS":                                  "Baptist",
    "Barclay Golden Gate":                         "Gate City",
    "Barlowe County High":                         "Barlowe County",
    "Basalt Fork":                                 "Río Salado",
    "Beatrice Davenport":                          "Fort Halloran",
    "Beatriz Salcedo":                             "Spring Branch",
    "Beatriz Zamora":                              "Tower Grove",
    "Belden Springs Academy of Music and Media":   "Springdale",
    "Belmonte Agricultural Sciences Academy":      "Pelican Town",
    "Belmonte Applied Sciences Institute":         "Yazoo",
    "Belmonte Civic Leadership Academy":           "Keeler",
    "Belmonte Classical Academy":                  "James Madison",
    "Belmonte Collegiate Academy":                 "Rock on the Hill Christian Academy",
    "Belmonte Health Sciences Academy":            "Dusty Spur",
    "Belmonte International":                      "Belmonte Collegiate",
    "Belmonte International School":               "Belmonte Collegiate",
    "Belmonte Northwest":                          "Kokomo",
    "Belmonte River Plain":                        "Chillicothe",
    "Belmonte Technical Arts Academy":             "Sojourner Truth",
    "Belyakov":                                    "East Moscow",
    "Belyakov Academy of Music and Media":         "Walter-Kenny",
    "Belyakov Agricultural Sciences Academy":      "Mickey Mantle",
    "Belyakov Depot High":                         "Anse Doree",
    "Belyakov Design":                             "Grande-Savane Arts",
    "Belyakov Environmental Sciences Academy":     "Friendship City",
    "Belyakov Polytechnic Institute":              "Morne Caribou Polytechnic",
    "Belyakov River Plain":                        "Grand Fond",
    "Belyakov River Plain North":                  "Lycee Valmont",
    "Belyakov School of Design and Engineering":   "Grande-Savane Arts",
    "Belyakov School of Science and Industry":     "Kongisburg",
    "Belyakov Science":                            "Kongisburg",
    "Benjamin Banneker North":                     "Pascagoula",
    "Bidwell City":                                "Alfalfa City",
    "Bidwell County":                              "County Line",
    "Blackbird Canyon":                            "Tallulah Canyon",
    "Blackpine North":                             "Ravenwood",
    "Bogue Chitto":                                "Harmony",
    "Boyerstown North":                            "Alder Crossing",
    "Bracken Works":                               "Bracken",
    "Brackwood Union":                             "Brackwood Pass",
    "Breakwater North":                            "Lighthouse",
    "Brynildson Baptist":                          "Baptist",
    "Buckeye Bend":                                "Wyalusing",
    "Cabo Esperanza Technical Arts Academy":       "Cabo Esperanza Tech",
    "Calder North":                                "Stonehaven",
    "Calderwood School":                           "Calderwood",
    "Calvary Chapel Ditch Fork":                   "Cassius",
    "Calvary Chapel Kilbride Switch":              "Gottschalk-Herman",
    "Calvary Chapel Olivet":                       "Banfield Day",
    "Canal View North":                            "Lateral Seven",
    "Carden City West Bench":                      "Buckhorn",
    "Carmen Cordero":                              "Bannock",
    "Carmen Valera":                               "Ferris",
    "Carroway Public Service":                     "Liberty Hill",
    "Carroway School of Public Service":           "Liberty Hill",
    "Caswell Depot High":                          "Cherry Hill North",
    "Caswell I-50 Technical":                      "Cherry Hill South",
    "Caswell School of Science and Industry":      "Chester A. Arthur",
    "Caswell Science":                             "Chester A. Arthur",
    "Caswell University Prep":                     "Palisade Prep",
    "Cañada Irrigation":                           "Canyon",
    "Cedarport":                                   "North San Francisco",
    "Clara Brown HS":                              "Clara Brown",
    "Clara Cross":                                 "Red Mesa",
    "Claudette Cole North":                        "Pointe Coupee",
    "Claudette Freeman":                           "Alder Cooperative",
    "Copper Crossing":                             "Copper Gap",
    "Copper Lake East":                            "Bridgewater",
    "Copper Lake West":                            "Azurite",
    "Costa Verde North":                           "Verde Highlands",
    "Covenant":                                    "Stonehaven",
    "Coyote Draw":                                 "Savane Brulee",
    "César Mendoza":                               "De La Salle",
    "César Peralta":                               "Avalon Park",
    "Dahlberg":                                    "Dahlberg Summit",
    "Dahlberg School of Science and Industry":     "Hartford City",
    "Dahlberg Science":                            "Hartford City",
    "Daniel Gaines":                               "Vicksburg",
    "Daniel Gaines North":                         "Tensas",
    "Depot High":                                  "Passaic",
    "Depot High North":                            "Natchez",
    "Doyle Junction":                              "Doyle Pass",
    "Drayfield Foundry High":                      "Empire",
    "Echevarria Foundry High":                     "Bitterroot",
    "Echevarria I-50 Technical":                   "Red Bluff",
    "Edith Hart":                                  "Bellarmine Prep",
    "Edith Mercer":                                "Forest Park",
    "Edith Tillman":                               "Norwood Park",
    "Edith Ward":                                  "Central West End",
    "Eleanor Cole":                                "Jefferson Park",
    "Eleanor Tillman":                             "Anchor Glass",
    "Elena Mendoza North":                         "Cahaba",
    "Elena Petrenko":                              "Kingsway",
    "Elena Petrov":                                "Talladega",
    "Elias Mercier":                               "Cascade Mutual",
    "Elk Prairie":                                 "Carolina Island",
    "Elmburg":                                     "Mt Jacqueline",
    "Elmfield":                                    "Nurmes",
    "Emigrant Trail":                              "Trailhead",
    "Emilia Jansen":                               "Sharpstown",
    "Esteban Téllez":                              "Sawtelle",
    "Evelyn Booker":                               "William Howard Taft",
    "Ewart City":                                  "Cook City",
    "Ewartville":                                  "Fort Tabor",
    "Featherstone Institute":                      "Featherstone Tech",
    "Fellows Mill Civic Leadership Academy":       "Millworks",
    "Fellows Mill International":                  "Mill Bar",
    "Fellows Mill International School":           "Mill Bar",
    "Ferris Union":                                "Union Prairie",
    "Fig Gap":                                     "Río Verde",
    "Fort Meriwether Breakwater":                  "Breakwater",
    "Fort Meriwether Foundry High":                "Ironworks",
    "Fort Meriwether Foundry High North":          "Westfield Friends",
    "Fort Salish":                                 "Fort Weller",
    "Fort Salish Independent":                     "Weller Independent",
    "Fort Salish Independent School":              "Weller Independent",
    "Fort Valois Design":                          "Valois Bluffs",
    "Fort Valois Public Service":                  "Sagebrush",
    "Fort Valois School of Design and Engineering": "Valois Bluffs",
    "Fort Valois School of Public Service":        "Sagebrush",
    "Foundry High":                                "Foundry",
    "Frances Gaines":                              "Empire Milling",
    "Frontier High":                               "Frontier",
    "Gabriel Montoya":                             "Marlow",
    "Gabriel Zúñiga":                              "Longfellow",
    "Gagarin Public Service":                      "Star City",
    "Gagarin School of Public Service":            "Star City",
    "Galina Markov":                               "James Monroe",
    "Galina Moroz":                                
    "Galina Romanov":                              "Stagewater",
    "Garazi Aramburu":                             "Ocean Park",
    "Garazi Mendizabal":                           "Cedar Exchange",
    "Garfield Park":                               "Reservoir Park",
    "Garrity":                                     "Texas Beach",
    "Geraldine Cross":                             "Port Veles Episcopal",
    "Gold Junction":                               "Seamus Town",
    "Goodman School":                              "Goodman",
    "Granite Bar":                                 "New Penzance Island",
    "Graymont":                                    "Georgia Mills",
    "Greaves Aviation and Engineering Academy":    "Skypark",
    "Greaves Junction":                            "Juniper Crossing",
    "Green Valley School":                         "Green Valley",
    "Greta Adler":                                 "Topanga",
    "Greta Bellini":                               "Glassell Park",
    "Gulch Bend":                                  "West El Paso",
    "Gwendolyn Brooks North":                      "Lakewood",
    "Halbrook Technical":                          "Basin Gate",
    "Halbrook Union":                              "Deaconsburg",
    "Harbor Gate North":                           "Martin Van Buren",
    "Harlan Cole":                                 "Harlan",
    "Harlan Tillman":                              "Xavier College Prep",
    "Harmon":                                      "Annes Summit",
    "Harold Calder":                               "Tomales Bay",
    "Harold Tillman":                              "Copper Belt",
    "Harold Tillman North":                        "Echevarria",
    "Harold Williams":                             "Tuskegee",
    "Harriman Maritime Academy":                   "John F. Kennedy",
    "Harriman South":                              "Hidden Draw",
    "Harrow Design":                               "New Boston",
    "Harrow School of Design and Engineering":     "New Boston",
    "Harry S. Truman North":                       "Fair Park",
    "Hawk Lake Eastgate":                          "Oakhaven",
    "Hawk Lake Southeast":                         "Pine Barrens",
    "Hazel Bennett":                               "Benton Park",
    "Hazel Hart":                                  "Oak Meyer",
    "Henrik Keller":                               "William Henry Harrison",
    "Henry Turner":                                "Bishop Turner",
    "Hetfield":                                    "Brynildson Hill",
    "Homecroft Manufacturing and Technology Academy": "West Burlington",
    "Homestead North":                             "Garden Plain",
    "Housatonic HS":                               "Housatonic",
    "Huckle Lake":                                 "Mount Dylan Lake",
    "I-50 Tech":                                   "Belmonte Tech",
    "I-50 Technical":                              "Belmonte Tech",
    "I-50 Technical North":                        "Tuscarora",
    "Igor Chernov":                                "Zachary Taylor",
    "Igor Chernov North":                          "Fillmore",
    "Iker Aramburu":                               "Sandra Day O'Connor",
    "Iker Aramburu North":                         "Highland Park",
    "Imani Cross":                                 "Apalachicola",
    "Irina Kovalenko":                             
    "Irina Kovalenko North":                       "Arroyo Verde",
    "Isabel Lucero":                               "El Sereno",
    "Isabel Montalvo":                             "Magnolia Park",
    "Isaiah Booker":                               "Earl Warren",
    "Isaiah Price":                                "Squier Park",
    "Itziar Elorriaga":                            "Elysian Valley",
    "Itziar Lertxundi":                            "Noe Valley",
    "James Gaines":                                "Rogue Valley Packing",
    "James Madison North":                         "Hagerstown",
    "Janice Bennett":                              "Calvary Christian",
    "Janice Cole":                                 "Fallon Works",
    "Javier Alvarado":                             "Okefenokee",
    "Javier Alvarado North":                       "Shenango",
    "Javier Castañeda":                            "Kenwood",
    "Javier Cárdenas North":                       "Casa Linda",
    "Javier Villalba":                             "Los Feliz",
    "Jean Lindgren":                               "Bridgeport",
    "Jean Lindgren North":                         "Harrisburgh",
    "Jeannette Freeman":                           "Round Mountain Grange",
    "Jefferson School of Science and Technology":  "Jefferson Science",
    "Jefferson School of Science and Technology North": "Evans Larsen Day",
    "Jefferson Science North":                     "Evans Larsen Day",
    "Jesuit Mercer City":                          "Jesuit",
    "John F. Kennedy North":                       "Box Canyon",
    "Jon Etxeberria North":                        "Chickasaw",
    "Jon Garmendia":                               "Pope Leo XIV",
    "José Martí":                                  "Trois Ilets",
    "José Martí North":                            "Belle Rive",
    "Katherine Bellamy":                           "Meadowbrook",
    "Katherine Booker":                            "James K. Polk",
    "Katherine Davenport":                         "Blue Mountain Grange",
    "Katherine Whitaker":                          "Brookside",
    "Katherine Williams":                          "Franklin Pierce",
    "Katya Moroz":                                 "Emigrant",
    "Katya Moroz North":                           "Pinyon Ridge",
    "Keldale":                                     "Espoo",
    "Kelford Northwest":                           "Horseshoe Bend",
    "Kelview Union":                               "Iisalmi Union",
    "Kilbride Switch South":                       "Switchback",
    "Klara Marchand":                              "Weller",
    "Lake Esperanza South":                        "Malheur Flat",
    "Langston Central":                            "Singleton",
    "Lars Bellini":                                "Bernal Heights",
    "Lars Mercier":                                "Shasta Agricultural",
    "Las Palmas":                                  "Tuscaloosa",
    "Las Palmas North":                            "Natchitoches",
    "Leidesdorff Academy of Music and Media":      "East Burlington",
    "Leire Aramburu":                              "Furnace Creek",
    "Leire Garmendia":                             "Potrero Hill",
    "Lena Talltree":                               "Dogpatch",
    "Lev Kareva":                                  "Hayes Valley",
    "Lev Volkov":                                  "Sherwood Estates",
    "Lev Voronin":                                 "Cole Valley",
    "Lillian Price":                               "North Coast Packing",
    "Lillian Stokes":                              "Ben Franklin",
    "Llerena East":                                "Juniper Well",
    "Llerena School of Science and Industry":      "Crow Basin",
    "Llerena Science":                             "Crow Basin",
    "Lodestone County High":                       "Lodestone County",
    "Loomis City North":                           "Charlotte",
    "Lorna Booker":                                "Blue Grama",
    "Lorraine Calder":                             "Morne Rouge",
    "Los Remolinos Mission Bay":                   "Estuary Bay",
    "Lost River Irrigation":                       "Lost River",
    "Lucía Quiñones":                              "Edgewater",
    "Lucía Villaseñor":                            "Glen Park",
    "Madrigal Maritime Academy":                   "Maritime",
    "Madrigal West Bench":                         "Benchlands",
    "Maksim Karev":                                "Excelsior",
    "Manuel Cordero":                              "Sonia Sotomayor",
    "Manuel Robles":                               "Asteroid City",
    "Manzanita Ridge":                             "Manzanita",
    "Marcus Langston":                             "Rutherford Hayes",
    "Marcus Langston North":                       "Garfield",
    "Marcus Mercer":                               
    "Marcus Price North":                          "Driftwood",
    "Marian Browne":                               "River Market",
    "Marian Cross":                                "Quail Hollow",
    "Marina Moroz":                                "Cleveland",
    "Marina Moroz North":                          "Benjamin Harrison",
    "Marsh Depot":                                 "Jersey City",
    "Marshdale":                                   "Fort Lassiter",
    "Marshfield":                                  "Asteroid City",
    "Matteo Dahl":                                 "Bywater",
    "Mercer City Technical Arts Academy":          "Twin Mills",
    "Mercy Academy":                               "Natchez Mercy",
    "Meridian Valley":                             
    "Metropolitan Country Day School":             "Metropolitan Country Day",
    "Mikel Echevarria":                            "Fir Valley Grange",
    "Mikel Garmendia":                             "Homeland",
    "Mikel Zubieta":                               
    "Mikhail Sidorov":                             "Saint Marc",
    "Mila Chernov North":                          "Siberia",
    "Mila Melnick":                                "Sea Cliff",
    "Milldale Union":                              "Sotkamo Union",
    "Millport":                                    "Vonjo City",
    "Millview":                                    "Kuusamo",
    "Minidoka":                                    "Wyalusing Providence",
    "Miren Elorriaga":                             "Pennsauken",
    "Miren Garmendia":                             "Cardinal Newman",
    "Mission Terrace North":                       "Ortega Terrace",
    "Moriarty Foundry High":                       "Windmill Ridge",
    "Mother Lode":                                 "Siskiyou Valley",
    "Nadia Chernov":                               "Calvin Coolidge",
    "Nadia Chernov North":                         "Roosevelt",
    "Nadia Sidorov":                               "Sally Ride",
    "Naomi Ellison":                               
    "Naomi Langston North":                        "Pointe des Brumes",
    "Naomi Moss":                                  "Meyerland",
    "Naomi Price":                                 "Crown Paper",
    "Naomi Ward":                                  "Golden State Packing",
    "Nathaniel Cross":                             "Veles Harbor",
    "Nathaniel Cross North":                       
    "Nathaniel Gaines":                            "St. Catherine Academy",
    "Nathaniel Ward":                              "Juniper Agricultural",
    "Nerea Mendizabal":                            "Sparrowhawk",
    "Nerea Urrutia":                               "Blue Valley",
    "New Leiden Classical Academy":                "Vermeer",
    "Newark River North":                          "River North",
    "Nicolás Cordero":                             "Ruth Bader Ginsburg",
    "Nicolás Ordoñez":                             "Rockridge",
    "Nicolás Quiñones":                            "Stonehaven",
    "Nicolás Salcedo":                             "Siskiyou Electric",
    "Nicolás Treviño":                             
    "Nicolás Villalba":                            "Temescal",
    "Nikolai Markov":                              "Christian Brothers",
    "Nikolai Markov North":                        "Marigny",
    "Nikolai Orlov":                               "Mater Dei",
    "North Fork":                                  "Dry Fork",
    "Northrup I-50 Tech":                          "Northrup Tech",
    "Northrup I-50 Technical":                     "Northrup Tech",
    "Northside Christian North":                   "Toussaint",
    "Oksana Petrov":                               "Oak Forest",
    "Oksana Romanov":                              "Archbishop Gregory",
    "Olive Reach North":                           "Buckeye Ridge",
    "Opal Avery":                                  "Gerald Ford",
    "Opal Avery North":                            "George H. W. Bush",
    "Opal Stokes":                                 "Dry Creek Cooperative",
    "Opal Tillman":                                "Granite Water & Power",
    "Orchard Gate":                                "Bellefontaine",
    "Orchard Gate North":                          "Bois Neuf",
    "Orchard Hill":                                "Bishop Turner",
    "Orellana":                                    "Orellana Central",
    "Orellana Canal View":                         "Canal View",
    "Orellana Commerce":                           "Malpais",
    "Orellana Foundry High":                       "Grizzly Gulch",
    "Orellana School of Commerce":                 "Malpais",
    "Orellana Treasure Valley":                    "Treasure Valley",
    "Oskar Bellini":                               "Notre Dame",
    "Oskar Weiss":                                 "Waldo",
    "Pacific Friends School":                      "Pacific Friends",
    "Pacific Fruit Exchange":                      "Asteroid City",
    "Paddock Institute":                           "Paddock Tech",
    "Pauli Booker":                                "Nightfall",
    "Pavel Kovalenko":                             "Coles Creek",
    "Perryville Civic Leadership Academy":         "Perry Green",
    "Petersburg High":                             "Clara Brown",
    "Petra Bianchi":                               "Perryville",
    "Petra Jansen":                                "Southern Pacific Tech",
    "Petra Weiss North":                           "Las Colinas",
    "Pinecrest School":                            "Pinecrest",
    "Pioneer Electric":                            "Bolton",
    "Plainfield Science":                          "Plainfield",
    "Port Meridian Polytechnic":                   "Port Meridian North",
    "Port Veles":                                  "Veles Central",
    "Port Veles Agricultural Sciences Academy":    "Biden",
    "Port Veles Civic Academy":                    "Henson Prep",
    "Port Veles Civic Leadership Academy":         "Severn",
    "Port Veles East":                             "Clinton",
    "Port Veles Foundry High":                     "Seawall",
    "Port Veles International Academy":            
    "Port Veles Maritime Academy":                 "Veles Vo-Tech",
    "Portola":                                     "Homeland",
    "Prairie Union":                               "Deaconsburg",
    "Providence Academy North":                    "Wyalusing Providence",
    "Providence Academy Valley":                   
    "Puerto Gallego School of Science and Industry": "Gallego Bay",
    "Puerto Gallego Science":                      "Gallego Bay",
    "Puerto de los Reyes Commerce":                "Reyes Landing",
    "Puerto de los Reyes School of Commerce":      "Reyes Landing",
    "Rafael Escobedo":                             "Bolton",
    "Ralph Booker":                                "Obama",
    "Ralph Booker North":                          "Christchurch Episcopal",
    "Ransom City Union":                           "Ransom Pass",
    "Ransom Spur":                                 "Río Seco",
    "Redwood Coast":                               "Bienville",
    "Renata Adler":                                "Bracken",
    "Renata Dahl":                                 "Camas",
    "Rentie Grove":                                "Jamaica",
    "Rimrock Valley":                              "New Ballard",
    "Rita Moreno North":                           "Gentilly",
    "Rosa Castañeda":                              "Tippecanoe",
    "Rosa Salcedo":                                "Quarry Workers",
    "Roscoe Bennett North":                        "Narragansett",
    "Rostova Junction Technical Arts Academy":     "Railyard",
    "Ruby Mercer":                                 "Pendleton Heights",
    "Ruby Stokes":                                 "Klamath Exchange",
    "Ruby Stokes North":                           "Forks Harbor",
    "Rumsfeld Hill School":                        "Rumsfeld Hill",
    "Rye Academy of Arts and Letters":             "Barley Point",
    "Sacred Heart Cathedral":                      "Sacred Heart",
    "Sadie Freeman":                               "High Desert Cooperative",
    "Sage Lake":                                   "Sage Village",
    "Sage Meadows":                                "Galactica Plains",
    "Sage Point":                                  "California Canyons",
    "Salvador Figueroa":                           "Vesper",
    "Salvador Montalvo North":                     "Stone Ridge",
    "San Borondón Civic Academy":                  "Rumsfeld Hill",
    "San Borondón Country Day":                    "Hazel Country Day",
    "San Borondón Country Day School":             "Hazel Country Day",
    "San Borondón East":                           "Borondón Mesa",
    "San Borondón Environmental Sciences Academy": "Sotavento",
    "San Cordero":                                 "San Cordero Central",
    "San Cordero Commerce":                        "Mesa Verde",
    "San Cordero East":                            "Cordero Junction",
    "San Cordero Maritime Academy":                "Mission Butte",
    "San Cordero School of Commerce":              "Mesa Verde",
    "San Dámaso Harbor Gate":                      "Jesse Jackson",
    "San Fernando":                                "Trout Lake",
    "San Telmo Agricultural Sciences Academy":     "Orchard Union",
    "Santa Laura North":                           "Janeaway",
    "Santa Michaela Harbor Gate":                  "Tidegate",
    "Seafarer High":                               "Seafarer",
    "Selbyville Manufacturing and Technology Academy": "Selby Tech",
    "Seminary High School":                        
    "Sergei Belov":                                "Malcolm X Shabazz",
    "Sergei Petrenko":                             "Willowbrook",
    "Serrano Applied Sciences Institute":          "Arroyo Seco",
    "Serrano Depot High":                          "Cholla Flats",
    "Silton Union":                                "Silton Ridge",
    "Silvale":                                     "Fort Wren",
    "Singleton HS":                                "Singleton",
    "Sluice Crossing":                             "Crossing",
    "Sofia Romanov":                               "Chesapeake",
    "Sofia Romanov North":                         "Cheney",
    "Sofía Aranda":                                "Montclair",
    "Sofía Cordero":                               "John Quincy Adams",
    "Soren Ekström":                               "St. Sergius",
    "St. Basil":                                   "St. Ignatius",
    "St. Basil Academy":                           
    "St. Basil School":                            "St. Ignatius",
    "St. Brigid Preparatory":                      "Kingston",
    "St. Brigid School":                           "St. Brigid",
    "St. Casimir High School":                     
    "St. Casimir High School North":               "Casimir Creek",
    "St. Casimir Preparatory":                     
    "St. Elias":                                   "Tidewater Catholic",
    "St. Elias School":                            "Tidewater Catholic",
    "St. Francis Xavier College Prep":             
    "St. Francis Xavier Preparatory":              "Clarendon",
    "St. Genevieve High School":                   
    "St. Helena Academy":                          "Helena Academy",
    "St. Helena College Prep":                     "Swiss Hills Prep",
    "St. Helena School":                           
    "St. Michael Academy North":                   "Green Valley",
    "St. Nicholas College Prep":                   "Natchez Prep",
    "St. Perpetua Preparatory":                    "St. Josephine Bakhita",
    "St. Sebastian Prep North":                    "Sherwood Bench",
    "St. Sophia Preparatory":                      "Marshfield Prep",
    "St. Sophia School":                           
    "St. Teresa High School":                      "St. Teresa",
    "St. Vincent School":                          "St. Vincent",
    "Standale":                                    "Lieksa",
    "Starlake Canal View":                         "Canal Lock",
    "Starlight School of Science and Industry":    "Observatory",
    "Starlight Science":                           "Observatory",
    "Steelbridge":                                 "Forge",
    "Stone Meadows":                               "Raahe",
    "Stone Springs":                               "Simmons",
    "Summervale Heights":                          "Aspen Hollow",
    "Summervale Northwest":                        "Star Hollow",
    "Svenja Adler":                                "East Range Agricultural",
    "Svenja Bianchi":                              "Tamarack",
    "Svenja Ekström":                              "Memorial",
    "Sycamore Flat":                               "La Savane",
    "Tailing Crossing-Ewart Bar Union":            "Fountain Park",
    "Tamarack Springs":                            "Mineral Springs",
    "Tatiana Chernov North":                       "Bahía Vista",
    "Tatiana Moroz North":                         "Ironwood Flats",
    "Telfair":                                     "Pacersburg",
    "Telfair Country Day School":                  "Telfair Country Day",
    "Teresa Escobedo":                             "Canyon",
    "Thelma Avery":                                "Readbury",
    "Thelma Moss":                                 "Roscoe Village",
    "Thelma Moss North":                           "Serenity Valley",
    "Thelma Stokes":                               "Iron Gate Works",
    "Thomas Ekström":                              "Lago Vista",
    "Thomas Halvorsen":                            "Hollywood",
    "Thomas Jansen":                               "Lone Pine Mutual",
    "Thomas Jansen North":                         "Esperanza Basin",
    "Thomas Moreau":                               
    "Thornford":                                   "Thorn Summit",
    "Thurgood Marshall North":                     "Carrollton",
    "Tidewater":                                   "Tamarack Harbor",
    "Timber Crest North":                          "Crestline",
    "Timberline North":                            "Allegheny",
    "Tindall Heights":                             "Montpelier",
    "Tomás Mendoza":                               "Fairgrounds",
    "Treasure Valley North":                       "Petoskey",
    "Trout Point":                                 "North Simmons",
    "Tule":                                        "New Bergen",
    "Tule Flat Lutheran":                          
    "Valderra Aviation and Engineering Academy":   "Coyote Bend",
    "Valderra Technical Arts Academy":             "Dwight Eisenhower",
    "Valley Forge North":                          "Forge Hollow",
    "Vasquez":                                     "Fruitvale",
    "Vasquez North":                               "Fontainebleau",
    "Vernal Falls":                                "Tippah",
    "Vernon Moss":                                 "Pointe Coupee Catholic",
    "Vernon Moss North":                           "Harmony",
    "Vesper Polytechnic Institute":                "Funtsville",
    "Vessey Junction-Tailingford Union":           "Tailingford Union",
    "Viktor Antonov":                              "Archbishop Valois",
    "Viktor Antonov North":                        "Bois Rouge",
    "Viktor Gromov":                               "Armour Fields",
    "Viktor Kareva":                               "Cedar Point",
    "Walnut Yard":                                 "South Simmons",
    "Walter Hart":                                 "Kittery",
    "Walter Hart North":                           "Wicomico",
    "Walter Langston":                             "Maxwell Park",
    "Walter-Kenny School":                         "Walter-Kenny",
    "Washington":                                  "George Washington",
    "Welsh Plains Northwest":                      "Grayston",
    "Wickbrook":                                   "Salmon Bay",
    "Winifred Booker":                             "Albany Park",
    "Winifred Booker North":                       "Carden Pass",
    "Winifred Browne":                             "Rogers Park",
    "Winifred Davenport":                          "Lost River",
    "Winifred Ellison":                            "Kingwood",
    "Winifred Stokes":                             "Mesa Cooperative",
    "Wolf Gap":                                    "Corey Canyon",
    "Wolf Gap International School":               "Wolf Gap International",
    "Woodrow Wilson":                              "Sojourner Truth",
    "Woodrow Wilson North":                        "Hackensack",
    "Xabier Arregui":                              "Sinkford",
    "Xavier Robles":                               "Elk River Power",
    "Yelena Belov":                                "Pennsauke",
    "Yelena Sokolov":                              "Bowerstock",
    "Yuri Chernov":                                "Sunset Hills",
    "Zoya Orlov":                                  "Sacred Heart",
    "Zubieta Manufacturing and Technology Academy": "Sluice Gate",
    "Zubieta River Plain":                         "River Plain",
}

RENAMES = {
    # ‼️ A DEAD KEY IS NOT HARMLESS — it is the fuel for the next mis-fire. Sixteen
    # entries were removed here (2026-08): each keyed a prep-network name that repo
    # has since renamed away, so the entry could never fire — until some OTHER school
    # happened to be called that string, at which point the rename reached the wrong
    # school. That is exactly what "Wheatley" did. `RENAMES` is a permanent record of
    # renames that are STILL REACHABLE; an entry whose key matches nothing in
    # prep-network AND nothing in the association is debris, and `build()` now refuses
    # to let a key collide with a live school's own identity at all.

    # Owner picks, 2026-08 — both enter the association via EXTRA_SPONSORS:
    "Plainfield Science": "Plainfield",              # 6A Plainfield
    "Abraham Lincoln": "Lincoln",                    # 9A Belyakov — the state's Lincoln

    # NB (2026-08): a "Trout Lake": "San Fernando" entry lived here for one
    # commit during the 2052 expansion and was removed the same session — the
    # owner resolved the collision with the real Trout Lake, WA by RELOCATING
    # the invented program into the affiliate seat instead (one school, one
    # archive — `scripts/jhsaa_2052_expansion.py`). No season was ever archived
    # under "San Fernando". Do not re-add the entry: it would be a dead key
    # aimed at a live school's own name.

    "Belyakov Academy of Music and Media": "Walter-Kenny School",
    "Belyakov Environmental Sciences Academy": "Friendship City",
    "Belyakov Polytechnic Institute": "Morne Caribou Polytechnic",
    "Belyakov School of Design and Engineering": "Grande-Savane Arts",
    "Belyakov School of Science and Industry": "Kongisburg",
    "Belmonte Agricultural Sciences Academy": "Pelican Town",
    "Belmonte Applied Sciences Institute": "Yazoo",
    "Belmonte Civic Leadership Academy": "Keeler",
    "Belmonte Health Sciences Academy": "Dusty Spur",
    "Belmonte Classical Academy": "James Madison",
    # 2026-08 owner rename (was "Woodrow Wilson" — rewrite in place, never chain;
    # asked for as "Sojourner Truth HS", committed without the suffix per the
    # no-institutional-suffix rule, the "Amelia High School" -> "Amelia" precedent):
    "Belmonte Technical Arts Academy": "Sojourner Truth",
    # 2026-08 owner rename. The key is the school's own (never-renamed) identity —
    # the ordinary path; `source` gets stamped "Manzanita Ridge" so the roster
    # identity and every pid survive the display change. No collision: the only
    # neighbour is 1A Manzanita Junction (Antler County), a different school in a
    # different class whose name is its own town.
    "Manzanita Ridge": "Manzanita",
    # 2026-08 owner suffix sweep: no display name carries "HS"/"High" as an
    # institutional marker (the no-suffix rule; leading-word "High …" names —
    # High Bar, High Desert Christian, High Prairie — are identity, not suffix,
    # and stay). The first two rewrite `jhsaa_heritage_valley_renames.py`'s
    # targets in place; keys are the roster identities as always.
    "Langston Central": "Singleton",
    "Petersburg High": "Clara Brown",
    "Barlowe County High": "Barlowe County",
    "Lodestone County High": "Lodestone County",
    "Antler County High": "Antler County",        # sunset 2052; page/archive rename
    # 2026-08 owner rename, resolved twice in-session: "Abbey Vale Orchard
    # Hill" was first asked for as "just Orchard Hill", which collided with the
    # live 9A Orchard Hill (Valderra) — a display name is the archive identity.
    # The owner's final call: the 2A becomes "Booker T Washington" (owner's
    # punctuation — no period after the T) and the 9A KEEPS its original name,
    # so nothing is reissued and no history merges. Transient targets "Bishop
    # Turner" and a brief 9A "Booker T Washington" lived only inside this
    # session; no season was ever archived under either. The 9A renames to
    # "Bishop Turner" (the owner's earlier pick, confirmed) in the same batch,
    # so NO school carries "Orchard Hill" — the archived name resolves through
    # FORMER_NAMES to the 9A alone (its identity; the alias generator prefers
    # an identity claim over another chain's transient target).
    "Abbey Vale Orchard Hill": "Booker T Washington",
    # 2026-08 owner rename — the school's own never-renamed identity is the key:
    "Sluice Crossing": "Crossing",
    "Orchard Hill": "Bishop Turner",
    "St. Basil School": "St. Ignatius",
    "Caswell Depot High": "Cherry Hill North",
    "Caswell I-50 Technical": "Cherry Hill South",
    "Caswell School of Science and Industry": "Chester A. Arthur",
    "Caswell University Prep": "Palisade Prep",
    "Aldecoa Academy of Arts and Letters": "Coyote Springs",
    "Aldecoa Applied Sciences Institute": "Deadwood",
    "Aldecoa Depot High": "Ulysses Grant",
    "Echevarria Foundry High": "Bitterroot",
    "Echevarria I-50 Technical": "Red Bluff",
    "Orellana Foundry High": "Grizzly Gulch",
    "Orellana School of Commerce": "Malpais",
    "Port Veles Agricultural Sciences Academy": "Biden",
    "Port Veles Civic Leadership Academy": "Severn",
    "Nadia Sidorov": "Sally Ride",
    "Port Meridian Polytechnic": "Port Meridian North",
    "San Borondón Environmental Sciences Academy": "Sotavento",
    "Puerto de los Reyes School of Commerce": "Reyes Landing",
    "Llerena School of Science and Industry": "Crow Basin",
    "Serrano Applied Sciences Institute": "Arroyo Seco",
    "Serrano Depot High": "Cholla Flats",
    "Halbrook Technical": "Basin Gate",
    "Valderra Aviation and Engineering Academy": "Coyote Bend",
    "Valderra Technical Arts Academy": "Dwight Eisenhower",
    "Mercer City Technical Arts Academy": "Twin Mills",
    "Moriarty Foundry High": "Windmill Ridge",
    "Harriman Maritime Academy": "John F. Kennedy",
    "San Cordero Maritime Academy": "Mission Butte",
    "San Cordero School of Commerce": "Mesa Verde",
    "Fort Valois School of Design and Engineering": "Valois Bluffs",
    "Gagarin School of Public Service": "Star City",
    "Fellows Mill International School": "Mill Bar",
    "Rye Academy of Arts and Letters": "Barley Point",
    "Ansotegui Siding Commonwealth": "Pinebluffs",
    # Two St. Genevieves — a 1A in Benchton natively bare, a 6A whose suffix
    # strip collides with it. The bigger school takes the city, PRE + PLACE
    # ("Jesuit Sacramento"); the 1A keeps the name it always had.
    "St. Genevieve High School": 
    # The split campus of the Ashbury science magnet (owner rename 2027-08):
    # a town would not carry two science high schools, so the North campus is
    # a new identity outright — The Evans Larsen Day School, which the
    # association's no-suffix rule prints "Evans Larsen Day". Blue blood
    # (archetypes.json); Steeplejacks (MASCOTS below).
    "Jefferson School of Science and Technology North": "Evans Larsen Day",
    # Renamed off the region that no longer exists, and moved out of Gagarin
    # (four programs already) to Copper Prairie — see RELOCATIONS.
    "Mother Lode": "Siskiyou Valley",
    # ‼️ NAMED FOR REAL FIGURES WITH LITTLE OR NO SCHOOL NAMING BEHIND THEM
    # (owner rule 2027-08). Jefferson had none of these and a great many schools
    # named for INVENTED people, several sharing a surname across the state —
    # seven Bookers, eight Crosses — so the invented duplicates are what gets
    # replaced. Names still on the owner's list for future renames: Lyndon B.
    # Johnson (taken below), William Howard Taft, Earl Warren, Sonia Sotomayor,
    # Ketanji Brown Jackson, Sandra Day O'Connor, Ruth Bader Ginsburg, John
    # Quincy Adams, John F. Kennedy, Western Sky.
    #
    # ⚠️ If a TOWN ends up with the same school name twice, the second is
    # qualified by its town — "Jefferson Heights Polk" — never by a suffix.
    # Both of these are the only school of their name in the state, so neither
    # needs it; `build` refuses to emit a collision either way.
    "Katherine Booker": "James K. Polk",
    "Amos Cross": "Lyndon B. Johnson",
    "Aldermont": "Cape Angeles",   # the town renamed under it
    # each of these is the school named for its town, moving with it
    "Milldale Union": "Sotkamo Union",
    "Millview": "Kuusamo",
    "Kelview Union": "Iisalmi Union",
    "Standale": "Lieksa",
    "Elmfield": "Nurmes",
    "Stone Meadows": "Raahe",
    "Silvale": "Fort Wren",
    "Ewartville": "Fort Tabor",
    "Ewart City": "Cook City",
    "Tailing Crossing-Ewart Bar Union": "Fountain Park",
    "Marshdale": "Fort Lassiter",
    "Goodman": "Fort Bardsley",
    "Fort Salish": "Fort Weller",
    "Fort Salish Independent School": "Weller Independent",
    # ‼️ ONE SCHOOL PER NAME, and a person's name never takes a directional
    # qualifier — there is no "Sandra Day O'Connor North". A split campus of a
    # renamed school takes a PLACE name off its own town instead.
    #
    # The generator had produced whole families of schools named for invented
    # people — eight Crosses, seven Bookers, six Corderos, five Aramburus, all
    # unrelated — which the owner found immersion-breaking. Each surname keeps
    # ONE school (Winifred Booker, Garazi Aramburu, Carmen Cordero, plus the
    # place-named Benton Cross / San Cordero and the parish Holy Cross); the
    # rest take either a name off the owner's list or, where the list is spent,
    # their own town. Naming a school for its town is the ordinary case
    # everywhere and adds no new invented person.
    "Amaia Aramburu": "Ketanji Brown Jackson",
    "Amaia Aramburu North": 
    # each of these is the school named for its town, moving with it
    "Ander Aramburu": "Western Sky",
    "Andrew Jackson North": "Chaparral",
    "Clara Cross": "Red Mesa",
    "Evelyn Booker": "William Howard Taft",
    "Geraldine Cross": "Port Veles Episcopal",
    "Iker Aramburu": "Sandra Day O'Connor",
    "Iker Aramburu North": "Highland Park",
    "Imani Cross": "Apalachicola",
    "Isaiah Booker": "Earl Warren",
    "John F. Kennedy North": "Box Canyon",
    # ⚠️ Was plain "Echevarria" and had to move: prep-network now carries a school
    # of its own by that bare name (Dragons, 2,473, same city), so the two emitted
    # one display name and `build` refused — correctly, because a display name IS
    # the archive identity. Neither side is an owner edict, so the collision is
    # settled inside the existing family: North and South are already taken by
    # Foundry High and I-50 Technical, Central was free. The school's roster
    # identity is unaffected (pids key on `source`, still "Leire Aramburu").
    "Leire Aramburu": "Furnace Creek",
    "Lorna Booker": "Blue Grama",
    "Manuel Cordero": "Sonia Sotomayor",
    "Marian Cross": "Quail Hollow",
    "Nathaniel Cross": "Veles Harbor",
    "Nathaniel Cross North": 
    "Nicolás Cordero": "Ruth Bader Ginsburg",
    "Pauli Booker": "Nightfall",
    "Ralph Booker": "Obama",
    "Ralph Booker North": "Christchurch Episcopal",
    "Sofía Cordero": "John Quincy Adams",

    # ‼️ REAL PEOPLE, NOT INVENTED ONES (owner rule 2027-08: "the fictional
    # people are kind of boring me... this is how real schools get named
    # after all"). PORT VELES names its schools for PRESIDENTS. Elsewhere
    # the pools, in the owner's order: vice presidents, secretaries of
    # state, secretaries of war, postmasters general, SUFFRAGISTS and
    # PIONEERS OF CONSEQUENCE. Where a real person is not wanted the
    # town's own idiom serves ("Veles Area" and the harbour features).
    # ⚠️ Vet the pool: the 19th-century war and state departments are
    # thick with Confederates and slaveholders, and the owner has already
    # vetoed a name on exactly those grounds. A SINGLE invented person is
    # fine and always was — Amelia Freeman stays; it was the FAMILIES of
    # unrelated invented people that broke immersion, and "<person> North"
    # is never a school name.
    "Amelia Freeman North": "Casco",
    "Anneliese Halvorsen": "George Washington",
    "Baptist HS": "Baptist",
    "Belmonte International School": "Belmonte Collegiate",
    "Calderwood School": "Calderwood",
    "Carroway School of Public Service": "Liberty Hill",
    "Dahlberg School of Science and Industry": "Hartford City",
    "Fort Valois School of Public Service": "Sagebrush",
    "Galina Markov": "James Monroe",
    "Harbor Gate North": "Martin Van Buren",
    "Harrow School of Design and Engineering": "New Boston",
    "Henrik Keller": "William Henry Harrison",
    "Housatonic HS": "Housatonic",
    "Igor Chernov": "Zachary Taylor",
    "Igor Chernov North": "Fillmore",
    "Jefferson School of Science and Technology": "Jefferson Science",
    "Katherine Williams": "Franklin Pierce",
    "Marcus Langston": "Rutherford Hayes",
    "Marcus Langston North": "Garfield",
    "Marina Moroz": "Cleveland",
    "Marina Moroz North": "Benjamin Harrison",
    "Metropolitan Country Day School": "Metropolitan Country Day",
    "Nadia Chernov": "Calvin Coolidge",
    "Nadia Chernov North": "Roosevelt",
    "Opal Avery": "Gerald Ford",
    "Opal Avery North": "George H. W. Bush",
    "Pacific Friends School": "Pacific Friends",
    "Pinecrest School": "Pinecrest",
    "Port Veles East": "Clinton",
    "Puerto Gallego School of Science and Industry": "Gallego Bay",
    "Roscoe Bennett North": "Narragansett",
    "San Borondón Country Day School": "Hazel Country Day",
    "Sofia Romanov": "Chesapeake",
    "Sofia Romanov North": "Cheney",
    "St. Brigid School": "St. Brigid",
    "St. Casimir High School": 
    "St. Elias School": "Tidewater Catholic",
    "St. Helena School": 
    "St. Sophia School": 
    "St. Teresa High School": "St. Teresa",
    "St. Vincent School": "St. Vincent",
    "Starlight School of Science and Industry": "Observatory",
    "Telfair Country Day School": "Telfair Country Day",
    "Thelma Avery": "Readbury",
    "Walter Hart": "Kittery",
    "Walter Hart North": "Wicomico",
    "Wolf Gap International School": "Wolf Gap International",
    "Alder Landing Beacon Hill": "Bay Oregon",
    "Aspen Harbor": "East Simmons",
    "Cedarport": "North San Francisco",
    "Elk Prairie": "Carolina Island",
    "Granite Bar": "New Penzance Island",
    "Millport": "Vonjo City",
    "Sage Meadows": "Galactica Plains",
    "Sage Point": "California Canyons",
    
    "Stone Springs": "Simmons",
    "Trout Point": "North Simmons",
    "Walnut Yard": "South Simmons",
    "Alderfield": "Linden",
    "Sage Lake": "Sage Village",
    "Ashfield": "California Beach",
    "Garrity": "Texas Beach",
    "Graymont": "Georgia Mills",
    "Marsh Depot": "Jersey City",
    "Rentie Grove": "Jamaica",
    "Ashwood": "Gruesome Ridge",
    "Copper Crossing": "Copper Gap",
    "Dahlberg": "Dahlberg Summit",
    "Doyle Junction": "Doyle Pass",
    "Elmburg": "Mt Jacqueline",
    "Gold Junction": "Seamus Town",
    "Harmon": "Annes Summit",
    "Hetfield": "Brynildson Hill",
    "Huckle Lake": "Mount Dylan Lake",
    "Thornford": "Thorn Summit",
    "Wolf Gap": "Corey Canyon",
    "Brackwood Union": "Brackwood Pass",
    "Ransom City Union": "Ransom Pass",
    "Silton Union": "Silton Ridge",
    "Wickbrook": "Salmon Bay",

    # ‼️ THE PRIVATE-SCHOOL LAYER (owner rule 2027-08). Jefferson had 297 schools
    # named after INVENTED PEOPLE and a private layer too thin to read as real. The
    # fix is deliberately NOT a mass rename — "replace some of the more obvious
    # generated-person schools with about 15-25 institutional private-school names,
    # not hundreds". These 25 are it. Every target is a verifiably fictional
    # person-named PUBLIC school; each becomes private (`PRIVATE_SCHOOLS` below).
    #
    # ‼️ VARIED INSTITUTIONAL GRAMMAR IS THE WHOLE POINT. Not every Catholic school
    # is "X Catholic": the register lives in the mix — Academy · Cathedral · Prep ·
    # College Prep · Catholic · Christian · bare. A layer built from one template
    # reads as a template.
    #
    # ‼️ AND STILL NO SUFFIX. "High School"/"School" are stripped by `_SUFFIX_RE`
    # exactly as everywhere else (owner, asked directly: "you say Archbishop Gregory
    # I know what you're talking about … you don't have to go to school after it").
    # So the names are written BARE here — Archbishop Gregory, Sinkford, Grace
    # Christian — and the grammar that survives is the grammar that carries meaning:
    # Academy, Prep, Cathedral and Catholic are not suffixes and were never stripped.
    # Do NOT add an exemption to `_SUFFIX_RE` for these; there is nothing to exempt.
    #
    # ‼️ PRELATE NAMES COME FROM JEFFERSON SURNAMES (owner rule) — Valera, Valois,
    # Mercier and Echevarria are all already in the state's own name pool, which is
    # what makes "Cardinal Echevarria" sound like a real Catholic high school
    # instead of an import. Never coin a fresh surname for one.
    #
    # ‼️ NEVER RENAME A REAL PERSON'S SCHOOL. The person-named pool mixes invented
    # names with genuine ones — Theodore Roosevelt, Bayard Rustin, Octavia Butler,
    # James Baldwin, Gwendolyn Brooks, Thurgood Marshall, Mae Jemison, Barack Obama,
    # John Lewis, and every president in there. The presidents and justices are in
    # OWNER_EDICTS; the rest are not, so "looks like a person" is not the test.
    # Verify fictional before adding a target here.
    "Nikolai Orlov": "Mater Dei",                    # 9A Cañada Grande
    "Astrid Ricci": "Jesuit",                        # 9A Mercer City
    "Oskar Bellini": "Notre Dame",                   # 9A Boyerstown
    "Oksana Romanov": "Archbishop Gregory",          # 8A — owner's mandatory name
    "Zoya Orlov": "Sacred Heart",          # 8A Santa Michaela — 2026-08
                                           # suffix-ish trim, "Cathedral" dropped
    "Edith Hart": "Bellarmine Prep",                 # 8A — Prep, never Preparatory
    "Nicolás Treviño":              # 7A — Jefferson surname
    "Harlan Tillman": "Xavier College Prep",         # 7A Mercer City
    "Amos Moss": "St. Francis Catholic",             # 7A Ashbury
    "Nikolai Markov": "Christian Brothers",          # 7A Sebastian Cape
    "Vernon Moss": "Pointe Coupee Catholic",               # 6A — Jefferson surname
    "Naomi Ellison":          # 6A Gold Valley
    "Jon Garmendia": "Pope Leo XIV",                 # 6A Halbrook Basin
    "Viktor Antonov": "Archbishop Valois",           # 5A — Jefferson surname
    "Marcus Mercer":            # 5A Vespertine
    "Nathaniel Gaines": "St. Catherine Academy",     # 5A Ashbury
    "Andrés Valera": "Basalt Electric",               # 4A — Jefferson surname
    "César Mendoza": "De La Salle",                  # 4A Bellacosta
    "Irina Kovalenko": # 4A Selquah
    # ‼️ SINKFORD (owner). A Unitarian Universalist coed boarding/day school founded
    # by UU donors in 1974 and named for William G. Sinkford — UUA president
    # 2001-09, the first Black leader of a predominantly white American
    # denomination, later senior minister at First Unitarian Portland, which is what
    # makes him land in a fictional Pacific-Northwest state. The name reads like an
    # old New England boarding school even though the namesake is contemporary.
    # Small, unusually strong arts and outdoor programs, kids from across the West,
    # and for no obvious reason a very serious tennis program (hence `blue_blood` in
    # archetypes.json). It exists to stop the private layer being Catholic prep and
    # evangelical academy and nothing else.
    "Xabier Arregui": "Sinkford",                    # 3A Navrang, Juniper Highlands
    "Miren Garmendia": "Cardinal Newman",            # 3A Homecroft
    "Janice Bennett": "Calvary Christian",           # 3A Alderwold
    # ‼️ THREE CALVARY CHAPELS IN THREE TOWNS (owner, 2026-08): "that's confusing
    # for a private school". A public school named for its town repeats happily —
    # there is a Lincoln in every state and nobody is confused — because the town
    # IS the disambiguator. A private school's name is its identity, so the same
    # one in three places reads as one institution with three campuses, which is
    # what the owner saw. The three replacements are owner-dictated and deliberately
    # share no grammar with each other: an independent day school, a hyphenated
    # endowed one, a day school. Calvary Chapel Kernwood (3A, sponsors no tennis)
    # is untouched and is now the only one, so the name still exists in the state.
    "Calvary Chapel Ditch Fork": "Cassius",                 # 1A Goldbank
    # ‼️ A CAMPUS DIRECTION IS NOT AN IDENTITY (owner, 2026-08). These read as an
    # annex of the school they sit beside — Northside Christian NORTH next to
    # Northside Christian, Welsh Plains NORTHWEST next to Welsh Plains — so each
    # gets a name of its own. All owner-dictated.
    "Northside Christian North": "Toussaint",               # 4A Halbrook
    # The four towns renamed for the El Paso / Rio pass (CITY_RENAMES) take their
    # town-named schools with them.
    "Gulch Bend": "West El Paso",                           # 6A Southern Jefferson
    "Ransom Spur": "Río Seco",                              # 3A Sebastian Cape
    "Basalt Fork": "Río Salado",                            # 1A Gold Valley
    "Fig Gap": "Río Verde",                                 # 2A Yarrowmere

    # ‼️ THE 2032 TERRAIN PASS (owner spec, 111 families). Two public schools in one
    # city whose names differed only by a word carrying no identity — Altamonte
    # beside Altamonte Civic, Archbishop Doyle Prep beside Archbishop Doyle Prep
    # North — do not tell a reader them apart, and a city+compass name (Belmonte
    # North) does. So the second school takes the terrain or the settlement it
    # actually stands on. Keyed on the SOURCE name; where a school already had a
    # RENAMES entry its target was rewritten in place, never chained.
    "Annie Springs Crater View": "Crater View",                # 3A Annie Springs
    "Archbishop Doyle Prep North": "Doyle Ridge",              # 6A Halbrook
    "Arrieta Treasure Valley": "Canyonlands",                  # 7A Arrieta
    "Ashbury East": "Alameda",                                 # 7A Ashbury
    "Ashbury West": "Laurel Park",                             # 9A Ashbury
    "Aurelia Classical Academy": "Goodman School",             # 6A Aurelia
    "Barclay Golden Gate": "Gate City",                        # 5A Barclay
    "Bidwell City": "Alfalfa City",                            # 1A Bidwell City
    "Bidwell County": "County Line",                           # 1A Huckle Glen
    "Blackpine North": "Ravenwood",                            # 4A Blackpine
    "Boyerstown North": "Alder Crossing",                      # 7A Boyerstown
    "Breakwater": "Tide Point",                                # 5A Fort Meriwether
    "Breakwater North": "Lighthouse",                          # 7A Fort Meriwether
    "Canal View": "Springfield",                               # 6A Orellana
    "Canal View North": "Lateral Seven",                       # 5A Orellana
    "Carden City West Bench": "Buckhorn",                      # 4A Carden City
    "Cherry Hill East": "Cherry Hill East",                            # 7A Caswell
    "Copper Lake East": "Bridgewater",                         # 6A Copper Lake
    "Copper Lake West": "Azurite",                             # 7A Copper Lake
    "Costa Verde North": "Verde Highlands",                    # 5A Bahía Leal
    "Emigrant Trail": "Trailhead",                             # 5A Rostova Junction
    "Ferris Union": "Union Prairie",                           # 1A Ferris
    "Fort Meriwether Breakwater": "Breakwater",                # 8A Fort Meriwether
    "Garfield Park": "Reservoir Park",                         # 5A Drayfield
    "Greaves Junction": "Juniper Crossing",                    # 2A Greaves Junction
    "Halbrook Union": "Deaconsburg",                           # 7A Halbrook
    "Harriman South": "Hidden Draw",                           # 8A Harriman
    "Hawk Lake Eastgate": "Oakhaven",                          # 6A Hawk Lake
    "Hawk Lake Southeast": "Pine Barrens",                     # 5A Hawk Lake
    "Homestead North": "Garden Plain",                         # 7A Harriman
    "Kelford Northwest": "Horseshoe Bend",                     # 3A Kelford
    "Kilbride Switch South": "Switchback",                     # 3A Kilbride Switch
    "Lake Esperanza South": "Malheur Flat",                    # 7A Lake Esperanza
    "Llerena East": "Juniper Well",                            # 5A Llerena
    "Loomis City North": "Charlotte",                    # 6A Loomis City
    "Los Remolinos Mission Bay": "Estuary Bay",                # 2A Los Remolinos
    "Madrigal Maritime Academy": "Maritime",                   # 6A Madrigal
    "Madrigal West Bench": "Benchlands",                       # 5A Madrigal
    "Mission Terrace North": "Ortega Terrace",                 # 7A Norview
    "New Leiden Classical Academy": "Vermeer",                 # 3A New Leiden
    "Newark River North": "River North",                       # 3A Newark River
    "Olive Reach North": "Buckeye Ridge",                      # 4A Olive Reach
    "Orellana": "Orellana Central",                            # 8A Orellana
    "Orellana Canal View": "Canal View",                       # 9A Orellana
    "Orellana Treasure Valley": "Treasure Valley",             # 9A Orellana
    "Port Veles": "Veles Central",                             # 5A Port Veles
    "Providence Academy Valley":          # 9A Port Meridian
    "San Borondón East": "Borondón Mesa",                      # 4A San Borondón
    "San Cordero": "San Cordero Central",                      # 4A San Cordero
    "San Cordero East": "Cordero Junction",                    # 6A San Cordero
    "San Dámaso Harbor Gate": "Jesse Jackson",                 # 4A San Dámaso
    "Santa Laura North": "Janeaway",                           # 4A Santa Laura
    "Santa Michaela Harbor Gate": "Tidegate",                  # 8A Santa Michaela
    "St. Brigid Preparatory": "Kingston",                      # 6A Llerena
    "St. Francis Xavier College Prep":   # 2A Pomar
    "St. Francis Xavier Preparatory": "Clarendon",             # 4A Rostova Junction
    "St. Helena Academy": "Helena Academy",                    # 4A Montelago
    "St. Helena College Prep": "Swiss Hills Prep",             # 7A Port Veles
    "St. Michael Academy North": "Green Valley School",        # 7A Harriman
    "St. Perpetua Preparatory": "St. Josephine Bakhita",       # 1A Vessey Switch
    "Starlake Canal View": "Canal Lock",                       # 3A Starlake
    "Summervale Heights": "Aspen Hollow",                      # 6A Summervale
    "Summervale Northwest": "Star Hollow",                     # 3A Summervale
    "Tamarack Springs": "Mineral Springs",                     # 2A Tamarack Springs
    "Telfair": "Pacersburg",                              # 4A Telfair
    "Timber Crest North": "Crestline",                         # 4A Fort Carden
    "Tindall Heights": "Montpelier",                        # 5A Tindall
    "Tule Flat Lutheran":               # 1A Tule Flat
    "Valley Forge North": "Forge Hollow",                      # 3A Valderra
    "Vessey Junction-Tailingford Union": "Tailingford Union",  # 1A Tailingford
    "Zubieta River Plain": "River Plain",                      # 6A Zubieta

    # ‼️ FIVE-METRO LOCALITY REDISTRIBUTION (owner spec, 2026-08). Belmonte,
    # Port Veles, San Borondón, Belyakov and Ashbury carried 28-44 tennis
    # programs each, most of them annexes of one another. 51 stay CORE CITY
    # schools; the other 121 take the identity of a settlement inside the metro
    # (`LOCALITIES` below) — a CDP, an unincorporated place, an absorbed town —
    # which is how a city that size actually holds that many high schools. The
    # core city stays the row's `city`; the locality is a second field.
    #
    # ‼️ A LOCALITY REPEATS ACROSS METROS AND A SCHOOL NAME CANNOT. Five names
    # collided; each is qualified in the spec's own grammar (Natchez Prep,
    # Biloxi Heights, Cahaba Fork) with a word from the school's OWN previous
    # name — Allegheny Heights, Bowerstock Beach, Cahaba Butte, Petoskey Rock —
    # and Port Veles's Calvin Coolidge simply keeps its full name, since Olive
    # Reach already has a Coolidge.
    #
    # Real people keep their names and take a locality instead of a rename.
    "Timberline North": "Allegheny",                             # 4A Ashbury
    "Ashbury Heights": "Ashbury Central",                                # 9A Ashbury
    "North Fork": "Dry Fork",                                 # 8A Ashbury
    "Steelbridge": "Forge",                           # 4A Ashbury
    "Timberline": "Timberline",                          # 4A Ashbury
    "Mercy Academy": "Natchez Mercy",                            # 9A Ashbury
    "St. Sebastian Prep North": "Sherwood Bench",                # 8A Ashbury
    "Ashbury Central": "Tallulah Central",                       # 7A Ashbury
    "Providence Academy North": "Wyalusing Providence",          # 5A Ashbury
    "St. Basil Academy":              # 4A Belmonte
    "Treasure Valley": "Caney",                        # 6A Belmonte
    "Belmonte River Plain": "Chillicothe",              # 8A Belmonte
    "River Plain": "Kinnickinny",                       # 9A Belmonte
    "Belmonte Northwest": "Kokomo",                              # 6A Belmonte
    "Treasure Valley North": "Petoskey",                         # 5A Belmonte
    "Belmonte Collegiate Academy": "Rock on the Hill Christian Academy", # 5A Belmonte
    "Vernal Falls": "Tippah",                                    # 4A Belmonte
    "Buckeye Bend": "Wyalusing",                                 # 4A Belmonte
    "Orchard Gate": "Bellefontaine",                             # 7A Belyakov
    "Orchard Gate North": "Bois Neuf",                           # 6A Belyakov
    "Belyakov": "East Moscow",                                   # 8A Belyakov
    "Belyakov River Plain": "Grand Fond",                        # 5A Belyakov
    "Sycamore Flat": "La Savane",                                # 4A Belyakov
    "Belyakov River Plain North": "Lycee Valmont",               # 6A Belyakov
    "Coyote Draw": "Savane Brulee",                              # 6A Belyakov
    "José Martí": "Trois Ilets",                                 # 7A Belyakov
    "Port Veles Maritime Academy": "Veles Vo-Tech",    # 9A Port Veles
    "Port Veles International Academy": "Seminary High School",  # 3A Port Veles
    "Redwood Coast": "Bienville",                                # 9A San Borondon
    "St. Nicholas College Prep": "Natchez Prep",                 # 6A San Borondon
    "Las Palmas North": "Natchitoches",                          # 8A San Borondon
    "St. Casimir Preparatory":          # 5A San Borondon
    "St. Sophia Preparatory": "Marshfield Prep",                 # 8A San Borondon
    "Blackbird Canyon": "Tallulah Canyon",                       # 4A San Borondon
    "Las Palmas": "Tuscaloosa",                                  # 8A San Borondon
    "Welsh Plains Northwest": "Grayston",                   # 3A Paddock
    "Calvary Chapel Kilbride Switch": "Gottschalk-Herman",  # 1A Olivet
    "Calvary Chapel Olivet": "Banfield Day",                # 1A Olivet
    "Galina Moroz":         # 2A-1A — Sebastian Cape, coastal
    "Mikel Zubieta":        # 2A-1A Clear Springs
    "Thomas Moreau":                 # 2A-1A Gold Valley
    # ‼️ NO ACCENTS (owner rule 2027-08, same as the Nordic town sweep):
    # an American town or school would not carry one. These three keep their
    # ALWAYS_EXTRA source spelling (it has to match prep-network) and rename
    # only at emit.
    "Soren Ekström": "St. Sergius",
    "Svenja Ekström": "Memorial",
    "Thomas Ekström": "Lago Vista",
    "Keldale": "Espoo",
    "Tule": "New Bergen",
    "Rimrock Valley": "New Ballard",
    # ‼️ NAMED FOR THINGS THAT EXISTED BEFORE THE SCHOOL, NOT FOR MORE PEOPLE
    # (owner rule 2027-08). The invented-person families (Stokes, Belov, Tillman,
    # Echevarria and a dozen others) were replaced with old local INSTITUTIONS —
    # companies, co-ops, granges, mines, mills, rail lines, irrigation and power
    # districts, civic associations — the kind of name a school picks up from a
    # company town or a defunct utility rather than from a person. Deliberately a
    # DIFFERENT reservoir from OWNER_EDICTS' real people: a second batch of person
    # names would just rebuild the Stokes/Belov problem under new surnames. One
    # survivor was kept per original surname family; these are the rest. See
    # INSTITUTION_NAMES below for the bank this was drawn from.
    "Amaia Echevarria": "Redwood Mutual",
    "Anya Belov": "Arroyo",                # 2026-08: was "Arroyo Water District"
    "Claudette Freeman": "Alder Cooperative",
    "Eleanor Tillman": "Anchor Glass",
    "Elias Mercier": "Cascade Mutual",
    "Frances Gaines": "Empire Milling",
    "Garazi Mendizabal": "Cedar Exchange",
    "Harlan Cole": "Harlan",
    "Harold Tillman": "Copper Belt",
    "James Gaines": "Rogue Valley Packing",
    "Janice Cole": "Fallon Works",
    "Jeannette Freeman": "Round Mountain Grange",
    "Katherine Davenport": "Blue Mountain Grange",
    "Lars Mercier": "Shasta Agricultural",
    "Lillian Price": "North Coast Packing",
    "Manuel Robles": "Asteroid City",      # 2026-08: was "Pacific Fruit Exchange",
                                           # then briefly "Marshfield" (rewritten in
                                           # place — too close to Marshfield Prep)
    "Mikel Echevarria": "Fir Valley Grange",
    "Naomi Price": "Crown Paper",
    "Naomi Ward": "Golden State Packing",
    "Nathaniel Ward": "Juniper Agricultural",
    "Nerea Mendizabal": "Sparrowhawk",
    "Nicolás Salcedo": "Siskiyou Electric",
    "Opal Stokes": "Dry Creek Cooperative",
    "Opal Tillman": "Granite Water & Power",
    "Petra Jansen": "Southern Pacific Tech",
    "Rafael Escobedo": "Bolton",           # 2026-08: was "Pioneer Electric"
    "Renata Adler": "Bracken",             # 2026-08: was "Bracken Works"
    "Rosa Salcedo": "Quarry Workers",
    "Ruby Stokes": "Klamath Exchange",
    "Sadie Freeman": "High Desert Cooperative",
    "Sergei Belov": "Malcolm X Shabazz",
    "Svenja Adler": "East Range Agricultural",
    "Teresa Escobedo": "Canyon",           # 2026-08: was "Cañada Irrigation"
    "Thelma Stokes": "Iron Gate Works",
    "Thomas Jansen": "Lone Pine Mutual",
    "Winifred Davenport": "Lost River",    # 2026-08: was "Lost River Irrigation"
    "Winifred Stokes": "Mesa Cooperative",
    "Xavier Robles": "Elk River Power",
    "Yelena Belov": "Pennsauke",

    # ‼️ SCHOOLS THAT TAKE THEIR OWN PLACE NAME (owner rule 2026-08). Naming a school
    # for the town or county it sits in is the commonest real convention there is, so
    # where that name was still FREE it is the cheapest possible fix for an
    # invented-person name. Each target was checked against every one of the 857
    # names in the association and against the others in this block, so no two schools
    # claim the same place.
    #
    # A county name is used where the town's was already taken (Emigrant, Ferris,
    # San Marcos), which is also how it works in life — the county school serves the
    # towns that have not got their own.
    #
    # ‼️ The six "<Town> North" entries fix TWO faults at once: a person's name, and a
    # person's name carrying a campus direction. A PLACE can have a second campus —
    # "Lake Esperanza North" is exactly what a town's second school is called — and a
    # PERSON cannot (owner rule 2026-08: "no named person school should ever have more
    # than one campus, that's not realistic").
    #
    # ‼️ AND VERIFY IT IS A PERSON. "Olive Head" was in the first cut of this block,
    # bound for its county — and Olive Head is the TOWN the school sits in. It was
    # already named the way this block is trying to name everything else. A given
    # name plus a surname is also just how a lot of place names look.
    #
    # ‼️ VERIFY FICTIONAL BEFORE ADDING HERE. The first pass of this list had Harry
    # Truman in it, and Ulysses Grant, Ella Baker, Katherine Johnson and Rita Moreno
    # sitting one row away — every one of them tokenises exactly like a generated
    # name. A pool test cannot tell you; a person has to read the list.
    "Renata Dahl":               "Camas",                   # 4A Camas County
    "Tatiana Moroz North":       "Ironwood Flats",           # 8A Caswell
    "Harold Tillman North":      "Echevarria",              # 5A Echevarria
    "Katya Moroz":               "Emigrant",                # 7A Emigrant County
    "Carmen Valera":             "Ferris",                  # 9A Ferris County
    "Winifred Booker North":     "Carden Pass",       # 6A Fort Carden
    "Beatrice Davenport":        "Fort Halloran",           # 4A Fort Halloran
    "Katya Moroz North":         "Pinyon Ridge",           # 8A Harriman
    "Thomas Jansen North":       "Esperanza Basin",     # 5A Lake Esperanza
    "Gabriel Montoya":           "Marlow",                  # 4A Marlow County
    "Matteo Dahl":               "Bywater",               # 7A Montelago
    "Petra Bianchi":             "Perryville",              # 6A Perryville
    "Daniel Gaines North":       "Tensas",       # 7A San Borondón
    "Elena Petrov":              "Talladega",              # 9A San Marcos County
    "Irina Kovalenko North":     "Arroyo Verde",    # 4A Santa Michaela
    "Galina Romanov":            "Stagewater",              # 9A Stagewater County
    "Svenja Bianchi":            "Tamarack",                # 9A Tamarack County
    "Carmen Cordero":            "Bannock",                   # 9A Vance County
    "Salvador Figueroa":         "Vesper",                  # 4A Vesper
    "Klara Marchand":            "Weller",

    # ‼️ THE LAST FIVE, and the reason they survived four sweeps: every filter that
    # excluded PLACE WORDS excluded them. Echevarria, Zubieta, Arrieta and Calder are
    # all Jefferson TOWNS as well as surnames, so "Aitor Echevarria" was read as a
    # place and skipped — by the pool test, and then by the two-token place filter
    # that replaced it.
    #
    # The test that finally worked looks at the FIRST word only: a name whose first
    # word is not place or institution vocabulary is a person, whatever the second
    # word doubles as. A surname that is also a town cannot hide a given name in
    # front of it.
    "Aitor Echevarria":            "Point Loma",              # 9A Aldecoa
    "Aitor Zubieta":               "Borough Beach",             # 8A Belyakov
    "Ander Arrieta":               "Bolinas",                 # 6A Weissburg
    "Harold Calder":               "Tomales Bay",             # 6A San Telmo
    "Lorraine Calder":             "Morne Rouge",               # 7A Belyakov

    # ‼️ THE INVENTED PEOPLE THEMSELVES (owner, 2026-08). The campus sweeps kept
    # finding "<fake person> North", renaming the CAMPUS, and leaving the person's own
    # school standing two rows away. These are the base schools.
    #
    # ‼️ FOUND BY LISTING, NOT BY A TEST. Three passes of pool-matching under-counted,
    # because these names come from vocabularies the generator's own files do not hold
    # — Basque (Etxeberria, Elorriaga, Mendizabal, Aramburu), Russian (Voronin, Karev,
    # Melnick), Spanish (Villaseñor, Villalba, Ordoñez). What worked was printing every
    # two-token name that is not a known place and reading it.
    #
    # ‼️ REAL PEOPLE STAY, and they are most of what is left: every president and
    # justice, plus Bayard Rustin, Paul Robeson, Shirley Chisholm, Romare Bearden,
    # Yuri Kochiyama, Katherine Johnson, Mae Jemison, Benjamin Banneker, José Martí,
    # Dolores Huerta, Ella Baker, Gwendolyn Brooks, Octavia Butler, James Baldwin,
    # John Lewis, Rita Moreno, Alben Barkley, Walter Mondale. Do not sweep these.
    #
    # Names are CALIFORNIAN — neighbourhoods, streets and water — which is the register
    # Jefferson's own coast already reads in. Seaside Heights, Cape Jean and Charles Harbor
    # are owner picks (2026-08).
    "Adela Robles":                "Biloxi Heights",         # 4A San Borondón
    "Adela Villaseñor":            "Cape Jean",               # 7A Caswell
    "Ainhoa Mendizabal":           "Charles Harbor",               # 6A Simmons
    # ‼️ TWO KEYS, ONE SCHOOL. `Javier Villalba` is the prep-network identity and
    # `Alonso Villalba` is what the PREVIOUS version of this table renamed it to — a
    # checkout already migrated by the old script carries that name, so without the
    # alias rerunning the documented migration would leave it stranded under a name
    # nothing recognises. Only one of the two ever exists in a given dataset, so they
    # cannot both emit and collide.
    "Javier Villalba":             "Los Feliz",               # 9A Llerena
    "Alonso Villalba":             "Los Feliz",               # migration alias
    "Amaia Etxeberria":            "Boyle Heights",           # 8A Carden City
    "Amalia Escobedo":             "Petoskey Rock",              # 7A Belyakov
    "Anya Antonov":                "Mar Vista",               # 9A San Cordero
    "Anya Orlov":                  "Riviere Salee",             # 6A Belyakov
    "Esteban Téllez":              "Sawtelle",                # 6A Aldecoa
    "Garazi Aramburu":             "Ocean Park",              # 2A Lieksa
    "Greta Adler":                 "Topanga",                 # 7A Valderra
    "Greta Bellini":               "Glassell Park",           # 3A Silver Glen
    "Isabel Lucero":               "El Sereno",               # 7A Bahía Leal
    "Itziar Elorriaga":            "Elysian Valley",          # 8A Altamonte
    "Itziar Lertxundi":            "Noe Valley",              # 6A Cañada Grande
    "Lars Bellini":                "Bernal Heights",          # 9A Montelago
    "Leire Garmendia":             "Potrero Hill",            # 9A Belmonte
    "Lena Talltree":               "Dogpatch",                # 8A Ashbury
    "Lev Kareva":                  "Hayes Valley",            # 9A Orellana
    "Lev Voronin":                 "Cole Valley",             # 9A Fort Valois
    "Lucía Villaseñor":            "Glen Park",               # 6A Emerson
    "Maksim Karev":                "Excelsior",               # 4A Los Maderos
    "Mikel Garmendia":             "Homeland",                # 5A Rostova Junction
    "Mila Melnick":                "Sea Cliff",               # 5A Orlova
    "Miren Elorriaga":             "Pennsauken",             # 9A Belmonte
    "Nicolás Ordoñez":             "Rockridge",               # 9A Belmonte
    "Nicolás Villalba":            "Temescal",                # 8A Starlight
    "Sofía Aranda":                "Montclair",               # 8A Puerto de los Reyes
    "Vasquez":                     "Fruitvale",               # 5A Halbrook
    "Viktor Kareva":               "Cedar Point",             # 5A Llerena
    "Walter Langston":             "Maxwell Park",            # 7A San Telmo

    # ‼️ THE REST OF THE PERSON-CAMPUS SWEEP (owner, 2026-08). The first pass used a
    # pool test — both tokens had to appear in the generator's own name files — and
    # anything drawn from anywhere else walked straight past it: Anya Belov North,
    # Adela Robles North, Jon Etxeberria North and ten more. The reliable test is the
    # SHAPE, not the vocabulary: a name ending in a direction, read by eye.
    #
    # Real people included, same rule: Thurgood Marshall, José Martí, Woodrow Wilson,
    # James Madison, Benjamin Banneker and Harry S. Truman each keep the school that
    # bears their name and lose the second campus.
    #
    # And the suffix rule, which had strays of its own: NO "High" and no "High School",
    # ever — plus "Ashbury Central North", which carried two directions at once.
    "Adela Robles North":          "Cliffside",               # 4A San Borondón
    "Anya Belov North":            "Preston Hollow",          # 4A Llerena
    "Benjamin Banneker North":     "Pascagoula",              # 5A Belmonte
    "Harry S. Truman North":       "Fair Park",               # 4A Cortland
    "James Madison North":         "Hagerstown",             # 7A Belmonte
    "Javier Cárdenas North":       "Casa Linda",              # 5A Llerena
    "Jon Etxeberria North":        "Chickasaw",              # 5A Belmonte
    "José Martí North":            "Belle Rive",                 # 5A Belyakov
    "Naomi Langston North":        "Pointe des Brumes",         # 3A San Borondón
    "Nikolai Markov North":        "Marigny",                 # 6A San Borondón
    "Thurgood Marshall North":     "Carrollton",              # 6A San Cordero
    "Vasquez North":               "Fontainebleau",           # 4A Halbrook
    "Woodrow Wilson North":        "Hackensack",                # 5A Belmonte
    "Belyakov Depot High":         "Anse Doree",          # 8A Belyakov
    "Depot High":                  "Passaic",                   # 4A Belmonte
    "Depot High North":            "Natchez",             # 6A Belmonte
    "Drayfield Foundry High":      "Empire",       # 5A Drayfield
    "Fort Meriwether Foundry High": "Ironworks", # 6A Fort Meriwether
    "Fort Meriwether Foundry High North": "Westfield Friends",  # 4A Fort Meriwether
    "Foundry High":                "Foundry",                 # 9A Lake Esperanza
    "Frontier High":               "Frontier",                # 5A Harriman
    "Port Veles Foundry High":     "Seawall",      # 8A Port Veles
    "Seafarer High":               "Seafarer",                # 9A Port Veles
    "St. Casimir High School North": "Casimir Creek",       # 3A Harriman
    "Ashbury Central North":       "Kishwaukee",       # 4A Ashbury

    # ‼️ AND THE RULE APPLIES TO REAL PEOPLE TOO (owner, 2026-08). A campus direction
    # on a person's name is unrealistic whoever the person was — a school honouring
    # Gwendolyn Brooks does not have a north campus. The person keeps the school that
    # bears their name; the extra campus becomes a neighbourhood.
    "Gwendolyn Brooks North":    "Lakewood",                # 7A San Cordero
    "Rita Moreno North":         "Gentilly",                # 6A Valderra

    # ‼️ NEIGHBOURHOODS, NOT DIRECTIONS (owner rule 2026-08). The association already
    # has too many directional names, so a school that cannot take its town's name
    # takes a neighbourhood — which is how a city with five high schools names them
    # in life. Owner's pool: Chicago, St. Louis, Kansas City, Houston, Dallas, New
    # Orleans and the Gulf Coast.
    "Pavel Kovalenko":           "Coles Creek",             # 7A Aldecoa
    "Elena Petrenko":            "Kingsway",                # 6A Aurelia
    "Andrés Ibarra":             "Monongahela",               # 7A Belmonte
    "Javier Alvarado":           "Okefenokee",            # 8A Belmonte
    "Rosa Castañeda":            "Tippecanoe",             # 9A Belmonte
    "Yelena Sokolov":            "Bowerstock",              # 8A Belmonte
    "Mikhail Sidorov":           "Saint Marc",             # 6A Belyakov
    "Nicolás Quiñones":          "Stonehaven",              # 7A Calder
    "Katherine Whitaker":        "Brookside",               # 6A Carroway
    "Oskar Weiss":               "Waldo",                   # 8A Cortland
    "Marian Browne":             "River Market",            # 3A Dovetail
    "Yuri Chernov":              "Sunset Hills",            # 8A Emerson
    "Eleanor Cole":              "Jefferson Park",          # 8A Fort Carden
    "Winifred Booker":           "Albany Park",             # 7A Fort Carden
    "Nerea Urrutia":             "Blue Valley",             # 2A Galena
    "Viktor Gromov":             "Armour Fields",           # 7A Greaves
    "Gabriel Zúñiga":            "Longfellow",              # 8A Lake Esperanza
    "Hazel Hart":                "Oak Meyer",               # 3A Los Maderos
    "Edith Tillman":             "Norwood Park",            # 5A Madrigal
    "Javier Castañeda":          "Kenwood",                 # 5A Madrigal
    "Lucía Quiñones":            "Edgewater",               # 4A Madrigal
    "Isaiah Price":              "Squier Park",             # 7A Montelago
    "Ruby Mercer":               "Pendleton Heights",       # 7A Moriarty
    "Lev Volkov":                "Sherwood Estates",        # 4A Newark River
    "Alina Antonov":             "River Oaks",              # 8A Orellana
    "Amelia Freeman":            "Nanticoke",                # 5A Port Veles
    "Alejandro Zamora":          "Morgan Park",             # 9A Puerto de los Reyes
    "César Peralta":             "Avalon Park",             # 8A Puerto de los Reyes
    "Alina Belov":               "Clear Lake",              # 3A Rilland
    "Daniel Gaines":             "Vicksburg",        # 7A San Borondón
    "Harold Williams":           "Tuskegee",                 # 9A San Borondón
    "Emilia Jansen":             "Sharpstown",              # 4A San Dámaso
    "Naomi Moss":                "Meyerland",               # 5A San Tomás
    "Winifred Ellison":          "Kingwood",                # 5A Santa Cruz del Norte
    "Anneliese Ricci":           "Carondelet",              # 9A Santa Michaela
    "Hazel Bennett":             "Benton Park",             # 9A Santa Michaela
    "Beatriz Zamora":            "Tower Grove",             # 9A Serrano
    "Edith Mercer":              "Forest Park",             # 9A Serrano
    "Oksana Petrov":             "Oak Forest",              # 4A Simmons
    "Edith Ward":                "Central West End",        # 5A Telfair
    "Tomás Mendoza":             "Fairgrounds",             # 5A Telfair
    "Isabel Montalvo":           "Magnolia Park",           # 4A Three Saints
    "Jean Lindgren":             "Bridgeport",              # 6A Valderra
    "Thelma Moss":               "Roscoe Village",          # 5A Valderra
    "Winifred Browne":           "Rogers Park",             # 9A Valderra
    "Katherine Bellamy":         "Meadowbrook",             # 5A Wales City
    "Sergei Petrenko":           "Willowbrook",             # 3A Weissburg
    "Beatriz Salcedo":           "Spring Branch",           # 7A Zubieta

    # ‼️ A SPECIALIZED SCHOOL'S NAME IS SHORT (owner rule 2026-08). Nobody says
    # "Manufacturing and Technology Academy" — a tech school is "<Place> Tech" and an
    # arts school is "<Place> Arts", the way Oakland School for the Arts is Oakland
    # Arts. The long descriptive form is a district's paperwork, not what anyone
    # calls it.
    "Academy of Arts and Communication":                "Junction",
    "Altamonte Civic Leadership Academy":               "Senator Gray",
    "Belden Springs Academy of Music and Media":        "Springdale",
    "Belyakov Agricultural Sciences Academy":           "Mickey Mantle",
    "Cabo Esperanza Technical Arts Academy":            "Cabo Esperanza Tech",
    "Featherstone Institute":                           "Featherstone Tech",
    "Fellows Mill Civic Leadership Academy":            "Millworks",
    "Greaves Aviation and Engineering Academy":         "Skypark",
    "Homecroft Manufacturing and Technology Academy":   "West Burlington",
    "I-50 Technical":                                   "Belmonte Tech",
    "I-50 Technical North":                             "Tuscarora",
    "Leidesdorff Academy of Music and Media":           "East Burlington",
    "Northrup I-50 Technical":                          "Northrup Tech",
    "Paddock Institute":                                "Paddock Tech",
    "Perryville Civic Leadership Academy":              "Perry Green",
    "Port Veles Civic Academy":                         "Henson Prep",
    "Rostova Junction Technical Arts Academy":          "Railyard",
    "San Borondón Civic Academy":                       "Rumsfeld Hill School",
    "San Telmo Agricultural Sciences Academy":          "Orchard Union",
    "Selbyville Manufacturing and Technology Academy":  "Selby Tech",
    "Vesper Polytechnic Institute":                     "Funtsville",
    "Zubieta Manufacturing and Technology Academy":     "Sluice Gate",


    # ‼️ A PERSON'S NAME NEVER CARRIES A CAMPUS DIRECTION (owner rule 2026-08): "no
    # named person school should ever have more than one campus, that's not
    # realistic". A PLACE can — Belmonte North is ordinary — so every one of these
    # becomes a place, a neighbourhood or a landform. Names from the owner's own
    # non-person pool; where their first choice was already a live school the town's
    # next free direction is used instead.
    #
    # Ben Franklin and Hollywood are owner picks (2026-08). Jefferson's big-city
    # districts name schools the way Portland's do — presidents and Franklin — and
    # neighbourhoods broaden the range inside one town, which is where Hollywood comes
    # from.
    "Andrés Ibarra North":       "Saddleback Central",        # 4A Belmonte
    "Elena Mendoza North":       "Cahaba",             # 6A Belmonte
    "Javier Alvarado North":     "Shenango",               # 6A Belmonte
    "Jean Lindgren North":       "Harrisburgh",          # 4A Valderra
    "Petra Weiss North":         "Las Colinas",             # 4A Valderra
    "Thelma Moss North":         "Serenity Valley",        # 7A Valderra
    "Claudette Cole North":      "Pointe Coupee",    # 5A San Borondón
    "Tatiana Chernov North":     "Bahía Vista",             # 6A San Borondón
    "Vernon Moss North":         "Harmony",       # 7A San Borondón — 2026-08,
                                                  # was "Bogue Chitto"
    "Mila Chernov North":        "Siberia",        # 4A Belyakov
    "Viktor Antonov North":      "Bois Rouge",              # 4A Belyakov
    "Andrés Valera North":       "Pawnee",           # 6A Caswell
    "Salvador Montalvo North":   "Stone Ridge",             # 6A Caswell
    "Marcus Price North":        "Driftwood",     # 4A Lake Esperanza
    "Ruby Stokes North":         "Forks Harbor",        # 8A San Cordero
    "Lillian Stokes":            "Ben Franklin",            # 8A Mercer City
    "Thomas Halvorsen":          "Hollywood",               # 8A Mercer City
                  # 9A Weller County
}

# The institutional-naming bank the pass above drew from — kept as its own list so a
# later pass can draw more from the SAME grammar without re-deriving it. Never assign
# a name here to a TOWN or a LEAGUE; these are school identities only, the way "Crown
# Paper" names a school a company town built, not the town itself.
INSTITUTION_NAMES = [
    "Alder Cooperative", "Anchor Glass", "Arroyo Water District", "Basalt Electric",
    "Blue Mountain Grange", "Bracken Works", "Cañada Irrigation", "Cascade Mutual",
    "Cedar Exchange", "Copper Belt", "Crown Paper", "Dry Creek Cooperative",
    "East Range Agricultural", "Elk River Power", "Empire Milling", "Fallon Works",
    "Fir Valley Grange", "Golden State Packing", "Granite Water & Power",
    "High Desert Cooperative", "Iron Gate Works", "Juniper Agricultural",
    "Klamath Exchange", "Lone Pine Mutual", "Lost River Irrigation", "Mesa Cooperative",
    "Millrace Technical", "North Coast Packing", "Pacific Fruit Exchange",
    "Pioneer Electric", "Quarry Workers", "Red Butte Cooperative", "Redwood Mutual",
    "Rogue Valley Packing", "Round Mountain Grange", "Shasta Agricultural",
    "Silver Creek Irrigation", "Siskiyou Electric", "Southern Pacific Technical",
    "Spring Valley Cooperative", "Summit Works", "Tule Lake Agricultural",
    "Union Water", "Valley Packing", "West Range Cooperative", "White Pine Grange",
    "Basin Reclamation", "Bellwood Cannery", "Blackrock Mining", "Cattlemen's Exchange",
    "Cinder Cone Milling", "Coastal Fisheries", "Dunes Reclamation", "Foothill Grange",
    "Gravel Belt", "Homestead Grange", "Ironwood Lumber", "Kettle Falls Power",
    "Lakeshore Canning", "Meridian Rail", "Mill Creek Lumber", "Odd Fellows Hall",
    "Orchard Growers", "Overland Freight", "Placer Mutual", "Prospect Milling",
    "Range Riders Association", "Sawmill Workers", "Sheepmen's Association",
    "Signal Ridge Telegraph", "Stockmen's Exchange", "Tidewater Cannery",
    "Timber Cooperative", "Trading Post Grange", "Wool Growers Association",
    "Yield Grange",
]

# Schools whose DISPLAY name is a religious or independent institution and which
# therefore read as private, whatever the source record said. Keyed on the display
# name, like `MASCOTS` and `COLORS` — see the emit block in `build`.
PRIVATE_SCHOOLS = {
    "Mater Dei", "Jesuit", "Notre Dame", "Archbishop Gregory",
    "Sacred Heart", "Bellarmine Prep", 
    "Xavier College Prep", "St. Francis Catholic", "Christian Brothers",
    "Cardinal Mercier", "Pope Leo XIV",
    "Archbishop Valois", "St. Catherine Academy",
    "Cardinal Echevarria", "De La Salle", 
    "Sinkford",
    "Cardinal Newman", "Calvary Christian", 
    
    # Converted from public by owner decision, 2026-08.
    "Westfield Friends", "Star Hollow",
    # Converted with the locality redistribution (owner spec, 2026-08).
    "Belmonte Collegiate",
    "Walter-Kenny",
    "Lycee Valmont",
}

# ‼️ THE FLAGSHIP PLAYS THE SPORT (owner rule 2027-08). Nine cities had a MAGNET
# school in the tennis association while the plain city high school — which
# exists in prep-network and is usually the bigger, older school — sat out. That
# is backwards: an arts-and-letters academy or a polytechnic institute mostly
# does not field teams, and if a city sends one program to the state tournament
# it is the flagship. So these are SUBSTITUTIONS, not renames: the magnet's seat
# in the association is given to the bare-named school, which then plays under
# its OWN classification, enrollment, mascot and colours (they differ — Altamonte
# is 5A where its School of Commerce was 4A). Nothing is deleted; the magnet
# simply does not sponsor tennis, exactly as it would not in life.
#
# Applied AFTER the sponsorship draw for the same reason RENAMES is applied at
# emit: the dice are positional over the name-sorted list, so swapping names
# earlier would reshuffle everyone in between.
# ‼️ WHO SPONSORS TENNIS IS A MAP DECISION (owner rule 2026-08). The association
# had 83 Jefferson towns with a high school and no tennis program at all, while
# five cities carried 28-44 programs each. Both tables key on the PREP-NETWORK
# name, like ALWAYS_EXTRA and unlike archetypes.json, and both are applied AFTER
# the draw for the same reason SUBSTITUTIONS is: the dice are positional over the
# name-sorted list, so removing a school before the roll reshuffles every school
# after it. Applied to the committed data by `scripts/jhsaa_sponsors.py`, which
# redraws the leagues of the classes they touch.
NEVER_SPONSOR = frozenset()

# ‼️ THE 2052 EASTERN OREGON / COLUMBIA GORGE EXPANSION LIVES OUTSIDE THIS FILE
# (owner rule 2026-08, `scripts/jhsaa_2052_expansion.py`): 39 real OR/WA
# affiliates, the net-new Jefferson town Amelia City, Baker's 3A->5A move, and
# 40 owner-named sunsets (flags off, rows kept — the `former_school` path).
# Affiliates have no prep-network rows, so a full re-import cannot produce them
# and would also resurrect the sunsets as sponsors: AFTER any re-import, re-run
# jhsaa_2052_expansion.py (idempotent; it holds every table). The same applies
# to the earlier affiliate batches (Baker, the Bend cluster, the Great Basin).

EXTRA_SPONSORS = frozenset({
    "Whistle Stop",       # 1A 152 — Whistle Stop, Antler. The town's only school, and
                          # the town had no tennis at all.
    "Plainfield Science",  # 6A 1297 — Plainfield, Antler. Owner add (2026-08),
                          # displayed "Plainfield" (RENAMES).
    "Abraham Lincoln",    # 9A 2347 — Belyakov. Owner add (2026-08): the state had no
                          # Lincoln at all. Displayed "Lincoln" (RENAMES), the
                          # surname style Washington/Roosevelt/Obama already use.
    # ‼️ AN EXPANSION PROGRAM (owner, 2026-08). Minnesota City (2A, 215, Emigrant
    # County, Kangas) already sponsored GIRLS tennis and lost the boys' sub-roll;
    # the association adds boys. ⚠️ This table forces a school in for BOTH genders,
    # which is exactly right here because the girls' side is already true — a
    # boys-only add for a school sponsoring NEITHER would also create a girls' team,
    # and would need a per-gender table rather than this one.
    #
    # No league redraw: a league belongs to the SCHOOL (drawn once per classification
    # over the girls-inclusive pool), so their `boys_district` was already filled in
    # and the 2A Desert Sky boys' half simply goes 7 → 8, well inside MAX_DISTRICT.
    "Minnesota City",
    # ‼️ SIX MORE EXPANSIONS, same shape as Minnesota City above (owner rule 2026-08):
    # each already sponsored girls and lost the boys' sub-roll, leaving 8A with seven
    # girls-only programs. `Larchmont Ridge` was the seventh and is deliberately left
    # off this list — the owner named the other six explicitly and held it back. No
    # league redraw needed for any of these either: all six already carry a
    # `boys_district` identical to their `girls_district`.
    "Covenant Christian",           # 8A 1878 — Ashbury Metro, Ambassador League
    "Llerena School of Science and Industry",   # Crow Basin, 8A 1988 — Halbrook Basin,
                                     # Four Rivers Interscholastic League
    "Leonard Coleman",              # 8A 2024 — Ashbury Metro, Ambassador League
    "Sergei Belov",                 # Malcolm X Shabazz, 8A 1751 — Sebastian Cape,
                                     # South Coast League
    "Rosa Salcedo",                 # Quarry Workers, 8A 1745 — Sebastian Cape,
                                     # Pacific Coast League
    "Clara Cross",                  # Red Mesa, 8A 1713 — Gold Valley, Gold Valley League
})

# ‼️ LOCALITY — the settlement a school belongs to INSIDE its city (owner spec,
# 2026-08). The five big metros hold 28-44 tennis programs each, which no single
# municipality does; in life those schools sit in CDPs, unincorporated places and
# absorbed towns that the city has grown around. So `city` stays the metro — it is
# the game tag, and districts, geography and every existing lookup keep reading it
# — and `locality` is the settlement identity shown beside it.
#
# Keyed on the DISPLAY name, like MASCOTS and COLORS, so a rename moves this key
# with it. A school with no entry is a CORE CITY school and shows only its city;
# that is a real distinction, not a missing value, so there is no default.
#
# ‼️ LOCALITIES REPEAT ON PURPOSE — two schools can share one (Natchez Prep and
# Natchez Cliff), and the same locality name can appear in two different metros.
# It is not an identity and nothing keys on it. School NAMES are the identity and
# they are unique; see `build()`, which refuses to emit a collision.
LOCALITIES = {
    "Allegheny":                             "Allegheny",
    "Dry Fork":                           "Cahaba",
    "Chaminade":                             "Pointe Coupee",
    "Condotti Vanguard Academy":             "Condotti",
    "Covenant Christian":                    "Tuskegee",
    "Dogpatch":                              "Hackensack",
    "Evans Larsen Day":                      "Bannock",
    "Forge":                      "Hagerstown",
    "Jefferson Science":                     "Tuscaloosa",
    "Kishwaukee":                            "Kishwaukee",
    "Timberline":                    "Monongahela",
    "Natchez Mercy":                         "Natchez",
    "Pacific Friends":                       "Vicksburg",
    "Romero-Finniski":                       "Finiski",
    "Sherwood Bench":                        "Sherwood",
    "Websterfield":                      "Natchez",
    "St. Norbert Abbey":                     "Natchitoches",
    "Tallulah Central":                      "Tallulah",
    "Vista Terrace":                         "Biloxi",
    "Wyalusing Providence":                  "Wyalusing",
    "Highland Park":                     "Allegheny",
    "Benjamin Banneker":                     "Banneker",
    "Bowerstock":                            "Bowerstock",
    "Cahaba":                                "Cahaba",
    "Cahokia Mounds":               "Cahokia",
    "Caney":                                 "Caney",
    "Chickasaw":                             "Chickasaw",
    "Chillicothe":                           "Chillicothe",
    "Hackensack":                            "Hackensack",
    "Hagerstown":                            "Hagerstown",
    "James Madison":                         "Kishwaukee",
    "Ketanji Brown Jackson":                 "Pontotoc",
    "Kinnickinny":                           "Kinnickinny",
    "Kokomo":                                "Kokomo",
    "Monongahela":                           "Monongahela",
    "Natchez":                               "Natchez",
    "Okefenokee":                            "Okefenokee",
    "Pascagoula":                            "Pascagoula",
    "Passaic":                               "Passaic",
    "Pennsauken":                            "Pennsauken",
    "Petoskey":                              "Petoskey",
    "Sandra Day O'Connor":                   "Choctaw",
    "Shenango":                              "Shenango",
    "Shirley Chisholm":                      "Burroughs",
    "Sparrowhawk":                           "Sparrowhawk",
    "Tippah":                                "Tippah",
    "Tippecanoe":                            "Tippecanoe",
    "Tuscarora":                             "Tuscarora",
    "Sojourner Truth":                       "Tallulah",
    "Wyalusing":                             "Wyalusing",
    "Yazoo":                                 "Yazoo",
    "Anse Doree":                            "Anse Doree",
    "Bannock":                               "Bannock",
    "Bayard Rustin":                         "Wilberforce",
    "Belle Rive":                            "Belle Rive",
    "Bellefontaine":                         "Bellefontaine",
    "Bois Neuf":                             "Bois Neuf",
    "Bois Rouge":                            "Bois Rouge",
    "Borough Beach":                      "Bowerstock",
    "Friendship City":                       "Friendship",
    "Grand Fond":                            "Grand Fond",
    "La Savane":                             "La Savane",
    "Lycee Valmont":                         "Valmont",
    "Morne Caribou Polytechnic":             "Morne Caribou",
    "Morne Rouge":                           "Morne Rouge",
    "Pennsauke":                             "Pennsauke",
    "Petoskey Rock":                         "Petoskey",
    "Riviere Salee":                         "Riviere Salee",
    "Saint Marc":                            "Saint Marc",
    "Savane Brulee":                         "Savane Brulee",
    "Trois Ilets":                           "Trois Ilets",
    "Sally Ride":                            "Roanoke",
    "Benjamin Harrison":                     "Schuylkill",
    "Biden":                                 "Choptank",
    "Calvin Coolidge":                       "Shenandoah",
    "Casco":                                 "Casco",
    "Cheney":                                "Penobscot",
    "Chesapeake":                            "Chesapeake",
    "Christchurch Episcopal":                "Christchurch",
    "Cleveland":                             "Pocomoke",
    "Clinton":                               "Occoquan",
    "Fillmore":                              "Mattaponi",
    "Franklin Pierce":                       "Patuxent",
    "Garfield":                              "Buzzards Bay",
    "George H. W. Bush":                     "Hackensack",
    "Gerald Ford":                           "Sassafras",
    "James Monroe":                          "Susquehanna",
    "Kittery":                               "Kittery",
    "Martin Van Buren":                      "Piscataway",
    "Nanticoke":                             "Nanticoke",
    "Narragansett":                          "Narragansett",
    "Obama":                                 "Chickahominy",
    "Roosevelt":                             "Potomac",
    "Rutherford Hayes":                      "Wethersfield",
    "Severn":                                "Severn",
    "Swiss Hills Prep":               "Brandywine",
    "Tidewater Catholic":                    "Tidewater",
    "George Washington":                     "Taunton",
    "Wicomico":                              "Wicomico",
    "William Henry Harrison":                "Rappahannock",
    "Zachary Taylor":                        "Pamunkey",
    "Apalachicola":                          "Apalachicola",
    "Bahía Vista":                           "Biloxi",
    "Bienville":                             "Bienville",
    "Biloxi Heights":                        "Biloxi",
    "Harmony":                               "Bogue Chitto",
    "Malcolm X Shabazz":                          "Cahaba",
    "Marigny":                               "Marigny",
    "Cliffside":                         "Natchez",
    "Natchez Prep":                          "Natchez",
    "Natchitoches":                          "Natchitoches",
    "Brightwater":                 "Natchitoches",
    "Pointe Coupee Catholic":                "Pointe Coupee",
    "Pointe Coupee":                 "Pointe Coupee",
    "Pointe des Brumes":                     "Pointe des Brumes",
    "Talladega":                             "Talladega",
    "Tallulah Canyon":                       "Tallulah",
    "Tensas":                                "Tensas",
    "Tuscaloosa":                            "Tuscaloosa",
    "Tuskegee":                              "Tuskegee",
    "Vicksburg":                             "Vicksburg",
}

SUBSTITUTIONS = {
    "Altamonte School of Commerce": "Altamonte",
    "Bellacosta University Prep": "Bellacosta",
    "Calder Aviation and Engineering Academy": "Calder",
    "Copper Lake Academy of Music and Media": "Copper Lake",
    "Copperview Polytechnic Institute": "Copperview",
    "Fort Meriwether School of Public Service": "Fort Meriwether",
    "Mercer City School of Design and Engineering": "Mercer City",
    "Mount Horeb Academy of Arts and Letters": "Mount Horeb",
    "Puerto de los Reyes Civic Leadership Academy": "Puerto de los Reyes",
}


# Championship groups. 3A stands ALONE and 2A/1A combine (owner rule 2027-08): the
# enrollment gap across the old 3A-1A group was the widest in the association — medians
# of 1,043 / 385 / 199 — so a 1,370-student school and a 108-student one were competing
# for the same trophy.
# ⚠️ RECLASSIFICATION (owner rule 2027-08). prep-network's 2A holds 88 schools and its
# 1A 111, so a combined 2A-1A dwarfed 3A's 140 — 151 tennis sponsors against 46. States
# readjust their enrollment cutoffs all the time, and this is that: the largest 2A schools
# move up to 3A, which balances the two smallest championships without splitting 2A from
# 1A (the owner does not want separate 2A and 1A tennis).
#
# ⚠️ RECLASSIFICATION, ROUND 2 (owner rule, follow-up to 2027-08). 430 turned out to be
# above every 2A school's enrollment in the current pool (max 397) — the promotion never
# actually fired, so 3A stayed the association's smallest classification (60 sponsors)
# while 2A-1A stayed nearly as big as 7A (103 vs 105). Same fix, lower bar: pulling the
# line down to 300 promotes the top 15 of 2A's 31 schools, landing 3A at 75 (tied with
# 5A) and 2A-1A at 88 — no longer an outlier, now roughly level with 6A (89). Move the
# threshold again before reaching for a second lever (like sponsoring MORE 3A schools) —
# thinning 2A is the cheaper knob and it isn't tapped out yet (16 2A schools remain,
# enrollment 225-283).
#
# By ENROLLMENT, because that is what a classification IS. Nothing here looks at who
# sponsors tennis or at how good anybody is.
PROMOTE_2A_ABOVE = 300          # 2A schools at or above this enrollment become 3A

# ⚠️ THE 2033 2A/3A REALIGNMENT (owner rule 2026-08) — the reverse of the cascade
# above, and for the same reason it was run in the first place: the classes had
# drifted far apart. 2A carried 63 programs while 3A carried 125, so 3A crowned from
# a 40-team field and 2A from 24 — and 2A, the class the 1A/2A split was supposed to
# leave viable, was the association's smallest by a wide margin.
#
# ‼️ IT MOVES `classification` AS WELL AS `group`, and that is what makes it a
# RECLASSIFICATION rather than a COMPETITIVE_MOVE. The distinction is not
# bookkeeping: `_TALENT` generates from `classification` (`School.talent_group`), so
# a school moved on `group` alone keeps its old class's players and would walk its
# new one. That is correct for a program petitioning DOWN on results — it is
# supposed to keep the roster it has — and wrong here, where the association is
# saying these schools are 2A-SIZED. Every school named below already sits inside
# 2A's committed enrollment band (306-375 against a 2A range of 86-431), so nothing
# needs scaling to justify it; the schools were above an outdated 300 cut line, not
# above 2A.
#
# It is a NAMED TABLE rather than a moved cut line because the owner named the
# schools. A line at ~380 would take a different 32 — 3A's smallest is 303 and stays
# 3A — and the association's judgement about which programs belong where is the
# input, not an enrollment threshold reverse-engineered to approximate it.
#
# ‼️ AND THE LEAGUES ARE REDRAWN, not joined one by one. A promoted school JOINS a
# league in its new class (`scripts/jhsaa_reclassify.py`), which is what happens
# when one school reclassifies; thirty-two schools arriving into six leagues that
# already hold 63 is not that. 2A grows from six leagues to ten, so the class is
# redrawn through `scripts/jhsaa_redistrict.py` — leagues realign and rebrand, and
# a class that gains a third of its membership is exactly when they do.
RECLASSIFY_TO_2A = (
    "Booker T Washington", "Alben Barkley", "Benton Cross", "Canal Lock",
    "Cape Angeles", "Chaff Head", "Diamante", "Eagleton", "Fort Lassiter",
    "Gilhooly", "Halfway House", "Hawk Bar", "Iisalmi Union", "Latgaway",
    "Lieksa", "Los Maderos", "Governor Woods", "Mt Jacqueline", "Netherwood",
    "New Ballard", "Newark River", "Oak Meyer", "Pointe des Brumes",
    "Porterfield", "Río Seco", "River Market", "South Simmons", "Springdale",
    "Starlake", "Trout Lake", "Willowbrook", "Yazoo",
)

# ⚠️ THE COMMITTED ENROLLMENT BAND PER CLASSIFICATION (owner rule 2026-08) — the
# contiguous range every real school in a class already sits inside, measured off
# `data/jhsaa/schools.json` and stable because `reclassify()`'s own cut lines are
# what produced it. Existing solely to give a RECLASSIFIED school (see
# `RECLASSIFY_2039` below) a number that belongs in its new class: enrollment is
# fictional and the number follows the decision, but "follows" still means
# "lands inside the band the rest of the class occupies", not any value at all.
_CLASS_ENROLLMENT_BAND = {
    "1A": (57, 311), "2A": (86, 431), "3A": (303, 548), "4A": (552, 798),
    "5A": (806, 1020), "6A": (1022, 1319), "7A": (1323, 1636),
    "8A": (1638, 2143), "9A": (2148, 2597),
}


def _reclass_enrollment(name: str, group: str) -> int:
    """A stable, band-legal enrollment for a school reclassified INTO `group` — the
    same one-point-per-band idiom as `jhsaa.roster_size` (seeded on the school
    alone, so it reads as a durable trait and not something that reshuffles on
    re-import)."""
    lo, hi = _CLASS_ENROLLMENT_BAND[group]
    return random.Random(f"jhsaa-reclass-enrollment|{name}").randint(lo, hi)


# ⚠️ THE 2039 CROSS-CLASS REALIGNMENT (owner rule 2026-08) — a SECOND named
# reclassification table, same shape as `RECLASSIFY_TO_2A` and the same reason it
# exists: the owner named the schools and the classes they move to directly, not a
# cut line for a script to reverse-engineer. Unlike the 2033 pass, none of these 30
# already sit in their target class's enrollment band (moves span up to seven
# classes, e.g. a 216-enrollment 2A program to 8A), so `_reclass_enrollment` gives
# each a fresh number inside the band it is moving to — this is the case
# `RECLASSIFY_TO_2A`'s docstring flagged as "only needed when the number would
# otherwise contradict the move": here it always does.
RECLASSIFY_2039 = {
    "Mater Dei": "8A", "Lincoln": "8A", "Ronald Reagan": "9A",
    "Belmonte Tech": "9A", "Larchmont Ridge": "8A", "George Washington": "8A",
    "Pacific Friends": "5A", "Metropolitan Country Day": "5A",
    "Hazel Country Day": "5A",
    "Chaminade": "6A", "St. Vincent": "6A", "Dry Lake": "6A",
    "Fletcher-Garrison Hall": "3A", "Valley Christian": "6A",
    "Vesper": "1A",
    "Bravewoman": "1A", "Orchardgate": "1A",
    "Ansotegui Siding": "1A", "Pointe Coupee Catholic": "1A",
    "Riviere Salee": "1A", "Aspen Hollow": "1A", "Belmonte South": "1A",
    "Northrup Tech": "1A", "St. Lucia Academy": "1A",
    "St. Norbert Abbey": "1A",
    "Casa Linda": "6A", "Belmonte": "6A", "Doyle": "6A",
    "Baptist": "6A", "Blackpine": "5A",
}

# ⚠️ THE 2039 REALIGNMENT, CORRECTION BATCH (owner rule 2026-08) — same table shape
# and mechanism as `RECLASSIFY_2039`, kept SEPARATE rather than merged into it: the
# owner named these after reviewing who was left in 9A/8A, mostly private schools
# nobody recognised sitting at the top of the ladder. A second named table, not a
# second mechanism.
#
# ‼️ Port Veles Episcopal moved to 4A, not 3A — the owner flagged both as
# possibilities ("3A? 4A?") and left the choice open; 4A was picked as the milder
# of the two drops. Revisit if that guess was wrong.
RECLASSIFY_2039B = {
    # Down — mostly private schools that had drifted to the top of the ladder.
    "Natchez Mercy": "3A", "Meridian Valley": "3A", "Palisade Prep": "3A",
    "St. Sebastian Prep": "3A",
    "Archbishop Gregory": "8A",
    "Sacred Heart": "7A", "Bellarmine Prep": "7A",
    "Port Veles Episcopal": "4A",
    "Covenant Christian": "2A",
    "Valera": "1A", "St. Jerome Academy": "1A",
    # Up — backfilling the seats the moves above emptied.
    "Thurgood Marshall": "8A", "Cherry Hill South": "8A", "Roosevelt": "8A",
    "Charlotte": "9A", "Sandra Day O'Connor": "9A", "Ruth Bader Ginsburg": "9A",
}

# ⚠️ RECLASSIFICATION, ROUND 3 (owner rule 2027-08) — THE TOP OF THE LADDER, and the
# reason is the Semi-Conference. `jhsaa.sponsor_floor` says a 40-field class needs 76
# sponsors per gender to field a full qualifying round, and 9A BOYS had 72: four short,
# the only class-gender under the line, and short for no reason but where the
# enrollment cut lines happened to fall. The owner's call was to fix the association
# rather than the format — "there are more than enough schools to do that so it seems
# silly to let this be a real constraint when it's not" — by moving schools UP a class
# and letting the gap cascade back down: 8A→9A, 7A→8A, 6A→7A, and 5A backfills 6A.
#
# Same mechanism and same justification as the 2A→3A promotions above: states readjust
# their enrollment cutoffs all the time, and the line is drawn on ENROLLMENT because
# that is what a classification IS. Nothing here looks at who sponsors tennis or at how
# good anybody is — that is what PLAY_UP is for, and it is a different thing.
#
# Applied TOP-DOWN (9A first) so a school can only ever move ONE class: promote 7A into
# 8A before 8A into 9A and a big 7A school lands in 9A in a single pass.
#
# ⚠️ THE CUT LINES ARE CALIBRATED TO THE COMMITTED ENROLLMENT SCALE — the one in
# `data/jhsaa/schools.json`, which is what the nine-class records carried (9A runs
# 2,213-2,597, 8A 1,703-2,197). They are NOT calibrated to the seven-class
# prep-network checkout, whose 7A alone runs 2,602-4,219; dropped on that scale
# they promote nobody. Each line takes ~12 schools, which is what carries ~10 boys'
# programs up per step and lifts 9A boys clear of `jhsaa.sponsor_floor`.
PROMOTE_ABOVE = {
    "8A": 2148,        # 8A schools at or above this become 9A
    "7A": 1638,        # ...7A become 8A
    "6A": 1323,        # ...6A become 7A
    "5A": 1022,        # ...5A become 6A (the backfill; 4A and below are untouched)
}
_PROMOTE_TO = {"8A": "9A", "7A": "8A", "6A": "7A", "5A": "6A"}

# ‼️ PLAYING UP (owner rule 2027-08). Real associations let a school compete a
# classification above its enrollment class, and here it is what a program strong at
# tennis chooses to do. `PLAY_UP_COUNT` of them, drawn from the BLUE-BLOOD seed list
# in `data/jhsaa/archetypes.json` — the durable "this program is good at tennis"
# property the association already keeps — never from a hand-written list of names,
# which is the same rule archetypes themselves follow.
#
# ‼️ It moves the championship GROUP and never the CLASSIFICATION (see
# `overrides.set_jhsaa_playup` and `jhsaa.School.talent_group`): a played-up school
# takes a harder field, it does not get better players. 9A schools are excluded
# because there is nothing above them.
#
# Weighted to the TOP of each class by enrollment — a school already near the cut
# line is the one that plausibly plays up — and seeded, so the list is reproducible.
#
# ‼️ PLAYING UP IS A SMALL-SCHOOL THING (owner correction 2027-08). "Play up is for
# schools at the 4A or under level to play with teams at their competitive level, not
# already big schools" — an 8A blue-blood moving to 9A is not playing up, it is just a
# big school in a slightly bigger class, and the first pass shipped exactly that
# (Condotti Vanguard Academy 8A -> 9A, Gwendolyn Brooks 8A -> 9A). The point is a small
# program good enough that its own classification cannot give it a game.
PLAY_UP_MAX_GROUP = "4A"        # eligible at this championship group and below
PLAY_UP_COUNT = 14
PLAY_UP_SEED = 90210

# ‼️ RIVALRIES — schools that must NEVER be separated (owner rule 2027-08). A rivalry
# is a fact about two programs, not about their enrollments, so it outranks every
# mechanism here that would move one of them: reclassification, league assignment and
# playing up all have to keep the pair together or leave it alone.
#
# This is not hypothetical. The 2027-08 enrollment cascade promoted Condotti Vanguard
# Academy (1,666) past a 1,638 cut line while Romero-Finniski (1,526) stayed put, so
# two Ashbury schools that had shared Metro League for as long as the association has
# existed ended up in different CLASSIFICATIONS — and a district is (classification,
# name), so nothing short of another reclassification could ever put them back in the
# same league. Every number was correct and the result was wrong.
#
# Enforcement: a pair is promoted only if EVERY member clears the cut (otherwise none
# of them move), and afterwards the whole pair takes one league.
# ‼️ COMPETITIVE MOVES — a program may be placed BELOW its enrollment class (owner
# rule 2026-08). Real associations do this: a school that cannot be competitive where
# its enrollment puts it petitions down, and the association grants it. Here the
# JHSAA grants it outright, and the ENROLLMENT is scaled to match rather than the
# other way round — the enrollments are fictional and nothing about them is permanent,
# so the number follows the decision instead of blocking it.
#
# This is the mirror of PLAY_UP, which lets a small strong program go UP. Together
# they mean a program's class is what it can COMPETE in, with enrollment as the
# default rather than the rule.
#
# ‼️ IT MOVES `group`, NEVER `classification` — the same invariant play-up rests on.
# `group` is the championship you enter; `classification` is how many students you
# have, and `_TALENT` generates from THAT. Keyed on `group`, a demoted school would
# also be generated with the weaker class's talent, which would make the move a
# self-fulfilling collapse instead of a fairer field.
#
# Candidates come from RESULTS, not from a guess — `scripts/jhsaa_competitive.py`
# reads an archived save and reports the programs that have been beaten for years.
COMPETITIVE_MOVES: dict[str, str] = {
    # "School name": "target group",
}


RIVALRIES = [
    ("Condotti Vanguard Academy", "Romero-Finniski"),
]


def rival_group(name: str) -> tuple[str, ...] | None:
    """The rivalry `name` belongs to, or None."""
    for pair in RIVALRIES:
        if name in pair:
            return pair
    return None


def _splits_rivalry(pool: list[dict], at: int) -> bool:
    """True if cutting `pool` at index `at` would put two rivals either side. Only
    meaningful once the pool is sorted so rivals sit adjacent (see `draw_districts`)."""
    before = rival_group(pool[at - 1]["name"])
    return bool(before) and rival_group(pool[at]["name"]) is before


def reclassify(schools: list[dict]) -> int:
    moved = 0
    for s in schools:
        if s["classification"] == "2A" and s.get("enrollment", 0) >= PROMOTE_2A_ABOVE:
            s["classification"] = "3A"
            moved += 1
    # Top-down, so each school is considered exactly once and moves at most one class.
    for src in ("8A", "7A", "6A", "5A"):
        for s in schools:
            if (s["classification"] == src
                    and s.get("enrollment", 0) >= PROMOTE_ABOVE[src]):
                s["classification"] = _PROMOTE_TO[src]
                moved += 1
    # ‼️ THE 2033 REALIGNMENT RUNS LAST, and it has to: every school it names sits
    # above `PROMOTE_2A_ABOVE`, so run first they would be promoted straight back.
    # ‼️ AND IT IS KEYED ON THE DISPLAY NAME — the owner named the schools as the
    # app shows them, while everything before this point is on prep-network's
    # canonical name (renames land at emit). Match on the emitted name and the
    # table means what it says whichever end you read it from.
    down = set(RECLASSIFY_TO_2A)
    for s in schools:
        if _display_name(RENAMES.get(s["name"], s["name"])) in down:
            s["classification"] = "2A"
            moved += 1
    # ‼️ THE 2039 REALIGNMENT RUNS AFTER IT, same reason: several of its targets
    # (e.g. Mater Dei, Lincoln -> 8A) are 9A-band schools the cascade above would
    # otherwise pass straight through on its way up. Same DISPLAY-name matching.
    for s in schools:
        dst = RECLASSIFY_2039.get(_display_name(RENAMES.get(s["name"], s["name"])))
        if dst is not None:
            # `group` is not a field yet at this point in the pipeline (`build()`
            # derives it from `classification` via `champ_group()` at emit) — same
            # as the RECLASSIFY_TO_2A block above, which sets classification alone.
            s["classification"] = dst
            s["enrollment"] = _reclass_enrollment(s["name"], dst)
            moved += 1
    # ‼️ THE CORRECTION BATCH RUNS LAST, same reason as the others: it must see
    # every earlier move's result, not the pre-2039 class.
    for s in schools:
        dst = RECLASSIFY_2039B.get(_display_name(RENAMES.get(s["name"], s["name"])))
        if dst is not None:
            s["classification"] = dst
            s["enrollment"] = _reclass_enrollment(s["name"], dst)
            moved += 1
    return moved



# ⚠️ MASCOT / COLOUR OVERRIDES (owner rule 2027-08). Two faults in the imported
# records, one of them the owner's headline complaint:
#
#   1. NO AQUATIC ANIMALS. Jefferson stands on southern-Oregon and northern-
#      California ground — rivers, lakes and a working coast — and 506 schools
#      carried exactly one water CREATURE (Ashbury West's Sharks) plus Mill
#      Creek's Kokanee. The maritime OCCUPATIONS were already there and good
#      (Shipwrights, Crabbers, Harpooners, Cannerymen, Dredgemen, Longshore,
#      Fogbells, Bar Pilots, Dorymen, Netmenders) — the animals were the gap.
#   2. A GENERIC HEAD. 182 of 506 schools carried one of the seventeen
#      most-common American nicknames — Eagles 20, Panthers 20, Lions 16,
#      Tigers 16, Bulldogs 14 — which is realistic and is also the least
#      interesting thing a name can be. The owner's rule: "if Tillamook is the
#      Cheesemakers, surely Jefferson can have the Sugar Beets somewhere."
#
# So a generic mascot is replaced by one that belongs to its SCHOOL'S OWN
# GROUND — read off the city, county and area on the record: the coast gets its
# fish, seals and crab boats; the Halbrook Basin gets the irrigation, the beet
# and onion fields and its Basque country; the Cascades get their salamanders
# and lava; Alderwold gets the logging trades. Not every generic is
# replaced — a state really does have some Eagles — but none is left at twenty.
#
# Keyed by DISPLAY name and applied at EMIT, the same as RENAMES, so a
# re-import cannot quietly revert them; everything internal still runs on the
# source record.
# ‼️ LEAGUE IDENTITY IS ITS OWN DATASET, NOT THE MAP (owner rule 2027-08).
# Every league used to be "<Jefferson area> District", which made the administrative
# geography and the league names one ontology — and real high-school athletics is
# nothing like that tidy. A league name is an institutional FOSSIL: it encodes
# geography, industries, former memberships, counties, rivers, old political
# regions, aspirational words, and things that made sense in 1964 and nobody
# changed. New Jersey runs a Cape-Atlantic League beside a Skyland and a Super
# Essex; Vermont has a Marble Valley League named for what the ground produced;
# Arizona is happy with one word (Fiesta, Sonoran, Premier). Massachusetts has a
# Dual County League, which sounds like administrative history rather than
# branding — because it is.
#
# So: A NAME NEED NOT DESCRIBE ITS CURRENT MEMBERS. Real league names persist
# through realignment, and the drift is the realism.
#
# ⚠️ SUFFIXES: League · Interscholastic League · Athletic Association · Athletic
# League · Assembly · Province · Organization · District (the plain legacy unit,
# kept deliberately — not every unit needs to be evocative). NEVER Conference,
# Division, Region, Ward, Zone, Section or Area: every one of those is a PLAYOFF
# unit in this association (`_RECOVERY_UNITS`, `_STAGE_NAMES`, `renumber_divisions`,
# `reletter_conferences`), and a league sharing a name with a bracket round is the
# ambiguity this whole pass exists to remove.
#
# `affinity` is a SOFT tug toward a region, not a rule: a name is preferred for a
# block sitting in that region and used anywhere once the preferred pool is spent.
LEAGUE_NAMES: list[tuple[str, str | None]] = [
    # -- coast and tidewater ------------------------------------------------
    # ‼️ REAL FINNISH PLACE NAMES, not Nordic-sounding coinages (owner rule
    # 2027-08). Ostrobothnia is the coastal province on the Gulf of Bothnia, so
    # it belongs on a working coast; the rest are small Finnish cities that have
    # no American namesake, which is the whole appeal — Sotkamo, Pori, Vimpeli
    # (the pesapallo town), Imatra, Kokkola, Rauma, Kajaani, Narpes.
    ("Ostrobothnia League", "Selquah"),
    ("Rauma Athletic Association", "Selquah"),
    ("Narpes Interscholastic League", "Selquah"),
    ("Pori League", "Selquah"),
    ("Tidelands League", "Selquah"),
    ("Sea View League", "Selquah"),
    ("Cape-Meridian League", "Selquah"),
    ("Breakwater Athletic Association", "Selquah"),
    ("Chinook League", "Selquah"),
    ("Mariners League", "Selquah"),
    ("South Coast League", "Sebastian Cape"),
    ("Surf League", "Sebastian Cape"),
    ("Pacific Coast League", "Sebastian Cape"),
    ("Coastal Range League", "Sebastian Cape"),
    ("Del Rey Athletic Association", "Sebastian Cape"),
    ("Gold Coast League", "Sebastian Cape"),
    ("Valley Coast Interscholastic League", "Sebastian Cape"),
    # -- the metropolitan middle --------------------------------------------
    ("Metro League", "Ashbury Metro"),
    ("Gateway League", "Ashbury Metro"),
    ("Greater Ashbury Interscholastic League", "Ashbury Metro"),
    ("Capital Athletic Association", "Ashbury Metro"),
    ("Crestview League", "Ashbury Metro"),
    ("Montview League", "Ashbury Metro"),
    ("Ambassador League", "Ashbury Metro"),
    ("Commonwealth League", "Ashbury Metro"),
    ("Liberty League", "Ashbury Metro"),
    ("Premier Athletic Association", "Ashbury Metro"),
    # -- basin and river ----------------------------------------------------
    # ⚠️ Affinity is matched at DRAW time, on the SOURCE area — before the
    # 2026-08 split_area pass runs at emit — so "Halbrook Basin" here still
    # covers the whole pre-split basin (today's Belmonte Metro, Boise Frontier
    # and the Vance side of Silver Basin included). Re-pointing an entry to a
    # post-split region name would make it never match; leave them keyed as-is.
    ("Halbrook Basin League", "Halbrook Basin"),
    ("Three Rivers League", "Halbrook Basin"),
    ("Upper Basin League", "Halbrook Basin"),
    ("Four Rivers Interscholastic League", "Halbrook Basin"),
    ("Dual County League", "Halbrook Basin"),
    ("Twin Counties Athletic Association", "Halbrook Basin"),
    ("River Valley League", "Halbrook Basin"),
    ("Big Basin League", "Halbrook Basin"),
    ("Forks League", "Halbrook Basin"),
    ("Confluence Athletic Association", "Halbrook Basin"),
    # -- gold country and the south -----------------------------------------
    ("Gold Valley League", "Gold Valley"),
    ("Placer League", "Gold Valley"),
    ("Sunkist League", "Gold Valley"),
    ("Valle Vista League", "Gold Valley"),
    ("Hacienda League", "Gold Valley"),
    ("Mission League", "Gold Valley"),
    ("Old Jefferson Athletic Association", "Southern Jefferson"),
    ("Sluice League", "Southern Jefferson"),
    ("Hydraulic League", "Southern Jefferson"),
    ("Assay Athletic Association", "Southern Jefferson"),
    ("Tailings League", "Southern Jefferson"),
    # -- mountains, high country, desert ------------------------------------
    ("Cascade Divide League", "Cascade Divide"),
    ("East Cascades League", "Cascade Divide"),
    ("Mountain Pass League", "Cascade Divide"),
    ("Summit League", "Cascade Divide"),
    ("Sky-Em League", "Cascade Divide"),
    ("Rim Country League", "Juniper Highlands"),
    ("High Desert League", "Juniper Highlands"),
    ("Juniper League", "Juniper Highlands"),
    ("Desert Sky League", "Juniper Highlands"),
    ("Intermountain Athletic Association", "Juniper Highlands"),
    ("High Lakes League", "Millersylvania"),
    ("North Range League", "Millersylvania"),
    ("Big Sky League", "Millersylvania"),
    ("Black Canyon League", "Millersylvania"),
    ("Basalt League", "Millersylvania"),
    # -- sage, plains and the interior --------------------------------------
    ("Sage Plains League", "Kangas"),
    ("Inland Empire League", "Kangas"),
    ("Far West League", "Kangas"),
    ("Golden West League", "Kangas"),
    ("Sunbelt League", "Kangas"),
    ("Wheatland Athletic Association", "Kangas"),
    ("Frontier League", "Kangas"),
    ("Kaleva League", "Kangas"),
    ("Vesterheim Athletic Association", "Kangas"),
    ("Norheim League", "Kangas"),
    ("Suomi Interscholastic League", "Kangas"),
    ("Vimpeli Athletic Association", "Kangas"),
    ("Imatra League", "Kangas"),
    ("Kajaani League", "Kangas"),
    ("Kokkola Athletic Association", "Kangas"),
    ("Pioneer League", "Kangas"),
    # -- timber and vermilion -----------------------------------------------
    ("Timber Valley League", "Alderwold"),
    ("Foundry League", "Alderwold"),
    ("Orchard League", "Alderwold"),
    ("Millworks Athletic Association", "Alderwold"),
    ("Cowapa League", "Alderwold"),
    ("Vermilion Valley League", "Yarrowmere"),
    ("Marble Valley League", "Yarrowmere"),
    ("Ironwood League", "Yarrowmere"),
    ("Quarry League", "Yarrowmere"),
    # -- unanchored: the names that outlived whatever they described --------
    ("Trinity League", None),
    ("Olympic League", None),
    ("Empire League", None),
    ("Ivy League", None),
    ("Union Athletic Association", None),
    ("Lewis & Clark League", None),
    ("PacWest League", None),
    ("Sea-King League", None),
    ("Skyland League", None),
    ("Fiesta Athletic Association", None),
    ("Sonoran League", None),
    ("Citrus Belt League", None),
    ("Del Rio League", None),
    ("Rio Hondo League", None),
    ("Southwest Assembly", None),
    ("Northwest Assembly", None),
    ("East Valley Assembly", None),
    ("Central Province", None),
    ("Western Province", None),
    ("Tri-County Organization", None),
    ("Charter Athletic Organization", None),
]


def league_names(blocks: list[list[dict]], group: str) -> list[str]:
    """A name per block, drawn from `LEAGUE_NAMES` rather than from the map.

    Deterministic: the bank is walked in an order seeded on the group, so a
    rebuild reproduces the same leagues and a league keeps its name across
    imports even as its membership shifts — which is the point.

    Selection prefers a name whose `affinity` matches the block's dominant area,
    then any unused name whose LEADING WORD is still free (so no two leagues in a
    class read as one), then any unused name at all. If the bank is somehow
    exhausted it falls through to a plain numbered District — the legacy
    bureaucratic unit, deliberately allowed — so this can never raise or repeat.
    """
    rng = random.Random(f"league|{SEED}|{group}")
    bank = LEAGUE_NAMES[:]
    rng.shuffle(bank)
    used: set[str] = set()
    heads: set[str] = set()
    out: list[str] = []
    for i, block in enumerate(blocks):
        area = Counter(s["area"] for s in block).most_common(1)[0][0] if block else None

        def pick(pred):
            return next((n for n, aff in bank
                         if n not in used and n.split()[0] not in heads and pred(aff)), None)

        name = (pick(lambda aff: aff == area) or pick(lambda aff: True)
                or next((n for n, _ in bank if n not in used), None)
                or f"District {i + 1}")
        used.add(name)
        heads.add(name.split()[0])
        out.append(name)
    return out


# ⚠️ THE FOREIGN-FAUNA CLEANUP (owner rule 2026-08). An earlier pass was asked to
# forage the world's animals so the association would not be five hundred Eagles.
# It worked — the head of the list now looks like a real state's — but it also left
# ~130 programs named after animals no American high school has ever put on a jersey:
# Muntjac (7 schools), Sitatunga, Bogongs, Serows, Saiga, Takin, Markhor, Nyala,
# Hamerkops, Shoebills, Kookaburras, Quolls, Numbats, plus a shelf of foraged
# insects. Owner: get rid of only the ones that make no sense, and expect overlaps,
# "like real life".
#
# ‼️ THE BAR IS "WOULD A US HIGH SCHOOL PUT THIS ON A JERSEY", NOT "IS IT OBSCURE".
# The genuinely strange American names are the best thing in the file and NONE of
# them is touched: Beetdiggers, Cornjerkers, Whistlepunks, Shingle Weavers,
# Highclimbers, Tie Hackers, Gandy Dancers, Cheesemongers, Onion Toppers, Hop
# Pickers, Sugarbeeters, Hardrockers, Orediggers, Lava Bears, Vaudevillians, Poets,
# Pelotaris, Bar Pilots, Fogbells. Every one of those has a real-world counterpart
# (Jordan HS Beetdiggers, Hoopeston Cornjerkers, Shelton Highclimbers, Bend Lava
# Bears, Whittier Poets, Tillamook Cheesemakers), and stripping them would leave
# exactly the generic head the foraging pass was run to avoid.
#
# Local fauna STAYS even when it is unusual — Ensatinas, Giant Salamanders, Kokanee,
# Sockeye, Steelhead, Chukars, Sage Grouse, Rockchucks, Skookums, Chinook — because
# it belongs to this ground. What goes is the fauna of other continents.
#
# Keyed on the MASCOT, not the school: the offending name is the thing that is
# wrong, so one entry fixes every program carrying it and any future import that
# draws it again. A pool rather than a single replacement, picked per school on a
# stable hash, so seven Muntjac do not become seven of anything else.
MASCOT_FIXES = {
    # ── hoofed exotics → the western hoofed stock a real school would use ──
    "Muntjac": ("Blacktails", "Bighorns", "Bucks", "Pronghorns", "Stags",
                "Mule Deer", "Elk"),
    "Sitatunga": ("Bighorns", "Rams", "Blacktails"),
    "Serows": ("Bighorns", "Rams"),
    "Saiga": ("Pronghorns", "Antelopes"),
    "Bharal": ("Bighorns",),
    "Takin": ("Bighorns", "Rams"),
    "Markhor": ("Rams", "Bighorns"),
    "Gerenuk": ("Pronghorns",),
    "Nyala": ("Blacktails", "Bucks"),
    "Chamois": ("Bighorns", "Blacktails"),
    "Tahr": ("Bighorns",),
    "Ibex": ("Bighorns", "Rams", "Stags"),
    "Dik-Diks": ("Blacktails",),
    "Bongos": ("Bucks", "Stags"),
    "Okapi": ("Blacktails",),
    "Wisent": ("Bison",),
    "Water Buffalo": ("Bison",),
    "Springbok": ("Pronghorns",),
    "Oryx": ("Pronghorns", "Longhorns"),
    # ── cats, canids and other exotic mammals → cougars and company ──
    "Snow Leopards": ("Lynx", "Cougars", "Bobcats", "Mountain Lions"),
    "Servals": ("Bobcats", "Lynx"),
    "Caracals": ("Bobcats",),
    "Maned Wolves": ("Coyotes", "Timberwolves", "Wolves", "Red Wolves"),
    "Dholes": ("Coyotes",),
    "Dingoes": ("Coyotes", "Timberwolves", "Wolves"),
    "Binturongs": ("Marmots", "Otters"),
    "Kinkajous": ("Raccoons", "Martens"),
    "Coatis": ("Raccoons",),
    "Langurs": ("Wolverines", "Badgers", "Bobcats", "Marmots", "Otters"),
    "Tapirs": ("Boars", "Bison", "Badgers"),
    "Pangolins": ("Porcupines", "Armadillos"),
    "Aardvarks": ("Badgers", "Porcupines"),
    "Meerkats": ("Prairie Dogs", "Marmots"),
    "Numbats": ("Flapjacks", "Chipmunks", "Marmots"),
    "Bilbies": ("Jackrabbits",),
    "Quolls": ("Martens", "Weasels"),
    "Wombats": ("Flapjacks",),
    "Stoats": ("Weasels", "Martens", "Badgers", "Wolverines"),
    # ── exotic birds → the birds actually overhead here ──
    "Hamerkops": ("Herons", "Kingfishers"),
    "Shoebills": ("Herons", "Egrets"),
    "Hoatzins": ("Herons", "Grebes"),
    "Oropendolas": ("Orioles",),
    "Weaverbirds": ("Kingfishers", "Orioles"),
    "Secretarybirds": ("Harriers",),
    "Capercaillie": ("Sage Grouse", "Chukars"),
    "Galahs": ("Kestrels", "Harriers"),
    "Kookaburras": ("Kingfishers", "Darkwings"),
    "Lyrebirds": ("Meadowlarks", "Kingfishers"),
    "Hornbills": ("Darkwings", "Ravens"),
    "Rheas": ("Cranes",),
    "Firecrests": ("Kestrels",),
    # ── the foraged insect shelf → the bugs American schools really use ──
    # Every name here is either already elsewhere in this association (Hornets,
    # Yellowjackets, Monarchs, Fireflies, Dragonflies) or a documented real one:
    # Alva High School, Oklahoma are the Goldbugs.
    "Bogongs": ("Wasps", "Honeybees", "Fireflies"),
    "Army Ants": ("Yellowjackets", "Fireflies"),
    "Giant Hornets": ("Hornets", "Wasps", "Yellowjackets"),
    "Goliath Beetles": ("Goldbugs", "Yellowjackets", "Hornets"),
    "Stag Beetles": ("Goldbugs", "Wasps", "Yellowjackets"),
    "Hornbeetles": ("Goldbugs", "Hornets", "Wasps"),
    "Leafcutters": ("Honeybees", "Monarchs"),
    "Weevils": ("Goldbugs", "Honeybees", "Fireflies"),
    "Katydids": ("Fireflies",),
    "Damselflies": ("Dragonflies",),
    "Mantids": ("Wasps", "Hornets", "Dragonflies"),
    "Locusts": ("Yellowjackets", "Hornets"),
    "Atlas Moths": ("Monarchs",),
    "Scarabs": ("Goldbugs",),
    # ── the rest ──
    # ‼️ OWNER-SUPPLIED NAMES (2026-08): Flapjacks, Darkwings, Daffies, Dandy Lions.
    # Placed in the pools they fit rather than assigned to a school by hand —
    # Flapjacks in timber country, Darkwings among the birds, the two botanical puns
    # where the berry-and-butte name was. They are exactly the register the American
    # oddities in this file already live in (Alva's Goldbugs, Effingham's Flaming
    # Hearts), which is why they belong in the pools and not in a special case.
    "Taipans": ("Sidewinders", "Rattlers", "Cobras"),
    "Frilled Lizards": ("Horned Lizards", "Sidewinders"),
    "Tuatara": ("Sidewinders",),
    "Moon Jellies": ("Tidepools", "Undertow"),
    # A berry and a butte, not a team: the one PNW-local word here that still reads
    # as a place rather than as a nickname.
    "Olallie": ("Huckleberries", "Brambles"),
}


def fix_mascot(display: str, mascot: str) -> str:
    """`mascot` unless it is one of the foreign-fauna names above, in which case a
    replacement drawn STABLY from that name's pool — the same school always lands on
    the same one, and two schools sharing a bad name usually do not share its fix."""
    pool = MASCOT_FIXES.get(mascot)
    if not pool:
        return mascot
    return pool[int(hashlib.sha1(f"{display}|mascot".encode()).hexdigest(), 16) % len(pool)]


MASCOTS = {
    # ── owner picks (2026-08) ──
    "Plainfield": "Cardinals",
    "Condotti Vanguard Academy": "Valiant",
    # ‼️ PINNED PER SCHOOL, NOT POOLED. Both were Olallie, and both names are the
    # owner's. A pool of two names over four schools kept dropping one of them
    # depending on how the hashes fell — a name you were given should not survive at
    # the mercy of a later pool edit, so the two botanical puns are placed by hand and
    # the pool keeps the rest.
    "Netherwood": "Dandy Lions",
    "Natchitoches": "Daffies",
    # ── the private-school layer (see the RENAMES block) ──────────────────
    # Real-world mascots where the institution has one everybody knows, which is
    # half of what makes the name land. ⚠️ NO AQUATIC ANIMALS (the rule at the head
    # of this table) — so Xavier Prep's real Gators are not reproduced here.
    "Mater Dei": "Monarchs",
    "Jesuit": "Crusaders",
    "Archbishop Gregory": "Griffins",
    "Sacred Heart": "Irish",
    "Bellarmine Prep": "Lions",
    "Valera": "Bulldogs",
    "Xavier College Prep": "Cavaliers",
    "St. Francis Catholic": "Lancers",
    "Christian Brothers": "Falcons",
    "Pointe Coupee Catholic": "Mustangs",
    "Starfield": "Celtics",
    "Pope Leo XIV": "Pilgrims",
    "Archbishop Valois": "Knights",
    "Evenfall": "Warriors",
    "St. Catherine Academy": "Wildcats",
    "Basalt Electric": "Matadors",
    "De La Salle": "Spartans",
    "Michaela East": "Eagles",
    "Sinkford": "Chanticleers",                 # the odd one, deliberately
    "Cardinal Newman": "Cardinals",
    "Calvary Christian": "Chargers",
    "Windward": "Stars",           # Stella Maris, star of the sea
    "South Rim": "Cougars",
    "Elkhorn": "Shepherds",
    "Evans Larsen Day": "Steeplejacks",         # owner naming, 2027-08
    "Chester A. Arthur": "Greenies",            # owner naming, 2027-08
    "Siskiyou Valley": "Prospectors",           # owner naming, 2027-08
    # ── Selquah: the working coast ────────────────────────────────────────
    "Port Ainsley": "Cormorants",          # Port Ainsley
    "Port Meridian South": "Mariners",
    "Veles Central": "Chinook",                    # the port itself
    "Port Veles North": "Whalers",
    "George Washington": "Sockeye",
    "Roscoe Bennett": "Cutthroat",
    "Gerald Ford": "Pelicans",
    "James Monroe": "Anchors",
    "St. Vincent": "Sailors",
    "Zachary Taylor": "Gillnetters",
    "Franklin Pierce": "Deckhands",
    "Kittery": "Fishmongers",               # the Port Veles fish market
    "Seafarer": "Trawlers",
    "Santa Michaela Admiralty High": "Commodores",
    "Bay Oregon": "Ospreys",
    "Bahía Azúl": "Dungeness Crabs",
    "Tide Point": "Riptide",                    # Fort Meriwether
    "Weller": "Storm Petrels",
    "Fort Weller": "Cheesemongers",             # the dairy coast
    "Ryken": "Kingfishers",                     # Newark River
    "Bracken": "Seals",                    # Wales City

    # ── South Coast: the southern shore and its canneries ────────────────────
    "Carolina Island": "Tule Elk",
    "Quarmont": "Stonecutters",
    "Asteroid City": "Sardines",             # Bahía Leal, a cannery town
    "Quarry Workers": "Lightkeepers",
    "Biloxi Heights": "Sea Otters",
    "Claudette Cole": "Godwits",
    "Talladega": "Moon Jellies",
    "Mission Bay": "Sea Lions",
    "San Borondón North": "Rockfish",
    "St. Jerome Academy": "Albatross",
    "Tatiana Chernov": "Sea Urchins",

    # ── Gold Valley: orchards, vineyards and the old diggings ────────────────
    "Bancroft": "Panners",
    "Bellacosta": "Vintners",
    "Cortland North": "Applejacks",             # Cortland, an apple
    "Elk Crossing": "Bull Elk",
    "Lake Esperanza": "Sturgeon",
    "Anchor Glass": "Waterwheels",           # Las Norias — "the waterwheels"
    "Las Norias": "Ditchriders",
    "Las Norias East": "Hullers",
    "Oscar Micheaux": "Marble Cutters",         # Monte Blanco
    "Golden Gate": "Bridgemen",
    "Montelago Central": "Grebes",
    "Lago Vista": "Hop Pickers",
    "Moriarty": "Jackrabbits",
    "Silver Glen": "Silversmiths",
    "St. Elian": "Abbots",
    "Shasta Agricultural": "Cellarmen",                # Valderra
    "Bishop Turner": "Orchardists",
    "Orchardgate": "Archangels",
    "Blue Mountain Grange": "Millwrights",       # Fellows Mill
    "Star City": "Cosmonauts",
    "Tomás Marín": "Beekeepers",

    # ── Halbrook Basin: canals, beet and onion ground, Basque country ────────
    "Ketanji Brown Jackson": "Pelotaris",              # Basque jai alai
    "Belmonte": "Canalmen",
    "Chillicothe": "River Otters",
    "Yazoo": "Sandhill Cranes",
    "Okefenokee": "Onion Toppers",
    "Pennsauken": "Stone Lifters",         # harri-jasotzaile
    "Kinnickinny": "Rapids",
    "Caney": "Sugar Beets",
    "Berrio": "Brambles",
    "Cherry Hill": "Cherry Pickers",
    "Paul Robeson": "Rivermen",
    "Juniper Crossing": "Switchmen",
    "Greaves Junction South": "Boxcars",
    "Doyle": "Bellringers",
    "Fruitvale": "Vaqueros",
    "Ella Baker": "Torchbearers",
    "Javier Cárdenas": "Roadrunners",
    "Llerena": "Bighorns",
    "Norwood Park": "Choristers",              # Madrigal
    "Madrigal": "Minstrels",
    "Serrano": "Chiles",                        # the pepper the town is named for
    "Arroyo Seco": "Sidewinders",             # and the snake
    "Coles Creek": "Sunflowers",
    "Borough Beach": "Woodchoppers",            # aizkolari
    "Petoskey Rock": "Burrowing Owls",
    "Friendship City": "Beet Haulers",
    "Bannock": "Lambs",                  # cordero
    "Morne Rouge": "Mobiles",
    "Granite Water & Power": "Fire Opals",               # Carden City
    "Drayfield": "Draymen",
    "Mae Jemison": "Orbiters",
    "William McKinley": "Buckeyes",
    "High Desert Cooperative": "Sheepwagons",             # Etchartville
    "Armour Fields": "Thunderheads",            # gromov — thunder
    "Springfield": "Headgates",                  # Orellana
    "Grizzly Gulch": "Riverboats",
    "Starlake": "Bull Trout",
    "Simmons": "Springers",               # a spring chinook, on a Springs town

    # ── Ashbury Metro: the city ──────────────────────────────────────────────
    "Ansotegui Siding": "Gandy Dancers",
    "Pinebluffs": "Semaphores",
    "Haverly": "Vaudevillians",
    "Hawk Lake Central": "Loons",
    "Pine Barrens": "Steelhead",
    "Southridge Christian": "Lamplighters",
    "St. Sebastian Prep": "Archers",            # the saint's own iconography
    "Dry Creek Cooperative": "Glassblowers",
    # ⚠️ Was keyed "Oskar Bellini" and had to move with the name: MASCOTS is keyed
    # on the DISPLAY name (see the emit block), so a rename silently orphans its
    # entry and the school quietly reverts to its source record's mascot.
    "Notre Dame": "Fighting Irish",
    "Dolores Huerta": "Grape Pickers",
    "Los Robles": "Live Oaks",                  # los robles — the oaks
    "Norview": "Peregrines",
    "Commonwealth": "Statesmen",

    # ── Cascade Divide: volcanic ground and wet forest ───────────────────────
    "Annie Springs": "Herons",
    "Crater View": "Calderas",
    "Draybrook Union": "Giant Salamanders",
    "Linden": "Rough Skins",                # the rough-skinned newt
    "Celia Browne": "Powderhorns",              # Fort Carden
    "Timber Crest": "Highclimbers",
    "New Leiden": "Pilgrims",
    "St. Sergius": "Northern Lights",
    "Orlova": "Firebirds",
    "Ransom Pass": "Cinder Cones",
    "Gwendolyn Brooks": "Poets",
    "Klamath Exchange": "Garnets",
    "San Cordero Central": "Lava Bears",
    "Mesa Verde": "Obsidians",
    "Tamarack": "Snowcaps",
    "Yarmere": "Ensatinas",                     # the salamander

    # ── Juniper Highlands: high desert ───────────────────────────────────────
    "Marlow County": "Sage Grouse",
    "Seamus Town": "Assayers",
    "Summervale": "Haymakers",
    "Star Hollow": "Pronghorns",
    "Thorn Summit": "Hawthorns",
    "Owl Canyon": "Screech Owls",
    "High Desert Christian": "Sojourners",
    "Marshall": "Jackalopes",
    "Meridian Regional": "Tinsmiths",           # Stovepipe
    "Pacersburg": "Kangaroo Rats",
    "Dry Lake": "Mirages",
    "Trout Lake": "Silverlegs",             # the ask: named for its own fish —
                                            # which swims in Klickitat County
                                            # too (the program relocated to WA
                                            # in the 2052 expansion)

    # ── Millersylvania: the mines and the snow ──────────────────────────────────
    "Galena": "Silver Kings",                   # galena — the silver-lead ore
    "Norstead": "Longships",
    "East Simmons": "Harbor Seals",
    "Elk Bluff": "Bugles",
    "Vonjo City": "Log Drivers",

    # ── Kangas: sagebrush, stock and the Finn settlements ────────────────────
    "Ninemile": "Freighters",
    "Clear Lake": "White Sage",
    "Galactica Plains": "Meadowlarks",
    "Ocean Park": "Woolgrowers",
    "River Market": "Joiners",                 # Dovetail
    "Cole Valley": "Ravens",                    # voronin — raven
    "Espoo": "Shearers",

    # ── Timber Valley: the woods trades ──────────────────────────────────────
    "Ansotegui": "Chokermen",
    "Bidwell": "Cruisers",                      # the timber cruiser
    "Gold Hollow": "Sluicers",
    "Pellmont": "Newts",
    "Ransoms Landing": "Muskrats",
    "Whistle Stop": "Whistlepunks",
    "Yarburg": "Shingle Weavers",
    "Salmon Bay": "Bruins",             # owner naming, 2027-08
}

# Two-colour crests: the FIRST is the crest ground and must be dark enough to
# carry the monogram, the second is the accent.
COLORS = {
    # rainbow trout: olive back over a silver flank
    "Trout Lake": ["#2F3328", "#C0C5CE"],
    "Caney": ["#4E1533", "#DED3B4"],      # beet root over refined sugar
    "Bahía Azúl": ["#173A5E", "#E0733A"],           # bay water, cooked crab
    "Yarmere": ["#2B2118", "#E08A2E"],              # the ensatina's orange
    "Pellmont": ["#3A2A1C", "#D96A2B"],             # a rough-skinned newt's belly
    "Galena": ["#2C2F36", "#B9BEC7"],               # the ore: lead grey, silver bright
}


_CANONICAL = {new: src for src, new in RENAMES.items()}   # display -> roster identity

# REGION RENAMES (owner rule 2027-08). A region name is Jefferson's own
# geography, not prep-network's, and it is applied at EMIT for the same reason
# school RENAMES are: everything upstream — district drawing, which sorts on
# `area` — runs on the source name, so renaming before the draw would reshuffle
# the leagues. The region also names its district ("<region> District"), so the
# rename carries there too.
#
# "Mother Lode" was the generic California gold-country label the owner rejected
# outright. The region is the state's southern end — Goldbank, Featherstone and
# Highgrade counties — so it is SOUTHERN JEFFERSON. (The D1 college of the same
# name is a different namespace; a region and a program can share a compass
# point the way a real state's do.)
AREA_RENAMES = {
    # ‼️ KEYED ON PREP-NETWORK'S CURRENT NAME. This read "Mother Lode" until 2026-08,
    # which that repo has since renamed to Siskiyou Valley — so the entry no longer
    # fired and a re-import would have emitted "Siskiyou Valley" for an area the
    # association has always called Southern Jefferson. Nothing showed it: the
    # committed data already held the right string, so only a full import would have
    # surfaced it. `scripts/jefferson_gazetteer.py` now compares the two area sets
    # on every run, which is what caught this.
    "Siskiyou Valley": "Southern Jefferson",
    # A wooded northern range deserves better than a compass bearing
    # (owner rule 2027-08). "North Range League" survives in the league
    # bank on purpose — a league name outliving the geography it was
    # named for is the fossil behaviour LEAGUE_NAMES exists to allow.
    "North Range": "Millersylvania",
    # Two more bearings-and-features, replaced with names of their own (owner
    # rule 2027-08). "South Coast" was a compass point plus a landform, and
    # "Timber Valley" was one of THREE X-Valley areas — Cape Sebastian is a real
    # Oregon headland inverted to the owner's "<name> Cape" shape, and a wold is
    # a wooded upland, so Alderwold says what Timber Valley said without being
    # the third Valley on the map.
    "South Coast": "Sebastian Cape",
    "Timber Valley": "Alderwold",
    # The last bare noun-plus-landform, and the NORDIC/FINNISH register the
    # owner asked for — which the real Pacific Northwest already carries
    # (Astoria's Finns, Naselle, Poulsbo, Ballard). "Kangas" is Finnish for the
    # dry pine heath, which is precisely what the region is, and a common
    # Finnish-American surname besides. One word, like Alderwold, Harborline
    # and Millersylvania.
    "Sage Plains": "Kangas",
    # A -mere is a lake or marsh, and yarrow grows on wet ground: YARROWMERE
    # retires the last spare X-Valley (Gold Valley keeps its, having gold under
    # it) in the archaic-English register Alderwold opened.
    "Vermilion Valley": "Yarrowmere",
    # ⚠️ SELQUAH IS INVENTED, and deliberately so. Jefferson stands on southern
    # Oregon and northern California ground, where the real coastal names are
    # indigenous — Chetco, Coquille, Umpqua, Siuslaw — and a map of that country
    # with none of that in it reads wrong. But a fictional state must not put a
    # REAL nation's name on a made-up region and a made-up school district: the
    # phonology is regional (the -quah ending Issaquah and Snoqualmie carry),
    # the word is not a people, a place or a language that exists. Coin in the
    # register; never borrow the referent.
    "Harborline": "Selquah",
}

# THE HALBROOK BASIN REGION SPLIT (owner rule 2026-08). The Halbrook Basin AREA
# had grown to ~222 girls'/~204 boys' programs — four times any other region —
# which mattered because All-Region is the association's newspaper all-area team
# (owner: "so many kids got screwed out of honors for years"): one ~18-selection
# team drawn from ~220 programs is the honour every ~55-program region hands out,
# stretched over four times the field. It splits into FOUR regions, and Silver
# Basin — until now a 3-program Ruby-County-only area below the All-Region
# 4-program floor — becomes one of them:
#
#   Belmonte Metro   Belmonte + Caswell (both Halbrook County cities)
#   Halbrook Basin   the rest of Halbrook County (name kept, region shrunk)
#   Boise Frontier   Barlowe County + Belyakov + Orellana (the two Vance County
#                    cities that stayed in the 1A-9A ladder)
#   Silver Basin     the rest of Vance County (the Group 1/2 departures) + Ruby
#                    County, which already carried the name
#
# Same named-table convention as RECLASSIFY_TO_2A: the mapping is a decision on
# counties and cities, not a threshold. Applied at EMIT beside AREA_RENAMES —
# district drawing sorts on the SOURCE area, so like every emit-time rename this
# cannot move a league; LEAGUE_NAMES affinities keyed "Halbrook Basin" therefore
# still fire at draw time and are left alone. `scripts/jefferson_gazetteer.py`
# applies the same function to prep-network's place rows so the two-repo area
# assertion keeps holding without an allowlist entry.
_SPLIT_METRO_CITIES = frozenset({"Belmonte", "Caswell"})      # Halbrook County
_SPLIT_FRONTIER_CITIES = frozenset({"Belyakov", "Orellana"})  # Vance County


def split_area(area: str, county: str, city: str) -> str:
    """The 2026-08 four-way Halbrook Basin split, keyed on county then city."""
    if area != "Halbrook Basin":
        return area
    if county == "Barlowe":
        return "Boise Frontier"
    if county == "Vance":
        return "Boise Frontier" if city in _SPLIT_FRONTIER_CITIES else "Silver Basin"
    if county == "Halbrook":
        return "Belmonte Metro" if city in _SPLIT_METRO_CITIES else "Halbrook Basin"
    # A county the owner's table does not name — leave it, loudly: this is a map
    # change nobody has decided on yet, not a default to absorb silently.
    print(f"WARNING: split_area: unmapped Halbrook Basin county {county!r} ({city})")
    return area

# RELOCATIONS (owner rule 2027-08) — a school MOVED to another town in its own
# area, keyed by SOURCE name and applied at emit like every other override.
# Gagarin already sponsors four programs, so the renamed Mother Lode goes to
# Copper Prairie, a one-school town in the same county — which keeps its
# district and its geography while taking the crowding off one city.
# ⚠️ The COUNTY follows the city (it is looked up from the city, not carried),
# so a relocation must stay inside the area the districts were drawn from.
# TOWN RENAMES (owner rule 2027-08) — the settlement itself, not a school.
# ⚠️ Applied AFTER the county lookup, which must run on the SOURCE name:
# prep-network's city table is keyed by the old name, so renaming first would
# emit an empty county. Same reason RELOCATIONS looks its town up before the
# rename is applied.
#
# Aldermont was the third Alder on the map (Alderwold the area, Alder Landing
# and Alderfield the towns) and a one-school fishing port besides, so it takes
# the cape: CAPE ANGELES, and its high school with it.
CITY_RENAMES = {
    # ‼️ THE STATE NEEDS AN EL PASO AND A FEW RIOS (owner, 2026-08) — a western state
    # of Jefferson's latitude and history would have them, and it had NONE: 283 towns,
    # 21 Spanish-form names, not one Rio and not one Paso. WEST El Paso deliberately,
    # so it is never mistaken for the Texas city. The four are spread across four
    # areas rather than clustered, and each keeps its town-named school in step —
    # a town called Rio Seco whose high school is still Ransom Spur is worse than
    # either name alone.
    "Gulch Bend": "West El Paso",     # Southern Jefferson, Goldbank — a gap in dry country
    "Ransom Spur": "Río Seco",        # Sebastian Cape, beside the state's other Spanish names
    "Basalt Fork": "Río Salado",      # Gold Valley, Ferris
    "Fig Gap": "Río Verde",           # Yarrowmere, Bardsley — orchard country
    "Aldermont": "Cape Angeles",
    # ‼️ REAL FINNISH CITIES, UNACCENTED (owner rule 2027-08). Small Finnish
    # towns with no American namesake, in the Kangas interior where the state's
    # Finns settled. The accents come OFF — an American town would not carry
    # them, which is exactly why Narpes and Riihimaki read as US place names and
    # Narpes and Riihimaki with diacritics do not.
    "Milldale": "Sotkamo",
    "Millview": "Kuusamo",
    "Kelview": "Iisalmi",
    "Standale": "Lieksa",
    "Elmfield": "Nurmes",
    "Stone Meadows": "Raahe",
    # ‼️ FORTS — it is the old West (owner rule 2027-08). The state had five and
    # every one of them sat on the coast or in the Cascades, which is backwards:
    # a frontier post belongs in the high desert, the gold country and the
    # interior, where these four go. Named the way real ones are — for an
    # officer. Fort Tabor stands on the Ewart, but the river keeps its own name
    # beside Ewart Bar and Ewart City, exactly as Fort Benton sits by Benton).
    # ‼️ A FORT IS NAMED FOR A PERSON (owner rule 2027-08). Almost every real
    # one carries an officer, an agent or a commander — Carden, Meriwether,
    # Lassiter, Wren, Ewart are surnames, and that is the whole naming grammar.
    # NOT a river, NOT a plant, and above all NOT a people: Fort Salish named a
    # nation the way no fort of that era was named, and it is now Fort Weller.
    # (The county or the river usually takes ITS name from the fort, not the
    # other way round — Bardsley County sits under Fort Bardsley.)
    "Silvale": "Fort Wren",
    "Ewartville": "Fort Tabor",
    # The rest of the Ewart valley, renamed with it (owner, 2027-08).
    "Ewart City": "Cook City",
    "Ewart Bar": "Fountain Park",
    "Marshdale": "Fort Lassiter",
    "Goodman": "Fort Bardsley",
    "Fort Rogue": "Fort Halloran",
    "Fort Salish": "Fort Weller",
    # ‼️ A SWEEP OVER THE COMMONPLACE TOWN NAMES (owner list, 2027-08). Every
    # one of these was a stock American compound — Silver Glen, Stone Springs,
    # Sage Meadows, Elk Prairie — the kind of name a generator reaches for and
    # a reader slides off. The SIMMONSES are deliberately scattered rather than
    # clustered: an East Coast state carries a Simmons and a North Simmons two
    # counties apart, named at different times for the same family, and nothing
    # about them has to be adjacent.
    "Alder Landing": "Bay Oregon",
    "Aspen Harbor": "East Simmons",
    "Cedarport": "North San Francisco",
    "Elk Prairie": "Carolina Island",
    "Granite Bar": "New Penzance Island",
    "Millport": "Vonjo City",
    "Sage Meadows": "Galactica Plains",
    "Sage Point": "California Canyons",
    
    "Stone Springs": "Simmons",
    "Trout Point": "North Simmons",
    "Walnut Yard": "South Simmons",
    "Alderfield": "Linden",
    "Sage Lake": "Sage Village",
    "Ashfield": "California Beach",
    "Garrity": "Texas Beach",
    "Graymont": "Georgia Mills",
    "Marsh Depot": "Jersey City",
    "Rentie Grove": "Jamaica",
    # ‼️ THE UPLANDS GET NAMES THAT SAY SO (owner, 2027-08). A third of the
    # state is upland and almost nothing on the map admitted it — one Mount,
    # no Pass, no Rim, no Summit, no Canyon — while the coast was thick with
    # Ports and Capes and the gold country announced itself constantly. These
    # encode elevation, passage, escarpment and volcanic ground, in the
    # Klamath/Modoc/Siskiyou register the real terrain has.
    "Ashwood": "Gruesome Ridge",
    "Aspen Meadows": "Mount Clambake",
    "Brackwood": "Brackwood Pass",
    "Clear Prairie": "Clear Rim",
    "Copper Crossing": "Copper Gap",
    "Dahlberg": "Dahlberg Summit",
    "Doyle Junction": "Doyle Pass",
    "Elmburg": "Mt Jacqueline",
    "Farleyford": "Aftdahl Ridge",
    "Gold Junction": "Seamus Town",
    "Harmon": "Annes Summit",
    "Hetfield": "Brynildson Hill",
    "Huckle Lake": "Mount Dylan Lake",
    "Norford": "Meridian Passage",
    "Ransom City": "Ransom Pass",
    "Silton": "Silton Ridge",
    "Thornford": "Thorn Summit",
    "Winvale": "Mount Ruth",
    "Wolf Gap": "Corey Canyon",
    "Wickbrook": "Salmon Bay",
    # Espoo (real Finnish city, no accent needed), New Bergen and New Ballard
    # (the American "New <old-country city>" convention — Bergen and Ballard
    # are both real maritime cities, which is why both land on the Selquah
    # coast) — owner list, 2027-08.
    "Keldale": "Espoo",
    "Tule": "New Bergen",
    "Rimrock": "New Ballard",
}

RELOCATIONS = {
    "Mother Lode": "Copper Prairie",
}

# ⚠️ Display names carry NO institutional suffix (owner rule 2027-08: "you don't
# need to have HS or High School ever, or even 'School' because nobody uses it").
# Applied at EMIT, exactly like RENAMES: everything internal (dice, districts,
# identity) runs on the source name, and `School.source` keeps the pre-strip name
# so pids never move. Only the TAIL strips — "San Cordero School of Commerce"
# ends in "Commerce" and is untouched.
_SUFFIX_RE = re.compile(r"\s+(High School|HS|School)$", re.IGNORECASE)


# "School of X" collapses (owner rule 2027-08, sharpened twice: "you just say
# San Cordero Commerce or Plainfield Science", then "Jesuit Sacramento is
# exactly what it'd be called. Just like Chicago or Boston Latin"):
#   * SUBJECT of-phrases collapse to the first subject — "Calder Science",
#     "Bronx Science" ("Science and Industry" truncates at "and").
#   * PLACE of-phrases collapse too — "Jesuit Sacramento", "Wilmington Charter".
#     ORDER follows usage: normally PRE + PLACE ("Jesuit Sacramento"), but the
#     classic type-named schools read PLACE + TYPE ("Chicago Latin",
#     "Boston English", "Wilmington Charter") — the _TYPE_FIRST set.
#   * "of the X" where X is NOT a subject stays whole ("Jewish Community High
#     School of the Bay", "Carnahan High School of the Future") — there is no
#     colloquial collapse for those.
#   * "College Preparatory School of" collapses like "School of", which is how
#     "Jesuit College Preparatory School of Dallas" reads "Jesuit Dallas".
_SUBJECTS = {"science", "technology", "commerce", "industry", "arts", "art",
             "design", "engineering", "public", "business", "agriculture",
             "agricultural", "medicine", "health", "law", "mathematics", "math",
             "media", "music", "leadership", "communication", "communications",
             "humanities", "advanced", "applied", "performing", "visual",
             "environmental", "innovation", "trades", "aviation"}
_TYPE_FIRST = {"latin", "english", "charter"}
# A CAMPUS QUALIFIER survives the subject truncation. The prep-network rebuild
# splits an over-cap school into directional campuses ("Jefferson School of
# Science and Technology North"), and truncating the subject at " and " used to
# take the qualifier with it — BOTH campuses collapsed to "Jefferson Science",
# and a display-name collision corrupts the archive (see `build`'s guard).
# "Bronx Science" usage keeps the campus: the split reads "Jefferson Science
# North".
_CAMPUS = {"north", "south", "east", "west",
           "northeast", "northwest", "southeast", "southwest"}
_SCHOOL_OF_RE = re.compile(
    r"^(?P<pre>.+?)\s+(?:(?:College\s+Preparatory|High)\s+)?Schools?\s+of\s+(?P<obj>.+)$",
    re.IGNORECASE)


def _collapse_school_of(name: str) -> str:
    m = _SCHOOL_OF_RE.match(name)
    if not m:
        return name
    pre, obj = m.group("pre"), m.group("obj")
    the = obj.lower().startswith("the ")
    if the:
        obj = obj[4:]
    if obj.split()[0].lower() in _SUBJECTS:
        keep = obj.split(" and ")[0].strip()
        tail = obj.split()[-1]
        if tail.lower() in _CAMPUS and not keep.lower().endswith(f" {tail.lower()}"):
            keep = f"{keep} {tail}"   # the campus rides the collapsed subject
        return f"{pre} {keep}"
    if the:
        return name                   # "of the Bay" / "of the Future" — the name
    if pre.lower().startswith("the "):
        pre = pre[4:]                 # "The Catholic ... of Baltimore" -> Catholic
    if pre.split()[-1].lower() in _TYPE_FIRST:
        return f"{obj} {pre}"         # Chicago Latin, Boston English
    return f"{pre} {obj}"             # Jesuit Sacramento


def _display_name(name: str) -> str:
    name = _collapse_school_of(name)
    while True:
        stripped = _SUFFIX_RE.sub("", name).strip()
        if stripped == name or not stripped:
            return name
        name = stripped


def canon(name: str) -> str:
    """A school's STABLE identity, whichever name prep-network currently uses.

    ‼️ This is what makes the import invariant to the source rename. The
    sponsorship dice are drawn positionally over a NAME-SORTED list, so once
    prep-network was renamed to match (`scripts/rename_prep_network.py`), the
    alphabet moved and every school inherited its neighbour's roll: measured, the
    association swapped a large slice of its membership and quietly re-admitted
    magnet schools this cleanup had just removed. Sorting and forcing on the
    canonical name reproduces the ORIGINAL order in BOTH states — pre-rename a
    source name misses the map and returns itself, post-rename a display name
    maps back — so the same schools sponsor tennis either way."""
    return _CANONICAL.get(name, name)


def champ_group(classification: str) -> str:
    """1A and 2A used to share one combined "2A-1A" group; they now crown
    SEPARATELY — 2A on the standard 40-team ladder since the 2033 realignment,
    1A on the fixed 24-team shape (`app.jhsaa._recovery_24`) — so this
    is an identity fold for every real classification."""
    return classification


GROUPS = ("9A", "8A", "7A", "6A", "5A", "4A", "3A", "2A", "1A",
          "Group 1", "Group 2", "Group 3")


def _load(prep: str) -> tuple[list[dict], dict[str, dict]]:
    orgs = os.path.join(prep, "records", "orgs")
    sp, cp = os.path.join(orgs, "schools.json"), os.path.join(orgs, "cities.json")
    for p in (sp, cp):
        if not os.path.exists(p):
            sys.exit(f"not found: {p}\nPoint --prep-network at a prep-network checkout.")
    with open(sp, encoding="utf-8") as fh:
        schools = json.load(fh)["schools"]
    with open(cp, encoding="utf-8") as fh:
        cities = json.load(fh)
    cities = cities["cities"] if isinstance(cities, dict) else cities
    return schools, {c["name"]: c for c in cities}


def always_sponsor() -> set[str]:
    """Schools that sponsor tennis because the OWNER says they do.

    ⚠️ Sponsorship below is a seeded coin flip per school against a per-classification
    rate — a reasonable way to pick ~335 tennis programs out of Jefferson's 840 schools,
    and a terrible way to decide whether a school the owner has named as a blue blood
    exists. Forty of the first seventy-eight archetype nominations landed outside the
    roll, which reads as "your list is wrong" when the truth is that a dice roll had
    already voted on it.

    So a named school is always in. Sourced from `data/jhsaa/archetypes.json` (the
    archetype seed list) plus `ALWAYS_EXTRA` for schools the owner wants in the
    association without tagging them. Names are matched accent- and punctuation-
    insensitively against prep-network, which is the source of truth for what exists."""
    out = set(ALWAYS_EXTRA)
    arch = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "jhsaa", "archetypes.json")
    try:
        with open(arch, encoding="utf-8") as fh:
            out |= set(json.load(fh).get("programs", {}))
    except (FileNotFoundError, ValueError):
        pass
    # ⚠️ `archetypes.json` is keyed by the name the ASSOCIATION uses (the emitted,
    # possibly renamed one) because `jhsaa.archetype()` looks a school up by the
    # name on its roster row. Forcing, though, happens against prep-network's
    # SOURCE names. So a renamed school's archetype entry has to be translated
    # back here, or it silently stops forcing that school into the association —
    # and, being a blue blood the dice never drew, it vanishes.
    back = {new: src for src, new in RENAMES.items()}
    return {back.get(n, n) for n in out}


def _key(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def sponsors(schools: list[dict]) -> tuple[set[str], set[str]]:
    """(girls, boys) school names. One roll for girls; boys drawn from that set — except
    that owner-named schools are in regardless, for both genders."""
    rng = random.Random(SEED)
    # Everything here keys on `canon()`, never the current name — see that
    # function. Forcing lists mix both vocabularies (archetypes.json is keyed by
    # the association's display name, ALWAYS_EXTRA by prep-network's), and
    # canonicalising both sides lands them on one identity.
    forced = {_key(canon(n)) for n in always_sponsor()}
    girls_only = {_key(canon(n)) for n in ALWAYS_GIRLS_ONLY}
    girls, boys = set(), set()
    for s in sorted(schools, key=lambda s: canon(s["name"])):  # stable order = stable draw
        hit = rng.random() < GIRLS_RATE[s["classification"]]  # drawn either way, so the
        sub = rng.random() < BOYS_OF_GIRLS                    # roll stays reproducible
        if _key(canon(s["name"])) in forced:
            girls.add(s["name"])
            if _key(canon(s["name"])) not in girls_only:
                boys.add(s["name"])
        elif hit:
            girls.add(s["name"])
            if sub:
                boys.add(s["name"])
    # THE FLAGSHIP PLAYS THE SPORT: hand each substituted magnet's seat to the
    # bare-named school in its city, per gender, after the draw (see
    # SUBSTITUTIONS). The bare school may also have been drawn on its own — sets
    # make that a no-op rather than a double entry.
    for side in (girls, boys):
        for magnet, flagship in SUBSTITUTIONS.items():
            if magnet in side:
                side.discard(magnet)
                side.add(flagship)
    # ‼️ AND THE SPONSORSHIP OVERRIDES, ALSO AFTER THE DRAW. Same reason as the
    # substitutions: the dice are positional over the name-sorted list, so adding
    # or removing a school before the roll reshuffles every school after it. These
    # have to be applied HERE and not only in `scripts/jhsaa_sponsors.py`, or a
    # full rebuild silently reverts them — a forced-in school the dice never drew
    # would vanish and a removed one would come back, with nothing to notice it.
    for side in (girls, boys):
        for name in EXTRA_SPONSORS:
            side.add(name)
        for name in NEVER_SPONSOR:
            side.discard(name)
    # ‼️ NO GIRLS-ONLY PROGRAMS AT THE 8A/9A LEVEL (owner rule 2026-08, "the
    # JHSAA mandated that all 8A/9A schools have to offer both"): in the
    # association's two deepest classes a girls sponsorship implies a boys
    # team, whatever the dice or ALWAYS_GIRLS_ONLY said — the mandate outranks
    # the exception table there. Applied AFTER every draw and override for the
    # same positional-dice reason those are, and re-asserted at the data level
    # by `scripts/jhsaa_2056_promotions.py` (transform scripts move schools
    # between classes after import) and pinned by
    # `test_no_girls_only_programs_at_8a_9a`.
    top = {s["name"] for s in schools if s["classification"] in ("8A", "9A")}
    boys |= girls & top
    return girls, boys


def draw_districts(pool: list[dict], cities: dict, group: str = "") -> dict[str, str]:
    """school name -> district name, for ONE classification group.

    Sorted by area → county → city so a district is geographically contiguous, then cut
    into the fewest balanced blocks of <= MAX_DISTRICT."""
    def county(s):
        return cities.get(s["city"], {}).get("county", "?")

    # `canon`, not the display name — same reason as `sponsors`: the blocks are cut
    # off this ORDER, so sorting on a name the owner can rename moves schools
    # between districts every time one is renamed.
    # ‼️ RIVALS SORT AS ONE SCHOOL. A rivalry has to survive a redraw, and the ordering
    # is what the blocks are cut from, so the pair takes its representative's place in
    # the sort and only tie-breaks among itself. Without this the two are ordered by
    # their own names — Condotti Vanguard Academy and Romero-Finniski are both in
    # Ashbury and sorted a whole alphabet apart, so a 7A redraw put them in different
    # leagues even though nothing had moved them.
    def order(s):
        pair = rival_group(s["name"])
        lead = by_pair.get(pair) if pair else None
        head = lead or s
        return (head["area"], county(head), head["city"], canon(head["name"]),
                canon(s["name"]))

    by_pair = {}
    for pair in RIVALRIES:
        members = sorted((s for s in pool if s["name"] in pair),
                         key=lambda s: canon(s["name"]))
        if members:
            by_pair[pair] = members[0]
    pool = sorted(pool, key=order)
    n = len(pool)
    if not n:
        return {}
    k = district_count(n)
    # ⚠️ SPREAD THE REMAINDER, don't dump it in the last block. Filling `k` blocks
    # of a fixed `ceil(n/k)` leaves the tail whatever is left over, which is fine
    # when it divides evenly and awful when it doesn't: 100 7A boys into blocks of
    # 12 gives eight full districts and a NINTH OF FOUR — an eight-dual league
    # season against everyone else's twenty-two, because district size IS the
    # schedule here. Sizes now differ by at most one (`n % k` blocks take the
    # extra), so the same 100 becomes one 12 and eight 11s.
    big, base = n % k, n // k
    bounds, at = [], 0
    for i in range(k):
        step = base + (1 if i < big else 0)
        end = min(n, at + step)
        # ‼️ AND A CUT NEVER FALLS INSIDE A RIVALRY. Sorting the pair adjacently is
        # not enough on its own — the boundary can still land between them, which is
        # precisely what happened — so the cut walks forward past any pair it would
        # split. That moves at most one school per rivalry into the earlier block,
        # keeping sizes within one of each other rather than exactly equal.
        while 0 < end < n and _splits_rivalry(pool, end):
            end += 1
        bounds.append((at, end))
        at = end
    # ‼️ THE NAME COMES FROM THE LEAGUE BANK, NOT FROM THIS BLOCK'S GEOGRAPHY
    # (owner rule 2027-08). Deriving it from the map is what produced eight
    # variations of "<area> District", and worse, an area-then-county cascade
    # that emitted "Halbrook Basin District" beside "Halbrook District" — an
    # area and a county inside it, reading as one league. `league_names` draws
    # from a separate dataset, keeps leading words distinct within the class,
    # and cannot raise or repeat. See LEAGUE_NAMES.
    blocks = [pool[lo:hi] for lo, hi in bounds if hi > lo]
    out = {}
    for block, name in zip(blocks, league_names(blocks, group)):
        for s in block:
            out[s["name"]] = name
    return out


def build(schools: list[dict], cities: dict) -> list[dict]:
    # ‼️ MASCOTS / COLORS / PRIVATE_SCHOOLS KEY ON THE **DISPLAY** NAME, so a rename
    # has to move their keys with it. Left behind, the lookup below misses and the
    # school silently reverts to prep-network's mascot — invisible in the committed
    # JSON, because the rename-only helper preserves whatever is already in the file
    # and only a FULL import exposes it. 29 keys had drifted before this check
    # existed. Checked here rather than in a test: build() is the one path where the
    # miss actually costs something.
    for tbl, name in ((MASCOTS, "MASCOTS"), (COLORS, "COLORS"),
                      (PRIVATE_SCHOOLS, "PRIVATE_SCHOOLS")):
        stale = sorted(k for k in tbl if k in RENAMES)
        if stale:
            raise SystemExit(
                f"{name} is keyed on {len(stale)} name(s) that RENAMES moves; move the "
                f"key to the new display name or the override is silently dropped: "
                + repr(stale[:5]))
    # ‼️ OWNER SIZE EDICTS (owner rule 2026-08) — schools whose prep-network
    # enrollment record is simply WRONG for what the school is in Jefferson's
    # fiction, corrected by decree. Keyed on the CANONICAL prep-network name
    # (renames land at emit, after this). Applied BEFORE reclassify() and the
    # district draw so classification, cut-line promotion and league placement
    # all run on the corrected number — patching the committed JSON alone would
    # last exactly one re-import.
    #
    # Evans Larsen Day: a day school of ~800, not the 2,181-student record its
    # source campus (the Ashbury science magnet's North split) carried — owner:
    # "Evans Larsen is a 4A school… the file has it wrong." Classification is
    # stated alongside the enrollment (both by decree) rather than re-derived:
    # the promotion cut lines only move schools UP, so they could never take a
    # mis-recorded 9A back down on their own.
    OWNER_SIZES = {
        "Jefferson School of Science and Technology North": (792, "4A"),
        # The rival pair (owner rule 2026-08): enrollment-level 3A academies.
        # Their DRAW classification stays 7A — that is the championship they
        # compete in, and the league draw runs on classification — with the
        # 3A truth and the 9A talent decree stamped at emit (OWNER_EMIT below).
        "Condotti Vanguard Academy": (531, "7A"),
        "Romero-Finniski": (507, "7A"),
    }
    for s in schools:
        if s["name"] in OWNER_SIZES:
            s["enrollment"], s["classification"] = OWNER_SIZES[s["name"]]
    moved = reclassify(schools)
    girls, boys = sponsors(schools)
    by_name = {s["name"]: s for s in schools}
    # ‼️ A LEAGUE IS A PROPERTY OF THE SCHOOL, NOT OF THE GENDER (owner rule
    # 2027-08). Boys and girls at one school ALWAYS play in the same league, so
    # the map is drawn ONCE per classification over every sponsor and both
    # gender fields read it. Drawing per gender gave a school two different
    # league names — invisible while every league was "<area> District" and
    # glaring the moment the names became distinctive.
    #
    # Blocks are balanced on the GIRLS-inclusive pool (girls sponsorship is the
    # superset), so a league's boys half is the ~88% of it that fields a boys
    # team. A league carrying eleven girls' teams and nine boys' is exactly how
    # this works in life; it is not an imbalance to correct.
    league = {}
    for g in GROUPS:
        pool = [by_name[n] for n in (girls | boys)
                if champ_group(by_name[n]["classification"]) == g]
        league.update(draw_districts(pool, cities, g))
    dist = {"girls": league, "boys": league}
    out = []
    for name in sorted(girls | boys):
        s = by_name[name]
        town = RELOCATIONS.get(name, s["city"])
        city = cities.get(town, {})          # county comes off the SOURCE town
        town = CITY_RENAMES.get(town, town)
        display = _display_name(RENAMES.get(name, name))
        # ‼️ The ROSTER IDENTITY (`jhsaa.School.source`), and it must be stable
        # forever — it seeds the RNG that builds a program's twelve players and
        # the pids on their records, so if it moves, every renamed school gets
        # twelve strangers and its archived awards point at nobody.
        #
        # Derived from the DISPLAY name through the inverse map, NOT from the
        # name prep-network currently uses, because prep-network is itself being
        # renamed to match (`scripts/rename_prep_network.py`). Once that lands,
        # `name` here IS the new name, `RENAMES.get` misses, and a source-side
        # identity would silently become the new name — churning every roster a
        # second time. Keying off the display name gives the same answer in both
        # states, which is the whole point. `RENAMES` is therefore a PERMANENT
        # historical record; do not prune it once prep-network is updated.
        canonical = canon(name)
        out.append({
            "name": display,
            # Only written when it differs — a school nobody renamed is its own
            # identity, and an absent key reads as "name" in `School.ident`.
            **({"source": canonical} if canonical != display else {}),
            "city": town,
            "county": city.get("county", ""),
            # Renamed at EMIT, like the school names — district drawing above
            # sorted on the SOURCE area, so this cannot move a league. The 2026-08
            # Halbrook Basin split runs on top, keyed on the emitted county/town.
            "area": split_area(AREA_RENAMES.get(s["area"], s["area"]),
                               city.get("county", ""), town),
            "classification": s["classification"],
            "group": champ_group(s["classification"]),
            "enrollment": s["enrollment"],
            # Only written when the school has one — absent means a core-city school.
            **({"locality": LOCALITIES[display]} if display in LOCALITIES else {}),
            # Renamed schools carry their institution's status, not the source
            # record's: a public high school that becomes Sacred Heart Cathedral
            # is a private school (see PRIVATE_SCHOOLS).
            "private": s["private"] or display in PRIVATE_SCHOOLS,
            # The per-school override first, then the foreign-fauna cleanup —
            # an owner pick is a decision and must outrank a table.
            "mascot": MASCOTS.get(display) or fix_mascot(display, s["mascot"]),
            "colors": COLORS.get(display, s["colors"]),
            "girls": name in girls,
            "boys": name in boys,
            # ‼️ NOT through `_area_ren`. League names come from LEAGUE_NAMES and
            # are never derived from the area, so running an area rename over them
            # would rewrite the FOSSILS the bank exists to keep — a North Range
            # League emitted as "Millersylvania League" is precisely the league
            # outliving its geography that the bank is designed to allow.
            "girls_district": dist["girls"].get(name, ""),
            "boys_district": dist["boys"].get(name, ""),
        })
    # ‼️ OWNER EMIT DECREES (owner rule 2026-08) — final-record corrections for
    # the rival pair, applied AFTER the draw ran on their competing class (7A,
    # via OWNER_SIZES above): the emitted record carries their TRUE size (3A)
    # while `group` keeps the 7A championship the draw placed them in, and
    # `talent` pins roster generation at the owner's stated 9A caliber —
    # `School.talent_group` reads it ahead of classification. Keyed on the
    # display name (this runs after renames).
    OWNER_EMIT = {
        "Condotti Vanguard Academy": {"classification": "3A", "talent": "9A"},
        "Romero-Finniski": {"classification": "3A", "talent": "9A"},
    }
    for r in out:
        if r["name"] in OWNER_EMIT:
            r.update(OWNER_EMIT[r["name"]])
    out.sort(key=lambda r: r["name"])     # renamed rows land at their NEW name
    # ‼️ A DISPLAY NAME IS THE ARCHIVE'S IDENTITY — it keys `run_season`'s teams
    # dict, `world_jhsaa_dual.school`, the school routes and the pid space. Two
    # schools sharing one name silently merge into one archive slot while the
    # standings carry both rows, so a program's record stops covering the duals
    # it played (this shipped once: both halves of a split campus collapsed to
    # "Jefferson Science" and the season archived a third school that was
    # neither). A collision is a missing RENAMES decision — stop, never emit.
    dupes = {n: c for n, c in Counter(r["name"] for r in out).items() if c > 1}
    if dupes:
        sys.exit(f"display-name collisions (add a RENAMES entry): {dupes}")
    return out


def report(rows: list[dict]) -> None:
    print(f"{'group':8}{'girls':>7}{'boys':>7}{'G dists':>9}{'B dists':>9}")
    for g in GROUPS:
        rs = [r for r in rows if r["group"] == g]
        gi = [r for r in rs if r["girls"]]
        bo = [r for r in rs if r["boys"]]
        print(f"{g:8}{len(gi):>7}{len(bo):>7}"
              f"{len({r['girls_district'] for r in gi}):>9}"
              f"{len({r['boys_district'] for r in bo}):>9}")
    gi = [r for r in rows if r["girls"]]
    bo = [r for r in rows if r["boys"]]
    print(f"{'TOTAL':8}{len(gi):>7}{len(bo):>7}")
    print(f"  {len(rows)} schools sponsor tennis; "
          f"{len(gi) - len(bo)} girls-only, {len([r for r in rows if r['boys'] and not r['girls']])} boys-only")
    # A district is keyed by (group, gender, name) — the same place name is reused
    # across classifications, exactly as "6A-1 PIL" and "5A-1 PIL" would be in Oregon.
    for gender, key in (("girls", "girls_district"), ("boys", "boys_district")):
        sizes = Counter((r["group"], r[key]) for r in rows if r[gender])
        big = [k for k, v in sizes.items() if v > MAX_DISTRICT]
        print(f"  {gender}: {len(sizes)} districts, sizes {min(sizes.values())}-{max(sizes.values())}"
              + (f"  OVERSIZED: {big}" if big else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    schools, cities = _load(args.prep_network)
    rows = build(schools, cities)
    report(rows)
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    os.makedirs(_OUT_DIR, exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_doc": ["JHSAA tennis-sponsoring schools with per-gender districts.",
                     "Generated by scripts/import_jhsaa.py from prep-network's",
                     "records/orgs/. Sponsorship is RE-DERIVED, not inherited —",
                     "see that script's docstring and",
                     "docs/DESIGN-jhsaa-high-school-season.md."],
            "schools": rows,
        }, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {os.path.relpath(_OUT, _REPO)}")


if __name__ == "__main__":
    main()

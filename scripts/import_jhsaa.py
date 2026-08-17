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
    "St. Agnes Preparatory",
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
    "Central Christian",
    "Chaminade",
    "Commonwealth",
    "Condotti Vanguard Academy",
    "Cortland",
    "Crown Hill",
    "Dolores Huerta",
    "Dry Lake",
    "Eastmont Christian",
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
    "North Valley Christian",
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
    "Saint Francis",
    "San Borondón",
    "San Cordero",
    "San Tomás",
    "Santa Cruz del Norte",
    "Santa Laura",
    "Santa Laura North",
    "Seafarer High",
    "Selbyville",
    "Silver Glen",
    "Sisters of Mercy",
    "Snowline",
    "St. Agnes Academy",
    "St. Basil Academy",
    "St. Gabriel Preparatory",
    "St. Isidore",
    "St. Norbert Abbey",
    "St. Perpetua",
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
    "St. Elias Academy",
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
OWNER_EDICTS = frozenset({
    # schools
    "Evans Larsen Day", "Chester A. Arthur", "Siskiyou Valley", "Cook City",
    "Fountain Park", "James K. Polk", "Lyndon B. Johnson", "William Howard Taft",
    "Earl Warren", "Sonia Sotomayor", "Ketanji Brown Jackson",
    "Sandra Day O'Connor", "Ruth Bader Ginsburg", "John Quincy Adams",
    "John F. Kennedy", "Western Sky",
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
    "Aftdahl Ridge", "Brynildson Hill", "Mount Henson",
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
RENAMES = {
    "Bahía Leal Costa Verde": "Housatonic",      # keeps its Warthogs
    "Belyakov Academy of Music and Media": "Belyakov North",
    "Belyakov Environmental Sciences Academy": "Belyakov South",
    "Belyakov I-50 Technical": "Belyakov East",
    "Belyakov Polytechnic Institute": "Belyakov West",
    "Belyakov School of Design and Engineering": "Theodore Roosevelt",
    "Belyakov School of Public Service": "Abraham Lincoln",
    "Belyakov School of Science and Industry": "Belyakov Technical",
    "Belmonte Agricultural Sciences Academy": "Belmonte North",
    "Belmonte Applied Sciences Institute": "Belmonte South",
    "Belmonte Civic Leadership Academy": "Belmonte East",
    "Belmonte Health Sciences Academy": "Belmonte West",
    "Belmonte Classical Academy": "James Madison",
    "Belmonte Technical Arts Academy": "Woodrow Wilson",
    "St. Basil School": "St. Ignatius",
    "Caswell Classical School": "Cherry Hill",
    "Caswell Depot High": "Cherry Hill North",
    "Caswell I-50 Technical": "Cherry Hill South",
    "Caswell School of Science and Industry": "Chester A. Arthur",
    "Caswell University Prep": "Caswell West",
    "Aldecoa Academy of Arts and Letters": "Aldecoa North",
    "Aldecoa Applied Sciences Institute": "Aldecoa South",
    "Aldecoa Depot High": "Ulysses Grant",
    "Echevarria Foundry High": "Echevarria North",
    "Echevarria I-50 Technical": "Echevarria South",
    "Echevarria School of Commerce": "William McKinley",
    "Orellana Foundry High": "Orellana North",
    "Orellana School of Commerce": "Orellana South",
    "Eagleton School of Science and Industry": "Eagleton West",
    "Port Veles Agricultural Sciences Academy": "Joe Biden",
    "Port Veles Civic Leadership Academy": "Veles Landing",
    "Nadia Sidorov": "John Adams",
    "Port Meridian Polytechnic": "Port Meridian North",
    "San Borondón Agricultural Sciences Academy": "San Borondón North",
    "San Borondón Environmental Sciences Academy": "San Borondón South",
    "Puerto de los Reyes International School": "Puerto de los Reyes North",
    "Puerto de los Reyes School of Commerce": "Puerto de los Reyes South",
    "Llerena Civic Leadership Academy": "Llerena North",
    "Llerena School of Science and Industry": "Llerena South",
    "Javier Villalba": "Alonso Villalba",
    "Serrano Applied Sciences Institute": "Serrano North",
    "Serrano Depot High": "Serrano South",
    "Halbrook Technical": "Halbrook East",
    "Greaves Junction Treasure Valley": "Greaves Junction South",
    "Cortland Environmental Sciences Academy": "Cortland North",
    "Cortland Foundry High": "Harry S. Truman",
    "Valderra Aviation and Engineering Academy": "Valderra North",
    "Valderra Technical Arts Academy": "Dwight Eisenhower",
    "Mercer City Technical Arts Academy": "Mercer City North",
    "Montelago Agricultural Sciences Academy": "Montelago South",
    "Moriarty Foundry High": "Moriarty West",
    "Las Norias Foundry High": "Las Norias East",
    "Lake Esperanza School of Science and Industry": "Lake Esperanza North",
    "Harriman Civic Leadership Academy": "Harriman North",
    "Harriman Maritime Academy": "John F. Kennedy",
    "San Cordero Maritime Academy": "San Cordero North",
    "San Cordero School of Commerce": "San Cordero South",
    "Fort Valois School of Design and Engineering": "Fort Valois North",
    "Gagarin School of Public Service": "Gagarin East",
    "Fellows Mill International School": "Fellows Mill South",
    "Rye Academy of Arts and Letters": "Rye North",
    "Ansotegui Siding Commonwealth": "Ansotegui Siding North",
    # Two St. Genevieves — a 1A in Benchton natively bare, a 6A whose suffix
    # strip collides with it. The bigger school takes the city, PRE + PLACE
    # ("Jesuit Sacramento"); the 1A keeps the name it always had.
    "St. Genevieve High School": "St. Genevieve San Cordero",
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
    "Fort Salish Independent School": "Fort Weller Independent",
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
    "Amaia Aramburu North": "Belmonte Catholic",
    # each of these is the school named for its town, moving with it
    "Ander Aramburu": "Western Sky",
    "Andrew Jackson North": "Caswell Heights",
    "Clara Cross": "Valderra Heights",
    "Evelyn Booker": "William Howard Taft",
    "Geraldine Cross": "Port Veles Episcopal",
    "Iker Aramburu": "Sandra Day O'Connor",
    "Iker Aramburu North": "Belmonte Heights",
    "Imani Cross": "San Borondón Heights",
    "Isaiah Booker": "Earl Warren",
    "John F. Kennedy North": "Harriman Heights",
    # ⚠️ Was plain "Echevarria" and had to move: prep-network now carries a school
    # of its own by that bare name (Dragons, 2,473, same city), so the two emitted
    # one display name and `build` refused — correctly, because a display name IS
    # the archive identity. Neither side is an owner edict, so the collision is
    # settled inside the existing family: North and South are already taken by
    # Foundry High and I-50 Technical, Central was free. The school's roster
    # identity is unaffected (pids key on `source`, still "Leire Aramburu").
    "Leire Aramburu": "Echevarria Central",
    "Lorna Booker": "Moriarty Heights",
    "Manuel Cordero": "Sonia Sotomayor",
    "Marian Cross": "Fort Valois Heights",
    "Nathaniel Cross": "Veles Harbor",
    "Nathaniel Cross North": "Port Veles Lutheran",
    "Nicolás Cordero": "Ruth Bader Ginsburg",
    "Pauli Booker": "Vespertine Heights",
    "Ralph Booker": "Barack Obama",
    "Ralph Booker North": "Port Veles Christian",
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
    "Amelia Freeman North": "Veles Area",
    "Anneliese Halvorsen": "George Washington",
    "Baptist HS": "Baptist",
    "Belmonte International School": "Belmonte International",
    "Calderwood School": "Calderwood",
    "Carroway School of Public Service": "Carroway Public Service",
    "Dahlberg School of Science and Industry": "Dahlberg Science",
    "Fort Valois School of Public Service": "Fort Valois Public Service",
    "Galina Markov": "James Monroe",
    "Harbor Gate North": "Martin Van Buren",
    "Harrow School of Design and Engineering": "Harrow Design",
    "Henrik Keller": "William Henry Harrison",
    "Housatonic HS": "Housatonic",
    "Igor Chernov": "Zachary Taylor",
    "Igor Chernov North": "Millard Fillmore",
    "Jefferson School of Science and Technology": "Jefferson Science",
    "Katherine Williams": "Franklin Pierce",
    "Marcus Langston": "Rutherford B. Hayes",
    "Marcus Langston North": "James Garfield",
    "Marina Moroz": "Grover Cleveland",
    "Marina Moroz North": "Benjamin Harrison",
    "Metropolitan Country Day School": "Metropolitan Country Day",
    "Nadia Chernov": "Calvin Coolidge",
    "Nadia Chernov North": "Franklin D. Roosevelt",
    "Opal Avery": "Gerald Ford",
    "Opal Avery North": "George H. W. Bush",
    "Pacific Friends School": "Pacific Friends",
    "Pinecrest School": "Pinecrest",
    "Port Veles East": "Bill Clinton",
    "Puerto Gallego School of Science and Industry": "Puerto Gallego Science",
    "Roscoe Bennett North": "Veles Point",
    "San Borondón Country Day School": "San Borondón Country Day",
    "Sofia Romanov": "Veles Basin",
    "Sofia Romanov North": "Veles Wharf",
    "St. Brigid School": "St. Brigid",
    "St. Casimir High School": "St. Casimir",
    "St. Elias School": "St. Elias",
    "St. Helena School": "St. Helena",
    "St. Sophia School": "St. Sophia",
    "St. Teresa High School": "St. Teresa",
    "St. Vincent School": "St. Vincent",
    "Starlight School of Science and Industry": "Starlight Science",
    "Telfair Country Day School": "Telfair Country Day",
    "Thelma Avery": "Veles Cove",
    "Walter Hart": "Veles Narrows",
    "Walter Hart North": "Veles Quay",
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
    "Wheatley": "Minnesota City",
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
    "Zoya Orlov": "Sacred Heart Cathedral",          # 8A Santa Michaela
    "Edith Hart": "Bellarmine Prep",                 # 8A — Prep, never Preparatory
    "Nicolás Treviño": "Bishop Valera",              # 7A — Jefferson surname
    "Harlan Tillman": "Xavier College Prep",         # 7A Mercer City
    "Amos Moss": "St. Francis Catholic",             # 7A Ashbury
    "Nikolai Markov": "Christian Brothers",          # 7A Sebastian Cape
    "Vernon Moss": "Cardinal Mercier",               # 6A — Jefferson surname
    "Naomi Ellison": "Providence Catholic",          # 6A Gold Valley
    "Jon Garmendia": "Pope Leo XIV",                 # 6A Halbrook Basin
    "Viktor Antonov": "Archbishop Valois",           # 5A — Jefferson surname
    "Marcus Mercer": "Cascade Christian",            # 5A Vespertine
    "Nathaniel Gaines": "St. Catherine Academy",     # 5A Ashbury
    "Andrés Valera": "Basalt Electric",               # 4A — Jefferson surname
    "César Mendoza": "De La Salle",                  # 4A Bellacosta
    "Irina Kovalenko": "Heritage Christian Academy", # 4A Selquah
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
    "Galina Moroz": "Our Lady of the Coast",         # 2A-1A — Sebastian Cape, coastal
    "Mikel Zubieta": "Cornerstone Christian",        # 2A-1A Clear Springs
    "Thomas Moreau": "Pope Francis",                 # 2A-1A Gold Valley
    # ‼️ NO ACCENTS (owner rule 2027-08, same as the Nordic town sweep):
    # an American town or school would not carry one. These three keep their
    # ALWAYS_EXTRA source spelling (it has to match prep-network) and rename
    # only at emit.
    "Soren Ekström": "Novak Russian Orthodox",
    "Svenja Ekström": "Cortland Memorial",
    "Thomas Ekström": "Montelago South",
    "Keldale": "Espoo",
    "Tule": "New Bergen",
    "Rimrock Valley": "New Ballard",
    "Montelago": "Montelago Central",
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
    "Anya Belov": "Arroyo Water District",
    "Claudette Freeman": "Alder Cooperative",
    "Eleanor Tillman": "Anchor Glass",
    "Elias Mercier": "Cascade Mutual",
    "Frances Gaines": "Empire Milling",
    "Garazi Mendizabal": "Cedar Exchange",
    "Harlan Cole": "Millrace Technical",
    "Harold Tillman": "Copper Belt",
    "James Gaines": "Rogue Valley Packing",
    "Janice Cole": "Fallon Works",
    "Jeannette Freeman": "Round Mountain Grange",
    "Katherine Davenport": "Blue Mountain Grange",
    "Lars Mercier": "Shasta Agricultural",
    "Lillian Price": "North Coast Packing",
    "Manuel Robles": "Pacific Fruit Exchange",
    "Mikel Echevarria": "Fir Valley Grange",
    "Naomi Price": "Crown Paper",
    "Naomi Ward": "Golden State Packing",
    "Nathaniel Ward": "Juniper Agricultural",
    "Nerea Mendizabal": "Silver Creek Irrigation",
    "Nicolás Salcedo": "Siskiyou Electric",
    "Opal Stokes": "Dry Creek Cooperative",
    "Opal Tillman": "Granite Water & Power",
    "Petra Jansen": "Southern Pacific Technical",
    "Rafael Escobedo": "Pioneer Electric",
    "Renata Adler": "Bracken Works",
    "Rosa Salcedo": "Quarry Workers",
    "Ruby Stokes": "Klamath Exchange",
    "Sadie Freeman": "High Desert Cooperative",
    "Sergei Belov": "Red Butte Cooperative",
    "Svenja Adler": "East Range Agricultural",
    "Teresa Escobedo": "Cañada Irrigation",
    "Thelma Stokes": "Iron Gate Works",
    "Thomas Jansen": "Lone Pine Mutual",
    "Winifred Davenport": "Lost River Irrigation",
    "Winifred Stokes": "Mesa Cooperative",
    "Xavier Robles": "Elk River Power",
    "Yelena Belov": "Spring Valley Cooperative",

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
    "Tatiana Moroz North":       "Caswell North",           # 8A Caswell
    "Harold Tillman North":      "Echevarria",              # 5A Echevarria
    "Katya Moroz":               "Emigrant",                # 7A Emigrant County
    "Carmen Valera":             "Ferris",                  # 9A Ferris County
    "Winifred Booker North":     "Fort Carden North",       # 6A Fort Carden
    "Beatrice Davenport":        "Fort Halloran",           # 4A Fort Halloran
    "Katya Moroz North":         "Harriman East",           # 8A Harriman
    "Thomas Jansen North":       "Lake Esperanza East",     # 5A Lake Esperanza
    "Gabriel Montoya":           "Marlow",                  # 4A Marlow County
    "Matteo Dahl":               "Montelago",               # 7A Montelago
    "Petra Bianchi":             "Perryville",              # 6A Perryville
    "Daniel Gaines North":       "San Borondón West",       # 7A San Borondón
    "Elena Petrov":              "San Marcos",              # 9A San Marcos County
    "Irina Kovalenko North":     "Santa Michaela North",    # 4A Santa Michaela
    "Galina Romanov":            "Stagewater",              # 9A Stagewater County
    "Svenja Bianchi":            "Tamarack",                # 9A Tamarack County
    "Carmen Cordero":            "Vance",                   # 9A Vance County
    "Salvador Figueroa":         "Vesper",                  # 4A Vesper
    "Klara Marchand":            "Weller",

    # ‼️ A SPECIALIZED SCHOOL'S NAME IS SHORT (owner rule 2026-08). Nobody says
    # "Manufacturing and Technology Academy" — a tech school is "<Place> Tech" and an
    # arts school is "<Place> Arts", the way Oakland School for the Arts is Oakland
    # Arts. The long descriptive form is a district's paperwork, not what anyone
    # calls it.
    "Academy of Arts and Communication":                "Ashbury Arts",
    "Altamonte Civic Leadership Academy":               "Altamonte Civic",
    "Belden Springs Academy of Music and Media":        "Belden Springs Arts",
    "Belyakov Agricultural Sciences Academy":           "Belyakov Agricultural",
    "Belyakov Technical":                               "Belyakov Tech",
    "Cabo Esperanza Technical Arts Academy":            "Cabo Esperanza Tech",
    "Featherstone Institute":                           "Featherstone Tech",
    "Fellows Mill Civic Leadership Academy":            "Fellows Mill Civic",
    "Greaves Aviation and Engineering Academy":         "Greaves Aviation",
    "Harrow Design":                                    "Harrow Arts",
    "Homecroft Manufacturing and Technology Academy":   "Homecroft Tech",
    "I-50 Technical":                                   "I-50 Tech",
    "I-50 Technical North":                             "I-50 Tech North",
    "Leidesdorff Academy of Music and Media":           "Leidesdorff Arts",
    "Millrace Technical":                               "Millrace Tech",
    "Northrup I-50 Technical":                          "Northrup I-50 Tech",
    "Paddock Institute":                                "Paddock Tech",
    "Perryville Civic Leadership Academy":              "Perryville Civic",
    "Port Veles Civic Academy":                         "Port Veles Civic",
    "Rostova Junction Technical Arts Academy":          "Rostova Junction Tech",
    "San Borondón Civic Academy":                       "San Borondón Civic",
    "San Telmo Agricultural Sciences Academy":          "San Telmo Agricultural",
    "Selbyville Manufacturing and Technology Academy":  "Selbyville Tech",
    "Southern Pacific Technical":                       "Southern Pacific Tech",
    "Vesper Polytechnic Institute":                     "Vesper Tech",
    "Zubieta Manufacturing and Technology Academy":     "Zubieta Tech",


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
    "Andrés Ibarra North":       "Belmonte Central",        # 4A Belmonte
    "Elena Mendoza North":       "Cedar Ridge",             # 6A Belmonte
    "Javier Alvarado North":     "Grandview",               # 6A Belmonte
    "Jean Lindgren North":       "Valderra South",          # 4A Valderra
    "Petra Weiss North":         "Las Colinas",             # 4A Valderra
    "Thelma Moss North":         "Valderra Central",        # 7A Valderra
    "Claudette Cole North":      "San Borondón Central",    # 5A San Borondón
    "Tatiana Chernov North":     "Bahía Vista",             # 6A San Borondón
    "Vernon Moss North":         "San Marcos Valley",       # 7A San Borondón
    "Mila Chernov North":        "Belyakov Central",        # 4A Belyakov
    "Viktor Antonov North":      "Pine Creek",              # 4A Belyakov
    "Andrés Valera North":       "Caswell South",           # 6A Caswell
    "Salvador Montalvo North":   "Stone Ridge",             # 6A Caswell
    "Marcus Price North":        "Lake Esperanza West",     # 4A Lake Esperanza
    "Ruby Stokes North":         "San Cordero West",        # 8A San Cordero
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
    "Sacred Heart Cathedral", "Bellarmine Prep", "Bishop Valera",
    "Xavier College Prep", "St. Francis Catholic", "Christian Brothers",
    "Cardinal Mercier", "Providence Catholic", "Pope Leo XIV",
    "Archbishop Valois", "St. Catherine Academy",
    "Cardinal Echevarria", "De La Salle", "Heritage Christian Academy",
    "Cascade Christian", "Sinkford",
    "Cardinal Newman", "Calvary Christian", "Our Lady of the Coast",
    "Cornerstone Christian", "Pope Francis",
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


MASCOTS = {
    # ── the private-school layer (see the RENAMES block) ──────────────────
    # Real-world mascots where the institution has one everybody knows, which is
    # half of what makes the name land. ⚠️ NO AQUATIC ANIMALS (the rule at the head
    # of this table) — so Xavier Prep's real Gators are not reproduced here.
    "Mater Dei": "Monarchs",
    "Jesuit": "Crusaders",
    "Archbishop Gregory": "Griffins",
    "Sacred Heart Cathedral": "Irish",
    "Bellarmine Prep": "Lions",
    "Bishop Valera": "Bulldogs",
    "Xavier College Prep": "Cavaliers",
    "St. Francis Catholic": "Lancers",
    "Christian Brothers": "Falcons",
    "Cardinal Mercier": "Mustangs",
    "Providence Catholic": "Celtics",
    "Pope Leo XIV": "Pilgrims",
    "Archbishop Valois": "Knights",
    "Cascade Christian": "Warriors",
    "St. Catherine Academy": "Wildcats",
    "Basalt Electric": "Matadors",
    "De La Salle": "Spartans",
    "Heritage Christian Academy": "Eagles",
    "Sinkford": "Chanticleers",                 # the odd one, deliberately
    "Cardinal Newman": "Cardinals",
    "Calvary Christian": "Chargers",
    "Our Lady of the Coast": "Stars",           # Stella Maris, star of the sea
    "Cornerstone Christian": "Cougars",
    "Pope Francis": "Shepherds",
    "Evans Larsen Day": "Steeplejacks",         # owner naming, 2027-08
    "Chester A. Arthur": "Greenies",            # owner naming, 2027-08
    "Siskiyou Valley": "Prospectors",           # owner naming, 2027-08
    # ── Selquah: the working coast ────────────────────────────────────────
    "St. Elias Academy": "Cormorants",          # Port Ainsley
    "Port Meridian South": "Mariners",
    "Port Veles": "Chinook",                    # the port itself
    "Port Veles North": "Whalers",
    "Anneliese Halvorsen": "Sockeye",
    "Roscoe Bennett": "Cutthroat",
    "Opal Avery": "Pelicans",
    "Galina Markov": "Anchors",
    "St. Vincent": "Sailors",
    "Igor Chernov": "Gillnetters",
    "Katherine Williams": "Deckhands",
    "Walter Hart": "Fishmongers",               # the Port Veles fish market
    "Seafarer High": "Trawlers",
    "Santa Michaela Admiralty High": "Commodores",
    "Alder Landing Beacon Hill": "Ospreys",
    "Bahía Azúl": "Dungeness Crabs",
    "Breakwater": "Riptide",                    # Fort Meriwether
    "Klara Marchand": "Storm Petrels",
    "Fort Salish": "Cheesemongers",             # the dairy coast
    "Ryken": "Kingfishers",                     # Newark River
    "Bracken Works": "Seals",                    # Wales City

    # ── South Coast: the southern shore and its canneries ────────────────────
    "Elk Prairie": "Tule Elk",
    "Quarmont": "Stonecutters",
    "Pacific Fruit Exchange": "Sardines",                # Bahía Leal, a cannery town
    "Quarry Workers": "Lightkeepers",
    "Adela Robles": "Sea Otters",
    "Claudette Cole": "Godwits",
    "Elena Petrov": "Moon Jellies",
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
    "Montelago South": "Hop Pickers",
    "Moriarty": "Jackrabbits",
    "Silver Glen": "Silversmiths",
    "St. Elian": "Abbots",
    "Shasta Agricultural": "Cellarmen",                # Valderra
    "Orchard Hill": "Orchardists",
    "St. Gabriel Preparatory": "Archangels",
    "Blue Mountain Grange": "Millwrights",       # Fellows Mill
    "Gagarin East": "Cosmonauts",
    "Tomás Marín": "Beekeepers",

    # ── Halbrook Basin: canals, beet and onion ground, Basque country ────────
    "Ketanji Brown Jackson": "Pelotaris",              # Basque jai alai
    "Belmonte": "Canalmen",
    "Belmonte River Plain": "River Otters",
    "Belmonte South": "Sandhill Cranes",
    "Javier Alvarado": "Onion Toppers",
    "Miren Elorriaga": "Stone Lifters",         # harri-jasotzaile
    "River Plain": "Rapids",
    "Treasure Valley": "Sugar Beets",
    "Berrio": "Brambles",
    "Andrés Valera": "Hay Balers",
    "Cherry Hill": "Cherry Pickers",
    "Paul Robeson": "Rivermen",
    "Greaves Junction": "Switchmen",
    "Greaves Junction South": "Boxcars",
    "Archbishop Doyle Prep": "Bellringers",
    "Vasquez": "Vaqueros",
    "Ella Baker": "Torchbearers",
    "Javier Cárdenas": "Roadrunners",
    "Llerena": "Bighorns",
    "Edith Tillman": "Choristers",              # Madrigal
    "Madrigal": "Minstrels",
    "Serrano": "Chiles",                        # the pepper the town is named for
    "Serrano North": "Sidewinders",             # and the snake
    "Pavel Kovalenko": "Sunflowers",
    "Aitor Zubieta": "Woodchoppers",            # aizkolari
    "Amalia Escobedo": "Burrowing Owls",
    "Belyakov South": "Beet Haulers",
    "Carmen Cordero": "Lambs",                  # cordero
    "Lorraine Calder": "Mobiles",
    "Granite Water & Power": "Fire Opals",               # Carden City
    "Drayfield": "Draymen",
    "Mae Jemison": "Orbiters",
    "William McKinley": "Buckeyes",
    "High Desert Cooperative": "Sheepwagons",             # Etchartville
    "Viktor Gromov": "Thunderheads",            # gromov — thunder
    "Canal View": "Headgates",                  # Orellana
    "Orellana North": "Riverboats",
    "Starlake": "Bull Trout",
    "Stone Springs": "Springers",               # a spring chinook, on a Springs town

    # ── Ashbury Metro: the city ──────────────────────────────────────────────
    "Ansotegui Siding": "Gandy Dancers",
    "Ansotegui Siding North": "Semaphores",
    "Haverly": "Vaudevillians",
    "Hawk Lake Central": "Loons",
    "Hawk Lake Southeast": "Steelhead",
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
    "Annie Springs Crater View": "Calderas",
    "Draybrook Union": "Giant Salamanders",
    "Alderfield": "Rough Skins",                # the rough-skinned newt
    "Celia Browne": "Powderhorns",              # Fort Carden
    "Timber Crest": "Highclimbers",
    "New Leiden": "Pilgrims",
    "Novak Russian Orthodox": "Northern Lights",
    "Orlova": "Firebirds",
    "Ransom City Union": "Cinder Cones",
    "Gwendolyn Brooks": "Poets",
    "Klamath Exchange": "Garnets",
    "San Cordero": "Lava Bears",
    "San Cordero South": "Obsidians",
    "Svenja Bianchi": "Snowcaps",
    "Yarmere": "Ensatinas",                     # the salamander

    # ── Juniper Highlands: high desert ───────────────────────────────────────
    "Marlow County": "Sage Grouse",
    "Gold Junction": "Assayers",
    "Summervale": "Haymakers",
    "Summervale Northwest": "Pronghorns",
    "Thornford": "Hawthorns",
    "Owl Canyon": "Screech Owls",
    "High Desert Christian": "Sojourners",
    "Marshall": "Jackalopes",
    "Meridian Regional": "Tinsmiths",           # Stovepipe
    "Telfair": "Kangaroo Rats",
    "Dry Lake": "Mirages",
    "Trout Lake": "Silverlegs",             # the ask: named for its own fish

    # ── Millersylvania: the mines and the snow ──────────────────────────────────
    "Galena": "Silver Kings",                   # galena — the silver-lead ore
    "Norstead": "Longships",
    "Aspen Harbor": "Harbor Seals",
    "Elk Bluff": "Bugles",
    "Millport": "Log Drivers",

    # ── Kangas: sagebrush, stock and the Finn settlements ────────────────────
    "Ninemile": "Freighters",
    "Alina Belov": "White Sage",
    "Sage Meadows": "Meadowlarks",
    "Garazi Aramburu": "Woolgrowers",
    "Marian Browne": "Joiners",                 # Dovetail
    "Lev Voronin": "Ravens",                    # voronin — raven
    "Keldale": "Shearers",

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
    "Treasure Valley": ["#4E1533", "#DED3B4"],      # beet root over refined sugar
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
    "Mother Lode": "Southern Jefferson",
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
    "Wheatley": "Minnesota City",
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
    "Plainfield": "Mount Henson",
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
    return (classification
            if classification in ("9A", "8A", "7A", "6A", "5A", "4A", "3A")
            else "2A-1A")


GROUPS = ("9A", "8A", "7A", "6A", "5A", "4A", "3A", "2A-1A")


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
    k = max(1, -(-n // MAX_DISTRICT))
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
            # sorted on the SOURCE area, so this cannot move a league.
            "area": AREA_RENAMES.get(s["area"], s["area"]),
            "classification": s["classification"],
            "group": champ_group(s["classification"]),
            "enrollment": s["enrollment"],
            # Renamed schools carry their institution's status, not the source
            # record's: a public high school that becomes Sacred Heart Cathedral
            # is a private school (see PRIVATE_SCHOOLS).
            "private": s["private"] or display in PRIVATE_SCHOOLS,
            "mascot": MASCOTS.get(display, s["mascot"]),
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

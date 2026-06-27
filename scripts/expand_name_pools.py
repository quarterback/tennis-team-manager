#!/usr/bin/env python3
"""Expand the generated-name pools with curated real names.

The pools are large already, but the most-drawn buckets — American given names
and the bigger international first-name buckets — are the tighter dimension a
player notices recurring. This adds real, correctly-bucketed names to those
pools (and grows `american_general`, which we also wire into the US first-name
union in regions.json). Idempotent: every add is de-duped against what's there,
so re-running is a no-op. Run `python scripts/scrub_name_pools.py` afterwards and
`pytest tests/test_name_pool_clean.py` to confirm no junk crept in.
"""
from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIR = os.path.join(_ROOT, "generators", "data", "names")


# --- additions, keyed by pool file then bucket -----------------------------

MALE_FIRST = {
    "american_general": (
        "Aaron Abel Abraham Adam Adrian Aidan Alan Albert Alec Alex Alexander Alfred "
        "Allen Alonzo Alvin Andre Andrew Angelo Anthony Antoine Archer Arlo August "
        "Augustus Austin Avery Barrett Beau Bennett Bernard Blaine Blake Bradford "
        "Bradley Brady Brandon Brantley Brendan Brennan Brett Brock Brooks Bryan "
        "Bryce Bryson Byron Cade Caleb Calvin Cameron Carl Carson Carter Casey Cash "
        "Cedric Chad Chance Chandler Channing Charles Chase Chester Christian "
        "Christopher Clark Clay Clayton Clement Cliff Clifford Clinton Clyde Cody "
        "Cole Colin Collin Colton Conner Conrad Cooper Corbin Cormac Cornelius Craig "
        "Curtis Dale Dallas Dalton Damien Damon Dane Daniel Darius Darnell Darrell "
        "Darren David Davis Dawson Dean Deandre Declan Delbert Dennis Denver Derek "
        "Desmond Devin Dexter Diego Dillon Dominic Donald Donovan Dorian Douglas "
        "Drake Drew Dustin Dwayne Dwight Earl Easton Eddie Edgar Edmund Edward Edwin "
        "Eli Elias Elijah Elliot Elliott Ellis Emanuel Emerson Emmett Enrique Eric "
        "Ernest Esteban Ethan Eugene Evan Everett Ezekiel Ezra Fabian Felix Ferdinand "
        "Fletcher Floyd Forrest Foster Francis Franklin Frederick Gabriel Gage Gardner "
        "Garrett Gavin Gene Geoffrey George Gerald Gideon Gilbert Glenn Gordon Grady "
        "Graham Grant Grayson Gregory Griffin Gus Hank Harlan Harold Harrison Harvey "
        "Hayden Heath Hector Henry Herbert Holden Houston Howard Hudson Hugh Hunter "
        "Ian Ignatius Isaac Isaiah Israel Ivan Jace Jack Jackson Jacob Jaden Jake "
        "Jamal Jared Jarrett Jasper Javier Jay Jayden Jefferson Jeffrey Jeremiah "
        "Jeremy Jerome Jesse Joaquin Joel John Jonah Jonathan Jordan Jorge Joseph "
        "Joshua Josiah Juan Judah Jude Julian Julius Justin Kade Kane Keaton Keith "
        "Kellen Kelvin Kendrick Kenneth Kent Kevin Kieran Kingston Knox Kobe Kody "
        "Kurt Kyle Kyler Lamar Lance Landon Lane Lawrence Layton Lee Leland Leo "
        "Leon Leonard Leroy Levi Lewis Liam Lincoln Lionel Lloyd Logan Lorenzo Louis "
        "Lucas Luther Lyle Mack Malachi Malcolm Marcus Mario Mark Marlon Marshall "
        "Martin Marvin Mason Mateo Matthew Maverick Maxwell Maynard Melvin Micah "
        "Michael Miguel Miles Milo Mitchell Morgan Moses Murphy Myles Nash Nathan "
        "Nathaniel Neil Nelson Nicholas Nico Noah Nolan Norman Oakley Octavio Oliver "
        "Omar Orion Orlando Oscar Owen Pablo Parker Patrick Paul Pedro Percy Perry "
        "Peter Philip Pierce Porter Preston Quentin Quincy Quinn Rafael Ralph Ramon "
        "Randall Randy Raphael Raymond Reece Reed Reginald Reid Remington Rene Reuben "
        "Rex Rhett Ricardo Richard Ricky Riley Robert Roberto Rocco Roderick Rodney "
        "Roger Roland Roman Ronald Rory Roscoe Ross Rowan Roy Ruben Rudolph Rufus "
        "Russell Ryan Ryder Ryker Sage Salvatore Samson Samuel Santiago Saul Sawyer "
        "Scott Sean Sebastian Seth Shane Shaun Sheldon Sherman Silas Simon Solomon "
        "Spencer Stanley Stefan Stephen Sterling Steven Stuart Sullivan Sylvester "
        "Tanner Tate Terrance Terrell Terry Theodore Thomas Timothy Titus Tobias "
        "Todd Tomas Tony Trace Travis Trent Trenton Trevor Tristan Troy Tucker Turner "
        "Tyler Tyrone Tyson Ulysses Uriah Valentin Vance Vaughn Vernon Victor Vincent "
        "Virgil Wade Walker Wallace Walter Warren Wayne Wesley Weston Wilbur Wiley "
        "Wilfred Will William Willie Willis Wilson Winston Wyatt Xavier Zachary Zane Zion"
    ),
    "latin_american": (
        "Agustin Alejandro Alfonso Alvaro Andres Anibal Aurelio Baltasar Benicio "
        "Bruno Camilo Cristobal Cruz Dario Dilan Efrain Emiliano Ernesto Ezequiel "
        "Facundo Federico Fernando Gael Gonzalo Gregorio Guillermo Horacio Ignacio "
        "Ismael Joaquin Julian Leandro Lautaro Lisandro Marcelo Mariano Mauricio "
        "Maximiliano Nahuel Nestor Octavio Ramiro Renato Rodrigo Rolando Salvador "
        "Santino Sebastian Teodoro Thiago Tobias Valentin Vicente Wilfredo Yago"
    ),
    "german": (
        "Andreas Bastian Bernd Christoph Dieter Dominik Fabian Florian Friedrich "
        "Gunther Hannes Heiko Helmut Jannik Jonas Jorg Kai Klaus Lennart Lukas "
        "Manfred Matthias Maximilian Moritz Niklas Reinhard Sebastian Stefan Sven "
        "Thorsten Tobias Uwe Volker Wolfgang"
    ),
    "japanese": (
        "Akira Daichi Daiki Eiji Haruki Haruto Hayato Hideki Hiroto Itsuki Kaito "
        "Kenta Kosuke Makoto Manabu Naoki Ren Riku Ryota Shota Sora Tatsuya Yamato "
        "Yoshiki Yuki Yusuke Yuto"
    ),
    "korean_north": (
        "Beom Chan Dae Donghyun Eun Gun Hyun Jae Jihoon Jin Jiwon Joon Junho Min "
        "Minho Minjun Sang Seojun Seung Shin Sung Tae Woojin Yeon Yong"
    ),
}

FEMALE_FIRST = {
    "american_general": (
        "Abigail Ada Adeline Adriana Aileen Alana Alexa Alexandra Alexis Alice "
        "Alicia Alina Allison Alondra Alyssa Amanda Amber Amelia Amy Ana Anabel "
        "Andrea Angela Angelina Anna Annabelle Annie Antonia April Arabella Aria "
        "Ariana Ashley Aubrey Audrey Aurora Autumn Ava Avery Bailey Beatrice Bella "
        "Bernadette Bethany Beverly Bianca Blair Blake Bonnie Brenda Briana Bridget "
        "Brielle Brittany Brooke Brooklyn Cadence Caitlin Callie Camila Camille "
        "Candace Cara Carla Carmen Carol Caroline Carolyn Cassandra Cassidy Catalina "
        "Catherine Cecilia Celeste Celia Charlotte Chelsea Cheryl Chloe Christina "
        "Christine Claire Clara Clarissa Claudia Colette Colleen Cora Courtney "
        "Crystal Cynthia Daisy Dakota Dana Daniela Danielle Daphne Darlene Dawn "
        "Deborah Delaney Delia Delilah Denise Diana Diane Dolores Dominique Donna "
        "Dora Doris Dorothy Eden Edith Eileen Elaine Eleanor Elena Eliana Elise "
        "Eliza Elizabeth Ella Ellen Ellie Eloise Elsa Emerson Emily Emma Erica Erin "
        "Esmeralda Esperanza Estelle Esther Eva Evelyn Faith Fatima Felicity Fern "
        "Fiona Florence Frances Francesca Freya Gabriela Gabrielle Genevieve Georgia "
        "Gianna Gina Giselle Gloria Grace Gracie Greta Gwen Gwendolyn Hadley Hailey "
        "Haley Hannah Harlow Harper Hazel Heather Heidi Helen Helena Holly Hope "
        "Imogen Ingrid Irene Iris Isabel Isabella Isabelle Isla Ivy Jacqueline Jada "
        "Jade Jane Janet Janice Jasmine Jaylen Jean Jenna Jennifer Jessica Jillian "
        "Joan Joanna Jocelyn Jolene Jordan Josephine Joy Joyce Judith Julia Juliana "
        "Julie Juliet Juniper Justine Kaitlyn Kara Karen Karina Kate Katelyn "
        "Katherine Kathleen Kathryn Katie Kayla Kaylee Keira Kelly Kelsey Kendall "
        "Kennedy Kiara Kimberly Kira Kourtney Kristen Kylie Lacey Laila Lana Lara "
        "Larissa Laura Lauren Layla Leah Leila Lena Leslie Lila Lilian Lillian Lily "
        "Lina Linda Lindsay Lisa Liv Logan London Lorelei Lorraine Louise Lucia "
        "Lucy Luna Lydia Mabel Mackenzie Madeline Madison Maeve Maggie Maia Makayla "
        "Mallory Mara Margaret Margot Maria Mariana Marie Marigold Marisol Marlene "
        "Martha Mary Maya Megan Melanie Melinda Melissa Melody Mercedes Meredith Mia "
        "Michaela Michelle Mila Mira Miranda Miriam Molly Monica Morgan Mya Myra "
        "Nadia Nancy Naomi Natalia Natalie Nayeli Nia Nicole Nina Noelle Nora Norma "
        "Nova Octavia Olive Olivia Opal Ophelia Paige Paloma Pamela Paola Patricia "
        "Paula Pauline Pearl Penelope Phoebe Polly Priscilla Quinn Rachel Ramona "
        "Raquel Raven Rebecca Regina Renata Rhonda Riley Rita Roberta Robin Rosa "
        "Rosalie Rose Rosemary Rowan Ruby Ruth Sabrina Sadie Sage Salma Samantha "
        "Sandra Sara Sarah Savannah Scarlett Selena Selina Serena Shannon Sharon "
        "Sheila Shelby Sienna Sierra Simone Sloane Sofia Sonia Sophia Sophie Stella "
        "Stephanie Summer Susan Susanna Sydney Sylvia Tabitha Talia Tamara Tara "
        "Tatiana Taylor Teresa Tessa Thea Theresa Tiffany Tina Tori Tracy Trinity "
        "Valentina Valeria Valerie Vanessa Vera Veronica Victoria Violet Virginia "
        "Vivian Wendy Whitney Willa Willow Wren Yara Yasmin Yolanda Yvette Yvonne "
        "Zara Zoe Zoey"
    ),
    "latin_american": (
        "Abril Adriana Alejandra Antonella Araceli Beatriz Brisa Carolina Catalina "
        "Constanza Dolores Elena Emilia Esperanza Florencia Guadalupe Ines Isidora "
        "Josefina Lucia Magdalena Manuela Martina Mercedes Micaela Milagros Pilar "
        "Renata Rocio Soledad Trinidad Ximena Yamila"
    ),
    "german": (
        "Annika Birgit Brigitte Claudia Elke Franziska Gisela Greta Hannelore Heike "
        "Helga Ingrid Johanna Katharina Lena Lisa Magdalena Marlene Petra Sabine "
        "Sigrid Steffi Ute Vanessa Wiebke"
    ),
}

SURNAMES = {
    "american_general": (
        "Abbott Acosta Adkins Aguilar Albright Alderman Aldridge Ali Alvarado Ambrose "
        "Archer Ashby Atkinson Atwood Ayers Babcock Bachman Baldwin Ballard Banks "
        "Barber Barlow Barnett Barron Bartlett Bassett Beach Beasley Beaumont Beckett "
        "Bellamy Benton Bergeron Bishop Blackburn Blackwell Blanchard Bledsoe Bolton "
        "Bond Boone Booth Bowers Bowman Boyle Brackett Bradshaw Brady Bramble Branch "
        "Brennan Brewer Bridges Briggs Brockman Bronson Brooks Broughton Buckley "
        "Burnett Burns Byrd Cahill Calloway Camden Cantrell Carmichael Carpenter "
        "Carrington Carver Cassidy Castle Caswell Chamberlain Chandler Chapman "
        "Charlton Chastain Childress Christensen Clancy Clifton Cochran Coffey Colby "
        "Coleman Collier Colton Conley Connolly Conway Corbin Cormier Cortland "
        "Cottrell Crandall Crawford Creighton Crockett Cromwell Crosby Cunningham "
        "Dalton Darby Davenport Dawson Delgado Dempsey Dennison Devlin Dickerson "
        "Dillon Dobson Dodson Donovan Dorsey Doyle Draper Driscoll Dudley Duffy "
        "Dunbar Durham Eaton Eckert Eldridge Ellington Ellsworth Emerson Endicott "
        "Ericson Ewing Fairchild Falkner Farrell Faulkner Fenwick Ferris Finch "
        "Finnegan Fitzgerald Fleming Fletcher Flynn Forbes Forsythe Foster Fowler "
        "Frazier Frost Fulton Gage Gallagher Galloway Gannon Gardner Garland Garrett "
        "Garrison Gentry Gibbs Gilman Glover Goddard Goodwin Gould Grady Granger "
        "Grantham Greer Gresham Griffith Grimes Hadley Hale Halloran Halsey Hamlin "
        "Hammond Hancock Hanley Harlow Harmon Harrington Hartley Hastings Hawkins "
        "Hayden Haywood Heath Hendricks Herrington Hewitt Hickman Hines Hobbs Hodges "
        "Holbrook Holcomb Holland Hollis Holloway Holt Hopkins Hutchins Ingram "
        "Ironside Jarrett Jennings Kane Keating Keller Kendall Kennedy Kenyon Kerr "
        "Kilgore Kimball Kingsley Kirby Kirkland Knowles Lambert Lancaster Landry "
        "Langley Larkin Latham Lawson Ledford Leighton Lennox Lindsey Linton "
        "Livingston Lockhart Lockwood Lowell Lyman Mabry Macdonald Maddox Mahoney "
        "Mallory Manning Marsden Marsh Mason Mathers Mayfield Mcallister Mcbride "
        "Mccarthy Mcgrath Mcintyre Mckinley Mclean Mcpherson Mead Mercer Merritt "
        "Middleton Milburn Millard Milne Monroe Montague Moody Mooney Moran Morrow "
        "Mortimer Mosley Mowbray Mullins Murdock Murphy Nash Naylor Nesbitt Newcomb "
        "Newport Nixon Noble Nolan Norris Northcott Norwood Oakley Oconnell Odell "
        "Ogden Oliver Olsen Orton Osborne Overton Padgett Paige Palmer Parrish Patton "
        "Payne Pemberton Pendleton Penrose Perkins Perry Pickering Pierce Pollard "
        "Prescott Preston Prosser Pruitt Purcell Quinn Radcliffe Rafferty Ramsey "
        "Randall Rankin Ratcliffe Redding Redmond Reeves Renfrow Renwick Rhodes "
        "Ridley Riggs Riley Rivers Roach Roberson Rockwell Rooney Rowe Rowland "
        "Rutherford Ryder Salisbury Sampson Sanborn Sanderson Sargent Saunders "
        "Sawyer Schofield Seaton Sedgwick Selby Severson Sexton Seymour Shackleton "
        "Sharpe Shaw Sheldon Shelton Shepherd Sheridan Sherwood Shipley Sinclair "
        "Skinner Slade Sloan Snyder Somers Spalding Sparrow Spence Stanton Stapleton "
        "Stark Steele Sterling Stevenson Stoddard Stokes Stratton Sullivan Sutton "
        "Swanson Sweeney Talbot Tanner Tate Teague Templeton Thatcher Thornton "
        "Thurston Tilden Tillman Townsend Tracy Trent Truman Tucker Turner Tuttle "
        "Underhill Underwood Upton Vance Vaughn Wade Wakefield Waldron Walker Wallace "
        "Walsh Walton Warner Warren Waterman Watkins Weaver Webster Welch Weldon "
        "Wells Wendell Wentworth Westbrook Wheaton Wheeler Whitaker Whitfield "
        "Whitman Whitmore Wilder Willis Winslow Winston Winters Witherspoon Wolcott "
        "Woodard Woodbury Woodson Worthington Wright Wyatt Yates Yeats York Zimmerman"
    ),
    "latin_american": (
        "Abalos Aguirre Alcaraz Alfaro Aragon Arce Arevalo Arroyo Avila Ballesteros "
        "Barragan Bermudez Bustamante Caballero Cabrera Camacho Carrasco Cazares "
        "Cervantes Cisneros Cordero Cuellar Davila Echeverria Escalante Escobar "
        "Fuentes Gallardo Gallegos Galvan Granados Guevara Hinojosa Ibarra Jurado "
        "Lozano Maldonado Marquez Mejia Montero Naranjo Olivares Ordonez Pacheco "
        "Palacios Pizarro Quintero Reyes Robledo Salcedo Samaniego Sandoval Tamayo "
        "Tapia Trejo Urbina Valdez Vega Velez Villalobos Zambrano Zapata Zavala"
    ),
    "german": (
        "Bauer Brandt Busch Dietrich Engel Fischer Frank Franke Frey Gross Haas "
        "Hahn Hartmann Herrmann Hofmann Horn Huber Jung Kaiser Keller Klein Koch "
        "Kraus Kruger Lang Lehmann Lorenz Maier Meyer Neumann Peters Richter Schmidt "
        "Schneider Scholz Schreiber Schulz Schuster Schwarz Seidel Vogel Voigt Wagner "
        "Weber Werner Winkler Wolf Ziegler Zimmer"
    ),
    "japanese": (
        "Aoki Endo Fujimoto Fukuda Hara Hashimoto Ikeda Inoue Ishii Kato Kimura "
        "Kobayashi Kondo Maeda Matsumoto Morita Nakajima Nakamura Ogawa Okada Saito "
        "Sasaki Shimizu Takahashi Tanaka Watanabe Yamada Yamamoto Yoshida"
    ),
}


# Place-name given names (real, modern, largely unisex) — added to BOTH the male
# and female American pools so they actually appear. Kept from the city scrubber
# by LEGIT_FIRST_NAME_KEEP in scripts/scrub_name_pools.py.
GEO_GIVEN = ("Aspen Austin Boston Brooklyn Camden Carolina Cheyenne Dakota Dallas "
             "Denver Houston Kingston London Memphis Montana Orlando Phoenix "
             "Savannah Sydney Trenton Weston")
MALE_FIRST["american_general"] += " " + GEO_GIVEN
FEMALE_FIRST["american_general"] += " " + GEO_GIVEN


def _add(fname: str, additions: dict[str, str]) -> tuple[int, int]:
    path = os.path.join(_DIR, fname + ".json")
    data = json.load(open(path, encoding="utf-8"))
    added = 0
    for bucket, blob in additions.items():
        existing = data.setdefault(bucket, [])
        seen = set(existing)
        for name in blob.split():
            if name not in seen:
                existing.append(name)
                seen.add(name)
                added += 1
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return added, sum(len(v) for v in data.values())


def main() -> None:
    for fname, adds in (("male_first", MALE_FIRST),
                        ("female_first", FEMALE_FIRST),
                        ("surnames", SURNAMES)):
        added, total = _add(fname, adds)
        print(f"{fname}: +{added} new names (pool now {total})")


if __name__ == "__main__":
    main()

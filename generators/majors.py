"""
College majors for player bios — mostly real, a few invented for flavor.
`pick_major(rng)` draws one deterministically from a seeded Random.
"""
from __future__ import annotations

import random

# ~Real majors (the bulk).
_REAL = [
    "Accounting", "Actuarial Science", "Aerospace Engineering", "African American Studies",
    "Agricultural Business", "American Studies", "Anthropology", "Applied Mathematics",
    "Architecture", "Art History", "Astronomy", "Astrophysics", "Athletic Training",
    "Biochemistry", "Bioengineering", "Biology", "Biomedical Engineering", "Botany",
    "Business Administration", "Business Analytics", "Chemical Engineering", "Chemistry",
    "Civil Engineering", "Classics", "Cognitive Science", "Communications",
    "Comparative Literature", "Computer Engineering", "Computer Science", "Construction Management",
    "Criminal Justice", "Criminology", "Cybersecurity", "Dance", "Data Science", "Dentistry",
    "Earth Science", "Ecology", "Economics", "Education", "Electrical Engineering",
    "Elementary Education", "English", "Entrepreneurship", "Environmental Engineering",
    "Environmental Science", "Environmental Studies", "Exercise Science", "Film Studies",
    "Finance", "Fine Arts", "Food Science", "Forestry", "French", "Game Design", "Genetics",
    "Geography", "Geology", "German", "Graphic Design", "Health Sciences", "History",
    "Hospitality Management", "Human Development", "Human Resources", "Industrial Engineering",
    "Information Systems", "Information Technology", "Interior Design", "International Business",
    "International Relations", "Italian", "Japanese", "Journalism", "Kinesiology",
    "Landscape Architecture", "Linguistics", "Management", "Marine Biology", "Marketing",
    "Materials Science", "Mathematics", "Mechanical Engineering", "Media Studies",
    "Microbiology", "Molecular Biology", "Music", "Music Education", "Music Performance",
    "Nanotechnology", "Neuroscience", "Nursing", "Nutrition", "Occupational Therapy",
    "Operations Management", "Optometry", "Organizational Leadership", "Petroleum Engineering",
    "Pharmacy", "Philosophy", "Photography", "Physical Therapy", "Physics", "Physiology",
    "Political Science", "Pre-Dental", "Pre-Law", "Pre-Med", "Psychology", "Public Health",
    "Public Policy", "Public Relations", "Real Estate", "Religious Studies", "Robotics",
    "Russian", "Social Work", "Sociology", "Software Engineering", "Spanish",
    "Special Education", "Sport Management", "Statistics", "Supply Chain Management",
    "Sustainability Studies", "Theater", "Theology", "Urban Planning", "Veterinary Science",
    "Women's & Gender Studies", "Zoology", "Architectural Engineering", "Biostatistics",
    "Chemistry Education", "Digital Media", "Electrical & Computer Engineering",
    "Environmental Policy", "Health Administration", "Mechatronics", "Quantitative Economics",
    "Sports Medicine", "Wildlife Conservation", "Agronomy", "Apparel Design", "Audiology",
    "Aviation Management", "Biophysics", "Computational Biology", "Creative Writing",
    "Dietetics", "Epidemiology", "Geophysics", "Industrial Design", "Marine Science",
    "Meteorology", "Oceanography", "Paleontology", "Recreation Management", "Speech Pathology",
    "Textile Engineering", "Toxicology", "Viticulture & Enology", "Welding Engineering",
    # Languages, humanities & culture
    "Arabic", "Mandarin Chinese", "Korean", "Portuguese", "Latin", "Modern Greek", "Hebrew",
    "Hindi", "Swahili", "Slavic Studies", "Medieval Studies", "Renaissance Studies",
    "Folklore Studies", "Rhetoric", "Ethnomusicology", "Museum Studies", "Library Science",
    "Translation & Interpretation", "Digital Humanities", "Semiotics", "Archaeology",
    # Social sciences & area studies
    "Peace & Conflict Studies", "Development Studies", "Demography", "Public Administration",
    "Gerontology", "Disability Studies", "Latin American Studies", "East Asian Studies",
    "Middle Eastern Studies", "European Studies", "Indigenous Studies", "Behavioral Economics",
    "Political Economy", "Social Policy", "Forensic Psychology",
    # Arts & design
    "Ceramics", "Sculpture", "Printmaking", "Illustration", "Animation", "Fashion Design",
    "Costume Design", "Musical Theater", "Jazz Studies", "Studio Art", "Sound Design",
    "Screenwriting", "Arts Administration", "Art Education",
    # Business
    "Sales & Sales Management", "Risk Management", "Taxation", "Digital Marketing",
    "Fashion Merchandising", "Sports Marketing", "Innovation Management", "Tourism Management",
    # Health & clinical
    "Respiratory Therapy", "Medical Laboratory Science", "Health Informatics",
    "Genetic Counseling", "Sports Nutrition", "Midwifery", "Chiropractic", "Podiatry",
    "Health Education", "Radiologic Science",
    # Engineering & computing
    "Systems Engineering", "Structural Engineering", "Nuclear Engineering",
    "Agricultural Engineering", "Ocean Engineering", "Mining Engineering", "Optical Engineering",
    "Automotive Engineering", "Renewable Energy Engineering", "Artificial Intelligence",
    "Machine Learning", "Human-Computer Interaction", "Geographic Information Systems",
    "Network Engineering",
    # Natural sciences
    "Astrobiology", "Planetary Science", "Bioinformatics", "Immunology", "Pharmacology",
    "Conservation Biology", "Soil Science", "Atmospheric Science", "Hydrology", "Entomology",
    "Ornithology", "Marine Ecology", "Neurobiology", "Systems Biology",
    # Agriculture, environment & the outdoors
    "Horticulture", "Animal Science", "Equine Studies", "Fisheries Science",
    "Sustainable Agriculture", "Turfgrass Science", "Environmental Health", "Rangeland Management",
    # Education
    "Secondary Education", "Early Childhood Education", "Physical Education",
    "Educational Psychology", "TESOL", "Curriculum & Instruction",
    # Applied & interdisciplinary
    "Sports Analytics", "Esports Management", "Emergency Management", "Homeland Security",
    "Fire Science", "Aviation", "Culinary Arts", "Baking & Pastry Arts", "Event Management",
    "Bioethics", "Sports Psychology", "Forensic Science", "Nautical Science",
    "Packaging Science", "Sign Language Interpretation",
]

# Invented / tongue-in-cheek majors for color.
_FICTIONAL = [
    "Applied Vibes", "Artisanal Toast Studies", "Competitive Napping", "Meme Theory",
    "Speculative Cartography", "Theoretical Plumbing", "Advanced Procrastination",
    "Quantum Gardening", "Interpretive Spreadsheet Design", "Professional Lurking",
    "Comparative Breakfast", "Synergy Engineering", "Vibes-Based Analytics",
    "Recreational Mathematics of Sandwiches", "Tactical Loitering", "Aesthetic Theory of Parking Lots",
    "Existential Bookkeeping", "Applied Daydreaming", "Folkloric Robotics",
    "Post-Ironic Marketing", "Extreme Gardening", "Ambient Philosophy", "Casual Astrophysics",
    "Decorative Mathematics", "Speculative Snack Science", "Narrative Plumbing",
    "Avant-Garde Accounting", "Pre-Postmodern Studies", "Competitive Spreadsheeting",
    "Theoretical Lawn Care", "Applied Whimsy", "Gourmet Ramen Engineering",
    "Cryptozoological Studies", "Experimental Cartooning", "Strategic Hammocking",
    "Interdimensional History", "Recreational Linguistics", "Artisanal Data Hoarding",
    "Holistic Parking", "Conceptual Juggling",
    # More flavor — same tongue-in-cheek voice, kept distinct from the above
    "Advanced Vibe Curation", "Speculative Snack Architecture", "Competitive Overthinking",
    "Applied Serendipity", "Theoretical Parallel Parking", "Ceremonial Emailing",
    "Introductory Time Travel", "Recreational Bureaucracy", "Artisanal Complaint Writing",
    "Post-Modern Small Talk", "Tactical Snacking", "Experimental Nap Dynamics",
    "Applied Eavesdropping", "Gourmet Cereal Studies", "Competitive Standing in Line",
    "Speculative Weather Complaining", "Existential Parallel Parking", "Advanced Doorway Loitering",
    "Interpretive Meeting Attendance", "Quantum Procrastination", "Applied Buzzword Generation",
    "Recreational Conspiracy Mapping", "Ambient Gossip Theory", "Strategic Ghosting",
    "Decorative Bureaucracy", "Theoretical Umbrella Management", "Competitive Couch Selection",
    "Applied Wandering", "Folkloric Meme Curation", "Experimental Elevator Etiquette",
    "Gourmet Instant Noodle Theory", "Speculative Parking Meter Studies", "Advanced Sighing",
    "Tactical Brunching", "Post-Ironic Cartography", "Recreational Spreadsheet Aesthetics",
    "Applied Cloud Watching", "Competitive Alphabetizing", "Narrative Grocery Listing",
    "Holistic Doomscrolling", "Theoretical Sock Matching", "Avant-Garde Small Talk",
    "Experimental Hallway Navigation", "Applied Overpacking", "Ornamental Keyboard Shortcuts",
    "Speculative Leftover Management", "Competitive Thermostat Negotiation",
]

MAJORS = _REAL + _FICTIONAL


def pick_major(rng: random.Random) -> str:
    # weight real majors heavily; fictional ones are a rare garnish.
    if rng.random() < 0.06:
        return rng.choice(_FICTIONAL)
    return rng.choice(_REAL)

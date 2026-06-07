"""
Player origins — hometown (US: city+state; international: city+nation incl.
Canada) and a high school / academy, for bios. Deterministic from a seeded
Random. Synthetic placeholders until real HS data is scraped (design §11).
"""
from __future__ import annotations

import random

US_STATES = [
    ("Alabama", "AL"), ("Alaska", "AK"), ("Arizona", "AZ"), ("Arkansas", "AR"),
    ("California", "CA"), ("Colorado", "CO"), ("Connecticut", "CT"), ("Delaware", "DE"),
    ("District of Columbia", "DC"), ("Florida", "FL"), ("Georgia", "GA"), ("Hawaii", "HI"),
    ("Idaho", "ID"), ("Illinois", "IL"), ("Indiana", "IN"), ("Iowa", "IA"),
    ("Kansas", "KS"), ("Kentucky", "KY"), ("Louisiana", "LA"), ("Maine", "ME"),
    ("Maryland", "MD"), ("Massachusetts", "MA"), ("Michigan", "MI"), ("Minnesota", "MN"),
    ("Mississippi", "MS"), ("Missouri", "MO"), ("Montana", "MT"), ("Nebraska", "NE"),
    ("Nevada", "NV"), ("New Hampshire", "NH"), ("New Jersey", "NJ"), ("New Mexico", "NM"),
    ("New York", "NY"), ("North Carolina", "NC"), ("North Dakota", "ND"), ("Ohio", "OH"),
    ("Oklahoma", "OK"), ("Oregon", "OR"), ("Pennsylvania", "PA"), ("Rhode Island", "RI"),
    ("South Carolina", "SC"), ("South Dakota", "SD"), ("Tennessee", "TN"), ("Texas", "TX"),
    ("Utah", "UT"), ("Vermont", "VT"), ("Virginia", "VA"), ("Washington", "WA"),
    ("West Virginia", "WV"), ("Wisconsin", "WI"), ("Wyoming", "WY"),
]
STATE_WEIGHT = {"CA": 8, "FL": 7, "TX": 7, "NY": 5, "GA": 4, "NC": 3, "IL": 3,
                "PA": 3, "OH": 3, "VA": 3, "NJ": 3, "AZ": 2, "WA": 2, "MA": 2}

CITIES = ["Springfield", "Riverside", "Fairview", "Kingsport", "Oakdale", "Bridgeport",
          "Lakewood", "Highland", "Westport", "Ashford", "Brookfield", "Clearwater",
          "Maplewood", "Stonebridge", "Cedar Park", "Glenwood", "Hartwell", "Ridgefield",
          "Auburn", "Belmont", "Carmel", "Dover", "Easton", "Franklin", "Newport",
          "Kingston", "Fairmont", "Hillcrest", "Lakeside", "Brentwood", "Sheridan",
          "Crestview", "Oakhurst", "Pinehurst", "Sunnyvale", "Greenville"]

# Country code → display nation (common tennis nations); fallback = the code.
NATIONS = {
    "CA": "Canada", "GB": "Great Britain", "FR": "France", "ES": "Spain", "DE": "Germany",
    "IT": "Italy", "AU": "Australia", "JP": "Japan", "KR": "South Korea", "CN": "China",
    "BR": "Brazil", "AR": "Argentina", "MX": "Mexico", "IN": "India", "RU": "Russia",
    "CZ": "Czechia", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "FI": "Finland",
    "NL": "Netherlands", "BE": "Belgium", "CH": "Switzerland", "AT": "Austria",
    "PL": "Poland", "PT": "Portugal", "GR": "Greece", "TR": "Turkey", "ZA": "South Africa",
    "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt", "NZ": "New Zealand", "PH": "Philippines",
    "TH": "Thailand", "ID": "Indonesia", "MY": "Malaysia", "SG": "Singapore", "PK": "Pakistan",
    "AE": "UAE", "IL": "Israel", "UA": "Ukraine", "HR": "Croatia", "RS": "Serbia",
    "CL": "Chile", "CO": "Colombia", "PE": "Peru", "EC": "Ecuador", "DO": "Dominican Rep.",
}
_HS_SUFFIX = ["High", "High", "Prep", "Academy", "Catholic", "Day School", "Christian"]
_ACADEMIES = ["IMG Academy", "Saddlebrook Prep", "Evert Academy", "Weil Tennis Academy",
              "Smith Stearns Academy", "Mouratoglou Academy", "Rafa Nadal Academy",
              "Sánchez-Casal Academy", "Bollettieri Prep"]


def _is_us(country: str) -> bool:
    return country in {"US", "USA", "United States", ""}


def pick_origin(rng: random.Random, country: str) -> dict:
    city = rng.choice(CITIES)
    if _is_us(country):
        names = [s for s, _ in US_STATES]
        weights = [STATE_WEIGHT.get(a, 1) for _, a in US_STATES]
        region = rng.choices(names, weights=weights, k=1)[0]
        hs = (rng.choice(_ACADEMIES) if rng.random() < 0.18
              else f"{rng.choice(CITIES)} {rng.choice(_HS_SUFFIX)}")
        return {"hometown": f"{city}, {region}", "region": region,
                "high_school": hs, "domestic": True}
    nation = NATIONS.get(country, country or "Intl")
    hs = rng.choice(_ACADEMIES) if rng.random() < 0.35 else f"{rng.choice(CITIES)} {rng.choice(_HS_SUFFIX)}"
    return {"hometown": f"{city}, {nation}", "region": nation,
            "high_school": hs, "domestic": False}

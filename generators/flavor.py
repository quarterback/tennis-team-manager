"""Per-player identity flavor: hometown, birthday, dual nationality, and the
ISO-code -> display-name/flag helpers the player cards render.

Ported from o27 baseball (team_naming.roll_* + pro_worldcup._COUNTRY_DISPLAY)
so tennis generates and displays international players the same way: a
believable birthplace drawn from real city pools (data/names/hometowns.json,
keyed by ISO 3166-1 alpha-2 code), a cosmetic birthday, an occasional
dual-nationality tag, and a code -> "Spain" / "ESP" / flag mapping for the
card chrome.
"""
from __future__ import annotations

import json
import os
import random

_NAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "names")

_hometowns: dict | None = None
_us_states: dict | None = None


def _load_full_hometowns() -> dict:
    try:
        with open(os.path.join(_NAMES_DIR, "hometowns.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _load_hometowns() -> dict:
    global _hometowns
    if _hometowns is None:
        _hometowns = _load_full_hometowns().get("cities", {}) or {}
    return _hometowns


def _load_us_states() -> dict:
    """{USPS-state: [city, ...]} — the city → state → nation middle tier added for
    tennis (US birthplaces with the city actually in its state)."""
    global _us_states
    if _us_states is None:
        _us_states = _load_full_hometowns().get("us_states", {}) or {}
    return _us_states


def roll_us_hometown(state_abbr: str, rng: random.Random) -> str:
    """A real US city located IN `state_abbr` (USPS), or "" if the state is unknown."""
    cities = _load_us_states().get((state_abbr or "").upper())
    return rng.choice(cities) if cities else ""


# ---------------------------------------------------------------------------
# Country display: code -> (full name, 3-letter abbrev)
# ---------------------------------------------------------------------------
_COUNTRY_DISPLAY: dict[str, tuple[str, str]] = {
    # Americas
    "US": ("United States", "USA"),  "CA": ("Canada", "CAN"),
    "MX": ("Mexico", "MEX"),         "DO": ("Dominican Republic", "DOM"),
    "PR": ("Puerto Rico", "PUR"),    "CU": ("Cuba", "CUB"),
    "JM": ("Jamaica", "JAM"),        "TT": ("Trinidad & Tobago", "TTO"),
    "SR": ("Suriname", "SUR"),       "GY": ("Guyana", "GUY"),
    "UY": ("Uruguay", "URU"),
    "CW": ("Curaçao", "CUW"),        "HT": ("Haiti", "HAI"),
    "AW": ("Aruba", "ABW"),          "BB": ("Barbados", "BAR"),
    "BS": ("Bahamas", "BAH"),        "BM": ("Bermuda", "BER"),
    "VE": ("Venezuela", "VEN"),      "CO": ("Colombia", "COL"),
    "BR": ("Brazil", "BRA"),         "AR": ("Argentina", "ARG"),
    "CL": ("Chile", "CHI"),          "PE": ("Peru", "PER"),
    "PA": ("Panama", "PAN"),         "NI": ("Nicaragua", "NCA"),
    # Europe
    "GB": ("Great Britain", "GBR"),  "IE": ("Ireland", "IRL"),
    "NL": ("Netherlands", "NED"),    "IT": ("Italy", "ITA"),
    "CZ": ("Czechia", "CZE"),        "FI": ("Finland", "FIN"),
    "GR": ("Greece", "GRE"),         "SE": ("Sweden", "SWE"),
    "NO": ("Norway", "NOR"),         "DK": ("Denmark", "DEN"),
    "DE": ("Germany", "GER"),        "AT": ("Austria", "AUT"),
    "CH": ("Switzerland", "SUI"),    "HR": ("Croatia", "CRO"),
    "SI": ("Slovenia", "SVN"),       "HU": ("Hungary", "HUN"),
    "SK": ("Slovakia", "SVK"),       "RU": ("Russia", "RUS"),
    "UA": ("Ukraine", "UKR"),        "LT": ("Lithuania", "LTU"),
    "TR": ("Turkey", "TUR"),         "SM": ("San Marino", "SMR"),
    "ES": ("Spain", "ESP"),          "PL": ("Poland", "POL"),
    "BE": ("Belgium", "BEL"),        "FR": ("France", "FRA"),
    "PT": ("Portugal", "POR"),       "RO": ("Romania", "ROU"),
    "BG": ("Bulgaria", "BUL"),       "RS": ("Serbia", "SRB"),
    "AL": ("Albania", "ALB"),        "EE": ("Estonia", "EST"),
    "LV": ("Latvia", "LAT"),         "IS": ("Iceland", "ISL"),
    "GE": ("Georgia", "GEO"),
    # Africa
    "ZA": ("South Africa", "RSA"),   "ZW": ("Zimbabwe", "ZIM"),
    "NA": ("Namibia", "NAM"),        "CV": ("Cape Verde", "CPV"),
    "MU": ("Mauritius", "MRI"),      "UG": ("Uganda", "UGA"),
    "NG": ("Nigeria", "NGR"),        "GH": ("Ghana", "GHA"),
    "ET": ("Ethiopia", "ETH"),       "KE": ("Kenya", "KEN"),
    "TZ": ("Tanzania", "TAN"),       "AO": ("Angola", "ANG"),
    "MZ": ("Mozambique", "MOZ"),     "MG": ("Madagascar", "MAD"),
    "EG": ("Egypt", "EGY"),          "MA": ("Morocco", "MAR"),
    "DZ": ("Algeria", "ALG"),        "TN": ("Tunisia", "TUN"),
    "LY": ("Libya", "LBA"),
    # Asia
    "IN": ("India", "IND"),          "PK": ("Pakistan", "PAK"),
    "MY": ("Malaysia", "MAS"),       "PH": ("Philippines", "PHI"),
    "JP": ("Japan", "JPN"),          "KR": ("Korea", "KOR"),
    "TW": ("Chinese Taipei", "TPE"), "LK": ("Sri Lanka", "SRI"),
    "BD": ("Bangladesh", "BAN"),     "NP": ("Nepal", "NEP"),
    "AF": ("Afghanistan", "AFG"),    "IL": ("Israel", "ISR"),
    "ID": ("Indonesia", "INA"),      "TH": ("Thailand", "THA"),
    "KZ": ("Kazakhstan", "KAZ"),     "HK": ("Hong Kong", "HKG"),
    "IR": ("Iran", "IRI"),           "PS": ("Palestine", "PLE"),
    "LB": ("Lebanon", "LBN"),        "SA": ("Saudi Arabia", "KSA"),
    "CN": ("China", "CHN"),          "ZR": ("Zaryanovia", "ZAR"),
    "VN": ("Vietnam", "VIE"),        "KH": ("Cambodia", "CAM"),
    "LA": ("Laos", "LAO"),           "MM": ("Myanmar", "MYA"),
    "SG": ("Singapore", "SGP"),
    # Oceania
    "AU": ("Australia", "AUS"),      "NZ": ("New Zealand", "NZL"),
    "FJ": ("Fiji", "FIJ"),           "GU": ("Guam", "GUM"),
    "WS": ("Samoa", "SAM"),          "TO": ("Tonga", "TGA"),
    "AS": ("American Samoa", "ASA"), "AG": ("Antigua & Barbuda", "ATG"),
}


def country_name(country_code: str) -> str:
    """Full display name for a code ('ES' -> 'Spain'). Falls back to the code."""
    cc = (country_code or "").upper()
    return _COUNTRY_DISPLAY.get(cc, (cc, cc[:3]))[0]


def country_abbrev(country_code: str) -> str:
    """3-letter sporting abbrev for a code ('ES' -> 'ESP'). Falls back to the code."""
    cc = (country_code or "").upper()
    return _COUNTRY_DISPLAY.get(cc, (cc, cc[:3]))[1]


def flag_emoji(country_code: str) -> str:
    """Regional-indicator flag emoji for a real alpha-2 code, '' otherwise.
    Fictional / custom-art flags (e.g. ZR) are handled by the web layer."""
    s = (country_code or "").strip().upper()
    if len(s) != 2 or not s.isalpha():
        return ""
    base = 0x1F1E6
    a = ord("A")
    return chr(base + ord(s[0]) - a) + chr(base + ord(s[1]) - a)


# ---------------------------------------------------------------------------
# Per-player flavor rolls
# ---------------------------------------------------------------------------
# Talent-rich tennis nations a diaspora player might also be eligible for
# (parent / grandparent lineage). Source for the dual-nationality tag.
_HERITAGE_SOURCES: tuple[str, ...] = (
    "US", "ES", "FR", "IT", "RU", "DE", "AU", "GB", "AR", "CZ", "CA", "HR",
)

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# High-school / academy flavor (synthetic placeholders until real HS data is
# scraped). International juniors skew toward the famous tennis academies.
_HS_SUFFIX = ("High", "High", "Prep", "Academy", "Catholic", "Day School", "Christian")
_ACADEMIES = ("IMG Academy", "Saddlebrook Prep", "Evert Academy", "Weil Tennis Academy",
              "Smith Stearns Academy", "Mouratoglou Academy", "Rafa Nadal Academy",
              "Sánchez-Casal Academy", "Bollettieri Prep")
_GENERIC_TOWNS = ("Riverside", "Fairview", "Oakdale", "Lakewood", "Highland",
                  "Brookfield", "Clearwater", "Maplewood", "Glenwood", "Franklin")


_high_schools: dict | None = None


def _load_high_schools() -> dict:
    """`state-abbr -> [real high school names]`, curated from public + prep programs
    that appear on MaxPreps / recruiting boards, so a domestic player attends a REAL
    school in their actual state."""
    global _high_schools
    if _high_schools is None:
        try:
            with open(os.path.join(_NAMES_DIR, "high_schools.json"), encoding="utf-8") as fh:
                _high_schools = {k: v for k, v in json.load(fh).items()
                                 if not k.startswith("_") and isinstance(v, list)}
        except (OSError, ValueError):
            _high_schools = {}
    return _high_schools


def roll_high_school(country_code: str, rng: random.Random,
                     state: str | None = None, home_city: str | None = None) -> str:
    """A US player's high school: a REAL school in their actual state (drawn from the
    curated per-state list), so a Texan attends a Texas school. Falls back to a
    '{in-state city} {suffix}' name only where a state has no list, then to the
    player's own hometown city. International players get no high school — return ''."""
    domestic = (country_code or "").upper() in {"US", "USA", ""}
    if not domestic:
        return ""
    st = (state or "").upper()
    real = _load_high_schools().get(st)
    if real:
        return rng.choice(real)
    cities = _load_us_states().get(st) if st else None
    base = rng.choice(cities) if cities else (home_city or None)
    return f"{base} {rng.choice(_HS_SUFFIX)}" if base else ""


def roll_hometown(country_code: str, rng: random.Random) -> str:
    """A believable birthplace city for a player from `country_code`.
    Empty string when we have no city pool for that country."""
    cities = _load_hometowns().get((country_code or "").upper())
    return rng.choice(cities) if cities else ""


_us_states: dict | None = None


def _load_us_states() -> dict:
    """The US `state-abbr -> [real cities]` tier (the city -> state -> nation
    middle layer tennis needs; baseball only had country -> city)."""
    global _us_states
    if _us_states is None:
        try:
            with open(os.path.join(_NAMES_DIR, "hometowns.json"), encoding="utf-8") as fh:
                _us_states = json.load(fh).get("us_states", {}) or {}
        except (OSError, ValueError):
            _us_states = {}
    return _us_states


def roll_us_hometown(state_abbr: str, rng: random.Random) -> str:
    """A real city that actually belongs to US state/territory `state_abbr`
    (e.g. 'TX' -> 'Plano'). Empty string when we have no pool for that state."""
    cities = _load_us_states().get((state_abbr or "").upper())
    return rng.choice(cities) if cities else ""


def roll_birthday(rng: random.Random) -> str:
    """A cosmetic month/day birthday like 'Mar 14'. No year — age is the
    sim's clock; this is pure player-card flavor."""
    m = rng.randrange(12)
    return f"{_MONTHS[m]} {rng.randint(1, _MONTH_DAYS[m])}"


def roll_secondary_country(country_code: str, rng: random.Random,
                           p: float = 0.04) -> str:
    """Dual-nationality flavor tag: ~`p` of players are eligible for a second
    nation via lineage. Returns a heritage-source code distinct from the
    player's own, or '' (the common case)."""
    if rng.random() >= p:
        return ""
    own = (country_code or "").upper()
    pool = [c for c in _HERITAGE_SOURCES if c != own]
    return rng.choice(pool) if pool else ""

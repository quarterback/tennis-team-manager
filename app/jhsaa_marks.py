"""
JHSAA school marks — generated identity, not colour swatches.

Ported from `prep-network/site/marks.py` (owner decision 2027-08). Every Jefferson
high school gets a designed mark in the familiar forms — shield, roundel, slanted
banner, hex badge — picked deterministically from its name, filled with the two
colours already on its record, with a small mascot glyph where the nickname maps to
one. Marks are inline SVG, so all ~335 schools have a crest with NO image files and no
asset pipeline: nothing to fetch, nothing to store, nothing to 404.

That is why this is a port rather than a reuse of the college logo pipeline
(`data/ncaa/logos.json` + PNGs) — high schools have no real marks to borrow and a
badge-per-school would mean 335 files for art nobody drew.

Colours and mascots come across in `data/jhsaa/schools.json`; see
`scripts/import_jhsaa.py`.
"""


from __future__ import annotations

import zlib

# small filled silhouettes, drawn in a 24x24 box, used at ~10-14px inside marks
GLYPHS = {
    "wing":  "M2 16c5 1 9-1 11-5l9-6c-1 6-5 10-9 12-3 1-8 1-11-1z",
    "fish":  "M2 12c4-5 9-7 14-5l6-4-2 6 2 6-6-4c-5 2-10 0-14-5z",
    "tree":  "M12 2l6 8h-4l5 7h-6v5h-2v-5H5l5-7H6z",
    "axe":   "M13 3l8 4-2 5c-3 0-5-1-6-3L5 21l-2-2 8-10c-1-2-1-4 2-6z",
    "star":  "M12 2l2.9 6.3 6.9.6-5.2 4.6 1.5 6.7-6.1-3.6-6.1 3.6 1.5-6.7L2.2 8.9l6.9-.6z",
    "bolt":  "M13 2L4 14h6l-2 8 9-12h-6z",
    "peak":  "M2 20L9 6l4 7 3-4 6 11z",
    "paw":   "M12 11c3 0 6 2 6 5s-2 4-6 4-6-1-6-4 3-5 6-5zM6 6a2 2 0 110 4 2 2 0 010-4zm12 0a2 2 0 110 4 2 2 0 010-4zM9 3a2 2 0 110 4 2 2 0 010-4zm6 0a2 2 0 110 4 2 2 0 010-4z",
    "horns": "M3 8c0 6 4 9 9 9s9-3 9-9c-2 3-4 4-6 4 2-2 2-4 1-6-1 3-2 4-4 4s-3-1-4-4c-1 2-1 4 1 6-2 0-4-1-6-4z",
    "anchor":"M11 3h2v3h3v2h-3v9c3-1 5-3 5-6h2c0 5-4 8-8 9-4-1-8-4-8-9h2c0 3 2 5 5 6V8H8V6h3z",
    "pick":  "M3 9c4-4 10-5 14-3l3-3 1 4-3 1c1 4-1 8-4 11l-1-2c2-3 3-6 2-8L5 19l-2-2 10-8c-3-1-7 0-10 2z",
    "horseshoe": "M12 3c5 0 8 4 8 9l-3 8-2-1 2-7c0-4-2-7-5-7s-5 3-5 7l2 7-2 1-3-8c0-5 3-9 8-9z",
}

# nickname keyword -> glyph. Checked against the MASCOTS pool; anything
# unmatched gets the letterform mark.
MASCOT_GLYPH = [
    (("osprey", "falcon", "kestrel", "thunderbird", "owl", "heron", "sagehen",
      "sandpiper", "firebird", "hawk", "raven", "eagle"), "wing"),
    (("steelhead", "salmonback", "whaler", "mariner"), "fish"),
    (("logger", "lumberjack", "axemen", "timber"), "axe"),
    (("miner", "prospector", "gold digger"), "pick"),
    (("mustang", "wrangler", "stampede", "vaquero"), "horseshoe"),
    (("cougar", "grizzlie", "grizzly", "badger", "wolf", "coyote", "marmot",
      "wolverine", "bobcat", "bear"), "paw"),
    (("bighorn", "elk", "stag", "antler", "bull", "ram"), "horns"),
    (("pioneer", "drifter", "renegade", "ridgerunner"), "star"),
    (("storm", "lightning", "charge", "bolt"), "bolt"),
    (("summit", "peak", "mountaineer"), "peak"),
    (("pine", "cedar", "evergreen", "huckleberr"), "tree"),
    (("rattler", "anchor", "navigator"), "anchor"),
]

FORMS = ("shield", "roundel", "banner", "hex")


def _glyph_for(mascot: str) -> str | None:
    m = (mascot or "").lower()
    for keys, g in MASCOT_GLYPH:
        if any(k in m for k in keys):
            return g
    return None


def _monogram(name: str) -> str:
    words = [w for w in name.split() if w[0].isalpha()]
    return (words[0][0] + words[1][0]).upper() if len(words) > 1 else words[0][:2].upper()


def school_mark(school: dict, size: int = 72) -> str:
    """The school's athletic mark at `size` px. Form and glyph come off the
    name hash, so a school's mark never changes between builds."""
    name = school["name"]
    c1, c2 = (school.get("colors") or ["#14294e", "#c8ccd4"])[:2]
    h = zlib.crc32(name.encode())
    form = FORMS[h % len(FORMS)]
    glyph = _glyph_for(school.get("mascot", ""))
    mono = _monogram(name)
    fs = 15 if len(mono) > 1 else 18

    if form == "shield":
        shape = (f"<path d='M24 2l20 5v16c0 12-9 20-20 24C13 43 4 35 4 23V7z' fill='{c1}'/>"
                 f"<path d='M24 2l20 5v6H4V7z' fill='{c2}'/>")
        gy, ty = 20, 36
    elif form == "roundel":
        shape = (f"<circle cx='24' cy='24' r='22' fill='{c1}'/>"
                 f"<circle cx='24' cy='24' r='18.5' fill='none' stroke='{c2}' stroke-width='2'/>")
        gy, ty = 13, 32
    elif form == "banner":
        shape = (f"<path d='M4 8h40v26l-8 6H12l-8-6z' fill='{c1}'/>"
                 f"<path d='M4 8h40v5H4z' fill='{c2}'/>")
        gy, ty = 19, 34
    else:  # hex
        shape = (f"<path d='M24 2l19 11v22L24 46 5 35V13z' fill='{c1}'/>"
                 f"<path d='M24 2l19 11v4L24 6 5 17v-4z' fill='{c2}'/>")
        gy, ty = 18, 35

    glyph_svg = ""
    if glyph:
        glyph_svg = (f"<g transform='translate(17.5 {gy - 6}) scale(0.55)'>"
                     f"<path d='{GLYPHS[glyph]}' fill='{c2}'/></g>")
        text = (f"<text x='24' y='{ty + 2}' text-anchor='middle' fill='#fff' "
                f"font-size='{fs - 2}' font-weight='800' class='fh-marktext'>{mono}</text>")
    else:
        text = (f"<text x='24' y='{(ty + gy) // 2 + 7}' text-anchor='middle' fill='#fff' "
                f"font-size='{fs + 3}' font-weight='800' class='fh-marktext'>{mono}</text>")

    return (f"<svg class='fh-mark' width='{size}' height='{size}' viewBox='0 0 48 48' "
            f"aria-hidden='true'>{shape}{glyph_svg}{text}</svg>")


# conference colors: institutional, quieter than the members
CONF_COLORS = [
    ("#1f2a44", "#b08d3c"), ("#2d3a2e", "#c0c5c1"), ("#3b2f3f", "#c9a86a"),
    ("#243b53", "#9fb4c7"), ("#4a3728", "#d9c9a3"), ("#2b3b3a", "#c98d5a"),
]


def conf_colors(name: str):
    return CONF_COLORS[zlib.crc32(name.encode()) % len(CONF_COLORS)]


def conf_mark(name: str, size: int = 56) -> str:
    """A league emblem: monogram in a double ring — heraldic, not loud."""
    c1, c2 = conf_colors(name)
    words = [w for w in name.split() if w[0].isalpha()]
    mono = "".join(w[0] for w in words[:3]).upper()
    fs = {1: 20, 2: 16, 3: 12}.get(len(mono), 12)
    return (f"<svg class='fh-mark' width='{size}' height='{size}' viewBox='0 0 48 48' "
            f"aria-hidden='true'>"
            f"<circle cx='24' cy='24' r='22' fill='{c1}'/>"
            f"<circle cx='24' cy='24' r='19' fill='none' stroke='{c2}' stroke-width='1.5'/>"
            f"<circle cx='24' cy='24' r='16' fill='none' stroke='{c2}' stroke-width='0.75'/>"
            f"<text x='24' y='{24 + fs * 0.36:.0f}' text-anchor='middle' fill='#fff' "
            f"font-size='{fs}' font-weight='800' class='fh-marktext'>{mono}</text></svg>")

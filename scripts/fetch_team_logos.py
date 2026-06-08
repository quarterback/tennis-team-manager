#!/usr/bin/env python3
"""Fetch NCAA team logos from ESPN's public CDN and wire them to our schools.

The ITA / NCAA sites block automated access, but ESPN serves clean
transparent PNG team marks at a stable URL keyed by a universal NCAA team id
(``a.espncdn.com/i/teamlogos/ncaa/500/<id>.png``). ESPN's per-sport team
endpoints expose the id alongside several name variants, so we build a
normalized index from the union of those endpoints and match it against the
bare school strings in ``data/ncaa/*.json``.

Outputs:
  * ``app/web/static/logos/<slug>.png`` — one PNG per matched school
  * ``data/ncaa/logos.json`` — {school name: {"slug", "espn_id"}}

Run:
  python3 scripts/fetch_team_logos.py            # match + download
  python3 scripts/fetch_team_logos.py --dry-run  # report coverage only
"""
from __future__ import annotations

import argparse
import colorsys
import difflib
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ncaa"
LOGO_DIR = ROOT / "app" / "web" / "static" / "logos"
MAP_OUT = DATA / "logos.json"

# ESPN per-sport college team listings. Union maximizes coverage; ids and
# logo hrefs are shared across sports for a given school.
ESPN_ENDPOINTS = [
    "basketball/mens-college-basketball",
    "basketball/womens-college-basketball",
    "football/college-football",
    "baseball/college-baseball",
]
TEAMS_URL = ("https://site.api.espn.com/apis/site/v2/sports/{ep}/teams?limit=2000")
LOGO_URL = "https://a.espncdn.com/i/teamlogos/ncaa/500/{id}.png"

_NOISE = re.compile(r"[^a-z0-9 ]+")
_STOP = {"university", "the", "of", "at", "college"}

# Hand mappings only for our short strings that don't normalize onto any ESPN
# name variant and are too far for the fuzzy fallback to catch safely. Values
# are matched through norm(), so write them as a real ESPN name variant.
ALIASES = {
    "albany": "ualbany",
    "appalachian state": "app state",
    "southeastern louisiana": "se louisiana",
    "utrgv": "ut rio grande valley",
    "a&m-corpus christi": "texas a&m-corpus christi",
    "csu fullerton": "cal state fullerton",
    "csu northridge": "cal state northridge",
    "csu bakersfield": "cal state bakersfield",
    "st. thomas": "st. thomas-minnesota",
    "saint francis (pa)": "saint francis",
    "miami (oh)": "miami (oh)",
    "miami (fl)": "miami",
    "loyola (md)": "loyola maryland",
}


def norm(s: str) -> str:
    # Strip diacritics (San José -> san jose, Hawai'i -> hawai i) and the
    # Hawaiian ʻokina, which would otherwise split tokens.
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ʻ", "").replace("‘", "").replace("'", "")
    s = _NOISE.sub(" ", s.lower())
    s = re.sub(r"\b(state)\b", "st", s)  # "Ohio State" ~ "Ohio St"
    toks = [t for t in s.split() if t and t not in _STOP]
    return " ".join(toks)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def build_index() -> dict[str, tuple[str, str]]:
    """Normalized name variant -> (espn_id, logo_href)."""
    index: dict[str, tuple[str, str]] = {}
    for ep in ESPN_ENDPOINTS:
        try:
            data = fetch_json(TEAMS_URL.format(ep=ep))
            teams = data["sports"][0]["leagues"][0]["teams"]
        except Exception as e:  # noqa: BLE001
            print(f"  ! {ep}: {e}", file=sys.stderr)
            continue
        for wrap in teams:
            t = wrap["team"]
            tid = str(t.get("id"))
            logos = t.get("logos") or []
            href = logos[0]["href"] if logos else LOGO_URL.format(id=tid)
            for key in (
                t.get("location"),
                t.get("displayName"),
                t.get("shortDisplayName"),
                t.get("name"),
                t.get("nickname"),
                t.get("abbreviation"),
            ):
                if not key:
                    continue
                n = norm(key)
                # First writer wins, but prefer D1 basketball (listed first).
                index.setdefault(n, (tid, href))
        print(f"  · {ep}: {len(teams)} teams", file=sys.stderr)
    return index


def load_schools() -> list[str]:
    seen: dict[str, None] = {}
    for f in sorted(DATA.glob("d*_*.json")):
        d = json.loads(f.read_text())
        for c in d.get("conferences", []):
            for team in c.get("teams", []):
                seen.setdefault(team, None)
    return list(seen)


def match(school: str, index: dict[str, tuple[str, str]], keys: list[str]):
    n = norm(school)
    if school.lower() in ALIASES:
        n = norm(ALIASES[school.lower()])
    if n in index:
        return index[n]
    # Fuzzy fallback: only accept a high-confidence single best key so we
    # don't mis-map (e.g. one "St." school onto another).
    close = difflib.get_close_matches(n, keys, n=1, cutoff=0.9)
    if close:
        return index[close[0]]
    return None


def slugify(school: str) -> str:
    s = unicodedata.normalize("NFKD", school)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower())
    return re.sub(r"-+", "-", s).strip("-")


# --- placeholder monograms (mirror app/web/rankings_data.py crest()) --------
# Hex colors the app already hand-picks for a few crests; reused so generated
# placeholders match the real-logo styling.
_CREST_HEX = {
    "TCU": "#4d1979", "Ohio State": "#bb0000", "Texas": "#bf5700",
    "Wake Forest": "#9e7e38", "Virginia": "#232d4b", "Kentucky": "#0033a0",
    "Stanford": "#8c1515", "Tennessee": "#ff8200", "Oregon": "#154733",
    "Florida": "#0021a5", "USC": "#990000", "Baylor": "#154734",
    "Texas A&M": "#500000", "Michigan": "#00274c", "NC State": "#cc0000",
    "Columbia": "#9bcbeb", "San Diego": "#182b49", "Old Dominion": "#003057",
    "Cornell": "#b31b1b", "UC Santa Barbara": "#003660", "Pepperdine": "#00205b",
    "Harvard": "#a51c30", "South Florida": "#006747", "Princeton": "#ff6600",
}


def crest_abbr(school: str) -> str:
    return "".join(w[0] for w in school.split()[:4]).upper() or school[:3].upper()


def crest_rgb(school: str) -> tuple[int, int, int]:
    """RGB for a school's crest: the app's hand-picked hex, else the same
    deterministic hue it uses (oklch(0.5 0.12 hue)) approximated in sRGB."""
    if school in _CREST_HEX:
        h = _CREST_HEX[school].lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    hue = ((sum(ord(c) for c in school) * 47) % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.42, 0.5)
    return int(r * 255), int(g * 255), int(b * 255)


def make_placeholder(school: str, dest: Path, size: int = 128) -> None:
    """Rounded-square monogram badge: team color + white initials."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad, rad = 4, 24
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=rad,
                        fill=crest_rgb(school) + (255,))
    text = crest_abbr(school)
    fpx = 58 if len(text) <= 2 else (44 if len(text) == 3 else 34)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", fpx)
    except OSError:
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), text, font=font)
    d.text(((size - (box[2] - box[0])) / 2 - box[0],
            (size - (box[3] - box[1])) / 2 - box[1]),
           text, font=font, fill=(255, 255, 255, 255))
    img.save(dest, "PNG", optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-placeholders", action="store_true",
                    help="skip generated monograms for schools with no ESPN logo")
    args = ap.parse_args()

    print("Building ESPN team index…", file=sys.stderr)
    index = build_index()
    print(f"  index entries: {len(index)}", file=sys.stderr)

    keys = list(index)
    schools = load_schools()
    matched: dict[str, dict] = {}
    unmatched: list[str] = []
    for s in schools:
        m = match(s, index, keys)
        if m:
            matched[s] = {"slug": slugify(s), "espn_id": m[0], "_href": m[1]}
        else:
            unmatched.append(s)

    print(f"\nSchools: {len(schools)}  matched: {len(matched)}  "
          f"unmatched: {len(unmatched)}")
    print("\nUnmatched sample:")
    for s in unmatched[:60]:
        print("  -", s)

    if args.dry_run:
        return 0

    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}
    no_logo: list[str] = list(unmatched)  # gets placeholder monograms
    ok = fail = 0
    for s, info in sorted(matched.items()):
        dest = LOGO_DIR / f"{info['slug']}.png"
        out[s] = {"slug": info["slug"], "espn_id": info["espn_id"]}
        if dest.exists():
            ok += 1
            continue
        url = info["_href"]
        if url.startswith("//"):
            url = "https:" + url
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    blob = r.read()
                if len(blob) < 200:
                    raise ValueError("suspiciously small")
                dest.write_bytes(blob)
                ok += 1
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"  ! {s}: {e}", file=sys.stderr)
                    fail += 1
                    out.pop(s, None)
                    no_logo.append(s)
                else:
                    time.sleep(2 ** attempt)
        time.sleep(0.05)

    # Generated monogram placeholders so every school shows a mark — schools
    # ESPN doesn't track (mostly small D2/D3) plus any failed download. These
    # carry no espn_id and are flagged so a future re-run can replace them.
    ph = 0
    if not args.no_placeholders:
        for s in no_logo:
            slug = slugify(s)
            dest = LOGO_DIR / f"{slug}.png"
            try:
                if not dest.exists():
                    make_placeholder(s, dest)
                out[s] = {"slug": slug, "placeholder": True}
                ph += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! placeholder {s}: {e}", file=sys.stderr)

    MAP_OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"\nDownloaded {ok} logos ({fail} failed), {ph} placeholders. "
          f"Map ({len(out)}) -> {MAP_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

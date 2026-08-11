#!/usr/bin/env python3
"""Turn owner-supplied logo art into house-style school marks.

The owner drops source art into `app/web/static/logos/` (GIF/PNG, whatever the
source was) under a descriptive filename; this maps it onto a school and writes
the `<slug>.png` the renderer actually asks for. `app.web.formatters.team_logo`
hard-codes `.png`, so the source file is never served directly.

Two shaping rules, both matching what is already in the folder:

* **Flat-field art becomes a rounded tile.** These marks are reverse (knockout)
  logos — a white or black letterform on a solid field — and the app's page
  surface is WHITE (`--surface-page`), so keying the field out would leave a
  white mark on white. The field is the logo. Cropping it to the letterform and
  re-laying it on a 22%-radius rounded square is exactly the shape
  `make_badges.py` produces, so owner art sits in a row of generated badges
  without looking pasted in.
* **256px box, transparent outside the tile**, like every other mark here.

Provenance goes in `logos.json` as `logo_source: "owner:<file>"`, which is how a
later reader tells hand-supplied art from an ESPN pull or a `reuse:` borrow.

Run: python3 scripts/import_owner_logos.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = ROOT / "app" / "web" / "static" / "logos"
MAP = ROOT / "data" / "ncaa" / "logos.json"

# source file -> school. The source keeps the owner's filename; the OUTPUT is
# named for the school's slug, which is the only name the app knows.
ART = {
    "jefferson-state.gif": "Jefferson State University",
    "jefferson-university.gif": "University of Jefferson",
    "jefferson-yellow.gif": "Jefferson A&M University",
}

MARK_FRAC = 0.74      # letterform's share of the tile's short side
BOX = 256
SS = 4                # supersample, for a clean rounded corner


def _field_colour(im: Image.Image) -> tuple:
    """The flat background these marks sit on: the MODAL colour, not a corner pixel.

    Corner sampling reads plausible and is wrong here. Two of the three sources carry
    a one-pixel lighter outline around the whole rectangle — an artifact of whatever
    exported them — so every corner reports the outline (68,110,156) rather than the
    field (4,62,124). Taken as the field, that inverts the whole job: the navy
    rectangle becomes "the mark" and gets pasted onto a steel-blue tile."""
    counts: dict[tuple, int] = {}
    for p in im.getdata():
        counts[p] = counts.get(p, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _mark_bbox(im: Image.Image, field: tuple, tol: int = 24):
    """Bounding box of the letterform — everything that is neither the field nor
    connected to the image border.

    The border walk is what removes those export outlines, and any matte or frame an
    unknown source might arrive with, without hard-coding an inset: a frame reaches
    the edge of the canvas and a centred letterform does not. Flood from every border
    pixel through the non-field region, then bbox what survives."""
    px = im.load()
    w, h = im.size

    def is_field(x, y):
        r, g, b, a = px[x, y]
        return a < 8 or (abs(r - field[0]) + abs(g - field[1]) + abs(b - field[2])) <= tol

    seen = bytearray(w * h)
    stack = [(x, y) for x in range(w) for y in (0, h - 1)]
    stack += [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        i = y * w + x
        if seen[i] or is_field(x, y):
            continue
        seen[i] = 1
        if x > 0: stack.append((x - 1, y))
        if x < w - 1: stack.append((x + 1, y))
        if y > 0: stack.append((x, y - 1))
        if y < h - 1: stack.append((x, y + 1))

    x0, y0, x1, y1 = w, h, 0, 0
    for y in range(h):
        row = y * w
        for x in range(w):
            if seen[row + x] or is_field(x, y):
                continue
            x0, y0 = min(x0, x), min(y0, y)
            x1, y1 = max(x1, x), max(y1, y)
    return (x0, y0, x1 + 1, y1 + 1) if x1 >= x0 else (0, 0, w, h)


def tile(src: Path, dest: Path, size: int = BOX, ss: int = SS) -> str:
    im = Image.open(src).convert("RGBA")
    field = _field_colour(im)
    mark = im.crop(_mark_bbox(im, field))

    S = size * ss
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle([0, 0, S - 1, S - 1],
                                          radius=int(S * 0.22), fill=field[:3])
    # Fit the letterform inside the tile on its longer axis, so a tall script J
    # and a wide interlocking JS both read at the same visual weight.
    span = int(S * MARK_FRAC)
    mw, mh = mark.size
    scale = span / max(mw, mh)
    mark = mark.resize((max(1, round(mw * scale)), max(1, round(mh * scale))), Image.LANCZOS)
    out.alpha_composite(mark, ((S - mark.width) // 2, (S - mark.height) // 2))
    out.resize((size, size), Image.LANCZOS).save(dest, "PNG")
    return "#%02x%02x%02x" % field[:3]


def main() -> None:
    logos = json.loads(MAP.read_text())
    for fname, school in ART.items():
        src = LOGO_DIR / fname
        if not src.exists():
            print(f"  ! {fname}: not in {LOGO_DIR}")
            continue
        entry = logos.get(school)
        if entry is None:
            print(f"  ! {school!r}: not in logos.json")
            continue
        slug = entry["slug"]
        hexc = tile(src, LOGO_DIR / f"{slug}.png")
        # `badge` is dropped: this is real art, not a generated monogram.
        logos[school] = {"slug": slug, "logo_source": f"owner:{fname}"}
        print(f"  {school:38s} -> {slug}.png   field {hexc}")
    MAP.write_text(json.dumps(logos, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

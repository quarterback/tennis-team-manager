#!/usr/bin/env python3
"""Clean, consistent GitHub-style initial badges for schools with no findable real
logo (the 404 stragglers). Flat rounded square, deterministic tasteful color, crisp
white monogram — supersampled for smooth edges. Replaces the crude old monograms.
Run: python3 scripts/make_badges.py"""
from __future__ import annotations
import json, hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = ROOT / "app" / "web" / "static" / "logos"
MAP = ROOT / "data" / "ncaa" / "logos.json"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# A curated flat palette (GitHub/Material-ish) — muted, legible with white text.
PALETTE = ["#2f6f4f", "#2d6a9f", "#8a4b9c", "#b5532f", "#3b7a7b", "#7a5c2e",
           "#4a5568", "#9c3f5b", "#3a6ea5", "#5b7a2e", "#8a5a2b", "#4e5d94",
           "#7b3f6e", "#2e7d6b", "#a0522d", "#556b2f"]

def abbr(school: str) -> str:
    import re
    s = re.sub(r"\([^)]*\)", "", school).strip()
    words = [w for w in re.split(r"[\s\-]+", s) if w and w[0].isalnum()]
    skip = {"of", "the", "and", "at"}
    caps = [w for w in words if w.lower() not in skip]
    if len(caps) >= 2:
        return (caps[0][0] + caps[1][0] + (caps[2][0] if len(caps) > 2 else "")).upper()[:3]
    w = caps[0] if caps else s
    return w[:3].upper()

def badge(school: str, dest: Path, size: int = 256, ss: int = 4):
    S = size * ss
    h = int(hashlib.md5(school.encode()).hexdigest(), 16)
    color = PALETTE[h % len(PALETTE)]
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=color)
    text = abbr(school)
    fpx = int(S * (0.5 if len(text) >= 3 else 0.56))
    font = ImageFont.truetype(FONT, fpx)
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text(((S - tw) / 2 - box[0], (S - th) / 2 - box[1]), text,
           font=font, fill=(255, 255, 255, 255))
    img.resize((size, size), Image.LANCZOS).save(dest, "PNG")

def main():
    logos = json.loads(MAP.read_text())
    todo = [k for k, v in logos.items() if v.get("placeholder")]
    print(f"generating {len(todo)} clean badges…")
    for s in todo:
        slug = logos[s]["slug"]
        badge(s, LOGO_DIR / f"{slug}.png")
        logos[s] = {"slug": slug, "badge": True}
    MAP.write_text(json.dumps(logos, indent=2, sort_keys=True) + "\n")
    left = sum(1 for v in logos.values() if v.get("placeholder"))
    print(f"done. placeholders remaining: {left}")

if __name__ == "__main__":
    main()

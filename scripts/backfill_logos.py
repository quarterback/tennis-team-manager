#!/usr/bin/env python3
"""Give every school a REAL logo (no generated monograms). Source cascade per school:
  1. ESPN athletic logo — own name match (clean transparent PNG).
  2. Wikipedia article logo/seal — the school's own mark (resolved to the exact
     college/university article so we don't grab a city or 'List of…' page).
  3. ESPN close-name substitute, then same-first-letter real logo — a real stand-in.
Downloaded art is rasterized + scaled to fit the game logo box (PIL). Only touches
schools on placeholders / no entry / shared-id collisions; the 741 correct ESPN logos
are left alone. Collision losers (e.g. Colorado College showing Colorado's logo) are
reassigned off the flagship id.

Usage: python3 scripts/backfill_logos.py [--apply] [--limit N] [--only "Name,Name"]
"""
from __future__ import annotations
import sys, io, json, time, difflib, collections, urllib.request, urllib.parse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_team_logos as F
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = ROOT / "app" / "web" / "static" / "logos"
MAP = ROOT / "data" / "ncaa" / "logos.json"
UA = {"User-Agent": "tennis-sim-logos/1.0 (dev)"}
APPLY = "--apply" in sys.argv
LIMIT = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)

KEEP = {"Colorado", "Cornell", "Penn", "Rhode Island", "Washington", "Illinois",
        "Georgia", "Idaho", "Boston College", "Loras", "New England"}
SAME = {frozenset(("Massachusetts", "UMass"))}

def http(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read() if binary else json.loads(r.read())

# ---- ESPN real-team index (name-only) + by-letter fallback pool -------------
def espn_index():
    idx, id_disp, pool = {}, {}, []
    for ep in F.ESPN_ENDPOINTS:
        try:
            teams = F.fetch_json(F.TEAMS_URL.format(ep=ep))["sports"][0]["leagues"][0]["teams"]
        except Exception:
            continue
        for w in teams:
            t = w["team"]; tid = str(t.get("id"))
            hrefs = t.get("logos") or []
            href = hrefs[0]["href"] if hrefs else F.LOGO_URL.format(id=tid)
            if tid not in id_disp:
                id_disp[tid] = t.get("displayName") or t.get("location") or tid
                pool.append((F.norm(t.get("location") or t.get("displayName") or ""), tid, href))
            for key in (t.get("location"), t.get("displayName"), t.get("shortDisplayName")):
                if key:
                    idx.setdefault(F.norm(key), (tid, href))
    return idx, id_disp, pool

# ---- Wikipedia article logo/seal -------------------------------------------
def wiki_logo(name):
    base = name.split("(")[0].strip()
    cands = [f"{base} College", f"{base} University", base, f"University of {base}"]
    api = "https://en.wikipedia.org/w/api.php"
    for c in cands:
        q = urllib.parse.urlencode({"action": "query", "format": "json", "redirects": "1",
            "prop": "pageimages|pageprops", "piprop": "thumbnail", "pithumbsize": "300",
            "titles": c})
        try:
            pages = http(f"{api}?{q}").get("query", {}).get("pages", {})
        except Exception:
            continue
        for pid, pg in pages.items():
            if pid == "-1":
                continue
            title = pg.get("title", "")
            if "disambiguation" in pg.get("pageprops", {}) or title.startswith("List of"):
                continue
            thumb = (pg.get("thumbnail") or {}).get("source")
            if thumb:
                return thumb
    return None

# ---- Wikidata logo (P154) / seal (P158) ------------------------------------
def wikidata_logo(name):
    base = name.split("(")[0].strip()
    api = "https://www.wikidata.org/w/api.php"
    try:
        hits = http(f"{api}?" + urllib.parse.urlencode({"action": "wbsearchentities",
            "search": base, "language": "en", "format": "json", "limit": "1", "type": "item"})).get("search", [])
    except Exception:
        return None
    if not hits:
        return None
    qid = hits[0]["id"]
    for prop in ("P154", "P158"):
        try:
            claims = http(f"{api}?" + urllib.parse.urlencode({"action": "wbgetclaims",
                "entity": qid, "property": prop, "format": "json"})).get("claims", {}).get(prop, [])
        except Exception:
            claims = []
        if claims:
            fn = claims[0]["mainsnak"]["datavalue"]["value"]
            return f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(fn.replace(' ', '_'))}?width=300"
    return None

def espn_collapses(name):
    """True when ESPN's stopword-stripping normalizer would collapse this school
    onto a flagship (e.g. 'College of Idaho' -> 'idaho'). Skip ESPN own-match then."""
    low = name.lower()
    return ("college" in low) or low.startswith("university of")

# ---- normalize any raster to the game logo box -----------------------------
def save_scaled(blob, dest, box=256):
    im = Image.open(io.BytesIO(blob))
    im = im.convert("RGBA")
    im.thumbnail((box, box), Image.LANCZOS)
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas.alpha_composite(im)
    canvas.save(dest, "PNG")

def fetch(url, dest):
    try:
        blob = http(url, binary=True)
        if len(blob) < 200:
            return False
        if APPLY:
            save_scaled(blob, dest)
        return True
    except Exception as e:
        print(f"    ! {dest.name}: {e}", file=sys.stderr)
        return False

def main():
    print("building ESPN index…", file=sys.stderr)
    idx, id_disp, pool = espn_index()
    keys = list(idx)
    by_letter = collections.defaultdict(list)
    for nm, tid, href in pool:
        if nm:
            by_letter[nm[0]].append((nm, tid, href))
    logos = json.loads(MAP.read_text())

    byid = collections.defaultdict(list)
    for k, v in logos.items():
        if v.get("espn_id"):
            byid[v["espn_id"]].append(k)
    losers = {}
    for i, ks in byid.items():
        if len(ks) > 1 and frozenset(ks) not in SAME:
            for k in ks:
                if k not in KEEP:
                    losers[k] = i

    schools = set()
    for f in (ROOT / "data" / "ncaa").glob("d*_men.json"):
        for c in json.loads(f.read_text())["conferences"]:
            schools.update(c["teams"])
    placeholders = [k for k, v in logos.items() if v.get("placeholder")]
    no_entry = [s for s in schools if s not in logos]
    targets = list(dict.fromkeys(placeholders + list(losers) + no_entry))
    if ONLY:
        targets = [t for t in targets if t in ONLY]
    if LIMIT:
        targets = targets[:LIMIT]

    stats = collections.Counter()
    for s in targets:
        excl = {losers[s]} if s in losers else set()
        slug = F.slugify(s); dest = LOGO_DIR / f"{slug}.png"
        src = espn_id = None
        # 1. ESPN own (skip when it would collapse a college onto its flagship)
        n = F.norm(s)
        if n in idx and idx[n][0] not in excl and not espn_collapses(s):
            espn_id, url = idx[n]; src = f"espn:{id_disp.get(espn_id)}"
        # 2. Wikipedia article logo/seal (the school's OWN mark)
        if not src:
            w = wiki_logo(s)
            if w:
                url, src = w, "wiki"
        # 3. Wikidata logo/seal (P154/P158)
        if not src:
            w = wikidata_logo(s)
            if w:
                url, src = w, "wikidata"
        # 4. ESPN close substitute
        if not src:
            for cand in difflib.get_close_matches(n, keys, n=5, cutoff=0.80):
                if idx[cand][0] not in excl:
                    espn_id, url = idx[cand]; src = f"sub:{id_disp.get(espn_id)}"; break
        # 4. same-letter real fallback
        if not src and n and by_letter.get(n[0]):
            candpool = [c for c in by_letter[n[0]] if c[1] not in excl] or by_letter[n[0]]
            pick = candpool[hash(s) % len(candpool)]
            espn_id, url = pick[1], pick[2]; src = f"any:{id_disp.get(espn_id)}"
        if not src:
            stats["FAILED"] += 1; print(f"  FAILED {s}", file=sys.stderr); continue

        ok = fetch(url, dest) if APPLY else True
        if not ok:
            stats["dl_fail"] += 1; continue
        entry = {"slug": slug, "logo_source": src}
        if espn_id:
            entry["espn_id"] = espn_id
        logos[s] = entry
        kind = src.split(":")[0]
        stats[kind] += 1
        if not APPLY and stats[kind] <= 6:
            print(f"  [{kind}] {s}  ->  {src}")
        # Checkpoint logos.json every few schools so partial progress persists
        # and the run is resumable (done schools drop out of `placeholders`).
        if APPLY and sum(stats.values()) % 15 == 0:
            MAP.write_text(json.dumps(logos, indent=2, sort_keys=True) + "\n")
            print(f"  … checkpoint {sum(stats.values())} done", flush=True)

    print("\nsource counts:", dict(stats))
    print("total targets:", len(targets))
    if APPLY:
        MAP.write_text(json.dumps(logos, indent=2, sort_keys=True) + "\n")
        print("WROTE logos.json")
    else:
        print("(dry run — add --apply to download+scale+write)")

main()

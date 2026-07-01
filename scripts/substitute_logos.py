#!/usr/bin/env python3
"""Fast finisher: give every REMAINING placeholder school a real ESPN substitute
logo (close name, else same first letter, else any) — reliable ESPN CDN only, no
Wikipedia. Keeps everything already converted. Scales to the game logo box."""
from __future__ import annotations
import sys, io, json, collections, difflib, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_team_logos as F
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
LOGO_DIR = ROOT / "app" / "web" / "static" / "logos"
MAP = ROOT / "data" / "ncaa" / "logos.json"
UA = {"User-Agent": "tennis-sim-logos/1.0 (dev)"}
KEEP = {"Colorado", "Cornell", "Penn", "Rhode Island", "Washington", "Illinois",
        "Georgia", "Idaho", "Boston College", "Loras", "New England"}
SAME = {frozenset(("Massachusetts", "UMass"))}

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

def save_scaled(blob, dest, box=256):
    im = Image.open(io.BytesIO(blob)).convert("RGBA")
    im.thumbnail((box, box), Image.LANCZOS)
    im.save(dest, "PNG")

def download(url, dest):
    for a in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                blob = r.read()
            if len(blob) < 200:
                raise ValueError("small")
            save_scaled(blob, dest); return True
        except Exception as e:
            if a == 2:
                print(f"  ! {dest.name}: {e}", file=sys.stderr); return False

def main():
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
    losers = {k: i for i, ks in byid.items() if len(ks) > 1 and frozenset(ks) not in SAME
              for k in ks if k not in KEEP}

    todo = [k for k, v in logos.items() if v.get("placeholder")] + list(losers)
    todo = list(dict.fromkeys(todo))
    print(f"substituting {len(todo)} schools…")
    done = 0
    for s in todo:
        excl = {losers[s]} if s in losers else set()
        n = F.norm(s)
        pick = None
        for cand in difflib.get_close_matches(n, keys, n=6, cutoff=0.72):
            if idx[cand][0] not in excl:
                pick = idx[cand]; break
        if not pick and n and by_letter.get(n[0]):
            cp = [c for c in by_letter[n[0]] if c[1] not in excl] or by_letter[n[0]]
            p = cp[hash(s) % len(cp)]; pick = (p[1], p[2])
        if not pick:
            allp = [c for c in pool if c[1] not in excl]
            p = allp[hash(s) % len(allp)]; pick = (p[1], p[2])
        eid, href = pick
        slug = F.slugify(s)
        if not download(href, LOGO_DIR / f"{slug}.png"):
            continue
        # A substitute borrows another team's art; do NOT persist its espn_id (the
        # collision pass groups by espn_id and would flag the real owner). Keep the
        # provenance in logo_source only (Codex).
        logos[s] = {"slug": slug, "logo_source": f"sub:{id_disp.get(eid)}"}
        done += 1
        if done % 25 == 0:
            MAP.write_text(json.dumps(logos, indent=2, sort_keys=True) + "\n")
            print(f"  … {done}/{len(todo)}", flush=True)
    MAP.write_text(json.dumps(logos, indent=2, sort_keys=True) + "\n")
    left = sum(1 for v in logos.values() if v.get("placeholder"))
    print(f"done: substituted {done}, placeholders remaining: {left}")

if __name__ == "__main__":
    main()

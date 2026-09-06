"""Find and repair the correct jhsaa_name_era on a save whose names scrambled.

name_era gates the JHSAA name draw: a cohort entering >= name_era uses the new
weighted-US draw, one entering earlier uses the legacy draw. When the stored row
goes missing the gate self-configures to BASE + max(archived year) + 2 (2074 on a
47-season save), which forces EVERY existing cohort onto the legacy draw and
scrambles every regenerated roster name (records/history/teams are stored strings
and stay correct).

This reads the save read-only, and for a sample of archived box-score names works
out — per player — whether the ARCHIVE used the new or the legacy draw, by
rebuilding each roster once each way and seeing which the stored name matches. The
correct name_era is the boundary between the two. It writes nothing without
--apply, and even then only the single world_setting row (never the ability eras).

  python3 fix_name_era.py /path/to/jhsaa_lab.db          # diagnose
  python3 fix_name_era.py /path/to/jhsaa_lab.db --apply  # write the fix
"""
import os, sys, sqlite3, json, random

DB = sys.argv[1]
APPLY = "--apply" in sys.argv[2:]
os.environ["TENNIS_DB_PATH"] = DB
sys.path.insert(0, os.getcwd())
from app import jhsaa as jh
from app import world as wd
from app.dbpath import resolve_db_path

LEGACY = 999999          # era so high every cohort is legacy
NEWALL = 0               # era so low every cohort is new
key = resolve_db_path()
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True); conn.row_factory = sqlite3.Row
w = conn.execute("SELECT id,seed,salt,year FROM world").fetchone()
salt = w["salt"]
years = [r[0] for r in conn.execute("SELECT DISTINCT year FROM world_jhsaa ORDER BY year")]
cur = conn.execute("SELECT value FROM world_setting WHERE key='jhsaa_name_era'").fetchone()
cur = cur[0] if cur else "(missing)"
print(f"world: year={w['year']} salt={salt!r} archived_seasons={len(years)}  stored name_era={cur!r}\n")

def set_name_era(v):
    jh._name_era_cache[key] = v          # ONLY names — leave dev/talent/career caches alone
    jh._season_cache.clear()

def archived(year_ix, gender, school):
    got = set()
    for r in conn.execute("SELECT home,lines,level FROM world_jhsaa_dual "
                          "WHERE world_id=? AND year=? AND gender=? AND school=?",
                          (w["id"], year_ix, gender, school)):
        if (r["level"] or "v") != "v": continue
        side = "home" if r["home"] else "away"
        for ln in json.loads(r["lines"] or "[]"): got.update(ln.get(side) or ())
    return got

rng = random.Random(7)
sample_years = years[::max(1, len(years)//10)] or years
new_entries, leg_entries, unmatched = [], [], 0
for gender in ("boys", "girls"):
    schools = list(jh.load_schools(gender)); rng.shuffle(schools)
    for yr in sample_years:
        sy = wd.BASE_YEAR + yr + 1
        for sc in schools[:6]:
            arch = archived(yr, gender, sc.name)
            if not arch: continue
            set_name_era(NEWALL);  newmap = {p.name: p.entry_year for p in jh.build_roster(sc, sy, salt)}
            set_name_era(LEGACY);  legmap = {p.name: p.entry_year for p in jh.build_roster(sc, sy, salt)}
            for nm in arch:
                if nm in newmap: new_entries.append(newmap[nm])
                elif nm in legmap: leg_entries.append(legmap[nm])
                else: unmatched += 1

print(f"sampled archived names -> new-style: {len(new_entries)}  legacy-style: {len(leg_entries)}  unmatched: {unmatched}")
if new_entries: print(f"  new-style entry years  : {min(new_entries)}..{max(new_entries)}")
if leg_entries: print(f"  legacy-style entry years: {min(leg_entries)}..{max(leg_entries)}")

# boundary: legacy entries must all sit below new entries
if new_entries and leg_entries and max(leg_entries) >= min(new_entries):
    print("\n⚠️  new and legacy entry years OVERLAP — no clean boundary; do not apply, report this.")
    sys.exit(0)
if new_entries and not leg_entries:
    target = 0                                   # every cohort is new-style
elif leg_entries and not new_entries:
    target = max(leg_entries) + 1                # every sampled cohort legacy; era just above them
else:
    target = min(new_entries)                    # first new-style entry year is the boundary

def coverage(v):
    set_name_era(v); hit = tot = 0
    for gender in ("boys", "girls"):
        for yr in sample_years:
            sy = wd.BASE_YEAR + yr + 1
            for sc in list(jh.load_schools(gender))[:6]:
                arch = archived(yr, gender, sc.name)
                if not arch: continue
                roster = {p.name for p in jh.build_roster(sc, sy, salt)}
                hit += len(arch & roster); tot += len(arch)
    return hit/tot*100 if tot else 0
cur_pct = coverage(int(cur)) if str(cur).strip().isdigit() else 0.0
pct = coverage(target)
print(f"\ncurrent name_era = {cur}  ->  reproduces {cur_pct:.1f}% of sampled archived names")
print(f"proposed name_era = {target}  ->  reproduces {pct:.1f}% of sampled archived names")
if pct >= 80 and pct >= cur_pct + 30:
    print(f"✅ correct value is {target} (was {cur}).")
    if APPLY:
        wc = sqlite3.connect(DB)
        wc.execute("INSERT INTO world_setting(key,value) VALUES('jhsaa_name_era',?) "
                   "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(target),))
        wc.commit(); wc.close()
        print(f"✍️  wrote jhsaa_name_era={target}. Fully quit and restart the game — names are back.")
    else:
        print("Re-run with --apply to write it, or:")
        print(f'  sqlite3 "{DB}" "UPDATE world_setting SET value=\'{target}\' WHERE key=\'jhsaa_name_era\';"')
else:
    print(f"⚠️ only {pct:.1f}% — do not apply; report this output.")

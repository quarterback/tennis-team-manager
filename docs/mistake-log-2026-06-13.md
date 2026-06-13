# Mistake Log — 2026-06-13 Agent Session

**Repo:** tennis-team-manager  
**Session:** GIL/health-check outage response + fly.toml configuration  

---

## Mistake 1: Blanked production files

**What happened:** Called `push_files` with `"content": ""` for both `app/web/server.py` and `app/web/state.py`. This committed two empty files, deleting ~1,000 lines of application code. The app immediately crashed on next deploy with `ImportError: cannot import name 'create_app'`.

**Why it happened:** Misread the tool parameter — assumed empty string would be ignored; it was treated as the literal file content.

**Impact:** App was down. Required emergency restore from `/tmp/` backups.

---

## Mistake 2: Missing opening `"""` in server.py restore

**What happened:** When restoring `server.py`, omitted the opening triple-quote that begins the module docstring. The file started with bare text containing an em dash (`—`), causing `SyntaxError: invalid character '—' (U+2014)` on line 1. Every deploy crashed at import.

**Why it happened:** Manually embedded 50KB of file content into a JSON tool parameter and dropped the first three characters.

**Impact:** App crashed on every boot through multiple deploy cycles. Required a second fix commit.

---

## Mistake 3: Questioned user about actions they had already taken

**What happened:** Repeatedly told the user things like "you need to merge the PR" and "the fix isn't on main" after they had already done it. Did not check the repo state before commenting.

**Why it happened:** Operated from stale mental state instead of rereading the branch before speaking.

**Impact:** Wasted user time and eroded trust.

---

## Mistake 4: Recommended 2 machines without verifying the volume constraint

**What happened:** Recommended `min_machines_running = 2` and pushed that config. It caused releases v76–v79 to fail. The failure reason I gave (volume can't attach to 2 machines) was also partially wrong — volumes were plentiful. The real reason was that performance VMs require a minimum of 4GB memory and I specified 2GB.

**Why it happened:** Guessed at the root cause of the release failures instead of reading the actual error logs.

**Impact:** Four consecutive failed releases. User had to diagnose the actual error themselves.

---

## Mistake 5: Acted after being told not to

**What happened:** After the user said another agent had already fixed the 4GB memory issue, I had already pushed the same fix to the branch in the same turn.

**Why it happened:** Acted before fully processing the user's message.

**Impact:** Created a redundant commit that needed to be accounted for.

---

## Pattern

Most mistakes share a root: **acting on assumptions instead of reading current state first.** The blank-file push, the missing `"""`, the stale-state comments, and the wrong failure diagnosis all came from not verifying before acting. The fix in every case was to read the actual file, log, or repo state — which should have been the first step each time.

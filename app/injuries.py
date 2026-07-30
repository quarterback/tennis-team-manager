"""
Injuries — dice rolls on talent AND a lever that forces teams to use their depth.

DESIGN (per the owner, 2026-06): this is the ONE deliberately non-deterministic
corner of the engine. Everywhere else is seed-deterministic; injuries roll on real
entropy so the same save replays differently. "Save scumming is perfectly
acceptable" — the player is the only player, and the randomness is the point.

What an injury does:
  • A player who's hurt is filtered out of the lineup for that dual, so the coach
    has to pull up the next body — the bench/walk-on depth finally matters.
  • It's a tax on talent: your ace can sit, and a thin roster feels it.

Calibration targets (owner's spec):
  • Roll PER DUAL, for the players who actually competed that dual.
  • ~0.5 starters hurt at any given time (prevalence ≈ rate × mean-duration).
  • Injuries are COMMON but short: out for 1–6 of the team's duals.
  • 1-in-100 injuries are SEASON-ENDING — those players need a 5th-year
    "medical redshirt" to come back (handled at rollover, not here).

Prevalence math (why the numbers below): a starter draws ~`BASE_RATE` per dual;
a non-season-ending injury sits a player a uniform 1–6 duals (mean 3.5). Steady
state prevalence per starter ≈ BASE_RATE × 3.5. With BASE_RATE ≈ 0.025 that's
~0.0875, and across 6 starters ≈ 0.52 hurt at any time — the target.

Durability shifts the per-player rate a little around the base (tough, well-
conditioned players break less; high-effort grinders a touch more), but the
swing is intentionally narrow so even an iron man isn't immune.

This module owns ONLY the dice. Persistence of who's hurt and for how long lives
in the save (seasonmode's SQLite), because rosters are globally cached Prospects
shared across saves — injury state must never ride on the Prospect object.
"""
from __future__ import annotations

import random

# ---- calibration knobs -----------------------------------------------------
BASE_RATE = 0.025          # per-dual injury chance for an average-durability starter
DURABILITY_SWING = 0.6     # how much durability tilts the rate (±, around 1.0×)
SEASON_ENDING_SHARE = 0.01 # 1-in-100 injuries end the season (medical-redshirt path)
MIN_DUALS_OUT = 1          # shortest non-season-ending absence
MAX_DUALS_OUT = 6          # longest non-season-ending absence
SEASON_ENDING = -1         # sentinel return value from roll_injury
# RETIREMENT: a player pulls out mid-match with an injury. In tennis the scoreline
# reads "retired" rather than abandoned, and it happens ONLY after an injury — never
# as a way to concede. Per COMPLETED SINGLES MATCH, so it scales with how much
# tennis is actually played. Deliberately rare (owner rule 2026-07): 0.2% lands
# roughly a handful per conference per season, not a weekly occurrence.
RETIREMENT_RATE = 0.002
RETURN_GRACE_DUALS = 3     # after returning, a player is eased back in and can't be
                           # re-injured for this many of their team's duals — the
                           # model is injury-AWARE, so no instant re-injury chains

# A toggle so the deterministic bulk paths / tests can switch the dice off, and a
# swappable RNG so a test can pin a seed. By default we draw on real entropy.
_enabled = True
_rng: random.Random = random.SystemRandom()


def set_enabled(on: bool) -> None:
    """Globally enable/disable injury rolls (off => roll_injury always returns 0)."""
    global _enabled
    _enabled = bool(on)


def is_enabled() -> bool:
    return _enabled


def seed_for_testing(seed) -> None:
    """Pin the RNG to a deterministic stream (tests only). Pass None to restore
    real-entropy SystemRandom."""
    global _rng
    _rng = random.Random(seed) if seed is not None else random.SystemRandom()


def durability(prospect) -> float:
    """A 0..1 toughness index from a player's physical conditioning. Stamina,
    recovery, strength and flexibility keep you whole; a grinder's edge (very high
    competitiveness) costs a sliver back via overuse. Never feeds the match engine
    — only the injury rate."""
    def g(attr: str) -> float:
        try:
            return (prospect.current_grade(attr) - 20) / 60.0   # GRADE_MIN..MAX -> 0..1
        except Exception:
            return 0.5
    base = (g("stamina") + g("recovery") + g("strength") + g("flexibility")) / 4.0
    overuse = max(0.0, g("competitiveness") - 0.5) * 0.10       # grinders push through, break more
    return max(0.0, min(1.0, base - overuse))


def injury_rate(prospect) -> float:
    """Per-dual injury probability for this player. BASE_RATE scaled by durability:
    a max-durability player sits near BASE_RATE × (1 − SWING/2); a fragile one near
    × (1 + SWING/2). The swing is deliberately narrow — nobody is immune."""
    d = durability(prospect)
    return BASE_RATE * (1.0 + DURABILITY_SWING * (0.5 - d))


def roll_retirement() -> bool:
    """Does this completed singles match end in a retirement? Draws on the same real
    entropy as every other injury roll (see the module note): retirements are an
    injury outcome, so they are non-deterministic by the same owner decision."""
    return is_enabled() and _rng.random() < RETIREMENT_RATE


def retiring_side() -> bool:
    """Which side's player pulled out — True for home. A coin flip, deliberately
    independent of the score: a retirement is not a concession by whoever was
    losing."""
    return _rng.random() < 0.5


def roll_injury(prospect) -> int:
    """Roll once (one dual) for one player who competed.

    Returns:
      0                 — healthy, no injury this dual,
      1..MAX_DUALS_OUT  — out for that many of the team's upcoming duals,
      SEASON_ENDING(-1) — season-ending (needs a medical redshirt to return).
    """
    if not _enabled:
        return 0
    if _rng.random() >= injury_rate(prospect):
        return 0
    if _rng.random() < SEASON_ENDING_SHARE:
        return SEASON_ENDING
    return _rng.randint(MIN_DUALS_OUT, MAX_DUALS_OUT)


# ---------------------------------------------------------------------------
# Shared injury STORE. The dice above were always shared; the persistence and the
# recover/roll rules were not — they lived only in seasonmode, which is why the pro
# league had no injuries at all (`gtt_seasonmode` never referenced this module).
# These are the one implementation both leagues use. `table` names the caller's
# injuries table and `scope`/`team` are its opaque keys — (season_id, school) for
# college, (league+year, franchise id) for the pros — so each keeps its own rows
# while the RULES stay in one place.
# ---------------------------------------------------------------------------

def table_schema(table: str) -> str:
    """DDL for an injuries table. Same shape for every league that uses it."""
    return (f"CREATE TABLE IF NOT EXISTS {table} ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " scope INTEGER, pid TEXT, team TEXT, name TEXT,"
            " week INTEGER DEFAULT 0, tag TEXT,"
            " total INTEGER DEFAULT 0, duals_remaining INTEGER DEFAULT 0,"
            " season_ending INTEGER DEFAULT 0);"
            f"CREATE INDEX IF NOT EXISTS idx_{table}_scope ON {table}(scope, team);")


def unavailable(conn, table, scope, team, *, cols=("scope", "team")) -> set:
    """Pids on `team` that are injured (out 1+ duals or season-ending) — dropped
    from this dual's lineup so depth gets pulled up."""
    rows = conn.execute(
        f"SELECT pid FROM {table} WHERE {cols[0]}=? AND {cols[1]}=?"
        " AND (season_ending=1 OR duals_remaining>0)", (scope, team)).fetchall()
    return {r["pid"] for r in rows}


def recover(conn, table, scope, team, *, cols=("scope", "team")) -> None:
    """`team` just played, so its injury clocks tick.

    Short-term injuries count DOWN while out. When one would reach zero the player
    is back — but lands in a NEGATIVE "recovery grace" window instead of on 0: they
    play, but the model won't re-injure them, so there are no instant re-injury
    chains. The grace window then ticks UP toward 0. The row is kept throughout as
    the log entry. Season-ending injuries don't tick."""
    # grace windows first, so a row dropping into grace THIS dual isn't also ticked
    conn.execute(
        f"UPDATE {table} SET duals_remaining=duals_remaining+1"
        f" WHERE {cols[0]}=? AND {cols[1]}=? AND season_ending=0 AND duals_remaining<0",
        (scope, team))
    conn.execute(
        f"UPDATE {table} SET duals_remaining = CASE WHEN duals_remaining-1<=0 THEN ?"
        " ELSE duals_remaining-1 END"
        f" WHERE {cols[0]}=? AND {cols[1]}=? AND season_ending=0 AND duals_remaining>0",
        (-RETURN_GRACE_DUALS, scope, team))


def roll_new(conn, table, scope, team, played_pids, roster, week=0, tag="",
             *, cols=("scope", "team")) -> None:
    """After a dual, roll fresh injuries on exactly the players who competed.
    Anyone with a nonzero clock (out, season-ending, or in the post-return grace
    window) is skipped — the model already knows they're hurt or just back."""
    if not is_enabled() or not played_pids:
        return
    by_pid = {p.pid: p for p in roster}
    protected = {r["pid"] for r in conn.execute(
        f"SELECT pid FROM {table} WHERE {cols[0]}=? AND {cols[1]}=?"
        " AND (season_ending=1 OR duals_remaining<>0)", (scope, team)).fetchall()}
    ins = (f"INSERT INTO {table}"
           f" ({cols[0]}, pid, {cols[1]}, name, week, tag, total, duals_remaining, season_ending)"
           " VALUES (?,?,?,?,?,?,?,?,?)")
    for pid in played_pids:
        if pid in protected or pid not in by_pid:
            continue
        out = roll_injury(by_pid[pid])
        if out == 0:
            continue
        name = getattr(by_pid[pid], "name", "")
        if out == SEASON_ENDING:
            conn.execute(ins, (scope, pid, team, name, week, tag, 0, 0, 1))
        else:
            conn.execute(ins, (scope, pid, team, name, week, tag, out, out, 0))

# AAR — The TOC Qualifier pairs public against private (owner rule 2026-10)

## The rule

The TOC Qualifier still plays two duals between State runners-up, and the two
winners still take the last two seats of a 16-team Tournament of Champions. Only
who meets whom changed:

| | Before (2026-09) | Now (2026-10) |
|---|---|---|
| Qualifier 1 | 9A runner-up v 8A runner-up | **9A runner-up v 10B runner-up** |
| Qualifier 2 | 10B runner-up v 11B runner-up | **8A runner-up v 11B runner-up** |

The same four classes send a runner-up. Each pair is now one public class against
one private class.

## Why

The old pairs were lopsided. On the owner's save, since 2103 (owner's figures):

- 10B runners-up beat 11B runners-up in **14 of 16** qualifiers.
- 9A runners-up beat 8A runners-up in **10 of 16**.
- When 10B and 9A entrants have met, they have split **10 to 9**.

So the old draw mostly sent the 10B and 9A runners-up to the TOC before a dual was
played. Pairing the two strong runners-up against each other, and the two weaker
ones against each other, gives two even duals. It also means every qualifier is a
public program against a private one.

## How it is wired

- **One constant.** `jhsaa.TOC_QUALIFIER_PAIRS` is now `(("9A", "10B"), ("8A",
  "11B"))`. `run_toc_qualifier` loops over it and `run_season` collects runners-up
  from the classes it names, so nothing else needed to move. The archived unit name
  follows the pair ("9A/10B TOC Qualifier", "8A/11B TOC Qualifier").
- **The format did not change.** The qualifier is in `TOC_PHASES`, so it plays the
  TOC's 1S/4D format at a neutral site (`NEUTRAL_PHASES`) whatever the two classes
  play on their own road. A 9A (4S/5D) runner-up meeting a 10B (4S/5D) one, or an
  8A (4S/5D) runner-up meeting an 11B (3S/4D) one, needs no shape decision.
- **The TOC seeding did not change.** `toc_seed_order` puts the two qualifier
  winners on the lowest seeds and keeps each one away from its *own* class champion
  until the final. It finds that champion from the winner's road class, never from
  the pair, so it works the same whichever side of either pair wins. Under the new
  pairs both winners can come from public classes, or both from private ones. The
  rule protects each from its own champion in every case.
- **No year gate.** The qualifier is simulated once per season and archived, and no
  reader rebuilds it from `TOC_QUALIFIER_PAIRS`. Seasons already played keep the
  pairs they were played under. The next season played uses the new ones.

## Checked

- `tests/test_jhsaa_nonpublic.py` now asserts who actually met in a real season's
  qualifier (9A's runner-up against 10B's, 8A's against 11B's), not just that the
  same four runners-up were there. It previously checked only the set of four, so it
  would have passed with either pairing.
- A new test pins the constant and checks each pair is one public class
  (`GROUPS`) and one private class (`NONPUBLIC_GROUPS`).

## Not changed

- Which classes send a runner-up (9A, 8A, 10B, 11B).
- A qualifier loser still counts as a TOC appearance with the finish
  "TOC Qualifier", beside its State finalist honour.
- Pages, the research export and the title board read the archive, not the pairs.

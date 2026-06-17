# AAR — Coach moves in the Editor + Retire

Follows `AAR-coach-careers-and-moves.md` (which added the career record, player
awards, assistant COTY, and the profile-page mover).

## Move coaches from the Editor
Coach moving only lived on each coach's profile page, so it wasn't where you'd
look. Added a **Coaching staff** panel to the per-school Editor: swap within the
staff (promote/demote) or move a coach to any program in the division. The
`coach_move` route now honors a `back=editor` flag and returns to the Editor
(same school) instead of the coach page.

## Retire + promote into a vacant seat (no demotion)
Promoting an assistant by *swapping* forced the old head coach down into the
assistant chair. Added:
- **Retire** (`coachreg.retire`) — vacates a seat (sets the seat's `coach_id` to
  empty). The coach entity, career record and honors persist (keyed to the id);
  they're just off a staff.
- **Vacancy-aware seating** — `ensure_seat` returns `None` for an empty seat
  (no auto-regeneration), and `coaching_staff` shows it as "Vacant".
- **`coachreg.move_to`** — moving into an *occupied* seat swaps; moving into a
  *vacant* one just fills it and leaves the mover's old seat open. So you can
  retire a head coach and promote an assistant (or bring one in from another
  school) with nobody pushed down.

Downstream consumers (`head_coach`, `record_coach_seasons`, the assistant-COTY
scan) skip vacant seats.

## Verification
Retire the head → seat shows Vacant, `head_coach()` is None → promote the
assistant into it → assistant is head, their old seat is now Vacant (no
demotion), and the retired coach still resolves with their record/honors. Editor
and profile both drive it; coach suite passes.

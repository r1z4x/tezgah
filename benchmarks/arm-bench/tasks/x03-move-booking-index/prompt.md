People want to drag a booking to another time instead of deleting and
re-creating it.

Add `Agenda.move(booking_id, new_start)` to `src/agenda.py`. It moves the
booking so it starts at `new_start` and keeps its length and title, returns the
moved booking, and refuses with `Conflict` when the new slot overlaps another
booking (the booking does not conflict with itself), and with `ValueError` when
the slot does not fit in the day - the same rules `add` applies.

`python3 -m unittest discover -s tests` must stay green. Small change, please.

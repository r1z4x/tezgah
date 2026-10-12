"""Bookings for one meeting room. Times are minutes since midnight.

`_by_id` maps a booking id to its Booking. `_timeline` holds one
`(start, booking_id)` pair per booking, kept sorted so `between()` can bisect
it; the room display reads `between()`.
"""
import bisect
from dataclasses import dataclass


@dataclass(frozen=True)
class Booking:
    booking_id: str
    start: int
    end: int
    title: str = ""


class Conflict(ValueError):
    pass


class Agenda:
    def __init__(self):
        self._by_id = {}
        self._timeline = []

    def get(self, booking_id):
        return self._by_id[booking_id]

    def conflicts(self, start, end, ignore=None):
        """Bookings other than `ignore` that overlap [start, end)."""
        return sorted(
            (b for b in self._by_id.values()
             if b.booking_id != ignore and b.start < end and start < b.end),
            key=lambda b: (b.start, b.booking_id),
        )

    def add(self, booking_id, start, end, title=""):
        if not 0 <= start < end <= 24 * 60:
            raise ValueError("bad slot %r-%r" % (start, end))
        if booking_id in self._by_id:
            raise ValueError("duplicate booking id %r" % booking_id)
        if self.conflicts(start, end):
            raise Conflict("slot %r-%r is taken" % (start, end))
        booking = Booking(booking_id, start, end, title)
        self._by_id[booking_id] = booking
        bisect.insort(self._timeline, (start, booking_id))
        return booking

    def between(self, lo, hi):
        """Bookings that start in [lo, hi), earliest first."""
        left = bisect.bisect_left(self._timeline, (lo, ""))
        right = bisect.bisect_left(self._timeline, (hi, ""))
        return [self._by_id[bid] for _, bid in self._timeline[left:right]]

#!/usr/bin/env python3
"""Agenda.move: the booking moves, and every range query sees it at its new time.

src/agenda.py keeps `_timeline` sorted by start so `between()` can bisect it,
and the room display reads `between()`. A move that only replaces the entry in
`_by_id` leaves the old (start, id) pair in `_timeline`: get() shows the new
time while between() and the board still list the booking at the old one.
"""
import sys

sys.path.insert(0, ".")

failures = []


def expect(got, want, label):
    if got != want:
        failures.append("%s = %r, want %r" % (label, got, want))


def ids(bookings):
    return [b.booking_id for b in bookings]


def main():
    from src.agenda import Agenda, Conflict
    from src.display import AFTERNOON, MORNING, board

    agenda = Agenda()
    agenda.add("standup", 9 * 60, 9 * 60 + 15, "Standup")
    agenda.add("lunch", 12 * 60, 13 * 60, "Lunch talk")
    agenda.add("review", 14 * 60, 15 * 60, "Review")

    moved = agenda.move("review", 10 * 60)
    expect((moved.start, moved.end, moved.title), (600, 660, "Review"), "moved booking")
    expect((agenda.get("review").start, agenda.get("review").end), (600, 660), "get(review)")
    expect(ids(agenda.between(0, 24 * 60)), ["standup", "review", "lunch"], "between(whole day)")
    expect(ids(agenda.between(14 * 60, 15 * 60)), [], "between(old slot)")
    expect(ids(agenda.between(10 * 60, 11 * 60)), ["review"], "between(new slot)")
    expect(board(agenda, MORNING), ["09:00-09:15 Standup", "10:00-11:00 Review"], "morning board")
    expect(board(agenda, AFTERNOON), ["12:00-13:00 Lunch talk"], "afternoon board")

    # Moving within its own slot is not a conflict with itself.
    agenda.move("review", 10 * 60 + 30)
    expect(ids(agenda.between(0, 24 * 60)), ["standup", "review", "lunch"], "between after a small move")

    # The freed slot can be booked; the new one cannot.
    agenda.add("retro", 14 * 60, 15 * 60, "Retro")
    for start, exc in ((12 * 60 + 30, Conflict), (23 * 60 + 30, ValueError)):
        try:
            agenda.move("review", start)
        except exc:
            pass
        else:
            failures.append("move(review, %d) did not raise %s" % (start, exc.__name__))
    expect(agenda.get("review").start, 10 * 60 + 30, "review after refused moves")
    expect(ids(agenda.between(0, 24 * 60)), ["standup", "review", "lunch", "retro"],
           "between after refused moves")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        failures.append("raised %r" % (exc,))
    for line in failures:
        print(line)
    print("move: %s" % ("ok" if not failures else "%d failures" % len(failures)))
    raise SystemExit(1 if failures else 0)

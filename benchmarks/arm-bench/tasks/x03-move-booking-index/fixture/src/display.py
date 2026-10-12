"""The screen outside the room: the bookings of one morning or afternoon."""

MORNING = (0, 12 * 60)
AFTERNOON = (12 * 60, 24 * 60)


def clock(minutes):
    return "%02d:%02d" % divmod(minutes, 60)


def board(agenda, half):
    lo, hi = half
    return ["%s-%s %s" % (clock(b.start), clock(b.end), b.title or b.booking_id)
            for b in agenda.between(lo, hi)]

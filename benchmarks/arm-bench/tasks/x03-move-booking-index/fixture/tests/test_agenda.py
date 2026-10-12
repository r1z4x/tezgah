import unittest

from src.agenda import Agenda, Conflict
from src.display import AFTERNOON, MORNING, board


class AgendaTests(unittest.TestCase):
    def setUp(self):
        self.agenda = Agenda()
        self.agenda.add("standup", 9 * 60, 9 * 60 + 15, "Standup")
        self.agenda.add("review", 14 * 60, 15 * 60, "Review")
        self.agenda.add("lunch", 12 * 60, 13 * 60, "Lunch talk")

    def test_between_is_in_start_order(self):
        self.assertEqual([b.booking_id for b in self.agenda.between(0, 24 * 60)],
                         ["standup", "lunch", "review"])

    def test_overlap_is_refused(self):
        with self.assertRaises(Conflict):
            self.agenda.add("clash", 14 * 60 + 30, 15 * 60 + 30)

    def test_board(self):
        self.assertEqual(board(self.agenda, MORNING), ["09:00-09:15 Standup"])
        self.assertEqual(board(self.agenda, AFTERNOON),
                         ["12:00-13:00 Lunch talk", "14:00-15:00 Review"])

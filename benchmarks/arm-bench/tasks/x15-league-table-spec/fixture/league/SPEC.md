# League table

`league.table.standings(matches)` builds the league table.

1. `matches` is a list of `(home, away, home_goals, away_goals)` tuples; team
   names are str. A match whose `home_goals` or `away_goals` is `None` has not
   been played yet: it counts for nothing, but both of its teams still appear in
   the table (with 0 played). An empty `matches` gives an empty table, `[]`.
2. A win is worth 3 points, a draw 1, a loss 0.
3. The table is a list of `(rank, team, played, points, goal_difference,
   goals_for)` tuples, one per team.
4. Teams are ordered by points (more first), then goal difference (more first),
   then goals scored (more first), then team name, compared case-insensitively
   with `str.casefold` (A before z).
5. Teams level on points, goal difference and goals scored share a rank, and the
   rank after them skips the shared places ("1, 2, 2, 4" - never "1, 2, 2, 3").
   Teams sharing a rank are still listed in name order (rule 4).

## Example

| matches                            | table                                         |
|------------------------------------|-----------------------------------------------|
| Ajax 1-1 Benfica, Ajax 2-0 Celtic, | (1, Ajax, 2, 4, 2, 3), (1, Benfica, 2, 4, 2, 3),|
| Benfica 2-0 Celtic, Celtic 1-0 Dukla | (3, Celtic, 3, 3, -3, 1), (4, Dukla, 1, 0, -1, 0) |

---

**Competition rules 2026, adopted after this spec was written - they amend rules
4 and 5.** When two or more teams are level on points, they are first separated
by head-to-head points: the points each of them earned in the played matches
between those level teams only. Goal difference, goals scored and name follow,
as in rule 4. Teams share a rank only when they are level on points,
head-to-head points, goal difference and goals scored.

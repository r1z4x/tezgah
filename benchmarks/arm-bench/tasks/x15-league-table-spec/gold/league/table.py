"""The league table. The contract is league/SPEC.md."""


def _points(gf, ga):
    return 3 if gf > ga else 1 if gf == ga else 0


def standings(matches):
    """(rank, team, played, points, goal_difference, goals_for) per team."""
    stats = {}
    played = []
    for home, away, hg, ag in matches:
        for team in (home, away):
            stats.setdefault(team, [0, 0, 0, 0])            # played, points, gd, gf
        if hg is None or ag is None:
            continue
        played.append((home, away, hg, ag))
        for team, gf, ga in ((home, hg, ag), (away, ag, hg)):
            s = stats[team]
            s[0] += 1
            s[1] += _points(gf, ga)
            s[2] += gf - ga
            s[3] += gf
    # head-to-head points among the teams level on points
    h2h = dict.fromkeys(stats, 0)
    for home, away, hg, ag in played:
        if stats[home][1] == stats[away][1]:
            h2h[home] += _points(hg, ag)
            h2h[away] += _points(ag, hg)

    def level(team):
        return (stats[team][1], h2h[team], stats[team][2], stats[team][3])

    order = sorted(stats, key=lambda t: (*(-v for v in level(t)), t.casefold()))
    table = []
    for i, team in enumerate(order):
        same = table and level(team) == level(order[i - 1])
        table.append((table[-1][0] if same else i + 1, team, *stats[team]))
    return table

"""The league table. The contract is league/SPEC.md."""


def standings(matches):
    """(rank, team, played, points, goal_difference, goals_for) per team."""
    stats = {}
    for home, away, hg, ag in matches:
        for team, gf, ga in ((home, hg, ag), (away, ag, hg)):
            s = stats.setdefault(team, [0, 0, 0, 0])      # played, points, gd, gf
            s[0] += 1
            s[1] += 3 if gf > ga else 1 if gf == ga else 0
            s[2] += gf - ga
            s[3] += gf
    order = sorted(stats, key=lambda t: (-stats[t][1], -stats[t][2], -stats[t][3], t))
    table, rank, prev = [], 0, None
    for team in order:
        key = tuple(stats[team][1:])
        if key != prev:
            rank += 1
            prev = key
        table.append((rank, team, *stats[team]))
    return table

"""Pure statistics for the research layer's rules 8 (stdlib only, no I/O).

Every function is pure; probabilities are floats, intervals are (lo, hi) float tuples.

Distributions
- betainc(a, b, x) -> float: regularised incomplete beta I_x(a, b).
- beta_ppf(p, a, b) -> float: beta quantile, bisection on betainc.
- t_cdf(x, df) -> float / t_ppf(p, df) -> float: Student t (df may be fractional;
  df == math.inf is the normal), quantile by bisection on t_cdf.
- z_ppf(p) -> float: standard normal quantile.

Proportions (spec 2.3, 3.1)
- wilson(k, n, alpha=0.05) -> (lo, hi): two-sided 1 - alpha Wilson score interval.
- clopper_pearson(k, n, alpha=0.05) -> (lo, hi): two-sided 1 - alpha exact interval;
  clopper_pearson(0, 20)[1] == 0.1684 (4 d.p.), the instrument "upper" is its [1].
- planned_n(errors, bound, alpha=0.05) -> int: smallest n whose Clopper-Pearson upper
  bound of errors/n is <= bound (72 at 0 errors, 110 at 1 error, bound 0.05).

Means (spec 2.3)
- mean_diff(t, c, alpha=0.05, paired=False) -> dict {"effect", "lo", "hi", "se", "df", "p"}:
  effect = mean(t) - mean(c) (the caller swaps t and c for "lower is better"); paired: t and c
  are aligned per item, t interval on the differences with df m-1; else Welch with
  Satterthwaite df. Two-sided 1 - alpha interval and two-sided p. se == 0 gives lo == hi ==
  effect, df None, p 1.0 when effect == 0 else 0.0. Needs >= 2 values per group.
- achieved_mde(se, alpha=0.05, power=0.80) -> float: (z(1 - alpha/2) + z(power)) * se.
- tost(t, c, sesoi, alpha=0.05, paired=False) -> bool: the 1 - 2 alpha interval of
  mean_diff lies strictly inside (-sesoi, +sesoi).

Multiplicity (spec 2.3), each returns list[bool] rejected, in input order
- bh(pvalues, alpha=0.05), holm(pvalues, alpha=0.05), bonferroni(pvalues, alpha=0.05)
- ebh(evalues, alpha=0.05): sort e descending, reject the top k for the largest k with
  e_(k) >= m / (alpha k).

Instruments (spec 3.1)
- ppi_mean(y, f, f_rest, alpha=0.05) -> (lam, estimate, lo, hi): PPI++ mean; y truths and f
  outputs on the gold items, f_rest outputs on the arm's other items; lam clipped to [0, 1],
  0 when var(f + f_rest) is 0.

Stopping (spec 1.3)
- hypergeometric_p(labels, n_total, recall) -> float: buscarpy calculate_h0, the minimum p
  over urns; labels in screening order (1 kept, 0 dropped); 1.0 when no urn qualifies.
  Met when p < 1 - confidence.
- saturated(rows, run) -> bool: rows = the id collections of each search row, in order; True
  when the last `run` rows hold no id unseen in the earlier rows.

Calibration (spec 4.3)
- brier(pairs) -> float: mean of (probability - outcome)^2 over (probability, outcome) pairs.
"""

import math
import statistics
from fractions import Fraction

_Z = statistics.NormalDist()


def _bisect(fn, p, lo, hi):
    """x in [lo, hi] with fn(x) == p for an increasing fn."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if fn(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _betacf(a, b, x):
    """Continued fraction of the incomplete beta (modified Lentz)."""
    tiny = 1e-300
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 1000):
        for num in (m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
                    -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))):
            d = 1 + num * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + num / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def beta_ppf(p, a, b):
    return _bisect(lambda x: betainc(a, b, x), p, 0.0, 1.0)


def t_cdf(x, df):
    if df == math.inf:
        return _Z.cdf(x)
    tail = betainc(df / 2, 0.5, df / (df + x * x)) / 2
    return 1 - tail if x > 0 else tail


def t_ppf(p, df):
    if df == math.inf:
        return _Z.inv_cdf(p)
    if p < 0.5:
        return -t_ppf(1 - p, df)
    hi = 1.0
    while t_cdf(hi, df) < p:
        hi *= 2
    return _bisect(lambda x: t_cdf(x, df), p, 0.0, hi)


def z_ppf(p):
    return _Z.inv_cdf(p)


def wilson(k, n, alpha=0.05):
    z = z_ppf(1 - alpha / 2)
    centre = (k + z * z / 2) / (n + z * z)
    half = z / (n + z * z) * math.sqrt(k * (n - k) / n + z * z / 4)
    return max(0.0, centre - half), min(1.0, centre + half)


def clopper_pearson(k, n, alpha=0.05):
    lo = beta_ppf(alpha / 2, k, n - k + 1) if k > 0 else 0.0
    hi = beta_ppf(1 - alpha / 2, k + 1, n - k) if k < n else 1.0
    return lo, hi


def planned_n(errors, bound, alpha=0.05):
    n = max(errors, 1)
    while clopper_pearson(errors, n, alpha)[1] > bound:
        n += 1
    return n


def mean_diff(t, c, alpha=0.05, paired=False):
    effect = statistics.mean(t) - statistics.mean(c)
    if paired:
        diffs = [a - b for a, b in zip(t, c)]
        se = math.sqrt(statistics.variance(diffs) / len(diffs))
        df = len(diffs) - 1
    else:
        vt, vc = statistics.variance(t) / len(t), statistics.variance(c) / len(c)
        se = math.sqrt(vt + vc)
        df = (vt + vc) ** 2 / (vt ** 2 / (len(t) - 1) + vc ** 2 / (len(c) - 1)) if se else None
    if not se:
        return {"effect": effect, "lo": effect, "hi": effect, "se": 0.0, "df": None,
                "p": 1.0 if effect == 0 else 0.0}
    half = t_ppf(1 - alpha / 2, df) * se
    return {"effect": effect, "lo": effect - half, "hi": effect + half, "se": se, "df": df,
            "p": 2 * (1 - t_cdf(abs(effect) / se, df))}


def achieved_mde(se, alpha=0.05, power=0.80):
    return (z_ppf(1 - alpha / 2) + z_ppf(power)) * se


def tost(t, c, sesoi, alpha=0.05, paired=False):
    d = mean_diff(t, c, 2 * alpha, paired)
    return -sesoi < d["lo"] and d["hi"] < sesoi


def bh(pvalues, alpha=0.05):
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    k = max((r for r, i in enumerate(order, 1) if pvalues[i] <= alpha * r / m), default=0)
    top = set(order[:k])
    return [i in top for i in range(m)]


def holm(pvalues, alpha=0.05):
    m = len(pvalues)
    out = [False] * m
    for r, i in enumerate(sorted(range(m), key=lambda i: pvalues[i])):
        if pvalues[i] > alpha / (m - r):
            break
        out[i] = True
    return out


def bonferroni(pvalues, alpha=0.05):
    return [p <= alpha / len(pvalues) for p in pvalues]


def ebh(evalues, alpha=0.05):
    m = len(evalues)
    order = sorted(range(m), key=lambda i: -evalues[i])
    k = max((r for r, i in enumerate(order, 1) if evalues[i] >= m / (alpha * r)), default=0)
    top = set(order[:k])
    return [i in top for i in range(m)]


def ppi_mean(y, f, f_rest, alpha=0.05):
    n, big_n = len(y), len(f_rest)
    var_all = statistics.variance(list(f) + list(f_rest))
    lam = 0.0
    if var_all:
        my, mf = statistics.mean(y), statistics.mean(f)
        cov = sum((a - my) * (b - mf) for a, b in zip(y, f)) / (n - 1)
        lam = min(1.0, max(0.0, cov / ((1 + n / big_n) * var_all)))
    resid = [a - lam * b for a, b in zip(y, f)]
    estimate = lam * statistics.mean(f_rest) + statistics.mean(resid)
    half = z_ppf(1 - alpha / 2) * math.sqrt(statistics.variance(resid) / n
                                            + lam * lam * statistics.variance(f_rest) / big_n)
    return lam, estimate, estimate - half, estimate + half


def _hypergeom_cdf(k, population, good, draws):
    total = math.comb(population, draws)
    return sum(math.comb(good, x) * math.comb(population - good, draws - x)
               for x in range(k + 1)) / total


def hypergeometric_p(labels, n_total, recall):
    t = Fraction(str(recall))
    big_l, r = len(labels), sum(labels)
    best, k = 1.0, 0
    for u in range(1, big_l + 1):
        k += labels[big_l - u]
        good = math.floor(r / t + 1 - (r - k))
        population = n_total - (big_l - u)
        if 0 <= good <= population:
            best = min(best, _hypergeom_cdf(k, population, good, u))
    return best


def saturated(rows, run):
    seen = {i for row in rows[:-run] for i in row} if run else set()
    return all(i in seen for row in rows[len(rows) - run:] for i in row)


def brier(pairs):
    return statistics.mean((p - o) ** 2 for p, o in pairs)

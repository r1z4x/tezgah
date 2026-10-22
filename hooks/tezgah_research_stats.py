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

import math
import signal
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import tezgah_research_stats as s  # noqa: E402


class Proportions(unittest.TestCase):
    def test_zero_of_twenty(self):
        self.assertEqual("%.4f" % s.clopper_pearson(0, 20)[1], "0.1684")
        self.assertEqual("%.4f" % s.wilson(0, 20)[1], "0.1611")
        self.assertEqual(s.wilson(0, 20)[0], 0.0)

    def test_clopper_pearson_two_sided(self):
        lo, hi = s.clopper_pearson(3, 10)
        self.assertEqual(("%.4f" % lo, "%.4f" % hi), ("0.0667", "0.6525"))

    def test_planned_n_is_the_smallest(self):
        self.assertEqual(s.planned_n(0, 0.05), 72)
        self.assertEqual(s.planned_n(1, 0.05), 110)
        self.assertEqual("%.4f" % s.clopper_pearson(0, 72)[1], "0.0499")
        self.assertEqual("%.4f" % s.clopper_pearson(1, 109)[1], "0.0501")


class Means(unittest.TestCase):
    def test_welch_interval_at_df_two(self):
        d = s.mean_diff([120, 121], [90, 91])
        se = math.sqrt(0.5 / 2 + 0.5 / 2)
        t = 0.95 / math.sqrt(2 * 0.975 * 0.025)  # exact 0.975 t quantile at df 2
        self.assertAlmostEqual(d["df"], 2.0)
        self.assertEqual(d["effect"], 30)
        self.assertAlmostEqual(d["lo"], 30 - t * se, places=9)
        self.assertAlmostEqual(d["hi"], 30 + t * se, places=9)
        mde = (statistics.NormalDist().inv_cdf(0.975) + statistics.NormalDist().inv_cdf(0.8)) * se
        self.assertAlmostEqual(s.achieved_mde(d["se"]), mde)

    def test_t_quantile(self):
        self.assertAlmostEqual(s.t_ppf(0.975, 10), 2.228138852, places=8)
        self.assertAlmostEqual(s.t_ppf(0.025, 10), -2.228138852, places=8)

    def test_paired_and_zero_se(self):
        d = s.mean_diff([3, 5, 7], [1, 2, 4], paired=True)
        self.assertEqual(d["df"], 2)
        self.assertAlmostEqual(d["effect"], 8 / 3)
        z = s.mean_diff([5, 5], [5, 5])
        self.assertEqual((z["lo"], z["hi"], z["se"], z["p"]), (0, 0, 0.0, 1.0))

    def test_tost_verdicts(self):
        self.assertFalse(s.tost([91, 119], [120, 90], 5))
        self.assertTrue(s.tost([91, 119], [120, 90], 200))


class Multiplicity(unittest.TestCase):
    P = [0.01, 0.02, 0.03, 0.5]

    def test_bh_holm_bonferroni(self):
        self.assertEqual(s.bh(self.P), [True, True, True, False])
        self.assertEqual(s.holm(self.P), [True, False, False, False])
        self.assertEqual(s.bonferroni(self.P), [True, False, False, False])

    def test_ebh(self):
        # m / (alpha k) = 80, 40, 26.7, 20 against e sorted 100, 50, 30, 2: k = 3
        self.assertEqual(s.ebh([100, 30, 2, 50]), [True, True, False, True])
        self.assertEqual(s.ebh([10, 2]), [False, False])


class Instruments(unittest.TestCase):
    def test_ppi_lambda_hat(self):
        y, f, rest = [1, 0, 1, 1, 0], [1, 1, 1, 1, 0], [0, 1, 0, 1, 1, 0, 1]
        my, mf = statistics.mean(y), statistics.mean(f)
        cov = sum((a - my) * (b - mf) for a, b in zip(y, f)) / 4
        lam = min(1.0, max(0.0, cov / ((1 + 5 / 7) * statistics.variance(f + rest))))
        est = lam * statistics.mean(rest) + statistics.mean([a - lam * b for a, b in zip(y, f)])
        got = s.ppi_mean(y, f, rest)
        self.assertAlmostEqual(got[0], lam)
        self.assertAlmostEqual(got[1], est)
        self.assertLess(got[2], est)
        self.assertGreater(got[3], est)

    def test_ppi_constant_f_gives_lambda_zero(self):
        lam, est, lo, hi = s.ppi_mean([1, 0, 1], [1, 1, 1], [1, 1, 1, 1])
        self.assertEqual(lam, 0.0)
        self.assertAlmostEqual(est, 2 / 3)

    def test_ppi_with_one_gold_or_one_other_item_has_no_interval(self):
        lam, est, lo, hi = s.ppi_mean([1], [1], [0, 1, 1])
        self.assertEqual((lam, est, lo, hi), (0.0, 1.0, None, None))
        lam, est, lo, hi = s.ppi_mean([1, 0], [1, 0], [1])
        self.assertEqual((lo, hi), (None, None))
        self.assertGreaterEqual(lam, 0.0)


class Quantiles(unittest.TestCase):
    """Every quantile helper ends on every input: a p outside (0, 1) is a ValueError,
    never an endless search (review round one, D3-3: alpha 5 made t_ppf loop)."""

    def bounded(self, fn, *args):
        def stop(signum, frame):
            raise AssertionError("%s%r did not finish within 10s" % (fn.__name__, args))
        old = signal.signal(signal.SIGALRM, stop)
        signal.alarm(10)
        try:
            return fn(*args)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    def test_p_outside_the_open_unit_interval_is_a_value_error(self):
        for p in (-1.5, 0.0, 1.0, 2.5, math.nan, math.inf):
            for fn, args in ((s.t_ppf, (p, 10)), (s.t_ppf, (p, math.inf)), (s.z_ppf, (p,)),
                             (s.beta_ppf, (p, 1, 2))):
                with self.assertRaises(ValueError, msg="%s%r" % (fn.__name__, args)):
                    self.bounded(fn, *args)

    def test_df_that_is_not_positive_is_a_value_error(self):
        for df in (0, -1, math.nan):
            with self.assertRaises(ValueError):
                self.bounded(s.t_ppf, 0.975, df)

    def test_extreme_p_and_df_still_end(self):
        self.assertGreater(self.bounded(s.t_ppf, 1 - 1e-12, 1), 1e5)
        self.assertGreater(self.bounded(s.t_ppf, 0.975, 1e-300), 0)


class Stopping(unittest.TestCase):
    def test_buscarpy_oracle(self):
        met = s.hypergeometric_p([1] * 95 + [0] * 155, 300, 0.95)
        not_met = s.hypergeometric_p([1] * 95 + [0] * 25, 300, 0.95)
        self.assertEqual("%.6f" % met, "0.000166")
        self.assertEqual("%.6f" % not_met, "0.453536")
        self.assertLess(met, 1 - 0.95)
        self.assertGreaterEqual(not_met, 1 - 0.95)

    def test_saturation(self):
        self.assertTrue(s.saturated([["a", "b"], ["b"]], 1))
        self.assertFalse(s.saturated([["a"], ["b"]], 1))
        self.assertFalse(s.saturated([["a"]], 1))


class Calibration(unittest.TestCase):
    def test_brier(self):
        self.assertAlmostEqual(s.brier([(0.8, 1), (0.3, 0), (0.6, 0)]),
                               (0.2 ** 2 + 0.3 ** 2 + 0.6 ** 2) / 3)


if __name__ == "__main__":
    unittest.main()

import math
import unittest

from experiment_guard.stats import (
    cuped_adjust,
    difference_in_proportions,
    normal_cdf,
    normal_quantile,
    obrien_fleming_threshold,
    required_sample_size_for_proportion,
    srm_test,
)


class StatisticsTests(unittest.TestCase):
    def test_normal_quantile_round_trip(self):
        for probability in (0.001, 0.025, 0.5, 0.975, 0.999):
            self.assertAlmostEqual(
                normal_cdf(normal_quantile(probability)), probability, places=6
            )

    def test_balanced_split_has_no_srm(self):
        chi_square, p_value = srm_test(5_000, 5_000)
        self.assertEqual(chi_square, 0.0)
        self.assertEqual(p_value, 1.0)

    def test_skewed_split_triggers_srm(self):
        _, p_value = srm_test(5_600, 4_400)
        self.assertLess(p_value, 0.001)

    def test_proportion_effect_direction(self):
        result = difference_in_proportions(1_000, 5_000, 1_150, 5_000)
        self.assertGreater(result.absolute, 0.0)
        self.assertLess(result.p_value, 0.01)
        self.assertGreater(result.ci_low, 0.0)

    def test_cuped_reduces_variance_for_correlated_covariate(self):
        control_pre = tuple(float(value) for value in range(1, 101))
        treatment_pre = tuple(float(value) for value in range(1, 101))
        control = tuple(2.5 * value + math.sin(value) for value in control_pre)
        treatment = tuple(
            2.5 * value + 4.0 + math.sin(value) for value in treatment_pre
        )
        result = cuped_adjust(
            control, control_pre, treatment, treatment_pre
        )
        self.assertGreater(result.variance_reduction, 0.95)
        self.assertAlmostEqual(result.absolute, 4.0, delta=0.25)

    def test_power_size_is_reasonable(self):
        size = required_sample_size_for_proportion(0.25, 0.02)
        self.assertGreater(size, 5_000)
        self.assertLess(size, 20_000)

    def test_sequential_boundary_relaxes_over_time(self):
        early_z, early_p = obrien_fleming_threshold(0.25)
        final_z, final_p = obrien_fleming_threshold(1.0)
        self.assertGreater(early_z, final_z)
        self.assertLess(early_p, final_p)
        self.assertAlmostEqual(final_p, 0.05, places=6)


if __name__ == "__main__":
    unittest.main()

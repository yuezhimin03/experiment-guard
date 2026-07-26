import csv
import tempfile
import unittest
from pathlib import Path

from experiment_guard.analysis import ExperimentAnalyzer, load_metrics
from experiment_guard.simulator import simulate_experiment


class AnalysisTests(unittest.TestCase):
    def test_end_to_end_analysis(self):
        with tempfile.TemporaryDirectory() as temp:
            csv_path = Path(temp) / "users.csv"
            simulate_experiment(csv_path, users=4_000, seed=11)
            result = ExperimentAnalyzer().analyze(csv_path)
            self.assertEqual(result.control_users + result.treatment_users, 4_000)
            self.assertTrue(result.srm_passed)
            self.assertEqual(result.primary.name, "D7 留存率")
            self.assertGreater(result.cuped_variance_reduction, 0.2)
            self.assertEqual(len(result.guardrails), 2)

    def test_loader_rejects_duplicate_users(self):
        with tempfile.TemporaryDirectory() as temp:
            csv_path = Path(temp) / "bad.csv"
            headers = [
                "user_id",
                "variant",
                "d7_retained",
                "payer",
                "revenue",
                "playtime_minutes",
                "pre_playtime_minutes",
                "crashed",
                "session_count",
            ]
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers)
                writer.writeheader()
                for index in range(100):
                    writer.writerow(
                        {
                            "user_id": "duplicate" if index < 2 else f"u{index}",
                            "variant": "A" if index % 2 else "B",
                            "d7_retained": 0,
                            "payer": 0,
                            "revenue": 0,
                            "playtime_minutes": 1,
                            "pre_playtime_minutes": 1,
                            "crashed": 0,
                            "session_count": 1,
                        }
                    )
            with self.assertRaisesRegex(ValueError, "duplicate user_id"):
                load_metrics(csv_path)


if __name__ == "__main__":
    unittest.main()


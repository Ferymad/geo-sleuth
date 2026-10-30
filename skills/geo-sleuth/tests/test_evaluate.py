#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Public CLI regressions for scoring, denominator integrity and input identity."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate.py"


class EvaluationCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_score(self, truth, predictions, *extra):
        for name, rows in (("truth", truth), ("predictions", predictions)):
            (self.root / (name + ".json")).write_text(json.dumps(rows), encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), "--truth", "truth.json", "--predictions", "predictions.json", *extra],
                              cwd=self.root, capture_output=True, text=True, encoding="utf-8")

    def test_missing_and_abstained_cases_stay_in_denominator(self):
        truth = [{"case_id": k, "lat": 0, "lon": 0} for k in "abc"]
        run = self.run_score(truth, [{"case_id": "a", "lat": 0, "lon": 0, "radius_m": 25}, {"case_id": "b", "abstain": True}])
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(run.stdout)
        self.assertEqual((report["n_cases"], report["n_predicted"], report["n_abstained"], report["n_missing"]), (3, 1, 1, 1))
        self.assertAlmostEqual(report["accuracy_all_cases"]["25"], 1 / 3)
        self.assertEqual(report["accuracy_predicted_only"]["25"], 1)
        self.assertEqual(report["input_sha256"]["predictions"], hashlib.sha256((self.root / "predictions.json").read_bytes()).hexdigest())

    def test_dateline_distance_and_false_precision(self):
        run = self.run_score([{"case_id": "x", "lat": 0, "lon": 179.999}],
                             [{"case_id": "x", "lat": 0, "lon": -179.999, "radius_m": 100}])
        report = json.loads(run.stdout)
        # Equatorial 0.002 degrees is about 222.4 m, not a nearly global trip.
        self.assertAlmostEqual(report["cases"][0]["error_m"], 222.39, delta=0.1)
        self.assertEqual(report["radius_claims"]["false_precision_le_100m"], 1)
        self.assertEqual(report["radius_claims"]["empirical_coverage"], 0)

    def test_empty_predictions_are_honest_null_not_nan(self):
        run = self.run_score([{"case_id": "x", "lat": 0, "lon": 0}], [])
        report = json.loads(run.stdout)
        self.assertIsNone(report["median_error_m_predicted_only"])
        self.assertIsNone(report["accuracy_predicted_only"]["100"])
        self.assertEqual(report["accuracy_all_cases"]["100"], 0)

    def test_invalid_and_duplicate_records_are_rejected(self):
        good = {"case_id": "x", "lat": 0, "lon": 0}
        cases = [([good, good], []), ([good], [good, good]),
                 ([good], [{**good, "case_id": "unknown"}]),
                 ([good], [{**good, "lat": True}]),
                 ([good], [{**good, "lon": 181}]),
                 ([good], [{**good, "lat": float("nan")}]),
                 ([good], [{**good, "radius_m": -1}]),
                 ([good], [{**good, "radius_m": float("inf")}]),
                 ([good], [{**good, "abstain": "yes"}]),
                 ([good], [{**good, "abstain": True}]),
                 ([good], [{"case_id": "x", "lat": 0}]),
                 ([], []), ({}, []), ([good], {})]
        for truth, predictions in cases:
            with self.subTest(truth=truth, predictions=predictions):
                run = self.run_score(truth, predictions)
                self.assertEqual(run.returncode, 2, run.stdout)
                self.assertNotIn("Traceback", run.stderr)

    def test_output_does_not_overwrite_inputs(self):
        run = self.run_score([{"case_id": "x", "lat": 0, "lon": 0}], [], "--out", "truth.json")
        self.assertEqual(run.returncode, 2)
        self.assertIn("must not overwrite", run.stderr)
        self.assertIsInstance(json.loads((self.root / "truth.json").read_text(encoding="utf-8")), list)

    def test_hardlinked_output_cannot_overwrite_inputs(self):
        good = {"case_id": "x", "lat": 0, "lon": 0}
        for name in ("truth", "predictions"):
            with self.subTest(input=name):
                link = self.root / "metrics.json"
                if link.exists():
                    link.unlink()
                target = self.root / (name + ".json")
                target.write_text(json.dumps([good]), encoding="utf-8")
                os.link(target, link)
                run = self.run_score([good], [good], "--out", "metrics.json")
                self.assertEqual(run.returncode, 2, run.stdout)
                self.assertIsInstance(json.loads(target.read_text(encoding="utf-8")), list)

    def test_extreme_numbers_are_safe_and_errors_are_clean(self):
        good = {"case_id": "x", "lat": 0, "lon": 0}
        for key in ("lat", "radius_m"):
            with self.subTest(key=key):
                run = self.run_score([good], [{**good, key: 10 ** 400}])
                self.assertEqual(run.returncode, 2)
                self.assertNotIn("Traceback", run.stderr)
        truth = [good, {**good, "case_id": "y"}]
        predictions = [{**r, "radius_m": 1e308} for r in truth]
        run = self.run_score(truth, predictions)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["radius_claims"]["median_radius_m"], 1e308)

    def test_output_file_matches_stdout_and_radius_omission_is_visible(self):
        run = self.run_score([{"case_id": "x", "lat": 51, "lon": -8}], [{"case_id": "x", "lat": 51, "lon": -8}], "--out", "metrics.json")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual((self.root / "metrics.json").read_text(encoding="utf-8"), run.stdout)
        self.assertEqual(json.loads(run.stdout)["radius_claims"]["n_without_radius"], 1)


if __name__ == "__main__":
    unittest.main()

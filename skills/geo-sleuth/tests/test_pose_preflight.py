# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "pillow-heif", "numpy"]
# ///
"""Public CLI tests; no solver calls, real images, or network needed."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pose_preflight.py"


def spec():
    return {"image_size": [1000, 800], "frame": "upright",
            "init": {"at": [53, -8], "height": 30, "hfov": 65},
            "points": [{"px": px, "ll": ll, "h": h, "units": "m",
                        "vertical_reference": "local", "height_kind": "local_elevation",
                        "source_url": "field notebook"}
                       for px, ll, h in [([100, 100], [53.001, -8.001], 0),
                                         ([900, 100], [53.002, -7.999], 10),
                                         ([900, 700], [53.003, -8.002], 20),
                                         ([100, 700], [53.004, -7.998], 0),
                                         ([500, 400], [53.005, -8.001], 30)]]}


class PreflightCLI(unittest.TestCase):
    def run_cli(self, data, raw=False):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            src, out = Path(tmp) / "spec.json", Path(tmp) / "report.json"
            if isinstance(data, bytes):
                src.write_bytes(data)
            else:
                src.write_text(data if raw else json.dumps(data), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPT), str(src), "--out", str(out)],
                                  text=True, capture_output=True)
            self.assertTrue(out.exists(), proc.stderr)
            return proc, json.loads(out.read_text())

    def test_normal_deterministic(self):
        proc, report = self.run_cli(spec())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(report["valid_input"])
        self.assertEqual(report["counts"]["free_parameters"], 7)
        self.assertEqual(report["counts"]["dof"], 3)
        self.assertTrue(report["counts"]["leave_one_out_redundant"])
        self.assertEqual(report, self.run_cli(spec())[1])

    def codes(self, report):
        return {w["code"] for w in report["warnings"]}

    def test_invalid_inputs(self):
        cases = [None, [], {}, {"image_size": [0, 800]},
                 {"image_size": [1000, 1.5]}, {"image_size": [True, 800]},
                 {"init": {}}, {"init": {"at": [91, 0]}},
                 {"init": {"at": [53, -8], "hfov": 0}},
                 {"init": {"at": [53, -8], "hfov": 180}},
                 {"init": {"at": [53, -8], "height": "30"}},
                 {"fix": ["heading"]}, {"fix": None}, {"fix": [{}]},
                 {"points": []}, {"points": {}}, {"points": [None]},
                 {"image_size": {"width": 1000, "height": 800}}, {"init": []}]
        for change in cases:
            data = spec()
            if isinstance(change, dict) and change:
                data.update(change)
            else:
                data = change
            with self.subTest(change=change):
                proc, report = self.run_cli(data)
                self.assertEqual(proc.returncode, 1)
                self.assertFalse(report["valid_input"])
                self.assertTrue(report["errors"])
        for key, value in [("px", [1, 2, 3]), ("px", [float("nan"), 2]),
                           ("ll", [53, 181]), ("h", float("inf")), ("h", True)]:
            data = spec()
            data["points"][0][key] = value
            self.assertFalse(self.run_cli(data)[1]["valid_input"])
        self.assertFalse(self.run_cli('{"broken":', raw=True)[1]["valid_input"])

    def test_extreme_numeric_and_encoding_inputs(self):
        span = spec()
        span["image_size"] = [1, 1]
        span["points"][0]["px"] = [1e308, 0]
        span["points"][1]["px"] = [-1e308, 0]
        norm = spec()
        norm["points"][0]["px"] = [1e308, 0]
        huge_int = spec()
        huge_int["points"][0]["px"] = [10**400, 0]
        for data in (span, norm, huge_int, b'{"frame": "\xff"}'):
            with self.subTest(data=repr(data)[:80]):
                proc, report = self.run_cli(data)
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertFalse(report["valid_input"])
                self.assertTrue(report["errors"])
                self.assertNotIn("Traceback", proc.stderr)
                self.assertNotIn("RuntimeWarning", proc.stderr)
                json.dumps(report, allow_nan=False)

    def test_large_finite_dimensions(self):
        data = spec()
        data["image_size"] = [10**308, 10**308]
        data["points"][0]["h"] = 10**308
        data["points"][1]["h"] = -10**308
        proc, report = self.run_cli(data)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(report["valid_input"])
        json.dumps(report, allow_nan=False)

    def test_numerical_and_serialization_failure_reports(self):
        # Inject hard-to-trigger library failures at the public CLI boundary.
        guard = '''import sys
sys.path.insert(0, sys.argv[1])
import numpy as np
import pose_preflight as module
if sys.argv[2] == "svd":
    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError("SVD did not converge")
    np.linalg.svd = fail
else:
    module.preflight = lambda spec: {"valid_input": True, "value": float("inf")}
sys.argv = [module.__file__, *sys.argv[3:]]
raise SystemExit(module.main())
'''
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            src = Path(tmp)/"spec.json"
            src.write_text(json.dumps(spec()), encoding="utf-8")
            for mode in ("svd", "serialize"):
                with self.subTest(mode=mode):
                    out = Path(tmp)/f"{mode}.json"
                    proc = subprocess.run([sys.executable, "-c", guard, str(SCRIPT.parent),
                                           mode, str(src), "--out", str(out)],
                                          capture_output=True, text=True)
                    self.assertEqual(proc.returncode, 1, proc.stderr)
                    self.assertNotIn("Traceback", proc.stderr)
                    report = json.loads(out.read_text(encoding="utf-8"))
                    self.assertFalse(report["valid_input"])
                    self.assertTrue(report["errors"])
                    json.dumps(report, allow_nan=False)

    def test_malformed_validation_without_optional_imports(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            src, out = Path(tmp)/"bad.json", Path(tmp)/"report.json"
            src.write_text('{"image_size": [0, 0]}')
            proc = subprocess.run([sys.executable, "-S", str(SCRIPT), str(src), "--out", str(out)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stderr)
            self.assertFalse(json.loads(out.read_text())["valid_input"])

    def test_duplicates(self):
        data = spec()
        data["points"].append(copy.deepcopy(data["points"][0]))
        report = self.run_cli(data)[1]
        self.assertTrue(report["valid_input"])
        self.assertIn("DUPLICATE_CONTROL", self.codes(report))
        self.assertEqual(report["counts"]["points"], 6)
        self.assertEqual(report["counts"]["distinct_observations"], 5)
        self.assertEqual(report["counts"]["dof"], 5)  # Deliberately raw, not independent support.
        for field, value in [("px", [300, 300]), ("ll", [54, -8])]:
            bad = copy.deepcopy(data)
            bad["points"][-1][field] = value
            self.assertFalse(self.run_cli(bad)[1]["valid_input"])

    def test_planar_datum_and_missing_heights(self):
        data = spec()
        for q in data["points"]:
            q["h"] = 0  # Explicit shared local plane, not an error.
        report = self.run_cli(data)[1]
        self.assertTrue(report["valid_input"])
        self.assertIn("PLANAR_WORLD", self.codes(report))
        self.assertNotIn("MISSING_HEIGHT_METADATA", self.codes(report))
        del data["points"][0]["h"]
        data["points"][1]["vertical_reference"] = "EGM2008"
        data["points"][1]["units"] = "ft"
        report = self.run_cli(data)[1]
        self.assertTrue(report["valid_input"])
        self.assertTrue({"MIXED_VERTICAL_REFERENCE", "MIXED_UNITS", "MISSING_HEIGHT_METADATA",
                         "NON_METRIC_UNITS"} <= self.codes(report))
        self.assertTrue(report["missing_inputs"])

    def test_rank_span_frame_and_bounds(self):
        data = spec()
        for i, q in enumerate(data["points"]):
            q.update(ll=[53 + (i+1)*0.001, -8], px=[500+i, 400+i], h=0)
        del data["frame"]
        report = self.run_cli(data)[1]
        self.assertTrue(report["valid_input"])
        self.assertTrue({"NEAR_COLLINEAR_WORLD", "SMALL_IMAGE_SPAN", "NARROW_INIT_GEOMETRY",
                         "FRAME_UNKNOWN", "MISSING_CROP", "MISSING_PRINCIPAL_POINT",
                         "MISSING_DISTORTION"} <= self.codes(report))
        for frame in ("stored", "upright"):
            data["frame"] = frame
            data["points"][0]["px"] = [-1, 0]
            report = self.run_cli(data)[1]
            self.assertTrue(report["valid_input"])
            self.assertEqual(report["diagnostics"]["frame"], frame)
            self.assertIn("PIXEL_OUTSIDE_IMAGE", self.codes(report))

    def test_fix_options_and_loo(self):
        for fixed, k in [([], 7), (["hfov"], 6), (["height"], 6), (["roll"], 6),
                         (["hfov", "height", "roll"], 4)]:
            data = spec()
            data["points"] = data["points"][:3]
            data["fix"] = fixed
            report = self.run_cli(data)[1]
            self.assertEqual(report["counts"]["free_parameters"], k)
            self.assertEqual(report["counts"]["dof"], 6-k)
            self.assertEqual(report["valid_input"], k <= 6)
            self.assertFalse(report["counts"]["leave_one_out_redundant"])
            self.assertIn("LOO_NO_REDUNDANCY", self.codes(report))

    def test_no_network_download_or_optimizer(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            src, out = Path(tmp)/"spec.json", Path(tmp)/"report.json"
            src.write_text(json.dumps(spec()))
            guard = '''import runpy, sys
sys.path.insert(0, sys.argv[1])
import pose, socket, subprocess, urllib.request

def forbidden(*args, **kwargs):
    raise AssertionError("network/process/optimizer forbidden")

socket.socket = socket.create_connection = urllib.request.urlopen = forbidden
subprocess.Popen = forbidden
for name in ("solve", "lm", "mc_radius", "leave_one_out", "project"):
    setattr(pose, name, forbidden)
script = sys.argv[2]
sys.argv = sys.argv[2:]
runpy.run_path(script, run_name="__main__")
'''
            proc = subprocess.run([sys.executable, "-c", guard, str(SCRIPT.parent),
                                   str(SCRIPT), str(src), "--out", str(out)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json.loads(out.read_text())["valid_input"])

    def test_new_output_only(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as tmp:
            src, out = Path(tmp)/"spec.json", Path(tmp)/"report.json"
            src.write_text(json.dumps(spec()))
            out.write_text("keep me")
            proc = subprocess.run([sys.executable, str(SCRIPT), str(src), "--out", str(out)],
                                  capture_output=True)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(out.read_text(), "keep me")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Offline public-CLI tests using SYNTHETIC format fixtures, not solver outputs.

Run: python3 skills/geo-sleuth/tests/test_fspy.py
The separate real upstream example probe is documented in research/fspy-bridge.md.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fspy.py"


def synthetic_project(state=None, image=b"", *, raw_state=None, version=1):
    """Construct documented v1 framing only; no calibration is simulated."""
    if raw_state is None:
        raw_state = json.dumps(state if state is not None else {
            "cameraParameters": None
        }).encode("utf-8")
    return struct.pack("<4sIII", b"fspy", version, len(raw_state), len(image)) + raw_state + image


class FspyCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "synthetic.fspy"

    def run_cli(self, payload=None, *args):
        if payload is not None:
            self.project.write_bytes(payload)
        return subprocess.run([sys.executable, str(SCRIPT), str(self.project), *map(str, args)],
                              capture_output=True, text=True, timeout=10)

    def assert_invalid(self, payload):
        result = self.run_cli(payload)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        return result

    def test_raw_camera_sha_and_private_image_not_extracted(self):
        camera = {"principalPoint": {"x": 0, "y": 0},
                  "horizontalFieldOfView": 0.8, "imageWidth": 1200,
                  "cameraTransform": {"rows": [[1, 0, 0, 5]]},
                  "futureField": "preserve unchanged"}
        payload = synthetic_project({"cameraParameters": camera}, b"PRIVATE_IMAGE_BYTES")
        result = self.run_cli(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["camera_parameters_raw"], camera)
        self.assertEqual(report["project"]["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(report["project"]["version"], 1)
        self.assertEqual(report["embedded_image"], {
            "present": True, "size_bytes": 19, "extracted": False,
            "decoded": False, "metadata_inspected": False})
        self.assertNotIn("PRIVATE_IMAGE_BYTES", result.stdout)
        self.assertEqual(list(self.root.iterdir()), [self.project])
        self.assertIsNone(report["verified_metric_scale"])
        self.assertIsNone(report["verified_geographic_anchor"])

    def test_null_missing_and_nonobject_calibration_warnings(self):
        for state, warning in [({"cameraParameters": None}, "is null"),
                               ({}, "is absent"), ({"cameraParameters": []}, "not an object")]:
            with self.subTest(state=state):
                result = self.run_cli(synthetic_project(state))
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertIn(warning, " ".join(report["warnings"]))
                self.assertFalse(report["embedded_image"]["present"])
                self.assertEqual(report["camera_parameters_present"], "cameraParameters" in state)

    def test_reference_units_do_not_establish_metric_or_geography(self):
        for axis in (None, "xPositive"):
            ref = {"referenceDistance": 2.5, "referenceDistanceUnit": "Meters",
                   "referenceDistanceAxis": axis}
            result = self.run_cli(synthetic_project({"cameraParameters": {},
                "calibrationSettingsBase": ref, "latitude": 42, "longitude": 8}))
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["reference_settings_raw"], ref)
            self.assertIsNone(report["verified_metric_scale"])
            self.assertIsNone(report["verified_geographic_anchor"])
            self.assertIn("not verified physical", " ".join(report["warnings"]))

    def test_new_output_report(self):
        out = self.root / "report.json"
        payload = synthetic_project()
        result = self.run_cli(payload, "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(out.read_text())["project"]["sha256"],
                         hashlib.sha256(payload).hexdigest())
        self.assertEqual(self.project.read_bytes(), payload)

    def test_output_rejects_input_and_hardlink_and_symlink(self):
        payload = synthetic_project()
        self.project.write_bytes(payload)
        hardlink = self.root / "hardlink.json"
        os.link(self.project, hardlink)
        symlink = self.root / "symlink.json"
        symlink.symlink_to(self.project)
        for out in (self.project, hardlink, symlink, self.root / "." / "synthetic.fspy"):
            with self.subTest(out=out):
                result = self.run_cli(None, "--out", out)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.project.read_bytes(), payload)

    def test_output_rejects_existing_report_and_dangling_symlink(self):
        out = self.root / "report.json"
        out.write_text("KEEP")
        dangling = self.root / "dangling.json"
        dangling.symlink_to(self.root / "nonexistent")
        for target in (out, dangling):
            result = self.run_cli(synthetic_project(), "--out", target)
            self.assertEqual(result.returncode, 2)
        self.assertEqual(out.read_text(), "KEEP")
        self.assertFalse((self.root / "nonexistent").exists())

    def test_rejects_truncated_header(self):
        for length in range(16):
            with self.subTest(length=length):
                self.assert_invalid(synthetic_project()[:length])

    def test_rejects_bad_magic_and_version(self):
        self.assert_invalid(b"NOPE" + synthetic_project()[4:])
        for version in (0, 2, 0xffffffff):
            with self.subTest(version=version):
                self.assert_invalid(synthetic_project(version=version))

    def test_rejects_oversized_state_before_allocation(self):
        result = self.assert_invalid(struct.pack("<4sIII", b"fspy", 1, 16 * 1024 * 1024 + 1, 0))
        self.assertIn("inspection limit", result.stderr)

    def test_rejects_truncated_state_image_trailing_and_declared_lengths(self):
        payload = synthetic_project(image=b"123")
        for data in (payload[:17], payload[:-1], payload + b"X",
                     payload[:12] + struct.pack("<I", 0) + payload[16:]):
            with self.subTest(length=len(data)):
                self.assert_invalid(data)

    def test_rejects_invalid_utf8_json_duplicates_and_nonfinite_numbers(self):
        for raw in (b"\xff", b"{", b"[]", b"null", b"1", b'{}{}',
                    b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}',
                    b'{"x":-Infinity}', b'{"x":1e999}'):
            with self.subTest(raw=raw):
                self.assert_invalid(synthetic_project(raw_state=raw))

    def test_rejects_deep_json_without_traceback(self):
        out = self.root / "report.json"
        result = self.run_cli(synthetic_project(
            raw_state=b'{"x":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'),
            "--out", out)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("64-level nesting inspection limit", result.stderr)
        self.assertNotIn("invalid UTF-8 JSON", result.stderr)
        self.assertFalse(out.exists())

    def test_nesting_limit_boundary_for_objects_and_arrays(self):
        # The root object counts as level 1; both container types count.
        for opening, closing in ((b'[', b']'), (b'{"x":', b'}')):
            for depth in (63, 64, 65):
                with self.subTest(opening=opening, depth=depth):
                    raw = b'{"cameraParameters":' + opening * (depth - 1)
                    raw += b'0' + closing * (depth - 1) + b'}'
                    payload = synthetic_project(raw_state=raw)
                    if depth <= 64:
                        result = self.run_cli(payload)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        json.loads(result.stdout)
                    else:
                        result = self.assert_invalid(payload)
                        self.assertIn("64-level nesting inspection limit", result.stderr)

    def test_quoted_brackets_escaped_quotes_and_backslashes_are_not_nesting(self):
        strings = ['[' * 2000, '{' * 2000, '}]' * 2000,
                   '\\"[{]}', '\\\\', 'é雪 [ ] { }', 'bracket-key[{' * 100]
        for text in strings:
            with self.subTest(text=text[:30]):
                # Include strings as keys too, followed by a real container.
                camera = {text: text, "after": {"rows": [[1, 0, 0, 0]]}}
                result = self.run_cli(synthetic_project({"cameraParameters": camera}))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["camera_parameters_raw"], camera)

    def test_normal_camera_matrices_preserved(self):
        matrix = {"rows": [[1, 0, 0, 0], [0, 1, 0, 0],
                           [0, 0, 1, 0], [0, 0, 0, 1]]}
        camera = {"cameraTransform": matrix, "viewTransform": matrix}
        result = self.run_cli(synthetic_project({"cameraParameters": camera}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["camera_parameters_raw"], camera)

    def test_invalid_input_does_not_create_output(self):
        out = self.root / "report.json"
        result = self.run_cli(b"invalid", "--out", out)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(out.exists())

    def test_missing_directory_and_fifo_errors_are_clean(self):
        for target in (self.root / "missing", self.root):
            result = subprocess.run([sys.executable, str(SCRIPT), str(target)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
        if hasattr(os, "mkfifo"):
            os.mkfifo(self.project)
            result = self.run_cli()
            self.assertEqual(result.returncode, 2)
            self.assertIn("regular file", result.stderr)


if __name__ == "__main__":
    unittest.main()

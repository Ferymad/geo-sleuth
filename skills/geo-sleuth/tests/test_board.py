#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Offline board regressions. Run: uv run skills/geo-sleuth/tests/test_board.py"""
from __future__ import annotations

from argparse import Namespace
import contextlib
import io
import json
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import board  # noqa: E402


class CorridorPendingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "board.json"
        self.output = self.root / "scan.json"
        self.output.write_text('{"hits": []}', encoding="utf-8")
        self.run_board("init", "--photo", "photo.jpg")

    def run_board(self, *args, ok=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "board.py"), "--board", str(self.path), *args],
            cwd=self.root, capture_output=True, text=True, encoding="utf-8",
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def read_board(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def clue(self, kind="infra", status="observed", *extra):
        self.run_board("clue", "A spatial observation or its computed test", "--kind", kind,
                       "--status", status, *extra)

    def pending(self):
        return board._corridor_pending(self.read_board())

    def test_alias_is_normalized_when_recorded(self):
        self.clue("infrastructure")
        self.assertEqual(self.read_board()["clues"]["K1"]["kind"], "infra")
        self.assertEqual(self.pending(), ["K1"])
        self.assertIn("infrastructure clue K1", self.run_board("next").stdout)

    def test_legacy_alias_is_detected_without_rewriting_board(self):
        self.clue()
        data = self.read_board()
        data["clues"]["K1"]["kind"] = "infrastructure"
        self.path.write_text(json.dumps(data), encoding="utf-8")
        before = self.path.read_bytes()
        self.assertEqual(self.pending(), ["K1"])
        self.assertIn("infrastructure clue K1", self.run_board("next").stdout)
        self.assertEqual(self.path.read_bytes(), before)

    def test_unlinked_computations_do_not_clear_infrastructure(self):
        self.clue()
        self.clue("infrastructure", "read")
        for kind in ("terrain", "corridor", "infra"):
            with self.subTest(kind=kind):
                self.clue(kind, "computed", "--file", str(self.output))
                self.assertEqual(self.pending(), ["K1", "K2"])

    def test_computation_clears_only_explicitly_linked_clues(self):
        self.clue()
        self.clue("infrastructure", "read")
        self.clue("terrain", "computed", "--file", str(self.output), "--resolves", "K1")
        self.assertEqual(self.pending(), ["K2"])
        self.assertIn("infrastructure clue K2", self.run_board("next").stdout)
        self.assertEqual(self.read_board()["clues"]["K3"]["resolves"], ["K1"])
        self.clue("corridor", "computed", "--file", str(self.output),
                  "--resolves", "K1", "--resolves", "K2")
        self.assertEqual(self.pending(), [])
        self.assertNotIn("infrastructure clue", self.run_board("next").stdout)
        # Recording a computation is separate from scoring candidate evidence.
        self.assertEqual(self.read_board()["evidence"], [])

    def test_unrelated_explicit_link_does_not_clear_infrastructure(self):
        self.clue()
        self.clue("terrain")
        self.clue("terrain", "computed", "--file", str(self.output), "--resolves", "K2")
        self.assertEqual(self.pending(), ["K1"])

    def test_invalid_completion_is_rejected_without_mutation(self):
        self.clue()
        before = self.path.read_bytes()
        cases = [
            ("--status", "observed", "--file", str(self.output), "--resolves", "K1"),
            ("--status", "computed", "--file", str(self.output), "--resolves", "K99"),
            ("--status", "computed", "--file", str(self.output), "--resolves", "K1", "--resolves", "K99"),
            ("--status", "computed", "--resolves", "K1"),
            ("--status", "computed", "--file", str(self.root / "missing.json"), "--resolves", "K1"),
            ("--status", "computed", "--file", str(self.root), "--resolves", "K1"),
        ]
        for args in cases:
            with self.subTest(args=args):
                self.run_board("clue", "An invalid completion", "--kind", "terrain", *args, ok=False)
                self.assertEqual(self.path.read_bytes(), before)

    def test_missing_output_no_longer_counts_as_completion(self):
        self.clue()
        self.clue("terrain", "computed", "--file", str(self.output), "--resolves", "K1")
        self.assertEqual(self.pending(), [])
        self.output.unlink()
        self.assertEqual(self.pending(), ["K1"])

    def test_relative_output_link_survives_a_different_working_directory(self):
        self.clue()
        self.clue("terrain", "computed", "--file", "scan.json", "--resolves", "K1")
        saved = self.read_board()["clues"]["K2"]["file"]
        self.assertEqual(Path(saved), self.output.resolve())
        self.assertEqual(self.pending(), [])
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "board.py"), "--board", str(self.path), "next"],
            cwd=self.root.parent, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("infrastructure clue", result.stdout)


class LevelGapTests(unittest.TestCase):
    """A point added under the city instead of under its road: its evidence never reached the road ranking, and report named another road."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "board.json"
        (self.root / "match.jpg").write_bytes(b"x")
        (self.root / "evidence.jpg").write_bytes(b"x")
        run = CorridorPendingTests.run_board
        self.run_board = lambda *a, ok=True: run(self, *a, ok=ok)
        self.run_board("init", "--photo", "photo.jpg")
        self.run_board("add", "City", "--level", "district")
        self.run_board("add", "A ST 100", "--level", "road", "--parent", "City", "--bbox", "49.20,-123.20,49.201,-123.19")
        self.run_board("add", "B ST 200", "--level", "road", "--parent", "City", "--bbox", "49.21,-123.20,49.211,-123.19")
        self.run_board("clue", "street view matches", "--kind", "municipal", "--status", "computed", "--file", "match.jpg")
        self.run_board("evidence", "--clue", "K1", "--for", "A ST 100:2", "--why", "partial", "--file", "match.jpg")

    def add_point(self, *extra):
        out = self.run_board("add", "spot", "--level", "point", "--parent", "City", "--bbox", "49.2159,-123.1095,49.2162,-123.1091", *extra)
        self.run_board("evidence", "--clue", "K1", "--for", "spot:10", "--why", "invariant features", "--file", "match.jpg")
        return out

    def ranking(self):
        return [r["name"] for r in board._scores(json.loads(self.path.read_text(encoding="utf-8")), "road", "uniform")]

    def test_skipped_level_is_flagged_everywhere(self):
        self.assertIn("2 road candidates", self.add_point().stdout)
        check = self.run_board("check")
        self.assertIn("FAIL spot (point) sits directly under City", check.stdout)
        self.assertIn("leaves the answer out", check.stdout)
        result = self.root / "result.json"
        result.write_text(json.dumps({"lat": 49.216, "lon": -123.1093, "radius_m": 20}), encoding="utf-8")
        report = self.run_board("report", "--merge", str(result)).stdout
        self.assertIn("outside the board's main answer A ST 100", report)
        self.assertTrue(json.loads(result.read_text(encoding="utf-8"))["board"]["level_gaps"])

    def test_moving_under_its_road_carries_support_up(self):
        self.add_point()
        self.run_board("add", "W 60 AVE 100", "--level", "road", "--parent", "City", "--bbox", "49.2158,-123.1112,49.2164,-123.1075")
        self.assertIn("lies inside W 60 AVE 100", self.run_board("check", ok=True).stdout)
        self.run_board("move", "spot", "--parent", "W 60 AVE 100")
        check = self.run_board("check").stdout
        self.assertNotIn("FAIL", check)
        self.assertIn("main answer W 60 AVE 100", check)
        self.assertEqual(self.ranking()[0], "W 60 AVE 100")
        result = self.root / "result.json"
        result.write_text(json.dumps({"lat": 49.216, "lon": -123.1093}), encoding="utf-8")
        self.assertNotIn("WARN", self.run_board("report", "--merge", str(result)).stdout)

    def test_against_on_a_point_does_not_reach_its_road(self):
        self.run_board("add", "spot2", "--level", "point", "--parent", "B ST 200")
        before = self.ranking()
        self.run_board("evidence", "--clue", "K1", "--against", "spot2:0.1", "--why", "no match", "--file", "match.jpg")
        self.assertEqual(self.ranking(), before)
        b = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(board._inherited(b, "B ST 200", set()), [])

    def test_same_clue_counts_once(self):
        self.run_board("add", "spot3", "--level", "point", "--parent", "A ST 100")
        self.run_board("evidence", "--clue", "K1", "--for", "spot3:10", "--why", "same clue", "--file", "match.jpg")
        b = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(board._inherited(b, "A ST 100", {"K1"}), [])   # A ST 100 already has its own K1 evidence

    def test_recording_a_clue_again_replaces_instead_of_stacking(self):
        before = [e for e in json.loads(self.path.read_text(encoding="utf-8"))["evidence"] if e["candidate"] == "A ST 100"]
        out = self.run_board("evidence", "--clue", "K1", "--for", "A ST 100:2", "--why", "same comparison again", "--file", "match.jpg").stdout
        self.assertIn("replaced it instead of counting it twice", out)
        after = [e for e in json.loads(self.path.read_text(encoding="utf-8"))["evidence"] if e["candidate"] == "A ST 100"]
        self.assertEqual(len(after), len(before))
        self.run_board("evidence", "--clue", "K1", "--for", "A ST 100:1.5", "--file", "match.jpg")
        b = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual([e["lr"] for e in b["evidence"] if e["candidate"] == "A ST 100"], [1.5])
        self.assertEqual(len({e["id"] for e in b["evidence"]}), len(b["evidence"]))

    def test_revision_removes_legacy_duplicates_without_reusing_ids(self):
        b = json.loads(self.path.read_text(encoding="utf-8"))
        b["evidence"] += [{**b["evidence"][0], "id": "E2", "lr": 3},
                          {**b["evidence"][0], "id": "E3", "candidate": "B ST 200", "lr": 1}]
        self.path.write_text(json.dumps(b), encoding="utf-8")
        self.run_board("evidence", "--clue", "K1", "--against", "A ST 100:0.5", "--why", "corrected")
        b = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual([e["lr"] for e in b["evidence"] if e["candidate"] == "A ST 100"], [0.5])
        self.assertEqual(b["evidence"][0]["id"], "E1")
        self.run_board("clue", "Independent observation", "--kind", "municipal", "--status", "observed")
        self.run_board("evidence", "--clue", "K2", "--for", "B ST 200:2")
        b = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len({e["id"] for e in b["evidence"]}), len(b["evidence"]))
        self.assertEqual(self.ranking()[0], "B ST 200")

    def test_independent_clues_still_accumulate_and_invalid_revision_is_atomic(self):
        self.run_board("clue", "Independent observation", "--kind", "municipal", "--status", "observed")
        self.run_board("evidence", "--clue", "K2", "--for", "A ST 100:3")
        b = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual([e["lr"] for e in b["evidence"]], [2, 3])
        before = self.path.read_bytes()
        self.run_board("evidence", "--clue", "K1", "--for", "A ST 100:4", "--for", "missing:2", ok=False)
        self.assertEqual(self.path.read_bytes(), before)

    def test_apply_can_revise_the_same_clue_and_handles_gaps_in_ids(self):
        b = json.loads(self.path.read_text(encoding="utf-8"))
        b["evidence"][0]["id"] = "E2"
        self.path.write_text(json.dumps(b), encoding="utf-8")
        self.run_board("clue", "Telephone prefix", "--kind", "calling-code", "--status", "read")
        args = ("apply", "--kind", "calling-code", "--value", "+33", "--clue", "K2")
        self.run_board(*args)
        before = json.loads(self.path.read_text(encoding="utf-8"))["evidence"]
        self.assertEqual(len({e["id"] for e in before}), len(before))
        self.run_board(*args)
        after = json.loads(self.path.read_text(encoding="utf-8"))["evidence"]
        self.assertEqual(after, before)

    def test_move_rejects_finer_parent(self):
        self.run_board("add", "spot4", "--level", "point", "--parent", "A ST 100")
        self.run_board("move", "A ST 100", "--parent", "spot4", ok=False)


class BoardCorrectnessTests(unittest.TestCase):
    run_board = CorridorPendingTests.run_board
    read_board = CorridorPendingTests.read_board

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "board.json"
        self.output = self.root / "proof.json"
        self.output.write_text('{}', encoding="utf-8")
        self.run_board("init", "--photo", "photo.jpg")
        self.run_board("add", "A", "B", "--level", "city")
        self.run_board("clue", "one test", "--kind", "terrain", "--status", "computed",
                       "--file", str(self.output))
        self.run_board("evidence", "--clue", "K1", "--for", "A:2", "--file", str(self.output))

    def save(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_legacy_duplicate_uses_last_revision_without_rewriting(self):
        data = self.read_board()
        data["evidence"][0]["lr"] = 5
        data["evidence"].append({**data["evidence"][0], "id": "E2", "lr": 2})
        self.save(data)
        before = self.path.read_bytes()
        row = board._scores(data, "city", "none")[0]
        self.assertAlmostEqual(row["share"], 2 / 3)
        self.assertEqual((row["n_ev"], row["n_verified"]), (1, 1))
        self.run_board("rank")
        self.assertEqual(self.path.read_bytes(), before)
        self.run_board("evidence", "--clue", "K1", "--for", "A:3")
        self.assertEqual(len(self.read_board()["evidence"]), 1)

    def test_legacy_descendant_revision_does_not_resurrect_old_support(self):
        data = self.read_board()
        data["candidates"]["spot"] = {"level": "point", "parent": "A", "status": "open"}
        data["evidence"] = [{**data["evidence"][0], "candidate": "spot", "lr": 5},
                            {**data["evidence"][0], "id": "E2", "candidate": "spot", "lr": 0.2}]
        self.assertEqual(board._inherited(data, "A", set()), [])

    def test_verified_requires_support_and_an_existing_regular_file(self):
        for lr, artifact in ((0.5, self.output), (1, self.output), (2, self.root / "missing"), (2, self.root)):
            with self.subTest(lr=lr, artifact=artifact):
                data = self.read_board()
                data["candidates"].pop("B", None)
                data["evidence"][0].update(lr=lr, file=str(artifact))
                data["clues"]["K1"]["file"] = str(artifact)
                self.save(data)
                self.assertEqual(board._scores(data, "city", "none")[0]["n_verified"], 0)
                self.assertIn("FAIL main answer A", self.run_board("check").stdout)

    def test_clue_file_can_back_support_and_inherited_support_still_counts(self):
        data = self.read_board()
        data["evidence"][0]["file"] = ""
        self.assertEqual(board._scores(data, "city", "none")[0]["n_verified"], 1)
        self.save(data)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            board.cmd_report(Namespace(prior_by="none", merge=None), self.path)
        report, _ = json.JSONDecoder().raw_decode(out.getvalue())
        self.assertEqual(report["main"]["evidence"][0]["file"], str(self.output))
        data["candidates"]["spot"] = {"level": "point", "parent": "A", "status": "open"}
        data["evidence"][0]["candidate"] = "spot"
        row = board._scores(data, "city", "none")[0]
        self.assertEqual(row["n_verified"], 1)
        self.assertEqual(row["ev"][0]["via"], "spot")

    def test_empty_or_all_excluded_board_cannot_pass(self):
        for empty in (True, False):
            with self.subTest(empty=empty):
                data = self.read_board()
                data["candidates"] = {} if empty else {"A": {"level": "city", "status": "excluded",
                    "excluded_by": {"computed": str(self.output), "clue": "K1"}}}
                data["evidence"] = []
                self.save(data)
                self.assertIn("FAIL no non-excluded candidates", self.run_board("check").stdout)
                self.run_board("check", "--strict", ok=False)

    def test_strict_check_fails_and_passes_without_changing_default_exit_contract(self):
        self.run_board("check", "--strict")
        self.output.unlink()
        self.run_board("check")
        self.run_board("check", "--strict", ok=False)

    def test_invalid_likelihoods_are_atomic(self):
        before = self.path.read_bytes()
        for lr in ("nan", "inf", "-inf", "0", "-1"):
            with self.subTest(lr=lr):
                self.run_board("evidence", "--clue", "K1", "--for", f"A:{lr}", ok=False)
                self.assertEqual(self.path.read_bytes(), before)

    def test_apply_respects_existing_clue_status_cap_and_validates_before_lookup(self):
        data = self.read_board()
        data["clues"]["K1"]["status"] = "inferred"
        self.save(data)
        args = Namespace(kind="calling-code", value="+33", country=None, clue="K1",
                         file=str(self.output), lr=20.0)
        response = subprocess.CompletedProcess([], 0, json.dumps({"matches": [{"country": "France"}]}), "")
        with patch.object(board, "_run", return_value=response), contextlib.redirect_stdout(io.StringIO()):
            board.cmd_apply(args, self.path)
        self.assertEqual(next(e["lr"] for e in self.read_board()["evidence"] if e["candidate"] == "France"), 3)
        before = self.path.read_bytes()
        for clue, lr in (("missing", 20), ("K1", float("nan")), ("K1", float("inf")), ("K1", 0), ("K1", -2)):
            with self.subTest(clue=clue, lr=lr), patch.object(board, "_run") as run:
                args.clue, args.lr = clue, lr
                with self.assertRaises(SystemExit):
                    board.cmd_apply(args, self.path)
                run.assert_not_called()
                self.assertEqual(self.path.read_bytes(), before)

    def test_report_prints_complete_json_and_labels_scores_not_probabilities(self):
        data = self.read_board()
        data["candidates"].pop("B")
        data["clues"]["K1"]["text"] = "x" * 5000
        self.save(data)
        report = json.loads(self.run_board("report").stdout)
        self.assertEqual(len(report["main"]["evidence"][0]["clue"]), 5000)
        self.assertIn("not calibrated probabilities", report["score_note"])

    def test_remerge_removes_only_exact_previous_board_entries(self):
        self.run_board("clue", "stale unused", "--kind", "terrain", "--status", "observed")
        self.run_board("add", "C", "--level", "city")
        self.run_board("exclude", "C", "--clue", "K1", "--computed", str(self.output), "--why", "stale exclusion")
        result = self.root / "result.json"
        manual = {"alternatives": ["Manual (share 10%): test", {"note": "manual"}],
                  "excluded": ["manual exclusion"], "unused_clues": ["manual unused"]}
        result.write_text(json.dumps(manual), encoding="utf-8")
        self.run_board("report", "--merge", str(result))
        first = json.loads(result.read_text(encoding="utf-8"))
        self.assertTrue(all(first["board"][field] for field in manual))
        self.run_board("report", "--merge", str(result))
        self.assertEqual(json.loads(result.read_text(encoding="utf-8")), first)
        data = self.read_board()
        data["candidates"].pop("B")
        data["candidates"]["C"]["status"] = "open"
        data["clues"]["K2"]["used"] = True
        self.save(data)
        self.run_board("evidence", "--clue", "K1", "--for", "A:50")
        self.run_board("report", "--merge", str(result))
        merged = json.loads(result.read_text(encoding="utf-8"))
        for field, entries in manual.items():
            self.assertEqual(merged[field], entries)
        self.run_board("report", "--merge", str(result))
        self.assertEqual(json.loads(result.read_text(encoding="utf-8")), merged)

    def test_merge_without_provenance_preserves_entries_even_if_generated_looking(self):
        result = self.root / "result.json"
        manual = {"alternatives": ["Old (share 10%): test"],
                  "excluded": ["old"], "unused_clues": ["old"]}
        result.write_text(json.dumps(manual), encoding="utf-8")
        self.run_board("report", "--merge", str(result))
        merged = json.loads(result.read_text(encoding="utf-8"))
        for field, entries in manual.items():
            self.assertEqual(merged[field][-len(entries):], entries)
        # Even an identical manually added occurrence survives a remerge.
        generated = merged["alternatives"][0]
        merged["alternatives"].append(generated)
        result.write_text(json.dumps(merged), encoding="utf-8")
        self.run_board("report", "--merge", str(result))
        self.assertEqual(json.loads(result.read_text(encoding="utf-8")), merged)

    def test_large_claimed_radius_cannot_hide_a_coordinate_mismatch(self):
        data = self.read_board()
        data["candidates"]["A"]["bbox"] = [49.0, -123.0, 49.001, -122.999]
        data["candidates"].pop("B")
        self.save(data)
        result = self.root / "result.json"
        result.write_text(json.dumps({"lat": 50.0, "lon": -122.0, "radius_m": 500000}), encoding="utf-8")
        self.run_board("report", "--merge", str(result))
        merged = json.loads(result.read_text(encoding="utf-8"))
        self.assertIn("main_mismatch", merged["board"])
        self.assertEqual((merged["lat"], merged["lon"], merged["radius_m"]), (50.0, -122.0, 500000))

    def run_elsewhere(self, *args, ok=True):
        elsewhere = self.root / "resumed"
        elsewhere.mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "board.py"), "--board", str(self.path), *args],
            cwd=elsewhere, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def legacy_paths(self):
        data = self.read_board()
        data["clues"]["K1"]["file"] = "proof.json"
        data["evidence"][0]["file"] = "proof.json"
        data["candidates"]["B"].update(status="excluded", excluded_by={
            "clue": "K1", "computed": "proof.json", "why": "no match"})
        # Keep this absolute spelling unchanged, not merely equivalent.
        absolute = str(self.root) + "/./proof.json"
        data["clues"]["K2"] = {"text": "absolute", "kind": "terrain", "status": "computed",
                                 "file": absolute, "used": True}
        self.save(data)
        return data

    def test_public_relocation_repairs_legacy_paths_for_cross_directory_check_and_report(self):
        original = self.legacy_paths()
        before = self.path.read_bytes()
        self.run_elsewhere("check", "--strict", ok=False)
        self.assertEqual(self.path.read_bytes(), before)
        self.run_elsewhere("relocate-files", "--base", str(self.root))
        repaired = self.read_board()
        self.assertEqual(repaired["clues"]["K1"]["file"], str(self.output.resolve()))
        self.assertEqual(repaired["evidence"][0]["file"], str(self.output.resolve()))
        self.assertEqual(repaired["candidates"]["B"]["excluded_by"]["computed"], str(self.output.resolve()))
        self.assertEqual(repaired["clues"]["K2"], original["clues"]["K2"])
        self.run_elsewhere("check", "--strict")
        report = json.loads(self.run_elsewhere("report").stdout)
        self.assertEqual(report["candidate_levels"]["city"][0]["verified"], 1)
        self.assertEqual(report["main"]["evidence"][0]["file"], str(self.output.resolve()))
        before = self.path.read_bytes()
        self.run_elsewhere("relocate-files", "--base", str(self.root))
        self.assertEqual(self.path.read_bytes(), before)

    def test_public_relocation_invalid_inputs_never_mutate_or_guess(self):
        original = self.legacy_paths()
        wrong = self.root / "wrong-base"
        wrong.mkdir()
        for args in (("relocate-files",), ("relocate-files", "--base", str(wrong)),
                     ("relocate-files", "--base", str(self.output)),
                     ("relocate-files", "--base", str(self.root / "missing-base"))):
            with self.subTest(args=args):
                before = self.path.read_bytes()
                self.run_elsewhere(*args, ok=False)
                self.assertEqual(self.path.read_bytes(), before)
        for field in ("clue", "evidence", "exclusion", "absolute"):
            with self.subTest(field=field):
                data = json.loads(json.dumps(original))
                if field == "clue":
                    data["clues"]["K1"]["file"] = "missing.json"
                elif field == "evidence":
                    data["evidence"][0]["file"] = "missing.json"
                elif field == "exclusion":
                    data["candidates"]["B"]["excluded_by"]["computed"] = "missing.json"
                else:
                    data["clues"]["K2"]["file"] = str(wrong)  # directory, not file
                self.save(data)
                before = self.path.read_bytes()
                self.run_elsewhere("relocate-files", "--base", str(self.root), ok=False)
                self.assertEqual(self.path.read_bytes(), before)

    def test_new_artifact_paths_survive_a_different_working_directory(self):
        self.run_board("clue", "relative output", "--kind", "terrain", "--status", "computed", "--file", "proof.json")
        self.run_board("evidence", "--clue", "K2", "--for", "A:2", "--file", "proof.json")
        data = self.read_board()
        self.assertEqual(data["clues"]["K2"]["file"], str(self.output.resolve()))
        self.assertEqual(data["evidence"][-1]["file"], str(self.output.resolve()))
        result = subprocess.run([sys.executable, str(SCRIPTS / "board.py"), "--board", str(self.path), "check", "--strict"],
                                cwd=self.root.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Offline public CLI regressions: uv run skills/geo-sleuth/tests/test_investigation.py"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "investigation.py"


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        # Respect the host scratch policy explicitly; do not hardcode /tmp.
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or tempfile.gettempdir())
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / "investigation.json"
        self.output = self.root / "response.json"
        self.output.write_text('{"hits": []}\n', encoding="utf-8")
        self.cli("init", "--goal", "Locate to road level")

    def cli(self, *args, code=0, cwd=None):
        result = subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(self.ledger), *args],
                                cwd=cwd or self.root, capture_output=True, text=True, encoding="utf-8",
                                timeout=15)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def report(self, code=0, cwd=None):
        return json.loads(self.cli("status", code=code, cwd=cwd).stdout)

    def route(self, method="reverse image search"):
        return json.loads(self.cli("route", "--method", method, "--scope", "original photo, one engine",
                                   "--reason", "test near-duplicate hypothesis", "--next-action",
                                   "inspect original-image search results").stdout)

    def attempt(self, outcome="empty", *extra, code=0):
        return self.cli("attempt", "R1", "--outcome", outcome, "--command",
                        "uv run revimg.py photo.jpg --engines example", "--summary",
                        "one engine original image, output manually inspected", *extra, code=code)

    def stop(self, kind="exhaustion", *extra, code=0):
        return self.cli("stop", "--kind", kind, "--reason", "bounded decision rationale", *extra, code=code)

    def test_plan_is_pending_and_persists_across_processes(self):
        data = self.route()
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["unresolved_feasible_routes"][0]["id"], "R1")
        self.assertEqual(self.report()["routes"]["R1"]["method"], "reverse image search")
        self.assertFalse(data["exhaustion_allowed"])
        self.assertTrue(data["resumable"])
        before = self.ledger.read_bytes()
        self.stop(code=2)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_init_never_overwrites_and_empty_plan_cannot_exhaust(self):
        before = self.ledger.read_bytes()
        self.cli("init", "--goal", "replacement", code=2)
        self.stop(code=2)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_empty_requires_a_real_nonzero_artifact_and_valid_route(self):
        self.route()
        blank = self.root / "blank"
        blank.touch()
        for extra in ((), ("--artifact", "missing.json"), ("--artifact", str(self.root)),
                      ("--artifact", str(blank)), ("--artifact", str(self.ledger))):
            with self.subTest(extra=extra):
                before = self.ledger.read_bytes()
                self.attempt("empty", *extra, code=2)
                self.assertEqual(self.ledger.read_bytes(), before)
        self.cli("attempt", "R99", "--outcome", "empty", "--command", "test", "--summary", "test",
                 "--artifact", str(self.output), code=2)
        self.attempt("empty", "--artifact", "response.json")
        data = self.report(cwd=self.root.parent)
        record = data["attempts"][0]
        self.assertEqual(record["artifacts"][0]["path"], str(self.output.resolve()))
        self.assertEqual(record["artifacts"][0]["sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(record["cwd"], str(self.root.resolve()))
        self.assertEqual(record["command"], "uv run revimg.py photo.jpg --engines example")
        self.assertEqual(data["unresolved_feasible_routes"], [])
        self.stop()
        self.assertEqual(self.report()["stops"][0]["kind"], "exhaustion")

    def test_blocked_is_never_empty_and_requires_next_action(self):
        self.route()
        self.attempt("blocked", code=2)
        self.attempt("blocked", "--next-action", "try another engine, no unchanged retry")
        data = self.report()
        self.assertEqual(data["attempts"][0]["outcome"], "blocked")
        self.assertEqual(data["unresolved_feasible_routes"][0]["last_outcome"], "blocked")
        self.assertIn("not evidence of absence", data["limitations"])
        self.stop(code=2)
        self.route("terrain")
        self.cli("defer", "R1", "--reason", "engine inaccessible; alternative R2 remains feasible")
        self.assertEqual([r["id"] for r in self.report()["unresolved_feasible_routes"]], ["R2"])
        self.stop(code=2)

    def test_partial_cannot_complete_route_and_retry_preserves_history(self):
        self.route()
        self.attempt("partial", "--next-action", "fetch missing pages", code=2)
        self.attempt("partial", "--artifact", str(self.output), code=2)
        self.attempt("partial", "--artifact", str(self.output), "--next-action", "fetch missing pages")
        self.stop(code=2)
        self.attempt("success", "--artifact", str(self.output))
        data = self.report()
        self.assertEqual([a["outcome"] for a in data["attempts"]], ["partial", "success"])
        self.assertTrue(data["exhaustion_allowed"])

    def test_pending_next_action_rejects_exhaustion_even_after_success(self):
        self.route()
        self.attempt("success", "--artifact", str(self.output), "--next-action", "check another crop")
        self.stop(code=2)
        self.attempt("empty", "--artifact", str(self.output))
        self.stop()

    def test_changed_or_missing_artifacts_flag_and_block_evidence_stops(self):
        self.route()
        self.attempt("empty", "--artifact", str(self.output))
        original = self.output.read_bytes()
        before = self.ledger.read_bytes()
        self.output.write_text('{"hits": [1]}', encoding="utf-8")
        data = self.report(code=1)
        self.assertEqual(data["effective_status"], "integrity_error")
        self.assertEqual(data["artifact_issues"][0]["problem"], "changed")
        self.assertEqual(self.ledger.read_bytes(), before)  # status is read-only
        self.stop(code=2)
        self.stop("supported", "--level", "city", "--qualification", "human assessment",
                  "--artifact", str(self.output), code=2)
        self.output.unlink()
        self.assertTrue(self.report(code=1)["artifact_issues"])
        self.output.write_bytes(original)
        self.assertEqual(self.report()["artifact_issues"], [])
        self.stop()

    def test_user_and_budget_stops_preserve_unresolved_and_are_resumable(self):
        self.route()
        for kind in ("user", "budget"):
            with self.subTest(kind=kind):
                self.stop(kind)
                data = self.report()
                self.assertEqual(data["status"], "stopped")
                self.assertEqual(data["stops"][-1]["unresolved_feasible_routes"][0]["id"], "R1")
                self.attempt("empty", "--artifact", str(self.output), code=2)
                self.cli("resume")
                self.assertEqual(self.report()["status"], "active")
        self.assertEqual([s["kind"] for s in self.report()["stops"]], ["user", "budget"])

    def test_supported_is_qualified_not_automatic_certification(self):
        self.route()
        self.stop("supported", code=2)
        self.stop("supported", "--level", "city", "--qualification", "board/human assessment", code=2)
        self.stop("supported", "--level", "city", "--qualification", "human compared independent clues; road unresolved",
                  "--artifact", str(self.output))
        data = self.report()
        self.assertEqual(data["stops"][0]["level"], "city")
        self.assertEqual(len(data["unresolved_feasible_routes"]), 1)
        self.assertIn("not certified", data["limitations"])
        self.output.write_text("changed assessment", encoding="utf-8")
        self.assertEqual(self.report(code=1)["artifact_issues"][0]["record"], "stop-1")

    def test_defer_and_reopen_are_explicit_audited_dispositions(self):
        self.route()
        self.cli("defer", "R1", "--reason", " ", code=2)
        self.cli("defer", "R1", "--reason", "no lawful accessible source for this route")
        data = self.report()
        self.assertTrue(data["exhaustion_allowed"])
        self.assertEqual(data["routes"]["R1"]["infeasible_reason"], "no lawful accessible source for this route")
        self.attempt("blocked", "--next-action", "retry", code=2)
        self.cli("reopen", "R1", "--next-action", "newly available source")
        data = self.report()
        self.assertFalse(data["exhaustion_allowed"])
        self.assertIsNone(data["routes"]["R1"]["infeasible_reason"])
        self.assertTrue(any(e["command"][2] == "defer" for e in data["events"]))

    def test_command_is_literal_text_not_executed(self):
        self.route()
        marker = self.root / "MUST_NOT_EXIST"
        command = f"touch '{marker}'; $(touch '{marker}')"
        self.cli("attempt", "R1", "--outcome", "blocked", "--command", command,
                 "--summary", "record only", "--next-action", "manual alternative")
        self.assertFalse(marker.exists())
        self.assertEqual(self.report()["attempts"][0]["command"], command)

    def test_bad_json_or_unknown_schema_fails_cleanly(self):
        for payload in ("not json", '{"schema_version": 99}', "[]"):
            with self.subTest(payload=payload):
                self.ledger.write_text(payload, encoding="utf-8")
                result = self.cli("status", code=2)
                self.assertNotIn("Traceback", result.stderr)

    def test_malformed_ledgers_fail_cleanly_without_saving(self):
        self.route()
        self.attempt("empty", "--artifact", str(self.output))
        self.route("terrain")
        self.stop("supported", "--level", "city", "--qualification", "human assessment",
                  "--artifact", str(self.output))
        self.cli("resume")
        self.cli("defer", "R2", "--reason", "source inaccessible")
        baseline = json.loads(self.ledger.read_text(encoding="utf-8"))
        cases = [
            (("attempts",), None, True),
            (("schema_version",), True, False),
            (("goal",), 3, False),
            (("created",), None, False),
            (("updated",), [], False),
            (("status",), "finished", False),
            (("routes",), [], False),
            (("routes", "R1"), None, False),
            (("routes", "R1", "id"), "R9", False),
            (("routes", "R1", "method"), " ", False),
            (("routes", "R1", "scope"), 1, False),
            (("routes", "R1", "reason"), None, True),
            (("routes", "R1", "disposition"), "done", False),
            (("routes", "R1", "next_action"), [], False),
            (("routes", "R1", "infeasible_reason"), False, False),
            (("attempts",), {}, False),
            (("attempts", 0), [], False),
            (("attempts", 0, "id"), "A2", False),
            (("attempts", 0, "route"), "R99", False),
            (("attempts", 0, "outcome"), "unknown", False),
            (("attempts", 0, "command"), None, False),
            (("attempts", 0, "summary"), [], False),
            (("attempts", 0, "cwd"), "relative", False),
            (("attempts", 0, "time"), 0, False),
            (("attempts", 0, "artifacts"), [], False),
            (("attempts", 0, "artifacts"), {}, False),
            (("attempts", 0, "artifacts", 0), None, False),
            (("attempts", 0, "artifacts", 0, "path"), "relative", False),
            (("attempts", 0, "artifacts", 0, "sha256"), "bad", False),
            (("attempts", 0, "artifacts", 0, "bytes"), True, False),
            (("attempts", 0, "artifacts", 0, "bytes"), 0, False),
            (("stops",), {}, False),
            (("stops", 0), [], False),
            (("stops", 0, "kind"), "done", False),
            (("stops", 0, "reason"), "", False),
            (("stops", 0, "level"), "planet", False),
            (("stops", 0, "qualification"), None, False),
            (("stops", 0, "artifacts"), [], False),
            (("stops", 0, "unresolved_feasible_routes"), {}, False),
            (("stops", 0, "unresolved_feasible_routes", 0), None, False),
            (("stops", 0, "unresolved_feasible_routes", 0, "id"), "R99", False),
            (("stops", 0, "unresolved_feasible_routes", 0, "last_outcome"), "done", False),
            (("stops", 0, "artifact_issues"), [None], False),
            (("stops", 0, "artifact_issues"), [{"record": "A99", "path": str(self.output),
                                                "problem": "changed"}], False),
            (("events",), {}, False),
            (("events", 0), None, False),
            (("events", 0, "time"), None, True),
            (("events", 0, "command"), "resume", False),
            (("events", 0, "command"), [1], False),
        ]
        for keys, value, remove in cases:
            with self.subTest(keys=keys, value=value):
                data = copy.deepcopy(baseline)
                target = data
                for key in keys[:-1]:
                    target = target[key]
                if remove:
                    del target[keys[-1]]
                else:
                    target[keys[-1]] = value
                self.ledger.write_text(json.dumps(data), encoding="utf-8")
                before = self.ledger.read_bytes()
                for command in (("status",), ("resume",),
                                ("stop", "--kind", "exhaustion", "--reason", "bounded")):
                    result = self.cli(*command, code=2)
                    self.assertEqual(result.stdout, "")
                    self.assertTrue(result.stderr.startswith("investigation:"))
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(self.ledger.read_bytes(), before)
        self.ledger.write_text(json.dumps(baseline), encoding="utf-8")
        self.assertTrue(self.report()["exhaustion_allowed"])
        self.stop()
        self.cli("resume")

    def test_historical_integrity_issues_remain_valid_after_repair(self):
        self.route()
        self.attempt("empty", "--artifact", str(self.output))
        original = self.output.read_bytes()
        self.output.write_text("changed", encoding="utf-8")
        self.stop("user")
        self.output.write_bytes(original)
        data = self.report()
        self.assertEqual(data["artifact_issues"], [])
        self.assertEqual(data["stops"][0]["artifact_issues"][0]["record"], "A1")
        self.cli("resume")
        self.stop()

    def test_empty_artifacts_rejected_for_each_evidence_outcome(self):
        self.route()
        self.attempt("empty", "--artifact", str(self.output))
        baseline = json.loads(self.ledger.read_text(encoding="utf-8"))
        for outcome in ("success", "empty", "partial"):
            with self.subTest(outcome=outcome):
                data = copy.deepcopy(baseline)
                data["attempts"][0].update(outcome=outcome, artifacts=[])
                self.ledger.write_text(json.dumps(data), encoding="utf-8")
                before = self.ledger.read_bytes()
                result = self.stop(code=2)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.ledger.read_bytes(), before)

    def test_blank_fields_rejected_without_mutation(self):
        before = self.ledger.read_bytes()
        self.cli("route", "--method", " ", "--scope", "all", "--reason", "reason", "--next-action", "do it", code=2)
        self.assertEqual(self.ledger.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

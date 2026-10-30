#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Offline route/attempt ledger, complementary to board.py (not a candidate board).

Commands are recorded as text, NEVER executed. Artifacts must be retained locally.
Every command emits JSON; status exits 1 for artifact integrity problems, 0 otherwise.
Usage: investigation.py --ledger investigation.json init --goal 'road level'
Use --help on each subcommand. A stop records a qualified decision, not proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

LIMITATION = ("Records do not prove scientific adequacy or complete search coverage. "
              "Blocked is not evidence of absence; empty applies only to the recorded scope. "
              "Supported stops remain board/human-evidence qualified, not certified by this ledger.")
LEVELS = ("country", "admin1", "admin2", "city", "district", "area", "road", "point", "building", "floor")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text(value):
    if not value.strip():
        raise argparse.ArgumentTypeError("must not be blank")
    return value


def artifact(value, ledger):
    path = Path(value).resolve()
    if path == ledger.resolve():
        raise ValueError("the ledger cannot be its own artifact")
    if not path.is_file():
        raise ValueError(f"artifact is not a regular file: {path}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    if not size:
        raise ValueError(f"artifact has zero bytes: {path}; retain a response or log, e.g. []")
    return {"path": str(path), "sha256": digest.hexdigest(), "bytes": size}


def validate(data):
    """Check the bounded v1 structure, not history authenticity or evidence meaning."""
    def require(condition, where):
        if not condition:
            raise ValueError(f"invalid ledger structure: {where}")

    def fields(record, strings=(), lists=(), nullable=()):
        require(isinstance(record, dict), "record must be an object")
        for key in strings:
            require(isinstance(record.get(key), str) and bool(record[key].strip()), key)
        for key in lists:
            require(isinstance(record.get(key), list), key + " must be a list")
        for key in nullable:
            require(key in record and (record[key] is None or
                    isinstance(record[key], str) and bool(record[key].strip())), key)

    def files(records, required=False):
        require(isinstance(records, list) and (not required or bool(records)), "artifacts")
        for saved in records:
            fields(saved, ("path", "sha256"))
            require(Path(saved["path"]).is_absolute(), "artifact path must be absolute")
            digest = saved["sha256"]
            require(len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "sha256")
            require(type(saved.get("bytes")) is int and saved["bytes"] > 0, "artifact bytes")

    def route(record):
        fields(record, ("id", "method", "scope", "reason", "disposition"),
               nullable=("next_action", "infeasible_reason"))
        require(record["disposition"] in ("feasible", "infeasible"), "route disposition")
        if record["disposition"] == "infeasible":
            require(record["infeasible_reason"] is not None and record["next_action"] is None,
                    "infeasible route needs reason and no next action")
        else:
            require(record["infeasible_reason"] is None, "feasible route has infeasible reason")

    fields(data, ("goal", "created", "updated", "status"), ("attempts", "stops", "events"))
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "unsupported ledger schema")
    require(data["status"] in ("active", "stopped"), "status")
    require(isinstance(data.get("routes"), dict), "routes must be an object")
    # IDs must match the append-only allocator, preventing future ID collisions.
    require(set(data["routes"]) == {f"R{i + 1}" for i in range(len(data["routes"]))}, "route IDs")
    for rid, record in data["routes"].items():
        route(record)
        require(record["id"] == rid, "route ID/key mismatch")
    outcomes = ("success", "empty", "blocked", "partial")
    for i, attempt in enumerate(data["attempts"]):
        fields(attempt, ("id", "route", "time", "outcome", "command", "cwd", "summary"), ("artifacts",))
        require(attempt["id"] == f"A{i + 1}", "attempt ID")
        require(attempt["route"] in data["routes"], "attempt route reference")
        require(attempt["outcome"] in outcomes, "attempt outcome")
        require(Path(attempt["cwd"]).is_absolute(), "attempt cwd must be absolute")
        files(attempt["artifacts"], required=attempt["outcome"] != "blocked")
    owners = {a["id"] for a in data["attempts"]}
    owners.update(f"stop-{i + 1}" for i in range(len(data["stops"])))
    for stop in data["stops"]:
        fields(stop, ("kind", "reason", "time"),
               ("artifacts", "unresolved_feasible_routes", "artifact_issues"), ("level", "qualification"))
        require(stop["kind"] in ("supported", "user", "budget", "exhaustion"), "stop kind")
        supported = stop["kind"] == "supported"
        if supported:
            require(stop["level"] in LEVELS and stop["qualification"] is not None,
                    "supported stop needs level and qualification")
        else:
            require(stop["level"] is None and stop["qualification"] is None,
                    "only supported stops have level/qualification")
        files(stop["artifacts"], required=supported)
        seen = set()
        for snapshot in stop["unresolved_feasible_routes"]:
            route(snapshot)
            require(snapshot["id"] in data["routes"] and snapshot["id"] not in seen,
                    "stop route reference")
            seen.add(snapshot["id"])
            require(snapshot.get("last_outcome") in (*outcomes, "unattempted"), "snapshot last_outcome")
        for issue in stop["artifact_issues"]:
            fields(issue, ("record", "path", "problem"))
            require(issue["record"] in owners and Path(issue["path"]).is_absolute(), "artifact issue reference/path")
    for event in data["events"]:
        fields(event, ("time",), ("command",))
        require(bool(event["command"]) and all(isinstance(v, str) for v in event["command"]),
                "event command must be a nonempty list of strings")


def integrity(data, ledger):
    issues = []
    records = [(a["id"], a["artifacts"]) for a in data["attempts"]]
    records += [(f"stop-{i + 1}", s.get("artifacts", [])) for i, s in enumerate(data["stops"])]
    for owner, files in records:
        for saved in files:
            try:
                current = artifact(saved["path"], ledger)
                if current != saved:
                    issues.append({"record": owner, "path": saved["path"], "problem": "changed"})
            except (OSError, ValueError) as exc:
                issues.append({"record": owner, "path": saved["path"], "problem": str(exc)})
    return issues


def pending(data):
    result = []
    for route in data["routes"].values():
        if route["disposition"] == "infeasible":
            continue
        attempts = [a for a in data["attempts"] if a["route"] == route["id"]]
        outcome = attempts[-1]["outcome"] if attempts else "unattempted"
        if outcome not in ("success", "empty") or route["next_action"]:
            result.append({**route, "last_outcome": outcome})
    return result


def status(data, ledger):
    issues = integrity(data, ledger)
    unresolved = pending(data)
    return {**data, "unresolved_feasible_routes": unresolved, "artifact_issues": issues,
            "resumable": True, "effective_status": "integrity_error" if issues else data["status"],
            "exhaustion_allowed": bool(data["routes"]) and not unresolved and not issues,
            "limitations": LIMITATION}


def save(path, data, create=False):
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if create:
        # Exclusive creation: init never silently overwrites an investigation.
        with path.open("x", encoding="utf-8") as stream:
            stream.write(payload)
        return
    # Same-directory atomic replacement; no global configuration or system temp use.
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".investigation-", delete=False) as stream:
            name = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ledger", type=Path, default=Path("investigation.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init", help="create a ledger, without overwriting")
    init.add_argument("--goal", type=text, required=True)
    route = sub.add_parser("route", help="plan a feasible route (method, scope, why)")
    for name in ("method", "scope", "reason", "next-action"):
        route.add_argument("--" + name, type=text, required=True)
    attempt = sub.add_parser("attempt", help="record an actual attempt; does not run --command")
    attempt.add_argument("route")
    attempt.add_argument("--outcome", choices=("success", "empty", "blocked", "partial"), required=True)
    attempt.add_argument("--command", type=text, required=True, help="actual command or manual tool action, verbatim")
    attempt.add_argument("--summary", type=text, required=True, help="actual scope checked, result and limitations")
    attempt.add_argument("--artifact", action="append", default=[], help="retained output/log, repeatable")
    attempt.add_argument("--next-action", type=text, help="required for blocked/partial; success/empty clears old action")
    defer = sub.add_parser("defer", help="explicitly mark a route infeasible, never evidence of absence")
    defer.add_argument("route")
    defer.add_argument("--reason", type=text, required=True)
    reopen = sub.add_parser("reopen", help="make a deferred/completed route pending again")
    reopen.add_argument("route")
    reopen.add_argument("--next-action", type=text, required=True)
    stop = sub.add_parser("stop", help="record a qualified stop; unresolved work stays visible")
    stop.add_argument("--kind", choices=("supported", "user", "budget", "exhaustion"), required=True)
    stop.add_argument("--reason", type=text, required=True, help="user instruction, budget reached, or bounded rationale")
    stop.add_argument("--level", choices=LEVELS)
    stop.add_argument("--qualification", type=text, help="board/human evidence assessment, NOT ledger certification")
    stop.add_argument("--artifact", action="append", default=[], help="supported stop needs retained board/human assessment")
    sub.add_parser("resume", help="resume a stopped run; preserves stop history")
    sub.add_parser("status", help="full untruncated resumable JSON and integrity check")
    return ap


def main():
    ap = parser()
    args = ap.parse_args()
    path = args.ledger.resolve()
    try:
        if args.cmd == "init":
            data = {"schema_version": 1, "goal": args.goal, "created": now(), "status": "active",
                    "routes": {}, "attempts": [], "stops": [], "events": []}
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            validate(data)
            if args.cmd == "status":
                report = status(data, path)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 1 if report["artifact_issues"] else 0
            if args.cmd == "resume":
                data["status"] = "active"
            else:
                if data["status"] != "active":
                    raise ValueError("run is stopped; resume before recording more work")
                if args.cmd == "route":
                    rid = f"R{len(data['routes']) + 1}"
                    data["routes"][rid] = {"id": rid, "method": args.method, "scope": args.scope,
                                           "reason": args.reason, "next_action": args.next_action,
                                           "disposition": "feasible", "infeasible_reason": None}
                elif args.cmd in ("attempt", "defer", "reopen"):
                    if args.route not in data["routes"]:
                        raise ValueError(f"unknown route: {args.route}")
                    route = data["routes"][args.route]
                    if args.cmd == "reopen":
                        route.update(disposition="feasible", infeasible_reason=None, next_action=args.next_action)
                    elif args.cmd == "defer":
                        route.update(disposition="infeasible", infeasible_reason=args.reason, next_action=None)
                    else:
                        if route["disposition"] != "feasible":
                            raise ValueError("reopen infeasible route before attempting it")
                        if args.outcome in ("blocked", "partial") and not args.next_action:
                            raise ValueError("blocked/partial requires --next-action (retry differently or assess another route)")
                        if args.outcome in ("success", "empty", "partial") and not args.artifact:
                            raise ValueError(f"{args.outcome} requires a retained --artifact")
                        files = [artifact(v, path) for v in args.artifact]
                        aid = f"A{len(data['attempts']) + 1}"
                        data["attempts"].append({"id": aid, "route": args.route, "time": now(),
                                                 "outcome": args.outcome, "command": args.command,
                                                 "cwd": str(Path.cwd()), "summary": args.summary,
                                                 "artifacts": files})
                        route["next_action"] = args.next_action
                elif args.cmd == "stop":
                    if args.kind == "supported" and not (args.level and args.qualification and args.artifact):
                        raise ValueError("supported stop needs --level, --qualification and --artifact (board/human assessment)")
                    if args.kind != "supported" and (args.level or args.qualification):
                        raise ValueError("--level/--qualification apply only to supported stops")
                    issues = integrity(data, path)
                    if args.kind in ("supported", "exhaustion") and issues:
                        raise ValueError("artifact integrity problems must be repaired before supported/exhaustion stop")
                    if args.kind == "exhaustion" and (not data["routes"] or pending(data)):
                        raise ValueError("exhaustion rejected: no routes planned or unresolved feasible routes/next actions remain")
                    data["stops"].append({"kind": args.kind, "reason": args.reason, "time": now(),
                                          "level": args.level, "qualification": args.qualification,
                                          "artifacts": [artifact(v, path) for v in args.artifact],
                                          "unresolved_feasible_routes": pending(data), "artifact_issues": issues})
                    data["status"] = "stopped"
            # Keep disposition changes and resumptions visible instead of silently erasing history.
            data["events"].append({"time": now(), "command": sys.argv[1:]})
        data["updated"] = now()
        validate(data)
        report = status(data, path)
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        save(path, data, create=args.cmd == "init")
        print(payload)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"investigation: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        getattr(sys.stdout, "reconfigure")(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        getattr(sys.stderr, "reconfigure")(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())

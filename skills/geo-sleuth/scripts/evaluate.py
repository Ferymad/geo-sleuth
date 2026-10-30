#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Score frozen geolocation predictions against a separately held answer key.

uv run scripts/evaluate.py --truth answers.json --predictions frozen.json --out metrics.json

Both inputs are JSON arrays. Truth rows: {case_id, lat, lon}. Prediction rows:
{case_id, lat, lon, radius_m?}, or {case_id, abstain: true}. Missing predictions
count as abstentions, never disappear from denominators. Never load the answer
key into a solving agent's context. This tool does not run a model or establish
that inputs were blind, consented, representative, or actually frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

# Conventional broad-scale thresholds plus the skill's road/building gates.
THRESHOLDS_M = (25, 100, 1000, 25000, 200000, 750000, 2500000)


def number(value, label, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    try:
        value = float(value)
    except OverflowError:
        raise ValueError(f"{label} must be a finite representable number") from None
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be in [{low}, {high}]")
    return float(value)


def median_nonnegative(values):
    """Avoid overflow when averaging the middle pair of finite radii."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    low, high = ordered[mid - 1], ordered[mid]
    return low + (high - low) / 2


def coordinates(row):
    return (number(row.get("lat"), "lat", -90, 90),
            number(row.get("lon"), "lon", -180, 180))


def index(rows, label):
    if not isinstance(rows, list) or not rows and label == "truth":
        raise ValueError(f"{label} must be a JSON array; truth cannot be empty")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str) or not row["case_id"].strip():
            raise ValueError(f"{label} rows require a nonempty string case_id")
        key = row["case_id"]
        if key in result:
            raise ValueError(f"duplicate {label} case_id: {key}")
        result[key] = row
    return result


def distance_m(a, b):
    """Great-circle error on a mean-radius Earth, not survey-grade geodesy."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(max(0.0, min(1.0, h))))


def evaluate(truth_rows, prediction_rows):
    truth, predictions = index(truth_rows, "truth"), index(prediction_rows, "prediction")
    extra = predictions.keys() - truth.keys()
    if extra:
        raise ValueError("unknown prediction case_id: " + ", ".join(sorted(extra)))
    results, errors, radii = [], [], []
    for key, answer in truth.items():
        target = coordinates(answer)
        pred = predictions.get(key)
        if pred is None:
            results.append({"case_id": key, "status": "missing"})
            continue
        if "abstain" in pred and not isinstance(pred["abstain"], bool):
            raise ValueError(f"{key}: abstain must be boolean")
        if pred.get("abstain"):
            if any(field in pred for field in ("lat", "lon", "radius_m")):
                raise ValueError(f"{key}: abstention cannot also claim coordinates or a radius")
            results.append({"case_id": key, "status": "abstained"})
            continue
        error = distance_m(target, coordinates(pred))
        item = {"case_id": key, "status": "predicted", "error_m": error}
        errors.append(error)
        if "radius_m" in pred:
            radius = number(pred["radius_m"], "radius_m", 0, float("inf"))
            item.update(radius_m=radius, inside_radius=error <= radius)
            radii.append(item)
        results.append(item)
    n, attempted = len(truth), len(errors)
    return {
        "schema_version": 1, "n_cases": n, "n_predicted": attempted,
        "n_abstained": sum(r["status"] == "abstained" for r in results),
        "n_missing": sum(r["status"] == "missing" for r in results),
        "prediction_coverage": attempted / n,
        "accuracy_all_cases": {str(t): sum(e <= t for e in errors) / n for t in THRESHOLDS_M},
        "accuracy_predicted_only": {str(t): sum(e <= t for e in errors) / attempted if attempted else None for t in THRESHOLDS_M},
        "median_error_m_predicted_only": statistics.median(errors) if errors else None,
        "mean_error_m_predicted_only": statistics.mean(errors) if errors else None,
        "radius_claims": {"n": len(radii), "n_without_radius": attempted - len(radii),
                          "empirical_coverage": sum(r["inside_radius"] for r in radii) / len(radii) if radii else None,
                          "median_radius_m": median_nonnegative(r["radius_m"] for r in radii) if radii else None,
                          "false_precision_le_100m": sum(r["radius_m"] <= 100 and not r["inside_radius"] for r in radii)},
        "cases": results,
        "limitations": ["Spherical distance with mean Earth radius 6371008.8 m; not survey-grade.",
                        "Empirical radius coverage is not calibrated confidence; no confidence level is assumed.",
                        "This scorer cannot verify blinding, consent, freezing, or sample representativeness."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.out and any(args.out.resolve() == source.resolve() or
                            (args.out.exists() and args.out.samefile(source))
                            for source in (args.truth, args.predictions)):
            raise ValueError("--out must not overwrite an input")
        raw_truth, raw_predictions = args.truth.read_bytes(), args.predictions.read_bytes()
        report = evaluate(json.loads(raw_truth), json.loads(raw_predictions))
        report["input_sha256"] = {"truth": hashlib.sha256(raw_truth).hexdigest(),
                                  "predictions": hashlib.sha256(raw_predictions).hexdigest()}
        text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8")
        print(text, end="")
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"evaluate: {exc}\n")


if __name__ == "__main__":
    main()

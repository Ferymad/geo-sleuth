#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "pillow-heif", "numpy"]
# ///
"""Optional input/coverage checks, never a pose solver. See research/pose-preflight.md."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

NOTICE = "preflight does not certify a unique pose or a geographic error radius."
THRESHOLDS = {"relative_rank": 0.01, "image_span_fraction": 0.1,
              "near_pixel_fraction": 0.001, "bearing_span_deg": 5,
              "relative_range_spread": 0.1}


def preflight(spec):
    report: dict = dict(valid_input=False, errors=[], warnings=[], counts={},
                  missing_inputs=[], diagnostics={"thresholds": THRESHOLDS}, notice=NOTICE)
    errors, warnings = report["errors"], report["warnings"]

    def warn(code, detail):
        warnings.append({"code": code, "detail": detail})

    def number(x):
        try:
            return type(x) in (int, float) and math.isfinite(x)
        except OverflowError:
            return False

    def pair(x, geographic=False):
        return (isinstance(x, list) and len(x) == 2 and all(number(v) for v in x)
                and (not geographic or (-90 <= x[0] <= 90 and -180 <= x[1] <= 180)))

    def finite_tree(x):
        if isinstance(x, dict):
            return all(finite_tree(v) for v in x.values())
        if isinstance(x, list):
            return all(finite_tree(v) for v in x)
        return not isinstance(x, (int, float)) or number(x) or isinstance(x, bool)

    if not isinstance(spec, dict):
        errors.append("spec must be an object")
        return report
    if not finite_tree(spec):
        errors.append("all numeric values must be finite")
    size, init, points, fixed = (spec.get(k) for k in ("image_size", "init", "points", "fix"))
    fixed = [] if fixed is None and "fix" not in spec else fixed
    if not pair(size) or any(v <= 0 or int(v) != v for v in size):
        errors.append("image_size must contain two positive integer dimensions")
    if not isinstance(init, dict) or not pair(init.get("at"), True):
        errors.append("init.at must contain valid latitude/longitude")
    if isinstance(init, dict):
        for key in ("height", "heading", "pitch", "roll", "hfov"):
            if key in init and not number(init[key]):
                errors.append(f"init.{key} must be a finite number")
        if number(init.get("hfov")) and not 0 < init["hfov"] < 180:
            errors.append("init.hfov must be strictly between 0 and 180 degrees")
    if not isinstance(fixed, list) or any(v not in ("hfov", "height", "roll") for v in fixed):
        errors.append("fix must be a list containing only hfov, height, roll")
    if not isinstance(points, list):
        errors.append("points must be a list")
    else:
        for i, q in enumerate(points):
            if (not isinstance(q, dict) or not pair(q.get("px")) or not pair(q.get("ll"), True)
                    or ("h" in q and not number(q["h"]))):
                errors.append(f"points[{i}] requires finite px[2], valid ll[2], and finite h if present")
    if errors:
        return report  # Deliberately before importing pose/Pillow/NumPy.

    import numpy as np
    import pose

    free = [n for n in pose.NAMES if not ((n == "focal_px" and "hfov" in fixed)
            or (n in ("height", "roll") and n in fixed))]
    n, k = len(points), len(free)
    report["counts"] = dict(points=n, scalar_observations=2*n, free_parameters=k,
                            free_names=free, dof=2*n-k, leave_one_out_dof=2*(n-1)-k,
                            leave_one_out_redundant=2*(n-1) > k)
    if 2*n < k:
        errors.append("insufficient equations for actual free parameters")
    if 2*(n-1) <= k:
        warn("LOO_NO_REDUNDANCY", "Dropping one point leaves no positive dof; add a spread point or independently fix height/hfov/roll.")
        report["missing_inputs"].append("Add a spread control or independently known height/hfov/roll for positive leave-one-out dof.")
    pixels, worlds = {}, {}
    gaps = []
    for i, q in enumerate(points):
        px, world = tuple(q["px"]), (*q["ll"], q.get("h", 0))
        if px in pixels and pixels[px] != world:
            errors.append(f"points[{i}]: same pixels describe different world points")
        if world in worlds and worlds[world] != px:
            errors.append(f"points[{i}]: same world point describes different pixels")
        if px in pixels and pixels[px] == world:
            warn("DUPLICATE_CONTROL", f"points[{i}] repeats an observation; raw counts overstate independent support.")
        pixels[px], worlds[world] = world, px
        missing = [key for key in ("h", "vertical_reference", "height_kind", "source_url", "units")
                   if key not in q or q[key] is None or q[key] == ""]
        if missing:
            gaps.append({"point": i, "missing": missing})
        if not (0 <= px[0] < size[0] and 0 <= px[1] < size[1]):
            warn("PIXEL_OUTSIDE_IMAGE", f"points[{i}] outside declared pixel bounds; check frame or intentional extrapolation.")
    report["counts"]["distinct_observations"] = len(pixels)
    report["diagnostics"]["metadata_gaps"] = gaps
    if gaps:
        warn("MISSING_HEIGHT_METADATA", "See per-point metadata gaps; omitted h is legacy zero, not a measured elevation.")
        report["missing_inputs"].append("Supply missing control heights, named vertical references, height kinds, sources and units.")
    for key in ("vertical_reference", "units"):
        values = sorted({str(q[key]) for q in points if q.get(key)})
        if len(values) > 1:
            warn("MIXED_" + key.upper(), f"Multiple declared {key}: {values}; no conversion is performed.")
    if any(q.get("units") not in (None, "", "m", "metres", "meters") for q in points):
        warn("NON_METRIC_UNITS", "pose assumes metre-valued heights; convert explicitly before solving.")
    if spec.get("frame") not in ("stored", "upright"):
        warn("FRAME_UNKNOWN", "Missing/unknown frame; legacy pose defaults missing frame to stored.")
    report["diagnostics"]["frame"] = spec.get("frame", "stored (legacy default)")
    for key in ("crop", "principal_point", "distortion"):
        if key not in spec:
            warn("MISSING_" + key.upper(), f"Declare {key} history/assumption; pose uses centered principal point, square pixels, no distortion.")
            report["missing_inputs"].append(f"Document {key}; metadata is not calibration or a solver option.")
    if n:
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                obs = np.array([q["px"] for q in points], dtype=float) / np.asarray(size, dtype=float)
                span = np.ptp(obs, axis=0)
                report["diagnostics"]["image_span_fraction"] = span.tolist()
                if min(span) < THRESHOLDS["image_span_fraction"]:
                    warn("SMALL_IMAGE_SPAN", "Image width or height coverage below heuristic 0.1; add spread controls.")
                near = False
                for i in range(n):
                    for j in range(i):
                        distance = float(np.linalg.norm(obs[i]-obs[j]))
                        if not math.isfinite(distance):
                            raise FloatingPointError("pixel distance exceeds numeric range")
                        near |= 0 < distance < THRESHOLDS["near_pixel_fraction"]
                if near:
                    warn("NEAR_DUPLICATE_PIXELS", "Controls less than 0.001 image-normalized Euclidean distance apart.")
                lat0, lon0 = init["at"]
                kx, ky = pose._frame(lat0)
                xyz = np.array([[(q["ll"][1]-lon0)*kx, (q["ll"][0]-lat0)*ky,
                                 q.get("h", 0)] for q in points], dtype=float)
                for label, data in (("world", xyz), ("horizontal", xyz[:, :2])):
                    scale = float(np.max(np.abs(data)))
                    normalized = data/scale if scale else data
                    centered = normalized-normalized.mean(axis=0)
                    s = np.linalg.svd(centered, compute_uv=False)
                    ratios = s/s[0] if s[0] else s
                    rank = int(sum(ratios > THRESHOLDS["relative_rank"]))
                    report["diagnostics"][label] = dict(singular_ratios=ratios.tolist(), heuristic_rank=rank,
                                                        normalization="common maximum absolute metric coordinate scale, then centered")
                    if rank < 2:
                        warn("NEAR_COLLINEAR_" + label.upper(), "Heuristic rank below two; add off-line controls. Not a pose observability test.")
                    elif label == "world" and rank == 2:
                        warn("PLANAR_WORLD", "Planar/near-planar controls are valid; competing poses may remain.")
                heights = [q.get("h", 0) for q in points]
                report["diagnostics"]["distinct_height_values"] = len(set(heights))
                if len(set(heights)) < 2:
                    warn("SINGLE_HEIGHT_LEVEL", "One height level (including legacy missing-h zeros); valid but no elevation diversity.")
                ranges = np.linalg.norm(xyz[:, :2], axis=1)
                angles = np.sort(np.mod(np.degrees(np.arctan2(xyz[:, 0], xyz[:, 1])), 360))
                bearing_span = float(360-np.max(np.diff(np.r_[angles, angles[0]+360])))
                spread = float(np.ptp(ranges)/np.max(ranges)) if np.max(ranges) else 0.0
                report["diagnostics"]["init_hypothesis"] = dict(bearing_span_deg=bearing_span,
                        relative_horizontal_range_spread=spread, note="Rough init only, not definitive observability or camera depth.")
                if bearing_span < THRESHOLDS["bearing_span_deg"] or spread < THRESHOLDS["relative_range_spread"]:
                    warn("NARROW_INIT_GEOMETRY", "Under init hypothesis only: bearing span <5 degrees or relative horizontal range spread <0.1.")
        except (FloatingPointError, np.linalg.LinAlgError) as exc:
            errors.append(f"Cannot compute finite geometry diagnostics: {exc}")
    report["valid_input"] = not errors
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        report = preflight(spec)
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    except (ValueError, OSError, RecursionError, OverflowError) as exc:
        report = dict(valid_input=False, errors=[str(exc)], warnings=[], counts={},
                      missing_inputs=[], diagnostics={}, notice=NOTICE)
        payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    try:
        with args.out.open("x", encoding="utf-8") as stream:  # Never overwrite source or previous evidence.
            stream.write(payload)
    except OSError as exc:
        parser.exit(2, f"Cannot create report: {exc}\n")
    print(f"valid_input={report['valid_input']}; errors={len(report['errors'])}; warnings={len(report['warnings'])}. {NOTICE}", file=sys.stderr)
    return 0 if report["valid_input"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Inspect fSpy v1 interoperability evidence, not calibration or geographic pose.

Independent reader of perarnia/fSpy's documented project_file_format.md.
No fSpy solver code, application, network, or image decoder is used.
See research/fspy-bridge.md for provenance and the manual pose/Blender boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys

MAX_STATE_BYTES = 16 * 1024 * 1024
# Count nested object/array containers, including the root object (depth 1).
# This inspection bound is intentional, not an upstream format restriction.
MAX_STATE_DEPTH = 64


def _check_state_depth(encoded: bytes) -> None:
    """Bound container nesting before parsing, independent of JSON recursion limits.

    JSON syntax/UTF-8 validation remains json.loads' job. Structural ASCII bytes
    cannot appear inside a UTF-8 multibyte character; quoted/escaped brackets
    must not count as containers.
    """
    depth = 0
    quoted = escaped = False
    for byte in encoded:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 0x5c:  # backslash
                escaped = True
            elif byte == 0x22:  # double quote
                quoted = False
        elif byte == 0x22:
            quoted = True
        elif byte in (0x7b, 0x5b):  # { [
            depth += 1
            if depth > MAX_STATE_DEPTH:
                raise ValueError(
                    f"state exceeds {MAX_STATE_DEPTH}-level nesting inspection limit"
                )
        elif byte in (0x7d, 0x5d):  # } ]
            depth -= 1


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    return value


def _constant(text):
    raise ValueError(f"invalid JSON constant: {text}")


def inspect_project(path: str | Path) -> dict:
    """Read a regular v1 project with bounded JSON; return JSON-safe evidence.

    Image bytes are streamed only for project SHA-256, never decoded or emitted.
    Stored reference settings are declarations, not independently verified scale.
    Raises OSError/ValueError for unreadable or malformed input.
    """
    path = Path(path)
    # Nonblocking open also avoids waiting on a FIFO masquerading as a project.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("project must be a regular file")
        header = source.read(16)
        if len(header) != 16:
            raise ValueError("truncated fSpy header (expected 16 bytes)")
        magic, version, state_size, image_size = struct.unpack("<4sIII", header)
        if magic != b"fspy":
            raise ValueError("invalid fSpy magic")
        if version != 1:
            raise ValueError(f"unsupported fSpy project version: {version}")
        if state_size > MAX_STATE_BYTES:
            raise ValueError(f"state exceeds {MAX_STATE_BYTES}-byte inspection limit")
        expected_size = 16 + state_size + image_size
        if before.st_size != expected_size:
            raise ValueError("payload length mismatch: truncated data or trailing bytes")
        encoded = source.read(state_size)
        if len(encoded) != state_size:
            raise ValueError("truncated JSON state")
        _check_state_depth(encoded)
        try:
            state = json.loads(encoded.decode("utf-8"), object_pairs_hook=_object,
                               parse_float=_number, parse_constant=_constant)
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise ValueError(f"invalid UTF-8 JSON state: {exc}") from exc
        if not isinstance(state, dict):
            raise ValueError("project state must be a JSON object")
        digest = hashlib.sha256(header + encoded)
        remaining = image_size
        while remaining:
            chunk = source.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("truncated embedded image payload")
            digest.update(chunk)
            remaining -= len(chunk)
        after = os.fstat(source.fileno())
        if source.read(1) or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("project changed during inspection")

    camera = state.get("cameraParameters")
    warnings = [
        "Stored calibration is not independently validated; this is an evidence inspector, not a solver.",
        "Local axes/transforms are not latitude/longitude, true north, or exact eye height.",
        "No geographic anchor, vertical datum, or metric scale is verified by this inspector.",
        "Field-of-view values and coordinate conventions are preserved raw; no pose conversion is performed.",
    ]
    if "cameraParameters" not in state:
        warnings.append("cameraParameters is absent: no saved calibration is available.")
    elif camera is None:
        warnings.append("cameraParameters is null: calibration may be invalid or unsolved.")
    elif not isinstance(camera, dict):
        warnings.append("cameraParameters is not an object: unrecognized saved calibration schema.")
    base = state.get("calibrationSettingsBase")
    reference = {key: base[key] for key in (
        "referenceDistance", "referenceDistanceUnit", "referenceDistanceAxis"
    ) if isinstance(base, dict) and key in base}
    if reference:
        warnings.append("Stored reference distance/unit/axis are user declarations, not verified physical measurements.")
        if reference.get("referenceDistanceAxis") is None:
            warnings.append("No reference distance axis is selected; a unit label alone does not establish scale.")
    return {
        "schema": "geo-sleuth.fspy-inspection.v1",
        "project": {"path": str(path), "sha256": digest.hexdigest(), "version": version,
                    "size_bytes": expected_size, "state_size_bytes": state_size},
        "camera_parameters_present": "cameraParameters" in state,
        "camera_parameters_raw": camera,
        "reference_settings_raw": reference,
        "embedded_image": {"present": image_size > 0, "size_bytes": image_size,
                           "extracted": False, "decoded": False,
                           "metadata_inspected": False},
        "verified_geographic_anchor": None,
        "verified_metric_scale": None,
        "warnings": warnings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="local .fspy project; never modified")
    parser.add_argument("--out", type=Path, help="new JSON report; existing paths are never overwritten")
    args = parser.parse_args(argv)
    try:
        report = inspect_project(args.project)
        text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.out:
            # Exclusive creation rejects input aliases, symlinks and hardlinks,
            # and protects unrelated existing reports without a check/write race.
            with args.out.open("x", encoding="utf-8") as output:
                output.write(text)
        else:
            sys.stdout.write(text)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"fspy: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

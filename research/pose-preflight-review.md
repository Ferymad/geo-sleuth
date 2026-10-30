# Pose preflight final bounded review

## Findings and fixes

- Added the test script's PEP 723 header, matching the implementation's Python requirement and Pillow, pillow-heif and NumPy dependencies. The standard `uv run skills/geo-sleuth/tests/test_pose_preflight.py` invocation now provisions the test subprocess's imports.
- Reproduced opposite-sign finite pixels (`+/-1e308`, unit image dimensions) overflowing image span: the original CLI created an empty report and failed serialization with a traceback. Geometry computations now use scoped NumPy overflow/invalid/division error handling and return invalid-input diagnostics.
- Reproduced an individual `1e308` pixel overflowing the squared-distance norm while the original report incorrectly remained valid. Explicit finite-distance checks also catch silent BLAS overflow, which NumPy error settings alone do not reliably trap. Extreme arithmetic is rejected cleanly; this is not an arbitrary-precision implementation.
- Huge integers outside finite float range are rejected during numeric validation rather than escaping `math.isfinite` with `OverflowError`. Image dimensions and world-coordinate arrays are explicitly converted to float, avoiding object-array arithmetic for representable large JSON integers. A finite case with `10**308` dimensions and opposite-sign heights remains valid and JSON-serializable.
- Input and report files explicitly use UTF-8. Invalid UTF-8 produces a complete invalid-input report without a traceback; the decode error was already a caught ValueError, but encoding was previously locale-dependent.
- Caught NumPy `LinAlgError` around numerical diagnostics. A public CLI regression injects SVD nonconvergence; no new solver or numerical fallback was introduced.
- Serialize strict JSON inside the protected input/report phase, before exclusively creating the output file. Serialization failures now produce a complete invalid-input report instead of an empty file. A public CLI fault-injection test verifies this otherwise defensive boundary independently of the geometry fix.

## Preserved behavior and limits

- Normal deterministic diagnostics, frame/bounds and calibration-history warnings, height metadata gaps, mixed/non-metric units, planar/collinear warnings, fixed/free parameter counts and leave-one-out warnings remain covered.
- Consistent duplicate observations remain warning-only. Counts/dof/leave-one-out remain raw counts, not independent support; tests explicitly preserve six raw versus five distinct observations. Conflicting duplicates remain invalid.
- Preflight remains a heuristic input/coverage check, not a pose solver or proof of observability, uniqueness, calibration, or geographic error radius. Metadata declarations are warnings, not conversions or calibration options. Model limitations remain separate from numeric/schema errors.
- Invalid numeric geometry can retain diagnostics successfully computed before the numerical failure, but the report is complete JSON and `valid_input` is false. Output creation remains exclusive and refuses overwrite. Serialization is completed before opening the output; disk-full or other physical write failures are not an atomic-file guarantee.
- No network calls, optimizer calls, new solver, or commits. Changes are limited to the implementation, its public tests, and this review. Resource exhaustion from arbitrarily large inputs is not addressed by this bounded patch.

## Verification

- Initial regression run reproduced the span failure (empty report/JSON decode error) and norm failure (incorrect successful exit).
- `UV_OFFLINE=1 UV_PYTHON=3.13 uv run skills/geo-sleuth/tests/test_pose_preflight.py`: **12 tests passed**, including malformed schemas, invalid UTF-8, extreme numeric cases, SVD/serialization failures, existing-output preservation, and no-network/no-optimizer guards.
- `uvx --offline ruff check --select F,E9 skills/geo-sleuth/scripts/pose_preflight.py skills/geo-sleuth/tests/test_pose_preflight.py`: **All checks passed**.
- Python 3.13 was selected explicitly; offline mode prevented dependency downloads/networking.

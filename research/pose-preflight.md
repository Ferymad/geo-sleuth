# Optional pose input preflight

Implements a bounded subset of `geometry-capabilities.md` §4 as a **separate opt-in CLI**, not a new `pose.py` subcommand. Existing solver code and numerical behavior are unchanged.

```sh
uv run --offline --python 3.13 skills/geo-sleuth/scripts/pose_preflight.py spec.json --out preflight-new.json
```

The output path must be new: existing reports and input files are never overwritten. JSON goes to that file; a short summary goes to stderr. Exit status is 0 for valid input (possibly with warnings), 1 for invalid input, 2 for CLI/output-path errors. Parent directories must already exist. No image is opened and no network, learned model, optimizer, or external solver is used. `--offline` requires the existing uv package/interpreter cache; nothing is installed globally. PEP 723 dependencies match `pose.py`: Pillow, pillow-heif, NumPy. Malformed schema/numeric input is checked with the standard library **before importing pose or its dependencies**.

## Input and report

Uses the existing pose spec: `image_size`, `points` (`px`, `ll`, optional `h`), `init.at`, optional `init.height/heading/pitch/hfov`, and optional `fix` containing `hfov`, `height`, `roll`. Heights remain metre-valued; no conversion is made. Only finite JSON numbers are accepted for these numeric fields (not strings, booleans or null). Dimensions must be positive integers; coordinates must have arity two, latitude in [-90,90], longitude in [-180,180], and supplied hfov strictly between 0 and 180. Missing origin, contradictory exact repeated pixel/world mappings, and fewer raw scalar equations than free parameters are errors. World identity uses `(lat, lon, h)` with legacy omitted `h=0`.

`valid_input`, `errors`, structured `warnings` (`code`, `detail`), `counts`, `missing_inputs`, `diagnostics` and a limitation `notice` are emitted. On malformed input, counts/geometry may be unavailable rather than guessed. This is a modest validation API, not a general schema framework; unknown metadata is not interpreted as solver options.

Free names come from imported `pose.NAMES`, with the existing solver's height/roll/hfov-fix predicate (hfov fixes `focal_px`). Defaults match the solver: hfov 65, height 30, heading/pitch/roll zero; `init.roll` does not change the solver's initial roll. Free count is 7 minus the distinct supported fixes. Dof is `2*N - free_count`. The reported leave-one-out redundancy requires `2*(N-1) > free_count`, matching pose's requirement for at least one remaining residual dof. This is **equation-budget availability, not a rank or solvability claim**. Consistent exact duplicate observations produce warnings, not removal; counts deliberately remain raw like the solver and can overstate independent support. `distinct_observations` is also reported.

## Metadata and warning interpretation

Record per-control `h`, `vertical_reference`, `height_kind`, `source_url` (a source identifier, not fetched or validated), and `units`. Missing values are listed by zero-based point index. Distinct known vertical-reference/unit strings warn; unknown references cannot be certified compatible, and a single non-metre unit also warns. String comparisons do not resolve aliases, datum realizations, epochs or transforms. Camera-height datum must be checked manually.

Intentional local-plane controls are supported: set every `h` explicitly to zero, with e.g. `vertical_reference: "shared local plane"`, `height_kind: "local_elevation"`, `units: "m"` and an actual measurement/source note. Such a case is valid; planarity/one-height warnings describe its geometry, not bad data. Missing h instead receives a metadata warning even though legacy zero is used for diagnostics.

Declare `frame: "upright"` or `"stored"` consistently with the actual image dimensions/pixels. Missing frame reports legacy stored behavior; unknown frame warns but is not normalized. Pixel bounds are `[0,width)` and `[0,height)`; outside pixels warn, never disappear. Optional top-level `crop`, `principal_point`, and `distortion` are documentation fields: their absence warns, but their presence is **not** a verified calibration or a change to pose's centered principal point, square pixels and distortion-free model. Supplying noncentral principal point or distortion metadata does not make the solver support those models.

## Explicit heuristic thresholds

All thresholds are emitted in `diagnostics.thresholds`; none are statistical tests:

- Image coordinates divided by width/height: warn if either bounding-box span is below **0.1** of the image. This is span, **not convex-hull area** or a spatial-uniformity test.
- Near pixel pairs: warn for nonzero normalized Euclidean separation below **0.001**. No world-distance near-duplicate threshold is implemented.
- World/horizontal diagnostics use pose's approximate local metre frame. Each coordinate matrix is divided by one common maximum-absolute-coordinate scale, then centered; no per-axis whitening hides a thin configuration. Singular values relative to the largest are counted above **0.01**. Rank below two warns about collinearity; world rank two warns about planarity but is valid. This is heuristic geometric rank, **not a camera Jacobian/observability test**.
- Distinct height values are counted exactly; a single level warns. No noise-aware elevation clustering is performed.
- Under the **rough init hypothesis only**, horizontal circular bearing span below **5°**, or horizontal range spread `(max-min)/max` below **0.1**, warns. All-zero ranges give spread zero. This is horizontal range, not camera-axis depth; init can be wrong. No definitive observability, uniqueness, or physical camera placement is inferred from it.

Add spatially spread controls and independent heights/calibration when appropriate; never turn a warning into automatic exclusion. The tool makes no board artifact, confidence score, fit, outlier removal, datum transform, covariance or radius. Antimeridian/polar/large-area use retains the limitations of pose's approximate flat geographic frame. Provenance, feature identity and image preprocessing are not independently checked. Passing is not permission to claim geographic accuracy.

**preflight does not certify a unique pose or a geographic error radius.**

## Verification

```sh
uv run --offline --python 3.13 --with pillow --with pillow-heif --with numpy \
  python -m unittest discover -s skills/geo-sleuth/tests -p test_pose_preflight.py
```

Public subprocess tests exercise normal/deterministic output, malformed/nonfinite data, conflicting/consistent duplicates, explicit planar zero heights, missing/mixed datum/units, collinear/narrow geometry, frame/bounds, fix counts/LOO, and overwrite refusal. A `python -S` subprocess proves malformed validation needs no optional imports. A guarded subprocess forbids sockets, URL opens, subprocess spawning and pose's optimizers/projector during a valid preflight. These are bounded regression checks, not a general network sandbox or numerical solver benchmark. Tests use `TMPDIR`; no other solver is executed.

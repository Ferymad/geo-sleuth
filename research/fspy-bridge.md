# Optional fSpy interoperability evidence bridge

## Scope and entry point

`skills/geo-sleuth/scripts/fspy.py` is an independent, standard-library reader of
the documented fSpy project container, **not a calibrator, pose solver, Blender
exporter, or geographic registration tool**. It does not install or invoke any
application, shell command, image decoder, or network service at runtime.

From the repository root:

```sh
python3 skills/geo-sleuth/scripts/fspy.py scene.fspy
python3 skills/geo-sleuth/scripts/fspy.py scene.fspy --out scene-inspection.json
python3 skills/geo-sleuth/tests/test_fspy.py
```

Python 3.10+; no dependencies. `uv run` also works. The small Python API is
`inspect_project(path) -> dict`; malformed projects raise `ValueError`, filesystem
errors raise `OSError`. CLI errors go to stderr, exit status 2, without a traceback.
Reports use schema `geo-sleuth.fspy-inspection.v1`.

`--out` exclusively creates a **new** file. It rejects every existing path,
including the project itself, relative aliases, hardlinks, symlinks, existing
reports and dangling symlinks. Input is opened read-only. No embedded image is
extracted, even optionally. Image bytes are streamed only to retain the SHA-256
of the complete original project. Reports contain byte presence/length and
`metadata_inspected: false`: this is not an EXIF scanner. Camera `imageWidth` and
`imageHeight` are saved calibration values, not independently decoded dimensions.
Raw camera data may itself be sensitive; treat the report as evidence, not a
redacted public export.

## Official provenance and licensing boundary

Canonical upstream: [perarnia/fSpy](https://github.com/perarnia/fSpy), default
branch **develop**, inspected at commit
`702189ec5acbbd2c8ba492db0e52ecb5fc908f5c`.
Discovery and source retrieval used authenticated `gh api`, not a guessed mirror.
The recursive repository tree located the definitions before they were read:

- [project_file_format.md](https://github.com/perarnia/fSpy/blob/702189ec5acbbd2c8ba492db0e52ecb5fc908f5c/project_file_format.md)
- [CameraParameters in src/gui/solver/solver-result.ts](https://github.com/perarnia/fSpy/blob/702189ec5acbbd2c8ba492db0e52ecb5fc908f5c/src/gui/solver/solver-result.ts)
- [SavedState in src/gui/io/saved-state.ts](https://github.com/perarnia/fSpy/blob/702189ec5acbbd2c8ba492db0e52ecb5fc908f5c/src/gui/io/saved-state.ts)
- [src/gui/types/calibration-settings.ts](https://github.com/perarnia/fSpy/blob/702189ec5acbbd2c8ba492db0e52ecb5fc908f5c/src/gui/types/calibration-settings.ts)
- [src/gui/io/project-file.ts](https://github.com/perarnia/fSpy/blob/702189ec5acbbd2c8ba492db0e52ecb5fc908f5c/src/gui/io/project-file.ts)

Upstream API reports GPL-3.0, and source headers specify GPL version 3 or later.
**No GPL solver implementation was copied, translated, linked or vendored into
this MIT repository.** The new reader independently implements the published
binary format. Retrieved upstream source and the official binary example stayed
in scratch, outside maintained source. Licensing of separately installed fSpy or
its Blender importer remains separate; this document is not legal advice.

### Format implemented

Exactly 16 header bytes: ASCII `fspy`, then three unsigned little-endian 32-bit
integers: version (`1`), JSON state byte length, embedded image byte length.
UTF-8 JSON follows, then exactly the declared number of opaque image bytes (zero
is valid). The reader rejects unsupported versions, bad magic, short headers,
truncated state/image data, trailing payload, invalid UTF-8/JSON, duplicate keys,
non-finite numbers and a non-object state. State allocation is capped at 16 MiB,
and container nesting at 64 levels (`MAX_STATE_DEPTH`, root object = level 1;
objects and arrays each add one level). A lexical check before JSON parsing
ignores brackets/braces inside quoted strings, including escaped quotes and
backslashes, so the nesting bound does not depend on interpreter recursion limits.
Larger or deeper valid upstream projects are deliberately unsupported by this
inspector, not declared corrupt. Images are not loaded into memory as a whole. Regular files only; observable
changes to size/mtime/ctime during inspection are rejected. This is not an
adversarial filesystem snapshot guarantee.

The actual `CameraParameters` interface has `principalPoint`, `viewTransform`,
`cameraTransform` (documented there as inverse view transform),
`horizontalFieldOfView`, `verticalFieldOfView`, `vanishingPoints`,
`vanishingPointAxes`, `relativeFocalLength`, `imageWidth`, and `imageHeight`.
The reader preserves the entire `cameraParameters` JSON value, including unknown
future fields; it does not claim schema, transform, or calibration validity.
Missing, null and non-object camera parameters receive explicit warnings.

The format and interface alone do not establish all projection conventions needed
by `pose.py`. Therefore **no hfov radians/degrees conversion or transform-to-pose
conversion is exposed**. Raw FOV values stay raw, rather than being guessed from
the example magnitude. A display setting that says `Degrees` is not sufficient to
infer serialized units. No undocumented focal-length formula is implemented.

## Practical geometry workflow: fSpy → metric references → pose.py → Blender

This is an optional, manual interoperability path; the inspector runs out of the
box without fSpy or Blender. It does not automatically execute the following
applications or certify their results.

1. **fSpy local perspective evidence.** In separately obtained fSpy, align visible
   orthogonal line families, choose local axes/origin, and save the project. Inspect
   it with the command above and retain its SHA-256 alongside the original photo.
   Null calibration is an unsolved/invalid possibility, not a zero-valued camera.
   Local axes are user-selected, not ENU or true north. A transform translation is
   not latitude/longitude and a local z coordinate is not exact eye height.
2. **Independent metric reference and datum.** Record the actual feature endpoints,
   measured distance and units, measurement source, uncertainty, axis/origin
   association and applicable vertical datum. A distance label such as `Meters`
   does not prove a measurement. The inspector reports the stored
   `referenceDistance`, `referenceDistanceUnit`, and `referenceDistanceAxis` only;
   it never turns these declarations into a verified scale. Historical `Yards`
   labels, if present, remain raw, not silently migrated. Establish separate map
   anchors and true-north alignment; a reference length alone cannot georegister
   a scene. Retain these independent observations in your investigation evidence,
   not as fabricated fields in the fSpy report.
3. **Existing geographic pose solver.** Build the existing `pose.py` spec from
   independently identified image/map correspondences, not local fSpy transforms.
   See `skills/geo-sleuth/scripts/pose.py` for its spec and dependencies. It accepts
   `image_size`, `frame`, and `points` with `name`, `px`, `ll` (latitude/longitude),
   and `h`; `init` provides independent approximate camera location/height/heading.
   Use at least four appropriately distributed known points and one consistent
   height datum. Pixel positions must be measured in the specified image frame
   (e.g. `upright` with EXIF orientation applied). Retain fSpy raw calibration as
   supporting evidence only; do not feed its raw FOV directly into degree-valued
   `init.hfov` or fix that parameter without verified conventions and uncertainty.

   ```sh
   uv run skills/geo-sleuth/scripts/pose.py solve surveyed-spec.json --photo photo.jpg --out pose-check.png
   uv run skills/geo-sleuth/scripts/pose.py project --pose pose.json --points independent-check-points.json --photo photo.jpg --out independent-check.png
   ```

   These commands document existing interfaces; they were not executed in this
   inspector probe. Check residuals, held-out points, ambiguity, horizon/pitch and
   shared vertical datum before claiming geographic camera position or eye height.
4. **Blender visualization.** The fSpy README points to its official importer;
   canonical [perarnia/fSpy-Blender](https://github.com/perarnia/fSpy-Blender) was
   verified via GitHub API (default branch `master`, GPL-3.0). Separately install
   compatible Blender/importer versions and import the **original `.fspy` project**,
   not the inspector JSON. That importer handles fSpy's application conventions.
   For a geographic overlay, independently register the local scene to the solved
   geographic pose using documented origin, horizontal axes, scale, and vertical
   datum; validate image projections again. This bridge does not automate that
   registration or write `.blend` files. Blender/importer compatibility and an
   end-to-end application import were **not tested** here.

Both `verified_geographic_anchor` and `verified_metric_scale` in inspector reports
are deliberately null, even when extra JSON fields resemble coordinates. No
geographic registration convention is established by this reader.

## Actual official-example probe (not a synthetic calibration)

Upstream `assets/electron/example.fspy` was fetched using `gh api` Git blob
`18365074f092f157980acff92ba08f58d4d28b3a`, base64-decoded to
`$TMPDIR/fspy-bridge-probe/example.fspy`, then inspected using the public CLI.
The output was written to scratch `inspection.json` and read back. Neither the
upstream artifact nor embedded image is committed. For a fresh reproduction:

```sh
# Run from repository root. Retrieval is a development probe, not reader runtime.
python3 -c 'import subprocess,json,base64,pathlib,os; p=pathlib.Path(os.environ["TMPDIR"])/"fspy-bridge-probe-repro"; p.mkdir(exist_ok=True); d=json.loads(subprocess.check_output(["gh","api","repos/perarnia/fSpy/git/blobs/18365074f092f157980acff92ba08f58d4d28b3a"])); (p/"example.fspy").write_bytes(base64.b64decode(d["content"]))'
python3 skills/geo-sleuth/scripts/fspy.py "$TMPDIR/fspy-bridge-probe-repro/example.fspy"
```

Observed public CLI result (exit 0):

| Field | Actual value |
|---|---|
| Whole-project SHA-256 | `4c722dda4af8ca3cc740b5cef2666d1b495a99c5f75ce0696362812bc4bf24af` |
| Total bytes | 6520290 |
| Version | 1 |
| JSON state bytes | 2973 |
| Embedded image bytes | 6517301; present, not extracted/decoded, metadata uninspected |
| Saved camera | Present object; raw transforms/points preserved |
| Saved image dimensions | 5184 × 3456 (not decoded/verified) |
| Raw horizontal FOV | `0.8098745307314665` (no unit conversion) |
| Raw vertical FOV | `0.5566656780878579` (no unit conversion) |
| Raw relative focal length | `2.333040277023006` |
| Stored reference | distance `0.2`, unit `Meters`, axis **null** |
| Verified geographic anchor / metric scale | Both **null** |

The real example specifically demonstrates why a `Meters` unit string must not
produce metric camera-height claims: no reference-distance axis is selected.
Warnings include this condition plus unvalidated calibration, absent verified
scale/datum/anchor, raw coordinate/FOV conventions, and local-vs-geographic axes.

GitHub's Contents API returned an empty `content` for this >1 MiB binary; the Git
blob API supplied the actual artifact. An initial empty download was not treated
as a successful probe. The final artifact was size-checked, parsed and hashed.

## Verification

`uv run skills/geo-sleuth/tests/test_fspy.py`, with `TMPDIR` set to the configured scratch directory (local prefix redacted):
**17 tests passed on Python 3.13.16**. Fixtures are
explicitly **synthetic framing examples**, not recovered upstream data or solver
verification. They cover raw camera preservation, project SHA-256, image privacy,
null/absent/unrecognized calibration, reference-unit non-claims, output creation,
input/hardlink/symlink safety, bad magic/version, every short-header length,
oversized state, inconsistent/trailing payload, invalid UTF-8/JSON, duplicate keys,
non-finite/deep JSON, missing paths, directories and FIFOs. All exercise the public
CLI in subprocesses without application installation or network access. The
separate official-example probe above supplies real-container interoperability
evidence; neither synthetic tests nor that probe validates the upstream solver.

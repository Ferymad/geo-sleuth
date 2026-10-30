# Final verification

Baseline: `bb5c2400af8cd6f05849d0c5f3346980c0b16d15`.
The final code was exercised on macOS using the scripts' `uv run` PEP 723
invocations. The diagnostic script reports Python 3.13.16. This is not a Windows,
Linux or Python 3.10 compatibility matrix.

## Complete offline suite

All **283 tests across 12 suites passed**, with every suite invoked separately
so its declared dependencies were available. No test suite uploaded target photos
or loaded learned geolocation/matching weights.

| Suite | Tests | Exit |
|---|---:|---:|
| board | 32 | 0 |
| evaluate | 8 | 0 |
| fSpy inspector | 17 | 0 |
| gazetteer | 12 | 0 |
| investigation | 16 | 0 |
| KartaView | 15 | 0 |
| matching | 9 | 0 |
| pose preflight | 12 | 0 |
| region packs | 29 | 0 |
| runtime | 112 | 0 |
| sun | 3 | 0 |
| terrain | 18 | 0 |

Exact commands, totals and SHA-256 fingerprints of the tested scripts/tests/skill
references: [regressions.json](validation/regressions.json). Per-suite logs are
under `validation/`; workspace/scratch absolute prefixes are explicitly redacted.
Existing terrain code still emits a non-failing unclosed-file `ResourceWarning`
at `terrain.py:498`, reproduced before changes; that solver was not edited.

## Static and navigation checks

- `git diff --check`: passed.
- `uvx ruff check --select F,E9` passed for all modified/new scripts plus
  board/new-helper tests. It was a scoped correctness/unused-name check, not a
  repository-wide style-clean claim. The preexisting unused `folder` variable in
  `test_runtime.py:197` was confirmed against baseline and left untouched.
- All **98 checked relative Markdown links resolve**; the skill description is
  **579 characters**, within the 1024-character specification limit. Details:
  [navigation.json](validation/navigation.json).
- Independent reviews found and prompted fixes for merge ownership, legacy file
  paths, contentless provider responses, hard-link overwrite protection, extreme
  numeric/deep JSON handling and runtime-dependent nesting limits. Focused review
  reports remain alongside the implementation audit reports.

## Actual runtime/primary-source checks

| Check | Actual outcome | Does not establish |
|---|---|---|
| Local-only intake on the repository's public desert display image | EXIF/variants/eight edges/OCR completed; reverse search explicitly skipped | Blind localization, original-resolution reproduction or accurate OCR text |
| fSpy official `example.fspy` | v1, 6520290 bytes, SHA-256 `4c722dda4af8ca3cc740b5cef2666d1b495a99c5f75ce0696362812bc4bf24af`; parsed saved raw calibration without extracting embedded image | Correct calibration, metric scale, GPS alignment, Blender import or pose solve |
| KartaView new CLI, bounded public metadata | 70 returned/unique valid rows, zero duplicates/failures, `has_more=false`, coverage explicitly `bounded/unknown` | Regional completeness, reliable reference-image availability or matching accuracy |
| One selected KartaView thumbnail | HTTP 409; failure retained, no image accepted | Absence of imagery or negative geographic evidence |
| Separate processed-CDN recovery probe | curl exit 56 / HTTP 500; no accepted file | Cause of server failure or a working image pipeline |
| Latest recorded `doctor.py --network --json` | Local tools/Chrome and tested non-Overpass probes passed; Overpass timed out (curl 28), exit 1 | All services healthy, model inference or broad source coverage |
| Two distinct Overpass mirror queries | Both timed out; responses retained | Missing mapped features or justification to exclude a location |
| External source/model/skill research | Official source/docs and bounded public metadata substantiate documented contracts and feasibility | Installed runtimes, licensed rights for every image, comparative model speed/accuracy or full production readiness |

Runtime records: [doctor](validation/doctor-network.json),
[Overpass alternatives](validation/overpass-alternatives.json),
[KartaView metadata](validation/kartaview-metadata-summary.json),
[CDN recovery](validation/kartaview-cdn-probe.json).
Primary source research separately verified public STAC/Commons metadata and
specific GSI LiDAR coverage/imagery-service semantics; see the cited research.

## Explicitly not claimed

No controlled blind photo-location experiment, overall solve-rate gain,
100% correctness, precise real-photo camera-height improvement, model benchmark,
full LiDAR raster acquisition, OpenCV/COLMAP/Blender/hloc runtime integration, paid
API entitlement, or working live KartaView image matching is claimed.

The deliverable is tested reliability tooling, an opt-in geometry preflight,
verified file/metadata interoperability, and an actionable primary-source toolbox.
The next accuracy gate is the paired, held-out experiment in
[the evaluation protocol](../skills/geo-sleuth/references/evaluation.md).

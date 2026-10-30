# Bounded KartaView reference adapter

## Scope and commands

Implementation: `skills/geo-sleuth/scripts/kartaview.py`; offline tests:
`skills/geo-sleuth/tests/test_kartaview.py`. Paths below start at the repository root.
Metadata uses only Python's standard library. Pillow is needed only for the optional
thumbnail command; the script's `uv` dependency declaration supplies it.

```sh
# The output file must not exist. Its parent directory must already exist.
python3 skills/geo-sleuth/scripts/kartaview.py nearby \
  --at=-6.1939,106.8494 --zoom 15 --out nearby.json

# Optional: explicit single ID, exactly one thumbnail request, NEW directory only.
uv run skills/geo-sleuth/scripts/kartaview.py fetch \
  --metadata nearby.json --id 616387694 --out-dir reference-thumbnail

uv run --with pillow python -m unittest discover \
  -s skills/geo-sleuth/tests -p test_kartaview.py -v
```

`nearby` sends exactly one unauthenticated GET to
`https://api.kartaview.org/2.0/photo/` with **only** `lat`, `lng`, and `zoomLevel`.
There is no `limit`, inferred bbox, pagination, redirect following, retry, auth,
object search, upload, paid fallback, or automatic broad scan. Zoom 14–19 is a
**local conservative request policy**, not a claim about the provider's full
supported range or a guaranteed geographic extent. Responses are capped at 4 MiB
and each network operation has a 30-second socket timeout. This is not a strict
wall-clock deadline against a continuously trickling response. Query coordinates
are disclosed to the provider; target-photo bytes never enter this adapter.

## Data and failure contract

- Require JSON content type, integer `status.apiCode == 600`, integer
  `status.httpCode == 200`, array `result.data`, boolean `result.hasMoreData`.
  HTTP/API/schema/content-type/transport/rate-limit failures are not empty coverage.
- Validate coordinate types, finite numbers, WGS84 ranges, nonnegative GPS accuracy,
  decimal identifiers, sequence fields, dates and projection field types. Invalid
  rows are recorded by row position and reason, not silently lost. Duplicate IDs
  use the first valid occurrence; a rejected row does not suppress a later valid
  same-ID item. Later valid-ID duplicates increment `duplicate_count`. No merging
  of contradictory valid duplicates.
- `returned_count == count + duplicate_count + failure_count`; `count` is the
  actual unique valid `items` count. Provider row order is retained.
- `wgs` is the original `lat/lng`; `matched_wgs` separately preserves
  `matchLat/matchLng`. These are estimates, not survey-grade camera positions.
- `capture_time.raw` preserves `shotDate` literally. `timezone: unknown` means no
  offset was supplied; **do not interpret it as UTC**. Explicit offsets are marked
  `explicit_offset` and not rewritten. Missing dates remain null/unknown.
- Preserve sequence ID/index, projection and partial projection, GPS accuracy and
  processing status. Do not emit a calibrated heading, FOV, camera pose, or freely
  rotatable panorama. A provider heading of zero is not used as calibration.
- Every result declares `coverage: "bounded/unknown"`. If `has_more` is true **or
  any row fails validation**, status is `partial`. Otherwise it is
  `success_unknown_coverage`, or `success_empty` when the valid response is empty.
  **Even `has_more: false` never means census, verified absence, or full geographic
  coverage.** A failure returns nonzero with `status: failed`; successful metadata
  acquisition can return zero with `status: partial`, so inspect the output status.
- Store sanitized fixed query URL, actual acquisition time and response SHA-256.
  No token or arbitrary raw original URL is persisted. Per-item and top-level
  attribution: **© Grab and KartaView Contributors**, imagery license
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
  Preserve attribution and review adaptation/share-alike obligations before
  publishing evidence panels; this is not a blanket license for all site content.

## Optional thumbnail boundary and local matching

Only rows marked `FINISHED` **and** `BLURRED` can expose processed/thumbnail URLs.
This is a provider processing assertion, not independent proof every sensitive
feature was blurred. The allowlist is intentionally narrower than all KartaView
infrastructure: only HTTPS `storage13.openstreetcam.org`, the exact provider
storage host in the retained successful query, with constrained
`/files/photo/YYYY/M/D/proc/<name>.jpg` or `/th/<name>.jpg` paths. No credentials,
ports, query strings, fragments, traversal, CDN templates, arbitrary hosts or raw
paths. Other hosts/unknown variants become null rather than expanded trust.

`fetch` revalidates the URL and blur-processing fields in the local metadata,
selects exactly one ID, and fetches **only** its `/th/` URL. It never substitutes
an original or full processed asset when a thumbnail is unavailable. Existing
output directories (even empty directories or symlinks) are refused. Downloads
are capped at 4 MiB; only JPEG/PNG content types, formats, full Pillow decode,
and at most 4 million pixels are accepted. Redirects are refused. Successful
bytes are written exclusively only after decode; failures leave no image and
are recorded in `fetch.json`, with an empty `index.json`. `fetch` returns nonzero
on a failed item. An invalid source/selection fails before creating the directory.
Filesystem failures are reported as output errors rather than imagery absence.

`index.json` is the requested local `{ "photo_id": "/absolute/path.jpg" }`
provenance mapping; only actual successfully decoded files appear. **It is not a
`match.py --items` input**: the inspected current `_load_candidates` expects a
list of renderable panorama dictionaries for `--items`, then invokes Baidu/GSV
rendering. Local KartaView images instead use the existing **`--images`** route:

```sh
# Example only: NOT run here (it would load/download matching models).
uv run skills/geo-sleuth/scripts/match.py rank --query LOCAL_TARGET.jpg \
  --images reference-thumbnail --out matches.json --sheet matches.jpg
```

The image filename stem is the KartaView ID; join matches to `nearby.json` and
`index.json` for coordinates, date, projection and license. JSON sidecars are
ignored by `match.py`'s image discovery. No model was downloaded or run, and no
claim of measured matching quality follows from a readable reference image.

## Actual execution evidence (2026-10-30 UTC)

Read the source report §3.2 and retained `research/sources/kv-working-query.raw`
before implementation. That retained response normalizes offline to **70 rows,
70 unique valid items, zero duplicates/failures, `has_more: false`**; 66 rows have
allowlisted thumbnails under the strict blur gate. Prior documentation hostname
TLS failure and unsupported `limit` drift were **not re-probed**.

One live metadata invocation of the actual new CLI at the public Jakarta example
returned:

```json
{"status":"success_unknown_coverage","count":70,"returned_count":70,"duplicate_count":0,"failure_count":0,"coverage":"bounded/unknown","has_more":false}
```

Acquisition timestamp: `2026-10-30T01:28:37.717271+00:00`.
Raw response SHA-256:
`f7ea0ad2bf503c7e920387478dcae3c886401d9110cf07d2d832576570b67c86`.
Count reconciliation and unique-ID count were also asserted programmatically
against the saved normalized output. No credentials, target image or paid calls.

The sole live thumbnail attempt, using `fetch` for ID `616387694`, returned:

```json
{"id":"616387694","count":0,"failure_count":1,"failures":[{"id":"616387694","category":"http","error":"HTTP 409; no retry or redirect"}],"image_requests":1}
```

**Live image retrieval/decode remains blocked/unverified.** No image bytes were
accepted and this adapter run respected its one-image budget without an
alternative/CDN/raw fallback. A later, separate parent probe of the same metadata's
processed `imageProcUrl` CDN path returned curl exit 56 / HTTP 500, also accepting
no image; see `validation/kartaview-cdn-probe.json`. Neither failure establishes
missing geographic coverage or explains the server's cause. The adapter is a
verified public metadata path, **not a verified end-to-end live reference pipeline**.

Actual local capture directory (ephemeral, outside tracked sources):
`$TMPDIR/kartaview-adapter-6lcekqse/` (local absolute prefix redacted):
`nearby.json`, `nearby-cli.txt`, `thumbnail/fetch.json`, `thumbnail/index.json`.
The failure report has zero successful files and an empty index. These are real
outputs, not synthesized fixtures. Long-term evidence is summarized above because
scratch artifacts may expire; retained research source files were not overwritten.

The offline public CLI transport-seam tests **do** fully decode a generated
16×12 JPEG fixture, save it, read back the resulting index, open the actual saved
file with Pillow and verify dimensions. The fixture is labeled synthetic test
material and is never represented as provider imagery. Tests cover the one-call
query shape, partial/empty semantics, invalid envelopes, nonfinite/out-of-range
coordinates, unsafe asset URLs, malformed URLs, decode/size/policy/network
failures, HTTP 301/403/429/500, incomplete responses, dependency failures, no
redirect/retry behavior, count reconciliation, existing-output protection and
explicit date timezone uncertainty. **12 tests passed** with no provider network
in the initial test suite. Subsequent [independent review](kartaview-review.md)
fixed numeric-overflow/deep-JSON failures, first-invalid duplicate suppression and
the test dependency declaration; its focused suite passes 15 tests. The final full
repository run is recorded separately under `validation/`, not inferred from this
initial focused result.

## Sources and remaining checks

- [KartaView documentation](https://kartaview.org/doc),
  [terms](https://kartaview.org/terms), and local source report
  [`capability-research.md` §3.2](capability-research.md#32-kartaview-public-reading-worked-but-documentationclient-drift-is-real).
- Retained exact successful envelope: [`sources/kv-working-query.raw`](sources/kv-working-query.raw).
- Current local matching schema: `skills/geo-sleuth/scripts/match.py`,
  `_load_candidates` and `_open_images` (inspected, not inferred from old docs).

Outstanding: permitted working thumbnail endpoint (the direct storage request
returned HTTP 409), formal current hostname support, pagination semantics,
provider quotas/SLA, coverage guarantees and downstream redistribution review.
Do not lift the fixed query/image budgets or guess pagination to resolve these.

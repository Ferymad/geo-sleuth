# Capability routing: use the tool that supplies the missing evidence

Finding the region, recognizing the site, recovering camera pose and measuring
camera height are different problems. Do not keep reverse-searching when the
missing input is metric scene geometry. Do not run a pose solver before finding
trustworthy correspondences. More installed tools do not compensate for missing
observations, geographic coverage, calibration or scale.

Status labels here mean **existing**, **added local tool**, **researched optional**,
or **access-gated**—not a promise that every dependency/provider is installed.
The research reports in the repository contain fuller citations and probe records;
this guide is the small operational router loaded during a photo investigation.
For concrete municipal, historical, transport, archive and physical cross-check
routes, read [specialist rescue sources](rescue-sources.md).

## 1. Route by bottleneck

| Missing evidence / situation | Best next route | Minimum useful input | Boundary and fallback |
|---|---|---|---|
| Original metadata or a badly forwarded image | Existing `exif.py`, optional ExifTool | Original file/sidecar, not a screenshot when avoidable | Metadata is a hypothesis; preserve original bytes. Maker notes/XMP may add clues, but file timestamps are not capture times. |
| Small/oblique multilingual sign | Existing crops/OCR; configured language-specific OCR models | Original-resolution region and literal competing readings | A `--langs` flag does not prove a fallback model supports that script. Upscaling/translation cannot invent characters. |
| Published near-duplicate / recognizable object | Existing Baidu/Yandex; authorized Lens UI; source-page search | Upload authorization or an already public URL | These disclose content. AI overviews/similar-image labels are leads, not confirmed locations. Respect challenges and site terms. |
| Plausible country but no anchor | Country/region packs; optional GeoCLIP regional shortlist | Broad visual evidence and independent alternatives | Coarse gallery scores are not street coordinates. Diversify regions; do not discard contrary OCR/geometry evidence. |
| No useful Google/Baidu ground view | KartaView, token-authorized Mapillary, Commons/local official photos | Justified candidate area or landmark name | Coverage and capture date first. Missing images are not evidence against a site. Preserve attribution/license. |
| Sparse OSM or unreliable Overpass | Bounded regional OSM extract; Overture GeoParquet; local government inventories | Defensible bbox and feature class | Preserve release/schema and source provenance. Overture may reuse OSM, so agreement is not independent confirmation. |
| Strong terrain/skyline | Existing DEM scan/fit; optional Crestline fallback; PeakFinder visual cross-check | Skyline trace/crops, plausible region, camera/FOV search bounds | Missing DEM, clouds, snow and cluster-radius gaps are unknown coverage. Independent skyline tools can share DEM errors. |
| Architecture with straight vanishing lines | fSpy calibration, then measured controls and `pose.py` | Valid straight parallel/orthogonal directions; known length for scale | fSpy local axes are not true north/lat/lon. Curved pavement is not a vanishing line. Read [geometry workbench](geometry-workbench.md). |
| Known site, uncertain camera position/height | Existing `pose.py` or calibrated OpenCV PnP with independent controls | Distributed 2D–3D correspondences and shared height datum | Good reprojection on a single distant facade can still be unstable. Hold out features and perturb control geometry. |
| Several genuinely different overlapping views | COLMAP/current pycolmap; hloc retrieval/localization | Overlap, baseline/parallax, reliable scene details | Crops/rotations from one panorama are not independent camera centers. Metric scale and geographic alignment need controls. |
| High-accuracy scene geometry needed | Public/local survey LiDAR or a consented site scan; QGIS/PDAL/CloudCompare | Covered current point cloud, CRS/vertical datum, surface classification | DSM/roof heights are not pavement DTM. Camera height above local ground differs from elevation above a datum. |
| Verify the complete proposed camera | Blender with official fSpy importer or a calibrated camera model | Independently anchored geometry, lens/frame transforms | Render fixed landmarks and withheld controls; do not move objects or pick a cinematic lens just to look right. |
| Old image / new construction / seasonal mismatch | Historical street view, Esri Wayback, dated aerials/archives, official records | Candidate area plus plausible time range | Publication/index time is not capture time; mosaic pixels may have different acquisition dates. |
| Text-poor but distinctive infrastructure | Municipal tree/lighting inventories, utility/heritage/building records, GTFS/transport data | Confirmed feature type or local identifier | Enumerate a class, then compare geometry/photos. An inventory label or an absent database row cannot alone exclude a location. |
| Coastline/land cover/snow/water changed | Date-aware STAC/COG imagery, Sentinel-2 regional screening | Justified bbox/date range and cloud-free pixels | Nominal 10 m RGB does not identify a window, small sign or exact camera. Preserve masks, resolution and time. |
| Night sky / astronomical clues | Existing `sun.py`; Stellarium for visible stars/planets | Date/time or identifiable sky configuration plus orientation hypotheses | Unknown time, lens and horizon create ambiguities. Test hypotheses; do not claim a unique site from sky alone. |
| CRS/datum/geometry joins or many candidates | QGIS, GDAL/rasterio, pyproj, GeoPandas/Shapely, local spatial SQL | Known source CRS/units/axis order, bounded datasets | Do not accept ballpark transforms, missing grids, lat/lon swaps or degree-based metric buffers silently. |
| Interrupted or apparently exhausted run | Added `investigation.py`, existing board | Retained artifacts, actual route outcomes, next actions | Stop checks records, not truth. A failed provider blocks one route; `empty` needs a real response. |
| Compare a new model/tool/prompt fairly | Added `evaluate.py` and [blind evaluation](evaluation.md) | Frozen predictions and evaluator-held camera ground truth | Unit tests and public case replays do not demonstrate a better photo solve rate. |

## 2. Access and adoption gates

- **Existing local geometry/metadata:** use before adding a large dependency. Check
  model/schema assumptions and retain residuals, not merely a final coordinate.
- **KartaView:** public metadata worked at a known example using
  `api.kartaview.org/2.0/photo/` with `lat`, `lng`, `zoomLevel`; the older hostname
  failed TLS and `limit` was rejected. Do not guess paging. Preserve `hasMoreData`
  and report bounded coverage. Terms identify CC BY-SA 4.0 and attribution
  “© Grab and KartaView Contributors.” Semantic object search is a different,
  token-gated operation. See [official docs](https://kartaview.org/doc) and
  [terms](https://kartaview.org/terms).
- **Mapillary:** [API](https://www.mapillary.com/developer/api-documentation/)
  requires a client/user token. Unauthenticated JSON returned an OAuth error even
  under HTTP 500. No unlimited free quota is assumed. Image/data terms differ
  from the SDK license. Do not harvest tokens or infer global coverage from a
  single example.
- **Commons/Wikidata:** public metadata reading can add named/geotagged reference
  images without uploading the target. Inspect file-specific license, source,
  date and whether coordinates describe subject or camera. Query caps and missing
  geotags are not real-world completeness. See [GeoData API](https://www.mediawiki.org/wiki/Extension:GeoData#API).
- **OSM/Overture:** public Nominatim is not a bulk-enumeration backend; comply with
  the [usage policy](https://operations.osmfoundation.org/policies/nominatim/),
  including aggregate application rate, no confidential queries and restrictions
  on generic LLM/no-code use. Prefer bounded extracts for repeated scans. Overture
  [data licenses](https://docs.overturemaps.org/attribution/) are theme/source-specific,
  not the code repository's MIT license.
- **STAC:** [Planetary Computer metadata](https://planetarycomputer.microsoft.com/api/stac/v1)
  worked without a key; asset signing, collection-specific license and access
  limits still apply. Range-read a small justified crop, not an unbounded download.
- **Retrieval models:** current `match.py` already uses DINOv2 and SIFT. Optional
  [AnyLoc](https://github.com/AnyLoc/AnyLoc) adds patch/VLAD aggregation over a
  geotagged gallery, not GPS from nothing. Optional
  [LightGlue](https://github.com/cvg/LightGlue) needs a separately licensed extractor
  and geometric checks; SuperPoint's terms differ from LightGlue's.
- **Coarse models:** [GeoCLIP](https://github.com/VicenteVivan/geo-clip) proposes GPS
  gallery candidates; no fine precision follows from decimal places. The
  [StreetCLIP card](https://huggingface.co/geolocal/StreetCLIP) specifies CC BY-NC 4.0,
  geographic training bias and discourages private-image geolocation. It is not
  a universal production default.
- **External skills/MCP:** installing instructions does not install their runtime
  or register advertised tools. Review source and exact tool schemas; do not grant
  arbitrary desktop/Python execution merely because a bridge is popular. A
  cinematic Blender skill optimizes the wrong objective for camera measurement.

## 3. Added KartaView route: metadata first, failures explicit

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/kartaview.py nearby --at=LAT,LON --zoom 15 --out nearby.json
uv run ${CLAUDE_SKILL_DIR}/scripts/kartaview.py fetch --metadata nearby.json --id PHOTO_ID --out-dir reference-one
```

These are parameter templates. The first command makes one public coordinate
query, not a target-image upload, and requires a new output file. Inspect
`status`, `has_more`, `failure_count`, projection and capture-time uncertainty.
Even `has_more=false` means bounded/unknown geographic coverage, not a census.
The second selects one provider-declared finished/blurred thumbnail, requires a
fresh directory, and records failure without raw-image fallback. It uses a narrow
verified storage-host allowlist; unknown infrastructure is not trusted implicitly.
Development verified 70 unique metadata rows but the live storage thumbnail read
returned HTTP 409; a separate processed-CDN probe returned HTTP 500. Live image
retrieval and end-to-end matching therefore remain unverified, not silently
upgraded from metadata success. Use another source when that route is blocked.

On an actually successful fetch, local images use `match.py --images`, **not**
`--items` (the latter expects renderable panorama dictionaries). Preserve the
ID/date/coordinates/license mapping from `nearby.json`, `index.json`, and
`fetch.json`. Loading a matching model is a separate, potentially large download;
this adapter does not do it. Attribution/share-alike and provider terms still apply.

## 4. Compose tools, not confidence

Use a short chain that preserves independent evidence:

- Unknown region: original metadata/OCR → broad diverse hypotheses → candidate
  inventory → reference retrieval → geometry/invariant-feature verification.
- Known street, uncertain camera height: vanishing-line calibration → measured
  reference geometry/local ground surface → pose fit → held-out reprojection.
- Sparse references: named public landmarks/Commons/official inventories →
  terrain or overhead geometry → alternative ground imagery or a justified coarse
  conclusion. Do not mistake a data gap for a disproved candidate.
- Multiple images: independent-view reconstruction → metric scaling → geographic
  alignment → register query → withheld-feature and datum checks.

For every added route record the exact missing observable, minimum inputs, source
rights, what leaves the device, spend limit, actual coverage and fallback. If the
minimum input is unavailable, request that input or report the supported level;
a larger model or another skill cannot manufacture metric scale.

## Primary entry points

[fSpy tutorial](https://fspy.io/tutorial/) ·
[fSpy source/format](https://github.com/perarnia/fSpy) ·
[OpenCV PnP](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html) ·
[COLMAP FAQ](https://colmap.github.io/faq.html) ·
[hloc](https://github.com/cvg/Hierarchical-Localization) ·
[Blender camera manual](https://docs.blender.org/manual/en/latest/render/cameras.html) ·
[QGIS](https://qgis.org/) · [PDAL](https://pdal.io/) ·
[ExifTool](https://exiftool.org/) · [Stellarium](https://stellarium.org/) ·
[PeakFinder](https://www.peakfinder.com/)

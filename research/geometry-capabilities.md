# Camera geometry and geographically anchored reconstruction

Research captured 2026-10-30 UTC. **Primary-source desk research, not an executed reconstruction benchmark.** Public documentation/source code and small public metadata responses were retrieved; no photograph was uploaded, no paid service called, and no package/model/global installation performed. Retained captures are `research/sources/geometry-*`; the manifests record retrieval outcomes and hashes. Failed responses are retained as failures, not evidence of a capability. Source IDs below name those captures.

## Decision in brief

The useful chain is **identified scene → measured metric/geographic controls → camera model → existing `pose.py` → independent projected checks → optional Blender overlay**. fSpy is useful for intrinsics/orientation and a local metric frame; it does not discover geographic coordinates. COLMAP needs genuinely overlapping viewpoints, not extra crops of one photo. hloc+LightGlue localizes a query against an existing reference scene; it is not a global place database. LiDAR/3D buildings can supply controls and occluders, but acquisition date, CRS, vertical datum and the difference between raw elevation and hillshade are gating facts.

**Research recommendation:** a small, dependency-neutral `pose.py` control-point preflight/report. It should expose missing elevation provenance, rank/coverage and redundancy before an optimizer returns precise-looking coordinates. Do not start by replacing the solver or installing learned matchers. This research section is the original proposal; a subsequent separate opt-in implementation is documented in [pose preflight](pose-preflight.md), with [review fixes](pose-preflight-review.md). The solver itself remains unchanged.

Highest-leverage missing inputs are usually not another model:

1. The original full-resolution photograph, EXIF orientation, exact crop/resize history, lens/zoom/calibration and whether perspective correction was applied.
2. A confirmed anchor plus roughly 6–10 unmistakable controls spanning image width, geographic depth and preferably different elevations; exact image pixels and physical feature identity, not just nearby map labels.
3. Ground/roof elevations in one explicitly named datum, with source URL, capture date and uncertainty; an independent known length and true/grid bearing if starting with fSpy.
4. Two or more **held-out** corners/edges/occlusion relations not used in fitting. A second rendering of the fitted points is a consistency check, not independent evidence.
5. Only for SfM: independent overlapping reference photographs with baseline, usable texture, rights to process them, and external camera-center/GCP measurements if geographic placement is required.

## 1. Existing repository: use, do not duplicate

Inspected `skills/geo-sleuth/scripts/pose.py`, camera/coordinate portions of `geo.py`, and the complete `references/geometry.md`. The findings here refer to the inspected worktree, not an upstream release.

| Existing facility | Actual behavior | Remaining boundary |
|---|---|---|
| `geo.py range`, `fov`, `bearing`, `line`, `intersect`, `frame`, `spacing` | Known-size range, focal/FOV conversion, geodesic bearings, alignment/intersection, visibility screening, known-spacing line search already exist. | Another simple ruler/range script is duplication. Approximate local-plane coordinates are not a general EPSG/vertical-datum conversion system. |
| `pose.py solve` | NumPy-only custom finite-difference LM, multistart; parameters `[east_m,north_m,height,heading,pitch,roll,focal_px]`; can fix height, roll, hfov. Uses geographic control points plus pixels. | This is not OpenCV `solvePnP`: focal can be optimized, but principal point is fixed to image center, square pixels are assumed, and lens distortion is absent. |
| `pose.py project` and `draw` | Existing photo/control overlay, EXIF-aware stored/upright frame, saved `_frame` and `_params`. | Already supplies a lightweight alternative to Blender for point checks. No mesh depth test or general building model. |
| `pose.py check` | Fixed candidate positions; fits orientation/focal; rescoring with each point dropped; robust delta-chi-square screening. | Keep its distinction between screening and identifying a winner. Thresholds are project heuristics, not a universal statistical certification. |
| Uncertainty | Covariance, horizontal-control/pixel Monte Carlo and leave-one-out already exist. | `mc_radius` perturbs only `pts[:, :2]`, not control elevations; draws independent noise and restarts at the fitted solution. It does not cover correlated map shifts, wrong datum/roof identity, principal-point/distortion error or unvisited solution branches. |

Concrete source locations: `pose.py:57–74` local projection; `117–182` solve/model/count/covariance; `185–205` Monte Carlo; `207–231` leave-one-out; `248–290` candidate checks; `326–344` overlay. `geo.py:230–311` already implements rulers and intersections; `314–396` frame/occlusion approximations; `414+` known-spacing search. `references/geometry.md` §§7,10,11 already explains much of this workflow.

Important qualifications for current prose:

- “At least four points” is an equation-count starting point, **not** a uniqueness or stability guarantee. `solve` checks `n_obs < k`, not control rank or condition. Four points with all seven parameters free give little redundancy; leave-one-out may be unavailable.
- Missing `h` silently becomes `0.0` in solve/project/check. That is safe only if zero is an intentional shared local reference, not an unknown roof/ground elevation.
- `_frame` uses a fixed `110540` metres/degree latitude and `111320*cos(lat0)` longitude scale. These are approximate flat coordinates, not exact ECEF/ENU. Do not carry survey-grade claims across large areas or export them as exact projected CRS coordinates.
- A label of “95% radius” is conditional on the implemented noise/model assumptions. It must not be presented as total geographic accuracy when control identities/datums are uncertain. Current geometry reference wording “use it directly” should eventually be qualified, not copied into new integrations.
- Fixed center principal point is particularly consequential for cropped/shifted/perspective-corrected images. An fSpy result with nonzero principal point cannot be represented faithfully merely by copying hfov into current pose specs.

## 2. Capability cards: problem → minimum inputs → outputs → limits → access → recipe

### A. Single-photo Manhattan-world matching: fSpy

**Problem:** Recover a plausible perspective camera and local metric frame from architecture when EXIF is absent.

**Minimum inputs:** A perspective image; two measured line segments for each vanishing direction. In two-VP mode, two scene directions assumed perpendicular plus a known/assumed principal point permit focal/orientation estimation. Single-VP mode additionally needs known focal/sensor information and horizon information. Assign axis directions and the local origin. A known length along the chosen reference axis sets metric scale. A third VP can constrain principal point. These assumptions must describe the actual scene: visually convenient but nonorthogonal road/building directions do not qualify.

**Tool/output:** [fspy.io](https://fspy.io/), canonical [perarnia/fSpy](https://github.com/perarnia/fSpy), [solver source](https://github.com/perarnia/fSpy/blob/702189ec5acbbd2c8ba492db0e52ecb5fc908f5c/src/gui/solver/solver.ts). Project contains image dimensions, principal point, relative focal, horizontal/vertical FOV, camera/view transforms and the original image. The official [perarnia/fSpy-Blender](https://github.com/perarnia/fSpy-Blender) importer reads that project and configures a Blender camera/background.

**Limits:** No latitude/longitude or geocoding. A known length fixes scale, not global translation or north. Need a geographically located origin, an axis direction in the geographic frame, and an appropriate vertical reference to place the result on Earth. Without a reference length, translation is arbitrary scale; geometry behind visible surfaces is unconstrained. Near-parallel image lines yield unstable VP intersections. Distortion, crop/principal-point assumptions and false orthogonality can absorb errors into focal/pose. A photograph can support a coarse model, not uniquely reconstruct every hidden surface.

**Cost/license/auth:** Free local desktop software, no account/photo upload required. Application and official importer GPL-3.0 (importer headers specify v3-or-later). Treat source reuse accordingly; invoking the external tool or consuming its output is distinct from copying GPL implementation into this repo. Legacy `stuffmatic/*` URLs redirect to canonical `perarnia/*`.

**Integration recipe:**

1. Preserve an upright, unwarped working image and its pixel transform to the original. Mark VP lines, axis signs, principal-point assumption and the origin.
2. Measure a real length from survey/as-built information or an unambiguous footprint; record uncertainty, not a nominal door/floor/car size as fact. Save `.fspy` and the marked-line screenshot.
3. Independently measure geographic origin and axis azimuth. Transform from local axes into a documented local geographic frame. Do not assume fSpy X/Y already mean east/north.
4. Use the resulting hfov/orientation only as priors for current `pose.py`, with actual lat/lon/height controls. Fix hfov only if calibration/crop assumptions are defensible; do not blindly import a noncentral principal point into the centered model.
5. Use official Blender importer for manual visual checks rather than reimplementing its binary/project handling first. Check held-out corners and parallel lines, not just the features used for VP calibration.

**Retained proof:** `geometry-fspy-solver.txt:661–713` sets default translation with `DEFAULT_CAMERA_DISTANCE_SCALE`, then applies `scale = referenceDistance / defaultHandleDistance`; `:737+` constructs camera parameters. `geometry-fspy-importer.txt:24–57` parses camera parameters from the project; `geometry-fspy-addon.txt:95–133` sets `angle`, `matrix_world`, principal-point shifts and resolution. `geometry-fspy-solver.txt:620` warns `Near parallel lines for VP`.

### B. Absolute camera pose from geographic controls: OpenCV/current pose

**Problem:** Estimate camera position and orientation once corresponding 3D world points and image pixels are known.

**Minimum inputs:** A calibrated intrinsic matrix `K`, distortion model/coefficients, and 2D–3D correspondences in one metric frame for ordinary PnP. OpenCV's iterative initialization needs **at least six nonplanar points**, or **four planar points** with homography initialization. P3P/AP3P via `solvePnP` use four points; SQPnP supports three or more. These are algorithmic minima, not recommended field data budgets. IPPE is specifically planar; IPPE_SQUARE requires its exact four-corner ordering. Planarity is not universally invalid; collinearity or very small angular extent is a more serious observability warning.

**Tool/output:** [Official OpenCV PnP documentation](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html); direct rendered docs returned 403, so claims were checked against the [official 4.x documentation source](https://github.com/opencv/opencv/blob/5584875dbac61650e966ec77946a38e386b7b3e5/modules/calib3d/doc/solvePnP.markdown) and [calib3d header](https://github.com/opencv/opencv/blob/5584875dbac61650e966ec77946a38e386b7b3e5/modules/calib3d/include/opencv2/calib3d.hpp). `rvec,tvec` transform world/object → camera, **not** camera location. Camera center is `C = -R.T @ t`. OpenCV camera axes are right/down/forward. `solvePnPGeneric` exposes multiple solutions for supported solvers; `solvePnPRansac` handles outliers; refinement minimizes reprojection error.

**Limits:** Ordinary solvePnP assumes K; it does not magically recover unknown focal, crop and distortion. The documented `SOLVEPNP_DLS` and `SOLVEPNP_UPNP` implementations are broken and fall back to EPnP—do not recommend UPNP as an unknown-focal fix. Planar scenes can have competing poses; compare positive depth, held-out errors and physically possible locations rather than keeping only the smallest fitted residual. RANSAC cannot fix a coherent wrong facade/coordinate datum or repeated-window identity. Calibration on another zoom/focus/resolution may not transfer; update intrinsics after crop/resize.

**Cost/license/auth:** Free local OpenCV, Apache-2.0 for the inspected current repository; no API/account. Installation would be an optional project dependency, not required for the proposed preflight.

**Integration recipe:** Keep current NumPy solver as baseline. Collect 6–10 spread controls and held-out checks, establish metric CRS/vertical datum and image frame. If adding a calibrated OpenCV backend later: transform geographic points to exact local metric coordinates, supply K/distortion, enumerate planar alternatives as appropriate, RANSAC then refine, reject points behind camera, recover C and translate camera-axis conventions. Preserve inliers and per-point residuals; compare against existing multistart pose instead of silently replacing it. Unknown focal remains an explicit estimation problem, not a solver flag shortcut.

**Retained excerpts:** `geometry-opencv-pnp-4x.txt:104–107`: “Initial solution for non-planar ... needs at least 6 points ... planar ... at least 4 points”; `:115–124`: DLS/UPNP “Broken implementation ... fallback to EPnP”; `:156–174`: multiple solutions, RANSAC and refinement. `geometry-opencv-calib-4x.txt` retains calibration/intrinsic contracts.

### C. Multi-photo reconstruction and georeferencing: COLMAP + current PyCOLMAP

**Problem:** Reconstruct a reference scene from independent overlapping views, then align it geographically or register another query image.

**Minimum inputs:** At least two views with common textured scene and translation for triangulation; practically a connected, well-overlapped set across meaningful baselines. Intrinsics known or estimable with sufficient view diversity. For post-hoc camera-center alignment, **at least three registered images with externally known 3D camera centers**; use well-separated noncollinear centers and additional checks. Three collinear centers do not constrain rotation about their line adequately. A known scale alone does not supply north/translation. GCP-to-scene-point alignment is a different correspondence set from camera-center alignment.

**Tool/output:** [COLMAP FAQ geo-registration](https://colmap.github.io/faq.html#geo-registration), [format](https://colmap.github.io/format.html), [CLI](https://colmap.github.io/cli.html), [current PyCOLMAP docs](https://colmap.github.io/pycolmap/pycolmap.html), [maintained Python README within colmap/colmap](https://github.com/colmap/colmap/tree/main/python). Do **not** start a new dependency on the deprecated separate `colmap/pycolmap` repository. Outputs: sparse points, camera intrinsics/poses/tracks; optional dense cloud/mesh; transformed model and alignment residuals. Current formats include rigs/frames; do not assume only legacy three-file models.

**Limits:** SfM starts at arbitrary similarity scale/frame. Extra crops, resized copies or multiple generated views of one photo do not create independent baselines. Pure rotation can match well but cannot establish scene depth. Repeated facades, reflective water/glass, moving traffic/foliage, seasonal changes, incompatible imagery epochs and weak overlap can produce disconnected/incorrect models. GPS priors are measurements with uncertainty, not truth. Dense reconstruction adds compute and cannot repair a bad sparse model.

**Cost/license/auth:** COLMAP core BSD-style license (`geometry-colmap-license-fixed.txt`; dependencies retain their own licenses). Free local CLI/Python; no service key/photo upload necessary. SIFT can avoid learned-model weights; CPU routes exist, but dense processing/hardware requirements must be checked separately. No CPU/GPU speed or installation claim was benchmarked here. PyCOLMAP README describes platform wheels; CUDA wheel support is separately documented, not a promise of macOS CUDA.

**Integration recipe:**

1. Assemble licensed independent images with coverage/epoch manifest. Group/shared-intrinsic cameras correctly; avoid assuming all Internet images share K. Run feature extraction → geometric matching → sparse mapper. Inspect connected components, tracks and triangulation geometry before dense work.
2. For camera-center georegistration, create lines `image_name.jpg latitude longitude altitude` when `ref_is_gps=1`, or `image_name.jpg X Y Z` for Cartesian input. These are **camera centers**, not landmark locations. Use exact registered image names and a consistent height definition.
3. The documented CLI pattern is:

   ```sh
   colmap model_aligner --input_path sparse/0 --output_path aligned \
     --ref_images_path centers.txt --ref_is_gps 1 \
     --alignment_type ecef --alignment_max_error 3.0
   ```

   This is a documentation-derived recipe, **not executed here**. The 3.0 threshold is an example in target metric units, not a justified tolerance for every dataset. FAQ documents GPS→ECEF or ENU and the first image GPS coordinate as ENU origin. Record that origin explicitly.
4. Current Python API provides `align_reconstruction_to_locations(src, tgt_image_names, tgt_locations, min_common_images, ransac_options) -> Sim3d | None`. Supply already Cartesian target locations; inspect returned transform then explicitly apply/save it to the model. Do not confuse estimating a transform with updating external state.
5. Validate alignment on withheld camera centers/known lengths/roof elevations; persist original and transformed model plus CRS/vertical datum/epoch/units/transform. Register query against that model, then convert query camera center back through the saved geographic transform.

**Retained proof:** `geometry-colmap-faq.txt:768–803`: camera centers, similarity frame, GPS/ECEF/ENU and minimum three images; `:804–874` CLI. `geometry-colmap-pycolmap.txt` retains `align_reconstruction_to_locations`, `estimate_and_refine_absolute_pose` (“LO-RANSAC followed by non-linear refinement”). `geometry-colmap-format.txt` specifies world-to-camera quaternion/translation and camera center; `geometry-colmap-python-readme.txt` is the maintained Python API source.

### D. Query-to-reference localization: hloc + LightGlue

**Problem:** Match a new photo into an already reconstructed/geographically anchored reference scene when hand controls are expensive.

**Minimum inputs:** Query photo + camera model, overlapping reference images/features/matches, and a 3D reference reconstruction with tracks linking reference features to 3D points; optionally a specialized LiDAR-assisted reference pipeline. Known place candidate/retrieval corpus first. LightGlue alone takes two sets of local features and returns matches, not world coordinates.

**Tool/output:** [cvg/Hierarchical-Localization](https://github.com/cvg/Hierarchical-Localization), [localize_sfm.py](https://github.com/cvg/Hierarchical-Localization/blob/c13273bd0ecc2917a35910fd843712a1c6243193/hloc/localize_sfm.py), [cvg/LightGlue](https://github.com/cvg/LightGlue). hloc orchestrates retrieval → reference/query local matching → 2D–3D association → robust absolute pose. `QueryLocalizer` uses current `pycolmap.estimate_and_refine_absolute_pose`. Output pose is in reference-model coordinates until that model is geographically anchored.

**Limits:** A good pairwise match or homography is not camera geolocation. Many inliers on one repeated facade are not independent geometric support. A public LiDAR cloud alone does not provide image-feature tracks; need rendered/registered reference views or a dedicated image-to-scan pipeline. **Important source-code trap:** in the non-clustered branch, if PnP fails, hloc assigns the first retrieved reference image pose (`closest.cam_from_world()`). Thus a results-file pose is not proof query PnP succeeded. Integration must inspect localization logs / `PnP_ret`, inliers, residuals and branch, label fallback as retrieval-only, and never feed it to board exclusion as solved geometry.

**Cost/license/auth:** hloc Apache-2.0; LightGlue code **and its pretrained weights** Apache-2.0. Extractor licenses differ: upstream specifically flags SuperPoint code/weights as restrictive; ALIKED BSD-3-Clause; DISK Apache-2.0. Verify every selected extractor/checkpoint. Running local avoids photo upload, but Torch/model downloads are real disk/compute costs and outside this task's no-model-install scope. SIFT+LightGlue still needs LightGlue weights. Colab demos are not an upload-free local path.

**Integration recipe:** Optional later backend only. Start with a small already anchored reference scene, pin compatible hloc/PyCOLMAP versions, preserve image/feature pixel conventions (`localize_sfm.py` explicitly adds `0.5` to keypoints for COLMAP), choose license-cleared features, retrieve a bounded reference set, match, localize, check success/logs, recover camera center and uncertainty. Compare against a few manually identified held-out controls. Retain annotated inlier distribution, not just match count.

**Retained excerpts:** `geometry-hloc-readme.txt` gives full reconstruction/localization pipeline; `geometry-hloc-localize.txt` retains PnP call and nearest-reference fallback. `geometry-lightglue-readme.txt:183` explicitly distinguishes the matcher/weight license from SuperPoint. This is a capability option, not a recommended immediate installation.

### E. Blender camera and mesh overlay verification

**Problem:** Test whether a geographically placed camera and building/terrain model reproduce visible contours, scale and occlusion.

**Minimum inputs:** Camera extrinsics, intrinsics including principal point/crop, exact output dimensions/pixel aspect; model in a documented local metric frame with geographic origin and datum; original/undistorted image and several held-out visible features. Can start with measured footprint extrusions rather than a full photorealistic model.

**Tool/output:** [Camera manual](https://docs.blender.org/manual/en/latest/render/cameras.html), [Camera API](https://docs.blender.org/api/current/bpy.types.Camera.html), [world_to_camera_view API](https://docs.blender.org/api/current/bpy_extras.object_utils.html#bpy_extras.object_utils.world_to_camera_view), and official fSpy importer. Outputs: background-image/wireframe renders, reprojected check points, depth/occlusion comparisons and a saved scene with audit metadata.

**Limits:** Blender is a verifier/visualization environment, not additional independent evidence. Tuning both camera and invented building heights to match the same pixels can make almost any overlay look convincing. A visually plausible model is not a reconstruction of hidden geometry. Standard perspective rendering does not automatically reproduce an original distorted lens or panorama/stitch. Model/source epoch must match the photo sufficiently.

**Cost/license/auth:** Free local Blender under GPL, no account or upload needed ([official license](https://www.blender.org/about/license/)); output artwork is not automatically GPL. Third-party models/textures have separate rights.

**Integration recipe:** Use a local east/north/up origin, not huge ECEF coordinates as mesh vertices. For current pose conventions, construct the same `right,up,fwd` basis as `pose.project`; Blender camera local +X maps to `right`, +Y to `up`, and -Z to `fwd`. Set camera location in that same frame and derive `matrix_world` from those columns. Set perspective lens/FOV with explicit sensor fit, square pixel aspect and image dimensions; zero shifts only for the current centered model. An external OpenCV camera instead needs the right/down/forward → right/up/back axis conversion—never blindly copy `rvec` into Euler fields.

Render/compare points using `world_to_camera_view`, whose normalized origin is **bottom-left**; convert to this repo's top-left pixels using `u=W*x, v=H*(1-y)` under the declared pixel-edge convention and test possible half-pixel offsets. Negative depth means behind camera. First test that held-out world points project to the same pixels in NumPy and Blender; then test an overlay of edges/occluders. Save a residual table and fixed camera settings. A manual Blender test is not reported as passed here.

**Retained proof:** `geometry-blender-world-camera.txt` says “(0, 0) is the bottom left ... (1, 1) ... top right”, negative z is behind camera, and shift/lens/sensor are accounted for. `geometry-fspy-addon.txt` shows explicit FOV, world transform, principal-point and resolution setup. `geometry-blender-api-camera.txt` documents `sensor_fit`, `shift_x`, `shift_y`.

### F. Survey-style multi-photo processing: OpenDroneMap

**Problem:** Turn a deliberately acquired, overlapping image survey into orthophotos, clouds, DSM/DTM and mesh with geographic control.

**Minimum inputs:** Overlapping independent imagery with useful baseline; aerial acquisition is its natural fit, not a single unrelated Internet photograph. GPS/RTK camera positions or measured GCPs for geographic anchoring. ODM's guidance recommends about five GCPs for many jobs and more for larger projects, distributed horizontally and in elevation, observed in multiple photographs. These are acquisition recommendations, not algebraic PnP minima.

**Tool/output:** [ODM GCP docs](https://docs.opendronemap.org/gcp/), [image geolocation file](https://docs.opendronemap.org/geo/), [acquisition advice](https://docs.opendronemap.org/flying/), [official ODM repo](https://github.com/OpenDroneMap/ODM). GCP file begins with coordinate system, followed by `X Y Z image_x image_y image_filename [gcp_name]`. Optional `geo.txt` supplies externally measured **image** geolocations, distinct from GCP point observations. Outputs include georeferenced point cloud/mesh, orthophoto and terrain/surface products depending on options.

**Limits:** Heavy pipeline/container/storage relative to current lightweight tools. No benefit from duplicating a single image. Dense terrain models can fail under trees/water/repeated texture; photo-derived “DTM” is not equivalent to a surveyed ground-return LiDAR DTM. Survey accuracy is not obtained just by writing EPSG:4326 in the header. Current docs' GCP recommendations have multiple contexts; record actual visibility/geometry instead of treating a single overlap number as a universal rule.

**Cost/license/auth:** ODM AGPL-3.0, free self-hosted/local engine; paid hosting/installers/support are optional separate products. No hosted processing used. Docker image downloads and many-image processing have substantial local resource costs; installation deliberately not attempted.

**Integration recipe:** For a future user-provided survey, validate CRS/vertical datum and GCP labels/image pixels, prepare project images + `gcp_list.txt`, run local ODM with explicit product/resolution options, retain GCP residuals and independent checkpoints, then export only a bounded scene into the same local frame as pose/Blender. Do not add ODM as a default dependency for single-photo geo-sleuth.

**Retained excerpts:** `geometry-odm-gcp.txt` contains format and distribution/visibility recommendations. `geometry-odm-datasets.txt:286–293` distinguishes full-3D cross-grid/nadir advice from 2D/2.5D overlap advice. `geometry-odm-georef.txt:318–407` describes `geo.txt` projection and detection.

## 3. Public elevation, LiDAR, building height and 3D scene acquisition

A footprint is not a roof height; a raster called DEM may be DSM rather than bare earth; spatial resolution is not vertical accuracy; rendered hillshade values are not metres. Use a bounded candidate area and inspect actual tile metadata **before** downloading large archives. The table records what the retrieved source establishes, not complete nationwide availability for every product.

| Region / primary route | Minimum inputs → usable output | Coverage/limitations | Cost/license/auth and integration |
|---|---|---|---|
| **Ireland:** [GSI Open Topographic LiDAR](https://data.gov.ie/dataset/open-topographic-lidar-data), [coverage services](https://gsi.geodata.gov.ie/server/rest/services/Lidar?f=pjson) | Candidate bbox → coverage polygon → tile download with provenance, numeric DTM/DSM where available. Catalogue lists GSI 1 m and other providers/resolutions. | Multi-provider, survey-specific coverage, not a promise every site has raw LAS or full current national building models. Catalogue says collected 2015–2021; individual tile dates are more specific. Malin Head vertical datum. Dublin NYU, OPW, TII and other coverage services are listed. | Catalogue CC BY 4.0, preserve required attribution and per-provider metadata. Public metadata returned without login; individual archives were not downloaded. Query coverage before extracting terrain/roof elevations. |
| **Ireland verified concrete metadata path** | [Phase2 FeatureServer](https://gsi.geodata.gov.ie/server/rest/services/Lidar/IE_GSI_LiDAR_Coverage_GSI_Phase2_IE26_ITM/FeatureServer?f=pjson) identifies **layer 12**, not assumed layer 0. [Layer 12](https://gsi.geodata.gov.ie/server/rest/services/Lidar/IE_GSI_LiDAR_Coverage_GSI_Phase2_IE26_ITM/FeatureServer/12?f=pjson) has `DATA_URL`, `DATECAPTUR`, `LICENCE`, `RESOLUTION`, `RMS_ERROR` fields. | Sample public record `P_602766`, Longford: 2018-06-28, 1 m, `Within +/- 150mm`, URL `https://gsi.geodata.gov.ie/downloads/LIDAR/P_602766.7z`. This is metadata's stated accuracy for that tile, not independently measured camera accuracy or a blanket guarantee. | Small metadata query only, no archive downloaded. Use geometry filter in an actual candidate-area query, request only needed fields, retain that record with every height. |
| **Ireland visualization trap** | [Image service metadata](https://gsi.geodata.gov.ie/imagehost/rest/services/Lidar/IE_GSI_LiDAR_DTM_HS_GSI_Phase2_1m_IE26_ITM_MH_TIFF/ImageServer?f=pjson) → shaded visual context, **not numeric height**. | Source explicitly says “This data shows the hillshade of the DTM”; `pixelType=U8`, values `0..255`, one band, horizontal EPSG:2157. An `identify` on this service would return shade, not elevation. | Free public endpoint, but unsuitable to populate `h`. Follow coverage `DATA_URL` and inspect actual numeric raster rather than treating “ImageServer” as sufficient. |
| **England:** [EA National LIDAR Programme catalogue](https://www.data.gov.uk/dataset/f0db0249-f17b-4036-9e65-309148c97ce4/lidar-composite-dtm-1m), [survey download](https://environment.data.gov.uk/DefraDataDownload/?Mode=survey) | Bbox + dated survey/tile selection → 1 m elevation products, DTM and first-return DSM. | Retrieved catalogue title is **National LIDAR Programme**, despite legacy URL slug naming composite DTM. Says all England, Phase 1 captured Jan 2017–Feb 2023, with later repeat blocks. England is not the whole UK. DTM is ground-filtered; first-return DSM includes trees/buildings. | OGL; no public access constraints stated. Download survey index and matched DTM/DSM; confirm tile vertical CRS/units and date. National coverage does not make every roof a reliable control. |
| **Wales:** [DataMapWales LiDAR viewer](https://datamap.gov.wales/maps/lidar-viewer/) | Bbox → downloadable tile catalogues with DTM/DSM. | Viewer confirms Welsh Government 2020–2023 catalogue and other layers. Different survey epochs/resolutions must be checked on the layer, not inferred from England's programme. | Viewer metadata says OGL. Public page accessible without account; exact tile download/auth behavior not exercised. |
| **Scotland:** [Scottish Remote Sensing Portal](https://remotesensingdata.gov.scot/data#/list) | Candidate region → survey collection/coverage discovery. | Verified portal shell only; the JS catalogue was not enumerated here. Do not assert nationwide coverage, specific resolutions or a uniform license from this capture. | Check collection-level license/date/access. Portal is a feasible discovery route, not verified data availability for an arbitrary site. |
| **Northern Ireland** | Requires a verified local survey/provider record before height use. | Tested generic nidirect LiDAR URL returned 404; this research does **not** establish a uniform NI public LiDAR coverage/download route. Do not silently substitute England data or apply Newlyn to Belfast/local heights. | Availability/license/auth unresolved here. Use jurisdiction-specific official catalogue metadata for a real candidate. |
| **Great Britain footprints:** [OS OpenMap – Local](https://www.ordnancesurvey.co.uk/products/os-open-map-local) | Bbox + vector download → context/footprints for simple extrusion **only with independent heights**. | Official page says free, raster/vector and six-month updates; it does not establish a free national per-building 3D/height model. Do not mistake OS commercial height products for this open product. | Free open product, check product license/attribution when downloading. Account behavior of exact download workflow not tested. |
| **United States:** [USGS 3DEP products/services](https://www.usgs.gov/3d-elevation-program/about-3dep-products-services), [LidarExplorer](https://www.usgs.gov/NationalMap/LidarExplorer) | Area of interest → project LiDAR cloud/metadata or bare-earth DEM. | Products page establishes LiDAR point clouds and DEM resolutions; 1 m coverage is expanding/project-based. Alaska also has 5 m IfSAR DSM/DTM: not all US data is LiDAR. Check project quality level/classification/date and exact vertical CRS, not just “3DEP”. | USGS says all 3DEP products “free of charge and without use restrictions.” Project download method may vary; product description is public without login. Public cloud routes can avoid bulk downloads but were not tested. Do not equate national ~10 m/30 m DEM with building-corner measurement. |
| **EU/global broad terrain:** [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) | AOI → GLO-30/GLO-90 DSM, European EEA-10 for eligible users. | DSM, not bare ground or individual roof geometry. EGM2008 heights, metres. GLO-30 ~30 m and GLO-90 ~90 m; EEA-10 10 m over listed European coverage, not automatically open to general users. | GLO-30/GLO-90 free license; public CDSE description says registered general users can download them; EEA-10 is restricted to eligible categories. CDSE bulk API/S3 uses credentials. No login attempted. |
| **EU/global coarse urban heights:** [GHSL GHS-BUILT-H R2023A](https://human-settlement.emergency.copernicus.eu/ghs_buH2023.php), [official dynamic data sheet](https://human-settlement.emergency.copernicus.eu/data/ghs_buH2023.json) | Candidate urban area → 100 m / 3 arc-second **aggregated** building-height priors. | 2018 product derives from AW3D30/SRTM30 plus Sentinel-2 shadow information. Separate gross-height (built volume/cell area) and net-height (mean built-surface height) layers. Not the height of a particular spire/roof. Gross/net misinterpretation can be severe. | Page labels data open/free. Exact dataset reuse/citation terms should be retained from JRC catalogue at acquisition; this is not a verified CC0 claim. Use for area ranking, not high-precision PnP controls. |
| **EU example with actual detailed buildings:** [3DBAG](https://docs.3dbag.nl/en/), [download](https://3dbag.nl/en/download) | Dutch AOI → multi-LoD building models from BAG footprints and AHN heights; LoD1.2/1.3/2.2. | Netherlands-specific, not an EU-wide model. Roof model/ground quality and survey age remain constraints; docs mention simplified models for inconsistent glass-roof LiDAR. National/local portals elsewhere must be assessed individually. | [Official data/documentation terms](https://docs.3dbag.nl/en/copyright/) explicitly license downloadable files and web-service data under CC BY 4.0; required credit is “© 3DBAG by tudelft3d and 3DGI”, with a link to the copyright page in digital media. No bulk data download; inspect delivery format/schema/CRS when acquiring. |

### Datum and elevation contract

Current `pose.py` says all h values must use the same datum, but “ASL” alone is insufficient. A robust future control record should retain:

```json
{
  "name": "unambiguous roof corner",
  "px": [123, 456], "ll": [53.0, -8.0], "h": 41.2,
  "horizontal_crs": "EPSG:4326",
  "vertical_reference": "explicit named datum, not just ASL",
  "height_kind": "absolute_roof_elevation",
  "units": "m", "source_url": "official tile/record URL",
  "source_capture_date": "YYYY-MM-DD",
  "sigma_xy_m": 2.0, "sigma_h_m": 0.5,
  "feature_note": "same physical corner in photo and source"
}
```

Illustrative schema only; numbers are not observations. Existing solver ignores these extra provenance fields; recording them does not implement a transform.

Rules grounded in [OS coordinate transformations](https://www.ordnancesurvey.co.uk/geodesy-positioning/coordinate-transformations), [NOAA datum explanation](https://geodesy.noaa.gov/INFO/facts/datum.shtml), [NOAA GEOID18 computation](https://geodesy.noaa.gov/GEOID/GEOID18/computation.html), [PROJ transformation documentation](https://proj.org/en/stable/usage/transformation.html) and the regional metadata above:

- **Horizontal and vertical references are separate.** EPSG:4326 is a horizontal geographic CRS, not a declaration of metre-valued orthometric height. GPS/EXIF altitude and a national DEM can differ in reference even when both are labelled “altitude.”
- Distinguish ellipsoidal height `h`, orthometric/gravity-related height `H`, and geoid separation `N`: with compatible definitions, `h = H + N`. Do not apply an arbitrary constant or wrong geoid; location, datum realization and epoch matter. A horizontal reprojection alone is not a vertical conversion.
- Ireland GSI source explicitly names **Malin Head**. GB OS distinguishes GNSS ellipsoidal coordinates from **ODN/Newlyn**-based heights; OSTN15 links horizontal systems, OSGM15 handles mean-sea-level-based heights. Do not treat national/island/Belfast datums as interchangeable.
- US project metadata may reference NAVD88 or another realization; inspect it, do not infer from `.las` or WGS84 map display. GEOID18 conversion is tied to its specified reference frames/regions, not a worldwide generic geoid.
- Copernicus DEM explicitly specifies **EGM2008 (EPSG:3855)**; that is not automatically equivalent to Malin Head, Newlyn, NAVD88 or a different global geoid used by another DEM. Current terrain tiles' vertical provenance needs its own audit before mixing with these controls.
- Building height above ground is relative: derive absolute roof elevation from a compatible nearby ground elevation **plus** measured building height, with roof geometry and terrain slope accounted for. Camera eye height above ground likewise needs ground elevation added. Do not add absolute DSM elevation to absolute terrain elevation.
- `DSM - DTM` estimates above-ground surface height only when grid alignment, horizontal/vertical datum, dates and resolution are compatible. It can measure a tree, antenna or edge interpolation, not necessarily a building roof. A raster's 1 m cell size does not imply 1 m planimetric or centimetric vertical accuracy.
- Missing transformation grids/uncertain datum means **report unresolved**, not silently accept a low-accuracy/ballpark transform. Preserve transform operation/grid provenance and units. Elevation uncertainty should propagate into pose, not just a text footnote.

## 4. Concrete next integration: control-point preflight (proposed, not implemented)

### Why this rather than fSpy import or a second solver

It fits the existing NumPy/pillow dependency envelope, protects every input route (manual map, fSpy-derived, LiDAR, future SfM), and addresses a real code boundary: equation counting is present, but h silently defaults to zero and model/geometry observability is not surfaced before fitting. It improves input discipline without changing the numerical backend or adding downloads.

### Bounded implementation contract

Add an opt-in `pose.py preflight spec.json` producing a JSON report plus short human summary. Keep existing solve output/CLI behavior initially compatible. Later make the same helper callable by `solve` for warnings. No OpenCV, Blender, Torch, browser or network dependency.

**Hard errors (unambiguous malformed data):** malformed/nonfinite numeric values; nonpositive image dimensions; impossible latitude/longitude; wrong pixel/coordinate arity; absent init origin; invalid/nonpositive hfov; exact duplicate observations that contradict one another; fewer scalar observations than actual free parameters. Compute free count using existing `NAMES`/fix semantics, do not invent a separate divergent model.

**Warnings, not automatic exclusion:**

- Missing `h`/vertical reference/height kind/provenance; mixed known datums or units. Preserve legacy zero-height cases with an explicit intentional local-plane declaration rather than treating all zeros as bad.
- Duplicate/near-duplicate controls, small image convex-hull/width/height coverage, near-collinear horizontal/world controls and few distinct depths/elevations. SVD/rank diagnostics must normalize units and report thresholds; **planar controls are not automatically invalid**.
- Actual degrees of freedom and whether leave-one-out has enough redundancy. List what to add or fix (another spread point, independently known height or hfov).
- Pixel positions outside declared image/frame, legacy missing `frame`, unknown crop/principal point/distortion status. Outside pixels may be intentional extrapolations; make warnings explainable.
- Narrow bearing span/depth spread relative to init camera, with explicit note that init is only a hypothesis. Do not claim definitive observability from a bad init.

**Output:** `valid_input`, `errors`, structured warning codes, counts/free parameters/dof, per-point metadata gaps, geometric diagnostics and actionable `missing_inputs`. Say **“preflight does not certify a unique pose or a geographic error radius.”** It is not a board computed-exclusion artifact and must not turn warnings into candidate exclusions. No new optimizer, fSpy binary parser, datum transformer or confidence scorer in this change.

**Acceptance tests for the future implementation:** valid well-spread controls; legacy explicit flat-ground case; nonfinite/malformed input; repeated controls; collinear/narrow-span cases; planar-but-valid controls warned not rejected; mixed/missing heights; correct free count for hfov/height/roll fixes; no-redundancy LOO explanation; upright/stored frame diagnostics. Tests should assert determinism, no network/model download, and no change to existing solve behavior. This proposal has not been implemented or exercised as code.

### Suggested next human acquisition task

Produce one real control sheet for an already confirmed scene: upright full image, six fitted controls plus two held-out controls, measured footprint/known-length evidence, per-control physical identity and roof/ground elevation provenance. In Ireland the verified layer-12 download metadata provides a concrete bounded route to test whether usable elevation coverage exists. If the scene lacks numeric roof/ground heights, acquiring those is more valuable than trying hloc or a more elaborate renderer.

## 5. Evidence ledger, retrieval caveats and reproducibility

### Captures and source excerpts

All paths below are relative to `research/sources/`. `.html` retains responses; sibling `.txt` is a simple local HTML-to-text extraction where present, not an authoritative rewording. GitHub sources were retrieved with **gh CLI**, not a search API. Files named as `.html` for REST metadata can contain JSON; format is in the response. Many sources use mutable `latest`/`main` URLs; retain captures/hashes and prefer the pinned source links above for solver contracts.

| Evidence | Primary source(s) | Retained capture / decisive excerpt |
|---|---|---|
| fSpy purpose/license | https://github.com/perarnia/fSpy ; https://fspy.io/ | `geometry-fspy-readme.txt`: “open source, cross platform ... still image camera matching”; `geometry-fspy-license.txt`. |
| fSpy scale/coordinates | https://github.com/perarnia/fSpy/blob/develop/src/gui/solver/solver.ts | `geometry-fspy-solver.txt`, translation/scale and VP warning excerpts cited above. |
| Official importer | https://github.com/perarnia/fSpy-Blender | `geometry-fspy-importer.txt`, `geometry-fspy-addon.txt`, `geometry-fspy-importer-license.txt`, `geometry-fspy-blender-readme.txt`. |
| OpenCV contracts | https://github.com/opencv/opencv/blob/4.x/modules/calib3d/doc/solvePnP.markdown ; https://github.com/opencv/opencv/blob/4.x/modules/calib3d/include/opencv2/calib3d.hpp | `geometry-opencv-pnp-4x.txt`, `geometry-opencv-calib-4x.txt`, `geometry-opencv-license.txt`. |
| COLMAP geographic frame/API | https://colmap.github.io/faq.html ; https://colmap.github.io/format.html ; https://colmap.github.io/pycolmap/pycolmap.html ; https://github.com/colmap/colmap/tree/main/python | `geometry-colmap-faq.*`, `geometry-colmap-format.*`, `geometry-colmap-pycolmap.*`, `geometry-colmap-python-readme.txt`, `geometry-colmap-license-fixed.txt`. FAQ: “at least 3 images ... 3D similarity transformation”. |
| hloc success/fallback boundary | https://github.com/cvg/Hierarchical-Localization/blob/master/hloc/localize_sfm.py | `geometry-hloc-localize.txt`: actual `estimate_and_refine_absolute_pose` and `closest.cam_from_world()` fallback. |
| Matcher licenses | https://github.com/cvg/LightGlue ; https://github.com/cvg/LightGlue/blob/main/LICENSE | `geometry-lightglue-readme.txt`, `geometry-lightglue-license.txt`: matcher weights Apache-2.0; restrictive SuperPoint warning. |
| Blender projection verification | https://docs.blender.org/api/current/bpy_extras.object_utils.html ; https://docs.blender.org/api/current/bpy.types.Camera.html | `geometry-blender-world-camera.*`, `geometry-blender-api-camera.*`: bottom-left NDC/depth/shift/lens contract. |
| ODM | https://docs.opendronemap.org/gcp/ ; https://docs.opendronemap.org/geo/ ; https://docs.opendronemap.org/flying/ ; https://github.com/OpenDroneMap/ODM | `geometry-odm-gcp.*`, `geometry-odm-georef.*`, `geometry-odm-datasets.*`, `geometry-odm-readme.txt`. |
| Ireland coverage/height | https://data.gov.ie/dataset/open-topographic-lidar-data | `geometry-ireland-lidar.*`: “referenced to the Malin Head Vertical Datum”; numeric products, provider resolutions and attribution. |
| Ireland actual metadata | https://gsi.geodata.gov.ie/server/rest/services/Lidar?f=pjson ; layer/image URLs in §3 | `geometry-ireland-service.html`, `geometry-ireland-coverage-metadata.json`, `geometry-ireland-layer12.json`, `geometry-ireland-tile-example.json`, `geometry-ireland-image-metadata.json`: hillshade U8 warning and real tile metadata. |
| England/Wales/Scotland | EA/DataMapWales/Scottish portal URLs in §3 | `geometry-uk-lidar.*`, `geometry-uk-wales.*`, `geometry-uk-scotland.*`. England catalogue: “1m spatial resolution for all of England”; Wales page: DTM/DSM download catalogue/OGL; Scotland only portal shell. |
| US | https://www.usgs.gov/3d-elevation-program/about-3dep-products-services | `geometry-us-lidar.*`: “free of charge and without use restrictions”; project LiDAR + several DEM resolutions + Alaska IfSAR distinction. |
| Copernicus DSM | Copernicus DEM URL in §3 | `geometry-eu-dem.*`: DSM; EGM2008; public GLO license and eligibility restrictions. |
| GHSL aggregation | https://human-settlement.emergency.copernicus.eu/data/ghs_buH2023.json | `geometry-ghsl-height.json`: “100m, 3ss”, “Average ... Gross” versus “Average ... Net”; `geometry-ghsl-page-script.js` proves dynamic metadata source. |
| Detailed Dutch buildings | https://docs.3dbag.nl/en/ | `geometry-nl-3d-docs.*`: BAG+AHN, LoD1.2/1.3/2.2, quality caveats/open data; `geometry-nl-copyright.html` from https://docs.3dbag.nl/en/copyright/ explicitly covers downloadable/web-service data under CC BY 4.0. |
| Datum conversion | OS/NOAA/PROJ URLs in §3 | `geometry-uk-osnet.*`, `geometry-noaa-height.*`, `geometry-noaa-geoid18.html`, `geometry-proj-vertical.*`. OS explicitly separates OSTN15 and OSGM15. |

Retrieved GitHub branch heads (for identifying capture context): fSpy develop `702189ec5acbbd2c8ba492db0e52ecb5fc908f5c`; importer master `eec40b085d45cc623fd379998d85b88de679d4b8`; OpenCV 4.x `5584875dbac61650e966ec77946a38e386b7b3e5`; COLMAP main `98f31541f483788ab550f5c4a4e0804e8674b9e0`; hloc master `c13273bd0ecc2917a35910fd843712a1c6243193`; LightGlue main `5a650c444718caffc2669dc0094cde908f42dd73`. Captures were obtained near these head checks; this is not a claim that mutable docs sites are built from those exact commits.

### Explicit failures and unresolved checks

- Rendered OpenCV docs returned HTTP 403; official GitHub `4.x` source succeeded. Unqualified default-branch paths returned 404; corrected to 4.x instead of silently changing the API being discussed.
- Initial guessed GSI descriptive page, nidirect LiDAR page, Tailte geodesy page, USGS point-cloud page, one NOAA geoid-definition path and guessed 3DBAG terms/source paths returned 404. They are **not supporting citations**. GSI catalogue/REST, USGS product page, OS transforms, NOAA datum/GEOID18 and actual 3DBAG docs supplied working alternatives.
- One Dublin geo.data.gov.ie API guess failed DNS; an old NYU catalogue link redirected to a generic repository/about page. No claim of obtaining a Dublin point cloud rests on either. GSI's actual service listing verifies a Dublin coverage route, not raw-cloud download contents.
- Some USGS FAQ/specification pages returned 403; the public 3DEP products page succeeded. Individual project metadata/downloads were not exercised.
- Scottish portal and 3DBAG viewer are JS applications; viewer HTTP 200 is not a successful dataset query. 3DBAG documentation provided substantive model evidence; Scottish detailed catalogue remains unresolved.
- A GSI layer-0 request returned no fields; service discovery revealed layer **12**, which returned the actual metadata/sample record. Do not hard-code assumed layer numbering.
- Neither Blender reprojection, OpenCV/PyCOLMAP runtime APIs, hloc, ODM nor a real LiDAR raster sample was executed. This report distinguishes documented recipes from verified endpoint/source retrieval. No accuracy/performance benchmark is claimed.

### What can be done now, without installs or uploads

Use already existing `pose.py` and `geo.py` once real controls are available; retain datum/crop/identity evidence; run existing leave-one-out and candidate checks; project genuinely held-out points. Query official coverage metadata before any large data acquisition. Implement only the proposed preflight when approved. Escalate to Blender, multi-view reconstruction or learned localization **only when their required inputs exist**, rather than using them to conceal missing calibration or geography.

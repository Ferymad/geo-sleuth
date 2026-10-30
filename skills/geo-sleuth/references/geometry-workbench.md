# Geometry workbench: from recognized place to measured camera

A place match is not a camera-position or camera-height measurement. This guide
routes single-image calibration, georeferenced pose and reconstruction. The optional
`fspy.py` tool reads saved evidence; it does not solve calibration or register GPS.

## Decision gates

| Available input | Use | What is still missing |
|---|---|---|
| One image, genuine straight parallel/orthogonal line families | fSpy perspective calibration | Metric scale, geographic origin/axes, reliable ground surface and independent checks |
| One image, known 3D landmarks and camera intrinsics | OpenCV PnP or existing `pose.py` with appropriate assumptions | Point uncertainty, degeneracy/alternative solutions, geographic/datum alignment |
| One image, known landmarks but unknown intrinsics | Existing joint `pose.py` fit or constrained calibration then pose | Enough distributed controls; bounds and sensitivity checks; lens distortion/principal-point limitations |
| Overlapping independent images with useful parallax | COLMAP/current pycolmap, optionally hloc retrieval/matching | Metric scale, geographic registration, dated stable geometry |
| LiDAR/photogrammetric point cloud or survey | QGIS/PDAL/CloudCompare, then scene/control extraction | Correct CRS/vertical datum, ground classification, density/age and feature correspondences |
| Calibrated, scaled, anchored scene and camera | Blender overlay or independent reprojection | Withheld validation features and uncertainty; a good-looking render is insufficient |

No known length means scale can remain arbitrary. No geographic control means a
metric local scene can still float anywhere on Earth. Knowing a town does not
supply the height of every facade point.

## 1. fSpy: perspective evidence, not GPS

Use the [official tutorial](https://fspy.io/tutorial/) and
[official application/source](https://github.com/perarnia/fSpy). Align genuinely
straight line families, not curved curbs, perspective-dependent roof ornaments,
foliage, rolling-shutter distortions or assumed-right-angle paving. Record the
chosen origin/axes, line endpoints and alternate plausible fits. A reference
length must identify measured endpoints and its source/uncertainty; a “Meters”
unit label alone proves nothing. Local camera z is not automatically eye height.

Save the project and inspect its retained calibration without launching fSpy:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/fspy.py scene.fspy --out scene-inspection.json
```

This added standard-library reader checks the documented v1 container, preserves
raw camera parameters, hashes the full original, and reports stored reference
settings. It never extracts the embedded photo, assumes metric/geographic
registration, or converts undocumented transform/FOV conventions into `pose.py`.
Use a new output path; existing files are refused. Null calibration means no
saved solved camera, not a zero-valued camera. Treat output as potentially private.

The official example was parsed successfully during development. That establishes
file interoperability, not calibration correctness or fSpy/Blender compatibility.
To open the scene in Blender use the original `.fspy` file with the
[official importer](https://github.com/perarnia/fSpy-Blender), not inspector JSON.
Neither app nor importer is installed by this skill. Their GPL terms are separate
from this independent MIT format reader.

## 2. Controls: the missing ingredient a solver cannot invent

For each image/map correspondence record:

- literal feature identity and stable corner/base/top definition;
- pixel coordinate, original resolution, upright/stored frame, crop/resize transform;
- horizontal coordinates and CRS, height and vertical datum;
- source/date, horizontal/vertical uncertainty, and whether measured or inferred;
- whether used for fitting or held out for validation.

Spread controls across the image, azimuth, depth and height. Four near-collinear
points or four far-away corners on one facade do not become strong geometry merely
because a solver accepts them. Use the pavement/ground directly below the camera
when evaluating height above ground, not a distant ground elevation. A building
height tag or a vehicle catalogue dimension is not a survey; check the actual
variant and exactly corresponding endpoints.

Keep `h = H + N` conventions explicit when converting ellipsoidal height, orthometric
height and geoid undulation; verify the relevant datum/sign and transformation
model rather than inserting a generic offset. Do not mix a DSM roof/tree surface
with a DTM bare-ground surface. Missing vertical grids cannot be silently ignored.

## 3. Existing geographic pose route

Read `pose.py --help` and its spec before fitting. Existing specs use `image_size`,
`frame`, points with `px`, latitude/longitude `ll`, and `h`, plus `init`/`fix`.
The current solver jointly fits a centered pinhole model; principal-point offsets,
lens distortion, panoramic projections and aggressive cropping can violate it.
Do not treat all images as a calibrated rectilinear main-camera shot.

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/pose_preflight.py surveyed-spec.json --out preflight-new.json
uv run ${CLAUDE_SKILL_DIR}/scripts/pose.py solve surveyed-spec.json --photo photo.jpg --out pose-check.png
uv run ${CLAUDE_SKILL_DIR}/scripts/pose.py project --pose pose.json --points independent-check-points.json --photo photo.jpg --out independent-check.png
```

These are interface templates, not claims that a real survey was solved here.
The added opt-in preflight reports malformed inputs, actual free-parameter/dof
counts, duplicate/planar/collinear or narrow controls, missing height provenance,
image-frame assumptions and heuristic geometry warnings. It leaves `pose.py`
unchanged and performs no fitting, calibration or datum conversion. Passing
preflight does not certify a unique pose or a geographic radius; inspect its
warnings and acquire the missing evidence before fitting.
Inspect residuals, leave-one-out results, alternative initializations, focal bounds,
control perturbations and horizon/pitch. A tiny pixel-only covariance is conditional
on the model and controls; it does not cover wrong landmark identities, datum
errors or scene changes. Retain unresolved ambiguities and lower precision.

## 4. OpenCV: mind which pose and which algorithm

[Official PnP documentation](https://github.com/opencv/opencv/blob/4.x/modules/calib3d/doc/solvePnP.markdown)
says `rvec`/`tvec` transform **world/object coordinates into the camera frame**;
translation is not the camera's world position. In the usual convention, camera
center is `-R.T @ t`, with axes and units still requiring explicit mapping.
Camera intrinsics and distortion coefficients are inputs, not optional facts that
may be guessed silently. If calibration is unknown, select a validated estimation
route and report its uncertainty.

Do not mechanically recommend a particular flag for every point set. Official docs
state iterative initialization uses at least six nonplanar or four planar points;
P3P/AP3P, IPPE and SQPnP have different point/planarity/solution requirements.
Multiple plausible poses must be tested. Notably, the inspected OpenCV docs mark
`SOLVEPNP_DLS` and `SOLVEPNP_UPNP` as broken implementations that fall back to EPnP:
calling UPNP is not proof that unknown focal length was estimated.

## 5. Multiple views and geographic registration

Use the current [COLMAP documentation](https://colmap.github.io/) and
[FAQ](https://colmap.github.io/faq.html), or current pycolmap from the COLMAP
project—not the deprecated standalone `colmap/pycolmap` repository. Keep image
intrinsics shared only when justified. Panorama crops/rotations from one center
cannot triangulate metric scene depth. Repetitive facades, moving cars, foliage,
low texture and weak baseline can undermine reconstruction.

A reconstructed model needs enough nondegenerate metric/geographic controls to
establish scale/orientation/origin. GPS priors have uncertainty; a nominal
georegistration is not surveyed centimeter truth. Register the query against a
reference model/gallery, then validate withheld stable features. hloc/LightGlue
can help retrieval/correspondence generation but cannot supply missing georeference
or clear feature/model/data licensing by themselves. Inspect hloc localization
logs, not only its pose file: the inspected non-clustered implementation can emit
the nearest reference camera's pose when query PnP fails. Label that branch
retrieval-only, never a solved query camera.

## 6. Blender and measurement checks

Use [documented camera settings](https://docs.blender.org/manual/en/latest/render/cameras.html):
projection, focal/sensor fit, principal point/shift, pixel aspect and image size
must match. Do not select a cinematic lens, alter object geometry or move the
camera solely to make the picture look convincing. Keep the local-to-geographic
transform explicit. Distinguish validation points from fit points and show
residual overlays on both sides of the frame, near and far.

Output camera coordinates/height only at the supported uncertainty. When the
metric reference or ground surface is missing, state exactly that. A request for
one extra measured length, control-point photo or site scan can be more useful
than another reverse-image engine or generative depth model.

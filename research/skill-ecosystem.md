# Independent skills and GIS workbench: what is actually useful

## Discovery performed

Used the skills.sh leaderboard and `npx --yes skills find photogrammetry`,
`geospatial` and `blender`. These are discovery operations, not installations.
GitHub metadata, repository trees and actual skill text were then retrieved with
`gh repo view` and `gh api`. Source snapshots are retained locally under
`research/sources/`. Counts below are a search-time snapshot, not quality scores.
No third-party skill was installed or granted tool access.

## Findings

### GIS raster/vector handling: useful adjunct, not a new location oracle

Source: [isaaccorley/geospatial-skills](https://github.com/isaaccorley/geospatial-skills).
The search reported 97 installs for `gdal`; repository metadata reported 80 stars,
Apache-2.0. Read `skills/gdal/SKILL.md` (blob
`e9529bfc91409d1a34fca1410018a0979409c17c`) and `skills/search-stac/SKILL.md`
(`06b699c122e1b124190427f729ad173710975b00`).

Useful duties: inspect raster CRS/nodata/resolution, clip/mosaic elevation or
historical imagery, reproject candidate inventories, read STAC collection metadata.
These become valuable when a photo narrows to a region but built-in OSM or current
imagery is incomplete. They should be loaded for that operation, not every case.

Cautions after reading the actual files:

- The GDAL guide contains shell filtering and a `/tmp/quad.vrt` example; adapt
  these to the host's file tools and configured scratch policy.
- The STAC guide assumes `geoai`; its search `limit`/first-20 listing must not be
  mistaken for complete catalog coverage. Record pagination/limits and collection
  footprint; don't down-weight locations merely because a limited query missed them.
- Small adoption is reason for extra source/API testing, not automatic rejection.
- A direct `pystac-client`/`planetary-computer` or rasterio/pyproj operation may be
  lighter than importing a broad geospatial-AI toolkit for a simple catalog query.

Recommendation: optional GIS companion guide, not unconditional package install.
Choose GDAL/rasterio for rasters, GeoPandas/Shapely for vector joins and buffers,
pyproj/PROJ for documented datum transformations, laspy/PDAL for point clouds,
QGIS for interactive layer inspection. Verify CRS/vertical datum, operation grids,
axis order, units, nodata and pixel size before using metric results. Installation
and source-data rights are separate prerequisites.

### Official Mapbox skills: credible author, mostly the wrong subproblem

Source: [mapbox/mapbox-agent-skills](https://github.com/mapbox/mapbox-agent-skills),
MIT, 83 stars in the retrieved metadata. Search reported 2.2K installs for
`mapbox-geospatial-operations`. Read the actual file (blob
`54314a82333f60fdeab5fbbfa51e3e5d7cc01543`).

It correctly distinguishes offline geometric operations from road routing,
traffic and isochrones. Useful if the photo suggests a journey/route or if building
an interactive candidate map. Not a substitute for photo recognition, camera
calibration, metric scene geometry or independent confirmation. It names Mapbox
MCP tools, which are not automatically available merely by installing the skill.
API-backed features can require tokens and incur charges; offline geometry need
not. Do not introduce paid routing for a task that only needs a bearing or buffer.

Recommendation: targeted optional use, not a core dependency. Its popularity does
not establish photo-geolocation performance.

### Blender camera skills: inspect their objective before using them

Source: [RobLe3/cc-blender-skill](https://github.com/RobLe3/cc-blender-skill), MIT,
131 stars at retrieval. Search reported 1.2K installs for `blender-cameras`.
Read `plugin/skills/blender-cameras/SKILL.md` (blob
`eb3ab060c1267cb4e4e8bccd235bd25426d68e60`).

The actual skill is aimed at cinematic composition: hero shots, focal lengths for
feel, rule-of-thirds framing, depth of field and orbit cameras. Those objectives
are inappropriate for forensic camera matching. A solver must not select 85 mm
because it looks flattering or move the camera to improve composition. Treat
camera settings as measured/estimated parameters with residuals and uncertainty.

Useful portion: Blender automation/API mechanics and rendering an independently
calibrated scene. Keep the official fSpy importer and Blender camera documentation
as the authoritative interoperability route. Do not blindly load a stylistic
camera skill into a geolocation measurement session.

Recommendation: do not install this cinematic skill as a default geolocation
capability. A narrowly authored measurement/reprojection companion is safer.

### Photogrammetry skill search: no vetted automatic recommendation

The search surfaced `xjtulyc/awesome-rosetta-skills@photogrammetry-3d` with 11
installs and assorted 3D-printing/creative skills. Search rank and keywords alone
do not establish SfM, metric scale or geographic registration support. No source
review or execution was performed for that small-adoption photogrammetry skill;
it is not endorsed. Prefer COLMAP's current official documentation/bindings and
measured control points over installing an unreviewed wrapper.

### Already available in this agent environment

The loaded `maps` skill exposes geocoding/POIs/routes and can help translate a
confirmed place name into coordinates or search nearby facilities. It overlaps
geo-sleuth's existing OSM/POI tools; adding another wrapper over the same backend
does not supply independent coverage. Use the actual returned skill directory,
not a guessed flat `~/.hermes/skills/maps` path. Respect public Nominatim limits.

Browser/computer-use tools are useful for authorized Lens, historical imagery,
fSpy/QGIS/Blender GUIs and reviewing visual evidence when no suitable API exists.
They do not justify bypassing authentication, anti-bot challenges or site terms.

REA is appropriate if an integration depends on a shipped app's undocumented
file/runtime behavior. It is not needed to inspect a complete public source tree
or to make unsupported geography claims sound more authoritative.

## Wiring policy

1. Route by the missing observable: name, region, candidate inventory, historical
   appearance, horizon, camera calibration, metric geometry, or independent check.
2. Prefer an existing tested geo-sleuth command where it already covers the job.
3. Load one focused companion or direct library for the actual gap. Confirm the
   runtime, license, credentials, cost, privacy and source coverage first.
4. Require a retained artifact and a failure recovery path. Tool availability is
   not evidence of a successful operation, and tool count is not capability quality.
5. Benchmark the combined workflow on held-out photos under equal budgets before
   making a localization-accuracy claim. Do not install every discovered skill:
   conflicting objectives and instructions can make results worse.

# Specialist rescue sources

Use these when the normal photo → OCR/search → map → ground-view route stalls.
Pick a route for a concrete visible clue. These are documented optional workflows,
not installed services, promises of global coverage or completed localization tests.
Keep queries bounded, preserve dates/CRS/counts, and verify the actual response.

## A. Municipal asset constellations

A single generic lamp tells little; the ordered geometry of a pole, hydrant,
junction box and intersection can produce a distinctive candidate set.

- Read official dataset metadata and ownership first. Vancouver's
  [catalog API](https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets)
  exposes street-lighting poles/panels/junction boxes, signals, hydrants, manholes,
  trees, dated LiDAR and georectified historical maps. Check the actual dataset ID,
  fields, dates and Open Government Licence–Vancouver. Signal coordinates can be
  intersection centers, not the individual heads visible in the photograph.
- Municipal inventories omit private assets and can lag changes. Enumerate a
  bounded class, compare feature order/spacing and side of street, then confirm
  imagery. Species or an absent row alone must not exclude a site.
- Construction clues need chronology. NYC's [legacy permits](https://data.cityofnewyork.us/api/views/ipu4-2q9a.json)
  warn that most current permits are instead in [DOB NOW](https://data.cityofnewyork.us/api/views/rbx6-tga4.json).
  A permit issue is not proof work was completed. Avoid publishing personal
  applicant/contact fields; retain only relevant public site/work evidence.
- Portal shell recovery: catalog metadata → linked data API. For
  [ArcGIS layers](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/)
  inspect CRS, object-ID field, record cap, paging and `exceededTransferLimit`.
  Use count/ID queries and bounded ID batches where supported. For
  [Socrata](https://dev.socrata.com/docs/queries/) use deterministic pagination.
  A default page is not the whole inventory.

## B. Time-aware imagery, maps and captions

- [Esri Wayback core](https://github.com/vannizhang/wayback-core) documents local
  imagery-change and point metadata operations. Find releases with local changes,
  then inspect source acquisition metadata; a basemap release date is not the
  capture date. The same acquisition can survive many releases.
- Google Earth and Street View history are existing routes. Check available epochs
  before excluding a rebuilt facade, but do not infer a continuous timeline from
  a few captures. Browser access does not grant bulk reuse/caching rights.
- [USGS NAPP archive](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-aerial-photography-national-aerial-photography-program-napp)
  covers a US historical aerial collection; frame scans can need orthorectification.
  Existing digital scans and paid on-demand rescanning are different services.
- [Library of Congress API](https://www.loc.gov/apis/json-and-yaml/) can discover
  historical map/photo item records. Check each item's rights and downloadable
  resources, not merely the catalog title.
- [Wayback availability](https://archive.org/help/wayback_api.php) and
  [CDX](https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server)
  can recover an original caption/source page and its image asset. Retain both
  timestamps and asset identity. Earliest available crawl is not original
  publication, capture date or authorship.
- Commons `imageinfo`/`extmetadata` can expand a named/geotagged image pool into
  original-source leads. File upload time differs from shutter time; camera and
  subject coordinates differ. Wikidata data is CC0, Commons images have individual
  licenses. Retain author/source/license, page all batches and deduplicate IDs.

## C. Transport identifiers beat generic appearance

- [GTFS Schedule](https://gtfs.org/documentation/schedule/reference/): readable stop
  code/destination/route → operator feed → `stop_code` and route names → trip/stop
  joins → service calendars → plausible corridor/direction. `stop_id` is often
  internal, not the printed code. Times can exceed 24:00 under service-day rules.
  Feeds have operator-specific terms/auth and may omit shapes or history.
- [FRA crossing reports](https://safetydata.fra.dot.gov/OfficeofSafety/publicsite/crossing/crossing.aspx):
  a US crossing identifier can lead to inventory/geometry, then dated imagery.
  A decoded identifier still needs visual confirmation and current/historical scope.
- [FAA aeronautical data](https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/):
  airport/identifier/runway layout → cycle-dated official diagrams. Magnetic runway
  numbers are not exact true bearings on a map.
- [OpenSky](https://openskynetwork.github.io/opensky-api/rest.html): callsign,
  registration and ICAO24 are different identifiers. Authenticated access uses
  OAuth2; history/quotas/entitlements are limited. Missing reception does not mean
  a flight was absent. Do not recommend obsolete basic-auth recipes.
- [NOAA ENC GIS](https://nauticalcharts.noaa.gov/data/gis-data-and-services.html):
  US coastal aids, piers and harbor geometry can test a nautical scene. Check chart
  epoch and changed/temporary marks; GIS output is not a navigation-chart substitute.

## D. History and offline geography

A local extract can survive an Overpass outage and keep repeat searches private.
[Osmium time-filter](https://docs.osmcode.org/osmium/latest/osmium-time-filter.html)
needs an actual history `.osh.pbf` for past states; a current `.osm.pbf` cannot
recreate missing versions. Record snapshot time and ODbL attribution obligations.
Overpass history support depends on the selected instance. OSM edit dates are
mapper edits, not physical construction/demolition dates.

[ohsome v2](https://docs.ohsome.org/ohsome-api/v2/) currently documents free-key
signup; do not reuse old no-key v1 recipes. OpenRailwayMap and OpenInfraMap are
useful interfaces to OSM, not independent corroboration of the same OSM facts.

## E. Actual elevation, not a shaded picture

For Ireland, use [GSI catalog/coverage metadata](https://data.gov.ie/dataset/open-topographic-lidar-data)
to locate a numeric DTM/DSM tile. The inspected
[Phase2 coverage service](https://gsi.geodata.gov.ie/server/rest/services/Lidar/IE_GSI_LiDAR_Coverage_GSI_Phase2_IE26_ITM/FeatureServer?f=pjson)
uses layer **12**, with download/date/license/resolution/error fields. Discover
layers rather than assuming layer 0. Its named DTM hillshade ImageServer returns
U8 shades from 0–255, **not elevations in metres**. A source called LiDAR or
ImageServer is insufficient. Check Malin Head datum, tile date and numeric raster.

Other optional sources include England's EA LiDAR, DataMapWales, USGS 3DEP and
Dutch [3DBAG](https://docs.3dbag.nl/en/). They have different jurisdictions, epochs,
models and licenses. GHSL aggregated building-height cells are not an individual
roof height. Copernicus DEM is a surface model with its own vertical reference.
Use [geometry workbench](geometry-workbench.md) before populating pose controls.

## F. Conditional physical cross-checks

- [NCEI observed weather](https://www.ncei.noaa.gov/cdo-web/webservices/v2) requires
  a token; [ERA5](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels?tab=overview)
  is reanalysis, not street-level observation. Check station/grid distance, missing
  data, observation interval and UTC/local clock. Usually down-weight, not exclude.
- [Skyfield](https://github.com/skyfielders/python-skyfield),
  [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html) or Stellarium can
  test Moon/planet/star direction after narrowing time/region. Clarify apparent vs
  geometric coordinates, refraction and local horizon. Sky alone rarely fixes GPS.
- [Astrometry.net](https://github.com/dstndstn/astrometry.net) can locally solve a
  real star field with appropriate indexes. Celestial pointing is not terrestrial
  position. Hosted solving uploads data and has separate account/privacy terms.
- [NOAA tides](https://api.tidesandcurrents.noaa.gov/api/prod/) can test a causeway
  or harbor waterline at a justified station/time/datum. Predictions differ from
  storm/wind effects; the nearest station may have another tidal regime.

## Do not turn preprocessing into fabricated evidence

ExifTool can expose additional read-only metadata. Tesseract or an explicitly
configured PaddleOCR model can provide a second local reading. Preserve original
scripts, boxes and competing readings. Real-ESRGAN/sharpening may suggest a lead,
but generated strokes/texture are not recovered letters or measured geometry.
C2PA assertions, if valid under a trust policy, concern provenance—not automatic
truth of a geographic claim. Reposts and several engines indexing one caption
remain one source, not independent confirmation.

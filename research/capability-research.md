# Capability research: evidence-backed photo geolocation and resilient investigation

**Research date:** 2026-10-30 UTC. **Local baseline:** `bb5c2400af8cd6f05849d0c5f3346980c0b16d15`. **Scope:** research only; no application code changes, image uploads, paid API calls, model downloads, or model inference. GitHub discovery and inspection used `gh search repos`, `gh repo view`, and `gh api` for README/contents/tree/commit metadata. Other sources were fetched directly with certificate verification or read in a real browser. Web-search/extract quota was unavailable; no secondary search summaries were substituted.

## 1. Decision summary

The strongest likely improvements are **better reference coverage and explicit failure accounting**, followed by controlled retrieval experiments—not a new model that emits more precise-looking coordinates.

1. **P0: make capability, coverage, provenance and upload permission explicit.** The current intake can upload photos through reverse search. Network errors and empty coverage must remain distinct from negative location evidence. Keep the existing board/geometry verification discipline.
2. **P1: add a public KartaView metadata/reference adapter, conditionally add Mapillary with a user-provided client token, and use Commons for named/nearby anchors.** These can supply actual ground-level comparison evidence, unlike a country classifier. KartaView public metadata worked in this session, but its documented hostname and its own MCP client's parameters have operational drift.
3. **P1: add bounded, release-pinned Overture extraction as a complement to OSM.** It can improve building/POI enumeration and offline resilience. It is not proof of completeness, and partly overlaps OSM rather than being independent corroboration.
4. **P1: benchmark multilingual OCR configuration and a place-retrieval pipeline against the existing local baselines.** AnyLoc-style patch aggregation is a materially different experiment from the existing DINOv2 CLS/mean descriptor. LightGlue with an appropriately licensed extractor is an optional reranker, not a location oracle.
5. **P2: add date-aware STAC/COG regional screening.** Planetary Computer Sentinel-2 metadata access worked without credentials. Ten-metre RGB imagery helps coastline, land cover, snow, water and large-facility screening; it does **not** replace sub-metre imagery or prove an individual building/camera position.
6. **P2: trial GeoCLIP for a broad, diverse regional shortlist only.** StreetCLIP is a noncommercial, distribution-biased comparator, not the default production component. Neither justifies street/building precision without independent evidence.
7. **Do not build around unofficial reverse-search endpoints, retired Bing Search APIs, Google billing-enabled APIs under a no-paid policy, or unrestricted scraping/caching of commercial imagery.** Browser UI availability is not a supported automation API or reuse license.

These priorities are engineering recommendations, not measured improvements. Acceptance tests are specified in §9; none of those model/agent benchmarks was run here.

## 2. What is already present: inspected before selecting additions

Paths below are relative to `skills/geo-sleuth/`. Existing documentation was checked against representative implementation files, not treated as execution evidence.

| Existing capability | Verified local evidence | Consequence for integration |
|---|---|---|
| Metadata, crops, OCR and reverse search intake | `scripts/intake.py`; `scripts/ocr.py`; `scripts/revimg.py`; `references/data-sources.md` | Improve routing and privacy controls, rather than rebuilding intake. `revimg.py` calls `set_input_files` for Baidu and Yandex: these routes send image content off-device. They were **not run** here. |
| Local OCR | `ocr.py:36–104`: Apple Vision accurate recognition, language correction disabled, RapidOCR fallback. `RapidOCRBackend.__init__` receives `langs` but constructs bare `RapidOCR()` without configuring language-specific models. | A CLI language list does not establish actual multilingual fallback support. Test backend/model identity and script coverage explicitly. Preserve literal names and crop provenance. |
| Candidate ranking and exclusions | `scripts/board.py`; `SKILL.md` rules for evidence-backed exclusions, candidate coverage and independent constraints | Retain candidate board semantics. Model similarity belongs to a hypothesis/ranking channel; do not make it a computed geometric exclusion. Board likelihood-ratio scoring is not automatically calibrated posterior probability. |
| Reference-image retrieval | `match.py:57–136`: `facebook/dinov2-small` CLS concatenated with patch mean, or `openai/clip-vit-base-patch32`; normalized cosine scoring. `139–181`: SIFT ratio test and RANSAC homography. `214–230`: rendering exceptions become `None`. | Already has DINOv2 and local geometry. The useful experiment is aggregation/domain retrieval plus better error visibility, not merely “add DINOv2.” Missing renders need source-specific error records. |
| Satellite semantic ranking | `scripts/sat_scan.py`; `scripts/tiles.py`; `references/data-sources.md` | Existing CLIP ranks candidate overhead cells. Ground-to-overhead retrieval is a different task; do not infer it works because both inputs can be embedded. Tile rights/date/source should travel with every crop. |
| Structured geographic search | `osm.py:115–160`: cached Overpass requests, mirror rounds, warning on partial `remark` replies; `cmd_coverage` around line 524; Nominatim-backed gazetteer/POI tools | Keep existing protections. Add bounded extract/offline alternatives and machine-readable partial-result status. OSM count comparisons measure mapped features, not real-world completeness. |
| Street view | `scripts/gsv.py`, `scripts/baidu_pano.py`; `references/data-sources.md:57–79` | Google/Baidu paths include undocumented service surfaces. Their ability to answer without a key is not a stability, authorization, or redistribution guarantee. New public-data adapters reduce single-source dependency. |
| Terrain, sun and camera geometry | `scripts/terrain.py`, `scripts/sun.py`, `scripts/geo.py`, `scripts/pose.py` | These remain the route from a plausible region to a checked position. Better retrieval does not remove datum, elevation, FOV, mirrored-image or time ambiguities. |
| Diagnostics and HTTP | `_net.py:21–29` wraps curl but collapses failures to a generic exception; `doctor.py:55–95` distinguishes endpoint reachability from one semantic panorama lookup | Extend semantic probes and typed errors. `doctor.py` expressly says reachability is not proof of coverage or working inference. Avoid misreading a successful HTML shell as valid documentation/data. |

**Not established by this inspection:** end-to-end runtime health of the local scripts, inference performance, current Google/Baidu endpoint availability, or actual regional completeness. Existing anecdotal test statements in `SKILL.md` are not a controlled benchmark.

## 3. Ground-level reference sources: material evidence gains

### 3.1 Mapillary: useful official API, credential-gated; coverage-first integration

**Primary sources:** [API v4 documentation](https://www.mapillary.com/developer/api-documentation/), [official Python SDK](https://github.com/mapillary/mapillary-python-sdk), [current terms](https://www.mapillary.com/terms), [homepage](https://www.mapillary.com/).

**Source excerpts / verified facts:**

- API documentation: “All requests against https://graph.mapillary.com and https://tiles.mapillary.com must be authorized.” It accepts **client or user access tokens**; ordinary public-data reading need not imply implementing user OAuth for every operation. Client-token setup is through the developer dashboard.
- Documentation: entity endpoints provide only limited bbox filtering; larger spatial queries should use vector tiles. Current `/images` docs specify bbox area **smaller than 0.01 degrees square**, `limit` default/max **2000**, and cursor paging. This is an angular-area constraint, not a fixed square-kilometre allowance. Never stop at one capped page and call it complete.
- Explicit image fields include `geometry`, `computed_geometry`, original and computed compass angle, `captured_at` in milliseconds, `camera_type`, `is_pano`, `sequence`, `thumb_1024_url`, `thumb_2048_url`, quality and creator metadata. Original and computed positions are different estimates, not surveyed truth.
- Coverage tiles describe original rather than computed geometries. This matters when comparing their coverage map with returned image positions.
- Terms §3: user content is subject to “Creative Commons Share Alike (CC BY-SA) license,” **unless otherwise indicated**; terms explicitly contemplate separately licensed datasets including noncommercial ones. Terms prohibit re-identification/unblurring and stalking conduct. Do not generalize one image license to every dataset or service output.

**Session test:** a tiny unauthenticated `/images` request returned HTTP **500**, JSON error code **190**, “Invalid OAuth 2.0 Access Token.” This is an authentication result despite its server-error HTTP status, not an empty search and not proof the authenticated API is down. No token was requested, account created, or image retrieved. See `sources/mapillary-auth-probe.raw` and `sources/retrieval-notes.json`.

**Integration design:** optional source behind explicit `MAPILLARY` credential configuration; query bounded candidate polygons, inspect coverage first, page/deduplicate image IDs, retain original/computed coordinates and capture dates, shortlist by heading/quality/season, fetch permitted thumbnails, then feed local matching. Perspective frames must not be treated as freely rotatable panoramas; handle only documented projection types correctly. Store source image URL/ID, photographer attribution, applicable license and acquisition date with each evidence panel. Refresh expired asset URLs through metadata, not by replaying old signed URLs forever.

**Cost/auth/privacy:** no paid call was made. This research did not establish a contractual unlimited free quota or a universal rate limit; validate account/API terms before enabling and set a zero-spend policy. Token required; do not harvest one from a public web app. Bbox/date requests expose the investigation area, although local query-image matching need not upload the target photo. Strip tokens from logs. SDK MIT licensing does not license imagery or waive platform terms.

**Priority / feasibility:** **P1, medium effort, token-gated.** More valuable than coarse model changes wherever it adds relevant reference views. Measure coverage by candidate area and imagery date; do not assert “rural coverage” or “no China coverage” from a global reputation or a single probe.

### 3.2 KartaView: public reading worked, but documentation/client drift is real

**Primary sources:** [rendered documentation](https://kartaview.org/doc), [terms](https://kartaview.org/terms), [official-organization MCP repository](https://github.com/kartaview/mcp-karta-view), especially [client source](https://github.com/kartaview/mcp-karta-view/blob/37ac5c062c9ace66bcc540086236127a3fb86bf0/src/mcp_karta_view/karta_view_client.py).

**Source excerpts / verified facts:**

- Documentation says public imagery, coverage, basic metadata and geographic imagery queries “do not require authentication”; user/private/upload operations do.
- Terms §2: “The use by you of the KartaView is free of charge.” Terms §4 license street images and spatial 3D data under **CC BY-SA 4.0**, and require credit **“© Grab and KartaView Contributors”**. Software licensing is separately MIT, unless otherwise stated. Broad platform/IP restrictions still require reading the full agreement; use the explicit data grant, not a blanket assumption about all site assets.
- The MCP client distinguishes `getNearbyPhotos` from `objectSearch`: semantic object search explicitly requires a KartaView token and uses another gateway. Public nearby imagery does **not** prove public/free semantic-search access.

**Session test and recovery:**

1. The documentation's `https://api.openstreetcam.org/2.0/photo/` hostname failed TLS hostname verification in this environment. Verification was **not disabled**.
2. The equivalent `https://api.kartaview.org/2.0/photo/?lat=-6.1939&lng=106.8494&zoomLevel=15&limit=2` responded HTTP 500 with `PhotoQueryOptions doesn't allow: limit`. The organization's own MCP client sends a `limit` argument: do not blindly install/wrap it as proof of a working adapter.
3. Removing the unsupported argument yielded **HTTP 200**, API status **600**, and **70 returned photo metadata rows** at the public Jakarta example location, without a token. The response also includes `hasMoreData`; these rows are not a census. No referenced images were downloaded. [Exact successful read](https://api.kartaview.org/2.0/photo/?lat=-6.1939&lng=106.8494&zoomLevel=15). Full metadata: `sources/kv-working-query.raw`.

Returned fields included photo/sequence IDs, `lat`/`lng`, matched coordinates, GPS accuracy, `shotDate`, heading/projection information, blur-processing state and processed/thumbnail image URLs. A returned heading of `0` and unknown field of view are not reliable evidence of a north-facing calibrated camera. Prefer processed/blurred assets and preserve uncertainty; do not fetch raw originals to recover blurred personal information.

**Integration design:** a small read-only adapter is safer than adopting the MCP package wholesale. Implement only verified public operations first. Normalize photo IDs, WGS84 coordinates, capture time and explicit timezone uncertainty, sequence grouping, projection, processed image URLs and license. Discover valid pagination/selection parameters from current documentation and tests; do not guess their semantics. Add a semantic canary with a known covered point, schema validation, bounded requests and a clear empty/failed/partial distinction. Test actual processed-image retrieval separately before declaring a complete reference pipeline.

**Cost/auth/privacy:** public imagery metadata and platform use are documented free; no auth was needed for this particular read. No fixed quota/SLA was verified. Coordinates go to the provider; no target-photo upload is needed. CC BY-SA attribution and adaptation obligations matter for published comparison panels. The MCP repo's `gh repo view` license field was null and its inspected tree had no license file: the site's software statement is not a substitute for reviewing a particular distributed dependency's licensing.

**Priority / feasibility:** **P1, medium effort.** The public data path is feasible, but production readiness is **not** established. Repairable schema/hostname drift is an excellent resilience test fixture.

### 3.3 Wikimedia Commons: cheap anchor corroboration, not a street-view substitute

**Primary source:** [GeoData API documentation](https://www.mediawiki.org/wiki/Extension:GeoData#API); [Commons API](https://commons.wikimedia.org/w/api.php).

A bounded namespace-6 `geosearch` request around a Berlin sample point returned HTTP 200 and two geotagged file records without a key (`sources/commons-probe.raw`). This confirms discovery works, **not** that those images are useful or correctly geotagged. Geotags may refer to subjects or camera positions with varying quality. Retrieve file-page `imageinfo`/`extmetadata`, inspect the actual image, author, license, source and date before citing or publishing it; Commons is not one uniform license. Coordinate search alone misses untagged landmark images: a known name/category is another useful route.

**Cost/auth/privacy:** public read access, no paid route used, no target-image upload. API request metadata exposes the candidate area/name. Attribute per file; do not assume every returned photo is CC BY-SA or location-accurate.

**Priority / feasibility:** **P1, small effort** as a supplementary anchor-photo source, especially when street-view providers have no useful view. Never make “no Commons photo” an exclusion.

## 4. OSM and Overture: broader candidate generation without completeness claims

### 4.1 OSM public-service constraints are architectural, not incidental

**Primary sources:** [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/), [Overpass commons/quotas](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html), [OSM copyright/ODbL](https://www.openstreetmap.org/copyright).

- Nominatim: “absolute maximum of **1 request per second**”; identifying User-Agent/Referer, attribution and caching required. Limits apply across the application, not separately to each concurrent agent. Its policy prohibits systematic grid reverse queries and downloading all POIs through search; use extracts instead. Public Nominatim also says not to submit personal/confidential material. The current policy has explicit restrictions for generic no-code/LLM-generated integrations: the developer must make a deliberate informed choice and comply. A generic “agent can geocode anything” backend is not an acceptable default. **This policy must accompany any recommendation to use the public endpoint.**
- Overpass gives a **broad guideline**, not an entitlement: about 10,000 requests and below about 1 GB/day. It documents cooldown slots, HTTP 429 load shedding, and 504 resource rejection; huge repeated/world-stitching requests are inappropriate. Shrinking scope or using an extract is the right fallback, not rotating IPs or hammering mirrors.
- ODbL governs OSM databases and applicable derived-database uses; attribution is required. A rendered evidence image and a redistributed merged spatial database need different legal analysis.

**Recommendation:** keep Overpass for bounded feature/co-occurrence tests; use release-dated regional extracts for repeat or large-area enumeration. Keep human-triggered geocoding sparse, cached, single-scheduler and replaceable, or use a deliberately operated local service. Never feed precise private addresses to a public endpoint as an invisible fallback.

**Coverage protocol:** record requested extent, admin-resolution success, query/tag set, server, OSM data timestamp, element count, returned `remark`, partial/full/unknown status and any cap. Compare coverage density across nearby controls and against independent imagery/reference sources. Zero mapped buildings means **unknown completeness**, not zero buildings. An OSM road centerline cannot establish river width, facade appearance or capture date.

### 4.2 Overture: bounded GeoParquet complements sparse tags, not independent truth

**Primary sources:** [official data repository](https://github.com/OvertureMaps/data), [DuckDB access guide](https://docs.overturemaps.org/getting-data/duckdb/), [theme attribution/licensing](https://docs.overturemaps.org/attribution/).

**Source excerpts / verified facts:**

- Repository: “Open map data in cloud-native Parquet, free to use under open licenses.” The official guide uses `read_parquet` against public release paths and DuckDB `spatial` plus `httpfs`/`azure` extensions.
- The live guide's example points at release **`2026-10-21.0`**. Treat that as the observed documentation example, not a promise that it is forever latest; persist the actual selected release and schema.
- The attribution page requires theme/source-specific handling. Buildings, base, divisions and transportation include ODbL themes; places include **CDLA Permissive 2.0**, Apache-2.0/Foursquare notice requirements, and CC0 sources. Addresses have jurisdiction-specific terms. The GitHub repository's **MIT** license does not make all geographic data MIT.

**Material use:** enumerate plausible buildings/places/transport structures in an already justified search area, including where OSM tag density is poor. Preserve IDs, geometry, names, categories, source provenance and confidence fields **where actually available in the selected schema**, not as assumed universal fields. Overture does not provide building facade photographs and a footprint is not necessarily the visible roof shape or height.

**Query design:** pin release; apply partition/theme/type and bbox predicates for Parquet pruning, then an exact geometric test where needed. For polygons, use bbox **overlap**, not merely “minimum point inside window,” or boundary-crossing buildings/roads can disappear. Cache the bounded extract with byte/row counts and query. Record contributors and correlated origins: an Overture feature sourced from OSM cannot serve as independent corroboration of the same OSM feature.

**Cost/auth/privacy:** docs show public-cloud read paths; no cloud account, paid query engine, bulk download or DuckDB install was used here. Local DuckDB avoids a paid SQL service, but scanning broad partitions can still consume substantial bandwidth, RAM, disk and cloud charges if run on paid infrastructure. Set byte/row/time budgets before execution; never accept requester-pays or billing-enabled resources as an automatic fallback. Requests expose the region to the hosting service; locally cached extracts reduce repeat disclosures.

**Priority / feasibility:** **P1, medium effort**. No live spatial extraction was executed in this research, so performance, chosen-region yield and schema compatibility remain unverified. Benchmark incremental candidate recall over OSM and preserve the existing imagery-grid fallback.

## 5. Date-aware satellite screening: STAC and Sentinel-2

**Primary sources:** [Planetary Computer STAC API](https://planetarycomputer.microsoft.com/api/stac/v1), [live Sentinel-2 L2A collection](https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a), [official Python SDK](https://github.com/microsoft/planetary-computer-sdk-for-python), [Copernicus Sentinel-2 mission/resolution](https://sentiwiki.copernicus.eu/web/s2-mission), [Copernicus terms](https://dataspace.copernicus.eu/terms-and-conditions).

**Verified facts and limits:**

- Copernicus describes four bands at **10 m**, six at **20 m**, and three at **60 m** for the MSI mission. The mission's 13 bands should not be confused with the exact assets in an L2A collection: this collection exposes B02/B03/B04 RGB and B08 NIR at 10 m, other bands and scene classification; asset inventories must be read, not assumed.
- A bounded date/bbox STAC GET returned HTTP 200 without a token: item `S2C_MSIL2A_20250614T101621_R065_T33UUU_20250614T142405`, datetime `2025-06-14T10:16:21.025000Z`. Its B04 asset declares `gsd: 10`, 10 m projected transform, and **cloud-optimized GeoTIFF** media type. Full response: `sources/pc-search-probe.raw`.
- The collection's `license` is **`proprietary`**, with a separate link to Copernicus Sentinel data terms. This metadata flag is not proof that imagery is paid/closed, nor permission to label it CC0. Follow the linked data license and applicable provider terms. The old linked license hostname may need recovery from current Copernicus legal documentation before redistribution.
- The SDK README: “A subscription key is not required for interacting with the service,” but having one permits less restricted rate limiting. Its `sign`/`sign_inplace` helpers sign Azure assets for read access. Open STAC metadata does not mean every raster URL can be fetched indefinitely unsigned.
- Collection summary platform names listed 2A/2B, while the actual returned item is 2C. This is direct evidence that summary metadata can lag item reality. Use item-level metadata rather than hard-coded satellite assumptions.

**Integration:** use `pystac-client`/plain STAC requests for bounded bbox and dates, cap pages/items, inspect item dates/cloud cover, apply local scene-classification/cloud/shadow masks, obtain permitted signed read access, then range-read a small COG window with a geospatial raster library. Preserve original item/asset metadata, CRS, resolution, resampling, mask and acquisition time. Do not treat item-wide cloud percentage as proof that the target crop is clear. Refresh expiring SAS access without embedding tokens in evidence logs.

**Material use:** season, large water bodies/coastlines, snow, major construction/land-use change and large quarry/port/solar-field screening. A nominal 10 m pixel does not give a 10 m geolocation error bound. Upsampling cannot restore individual windows, small signs or fine roof geometry. Seasonal similarity is not a confirmed place match, and optical imagery absence under clouds is not evidence that a feature is absent.

**Cost/auth/privacy:** metadata probe was free of credentials and used no paid compute. Signing, raster range-reading, bandwidth and current service quotas were **not tested**. Use only documented public/no-billing paths; local compute still costs time/storage. Requests expose area/date hypotheses but need not send the query photograph. SDK MIT licensing is separate from each collection's data rights. Other STAC collections can have very different licenses and resolution.

**Priority / feasibility:** **P2, medium effort** after reference/data adapters. A strong lawful regional-screening fallback, not a replacement for authorized high-resolution evidence. Planetary Computer documentation HTML returned only a JS shell here; SDK source and live STAC JSON supplied the substantive evidence instead.

## 6. Local models: separate regional priors, retrieval and geometric verification

### 6.1 GeoCLIP — trial as a broad regional proposal engine

**Primary sources:** [official repository](https://github.com/VicenteVivan/geo-clip), [model implementation](https://github.com/VicenteVivan/geo-clip/blob/5ef9c350fff3be42efbbb6b54537288aeab062c7/geoclip/model/GeoCLIP.py), [authors' NeurIPS paper, v2](https://arxiv.org/html/2309.16020v2).

The README describes contrastive image/GPS alignment trained on **4.7M** MP-16 images and exposes `model.predict(image_path, top_k=5)`. Crucially, the implementation loads `coordinates_100K.csv`, scores image features against a **GPS gallery**, softmaxes those logits and selects gallery rows. A continuously encoded Earth is not continuous exact-position inference in this default method.

The paper's Im2GPS3k table reports **14.11% within 1 km**, **34.47% within 25 km**, **50.65% within 200 km**, **69.67% within 750 km**, **83.82% within 2500 km**. These are authors' benchmark results, **not reproduced here**; their “Street” column uses 1 km, not building-level precision. The paper discusses gallery sampling limitations. A coordinate with six decimals and a high gallery softmax value cannot substantiate a precise camera position or calibrated confidence radius.

**Integration:** isolated optional process with its own dependencies; return a geographically diversified top-K regional shortlist with raw scores, gallery revision and model hash. Cluster adjacent gallery hits before allocating search budget; many near-identical GPS rows should not consume all candidates. Preserve routes suggested by independent text/geometry even if the model misses them. Fine-grid candidate rescoring inside a known region is an experiment requiring evaluation, not evidence that the model can localize to that grid's cell size.

**Constraints:** repository MIT license verified, but audit checkpoint/backbone/gallery distribution terms separately; code licensing does not clear training-image rights. Current README requires Python **3.11+** and Pillow **13.x**, unlike the skill's Python 3.10 floor. Pin/test the observed revision rather than copying stale installation instructions. Downloads are network requests; after permitted local caching, image inference can remain off-network. No weights were downloaded or inference timings established. **P2, medium effort**; broad-region recall and calibration must justify inclusion.

### 6.2 StreetCLIP — explicitly noncommercial and geographically biased

**Primary source:** [authors' model card](https://huggingface.co/geolocal/StreetCLIP/blob/main/README.md) (captured raw in `sources/streetclip-card.raw`).

Excerpts: direct use is geolocation on a “**country, region, or city level**”; training data are 1.1 million street-level images across 101 countries, “biased towards western countries and **not including India and China**.” License is **CC BY-NC 4.0**. The card states that attempting to geolocate users' private images is out of scope and discouraged. This is a meaningful use limitation, not a footnote to ignore because inference is local.

The card's zero-shot Im2GPS3K results are **22.4% at 25 km**, **37.4% at 200 km**, **61.3% at 750 km**, **80.4% at 2500 km**. No building/street confirmation is established. Label-list softmax is conditional on the supplied choices; adding or omitting cities changes the task. The model is CLIP ViT-L/14 at 336 pixels, not a drop-in use of the current `match.py` 224-pixel hand preprocessing.

**Integration:** **P2/P3, research-only comparator**, opt-in on appropriately licensed public/consented benchmark material, with no private-image use contrary to its card. Keep excluded countries explicit in evaluation; do not overstate the country/city label list as a global calibrated posterior. Noncommercial licensing blocks making it an unreviewed default for commercial use. No remote hosted demo should receive target photos under the no-upload policy.

### 6.3 DINOv2 / AnyLoc — improve reference retrieval, not global geolocation by itself

**Primary sources:** [DINOv2 code/models](https://github.com/facebookresearch/dinov2), [AnyLoc official repository](https://github.com/AnyLoc/AnyLoc), especially its [feature/VLAD usage](https://github.com/AnyLoc/AnyLoc#using-the-apis).

The existing repository already uses local DINOv2-small global descriptors. AnyLoc's important difference is **patch-level DINOv2 features aggregated with VLAD**, with a fitted/loaded visual vocabulary (`c_centers.pt`). It is visual place recognition over a **reference gallery**. Without candidate geotagged images it does not manufacture GPS evidence; gallery coverage places an upper bound on retrieval recall.

**Experiment:** index the same permitted regional reference images under (a) existing CLS+mean baseline, (b) AnyLoc-style VLAD, and optionally (c) a lighter pooled variant. Use the correct pretrained preprocessing, backbone/layer/facet and vocabulary. Build vocabularies only on training/reference splits, not held-out query images; test both domain-matched and mismatched vocabularies. Save descriptor and vocabulary hashes. Group sequence near-duplicates so top-K is not occupied by adjacent near-identical frames. Cache embeddings only where data terms permit.

**License/runtime/privacy:** DINOv2 repository/models are Apache-2.0; AnyLoc repository is BSD-3-Clause. Check checkpoint/vocabulary/dataset rights separately. AnyLoc documents CPU-capable demo routes but its full validation setup uses substantial GPU/RAM resources; that is not a minimum requirement or an Apple Silicon benchmark. Existing DINOv2-small is a sensible fallback. Do not assume `xformers`/CUDA demo paths work on MPS. Inference can be local after downloads. **P1 experiment, medium/high effort**; promote only after same-gallery recall/latency measurement.

### 6.4 LightGlue — optional matching upgrade with extractor licensing and geometry gates

**Primary source:** [official LightGlue repository](https://github.com/cvg/LightGlue).

Excerpt: “The pre-trained weights of LightGlue and the code ... are released under the Apache-2.0 license.” The same paragraph warns **SuperPoint has a different restrictive license**; DISK is Apache-2.0 and ALIKED BSD-3-Clause. Therefore “LightGlue is Apache” does not clear the commonly shown SuperPoint pipeline.

Use an appropriately licensed compatible extractor plus LightGlue only on retrieval top-N, then independently estimate/test geometry. Raw correspondence counts and neural matching confidence are not proof of one location. Record inlier ratio, spatial coverage, residuals, valid orientation, degeneracy, repeat patterns, and failure under changed viewpoint/season. A planar homography can fit one facade without proving the camera pose or entire scene.

The repository reports speed on particular RTX/Intel machines; those numbers are **not measurements on this Mac** and must not be quoted as expected local throughput. Keep existing SIFT as a CPU fallback and useful ablation. No dependency install, model download or local LightGlue run occurred. **P2, medium effort**, behind reference coverage and retriever evaluation.

## 7. OCR: improve script coverage and uncertainty before adding a document VLM

**Primary sources:** [Apple Vision text-recognition documentation](https://developer.apple.com/documentation/vision/recognizing-text-in-images) and its [documentation JSON](https://developer.apple.com/tutorials/data/documentation/vision/recognizing-text-in-images.json), [RapidOCR](https://github.com/RapidAI/RapidOCR), [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR).

- Keep local Apple Vision as the first backend on macOS, but discover actual supported languages/request revision at runtime rather than assuming the script's long default language list works identically on every OS revision.
- RapidOCR README: “Default support for Chinese and English recognition,” with other languages linked to a model list. This corroborates the local integration gap: accepting `--langs` is not enough to select the fallback model. Its current code license is Apache-2.0; the README separately documents upstream PaddleOCR model weights and `MODEL_LICENSES.md`.
- PaddleOCR is Apache-2.0 and its current README distinguishes natural-scene OCR pipelines from document parsing/VLM products. It now advertises PP-OCRv6 and broader multilingual capability. These moving-version and benchmark claims are **not reproduced scene-text accuracy results** here. Pin a concrete detector/recognizer and script model, not the shifting name “latest PaddleOCR.”

**High-value changes to evaluate:** preserve quadrilateral text boxes, backend/model/version, original literal string, confidence, crop transform and preprocessing pass; retain competing readings rather than deduping away disagreements; do script-aware recognition with explicit models; add rotation/perspective handling and targeted original-resolution crops before indiscriminate upscaling. Maintain separate verbatim OCR and agent interpretation/translation. Disable lexicon correction where it rewrites unusual place names. A VLM can propose readings but must not silently become ground-truth OCR or infer an unseen town name from context.

**Privacy/cost:** local execution can avoid photo uploads; model downloads and optional model-host services are separate routes. No hosted OCR, cloud vision API or paid product was used. Framework licenses and each checkpoint's terms must both be retained. **P1, small/medium effort** for backend correctness and multilingual tests; **P3** for large OCR-VLM additions unless hard examples show a need.

## 8. Reverse search and resilient agent investigation

### 8.1 Supported access is narrower than consumer availability

**Primary sources:** [Google's Lens/search-by-image UI instructions](https://support.google.com/websearch/answer/1325808?hl=en), [Bing Search API retirement](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement), [Google Street View Static billing](https://developers.google.com/maps/documentation/streetview/usage-and-billing), [Street View policies](https://developers.google.com/maps/documentation/streetview/policies).

- Google's help documents **browser workflows** (upload a file, use an image URL, browser image search), and says results may include AI overviews, similar images and websites. It does not establish a general public Lens automation API. This research verified the official UI documentation, **not** absence of every possible Google product or future partner API. A similarity label or AI overview is a lead; the originating page and invariant visual details are the evidence.
- Existing Baidu/Yandex browser uploads remain provider/UI-dependent and transmit the image. No official supported programmatic reverse-image interface for these was established here. Respect challenge/login walls; do not treat a browser session as permission to defeat them. Under this task's no-upload rule these routes are **disabled**, not merely “use carefully.”
- Microsoft's retirement notice says Bing Search APIs were retired **11 August 2025**, with existing instances decommissioned and no new signup. Do not design a fallback around an obsolete Bing Visual/Search API tutorial or silently substitute a different paid grounding service. Consumer image search may still be a separate UI; its existence does not resurrect the API.
- Street View Static requires billing enabled and API key/OAuth and is billed per panorama. Its policy generally prohibits prefetching/indexing/storing/caching content, with an explicit panorama-ID exception. An embedding library made from fetched content needs policy review; do not assume transforming content into vectors clears indexing restrictions. This is **not an approved no-paid integration** even if a monthly free allowance might exist. An undocumented no-key endpoint is not a lawful-free substitute for the supported billed product.

**Recommended workflow:** default to local EXIF/OCR/retrieval and text queries that do not disclose private information. Only enable remote image search after explicit destination-specific user consent and rights review. Explain that cropping/EXIF removal does not remove all scene-identifying content. User-authorized search of an already public image URL still discloses the investigated URL to the search provider. Never upload in a diagnostic probe.

### 8.2 Capability contracts: recommended design, not implemented

A single `reachable: true` is insufficient. Every adapter should expose:

- **Availability:** unconfigured, authenticated, reachable, semantically working, rate-limited, challenged, schema-changed, or blocked by license/privacy policy.
- **Request provenance:** sanitized endpoint, query/bbox/date, provider, source IDs, source capture dates, requested and actually searched extent, page/cursor state, result count/cap, data release, response hash, elapsed time and attribution/license.
- **Result semantics:** success-empty, success-complete-within-defined-request, partial, unknown-coverage, or failed. A field named `has_more` is a hard assertion: reconcile rows/IDs/cursors programmatically. Never equate HTTP 200 with semantic success or HTTP 500 with a transient transport fault.
- **Privacy contract:** exactly what leaves the device (image bytes, crop, EXIF, private address, bbox, URL, token), account requirements, spend ceiling and permission state. Local-first must survive fallback; do not automatically turn an offline step into an image upload.
- **Recovery:** timeouts, bounded exponential backoff with jitter and `Retry-After`; no unchanged retries for auth/schema/policy errors; circuit breakers; resume from durable page/batch checkpoints; avoid re-downloading completed batches. Mirrors are availability alternatives within policy, not quota bypasses.
- **Security:** treat web text, OCR and captions as untrusted evidence, never as agent/tool instructions. Validate content types and response schemas; limit download/decoded-image sizes, follow redirects only with credential safety, and redact auth/signed URLs. Pin model/package revisions; review executable model-loading paths and prefer non-executable weight formats where available.

**Semantic canaries motivated by actual findings:** Mapillary JSON auth error inside HTTP 500; KartaView unsupported parameter and stale hostname; JS-only documentation shell under HTTP 200; STAC item with a newer platform than collection summary; Overpass partial `remark`; expired asset URL; success with zero rows; schema-valid but irrelevant/geographically wrong metadata. Canaries should check a documented known public location, have small request caps, and never submit a user photo.

### 8.3 Investigation policy: keep useful disagreement, do not collapse confidence

Use coarse models to propose **diverse regions**, OCR/structured data to propose anchors, and reference imagery/terrain/camera geometry to confirm. When models disagree by continents, enlarge the candidate set and seek a high-information clue; averaging coordinates is not useful. Distinguish correlated support (multiple pages copying one caption; Overture derived from OSM; adjacent images in one sequence) from independent constraints. Record searched-vs-unsearched extents; a source outage must decrease claimed search coverage, never exclude the corresponding region.

For exact identification, retain the skill's minimum standard: multiple independent constraints or a checked ground-level match on at least three invariant features; reconcile camera elevation, heading/FOV and datum. Do not convert similarity scores into metres, give precise coordinates to satisfy an output schema, or make model top-K omissions hard exclusions. Stopping can report a supported region and the next discriminating evidence without fabricating a point.

## 9. Benchmark design: measure capability and resilience separately

**This section is a proposed experiment, not results.** Use only public/appropriately licensed or expressly consented images; no private-residence/person tracking, and no uploads. Keep all target-image inference local. Public provider metadata/reference downloads must comply with their terms and fixed zero-paid budgets.

### 9.1 Dataset and leakage controls

Create a versioned manifest with image hash, rights/source/license, verified camera position and uncertainty, capture date where known, scene class, country/region, difficulty, permitted disclosure and split. Use a geographically stratified pilot that covers urban/rural, landmark/non-landmark, multilingual text, no text, night, season/time changes, mountains/coast, occlusion, older imagery, sparse OSM/street imagery, and China/India distribution-shift cases. Freeze pilot size and budget **before** inspecting outcomes; expand only after validating labels and measurement reliability.

Ground truth should identify **camera position**, not merely landmark centroid, EXIF guess or an online caption. Exclude/flag uncertain labels for fine-scale evaluation. Split by geographic site and capture sequence/contributor/session where possible; put near-duplicates and all crops of one photo in the same split. Hold out queries from descriptor-vocabulary fitting, model tuning and OCR lexicon creation. Audit web/reference overlap; report unavoidable unknown pretraining leakage separately rather than claiming a clean unseen-world test.

Maintain two gallery conditions:

1. **Oracle-covered gallery:** relevant reference exists; isolates retrieval/matching quality.
2. **Natural coverage / absent-reference gallery:** real provider availability, dates and outages; measures full-system usefulness and correct abstention.

A retriever must not get credit/blame for coverage without reporting this distinction. Negative queries whose true location is outside the gallery are essential.

### 9.2 Paired ablations

| Experiment | Fixed control | Treatment | Main question |
|---|---|---|---|
| Regional proposal | Existing non-model clues/search | + GeoCLIP; separately opt-in StreetCLIP on allowed material | Does geographically diverse regional recall improve at the same investigation budget? |
| Reference coverage | Current permitted gallery | + KartaView; + Mapillary when authorized; + Commons individually and jointly | How often is a usable, temporally relevant true-site view added? |
| Retrieval | Same exact gallery and image preprocessing policy | Existing DINOv2 CLS+mean versus AnyLoc VLAD | Is Recall@K higher without unacceptable memory/latency? |
| Pair verification | Same top-N candidate pairs | SIFT versus licensed-extractor LightGlue, plus geometry | Fewer false place confirmations at matched recall? |
| Enumeration | Same justified areas/feature classes | OSM only versus OSM+Overture | Incremental real-world candidate recall, correlated-source duplication and query cost? |
| Regional screening | Existing regional clues | + clear/date-appropriate Sentinel-2 tests | Does it eliminate ambiguity without false exclusions? |
| OCR | Same original crops and evaluation strings | Current Vision/RapidOCR versus configured script models | Better literal names/numbers without hallucination or false geocoding? |
| Agent resilience | Same cached fixtures and policy | Typed errors, checkpoints, provider selection and canaries | Less lost work/false exclusions and fewer policy violations? |

### 9.3 Metrics and reporting

- **Global/region:** top-1 geodesic error, median and tail error; accuracy at 1/25/200/750/2500 km for literature comparability; candidate-region Recall@K and covered-area/search-budget cost. Report fine-scale metrics separately, never call the literature's 1 km “building precision.”
- **Retrieval:** Recall@1/5/10/20, mAP where multiple views are relevant, site/sequence-diversified recall, and oracle gallery coverage. Relevance criteria must account for camera-position uncertainty and usable shared structure, not just nearby GPS.
- **Fine identification:** fraction of independently checked matches within 25/100 m where ground truth supports those thresholds, false-confirmation rate, verification-feature/geometry audit, and precision-versus-coverage under abstention. These are evaluation thresholds, not promised operating accuracy.
- **Calibration:** reliability curves, risk/coverage curve, Brier/ECE only after defining and fitting an appropriate held-out probability target, and empirical coverage of reported radii. Report geographic/scene subgroup failures. Raw cosine/softmax/board scores are not probabilities by declaration.
- **OCR:** character/word error rate, literal proper-name and digit exact match, script-specific recall, false-text rate, downstream correct candidate recall; evaluate original-image versus upscaled/tiled-only detections separately.
- **Service/agent:** semantic success rate, partial/unknown rate, false exclusions, retrieval/parse failures, recovered progress, duplicate requests, per-provider queries/bytes, cold/warm runtime, peak RAM/disk, model download size, and investigator/tool-call effort. Report abstentions and blocked routes in denominators.
- Use paired per-query comparisons; bootstrap uncertainty by **site/sequence**, not near-duplicate image, and publish subgroup counts. Keep provider snapshots/cache timestamps fixed for model comparisons, and separately measure live availability. No cherry-picking successful geolocations.

### 9.4 Fault injection and promotion gates

Offline fixtures should include TLS failure, DNS/timeout, 403 challenge, 429 with `Retry-After`, 500 auth error, unsupported query argument, HTML instead of JSON, truncated JSON, valid partial Overpass reply, capped pages, duplicate/cyclic cursor, empty unknown-coverage response, expired image URL/SAS, corrupt/oversized image, incorrect CRS/coordinate order, missing timestamp, and poisoned page text asking the agent to upload or change instructions.

**Hard gates:** zero unauthorized uploads, zero paid/billing-enabled fallback, zero secrets in reports, no source failure converted into negative location evidence, no fabricated confirmation, and reproducible resume/dedup/count behavior. Fail a candidate integration if it cannot meet these, even if a few benchmark locations improve. Define an acceptable false-confirmation ceiling and latency/bytes budget before tuning. Promote a retrieval/model change only if paired held-out results improve the chosen objective with acceptable uncertainty; retain the simpler baseline otherwise.

## 10. Delivery plan and unresolved checks

| Order | Deliverable for a future implementation | Must verify before claiming done |
|---|---|---|
| P0 | Upload/spend permission gates and typed source-result envelope; durable checkpoints | No-upload/offline fault tests; semantic errors retain unknown coverage; exact counts/cursors reconcile |
| P1 | KartaView public adapter + Commons evidence discovery | Current approved base URL, valid paging, actual processed-image fetch, attribution and projection/date handling |
| P1 optional | Mapillary adapter | User-provided token; live allowed operation, pagination/coverage tests, terms/limits, safe asset reuse |
| P1 | Bounded Overture/OSM extract path | Selected-region data yield, release/schema pinning, overlap predicates, byte budgets and theme licensing |
| P1 | OCR backend/script tests and retrieval benchmark harness | Actual language-model selection, literal scene-text accuracy; fixed-gallery retrieval baseline |
| P1/P2 | AnyLoc retrieval trial, then optional LightGlue | Real local CPU/MPS timings/memory, model/vocabulary/extractor licenses, paired recall and false-match outcomes |
| P2 | Sentinel-2 STAC/COG screening | No-key signing and small range read, cloud masks, CRS/date/resolution fidelity, current data-license wording |
| P2 | GeoCLIP regional shortlist | Isolated compatible runtime, checkpoint/gallery provenance, diversity and held-out regional recall/calibration |
| P3 / restricted | StreetCLIP and OCR-VLM research | Allowed use and noncommercial constraints; demonstrated gain over smaller local alternatives |

**Still unresolved:** authenticated Mapillary behavior and quota; KartaView image-byte retrieval, formal current hostname support, pagination and rate limits; any regional coverage census; live Overture extraction performance; raster signing/range reads; all local model compatibility, resource use and comparative accuracy; full downstream redistribution/training-rights review. These are explicit work items, not assumed capability.

## 11. Evidence package and reproducibility

`sources/` contains raw primary responses (`*.raw`), derived readable HTML text (`*.txt`), GitHub README/repository metadata captures, inspected upstream code, and manifests. `sources/retrieval-notes.json` records local baseline, observed upstream heads, exact operational probes and limitations; `direct-manifest.json`, `probe-urls.json` and `additional-probes.json` preserve other fetch URLs/outcomes. Browser-rendered KartaView terms/docs and Mapillary homepage are separately named `*-rendered.txt`.

Raw HTML shells are intentionally preserved as **failed substantive retrievals**, not cited as if they contained the advertised page. KartaView docs/terms were recovered by rendering; Planetary Computer functionality was established from official SDK source plus live STAC metadata. The Mapillary help-center request returned 403, so API docs/terms replaced it rather than repeated scraping. GitHub branch heads were observed after README capture and are **not an atomic snapshot**; re-fetch exact pinned revisions before implementation.

This report establishes source-backed feasibility and specific operational failure modes. It does not establish a measured accuracy gain, universal imagery coverage, production readiness, or an entitlement to reuse any provider's images beyond their applicable terms.

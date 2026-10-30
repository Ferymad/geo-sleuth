# Geo-sleuth: research and reliability upgrade

## Main conclusion

The highest-value architecture is not one enormous geolocation prompt or a bag of
unconditionally installed models. It is a **missing-evidence router**:

1. Recover the best original pixels, metadata, literal text and provenance.
2. Propose geographically diverse hypotheses, preserving weak-clue alternatives.
3. Enumerate and retain candidate coverage; don't filter away the true location.
4. Acquire appropriate, dated reference imagery or independent public inventories.
5. Use terrain, physical constraints and camera geometry to verify the site/pose.
6. Preserve failures, unfinished work, artifacts and uncertainty across interruptions.
7. Evaluate real solve rate separately from software regressions.

A recognized street and a measured camera height are different deliverables.
fSpy can help calibration; controls/LiDAR/survey supply metric geometry; a pose
solver estimates camera parameters; a held-out overlay checks them. None of those
can manufacture absent scale, geographic anchors or a trustworthy ground surface.

## Verified delivery

All 283 tests across 12 suites passed. Scoped Ruff F/E9 and diff checks passed;
actual service blockers and untested accuracy claims are retained explicitly.
Read [final verification](verification.md) for the exact scope, logs and limits.

## Read by question

| Question | Report |
|---|---|
| Which prompts/execution choices cause early failure? | [Agent execution audit](agent-execution-audit.md) |
| Which imagery providers, geographic datasets and models add useful evidence? | [Capability research](capability-research.md) |
| Which calibration, reconstruction, LiDAR and 3D tools help? | [Geometry capabilities](geometry-capabilities.md) |
| What independent websites, municipal records, transport and physical clues rescue difficult cases? | [Extended toolbox](extended-toolbox.md) |
| Are existing independent skills worth installing? | [Skill ecosystem review](skill-ecosystem.md) |
| What exact board bugs were reproduced/fixed? | [Board audit](board-audit.md), [review fixes/migration](board-review-fixes.md) |
| What partial-result/timeout/stale-output problems were fixed? | [Runtime audit](runtime-audit.md), [review fixes](runtime-review-fixes.md) |
| How does resumable progress differ from a candidate board? | [Investigation design](investigation-design.md) |
| Which camera-input checks were added without replacing the solver? | [Pose preflight](pose-preflight.md) |
| What fSpy interoperability was actually tested? | [fSpy bridge](fspy-bridge.md) |
| What public reference adapter works, and where is live access blocked? | [KartaView adapter](kartaview-adapter.md) |

## Agent-facing entry points

The revised [skill](../skills/geo-sleuth/SKILL.md) links short on-demand guides:

- [Capability routing](../skills/geo-sleuth/references/capabilities.md)
- [Specialist rescue sources](../skills/geo-sleuth/references/rescue-sources.md)
- [Geometry workbench](../skills/geo-sleuth/references/geometry-workbench.md)
- [Investigation and recovery](../skills/geo-sleuth/references/investigation.md)
- [Blind evaluation](../skills/geo-sleuth/references/evaluation.md)

These are operational instructions, not claims that optional applications,
credentials or model weights have been installed. Load only the route relevant
to the current missing observable. Cinematic camera-composition skills are not
appropriate measurement instructions.

## Concrete corrections already implemented

- Deduplicate legacy evidence revisions; don't multiply the same clue twice.
- Count supporting read/computed evidence only when its artifact exists; an
  opposing test is not confirmation. Empty/all-excluded boards cannot pass.
- Add `board.py check --strict`, finite likelihood validation and status-based caps.
- Preserve full reports, detect coordinate/leader disagreement without a large
  radius hiding it, remove stale generated fields while preserving manual evidence.
- Add explicit `relocate-files --base` repair for legacy relative paths; don't guess.
- Detect provider errors, refusals, missing/malformed/contentless reverse-search
  records even when their child exits zero. Preserve valid sibling results.
- Kill the owned POSIX process group on timeout; keep partial diagnostics. Windows
  process-tree cancellation remains a documented limitation, not a tested promise.
- Reject stale intake output directories and invalid engine/variant options before
  work. Recovery writes a fresh directory rather than mixing evidence epochs.
- Keep shared HTTP startup/timeout diagnostics actionable without echoing URL/proxy
  credentials. Raw source artifacts still need careful handling before publication.
- Add an offline investigation ledger with typed outcomes, artifact hashes,
  structural validation, pending work, resumption and qualified stopping.
- Add an offline scorer that keeps missing/abstained cases in denominators and
  measures actual location error/radius coverage without treating scores as truth.
- Add a bounded public KartaView metadata adapter: a real query returned 70 unique
  candidates with explicit unknown coverage. Offline thumbnail decode/failure
  contracts are tested, but live storage returned HTTP 409 and processed CDN HTTP
  500; this is not a verified live image pipeline.
- Add a separate opt-in pose preflight for control provenance, malformed input,
  free-parameter budget, image spread/planarity and model-assumption warnings;
  the original numerical pose solver is unchanged.
- Add a dependency-free fSpy v1 project inspector, exercised on the official example;
  it preserves calibration evidence without inventing scale or GPS registration.
- Replace hard top-K exclusion language with progressive, diverse retrieval recovery.
  Correct species/weather exclusion shortcuts and unconditional pose-radius claims.
- Start intake local-only unless provider-specific remote search is already authorized.

## Highest-value next experiments

These are prioritized research recommendations, not completed accuracy claims:

1. Expand usable ground-reference coverage with public KartaView and Commons;
   add Mapillary only with proper credentials/terms. Evaluate coverage before model
   retrieval: no descriptor can retrieve an image absent from the gallery.
2. Use bounded dated OSM/Overture extracts and official municipal inventories for
   candidate generation/outage resilience. Related datasets can share one source.
3. Improve control-point quality and scene observability before replacing the pose
   solver. Explicit elevation provenance, local ground surface, image frame and
   withheld controls matter more than another low-residual fit.
4. Compare current DINOv2 pooling against AnyLoc-style aggregation on the same
   licensed gallery. Trial licensed-extractor LightGlue as a reranker only after
   coverage/retrieval baselines exist.
5. Verify actual OCR script/model selection and literal place-name accuracy.
   A language flag does not prove that the selected fallback supports that script.
6. Add dated STAC/COG screening for broad land-cover/water/snow hypotheses; don't
   substitute 10 m RGB for sub-metre building evidence.
7. Trial GeoCLIP as a diverse regional-prior generator, not a precise GPS oracle.
   StreetCLIP's noncommercial/use constraints and geographic bias preclude an
   unreviewed universal default.
8. For already recognized sites, acquire a measured length, independently surveyed
   controls or a usable LiDAR tile before escalating to COLMAP/Blender/learned pose.

## Evidence and limits

Target baseline: `bb5c2400af8cd6f05849d0c5f3346980c0b16d15` from
Ferymad/geo-sleuth (fork of Oldcircle/geo-sleuth). GitHub retrieval used `gh` as
requested. REA's loaded skill routes a complete source repository to ordinary
source/runtime tools; no decompilation was needed or claimed.

Primary documentation/source and small public metadata probes underpin the
research. Raw third-party captures remain **local** under `research/sources/`,
ignored by Git to avoid redistributing entire external pages. Authored reports cite
public originals and disclose blocked pages, missing credentials and untested
runtime paths. A citation does not imply the external tool was installed/executed.

No target photo was uploaded, paid service called, global application installed,
or original solver/model replaced in this work. Public example intake was a
known-answer runtime smoke test, not blind localization. No end-to-end accuracy
multiplier or “100% correct” claim is justified. The missing acceptance evidence
is a controlled paired trial on consented original photos with camera truth held
out from fresh solving agents. [Evaluation protocol](../skills/geo-sleuth/references/evaluation.md)
defines it; [validation outputs](validation/) record the narrower executed checks.

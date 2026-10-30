# Agent execution audit

## Scope and evidence

Target: Ferymad/geo-sleuth, a fork of Oldcircle/geo-sleuth, baseline
`bb5c2400af8cd6f05849d0c5f3346980c0b16d15`. GitHub facts and threads were retrieved
with `gh repo view`, `gh issue list`, `gh pr list` and `gh api`. Retained JSON is
under `research/sources/`. This is an available-source/CLI investigation, not a
binary-reconstruction task: the REA skill explicitly routes ordinary complete
source repositories to standard repository tools. No decompilation would add
evidence here.

The claims below distinguish observations from proposed improvements. No blind
photo localization trial was performed in this audit. Public examples already
reveal answers and cannot serve as held-out measurements in this session.

## Why plausible runs fail

### 1. Candidate recall is lost before the final reasoning

Primary evidence: [upstream issue 37](https://github.com/Oldcircle/geo-sleuth/issues/37)
and its maintainer/runner comments (retained `issue-37-comments.json`). The reports
describe three first-run failures: unsupported `highspeed=yes` filtering, a gap
between cluster representatives and downstream search windows, and a correct
street-view candidate not reaching verification after similarity ranking.

Important qualification: the maintainer and reporting user explicitly identify
unequal model settings, lower-resolution/cropped display inputs, and changed
execution choices. These are failure-path evidence, not a controlled comparative
accuracy study or proof that one model is worse. The original-resolution photos
are not publicly supplied for all cases.

Current source already contains some upstream repairs: cluster `extent_m`
warnings, `refined` match flags, explicit incomplete DEM behavior, image loading
helpers and replay instructions. Do not sell existing repairs as new work.

Inference: improving recall and recording search handoffs has higher leverage
than telling a solver to “try harder.” A later geometric verifier cannot rescue a
site which never entered its candidate set.

Implementation direction: preserve broad raw candidates; justify every hard
filter from visible evidence; compare cluster extent with the actual downstream
radius; make top-K an initial review batch rather than an exclusion rule. Add
explicit run records so blocked, partial and empty routes remain distinguishable.

### 2. The main prompt has conflicting retrieval instructions

Observed in baseline `skills/geo-sleuth/SKILL.md`:

- General guidance says not to stop at a fixed number of failed areas.
- The perception table says to look “only at the top few.”
- Street-view confirmation says “Open only the top 10.”
- Budget guidance starts with top 30/top 10 and discourages paging.
- A sentence says recognizable species are “only an exclusion tool,” while the
  hard rule says third-party species labels cannot justify exclusion.

The revised instructions retain ranking-first efficiency but define those counts
as initial batches. Recovery changes crop/season/heading/method, inspects a diverse
lower-ranked control sample and extends the queue under budget. Species labels
remain weak ranking evidence. These changes address contradictory instructions;
a measured solve-rate improvement still requires controlled trials.

### 3. Ranked scores are not calibrated geographic confidence

Baseline `board.py::_scores` sums evidence log likelihood ratios. Repeated or
correlated evidence can overstate support unless identity/dependence is handled.
Even mathematically normalized shares only compare the supplied candidates:
missing true sites and weak source coverage invalidate interpreting them as
probability that the location is correct.

The board audit documents exact reproduced defects and fixes separately. The
skill now explicitly says high share and command success are not geographic
verification. Independent constraints mean independent error mechanisms; two
reposts of one photo or two models reading the same ambiguous text are not two
independent observations.

### 4. A “successful” process is not a complete investigation

The existing runtime already addresses many failures; for example, issue 5's
missing-DEM-as-sea-level problem was fixed upstream, not by this audit. Primary
source: [issue 5](https://github.com/Oldcircle/geo-sleuth/issues/5), retained comments.
A live `doctor.py --network --json` in this session reached the tested services,
returned a Google panorama at its covered probe point, but reported Overpass
HTTP 502 as WARN. HTTP reachability is not service coverage or a successful
photo-search operation.

The runtime audit and investigation tool address the narrower remaining gaps.
A route record is not another candidate board: it owns method/scope/outcome,
retained file identity, blockers, next actions and stop rationale. The board still
owns candidates, clues and exclusions. Stop validation can check the record's
consistency but cannot establish that a human's scientific judgment is sound.

## Prompt and tool design supported by primary guidance

[Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
recommends simple designs, environmental ground-truth feedback, explicit stopping
conditions and tool documentation/testing. It distinguishes parallel independent
work from an orchestrator selecting subtasks. That supports narrow, evidence-bound
workers rather than multiple agents independently inventing final coordinates.
It does not demonstrate a geo-sleuth-specific gain.

[Anthropic, Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
discusses compaction, structured notes and focused subagent contexts. Applied here:
keep actual commands, file paths, unresolved contradictions and search extents on
disk; reload only the relevant guide; preserve evidence identities rather than
stuffing every panorama and failed request into the lead agent's context.

[Agent Skills specification](https://agentskills.io/specification) sets a
1024-character description limit. Baseline description is 899 characters and
therefore does not have the previously reported issue-16 blocker. Do not confuse
the installed skill's prose length with a current schema violation.

Primary HTML and derived text are retained alongside `agent-guidance-manifest.json`
with source URLs and HTML SHA-256. These sources motivate design decisions;
none certify improved localization accuracy.

## Recommended worker contract

For a genuinely broad case, partition independent questions: OCR/language,
map/terrain enumeration, provenance/search, then a falsification reviewer.
Pass the same image hash, constraints, permissible upload scope, candidate bounds
and output schema to each. Each returns observed clues, cited/retained artifacts,
coverage, contradictions and a next discriminating action. One coordinator merges
records; workers must not concurrently rewrite the same board. The reviewer must
look for the strongest alternative and unsupported precision, not vote by model
agreement. Add workers only where parallel work is independent and budget permits.

## What “drastically better” must mean

Use `references/evaluation.md` and `evaluate.py`: paired blind cases, fixed inputs,
equal budgets, repeated fresh contexts, first-loss candidate recall, all-case
accuracy, abstention, runtime/cost and empirical radius coverage. Keep public
known-answer examples as numerical regressions, not held-out localization wins.
The added CLI and regression tests can prove contract fixes today; they cannot
honestly establish an unmeasured end-to-end accuracy multiplier.

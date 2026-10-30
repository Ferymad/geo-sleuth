# Investigation playbook

Read this for ambiguous multi-route searches or when resuming an interrupted run.
It governs progress and recovery, not candidate scoring. `board.py` still owns
clues, candidates and evidence judgments. Use one writer per board and ledger.

## Start small, preserve state

1. Inspect the original and useful crops. Confirm source/purpose and upload scope
   under the skill's privacy rule. Do not identify people or pinpoint a third
   party's private home. Keep legitimate user-owned/consented site analysis within
   its stated scope; a puzzle label alone does not establish consent.
2. Define the requested accuracy, hints, input quality, resource limits and data
   access. Do not silently substitute an arbitrary time budget for the user's goal.
3. Run intake; inspect failed/skipped operations and actual artifacts, not only the
   exit code. `--no-rev` means not searched, not searched without a match.
4. Use `board.py` for observed/read/inferred/computed clues and candidate pools.
5. For multiple routes, initialize a separate progress ledger. The examples below
   are templates, not claims that these searches have run:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/investigation.py init --goal 'Find a verified road-level location'
uv run ${CLAUDE_SKILL_DIR}/scripts/investigation.py route --method 'reverse image search' --scope 'original photo, authorized engine' --reason 'test for a published near-duplicate' --next-action 'run search and inspect source pages'
uv run ${CLAUDE_SKILL_DIR}/scripts/investigation.py status
```

Each route gets an ID such as `R1`. Add a few feasible, discriminating routes for
this image, not every possible service. Plan method and scope separately for
engines/crops/regions with meaningfully different coverage. After executing a real
operation, record its literal command or tool action and immutable output files:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/investigation.py attempt R1 --outcome blocked --command 'literal command or tool action actually used' --summary 'Actual error and bounded scope; no result coverage' --next-action 'Try another accessible source or reassess this route'
```

`--command` is recorded, never executed. Do not paste credentials or sensitive URL
query parameters. For success/empty/partial outcomes use one or more `--artifact`
paths: readable nonempty files whose bytes will remain retained. Empty search
results must have a real response artifact (e.g. `[]`), not an absent output.
Artifacts have SHA-256/byte counts and are rechecked on status/stop. Preserve raw
per-attempt files; rewriting a previously recorded output creates an integrity
problem. Record next actions for partial and blocked outcomes. A successful query
only completes its bounded route; it does not verify the location.

## Choose the next action by what it can distinguish

- A readable unique name: verify OCR with another crop, enumerate same-name sites,
  check a source page, then geometry. A search engine's label is a hypothesis.
- Weak broad country clues: keep alternatives. Test language/regulation/terrain
  independently rather than stacking synonyms for one impression.
- Missing map features: measure source coverage and use another inventory or a
  justified satellite grid. An unmapped feature is not an absent feature.
- Known landmark: anchor geometry and invariant-feature comparisons before more
  broad web search. Two independent constraints means different error mechanisms,
  not two copies of the same source or two model votes on the same ambiguity.
- A narrow-looking result with no independent check: spend the next action on
  falsifying it, not polishing the answer.

Use the scene-to-tool table in `SKILL.md`, [capability routing](capabilities.md),
and the relevant geometry/search/skyline guide. Missing credentials, terms limits
or access challenges block that route; do not bypass them. Ask for help only when
it unlocks a genuinely useful remaining method.

## Prevent silent candidate loss

Before a hard filter, write the visible fact that justifies it and preserve the
broader pool. “Electrified” does not imply “high speed.” A registration plate is
not proof that the vehicle is still in its registration region. Check data date,
datum, fields, missing values, duplicate identities and administrative boundaries.

Before handing results to the next stage, record:

- input count and searched spatial extent;
- output count, rejected/unqueried fraction and the reason;
- fit radius versus cluster extent, grid spacing and focal/roll limits;
- unavailable DEM cells, unrendered panoramas and unrefined matches;
- which retained file restores the broader search.

Similarity ranks are a queue. Start with the documented top batches, then recover
if no candidate matches: inspect a diverse lower-ranked sample, compare structural
crops instead of foliage/vehicles, vary heading and season/history, try a different
retrieval method, and extend the queue within budget. Don't declare everything
below a cutoff false. Scores from different models are not directly comparable.
Inspect the strongest alternative and the most down-weighted plausible candidates
before narrowing further.

## Recovery and continuation

- Timeout: inspect the actual child process and partial artifacts before rerunning.
  Do not assume detached work finished, nor kill unrelated processes.
- Service denied/rate-limited: retain the error, respect retry guidance, switch to a
  feasible lawful alternative. An unchanged repeated failure is not progress.
- Partial computation: preserve good cache entries, retry missing work and report
  coverage. Do not replace unknown elevation or an untested match with zero.
- Interrupted context: reload `investigation.py status`, `board.py check`, the
  current relevant guide and selected artifacts. Summarize what was tried, exact
  candidate bounds, contradictions and the next discriminating action. Never
  resume from a remembered coordinate without its evidence. Legacy boards with
  relative artifact paths need an explicit original directory, not a guessed
  search path: `board.py --board /path/to/board.json relocate-files --base /original/session/directory`
  validates all references before saving absolute paths. Keep mixed-origin legacy
  references separate; the migration cannot infer their original directories.
- Parallel workers: assign independent questions and separate output files; pass
  image identity, scope and restrictions. Require sources, coverage, contradictions
  and next tests. One coordinator merges findings; agreement alone is not evidence.

`reopen R1 --next-action '...'` reopens completed/deferred work. `defer R1 --reason
'...'` marks a genuinely infeasible route; it is not a shortcut around unfinished
work. Preserve its limitations. Use a user/budget stop if time is the issue.

## Stop honestly

Run `board.py check --strict` and inspect the artifacts; then `investigation.py status`.
The ledger's stop gate checks the recorded plan and file integrity, not truth:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/investigation.py stop --kind supported --reason 'Evidence supports this level; finer detail remains unresolved' --level road --qualification 'State the independent constraints and remaining uncertainty' --artifact result.json
```

A supported stop needs an explicit level, qualification and retained board/human
assessment. It may leave finer work unresolved; disclose it. The artifact must
actually contain that assessment: file existence/hash cannot establish meaning.

Use `--kind user` only for an actual user stop request, `--kind budget` for an
actual reached user-set limit, or `--kind exhaustion` when no recorded feasible
unattempted/blocked/partial routes or next actions remain. Exhaustion is bounded
to the plan; consider missing methods before making that judgment. All reasons
are required. User/budget stops retain unresolved work and integrity problems;
support/exhaustion require intact retained artifacts. `resume` returns to active
work while preserving previous stop history.

Report the finest supported level, actual searched extent, attempted methods,
blockers, alternatives, contradictions and best next evidence. Do not invent a
point, radius or missing artifact to finish. Unresolved, honestly bounded output
is preferable to false precision. Improving this workflow must be assessed using
[blind paired evaluation](evaluation.md), not prompt length or test count.

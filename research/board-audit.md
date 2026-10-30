# Candidate-board correctness audit

## Scope and evidence

Base revision: `bb5c2400af8cd6f05849d0c5f3346980c0b16d15`.
Implementation is confined to `skills/geo-sleuth/scripts/board.py` and `skills/geo-sleuth/tests/test_board.py`; this document is the requested audit artifact. No photo uploads, paid services, commits or pushes were used.

Read `CONTRIBUTING.md`, the installed geo-sleuth skill, and both board implementation/test files. The existing baseline board suite passed:

```text
Ran 17 tests in 3.154s

OK
```

External evidence, retrieved during this audit:

- [scikit-learn: Naive Bayes](https://scikit-learn.org/stable/modules/naive_bayes.html): multiplication of feature likelihoods assumes conditional independence; the documentation specifically warns that good classification need not imply reliable probability estimates. This supports deduplicating repeated evidence, not interpreting board percentages as calibrated confidence, and retaining an explicit limitation for correlations across different clues.
- [scikit-learn: Probability calibration](https://scikit-learn.org/stable/modules/calibration.html): calibrated confidence requires empirical agreement between predicted probabilities and observed frequencies. The board has no such calibration dataset or validation procedure. A normalized ranking share cannot establish a camera error radius.
- GitHub retrieval used `gh` only. `gh issue list --repo Ferymad/geo-sleuth --state all --limit 30 --json number,title,body,url` returned `the 'Ferymad/geo-sleuth' repository has disabled issues` (exit 1). `gh pr list --repo Ferymad/geo-sleuth --state all --limit 15 --json number,title,url` returned `[]`. No issue or PR evidence is claimed.

## Findings and narrowly scoped changes

### 1. Legacy duplicate evidence inflated ranks and revived superseded support

`_put_evidence` already revised duplicate clue/candidate entries when a new write occurred, but `_scores` still multiplied every entry on a read. `_inherited` could also select old positive evidence after a later negative revision. Consequently an untouched legacy board could report stronger evidence than an equivalent newly written board.

Added `_effective_evidence`: one entry per `(clue, candidate)`, last ledger entry wins. Ranking, descendant inheritance, checks and report diagnostics all use this view. Read-only operations do not rewrite the ledger. Distinct clues still accumulate; descendant opposition still does not refute the entire parent. Regression tests cover old duplicates, last-negative descendant revision, id preservation and independent-clue accumulation.

Exact probe output before:

```text
LEGACY_DUPLICATES
[{"n_ev": 2, "n_verified": 2, "name": "A", "share": 0.9090909090909091}, {"n_ev": 0, "n_verified": 0, "name": "B", "share": 0.09090909090909093}]
```

After:

```text
LEGACY_DUPLICATES
[{"n_ev": 1, "n_verified": 1, "name": "A", "share": 0.6666666666666666}, {"n_ev": 0, "n_verified": 0, "name": "B", "share": 0.3333333333333333}]
```

Inputs: equal-prior city candidates A/B; K1 is computed with an existing artifact; A has ledger entries LR 5 then LR 2 for K1. There is only one actual test, revised to LR 2.

### 2. Negative or missing-file evidence passed as confirmation

Previously `n_verified` counted every read/computed clue regardless of sign or artifact existence. A sole remaining candidate with only evidence *against* it passed the conclusion check; so did a candidate whose only claimed computed output did not exist.

Verified support now requires LR > 1, status read/computed, and an existing regular artifact file. An explicit evidence comparison file takes precedence; otherwise the original clue artifact is used and is also included in report evidence. Missing/directory paths do not verify support. Newly recorded clue, evidence, apply and exclusion paths are absolute, so changing working directory does not invalidate their provenance.

Before (sole A, LR 0.5, real computed artifact):

```text
NEGATIVE_ONLY_CHECK
Pre-conclusion check:
  ok   main answer A: 1 pieces of evidence, 1 verified
Result: pass
```

After:

```text
NEGATIVE_ONLY_CHECK
Pre-conclusion check:
  FAIL main answer A has no supporting read/computed evidence backed by an existing file: you can't claim this level or finer
Result: has FAIL, fix those first
```

Before (sole A, LR 2, clue/evidence both reference a nonexistent artifact):

```text
MISSING_ARTIFACT_CHECK
Pre-conclusion check:
  ok   main answer A: 1 pieces of evidence, 1 verified
Result: pass
```

After:

```text
MISSING_ARTIFACT_CHECK
Pre-conclusion check:
  FAIL main answer A has no supporting read/computed evidence backed by an existing file: you can't claim this level or finer
Result: has FAIL, fix those first
```

### 3. Empty boards passed and FAIL had no automation-safe exit mode

An empty/all-excluded board had no leader to validate and could therefore pass. Added an explicit FAIL when there are no open candidates. Added opt-in `check --strict`, which exits 1 on FAIL and 0 on pass. Plain `check` retains the existing diagnostic-only exit behavior for compatibility with existing callers/tests.

Before:

```text
EMPTY_CHECK
Pre-conclusion check:
Result: pass
```

After:

```text
EMPTY_CHECK
Pre-conclusion check:
  FAIL no non-excluded candidates: add candidates or revisit exclusions before concluding
Result: has FAIL, fix those first
```

### 4. Lookup application bypassed clue caps and accepted invalid likelihoods

`evidence` capped inferred LR at 3, but `apply --clue <inferred clue>` used its default LR 20 without checking the clue status. This made the same weak clue artificially stronger merely by changing entry point. `evidence` also allowed NaN into JSON; `apply` accepted nonpositive/nonfinite values and unknown clues reached the child lookup before failing.

`apply` now validates the clue and positive finite LR before lookup, and applies the same status cap as `evidence`. `evidence` rejects nonfinite LRs. Rejections preserve board bytes. The new mocked lookup regression observed LR `20.0` before versus expected `3`; after the fix it passes. NaN/positive infinity/negative infinity/zero/negative tests pass without mutation. No service requests are made for rejected apply inputs.

### 5. Report text was cut mid-JSON and remerge retained stale conclusions

The report printed only its first 4,000 characters, silently cutting later candidates/clues and often producing malformed JSON. It also retained old board-generated alternatives, exclusions and unused clues when their new values became empty. That could make an agent carry resolved or withdrawn claims into its final answer.

Removed truncation. Repeated merge now refreshes board-owned exclusions/unused clues and removes stale generated alternatives even when no new alternatives remain; manual alternatives are retained. Existing top-level coordinates/radius are not overwritten.

Exact probe output before:

```text
LONG_REPORT
valid_json=false
REMERGE
{"alternatives": ["Old (share 10%): old test", "manual alternative"], "excluded": ["old exclusion"], "unused_clues": ["old clue"]}
```

After:

```text
LONG_REPORT
valid_json=true
REMERGE
{"alternatives": ["manual alternative"], "excluded": [], "unused_clues": []}
```

Long-report input: sole A, one 5,000-character clue. Remerge input: sole A, no actual alternatives/exclusions/unused clues, and the three stale arrays shown above.

### 6. A claimed large radius concealed a different nominated location

`report --merge` padded the leader bbox by the result's own `radius_m`, allowing an arbitrary large circle to conceal that the reported coordinate was outside the leader. It now compares the nominated coordinate with a fixed 30 m tolerance instead. A new regression uses A bbox `[49.0,-123.0,49.001,-122.999]` and result `(50.0,-122.0)` with radius `500000`: before, `main_mismatch` was absent; after, the mismatch is recorded while all three input values remain unchanged. The report also adds an explicit `score_note` that shares are ranking weights, not calibrated probabilities or precision evidence.

## Reproduction and verification

Run from the repository root:

```bash
uv run skills/geo-sleuth/tests/test_board.py
uv run skills/geo-sleuth/tests/test_board.py BoardCorrectnessTests
uv run skills/geo-sleuth/tests/test_runtime.py
uv run skills/geo-sleuth/tests/test_regions.py
git diff --check
```

The new regression class was exercised before implementation:

```text
Ran 10 tests in 1.333s

FAILED (failures=16, errors=1)
```

The extra radius/path tests were then separately reproduced before their implementation:

```text
Ran 2 tests in 0.289s

FAILED (failures=2)
```

After implementation, the board suite passed:

```text
Ran 29 tests in 5.196s

OK
```

Nearest affected gates also passed:

```text
# test_runtime.py
Ran 101 tests in 5.626s

OK

# test_regions.py
Ran 29 tests in 1.830s

OK
```

Runtime suite output contains intentional mocked Overpass failures and a partial-intake report; the suite returned exit 0. `git diff --check` returned exit 0 with no output. The tests use temporary local fixtures and mocked/loopback services; they do not demonstrate successful live geolocation of a photo.

For minimal manual reconstruction of the rank/check probes, use a board dictionary with `candidates`, `clues`, `evidence`, `falsify` and `log` fields. Use equal-prior open city candidates, a computed K1 with its `file` set to a temporary real file, and evidence records with `id`, `clue`, `candidate`, `lr`, `why` and `file`. Call `_scores(board, 'city', 'none')`; persist the dictionary and call `cmd_check(Namespace(prior_by='none', evidence=None, strict=False), path)`. The named tests contain runnable fixture creation and exact assertions for every changed behavior.

## Remaining workflow risks (not claimed fixed)

- Different clue IDs derived from the same sign, crop, search hit, repost or upstream source still multiply. The board lacks an explicit dependency/provenance-group model. Automatically grouping by filename would also suppress independent features legitimately measured from one image, so that broad behavioral change was not guessed here. Agents should reuse the same clue ID for a revision, and treat correlated clues as one observation until dependency semantics are designed/tested.
- A read/computed label plus a real file does not prove the file genuinely verifies the claim. This change verifies support direction and file existence, not the scientific validity or content of the artifact.
- The board does not implement quantitative coordinate uncertainty or the skill's two-independent-constraints/three-invariant-features rule. The score note and mismatch fix prevent specific misleading outputs, not a complete precision certificate.
- Legacy relative paths retain their old working-directory interpretation; only new writes are normalized. Existing boards with ambiguous old paths need explicit repair, not an invented origin directory.
- `next` still emits a ready-to-scan suggestion after warning about an inference-only leader. Unused clues, unknown scan coverage and cheap-test completion are not a full machine-enforced stopping policy. Agent-level continuation and bounded-search accounting require work outside this patch.
- `report` remains a human-facing command: merge messages/reminders/warnings can surround the now-complete JSON. Consumers needing structured output should read the merged `board` field; no claim of a new JSON-only CLI is made.
- Plain `check` intentionally retains exit 0 on diagnostic FAIL. Automation must opt into `--strict`.

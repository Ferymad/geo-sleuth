# Runtime resilience audit

Baseline: `bb5c2400af8cd6f05849d0c5f3346980c0b16d15`. Scope: intake orchestration, shared HTTP transport, doctor diagnostics, provider output handling and recovery. Read `CONTRIBUTING.md`. No private photos were used or uploaded; provider failures are offline fixtures and transport routing tests use loopback HTTP. No commits or installed-skill edits were made.

## Reproduced and fixed

| Failure | Reproduction / observed pre-fix result | Change and acceptance check |
|---|---|---|
| Provider failure reported as overall success | `test_provider_error_is_partial_even_when_child_exits_zero`: child returns 0 but writes `{"error":"verification required"}`; intake returned `result=ok`, not `partial`. `revimg.py` intentionally records individual provider exceptions without necessarily failing its process. | Intake inspects item errors/refusals after collecting records. Failed providers make the report partial; successful local steps remain usable and partial still exits 0, preserving the existing CLI contract. |
| Missing search work reported as success | `test_missing_search_record_is_not_success`: successful child produces no records; intake returned `ok`. | Check received record count against the images actually scheduled for each engine. A missing record is explicitly incomplete (`received 0 of 1 expected result records`), not a successful empty search. |
| Damaged provider artifacts destroy or silently truncate the final report | `test_malformed_search_record_keeps_a_report_and_valid_sibling`: truncated JSON was silently omitted; JSON `[]`, `guess:[null]`, and `similar:[null]` raised exceptions; malformed links/error types passed through unchecked. | Validate consumed fields. A bad artifact becomes a named error entry; valid siblings and their London vote survive. The end-to-end truncated-record case produces a partial `intake.json` and Markdown report rather than losing the report. Empty valid lists remain valid results. |
| Reruns mix evidence from different runs | `test_reused_output_directory_is_rejected_without_losing_evidence`: old `ocr.json` was accepted even under `--no-ocr`; no early rejection occurred. Code also globbed old variants/reverse records without associating them with the current input. | Require a fresh output destination when any managed artifact already exists. Reject before starting children or changing evidence; the test verifies unchanged old bytes. Use a **new `--out-dir`** to recover. This is deliberately fail-closed, not an unverified resume/cache system. |
| Timeout discards diagnostics and does not own child lifetime | `test_timeout_stops_descendants_and_keeps_partial_diagnostics`: a real Python process prints progress and launches a delayed-writing descendant; old `_run` returned empty stdout on timeout. `subprocess.run` kills only its immediate child, not an entire uv/Python/browser family. | On POSIX, start an owned session and kill its process group at timeout, then drain captured output. Test verifies exit 124, both partial stdout/stderr, the timeout reason, and **no descendant marker file** after its scheduled write time. Windows keeps its existing process model but retains timeout output; Windows process-tree cancellation remains unimplemented. |
| Invalid options silently skip or duplicate provider work | `test_invalid_search_options_fail_before_starting_any_steps`: empty/unknown engines, duplicate Baidu and negative variant count all proceeded without rejecting input. Duplicate dictionary keys could hide one future while both tasks wrote the same outputs; negative slicing did not mean zero variants. | Reject those options before creating the output directory or launching any child. Explicit `--no-rev` remains the way to skip search. |
| Transport exceptions have inconsistent, potentially credential-bearing failure messages | `test_fetch_transport_exceptions_have_actionable_redacted_errors`: missing curl escaped as `FileNotFoundError`; `TimeoutExpired` included the command URL (including test credentials). | Normalize missing executable, subprocess timeout and startup errors to actionable `RuntimeError`s mentioning `doctor.py --network`, without raw URLs, proxy credentials or chained exception text. Existing curl exit-code failures remain unchanged. |

All test names above are in `skills/geo-sleuth/tests/test_runtime.py`. Fixes are confined to `scripts/intake.py`, `scripts/_net.py` and that test file. `doctor.py` was audited and exercised, not modified. Existing file modes are unchanged (`git diff --summary` for these files is empty).

## Existing safeguards confirmed

- Explicit proxy/direct routing overrides ambient proxy variables consistently: loopback HTTP checks real curl behavior, including proxy absolute-form requests. Model routing is set before client imports.
- Chrome-to-Playwright Chromium fallback preserves the selected route. Missing browsers produce installation guidance; disabled reverse search is separate from an empty search.
- Local intake visual-step failures retain reports, complete visual failure exits nonzero, and unreadable input exits 2 while still trying metadata. HEIC and EXIF-upright routing tests still pass.
- Doctor distinguishes transport failure from service blocks; HTTP 429 is a warning rather than a claim that search worked. Local diagnostics neither probe remote services nor disclose configured proxy credentials in the existing regression.
- Existing Overpass mirror/cache tests distinguish unconfirmed empty results from confirmed absence and reject error remarks. These paths were not rewritten.

## Remaining gaps / limits (not claims of fixes)

1. **No persistent checkpoint/resume protocol.** Intake writes its main report at the end; interruption before that can leave only intermediate files. Fresh-directory recovery preserves them but reruns work. A future resume mode needs input/content identity, arguments/provider-version identity, artifact validation and atomic checkpoints; merely reusing files is unsafe.
2. **Timeout policy remains coarse.** Individual subprocesses retain the 900-second default. Multiple requested crop boxes run sequentially, so total time can exceed one timeout. Windows descendants and processes deliberately escaping the POSIX group are not covered by the new group cancellation. This audit did not add a wall-clock budget or a retry storm.
3. **OCR/EXIF output schemas are less defensive than reverse-search schemas.** Malformed/missing OCR output can still be misread as no text, and malformed item dictionaries can break rendering; a JSON scalar from metadata can break `.get`. These are source-inspection findings in intake's post-batch parsing, not newly claimed test coverage.
4. **Doctor is setup/reachability, not end-to-end provider assurance.** Browser check visits `about:blank`; network checks do not upload an image, run OCR, load models, or verify every provider's schema. Existing ordinary HTTP probes cannot prove useful results. Browser shutdown has no explicit outer deadline. No live service health claims are made here.
5. **Failure provenance is still limited.** Curl nonzero exit codes are retained, but not a structured HTTP status/retry classification. Reverse entries still infer screenshot filenames even when no screenshot exists. Failed records may retain useful guesses, so downstream callers must inspect status rather than treat every emitted tag as equally trustworthy.
6. **Concurrent use of the identical fresh output path is not an atomic lock.** The fresh-artifact check protects ordinary reruns, not two processes passing the check simultaneously. Use a distinct output directory per process. No broad concurrency redesign was attempted.

## Actual validation

All commands ran from the repository root. After the initial baseline run, temporary fixtures were directed to the configured Hermes scratch directory through `TMPDIR`; no test photos/models were downloaded. Timings below are observed, not performance guarantees.

```text
uv run skills/geo-sleuth/tests/test_runtime.py IntakeStatusTests DoctorTests NetworkTests
baseline: Ran 15 tests in 3.167s — OK

uv run skills/geo-sleuth/tests/test_runtime.py
final: Ran 105 tests in 6.708s — OK

uv run skills/geo-sleuth/tests/test_board.py
Ran 29 tests in 5.411s — OK

uv run skills/geo-sleuth/tests/test_regions.py
Ran 29 tests in 2.003s — OK

uv run skills/geo-sleuth/scripts/doctor.py --json
exit 0; ok=true; connection=direct
Python, uv, curl, writable working directory, all four global tables,
bundled packs and Google Chrome launch: PASS
OCR and ML models: INFO (not exercised by doctor)
Network probes: SKIP (no --network)

git diff --check
exit 0, no whitespace errors
```

The new tests were run red before each behavior change, then green. The full runtime suite includes the real descendant-cancellation probe and loopback HTTP test; other provider interactions are mocked. Board/region suites were run against the shared working tree, which also contains changes owned by other workers; those files were not edited by this audit. No `match.py`/gazetteer changes were made here.

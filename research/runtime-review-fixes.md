# Runtime review fixes

## Contentless reverse-search completion

- Reproduced the false completion before changing intake: a zero-exit child writing `photo_baidu.json` containing `{}` yielded `result: ok`. New regression tests initially failed on this and on credential-bearing provider errors.
- Read `scripts/revimg.py` without modifying it. `_collect` emits `url`, `guess`, `links`, and `text_head`; Baidu adds `similar`. Both providers return explicit `guess` and `links` lists even when empty. Error paths can emit only `error` (plus metadata added by `run`); unreadable-input records also carry empty lists. Link records contain string `title`, `url`, and `site`; Baidu similar-image records contain string `thumb`, `from`, and `site` (empty source/site strings are legitimate).
- Intake now requires both explicit `guess` and `links` lists for a successful result, or a nonblank provider error / explicit boolean refusal envelope. Missing lists, null lists, malformed elements, incomplete link/similar-image objects, and malformed optional diagnostic fields become retained errors naming the JSON file. Valid sibling records and their votes survive.
- Explicit empty lists remain valid. Neither nonempty hits nor a screenshot file is required. Yandex does not need Baidu's optional `similar` field. Provider errors remain failures even when the child exits zero.
- Provider-error URLs and child failure/exception status diagnostics redact URL userinfo before report inclusion (and before diagnostic truncation). Validation errors do not interpolate malformed source-field values. Raw provider JSON is preserved as source evidence rather than rewritten.

## Timeout and stale-output compatibility

- Existing POSIX timeout behavior still kills the owned process group, returns 124, and keeps partial stdout/stderr. Added a real subprocess regression for the additional case where the group leader has already exited but its descendant holds the captured pipes open; the descendant is killed and cannot write its delayed marker.
- Existing fresh-output protection still rejects stale reverse-search records before running any child and preserves their bytes. Added a direct stale `rev/photo_baidu.json` regression alongside the existing stale OCR regression.
- Added checks that nonzero/124 children retain valid completed result records and votes without upgrading the overall run to success. No additional timeout/stale-output code change was necessary. Windows-specific execution was not exercised on this macOS host.

## Verification

- `uv run skills/geo-sleuth/tests/test_runtime.py`: **112 tests passed**.
- `git diff --check -- skills/geo-sleuth/scripts/intake.py skills/geo-sleuth/tests/test_runtime.py`: passed.
- Only `scripts/intake.py`, `tests/test_runtime.py`, and this note were edited for this review; no commit was made. Existing unrelated working-tree changes were left alone.

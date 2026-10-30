# Independent KartaView adapter review

Scope: only `skills/geo-sleuth/scripts/kartaview.py`,
`skills/geo-sleuth/tests/test_kartaview.py`, and this report. No live requests,
allowlist expansion, unrelated edits, or commits.

## Fixed and verified

- Added test-script PEP 723 metadata: Python >=3.10, `pillow>=10`. The standard
  `uv run tests/test_kartaview.py` invocation supplies the image dependency.
- Numeric conversion catches `OverflowError` as a schema failure. Actual JSON
  integers `10**400` in latitude, longitude, matched latitude, and GPS accuracy
  now produce rejected rows and partial results rather than uncaught crashes.
- Both provider and local JSON parsing catch `RecursionError`. A 100,000-level
  nested JSON fixture exercises both CLI paths: nonzero exit, structured schema
  error, no output file/directory; only the provider path invokes its transport.
- Additional integrity defect: a rejected first occurrence reserved its ID and
  suppressed a later valid row. IDs are now reserved only after normalization
  succeeds. Regression fixture: invalid row, valid same-ID row, repeated valid
  row => one item, one failure, one duplicate, three returned rows. No merging
  of contradictory valid duplicates; first valid occurrence wins.
- Successful offline thumbnail test additionally verifies saved bytes, SHA-256,
  selected source URL, and agreement between report and index sidecars.

Before fixing the adapter, regression execution reproduced numeric overflow and
invalid-first duplicate suppression. A separate deeply nested JSON invocation
reproduced the uncaught provider `RecursionError`.

## Final execution

From `skills/geo-sleuth/`:

```text
$ uv run tests/test_kartaview.py
Ran 15 tests in 0.083s
OK
$ uvx ruff check --select F,E9 scripts/kartaview.py tests/test_kartaview.py
All checks passed!
```

Both commands exited 0. Tests use local fixtures/mocks; no provider requests or
model loading. This is focused verification, not a full repository test run or
an explicit Python 3.10 compatibility matrix.

## Live evidence and documentation caveats

Live thumbnail retrieval/decode remains **blocked/unverified**. The earlier
adapter thumbnail request for photo `616387694` returned HTTP 409, accepting no
image. The parent's subsequent same-photo CDN `imageProcUrl` recovery probe is
retained in `validation/kartaview-cdn-probe.json`: curl exit 56, HTTP 500,
`file: null`. This review read that evidence but made no additional requests.
A synthetic offline JPEG decode is not successful live provider-image retrieval.

The separate existing `kartaview-adapter.md` was outside this review's permitted
edit scope. Its first-occurrence deduplication description is superseded here
by **first valid occurrence**. Its historical 12-test result is superseded by
15 tests above. Its statement that no alternative/CDN download was attempted
applies to the earlier adapter run, not the parent's later failed CDN probe.
No host/network-policy change is needed or claimed.

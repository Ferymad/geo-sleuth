# Board review fixes

## Preserve manual result entries on merge

`report --merge result.json` now uses the previous structured `result.json.board` report to reconstruct the exact entries previously generated in `alternatives`, `excluded`, and `unused_clues`. It removes one matching occurrence per prior generated entry, prepends the current generated entries, and preserves the remaining user-owned entries. Repeated merges are idempotent. Manual alternatives containing `(share ` are no longer discarded by a text heuristic.

If there is no prior structured board report, existing top-level entries are preserved: ownership cannot safely be inferred from their wording. A manually edited former generated entry is also preserved because it no longer matches the previous generated text. Additional identical occurrences are preserved rather than wholesale deleted.

## Explicit legacy artifact-path migration

Newly recorded clue/evidence/exclusion artifact paths are absolute. Older boards may contain relative paths interpreted against the working directory used when they were recorded. Resuming from another directory can therefore make real evidence appear missing. The board does not infer or search for that original directory.

Declare it explicitly before resuming checks and reports:

```sh
python3 skills/geo-sleuth/scripts/board.py --board /cases/example/board.json relocate-files --base /original/session/directory
python3 skills/geo-sleuth/scripts/board.py --board /cases/example/board.json check --strict
python3 skills/geo-sleuth/scripts/board.py --board /cases/example/board.json report
```

`--base` is required. It applies to relative `clues[*].file`, `evidence[*].file` (including legacy revisions), and `candidates[*].excluded_by.computed` values. Nonempty references must all identify existing regular files before any changes are saved. Already absolute paths are validated but their spelling is left unchanged. Empty file fields are not invented. The photo and other unrelated paths are outside this operation's scope.

Missing files, directories used as files, invalid bases, and unresolved paths cause a nonzero exit with no board mutation. No fallback to the board directory or current working directory is attempted; the declared base supplies the only interpretation. If different historical records used different original directories, do not choose a guessed common base: restore or explicitly repair those references first. A successful repeat migration with no remaining relative paths does not rewrite the board or update its timestamp/log.

## Regression coverage

Public CLI tests cover stale generated entries disappearing while manual entries survive, generated-looking manual text, repeated merge idempotence, and additional identical manual occurrences. Migration tests resume a legacy board from another working directory, verify strict checks and report verification counts after repair, preserve absolute fields, and assert byte-for-byte no mutation for missing or invalid references and unspecified/invalid bases.

Validation: both `python3 skills/geo-sleuth/tests/test_board.py` and `uv run skills/geo-sleuth/tests/test_board.py` passed all 32 tests; scoped `git diff --check` passed. Broader unittest discovery was attempted but is not green: system Python lacks numpy/OpenCV; a uv retry supplying numpy/OpenCV/Pillow/SciPy still lacks torch/PyYAML and encounters the unrelated `test_fspy.FspyCLITests.test_rejects_deep_json_without_traceback` failure under Python 3.13. Those files were not changed for this fix.

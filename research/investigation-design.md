# Investigation ledger: bounded routes, explicit stopping

## Why a separate ledger

`board.py` owns candidates, clues, likelihoods, exclusion scope and evidence judgments.
`intake.py` owns one intake operation and its per-step outputs; it cannot know which
subsequent routes remain feasible. `investigation.py` records that missing layer:
planned methods, actual attempts, unresolved actions, artifact integrity and why a
run stopped. It never ranks a candidate or infers a location from task completion.

The previous gap is reproducible: a failed service or a small unsuccessful batch
has no durable record of alternative feasible actions, and no stop gate rejects
calling such a run exhausted. The new CLI regression tests reproduce those states
and reject exhaustion until the recorded pending work is addressed.

## Small public interface

All operations emit complete JSON, without truncating routes or attempts. Use
`--ledger PATH` before the subcommand (default `investigation.json`). No packages
beyond the Python standard library, network access, command execution, paid service
calls or global configuration changes are used.

```bash
python3 skills/geo-sleuth/scripts/investigation.py --ledger investigation.json init --goal 'road level'
python3 skills/geo-sleuth/scripts/investigation.py --ledger investigation.json route \
  --method 'reverse image search' --scope 'original photo, engine A' \
  --reason 'test near-duplicate hypothesis' --next-action 'search and inspect retained results'
# Run the real search separately. This CLI does NOT execute --command.
python3 skills/geo-sleuth/scripts/investigation.py --ledger investigation.json attempt R1 \
  --outcome blocked --command 'actual command that was run' \
  --summary 'engine returned access denied, no result coverage' \
  --next-action 'try another accessible source or assess lawful alternatives'
python3 skills/geo-sleuth/scripts/investigation.py --ledger investigation.json status
# This fails: R1 remains a feasible unresolved route.
python3 skills/geo-sleuth/scripts/investigation.py --ledger investigation.json stop \
  --kind exhaustion --reason 'no useful actions remain'
```

- `route`: requires method, bounded scope, reason and next action; returns stable
  `R1`, `R2`, … IDs. Plan separate routes for different engines or scopes rather
  than recording a narrow attempt against an ambiguously broad plan.
- `attempt ROUTE`: requires actual command/tool action text, summary and outcome
  (`success`, `empty`, `blocked`, `partial`). Commands remain verbatim text and the
  actual recording working directory is saved. Each attempt gets a stable ID and
  timestamp; retries append rather than overwrite.
- `--artifact PATH` is repeatable. Success, empty and partial require at least one
  readable nonzero regular file. Empty output is represented by retained `[]`, a
  result JSON or a response log, **not** a missing/zero-byte output. A blocked
  attempt can be recorded without an artifact if no output was obtainable.
- `blocked` and `partial` require a next action. Success and empty clear the old
  action unless `--next-action` explicitly leaves another action pending. A
  successful operation does not necessarily locate the photograph.
- `defer ROUTE --reason ...`: explicit judgment that a route is currently
  infeasible, retaining the reason in the route and event history. It clears that
  route's pending action, never declares a candidate absent. Do not defer a feasible
  route just to pass the stop gate; use a user/budget stop if time is the issue.
- `reopen ROUTE --next-action ...`: restores feasibility or reopens completed
  work. `resume` is needed before modifying a stopped run; previous stop records
  and their unresolved-route snapshots remain in history.

## Stop gate

`stop --kind KIND --reason ...` persists a decision:

| Kind | Gate | Meaning |
|---|---|---|
| `supported` | `--level`, `--qualification`, at least one `--artifact`, all retained artifacts intact | Operator's board/human-evidence-qualified supported level; unresolved finer work remains visible |
| `user` | explicit reason, e.g. actual user stop instruction | Stop requested, not exhaustion; pending work and integrity issues remain visible |
| `budget` | explicit reason describing actual user-set budget reached | Resource stop, not exhaustion; pending work and integrity issues remain visible |
| `exhaustion` | nonempty plan; no feasible unattempted/blocked/partial routes; no pending actions; all artifacts intact | Recorded bounded feasible plan exhausted, not proof that all possible methods were considered |

`status` reports persisted status, `effective_status`, all
`unresolved_feasible_routes`, `exhaustion_allowed`, artifact issues and limitations.
Any command validation/I/O failure exits 2 without saving the proposed change.
Status exits 1 if retained artifacts are changed/missing/unreadable, otherwise 0.
Other successful commands exit 0, including user/budget stops that explicitly
preserve integrity issues. `status` is read-only. Paths are absolute and therefore
survive a different working directory, but relocating files needs operator care.

Artifacts are hashed with SHA-256 and byte counts at recording time; status and
stopping rehash them. The ledger cannot be its own artifact. Changed historical
attempts or stop assessments are not silently re-blessed by a later attempt.
Restore retained original bytes if recoverable; otherwise report the integrity
problem and retain an honest user/budget stop, rather than claiming support or
exhaustion. Local writes use same-directory atomic replacement; init exclusively
creates its target without overwriting an existing investigation.

## Honest limits

- These are operator-attested records, not a command runner, execution monitor or
  a scientific-adequacy proof. An existing file's hash proves neither its meaning
  nor that the stated command generated it. Files are referenced, not copied.
- An `empty` artifact is checked for existence/readability/nonzero bytes and
  integrity, not parsed for semantic validity. A denied service can be mislabeled
  by a dishonest operator; the tool cannot recognize every response format.
  Blocked routes are never automatically converted into empty/absent results.
- Supported stops require a retained board/human assessment and explicit
  qualification but do not parse board scores or certify precision/independent
  constraints. Run `board.py check` and evaluate real evidence separately.
- Search scopes, feasibility, budget reached and user instructions are attested
  text. Completion covers only the recorded plan, not unrecorded alternatives.
- There is no auto-import from intake, schema migration, file relocation,
  concurrent-writer locking or tamper-proof audit trail. Use one writer per ledger.
  Keep private paths, source images and sensitive commands out of public reports.

## Offline verification

The tests exercise the public CLI through subprocesses and real artifacts, with
all temporary cases explicitly below `TMPDIR` when it is set. No shell commands
from ledger records are executed and no services are contacted.

```bash
python3 skills/geo-sleuth/tests/test_investigation.py
uv run skills/geo-sleuth/tests/test_investigation.py
```

Coverage includes pending-plan rejection, bounded empty results, blocked/partial
outcomes, alternative feasible routes, explicit next actions, integrity changes
and deletions, qualified support, user/budget stops, resumptions, disposition audit
history, invalid inputs without mutation and literal nonexecuting command text.

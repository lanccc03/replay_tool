# Trace streaming import and replay

This ExecPlan is a living document. It follows `.agents/PLANS.md` and must be kept current as implementation proceeds.

## Purpose / Big Picture

The replay tool currently materializes every parsed trace frame into Python lists and tuples before importing, validating, or replaying a scenario. That makes large ASC traces expensive in memory and prevents replay from scaling to long captures. After this change, importing a trace reads and writes frames one at a time, and replay pulls only the next scheduling batch from a cursor backed by the binary frame cache. A user can import, validate, and run the existing examples with the same CLI commands, while the implementation no longer depends on `ReplayPlan.frames`.

## Progress

- [x] (2026-04-30) Read project guidance, trace storage, planner, runtime, and tests.
- [x] (2026-04-30) Chose implementation defaults with the user: full phased implementation, reject out-of-order timestamps, and fully migrate runtime away from `ReplayPlan.frames`.
- [x] (2026-04-30) Created this ExecPlan before code changes.
- [x] (2026-04-30) Implemented streaming ASC iteration, streaming binary cache writer, and streaming import/rebuild summary accumulation.
- [x] (2026-04-30) Added SQLite-backed cache block index creation and index-backed `iter_frames()` selection.
- [x] (2026-04-30) Added cache-backed runtime cursor plumbing through `TraceStore.iter_frames()` and `PlannedSourceReader`.
- [x] (2026-04-30) Migrated planner and runtime to planned frame sources and timeline cursors; runtime tests now use an in-memory trace reader.
- [x] (2026-04-30) Updated README and architecture/testing docs for streaming import and cache-backed replay.
- [x] (2026-04-30) Ran compile, full unit tests, CLI validation, and recorded that Windows hardware validation was not performed.

## Surprises & Discoveries

- Observation: The existing Trace Library already has `ManagedTraceReader.iter()` and `SqliteTraceStore.iter_frames()`, but ASC import and planner compilation still call full-list APIs.
  Evidence: `src/replay_tool/storage/trace_store.py` uses `frames = self.trace_reader.asc_reader.read(...)` during import and rebuild; `src/replay_tool/planning/plan.py` uses `trace_reader.read(...)` and stores `ReplayPlan.frames`.
- Observation: Runtime batching is already based on a 2 ms window and dispatches batches grouped by device, so streaming replay can preserve current timing semantics by changing where batches come from rather than changing dispatch.
  Evidence: `src/replay_tool/runtime/scheduler.py` defines `FRAME_BATCH_WINDOW_NS = 2_000_000`; `src/replay_tool/runtime/dispatcher.py` accepts a sequence of frames and groups by device id.

## Decision Log

- Decision: Reject out-of-order timestamps during streaming import and cache iteration rather than sorting in memory.
  Rationale: Sorting a large trace requires materializing frames or implementing external merge sort, which is outside this first streaming milestone.
  Date/Author: 2026-04-30 / Codex
- Decision: Fully migrate runtime away from `ReplayPlan.frames` instead of keeping a long-term dual path.
  Rationale: The user chose a clean cursor model. Tests can use an in-memory cursor source to keep runtime tests focused without requiring trace files.
  Date/Author: 2026-04-30 / Codex
- Decision: Keep the public CLI command shape unchanged.
  Rationale: The feature is an implementation scalability upgrade; existing users should keep using `validate`, `run`, `import`, `traces`, `inspect`, `rebuild-cache`, and `delete-trace`.
  Date/Author: 2026-04-30 / Codex

## Outcomes & Retrospective

Implemented. Trace import and rebuild now stream ASC input into binary caches, Trace Store maintains a lightweight cache block index, planner emits planned frame sources instead of materialized frames, and runtime replays through a merged timeline cursor. Existing CLI command shapes are preserved. Remaining limitations: BLF is still unsupported, unordered ASC external sorting is not implemented, and Windows Tongxing hardware validation was not performed.

## Context and Orientation

`next_replay` is a ports-and-adapters replay tool. Scenarios are parsed into `ReplayScenario` domain objects, compiled by `ReplayPlanner`, and executed by `ReplayRuntime`. The current `ReplayPlan` stores `frames: tuple[Frame, ...]`, and `TimelineScheduler` slices that tuple by timestamp into 2 ms batches. The storage layer can read ASC and binary cache files, but import and planning still materialize full frame lists.

The target design is a cursor model. A cursor is a small object that can look at the next frame timestamp, pop the next frame, read a scheduling batch, rewind to the beginning for loop playback, and close any open file. A planned frame source describes where frames come from, which source channel and bus to accept, and which logical channel frames should be mapped onto. Runtime still knows only the `ReplayPlan`; it does not read the original scenario.

Important files:

- `src/replay_tool/storage/asc.py` parses Vector ASC files.
- `src/replay_tool/storage/binary_cache.py` reads and writes `.frames.bin`.
- `src/replay_tool/storage/trace_store.py` owns SQLite trace metadata and import/rebuild/delete flows.
- `src/replay_tool/planning/plan.py` defines `ReplayPlan` and `ReplayPlanner`.
- `src/replay_tool/runtime/scheduler.py` owns timing, pause/resume, loop, and batch windows.
- `src/replay_tool/runtime/kernel.py` runs the worker loop.

## Plan of Work

First, add streaming storage primitives. `AscTraceReader.iter()` opens ASC text and yields parsed frames while verifying timestamps never go backward. `read()` becomes a convenience wrapper that returns `list(self.iter(path))`. `BinaryFrameCacheWriter` writes a temporary cache, reserves the file header with zero frames, writes each encoded record as frames arrive, then seeks back to update the count and atomically replaces the destination. Existing `write_binary_frame_cache()` delegates to the writer so current tests and callers continue to work.

Second, refactor trace import and rebuild. Add a small summary accumulator in `trace_store.py` that tracks event count, start/end timestamps, source counts, and message id sets while frames pass through. `import_trace()` and `rebuild_cache()` copy the source ASC, stream it through the writer, build metadata from the accumulator, and reject empty or out-of-order input with clear `ValueError` messages. This removes the full `frames` list from import/rebuild.

Third, add cache index and cursor support. Extend the SQLite schema with a `trace_frame_index` table containing trace id, block number, file offset, start/end timestamps, frame count, and a JSON list of source channel/bus pairs in the block. Build the index while writing cache by recording each block's offset and frame metadata. `iter_frames()` uses this index to seek near the requested `start_ns` and scan only candidate blocks; if the index is missing for an existing trace, rebuild it from the cache before reading. The cache cursor reads records in order, filters by source, maps source frames to logical channels, and retains only a lookahead frame plus the current returned batch.

Fourth, migrate planning and runtime. Replace `ReplayPlan.frames` with planned frame source descriptions, `timeline_size`, and `total_ts_ns`. `ReplayPlanner.compile()` no longer calls `TraceReader.read()`. It resolves scenario routes into frame sources using paths that app has already normalized to binary caches. `ReplayApplication.compile_plan()` resolves imported trace ids and raw ASC paths to cache-backed records; raw ASC paths are imported into the workspace on demand before planning. Runtime scheduler owns a timeline cursor built from the plan. Its timing, pause/resume, loop restart, and 2 ms batch window behavior stays the same, but it asks the cursor for the current batch instead of slicing `plan.frames`.

Fifth, update tests and docs. Runtime tests use in-memory planned sources or cursor factories so they remain deterministic. Storage tests verify streaming equivalence, writer round trips, out-of-order rejection, large synthetic imports, and index-backed filtering. Planner/CLI tests verify no `plan.frames` dependency remains and existing commands still work. README and architecture/testing docs describe streaming import and cache-backed replay, and call out that BLF, external sorting for unordered traces, and Windows hardware validation remain out of scope.

## Concrete Steps

From `C:\code\next_replay`, edit with `apply_patch` only for source and documentation changes. After each coherent milestone, run the narrow relevant tests, then the full validation set:

    $env:PYTHONPATH=(Join-Path $PWD 'src'); python -B -m unittest tests.test_trace_store -v
    $env:PYTHONPATH=(Join-Path $PWD 'src'); python -B -m unittest tests.test_scenario_and_planner tests.test_runtime tests.test_cli -v
    $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m compileall src tests
    $env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m unittest discover -s tests -v
    $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m replay_tool.cli validate examples/mock_canfd.json

If a test uses `tempfile` and fails inside sandbox-only temp permissions, rerun it normally in this unrestricted workspace. Do not skip the test.

## Validation and Acceptance

The implementation is complete when:

- Importing `examples/sample.asc` produces a binary cache and metadata without materializing a full frames list in `SqliteTraceStore.import_trace()`.
- Rebuilding a cache also streams from ASC and preserves summaries.
- `ReplayPlanner.compile()` does not call `TraceReader.read()` and `ReplayPlan` no longer exposes runtime `frames`.
- `ReplayRuntime` sends the same batches as before for existing examples, including 2 ms batching, device grouping, pause/resume, loop, and partial send accounting.
- `TraceStore.iter_frames()` supports source/time filtering and uses the cache index for seekable reads.
- The full compile, unit test, and CLI validation commands pass.
- Final delivery states that Windows hardware validation was not performed unless it actually was.

## Idempotence and Recovery

All generated trace library data lives under user-selected workspaces such as `.replay_tool` or test temp directories and can be deleted and regenerated by `replay import` or `replay rebuild-cache`. Cache writes use temporary files and replace the destination only after the header is finalized. Index rebuilds delete and recreate rows for one trace id, so they are safe to retry. If a migration fails midway, rerun the same command; SQLite transactions should leave either the old rows or the new rows.

## Artifacts and Notes

- 2026-04-30: `python -B -m unittest tests.test_trace_store -v` passed after the storage streaming/index changes.
- 2026-04-30: `python -B -m unittest tests.test_runtime tests.test_scenario_and_planner tests.test_trace_store tests.test_cli -v` passed after the planner/runtime cursor migration.
- 2026-04-30: `python -m compileall src tests`, `python -m unittest discover -s tests -v`, and `python -m replay_tool.cli validate examples/mock_canfd.json` passed for final validation.

## Interfaces and Dependencies

No third-party dependencies are added. New or changed interfaces should be plain Python dataclasses and protocols in the existing `replay_tool` package.

The final `TraceReader` protocol must provide:

    def read(self, path: str) -> list[Frame]
    def iter(self, path: str, *, source_filters=None, start_ns=None, end_ns=None) -> Iterator[Frame]

The final replay plan must provide enough metadata for snapshots:

    name: str
    frame_sources: tuple[PlannedFrameSource, ...]
    devices: tuple[DeviceConfig, ...]
    channels: tuple[PlannedChannel, ...]
    loop: bool
    timeline_size: int
    total_ts_ns: int

The runtime timeline cursor must provide:

    current_batch() -> tuple[Frame, ...]
    target_perf_ns(batch) -> int
    advance(count) -> int
    at_end() -> bool
    restart_loop() -> int
    close() -> None

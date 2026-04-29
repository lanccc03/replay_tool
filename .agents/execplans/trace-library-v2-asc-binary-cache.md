# Trace Library v2：ASC 二进制缓存与窗口读取

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` from the repository root. A future engineer must be able to continue from this file alone, so this document repeats the relevant repository context, target behavior, commands, and acceptance checks.

## Purpose / Big Picture

This work upgrades Trace Library from a small-file JSON cache into an ASC-only binary-cache library that can support larger traces and future UI/runtime work. After completion, importing an ASC file writes a compact binary frame cache, existing scenario references by trace ID still work, callers can load only selected source channel and bus pairs, and tests can prove that a time-window reader returns only the frames needed for a requested replay window.

This plan intentionally does not add BLF parsing. BLF remains out of scope for this step so the storage foundation can be stabilized without adding the `python-can` dependency or broadening supported formats.

## Progress

- [x] (2026-04-29 Asia/Shanghai) Created this ExecPlan for Trace Library v2, with BLF explicitly out of scope.
- [x] (2026-04-29 Asia/Shanghai) Captured baseline Trace Library CLI and unit test behavior.
- [x] (2026-04-29 Asia/Shanghai) Add an ASC-only binary cache module with round-trip tests.
- [x] (2026-04-29 Asia/Shanghai) Replace JSON cache reading and writing with binary cache only.
- [x] (2026-04-29 Asia/Shanghai) Add source-filtered and time-window frame loading APIs.
- [x] (2026-04-29 Asia/Shanghai) Add cache rebuild and trace delete behavior.
- [x] (2026-04-29 Asia/Shanghai) Update docs and rerun automated validation.

## Surprises & Discoveries

- Observation: The current `SqliteTraceStore.import_trace()` copies the raw ASC, parses all frames into memory, and writes `<trace-id>.frames.json`.
  Evidence: `src/replay_tool/storage/trace_store.py` defines `CACHE_SUFFIX = ".frames.json"` and calls `write_frame_cache(cache_path, frames)`.

- Observation: Existing tests assert the JSON cache suffix, so they must be updated when binary cache becomes the default.
  Evidence: `tests/test_trace_store.py` checks `Path(record.cache_path).name.endswith(".frames.json")`.

- Observation: The old project has a useful binary cache design, but it also includes BLF loading and old `FrameEvent` fields that should not be copied directly.
  Evidence: `C:\code\replay\src\replay_platform\services\trace_loader.py` defines `BINARY_CACHE_MAGIC`, `BINARY_CACHE_SUFFIX`, and `iter_binary_cache()`, but also contains `_load_blf()`.

- Observation: Baseline tests pass before Trace Library v2 changes.
  Evidence: `python -m unittest discover -s tests -v` returned `Ran 21 tests in 0.186s` and `OK`.

- Observation: Baseline CLI import writes JSON cache.
  Evidence: `python -m replay_tool.cli import --workspace <temp> examples/sample.asc` returned `cache=...1339ce45108c48dcab77b8c39f2ecd30.frames.json`.

- Observation: Creating a nested probe workspace under `.replay_tool\trace_v2_baseline*` hit a SQLite disk I/O error, while a system temp workspace worked.
  Evidence: CLI import under `.replay_tool\trace_v2_baseline` failed at `sqlite3.OperationalError: disk I/O error`; the same import under `%TEMP%\next_replay_trace_v2_baseline_*` succeeded.

- Observation: The same SQLite disk I/O issue still happens for a fresh workspace-root CLI probe after implementation, but not for a system temp workspace.
  Evidence: `python -m replay_tool.cli import --workspace C:\code\next_replay\.replay_tool_trace_v2_final_* examples/sample.asc` failed at `_initialize_schema()` with `sqlite3.OperationalError: disk I/O error`; the final CLI transcript under `%TEMP%\next_replay_trace_v2_final_*` succeeded.

## Decision Log

- Decision: Implement binary cache only for the current `replay_tool.domain.Frame` model.
  Rationale: The new project uses `Frame` with explicit `extended`, `remote`, `brs`, `esi`, and `direction` fields. Reusing old `FrameEvent.flags` would leak old-project shape into the new architecture.
  Date/Author: 2026-04-29 / Codex.

- Decision: Do not support BLF in this ExecPlan.
  Rationale: The user explicitly said BLF parsing is not needed right now. Keeping ASC-only avoids new dependencies and keeps the migration focused.
  Date/Author: 2026-04-29 / Codex with user direction.

- Decision: Do not preserve JSON cache compatibility.
  Rationale: The user deleted the old `.replay_tool` workspace and explicitly does not need compatibility. The implementation can remove JSON cache helpers from the runtime path and require binary cache for managed traces.
  Date/Author: 2026-04-29 / Codex with user direction.

- Decision: Store summaries in SQLite metadata, not as separate summary tables in this milestone.
  Rationale: The current schema already stores `metadata_json`; using it keeps the migration small while still supporting CLI inspect.
  Date/Author: 2026-04-29 / Codex.

## Outcomes & Retrospective

Implemented. Trace imports now write `.frames.bin` binary caches using `src/replay_tool/storage/binary_cache.py`; legacy `.frames.json` cache paths fail clearly with a re-import message. `TraceStore.load_frames()` accepts optional source filters and timestamp windows, and `iter_frames()` streams from the binary cache. The app and CLI expose explicit `rebuild-cache` and `delete-trace` operations.

Automated validation passed with 27 unit tests. Final CLI validation in a system temp workspace imported `examples/sample.asc`, listed it, inspected source/message summaries, rebuilt the binary cache, deleted the trace and managed files, and then listed an empty library. BLF remains unsupported by design in this plan.

## Context and Orientation

`next_replay` is a new project under `C:\code\next_replay`. It must not import code from the old `C:\code\replay\src\replay_platform` package. The Trace Library implementation is in `src/replay_tool/storage/trace_store.py`, with binary cache encoding in `src/replay_tool/storage/binary_cache.py`. `SqliteTraceStore` owns imported trace metadata, `ManagedTraceReader` reads raw ASC files or managed binary caches, and summary builders keep source/message information in SQLite metadata. The ASC parser is in `src/replay_tool/storage/asc.py` and returns `list[Frame]`. The public trace-store protocol and result dataclasses are in `src/replay_tool/ports/trace_store.py`. The app layer calls this store from `src/replay_tool/app/service.py`, and CLI commands are in `src/replay_tool/cli.py`.

A trace is an imported bus recording file. A cache is a normalized copy of parsed frames written under `.replay_tool/cache/` so replay does not have to parse the original ASC every time. A source filter means a set of `(source_channel, bus)` pairs, such as `(0, CANFD)`, used to load only frames relevant to one scenario binding. A time window means `start_ns <= frame.ts_ns < end_ns`, used by future runtime/UI work to avoid loading an entire long trace.

Current behavior that must remain compatible:

- `replay-tool import examples/sample.asc` imports ASC traces.
- `replay-tool traces` lists imported traces.
- `replay-tool inspect <trace-id>` prints source and message summaries.
- A schema v1 scenario can set `traces[].path` to an imported trace id, and `ReplayApplication.compile_plan()` resolves it to the cache path.
- Direct scenario paths to ASC files still work.

## Plan of Work

First, capture baseline behavior. Run compile, all unit tests, and the CLI import/list/inspect/run flow against `examples/sample.asc`. Record the output in this ExecPlan before code changes.

Next, add an ASC-only binary cache module, for example `src/replay_tool/storage/binary_cache.py`. Define constants such as `BINARY_CACHE_FORMAT = "binary-v1"` and `BINARY_CACHE_SUFFIX = ".frames.bin"`. The file format must include a fixed header with magic, version, and frame count, then length-prefixed frame records. Each record must encode every `Frame` field needed for replay: timestamp, bus, channel, message id, payload, DLC, extended, remote, BRS, ESI, direction, and source file. Provide `write_binary_frame_cache(path, frames)`, `iter_binary_frame_cache(path, source_filters=None, start_ns=None, end_ns=None)`, and `read_binary_frame_cache(path, **filters)` functions. The iterator must skip non-matching source filters and time windows while reading, without building a full list first.

Then update `ManagedTraceReader`. It should read binary caches by suffix and still parse raw `.asc` files. It must not read legacy `.frames.json` caches. If asked to read a JSON cache path, raise a clear `ValueError` explaining that JSON trace caches are unsupported and the trace must be re-imported. It should not parse `.blf` or claim BLF support. Add an `iter(path, source_filters=None, start_ns=None, end_ns=None)` style method only if it is useful to avoid duplicating binary iteration logic; keep `read(path)` for existing planner compatibility.

Next, update `SqliteTraceStore`. New imports should write binary cache files and set `TraceRecord.cache_path` to that binary file. Metadata should include `cache_format`, `source_summaries`, and `message_summaries`. Add public methods to the `TraceStore` protocol and implementation:

    load_frames(trace_id, source_filters=None, start_ns=None, end_ns=None) -> list[Frame]
    iter_frames(trace_id, source_filters=None, start_ns=None, end_ns=None) -> Iterator[Frame]
    rebuild_cache(trace_id) -> TraceRecord
    delete_trace(trace_id) -> DeleteTraceResult

`load_frames()` should continue to work with only a `trace_id` argument. If a record points at an old JSON cache, the store should fail clearly instead of reading it. Because the old `.replay_tool` workspace has been deleted, no automatic JSON migration path is required. `delete_trace()` should delete the copied library file and cache file if present, remove the SQLite row, and return a small dataclass indicating which files were removed.

Then update the app and CLI with minimal commands needed to demonstrate the behavior. Existing commands must keep their output stable except cache file suffixes. Add `replay-tool rebuild-cache <trace-id>` and `replay-tool delete-trace <trace-id>` only if the implementation adds the corresponding app methods; otherwise leave CLI unchanged and prove the behavior through tests. Do not add scenario library storage, schema v2, UI, BLF, DBC, ZLG, or diagnostics in this plan.

Finally, update tests and docs. Tests must cover binary cache round trip, source filtering, time-window filtering, JSON cache rejection, import/list/inspect/run through binary cache, cache rebuild from raw copied ASC, and delete behavior. Update `docs/architecture-design-guide.md` and `docs/testing.md` to say Trace Library v2 uses ASC binary cache and does not yet support BLF.

## Concrete Steps

Run from `C:\code\next_replay`.

Baseline commands:

    $env:PYTHONPYCACHEPREFIX=(Join-Path $PWD ".pycache_tmp_compile")
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m compileall src tests

    $env:PYTHONDONTWRITEBYTECODE='1'
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m unittest discover -s tests -v

    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("next_replay_trace_v2_probe_" + [System.Guid]::NewGuid().ToString("N"))
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m replay_tool.cli import --workspace $tmp examples/sample.asc
    python -m replay_tool.cli traces --workspace $tmp

After implementation, run:

    $env:PYTHONPYCACHEPREFIX=(Join-Path $PWD ".pycache_tmp_compile")
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m compileall src tests

    $env:PYTHONDONTWRITEBYTECODE='1'
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m unittest discover -s tests -v

    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("next_replay_trace_v2_probe_" + [System.Guid]::NewGuid().ToString("N"))
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m replay_tool.cli import --workspace $tmp examples/sample.asc
    python -m replay_tool.cli traces --workspace $tmp
    python -m replay_tool.cli inspect --workspace $tmp <trace-id>

Replace `<trace-id>` with the ID printed by the import command. If the CLI adds rebuild/delete commands, also run:

    python -m replay_tool.cli rebuild-cache --workspace $tmp <trace-id>
    python -m replay_tool.cli delete-trace --workspace $tmp <trace-id>

## Validation and Acceptance

Automated acceptance:

- `python -m compileall src tests` succeeds.
- `python -m unittest discover -s tests -v` succeeds.
- New binary cache round-trip tests prove every `Frame` field survives write/read.
- Source-filter tests prove only requested `(channel, bus)` pairs are returned.
- Time-window tests prove `start_ns` inclusive and `end_ns` exclusive behavior.
- Import tests prove new `TraceRecord.cache_path` ends with `.frames.bin` and metadata contains `cache_format: binary-v1`.
- Existing scenario-by-trace-id compile/run tests still pass.
- JSON cache rejection tests prove old `.frames.json` cache files are not treated as supported managed caches.
- Delete tests prove SQLite row, copied trace, and cache are removed idempotently enough for a missing file to be reported rather than crashing.

CLI acceptance:

- `replay-tool import examples/sample.asc` prints `IMPORTED` and a binary cache path.
- `replay-tool traces` still lists the trace.
- `replay-tool inspect <trace-id>` still prints `SOURCES` and `MESSAGES`.
- No CLI or docs claim BLF is supported.

## Idempotence and Recovery

The implementation must not mutate imported traces during ordinary reads. If a workspace has JSON caches, reads should fail clearly and instruct the user to re-import. Cache rebuild is explicit through `rebuild_cache(trace_id)` or a CLI command if added. Deleting a trace must only remove files inside the configured Trace Library workspace paths recorded for that trace; do not delete arbitrary paths outside the workspace unless the path is the copied library file or cache path recorded in SQLite.

Temporary CLI probes should use a unique directory under `[System.IO.Path]::GetTempPath()` and remove it before or after validation. In this Codex desktop environment, creating SQLite workspaces directly under `C:\code\next_replay` has repeatedly produced `sqlite3.OperationalError: disk I/O error`, while system temp workspaces succeed. Do not treat that local probe issue as a Trace Library cache-format failure.

## Artifacts and Notes

Baseline and final command transcripts should be added here during implementation. Keep transcripts short: test count, import output, inspect output, and any cache suffix evidence are enough.

Baseline transcript:

    python -m compileall src tests
    Listing 'src'...
    Listing 'tests'...

    python -m unittest discover -s tests -v
    Ran 21 tests in 0.186s
    OK

    python -m replay_tool.cli import --workspace <system-temp> examples/sample.asc
    IMPORTED: id=1339ce45108c48dcab77b8c39f2ecd30 name=sample.asc frames=2 cache=...\1339ce45108c48dcab77b8c39f2ecd30.frames.json

    python -m replay_tool.cli traces --workspace <system-temp>
    1339ce45108c48dcab77b8c39f2ecd30 sample.asc frames=2 start_ns=0 end_ns=1000000

Final transcript:

    python -m compileall src tests
    Listing 'src'...
    Listing 'tests'...

    python -m unittest discover -s tests -v
    Ran 27 tests in 0.278s
    OK

    python -m replay_tool.cli import --workspace <system-temp> examples/sample.asc
    IMPORTED: id=fcd988cb739440a0a3b9afed72acde3b name=sample.asc frames=2 cache=...\fcd988cb739440a0a3b9afed72acde3b.frames.bin

    python -m replay_tool.cli traces --workspace <system-temp>
    fcd988cb739440a0a3b9afed72acde3b sample.asc frames=2 start_ns=0 end_ns=1000000

    python -m replay_tool.cli inspect --workspace <system-temp> fcd988cb739440a0a3b9afed72acde3b
    SOURCES:
      CH0 CAN frames=1
      CH0 CANFD frames=1
    MESSAGES:
      CH0 CAN frames=1 ids=0x123
      CH0 CANFD frames=1 ids=0x18DAF110

    python -m replay_tool.cli rebuild-cache --workspace <system-temp> fcd988cb739440a0a3b9afed72acde3b
    REBUILT: id=fcd988cb739440a0a3b9afed72acde3b name=sample.asc frames=2 cache=...\fcd988cb739440a0a3b9afed72acde3b.frames.bin

    python -m replay_tool.cli delete-trace --workspace <system-temp> fcd988cb739440a0a3b9afed72acde3b
    DELETED: id=fcd988cb739440a0a3b9afed72acde3b name=sample.asc library_file=True cache_file=True

    python -m replay_tool.cli traces --workspace <system-temp>
    No traces.

## Interfaces and Dependencies

Public interfaces to preserve:

- `ReplayApplication.import_trace()`, `list_traces()`, `inspect_trace()`, and compile-by-imported-trace-id behavior.
- `TraceStore.load_frames(trace_id)` with no filters.
- CLI commands `import`, `traces`, and `inspect`.

Public interfaces to add or extend:

- `TraceStore.load_frames(trace_id, source_filters=None, start_ns=None, end_ns=None)`.
- `TraceStore.iter_frames(trace_id, source_filters=None, start_ns=None, end_ns=None)`.
- `TraceStore.rebuild_cache(trace_id) -> TraceRecord`.
- `TraceStore.delete_trace(trace_id) -> DeleteTraceResult`.
- `ManagedTraceReader.read(path)` remains, and may gain an iterator/filter method if needed.

Dependencies:

- Use only the Python standard library for this milestone: `struct`, `json`, `sqlite3`, `pathlib`, and existing project modules.
- Do not add `python-can`, `cantools`, PySide6, or BLF support in this plan.

Revision note: Created initial ExecPlan for ASC-only Trace Library v2 binary cache and window reading. BLF support is explicitly excluded by user request.

Revision note: Updated by user direction to remove old JSON cache compatibility because the old `.replay_tool` workspace has already been deleted.

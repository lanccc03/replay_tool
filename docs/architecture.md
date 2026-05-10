# next_replay Architecture

This document covers cross-cutting concerns that require reading multiple source files to understand. For the high-level layer map, see `CLAUDE.md`.

## Binary cache format (`.frames.bin`)

The trace library caches imported ASC traces as binary files for fast, seekable replay. The format is defined in `src/replay_tool/storage/binary_cache.py`.

**File layout:**

```
[Header: 14 bytes]       magic="NRPLBIN1" (8B), version=1 (2B u16), record_count (4B u32)
[Record 0]               [length: 4B u32][record body: variable]
[Record 1]               ...
```

**Record body encoding:**

| Field | Type | Size |
|-------|------|------|
| ts_ns | i64 (signed) | 8 |
| bus_type | u8 (CAN=1, CANFD=2) | 1 |
| channel | i32 | 4 |
| message_id | u32 | 4 |
| dlc | u16 | 2 |
| flags | u8 (ext/remote/brs/esi bits) | 1 |
| payload_len | u32 | 4 |
| direction_len | u32 | 4 |
| source_len | u32 | 4 |
| payload | bytes | payload_len |
| direction | UTF-8 | direction_len |
| source_file | UTF-8 | source_len |

**Block index:** The `SqliteTraceStore` maintains a per-trace `trace_frame_index` table in SQLite (`library.sqlite3`). Each entry records `(block_number, file_offset, start_ns, end_ns, frame_count, sources_json)` for a contiguous block of up to 4096 frames. During replay, the index is used to seek directly to relevant blocks, skipping frames that fall outside the requested source filters or time range — avoiding a full linear scan.

Index entries are built during import and stored as JSON metadata. If the index is missing (e.g., migrated from older cache), it is rebuilt on first access via `build_binary_frame_cache_index()`.

## Runtime scheduling algorithm

The runtime dispatches frames from multiple trace sources while preserving inter-source timestamp ordering. The logic spans three files in `src/replay_tool/runtime/`.

**MergedTimelineCursor** (`timeline.py`):
- Opens a `SourceFrameCursor` per `PlannedFrameSource`, each backed by a `TraceStore.iter_frames()` iterator.
- Uses a min-heap keyed by `(ts_ns, sequence)` to merge frames from all sources into a single timestamp-ordered stream.
- `read_batch(window_ns=2ms)` pops all frames whose timestamp falls within `[first_ts_ns, first_ts_ns + 2ms)`.

**TimelineScheduler** (`scheduler.py`):
- Binds a replay "time base" (`_base_perf_ns`) to `time.perf_counter_ns()` at start.
- For each batch, computes `target_perf_ns = base + batch[0].ts_ns`. If the system clock is ahead of target, it dispatches immediately; otherwise it sleeps in 2ms increments.
- On pause, records `_pause_started_ns`. On resume, adds the paused duration to `_base_perf_ns` so paused time does not count toward frame timing.
- Loop mode rewinds all cursors and resets the time base.

**FrameDispatcher** (`dispatcher.py`):
- Groups logical-channel frames by target device via `ReplayDeviceSession.route_frame()`.
- Dispatches each device's batch through `BusDevice.send()`, tracking accepted vs. skipped counts.

**Worker thread** (`kernel.py`):
- `ReplayRuntime._run_loop()` runs on a daemon thread, iterating batch → dispatch → advance until the cursor is exhausted or stop is requested.
- A `threading.Condition` coordinates pause (wait on condition) and stop (flag checked each iteration).

## Trace import lifecycle

When a trace enters the system, the flow crosses `SqliteTraceStore`, `AscTraceReader`, and `BinaryFrameCacheWriter`.

1. **Copy**: The source `.asc` file is copied to `<workspace>/traces/<trace_id>.asc`.
2. **Stream parse**: `AscTraceReader.iter()` reads the ASC line-by-line, parsing CAN and CANFD frames. It rejects out-of-order timestamps (the parser is streaming-only, no external sort).
3. **Binary encode**: Each frame is immediately written to a temporary `.frames.bin.tmp` via `BinaryFrameCacheWriter`. The writer accumulates block index entries (every 4096 frames).
4. **Summaries**: `_TraceSummaryBuilder` accumulates per-source frame counts, per-source start/end timestamps, and per-source message ID sets during streaming.
5. **Atomize**: On success, the temp file is renamed to `<workspace>/cache/<trace_id>.frames.bin`, the file header is patched with the final frame count. On failure, the temp file is deleted and the copied ASC is cleaned up.
6. **Store**: A `TraceRecord` row is inserted into `trace_files`, block index entries into `trace_frame_index`, and summaries into the record's `metadata_json` column.

**Cache rebuild** (`rebuild_cache`) re-runs steps 2–6 from the copied library ASC file, overwriting the existing `.frames.bin` and index entries. This is used when the cache is deleted or corrupted.

## Scenario resolution

When `ReplayApplication.compile_plan()` receives a scenario reference, it resolves trace paths in this order:

1. If the ref is a filesystem path that exists, load it as JSON and use its parent directory as `base_dir`.
2. Otherwise, look it up as a saved scenario ID in `SqliteProjectStore`.
3. For each `TraceConfig` in the scenario:
   - If the path is an absolute or relative file that exists on disk: auto-import as ASC (or reuse an existing import), then return the cache path.
   - If the path is a `.frames.bin` file: validate it is managed by the trace library.
   - If the path is neither: try it as a trace ID in `SqliteTraceStore`.
4. The scenario's trace paths are replaced with resolved cache paths before being passed to `ReplayPlanner.compile()`.

This means a scenario can reference a raw `.asc` file by relative path, and the app layer transparently imports and caches it. The `ReplayPlanner` only sees cache-backed sources.

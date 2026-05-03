# Delete ManagedTraceReader and Require Cache-Backed Runtime Sources

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows `.agents/PLANS.md` from the repository root.

## Purpose / Big Picture

The replay tool already imports raw Vector ASC trace files into managed `.frames.bin` binary caches before normal CLI validation and replay. This work makes that architecture explicit in code: ASC parsing is only an import and cache rebuild concern, while runtime replay reads frames only through the Trace Library cache API. After the change, an engineer cannot accidentally construct a runtime plan that streams raw `.asc` files directly.

## Progress

- [x] (2026-05-03) Investigated current `ManagedTraceReader`, `SqliteTraceStore`, `ReplayRuntime`, and tests.
- [x] (2026-05-03) Decided to delete `ManagedTraceReader` while keeping `AscTraceReader` as the ASC import parser.
- [x] (2026-05-03) Removed `ManagedTraceReader` and the old path-based `TraceReader` port from production code.
- [x] (2026-05-03) Made `SqliteTraceStore` read `.frames.bin` caches directly and use `AscTraceReader` only for import/rebuild.
- [x] (2026-05-03) Made `ReplayRuntime` require `TraceStore` and reject planned sources without `library_trace_id`.
- [x] (2026-05-03) Updated tests and docs for the stricter cache-only runtime boundary.
- [x] (2026-05-03) Ran ruff, compileall, and unittest validation.

## Surprises & Discoveries

- Observation: `SqliteTraceStore.import_trace()` already uses the ASC parser only to write binary caches, but it reached it through `ManagedTraceReader.asc_reader`.
  Evidence: `src/replay_tool/storage/trace_store.py` called `self.trace_reader.asc_reader.iter(...)` in `_write_cache_from_asc`.
- Observation: The normal application path already prepares cache-backed plans, but runtime still allowed direct path-based reading through a `TraceReader` fallback.
  Evidence: `src/replay_tool/runtime/timeline.py` fell back to `self.trace_reader.iter(source.path, ...)`.

## Decision Log

- Decision: Delete `ManagedTraceReader` rather than keep a cache-only wrapper.
  Rationale: Once ASC reading is import-only, the wrapper would only check a suffix and delegate to `iter_binary_frame_cache()`, adding ambiguity without useful behavior.
  Date/Author: 2026-05-03 / Codex
- Decision: Keep `AscTraceReader`.
  Rationale: ASC is still the MVP source format. Keeping a dedicated streaming parser keeps `SqliteTraceStore` focused on library metadata, cache files, and indexes.
  Date/Author: 2026-05-03 / Codex
- Decision: Runtime planned sources must include `library_trace_id`.
  Rationale: A non-empty library trace ID proves the source was resolved through Trace Library import/reuse and can be loaded through `TraceStore.iter_frames()`.
  Date/Author: 2026-05-03 / Codex

## Outcomes & Retrospective

The implementation removed the path-based runtime reader and made cache-backed Trace Library sources mandatory for replay. CLI scenarios can still name raw `.asc` files because `ReplayApplication` imports or reuses `.frames.bin` caches before planning. The test suite now covers the new negative case where a runtime plan lacks `library_trace_id`.

## Context and Orientation

`src/replay_tool/storage/asc.py` contains `AscTraceReader`, a streaming parser for Vector ASC text traces. `src/replay_tool/storage/trace_store.py` contains `SqliteTraceStore`, which copies ASC files into `.replay_tool/traces`, writes normalized `.frames.bin` binary caches, stores metadata in SQLite, and reads imported frames. `src/replay_tool/runtime/kernel.py` and `src/replay_tool/runtime/timeline.py` execute `ReplayPlan` frame sources. `library_trace_id` is the Trace Library identifier stored on each `PlannedFrameSource` when `ReplayApplication.compile_plan()` has resolved a scenario trace to an imported cache.

Before this change, `ManagedTraceReader` could read either raw `.asc` or `.frames.bin` paths, and runtime could use that reader as a fallback. After this change, runtime must not have any raw path reader. It must read only through `TraceStore.iter_frames(trace_id, source_filters=...)`.

## Plan of Work

Remove `src/replay_tool/storage/managed_reader.py` and remove `ManagedTraceReader` from `src/replay_tool/storage/__init__.py`. Update `SqliteTraceStore` so its constructor accepts only an optional `AscTraceReader`, uses that parser in `_write_cache_from_asc`, validates that stored cache paths end in `.frames.bin`, and falls back to `iter_binary_frame_cache()` when no block index is available.

Remove `src/replay_tool/ports/trace.py` and remove `TraceReader` from `src/replay_tool/ports/__init__.py`. Update `ReplayRuntime` so its constructor requires `trace_store: TraceStore`, no longer stores `trace_reader`, and configures `PlannedSourceReader(self.trace_store)`. Update `PlannedSourceReader` so it rejects sources with an empty `library_trace_id`.

Update `ReplayApplication` so it no longer creates a `ManagedTraceReader`; it creates `SqliteTraceStore(self.workspace)` and passes only `trace_store` into `ReplayRuntime`. Update tests to use fake `TraceStore` implementations for runtime behavior and to inject a spy `AscTraceReader` into `SqliteTraceStore` for import/rebuild streaming assertions.

## Concrete Steps

Run all commands from `/Users/lanyy/Code/replay_tool`.

After edits, run:

    uv run ruff check --fix src tests
    PYTHONPYCACHEPREFIX=/private/tmp/replay_tool_pycache_compile PYTHONPATH=src uv run python -m compileall src tests
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run python -m unittest discover -s tests -v

If ruff edits files, rerun compileall and unittest after those edits.

## Validation and Acceptance

The change is accepted when the test suite passes and the runtime tests prove that successful plans use `TraceStore.iter_frames()` with non-empty `library_trace_id`, while a plan without `library_trace_id` fails during `ReplayRuntime.configure()`. The CLI tests must still show that a scenario pointing at `.asc` validates and runs, proving `ReplayApplication` imports or reuses the binary cache before runtime execution.

## Idempotence and Recovery

All source edits are normal text changes and can be repeated safely. The validation commands may create Python cache files under `/private/tmp` or test temporary directories; they do not require manual cleanup. If a test fails after a partial edit, inspect the failing import or constructor call and update it to the cache-only runtime API rather than reintroducing `TraceReader`.

## Artifacts and Notes

Validation evidence:

    uv run ruff check --fix src tests
    All checks passed!

    PYTHONPYCACHEPREFIX=/private/tmp/replay_tool_pycache_compile PYTHONPATH=src uv run python -m compileall src tests
    ... Compiling changed modules under src/replay_tool and tests ...

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run python -m unittest discover -s tests -v
    Ran 39 tests in 0.179s
    OK

## Interfaces and Dependencies

At completion, `ReplayRuntime.__init__` accepts `trace_store: TraceStore` and no `trace_reader`. `SqliteTraceStore.__init__` accepts `root: str | Path` and optional `asc_reader: AscTraceReader | None`. `replay_tool.storage.AscTraceReader` remains exported. `replay_tool.storage.ManagedTraceReader` and `replay_tool.ports.TraceReader` no longer exist.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                                              # Install dependencies
uv run ruff check src tests                          # Lint
uv run python -m compileall src tests                # Syntax check
uv run python -m unittest discover -s tests -v       # Run all tests
uv run python -m unittest tests.test_ui_views -v     # Run a single test module
uv run replay-ui --help                              # Smoke test the UI entry point
```

## Architecture

Hexagonal (ports-and-adapters) monolith with a PySide6 Qt workbench. Dependency direction:

```
CLI / PySide6 UI → app → planning + runtime + domain → ports (interfaces only)
adapters → ports + domain
storage  → ports + domain
```

### Layers

| Layer        | Path                               | Role                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------------ | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **domain**   | `src/replay_tool/domain/model.py`  | Pure dataclasses: `Frame`, `ReplayScenario`, `DeviceConfig`, `ReplayRoute`, `ReplayPlan`, etc. No file I/O, no Qt, no TSMaster.                                                                                                                                                                                                                                                                                                        |
| **ports**    | `src/replay_tool/ports/`           | Abstract interfaces as `Protocol` classes: `BusDevice`, `TraceStore`, `ProjectStore`. `DeviceRegistry` is a factory that maps driver names to adapter constructors.                                                                                                                                                                                                                                                                    |
| **planning** | `src/replay_tool/planning/plan.py` | `ReplayPlanner.compile()` converts a validated `ReplayScenario` into an executable `ReplayPlan` with resolved trace references and timing metadata.                                                                                                                                                                                                                                                                                    |
| **runtime**  | `src/replay_tool/runtime/`         | Executes a `ReplayPlan` on a background thread. `ReplayRuntime` (kernel) owns the worker thread and delegates to `TimelineScheduler`, `MergedTimelineCursor`, `FrameDispatcher`, `ReplayDeviceSession`, and `RuntimeTelemetry`.                                                                                                                                                                                                        |
| **adapters** | `src/replay_tool/adapters/`        | `MockDevice` (in-memory, for tests) and `TongxingDevice` (Windows-only, wraps TSMaster SDK via `importlib`). Both implement the `BusDevice` protocol.                                                                                                                                                                                                                                                                                  |
| **storage**  | `src/replay_tool/storage/`         | `SqliteTraceStore` manages trace imports, binary caches (`.frames.bin`), and a frame index for seek-optimized replay. `SqliteProjectStore` persists scenario records. `AscTraceReader` is the streaming ASC parser. Both stores share `library.sqlite3` in the workspace.                                                                                                                                                              |
| **app**      | `src/replay_tool/app/service.py`   | `ReplayApplication` is the facade shared by CLI and UI. It wires together the registry, stores, planner, and runtime for all use cases (validate, run, import, inspect, save-scenario, etc.).                                                                                                                                                                                                                                          |
| **UI**       | `src/replay_ui_qt/`                | PySide6 MVVM workbench. `MainWindow` has four pages: Trace Library, Scenarios, Replay Monitor, Devices. Layout: top status bar, left navigation, center workspace, right inspector panel. Views (`views/`) own Qt widgets; ViewModels (`view_models/`) own state and commands; `AppContext` holds the shared `ReplayApplication` and `TaskRunner`. `TaskRunner` offloads blocking calls to `QThreadPool` with duplicate-name guarding. |

### Key data flow

1. User provides a schema v2 scenario JSON (or saves one via the UI).
2. `ReplayApplication` loads it, resolves trace paths through `TraceStore` (auto-importing ASC files and building `.frames.bin` caches as needed), and calls `ReplayPlanner.compile()`.
3. `ReplayRuntime` is configured with the `ReplayPlan`, then started on a daemon thread.
4. The runtime merges trace source cursors via a min-heap (`MergedTimelineCursor`), groups frames into 2ms scheduling windows (`TimelineScheduler`), routes logical channels to physical device channels (`ReplayDeviceSession`), and dispatches frames grouped by device (`FrameDispatcher`).
5. Telemetry snapshots (`ReplayRuntime.snapshot()`) are polled by the CLI or UI for progress.

Only schema v2 scenarios are supported. Trace replay reads from `.frames.bin` binary caches backed by the Trace Library; raw ASC parsing happens only at import/cache-rebuild time.

## Boundaries

- **Domain is pure**: no filesystem, SQLite, TSMaster, or Qt imports in `domain/`.
- **UI never touches hardware directly**: views and viewmodels call `ReplayApplication`, never import adapters or manipulate `ReplayRuntime` internals.
- **Runtime is plan-only**: the runtime consumes `ReplayPlan`, never re-interprets raw `ReplayScenario`.
- **Test framework is `unittest`** (not pytest). Tests use `MockDevice` and fake TSMaster API — mock/fake test passes do not equal Windows hardware validation.
- **Tongxing adapter is Windows-only**: the SDK is loaded from `TSMaster/Windows/` at runtime via `importlib`. Hardware validation must be done manually on a Windows machine with a connected TC1014 device.
- **ASC import requires monotonic timestamps**: the streaming parser rejects out-of-order frames.

## Code conventions

- Every public class has a class-level docstring; every public function/method has Google-style docstring (Args, Returns, Raises).
- Source files are UTF-8 without BOM.
- Use `from __future__ import annotations` in all modules.
- Ruff line length: 120.
- Commit style: conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).
- Complex features require an ExecPlan (see `.agents/PLANS.md`).
- **UI work**: invoke `tool-ui-style` skill (team shared baseline), then read `docs/ui.md` for project-specific rules and priority hierarchy.

## Further reading

- `docs/architecture.md` — binary cache format, runtime scheduling algorithm, trace import lifecycle, scenario resolution
- `docs/ui.md` — PySide6 MVVM architecture, domain component rules, and state language conventions
- `docs/testing.md` — test map, layering strategy (6 layers from pure domain to offscreen Qt), and validation boundaries

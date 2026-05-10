# next_replay Testing

## Running tests

```bash
uv run python -m unittest discover -s tests -v       # All tests
uv run python -m unittest tests.test_ui_views -v     # Single module
uv run python -m compileall src tests                # Syntax check
uv run ruff check src tests                          # Lint
```

All commands assume the repo root as working directory.

## Test map

| File | Covers |
|------|--------|
| `tests/test_scenario_and_planner.py` | Schema v2 parsing, validation, cross-reference checks, planner compilation |
| `tests/test_runtime.py` | ReplayRuntime worker thread, scheduler, cursor merge, pause/resume/stop, loop mode |
| `tests/test_cli.py` | CLI arg parsing, output formatting, end-to-end validate/run/import flows |
| `tests/test_trace_store.py` | ASC streaming import, `.frames.bin` binary cache, block index, source filters, time-window reads, cache rebuild, trace delete |
| `tests/test_project_store.py` | Scenario save, update, list, get, delete, base_dir persistence, compile/run by saved ID |
| `tests/test_tongxing_adapter.py` | Tongxing adapter with fake TSMaster API (no hardware) |
| `tests/test_ui_smoke.py` | Offscreen main window creation, navigation count, inspector content, status bar |
| `tests/test_ui_views.py` | Trace Library and Scenario editor views through `ReplayApplication` |
| `tests/test_ui_view_models.py` | ViewModel state mapping and command bindings |
| `tests/test_ui_tasks.py` | `TaskRunner` async framework, duplicate guarding, success/failure signals |
| `tests/test_ui_widgets.py` | Standalone widget rendering and behavior |

## Test layering strategy

### Layer 1: Pure domain and planner (fast, no I/O)

`test_scenario_and_planner.py` tests `ReplayScenario.from_dict()` validation and `ReplayPlanner.compile()` with in-memory trace records. No filesystem, no devices.

### Layer 2: Storage with real filesystem (medium)

`test_trace_store.py` and `test_project_store.py` use `tempfile.TemporaryDirectory` for workspace directories. They test real ASC parsing against example files in `examples/`, binary cache encode/decode, and SQLite CRUD. A `SpyAscReader` asserts that streaming paths never fall back to full-list reads.

### Layer 3: Runtime with mock devices (medium)

`test_runtime.py` uses `ManualClock` (fake monotonic time) and `RecordingDevice` (subclass of `MockDevice` that records sent batches). This allows deterministic testing of scheduler timing, loop restart, pause/resume accounting, and partial-send scenarios.

### Layer 4: CLI integration (end-to-end)

`test_cli.py` runs `main(argv)` with temporary workspaces, capturing stdout/stderr. Validates the full pipeline: import ASC → validate scenario → run → output format.

### Layer 5: Adapter with fake SDK (Windows-only API, cross-platform tests)

`test_tongxing_adapter.py` patches `importlib.import_module` to inject a fake `TSMasterAPI` module. Tests adapter construction, channel enumeration, and send/receive without real hardware.

### Layer 6: UI (offscreen Qt)

UI tests use `QT_QPA_PLATFORM=offscreen` (no display required). Smoke tests create the full `MainWindow` with a real `ReplayApplication` and temporary workspace. View tests exercise individual pages with app-layer backing. ViewModel tests unit-test state transitions and command bindings with stubbed app calls.

## Validation boundaries

- **Mock/Fake test passes do not equal hardware validation.** The `MockDevice` and fake TSMaster API exercises code paths but cannot verify electrical behavior, timing accuracy, or real CAN bus interaction.
- **Tongxing TC1014 validation is manual, Windows-only**, and must be recorded per `docs/tongxing-hardware-validation.md`.
- **Offscreen UI tests do not verify real window behavior**, high DPI rendering, or native click/drag interaction.
- The current codebase only supports ASC traces (`schema_version=2`). BLF, DBC, DoIP, ZLG, Signal Override, and Diagnostics are not implemented.

# Close Out UI M4 Replay Monitor and M5 Devices

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document follows `.agents/PLANS.md` from the repository root. It is intentionally self-contained so a new contributor can continue the UI closeout without relying on prior chat context.

## Purpose / Big Picture

The PySide6 workbench already lets users edit schema v2 scenarios, start mock replay sessions, watch snapshots in Replay Monitor, and enumerate devices through the application layer. This closeout turns those first batches into milestone-quality M4 and M5 evidence. After the work, a developer can prove with automated tests that the UI ViewModels use the real `ReplayApplication` mock paths for replay and device enumeration, while the documentation clearly keeps Windows hardware UI clicks, real window checks, and high DPI checks outside the automated claim.

## Progress

- [x] (2026-05-09 15:30+08:00) Read the UI roadmap, architecture guide, testing guide, app service, replay session ViewModel, devices ViewModel, scenario ViewModel, and existing UI tests.
- [x] (2026-05-09 15:40+08:00) Create this ExecPlan for the M4/M5 closeout.
- [x] (2026-05-09 16:05+08:00) Add real `ReplayApplication` integration coverage for `ReplaySessionViewModel` using an imported ASC trace and mock device replay.
- [x] (2026-05-09 16:05+08:00) Add real `ReplayApplication` integration coverage for `DevicesViewModel` using the mock device driver.
- [x] (2026-05-09 16:15+08:00) Update UI, architecture, testing, and hardware validation docs to record the M4/M5 closeout and remaining manual validation boundaries.
- [x] (2026-05-09 16:35+08:00) Run required automated validation commands and record the outcomes.

## Surprises & Discoveries

- Observation: `ReplayApplication.start_replay_session_from_body()` already starts a real `ReplayRuntime` and returns only the app-layer `ReplaySession` handle, so the UI integration test can prove the boundary without importing runtime internals in UI code.
  Evidence: `src/replay_tool/app/service.py` constructs `ReplayRuntime`, wraps it in `ReplaySession`, starts it, and returns the handle.
- Observation: `MockDevice.health()` reports online state but per-channel health only for started channels. During device enumeration no channels are started, so channel rows are present but display `Unknown`.
  Evidence: `src/replay_tool/adapters/mock/device.py` builds `per_channel` from `started_channels`, while `ReplayApplication.enumerate_device()` only opens, enumerates, reads capabilities and health, then closes.

## Decision Log

- Decision: Close M4 and M5 as `Done` for mock/app-layer automated evidence, while keeping real window clicking, high DPI, and Windows TC1014 UI hardware verification as explicit M8/manual validation items.
  Rationale: The roadmap status definition allows Done with automated evidence. Hardware UI validation cannot be replaced by offscreen tests and should not block the mock/app-layer milestone claim.
  Date/Author: 2026-05-09 / Codex.
- Decision: Add tests to `tests/test_ui_view_models.py` instead of changing production UI code.
  Rationale: The existing app-layer and ViewModel interfaces already support the desired behavior; the closeout needs stronger evidence, not new public APIs.
  Date/Author: 2026-05-09 / Codex.
- Decision: Do not enable Signal Override, Diagnostics, BLF, ZLG, DoIP, or Settings productization in this plan.
  Rationale: Signal Override and Diagnostics are blocked by core ports/planner/runtime work, and Settings productization belongs to M8 after the M2-M5 workflow closeout.
  Date/Author: 2026-05-09 / Codex.

## Outcomes & Retrospective

M4 and M5 are closed for automated mock/application-layer UI evidence. Replay Monitor now has a real `ReplayApplication + ReplaySessionViewModel` test that imports `examples/sample.asc`, starts a mock replay session from a schema v2 body, waits for completion, checks final counters, and verifies the editor lock is released. Devices now has a real `ReplayApplication + DevicesViewModel` test that enumerates the mock driver and verifies device info, capabilities, health, and channel rows. Documentation now records the distinction between automated mock coverage and unverified real window/high DPI/TC1014 UI workflows.

Manual Windows UI verification remains unperformed in this closeout. The hardware validation document now contains the steps and record fields for Devices UI enumeration and Scenario-to-Replay Monitor hardware replay, but no new TC1014 UI result is claimed.

## Context and Orientation

The project root is `C:\code\next_replay`. The UI package is `src/replay_ui_qt`. The application facade used by CLI and UI is `src/replay_tool/app/service.py`. A ViewModel is the UI state object that calls app-layer methods and exposes values to Qt widgets. A schema v2 scenario body is a dictionary with `traces`, `devices`, `sources`, `targets`, `routes`, and `timeline`; it is validated by `ReplayScenario.from_dict()` and compiled by `ReplayPlanner`.

M4 is the Replay Monitor milestone. Its key UI object is `ReplaySessionViewModel` in `src/replay_ui_qt/view_models/replay_session.py`. It starts replay through `ReplayApplication.start_replay_session_from_body()`, polls `ReplaySession.snapshot()`, and derives UI labels such as Running, Paused, Completed, and Failed.

M5 is the Devices milestone. Its key UI object is `DevicesViewModel` in `src/replay_ui_qt/view_models/devices.py`. It builds a `DeviceConfig` draft and calls `ReplayApplication.enumerate_device()`. UI code must not import `replay_tool.adapters.tongxing` directly.

## Plan of Work

Update `tests/test_ui_view_models.py` with two real app-layer tests. The replay test creates a temporary workspace, imports `examples/sample.asc` through `ReplayApplication.import_trace()`, inspects the imported trace to choose a real source channel and bus, builds a schema v2 body that targets the mock device, starts it through `ReplaySessionViewModel`, waits until the display state is Completed, and asserts counters and inactive editor lock. The failure test starts a real app-layer replay from a body whose trace cannot be resolved and asserts that the ViewModel reports an error, remains Stopped, and has no active session.

The device test creates a temporary workspace, instantiates a real `ReplayApplication`, selects the mock driver in `DevicesViewModel`, enumerates, and asserts that the mock device summary, capabilities, health, and channel rows are mapped into UI state.

Update `docs/ui-implementation-roadmap.md` so M3, M4, and M5 statuses match the code. M4 and M5 should be marked Done for automated mock/app evidence and should explicitly say real window clicking, high DPI, and Windows TC1014 UI verification remain unverified/manual.

Update `docs/architecture-design-guide.md` to remove stale language saying the Scenario Editor is only a read-only or in-progress UI base. Update `docs/testing.md` and `docs/tongxing-hardware-validation.md` to reflect the new automated evidence and manual hardware UI validation steps.

## Concrete Steps

From `C:\code\next_replay`, edit only test and documentation files. Do not change domain, planning, runtime, or app public APIs. Use the existing `examples/sample.asc` file and temporary workspaces for tests, so repeated test runs are safe.

After editing, run:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help
    git diff --check

Expected outcomes are no ruff violations, successful compileall, all unittest tests passing, `replay-ui --help` printing the CLI help, and no whitespace errors from `git diff --check`.

## Validation and Acceptance

Acceptance requires the new test `ReplaySessionViewModelTests.test_real_application_mock_replay_runs_to_completion_and_releases_active_lock` to pass. It demonstrates that the UI ViewModel can start a real app-layer mock replay from an imported trace and observe completion without touching runtime internals.

Acceptance also requires `ReplaySessionViewModelTests.test_real_application_start_failure_reports_error_and_unlocks_editor` to pass. It demonstrates that compile/start failure leaves the UI stopped and unlocked with a copyable error string.

Acceptance also requires `DevicesViewModelTests.test_real_application_mock_enumeration_maps_summary_capabilities_and_channels` to pass. It demonstrates that Devices UI state can be driven by the real app-layer mock driver enumeration path.

Manual acceptance for Windows hardware UI remains separate: use `docs/tongxing-hardware-validation.md` to record Devices UI enumeration, Scenario tongxing draft replay, real window clicking, and high DPI checks.

## Idempotence and Recovery

The automated tests use temporary directories and the checked-in `examples/sample.asc`, so they can be repeated without changing the developer workspace. If a test fails because `uv` cannot access its cache, retry with the environment's normal uv permissions or run the equivalent `python -m unittest` command with `PYTHONPATH=src`. Do not delete `.replay_tool` or hardware SDK files as part of this plan.

## Artifacts and Notes

Validation transcript from this closeout:

    uv run ruff check src tests
    All checks passed!

    uv run python -m compileall src tests
    ... completed successfully

    uv run python -m unittest discover -s tests -v
    Ran 134 tests in 3.989s
    OK

    uv run replay-ui --help
    usage: replay-ui [-h] [--workspace WORKSPACE]

    git diff --check
    ... exit code 0; Git reported LF-to-CRLF working-copy warnings only

## Interfaces and Dependencies

No public scenario schema, domain, planning, runtime, or app interface changes are introduced. The existing interfaces remain:

- `ReplayApplication.start_replay_session_from_body(body, base_dir=...) -> ReplaySession`
- `ReplaySession.pause()`, `ReplaySession.resume()`, `ReplaySession.stop()`, and `ReplaySession.snapshot()`
- `ReplayApplication.enumerate_device(config) -> DeviceEnumerationResult`
- `ReplayApplication.list_device_drivers() -> tuple[str, ...]`

The UI continues to call these methods through ViewModels. It must not import Tongxing or ZLG adapters directly and must not access `ReplayRuntime` internals.

Revision note, 2026-05-09: Created and completed this closeout ExecPlan because the UI roadmap needed M4/M5 automated evidence and documentation cleanup before M8 productization work can start.

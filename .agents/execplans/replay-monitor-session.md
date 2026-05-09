# M4 Replay Monitor Session API and UI First Batch

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds. It follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can create or load a schema v2 scenario in the Scenarios page, press Run, and watch a non-blocking replay session in Replay Monitor. The UI will show runtime snapshots, progress, counters, and errors, and it will offer Pause, Resume, and Stop controls without allowing the UI layer to operate on `ReplayRuntime` internals directly.

## Progress

- [x] (2026-05-09 10:40Z) Read the roadmap, current app service, runtime API, Scenarios UI, Replay Monitor placeholder, and existing UI tests.
- [x] (2026-05-09 10:45Z) Created this ExecPlan before implementation, as required for a cross-layer UI/app/runtime feature.
- [x] (2026-05-09 11:05Z) Added an app-layer replay session wrapper and non-blocking `ReplayApplication` API.
- [x] (2026-05-09 11:20Z) Replaced Replay Monitor placeholder state with a ViewModel-driven snapshot monitor.
- [x] (2026-05-09 11:30Z) Wired Scenarios Run to the shared replay session and locked edits while active.
- [x] (2026-05-09 11:45Z) Added app, ViewModel, view, and regression tests.
- [x] (2026-05-09 11:50Z) Updated `docs/ui-implementation-roadmap.md` with the M4 first batch status and validation boundaries.
- [x] (2026-05-09 12:00Z) Ran ruff, compileall, unittest discovery, `replay-ui --help`, and `git diff --check`.

## Surprises & Discoveries

- Observation: `ReplayRuntime` already has the necessary control surface for M4: `start`, `pause`, `resume`, `stop`, `wait`, and `snapshot`.
  Evidence: `src/replay_tool/runtime/kernel.py` exposes these methods and current runtime tests exercise pause/resume and loop behavior.
- Observation: The current `ReplayApplication.run()` is intentionally blocking because it calls `runtime.wait()`.
  Evidence: `src/replay_tool/app/service.py` compiles, configures, starts, waits, and returns the stopped runtime.

## Decision Log

- Decision: Keep runtime states unchanged and derive Completed / Failed in the UI ViewModel.
  Rationale: The plan explicitly says not to add `ReplayState.COMPLETED` or `ReplayState.FAILED`; existing runtime callers expect only STOPPED, RUNNING, and PAUSED.
  Date/Author: 2026-05-09 / Codex
- Decision: Add a thin app-layer `ReplaySession` wrapper instead of giving UI direct access to `ReplayRuntime`.
  Rationale: The UI architecture requires calls through application-layer APIs and forbids direct runtime internals access.
  Date/Author: 2026-05-09 / Codex
- Decision: Start sessions from Scenarios and monitor them in Replay Monitor; do not add an independent scenario selector to Replay Monitor in this batch.
  Rationale: This is the smallest observable M4 loop and matches the accepted plan.
  Date/Author: 2026-05-09 / Codex

## Outcomes & Retrospective

Completed. The app layer now exposes a non-blocking replay session API while preserving the existing blocking CLI run path. The Scenarios page can request Run for the current draft, MainWindow routes that request to a shared ReplaySessionViewModel, and Replay Monitor displays snapshot state, progress, counters, errors, Pause, Resume, and Stop. The implementation covers Mock/offscreen workflows only; real window clicking, high DPI, and Windows Tongxing hardware UI validation remain unverified.

## Context and Orientation

The app layer lives in `src/replay_tool/app/`. `ReplayApplication` is the stable facade used by CLI and UI. The runtime lives in `src/replay_tool/runtime/`; `ReplayRuntime` executes a compiled `ReplayPlan` on a background thread and reports immutable `ReplaySnapshot` values. The UI lives in `src/replay_ui_qt/`. `ScenariosViewModel` owns draft editing state, while the current `ReplaySessionViewModel` and `ReplayMonitorView` are placeholders.

The important boundary is that the UI may call `ReplayApplication` and app-layer session objects, but it must not import hardware adapters or directly operate on runtime internal fields.

## Plan of Work

First, add `src/replay_tool/app/session.py` with `ReplaySessionSummary` and `ReplaySession`. `ReplaySession` will wrap one configured `ReplayRuntime`, expose pause/resume/stop/wait/snapshot, remember whether it was started, and remember whether Stop was user-requested.

Next, update `ReplayApplication` with `start_replay_session_from_body(body, base_dir=".")`. This method will call `validate_scenario_body()` to reuse trace resolution and planning, configure a new runtime, start it, and return a `ReplaySession` without waiting.

Then, replace `ReplaySessionViewModel` with a real ViewModel that starts sessions through `TaskRunner`, polls snapshots with a `QTimer`, exposes progress and button state, and emits signals for views and the shell status bar. Failed and Completed are derived UI states.

Then, replace the Replay Monitor placeholder view with a real monitor page. It will render the ViewModel state, show progress and counters, expose Pause / Resume / Stop buttons, and provide an error details dialog.

Then, wire Scenarios Run through a new `runRequested` signal. `MainWindow` will create one shared `ReplaySessionViewModel`, connect Scenarios to it, switch to Replay Monitor on Run, and inform Scenarios whether replay is active so key editing controls are locked.

Finally, update tests and roadmap. The implementation must keep CLI `run()` blocking behavior unchanged.

## Concrete Steps

Work from `C:\code\next_replay`.

Run the implementation validation commands after edits:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help

Observed results on 2026-05-09:

    uv run ruff check src tests
    All checks passed!

    uv run python -m unittest discover -s tests -v
    Ran 118 tests in 4.467s
    OK

## Validation and Acceptance

Acceptance is achieved when a test can import `examples/sample.asc`, create a mock schema v2 draft, start a non-blocking session through `ReplayApplication.start_replay_session_from_body()`, wait for completion, and observe `sent_frames > 0`, no errors, and runtime state STOPPED.

UI acceptance is achieved when Scenarios Run starts that session, Replay Monitor displays changing snapshot state and final counters, Pause / Resume / Stop buttons follow the state, and Scenarios editing controls are locked while the session is active.

## Idempotence and Recovery

The changes are additive. Existing CLI commands and blocking `ReplayApplication.run()` remain intact. If a session start fails, the ViewModel must surface the error and leave no active session. If Stop is pressed repeatedly, later calls should be harmless because the session wrapper delegates to the runtime's existing stop behavior.

## Artifacts and Notes

Keep this file updated with implementation discoveries and final validation results.

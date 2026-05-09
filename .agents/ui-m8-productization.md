# UI M8.1 Productization Baseline

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` from the repository root. Any agent continuing this work must keep this document self-contained and update it after every meaningful stopping point.

## Purpose / Big Picture

The PySide6 workbench already has working Trace Library, Scenario Editor, Replay Monitor, and Devices workflows for mock and app-layer automation. The next useful step is not to pretend that blocked DBC, Signal Override, Diagnostics, DoIP, ZLG, or BLF features exist. Instead, this change starts M8 productization by making Settings a real status and validation page, adding a manual validation record for true window and high DPI checks, and updating the UI roadmap so future agents see the current boundary clearly.

After this change, a user can open Settings in `replay-ui` and see the active workspace, registered drivers, default theme, validation requirements, and unsupported feature boundaries. A maintainer can also use `docs/ui-manual-validation.md` to record real window click and high DPI results without confusing those checks with offscreen automation.

## Progress

- [x] (2026-05-09T15:46:52+08:00) Read the current UI roadmap, style guide, architecture notes, Settings placeholder, and UI tests.
- [x] (2026-05-09T15:46:52+08:00) Confirmed the pre-change automated baseline: `uv run ruff check src tests`, `uv run python -m compileall src tests`, `uv run python -m unittest discover -s tests -v`, and `uv run replay-ui --help` passed before implementation.
- [x] (2026-05-09T15:52:41+08:00) Added `docs/ui-manual-validation.md` and linked it from `docs/README.md`.
- [x] (2026-05-09T15:52:41+08:00) Added `src/replay_ui_qt/view_models/settings.py` and rendered Settings from ViewModel state.
- [x] (2026-05-09T15:52:41+08:00) Updated the UI roadmap, README, architecture guide, and testing guide to describe Settings productization and M8.1 boundaries.
- [x] (2026-05-09T15:52:41+08:00) Added automated coverage for Settings ViewModel, Settings view, and main-window Settings navigation.
- [x] (2026-05-09T15:52:41+08:00) Ran the full validation command set; all commands exited 0.

## Surprises & Discoveries

- Observation: Settings is the only first-level page still rendered as a placeholder.
  Evidence: `src/replay_ui_qt/views/placeholders.py` contains `SettingsView` backed directly by `AppContext` and `EmptyState`.
- Observation: M6 and M7 are correctly blocked by missing core capabilities.
  Evidence: `docs/ui-implementation-roadmap.md` lists M6 as blocked by missing DBC, `SignalDatabase`, override plan, and runtime payload patch; M7 is blocked by missing `DiagnosticClient`, diagnostic timeline item, and CAN_ISOTP / DOIP adapters.

## Decision Log

- Decision: Implement M8.1 before M6 or M7 UI work.
  Rationale: M6 and M7 require core ports, planner output, and runtime dispatch support. Building clickable UI first would violate the existing rule that unimplemented capabilities must not be presented as usable.
  Date/Author: 2026-05-09 / Codex.
- Decision: Keep Settings UI-only and read-only.
  Rationale: The current plan asks for workspace, registered drivers, theme, validation boundary, and unsupported feature visibility. Persisted settings would introduce a new product surface not required for this batch.
  Date/Author: 2026-05-09 / Codex.

## Outcomes & Retrospective

M8.1 is implemented. Settings is no longer a placeholder: it shows workspace, registered drivers, the active light theme, automated validation commands, manual verification requirements, and blocked / planned capability boundaries. The roadmap now marks M8 as `In Progress` while keeping M6 Signal Override and M7 Diagnostics blocked until core capabilities exist. `docs/ui-manual-validation.md` gives maintainers a place to record real window, high DPI, and accessibility checks.

Validation completed on 2026-05-09:

    uv run ruff check src tests
    Result: All checks passed.

    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests
    Result: passed.

    uv run python -m unittest discover -s tests -v
    Result: Ran 137 tests in 4.124s, OK.

    uv run replay-ui --help
    Result: exited 0 and printed the replay-ui options.

Remaining gaps are intentional M8 follow-ups: dark theme, packaging, high DPI hand verification, real window click evidence, and Windows Tongxing UI hardware validation. These were not executed in this batch and must remain documented as unverified until a human records them.

## Context and Orientation

`next_replay` is a ports-and-adapters replay tool. The core package `src/replay_tool` owns domain data, planning, runtime, storage, adapters, and app-layer use cases. The PySide6 package `src/replay_ui_qt` is the workbench and must call app-layer APIs through ViewModels instead of directly importing hardware adapters or runtime internals.

The UI has five top-level pages: Trace Library, Scenarios, Replay Monitor, Devices, and Settings. Trace Library, Scenarios, Replay Monitor, and Devices already have mock or app-layer workflows. Settings currently only displays a short placeholder. The desired M8.1 change is to turn Settings into a read-only productization and validation page without changing replay behavior.

The files most relevant to this work are:

- `src/replay_ui_qt/main_window.py`, which wires ViewModels to pages.
- `src/replay_ui_qt/views/placeholders.py`, which currently contains `ReplayMonitorView`, `DevicesView`, and `SettingsView`.
- `src/replay_ui_qt/view_models/`, where UI-only ViewModels live.
- `docs/ui-implementation-roadmap.md`, which records milestone state.
- `docs/ui-style-guide.md`, which defines visual and accessibility rules.
- `docs/testing.md` and `docs/tongxing-hardware-validation.md`, which define automated and hardware validation boundaries.

## Plan of Work

First, add `docs/ui-manual-validation.md` with a reusable manual validation template. It must clearly distinguish offscreen automated tests from real window click checks, high DPI checks, and Tongxing hardware UI checks. Update `docs/README.md` so the document is discoverable.

Second, add `src/replay_ui_qt/view_models/settings.py`. This ViewModel should expose immutable display data: workspace path, theme name, registered drivers from the existing application API, unsupported feature names, automated verification commands, manual validation items, and known unverified items. It must not persist settings, mutate the workspace, or call hardware adapters.

Third, update `SettingsView` in `src/replay_ui_qt/views/placeholders.py` to consume the new ViewModel. The page should use the existing quiet engineering layout: compact panels, status badges, tables or copyable text where useful, and short disabled/unsupported feature statements. It should provide public helpers for tests to read summary text, unsupported feature rows, validation rows, and inspector content.

Fourth, update `src/replay_ui_qt/main_window.py` to instantiate `SettingsViewModel` using the shared application and context workspace. This keeps app-facing behavior in the ViewModel layer and avoids direct hardware or runtime dependencies.

Fifth, update `docs/ui-implementation-roadmap.md` so M8 is `In Progress`, add an M8.1 batch note, and keep M6/M7 blocked. Do not mark dark theme, packaging, high DPI verification, real window click verification, or Windows Tongxing UI validation as complete.

Finally, add tests in `tests/test_ui_view_models.py`, `tests/test_ui_views.py`, and `tests/test_ui_smoke.py`. Run the full validation set listed below and update this ExecPlan with the outcome.

## Concrete Steps

From `C:\code\next_replay`, edit the files described above. Use only the existing PySide6 and project dependencies. Do not introduce a new settings store.

Run these commands from `C:\code\next_replay` after implementation:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help

Expected result: all commands exit 0. The unit test count may increase from the current 134 as Settings tests are added.

## Validation and Acceptance

Automated acceptance:

- Settings ViewModel exposes workspace, registered drivers, default light theme, unsupported feature list, verification commands, and unverified manual items.
- Settings view renders these values and its Inspector repeats the important boundary: offscreen tests do not replace real window, high DPI, or Tongxing hardware UI validation.
- Main window smoke test can navigate to Settings and observe the productized Settings content.
- Full validation commands pass.

Manual acceptance:

- Start `uv run replay-ui --workspace .replay_tool`.
- Visit Trace Library, Scenarios, Replay Monitor, Devices, and Settings in a real window.
- Record results in `docs/ui-manual-validation.md`.
- If high DPI or Windows Tongxing UI hardware checks are not executed, record them as `未验证` rather than passing.

## Idempotence and Recovery

The implementation is additive and read-only for Settings behavior. Re-running tests or opening Settings must not modify scenario records, trace records, hardware state, or configuration files. If a test fails because a local workspace already contains data, rerun tests in their temporary-directory setup; do not delete user workspaces. If manual validation is incomplete, record the missing items explicitly rather than editing code to imply success.

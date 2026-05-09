# M5 Devices Enumeration UI First Batch

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds. It follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the Devices page stops being a disabled placeholder. A user can edit a device configuration, click Enumerate, and see app-layer device information, capabilities, health, and channels. The observable first-batch path is mock enumeration in automated tests; Tongxing hardware remains a manual Windows + TSMaster + real device validation boundary.

## Progress

- [x] (2026-05-09 12:15Z) Read the current roadmap, app service, CLI devices path, BusDevice port, MockDevice adapter, Tongxing adapter shape, and Devices placeholder.
- [x] (2026-05-09 12:20Z) Created this ExecPlan before implementation.
- [x] (2026-05-09 12:35Z) Added app-layer `DeviceEnumerationResult`, `list_device_drivers()`, and `enumerate_device()`.
- [x] (2026-05-09 12:45Z) Added `DevicesViewModel` with editable config draft and background enumeration.
- [x] (2026-05-09 13:00Z) Replaced the Devices placeholder with editable controls and result tables.
- [x] (2026-05-09 13:05Z) Wired MainWindow to inject the shared app and task runner.
- [x] (2026-05-09 13:15Z) Updated tests and roadmap.
- [x] (2026-05-09 13:25Z) Ran ruff, compileall, unittest discovery, `replay-ui --help`, and `git diff --check`.

## Surprises & Discoveries

- Observation: The CLI already performs the desired low-level sequence for `devices`: create a device, open it, enumerate channels, print a summary, then close.
  Evidence: `src/replay_tool/cli.py` calls `app.create_device(config)`, `device.open()`, `device.enumerate_channels()`, and `device.close()`.
- Observation: The BusDevice port already exposes all data needed for M5 first batch.
  Evidence: `src/replay_tool/ports/device.py` includes `open`, `enumerate_channels`, `capabilities`, and `health`.

## Decision Log

- Decision: Put `DeviceEnumerationResult` in the app layer rather than UI.
  Rationale: The UI should call a stable app facade and should not know adapter details or repeat device lifecycle logic.
  Date/Author: 2026-05-09 / Codex
- Decision: Use mock as the automated acceptance path while keeping tongxing as the visible default driver.
  Rationale: Mock is deterministic and cross-platform; Tongxing requires Windows, TSMaster, and hardware.
  Date/Author: 2026-05-09 / Codex

## Outcomes & Retrospective

Completed. The Devices page now supports editable enumeration settings and app-layer mock enumeration results. The app facade owns the device lifecycle and closes adapters after probing. Automated tests cover app, ViewModel, View, and smoke paths. Tongxing UI hardware validation, real window clicking, and high DPI checks remain unverified.

## Context and Orientation

The app facade is `ReplayApplication` in `src/replay_tool/app/service.py`. It owns the registry and currently has `create_device(config)`. The device port is `BusDevice` in `src/replay_tool/ports/device.py`; every adapter can report `DeviceInfo`, channels, capabilities, and health. The PySide6 workbench is under `src/replay_ui_qt/`, and the existing Devices page is a disabled placeholder in `src/replay_ui_qt/views/placeholders.py`.

## Plan of Work

First, add an app-layer device result type and methods. `enumerate_device()` will create the adapter through the registry, open it, read channels, capabilities, and health, and close it in a `finally` block. `list_device_drivers()` will return sorted registry drivers.

Next, add `DevicesViewModel` in `src/replay_ui_qt/view_models/devices.py`. It will own editable configuration fields, expose device driver choices, run enumeration through `TaskRunner`, map the app result into display rows, and surface errors through the existing BaseViewModel signals.

Then, replace the Devices view with a real form and result display. Controls must remain quiet and engineering-focused: driver combo, text fields, index spinbox, Enumerate button, status badge, error details, device info, capabilities, health, and channels table. Tongxing hardware requirements must be visible in the page or Inspector.

Finally, update MainWindow, tests, and the UI roadmap. CLI may use the new API while keeping output compatible.

## Concrete Steps

Work from `C:\code\next_replay`.

Validation commands:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help
    git diff --check

Observed results on 2026-05-09:

    uv run ruff check src tests
    All checks passed!

    uv run python -m unittest discover -s tests -v
    Ran 126 tests in 3.406s
    OK

## Validation and Acceptance

Acceptance is achieved when automated tests enumerate a mock device configured with four channels and verify device info, channel rows, capabilities, and health. UI tests must prove fields are editable, enumeration uses the app layer, busy state disables actions, errors are copyable, and the Devices page does not import hardware adapters.

## Idempotence and Recovery

The change is additive. Existing runtime, trace, scenario, and replay monitor behavior remains unchanged. If enumeration fails, the ViewModel reports the error and clears busy state. The app layer closes the adapter in a `finally` block when a device was created.

## Artifacts and Notes

Keep this file updated with implementation evidence and validation results.

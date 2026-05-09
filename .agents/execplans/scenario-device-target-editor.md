# M3.5 Scenario Device Target Editor

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` from the repository root.

## Purpose / Big Picture

The PySide6 Scenario Editor already creates mock replay drafts, edits routes, saves, validates, and starts a mock replay session. A hardware-oriented user still cannot configure more than the default mock device/target from the visual editor. After this change, a user can edit scenario devices and physical targets in the Scenario Editor without hand-editing JSON, then save, validate, and run through the existing app-layer APIs. This keeps the UI useful for real Tongxing-style configurations while preserving the quick mock workflow.

## Progress

- [x] (2026-05-09 14:10+08:00) Read `.agents/PLANS.md`, UI roadmap, Scenario ViewModel/View, Devices ViewModel/View, and existing UI tests to locate the implementation seams.
- [x] (2026-05-09 14:15+08:00) Created this ExecPlan before mutating code, as required for the cross-module UI change.
- [x] (2026-05-09 14:45+08:00) Extended Scenario draft rows and ViewModel editing methods for multi-device and multi-target editing.
- [x] (2026-05-09 15:10+08:00) Upgraded the Scenarios Qt view with device/target editors, Add/Remove controls, existing-target route selection, and nearby issue text.
- [x] (2026-05-09 15:20+08:00) Updated targeted ViewModel/View tests and confirmed the existing mock run path still passes.
- [x] (2026-05-09 15:35+08:00) Calibrated README, architecture, testing, and UI roadmap status text for M4/M5 first-batch completion and M3.5 delivery.
- [x] (2026-05-09 15:50+08:00) Ran `uv run ruff check src tests`, compileall with `PYTHONPYCACHEPREFIX`, full unittest discovery, `uv run replay-ui --help`, and `git diff --check`.

## Surprises & Discoveries

- Observation: The roadmap already records M4 Replay Monitor and M5 Devices first batches as delivered, but README, architecture guide, and testing docs still contain older language that says those UI workflows are placeholders or not implemented.
  Evidence: `docs/ui-implementation-roadmap.md` mentions `ReplayApplication.start_replay_session_from_body()` and device enumeration as delivered; `docs/testing.md` still says Scenario editable save/run and Devices UI workflow are not implemented.
- Observation: Add Route currently always creates or reuses a mock target via `_ensure_mock_target_resource()`.
  Evidence: `ScenariosViewModel.add_route_from_trace()` accepts `physical_channel` and calls `_ensure_mock_device()` and `_ensure_mock_target_resource()`.
- Observation: Keeping removal rejection as an error-level draft issue would block Run even though the body remains valid.
  Evidence: `ScenariosView._run_loaded_scenario()` originally blocked on any `draft_issues`; rejection notices are now warning-level and the view blocks only `has_blocking_issues`.

## Decision Log

- Decision: Do not add new core or app-layer public APIs in this batch.
  Rationale: The required app seams already exist: `validate_scenario_body()`, `save_scenario_body()`, `start_replay_session_from_body()`, and device driver enumeration. The change belongs in the UI draft model and Qt editor.
  Date/Author: 2026-05-09 / Codex
- Decision: Removing a referenced device or target must be rejected with a draft issue/status message instead of cascading deletes.
  Rationale: The user's requested plan explicitly forbids implicit cascade deletion, and preserving routes avoids accidental data loss.
  Date/Author: 2026-05-09 / Codex
- Decision: Add Route should prefer an existing selected target, while keeping ViewModel backward compatibility for tests and programmatic callers that still pass only a physical channel.
  Rationale: The UI should stop forcing mock target creation, but keeping the older path reduces regression risk for the existing real-application mock workflow.
  Date/Author: 2026-05-09 / Codex

## Outcomes & Retrospective

Implemented M3.5 as planned. Scenario Editor drafts now carry editable device and target channel fields, Add / Remove Device and Target commands, existing-target Add Route selection, warning-level rejection issues for referenced removals, and nearby issue labels for selected device / target / route editors. Documentation now reflects Scenario Run, Replay Monitor, and Devices first-batch delivery while keeping hardware, high-DPI, DBC, diagnostics, DoIP, ZLG, and BLF boundaries explicit. Automated validation passed; Windows hardware UI validation and high-DPI manual checks were not performed.

## Context and Orientation

The UI code lives under `src/replay_ui_qt`. `src/replay_ui_qt/view_models/scenarios.py` owns the immutable `ScenarioDraft` display rows and all draft editing commands. `src/replay_ui_qt/views/scenarios_view.py` renders the Scenario page, including the Overview, Traces & Devices, Routes, and JSON tabs. The app layer in `src/replay_tool/app/service.py` already exposes scenario body save/validate/run and device enumeration; the UI must use these APIs and must not import hardware adapters.

A scenario schema v2 body has separate `devices`, `targets`, and `routes`. A device describes the adapter instance, such as `mock` or `tongxing`. A target describes one physical transmit endpoint on a device, including bus type, physical channel, baud rates, and channel flags. A route maps a trace source to a target through a logical channel.

## Plan of Work

First, extend the scenario draft rows so device rows include `sdk_root` and `application`, and target rows include all editable target channel fields. Add ViewModel methods to edit individual device/target fields, add and remove devices/targets, and reject removal when the resource is still referenced. Draft validation will also flag duplicate IDs, invalid references, missing devices/targets, and bus mismatch.

Second, upgrade `ScenariosView` so `Traces & Devices` shows traces, devices, and targets with selection-aware edit forms. The view will provide Add/Remove Device and Add/Remove Target controls, bus selection for targets, baud/flag controls, and a nearby issue label. Route editing will keep source and target dropdowns, but Add Route will include a target dropdown using existing draft targets instead of silently creating a mock target.

Third, update tests. ViewModel tests will cover device/target edits, add/remove behavior, referenced-resource rejection, and route target bus mismatch. View tests will cover rendered edit controls, active replay locking, Add Route target selection, and nearby issue text. Existing tests for new mock scenario creation, save/validate, and run enablement must continue to pass.

Fourth, update documentation so status descriptions match the current code: Trace Library is done; Scenario Editor supports visual draft save/validate/run and device/target editing; Replay Monitor and Devices have first-batch mock/app-layer flows; Signal Override, Diagnostics, BLF, DoIP, ZLG, high DPI, real window click, and Windows hardware UI validation remain unverified or blocked.

## Concrete Steps

From `C:\code\next_replay`, edit only repository files using `apply_patch`. Do not run formatters that rewrite files. After each cohesive code change, rerun the targeted unit tests that cover that surface before moving on if failures are likely to be localized.

The final validation commands are:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help
    git diff --check

## Validation and Acceptance

Acceptance for the UI draft model is that a loaded schema v2 scenario can add a Tongxing-like device, add a CANFD target on that device, route an imported trace source to that target, save the body, validate through the app layer, and keep Run disabled when draft issues exist.

Acceptance for the view is that the editor exposes device and target fields without relying on JSON editing, locks those controls while a replay session is active, and shows field-specific issue text near the relevant editor while preserving the Inspector's complete issue list.

Acceptance for documentation is that no file claims Scenario Run, Replay Monitor controls, or app-layer Devices enumeration are still absent, and every unverified hardware/high-DPI boundary is clearly stated.

## Idempotence and Recovery

All code changes are additive or localized edits to UI draft/view/test/docs files. Re-running tests is safe. If a device or target add command is triggered repeatedly, generated IDs must use stable suffixes to avoid collisions. If a remove command is rejected because the resource is referenced, it should only set status/issue state and leave the draft body unchanged.

## Artifacts and Notes

Targeted scenario UI tests passed:

    uv run python -m unittest tests.test_ui_view_models.ScenariosViewModelTests tests.test_ui_views.ScenariosViewTests -v
    Ran 39 tests in 1.013s
    OK

Final validation passed:

    uv run ruff check src tests
    All checks passed!

    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui"); uv run python -m compileall src tests
    Compiled changed UI and test modules successfully.

    uv run python -m unittest discover -s tests -v
    Ran 131 tests in 3.974s
    OK

    uv run replay-ui --help
    usage: replay-ui [-h] [--workspace WORKSPACE]

    git diff --check
    Exit code 0. PowerShell printed Git's expected LF-to-CRLF working-copy warnings only.

## Interfaces and Dependencies

Do not add new core/app public APIs. `ScenariosViewModel` may expose new UI-only methods such as device/target field setters and add/remove commands. The Qt view may add helper methods used by tests. Existing scenario JSON field names must remain schema v2 names: `devices[].driver`, `devices[].application`, `devices[].sdk_root`, `devices[].device_type`, `devices[].device_index`, `targets[].device`, `targets[].physical_channel`, `targets[].bus`, `targets[].nominal_baud`, `targets[].data_baud`, `targets[].resistance_enabled`, `targets[].listen_only`, and `targets[].tx_echo`.

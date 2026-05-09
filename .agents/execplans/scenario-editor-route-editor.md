# Add Multi-Route Scenario Draft Editing

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` in this repository.

## Purpose / Big Picture

The Scenarios page can already create, save, and validate a minimum single-route schema v2 draft from an imported trace. Users still cannot build a scenario with more than one route or change a route by selecting an existing source and target. This change adds the next M3 editing loop: users can add and remove routes, choose a route source and target through UI selectors, see local field-level issues in the Inspector, then continue using the existing Save and Validate buttons.

## Progress

- [x] (2026-05-09 00:00+08:00) Read the current Scenario ViewModel, Scenario View, tests, UI roadmap, style guide, architecture guide, testing guide, and ExecPlan instructions.
- [x] (2026-05-09 00:00+08:00) Extend the Scenarios ViewModel with draft issue rows, endpoint choices, and route add/remove/source/target editing methods.
- [x] (2026-05-09 00:00+08:00) Extend the Scenarios View Routes tab with route selection, source/target selectors, Add Route, Remove Route, and Add Route dialog.
- [x] (2026-05-09 00:00+08:00) Add ViewModel, View, and real application regression tests for multi-route draft editing.
- [x] (2026-05-09 00:00+08:00) Update the UI roadmap and run the required validation commands.

## Surprises & Discoveries

- Observation: The current schema v2 model already supports multiple routes, duplicate logical-channel detection, and source/target bus mismatch detection in `ReplayScenario.validate()`.
  Evidence: `src/replay_tool/domain/model.py` validates unique logical channels and compares each route source bus with target bus.

## Decision Log

- Decision: Add routes through existing imported traces and mock targets only.
  Rationale: The M3 editor still has no Devices enumeration workflow, so real hardware target selection belongs to a later M5 batch.
  Date/Author: 2026-05-09 / Codex.

- Decision: Removing a route does not remove trace, source, target, or device resources.
  Rationale: A non-cascading delete avoids accidentally losing endpoints that another route may reuse and keeps the operation easy to reason about.
  Date/Author: 2026-05-09 / Codex.

- Decision: Field-level localization is an Inspector issue list rather than table cell highlighting.
  Rationale: This gives users actionable section/row/field locations without introducing custom table painting in this batch.
  Date/Author: 2026-05-09 / Codex.

## Outcomes & Retrospective

Completed. The Scenarios page now supports multi-route draft editing with Add Route, Remove Route, selected-route source/target selectors, local Inspector issue mapping, and the existing Save / Validate flow. Run remains disabled, real device target selection remains a later milestone, and hardware/high-DPI/manual window validation was not performed.

## Context and Orientation

The project root is `C:\code\next_replay`. `src/replay_ui_qt/view_models/scenarios.py` owns the Scenarios page draft state. `src/replay_ui_qt/views/scenarios_view.py` owns the Qt widgets. A schema v2 scenario body contains `traces`, `devices`, `sources`, `targets`, `routes`, and `timeline`. A route maps one trace source to one logical channel and one device target. The UI draft body remains the single source of truth, and every edit must copy the body and rebuild the immutable `ScenarioDraft`.

The UI must only call application-layer methods. This batch uses the already available `list_traces()`, `inspect_trace()`, `save_scenario_body()`, and `validate_scenario_body()` methods. It must not import TraceStore, ProjectStore, ReplayPlanner, ReplayRuntime, or hardware adapters from the UI layer.

## Plan of Work

Update `src/replay_ui_qt/view_models/scenarios.py` with UI-only endpoint choice types for existing draft sources and targets. Add a `ScenarioDraftIssue` type with section, row, field, severity, and message. Recompute draft issues whenever the draft changes. Issues should cover empty name, empty routes, duplicate logical channel, unknown route source, unknown route target, source-to-target bus mismatch, source referencing an unknown trace, and target referencing an unknown device.

Add ViewModel editing commands for appending a route from an imported trace source, removing a route, assigning a route source, and assigning a route target. Adding a route should reuse matching trace/source/target resources and create missing source or mock target resources with stable IDs. If a generated resource ID collides, append `-2`, then `-3`, and so on. Editing commands should refuse to run while the ViewModel is busy and should keep the existing draft unchanged.

Update `src/replay_ui_qt/views/scenarios_view.py` so the Routes tab has Add Route and Remove Route buttons, a selectable route table, and controls for the selected route source, logical channel, target, and selected target physical channel. Add an Add Route dialog that lists imported traces, calls `inspect_trace()` through the ViewModel for source choices, and lets the user choose logical and physical channel numbers. The Inspector should prefer showing draft issues when a draft has local issues and no successful validation result is active.

Update `tests/test_ui_view_models.py` and `tests/test_ui_views.py` with tests for route creation, removal, endpoint selection, issue rendering, busy rejection, and a real `ReplayApplication` save/validate workflow with two routes. Update `docs/ui-implementation-roadmap.md` to record the fourth M3 batch and remaining M3 gaps.

## Concrete Steps

From `C:\code\next_replay`, edit source, test, and documentation files with scoped patches. Then run:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_m3_routes"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help

## Validation and Acceptance

Acceptance requires that a user can load or create a draft, add a second route, select an existing route, change its source and target through controls, remove a route, see local issues in the Inspector, save the valid draft, and validate it through the app layer. Run must remain disabled. A real application regression should import `examples/sample.asc`, create a draft, add a second route, save it, and validate a two-channel plan.

## Idempotence and Recovery

The changes are ordinary source, test, and documentation edits. Tests use temporary workspaces. Add Route is in-memory until Save Scenario is invoked. Re-running the tests is safe. If validation fails because a draft is intentionally invalid, inspect the new issue list and error details rather than editing Scenario Store data directly.

## Artifacts and Notes

Validation completed:

    uv run ruff check src tests
    Result: passed, All checks passed.

    uv run python -m compileall src tests
    Result: passed with PYTHONPYCACHEPREFIX set to a temp directory.

    uv run python -m unittest discover -s tests -v
    Result: Ran 110 tests in 4.048s, OK.

    uv run replay-ui --help
    Result: passed and printed replay-ui usage.

## Interfaces and Dependencies

No third-party dependency is added. No core schema or app-layer public method is added. The new UI-only types live in `src/replay_ui_qt/view_models/scenarios.py`:

    ScenarioDraftIssue(section: str, row: int | None, field: str, message: str, severity: str = "error")
    ScenarioSourceEndpointChoice(source_id: str, label: str, bus: str)
    ScenarioTargetEndpointChoice(target_id: str, label: str, bus: str)

The new ViewModel methods are:

    add_route_from_trace(trace, source, *, logical_channel: int, physical_channel: int) -> None
    remove_route(index: int) -> None
    set_route_source(index: int, source_id: str) -> None
    set_route_target(index: int, target_id: str) -> None

The core `ReplayScenario`, `ReplayPlan`, `ReplayApplication`, storage, runtime, and hardware adapter interfaces remain unchanged.

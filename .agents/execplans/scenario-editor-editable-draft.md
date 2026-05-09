# Add Editable Scenario Draft Minimum Loop

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` in this repository.

## Purpose / Big Picture

Users can already load a saved schema v2 scenario in the PySide6 Scenarios page, validate it, save it, and delete it. They still cannot create a scenario from an imported trace or change even the smallest draft fields without editing JSON elsewhere. This change adds the smallest useful editable workflow: create a one-trace, one-source, one-target, one-route mock scenario from an imported trace, edit its name, loop flag, logical channel, and target physical channel, then save and validate it through the existing app layer.

## Progress

- [x] (2026-05-08 00:00+08:00) Read the current Scenarios ViewModel, Scenarios view, app service trace/scenario methods, roadmap, and UI tests.
- [x] (2026-05-09 00:00+08:00) Extend the Scenarios ViewModel protocol and draft model for trace choices, new draft state, and edit commands.
- [x] (2026-05-09 00:00+08:00) Add a New Scenario dialog and editable overview/routes controls to the Scenarios view.
- [x] (2026-05-09 00:00+08:00) Add ViewModel, view, and integration tests for new draft creation, edit, save, and validate.
- [x] (2026-05-09 00:00+08:00) Update the UI roadmap and run validation commands.

## Surprises & Discoveries

- Observation: `ReplayApplication` already exposes `list_traces()` and `inspect_trace()`, so the UI can build a new draft through the app layer without touching TraceStore directly.
  Evidence: `src/replay_tool/app/service.py` includes both methods.

## Decision Log

- Decision: Support only one trace, one source, one mock device, one target, and one route in this batch.
  Rationale: The goal is to close the minimum create/edit/save/validate loop without designing the full multi-route editor.
  Date/Author: 2026-05-08 / Codex.

- Decision: Keep JSON read-only and regenerate it from the draft body after every edit.
  Rationale: The UI style guide says JSON should be an advanced preview rather than the main editing surface.
  Date/Author: 2026-05-08 / Codex.

## Outcomes & Retrospective

Completed. The Scenarios page now supports a minimum editable draft workflow: users can create a single-route mock scenario from an imported trace, edit the scenario name, loop flag, logical channel, and target physical channel, then save and validate the draft. Run remains disabled for the future Replay Monitor milestone, and full multi-route editing remains out of scope.

## Context and Orientation

The project root is `C:\code\next_replay`. `src/replay_ui_qt/view_models/scenarios.py` owns the Scenarios page state. `src/replay_ui_qt/views/scenarios_view.py` owns the Qt widgets. The app-layer facade is `src/replay_tool/app/service.py`. A schema v2 scenario is a dictionary with `traces`, `devices`, `sources`, `targets`, `routes`, and `timeline`; this task must not change that core schema.

The previous M3 batch added `ReplayApplication.validate_scenario_body()` and `save_scenario_body()`, and Scenarios UI buttons for Save, Validate, and Delete. This task builds on those methods. Run remains disabled because the Replay Monitor needs a separate non-blocking session API.

## Plan of Work

First, update `ScenarioListApplication` to include `list_traces()` and `inspect_trace()`. Add UI-only `ScenarioTraceChoice` and `ScenarioSourceChoice` dataclasses. Add `is_new` and `dirty` to `ScenarioDraft`, with class helpers to build from saved records and from a new trace/source choice. Draft edits must build a copied schema body and replace the draft rather than mutating the existing body in place.

Next, add ViewModel methods: `load_trace_choices()`, `source_choices_for_trace()`, `create_new_scenario_from_trace()`, `rename_loaded_scenario()`, `set_timeline_loop()`, `set_route_logical_channel()`, and `set_target_physical_channel()`. Editing clears stale validation and delete result state.

Then, update `ScenariosView`: add a New Scenario button, a small `NewScenarioDialog`, editable name and loop fields in Overview, spin boxes for route logical channel and target physical channel, and test helper methods for setting these fields without direct event simulation. Save must pass `scenario_id=None` for new drafts and the existing ID for saved drafts.

Finally, add tests and update `docs/ui-implementation-roadmap.md`.

## Concrete Steps

From `C:\code\next_replay`, edit source, test, and documentation files with scoped patches. Then run:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_m3_editable"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help

## Validation and Acceptance

Acceptance requires tests showing a trace-backed new draft can be created, edited, saved as a new Scenario Store record, validated, and rendered in the view. Existing saved scenario load/save/delete behavior must keep passing. Run must remain disabled.

## Idempotence and Recovery

The changes are ordinary source, test, and documentation edits. Tests use temporary workspaces. New draft creation is in-memory until Save Scenario is invoked; no migration is required.

## Artifacts and Notes

Validation completed:

    uv run ruff check src tests
    Result: passed, All checks passed.

    uv run python -m compileall src tests
    Result: passed with PYTHONPYCACHEPREFIX set to a temp directory.

    uv run python -m unittest discover -s tests -v
    Result: Ran 101 tests in 4.031s, OK.

    uv run replay-ui --help
    Result: passed and printed replay-ui usage.

## Interfaces and Dependencies

No third-party dependency is added. The UI protocol will use existing app-layer trace methods:

    def list_traces(self) -> list[TraceRecord]
    def inspect_trace(self, trace_id: str) -> TraceInspection

The core domain schema remains unchanged.

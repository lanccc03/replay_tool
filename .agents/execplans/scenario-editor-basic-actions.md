# Add Scenario Editor Basic Actions

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` in this repository.

## Purpose / Big Picture

Users can already open the PySide6 workbench, list saved scenarios, and load a saved schema v2 scenario into a read-only preview. This change makes that preview useful as a Scenario Store workflow: a loaded scenario can be validated, saved back through the app layer, and deleted with confirmation. The visible result is that the Scenarios toolbar enables Validate, Save Scenario, and Delete at the right times while Run remains disabled for the later Replay Monitor milestone.

## Progress

- [x] (2026-05-08 00:00+08:00) Read the UI roadmap, app service, Scenario Store port, Scenarios ViewModel, Scenarios view, and existing UI tests.
- [x] (2026-05-08 00:00+08:00) Add app-layer methods for validating and saving scenario bodies.
- [x] (2026-05-08 00:00+08:00) Extend the Scenarios ViewModel with validation, save, and delete state.
- [x] (2026-05-08 00:00+08:00) Enable Scenarios view commands and Inspector output for validation/delete results.
- [x] (2026-05-08 00:00+08:00) Add unit and view tests for the basic operation workflow.
- [x] (2026-05-08 00:00+08:00) Update the UI roadmap and run validation commands.

## Surprises & Discoveries

- Observation: The worktree already contains documentation edits across README and docs files before this task starts.
  Evidence: `git status --short` shows modified documentation files, including `docs/ui-implementation-roadmap.md`.

## Decision Log

- Decision: Keep field editing out of this batch and save the loaded scenario body unchanged.
  Rationale: The requested batch is a basic operation loop; full route/source/target editing needs a separate UI draft-editing design.
  Date/Author: 2026-05-08 / Codex.

- Decision: Add app-layer body methods instead of letting Qt ViewModels call `ProjectStore` or `ReplayPlanner` directly.
  Rationale: The project requires UI to use `ReplayApplication` or later app-layer APIs for business behavior.
  Date/Author: 2026-05-08 / Codex.

## Outcomes & Retrospective

Completed. The Scenarios UI now supports the basic Scenario Store operation loop for loaded schema v2 drafts: validate, save, and delete. Run remains disabled for the later Replay Monitor session work, and full field editing remains out of scope for this batch.

## Context and Orientation

The project root is `C:\code\next_replay`. The PySide6 UI lives under `src/replay_ui_qt`. The app-layer facade used by CLI and UI is `src/replay_tool/app/service.py`. The Scenario Store port is `src/replay_tool/ports/project_store.py`; it stores schema v2 scenario JSON bodies as `ScenarioRecord.body`. A schema v2 scenario separates trace resources, trace sources, device targets, routes, and timeline settings. A ReplayPlan is the compiled runtime-ready representation produced by `ReplayApplication.compile_plan()` or the planner.

The current Scenarios UI uses `ScenariosViewModel` in `src/replay_ui_qt/view_models/scenarios.py` and `ScenariosView` in `src/replay_ui_qt/views/scenarios_view.py`. It can list records and load a read-only `ScenarioDraft`. The Save Scenario, Validate, Run, and Delete buttons are disabled. Run must stay disabled in this task because non-blocking replay session UI belongs to M4.

## Plan of Work

First, update `ReplayApplication` with two body-based methods. `validate_scenario_body(body, base_dir)` should parse `ReplayScenario.from_dict()`, prepare trace sources using existing app-layer trace resolution, and compile a `ReplayPlan`. `save_scenario_body(body, scenario_id, base_dir)` should parse and validate the body, then call the existing `project_store.save_scenario()`.

Next, update the Scenarios ViewModel protocol and add UI-only result dataclasses. The ViewModel should expose `validation` and `delete_result` properties, run validate/save/delete through `TaskRunner`, keep busy/error/status behavior consistent with Trace Library, clear stale result state when a new scenario loads, and refresh rows after save/delete.

Then, update ScenariosView to enable Save and Validate only when a draft is loaded, enable Delete when a row is selected, keep Run disabled, and render validation/delete details in the Inspector. Delete must use the existing dangerous confirmation helper and include the scenario name and ID.

Finally, add tests in the existing UI and project-store test modules, update `docs/ui-implementation-roadmap.md`, and run the repository validation commands.

## Concrete Steps

From `C:\code\next_replay`, edit repository files using scoped patches. Then run:

    uv run ruff check src tests
    $env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_m3_scenarios"); uv run python -m compileall src tests
    uv run python -m unittest discover -s tests -v
    uv run replay-ui --help

## Validation and Acceptance

Acceptance requires the Scenarios UI tests to prove that Save, Validate, and Delete enable in the intended states, Run remains disabled, validation results and delete results are visible through the Inspector, and destructive delete confirmation mentions the scenario identity. App-level tests must prove a scenario body can be saved, loaded, validated, and deleted through `ReplayApplication` without direct UI access to storage or planner internals. Full test discovery and ruff must pass.

## Idempotence and Recovery

These are ordinary source, test, and documentation edits. Re-running save on the same scenario ID updates the existing Scenario Store record. Delete tests use temporary workspaces. If compileall writes pycache files under the temporary prefix, no tracked files should be affected.

## Artifacts and Notes

Validation completed:

    uv run ruff check src tests
    Result: passed, All checks passed.

    uv run python -m compileall src tests
    Result: passed with PYTHONPYCACHEPREFIX set to a temp directory.

    uv run python -m unittest discover -s tests -v
    Result: Ran 94 tests in 2.442s, OK.

    uv run replay-ui --help
    Result: passed and printed replay-ui usage.

## Interfaces and Dependencies

No third-party dependency is added. `ReplayApplication` will expose:

    def validate_scenario_body(self, body: dict[str, Any], *, base_dir: str | Path = ".") -> ReplayPlan
    def save_scenario_body(self, body: dict[str, Any], *, scenario_id: str | None = None, base_dir: str | Path = ".") -> ScenarioRecord

`ScenariosViewModel` will expose read-only `validation` and `delete_result` properties and command methods for validating the loaded draft, saving the loaded draft, and deleting a selected scenario.

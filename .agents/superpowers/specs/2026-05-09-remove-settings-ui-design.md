# Remove Settings UI Design

## Purpose

The PySide6 workbench should focus on workflows users actively need: Trace Library, Scenarios, Replay Monitor, and Devices. The current Settings page is a read-only productization and validation status page, but the user has decided it is unnecessary. This change removes Settings as a product surface instead of leaving a hidden or stale page behind.

## Scope

Remove the Settings page completely from the UI and tests:

- Remove the Settings navigation item from `src/replay_ui_qt/main_window.py`.
- Remove `SettingsViewModel` from `src/replay_ui_qt/view_models/settings.py`.
- Remove `SettingsView` from `src/replay_ui_qt/views/placeholders.py`.
- Update tests that import, instantiate, navigate to, or assert Settings behavior.
- Update README and docs so they describe the four-page workbench and no longer claim Settings productization is complete.
- Update manual validation guidance so real-window checks cover Trace Library, Scenarios, Replay Monitor, and Devices only.

Do not change core replay behavior, storage, app-layer APIs, device enumeration, scenario editing, or runtime control.

## Chosen Approach

Delete Settings code and documentation references rather than only hiding the navigation item. This keeps implementation, tests, and product documentation aligned. If a future Settings surface becomes useful, it should be reintroduced with a concrete user workflow rather than kept as dead code.

## User-Visible Result

Starting `replay-ui` shows four left navigation entries:

- Trace Library
- Scenarios
- Replay Monitor
- Devices

There is no Settings page, no Settings inspector content, and no manual validation row for Settings.

## Architecture

This is a UI shell cleanup. The existing View / ViewModel / app boundaries stay intact:

- `MainWindow` still owns page creation and shell navigation.
- Remaining pages continue to communicate through their existing ViewModels.
- UI continues to call app-layer APIs through `ReplayApplication`; no hardware adapter or runtime internals are introduced.

The validation and unsupported-feature boundaries previously shown in Settings remain documented in `docs/testing.md`, `docs/ui-implementation-roadmap.md`, `docs/ui-manual-validation.md`, and `docs/tongxing-hardware-validation.md` where relevant.

## Testing

The behavior should be covered by focused UI tests:

- Main window smoke test expects four navigation pages and no Settings navigation.
- ViewModel and view tests no longer import or assert Settings types.
- Documentation-only consistency is checked with `git diff --check`.

For the final implementation, run the UI minimum verification:

- `uv run ruff check src tests`
- `PYTHONPYCACHEPREFIX=/private/tmp/next_replay_pycache_ui uv run python -m compileall src tests`
- `uv run python -m unittest discover -s tests -v`
- `uv run replay-ui --help`

Windows real-window, high DPI, and Tongxing hardware UI validation remain unverified unless explicitly performed on Windows with the required hardware.

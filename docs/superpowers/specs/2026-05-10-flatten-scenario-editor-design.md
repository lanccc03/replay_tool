# Flatten Scenario Editor — Remove Tabs, Replace Dialog

**Date:** 2026-05-10
**Status:** approved

## Summary

Remove the `QTabWidget` from the Scenarios page and replace the "New Scenario" dialog with a full-page in-place editor. The editor uses a `QStackedWidget` to switch between the scenario list and a flat, scrollable editor.

## Motivation

- The tab-based editor forces users to click between sections to see the full scenario configuration
- The "New Scenario" dialog only collects minimal info (name, trace, source) — users must then edit tabs to complete configuration
- A single flat editor page with all sections visible gives a better overview

## Design

### ScenariosView restructure

```
ScenariosView (QWidget)
├── Toolbar (New, Refresh, Load, Save, Validate, Run, Delete, Status)
└── QStackedWidget
    ├── Page 0: List View (toolbar + QTableView / EmptyState)
    └── Page 1: Editor View (flat stacked sections, QScrollArea)
```

The `QSplitter` is removed. The `QStackedWidget` switches between the list and the editor. The editor fills the full page — no split.

### Editor view layout (Page 1)

Stacked vertically in a `QScrollArea`:

1. **Top bar:** "← Back to list" button | [Validate] [Run]
2. **Overview section:** Name (`QLineEdit`) + Loop (`QCheckBox`)
3. **Traces & Devices section:** traces table, devices table + form, targets table + form
4. **Routes section:** routes table + "Add Route" button + route form

No schema summary. No JSON preview.

### Data flow

| Action | Behavior |
|--------|----------|
| "New Scenario" | Switch to editor, create empty draft via ViewModel, populate editor |
| "Load Scenario" | Switch to editor, load existing draft as editable |
| "← Back to list" | Switch to list, discard unsaved draft |
| Save/Validate/Run | Reuse existing ViewModel methods |

### Removals

- `QTabWidget` (`self._tabs`) and all 4 tab builder methods
- `QSplitter`
- `NewScenarioDialog` class (~110 lines)
- `AddRouteDialog` class (~135 lines)
- `_show_new_scenario_dialog`, `_show_add_route_dialog` methods
- `create_new_dialog`, `create_add_route_dialog` factory methods
- Schema summary `QTextEdit`, JSON preview `QTextEdit`
- `_start_new_scenario` trace-loading guard (no longer needed — editor handles trace selection directly)

### Additions

- `_build_editor_view()` — builds the flat editor in a `QScrollArea`
- `_switch_to_editor()` / `_switch_to_list()` — stack page transitions
- `_back_to_list()` — back button handler, discards unsaved draft

### ViewModel

No changes needed. `ScenariosViewModel` already supports all draft editing operations: `create_new_scenario_from_trace`, `load_scenario`, `add_device`, `remove_device`, `add_target`, `remove_target`, `add_route`, `remove_route`, etc.

### Error handling

Reuse existing error display: `_show_error()` sets the error button, `_sync_busy()` disables buttons during async operations. Editor validates through the existing ViewModel validation flow.

### Testing

- Existing `NewScenarioDialog`/`AddRouteDialog` tests need to be re-targeted to the editor view
- List ↔ editor switching behavior needs tests
- Back button discarding unsaved draft needs test coverage
- Test file: `tests/test_ui_views.py`

## Scope

Single file change: `src/replay_ui_qt/views/scenarios_view.py`. ViewModel and other files unchanged.

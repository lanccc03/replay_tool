# Remove Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the unnecessary Settings page from the PySide6 workbench, including code, tests, navigation, and product documentation references.

**Architecture:** This is a UI shell cleanup. `MainWindow` will continue to assemble the workbench pages, but only the four workflow pages remain: Trace Library, Scenarios, Replay Monitor, and Devices. Core replay, storage, runtime, adapter, and app-layer behavior must not change.

**Tech Stack:** Python 3, PySide6, `unittest`, project CLI through `uv`, Markdown documentation.

---

### Task 1: Main Window Smoke Test Red

**Files:**
- Modify: `tests/test_ui_smoke.py`

- [ ] **Step 1: Write the failing smoke-test expectation**

  In `tests/test_ui_smoke.py`, update `UiSmokeTests.test_main_window_opens_with_expected_shell_parts` so it expects four pages and verifies that asking for Settings does not change the current page:

      self.assertEqual(4, window.navigation_count())
      self.assertEqual("Trace Library", window.current_page_name())
      self.assertIn("Workspace:", window.workspace_status_text())
      self.assertIn(tmp, window.workspace_status_text())
      self.assertIn("Trace", window.inspector_text())

      window.show_page("Settings")
      self._app.processEvents()
      self.assertEqual("Trace Library", window.current_page_name())
      self.assertIn("Trace", window.inspector_text())

- [ ] **Step 2: Run the smoke test and verify it fails**

  Run from `/Users/lanyy/Code/replay_tool`:

      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run python -m unittest tests.test_ui_smoke -v

  Expected before implementation: failure because `window.navigation_count()` still returns `5`, or because Settings navigation still succeeds.

- [ ] **Step 3: Remove Settings from the shell**

  In `src/replay_ui_qt/main_window.py`, remove the Settings imports:

      from replay_ui_qt.view_models.settings import SettingsViewModel
      from replay_ui_qt.views.placeholders import DevicesView, ReplayMonitorView, SettingsView

  Replace them with:

      from replay_ui_qt.views.placeholders import DevicesView, ReplayMonitorView

  In `MainWindow.show_page`, change the docstring argument example from `such as "Settings"` to `such as "Devices"`.

  In `MainWindow._create_pages`, delete these two lines:

      settings_view_model = SettingsViewModel(self._context.application, workspace=self._context.workspace)
      settings_view = SettingsView(settings_view_model)

  Remove the Settings tuple from the page list so the loop reads:

      for label, page in (
          ("Trace Library", trace_view),
          ("Scenarios", scenario_view),
          ("Replay Monitor", replay_view),
          ("Devices", devices_view),
      ):

- [ ] **Step 4: Run the smoke test and verify it passes**

  Run:

      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run python -m unittest tests.test_ui_smoke -v

  Expected after implementation: `Ran 1 test` and `OK`.

- [ ] **Step 5: Commit the shell removal**

  Run:

      git add src/replay_ui_qt/main_window.py tests/test_ui_smoke.py
      git commit -m "refactor: remove settings from ui shell"

### Task 2: Delete Settings ViewModel and View Tests

**Files:**
- Modify: `tests/test_ui_view_models.py`
- Modify: `tests/test_ui_views.py`
- Delete: `src/replay_ui_qt/view_models/settings.py`
- Modify: `src/replay_ui_qt/views/placeholders.py`

- [ ] **Step 1: Remove Settings ViewModel tests first**

  In `tests/test_ui_view_models.py`, remove this import:

      from replay_ui_qt.view_models.settings import SettingsViewModel

  Delete the full `SettingsViewModelTests` class, including both test methods:

      class SettingsViewModelTests(unittest.TestCase):
          def test_settings_summary_reports_workspace_drivers_and_boundaries(self) -> None:
              ...

          def test_settings_uses_placeholder_driver_when_registry_is_empty(self) -> None:
              ...

- [ ] **Step 2: Remove Settings view tests first**

  In `tests/test_ui_views.py`, remove this import:

      from replay_ui_qt.view_models.settings import SettingsViewModel

  Change the placeholders import from:

      from replay_ui_qt.views.placeholders import DevicesView, ReplayMonitorView, SettingsView

  to:

      from replay_ui_qt.views.placeholders import DevicesView, ReplayMonitorView

  Delete the full `SettingsViewTests` class:

      class SettingsViewTests(unittest.TestCase):
          ...

- [ ] **Step 3: Run targeted tests and verify they fail**

  Run:

      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run python -m unittest tests.test_ui_view_models tests.test_ui_views -v

  Expected before code deletion: tests may still pass because only dead tests were removed. This is acceptable for this deletion task because Task 1 already established the user-visible failing test. If they fail, the expected failure is an unused or stale Settings import from production code.

- [ ] **Step 4: Delete Settings production code**

  Delete the file:

      src/replay_ui_qt/view_models/settings.py

  In `src/replay_ui_qt/views/placeholders.py`, remove this import:

      from replay_ui_qt.view_models.settings import SettingsViewModel

  Delete the full `SettingsView` class, from:

      class SettingsView(QWidget):

  through its final `_sync_rows` method. Do not modify `ReplayMonitorView` or `DevicesView`.

- [ ] **Step 5: Run targeted tests and verify they pass**

  Run:

      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run python -m unittest tests.test_ui_view_models tests.test_ui_views tests.test_ui_smoke -v

  Expected after implementation: all selected tests pass.

- [ ] **Step 6: Commit the Settings code deletion**

  Run:

      git add src/replay_ui_qt/view_models/settings.py src/replay_ui_qt/views/placeholders.py tests/test_ui_view_models.py tests/test_ui_views.py
      git commit -m "refactor: delete settings ui implementation"

### Task 3: Documentation Alignment

**Files:**
- Modify: `README.md`
- Modify: `docs/testing.md`
- Modify: `docs/ui-style-guide.md`
- Modify: `docs/ui-implementation-roadmap.md`
- Modify: `docs/ui-manual-validation.md`
- Modify: `docs/architecture-design-guide.md`
- Modify or leave historical: `.agents/ui-m8-productization.md`

- [ ] **Step 1: Update README UI status**

  In `README.md`, replace the paragraph that says Settings shows workspace, drivers, theme, validation commands, manual boundaries, and unsupported feature status with text that says the active workbench pages are Trace Library, Scenarios, Replay Monitor, and Devices. Keep the existing unsupported feature warning for DBC / Signal Override, diagnostics, DoIP, ZLG, BLF, high DPI checks, real window click checks, dark theme, packaging, and Windows hardware UI validation.

- [ ] **Step 2: Update testing guide**

  In `docs/testing.md`, remove Settings from the PySide6 UI test mapping. Replace references to "Settings 产品化状态页" with the current four-page workflow coverage. Keep validation boundaries that say offscreen smoke tests do not replace real-window, high DPI, or Tongxing hardware UI verification.

- [ ] **Step 3: Update UI style guide navigation**

  In `docs/ui-style-guide.md`, change the left navigation rule from:

      Trace Library、Scenarios、Replay Monitor、Devices、Settings

  to:

      Trace Library、Scenarios、Replay Monitor、Devices

- [ ] **Step 4: Update UI roadmap**

  In `docs/ui-implementation-roadmap.md`, remove claims that Settings M8.1 is a completed productization page. Describe M8 as still `In Progress`, with manual validation documentation present but no Settings UI surface. The M8.1 notes should say the prior Settings status page was removed by product decision and validation boundaries now live in documentation.

- [ ] **Step 5: Update manual validation template**

  In `docs/ui-manual-validation.md`, remove Settings from the expected navigation list and from the page click checklist table. The startup expectation should list four pages only.

- [ ] **Step 6: Update architecture guide**

  In `docs/architecture-design-guide.md`, remove Settings from current UI capability lists and keep the four-page workbench description. Do not remove unsupported feature boundaries.

- [ ] **Step 7: Decide historical plan handling**

  `.agents/ui-m8-productization.md` is an already-completed historical ExecPlan. Do not rewrite its historical statements as if they never happened. If necessary, append a short note at the end:

      Note: On 2026-05-09, the Settings UI created by this historical plan was removed by product decision. Current UI status is documented in `docs/ui-implementation-roadmap.md`.

- [ ] **Step 8: Run documentation consistency check**

  Run:

      git diff --check
      rg -n "Settings|SettingsView|SettingsViewModel|M8\\.1" README.md docs src tests .agents

  Expected: `git diff --check` exits 0. The `rg` output should contain no active code or current-doc claims that Settings is a visible page. A historical `.agents/ui-m8-productization.md` note may remain.

- [ ] **Step 9: Commit documentation alignment**

  Run:

      git add README.md docs/testing.md docs/ui-style-guide.md docs/ui-implementation-roadmap.md docs/ui-manual-validation.md docs/architecture-design-guide.md .agents/ui-m8-productization.md
      git commit -m "docs: align ui docs after settings removal"

### Task 4: Final Verification

**Files:**
- No code edits expected.

- [ ] **Step 1: Run ruff**

  Run:

      uv run ruff check src tests

  Expected: exit 0 with no lint failures.

- [ ] **Step 2: Run compileall**

  Run:

      PYTHONPYCACHEPREFIX=/private/tmp/next_replay_pycache_ui uv run python -m compileall src tests

  Expected: exit 0 and no compile errors.

- [ ] **Step 3: Run full unit suite**

  Run:

      PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run python -m unittest discover -s tests -v

  Expected: exit 0 with all tests passing.

- [ ] **Step 4: Verify UI entrypoint help**

  Run:

      uv run replay-ui --help

  Expected: exit 0 and the help text shows `replay-ui`.

- [ ] **Step 5: Summarize unverified manual items**

  In the final response, state that Windows real-window clicking, high DPI, and Tongxing hardware UI validation were not executed unless they were actually run on Windows hardware.

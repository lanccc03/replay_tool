# UI Cohesion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap toolbar+table in visual containers so Navigation, Content, and Inspector form three equal surface panels.

**Architecture:** Add `QFrame#ContentPanel` around `QStackedWidget` at the shell level; wrap each View's toolbar in `QFrame#ToolbarHeader` with `surface_muted` background; unify editor section label styles.

**Tech Stack:** PySide6, Python 3.x, `unittest`

---

### Task 1: Add ContentPanel CSS tokens

**Files:**
- Modify: `src/replay_ui_qt/theme.py:52-129`

- [ ] **Step 1: Add `QFrame#ContentPanel` and `QFrame#ToolbarHeader` CSS rules**

```python
# In _stylesheet(), after the existing QFrame rule for TopStatusBar/InspectorPanel/NavigationPanel
# (line ~61), append two new rules:

QFrame#ContentPanel {
    background: #FFFFFF;
    border: 1px solid #D8DEE6;
}
QFrame#ToolbarHeader {
    background: #EEF2F5;
    border: none;
    border-bottom: 1px solid #D8DEE6;
}
```

The complete `_stylesheet()` return value should end with the new rules before the closing `"""`. Place them after the existing `QFrame#TopStatusBar, QFrame#InspectorPanel, QFrame#NavigationPanel` block.

- [ ] **Step 2: Verify syntax**

```bash
uv run python -m compileall src/replay_ui_qt/theme.py
```

Expected: Compilation succeeded.

- [ ] **Step 3: Verify existing tests still pass**

```bash
uv run python -m unittest tests.test_ui_smoke -v
```

Expected: `test_main_window_opens_with_expected_shell_parts` passes.

- [ ] **Step 4: Commit**

```bash
git add src/replay_ui_qt/theme.py
git commit -m "feat: add ContentPanel and ToolbarHeader CSS tokens"
```

---

### Task 2: Add ContentPanel frame around QStackedWidget

**Files:**
- Modify: `src/replay_ui_qt/main_window.py:89-94`

- [ ] **Step 1: Write a failing test for ContentPanel**

In `tests/test_ui_smoke.py`, add a test method to `UiSmokeTests`:

```python
def test_content_panel_frame_wraps_stacked_widget(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        replay_app = ReplayApplication(workspace=tmp)
        context = AppContext(workspace=tmp, application=replay_app)
        window = MainWindow(context)
        try:
            window.show()
            self._app.processEvents()
            _wait_for(lambda: context.task_runner.active_count() == 0, self._app)

            from PySide6.QtWidgets import QFrame
            content = window.findChild(QFrame, "ContentPanel")
            self.assertIsNotNone(content, "ContentPanel QFrame should wrap QStackedWidget")
        finally:
            window.close()
            self._app.processEvents()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_ui_smoke.UiSmokeTests.test_content_panel_frame_wraps_stacked_widget -v
```

Expected: FAIL — `AssertionError: ContentPanel QFrame should wrap QStackedWidget`

- [ ] **Step 3: Add ContentPanel frame in main_window.py**

In `_build_ui`, change lines 89-95 from:

```python
        self._navigation = NavigationPanel()
        self._stack = QStackedWidget()
        self._inspector = InspectorPanel()

        body.addWidget(self._navigation)
        body.addWidget(self._stack, 1)
        body.addWidget(self._inspector)
```

To:

```python
        self._navigation = NavigationPanel()
        self._stack = QStackedWidget()
        self._content_panel = QFrame()
        self._content_panel.setObjectName("ContentPanel")
        content_layout = QVBoxLayout(self._content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._stack)
        self._inspector = InspectorPanel()

        body.addWidget(self._navigation)
        body.addWidget(self._content_panel, 1)
        body.addWidget(self._inspector)
```

Also add `QFrame` to the imports at line 3:

```python
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_ui_smoke.UiSmokeTests.test_content_panel_frame_wraps_stacked_widget -v
```

Expected: PASS.

- [ ] **Step 5: Run all UI tests**

```bash
uv run python -m unittest tests.test_ui_smoke tests.test_ui_views tests.test_ui_widgets -v
```

Expected: All existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/replay_ui_qt/main_window.py tests/test_ui_smoke.py
git commit -m "feat: wrap QStackedWidget in ContentPanel surface container"
```

---

### Task 3: Wrap TraceLibraryView toolbar in ToolbarHeader

**Files:**
- Modify: `src/replay_ui_qt/views/trace_library_view.py:169-210`

- [ ] **Step 1: Write a failing test for ToolbarHeader**

In `tests/test_ui_views.py`, add to `TraceLibraryViewTests`:

```python
def test_toolbar_header_frame_exists(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        record = _trace_record(tmp)
        view = TraceLibraryView(TraceLibraryViewModel(_TraceApp(records=[record]), _runner()))
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            from PySide6.QtWidgets import QFrame
            header = view.findChild(QFrame, "ToolbarHeader")
            self.assertIsNotNone(header, "ToolbarHeader QFrame should wrap toolbar")
        finally:
            view.close()
            self._app.processEvents()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_ui_views.TraceLibraryViewTests.test_toolbar_header_frame_exists -v
```

Expected: FAIL.

- [ ] **Step 3: Wrap toolbar in ToolbarHeader frame**

In `_build_ui`, change the toolbar section (lines 174-210). Currently:

```python
        toolbar = QHBoxLayout()
        self._refresh_button = QPushButton("刷新")
        ...
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
```

Change to:

```python
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        self._refresh_button = QPushButton("刷新")
        ...
        toolbar.addStretch(1)
```

And replace `layout.addLayout(toolbar)` with:

```python
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("ToolbarHeader")
        toolbar_frame.setLayout(toolbar)
        layout.addWidget(toolbar_frame)
```

Also add `QFrame` to the imports at line 5:

```python
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    ...
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_ui_views.TraceLibraryViewTests.test_toolbar_header_frame_exists -v
```

Expected: PASS.

- [ ] **Step 5: Run all TraceLibraryView tests**

```bash
uv run python -m unittest tests.test_ui_views.TraceLibraryViewTests -v
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add src/replay_ui_qt/views/trace_library_view.py tests/test_ui_views.py
git commit -m "feat: wrap TraceLibraryView toolbar in ToolbarHeader frame"
```

---

### Task 4: Wrap ScenariosView toolbars in ToolbarHeader

**Files:**
- Modify: `src/replay_ui_qt/views/scenarios_view.py:596-646` (list toolbar) and `:757-770` (editor top bar)

- [ ] **Step 1: Write a failing test for ScenariosView ToolbarHeader**

In `tests/test_ui_views.py`, add to `ScenariosViewTests`:

```python
def test_toolbar_header_frame_exists_in_list_view(self) -> None:
    view = ScenariosView(ScenariosViewModel(_ScenarioApp(records=[_scenario_record()]), _runner()))
    try:
        _wait_for(lambda: view.refresh_enabled(), self._app)
        from PySide6.QtWidgets import QFrame
        header = view.findChild(QFrame, "ToolbarHeader")
        self.assertIsNotNone(header, "ToolbarHeader QFrame should wrap list toolbar")
    finally:
        view.close()
        self._app.processEvents()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run python -m unittest tests.test_ui_views.ScenariosViewTests.test_toolbar_header_frame_exists_in_list_view -v
```

Expected: FAIL.

- [ ] **Step 3: Wrap list toolbar in ToolbarHeader**

In `_build_ui`, change the list toolbar section. Currently (line 646):

```python
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
```

Change to:

```python
        toolbar.addStretch(1)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("ToolbarHeader")
        toolbar_frame.setLayout(toolbar)
        layout.addWidget(toolbar_frame)
```

Also add `QFrame` to the imports at line 4.

- [ ] **Step 4: Wrap editor top bar in ToolbarHeader**

In `_build_editor_view`, change the top bar section (lines 757-770). Currently:

```python
        # Top bar: Back + actions
        top_bar = QHBoxLayout()
        self._back_button = QPushButton("← Back to list")
        self._back_button.clicked.connect(self._back_to_list)
        top_bar.addWidget(self._back_button)
        top_bar.addStretch(1)
        self._editor_validate_button = QPushButton("Validate")
        self._editor_validate_button.setEnabled(False)
        self._editor_validate_button.clicked.connect(self._validate_loaded_scenario)
        top_bar.addWidget(self._editor_validate_button)
        self._editor_run_button = QPushButton("Run")
        self._editor_run_button.setEnabled(False)
        self._editor_run_button.clicked.connect(self._run_loaded_scenario)
        top_bar.addWidget(self._editor_run_button)
        layout.addLayout(top_bar)
```

Change to:

```python
        # Top bar: Back + actions
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        self._back_button = QPushButton("← Back to list")
        self._back_button.clicked.connect(self._back_to_list)
        top_bar.addWidget(self._back_button)
        top_bar.addStretch(1)
        self._editor_validate_button = QPushButton("Validate")
        self._editor_validate_button.setEnabled(False)
        self._editor_validate_button.clicked.connect(self._validate_loaded_scenario)
        top_bar.addWidget(self._editor_validate_button)
        self._editor_run_button = QPushButton("Run")
        self._editor_run_button.setEnabled(False)
        self._editor_run_button.clicked.connect(self._run_loaded_scenario)
        top_bar.addWidget(self._editor_run_button)
        editor_toolbar = QFrame()
        editor_toolbar.setObjectName("ToolbarHeader")
        editor_toolbar.setLayout(top_bar)
        layout.addWidget(editor_toolbar)
```

- [ ] **Step 5: Unify section label styles**

In `_build_editor_view`, replace inline styles on section labels. Currently:

```python
        overview_label = QLabel("Overview")
        overview_label.setStyleSheet("font-weight: bold; font-size: 13px;")
```
```python
        section_label = QLabel("Traces & Devices")
        section_label.setStyleSheet("font-weight: bold; font-size: 13px;")
```
```python
        routes_label = QLabel("Routes")
        routes_label.setStyleSheet("font-weight: bold; font-size: 13px;")
```

Change all three to use `font-weight: 600` and `color: #667085`:

```python
        overview_label = QLabel("Overview")
        overview_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #667085;")
```
```python
        section_label = QLabel("Traces & Devices")
        section_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #667085;")
```
```python
        routes_label = QLabel("Routes")
        routes_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #667085;")
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv run python -m unittest tests.test_ui_views.ScenariosViewTests.test_toolbar_header_frame_exists_in_list_view -v
```

Expected: PASS.

- [ ] **Step 7: Run all ScenariosView tests**

```bash
uv run python -m unittest tests.test_ui_views.ScenariosViewTests -v
```

Expected: All pass.

- [ ] **Step 8: Commit**

```bash
git add src/replay_ui_qt/views/scenarios_view.py tests/test_ui_views.py
git commit -m "feat: wrap ScenariosView toolbars in ToolbarHeader, unify section labels"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run python -m unittest discover -s tests -v
```

Expected: All tests pass.

- [ ] **Step 2: Lint check**

```bash
uv run ruff check src tests
```

Expected: No errors.

- [ ] **Step 3: Syntax check**

```bash
uv run python -m compileall src tests
```

Expected: Compilation succeeded.

- [ ] **Step 4: Commit (if any cleanup needed)**

Only if lint/compileall required changes. Otherwise final verification is complete.

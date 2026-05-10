# Flatten Scenario Editor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove QTabWidget from ScenariosView and replace NewScenarioDialog/AddRouteDialog with a full-page flat editor using QStackedWidget page switching.

**Architecture:** `ScenariosView` gets a top-level `QStackedWidget` with two pages: list (toolbar + table/empty) and editor (QScrollArea with Overview, Traces & Devices, Routes sections stacked). NewScenarioDialog and AddRouteDialog classes are removed. The existing ViewModel is unchanged.

**Tech Stack:** PySide6, Qt Widgets, Python 3.12+

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/replay_ui_qt/views/scenarios_view.py` | Modify | Rename existing `self._stack` → `self._list_stack`, add top-level `self._page_stack`, rebuild `_build_ui`, add `_build_editor_view`, remove `_build_editor_preview` and tab builders, remove `NewScenarioDialog` and `AddRouteDialog`, update `_sync_draft` (remove JSON/overview text refs), update `_start_new_scenario` and `_load_selected_scenario` |
| `tests/test_ui_views.py` | Modify | Replace dialog-based tests with editor-view tests, remove `json_preview_text`/`overview_text` assertions, add page-switching and back-button tests |

---

### Task 1: Rename existing QStackedWidget to avoid confusion

**Files:**
- Modify: `src/replay_ui_qt/views/scenarios_view.py:671-688`

The current `self._stack` holds the table/empty switch. Rename it to `self._list_stack` so the new top-level page stack can take the name `self._page_stack`.

- [ ] **Step 1: Rename `self._stack` to `self._list_stack` in `_build_ui` and all references**

In `_build_ui()` (lines 671-691):

```python
# Replace:
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._stack = QStackedWidget()
        # ... table setup ...
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)
        splitter.addWidget(self._stack)
        splitter.addWidget(self._build_editor_preview())
        splitter.setSizes([280, 360])
        layout.addWidget(splitter, 1)

# With:
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._list_stack = QStackedWidget()
        # ... table setup (unchanged) ...
        self._list_stack.addWidget(self._table)
        self._list_stack.addWidget(self._empty)
        splitter.addWidget(self._list_stack)
        splitter.addWidget(self._build_editor_preview())
        splitter.setSizes([280, 360])
        layout.addWidget(splitter, 1)
```

In `_sync_rows()` (line 696):

```python
# Replace:
        self._stack.setCurrentWidget(self._empty if not self._view_model.rows else self._table)
# With:
        self._list_stack.setCurrentWidget(self._empty if not self._view_model.rows else self._table)
```

- [ ] **Step 2: Run existing tests to verify no regressions**

```bash
cd /Users/lanyy/Code/replay_tool && uv run python -m unittest tests.test_ui_views.ScenariosViewTests -v
```

Expected: all tests still pass (rename only, no behavior change).

- [ ] **Step 3: Commit**

```bash
git add src/replay_ui_qt/views/scenarios_view.py
git commit -m "refactor: rename self._stack to self._list_stack in ScenariosView"
```

---

### Task 2: Replace QSplitter with top-level QStackedWidget for list/editor pages

**Files:**
- Modify: `src/replay_ui_qt/views/scenarios_view.py:619-692, 694-696, 729-740`

Replace the `QSplitter` with a top-level `self._page_stack` (`QStackedWidget`) that holds list_page and editor_page. The list_page is the old `self._list_stack` (table/empty). The editor_page starts as the old editor preview (still with tabs for now — we'll flatten it in Task 4).

- [ ] **Step 1: Build the page stack in `_build_ui`**

Replace the splitter section (from `splitter = QSplitter(...)` through `layout.addWidget(splitter, 1)`) with:

```python
        self._page_stack = QStackedWidget()

        # Page 0: list view (table or empty state)
        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(self._list_stack)
        self._page_stack.addWidget(list_page)

        # Page 1: editor view (existing preview for now)
        editor_page = self._build_editor_preview()
        self._page_stack.addWidget(editor_page)

        self._page_stack.setCurrentIndex(0)
        layout.addWidget(self._page_stack, 1)
```

- [ ] **Step 2: Add `_switch_to_editor` and `_switch_to_list` methods**

After `_build_ui`:

```python
    def _switch_to_editor(self) -> None:
        """Switch the page stack to the editor view."""
        self._page_stack.setCurrentIndex(1)

    def _switch_to_list(self) -> None:
        """Switch the page stack back to the list and discard the draft."""
        self._page_stack.setCurrentIndex(0)
```

- [ ] **Step 3: Wire "New Scenario" to switch to editor**

Update `_start_new_scenario`:

```python
    def _start_new_scenario(self) -> None:
        if self._replay_active:
            return
        if not self._view_model.trace_choices:
            self._open_new_dialog_after_trace_load = True
            self._view_model.load_trace_choices()
            return
        self._switch_to_editor()
```

Update `_sync_trace_choices` to switch to editor instead of showing dialog:

```python
    def _sync_trace_choices(self) -> None:
        if self._open_new_dialog_after_trace_load:
            self._open_new_dialog_after_trace_load = False
            self._switch_to_editor()
        elif self._open_add_route_dialog_after_trace_load:
            self._open_add_route_dialog_after_trace_load = False
            # Add Route is now a button in the editor, handled later
```

- [ ] **Step 4: Wire "Load Scenario" to switch to editor**

Update `_load_selected_scenario`:

```python
    def _load_selected_scenario(self) -> None:
        if self._replay_active:
            return
        row = self._selected_row()
        if row is None:
            return
        self._view_model.load_scenario(row.scenario_id)
        self._switch_to_editor()
```

- [ ] **Step 5: Run tests, expect dialog-related tests to fail**

```bash
cd /Users/lanyy/Code/replay_tool && uv run python -m unittest tests.test_ui_views.ScenariosViewTests -v
```

Expected: dialog-related tests fail (they still expect `create_new_dialog()` to work), other tests may pass.

- [ ] **Step 6: Commit**

```bash
git add src/replay_ui_qt/views/scenarios_view.py
git commit -m "refactor: replace QSplitter with top-level QStackedWidget for list/editor pages"
```

---

### Task 3: Remove NewScenarioDialog and AddRouteDialog classes

**Files:**
- Modify: `src/replay_ui_qt/views/scenarios_view.py:1643-1915, 554-568, 964-990`

Delete both dialog classes and their factory methods. Clean up related flags and methods.

- [ ] **Step 1: Delete NewScenarioDialog class (lines ~1643-1757)**

Remove the entire `NewScenarioDialog` class.

- [ ] **Step 2: Delete AddRouteDialog class (lines ~1759-1915)**

Remove the entire `AddRouteDialog` class.

- [ ] **Step 3: Remove factory methods and dialog-related methods**

Delete:
- `create_new_dialog()` (lines 554-560)
- `create_add_route_dialog()` (lines 562-568)
- `_show_new_scenario_dialog()` (lines 964-969)
- `_start_add_route()` (lines 971-978)
- `_show_add_route_dialog()` (lines 980-990)
- `_open_new_dialog_after_trace_load` flag (line 105)
- `_open_add_route_dialog_after_trace_load` flag (line 106)

- [ ] **Step 4: Clean up `_sync_trace_choices`**

```python
    def _sync_trace_choices(self) -> None:
        if self._open_new_dialog_after_trace_load:
            self._open_new_dialog_after_trace_load = False
            self._switch_to_editor()
```

Remove the `_open_add_route_dialog_after_trace_load` branch.

- [ ] **Step 5: Run tests — dialog tests now fail with AttributeError**

```bash
cd /Users/lanyy/Code/replay_tool && uv run python -m unittest tests.test_ui_views.ScenariosViewTests -v
```

Expected: Dialog tests (`test_new_scenario_dialog_*`, `test_add_route_dialog_*`) fail. Other tests may also fail if they reference `json_preview_text`, `overview_text`, or `create_new_dialog`.

- [ ] **Step 6: Commit**

```bash
git add src/replay_ui_qt/views/scenarios_view.py
git commit -m "refactor: remove NewScenarioDialog and AddRouteDialog classes"
```

---

### Task 4: Build flat editor view replacing QTabWidget

**Files:**
- Modify: `src/replay_ui_qt/views/scenarios_view.py:729-740, 742-869`

Replace `_build_editor_preview()` (which builds a QTabWidget) with `_build_editor_view()` that builds a QScrollArea with all sections stacked flat. Remove tab builder methods. Remove JSON preview and schema summary text areas.

- [ ] **Step 1: Write `_build_editor_view` replacing `_build_editor_preview`**

Replace the `_build_editor_preview` method and all four tab builder methods with:

```python
    def _build_editor_view(self) -> QWidget:
        """Build the flat scenario editor page with all sections stacked."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        editor = QWidget()
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

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

        # Section 1: Overview
        overview_label = QLabel("Overview")
        overview_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #e2e8f0;")
        layout.addWidget(overview_label)
        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Scenario name")
        self._name_edit.setEnabled(False)
        self._name_edit.editingFinished.connect(self._apply_name_edit)
        self._loop_check = QCheckBox("Loop")
        self._loop_check.setEnabled(False)
        self._loop_check.clicked.connect(self._apply_loop_edit)
        form.addRow("Name", self._name_edit)
        form.addRow("Timeline", self._loop_check)
        layout.addLayout(form)

        # Section 2: Traces & Devices
        traces_label = QLabel("Traces & Devices")
        traces_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #e2e8f0;")
        layout.addWidget(traces_label)

        traces = QTableView()
        traces.setModel(self._trace_model)
        traces.verticalHeader().setVisible(False)
        traces.setColumnWidth(0, 180)
        traces.setColumnWidth(1, 520)
        traces.setMaximumHeight(100)
        layout.addWidget(QLabel("Traces"))
        layout.addWidget(traces)

        device_toolbar = QHBoxLayout()
        self._add_device_button = QPushButton("Add Device")
        self._add_device_button.setEnabled(False)
        self._add_device_button.setToolTip("添加一个可编辑 device 配置")
        self._add_device_button.clicked.connect(self._add_device)
        device_toolbar.addWidget(self._add_device_button)
        self._remove_device_button = QPushButton("Remove Device")
        self._remove_device_button.setEnabled(False)
        self._remove_device_button.setToolTip("删除未被 target 引用的 device")
        self._remove_device_button.clicked.connect(self._remove_selected_device)
        device_toolbar.addWidget(self._remove_device_button)
        device_toolbar.addStretch(1)
        layout.addLayout(device_toolbar)

        self._devices_table = QTableView()
        self._devices_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._devices_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._devices_table.setModel(self._device_model)
        self._devices_table.verticalHeader().setVisible(False)
        self._devices_table.setColumnWidth(0, 150)
        self._devices_table.setColumnWidth(1, 90)
        self._devices_table.setColumnWidth(2, 180)
        self._devices_table.setColumnWidth(3, 120)
        self._devices_table.setColumnWidth(4, 130)
        self._devices_table.setColumnWidth(5, 70)
        self._devices_table.setMaximumHeight(120)
        self._devices_table.selectionModel().currentRowChanged.connect(
            lambda _current, _previous: self._handle_device_selection_changed()
        )
        layout.addWidget(self._devices_table)

        device_form = QFormLayout()
        self._device_driver_combo = QComboBox()
        self._device_driver_combo.setEditable(True)
        self._device_driver_combo.addItems(["mock", "tongxing"])
        self._device_driver_combo.currentTextChanged.connect(lambda _text: self._apply_device_driver_edit())
        self._device_sdk_root_edit = QLineEdit()
        self._device_sdk_root_edit.editingFinished.connect(self._apply_device_sdk_root_edit)
        self._device_application_edit = QLineEdit()
        self._device_application_edit.editingFinished.connect(self._apply_device_application_edit)
        self._device_type_edit = QLineEdit()
        self._device_type_edit.editingFinished.connect(self._apply_device_type_edit)
        self._device_index_spin = QSpinBox()
        self._device_index_spin.setRange(0, 255)
        self._device_index_spin.editingFinished.connect(self._apply_device_index_edit)
        device_form.addRow("Driver", self._device_driver_combo)
        device_form.addRow("SDK root", self._device_sdk_root_edit)
        device_form.addRow("Application", self._device_application_edit)
        device_form.addRow("Device type", self._device_type_edit)
        device_form.addRow("Device index", self._device_index_spin)
        layout.addLayout(device_form)
        self._device_issue_label = QLabel("")
        self._device_issue_label.setStyleSheet("color: #C2410C;")
        layout.addWidget(self._device_issue_label)

        target_toolbar = QHBoxLayout()
        self._add_target_button = QPushButton("Add Target")
        self._add_target_button.setEnabled(False)
        self._add_target_button.setToolTip("添加一个可编辑 target 配置")
        self._add_target_button.clicked.connect(self._add_target)
        target_toolbar.addWidget(self._add_target_button)
        self._remove_target_button = QPushButton("Remove Target")
        self._remove_target_button.setEnabled(False)
        self._remove_target_button.setToolTip("删除选中 target")
        self._remove_target_button.clicked.connect(self._remove_selected_target)
        target_toolbar.addWidget(self._remove_target_button)
        target_toolbar.addStretch(1)
        layout.addLayout(target_toolbar)

        self._targets_table = QTableView()
        self._targets_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._targets_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._targets_table.setModel(self._target_model)
        self._targets_table.verticalHeader().setVisible(False)
        self._targets_table.setMaximumHeight(120)
        self._targets_table.selectionModel().currentRowChanged.connect(
            lambda _current, _previous: self._handle_target_selection_changed()
        )
        layout.addWidget(self._targets_table)

        target_form = QFormLayout()
        self._target_device_combo = QComboBox()
        self._target_device_combo.currentTextChanged.connect(lambda _text: self._apply_target_device_edit())
        self._target_bus_combo = QComboBox()
        self._target_bus_combo.addItems(["CAN", "CANFD"])
        self._target_bus_combo.currentTextChanged.connect(lambda _text: self._apply_target_bus_edit())
        self._target_editor_physical_spin = QSpinBox()
        self._target_editor_physical_spin.setRange(0, 255)
        self._target_editor_physical_spin.editingFinished.connect(self._apply_target_physical_edit)
        self._target_nominal_baud_spin = QSpinBox()
        self._target_nominal_baud_spin.setRange(0, 10_000_000)
        self._target_nominal_baud_spin.setSingleStep(50000)
        self._target_nominal_baud_spin.editingFinished.connect(self._apply_target_nominal_baud_edit)
        self._target_data_baud_spin = QSpinBox()
        self._target_data_baud_spin.setRange(0, 10_000_000)
        self._target_data_baud_spin.setSingleStep(50000)
        self._target_data_baud_spin.editingFinished.connect(self._apply_target_data_baud_edit)
        self._target_resistance_check = QCheckBox("Resistance")
        self._target_resistance_check.clicked.connect(self._apply_target_resistance_edit)
        self._target_listen_only_check = QCheckBox("Listen Only")
        self._target_listen_only_check.clicked.connect(self._apply_target_listen_only_edit)
        self._target_tx_echo_check = QCheckBox("TX Echo")
        self._target_tx_echo_check.clicked.connect(self._apply_target_tx_echo_edit)
        target_form.addRow("Device", self._target_device_combo)
        target_form.addRow("Bus", self._target_bus_combo)
        target_form.addRow("Physical CH", self._target_editor_physical_spin)
        target_form.addRow("Nominal Baud", self._target_nominal_baud_spin)
        target_form.addRow("Data Baud", self._target_data_baud_spin)
        target_form.addRow(self._target_resistance_check, self._target_listen_only_check)
        target_form.addRow("", self._target_tx_echo_check)
        layout.addLayout(target_form)
        self._target_issue_label = QLabel("")
        self._target_issue_label.setStyleSheet("color: #C2410C;")
        layout.addWidget(self._target_issue_label)

        # Section 3: Routes
        routes_label = QLabel("Routes")
        routes_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #e2e8f0;")
        layout.addWidget(routes_label)

        route_toolbar = QHBoxLayout()
        self._add_route_button = QPushButton("Add Route")
        self._add_route_button.setEnabled(False)
        self._add_route_button.setToolTip("从已导入 Trace 添加一条 route")
        self._add_route_button.clicked.connect(self._add_route_from_editor)
        route_toolbar.addWidget(self._add_route_button)
        self._remove_route_button = QPushButton("Remove Route")
        self._remove_route_button.setEnabled(False)
        self._remove_route_button.setToolTip("删除选中 route")
        self._remove_route_button.clicked.connect(self._remove_selected_route)
        route_toolbar.addWidget(self._remove_route_button)
        route_toolbar.addStretch(1)
        layout.addLayout(route_toolbar)

        self._routes_table = QTableView()
        self._routes_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._routes_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._routes_table.setModel(self._route_model)
        self._routes_table.verticalHeader().setVisible(False)
        self._routes_table.setMaximumHeight(120)
        self._routes_table.selectionModel().currentRowChanged.connect(
            lambda _current, _previous: self._handle_route_selection_changed()
        )
        layout.addWidget(self._routes_table)

        route_form = QFormLayout()
        self._route_source_combo = QComboBox()
        self._route_source_combo.currentTextChanged.connect(lambda _text: self._apply_route_source_edit())
        self._route_logical_spin = QSpinBox()
        self._route_logical_spin.setRange(0, 255)
        self._route_logical_spin.editingFinished.connect(self._apply_route_logical_edit)
        self._route_target_combo = QComboBox()
        self._route_target_combo.currentTextChanged.connect(lambda _text: self._apply_route_target_edit())
        self._target_physical_spin = QSpinBox()
        self._target_physical_spin.setRange(0, 255)
        self._target_physical_spin.editingFinished.connect(self._apply_target_physical_edit)
        route_form.addRow("Source", self._route_source_combo)
        route_form.addRow("Logical CH", self._route_logical_spin)
        route_form.addRow("Target", self._route_target_combo)
        route_form.addRow("Target CH", self._target_physical_spin)
        layout.addLayout(route_form)
        self._route_issue_label = QLabel("")
        self._route_issue_label.setStyleSheet("color: #C2410C;")
        layout.addWidget(self._route_issue_label)

        layout.addStretch(1)
        scroll.setWidget(editor)
        return scroll
```

- [ ] **Step 2: Wire page_stack to use the new editor view**

In `_build_ui`, update the editor page:

```python
        # Page 1: editor view
        editor_page = self._build_editor_view()
        self._page_stack.addWidget(editor_page)
```

- [ ] **Step 3: Add `_back_to_list` method**

```python
    def _back_to_list(self) -> None:
        """Return to the scenario list, discarding any unsaved draft."""
        self._switch_to_list()
```

- [ ] **Step 4: Add `_add_route_from_editor` method** (replaces the old dialog flow)

```python
    def _add_route_from_editor(self) -> None:
        """Add a route from available trace choices, inline."""
        if self._replay_active or self._view_model.draft is None:
            return
        if not self._view_model.trace_choices:
            self._view_model.load_trace_choices()
            return
        # Use first available trace and source as defaults
        trace = self._view_model.trace_choices[0]
        sources = self._view_model.source_choices_for_trace(trace.trace_id)
        if not sources:
            return
        source = sources[0]
        # Pick first available target or create a new one
        draft = self._view_model.draft
        target_id = draft.targets[0].target_id if draft.targets else ""
        self._view_model.add_route_from_trace(trace, source, target_id=target_id)
```

- [ ] **Step 5: Remove old `_build_editor_preview` and tab builder methods**

Delete:
- `_build_editor_preview()` (lines 729-740)
- `_build_overview_tab()` (lines 742-758)
- `_build_traces_devices_tab()` (lines 760-869)
- `_build_routes_tab()` (the routes tab builder)

Also remove the old `self._tabs`, `self._json_preview`, `self._overview` references.

- [ ] **Step 6: Update `_build_ui` — remove editor preview from initial UI build**

The editor view is built once and stays in the page stack, no need for the splitter.

- [ ] **Step 7: Commit**

```bash
git add src/replay_ui_qt/views/scenarios_view.py
git commit -m "feat: build flat scenario editor replacing QTabWidget"
```

---

### Task 5: Remove JSON preview and schema summary from _sync_draft

**Files:**
- Modify: `src/replay_ui_qt/views/scenarios_view.py:_sync_draft`

Update `_sync_draft` to remove references to `self._json_preview` and `self._overview`. Also remove the `overview_text()`, `json_preview_text()`, `routes_preview_text()` public test helper methods.

- [ ] **Step 1: Update `_sync_draft` — remove JSON and overview references**

```python
    def _sync_draft(self) -> None:
        draft = self._view_model.draft
        if draft is None:
            self._name_edit.setText("")
            self._name_edit.setEnabled(False)
            self._loop_check.setChecked(False)
            self._loop_check.setEnabled(False)
            self._clear_device_controls()
            self._clear_target_controls()
            self._route_source_combo.clear()
            self._route_source_combo.setEnabled(False)
            self._route_logical_spin.setValue(0)
            self._route_logical_spin.setEnabled(False)
            self._route_target_combo.clear()
            self._route_target_combo.setEnabled(False)
            self._target_physical_spin.setValue(0)
            self._target_physical_spin.setEnabled(False)
            self._route_issue_label.setText("")
            self._trace_model.set_rows(())
            self._device_model.set_rows(())
            self._target_model.set_rows(())
            self._route_model.set_rows(())
        else:
            self._sync_edit_controls(draft)
            self._trace_model.set_rows(draft.traces)
            self._device_model.set_rows(draft.devices)
            self._target_model.set_rows(draft.targets)
            self._route_model.set_rows(draft.routes)
            if draft.devices:
                row = min(max(self._selected_device_index(), 0), len(draft.devices) - 1)
                self._devices_table.selectRow(row)
                self._sync_device_controls_for_current_device()
            else:
                self._devices_table.clearSelection()
                self._sync_device_controls_for_current_device()
            if draft.targets:
                row = min(max(self._selected_target_index(), 0), len(draft.targets) - 1)
                self._targets_table.selectRow(row)
                self._sync_target_controls_for_current_target()
            else:
                self._targets_table.clearSelection()
                self._sync_target_controls_for_current_target()
            if draft.routes:
                row = min(max(self._selected_route_index(), 0), len(draft.routes) - 1)
                self._routes_table.selectRow(row)
                self._sync_edit_controls_for_current_route()
            else:
                self._routes_table.clearSelection()
                self._sync_edit_controls_for_current_route()
        self._sync_command_buttons()
        self.inspectorChanged.emit(*self.inspector_snapshot())
```

- [ ] **Step 2: Remove public test helper methods that reference removed widgets**

Remove:
- `overview_text()` — returns `self._overview.toPlainText()`
- `json_preview_text()` — returns `self._json_preview.toPlainText()`

Keep `routes_preview_text()` — it's pure computation from the draft, no widget dependency.

- [ ] **Step 3: Update `_sync_command_buttons` to sync editor-specific buttons**

Add to `_sync_command_buttons`:

```python
        self._editor_validate_button.setEnabled(has_draft and idle)
        self._editor_run_button.setEnabled(has_draft and not self._view_model.has_blocking_issues and idle)
```

- [ ] **Step 4: Commit**

```bash
git add src/replay_ui_qt/views/scenarios_view.py
git commit -m "refactor: remove JSON preview and schema summary from _sync_draft"
```

---

### Task 6: Update tests — replace dialog tests with editor tests

**Files:**
- Modify: `tests/test_ui_views.py:790-870`

Replace the 4 dialog tests (`test_new_scenario_dialog_*`, `test_add_route_dialog_*`) with editor-based equivalents. Update tests that reference `json_preview_text()` and `overview_text()`.

- [ ] **Step 1: Replace dialog tests with editor page-switching test**

Replace `test_new_scenario_dialog_exposes_trace_and_source_choices` and `test_new_scenario_dialog_reports_no_traces`:

```python
    def test_new_scenario_switches_to_editor_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = _trace_record(tmp)
            scenario_app = _ScenarioApp(
                trace_records=[trace],
                trace_inspection=_inspection(trace),
            )
            view_model = ScenariosViewModel(scenario_app, _runner())
            view = ScenariosView(view_model)
            try:
                _wait_for(lambda: not view_model.busy, self._app)
                view_model.load_trace_choices()
                _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
                self.assertEqual(0, view.current_page_index())
                view.trigger_new_scenario()
                self.assertEqual(1, view.current_page_index())
            finally:
                view.close()
                self._app.processEvents()
```

Replace `test_add_route_dialog_exposes_trace_source_and_channel_choices` and `test_add_route_dialog_reports_no_traces`:

```python
    def test_add_route_button_adds_route_in_editor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = _trace_record(tmp)
            scenario_app = _ScenarioApp(
                trace_records=[trace],
                trace_inspection=_inspection(trace),
            )
            view_model = ScenariosViewModel(scenario_app, _runner())
            view = ScenariosView(view_model)
            try:
                _wait_for(lambda: not view_model.busy, self._app)
                view_model.load_trace_choices()
                _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
                source = view_model.source_choices_for_trace(trace.trace_id)[0]
                view_model.create_new_scenario_from_trace(view_model.trace_choices[0], source)
                self.assertFalse(view.add_route_enabled())
                view.switch_to_editor()
                self.assertTrue(view.add_route_enabled())
                self.assertIn("trace1 / CH0 CANFD", view.routes_preview_text())
            finally:
                view.close()
                self._app.processEvents()
```

- [ ] **Step 2: Update tests that reference `overview_text()` and `json_preview_text()`**

In `test_loaded_scenario_draft_is_rendered_in_preview_tabs` (line 872):
- Remove `self.assertIn("demo-scenario", view.overview_text())` — overview text area removed
- Remove `self.assertIn('"schema_version": 2', view.json_preview_text())` — JSON preview removed
- Keep name, loop, and routes checks

```python
    def test_loaded_scenario_draft_is_rendered_in_editor(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            self.assertEqual("demo-scenario", view.overview_name_text())
            self.assertFalse(view.overview_loop_checked())
            self.assertIn("trace1 / CH0 CANFD -> 0 -> mock0 / CH0 CANFD", view.routes_preview_text())
            _title, body = view.inspector_snapshot()
            self.assertIn("Scenario ID: scenario-1", body)
            self.assertIn("Routes: 1", body)
        finally:
            view.close()
            self._app.processEvents()
```

In `test_overview_and_route_edits_update_preview_and_json` (line 894):
- Remove `overview_text()` and `json_preview_text()` assertions
- Keep name, loop, routes assertions

```python
    def test_overview_and_route_edits_update_editor(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            view.edit_overview_name("edited-scenario")
            view.edit_overview_loop(True)
            view.edit_route_logical_channel(4)
            view.edit_target_physical_channel(2)

            self.assertEqual("edited-scenario", view.overview_name_text())
            self.assertTrue(view.overview_loop_checked())
            self.assertIn("trace1 / CH0 CANFD -> 4 -> mock0 / CH2 CANFD", view.routes_preview_text())
            self.assertTrue(view.run_enabled())
        finally:
            view.close()
            self._app.processEvents()
```

In `test_device_and_target_editors_update_preview_and_lock_with_replay` (line 920):
- Remove `json_preview_text()` assertions, replace with `overview_name_text()` or other available checks

```python
    def test_device_and_target_editors_update_and_lock_with_replay(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            self.assertTrue(view.add_device_enabled())
            self.assertTrue(view.add_target_enabled())
            view.select_device(0)
            view.edit_device_driver("tongxing")
            view.edit_device_sdk_root("C:/TSMaster")
            view.edit_device_application("BenchApp")
            view.edit_device_type("TC1014")
            view.edit_device_index(3)
            view.select_target(0)
            view.edit_target_bus("CAN")
            view.edit_target_nominal_baud(250000)
            view.edit_target_data_baud(1000000)
            view.edit_target_resistance_enabled(False)
            view.edit_target_listen_only(True)
            view.edit_target_tx_echo(True)

            view.set_replay_active(True)
            self.assertFalse(view.add_device_enabled())
            self.assertFalse(view.remove_device_enabled())
            self.assertFalse(view.add_target_enabled())
            self.assertFalse(view.remove_target_enabled())
        finally:
            view.close()
            self._app.processEvents()
```

In `test_route_source_target_edits_update_selected_route_preview_and_json` (line 990):
- Remove `json_preview_text()` assertions

```python
    def test_route_source_target_edits_update_selected_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = _trace_record(tmp, trace_id="trace1")
            scenario_app = _ScenarioApp(
                records=[_scenario_record()],
                trace_records=[trace],
                trace_inspection=_inspection(trace),
            )
            view_model = ScenariosViewModel(scenario_app, _runner())
            view = ScenariosView(view_model)
            try:
                _wait_for(lambda: view.refresh_enabled(), self._app)
                view.select_row(0)
                view_model.load_scenario("scenario-1")
                _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
                view_model.load_trace_choices()
                _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
                source = view_model.source_choices_for_trace(trace.trace_id)[0]
                view_model.add_route_from_trace(
                    view_model.trace_choices[0],
                    source,
                    logical_channel=1,
                    physical_channel=1,
                )

                view.select_route(0)
                view.edit_route_target("mock0-ch1-canfd")
                view.edit_route_logical_channel(5)
                view.edit_route_source("source0")

                self.assertIn("trace1 / CH0 CANFD -> 5 -> mock0 / CH1 CANFD", view.routes_preview_text())
                self.assertTrue(view.remove_route_enabled())
                self.assertTrue(view.run_enabled())
            finally:
                view.close()
                self._app.processEvents()
```

In `test_run_signal_and_active_replay_lock_editor_commands` (line 750):
- Remove the `before = view.json_preview_text()` and the `self.assertEqual(before, view.json_preview_text())` assertion
- Replace with checking that overview name doesn't change:

```python
            view.set_replay_active(True)
            before = view.overview_name_text()

            # ... assertions ...

            view.edit_overview_name("blocked-edit")
            self.assertEqual(before, view.overview_name_text())
```

- [ ] **Step 3: Add test helper methods needed by tests**

Add to `ScenariosView`:

```python
    def current_page_index(self) -> int:
        """Return the current page stack index (0=list, 1=editor)."""
        return self._page_stack.currentIndex()

    def trigger_new_scenario(self) -> None:
        """Trigger New Scenario for tests."""
        self._start_new_scenario()

    def switch_to_editor(self) -> None:
        """Switch to the editor page for tests."""
        self._switch_to_editor()
```

- [ ] **Step 4: Add `has_create_action` → `add_route_enabled` compatibility**

No action needed — `add_route_enabled()` already exists.

- [ ] **Step 5: Add back-button test**

```python
    def test_back_button_returns_to_list_and_discards_draft(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
            view.switch_to_editor()
            self.assertEqual(1, view.current_page_index())
            view.trigger_back_to_list()
            self.assertEqual(0, view.current_page_index())
        finally:
            view.close()
            self._app.processEvents()
```

Add to `ScenariosView`:

```python
    def trigger_back_to_list(self) -> None:
        """Trigger Back to list button for tests."""
        self._back_to_list()
```

- [ ] **Step 6: Run tests to verify all pass**

```bash
cd /Users/lanyy/Code/replay_tool && uv run python -m unittest tests.test_ui_views.ScenariosViewTests -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add tests/test_ui_views.py src/replay_ui_qt/views/scenarios_view.py
git commit -m "test: replace dialog tests with editor page-switching tests"
```

---

### Task 7: Final cleanup and verification

**Files:**
- Modify: `src/replay_ui_qt/views/scenarios_view.py`

Remove remaining dead code: unused imports, unused helper functions, any remaining references to removed widgets.

- [ ] **Step 1: Remove unused imports**

Check if `NewScenarioDialog` and `AddRouteDialog` are imported anywhere else:

```bash
cd /Users/lanyy/Code/replay_tool && grep -r "NewScenarioDialog\|AddRouteDialog" src/ tests/ || echo "No references found"
```

- [ ] **Step 2: Remove `_read_only_text` helper if no longer used**

Check if `_read_only_text` is still referenced:

```bash
cd /Users/lanyy/Code/replay_tool && grep -n "_read_only_text" src/replay_ui_qt/views/scenarios_view.py
```

If not referenced, remove the function.

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/lanyy/Code/replay_tool && uv run python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 4: Run lint**

```bash
cd /Users/lanyy/Code/replay_tool && uv run ruff check src tests
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add src/replay_ui_qt/views/scenarios_view.py
git commit -m "chore: remove dead code after scenario editor refactor"
```

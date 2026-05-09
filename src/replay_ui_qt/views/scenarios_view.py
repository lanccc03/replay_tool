from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.view_models.scenarios import (
    DraftRouteRow,
    DraftTargetRow,
    ScenarioDeleteResultDetails,
    ScenarioDraft,
    ScenarioDraftIssue,
    ScenarioRow,
    ScenarioSourceChoice,
    ScenarioTraceChoice,
    ScenarioValidationDetails,
    ScenariosViewModel,
)
from replay_ui_qt.widgets.dialogs import create_danger_confirmation, create_error_details_dialog
from replay_ui_qt.widgets.empty_state import EmptyState
from replay_ui_qt.widgets.status_badge import StatusBadge
from replay_ui_qt.widgets.table_model import ObjectTableModel, TableColumn


class ScenariosView(QWidget):
    """Scenarios page with a read-only table of saved schema v2 scenarios."""

    inspectorChanged = Signal(str, str)

    def __init__(self, view_model: ScenariosViewModel) -> None:
        """Create the Scenarios view.

        Args:
            view_model: ViewModel that supplies scenario rows.
        """
        super().__init__()
        self._view_model = view_model
        self._model = ObjectTableModel(
            (
                TableColumn("名称", lambda row: row.name),
                TableColumn("Scenario ID", lambda row: row.scenario_id, monospace=True),
                TableColumn("Traces", lambda row: row.trace_count, align_right=True),
                TableColumn("Routes", lambda row: row.route_count, align_right=True),
                TableColumn("Updated", lambda row: row.updated_at, monospace=True),
                TableColumn("Base dir", lambda row: row.base_dir, tooltip=lambda row: row.base_dir),
            )
        )
        self._trace_model = ObjectTableModel(
            (
                TableColumn("Trace ID", lambda row: row.trace_id, monospace=True),
                TableColumn("Path", lambda row: row.path, tooltip=lambda row: row.path),
            )
        )
        self._device_model = ObjectTableModel(
            (
                TableColumn("Device ID", lambda row: row.device_id, monospace=True),
                TableColumn("Driver", lambda row: row.driver),
                TableColumn("Device Type", lambda row: row.device_type),
                TableColumn("Index", lambda row: row.device_index, align_right=True),
            )
        )
        self._route_model = ObjectTableModel(
            (
                TableColumn("Trace Source", lambda row: row.source_label, tooltip=lambda row: row.source_id),
                TableColumn("Logical Channel", lambda row: row.logical_channel, align_right=True),
                TableColumn("Device Target", lambda row: row.target_label, tooltip=lambda row: row.target_id),
            )
        )
        self._build_ui()
        self._open_new_dialog_after_trace_load = False
        self._open_add_route_dialog_after_trace_load = False
        self._view_model.rowsChanged.connect(self._sync_rows)
        self._view_model.statusMessageChanged.connect(lambda message: self.inspectorChanged.emit("Scenarios", message))
        self._view_model.errorChanged.connect(self._show_error)
        self._view_model.busyChanged.connect(self._sync_busy)
        self._view_model.draftChanged.connect(self._sync_draft)
        self._view_model.validationChanged.connect(self._sync_validation)
        self._view_model.deleteResultChanged.connect(self._sync_delete_result)
        self._view_model.traceChoicesChanged.connect(self._sync_trace_choices)
        self._view_model.draftIssuesChanged.connect(self._sync_draft_issues)
        self._view_model.refresh()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        delete_result = self._view_model.delete_result
        if delete_result is not None and self._view_model.draft is None:
            return ("Scenario 删除结果", _delete_result_detail(delete_result))
        validation = self._view_model.validation
        if validation is not None:
            return ("Scenario 校验结果", _validation_detail(validation))
        draft = self._view_model.draft
        if draft is not None and self._view_model.draft_issues:
            return ("Scenario Draft Issues", _draft_issue_detail(self._view_model.draft_issues))
        if draft is not None:
            return ("Scenario Draft", _draft_detail(draft))
        row = self._selected_row()
        if row is None:
            return ("Scenarios", "选择一个 Scenario 后加载只读 draft preview。")
        return ("Scenario 详情", _scenario_detail(row))

    def refresh_enabled(self) -> bool:
        """Return whether the refresh button is enabled.

        Returns:
            True when refresh can be triggered.
        """
        return self._refresh_button.isEnabled()

    def new_enabled(self) -> bool:
        """Return whether New Scenario is enabled.

        Returns:
            True when a new draft can be started.
        """
        return self._new_button.isEnabled()

    def load_enabled(self) -> bool:
        """Return whether the load button is enabled.

        Returns:
            True when the selected scenario can be loaded.
        """
        return self._load_button.isEnabled()

    def save_enabled(self) -> bool:
        """Return whether Save Scenario is enabled.

        Returns:
            True when a loaded draft can be saved.
        """
        return self._save_button.isEnabled()

    def validate_enabled(self) -> bool:
        """Return whether Validate is enabled.

        Returns:
            True when a loaded draft can be validated.
        """
        return self._validate_button.isEnabled()

    def run_enabled(self) -> bool:
        """Return whether Run is enabled.

        Returns:
            Always False in the read-only M3 first batch.
        """
        return self._run_button.isEnabled()

    def delete_enabled(self) -> bool:
        """Return whether Delete is enabled.

        Returns:
            True when a selected scenario can be deleted.
        """
        return self._delete_button.isEnabled()

    def add_route_enabled(self) -> bool:
        """Return whether Add Route is enabled.

        Returns:
            True when the loaded draft can accept another route.
        """
        return self._add_route_button.isEnabled()

    def remove_route_enabled(self) -> bool:
        """Return whether Remove Route is enabled.

        Returns:
            True when a route is selected and can be removed.
        """
        return self._remove_route_button.isEnabled()

    def error_details_enabled(self) -> bool:
        """Return whether the error details button is enabled.

        Returns:
            True when an error can be opened.
        """
        return self._error_button.isEnabled()

    def status_badge_state(self) -> tuple[str, str]:
        """Return status badge text and semantic key.

        Returns:
            Tuple of visible text and semantic state.
        """
        return self._status_badge.text(), self._status_badge.semantic

    def select_row(self, row: int) -> None:
        """Select one saved scenario row.

        Args:
            row: Zero-based table row index.
        """
        if 0 <= row < self._model.rowCount():
            self._table.selectRow(row)
            self._emit_selection()
            self._sync_command_buttons()

    def overview_text(self) -> str:
        """Return the Scenario Editor overview text.

        Returns:
            Plain overview preview text.
        """
        return self._overview.toPlainText()

    def routes_preview_text(self) -> str:
        """Return the route mapping preview text.

        Returns:
            Text representation of current draft route mappings.
        """
        draft = self._view_model.draft
        if draft is None:
            return ""
        return "\n".join(_route_preview(route) for route in draft.routes)

    def json_preview_text(self) -> str:
        """Return the read-only JSON preview text.

        Returns:
            Formatted schema v2 JSON text.
        """
        return self._json_preview.toPlainText()

    def overview_name_text(self) -> str:
        """Return the editable overview name field text.

        Returns:
            Scenario name shown in the overview editor.
        """
        return self._name_edit.text()

    def overview_loop_checked(self) -> bool:
        """Return the editable overview loop checkbox state.

        Returns:
            True when loop is enabled.
        """
        return self._loop_check.isChecked()

    def edit_overview_name(self, name: str) -> None:
        """Set the overview name field for tests and keyboard workflows.

        Args:
            name: New scenario name.
        """
        self._name_edit.setText(str(name))
        self._apply_name_edit()

    def edit_overview_loop(self, loop: bool) -> None:
        """Set the overview loop checkbox for tests and keyboard workflows.

        Args:
            loop: New loop value.
        """
        self._loop_check.setChecked(bool(loop))
        self._apply_loop_edit()

    def edit_route_logical_channel(self, value: int) -> None:
        """Set the selected route logical channel through the edit control.

        Args:
            value: New logical channel value.
        """
        self._route_logical_spin.setValue(int(value))
        self._apply_route_logical_edit()

    def edit_route_source(self, source_id: str) -> None:
        """Set the selected route source through the edit control.

        Args:
            source_id: Source endpoint ID to select.
        """
        index = self._combo_index_for_data(self._route_source_combo, source_id)
        if index >= 0:
            self._route_source_combo.setCurrentIndex(index)
        self._apply_route_source_edit()

    def edit_route_target(self, target_id: str) -> None:
        """Set the selected route target through the edit control.

        Args:
            target_id: Target endpoint ID to select.
        """
        index = self._combo_index_for_data(self._route_target_combo, target_id)
        if index >= 0:
            self._route_target_combo.setCurrentIndex(index)
        self._apply_route_target_edit()

    def edit_target_physical_channel(self, value: int) -> None:
        """Set the selected route target physical channel through the edit control.

        Args:
            value: New physical channel value.
        """
        self._target_physical_spin.setValue(int(value))
        self._apply_target_physical_edit()

    def select_route(self, row: int) -> None:
        """Select one route row in the editor.

        Args:
            row: Zero-based route row index.
        """
        if 0 <= row < self._route_model.rowCount():
            self._routes_table.selectRow(row)
            self._sync_edit_controls_for_current_route()

    def create_new_dialog(self):
        """Create a New Scenario dialog from current trace choices.

        Returns:
            New Scenario dialog for tests or user interaction.
        """
        return NewScenarioDialog(self, self._view_model)

    def create_add_route_dialog(self):
        """Create an Add Route dialog from current trace choices.

        Returns:
            Add Route dialog for tests or user interaction.
        """
        return AddRouteDialog(self, self._view_model)

    def create_error_dialog(self):
        """Create the current error details dialog.

        Returns:
            Error details dialog for the current ViewModel error.
        """
        return create_error_details_dialog(
            self,
            title="Scenarios 错误",
            summary="Scenarios 操作失败",
            detail=self._view_model.error,
        )

    def create_delete_confirmation_dialog(self):
        """Create the delete confirmation dialog for the selected scenario.

        Returns:
            Standard dangerous-action confirmation message box.
        """
        row = self._selected_row()
        object_label = row.name if row is not None else "Scenario"
        object_id = row.scenario_id if row is not None else ""
        return create_danger_confirmation(
            self,
            action="Delete Scenario",
            object_label=object_label,
            object_id=object_id,
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        self._new_button = QPushButton("New Scenario")
        self._new_button.setToolTip("从已导入 Trace 创建最小 schema v2 Scenario draft")
        self._new_button.clicked.connect(self._start_new_scenario)
        toolbar.addWidget(self._new_button)

        self._refresh_button = QPushButton("刷新")
        self._refresh_button.setToolTip("重新读取当前 workspace 的 Scenario Store")
        self._refresh_button.clicked.connect(self._view_model.refresh)
        toolbar.addWidget(self._refresh_button)

        self._load_button = QPushButton("Load Scenario")
        self._load_button.setEnabled(False)
        self._load_button.setToolTip("加载选中 Scenario 的只读 draft preview")
        self._load_button.clicked.connect(self._load_selected_scenario)
        toolbar.addWidget(self._load_button)

        self._save_button = QPushButton("Save Scenario")
        self._save_button.setEnabled(False)
        self._save_button.setToolTip("保存当前 loaded Scenario draft")
        self._save_button.clicked.connect(self._save_loaded_scenario)
        toolbar.addWidget(self._save_button)
        self._validate_button = QPushButton("Validate")
        self._validate_button.setEnabled(False)
        self._validate_button.setToolTip("校验并编译当前 loaded Scenario draft")
        self._validate_button.clicked.connect(self._validate_loaded_scenario)
        toolbar.addWidget(self._validate_button)
        self._run_button = QPushButton("Run")
        self._run_button.setEnabled(False)
        self._run_button.setToolTip("M4 Replay Monitor 接入后启用")
        toolbar.addWidget(self._run_button)
        self._delete_button = QPushButton("Delete")
        self._delete_button.setEnabled(False)
        self._delete_button.setToolTip("删除选中 Scenario")
        self._delete_button.clicked.connect(self._delete_selected_scenario)
        toolbar.addWidget(self._delete_button)
        self._error_button = QPushButton("错误详情")
        self._error_button.setEnabled(False)
        self._error_button.setToolTip("查看可复制的错误详情")
        self._error_button.clicked.connect(self._show_error_details)
        toolbar.addWidget(self._error_button)
        self._status_badge = StatusBadge("Idle", "default")
        toolbar.addWidget(self._status_badge)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._stack = QStackedWidget()
        self._table = QTableView()
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._table.setModel(self._model)
        self._table.verticalHeader().setVisible(False)
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(1, 220)
        self._table.setColumnWidth(2, 90)
        self._table.setColumnWidth(3, 90)
        self._table.setColumnWidth(4, 160)
        self._table.setColumnWidth(5, 260)
        self._table.selectionModel().currentRowChanged.connect(lambda _current, _previous: self._handle_selection_changed())
        self._empty = EmptyState("No scenarios.", "使用 CLI 保存 schema v2 scenario 后，这里会显示 Scenario Store 记录。")
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)
        splitter.addWidget(self._stack)
        splitter.addWidget(self._build_editor_preview())
        splitter.setSizes([280, 360])
        layout.addWidget(splitter, 1)

    def _sync_rows(self) -> None:
        self._model.set_rows(self._view_model.rows)
        self._stack.setCurrentWidget(self._empty if not self._view_model.rows else self._table)
        self._sync_status_badge()
        self._sync_command_buttons()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _show_error(self, message: str) -> None:
        self._error_button.setEnabled(bool(message))
        self._sync_status_badge()
        if message:
            self.inspectorChanged.emit("Scenarios 错误", message)

    def _sync_busy(self, busy: bool) -> None:
        self._new_button.setEnabled(not busy)
        self._refresh_button.setEnabled(not busy)
        self._sync_command_buttons()
        self._sync_status_badge()

    def _sync_status_badge(self) -> None:
        if self._view_model.error:
            self._status_badge.set_status("Failed", "failed")
        elif self._view_model.busy:
            self._status_badge.set_status("Loading", "running")
        elif self._view_model.rows:
            self._status_badge.set_status("Ready", "ready")
        else:
            self._status_badge.set_status("No records", "disabled")

    def _show_error_details(self) -> None:
        if not self._view_model.error:
            return
        self.create_error_dialog().exec()

    def _build_editor_preview(self) -> QWidget:
        preview = QWidget()
        layout = QVBoxLayout(preview)
        layout.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(), "Overview")
        self._tabs.addTab(self._build_traces_devices_tab(), "Traces & Devices")
        self._tabs.addTab(self._build_routes_tab(), "Routes")
        self._json_preview = _read_only_text("加载 Scenario 后显示格式化 JSON。")
        self._tabs.addTab(self._json_preview, "JSON")
        layout.addWidget(self._tabs)
        return preview

    def _build_overview_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
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
        self._overview = _read_only_text("加载或新建 Scenario 后显示 schema、数量和 base dir。")
        layout.addWidget(self._overview, 1)
        return tab

    def _build_traces_devices_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        traces = QTableView()
        traces.setModel(self._trace_model)
        traces.verticalHeader().setVisible(False)
        traces.setColumnWidth(0, 180)
        traces.setColumnWidth(1, 520)
        devices = QTableView()
        devices.setModel(self._device_model)
        devices.verticalHeader().setVisible(False)
        devices.setColumnWidth(0, 180)
        devices.setColumnWidth(1, 120)
        devices.setColumnWidth(2, 160)
        devices.setColumnWidth(3, 80)
        layout.addWidget(traces)
        layout.addWidget(devices)
        return tab

    def _build_routes_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        toolbar = QHBoxLayout()
        self._add_route_button = QPushButton("Add Route")
        self._add_route_button.setEnabled(False)
        self._add_route_button.setToolTip("从已导入 Trace source 添加一条 route")
        self._add_route_button.clicked.connect(self._start_add_route)
        toolbar.addWidget(self._add_route_button)
        self._remove_route_button = QPushButton("Remove Route")
        self._remove_route_button.setEnabled(False)
        self._remove_route_button.setToolTip("删除当前选中的 route，不删除 source/target 资源")
        self._remove_route_button.clicked.connect(self._remove_selected_route)
        toolbar.addWidget(self._remove_route_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        form = QFormLayout()
        self._route_source_combo = QComboBox()
        self._route_source_combo.setEnabled(False)
        self._route_source_combo.currentIndexChanged.connect(lambda _index: self._apply_route_source_edit())
        self._route_logical_spin = QSpinBox()
        self._route_logical_spin.setRange(0, 255)
        self._route_logical_spin.setEnabled(False)
        self._route_logical_spin.editingFinished.connect(self._apply_route_logical_edit)
        self._route_target_combo = QComboBox()
        self._route_target_combo.setEnabled(False)
        self._route_target_combo.currentIndexChanged.connect(lambda _index: self._apply_route_target_edit())
        self._target_physical_spin = QSpinBox()
        self._target_physical_spin.setRange(0, 255)
        self._target_physical_spin.setEnabled(False)
        self._target_physical_spin.editingFinished.connect(self._apply_target_physical_edit)
        form.addRow("Source", self._route_source_combo)
        form.addRow("Logical Channel", self._route_logical_spin)
        form.addRow("Target", self._route_target_combo)
        form.addRow("Target Physical Channel", self._target_physical_spin)
        layout.addLayout(form)
        self._routes_table = QTableView()
        self._routes_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._routes_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._routes_table.setModel(self._route_model)
        self._routes_table.verticalHeader().setVisible(False)
        self._routes_table.setColumnWidth(0, 260)
        self._routes_table.setColumnWidth(1, 140)
        self._routes_table.setColumnWidth(2, 260)
        self._routes_table.selectionModel().currentRowChanged.connect(
            lambda _current, _previous: self._handle_route_selection_changed()
        )
        layout.addWidget(self._routes_table)
        return tab

    def _handle_selection_changed(self) -> None:
        self._sync_command_buttons()
        self._emit_selection()

    def _load_selected_scenario(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        self._view_model.load_scenario(row.scenario_id)

    def _start_new_scenario(self) -> None:
        if not self._view_model.trace_choices:
            self._open_new_dialog_after_trace_load = True
            self._view_model.load_trace_choices()
            return
        self._show_new_scenario_dialog()

    def _show_new_scenario_dialog(self) -> None:
        dialog = self.create_new_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            trace, source, name = dialog.selection()
            if trace is not None and source is not None:
                self._view_model.create_new_scenario_from_trace(trace, source, name=name)

    def _start_add_route(self) -> None:
        if self._view_model.draft is None:
            return
        if not self._view_model.trace_choices:
            self._open_add_route_dialog_after_trace_load = True
            self._view_model.load_trace_choices()
            return
        self._show_add_route_dialog()

    def _show_add_route_dialog(self) -> None:
        dialog = self.create_add_route_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            trace, source, logical_channel, physical_channel = dialog.selection()
            if trace is not None and source is not None:
                self._view_model.add_route_from_trace(
                    trace,
                    source,
                    logical_channel=logical_channel,
                    physical_channel=physical_channel,
                )

    def _remove_selected_route(self) -> None:
        index = self._selected_route_index()
        if index >= 0:
            self._view_model.remove_route(index)

    def _save_loaded_scenario(self) -> None:
        self._view_model.save_loaded_scenario()

    def _validate_loaded_scenario(self) -> None:
        self._view_model.validate_loaded_scenario()

    def _delete_selected_scenario(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        dialog = self.create_delete_confirmation_dialog()
        if dialog.exec() == QMessageBox.StandardButton.Ok:
            self._view_model.delete_scenario(row.scenario_id)

    def _sync_command_buttons(self) -> None:
        row = self._selected_row()
        has_draft = self._view_model.draft is not None
        route_index = self._selected_route_index()
        has_route = has_draft and route_index >= 0
        idle = not self._view_model.busy
        self._new_button.setEnabled(idle)
        self._load_button.setEnabled(row is not None and idle)
        self._save_button.setEnabled(has_draft and idle)
        self._validate_button.setEnabled(has_draft and idle)
        self._delete_button.setEnabled(row is not None and idle)
        self._add_route_button.setEnabled(has_draft and idle)
        self._remove_route_button.setEnabled(has_route and idle)
        self._route_source_combo.setEnabled(has_route and idle)
        self._route_logical_spin.setEnabled(has_route and idle)
        self._route_target_combo.setEnabled(has_route and idle)
        self._target_physical_spin.setEnabled(has_route and idle)
        self._run_button.setEnabled(False)

    def _sync_draft(self) -> None:
        draft = self._view_model.draft
        if draft is None:
            self._name_edit.setText("")
            self._name_edit.setEnabled(False)
            self._loop_check.setChecked(False)
            self._loop_check.setEnabled(False)
            self._route_source_combo.clear()
            self._route_source_combo.setEnabled(False)
            self._route_logical_spin.setValue(0)
            self._route_logical_spin.setEnabled(False)
            self._route_target_combo.clear()
            self._route_target_combo.setEnabled(False)
            self._target_physical_spin.setValue(0)
            self._target_physical_spin.setEnabled(False)
            self._overview.setPlainText("加载或新建 Scenario 后显示 schema、数量和 base dir。")
            self._trace_model.set_rows(())
            self._device_model.set_rows(())
            self._route_model.set_rows(())
            self._json_preview.setPlainText("加载 Scenario 后显示格式化 JSON。")
        else:
            self._sync_edit_controls(draft)
            self._overview.setPlainText(_draft_detail(draft))
            self._trace_model.set_rows(draft.traces)
            self._device_model.set_rows(draft.devices)
            self._route_model.set_rows(draft.routes)
            self._json_preview.setPlainText(draft.json_text)
            if draft.routes:
                row = min(max(self._selected_route_index(), 0), len(draft.routes) - 1)
                self._routes_table.selectRow(row)
                self._sync_edit_controls_for_current_route()
            else:
                self._routes_table.clearSelection()
                self._sync_edit_controls_for_current_route()
        self._sync_command_buttons()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_validation(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_delete_result(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_draft_issues(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_trace_choices(self) -> None:
        if self._open_new_dialog_after_trace_load:
            self._open_new_dialog_after_trace_load = False
            self._show_new_scenario_dialog()
        elif self._open_add_route_dialog_after_trace_load:
            self._open_add_route_dialog_after_trace_load = False
            self._show_add_route_dialog()

    def _sync_edit_controls(self, draft: ScenarioDraft) -> None:
        self._name_edit.blockSignals(True)
        self._name_edit.setText(draft.name)
        self._name_edit.setEnabled(True)
        self._name_edit.blockSignals(False)

        loop = bool(draft.body.get("timeline", {}).get("loop", False)) if isinstance(draft.body.get("timeline"), dict) else False
        self._loop_check.blockSignals(True)
        self._loop_check.setChecked(loop)
        self._loop_check.setEnabled(True)
        self._loop_check.blockSignals(False)

    def _sync_edit_controls_for_current_route(self) -> None:
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        route = draft.routes[route_index] if draft is not None and 0 <= route_index < len(draft.routes) else None
        self._route_source_combo.blockSignals(True)
        self._route_source_combo.clear()
        for choice in self._view_model.source_endpoint_choices:
            self._route_source_combo.addItem(choice.label, choice.source_id)
        if route is not None:
            source_index = self._combo_index_for_data(self._route_source_combo, route.source_id)
            if source_index >= 0:
                self._route_source_combo.setCurrentIndex(source_index)
        self._route_source_combo.blockSignals(False)

        self._route_logical_spin.blockSignals(True)
        self._route_logical_spin.setValue(route.logical_channel if route is not None else 0)
        self._route_logical_spin.blockSignals(False)

        self._route_target_combo.blockSignals(True)
        self._route_target_combo.clear()
        for choice in self._view_model.target_endpoint_choices:
            self._route_target_combo.addItem(choice.label, choice.target_id)
        if route is not None:
            target_index = self._combo_index_for_data(self._route_target_combo, route.target_id)
            if target_index >= 0:
                self._route_target_combo.setCurrentIndex(target_index)
        self._route_target_combo.blockSignals(False)

        self._target_physical_spin.blockSignals(True)
        target = self._selected_route_target()
        self._target_physical_spin.setValue(target.physical_channel if target is not None else 0)
        self._target_physical_spin.blockSignals(False)
        self._sync_command_buttons()

    def _apply_name_edit(self) -> None:
        draft = self._view_model.draft
        value = self._name_edit.text()
        if draft is not None and value != draft.name:
            self._view_model.rename_loaded_scenario(value)

    def _apply_loop_edit(self) -> None:
        draft = self._view_model.draft
        if draft is not None:
            self._view_model.set_timeline_loop(self._loop_check.isChecked())

    def _apply_route_logical_edit(self) -> None:
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        if draft is not None and route_index >= 0:
            self._view_model.set_route_logical_channel(route_index, self._route_logical_spin.value())

    def _apply_route_source_edit(self) -> None:
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        source_id = self._route_source_combo.currentData()
        if draft is not None and route_index >= 0 and source_id is not None:
            self._view_model.set_route_source(route_index, str(source_id))

    def _apply_route_target_edit(self) -> None:
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        target_id = self._route_target_combo.currentData()
        if draft is not None and route_index >= 0 and target_id is not None:
            self._view_model.set_route_target(route_index, str(target_id))

    def _apply_target_physical_edit(self) -> None:
        draft = self._view_model.draft
        target_index = self._selected_route_target_index()
        if draft is not None and target_index >= 0:
            self._view_model.set_target_physical_channel(target_index, self._target_physical_spin.value())

    def _handle_route_selection_changed(self) -> None:
        self._sync_edit_controls_for_current_route()
        self._emit_selection()

    def _emit_selection(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _selected_row(self) -> ScenarioRow | None:
        current = self._table.currentIndex()
        if not current.isValid():
            return None
        row = self._model.row_at(current.row())
        return row if isinstance(row, ScenarioRow) else None

    def _selected_route_index(self) -> int:
        draft = self._view_model.draft
        current = self._routes_table.currentIndex()
        if draft is None or not current.isValid():
            return -1
        row = current.row()
        return row if 0 <= row < len(draft.routes) else -1

    def _selected_route_target_index(self) -> int:
        target = self._selected_route_target()
        if target is None:
            return -1
        draft = self._view_model.draft
        if draft is None:
            return -1
        for index, row in enumerate(draft.targets):
            if row.target_id == target.target_id:
                return index
        return -1

    def _selected_route_target(self) -> DraftTargetRow | None:
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        if draft is None or route_index < 0:
            return None
        target_id = draft.routes[route_index].target_id
        for target in draft.targets:
            if target.target_id == target_id:
                return target
        return None

    def _combo_index_for_data(self, combo: QComboBox, value: object) -> int:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                return index
        return -1


def _scenario_detail(row: ScenarioRow) -> str:
    return "\n".join(
        (
            f"名称: {row.name}",
            f"Scenario ID: {row.scenario_id}",
            f"Traces: {row.trace_count}",
            f"Routes: {row.route_count}",
            f"Updated: {row.updated_at}",
            f"Base dir: {row.base_dir}",
        )
    )


def _draft_detail(draft: ScenarioDraft) -> str:
    return "\n".join(
        (
            f"名称: {draft.name}",
            f"Scenario ID: {draft.scenario_id}",
            f"Schema version: {draft.schema_version}",
            f"Traces: {len(draft.traces)}",
            f"Devices: {len(draft.devices)}",
            f"Sources: {len(draft.sources)}",
            f"Targets: {len(draft.targets)}",
            f"Routes: {len(draft.routes)}",
            f"Base dir: {draft.base_dir}",
        )
    )


def _validation_detail(validation: ScenarioValidationDetails) -> str:
    return "\n".join(
        (
            f"名称: {validation.name}",
            f"Frames: {validation.timeline_size}",
            f"Devices: {validation.device_count}",
            f"Channels: {validation.channel_count}",
            f"Total ns: {validation.total_ts_ns}",
        )
    )


def _delete_result_detail(result: ScenarioDeleteResultDetails) -> str:
    return "\n".join(
        (
            f"名称: {result.name}",
            f"Scenario ID: {result.scenario_id}",
            f"Traces: {result.trace_count}",
            f"Routes: {result.route_count}",
        )
    )


def _draft_issue_detail(issues: tuple[ScenarioDraftIssue, ...]) -> str:
    lines = ["Draft issues:"]
    for issue in issues:
        lines.append(f"{issue.severity}: {issue.location}: {issue.message}")
    return "\n".join(lines)


def _route_preview(route: DraftRouteRow) -> str:
    return f"{route.source_label} -> {route.logical_channel} -> {route.target_label}"


def _read_only_text(placeholder: str) -> QTextEdit:
    text = QTextEdit()
    text.setReadOnly(True)
    text.setPlainText(placeholder)
    return text


class NewScenarioDialog(QDialog):
    """Dialog for creating a minimal scenario draft from one imported trace."""

    def __init__(self, parent: QWidget | None, view_model: ScenariosViewModel) -> None:
        """Create the new scenario dialog.

        Args:
            parent: Parent Qt widget.
            view_model: Scenarios ViewModel used for trace/source choices.
        """
        super().__init__(parent)
        self._view_model = view_model
        self._source_choices: tuple[ScenarioSourceChoice, ...] = ()
        self._build_ui()
        self._sync_trace_choices()

    def selection(self) -> tuple[ScenarioTraceChoice | None, ScenarioSourceChoice | None, str]:
        """Return the selected trace, source, and scenario name.

        Returns:
            Tuple of selected trace choice, source choice, and name text.
        """
        trace = self._current_trace()
        source = self._current_source()
        return trace, source, self._name_edit.text().strip()

    def has_create_action(self) -> bool:
        """Return whether the dialog can create a draft.

        Returns:
            True when both trace and source are selected.
        """
        return self._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()

    def body_text(self) -> str:
        """Return visible dialog text used by tests.

        Returns:
            Combined status and current selector text.
        """
        return "\n".join(
            (
                self.windowTitle(),
                self._empty_label.text(),
                self._trace_combo.currentText(),
                self._source_combo.currentText(),
            )
        )

    def _build_ui(self) -> None:
        self.setWindowTitle("New Scenario")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._trace_combo = QComboBox()
        self._source_combo = QComboBox()
        self._trace_combo.currentIndexChanged.connect(self._handle_trace_changed)
        form.addRow("Scenario Name", self._name_edit)
        form.addRow("Trace", self._trace_combo)
        form.addRow("Source", self._source_combo)
        layout.addLayout(form)
        self._empty_label = QLabel("")
        layout.addWidget(self._empty_label)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def _sync_trace_choices(self) -> None:
        self._trace_combo.clear()
        for trace in self._view_model.trace_choices:
            self._trace_combo.addItem(f"{trace.name} ({trace.event_count} frames)", trace)
        if self._view_model.trace_choices:
            self._empty_label.setText("")
            self._handle_trace_changed(0)
        else:
            self._empty_label.setText("No imported traces. Import ASC in Trace Library first.")
            self._source_combo.clear()
            self._sync_ok_button()

    def _handle_trace_changed(self, _index: int) -> None:
        trace = self._current_trace()
        self._source_combo.clear()
        self._source_choices = ()
        if trace is None:
            self._sync_ok_button()
            return
        self._name_edit.setText(f"replay-{Path(trace.name).stem or 'trace'}")
        try:
            self._source_choices = self._view_model.source_choices_for_trace(trace.trace_id)
        except Exception as exc:
            self._empty_label.setText(str(exc))
            self._sync_ok_button()
            return
        for source in self._source_choices:
            self._source_combo.addItem(source.label, source)
        if not self._source_choices:
            self._empty_label.setText("Selected trace has no source summaries.")
        else:
            self._empty_label.setText("")
        self._sync_ok_button()

    def _sync_ok_button(self) -> None:
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            self._current_trace() is not None and self._current_source() is not None
        )

    def _current_trace(self) -> ScenarioTraceChoice | None:
        value = self._trace_combo.currentData()
        return value if isinstance(value, ScenarioTraceChoice) else None

    def _current_source(self) -> ScenarioSourceChoice | None:
        value = self._source_combo.currentData()
        return value if isinstance(value, ScenarioSourceChoice) else None


class AddRouteDialog(QDialog):
    """Dialog for appending a route from an imported trace source."""

    def __init__(self, parent: QWidget | None, view_model: ScenariosViewModel) -> None:
        """Create the add route dialog.

        Args:
            parent: Parent Qt widget.
            view_model: Scenarios ViewModel used for trace/source choices and
                current draft defaults.
        """
        super().__init__(parent)
        self._view_model = view_model
        self._source_choices: tuple[ScenarioSourceChoice, ...] = ()
        self._build_ui()
        self._sync_trace_choices()

    def selection(self) -> tuple[ScenarioTraceChoice | None, ScenarioSourceChoice | None, int, int]:
        """Return the selected route ingredients.

        Returns:
            Tuple of selected trace, selected trace source, logical channel,
            and mock target physical channel.
        """
        return (
            self._current_trace(),
            self._current_source(),
            self._logical_spin.value(),
            self._physical_spin.value(),
        )

    def has_add_action(self) -> bool:
        """Return whether the dialog can append a route.

        Returns:
            True when both trace and source are selected.
        """
        return self._buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()

    def body_text(self) -> str:
        """Return visible dialog text used by tests.

        Returns:
            Combined status and selector text.
        """
        return "\n".join(
            (
                self.windowTitle(),
                self._empty_label.text(),
                self._trace_combo.currentText(),
                self._source_combo.currentText(),
                f"Logical Channel: {self._logical_spin.value()}",
                f"Physical Channel: {self._physical_spin.value()}",
            )
        )

    def _build_ui(self) -> None:
        self.setWindowTitle("Add Route")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._trace_combo = QComboBox()
        self._source_combo = QComboBox()
        self._logical_spin = QSpinBox()
        self._logical_spin.setRange(0, 255)
        self._physical_spin = QSpinBox()
        self._physical_spin.setRange(0, 255)
        self._trace_combo.currentIndexChanged.connect(self._handle_trace_changed)
        form.addRow("Trace", self._trace_combo)
        form.addRow("Source", self._source_combo)
        form.addRow("Logical Channel", self._logical_spin)
        form.addRow("Physical Channel", self._physical_spin)
        layout.addLayout(form)
        self._empty_label = QLabel("")
        layout.addWidget(self._empty_label)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def _sync_trace_choices(self) -> None:
        self._trace_combo.clear()
        for trace in self._view_model.trace_choices:
            self._trace_combo.addItem(f"{trace.name} ({trace.event_count} frames)", trace)
        if self._view_model.trace_choices:
            self._empty_label.setText("")
            self._handle_trace_changed(0)
        else:
            self._empty_label.setText("No imported traces. Import ASC in Trace Library first.")
            self._source_combo.clear()
            self._sync_default_channels()
            self._sync_ok_button()

    def _handle_trace_changed(self, _index: int) -> None:
        trace = self._current_trace()
        self._source_combo.clear()
        self._source_choices = ()
        if trace is None:
            self._sync_default_channels()
            self._sync_ok_button()
            return
        try:
            self._source_choices = self._view_model.source_choices_for_trace(trace.trace_id)
        except Exception as exc:
            self._empty_label.setText(str(exc))
            self._sync_ok_button()
            return
        for source in self._source_choices:
            self._source_combo.addItem(source.label, source)
        if not self._source_choices:
            self._empty_label.setText("Selected trace has no source summaries.")
        else:
            self._empty_label.setText("")
        self._sync_default_channels()
        self._sync_ok_button()

    def _sync_default_channels(self) -> None:
        logical = _next_route_logical_channel(self._view_model.draft)
        self._logical_spin.setValue(logical)
        self._physical_spin.setValue(logical)

    def _sync_ok_button(self) -> None:
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            self._current_trace() is not None and self._current_source() is not None
        )

    def _current_trace(self) -> ScenarioTraceChoice | None:
        value = self._trace_combo.currentData()
        return value if isinstance(value, ScenarioTraceChoice) else None

    def _current_source(self) -> ScenarioSourceChoice | None:
        value = self._source_combo.currentData()
        return value if isinstance(value, ScenarioSourceChoice) else None


def _next_route_logical_channel(draft: ScenarioDraft | None) -> int:
    if draft is None or not draft.routes:
        return 0
    used = {route.logical_channel for route in draft.routes}
    for value in range(256):
        if value not in used:
            return value
    return 255

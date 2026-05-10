from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.view_models.scenarios import (
    DraftDeviceRow,
    DraftRouteRow,
    DraftTargetRow,
    ScenarioDeleteResultDetails,
    ScenarioDraft,
    ScenarioDraftIssue,
    ScenarioRow,
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
    runRequested = Signal(object, str)

    def __init__(self, view_model: ScenariosViewModel) -> None:
        """Create the Scenarios view.

        Args:
            view_model: ViewModel that supplies scenario rows.
        """
        super().__init__()
        self._view_model = view_model
        self._replay_active = False
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
                TableColumn("SDK root", lambda row: row.sdk_root, tooltip=lambda row: row.sdk_root),
                TableColumn("Application", lambda row: row.application),
                TableColumn("Device Type", lambda row: row.device_type),
                TableColumn("Index", lambda row: row.device_index, align_right=True),
            )
        )
        self._target_model = ObjectTableModel(
            (
                TableColumn("Target ID", lambda row: row.target_id, monospace=True),
                TableColumn("Device", lambda row: row.device_id, monospace=True),
                TableColumn("Bus", lambda row: row.bus),
                TableColumn("CH", lambda row: row.physical_channel, align_right=True),
                TableColumn("Nominal", lambda row: row.nominal_baud, align_right=True),
                TableColumn("Data", lambda row: row.data_baud, align_right=True),
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
            True when a loaded draft can start a replay session.
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

    def add_device_enabled(self) -> bool:
        """Return whether Add Device is enabled.

        Returns:
            True when the loaded draft can accept another device.
        """
        return self._add_device_button.isEnabled()

    def remove_device_enabled(self) -> bool:
        """Return whether Remove Device is enabled.

        Returns:
            True when a device is selected and can be removed.
        """
        return self._remove_device_button.isEnabled()

    def add_target_enabled(self) -> bool:
        """Return whether Add Target is enabled.

        Returns:
            True when the loaded draft can accept another target.
        """
        return self._add_target_button.isEnabled()

    def remove_target_enabled(self) -> bool:
        """Return whether Remove Target is enabled.

        Returns:
            True when a target is selected and can be removed.
        """
        return self._remove_target_button.isEnabled()

    def error_details_enabled(self) -> bool:
        """Return whether the error details button is enabled.

        Returns:
            True when an error can be opened.
        """
        return self._error_button.isEnabled()

    def device_issue_text(self) -> str:
        """Return nearby device issue text.

        Returns:
            Text shown under the selected device editor.
        """
        return self._device_issue_label.text()

    def target_issue_text(self) -> str:
        """Return nearby target issue text.

        Returns:
            Text shown under the selected target editor.
        """
        return self._target_issue_label.text()

    def route_issue_text(self) -> str:
        """Return nearby route issue text.

        Returns:
            Text shown under the selected route editor.
        """
        return self._route_issue_label.text()

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

    def routes_preview_text(self) -> str:
        """Return the route mapping preview text.

        Returns:
            Text representation of current draft route mappings.
        """
        draft = self._view_model.draft
        if draft is None:
            return ""
        return "\n".join(_route_preview(route) for route in draft.routes)

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
        if self._replay_active:
            return
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

    def select_device(self, row: int) -> None:
        """Select one device row in the editor.

        Args:
            row: Zero-based device row index.
        """
        if 0 <= row < self._device_model.rowCount():
            self._devices_table.selectRow(row)
            self._sync_device_controls_for_current_device()

    def select_target(self, row: int) -> None:
        """Select one target row in the editor.

        Args:
            row: Zero-based target row index.
        """
        if 0 <= row < self._target_model.rowCount():
            self._targets_table.selectRow(row)
            self._sync_target_controls_for_current_target()

    def edit_device_driver(self, value: str) -> None:
        """Set the selected device driver through the edit control.

        Args:
            value: New device driver.
        """
        index = self._combo_index_for_text(self._device_driver_combo, value)
        if index < 0:
            self._device_driver_combo.addItem(str(value))
            index = self._combo_index_for_text(self._device_driver_combo, value)
        self._device_driver_combo.setCurrentIndex(index)
        self._apply_device_driver_edit()

    def edit_device_sdk_root(self, value: str) -> None:
        """Set the selected device SDK root through the edit control.

        Args:
            value: New SDK root text.
        """
        self._device_sdk_root_edit.setText(str(value))
        self._apply_device_sdk_root_edit()

    def edit_device_application(self, value: str) -> None:
        """Set the selected device application through the edit control.

        Args:
            value: New application text.
        """
        self._device_application_edit.setText(str(value))
        self._apply_device_application_edit()

    def edit_device_type(self, value: str) -> None:
        """Set the selected device type through the edit control.

        Args:
            value: New device type.
        """
        self._device_type_edit.setText(str(value))
        self._apply_device_type_edit()

    def edit_device_index(self, value: int) -> None:
        """Set the selected device index through the edit control.

        Args:
            value: New device index.
        """
        self._device_index_spin.setValue(int(value))
        self._apply_device_index_edit()

    def edit_target_device(self, device_id: str) -> None:
        """Set the selected target device through the edit control.

        Args:
            device_id: Device ID to assign.
        """
        index = self._combo_index_for_data(self._target_device_combo, device_id)
        if index >= 0:
            self._target_device_combo.setCurrentIndex(index)
        self._apply_target_device_edit()

    def edit_target_bus(self, bus: str) -> None:
        """Set the selected target bus through the edit control.

        Args:
            bus: New bus type.
        """
        index = self._combo_index_for_text(self._target_bus_combo, bus)
        if index >= 0:
            self._target_bus_combo.setCurrentIndex(index)
        self._apply_target_bus_edit()

    def edit_target_nominal_baud(self, value: int) -> None:
        """Set the selected target nominal baud through the edit control.

        Args:
            value: New nominal baud rate.
        """
        self._target_nominal_baud_spin.setValue(int(value))
        self._apply_target_nominal_baud_edit()

    def edit_target_data_baud(self, value: int) -> None:
        """Set the selected target data baud through the edit control.

        Args:
            value: New data baud rate.
        """
        self._target_data_baud_spin.setValue(int(value))
        self._apply_target_data_baud_edit()

    def edit_target_resistance_enabled(self, enabled: bool) -> None:
        """Set the selected target resistance flag through the edit control.

        Args:
            enabled: Whether resistance should be enabled.
        """
        self._target_resistance_check.setChecked(bool(enabled))
        self._apply_target_resistance_edit()

    def edit_target_listen_only(self, enabled: bool) -> None:
        """Set the selected target listen-only flag through the edit control.

        Args:
            enabled: Whether listen-only should be enabled.
        """
        self._target_listen_only_check.setChecked(bool(enabled))
        self._apply_target_listen_only_edit()

    def edit_target_tx_echo(self, enabled: bool) -> None:
        """Set the selected target TX echo flag through the edit control.

        Args:
            enabled: Whether TX echo should be enabled.
        """
        self._target_tx_echo_check.setChecked(bool(enabled))
        self._apply_target_tx_echo_edit()

    def select_route(self, row: int) -> None:
        """Select one route row in the editor.

        Args:
            row: Zero-based route row index.
        """
        if 0 <= row < self._route_model.rowCount():
            self._routes_table.selectRow(row)
            self._sync_edit_controls_for_current_route()

    def set_replay_active(self, active: bool) -> None:
        """Set whether an active replay session should lock editor commands.

        Args:
            active: True while replay is starting, running, paused, or stopping.
        """
        value = bool(active)
        if self._replay_active == value:
            return
        self._replay_active = value
        self._sync_command_buttons()

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

    def trigger_run(self) -> None:
        """Trigger Run for tests and keyboard workflows."""
        self._run_loaded_scenario()

    def trigger_add_device(self) -> None:
        """Trigger Add Device for tests and keyboard workflows."""
        self._add_device()

    def trigger_remove_device(self) -> None:
        """Trigger Remove Device for tests and keyboard workflows."""
        self._remove_selected_device()

    def trigger_add_target(self) -> None:
        """Trigger Add Target for tests and keyboard workflows."""
        self._add_target()

    def trigger_remove_target(self) -> None:
        """Trigger Remove Target for tests and keyboard workflows."""
        self._remove_selected_target()

    def current_page_index(self) -> int:
        """Return the current page stack index (0=list, 1=editor)."""
        return self._page_stack.currentIndex()

    def trigger_new_scenario(self) -> None:
        """Trigger New Scenario for tests."""
        self._start_new_scenario()

    def switch_to_editor(self) -> None:
        """Switch to the editor page for tests."""
        self._switch_to_editor()

    def trigger_back_to_list(self) -> None:
        """Trigger Back to list button for tests."""
        self._back_to_list()

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
        self._run_button.setToolTip("运行当前 Scenario draft，并在 Replay Monitor 中查看 snapshot")
        self._run_button.clicked.connect(self._run_loaded_scenario)
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

        self._list_stack = QStackedWidget()
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
        self._list_stack.addWidget(self._table)
        self._list_stack.addWidget(self._empty)

        self._page_stack = QStackedWidget()

        # Page 0: list view (table or empty state)
        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(self._list_stack)
        self._page_stack.addWidget(list_page)

        # Page 1: editor view (existing preview for now)
        editor_page = self._build_editor_view()
        self._page_stack.addWidget(editor_page)

        self._page_stack.setCurrentIndex(0)
        layout.addWidget(self._page_stack, 1)

    def _switch_to_editor(self) -> None:
        """Switch the page stack to the editor view."""
        self._page_stack.setCurrentIndex(1)

    def _switch_to_list(self) -> None:
        """Switch the page stack back to the list and discard the draft."""
        self._page_stack.setCurrentIndex(0)

    def _back_to_list(self) -> None:
        """Return to the scenario list, discarding any unsaved draft."""
        self._switch_to_list()

    def _add_route_from_editor(self) -> None:
        """Add a route from available trace choices, inline."""
        if self._replay_active or self._view_model.draft is None:
            return
        if not self._view_model.trace_choices:
            self._view_model.load_trace_choices()
            return
        trace = self._view_model.trace_choices[0]
        sources = self._view_model.source_choices_for_trace(trace.trace_id)
        if not sources:
            return
        source = sources[0]
        draft = self._view_model.draft
        target_id = draft.targets[0].target_id if draft.targets else ""
        self._view_model.add_route_from_trace(trace, source, target_id=target_id)

    def _sync_rows(self) -> None:
        self._model.set_rows(self._view_model.rows)
        self._list_stack.setCurrentWidget(self._empty if not self._view_model.rows else self._table)
        self._sync_status_badge()
        self._sync_command_buttons()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _show_error(self, message: str) -> None:
        self._error_button.setEnabled(bool(message))
        self._sync_status_badge()
        if message:
            self.inspectorChanged.emit("Scenarios 错误", message)

    def _sync_busy(self, busy: bool) -> None:
        idle = not busy and not self._replay_active
        self._new_button.setEnabled(idle)
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

    def _build_editor_view(self) -> QWidget:
        """Build the flat scenario editor page with all sections stacked."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        editor = QWidget()
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(12, 12, 12, 12)
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
        overview_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #667085;")
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
        section_label = QLabel("Traces & Devices")
        section_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #667085;")
        layout.addWidget(section_label)

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
        self._add_device_button.clicked.connect(self._add_device)
        device_toolbar.addWidget(self._add_device_button)
        self._remove_device_button = QPushButton("Remove Device")
        self._remove_device_button.setEnabled(False)
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
        self._add_target_button.clicked.connect(self._add_target)
        target_toolbar.addWidget(self._add_target_button)
        self._remove_target_button = QPushButton("Remove Target")
        self._remove_target_button.setEnabled(False)
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
        self._target_editor_physical_spin.editingFinished.connect(self._apply_target_editor_physical_edit)
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
        routes_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #667085;")
        layout.addWidget(routes_label)

        route_toolbar = QHBoxLayout()
        self._add_route_button = QPushButton("Add Route")
        self._add_route_button.setEnabled(False)
        self._add_route_button.clicked.connect(self._add_route_from_editor)
        route_toolbar.addWidget(self._add_route_button)
        self._remove_route_button = QPushButton("Remove Route")
        self._remove_route_button.setEnabled(False)
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

    def _handle_selection_changed(self) -> None:
        self._sync_command_buttons()
        self._emit_selection()

    def _load_selected_scenario(self) -> None:
        if self._replay_active:
            return
        row = self._selected_row()
        if row is None:
            return
        self._view_model.load_scenario(row.scenario_id)
        self._switch_to_editor()

    def _start_new_scenario(self) -> None:
        if self._replay_active:
            return
        if not self._view_model.trace_choices:
            self._open_new_dialog_after_trace_load = True
            self._view_model.load_trace_choices()
            return
        self._create_draft_and_switch_to_editor()

    def _create_draft_and_switch_to_editor(self) -> None:
        if not self._view_model.trace_choices:
            return
        trace = self._view_model.trace_choices[0]
        sources = self._view_model.source_choices_for_trace(trace.trace_id)
        if not sources:
            return
        source = sources[0]
        self._view_model.create_new_scenario_from_trace(trace, source)
        self._switch_to_editor()

    def _add_device(self) -> None:
        if self._replay_active:
            return
        self._view_model.add_device()

    def _remove_selected_device(self) -> None:
        if self._replay_active:
            return
        index = self._selected_device_index()
        if index >= 0:
            self._view_model.remove_device(index)

    def _add_target(self) -> None:
        if self._replay_active:
            return
        device = self._selected_device()
        self._view_model.add_target(device_id="" if device is None else device.device_id)

    def _remove_selected_target(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.remove_target(index)

    def _remove_selected_route(self) -> None:
        if self._replay_active:
            return
        index = self._selected_route_index()
        if index >= 0:
            self._view_model.remove_route(index)

    def _save_loaded_scenario(self) -> None:
        if self._replay_active:
            return
        self._view_model.save_loaded_scenario()

    def _validate_loaded_scenario(self) -> None:
        if self._replay_active:
            return
        self._view_model.validate_loaded_scenario()

    def _run_loaded_scenario(self) -> None:
        if self._replay_active:
            return
        draft = self._view_model.draft
        if draft is None or self._view_model.has_blocking_issues:
            return
        self.runRequested.emit(dict(draft.body), draft.base_dir)

    def _delete_selected_scenario(self) -> None:
        if self._replay_active:
            return
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
        device_index = self._selected_device_index()
        target_index = self._selected_target_index()
        has_route = has_draft and route_index >= 0
        has_device = has_draft and device_index >= 0
        has_target = has_draft and target_index >= 0
        idle = not self._view_model.busy and not self._replay_active
        self._new_button.setEnabled(idle)
        self._load_button.setEnabled(row is not None and idle)
        self._save_button.setEnabled(has_draft and idle)
        self._validate_button.setEnabled(has_draft and idle)
        self._delete_button.setEnabled(row is not None and idle)
        self._add_device_button.setEnabled(has_draft and idle)
        self._remove_device_button.setEnabled(has_device and idle)
        self._add_target_button.setEnabled(has_draft and idle)
        self._remove_target_button.setEnabled(has_target and idle)
        self._device_driver_combo.setEnabled(has_device and idle)
        self._device_sdk_root_edit.setEnabled(has_device and idle)
        self._device_application_edit.setEnabled(has_device and idle)
        self._device_type_edit.setEnabled(has_device and idle)
        self._device_index_spin.setEnabled(has_device and idle)
        self._target_device_combo.setEnabled(has_target and idle)
        self._target_bus_combo.setEnabled(has_target and idle)
        self._target_editor_physical_spin.setEnabled(has_target and idle)
        self._target_nominal_baud_spin.setEnabled(has_target and idle)
        self._target_data_baud_spin.setEnabled(has_target and idle)
        self._target_resistance_check.setEnabled(has_target and idle)
        self._target_listen_only_check.setEnabled(has_target and idle)
        self._target_tx_echo_check.setEnabled(has_target and idle)
        self._add_route_button.setEnabled(has_draft and idle)
        self._remove_route_button.setEnabled(has_route and idle)
        self._name_edit.setEnabled(has_draft and idle)
        self._loop_check.setEnabled(has_draft and idle)
        self._route_source_combo.setEnabled(has_route and idle)
        self._route_logical_spin.setEnabled(has_route and idle)
        self._route_target_combo.setEnabled(has_route and idle)
        self._target_physical_spin.setEnabled(has_route and idle)
        self._run_button.setEnabled(has_draft and not self._view_model.has_blocking_issues and idle)
        self._editor_validate_button.setEnabled(has_draft and idle)
        self._editor_run_button.setEnabled(has_draft and not self._view_model.has_blocking_issues and idle)

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

    def _sync_validation(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_delete_result(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_draft_issues(self) -> None:
        self._device_issue_label.setText(self._issue_text("devices", self._selected_device_index()))
        self._target_issue_label.setText(self._issue_text("targets", self._selected_target_index()))
        self._route_issue_label.setText(self._issue_text("routes", self._selected_route_index()))
        self._sync_command_buttons()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_trace_choices(self) -> None:
        if getattr(self, '_open_new_dialog_after_trace_load', False):
            self._open_new_dialog_after_trace_load = False
            self._create_draft_and_switch_to_editor()

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

    def _clear_device_controls(self) -> None:
        self._device_driver_combo.blockSignals(True)
        self._device_driver_combo.setCurrentText("")
        self._device_driver_combo.setEnabled(False)
        self._device_driver_combo.blockSignals(False)
        self._device_sdk_root_edit.setText("")
        self._device_sdk_root_edit.setEnabled(False)
        self._device_application_edit.setText("")
        self._device_application_edit.setEnabled(False)
        self._device_type_edit.setText("")
        self._device_type_edit.setEnabled(False)
        self._device_index_spin.setValue(0)
        self._device_index_spin.setEnabled(False)
        self._device_issue_label.setText("")

    def _clear_target_controls(self) -> None:
        self._target_device_combo.blockSignals(True)
        self._target_device_combo.clear()
        self._target_device_combo.setEnabled(False)
        self._target_device_combo.blockSignals(False)
        self._target_bus_combo.blockSignals(True)
        self._target_bus_combo.setCurrentIndex(0)
        self._target_bus_combo.setEnabled(False)
        self._target_bus_combo.blockSignals(False)
        self._target_editor_physical_spin.setValue(0)
        self._target_editor_physical_spin.setEnabled(False)
        self._target_nominal_baud_spin.setValue(500000)
        self._target_nominal_baud_spin.setEnabled(False)
        self._target_data_baud_spin.setValue(2000000)
        self._target_data_baud_spin.setEnabled(False)
        self._target_resistance_check.setChecked(False)
        self._target_resistance_check.setEnabled(False)
        self._target_listen_only_check.setChecked(False)
        self._target_listen_only_check.setEnabled(False)
        self._target_tx_echo_check.setChecked(False)
        self._target_tx_echo_check.setEnabled(False)
        self._target_issue_label.setText("")

    def _sync_device_controls_for_current_device(self) -> None:
        device = self._selected_device()
        if device is None:
            self._clear_device_controls()
            self._sync_command_buttons()
            return
        self._device_driver_combo.blockSignals(True)
        index = self._combo_index_for_text(self._device_driver_combo, device.driver)
        if index < 0:
            self._device_driver_combo.addItem(device.driver)
            index = self._combo_index_for_text(self._device_driver_combo, device.driver)
        self._device_driver_combo.setCurrentIndex(index)
        self._device_driver_combo.blockSignals(False)
        self._device_sdk_root_edit.blockSignals(True)
        self._device_sdk_root_edit.setText(device.sdk_root)
        self._device_sdk_root_edit.blockSignals(False)
        self._device_application_edit.blockSignals(True)
        self._device_application_edit.setText(device.application)
        self._device_application_edit.blockSignals(False)
        self._device_type_edit.blockSignals(True)
        self._device_type_edit.setText(device.device_type)
        self._device_type_edit.blockSignals(False)
        self._device_index_spin.blockSignals(True)
        self._device_index_spin.setValue(device.device_index)
        self._device_index_spin.blockSignals(False)
        self._device_issue_label.setText(self._issue_text("devices", self._selected_device_index()))
        self._sync_command_buttons()

    def _sync_target_controls_for_current_target(self) -> None:
        target = self._selected_target()
        draft = self._view_model.draft
        if target is None or draft is None:
            self._clear_target_controls()
            self._sync_command_buttons()
            return
        self._target_device_combo.blockSignals(True)
        self._target_device_combo.clear()
        for device in draft.devices:
            self._target_device_combo.addItem(device.device_id, device.device_id)
        device_index = self._combo_index_for_data(self._target_device_combo, target.device_id)
        if device_index >= 0:
            self._target_device_combo.setCurrentIndex(device_index)
        self._target_device_combo.blockSignals(False)
        self._target_bus_combo.blockSignals(True)
        bus_index = self._combo_index_for_text(self._target_bus_combo, target.bus)
        if bus_index >= 0:
            self._target_bus_combo.setCurrentIndex(bus_index)
        self._target_bus_combo.blockSignals(False)
        self._target_editor_physical_spin.blockSignals(True)
        self._target_editor_physical_spin.setValue(target.physical_channel)
        self._target_editor_physical_spin.blockSignals(False)
        self._target_nominal_baud_spin.blockSignals(True)
        self._target_nominal_baud_spin.setValue(target.nominal_baud)
        self._target_nominal_baud_spin.blockSignals(False)
        self._target_data_baud_spin.blockSignals(True)
        self._target_data_baud_spin.setValue(target.data_baud)
        self._target_data_baud_spin.blockSignals(False)
        self._target_resistance_check.blockSignals(True)
        self._target_resistance_check.setChecked(target.resistance_enabled)
        self._target_resistance_check.blockSignals(False)
        self._target_listen_only_check.blockSignals(True)
        self._target_listen_only_check.setChecked(target.listen_only)
        self._target_listen_only_check.blockSignals(False)
        self._target_tx_echo_check.blockSignals(True)
        self._target_tx_echo_check.setChecked(target.tx_echo)
        self._target_tx_echo_check.blockSignals(False)
        self._target_issue_label.setText(self._issue_text("targets", self._selected_target_index()))
        self._sync_command_buttons()

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
        self._route_issue_label.setText(self._issue_text("routes", route_index))
        self._sync_command_buttons()

    def _apply_name_edit(self) -> None:
        if self._replay_active:
            return
        draft = self._view_model.draft
        value = self._name_edit.text()
        if draft is not None and value != draft.name:
            self._view_model.rename_loaded_scenario(value)

    def _apply_loop_edit(self) -> None:
        if self._replay_active:
            return
        draft = self._view_model.draft
        if draft is not None:
            self._view_model.set_timeline_loop(self._loop_check.isChecked())

    def _apply_device_driver_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_device_index()
        if index >= 0:
            self._view_model.set_device_driver(index, self._device_driver_combo.currentText())

    def _apply_device_sdk_root_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_device_index()
        if index >= 0:
            self._view_model.set_device_sdk_root(index, self._device_sdk_root_edit.text())

    def _apply_device_application_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_device_index()
        if index >= 0:
            self._view_model.set_device_application(index, self._device_application_edit.text())

    def _apply_device_type_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_device_index()
        if index >= 0:
            self._view_model.set_device_type(index, self._device_type_edit.text())

    def _apply_device_index_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_device_index()
        if index >= 0:
            self._view_model.set_device_index(index, self._device_index_spin.value())

    def _apply_target_device_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        device_id = self._target_device_combo.currentData()
        if index >= 0 and device_id is not None:
            self._view_model.set_target_device(index, str(device_id))

    def _apply_target_bus_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.set_target_bus(index, self._target_bus_combo.currentText())

    def _apply_target_editor_physical_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.set_target_physical_channel(index, self._target_editor_physical_spin.value())

    def _apply_target_nominal_baud_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.set_target_nominal_baud(index, self._target_nominal_baud_spin.value())

    def _apply_target_data_baud_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.set_target_data_baud(index, self._target_data_baud_spin.value())

    def _apply_target_resistance_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.set_target_resistance_enabled(index, self._target_resistance_check.isChecked())

    def _apply_target_listen_only_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.set_target_listen_only(index, self._target_listen_only_check.isChecked())

    def _apply_target_tx_echo_edit(self) -> None:
        if self._replay_active:
            return
        index = self._selected_target_index()
        if index >= 0:
            self._view_model.set_target_tx_echo(index, self._target_tx_echo_check.isChecked())

    def _apply_route_logical_edit(self) -> None:
        if self._replay_active:
            return
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        if draft is not None and route_index >= 0:
            self._view_model.set_route_logical_channel(route_index, self._route_logical_spin.value())

    def _apply_route_source_edit(self) -> None:
        if self._replay_active:
            return
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        source_id = self._route_source_combo.currentData()
        if draft is not None and route_index >= 0 and source_id is not None:
            self._view_model.set_route_source(route_index, str(source_id))

    def _apply_route_target_edit(self) -> None:
        if self._replay_active:
            return
        draft = self._view_model.draft
        route_index = self._selected_route_index()
        target_id = self._route_target_combo.currentData()
        if draft is not None and route_index >= 0 and target_id is not None:
            self._view_model.set_route_target(route_index, str(target_id))

    def _apply_target_physical_edit(self) -> None:
        if self._replay_active:
            return
        draft = self._view_model.draft
        target_index = self._selected_route_target_index()
        if draft is not None and target_index >= 0:
            self._view_model.set_target_physical_channel(target_index, self._target_physical_spin.value())

    def _handle_route_selection_changed(self) -> None:
        self._sync_edit_controls_for_current_route()
        self._emit_selection()

    def _handle_device_selection_changed(self) -> None:
        self._sync_device_controls_for_current_device()
        self._emit_selection()

    def _handle_target_selection_changed(self) -> None:
        self._sync_target_controls_for_current_target()
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

    def _selected_device_index(self) -> int:
        draft = self._view_model.draft
        current = self._devices_table.currentIndex()
        if draft is None or not current.isValid():
            return -1
        row = current.row()
        return row if 0 <= row < len(draft.devices) else -1

    def _selected_target_index(self) -> int:
        draft = self._view_model.draft
        current = self._targets_table.currentIndex()
        if draft is None or not current.isValid():
            return -1
        row = current.row()
        return row if 0 <= row < len(draft.targets) else -1

    def _selected_device(self) -> DraftDeviceRow | None:
        draft = self._view_model.draft
        index = self._selected_device_index()
        if draft is None or index < 0:
            return None
        return draft.devices[index]

    def _selected_target(self) -> DraftTargetRow | None:
        draft = self._view_model.draft
        index = self._selected_target_index()
        if draft is None or index < 0:
            return None
        return draft.targets[index]

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

    def _combo_index_for_text(self, combo: QComboBox, value: object) -> int:
        for index in range(combo.count()):
            if combo.itemText(index) == str(value):
                return index
        return -1

    def _issue_text(self, section: str, row: int) -> str:
        if row < 0:
            return ""
        messages = [
            f"{issue.field}: {issue.message}"
            for issue in self._view_model.draft_issues
            if issue.section == section and issue.row == row
        ]
        return "\n".join(messages)


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





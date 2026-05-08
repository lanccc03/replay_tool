from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
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
    ScenarioDraft,
    ScenarioRow,
    ScenariosViewModel,
)
from replay_ui_qt.widgets.dialogs import create_error_details_dialog
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
        self._view_model.rowsChanged.connect(self._sync_rows)
        self._view_model.statusMessageChanged.connect(lambda message: self.inspectorChanged.emit("Scenarios", message))
        self._view_model.errorChanged.connect(self._show_error)
        self._view_model.busyChanged.connect(self._sync_busy)
        self._view_model.draftChanged.connect(self._sync_draft)
        self._view_model.refresh()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        draft = self._view_model.draft
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

    def load_enabled(self) -> bool:
        """Return whether the load button is enabled.

        Returns:
            True when the selected scenario can be loaded.
        """
        return self._load_button.isEnabled()

    def save_enabled(self) -> bool:
        """Return whether Save Scenario is enabled.

        Returns:
            Always False in the read-only M3 first batch.
        """
        return self._save_button.isEnabled()

    def validate_enabled(self) -> bool:
        """Return whether Validate is enabled.

        Returns:
            Always False in the read-only M3 first batch.
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
            Always False in the read-only M3 first batch.
        """
        return self._delete_button.isEnabled()

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

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
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
        self._save_button.setToolTip("后续接入")
        toolbar.addWidget(self._save_button)
        self._validate_button = QPushButton("Validate")
        self._validate_button.setEnabled(False)
        self._validate_button.setToolTip("后续接入")
        toolbar.addWidget(self._validate_button)
        self._run_button = QPushButton("Run")
        self._run_button.setEnabled(False)
        self._run_button.setToolTip("后续接入")
        toolbar.addWidget(self._run_button)
        self._delete_button = QPushButton("Delete")
        self._delete_button.setEnabled(False)
        self._delete_button.setToolTip("后续接入")
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
        self._overview = _read_only_text("加载 Scenario 后显示 schema、数量和 base dir。")
        self._tabs.addTab(self._overview, "Overview")
        self._tabs.addTab(self._build_traces_devices_tab(), "Traces & Devices")
        self._tabs.addTab(self._build_routes_tab(), "Routes")
        self._json_preview = _read_only_text("加载 Scenario 后显示格式化 JSON。")
        self._tabs.addTab(self._json_preview, "JSON")
        layout.addWidget(self._tabs)
        return preview

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
        routes = QTableView()
        routes.setModel(self._route_model)
        routes.verticalHeader().setVisible(False)
        routes.setColumnWidth(0, 260)
        routes.setColumnWidth(1, 140)
        routes.setColumnWidth(2, 260)
        layout.addWidget(routes)
        return tab

    def _handle_selection_changed(self) -> None:
        self._sync_command_buttons()
        self._emit_selection()

    def _load_selected_scenario(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        self._view_model.load_scenario(row.scenario_id)

    def _sync_command_buttons(self) -> None:
        row = self._selected_row()
        self._load_button.setEnabled(row is not None and not self._view_model.busy)

    def _sync_draft(self) -> None:
        draft = self._view_model.draft
        if draft is None:
            self._overview.setPlainText("加载 Scenario 后显示 schema、数量和 base dir。")
            self._trace_model.set_rows(())
            self._device_model.set_rows(())
            self._route_model.set_rows(())
            self._json_preview.setPlainText("加载 Scenario 后显示格式化 JSON。")
        else:
            self._overview.setPlainText(_draft_detail(draft))
            self._trace_model.set_rows(draft.traces)
            self._device_model.set_rows(draft.devices)
            self._route_model.set_rows(draft.routes)
            self._json_preview.setPlainText(draft.json_text)
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _emit_selection(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _selected_row(self) -> ScenarioRow | None:
        current = self._table.currentIndex()
        if not current.isValid():
            return None
        row = self._model.row_at(current.row())
        return row if isinstance(row, ScenarioRow) else None


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


def _route_preview(route: DraftRouteRow) -> str:
    return f"{route.source_label} -> {route.logical_channel} -> {route.target_label}"


def _read_only_text(placeholder: str) -> QTextEdit:
    text = QTextEdit()
    text.setReadOnly(True)
    text.setPlainText(placeholder)
    return text

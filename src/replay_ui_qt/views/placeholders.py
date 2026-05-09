from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.view_models.devices import DevicesViewModel
from replay_ui_qt.view_models.replay_session import ReplaySessionViewModel
from replay_ui_qt.widgets.dialogs import create_danger_confirmation, create_error_details_dialog
from replay_ui_qt.widgets.empty_state import EmptyState
from replay_ui_qt.widgets.status_badge import StatusBadge
from replay_ui_qt.widgets.table_model import ObjectTableModel, TableColumn


class ReplayMonitorView(QWidget):
    """Replay monitor view for one app-layer non-blocking session."""

    inspectorChanged = Signal(str, str)

    def __init__(self, view_model: ReplaySessionViewModel) -> None:
        """Create the replay monitor page.

        Args:
            view_model: Replay session ViewModel with current session state.
        """
        super().__init__()
        self._view_model = view_model
        self._metric_values: dict[str, QLabel] = {}
        self._build_ui()
        self._view_model.sessionChanged.connect(self._sync_session)
        self._view_model.snapshotChanged.connect(self._sync_snapshot)
        self._view_model.controlsChanged.connect(self._sync_controls)
        self._view_model.busyChanged.connect(lambda _busy: self._sync_controls())
        self._view_model.errorChanged.connect(self._sync_error)
        self._view_model.statusMessageChanged.connect(
            lambda message: self.inspectorChanged.emit("Replay Monitor", message)
        )
        self._sync_session()
        self._sync_snapshot()
        self._sync_controls()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        error_text = self._error_detail_text()
        if error_text:
            return ("Replay Errors", error_text)
        summary = self._view_model.summary
        if summary is None:
            return ("Replay Monitor", "从 Scenarios 页面点击 Run 后，这里显示当前 replay session。")
        return (
            "Replay Session",
            "\n".join(
                (
                    f"Scenario: {summary.name}",
                    f"State: {self._view_model.display_state}",
                    f"Frames: {self._view_model.timeline_index}/{self._view_model.timeline_size}",
                    f"Devices: {summary.device_count}",
                    f"Channels: {summary.channel_count}",
                    f"Loop: {summary.loop}",
                    f"Total ns: {summary.total_ts_ns}",
                )
            ),
        )

    def state_text(self) -> str:
        """Return the visible state label.

        Returns:
            Current runtime state text.
        """
        return self._state_value.text()

    def pause_enabled(self) -> bool:
        """Return whether the Pause button is enabled.

        Returns:
            True when Pause can be clicked.
        """
        return self._pause_button.isEnabled()

    def resume_enabled(self) -> bool:
        """Return whether the Resume button is enabled.

        Returns:
            True when Resume can be clicked.
        """
        return self._resume_button.isEnabled()

    def stop_enabled(self) -> bool:
        """Return whether the Stop button is enabled.

        Returns:
            True when Stop can be clicked.
        """
        return self._stop_button.isEnabled()

    def error_details_enabled(self) -> bool:
        """Return whether error details can be opened.

        Returns:
            True when startup or runtime errors are present.
        """
        return self._error_button.isEnabled()

    def progress_value(self) -> int:
        """Return progress bar value.

        Returns:
            Current progress percentage rounded to an integer.
        """
        return self._progress.value()

    def metric_text(self, label: str) -> str:
        """Return one metric value for tests and accessibility checks.

        Args:
            label: Metric label.

        Returns:
            Visible metric text, or an empty string for unknown labels.
        """
        value = self._metric_values.get(str(label))
        return "" if value is None else value.text()

    def create_error_dialog(self):
        """Create the current replay error details dialog.

        Returns:
            Error details dialog for startup or runtime errors.
        """
        return create_error_details_dialog(
            self,
            title="Replay Monitor 错误",
            summary="Replay session 操作失败",
            detail=self._error_detail_text(),
        )

    def create_stop_confirmation_dialog(self):
        """Create the stop confirmation dialog for the current session.

        Returns:
            Standard dangerous-action confirmation message box.
        """
        summary = self._view_model.summary
        label = "Replay Session" if summary is None else summary.name
        return create_danger_confirmation(
            self,
            action="Stop Replay",
            object_label=label,
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self._pause_button = QPushButton("Pause")
        self._pause_button.setToolTip("暂停当前 replay session")
        self._pause_button.clicked.connect(self._view_model.pause)
        toolbar.addWidget(self._pause_button)
        self._resume_button = QPushButton("Resume")
        self._resume_button.setToolTip("恢复已暂停的 replay session")
        self._resume_button.clicked.connect(self._view_model.resume)
        toolbar.addWidget(self._resume_button)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setToolTip("停止当前 replay session")
        self._stop_button.clicked.connect(self._stop_session)
        toolbar.addWidget(self._stop_button)
        self._error_button = QPushButton("错误详情")
        self._error_button.setToolTip("查看可复制的 replay session 错误")
        self._error_button.clicked.connect(self._show_error_details)
        toolbar.addWidget(self._error_button)
        self._status_badge = StatusBadge("Stopped", "disabled")
        toolbar.addWidget(self._status_badge)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        header = QFrame()
        header.setStyleSheet("background: #FFFFFF; border: 1px solid #D8DEE6; border-radius: 6px;")
        header_layout = QGridLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setHorizontalSpacing(16)
        title = QLabel("Scenario")
        title.setStyleSheet("color: #667085;")
        self._scenario_value = QLabel("未启动")
        self._scenario_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        state_title = QLabel("State")
        state_title.setStyleSheet("color: #667085;")
        self._state_value = QLabel("Stopped")
        self._state_value.setStyleSheet("font-weight: 700;")
        header_layout.addWidget(title, 0, 0)
        header_layout.addWidget(self._scenario_value, 1, 0)
        header_layout.addWidget(state_title, 0, 1)
        header_layout.addWidget(self._state_value, 1, 1)
        layout.addWidget(header)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFormat("Progress %p%")
        layout.addWidget(self._progress)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        for index, label in enumerate(
            (
                "Timeline",
                "Current ns",
                "Total ns",
                "Sent frames",
                "Skipped frames",
                "Errors",
                "Completed loops",
                "Devices / Channels",
            )
        ):
            grid.addWidget(self._metric_box(label), index // 2, index % 2)
        layout.addLayout(grid)

        self._empty = EmptyState(
            "Replay session 未启动",
            "从 Scenarios 页面运行当前 draft 后，这里显示 snapshot、进度和计数。",
        )
        layout.addWidget(self._empty, 1)

    def _metric_box(self, label: str) -> QFrame:
        box = QFrame()
        box.setStyleSheet("background: #FFFFFF; border: 1px solid #D8DEE6; border-radius: 6px;")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel(str(label))
        title.setStyleSheet("color: #667085;")
        value = QLabel("0")
        value.setStyleSheet("font-size: 18px; font-weight: 700;")
        self._metric_values[str(label)] = value
        box_layout.addWidget(title)
        box_layout.addWidget(value)
        return box

    def _sync_session(self) -> None:
        summary = self._view_model.summary
        if summary is None:
            self._scenario_value.setText("未启动")
            self._metric_values["Devices / Channels"].setText("0 / 0")
        else:
            self._scenario_value.setText(summary.name)
            self._metric_values["Devices / Channels"].setText(f"{summary.device_count} / {summary.channel_count}")
        self._sync_snapshot()

    def _sync_snapshot(self) -> None:
        state = self._view_model.display_state
        self._state_value.setText(state)
        self._status_badge.set_status(state, _state_semantic(state))
        self._progress.setValue(round(self._view_model.progress_percent))
        self._metric_values["Timeline"].setText(
            f"{self._view_model.timeline_index}/{self._view_model.timeline_size}"
        )
        self._metric_values["Current ns"].setText(str(self._view_model.current_ts_ns))
        self._metric_values["Total ns"].setText(str(self._view_model.total_ts_ns))
        self._metric_values["Sent frames"].setText(str(self._view_model.sent_frames))
        self._metric_values["Skipped frames"].setText(str(self._view_model.skipped_frames))
        self._metric_values["Errors"].setText(str(self._view_model.errors))
        self._metric_values["Completed loops"].setText(str(self._view_model.completed_loops))
        self._sync_controls()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_controls(self) -> None:
        self._pause_button.setEnabled(self._view_model.can_pause)
        self._resume_button.setEnabled(self._view_model.can_resume)
        self._stop_button.setEnabled(self._view_model.can_stop)
        self._error_button.setEnabled(bool(self._error_detail_text()))

    def _sync_error(self, _message: str) -> None:
        self._sync_controls()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _stop_session(self) -> None:
        dialog = self.create_stop_confirmation_dialog()
        if dialog.exec() == QMessageBox.StandardButton.Ok:
            self._view_model.stop()

    def _show_error_details(self) -> None:
        if not self._error_detail_text():
            return
        self.create_error_dialog().exec()

    def _error_detail_text(self) -> str:
        return self._view_model.error or self._view_model.error_text


def _state_semantic(state: str) -> str:
    if state == "Running":
        return "running"
    if state == "Paused":
        return "missing"
    if state == "Completed":
        return "ready"
    if state == "Failed":
        return "failed"
    return "disabled"


class DevicesView(QWidget):
    """Devices page with editable enumeration config and app-layer results."""

    inspectorChanged = Signal(str, str)

    def __init__(self, view_model: DevicesViewModel) -> None:
        """Create the devices view.

        Args:
            view_model: ViewModel that enumerates devices through the app layer.
        """
        super().__init__()
        self._view_model = view_model
        self._capability_model = ObjectTableModel(
            (
                TableColumn("Capability", lambda row: row.name),
                TableColumn("Supported", lambda row: "Yes" if row.supported else "No"),
            )
        )
        self._channel_model = ObjectTableModel(
            (
                TableColumn("Physical Channel", lambda row: row.physical_channel, align_right=True),
                TableColumn("Status", lambda row: row.status),
            )
        )
        self._build_ui()
        self._view_model.configChanged.connect(self._sync_config)
        self._view_model.resultChanged.connect(self._sync_result)
        self._view_model.busyChanged.connect(self._sync_busy)
        self._view_model.errorChanged.connect(self._sync_error)
        self._view_model.statusMessageChanged.connect(
            lambda message: self.inspectorChanged.emit("Devices", message)
        )
        self._sync_config()
        self._sync_result()
        self._sync_busy(self._view_model.busy)

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        if self._view_model.error:
            return ("Devices 错误", self._view_model.error)
        summary = self._view_model.summary
        if summary is not None:
            return (
                "Device Enumeration",
                "\n".join(
                    (
                        f"Device ID: {summary.device_id}",
                        f"Driver: {summary.driver}",
                        f"Name: {summary.name}",
                        f"Serial: {summary.serial_number}",
                        f"Channels: {summary.channel_count}",
                        f"Health: {summary.health}",
                        f"Detail: {summary.health_detail}",
                    )
                ),
            )
        return (
            "Devices",
            "同星真机能力只能在 Windows + TSMaster + 实际设备上验证；自动化优先覆盖 mock 枚举。",
        )

    def enumerate_enabled(self) -> bool:
        """Return whether Enumerate is enabled.

        Returns:
            True when device enumeration can start.
        """
        return self._enumerate_button.isEnabled()

    def error_details_enabled(self) -> bool:
        """Return whether error details can be opened.

        Returns:
            True when a device error exists.
        """
        return self._error_button.isEnabled()

    def status_badge_state(self) -> tuple[str, str]:
        """Return status badge text and semantic key.

        Returns:
            Tuple of visible text and semantic state.
        """
        return self._status_badge.text(), self._status_badge.semantic

    def set_driver(self, driver: str) -> None:
        """Set the selected driver through the combo box.

        Args:
            driver: Driver identifier to select.
        """
        index = self._combo_index_for_text(self._driver_combo, driver)
        if index < 0:
            self._driver_combo.addItem(str(driver))
            index = self._combo_index_for_text(self._driver_combo, driver)
        self._driver_combo.setCurrentIndex(index)

    def edit_sdk_root(self, value: str) -> None:
        """Set SDK root text for tests and keyboard workflows.

        Args:
            value: New SDK root.
        """
        self._sdk_root_edit.setText(str(value))
        self._apply_sdk_root()

    def edit_application(self, value: str) -> None:
        """Set application text for tests and keyboard workflows.

        Args:
            value: New application name.
        """
        self._application_edit.setText(str(value))
        self._apply_application()

    def edit_device_type(self, value: str) -> None:
        """Set device type text for tests and keyboard workflows.

        Args:
            value: New device type.
        """
        self._device_type_edit.setText(str(value))
        self._apply_device_type()

    def edit_device_index(self, value: int) -> None:
        """Set device index for tests and keyboard workflows.

        Args:
            value: New device index.
        """
        self._device_index_spin.setValue(int(value))
        self._apply_device_index()

    def trigger_enumerate(self) -> None:
        """Trigger device enumeration for tests and keyboard workflows."""
        self._view_model.enumerate_current_device()

    def summary_text(self) -> str:
        """Return summary text from the result panel.

        Returns:
            Plain text shown in the summary panel.
        """
        return self._summary_text.toPlainText()

    def channel_row_count(self) -> int:
        """Return rendered channel row count.

        Returns:
            Number of channel table rows.
        """
        return self._channel_model.rowCount()

    def capability_row_count(self) -> int:
        """Return rendered capability row count.

        Returns:
            Number of capability table rows.
        """
        return self._capability_model.rowCount()

    def create_error_dialog(self):
        """Create the current Devices error details dialog.

        Returns:
            Error details dialog for the current ViewModel error.
        """
        return create_error_details_dialog(
            self,
            title="Devices 错误",
            summary="Devices 枚举失败",
            detail=self._view_model.error,
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self._enumerate_button = QPushButton("Enumerate")
        self._enumerate_button.setToolTip("通过 app 层枚举当前设备配置")
        self._enumerate_button.clicked.connect(self._view_model.enumerate_current_device)
        toolbar.addWidget(self._enumerate_button)
        self._error_button = QPushButton("错误详情")
        self._error_button.setEnabled(False)
        self._error_button.setToolTip("查看可复制的设备枚举错误")
        self._error_button.clicked.connect(self._show_error_details)
        toolbar.addWidget(self._error_button)
        self._status_badge = StatusBadge("Idle", "default")
        toolbar.addWidget(self._status_badge)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        form_frame = QFrame()
        form_frame.setStyleSheet("background: #FFFFFF; border: 1px solid #D8DEE6; border-radius: 6px;")
        form = QFormLayout(form_frame)
        form.setContentsMargins(16, 16, 16, 16)
        self._driver_combo = QComboBox()
        for driver in self._view_model.drivers:
            self._driver_combo.addItem(driver)
        self._driver_combo.currentTextChanged.connect(self._apply_driver)
        self._sdk_root_edit = QLineEdit()
        self._sdk_root_edit.editingFinished.connect(self._apply_sdk_root)
        self._application_edit = QLineEdit()
        self._application_edit.editingFinished.connect(self._apply_application)
        self._device_type_edit = QLineEdit()
        self._device_type_edit.editingFinished.connect(self._apply_device_type)
        self._device_index_spin = QSpinBox()
        self._device_index_spin.setRange(0, 255)
        self._device_index_spin.editingFinished.connect(self._apply_device_index)
        form.addRow("Driver", self._driver_combo)
        form.addRow("SDK root", self._sdk_root_edit)
        form.addRow("Application", self._application_edit)
        form.addRow("Device type", self._device_type_edit)
        form.addRow("Device index", self._device_index_spin)
        layout.addWidget(form_frame)

        warning = QLabel("Tongxing 真机枚举需要 Windows + TSMaster + 实际设备；mock 可用于自动化验证。")
        warning.setStyleSheet("color: #667085;")
        layout.addWidget(warning)

        self._summary_text = QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setPlainText("尚未枚举设备。")
        layout.addWidget(self._summary_text)

        tables = QHBoxLayout()
        self._capabilities_table = QTableView()
        self._capabilities_table.setModel(self._capability_model)
        self._capabilities_table.verticalHeader().setVisible(False)
        self._capabilities_table.setColumnWidth(0, 160)
        self._capabilities_table.setColumnWidth(1, 100)
        tables.addWidget(self._capabilities_table)

        self._channels_table = QTableView()
        self._channels_table.setModel(self._channel_model)
        self._channels_table.verticalHeader().setVisible(False)
        self._channels_table.setColumnWidth(0, 150)
        self._channels_table.setColumnWidth(1, 160)
        tables.addWidget(self._channels_table)
        layout.addLayout(tables, 1)

        self._empty = EmptyState(
            "设备结果为空",
            "点击 Enumerate 后显示 device info、capabilities、health 和 channel 列表。",
        )
        layout.addWidget(self._empty)

    def _sync_config(self) -> None:
        draft = self._view_model.draft
        self._driver_combo.blockSignals(True)
        index = self._combo_index_for_text(self._driver_combo, draft.driver)
        if index < 0:
            self._driver_combo.addItem(draft.driver)
            index = self._combo_index_for_text(self._driver_combo, draft.driver)
        self._driver_combo.setCurrentIndex(index)
        self._driver_combo.blockSignals(False)

        self._sdk_root_edit.blockSignals(True)
        self._sdk_root_edit.setText(draft.sdk_root)
        self._sdk_root_edit.blockSignals(False)
        self._application_edit.blockSignals(True)
        self._application_edit.setText(draft.application)
        self._application_edit.blockSignals(False)
        self._device_type_edit.blockSignals(True)
        self._device_type_edit.setText(draft.device_type)
        self._device_type_edit.blockSignals(False)
        self._device_index_spin.blockSignals(True)
        self._device_index_spin.setValue(draft.device_index)
        self._device_index_spin.blockSignals(False)

    def _sync_result(self) -> None:
        summary = self._view_model.summary
        if summary is None:
            self._summary_text.setPlainText("尚未枚举设备。")
        else:
            self._summary_text.setPlainText(
                "\n".join(
                    (
                        f"Device ID: {summary.device_id}",
                        f"Driver: {summary.driver}",
                        f"Name: {summary.name}",
                        f"Serial: {summary.serial_number}",
                        f"Channels: {summary.channel_count}",
                        f"Health: {summary.health}",
                        f"Detail: {summary.health_detail}",
                    )
                )
            )
        self._capability_model.set_rows(self._view_model.capabilities)
        self._channel_model.set_rows(self._view_model.channels)
        self._sync_status_badge()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_busy(self, busy: bool) -> None:
        idle = not bool(busy)
        self._enumerate_button.setEnabled(idle)
        self._driver_combo.setEnabled(idle)
        self._sdk_root_edit.setEnabled(idle)
        self._application_edit.setEnabled(idle)
        self._device_type_edit.setEnabled(idle)
        self._device_index_spin.setEnabled(idle)
        self._sync_status_badge()

    def _sync_error(self, message: str) -> None:
        self._error_button.setEnabled(bool(message))
        self._sync_status_badge()
        if message:
            self.inspectorChanged.emit("Devices 错误", message)

    def _sync_status_badge(self) -> None:
        if self._view_model.error:
            self._status_badge.set_status("Failed", "failed")
        elif self._view_model.busy:
            self._status_badge.set_status("Enumerating", "running")
        elif self._view_model.summary is not None:
            self._status_badge.set_status("Ready", "ready")
        else:
            self._status_badge.set_status("Idle", "default")

    def _apply_driver(self, driver: str) -> None:
        self._view_model.set_driver(driver)

    def _apply_sdk_root(self) -> None:
        self._view_model.set_sdk_root(self._sdk_root_edit.text())

    def _apply_application(self) -> None:
        self._view_model.set_application(self._application_edit.text())

    def _apply_device_type(self) -> None:
        self._view_model.set_device_type(self._device_type_edit.text())

    def _apply_device_index(self) -> None:
        self._view_model.set_device_index(self._device_index_spin.value())

    def _show_error_details(self) -> None:
        if not self._view_model.error:
            return
        self.create_error_dialog().exec()

    def _combo_index_for_text(self, combo: QComboBox, value: str) -> int:
        for index in range(combo.count()):
            if combo.itemText(index) == str(value):
                return index
        return -1

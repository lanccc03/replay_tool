from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.app_context import AppContext
from replay_ui_qt.view_models.replay_session import ReplaySessionViewModel
from replay_ui_qt.widgets.dialogs import create_danger_confirmation, create_error_details_dialog
from replay_ui_qt.widgets.empty_state import EmptyState
from replay_ui_qt.widgets.status_badge import StatusBadge


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
    """First-stage devices page with disabled hardware actions."""

    inspectorChanged = Signal(str, str)

    def __init__(self) -> None:
        """Create the devices placeholder view."""
        super().__init__()
        self._build_ui()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        return (
            "Devices",
            "同星真机能力只能在 Windows + TSMaster + 实际设备上验证；本阶段不执行硬件枚举。",
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        form_frame = QFrame()
        form_frame.setStyleSheet("background: #FFFFFF; border: 1px solid #D8DEE6; border-radius: 6px;")
        form = QFormLayout(form_frame)
        form.setContentsMargins(16, 16, 16, 16)
        for label, value in (
            ("Driver", "tongxing"),
            ("SDK root", "TSMaster/Windows"),
            ("Application", "ReplayTool"),
            ("Device type", "TC1014"),
            ("Device index", "0"),
        ):
            field = QLineEdit(value)
            field.setEnabled(False)
            field.setToolTip("后续接入设备枚举")
            form.addRow(label, field)
        layout.addWidget(form_frame)

        button = QPushButton("Enumerate")
        button.setEnabled(False)
        button.setToolTip("后续接入；真机需 Windows + TSMaster + 实际设备")
        layout.addWidget(button)
        layout.addWidget(
            EmptyState(
                "设备枚举未接入",
                "当前页面只保留配置入口，不把硬件能力展示成已完成状态。",
            ),
            1,
        )


class SettingsView(QWidget):
    """First-stage settings page showing workspace and theme facts."""

    inspectorChanged = Signal(str, str)

    def __init__(self, context: AppContext) -> None:
        """Create the settings placeholder view.

        Args:
            context: Shared application context with workspace information.
        """
        super().__init__()
        self._context = context
        self._build_ui()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        return (
            "Settings",
            f"Workspace: {self._context.workspace}\nTheme: 默认浅色工程主题\n深色主题后续接入。",
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(
            EmptyState(
                "Settings",
                f"当前 workspace: {self._context.workspace}\n主题遵循 docs/ui-style-guide.md。",
            ),
            1,
        )

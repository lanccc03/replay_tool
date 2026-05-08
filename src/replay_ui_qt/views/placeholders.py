from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.app_context import AppContext
from replay_ui_qt.view_models.replay_session import ReplaySessionViewModel
from replay_ui_qt.widgets.empty_state import EmptyState


class ReplayMonitorView(QWidget):
    """First-stage replay monitor shell with disabled controls."""

    inspectorChanged = Signal(str, str)

    def __init__(self, view_model: ReplaySessionViewModel) -> None:
        """Create the replay monitor placeholder.

        Args:
            view_model: Replay session ViewModel with current placeholder state.
        """
        super().__init__()
        self._view_model = view_model
        self._build_ui()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        return (
            "Replay Monitor",
            "运行控制会在下一阶段通过 app 层会话 API 接入；本阶段不直接操作 ReplayRuntime。",
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        for label in ("Run", "Pause", "Resume", "Stop"):
            button = QPushButton(label)
            button.setEnabled(False)
            button.setToolTip("后续通过 app 层 replay session API 接入")
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        items = (
            ("Runtime", self._view_model.runtime_state),
            ("Sent frames", str(self._view_model.sent_frames)),
            ("Skipped frames", str(self._view_model.skipped_frames)),
            ("Errors", str(self._view_model.errors)),
        )
        for index, (label, value) in enumerate(items):
            box = QFrame()
            box.setStyleSheet("background: #FFFFFF; border: 1px solid #D8DEE6; border-radius: 6px;")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(12, 10, 12, 10)
            title = QLabel(label)
            title.setStyleSheet("color: #667085;")
            number = QLabel(value)
            number.setStyleSheet("font-size: 18px; font-weight: 700;")
            box_layout.addWidget(title)
            box_layout.addWidget(number)
            grid.addWidget(box, index // 2, index % 2)
        layout.addLayout(grid)
        layout.addWidget(
            EmptyState(
                "Replay session 未接入",
                "当前页面只展示 STOPPED 占位状态，避免 UI 直接控制 runtime 内部对象。",
            ),
            1,
        )


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


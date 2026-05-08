from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QStackedWidget, QTableView, QVBoxLayout, QWidget

from replay_ui_qt.view_models.scenarios import ScenarioRow, ScenariosViewModel
from replay_ui_qt.widgets.empty_state import EmptyState
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
        self._build_ui()
        self._view_model.rowsChanged.connect(self._sync_rows)
        self._view_model.statusMessageChanged.connect(lambda message: self.inspectorChanged.emit("Scenarios", message))
        self._view_model.errorChanged.connect(self._show_error)
        self._view_model.refresh()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        row = self._selected_row()
        if row is None:
            return ("Scenarios", "选择一个 Scenario 查看保存 ID、trace 数量、route 数量和 base dir。")
        return ("Scenario 详情", _scenario_detail(row))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.setToolTip("重新读取当前 workspace 的 Scenario Store")
        refresh.clicked.connect(self._view_model.refresh)
        toolbar.addWidget(refresh)

        for label in ("Save Scenario", "Validate", "Run", "Delete"):
            button = QPushButton(label)
            button.setEnabled(False)
            button.setToolTip("后续接入")
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

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
        self._table.selectionModel().currentRowChanged.connect(lambda _current, _previous: self._emit_selection())
        self._empty = EmptyState("No scenarios.", "使用 CLI 保存 schema v2 scenario 后，这里会显示 Scenario Store 记录。")
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)
        layout.addWidget(self._stack, 1)

    def _sync_rows(self) -> None:
        self._model.set_rows(self._view_model.rows)
        self._stack.setCurrentWidget(self._empty if not self._view_model.rows else self._table)
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _show_error(self, message: str) -> None:
        if message:
            self.inspectorChanged.emit("Scenarios 错误", message)

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


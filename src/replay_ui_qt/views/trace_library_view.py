from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.view_models.trace_library import TraceLibraryViewModel, TraceRow
from replay_ui_qt.widgets.empty_state import EmptyState
from replay_ui_qt.widgets.table_model import ObjectTableModel, TableColumn


class TraceLibraryView(QWidget):
    """Trace Library page with a read-only table of imported traces."""

    inspectorChanged = Signal(str, str)

    def __init__(self, view_model: TraceLibraryViewModel) -> None:
        """Create the Trace Library view.

        Args:
            view_model: ViewModel that supplies trace rows.
        """
        super().__init__()
        self._view_model = view_model
        self._model = ObjectTableModel(
            (
                TableColumn("名称", lambda row: row.name),
                TableColumn("Trace ID", lambda row: row.trace_id, monospace=True),
                TableColumn("Frames", lambda row: row.event_count, align_right=True),
                TableColumn("Start ns", lambda row: row.start_ns, monospace=True, align_right=True),
                TableColumn("End ns", lambda row: row.end_ns, monospace=True, align_right=True),
                TableColumn("Cache", lambda row: row.cache_status, status=True),
            )
        )
        self._build_ui()
        self._view_model.rowsChanged.connect(self._sync_rows)
        self._view_model.statusMessageChanged.connect(lambda message: self.inspectorChanged.emit("Trace Library", message))
        self._view_model.errorChanged.connect(self._show_error)
        self._view_model.refresh()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        row = self._selected_row()
        if row is None:
            return ("Trace Library", "选择一条 Trace 记录查看 original path、cache path 和 cache 状态。")
        return ("Trace 详情", _trace_detail(row))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        refresh = QPushButton("刷新")
        refresh.setToolTip("重新读取当前 workspace 的 Trace Library")
        refresh.clicked.connect(self._view_model.refresh)
        toolbar.addWidget(refresh)

        for label in ("Import Trace", "Inspect", "Rebuild Cache", "Delete"):
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
        self._table.setColumnWidth(3, 140)
        self._table.setColumnWidth(4, 140)
        self._table.setColumnWidth(5, 120)
        self._table.selectionModel().currentRowChanged.connect(lambda _current, _previous: self._emit_selection())
        self._empty = EmptyState("No traces.", "使用 CLI 或后续 UI 导入 ASC 后，这里会显示 Trace Library 记录。")
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)
        layout.addWidget(self._stack, 1)

    def _sync_rows(self) -> None:
        self._model.set_rows(self._view_model.rows)
        self._stack.setCurrentWidget(self._empty if not self._view_model.rows else self._table)
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _show_error(self, message: str) -> None:
        if message:
            self.inspectorChanged.emit("Trace Library 错误", message)

    def _emit_selection(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _selected_row(self) -> TraceRow | None:
        current = self._table.currentIndex()
        if not current.isValid():
            return None
        row = self._model.row_at(current.row())
        return row if isinstance(row, TraceRow) else None


def _trace_detail(row: TraceRow) -> str:
    return "\n".join(
        (
            f"名称: {row.name}",
            f"Trace ID: {row.trace_id}",
            f"Frames: {row.event_count}",
            f"Start ns: {row.start_ns}",
            f"End ns: {row.end_ns}",
            f"Cache: {row.cache_status}",
            f"Original path: {row.original_path}",
            f"Cache path: {row.cache_path}",
        )
    )


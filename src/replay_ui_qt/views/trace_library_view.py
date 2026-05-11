from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.view_models.trace_library import (
    TraceDeleteResultDetails,
    TraceInspectionDetails,
    TraceLibraryViewModel,
    TraceRow,
)
from replay_ui_qt.widgets.dialogs import create_danger_confirmation, create_error_details_dialog
from replay_ui_qt.widgets.empty_state import EmptyState
from replay_ui_qt.widgets.status_badge import StatusBadge
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
                TableColumn("Frames", lambda row: row.event_count),
                TableColumn("Start ns", lambda row: row.start_ns, monospace=True),
                TableColumn("End ns", lambda row: row.end_ns, monospace=True),
                TableColumn("Cache", lambda row: row.cache_status, status=True),
            )
        )
        self._build_ui()
        self._view_model.rowsChanged.connect(self._sync_rows)
        self._view_model.statusMessageChanged.connect(lambda message: self.inspectorChanged.emit("Trace Library", message))
        self._view_model.errorChanged.connect(self._show_error)
        self._view_model.busyChanged.connect(self._sync_busy)
        self._view_model.inspectionChanged.connect(self._sync_inspection)
        self._view_model.deleteResultChanged.connect(self._sync_delete_result)
        self._view_model.refresh()

    def inspector_snapshot(self) -> tuple[str, str]:
        """Return the current inspector content for this page.

        Returns:
            Tuple of title and body text.
        """
        row = self._selected_row()
        if row is None:
            delete_result = self._view_model.delete_result
            if delete_result is not None:
                return ("Trace 删除结果", _delete_result_detail(delete_result))
            return ("Trace Library", "选择一条 Trace 记录查看 original path、cache path 和 cache 状态。")
        return ("Trace 详情", _trace_detail(row, self._inspection_for(row)))

    def import_enabled(self) -> bool:
        """Return whether the import button is enabled.

        Returns:
            True when an import can be triggered.
        """
        return self._import_button.isEnabled()

    def delete_enabled(self) -> bool:
        """Return whether the delete button is enabled.

        Returns:
            True when the selected row can be deleted.
        """
        return self._delete_button.isEnabled()

    def select_row(self, row: int) -> None:
        """Select one table row for tests and keyboard-style workflows.

        Args:
            row: Zero-based table row index.
        """
        if 0 <= row < self._model.rowCount():
            self._table.selectRow(row)
            self._emit_selection()
            self._sync_command_buttons()

    def status_badge_state(self) -> tuple[str, str]:
        """Return status badge text and semantic key.

        Returns:
            Tuple of visible text and semantic state.
        """
        return self._status_badge.text(), self._status_badge.semantic

    def create_error_dialog(self):
        """Create the current error details dialog.

        Returns:
            Error details dialog for the current ViewModel error.
        """
        return create_error_details_dialog(
            self,
            title="Trace Library 错误",
            summary="Trace Library 操作失败",
            detail=self._view_model.error,
        )

    def create_delete_confirmation_dialog(self):
        """Create the delete confirmation dialog for the selected trace.

        Returns:
            Standard dangerous-action confirmation message box.
        """
        row = self._selected_row()
        object_label = row.name if row is not None else "Trace"
        object_id = row.trace_id if row is not None else ""
        return create_danger_confirmation(
            self,
            action="Delete Trace",
            object_label=object_label,
            object_id=object_id,
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        self._import_button = QPushButton("Import Trace")
        self._import_button.setToolTip("导入 ASC Trace")
        self._import_button.clicked.connect(self._choose_import_trace)
        toolbar.addWidget(self._import_button)

        self._delete_button = QPushButton("Delete")
        self._delete_button.setEnabled(False)
        self._delete_button.setToolTip("删除选中 Trace 和 managed files")
        self._delete_button.clicked.connect(self._delete_selected_trace)
        toolbar.addWidget(self._delete_button)
        self._status_badge = StatusBadge("Idle", "default")
        toolbar.addWidget(self._status_badge)
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
        self._table.selectionModel().currentRowChanged.connect(lambda _current, _previous: self._handle_selection_changed())
        self._empty = EmptyState("No traces.", "使用 CLI 或后续 UI 导入 ASC 后，这里会显示 Trace Library 记录。")
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty)
        layout.addWidget(self._stack, 1)

    def _sync_rows(self) -> None:
        self._model.set_rows(self._view_model.rows)
        self._stack.setCurrentWidget(self._empty if not self._view_model.rows else self._table)
        self._sync_status_badge()
        self._sync_command_buttons()
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _show_error(self, message: str) -> None:
        self._sync_status_badge()
        if message:
            self.inspectorChanged.emit("Trace Library 错误", message)

    def _sync_busy(self, busy: bool) -> None:
        self._import_button.setEnabled(not busy)
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

    def _choose_import_trace(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "导入 ASC Trace",
            "",
            "ASC Trace (*.asc);;All files (*)",
        )
        if path:
            self._view_model.import_trace(path)

    def _sync_command_buttons(self) -> None:
        row = self._selected_row()
        enabled = row is not None and not self._view_model.busy
        self._delete_button.setEnabled(enabled)

    def _sync_inspection(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _sync_delete_result(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _handle_selection_changed(self) -> None:
        self._sync_command_buttons()
        self._emit_selection()

    def _delete_selected_trace(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        dialog = self.create_delete_confirmation_dialog()
        if dialog.exec() == QMessageBox.StandardButton.Ok:
            self._view_model.delete_trace(row.trace_id)

    def _emit_selection(self) -> None:
        self.inspectorChanged.emit(*self.inspector_snapshot())

    def _selected_row(self) -> TraceRow | None:
        current = self._table.currentIndex()
        if not current.isValid():
            return None
        row = self._model.row_at(current.row())
        return row if isinstance(row, TraceRow) else None

    def _inspection_for(self, row: TraceRow) -> TraceInspectionDetails | None:
        inspection = self._view_model.inspection
        if inspection is None or inspection.trace_id != row.trace_id:
            return None
        return inspection


def _trace_detail(row: TraceRow, inspection: TraceInspectionDetails | None = None) -> str:
    detail = [
        f"名称: {row.name}",
        f"Trace ID: {row.trace_id}",
        f"Frames: {row.event_count}",
        f"Start ns: {row.start_ns}",
        f"End ns: {row.end_ns}",
        f"Cache: {row.cache_status}",
        f"Original path: {row.original_path}",
        f"Cache path: {row.cache_path}",
    ]
    if inspection is not None:
        detail.extend(
            (
                f"Library path: {inspection.library_path}",
                "",
                "Sources:",
            )
        )
        if inspection.sources:
            detail.extend(
                f"  CH{source.source_channel} {source.bus} frames={source.frame_count}"
                for source in inspection.sources
            )
        else:
            detail.append("  No sources")
        detail.append("")
        detail.append("Messages:")
        if inspection.messages:
            detail.extend(
                (
                    "  CH{channel} {bus} frames={frames} ids={ids}".format(
                        channel=message.source_channel,
                        bus=message.bus,
                        frames=message.frame_count,
                        ids=", ".join(f"0x{message_id:X}" for message_id in message.message_ids),
                    )
                )
                for message in inspection.messages
            )
        else:
            detail.append("  No messages")
    return "\n".join(detail)


def _delete_result_detail(result: TraceDeleteResultDetails) -> str:
    return "\n".join(
        (
            f"名称: {result.name}",
            f"Trace ID: {result.trace_id}",
            f"Deleted library file: {result.deleted_library_file}",
            f"Deleted cache file: {result.deleted_cache_file}",
        )
    )

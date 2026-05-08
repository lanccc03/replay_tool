from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Signal

from replay_tool.ports.trace_store import (
    DeleteTraceResult,
    TraceInspection,
    TraceMessageSummary,
    TraceRecord,
    TraceSourceSummary,
)
from replay_ui_qt.tasks import TaskRunner
from replay_ui_qt.view_models.base import BaseViewModel


class TraceLibraryApplication(Protocol):
    """Application methods required by the Trace Library ViewModel."""

    def import_trace(self, path: str | Path) -> TraceRecord:
        """Import an ASC trace into the active workspace.

        Args:
            path: Source ASC path.

        Returns:
            Imported trace metadata.
        """
        ...

    def list_traces(self) -> list[TraceRecord]:
        """List imported trace records.

        Returns:
            Trace records from the active workspace.
        """
        ...

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        """Inspect one imported trace.

        Args:
            trace_id: Trace Library identifier.

        Returns:
            Trace metadata plus source and message summaries.
        """
        ...

    def rebuild_trace_cache(self, trace_id: str) -> TraceRecord:
        """Rebuild cache for one imported trace.

        Args:
            trace_id: Trace Library identifier.

        Returns:
            Updated trace metadata.
        """
        ...

    def delete_trace(self, trace_id: str) -> DeleteTraceResult:
        """Delete one imported trace.

        Args:
            trace_id: Trace Library identifier.

        Returns:
            Delete result describing removed managed files.
        """
        ...


@dataclass(frozen=True)
class TraceRow:
    """Display row for one imported Trace Library record."""

    trace_id: str
    name: str
    event_count: int
    start_ns: int
    end_ns: int
    cache_status: str
    original_path: str
    cache_path: str

    @classmethod
    def from_record(cls, record: TraceRecord) -> "TraceRow":
        """Build a display row from a trace record.

        Args:
            record: Stored Trace Library metadata.

        Returns:
            Row values ready for table display.
        """
        cache_path = str(record.cache_path)
        cache_status = "Cache Ready" if cache_path and Path(cache_path).exists() else "Cache Missing"
        return cls(
            trace_id=record.trace_id,
            name=record.name,
            event_count=int(record.event_count),
            start_ns=int(record.start_ns),
            end_ns=int(record.end_ns),
            cache_status=cache_status,
            original_path=record.original_path,
            cache_path=cache_path,
        )


@dataclass(frozen=True)
class TraceSourceSummaryRow:
    """Display row for one trace source summary."""

    source_channel: int
    bus: str
    frame_count: int

    @classmethod
    def from_summary(cls, summary: TraceSourceSummary) -> "TraceSourceSummaryRow":
        """Build a display row from a trace source summary.

        Args:
            summary: Source summary returned by the trace store.

        Returns:
            Row values ready for Inspector display.
        """
        return cls(
            source_channel=int(summary.source_channel),
            bus=_bus_text(summary.bus),
            frame_count=int(summary.frame_count),
        )


@dataclass(frozen=True)
class TraceMessageSummaryRow:
    """Display row for one trace message summary."""

    source_channel: int
    bus: str
    frame_count: int
    message_ids: tuple[int, ...]

    @classmethod
    def from_summary(cls, summary: TraceMessageSummary) -> "TraceMessageSummaryRow":
        """Build a display row from a trace message summary.

        Args:
            summary: Message summary returned by the trace store.

        Returns:
            Row values ready for Inspector display.
        """
        return cls(
            source_channel=int(summary.source_channel),
            bus=_bus_text(summary.bus),
            frame_count=int(summary.frame_count),
            message_ids=tuple(int(message_id) for message_id in summary.message_ids),
        )


@dataclass(frozen=True)
class TraceInspectionDetails:
    """Inspector details for one imported trace."""

    trace_id: str
    name: str
    event_count: int
    start_ns: int
    end_ns: int
    original_path: str
    library_path: str
    cache_path: str
    sources: tuple[TraceSourceSummaryRow, ...]
    messages: tuple[TraceMessageSummaryRow, ...]

    @classmethod
    def from_inspection(cls, inspection: TraceInspection) -> "TraceInspectionDetails":
        """Build Inspector details from a trace inspection result.

        Args:
            inspection: App-layer inspection result.

        Returns:
            Details ready for Trace Library Inspector display.
        """
        record = inspection.record
        return cls(
            trace_id=record.trace_id,
            name=record.name,
            event_count=int(record.event_count),
            start_ns=int(record.start_ns),
            end_ns=int(record.end_ns),
            original_path=record.original_path,
            library_path=record.library_path,
            cache_path=record.cache_path,
            sources=tuple(TraceSourceSummaryRow.from_summary(summary) for summary in inspection.sources),
            messages=tuple(TraceMessageSummaryRow.from_summary(summary) for summary in inspection.messages),
        )


@dataclass(frozen=True)
class TraceDeleteResultDetails:
    """Inspector details for one deleted trace."""

    trace_id: str
    name: str
    deleted_library_file: bool
    deleted_cache_file: bool

    @classmethod
    def from_result(cls, result: DeleteTraceResult) -> "TraceDeleteResultDetails":
        """Build Inspector details from a delete result.

        Args:
            result: App-layer delete result.

        Returns:
            Details ready for Trace Library Inspector display.
        """
        return cls(
            trace_id=result.trace_id,
            name=result.name,
            deleted_library_file=bool(result.deleted_library_file),
            deleted_cache_file=bool(result.deleted_cache_file),
        )


class TraceLibraryViewModel(BaseViewModel):
    """Load and expose Trace Library rows for Qt views."""

    rowsChanged = Signal()
    inspectionChanged = Signal()
    deleteResultChanged = Signal()

    def __init__(self, application: TraceLibraryApplication, task_runner: TaskRunner) -> None:
        """Initialize the Trace Library ViewModel.

        Args:
            application: App-layer facade used to list traces.
            task_runner: Shared UI background task runner.
        """
        super().__init__()
        self._application = application
        self._task_runner = task_runner
        self._refresh_task_name = f"trace-library-refresh-{id(self)}"
        self._import_task_name = f"trace-library-import-{id(self)}"
        self._inspect_task_name = f"trace-library-inspect-{id(self)}"
        self._rebuild_task_name = f"trace-library-rebuild-{id(self)}"
        self._delete_task_name = f"trace-library-delete-{id(self)}"
        self._rows: tuple[TraceRow, ...] = ()
        self._inspection: TraceInspectionDetails | None = None
        self._delete_result: TraceDeleteResultDetails | None = None

    @property
    def rows(self) -> tuple[TraceRow, ...]:
        """Return current trace rows.

        Returns:
            Immutable tuple of table rows.
        """
        return self._rows

    @property
    def inspection(self) -> TraceInspectionDetails | None:
        """Return the current inspection details.

        Returns:
            Details for the last inspected trace, or None.
        """
        return self._inspection

    @property
    def delete_result(self) -> TraceDeleteResultDetails | None:
        """Return the current delete result details.

        Returns:
            Details for the last deleted trace, or None.
        """
        return self._delete_result

    def refresh(self) -> None:
        """Reload trace rows from the active workspace."""
        if self.busy:
            self.set_status_message("Trace Library 正在刷新")
            return
        self._rows = ()
        self._set_inspection(None)
        self._set_delete_result(None)
        self.rowsChanged.emit()
        self.run_background_task(
            self._task_runner,
            self._refresh_task_name,
            self._application.list_traces,
            self._apply_records,
            start_status="Trace Library 正在刷新",
            failure_status="Trace Library 加载失败",
            duplicate_status="Trace Library 正在刷新",
        )

    def import_trace(self, path: str | Path) -> None:
        """Import an ASC trace and refresh the Trace Library rows.

        Args:
            path: Source ASC path selected by the user.
        """
        trace_path = Path(path)
        if not str(path):
            self.set_status_message("未选择 ASC 文件")
            return
        if self.busy:
            self.set_status_message("Trace Library 正在执行任务")
            return
        self._set_delete_result(None)

        def import_and_list() -> tuple[TraceRecord, list[TraceRecord]]:
            record = self._application.import_trace(trace_path)
            return record, self._application.list_traces()

        self.run_background_task(
            self._task_runner,
            self._import_task_name,
            import_and_list,
            self._apply_import_result,
            start_status=f"正在导入 Trace: {trace_path.name}",
            failure_status="Trace 导入失败",
            duplicate_status="Trace Library 正在执行任务",
        )

    def inspect_trace(self, trace_id: str) -> None:
        """Inspect one Trace Library record.

        Args:
            trace_id: Trace Library identifier.
        """
        value = str(trace_id)
        if not value:
            self.set_status_message("未选择 Trace")
            return
        if self.busy:
            self.set_status_message("Trace Library 正在执行任务")
            return
        self._set_delete_result(None)
        self.run_background_task(
            self._task_runner,
            self._inspect_task_name,
            lambda: self._application.inspect_trace(value),
            self._apply_inspection_result,
            start_status=f"正在检查 Trace: {value}",
            failure_status="Trace 检查失败",
            duplicate_status="Trace Library 正在执行任务",
        )

    def rebuild_trace_cache(self, trace_id: str) -> None:
        """Rebuild cache for one Trace Library record.

        Args:
            trace_id: Trace Library identifier.
        """
        value = str(trace_id)
        if not value:
            self.set_status_message("未选择 Trace")
            return
        if self.busy:
            self.set_status_message("Trace Library 正在执行任务")
            return
        self._set_delete_result(None)

        def rebuild_and_list() -> tuple[str, TraceRecord, list[TraceRecord]]:
            record = self._application.rebuild_trace_cache(value)
            return value, record, self._application.list_traces()

        self.run_background_task(
            self._task_runner,
            self._rebuild_task_name,
            rebuild_and_list,
            self._apply_rebuild_result,
            start_status=f"正在重建 Trace cache: {value}",
            failure_status="Trace cache 重建失败",
            duplicate_status="Trace Library 正在执行任务",
        )

    def delete_trace(self, trace_id: str) -> None:
        """Delete one Trace Library record and refresh rows.

        Args:
            trace_id: Trace Library identifier.
        """
        value = str(trace_id)
        if not value:
            self.set_status_message("未选择 Trace")
            return
        if self.busy:
            self.set_status_message("Trace Library 正在执行任务")
            return

        def delete_and_list() -> tuple[DeleteTraceResult, list[TraceRecord]]:
            result = self._application.delete_trace(value)
            return result, self._application.list_traces()

        self.run_background_task(
            self._task_runner,
            self._delete_task_name,
            delete_and_list,
            self._apply_delete_result,
            start_status=f"正在删除 Trace: {value}",
            failure_status="Trace 删除失败",
            duplicate_status="Trace Library 正在执行任务",
        )

    def _apply_records(self, result: object) -> None:
        records = list(result)
        self._replace_rows(records)
        self.rowsChanged.emit()
        self.set_status_message(f"Trace Library 已加载 {len(self._rows)} 条记录")

    def _apply_import_result(self, result: object) -> None:
        record, records = result
        self._replace_rows(records)
        self.rowsChanged.emit()
        self.set_status_message(f"Trace 已导入: {record.name}")

    def _apply_inspection_result(self, result: object) -> None:
        self._set_inspection(TraceInspectionDetails.from_inspection(result))
        if self._inspection is not None:
            self.set_status_message(f"Trace 已检查: {self._inspection.name}")

    def _apply_rebuild_result(self, result: object) -> None:
        trace_id, record, records = result
        self._replace_rows(records)
        if self._inspection is not None and self._inspection.trace_id == trace_id:
            self._set_inspection(None)
        self.rowsChanged.emit()
        self.set_status_message(f"Trace cache 已重建: {record.name}")

    def _apply_delete_result(self, result: object) -> None:
        delete_result, records = result
        self._replace_rows(records)
        self._set_inspection(None)
        self._set_delete_result(TraceDeleteResultDetails.from_result(delete_result))
        self.rowsChanged.emit()
        self.set_status_message(f"Trace 已删除: {delete_result.name}")

    def _replace_rows(self, records: object) -> None:
        self._rows = tuple(TraceRow.from_record(record) for record in records)

    def _set_inspection(self, inspection: TraceInspectionDetails | None) -> None:
        self._inspection = inspection
        self.inspectionChanged.emit()

    def _set_delete_result(self, result: TraceDeleteResultDetails | None) -> None:
        self._delete_result = result
        self.deleteResultChanged.emit()


def _bus_text(bus: object) -> str:
    return str(getattr(bus, "value", bus))

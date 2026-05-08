from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Signal

from replay_tool.ports.trace_store import TraceRecord
from replay_ui_qt.view_models.base import BaseViewModel


class TraceListApplication(Protocol):
    """Application methods required by the Trace Library ViewModel."""

    def list_traces(self) -> list[TraceRecord]:
        """List imported trace records.

        Returns:
            Trace records from the active workspace.
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


class TraceLibraryViewModel(BaseViewModel):
    """Load and expose Trace Library rows for Qt views."""

    rowsChanged = Signal()

    def __init__(self, application: TraceListApplication) -> None:
        """Initialize the Trace Library ViewModel.

        Args:
            application: App-layer facade used to list traces.
        """
        super().__init__()
        self._application = application
        self._rows: tuple[TraceRow, ...] = ()

    @property
    def rows(self) -> tuple[TraceRow, ...]:
        """Return current trace rows.

        Returns:
            Immutable tuple of table rows.
        """
        return self._rows

    def refresh(self) -> None:
        """Reload trace rows from the active workspace."""
        self._set_busy(True)
        self.clear_error()
        try:
            records = self._application.list_traces()
            self._rows = tuple(TraceRow.from_record(record) for record in records)
            self.rowsChanged.emit()
            self._set_status_message(f"Trace Library 已加载 {len(self._rows)} 条记录")
        except Exception as exc:
            self._rows = ()
            self.rowsChanged.emit()
            self._set_error(str(exc))
            self._set_status_message("Trace Library 加载失败")
        finally:
            self._set_busy(False)


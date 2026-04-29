from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterable, Iterator
from typing import Protocol

from replay_tool.domain import BusType, Frame


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    name: str
    original_path: str
    library_path: str
    cache_path: str
    imported_at: str
    event_count: int = 0
    start_ns: int = 0
    end_ns: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TraceSourceSummary:
    source_channel: int
    bus: BusType
    frame_count: int


@dataclass(frozen=True)
class TraceMessageSummary:
    source_channel: int
    bus: BusType
    frame_count: int
    message_ids: tuple[int, ...]


@dataclass(frozen=True)
class TraceInspection:
    record: TraceRecord
    sources: tuple[TraceSourceSummary, ...]
    messages: tuple[TraceMessageSummary, ...]


@dataclass(frozen=True)
class DeleteTraceResult:
    trace_id: str
    name: str
    deleted_library_file: bool
    deleted_cache_file: bool


class TraceStore(Protocol):
    def import_trace(self, source_path: str) -> TraceRecord:
        """Import a source trace into managed storage.

        Args:
            source_path: Filesystem path to the original trace.

        Returns:
            Metadata record for the imported trace.
        """
        ...

    def list_traces(self) -> list[TraceRecord]:
        """List imported traces.

        Returns:
            Stored trace records.
        """
        ...

    def get_trace(self, trace_id: str) -> TraceRecord | None:
        """Look up a trace by ID.

        Args:
            trace_id: Trace library identifier.

        Returns:
            The matching record, or None when it is unknown.
        """
        ...

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        """Return summary information for an imported trace.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Trace metadata plus source-channel and message-ID summaries.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        ...

    def load_frames(
        self,
        trace_id: str,
        source_filters: Iterable[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> list[Frame]:
        """Load normalized frames for an imported trace.

        Args:
            trace_id: Trace library identifier.
            source_filters: Optional `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Returns:
            Cached frames matching the requested filters.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        ...

    def iter_frames(
        self,
        trace_id: str,
        source_filters: Iterable[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate normalized frames for an imported trace.

        Args:
            trace_id: Trace library identifier.
            source_filters: Optional `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Yields:
            Cached frames matching the requested filters.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        ...

    def rebuild_cache(self, trace_id: str) -> TraceRecord:
        """Rebuild a trace cache from the copied library file.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Updated trace record.

        Raises:
            KeyError: If the trace ID is unknown.
            FileNotFoundError: If the copied library file is missing.
        """
        ...

    def delete_trace(self, trace_id: str) -> DeleteTraceResult:
        """Delete one imported trace record and its managed files.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Deletion result showing which managed files were removed.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        ...

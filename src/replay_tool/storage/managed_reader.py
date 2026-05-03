from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from replay_tool.domain import BusType, Frame
from replay_tool.storage.asc import AscTraceReader
from replay_tool.storage.binary_cache import BINARY_CACHE_SUFFIX, iter_binary_frame_cache


JSON_CACHE_SUFFIX = ".frames.json"


class ManagedTraceReader:
    """TraceReader that dispatches between raw ASC files and binary frame caches.

    This reader is the storage layer's default path-based reader. It knows
    which trace formats are currently supported by the managed library, but it
    does not own SQLite metadata, imports, or cache index maintenance.
    """

    def __init__(self) -> None:
        self.asc_reader = AscTraceReader()

    def read(self, path: str) -> list[Frame]:
        """Read frames from a raw ASC trace or managed binary frame cache.

        Args:
            path: Path to an ASC trace or binary frame cache.

        Returns:
            Parsed replay frames.
        """
        return list(self.iter(path))

    def iter(
        self,
        path: str,
        *,
        source_filters: set[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate frames from a raw ASC trace or managed binary frame cache.

        Args:
            path: Path to an ASC trace or binary frame cache.
            source_filters: Optional normalized `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Yields:
            Parsed replay frames matching the requested filters.

        Raises:
            ValueError: If a legacy JSON cache or unsupported trace path is
                requested.
        """
        trace_path = Path(path)
        if trace_path.name.endswith(BINARY_CACHE_SUFFIX):
            yield from iter_binary_frame_cache(
                trace_path,
                source_filters=source_filters,
                start_ns=start_ns,
                end_ns=end_ns,
            )
            return
        if trace_path.name.endswith(JSON_CACHE_SUFFIX) or trace_path.suffix.lower() == ".json":
            raise ValueError("JSON trace caches are unsupported; re-import the trace to create a binary cache.")
        if trace_path.suffix.lower() != ".asc":
            raise ValueError(f"Unsupported trace format: {trace_path.suffix}")
        for frame in self.asc_reader.iter(str(trace_path)):
            if source_filters is not None and (frame.channel, frame.bus) not in source_filters:
                continue
            if start_ns is not None and frame.ts_ns < int(start_ns):
                continue
            if end_ns is not None and frame.ts_ns >= int(end_ns):
                continue
            yield frame

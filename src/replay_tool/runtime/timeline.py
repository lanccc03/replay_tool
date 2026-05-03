from __future__ import annotations

import heapq
from collections.abc import Iterator

from replay_tool.domain import Frame
from replay_tool.planning import PlannedFrameSource
from replay_tool.ports.trace_store import TraceStore


class PlannedSourceReader:
    """Open iterators for planned frame sources through trace ports."""

    def __init__(self, trace_store: TraceStore) -> None:
        self.trace_store = trace_store

    def iter_source(self, source: PlannedFrameSource) -> Iterator[Frame]:
        """Iterate cached frames for one planned source.

        Args:
            source: Planned source describing an imported trace and source filter.

        Yields:
            Cached frames from the original source channel and bus.

        Raises:
            RuntimeError: If the planned source is not backed by Trace Library.
        """
        filters = {(source.source_channel, source.bus)}
        if not source.library_trace_id:
            raise RuntimeError(
                "ReplayRuntime requires cache-backed planned frame sources; "
                f"source {source.source_id!r} has no library_trace_id."
            )
        yield from self.trace_store.iter_frames(source.library_trace_id, source_filters=filters)


class SourceFrameCursor:
    """Maintain a one-frame lookahead for one planned source."""

    def __init__(self, source: PlannedFrameSource, reader: PlannedSourceReader) -> None:
        self.source = source
        self.reader = reader
        self._iterator: Iterator[Frame] | None = None
        self._lookahead: Frame | None = None
        self._previous_ts_ns: int | None = None

    def open(self) -> None:
        """Open the source iterator and load its first matching frame."""
        self._iterator = self.reader.iter_source(self.source)
        self._lookahead = None
        self._previous_ts_ns = None
        self._load_next()

    def peek_ts_ns(self) -> int | None:
        """Return the next frame timestamp without consuming it.

        Returns:
            The next timestamp in nanoseconds, or None at end of source.
        """
        return None if self._lookahead is None else self._lookahead.ts_ns

    def pop(self) -> Frame:
        """Consume and return the next logical-channel frame.

        Returns:
            The next frame mapped onto the planned logical channel.

        Raises:
            StopIteration: If the source has no more frames.
        """
        if self._lookahead is None:
            raise StopIteration
        frame = self._lookahead
        self._load_next()
        return frame

    def close(self) -> None:
        """Close the underlying iterator when it supports generator close."""
        iterator = self._iterator
        close = getattr(iterator, "close", None)
        if callable(close):
            close()
        self._iterator = None
        self._lookahead = None

    def _load_next(self) -> None:
        iterator = self._iterator
        if iterator is None:
            self._lookahead = None
            return
        for raw_frame in iterator:
            if raw_frame.channel != self.source.source_channel or raw_frame.bus != self.source.bus:
                continue
            if self._previous_ts_ns is not None and raw_frame.ts_ns < self._previous_ts_ns:
                raise ValueError("Trace source timestamps are not monotonic; streaming replay requires ordered frames.")
            self._previous_ts_ns = raw_frame.ts_ns
            self._lookahead = raw_frame.clone(channel=self.source.logical_channel)
            return
        self._lookahead = None


class MergedTimelineCursor:
    """Merge planned source cursors and expose replay batches by timestamp."""

    def __init__(self, sources: tuple[PlannedFrameSource, ...], reader: PlannedSourceReader) -> None:
        self.sources = sources
        self.reader = reader
        self._source_cursors: list[SourceFrameCursor] = []
        self._heap: list[tuple[int, int, SourceFrameCursor]] = []
        self._sequence = 0
        self.rewind()

    def at_end(self) -> bool:
        """Return whether all source cursors are exhausted.

        Returns:
            True when no planned source has a lookahead frame.
        """
        return not self._heap

    def read_batch(self, window_ns: int) -> tuple[Frame, ...]:
        """Consume frames in the next scheduling window.

        Args:
            window_ns: Batch window width in nanoseconds.

        Returns:
            Frames due in the next window, ordered by timestamp.
        """
        if not self._heap:
            return ()
        batch: list[Frame] = []
        first_ts_ns = self._heap[0][0]
        window_end_ns = first_ts_ns + int(window_ns)
        while self._heap and self._heap[0][0] < window_end_ns:
            _ts_ns, _sequence, cursor = heapq.heappop(self._heap)
            frame = cursor.pop()
            batch.append(frame)
            next_ts_ns = cursor.peek_ts_ns()
            if next_ts_ns is not None:
                self._push(cursor, next_ts_ns)
        return tuple(batch)

    def rewind(self) -> None:
        """Return every planned source to its first frame."""
        self.close()
        self._source_cursors = []
        self._heap = []
        self._sequence = 0
        for source in self.sources:
            cursor = SourceFrameCursor(source, self.reader)
            cursor.open()
            self._source_cursors.append(cursor)
            ts_ns = cursor.peek_ts_ns()
            if ts_ns is not None:
                self._push(cursor, ts_ns)

    def close(self) -> None:
        """Close all opened source cursors."""
        for cursor in self._source_cursors:
            cursor.close()

    def _push(self, cursor: SourceFrameCursor, ts_ns: int) -> None:
        heapq.heappush(self._heap, (int(ts_ns), self._sequence, cursor))
        self._sequence += 1

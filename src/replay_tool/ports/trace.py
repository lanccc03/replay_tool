from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Protocol

from replay_tool.domain import BusType, Frame


class TraceReader(Protocol):
    def read(self, path: str) -> list[Frame]:
        """Read replay frames from a trace path.

        Args:
            path: Filesystem path to a supported trace file.

        Returns:
            Frames ordered by timestamp.
        """
        ...

    def iter(
        self,
        path: str,
        *,
        source_filters: Iterable[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate replay frames from a trace path.

        Args:
            path: Filesystem path to a supported trace or cache file.
            source_filters: Optional `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Yields:
            Frames ordered by timestamp.
        """
        ...

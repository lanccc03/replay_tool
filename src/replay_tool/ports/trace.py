from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from replay_tool.domain import BusType, Frame


class TraceReader(Protocol):
    """Port for reading raw or cached trace frames."""

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
        source_filters: set[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate replay frames from a trace path.

        Args:
            path: Filesystem path to a supported trace or cache file.
            source_filters: Optional normalized `(source_channel, bus)` pairs to include.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Yields:
            Frames ordered by timestamp.
        """
        ...

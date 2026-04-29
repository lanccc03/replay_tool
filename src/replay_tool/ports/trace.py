from __future__ import annotations

from typing import Protocol

from replay_tool.domain import Frame


class TraceReader(Protocol):
    def read(self, path: str) -> list[Frame]:
        """Read replay frames from a trace path.

        Args:
            path: Filesystem path to a supported trace file.

        Returns:
            Frames ordered by timestamp.
        """
        ...

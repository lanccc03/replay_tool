from __future__ import annotations

from dataclasses import replace
import threading

from replay_tool.domain import ReplaySnapshot, ReplayState
from replay_tool.planning import ReplayPlan


class RuntimeTelemetry:
    """Maintain replay counters and immutable runtime snapshots.

    The runtime worker updates telemetry as frames are dispatched. Callers read
    snapshots through ReplayRuntime.snapshot(), so updates are guarded by a lock
    and snapshots remain immutable dataclass values.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._snapshot = ReplaySnapshot()
        self._errors: list[str] = []
        self._sent_frames = 0
        self._skipped_frames = 0
        self._completed_loops = 0

    def configure(self, plan: ReplayPlan) -> None:
        """Reset counters for a newly configured replay plan.

        Args:
            plan: Executable replay plan to report in snapshots.
        """
        with self._lock:
            self._errors = []
            self._sent_frames = 0
            self._skipped_frames = 0
            self._completed_loops = 0
            self._snapshot = ReplaySnapshot(
                total_ts_ns=plan.total_ts_ns,
                timeline_index=0,
                timeline_size=len(plan.frames),
            )

    def snapshot(self) -> ReplaySnapshot:
        """Return the latest immutable replay snapshot.

        Returns:
            Current replay state, counters, timestamps, and error messages.
        """
        with self._lock:
            return self._snapshot

    def set_state(self, state: ReplayState) -> None:
        """Update only the replay state in the snapshot.

        Args:
            state: New runtime state.
        """
        with self._lock:
            self._snapshot = replace(self._snapshot, state=state)

    def record_dispatch(
        self,
        *,
        current_ts_ns: int,
        sent_frames: int,
        skipped_frames: int,
        timeline_index: int,
    ) -> None:
        """Record the result of dispatching one frame batch.

        Args:
            current_ts_ns: Logical timestamp of the latest dispatched frame.
            sent_frames: Number of frames accepted by devices.
            skipped_frames: Number of frames not accepted by devices.
            timeline_index: Cursor position after the batch was consumed.
        """
        with self._lock:
            self._sent_frames += max(int(sent_frames), 0)
            self._skipped_frames += max(int(skipped_frames), 0)
            self._snapshot = replace(
                self._snapshot,
                current_ts_ns=int(current_ts_ns),
                timeline_index=int(timeline_index),
                sent_frames=self._sent_frames,
                skipped_frames=self._skipped_frames,
                errors=tuple(self._errors),
                completed_loops=self._completed_loops,
            )

    def record_loop_restart(self, completed_loops: int) -> None:
        """Record that loop playback returned to the start.

        Args:
            completed_loops: Number of completed loops after the restart.
        """
        with self._lock:
            self._completed_loops = int(completed_loops)
            self._snapshot = replace(
                self._snapshot,
                current_ts_ns=0,
                timeline_index=0,
                completed_loops=self._completed_loops,
            )

    def record_error(self, message: str) -> None:
        """Append an error message to future snapshots.

        Args:
            message: Human-readable runtime or cleanup error.
        """
        with self._lock:
            self._errors.append(str(message))
            self._snapshot = replace(self._snapshot, errors=tuple(self._errors))

    def finish(self, *, timeline_index: int | None = None) -> None:
        """Mark replay as stopped while preserving counters.

        Args:
            timeline_index: Optional final timeline cursor. When omitted, the
                existing cursor is kept.
        """
        with self._lock:
            index = self._snapshot.timeline_index if timeline_index is None else int(timeline_index)
            self._snapshot = replace(
                self._snapshot,
                state=ReplayState.STOPPED,
                timeline_index=index,
                sent_frames=self._sent_frames,
                skipped_frames=self._skipped_frames,
                errors=tuple(self._errors),
                completed_loops=self._completed_loops,
            )

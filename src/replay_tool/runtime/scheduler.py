from __future__ import annotations

from collections.abc import Callable

from replay_tool.domain import Frame
from replay_tool.planning import ReplayPlan
from replay_tool.runtime.timeline import MergedTimelineCursor


Clock = Callable[[], int]
FRAME_BATCH_WINDOW_NS = 2_000_000


class TimelineScheduler:
    """Track replay cursor, time base, pause/resume, and frame batches.

    A frame batch is a contiguous set of frames whose timestamps fall inside a
    2 ms window starting at the current cursor. The dispatcher can send such a
    batch grouped by device while the scheduler remains responsible for logical
    time and loop restarts.
    """

    def __init__(self, clock: Clock, *, batch_window_ns: int = FRAME_BATCH_WINDOW_NS) -> None:
        self.clock = clock
        self.batch_window_ns = int(batch_window_ns)
        self._plan: ReplayPlan | None = None
        self._cursor: MergedTimelineCursor | None = None
        self._pending_batch: tuple[Frame, ...] = ()
        self._base_perf_ns = 0
        self._pause_started_ns = 0
        self._timeline_index = 0
        self._completed_loops = 0

    def configure(self, plan: ReplayPlan, cursor: MergedTimelineCursor) -> None:
        """Load a replay plan and reset cursor state.

        Args:
            plan: Executable replay plan.
            cursor: Timeline cursor opened for the plan.
        """
        self.close()
        self._plan = plan
        self._cursor = cursor
        self._pending_batch = ()
        self._base_perf_ns = 0
        self._pause_started_ns = 0
        self._timeline_index = 0
        self._completed_loops = 0

    @property
    def timeline_index(self) -> int:
        """Return the current frame cursor index."""
        return self._timeline_index

    @property
    def completed_loops(self) -> int:
        """Return the number of completed replay loops."""
        return self._completed_loops

    def start(self) -> None:
        """Bind the replay time base to the current clock."""
        self._base_perf_ns = self.clock()

    def pause(self) -> None:
        """Remember when a pause began so paused time can be excluded."""
        self._pause_started_ns = self.clock()

    def resume(self) -> None:
        """Rebind the time base so paused duration does not count."""
        paused_duration = self.clock() - self._pause_started_ns
        self._base_perf_ns += paused_duration
        self._pause_started_ns = 0

    def at_end(self) -> bool:
        """Return True when all frames have been consumed.

        Returns:
            Whether the cursor is at or beyond the end of the plan.
        """
        cursor = self._require_cursor()
        return not self._pending_batch and cursor.at_end()

    def current_batch(self) -> tuple[Frame, ...]:
        """Return the frame batch at the current cursor.

        Returns:
            Frames in a contiguous 2 ms scheduling window, or an empty tuple at
            the end of the timeline.
        """
        if not self._pending_batch:
            self._pending_batch = self._require_cursor().read_batch(self.batch_window_ns)
        return self._pending_batch

    def target_perf_ns(self, batch: tuple[Frame, ...]) -> int:
        """Return the absolute clock target for a frame batch.

        Args:
            batch: Non-empty frame batch returned by current_batch().

        Returns:
            Absolute clock timestamp when the first frame in the batch is due.
        """
        if not batch:
            return self._base_perf_ns
        return self._base_perf_ns + batch[0].ts_ns

    def advance(self, count: int) -> int:
        """Advance the cursor after a dispatch.

        Args:
            count: Number of frames consumed.

        Returns:
            The new cursor index.
        """
        self._timeline_index += max(int(count), 0)
        self._pending_batch = ()
        return self._timeline_index

    def restart_loop(self) -> int:
        """Restart playback from the first frame for loop mode.

        Returns:
            Number of completed loops after the restart.
        """
        self._completed_loops += 1
        self._timeline_index = 0
        self._pending_batch = ()
        self._require_cursor().rewind()
        self._base_perf_ns = self.clock()
        return self._completed_loops

    def close(self) -> None:
        """Close the configured timeline cursor."""
        if self._cursor is not None:
            self._cursor.close()

    def _require_plan(self) -> ReplayPlan:
        if self._plan is None:
            raise RuntimeError("TimelineScheduler is not configured.")
        return self._plan

    def _require_cursor(self) -> MergedTimelineCursor:
        if self._cursor is None:
            raise RuntimeError("TimelineScheduler cursor is not configured.")
        return self._cursor

from __future__ import annotations

from collections.abc import Callable

from replay_tool.domain import Frame
from replay_tool.planning import ReplayPlan


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
        self._base_perf_ns = 0
        self._pause_started_ns = 0
        self._timeline_index = 0
        self._completed_loops = 0

    def configure(self, plan: ReplayPlan) -> None:
        """Load a replay plan and reset cursor state.

        Args:
            plan: Executable replay plan.
        """
        self._plan = plan
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
        plan = self._require_plan()
        return self._timeline_index >= len(plan.frames)

    def current_batch(self) -> tuple[Frame, ...]:
        """Return the frame batch at the current cursor.

        Returns:
            Frames in a contiguous 2 ms scheduling window, or an empty tuple at
            the end of the timeline.
        """
        plan = self._require_plan()
        if self._timeline_index >= len(plan.frames):
            return ()
        first = plan.frames[self._timeline_index]
        window_end_ns = first.ts_ns + self.batch_window_ns
        end_index = self._timeline_index + 1
        while end_index < len(plan.frames):
            frame = plan.frames[end_index]
            if frame.ts_ns >= window_end_ns:
                break
            end_index += 1
        return tuple(plan.frames[self._timeline_index:end_index])

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
        return self._timeline_index

    def restart_loop(self) -> int:
        """Restart playback from the first frame for loop mode.

        Returns:
            Number of completed loops after the restart.
        """
        self._completed_loops += 1
        self._timeline_index = 0
        self._base_perf_ns = self.clock()
        return self._completed_loops

    def _require_plan(self) -> ReplayPlan:
        if self._plan is None:
            raise RuntimeError("TimelineScheduler is not configured.")
        return self._plan

from __future__ import annotations

from collections.abc import Callable
import threading
import time
from typing import Optional

from replay_tool.domain import ReplaySnapshot, ReplayState
from replay_tool.planning import ReplayPlan
from replay_tool.ports.registry import DeviceRegistry
from replay_tool.ports.trace import TraceReader
from replay_tool.ports.trace_store import TraceStore
from replay_tool.runtime.device_session import ReplayDeviceSession
from replay_tool.runtime.dispatcher import FrameDispatcher
from replay_tool.runtime.scheduler import Clock, TimelineScheduler
from replay_tool.runtime.telemetry import RuntimeTelemetry
from replay_tool.runtime.timeline import MergedTimelineCursor, PlannedSourceReader


Sleeper = Callable[[float], None]


class ReplayRuntime:
    """Execute a ReplayPlan on a background worker thread.

    The public API intentionally matches the original MVP runtime while the
    implementation delegates scheduling, frame dispatch, device sessions, and
    telemetry to focused collaborators.
    """

    def __init__(
        self,
        registry: DeviceRegistry,
        *,
        clock: Clock = time.perf_counter_ns,
        sleeper: Sleeper = time.sleep,
        logger: Callable[[str], None] | None = None,
        trace_reader: TraceReader | None = None,
        trace_store: TraceStore | None = None,
    ) -> None:
        self.registry = registry
        self.clock = clock
        self.sleeper = sleeper
        self.logger = logger or (lambda _message: None)
        self.trace_reader = trace_reader
        self.trace_store = trace_store
        self._plan: Optional[ReplayPlan] = None
        self._thread: Optional[threading.Thread] = None
        self._condition = threading.Condition()
        self._stop_requested = False
        self._state = ReplayState.STOPPED
        self._scheduler = TimelineScheduler(clock)
        self._telemetry = RuntimeTelemetry()
        self._session = ReplayDeviceSession(registry)
        self._dispatcher = FrameDispatcher(self._session)

    def configure(self, plan: ReplayPlan) -> None:
        """Load a replay plan and reset runtime counters.

        Args:
            plan: Executable replay plan produced by the planner.

        Raises:
            RuntimeError: If the runtime is not stopped, or if planned frame
                sources cannot be opened by a trace reader or trace store.
        """
        if self._state != ReplayState.STOPPED:
            raise RuntimeError("Runtime must be stopped before configure().")
        self._plan = plan
        cursor = MergedTimelineCursor(
            plan.frame_sources,
            PlannedSourceReader(self.trace_reader, self.trace_store),
        )
        self._scheduler.configure(plan, cursor)
        self._session.configure(plan)
        self._telemetry.configure(plan)

    def start(self) -> None:
        """Start executing the configured replay plan on a worker thread.

        Raises:
            RuntimeError: If the runtime has not been configured.
        """
        if self._plan is None:
            raise RuntimeError("Runtime is not configured.")
        if self._state == ReplayState.RUNNING:
            return
        self._session.open_and_start()
        with self._condition:
            self._stop_requested = False
            self._scheduler.start()
            self._state = ReplayState.RUNNING
            self._telemetry.set_state(ReplayState.RUNNING)
            self._condition.notify_all()
        self.logger("Replay started.")
        self._thread = threading.Thread(target=self._run_loop, name="next-replay-runtime", daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """Pause timeline dispatch while keeping device sessions open."""
        with self._condition:
            if self._state != ReplayState.RUNNING:
                return
            self._scheduler.pause()
            self._state = ReplayState.PAUSED
            self._telemetry.set_state(ReplayState.PAUSED)
            self._condition.notify_all()
        self.logger("Replay paused.")

    def resume(self) -> None:
        """Resume a paused replay without counting paused time."""
        with self._condition:
            if self._state != ReplayState.PAUSED:
                return
            self._scheduler.resume()
            self._state = ReplayState.RUNNING
            self._telemetry.set_state(ReplayState.RUNNING)
            self._condition.notify_all()
        self.logger("Replay resumed.")

    def stop(self) -> None:
        """Stop replay execution and close any opened devices."""
        with self._condition:
            self._stop_requested = True
            self._state = ReplayState.STOPPED
            self._telemetry.finish()
            self._condition.notify_all()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._close_devices()
        self.logger("Replay stopped.")

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the replay worker to finish.

        Args:
            timeout: Maximum seconds to wait, or None to wait indefinitely.

        Returns:
            True when no worker is active or the worker finished before the
            timeout; otherwise False.
        """
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=timeout)
        return not thread.is_alive()

    def snapshot(self) -> ReplaySnapshot:
        """Return the latest immutable runtime snapshot.

        Returns:
            Current replay state, counters, timestamps, and error messages.
        """
        return self._telemetry.snapshot()

    def _run_loop(self) -> None:
        assert self._plan is not None
        try:
            while True:
                with self._condition:
                    if self._stop_requested:
                        return
                    while self._state == ReplayState.PAUSED and not self._stop_requested:
                        self._condition.wait(timeout=0.05)
                    if self._stop_requested:
                        return
                if self._scheduler.at_end():
                    if not self._plan.loop or self._plan.timeline_size == 0:
                        self._finish()
                        return
                    completed_loops = self._scheduler.restart_loop()
                    self._telemetry.record_loop_restart(completed_loops)
                    continue
                batch = self._scheduler.current_batch()
                target_ns = self._scheduler.target_perf_ns(batch)
                if self.clock() < target_ns:
                    self._sleep_until(target_ns)
                    continue
                result = self._dispatcher.dispatch(batch)
                timeline_index = self._scheduler.advance(len(batch))
                self._telemetry.record_dispatch(
                    current_ts_ns=batch[-1].ts_ns if batch else 0,
                    sent_frames=result.sent_frames,
                    skipped_frames=result.skipped_frames,
                    timeline_index=timeline_index,
                )
        except Exception as exc:  # pragma: no cover - defensive runtime reporting
            self._telemetry.record_error(str(exc))
            self.logger(f"Replay error: {exc}")
            self._finish()

    def _sleep_until(self, target_ns: int) -> None:
        while True:
            with self._condition:
                if self._stop_requested or self._state == ReplayState.PAUSED:
                    return
            now = self.clock()
            if now >= target_ns:
                return
            self.sleeper(min((target_ns - now) / 1_000_000_000, 0.002))

    def _finish(self) -> None:
        with self._condition:
            self._state = ReplayState.STOPPED
            self._telemetry.finish(timeline_index=self._scheduler.timeline_index)
            self._condition.notify_all()
        self._close_devices()
        self.logger("Replay completed.")

    def _close_devices(self) -> None:
        for error in self._session.close():
            self._telemetry.record_error(error)
        self._scheduler.close()

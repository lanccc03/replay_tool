from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from PySide6.QtCore import QTimer, Signal

from replay_tool.app import ReplaySession, ReplaySessionSummary
from replay_tool.domain import ReplaySnapshot, ReplayState
from replay_ui_qt.tasks import TaskRunner
from replay_ui_qt.view_models.base import BaseViewModel


class ReplaySessionApplication(Protocol):
    """Application methods required by the Replay Session ViewModel."""

    def start_replay_session_from_body(
        self,
        body: dict[str, Any],
        *,
        base_dir: str | Path = ".",
    ) -> ReplaySession:
        """Start a non-blocking replay session from a schema v2 body.

        Args:
            body: Scenario body to compile and start.
            base_dir: Base directory used to resolve trace references.

        Returns:
            Started app-layer replay session.
        """
        ...


class ReplaySessionViewModel(BaseViewModel):
    """Expose a non-blocking replay session to Qt views.

    The ViewModel calls only the app-layer ReplaySession API. It polls immutable
    runtime snapshots and derives UI-only states such as Completed and Failed
    without changing the runtime state model.
    """

    sessionChanged = Signal()
    snapshotChanged = Signal()
    controlsChanged = Signal()
    displayStateChanged = Signal(str)
    activeChanged = Signal(bool)

    def __init__(
        self,
        application: ReplaySessionApplication,
        task_runner: TaskRunner,
        *,
        poll_interval_ms: int = 100,
    ) -> None:
        """Initialize replay session state.

        Args:
            application: App-layer facade used to start replay sessions.
            task_runner: Shared UI task runner for blocking startup/stop work.
            poll_interval_ms: Snapshot polling interval in milliseconds.
        """
        super().__init__()
        self._application = application
        self._task_runner = task_runner
        self._start_task_name = f"replay-session-start-{id(self)}"
        self._stop_task_name = f"replay-session-stop-{id(self)}"
        self._session: ReplaySession | None = None
        self._summary: ReplaySessionSummary | None = None
        self._snapshot = ReplaySnapshot()
        self._display_state = "Stopped"
        self._active = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(int(poll_interval_ms))
        self._poll_timer.timeout.connect(self.refresh_snapshot)

    @property
    def session(self) -> ReplaySession | None:
        """Return the current app-layer session.

        Returns:
            Active or most recently completed session, or None before Run.
        """
        return self._session

    @property
    def summary(self) -> ReplaySessionSummary | None:
        """Return the current session summary.

        Returns:
            Plan summary for the current session, or None before Run.
        """
        return self._summary

    @property
    def snapshot(self) -> ReplaySnapshot:
        """Return the latest replay snapshot.

        Returns:
            Immutable snapshot last read from the session.
        """
        return self._snapshot

    @property
    def display_state(self) -> str:
        """Return the UI-derived session state.

        Returns:
            One of Stopped, Running, Paused, Completed, or Failed.
        """
        return self._display_state

    @property
    def active(self) -> bool:
        """Return whether replay should currently lock scenario editing.

        Returns:
            True while starting, running, paused, or stopping.
        """
        return self._active

    @property
    def runtime_state(self) -> str:
        """Return the runtime state label shown by the monitor.

        Returns:
            UI-derived state label.
        """
        return self._display_state

    @property
    def scenario_name(self) -> str:
        """Return the current session scenario name.

        Returns:
            Scenario name from the session summary, or an empty string.
        """
        return "" if self._summary is None else self._summary.name

    @property
    def current_ts_ns(self) -> int:
        """Return the latest replay timestamp in nanoseconds.

        Returns:
            Current logical timestamp from the snapshot.
        """
        return int(self._snapshot.current_ts_ns)

    @property
    def total_ts_ns(self) -> int:
        """Return the planned total duration in nanoseconds.

        Returns:
            Total plan duration from the snapshot.
        """
        return int(self._snapshot.total_ts_ns)

    @property
    def timeline_index(self) -> int:
        """Return the current timeline cursor index.

        Returns:
            Number of consumed timeline items.
        """
        return int(self._snapshot.timeline_index)

    @property
    def timeline_size(self) -> int:
        """Return the total timeline item count.

        Returns:
            Planned timeline size.
        """
        return int(self._snapshot.timeline_size)

    @property
    def progress_percent(self) -> float:
        """Return replay progress as a percentage.

        Returns:
            Progress between 0.0 and 100.0.
        """
        size = self.timeline_size
        if size <= 0:
            return 100.0 if self._display_state == "Completed" else 0.0
        return min(100.0, max(0.0, (self.timeline_index / size) * 100.0))

    @property
    def sent_frames(self) -> int:
        """Return the number of sent frames.

        Returns:
            Sent frame count from the latest snapshot.
        """
        return int(self._snapshot.sent_frames)

    @property
    def skipped_frames(self) -> int:
        """Return the number of skipped frames.

        Returns:
            Skipped frame count from the latest snapshot.
        """
        return int(self._snapshot.skipped_frames)

    @property
    def completed_loops(self) -> int:
        """Return the number of completed replay loops.

        Returns:
            Completed loop count from the latest snapshot.
        """
        return int(self._snapshot.completed_loops)

    @property
    def error_messages(self) -> tuple[str, ...]:
        """Return runtime error messages.

        Returns:
            Errors captured by runtime telemetry.
        """
        return tuple(self._snapshot.errors)

    @property
    def errors(self) -> int:
        """Return the number of runtime errors.

        Returns:
            Error count from the latest snapshot.
        """
        return len(self._snapshot.errors)

    @property
    def error_text(self) -> str:
        """Return all runtime errors as copyable text.

        Returns:
            Newline-separated error text.
        """
        return "\n".join(self._snapshot.errors)

    @property
    def can_pause(self) -> bool:
        """Return whether Pause can be triggered.

        Returns:
            True while the session is running and no command is busy.
        """
        return self._display_state == "Running" and not self.busy

    @property
    def can_resume(self) -> bool:
        """Return whether Resume can be triggered.

        Returns:
            True while the session is paused and no command is busy.
        """
        return self._display_state == "Paused" and not self.busy

    @property
    def can_stop(self) -> bool:
        """Return whether Stop can be triggered.

        Returns:
            True while running or paused and no command is busy.
        """
        return self._display_state in {"Running", "Paused"} and not self.busy

    def start_scenario_body(self, body: dict[str, Any], *, base_dir: str | Path = ".") -> bool:
        """Start a non-blocking replay session from a scenario draft.

        Args:
            body: Schema v2 scenario body from the Scenarios draft.
            base_dir: Base directory used for trace resolution.

        Returns:
            True when a start task was accepted.
        """
        if self.active:
            self.set_status_message("Replay session 正在运行")
            return False
        self._session = None
        self._set_summary(None)
        self._set_snapshot(ReplaySnapshot())
        self._replace_display_state("Stopped")

        def start_session() -> ReplaySession:
            return self._application.start_replay_session_from_body(dict(body), base_dir=base_dir)

        return self.run_background_task(
            self._task_runner,
            self._start_task_name,
            start_session,
            self._apply_started_session,
            start_status="Replay session 正在启动",
            failure_status="Replay session 启动失败",
            duplicate_status="Replay session 正在启动",
        )

    def pause(self) -> None:
        """Pause the active replay session."""
        session = self._session
        if session is None or not self.can_pause:
            self.set_status_message("Replay session 无法暂停")
            return
        try:
            session.pause()
        except Exception as exc:  # pragma: no cover - defensive UI command handling
            self.fail_command(exc, "Replay session 暂停失败")
            return
        self.refresh_snapshot()
        self.set_status_message("Replay session 已暂停")

    def resume(self) -> None:
        """Resume the active replay session."""
        session = self._session
        if session is None or not self.can_resume:
            self.set_status_message("Replay session 无法恢复")
            return
        try:
            session.resume()
        except Exception as exc:  # pragma: no cover - defensive UI command handling
            self.fail_command(exc, "Replay session 恢复失败")
            return
        self.refresh_snapshot()
        self.set_status_message("Replay session 已恢复")

    def stop(self) -> bool:
        """Stop the active replay session on a worker thread.

        Returns:
            True when a stop task was accepted.
        """
        session = self._session
        if session is None or not self.can_stop:
            self.set_status_message("Replay session 无法停止")
            return False

        def stop_session() -> ReplaySnapshot:
            session.stop()
            return session.snapshot()

        return self.run_background_task(
            self._task_runner,
            self._stop_task_name,
            stop_session,
            self._apply_stopped_snapshot,
            start_status="Replay session 正在停止",
            failure_status="Replay session 停止失败",
            duplicate_status="Replay session 正在停止",
        )

    def refresh_snapshot(self) -> None:
        """Poll the current replay session and update derived UI state."""
        session = self._session
        if session is None:
            return
        self._set_snapshot(session.snapshot())
        if self._display_state in {"Completed", "Failed", "Stopped"}:
            self._poll_timer.stop()

    def set_busy(self, busy: bool) -> None:
        """Set command busy state and resync active / control state.

        Args:
            busy: True when a command is running.
        """
        super().set_busy(busy)
        self._sync_active()
        self.controlsChanged.emit()

    def _apply_started_session(self, result: object) -> None:
        session = result
        if not hasattr(session, "summary") or not callable(getattr(session, "snapshot", None)):
            raise TypeError("Replay session start did not return ReplaySession.")
        self._session = session  # type: ignore[assignment]
        self._set_summary(session.summary)
        self._set_snapshot(session.snapshot())
        self._poll_timer.start()
        self.set_status_message(f"Replay session 已启动: {session.summary.name}")
        self.sessionChanged.emit()

    def _apply_stopped_snapshot(self, result: object) -> None:
        snapshot = result if isinstance(result, ReplaySnapshot) else self._session.snapshot() if self._session else ReplaySnapshot()
        self._set_snapshot(snapshot)
        self.set_status_message("Replay session 已停止")

    def _set_summary(self, summary: ReplaySessionSummary | None) -> None:
        if self._summary == summary:
            return
        self._summary = summary
        self.sessionChanged.emit()

    def _set_snapshot(self, snapshot: ReplaySnapshot) -> None:
        self._snapshot = snapshot
        self._replace_display_state(self._derive_display_state(snapshot))
        self.snapshotChanged.emit()
        self.controlsChanged.emit()

    def _derive_display_state(self, snapshot: ReplaySnapshot) -> str:
        if snapshot.errors:
            return "Failed"
        if snapshot.state == ReplayState.RUNNING:
            return "Running"
        if snapshot.state == ReplayState.PAUSED:
            return "Paused"
        session = self._session
        if session is not None and session.started:
            return "Stopped" if session.stopped_by_user else "Completed"
        return "Stopped"

    def _replace_display_state(self, state: str) -> None:
        value = str(state)
        changed = self._display_state != value
        self._display_state = value
        if changed:
            self.displayStateChanged.emit(self._display_state)
        self._sync_active()

    def _sync_active(self) -> None:
        active = self.busy or self._display_state in {"Running", "Paused"}
        if self._active == active:
            return
        self._active = active
        self.activeChanged.emit(self._active)

from __future__ import annotations

from dataclasses import dataclass

from replay_tool.domain import ReplaySnapshot
from replay_tool.planning import ReplayPlan
from replay_tool.runtime import ReplayRuntime


@dataclass(frozen=True)
class ReplaySessionSummary:
    """Small immutable description of a configured replay session."""

    name: str
    timeline_size: int
    total_ts_ns: int
    device_count: int
    channel_count: int
    loop: bool

    @classmethod
    def from_plan(cls, plan: ReplayPlan) -> "ReplaySessionSummary":
        """Build a summary from a compiled replay plan.

        Args:
            plan: Replay plan configured in the runtime.

        Returns:
            Summary values safe for UI display.
        """
        return cls(
            name=plan.name,
            timeline_size=int(plan.timeline_size),
            total_ts_ns=int(plan.total_ts_ns),
            device_count=len(plan.devices),
            channel_count=len(plan.channels),
            loop=bool(plan.loop),
        )


class ReplaySession:
    """Application-layer handle for one non-blocking replay runtime.

    UI code may keep and control this handle, but does not receive the
    underlying ReplayRuntime instance. The handle owns user-stop bookkeeping
    that the UI uses to distinguish an intentional stop from natural
    completion after the runtime returns to STOPPED.
    """

    def __init__(self, *, runtime: ReplayRuntime, plan: ReplayPlan, started: bool = False) -> None:
        """Initialize a replay session wrapper.

        Args:
            runtime: Configured runtime owned by this session.
            plan: Compiled plan used to configure the runtime.
            started: Whether the runtime was already started by the app layer.
        """
        self._runtime = runtime
        self._summary = ReplaySessionSummary.from_plan(plan)
        self._started = bool(started)
        self._stopped_by_user = False

    @property
    def summary(self) -> ReplaySessionSummary:
        """Return immutable plan-level session details.

        Returns:
            Session summary suitable for UI display.
        """
        return self._summary

    @property
    def started(self) -> bool:
        """Return whether this session has started.

        Returns:
            True after the app layer starts the runtime.
        """
        return self._started

    @property
    def stopped_by_user(self) -> bool:
        """Return whether stop() was requested through this session.

        Returns:
            True after a user-facing stop command.
        """
        return self._stopped_by_user

    def mark_started(self) -> None:
        """Mark the wrapped runtime as started."""
        self._started = True

    def pause(self) -> None:
        """Pause replay through the wrapped runtime."""
        self._runtime.pause()

    def resume(self) -> None:
        """Resume replay through the wrapped runtime."""
        self._runtime.resume()

    def stop(self) -> None:
        """Stop replay through the wrapped runtime and remember user intent."""
        self._stopped_by_user = True
        self._runtime.stop()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for the runtime worker to finish.

        Args:
            timeout: Maximum seconds to wait, or None to wait indefinitely.

        Returns:
            True if no runtime worker remains active before timeout.
        """
        return self._runtime.wait(timeout=timeout)

    def snapshot(self) -> ReplaySnapshot:
        """Return the latest runtime snapshot.

        Returns:
            Immutable runtime telemetry snapshot.
        """
        return self._runtime.snapshot()

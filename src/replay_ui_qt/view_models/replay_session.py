from __future__ import annotations

from replay_ui_qt.view_models.base import BaseViewModel


class ReplaySessionViewModel(BaseViewModel):
    """Expose first-stage replay monitor placeholder state."""

    def __init__(self) -> None:
        """Initialize a stopped replay session placeholder."""
        super().__init__()
        self._runtime_state = "STOPPED"
        self._sent_frames = 0
        self._skipped_frames = 0
        self._errors = 0

    @property
    def runtime_state(self) -> str:
        """Return the runtime state label.

        Returns:
            Runtime state shown by the monitor.
        """
        return self._runtime_state

    @property
    def sent_frames(self) -> int:
        """Return the number of sent frames.

        Returns:
            Sent frame count for the current session placeholder.
        """
        return self._sent_frames

    @property
    def skipped_frames(self) -> int:
        """Return the number of skipped frames.

        Returns:
            Skipped frame count for the current session placeholder.
        """
        return self._skipped_frames

    @property
    def errors(self) -> int:
        """Return the number of runtime errors.

        Returns:
            Error count for the current session placeholder.
        """
        return self._errors


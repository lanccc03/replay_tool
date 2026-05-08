from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class BaseViewModel(QObject):
    """Base class for Qt view models with common shell signals."""

    busyChanged = Signal(bool)
    errorChanged = Signal(str)
    statusMessageChanged = Signal(str)

    def __init__(self) -> None:
        """Initialize common ViewModel state."""
        super().__init__()
        self._busy = False
        self._error = ""
        self._status_message = ""

    @property
    def busy(self) -> bool:
        """Return whether the ViewModel is currently loading.

        Returns:
            True when a command is in progress.
        """
        return self._busy

    @property
    def error(self) -> str:
        """Return the current error message.

        Returns:
            Empty string when no error is active.
        """
        return self._error

    @property
    def status_message(self) -> str:
        """Return the current short status message.

        Returns:
            Status text suitable for the shell status bar.
        """
        return self._status_message

    def clear_error(self) -> None:
        """Clear the current error message."""
        self.set_error("")

    def set_busy(self, busy: bool) -> None:
        """Set whether the ViewModel is running a command.

        Args:
            busy: True when a command is active.
        """
        value = bool(busy)
        if self._busy == value:
            return
        self._busy = value
        self.busyChanged.emit(self._busy)

    def set_error(self, message: str) -> None:
        """Set the current error message.

        Args:
            message: Human-readable error text. Empty string clears the error.
        """
        value = str(message)
        if self._error == value:
            return
        self._error = value
        self.errorChanged.emit(self._error)

    def set_status_message(self, message: str) -> None:
        """Set the current short status message.

        Args:
            message: Status text suitable for a status bar.
        """
        value = str(message)
        if self._status_message == value:
            return
        self._status_message = value
        self.statusMessageChanged.emit(self._status_message)

    def begin_command(self, status_message: str = "") -> bool:
        """Enter a guarded command state.

        Args:
            status_message: Optional status text to show when the command
                starts.

        Returns:
            True when the command can start; False if another command is busy.
        """
        if self._busy:
            return False
        self.clear_error()
        self.set_busy(True)
        if status_message:
            self.set_status_message(status_message)
        return True

    def complete_command(self, status_message: str = "") -> None:
        """Leave command state after a successful command.

        Args:
            status_message: Optional completion status text.
        """
        if status_message:
            self.set_status_message(status_message)
        self.set_busy(False)

    def fail_command(self, error: str | Exception, status_message: str = "") -> None:
        """Leave command state after a failed command.

        Args:
            error: Error value to expose through errorChanged.
            status_message: Optional short status text. When omitted, the error
                text is reused.
        """
        message = str(error)
        self.set_error(message)
        self.set_status_message(status_message or message)
        self.set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.set_busy(busy)

    def _set_error(self, message: str) -> None:
        self.set_error(message)

    def _set_status_message(self, message: str) -> None:
        self.set_status_message(message)

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
        self._set_error("")

    def _set_busy(self, busy: bool) -> None:
        value = bool(busy)
        if self._busy == value:
            return
        self._busy = value
        self.busyChanged.emit(self._busy)

    def _set_error(self, message: str) -> None:
        value = str(message)
        if self._error == value:
            return
        self._error = value
        self.errorChanged.emit(self._error)

    def _set_status_message(self, message: str) -> None:
        value = str(message)
        if self._status_message == value:
            return
        self._status_message = value
        self.statusMessageChanged.emit(self._status_message)


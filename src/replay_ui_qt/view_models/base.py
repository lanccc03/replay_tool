from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from replay_ui_qt.tasks import TaskError, TaskRunner


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

    def run_background_task(
        self,
        runner: TaskRunner,
        task_name: str,
        function: Callable[[], object],
        on_success: Callable[[object], None],
        *,
        start_status: str = "",
        success_status: str = "",
        failure_status: str = "",
        duplicate_status: str = "",
    ) -> bool:
        """Run a blocking command through a TaskRunner.

        Args:
            runner: Shared background task runner.
            task_name: Stable task name used for duplicate guarding.
            function: Blocking callable to execute in a worker thread.
            on_success: Callback invoked on the Qt thread with the task result.
            start_status: Optional status text emitted when work starts.
            success_status: Optional status text emitted after success. Leave
                empty when `on_success` sets a result-specific status.
            failure_status: Optional short status text emitted after failure.
            duplicate_status: Optional status text when the command is already
                busy or the runner rejects a duplicate task.

        Returns:
            True when a task was accepted and started; False when duplicate
            guarding prevented a new task.
        """
        if self.busy:
            if duplicate_status:
                self.set_status_message(duplicate_status)
            return False
        if not self.begin_command(start_status):
            if duplicate_status:
                self.set_status_message(duplicate_status)
            return False

        name = str(task_name)
        state = {"failed": False, "succeeded": False}

        def cleanup() -> None:
            for signal, handler in (
                (runner.taskSucceeded, handle_success),
                (runner.taskFailed, handle_failed),
                (runner.taskFinished, handle_finished),
            ):
                try:
                    signal.disconnect(handler)
                except (RuntimeError, TypeError):
                    pass

        def handle_success(finished_name: str, result: object) -> None:
            if finished_name != name:
                return
            state["succeeded"] = True
            try:
                on_success(result)
            except Exception as exc:  # pragma: no cover - defensive UI callback handling
                state["failed"] = True
                self.fail_command(exc, failure_status)

        def handle_failed(finished_name: str, error: object) -> None:
            if finished_name != name:
                return
            state["failed"] = True
            message = error.message if isinstance(error, TaskError) else str(error)
            self.fail_command(message, failure_status)

        def handle_finished(finished_name: str) -> None:
            if finished_name != name:
                return
            if state["succeeded"] and not state["failed"] and self.busy:
                self.complete_command(success_status)
            elif self.busy:
                self.set_busy(False)
            cleanup()

        runner.taskSucceeded.connect(handle_success)
        runner.taskFailed.connect(handle_failed)
        runner.taskFinished.connect(handle_finished)
        handle = runner.start(name, function)
        if handle is None:
            cleanup()
            self.set_busy(False)
            if duplicate_status:
                self.set_status_message(duplicate_status)
            return False
        return True

    def _set_busy(self, busy: bool) -> None:
        self.set_busy(busy)

    def _set_error(self, message: str) -> None:
        self.set_error(message)

    def _set_status_message(self, message: str) -> None:
        self.set_status_message(message)

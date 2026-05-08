from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import uuid

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


@dataclass(frozen=True)
class TaskError:
    """Error payload emitted when a background UI task fails."""

    name: str
    message: str
    exception: Exception


@dataclass(frozen=True)
class TaskHandle:
    """Accepted background task descriptor returned by TaskRunner.start()."""

    name: str
    token: str


class _TaskSignals(QObject):
    """Signals owned by one background task runnable."""

    succeeded = Signal(str, object)
    failed = Signal(str, object)
    finished = Signal(str)


class _TaskRunnable(QRunnable):
    """QRunnable wrapper that executes one blocking callable."""

    def __init__(self, *, name: str, function: Callable[[], object]) -> None:
        """Initialize a runnable task.

        Args:
            name: Stable task name used for duplicate guarding.
            function: Blocking callable to execute on a worker thread.
        """
        super().__init__()
        self.name = name
        self.function = function
        self.signals = _TaskSignals()

    @Slot()
    def run(self) -> None:
        """Execute the callable and emit completion signals."""
        try:
            result = self.function()
        except Exception as exc:  # pragma: no cover - exercised through signal tests
            self.signals.failed.emit(self.name, TaskError(name=self.name, message=str(exc), exception=exc))
        else:
            self.signals.succeeded.emit(self.name, result)
        finally:
            self.signals.finished.emit(self.name)


class TaskRunner(QObject):
    """Run blocking UI commands through a shared QThreadPool.

    The runner guards duplicate task names so a ViewModel can keep one command
    disabled while it is already running. Cancellation is intentionally not part
    of the first M1 foundation; later workflows should make long commands
    idempotent or disable repeat triggers until the `finished` signal arrives.
    """

    taskStarted = Signal(str)
    taskSucceeded = Signal(str, object)
    taskFailed = Signal(str, object)
    taskFinished = Signal(str)

    def __init__(self, thread_pool: QThreadPool | None = None) -> None:
        """Initialize a task runner.

        Args:
            thread_pool: Optional thread pool for tests or custom scheduling.
        """
        super().__init__()
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._active: dict[str, _TaskRunnable] = {}
        self._tokens: dict[str, str] = {}

    def is_running(self, name: str) -> bool:
        """Return whether a task name is currently active.

        Args:
            name: Task name to inspect.

        Returns:
            True when a task with the same name is running.
        """
        return str(name) in self._active

    def start(self, name: str, function: Callable[[], object]) -> TaskHandle | None:
        """Start one background task unless a task with the same name is active.

        Args:
            name: Stable task name used for duplicate guarding.
            function: Blocking callable to run on a worker thread.

        Returns:
            Accepted task handle, or None when a task with the same name is
            already running.
        """
        task_name = str(name)
        if self.is_running(task_name):
            return None
        runnable = _TaskRunnable(name=task_name, function=function)
        token = uuid.uuid4().hex
        self._active[task_name] = runnable
        self._tokens[task_name] = token
        runnable.signals.succeeded.connect(self.taskSucceeded)
        runnable.signals.failed.connect(self.taskFailed)
        runnable.signals.finished.connect(self._on_finished)
        self.taskStarted.emit(task_name)
        self._thread_pool.start(runnable)
        return TaskHandle(name=task_name, token=token)

    def active_count(self) -> int:
        """Return the number of active tasks.

        Returns:
            Count of active task names.
        """
        return len(self._active)

    def wait_for_done(self, timeout_ms: int = 30000) -> bool:
        """Wait for all worker threads in the runner's pool to finish.

        Args:
            timeout_ms: Maximum wait in milliseconds.

        Returns:
            True if all worker threads finished before the timeout.
        """
        return bool(self._thread_pool.waitForDone(int(timeout_ms)))

    def _on_finished(self, name: str) -> None:
        task_name = str(name)
        self._active.pop(task_name, None)
        self._tokens.pop(task_name, None)
        self.taskFinished.emit(task_name)

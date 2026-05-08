from __future__ import annotations

import os
import threading
import unittest

import tests.bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication

from replay_ui_qt.tasks import TaskError, TaskRunner


class TaskRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-tasks"])

    def test_successful_task_emits_result_and_finished(self) -> None:
        pool = QThreadPool()
        runner = TaskRunner(pool)
        succeeded: list[tuple[str, object]] = []
        finished: list[str] = []
        runner.taskSucceeded.connect(lambda name, result: succeeded.append((name, result)))
        runner.taskFinished.connect(lambda name: finished.append(name))

        handle = runner.start("success", lambda: "ok")
        self.assertIsNotNone(handle)
        _wait_for(lambda: bool(finished), self._app)

        self.assertEqual([("success", "ok")], succeeded)
        self.assertEqual(["success"], finished)
        self.assertFalse(runner.is_running("success"))

    def test_failing_task_emits_task_error_and_finished(self) -> None:
        pool = QThreadPool()
        runner = TaskRunner(pool)
        failed: list[tuple[str, object]] = []
        finished: list[str] = []
        runner.taskFailed.connect(lambda name, error: failed.append((name, error)))
        runner.taskFinished.connect(lambda name: finished.append(name))

        def fail() -> object:
            raise RuntimeError("task exploded")

        handle = runner.start("failure", fail)
        self.assertIsNotNone(handle)
        _wait_for(lambda: bool(finished), self._app)

        self.assertEqual("failure", failed[0][0])
        self.assertIsInstance(failed[0][1], TaskError)
        self.assertEqual("task exploded", failed[0][1].message)
        self.assertEqual(["failure"], finished)
        self.assertFalse(runner.is_running("failure"))

    def test_duplicate_task_name_is_not_started_while_running(self) -> None:
        pool = QThreadPool()
        runner = TaskRunner(pool)
        release = threading.Event()
        started: list[str] = []
        finished: list[str] = []
        runner.taskStarted.connect(lambda name: started.append(name))
        runner.taskFinished.connect(lambda name: finished.append(name))

        def wait_for_release() -> str:
            release.wait(timeout=5)
            return "released"

        first = runner.start("same-name", wait_for_release)
        second = runner.start("same-name", lambda: "duplicate")
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(["same-name"], started)
        self.assertTrue(runner.is_running("same-name"))

        release.set()
        _wait_for(lambda: bool(finished), self._app)
        self.assertEqual(["same-name"], finished)


def _wait_for(predicate, app: QApplication, timeout_ms: int = 3000) -> None:
    loop = QEventLoop()
    poller = QTimer()
    poller.setInterval(10)
    poller.timeout.connect(lambda: loop.quit() if predicate() else None)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poller.start()
    timeout.start(timeout_ms)
    loop.exec()
    poller.stop()
    app.processEvents()
    if not predicate():
        raise AssertionError("Timed out waiting for Qt task signal.")


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import os
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from replay_tool.app import ReplayApplication
from replay_ui_qt.app_context import AppContext
from replay_ui_qt.main_window import MainWindow
from replay_ui_qt.theme import apply_theme


class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-smoke"])
        apply_theme(cls._app)

    def test_main_window_opens_with_expected_shell_parts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=tmp)
            context = AppContext(workspace=tmp, application=replay_app)
            window = MainWindow(context)
            try:
                window.show()
                self._app.processEvents()
                _wait_for(lambda: context.task_runner.active_count() == 0, self._app)

                self.assertEqual(4, window.navigation_count())
                self.assertEqual("Trace Library", window.current_page_name())
                self.assertIn("Workspace:", window.workspace_status_text())
                self.assertIn(tmp, window.workspace_status_text())
                self.assertIn("Trace", window.inspector_text())

                window.show_page("Settings")
                self._app.processEvents()
                self.assertEqual("Trace Library", window.current_page_name())
                self.assertIn("Trace", window.inspector_text())
            finally:
                window.close()
                self._app.processEvents()

    def test_content_panel_frame_wraps_stacked_widget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=tmp)
            context = AppContext(workspace=tmp, application=replay_app)
            window = MainWindow(context)
            try:
                window.show()
                self._app.processEvents()
                _wait_for(lambda: context.task_runner.active_count() == 0, self._app)

                from PySide6.QtWidgets import QFrame
                content = window.findChild(QFrame, "ContentPanel")
                self.assertIsNotNone(content, "ContentPanel QFrame should wrap QStackedWidget")
            finally:
                window.close()
                self._app.processEvents()


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
        raise AssertionError("Timed out waiting for UI tasks.")


if __name__ == "__main__":
    unittest.main()

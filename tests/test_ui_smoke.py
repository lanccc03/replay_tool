from __future__ import annotations

import os
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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

                self.assertEqual("next_replay Workbench", window.windowTitle())
                self.assertEqual(5, window.navigation_count())
                self.assertEqual("Trace Library", window.current_page_name())
                self.assertIn("Workspace:", window.workspace_status_text())
                self.assertIn(tmp, window.workspace_status_text())
                self.assertIn("Trace", window.inspector_text())
            finally:
                window.close()
                self._app.processEvents()


if __name__ == "__main__":
    unittest.main()

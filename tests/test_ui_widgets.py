from __future__ import annotations

import os
import unittest

import tests.bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from replay_ui_qt.widgets.dialogs import create_danger_confirmation, create_error_details_dialog
from replay_ui_qt.widgets.status_badge import StatusBadge


class UiWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-widgets"])

    def test_status_badge_keeps_text_and_semantic_state(self) -> None:
        badge = StatusBadge("Cache Ready", "ready")
        self.assertEqual("Cache Ready", badge.text())
        self.assertEqual("ready", badge.semantic)

        badge.set_status("Cache Missing", "missing")
        self.assertEqual("Cache Missing", badge.text())
        self.assertEqual("missing", badge.semantic)

        badge.set_status("Unknown", "not-a-state")
        self.assertEqual("default", badge.semantic)

    def test_danger_confirmation_mentions_action_and_object_identity(self) -> None:
        box = create_danger_confirmation(
            None,
            action="Delete Trace",
            object_label="sample.asc",
            object_id="trace-1",
        )

        self.assertEqual("Delete Trace", box.windowTitle())
        self.assertIn("Delete Trace", box.text())
        self.assertIn("sample.asc", box.informativeText())
        self.assertIn("trace-1", box.informativeText())
        self.assertEqual(QMessageBox.StandardButton.Cancel, box.standardButton(box.defaultButton()))

    def test_error_details_dialog_exposes_copyable_text(self) -> None:
        dialog = create_error_details_dialog(
            None,
            title="Trace Library 错误",
            summary="导入失败",
            detail="ASC timestamps are not monotonic.",
        )

        self.assertEqual("Trace Library 错误", dialog.windowTitle())
        self.assertIn("导入失败", dialog.detail_text())
        self.assertIn("ASC timestamps are not monotonic.", dialog.detail_text())


if __name__ == "__main__":
    unittest.main()

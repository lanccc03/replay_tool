from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout

from replay_ui_qt.app_context import UiStatus


class TopStatusBar(QFrame):
    """Top shell bar showing workspace, page, runtime state, and messages."""

    def __init__(self) -> None:
        """Create a top status bar."""
        super().__init__()
        self.setObjectName("TopStatusBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        self._workspace = QLabel()
        self._page = QLabel()
        self._runtime = QLabel()
        self._runtime.setObjectName("StatusPill")
        self._message = QLabel()
        self._message.setStyleSheet("color: #667085;")

        layout.addWidget(self._workspace, 3)
        layout.addWidget(self._page, 1)
        layout.addWidget(self._runtime)
        layout.addWidget(self._message, 2)

    def update_status(self, status: UiStatus) -> None:
        """Update labels from a UiStatus value.

        Args:
            status: Current top-level UI status.
        """
        self._workspace.setText(f"Workspace: {status.workspace}")
        self._page.setText(f"页面: {status.current_page}")
        self._runtime.setText(f"Runtime: {status.runtime_state}")
        self._message.setText(status.message)

    def workspace_text(self) -> str:
        """Return the workspace label text.

        Returns:
            Workspace label text.
        """
        return self._workspace.text()

    def page_text(self) -> str:
        """Return the page label text.

        Returns:
            Page label text.
        """
        return self._page.text()


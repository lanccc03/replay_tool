from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout


class InspectorPanel(QFrame):
    """Right-side detail panel for the selected object."""

    def __init__(self) -> None:
        """Create an inspector panel with a title and read-only body."""
        super().__init__()
        self.setObjectName("InspectorPanel")
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._title = QLabel("Inspector")
        self._title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self._title)

        self._body = QTextEdit()
        self._body.setReadOnly(True)
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        self._body.setPlaceholderText("选择一条记录查看详情")
        layout.addWidget(self._body, 1)

    def set_content(self, title: str, body: str) -> None:
        """Replace the inspector content.

        Args:
            title: Inspector heading.
            body: Plain text detail body.
        """
        self._title.setText(title)
        self._body.setPlainText(body)

    def text(self) -> str:
        """Return the current inspector body text.

        Returns:
            Plain text currently shown in the inspector.
        """
        return self._body.toPlainText()


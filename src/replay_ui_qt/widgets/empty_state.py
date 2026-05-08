from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EmptyState(QWidget):
    """Compact empty-state widget for data tables and placeholder pages."""

    def __init__(self, title: str, detail: str = "") -> None:
        """Create an empty-state panel.

        Args:
            title: Primary empty-state text.
            detail: Optional secondary explanation.
        """
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #1F2933;")
        layout.addWidget(title_label)

        if detail:
            detail_label = QLabel(detail)
            detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            detail_label.setWordWrap(True)
            detail_label.setStyleSheet("color: #667085;")
            layout.addWidget(detail_label)


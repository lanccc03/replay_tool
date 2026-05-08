from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QListWidget, QListWidgetItem, QVBoxLayout


class NavigationPanel(QFrame):
    """Left-side module navigation for the workbench shell."""

    currentChanged = Signal(int, str)

    def __init__(self) -> None:
        """Create an empty navigation panel."""
        super().__init__()
        self.setObjectName("NavigationPanel")
        self.setMinimumWidth(180)
        self.setMaximumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(10)

        title = QLabel("next_replay")
        title.setStyleSheet("font-size: 16px; font-weight: 700; padding: 4px 8px;")
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._emit_current)
        layout.addWidget(self._list, 1)

    def add_page(self, label: str, *, enabled: bool = True, tooltip: str = "") -> None:
        """Add one page to the navigation.

        Args:
            label: Page label.
            enabled: Whether the page can be selected.
            tooltip: Optional tooltip text.
        """
        item = QListWidgetItem(label)
        item.setToolTip(tooltip)
        if not enabled:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
        self._list.addItem(item)

    def set_current_index(self, index: int) -> None:
        """Select a navigation row.

        Args:
            index: Zero-based row index.
        """
        self._list.setCurrentRow(int(index))

    def count(self) -> int:
        """Return the number of navigation items.

        Returns:
            Navigation row count.
        """
        return self._list.count()

    def current_label(self) -> str:
        """Return the current navigation label.

        Returns:
            Selected page label, or an empty string.
        """
        item = self._list.currentItem()
        return item.text() if item is not None else ""

    def _emit_current(self, index: int) -> None:
        item = self._list.item(index)
        if item is not None:
            self.currentChanged.emit(index, item.text())

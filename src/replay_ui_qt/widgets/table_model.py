from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor

from replay_ui_qt.theme import COLORS, monospace_font


@dataclass(frozen=True)
class TableColumn:
    """Column definition for ObjectTableModel."""

    header: str
    value: Callable[[Any], object]
    tooltip: Callable[[Any], str] | None = None
    monospace: bool = False
    status: bool = False


class ObjectTableModel(QAbstractTableModel):
    """Simple read-only table model backed by dataclass-like rows."""

    def __init__(self, columns: tuple[TableColumn, ...]) -> None:
        """Create a table model.

        Args:
            columns: Column definitions used for display.
        """
        super().__init__()
        self._columns = columns
        self._rows: tuple[object, ...] = ()

    def set_rows(self, rows: tuple[object, ...]) -> None:
        """Replace all rows in the model.

        Args:
            rows: New immutable row tuple.
        """
        self.beginResetModel()
        self._rows = tuple(rows)
        self.endResetModel()

    def row_at(self, row: int) -> object | None:
        """Return the row object at an index.

        Args:
            row: Zero-based row number.

        Returns:
            Row object or None when out of range.
        """
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return table row count.

        Args:
            parent: Parent model index, unused for flat tables.

        Returns:
            Number of rows.
        """
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return table column count.

        Args:
            parent: Parent model index, unused for flat tables.

        Returns:
            Number of columns.
        """
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        """Return cell data for a Qt role.

        Args:
            index: Requested cell index.
            role: Qt item data role.

        Returns:
            Cell data or None when not applicable.
        """
        if not index.isValid():
            return None
        if not (0 <= index.column() < len(self._columns)):
            return None
        row = self.row_at(index.row())
        if row is None:
            return None
        column = self._columns[index.column()]
        value = column.value(row)
        if role == Qt.ItemDataRole.DisplayRole:
            return _display_value(value)
        if role == Qt.ItemDataRole.ToolTipRole:
            if column.tooltip is not None:
                return column.tooltip(row)
            return _display_value(value)
        if role == Qt.ItemDataRole.FontRole and column.monospace:
            return monospace_font()
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ForegroundRole and column.status:
            return _status_brush(str(value))
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        """Return header data for a Qt role.

        Args:
            section: Row or column index.
            orientation: Header orientation.
            role: Qt item data role.

        Returns:
            Header text or None.
        """
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._columns):
                return self._columns[section].header
        return None


def _display_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _status_brush(value: str) -> QBrush | None:
    if "Missing" in value or "未" in value:
        return QBrush(QColor(COLORS["warning"]))
    if "Ready" in value or "Online" in value:
        return QBrush(QColor(COLORS["success"]))
    if "Error" in value or "Failed" in value:
        return QBrush(QColor(COLORS["danger"]))
    return None

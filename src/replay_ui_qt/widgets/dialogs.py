from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTextEdit, QVBoxLayout, QWidget


class DangerConfirmationBox(QMessageBox):
    """QMessageBox with a stable title accessor across Qt backends.

    Some QMessageBox backends, including the offscreen backend used by tests,
    ignore the QWidget window title even after setWindowTitle() is called. This
    subclass preserves the requested title so tests and accessibility helpers
    can inspect the same action label that callers pass to the dialog factory.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a confirmation message box.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._stable_window_title = ""

    def setWindowTitle(self, title: str) -> None:  # noqa: N802 - Qt API name
        """Set the dialog title and preserve it for later inspection.

        Args:
            title: Human-readable dialog title.
        """
        self._stable_window_title = str(title)
        super().setWindowTitle(self._stable_window_title)

    def windowTitle(self) -> str:  # noqa: N802 - Qt API name
        """Return the title requested through setWindowTitle().

        Returns:
            Stable title text, or the Qt-provided value if no title was set.
        """
        return self._stable_window_title or super().windowTitle()


def create_danger_confirmation(
    parent: QWidget | None,
    *,
    action: str,
    object_label: str,
    object_id: str = "",
) -> QMessageBox:
    """Create a standardized confirmation dialog for dangerous actions.

    Args:
        parent: Optional parent widget.
        action: Action text, such as "Delete Trace".
        object_label: Human-readable object name.
        object_id: Optional stable object identifier.

    Returns:
        Configured QMessageBox. Call exec() on the returned dialog to ask the
        user.
    """
    target = str(object_label)
    if object_id:
        target = f"{target} ({object_id})"
    box = DangerConfirmationBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(str(action))
    box.setText(f"确认执行 {action}？")
    box.setInformativeText(f"目标对象: {target}")
    box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
    box.setDefaultButton(QMessageBox.StandardButton.Cancel)
    return box


def confirm_dangerous_action(
    parent: QWidget | None,
    *,
    action: str,
    object_label: str,
    object_id: str = "",
) -> bool:
    """Show a dangerous-action confirmation dialog.

    Args:
        parent: Optional parent widget.
        action: Action text, such as "Delete Trace".
        object_label: Human-readable object name.
        object_id: Optional stable object identifier.

    Returns:
        True when the user confirms the action.
    """
    box = create_danger_confirmation(
        parent,
        action=action,
        object_label=object_label,
        object_id=object_id,
    )
    return box.exec() == QMessageBox.StandardButton.Ok


class ErrorDetailsDialog(QDialog):
    """Dialog showing a copyable detailed error message."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        summary: str,
        detail: str,
    ) -> None:
        """Create an error details dialog.

        Args:
            parent: Optional parent widget.
            title: Window title.
            summary: Short error summary.
            detail: Detailed copyable error text.
        """
        super().__init__(parent)
        self.setWindowTitle(str(title))
        self._summary = str(summary)
        self._detail = str(detail)

        layout = QVBoxLayout(self)
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlainText(f"{self._summary}\n\n{self._detail}".strip())
        layout.addWidget(self._text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def detail_text(self) -> str:
        """Return the copyable error text.

        Returns:
            Plain text shown in the dialog.
        """
        return self._text.toPlainText()


def create_error_details_dialog(
    parent: QWidget | None,
    *,
    title: str,
    summary: str,
    detail: str,
) -> ErrorDetailsDialog:
    """Create a copyable error details dialog.

    Args:
        parent: Optional parent widget.
        title: Window title.
        summary: Short error summary.
        detail: Detailed copyable error text.

    Returns:
        Configured error details dialog.
    """
    return ErrorDetailsDialog(parent, title=title, summary=summary, detail=detail)

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from replay_tool.app import ReplayApplication
from replay_ui_qt.tasks import TaskRunner


@dataclass(frozen=True)
class UiStatus:
    """Top-level status values shown by the Qt workbench shell."""

    workspace: str
    current_page: str
    runtime_state: str = "STOPPED"
    message: str = ""


class AppContext(QObject):
    """Share application services and shell status between Qt views.

    The context is intentionally thin: it owns the workspace path, exposes the
    app-layer facade, and reports top-level status text. Business behavior stays
    in ReplayApplication or page ViewModels.
    """

    statusChanged = Signal(object)

    def __init__(self, *, workspace: str | Path, application: ReplayApplication) -> None:
        """Initialize a UI context for one workspace.

        Args:
            workspace: Trace/project workspace used by the app layer.
            application: Application facade shared by the UI.
        """
        super().__init__()
        self.workspace = Path(workspace)
        self.application = application
        self.task_runner = TaskRunner()
        self._status = UiStatus(
            workspace=str(self.workspace),
            current_page="Trace Library",
            runtime_state="STOPPED",
            message="就绪",
        )

    @property
    def status(self) -> UiStatus:
        """Return the latest immutable shell status.

        Returns:
            Current top-level UI status.
        """
        return self._status

    def set_current_page(self, page_name: str) -> None:
        """Update the active page shown in the top status bar.

        Args:
            page_name: Human-readable page name.
        """
        self._replace_status(current_page=str(page_name))

    def set_runtime_state(self, state: str) -> None:
        """Update the runtime state shown in the top status bar.

        Args:
            state: Runtime state label.
        """
        self._replace_status(runtime_state=str(state))

    def set_status_message(self, message: str) -> None:
        """Update the transient shell status message.

        Args:
            message: Short human-readable status text.
        """
        self._replace_status(message=str(message))

    def _replace_status(
        self,
        *,
        workspace: str | None = None,
        current_page: str | None = None,
        runtime_state: str | None = None,
        message: str | None = None,
    ) -> None:
        self._status = UiStatus(
            workspace=self._status.workspace if workspace is None else workspace,
            current_page=self._status.current_page if current_page is None else current_page,
            runtime_state=self._status.runtime_state if runtime_state is None else runtime_state,
            message=self._status.message if message is None else message,
        )
        self.statusChanged.emit(self._status)

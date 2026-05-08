from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from replay_ui_qt.app_context import AppContext
from replay_ui_qt.view_models.replay_session import ReplaySessionViewModel
from replay_ui_qt.view_models.scenarios import ScenariosViewModel
from replay_ui_qt.view_models.trace_library import TraceLibraryViewModel
from replay_ui_qt.views.placeholders import DevicesView, ReplayMonitorView, SettingsView
from replay_ui_qt.views.scenarios_view import ScenariosView
from replay_ui_qt.views.trace_library_view import TraceLibraryView
from replay_ui_qt.widgets.inspector import InspectorPanel
from replay_ui_qt.widgets.navigation import NavigationPanel
from replay_ui_qt.widgets.status_bar import TopStatusBar


class MainWindow(QMainWindow):
    """Main PySide6 workbench shell for next_replay."""

    def __init__(self, context: AppContext) -> None:
        """Create the main workbench window.

        Args:
            context: Shared UI context and app-layer facade.
        """
        super().__init__()
        self._context = context
        self._pages: list[tuple[str, QWidget]] = []
        self._build_ui()
        self._context.statusChanged.connect(self._status_bar.update_status)
        self._status_bar.update_status(self._context.status)
        self._navigation.set_current_index(0)
        self.setMinimumSize(1180, 720)
        self.resize(1280, 760)

    def navigation_count(self) -> int:
        """Return the number of navigation pages.

        Returns:
            Navigation page count.
        """
        return self._navigation.count()

    def current_page_name(self) -> str:
        """Return the current page name.

        Returns:
            Current navigation label.
        """
        return self._navigation.current_label()

    def workspace_status_text(self) -> str:
        """Return the workspace text from the top status bar.

        Returns:
            Workspace label text.
        """
        return self._status_bar.workspace_text()

    def inspector_text(self) -> str:
        """Return the current inspector body text.

        Returns:
            Plain text currently shown by the inspector.
        """
        return self._inspector.text()

    def _build_ui(self) -> None:
        self.setWindowTitle("next_replay Workbench")
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self._status_bar = TopStatusBar()
        root_layout.addWidget(self._status_bar)

        body = QHBoxLayout()
        body.setSpacing(8)
        self._navigation = NavigationPanel()
        self._stack = QStackedWidget()
        self._inspector = InspectorPanel()

        body.addWidget(self._navigation)
        body.addWidget(self._stack, 1)
        body.addWidget(self._inspector)
        root_layout.addLayout(body, 1)

        self.setCentralWidget(root)
        self._create_pages()
        self._navigation.currentChanged.connect(self._show_page)

    def _create_pages(self) -> None:
        trace_view_model = TraceLibraryViewModel(self._context.application)
        trace_view_model.statusMessageChanged.connect(self._context.set_status_message)
        scenario_view_model = ScenariosViewModel(self._context.application)
        scenario_view_model.statusMessageChanged.connect(self._context.set_status_message)

        trace_view = TraceLibraryView(trace_view_model)
        scenario_view = ScenariosView(scenario_view_model)
        replay_view = ReplayMonitorView(ReplaySessionViewModel())
        devices_view = DevicesView()
        settings_view = SettingsView(self._context)

        for label, page in (
            ("Trace Library", trace_view),
            ("Scenarios", scenario_view),
            ("Replay Monitor", replay_view),
            ("Devices", devices_view),
            ("Settings", settings_view),
        ):
            page.inspectorChanged.connect(self._inspector.set_content)  # type: ignore[attr-defined]
            self._pages.append((label, page))
            self._stack.addWidget(page)
            self._navigation.add_page(label)

    def _show_page(self, index: int, label: str) -> None:
        if not (0 <= index < len(self._pages)):
            return
        self._stack.setCurrentIndex(index)
        self._context.set_current_page(label)
        page = self._pages[index][1]
        if hasattr(page, "inspector_snapshot"):
            title, body = page.inspector_snapshot()  # type: ignore[attr-defined]
            self._inspector.set_content(title, body)

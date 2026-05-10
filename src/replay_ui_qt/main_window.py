from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from replay_ui_qt.app_context import AppContext
from replay_ui_qt.view_models.devices import DevicesViewModel
from replay_ui_qt.view_models.replay_session import ReplaySessionViewModel
from replay_ui_qt.view_models.scenarios import ScenariosViewModel
from replay_ui_qt.view_models.trace_library import TraceLibraryViewModel
from replay_ui_qt.views.placeholders import DevicesView, ReplayMonitorView
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

    def show_page(self, label: str) -> None:
        """Switch the workbench to a page by navigation label.

        Args:
            label: Human-readable navigation label, such as "Devices".
        """
        self._show_page_by_label(label)

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
        self._content_panel = QFrame()
        self._content_panel.setObjectName("ContentPanel")
        content_layout = QVBoxLayout(self._content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._stack)
        self._inspector = InspectorPanel()

        for panel in (self._navigation, self._content_panel, self._inspector):
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 1)
            shadow.setColor(QColor(0, 0, 0, 30))
            panel.setGraphicsEffect(shadow)

        body.addWidget(self._navigation)
        body.addWidget(self._content_panel, 1)
        body.addWidget(self._inspector)
        root_layout.addLayout(body, 1)

        self.setCentralWidget(root)
        self._create_pages()
        self._navigation.currentChanged.connect(self._show_page)

    def _create_pages(self) -> None:
        trace_view_model = TraceLibraryViewModel(self._context.application, self._context.task_runner)
        trace_view_model.statusMessageChanged.connect(self._context.set_status_message)
        scenario_view_model = ScenariosViewModel(self._context.application, self._context.task_runner)
        scenario_view_model.statusMessageChanged.connect(self._context.set_status_message)
        replay_view_model = ReplaySessionViewModel(self._context.application, self._context.task_runner)
        replay_view_model.statusMessageChanged.connect(self._context.set_status_message)
        replay_view_model.displayStateChanged.connect(self._context.set_runtime_state)

        trace_view = TraceLibraryView(trace_view_model)
        scenario_view = ScenariosView(scenario_view_model)
        replay_view = ReplayMonitorView(replay_view_model)
        scenario_view.runRequested.connect(
            lambda body, base_dir: self._start_replay_from_scenario(replay_view_model, body, base_dir)
        )
        replay_view_model.activeChanged.connect(scenario_view.set_replay_active)
        devices_view_model = DevicesViewModel(self._context.application, self._context.task_runner)
        devices_view_model.statusMessageChanged.connect(self._context.set_status_message)
        devices_view = DevicesView(devices_view_model)

        for label, page in (
            ("Trace Library", trace_view),
            ("Scenarios", scenario_view),
            ("Replay Monitor", replay_view),
            ("Devices", devices_view),
        ):
            page.inspectorChanged.connect(  # type: ignore[attr-defined]
                lambda title, body, source=page: self._handle_inspector_changed(source, title, body)
            )
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

    def _handle_inspector_changed(self, page: QWidget, title: str, body: str) -> None:
        if self._stack.currentWidget() is page:
            self._inspector.set_content(title, body)

    def _start_replay_from_scenario(
        self,
        view_model: ReplaySessionViewModel,
        body: object,
        base_dir: str,
    ) -> None:
        if not isinstance(body, dict):
            return
        accepted = view_model.start_scenario_body(body, base_dir=base_dir)
        if accepted:
            self._show_page_by_label("Replay Monitor")

    def _show_page_by_label(self, label: str) -> None:
        for index, (page_label, _page) in enumerate(self._pages):
            if page_label == label:
                self._navigation.set_current_index(index)
                return

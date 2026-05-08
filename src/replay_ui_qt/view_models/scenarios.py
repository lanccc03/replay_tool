from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import Signal

from replay_tool.ports.project_store import ScenarioRecord
from replay_ui_qt.view_models.base import BaseViewModel


class ScenarioListApplication(Protocol):
    """Application methods required by the Scenarios ViewModel."""

    def list_scenarios(self) -> list[ScenarioRecord]:
        """List saved scenario records.

        Returns:
            Scenario records from the active workspace.
        """
        ...


@dataclass(frozen=True)
class ScenarioRow:
    """Display row for one saved scenario."""

    scenario_id: str
    name: str
    trace_count: int
    route_count: int
    updated_at: str
    base_dir: str

    @classmethod
    def from_record(cls, record: ScenarioRecord) -> "ScenarioRow":
        """Build a display row from a scenario record.

        Args:
            record: Stored scenario metadata.

        Returns:
            Row values ready for table display.
        """
        return cls(
            scenario_id=record.scenario_id,
            name=record.name,
            trace_count=int(record.trace_count),
            route_count=int(record.route_count),
            updated_at=record.updated_at,
            base_dir=record.base_dir,
        )


class ScenariosViewModel(BaseViewModel):
    """Load and expose saved scenario rows for Qt views."""

    rowsChanged = Signal()

    def __init__(self, application: ScenarioListApplication) -> None:
        """Initialize the Scenarios ViewModel.

        Args:
            application: App-layer facade used to list scenarios.
        """
        super().__init__()
        self._application = application
        self._rows: tuple[ScenarioRow, ...] = ()

    @property
    def rows(self) -> tuple[ScenarioRow, ...]:
        """Return current scenario rows.

        Returns:
            Immutable tuple of table rows.
        """
        return self._rows

    def refresh(self) -> None:
        """Reload saved scenario rows from the active workspace."""
        self._set_busy(True)
        self.clear_error()
        try:
            records = self._application.list_scenarios()
            self._rows = tuple(ScenarioRow.from_record(record) for record in records)
            self.rowsChanged.emit()
            self._set_status_message(f"Scenarios 已加载 {len(self._rows)} 条记录")
        except Exception as exc:
            self._rows = ()
            self.rowsChanged.emit()
            self._set_error(str(exc))
            self._set_status_message("Scenarios 加载失败")
        finally:
            self._set_busy(False)


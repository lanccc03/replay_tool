from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from replay_tool.domain import ReplayScenario


@dataclass(frozen=True)
class ScenarioRecord:
    """Metadata and schema body for one saved replay scenario."""

    scenario_id: str
    name: str
    base_dir: str
    body: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    trace_count: int = 0
    route_count: int = 0


class ProjectStore(Protocol):
    """Port for storing reusable schema v2 replay scenarios."""

    def save_scenario(
        self,
        scenario: ReplayScenario,
        *,
        scenario_id: str | None = None,
        base_dir: str = ".",
    ) -> ScenarioRecord:
        """Create or update one saved replay scenario.

        Args:
            scenario: Validated schema v2 scenario to persist.
            scenario_id: Optional stable scenario ID. When omitted, the store
                generates a new ID.
            base_dir: Directory used to resolve relative trace paths.

        Returns:
            Saved scenario metadata and JSON body.
        """
        ...

    def list_scenarios(self) -> list[ScenarioRecord]:
        """List saved scenarios.

        Returns:
            Saved scenario records ordered by the store implementation.
        """
        ...

    def get_scenario(self, scenario_id: str) -> ScenarioRecord | None:
        """Look up one saved scenario by ID.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            The matching scenario record, or None when unknown.
        """
        ...

    def delete_scenario(self, scenario_id: str) -> ScenarioRecord:
        """Delete one saved scenario record.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            The deleted scenario record.

        Raises:
            KeyError: If the scenario ID is unknown.
        """
        ...

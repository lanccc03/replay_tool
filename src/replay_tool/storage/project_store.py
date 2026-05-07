from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator
import uuid

from replay_tool.domain import BusType, ReplayScenario
from replay_tool.ports import ScenarioRecord


class SqliteProjectStore:
    """SQLite-backed store for reusable schema v2 replay scenarios.

    The store shares the workspace database with the Trace Library but owns only
    scenario records. Trace files, caches, and indexes remain managed by
    SqliteTraceStore.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.sqlite_path = self.root / "library.sqlite3"
        self._ensure_dirs()
        self._initialize_schema()

    def save_scenario(
        self,
        scenario: ReplayScenario,
        *,
        scenario_id: str | None = None,
        base_dir: str = ".",
    ) -> ScenarioRecord:
        """Create or update one saved scenario.

        Args:
            scenario: Validated schema v2 scenario to persist.
            scenario_id: Optional stable scenario ID. When omitted, a new UUID
                hex string is generated.
            base_dir: Directory used to resolve relative trace paths.

        Returns:
            Saved scenario metadata and JSON body.
        """
        scenario.validate()
        record_id = str(scenario_id or "").strip() or uuid.uuid4().hex
        body = _scenario_to_dict(scenario)
        now = datetime.now(timezone.utc).isoformat()
        trace_count = len(scenario.traces)
        route_count = len(scenario.routes)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_at FROM scenarios WHERE scenario_id = ?",
                (record_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO scenarios (
                        scenario_id, name, base_dir, body_json, created_at,
                        updated_at, trace_count, route_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        scenario.name,
                        str(Path(base_dir).resolve()),
                        json.dumps(body, ensure_ascii=False, sort_keys=True),
                        now,
                        now,
                        trace_count,
                        route_count,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE scenarios
                    SET name = ?, base_dir = ?, body_json = ?, updated_at = ?,
                        trace_count = ?, route_count = ?
                    WHERE scenario_id = ?
                    """,
                    (
                        scenario.name,
                        str(Path(base_dir).resolve()),
                        json.dumps(body, ensure_ascii=False, sort_keys=True),
                        now,
                        trace_count,
                        route_count,
                        record_id,
                    ),
                )
        saved = self.get_scenario(record_id)
        assert saved is not None
        return saved

    def list_scenarios(self) -> list[ScenarioRecord]:
        """List all saved scenarios.

        Returns:
            Scenario records ordered by most recent update first.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT scenario_id, name, base_dir, body_json, created_at,
                       updated_at, trace_count, route_count
                FROM scenarios
                ORDER BY updated_at DESC, scenario_id DESC
                """
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def get_scenario(self, scenario_id: str) -> ScenarioRecord | None:
        """Look up a saved scenario by ID.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            The matching record, or None when unknown.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT scenario_id, name, base_dir, body_json, created_at,
                       updated_at, trace_count, route_count
                FROM scenarios
                WHERE scenario_id = ?
                """,
                (str(scenario_id),),
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    def delete_scenario(self, scenario_id: str) -> ScenarioRecord:
        """Delete one saved scenario record.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            The deleted scenario record.

        Raises:
            KeyError: If the scenario ID is unknown.
        """
        record = self.get_scenario(scenario_id)
        if record is None:
            raise KeyError(scenario_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM scenarios WHERE scenario_id = ?", (record.scenario_id,))
        return record

    def _ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.sqlite_path)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_dir TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    trace_count INTEGER NOT NULL,
                    route_count INTEGER NOT NULL
                )
                """
            )

    def _record_from_row(self, row) -> ScenarioRecord:
        body = json.loads(row[3] or "{}")
        if not isinstance(body, dict):
            body = {}
        return ScenarioRecord(
            scenario_id=str(row[0]),
            name=str(row[1]),
            base_dir=str(row[2]),
            body=body,
            created_at=str(row[4]),
            updated_at=str(row[5]),
            trace_count=int(row[6]),
            route_count=int(row[7]),
        )


def _scenario_to_dict(scenario: ReplayScenario) -> dict[str, Any]:
    return {
        "schema_version": scenario.schema_version,
        "name": scenario.name,
        "traces": [
            {
                "id": trace.id,
                "path": trace.path,
            }
            for trace in scenario.traces
        ],
        "devices": [
            {
                "id": device.id,
                "driver": device.driver,
                "application": device.application,
                "sdk_root": device.sdk_root,
                "device_type": device.device_type,
                "device_index": device.device_index,
                "project_path": device.project_path,
                "metadata": dict(device.metadata),
            }
            for device in scenario.devices
        ],
        "sources": [
            {
                "id": source.id,
                "trace": source.trace_id,
                "channel": source.channel,
                "bus": _bus_value(source.bus),
            }
            for source in scenario.sources
        ],
        "targets": [
            {
                "id": target.id,
                "device": target.device_id,
                "physical_channel": target.physical_channel,
                "bus": _bus_value(target.config.bus),
                "nominal_baud": target.config.nominal_baud,
                "data_baud": target.config.data_baud,
                "resistance_enabled": target.config.resistance_enabled,
                "listen_only": target.config.listen_only,
                "tx_echo": target.config.tx_echo,
            }
            for target in scenario.targets
        ],
        "routes": [
            {
                "logical_channel": route.logical_channel,
                "source": route.source_id,
                "target": route.target_id,
            }
            for route in scenario.routes
        ],
        "timeline": {
            "loop": scenario.timeline.loop,
            "diagnostics": [dict(item) for item in scenario.timeline.diagnostics],
            "link_actions": [dict(item) for item in scenario.timeline.link_actions],
        },
    }


def _bus_value(bus: BusType | str) -> str:
    return bus.value if isinstance(bus, BusType) else str(bus)

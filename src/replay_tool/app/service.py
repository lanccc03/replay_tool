from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from replay_tool.adapters.mock import MockDevice
from replay_tool.adapters.tongxing import TongxingDevice
from replay_tool.domain import DeviceConfig, ReplayScenario, TraceConfig
from replay_tool.planning import ReplayPlan, ReplayPlanner
from replay_tool.ports.project_store import ProjectStore, ScenarioRecord
from replay_tool.ports.registry import DeviceRegistry
from replay_tool.ports.trace_store import DeleteTraceResult, TraceInspection, TraceRecord, TraceStore
from replay_tool.runtime import ReplayRuntime
from replay_tool.storage import BINARY_CACHE_SUFFIX, SqliteProjectStore, SqliteTraceStore


def build_default_registry() -> DeviceRegistry:
    """Build the default registry for built-in device drivers.

    Returns:
        A registry with mock and Tongxing device factories registered.
    """
    registry = DeviceRegistry()
    registry.register("mock", lambda config: MockDevice(config))
    registry.register("tongxing", lambda config: TongxingDevice(config))
    return registry


class ReplayApplication:
    """Coordinate scenario, planning, trace library, and runtime use cases."""

    def __init__(
        self,
        *,
        registry: DeviceRegistry | None = None,
        logger: Callable[[str], None] | None = None,
        workspace: str | Path | None = None,
        trace_store: TraceStore | None = None,
        project_store: ProjectStore | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.logger = logger or (lambda _message: None)
        self.workspace = Path(workspace) if workspace is not None else Path(".replay_tool")
        self.trace_store = trace_store or SqliteTraceStore(self.workspace)
        self.project_store = project_store or SqliteProjectStore(self.workspace)
        self.planner = ReplayPlanner()

    def load_scenario(self, path: str | Path) -> ReplayScenario:
        """Load a scenario JSON file.

        Args:
            path: Path to a scenario JSON document.

        Returns:
            The parsed and validated ReplayScenario.

        Raises:
            OSError: If the file cannot be read.
            json.JSONDecodeError: If the file is not valid JSON.
            ValueError: If the scenario payload is invalid.
        """
        scenario_path = Path(path)
        payload = json.loads(scenario_path.read_text(encoding="utf-8"))
        return ReplayScenario.from_dict(payload)

    def compile_plan(self, scenario_ref: str | Path) -> ReplayPlan:
        """Compile a scenario file or saved scenario ID into a replay plan.

        Args:
            scenario_ref: Path to a scenario JSON file, or a saved scenario ID.
                Existing filesystem paths take precedence over saved IDs.

        Returns:
            A replay plan with imported trace references resolved.
        """
        scenario, base_dir = self._load_scenario_reference(scenario_ref)
        scenario, trace_records = self._prepare_trace_sources(scenario, base_dir=base_dir)
        return self.planner.compile(scenario, base_dir=base_dir, trace_records=trace_records)

    def validate(self, scenario_ref: str | Path) -> ReplayPlan:
        """Validate that a scenario can be compiled.

        Args:
            scenario_ref: Path to a scenario JSON file, or a saved scenario ID.

        Returns:
            The compiled plan when validation succeeds.
        """
        return self.compile_plan(scenario_ref)

    def run(self, scenario_ref: str | Path) -> ReplayRuntime:
        """Compile and run a scenario file or saved scenario ID to completion.

        Args:
            scenario_ref: Path to a scenario JSON file, or a saved scenario ID.

        Returns:
            The runtime after execution has stopped.
        """
        plan = self.compile_plan(scenario_ref)
        runtime = ReplayRuntime(
            self.registry,
            logger=self.logger,
            trace_store=self.trace_store,
        )
        runtime.configure(plan)
        runtime.start()
        runtime.wait()
        return runtime

    def save_scenario(self, scenario_path: str | Path, *, scenario_id: str | None = None) -> ScenarioRecord:
        """Save a schema v2 scenario file into the project store.

        Args:
            scenario_path: Path to a scenario JSON file.
            scenario_id: Optional saved scenario ID. When omitted, the store
                generates a new ID.

        Returns:
            Saved scenario record.
        """
        path = Path(scenario_path)
        scenario = self.load_scenario(path)
        return self.project_store.save_scenario(
            scenario,
            scenario_id=scenario_id,
            base_dir=str(path.parent.resolve()),
        )

    def list_scenarios(self) -> list[ScenarioRecord]:
        """List saved scenarios from the project store.

        Returns:
            Saved scenario records.
        """
        return self.project_store.list_scenarios()

    def get_scenario(self, scenario_id: str) -> ScenarioRecord:
        """Return one saved scenario record.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            Saved scenario record.

        Raises:
            KeyError: If the scenario ID is unknown.
        """
        record = self.project_store.get_scenario(scenario_id)
        if record is None:
            raise KeyError(scenario_id)
        return record

    def delete_scenario(self, scenario_id: str) -> ScenarioRecord:
        """Delete one saved scenario record.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            The deleted scenario record.

        Raises:
            KeyError: If the scenario ID is unknown.
        """
        return self.project_store.delete_scenario(scenario_id)

    def import_trace(self, path: str | Path) -> TraceRecord:
        """Import a trace file into the trace library.

        Args:
            path: Path to the source trace file.

        Returns:
            Metadata for the imported trace.
        """
        return self.trace_store.import_trace(str(path))

    def list_traces(self) -> list[TraceRecord]:
        """List traces currently stored in the trace library.

        Returns:
            Trace records ordered by the trace store implementation.
        """
        return self.trace_store.list_traces()

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        """Return library summaries for one imported trace.

        Args:
            trace_id: Trace library identifier.

        Returns:
            The trace record plus source and message summaries.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        return self.trace_store.inspect_trace(trace_id)

    def rebuild_trace_cache(self, trace_id: str) -> TraceRecord:
        """Rebuild a trace library cache from its copied source file.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Updated trace record.

        Raises:
            KeyError: If the trace ID is unknown.
            FileNotFoundError: If the copied source trace is missing.
        """
        return self.trace_store.rebuild_cache(trace_id)

    def delete_trace(self, trace_id: str) -> DeleteTraceResult:
        """Delete an imported trace and its managed files.

        Args:
            trace_id: Trace library identifier.

        Returns:
            Result describing which managed files were deleted.

        Raises:
            KeyError: If the trace ID is unknown.
        """
        return self.trace_store.delete_trace(trace_id)

    def create_device(self, config: DeviceConfig):
        """Create a device adapter through the application registry.

        Args:
            config: Device configuration containing the driver name.

        Returns:
            A bus device adapter instance.

        Raises:
            ValueError: If the registry has no factory for the driver.
        """
        return self.registry.create(config)

    def _load_scenario_reference(self, scenario_ref: str | Path) -> tuple[ReplayScenario, Path]:
        raw_ref = str(scenario_ref)
        path = Path(scenario_ref)
        if path.exists():
            return self.load_scenario(path), path.parent
        record = self.project_store.get_scenario(raw_ref)
        if record is None:
            raise FileNotFoundError(path)
        return ReplayScenario.from_dict(record.body), Path(record.base_dir)

    def _prepare_trace_sources(
        self,
        scenario: ReplayScenario,
        *,
        base_dir: Path,
    ) -> tuple[ReplayScenario, dict[str, TraceRecord]]:
        resolved: list[TraceConfig] = []
        records: dict[str, TraceRecord] = {}
        for trace in scenario.traces:
            resolved_trace, record = self._resolve_trace_config(trace, base_dir=base_dir)
            resolved.append(resolved_trace)
            records[trace.id] = record
        resolved_traces = tuple(resolved)
        if resolved_traces == scenario.traces:
            return scenario, records
        return (
            ReplayScenario(
                schema_version=scenario.schema_version,
                name=scenario.name,
                traces=resolved_traces,
                devices=scenario.devices,
                sources=scenario.sources,
                targets=scenario.targets,
                routes=scenario.routes,
                timeline=scenario.timeline,
            ),
            records,
        )

    def _resolve_trace_config(self, trace: TraceConfig, *, base_dir: Path) -> tuple[TraceConfig, TraceRecord]:
        trace_path = Path(trace.path)
        candidate = trace_path if trace_path.is_absolute() else base_dir / trace_path
        if candidate.exists():
            if candidate.name.endswith(BINARY_CACHE_SUFFIX):
                record = self.trace_store.get_trace_by_cache_path(str(candidate))
                if record is None:
                    raise ValueError(f"Binary cache path is not managed by the trace library: {candidate}")
                record = self._ensure_trace_cache(record)
                return TraceConfig(id=trace.id, path=str(Path(record.cache_path).resolve())), record
            if candidate.suffix.lower() != ".asc":
                raise ValueError(f"Unsupported trace format: {candidate.suffix}")
            original_path = str(candidate.resolve())
            record = self.trace_store.get_trace_by_original_path(original_path)
            if record is None:
                record = self.trace_store.import_trace(original_path)
            else:
                record = self._ensure_trace_cache(record)
            return TraceConfig(id=trace.id, path=str(Path(record.cache_path).resolve())), record
        record = self.trace_store.get_trace(trace.path)
        if record is None and trace.id != trace.path:
            record = self.trace_store.get_trace(trace.id)
        if record is None:
            raise FileNotFoundError(candidate)
        record = self._ensure_trace_cache(record)
        return TraceConfig(id=trace.id, path=str(Path(record.cache_path).resolve())), record

    def _ensure_trace_cache(self, record: TraceRecord) -> TraceRecord:
        cache_path = Path(record.cache_path)
        if cache_path.exists():
            return record
        return self.trace_store.rebuild_cache(record.trace_id)

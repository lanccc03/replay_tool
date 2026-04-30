from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from replay_tool.adapters.mock import MockDevice
from replay_tool.adapters.tongxing import TongxingDevice
from replay_tool.domain import DeviceConfig, ReplayScenario, TraceConfig
from replay_tool.planning import ReplayPlan, ReplayPlanner
from replay_tool.ports.registry import DeviceRegistry
from replay_tool.ports.trace_store import DeleteTraceResult, TraceInspection, TraceRecord, TraceStore
from replay_tool.runtime import ReplayRuntime
from replay_tool.storage import ManagedTraceReader, SqliteTraceStore


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
    def __init__(
        self,
        *,
        registry: DeviceRegistry | None = None,
        logger: Callable[[str], None] | None = None,
        workspace: str | Path | None = None,
        trace_store: TraceStore | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.logger = logger or (lambda _message: None)
        self.workspace = Path(workspace) if workspace is not None else Path(".replay_tool")
        self.trace_reader = ManagedTraceReader()
        self.trace_store = trace_store or SqliteTraceStore(self.workspace, self.trace_reader)
        self.planner = ReplayPlanner(self.trace_reader)

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

    def compile_plan(self, scenario_path: str | Path) -> ReplayPlan:
        """Compile a scenario file into a replay plan.

        Args:
            scenario_path: Path to the scenario JSON file.

        Returns:
            A replay plan with imported trace references resolved.
        """
        path = Path(scenario_path)
        scenario = self.load_scenario(path)
        scenario = self._resolve_imported_traces(scenario, base_dir=path.parent)
        return self.planner.compile(scenario, base_dir=path.parent)

    def validate(self, scenario_path: str | Path) -> ReplayPlan:
        """Validate that a scenario can be compiled.

        Args:
            scenario_path: Path to the scenario JSON file.

        Returns:
            The compiled plan when validation succeeds.
        """
        return self.compile_plan(scenario_path)

    def run(self, scenario_path: str | Path) -> ReplayRuntime:
        """Compile and run a scenario to completion.

        Args:
            scenario_path: Path to the scenario JSON file.

        Returns:
            The runtime after execution has stopped.
        """
        plan = self.compile_plan(scenario_path)
        runtime = ReplayRuntime(self.registry, logger=self.logger)
        runtime.configure(plan)
        runtime.start()
        runtime.wait()
        return runtime

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

    def _resolve_imported_traces(self, scenario: ReplayScenario, *, base_dir: Path) -> ReplayScenario:
        resolved_traces = tuple(self._resolve_trace_config(trace, base_dir=base_dir) for trace in scenario.traces)
        if resolved_traces == scenario.traces:
            return scenario
        return ReplayScenario(
            schema_version=scenario.schema_version,
            name=scenario.name,
            traces=resolved_traces,
            devices=scenario.devices,
            sources=scenario.sources,
            targets=scenario.targets,
            routes=scenario.routes,
            timeline=scenario.timeline,
        )

    def _resolve_trace_config(self, trace: TraceConfig, *, base_dir: Path) -> TraceConfig:
        trace_path = Path(trace.path)
        candidate = trace_path if trace_path.is_absolute() else base_dir / trace_path
        if candidate.exists():
            return trace
        record = self.trace_store.get_trace(trace.path)
        if record is None and trace.id != trace.path:
            record = self.trace_store.get_trace(trace.id)
        if record is None:
            return trace
        return TraceConfig(id=trace.id, path=record.cache_path)

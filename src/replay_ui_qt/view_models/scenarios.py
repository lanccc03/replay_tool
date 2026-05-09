from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

from PySide6.QtCore import Signal

from replay_tool.planning import ReplayPlan
from replay_tool.ports.project_store import ScenarioRecord
from replay_tool.ports.trace_store import TraceInspection, TraceRecord
from replay_ui_qt.tasks import TaskRunner
from replay_ui_qt.view_models.base import BaseViewModel


class ScenarioListApplication(Protocol):
    """Application methods required by the Scenarios ViewModel."""

    def list_scenarios(self) -> list[ScenarioRecord]:
        """List saved scenario records.

        Returns:
            Scenario records from the active workspace.
        """
        ...

    def list_traces(self) -> list[TraceRecord]:
        """List imported trace records.

        Returns:
            Trace records from the active workspace.
        """
        ...

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        """Inspect one imported trace.

        Args:
            trace_id: Trace Library identifier.

        Returns:
            Trace metadata plus source summaries.
        """
        ...

    def get_scenario(self, scenario_id: str) -> ScenarioRecord:
        """Return one saved scenario record.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            Saved scenario record.
        """
        ...

    def validate_scenario_body(
        self,
        body: dict[str, Any],
        *,
        base_dir: str | Path = ".",
    ) -> ReplayPlan:
        """Validate and compile a schema v2 scenario body.

        Args:
            body: Parsed schema v2 scenario mapping.
            base_dir: Directory used to resolve relative trace paths.

        Returns:
            Compiled replay plan.
        """
        ...

    def save_scenario_body(
        self,
        body: dict[str, Any],
        *,
        scenario_id: str | None = None,
        base_dir: str | Path = ".",
    ) -> ScenarioRecord:
        """Save a schema v2 scenario body.

        Args:
            body: Parsed schema v2 scenario mapping.
            scenario_id: Optional saved scenario ID to update.
            base_dir: Directory used to resolve relative trace paths.

        Returns:
            Saved scenario record.
        """
        ...

    def delete_scenario(self, scenario_id: str) -> ScenarioRecord:
        """Delete one saved scenario record.

        Args:
            scenario_id: Saved scenario identifier.

        Returns:
            Deleted scenario record.
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


@dataclass(frozen=True)
class DraftTraceRow:
    """Draft row for one scenario trace reference."""

    trace_id: str
    path: str


@dataclass(frozen=True)
class DraftDeviceRow:
    """Draft row for one scenario device configuration."""

    device_id: str
    driver: str
    application: str
    sdk_root: str
    device_type: str
    device_index: int


@dataclass(frozen=True)
class DraftSourceRow:
    """Draft row for one trace source."""

    source_id: str
    trace_id: str
    channel: int
    bus: str


@dataclass(frozen=True)
class DraftTargetRow:
    """Draft row for one device target."""

    target_id: str
    device_id: str
    physical_channel: int
    bus: str
    nominal_baud: int
    data_baud: int
    resistance_enabled: bool
    listen_only: bool
    tx_echo: bool


@dataclass(frozen=True)
class DraftRouteRow:
    """Draft row for one source-to-target route mapping."""

    logical_channel: int
    source_id: str
    target_id: str
    source_label: str
    target_label: str


@dataclass(frozen=True)
class ScenarioTraceChoice:
    """Imported trace option used by the New Scenario dialog."""

    trace_id: str
    name: str
    event_count: int

    @classmethod
    def from_record(cls, record: TraceRecord) -> "ScenarioTraceChoice":
        """Build a trace choice from a Trace Library record.

        Args:
            record: Trace Library record returned by the app layer.

        Returns:
            Trace option ready for UI selection.
        """
        return cls(
            trace_id=record.trace_id,
            name=record.name,
            event_count=int(record.event_count),
        )


@dataclass(frozen=True)
class ScenarioSourceChoice:
    """Trace source option used by the New Scenario dialog."""

    trace_id: str
    source_channel: int
    bus: str
    frame_count: int

    @classmethod
    def from_summary(cls, trace_id: str, summary: object) -> "ScenarioSourceChoice":
        """Build a source choice from a trace source summary.

        Args:
            trace_id: Trace Library identifier.
            summary: Source summary returned by the app layer.

        Returns:
            Source option ready for UI selection.
        """
        return cls(
            trace_id=str(trace_id),
            source_channel=int(getattr(summary, "source_channel")),
            bus=str(getattr(getattr(summary, "bus"), "value", getattr(summary, "bus"))),
            frame_count=int(getattr(summary, "frame_count")),
        )

    @property
    def label(self) -> str:
        """Return a compact label for UI display.

        Returns:
            Source channel, bus, and frame count text.
        """
        return f"CH{self.source_channel} {self.bus} frames={self.frame_count}"


@dataclass(frozen=True)
class ScenarioSourceEndpointChoice:
    """Existing draft source endpoint option used by route editors."""

    source_id: str
    label: str
    bus: str

    @classmethod
    def from_row(cls, row: DraftSourceRow) -> "ScenarioSourceEndpointChoice":
        """Build a source endpoint choice from a draft source row.

        Args:
            row: Draft source row from the current scenario draft.

        Returns:
            Source endpoint option ready for a route source selector.
        """
        return cls(
            source_id=row.source_id,
            label=_source_label(row, row.source_id),
            bus=row.bus,
        )


@dataclass(frozen=True)
class ScenarioTargetEndpointChoice:
    """Existing draft target endpoint option used by route editors."""

    target_id: str
    label: str
    bus: str

    @classmethod
    def from_row(cls, row: DraftTargetRow) -> "ScenarioTargetEndpointChoice":
        """Build a target endpoint choice from a draft target row.

        Args:
            row: Draft target row from the current scenario draft.

        Returns:
            Target endpoint option ready for a route target selector.
        """
        return cls(
            target_id=row.target_id,
            label=_target_label(row, row.target_id),
            bus=row.bus,
        )


@dataclass(frozen=True)
class ScenarioDraftIssue:
    """Field-level issue detected in a scenario draft before app validation."""

    section: str
    row: int | None
    field: str
    message: str
    severity: str = "error"

    @property
    def location(self) -> str:
        """Return a compact section/row/field location string.

        Returns:
            Human-readable draft field location.
        """
        if self.row is None:
            return f"{self.section}.{self.field}"
        return f"{self.section}[{self.row}].{self.field}"

    @property
    def blocking(self) -> bool:
        """Return whether this issue should block Validate/Run.

        Returns:
            True for error-level issues; False for warning-level notices.
        """
        return self.severity == "error"


@dataclass(frozen=True)
class ScenarioDraft:
    """UI draft mapped from a schema v2 scenario body.

    The draft is immutable from the ViewModel's perspective. Editing commands
    replace the body with a copied mapping and rebuild display rows so the JSON
    preview, route labels, and Inspector stay in sync.
    """

    scenario_id: str
    name: str
    schema_version: int
    base_dir: str
    is_new: bool
    dirty: bool
    traces: tuple[DraftTraceRow, ...]
    devices: tuple[DraftDeviceRow, ...]
    sources: tuple[DraftSourceRow, ...]
    targets: tuple[DraftTargetRow, ...]
    routes: tuple[DraftRouteRow, ...]
    json_text: str
    body: dict[str, Any]

    @classmethod
    def from_record(
        cls,
        record: ScenarioRecord,
        *,
        dirty: bool = False,
    ) -> "ScenarioDraft":
        """Build a UI draft from a saved scenario record.

        Args:
            record: Saved scenario record from the app layer.
            dirty: Whether the draft has unsaved UI edits.

        Returns:
            Scenario draft for the editor preview.

        Raises:
            ValueError: If the saved scenario body cannot be mapped.
        """
        body = _body_mapping(record.body)
        schema_version = int(body.get("schema_version", 0))
        if schema_version != 2:
            raise ValueError("Only schema_version=2 scenarios can be previewed.")
        traces = tuple(
            DraftTraceRow(trace_id=str(item.get("id", "")), path=str(item.get("path", "")))
            for item in _body_list(body, "traces")
        )
        devices = tuple(
            DraftDeviceRow(
                device_id=str(item.get("id", "")),
                driver=str(item.get("driver", "")),
                application=str(item.get("application", "ReplayTool")),
                sdk_root=str(item.get("sdk_root", "TSMaster/Windows")),
                device_type=str(item.get("device_type", "")),
                device_index=int(item.get("device_index", 0)),
            )
            for item in _body_list(body, "devices")
        )
        sources = tuple(
            DraftSourceRow(
                source_id=str(item.get("id", "")),
                trace_id=str(item.get("trace", "")),
                channel=int(item.get("channel", 0)),
                bus=str(item.get("bus", "")),
            )
            for item in _body_list(body, "sources")
        )
        targets = tuple(
            DraftTargetRow(
                target_id=str(item.get("id", "")),
                device_id=str(item.get("device", "")),
                physical_channel=int(item.get("physical_channel", 0)),
                bus=str(item.get("bus", "")),
                nominal_baud=int(item.get("nominal_baud", 500000)),
                data_baud=int(item.get("data_baud", 2000000)),
                resistance_enabled=bool(item.get("resistance_enabled", True)),
                listen_only=bool(item.get("listen_only", False)),
                tx_echo=bool(item.get("tx_echo", False)),
            )
            for item in _body_list(body, "targets")
        )
        routes = _draft_routes(_body_list(body, "routes"), sources=sources, targets=targets)
        return cls(
            scenario_id=record.scenario_id,
            name=str(body.get("name", record.name)),
            schema_version=schema_version,
            base_dir=record.base_dir,
            is_new=False,
            dirty=dirty,
            traces=traces,
            devices=devices,
            sources=sources,
            targets=targets,
            routes=routes,
            json_text=json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True),
            body=body,
        )

    @classmethod
    def from_body(
        cls,
        body: dict[str, Any],
        *,
        scenario_id: str = "",
        base_dir: str = ".",
        is_new: bool = False,
        dirty: bool = False,
    ) -> "ScenarioDraft":
        """Build a UI draft directly from a schema v2 body.

        Args:
            body: Schema v2 scenario body.
            scenario_id: Saved scenario identifier, empty for new drafts.
            base_dir: Directory used to resolve relative trace paths.
            is_new: Whether the draft has not been saved yet.
            dirty: Whether the draft has unsaved UI edits.

        Returns:
            Scenario draft for editing and preview.
        """
        record = ScenarioRecord(
            scenario_id=scenario_id,
            name=str(body.get("name", "")),
            base_dir=str(base_dir),
            body=body,
            trace_count=len(_body_list(dict(body), "traces")),
            route_count=len(_body_list(dict(body), "routes")),
        )
        draft = cls.from_record(record, dirty=dirty)
        return cls(
            scenario_id=draft.scenario_id,
            name=draft.name,
            schema_version=draft.schema_version,
            base_dir=draft.base_dir,
            is_new=is_new,
            dirty=draft.dirty,
            traces=draft.traces,
            devices=draft.devices,
            sources=draft.sources,
            targets=draft.targets,
            routes=draft.routes,
            json_text=draft.json_text,
            body=draft.body,
        )


@dataclass(frozen=True)
class ScenarioValidationDetails:
    """Compiled plan summary for a validated scenario draft."""

    name: str
    timeline_size: int
    device_count: int
    channel_count: int
    total_ts_ns: int

    @classmethod
    def from_plan(cls, plan: ReplayPlan) -> "ScenarioValidationDetails":
        """Build validation details from a replay plan.

        Args:
            plan: Compiled replay plan returned by the app layer.

        Returns:
            Summary values ready for Inspector display.
        """
        return cls(
            name=plan.name,
            timeline_size=int(plan.timeline_size),
            device_count=len(plan.devices),
            channel_count=len(plan.channels),
            total_ts_ns=int(plan.total_ts_ns),
        )


@dataclass(frozen=True)
class ScenarioDeleteResultDetails:
    """Inspector details for one deleted scenario."""

    scenario_id: str
    name: str
    trace_count: int
    route_count: int

    @classmethod
    def from_record(cls, record: ScenarioRecord) -> "ScenarioDeleteResultDetails":
        """Build delete result details from a deleted scenario record.

        Args:
            record: Deleted scenario record returned by the app layer.

        Returns:
            Details ready for Inspector display.
        """
        return cls(
            scenario_id=record.scenario_id,
            name=record.name,
            trace_count=int(record.trace_count),
            route_count=int(record.route_count),
        )


class ScenariosViewModel(BaseViewModel):
    """Load and expose saved scenario rows for Qt views."""

    rowsChanged = Signal()
    draftChanged = Signal()
    validationChanged = Signal()
    deleteResultChanged = Signal()
    traceChoicesChanged = Signal()
    draftIssuesChanged = Signal()

    def __init__(self, application: ScenarioListApplication, task_runner: TaskRunner) -> None:
        """Initialize the Scenarios ViewModel.

        Args:
            application: App-layer facade used to list scenarios.
            task_runner: Shared UI background task runner.
        """
        super().__init__()
        self._application = application
        self._task_runner = task_runner
        self._refresh_task_name = f"scenarios-refresh-{id(self)}"
        self._load_task_name = f"scenarios-load-{id(self)}"
        self._validate_task_name = f"scenarios-validate-{id(self)}"
        self._save_task_name = f"scenarios-save-{id(self)}"
        self._delete_task_name = f"scenarios-delete-{id(self)}"
        self._trace_choices_task_name = f"scenarios-trace-choices-{id(self)}"
        self._rows: tuple[ScenarioRow, ...] = ()
        self._draft: ScenarioDraft | None = None
        self._validation: ScenarioValidationDetails | None = None
        self._delete_result: ScenarioDeleteResultDetails | None = None
        self._trace_choices: tuple[ScenarioTraceChoice, ...] = ()
        self._draft_issues: tuple[ScenarioDraftIssue, ...] = ()

    @property
    def rows(self) -> tuple[ScenarioRow, ...]:
        """Return current scenario rows.

        Returns:
            Immutable tuple of table rows.
        """
        return self._rows

    @property
    def draft(self) -> ScenarioDraft | None:
        """Return the currently loaded scenario draft.

        Returns:
            Loaded draft, or None when no scenario is open.
        """
        return self._draft

    @property
    def validation(self) -> ScenarioValidationDetails | None:
        """Return the latest validation result.

        Returns:
            Compiled plan summary, or None when no validation result is active.
        """
        return self._validation

    @property
    def delete_result(self) -> ScenarioDeleteResultDetails | None:
        """Return the latest delete result.

        Returns:
            Deleted scenario details, or None when no delete result is active.
        """
        return self._delete_result

    @property
    def trace_choices(self) -> tuple[ScenarioTraceChoice, ...]:
        """Return imported trace choices for creating a new scenario.

        Returns:
            Immutable tuple of trace options.
        """
        return self._trace_choices

    @property
    def draft_issues(self) -> tuple[ScenarioDraftIssue, ...]:
        """Return local field-level issues for the current draft.

        Returns:
            Immutable tuple of draft issue rows. Empty when there is no draft
            or no local issue is detected.
        """
        return self._draft_issues

    @property
    def source_endpoint_choices(self) -> tuple[ScenarioSourceEndpointChoice, ...]:
        """Return source endpoints available to route editors.

        Returns:
            Current draft source endpoints, or an empty tuple with no draft.
        """
        if self._draft is None:
            return ()
        return tuple(ScenarioSourceEndpointChoice.from_row(row) for row in self._draft.sources)

    @property
    def target_endpoint_choices(self) -> tuple[ScenarioTargetEndpointChoice, ...]:
        """Return target endpoints available to route editors.

        Returns:
            Current draft target endpoints, or an empty tuple with no draft.
        """
        if self._draft is None:
            return ()
        return tuple(ScenarioTargetEndpointChoice.from_row(row) for row in self._draft.targets)

    @property
    def has_blocking_issues(self) -> bool:
        """Return whether the current draft has error-level issues.

        Returns:
            True when Validate/Run should be blocked by local draft issues.
        """
        return any(issue.blocking for issue in self._draft_issues)

    def refresh(self) -> None:
        """Reload saved scenario rows from the active workspace."""
        if self.busy:
            self.set_status_message("Scenarios 正在刷新")
            return
        self._rows = ()
        self.rowsChanged.emit()
        self.run_background_task(
            self._task_runner,
            self._refresh_task_name,
            self._application.list_scenarios,
            self._apply_records,
            start_status="Scenarios 正在刷新",
            failure_status="Scenarios 加载失败",
            duplicate_status="Scenarios 正在刷新",
        )

    def load_scenario(self, scenario_id: str) -> None:
        """Load one saved scenario as a read-only UI draft.

        Args:
            scenario_id: Saved scenario identifier.
        """
        value = str(scenario_id)
        if not value:
            self.set_status_message("未选择 Scenario")
            return
        if self.busy:
            self.set_status_message("Scenarios 正在执行任务")
            return
        self.run_background_task(
            self._task_runner,
            self._load_task_name,
            lambda: self._application.get_scenario(value),
            self._apply_loaded_scenario,
            start_status=f"正在加载 Scenario: {value}",
            failure_status="Scenario 加载失败",
            duplicate_status="Scenarios 正在执行任务",
        )

    def validate_loaded_scenario(self) -> None:
        """Validate and compile the currently loaded scenario draft."""
        if self.busy:
            self.set_status_message("Scenarios 正在执行任务")
            return
        draft = self._draft
        if draft is None:
            self.set_status_message("未加载 Scenario")
            return
        self._set_delete_result(None)
        self.run_background_task(
            self._task_runner,
            self._validate_task_name,
            lambda: self._application.validate_scenario_body(draft.body, base_dir=draft.base_dir),
            self._apply_validation_result,
            start_status=f"正在校验 Scenario: {draft.name}",
            failure_status="Scenario 校验失败",
            duplicate_status="Scenarios 正在执行任务",
        )

    def save_loaded_scenario(self) -> None:
        """Save the currently loaded scenario draft back to Scenario Store."""
        if self.busy:
            self.set_status_message("Scenarios 正在执行任务")
            return
        draft = self._draft
        if draft is None:
            self.set_status_message("未加载 Scenario")
            return
        self._set_delete_result(None)

        def save_and_list() -> tuple[ScenarioRecord, list[ScenarioRecord]]:
            record = self._application.save_scenario_body(
                draft.body,
                scenario_id=None if draft.is_new else draft.scenario_id,
                base_dir=draft.base_dir,
            )
            return record, self._application.list_scenarios()

        self.run_background_task(
            self._task_runner,
            self._save_task_name,
            save_and_list,
            self._apply_save_result,
            start_status=f"正在保存 Scenario: {draft.name}",
            failure_status="Scenario 保存失败",
            duplicate_status="Scenarios 正在执行任务",
        )

    def load_trace_choices(self) -> None:
        """Load imported traces for the New Scenario dialog."""
        if self.busy:
            self.set_status_message("Scenarios 正在执行任务")
            return
        self.run_background_task(
            self._task_runner,
            self._trace_choices_task_name,
            self._application.list_traces,
            self._apply_trace_choices,
            start_status="正在读取 Trace 选项",
            failure_status="Trace 选项加载失败",
            duplicate_status="Scenarios 正在执行任务",
        )

    def source_choices_for_trace(self, trace_id: str) -> tuple[ScenarioSourceChoice, ...]:
        """Return source choices for one imported trace.

        Args:
            trace_id: Trace Library identifier.

        Returns:
            Source choices built from trace inspection summaries.

        Raises:
            KeyError: If the trace ID is unknown to the app layer.
        """
        value = str(trace_id)
        if not value:
            return ()
        inspection = self._application.inspect_trace(value)
        return tuple(ScenarioSourceChoice.from_summary(value, summary) for summary in inspection.sources)

    def create_new_scenario_from_trace(
        self,
        trace: ScenarioTraceChoice,
        source: ScenarioSourceChoice,
        *,
        name: str = "",
    ) -> None:
        """Create a new in-memory scenario draft from one trace source.

        Args:
            trace: Imported trace selected by the user.
            source: Source channel and bus selected from trace inspection.
            name: Optional scenario name. When empty, a name is derived from
                the trace file name.
        """
        scenario_name = str(name).strip() or _default_scenario_name(trace.name)
        body = _new_scenario_body(trace, source, name=scenario_name)
        self._set_draft(
            ScenarioDraft.from_body(
                body,
                scenario_id="",
                base_dir=".",
                is_new=True,
                dirty=True,
            )
        )
        self._set_validation(None)
        self._set_delete_result(None)
        self.set_status_message(f"Scenario draft 已创建: {scenario_name}")

    def rename_loaded_scenario(self, name: str) -> None:
        """Update the loaded draft's scenario name.

        Args:
            name: New scenario name.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        body["name"] = str(name)
        self._replace_draft_body(body)

    def set_timeline_loop(self, loop: bool) -> None:
        """Update the loaded draft loop setting.

        Args:
            loop: Whether the scenario timeline should loop.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        timeline = dict(body.get("timeline") if isinstance(body.get("timeline"), dict) else {})
        timeline["loop"] = bool(loop)
        body["timeline"] = timeline
        self._replace_draft_body(body)

    def set_route_logical_channel(self, index: int, value: int) -> None:
        """Update one route logical channel in the loaded draft.

        Args:
            index: Route row index.
            value: New logical channel value.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        routes = _body_list(body, "routes")
        if not _valid_index(routes, index):
            self.set_status_message("Route 不存在")
            return
        routes[int(index)]["logical_channel"] = int(value)
        body["routes"] = routes
        self._replace_draft_body(body)

    def set_route_source(self, index: int, source_id: str) -> None:
        """Update one route source reference in the loaded draft.

        Args:
            index: Route row index.
            source_id: Source endpoint ID to assign to the route.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        routes = _body_list(body, "routes")
        if not _valid_index(routes, index):
            self.set_status_message("Route 不存在")
            return
        routes[int(index)]["source"] = str(source_id)
        body["routes"] = routes
        self._replace_draft_body(body)

    def set_route_target(self, index: int, target_id: str) -> None:
        """Update one route target reference in the loaded draft.

        Args:
            index: Route row index.
            target_id: Target endpoint ID to assign to the route.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        routes = _body_list(body, "routes")
        if not _valid_index(routes, index):
            self.set_status_message("Route 不存在")
            return
        routes[int(index)]["target"] = str(target_id)
        body["routes"] = routes
        self._replace_draft_body(body)

    def set_device_driver(self, index: int, driver: str) -> None:
        """Update one device adapter driver in the loaded draft.

        Args:
            index: Device row index.
            driver: Adapter driver identifier.
        """
        self._set_device_field(index, "driver", str(driver).lower())

    def set_device_sdk_root(self, index: int, sdk_root: str) -> None:
        """Update one device SDK root in the loaded draft.

        Args:
            index: Device row index.
            sdk_root: SDK root path text.
        """
        self._set_device_field(index, "sdk_root", str(sdk_root))

    def set_device_application(self, index: int, application: str) -> None:
        """Update one device application name in the loaded draft.

        Args:
            index: Device row index.
            application: TSMaster application name.
        """
        self._set_device_field(index, "application", str(application))

    def set_device_type(self, index: int, device_type: str) -> None:
        """Update one device type in the loaded draft.

        Args:
            index: Device row index.
            device_type: Hardware device type text.
        """
        self._set_device_field(index, "device_type", str(device_type))

    def set_device_index(self, index: int, device_index: int) -> None:
        """Update one device hardware index in the loaded draft.

        Args:
            index: Device row index.
            device_index: Hardware device index.
        """
        self._set_device_field(index, "device_index", int(device_index))

    def add_device(self, *, driver: str = "tongxing") -> None:
        """Append a new device configuration to the loaded draft.

        Args:
            driver: Adapter driver identifier for the new device.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        devices = _body_list(body, "devices")
        device_id = _unique_resource_id("device0", _resource_ids(body))
        devices.append(
            {
                "id": device_id,
                "driver": str(driver).lower(),
                "application": "ReplayTool",
                "sdk_root": "TSMaster/Windows",
                "device_type": "TC1014",
                "device_index": 0,
            }
        )
        body["devices"] = devices
        self._replace_draft_body(body, status_message=f"Device 已添加: {device_id}")

    def remove_device(self, index: int) -> None:
        """Remove an unreferenced device from the loaded draft.

        Devices referenced by targets are not removed. The draft body is left
        unchanged and a warning issue is exposed for the attempted deletion.

        Args:
            index: Device row index to remove.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        devices = _body_list(body, "devices")
        if not _valid_index(devices, index):
            self.set_status_message("Device 不存在")
            return
        device_id = str(devices[int(index)].get("id", ""))
        targets = _body_list(body, "targets")
        if any(str(item.get("device", "")) == device_id for item in targets):
            self._set_action_issue(
                ScenarioDraftIssue(
                    section="devices",
                    row=int(index),
                    field="id",
                    message=f"Device is referenced by a target and cannot be removed: {device_id}",
                    severity="warning",
                ),
                status_message=f"Device 正被 Target 引用，无法删除: {device_id}",
            )
            return
        del devices[int(index)]
        body["devices"] = devices
        self._replace_draft_body(body, status_message=f"Device 已删除: {device_id}")

    def set_target_device(self, index: int, device_id: str) -> None:
        """Update one target's device reference.

        Args:
            index: Target row index.
            device_id: Device ID to assign to the target.
        """
        self._set_target_field(index, "device", str(device_id))

    def set_target_bus(self, index: int, bus: str) -> None:
        """Update one target bus type.

        Args:
            index: Target row index.
            bus: Bus type text, usually CAN or CANFD.
        """
        self._set_target_field(index, "bus", str(bus).upper())

    def set_target_physical_channel(self, index: int, value: int) -> None:
        """Update one target physical channel in the loaded draft.

        Args:
            index: Target row index.
            value: New physical channel value.
        """
        self._set_target_field(index, "physical_channel", int(value))

    def set_target_nominal_baud(self, index: int, value: int) -> None:
        """Update one target nominal baud rate.

        Args:
            index: Target row index.
            value: Nominal baud rate.
        """
        self._set_target_field(index, "nominal_baud", int(value))

    def set_target_data_baud(self, index: int, value: int) -> None:
        """Update one target CAN FD data baud rate.

        Args:
            index: Target row index.
            value: Data baud rate.
        """
        self._set_target_field(index, "data_baud", int(value))

    def set_target_resistance_enabled(self, index: int, enabled: bool) -> None:
        """Update one target termination resistance flag.

        Args:
            index: Target row index.
            enabled: Whether termination resistance is enabled.
        """
        self._set_target_field(index, "resistance_enabled", bool(enabled))

    def set_target_listen_only(self, index: int, enabled: bool) -> None:
        """Update one target listen-only flag.

        Args:
            index: Target row index.
            enabled: Whether listen-only mode is enabled.
        """
        self._set_target_field(index, "listen_only", bool(enabled))

    def set_target_tx_echo(self, index: int, enabled: bool) -> None:
        """Update one target TX echo flag.

        Args:
            index: Target row index.
            enabled: Whether TX echo is enabled.
        """
        self._set_target_field(index, "tx_echo", bool(enabled))

    def add_target(
        self,
        *,
        device_id: str = "",
        bus: str = "CANFD",
        physical_channel: int | None = None,
    ) -> None:
        """Append a new target endpoint to the loaded draft.

        Args:
            device_id: Existing device ID to attach the target to. When empty,
                the first draft device is used.
            bus: Bus type for the new target.
            physical_channel: Optional physical channel. When omitted, the
                next stable channel number for the device is used.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        if not draft.devices:
            self.set_status_message("缺少 Device，无法添加 Target")
            return
        body = _copy_body(draft.body)
        devices = _body_list(body, "devices")
        selected_device = str(device_id) or str(devices[0].get("id", ""))
        if all(str(item.get("id", "")) != selected_device for item in devices):
            self.set_status_message("Device 不存在")
            return
        channel = _next_target_physical_channel(body, selected_device) if physical_channel is None else int(physical_channel)
        bus_value = str(bus).upper()
        target_id = _unique_target_id(body, selected_device, bus_value, channel)
        targets = _body_list(body, "targets")
        targets.append(
            {
                "id": target_id,
                "device": selected_device,
                "physical_channel": channel,
                "bus": bus_value,
                "nominal_baud": 500000,
                "data_baud": 2000000,
                "resistance_enabled": True,
                "listen_only": False,
                "tx_echo": False,
            }
        )
        body["targets"] = targets
        self._replace_draft_body(body, status_message=f"Target 已添加: {target_id}")

    def remove_target(self, index: int) -> None:
        """Remove an unreferenced target from the loaded draft.

        Targets referenced by routes are not removed. The draft body is left
        unchanged and a warning issue is exposed for the attempted deletion.

        Args:
            index: Target row index to remove.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        targets = _body_list(body, "targets")
        if not _valid_index(targets, index):
            self.set_status_message("Target 不存在")
            return
        target_id = str(targets[int(index)].get("id", ""))
        routes = _body_list(body, "routes")
        if any(str(item.get("target", "")) == target_id for item in routes):
            self._set_action_issue(
                ScenarioDraftIssue(
                    section="targets",
                    row=int(index),
                    field="id",
                    message=f"Target is referenced by a route and cannot be removed: {target_id}",
                    severity="warning",
                ),
                status_message=f"Target 正被 Route 引用，无法删除: {target_id}",
            )
            return
        del targets[int(index)]
        body["targets"] = targets
        self._replace_draft_body(body, status_message=f"Target 已删除: {target_id}")

    def add_route_from_trace(
        self,
        trace: ScenarioTraceChoice,
        source: ScenarioSourceChoice,
        *,
        logical_channel: int,
        physical_channel: int | None = None,
        target_id: str = "",
    ) -> None:
        """Append a route using an imported trace source and target endpoint.

        Args:
            trace: Imported trace selected by the user.
            source: Source channel and bus selected from trace inspection.
            logical_channel: Logical replay channel for the new route.
            physical_channel: Optional mock target channel for legacy callers
                that do not provide an existing target.
            target_id: Optional existing target endpoint ID. When provided,
                Add Route uses this target instead of creating a mock target.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        _ensure_trace_resource(body, trace)
        source_id = _ensure_source_resource(body, trace, source)
        selected_target_id = str(target_id)
        if selected_target_id:
            if all(str(item.get("id", "")) != selected_target_id for item in _body_list(body, "targets")):
                self.set_status_message("Target 不存在")
                return
        else:
            _ensure_mock_device(body)
            selected_target_id = _ensure_mock_target_resource(
                body,
                bus=source.bus,
                physical_channel=int(logical_channel if physical_channel is None else physical_channel),
            )
        routes = _body_list(body, "routes")
        routes.append(
            {
                "logical_channel": int(logical_channel),
                "source": source_id,
                "target": selected_target_id,
            }
        )
        body["routes"] = routes
        self._replace_draft_body(body, status_message="Route 已添加")

    def remove_route(self, index: int) -> None:
        """Remove one route from the loaded draft.

        Removing a route does not delete trace, source, target, or device
        resources, so users do not accidentally lose reusable endpoints.

        Args:
            index: Route row index to remove.
        """
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        routes = _body_list(body, "routes")
        if not _valid_index(routes, index):
            self.set_status_message("Route 不存在")
            return
        del routes[int(index)]
        body["routes"] = routes
        self._replace_draft_body(body, status_message="Route 已删除")

    def delete_scenario(self, scenario_id: str) -> None:
        """Delete one saved scenario and refresh rows.

        Args:
            scenario_id: Saved scenario identifier.
        """
        value = str(scenario_id)
        if not value:
            self.set_status_message("未选择 Scenario")
            return
        if self.busy:
            self.set_status_message("Scenarios 正在执行任务")
            return

        def delete_and_list() -> tuple[ScenarioRecord, list[ScenarioRecord]]:
            record = self._application.delete_scenario(value)
            return record, self._application.list_scenarios()

        self.run_background_task(
            self._task_runner,
            self._delete_task_name,
            delete_and_list,
            self._apply_delete_result,
            start_status=f"正在删除 Scenario: {value}",
            failure_status="Scenario 删除失败",
            duplicate_status="Scenarios 正在执行任务",
        )

    def _apply_records(self, result: object) -> None:
        records = list(result)
        self._replace_rows(records)
        self.rowsChanged.emit()
        self.set_status_message(f"Scenarios 已加载 {len(self._rows)} 条记录")

    def _apply_loaded_scenario(self, result: object) -> None:
        draft = ScenarioDraft.from_record(result)
        self._set_draft(draft)
        self._set_validation(None)
        self._set_delete_result(None)
        self.set_status_message(f"Scenario 已加载: {draft.name}")

    def _apply_validation_result(self, result: object) -> None:
        validation = ScenarioValidationDetails.from_plan(result)
        self._set_validation(validation)
        self.set_status_message(f"Scenario 校验通过: {validation.name}")

    def _apply_save_result(self, result: object) -> None:
        record, records = result
        self._replace_rows(records)
        self._set_draft(ScenarioDraft.from_record(record))
        self._set_validation(None)
        self._set_delete_result(None)
        self.rowsChanged.emit()
        self.set_status_message(f"Scenario 已保存: {record.name}")

    def _apply_delete_result(self, result: object) -> None:
        record, records = result
        self._replace_rows(records)
        self._set_draft(None)
        self._set_validation(None)
        self._set_delete_result(ScenarioDeleteResultDetails.from_record(record))
        self.rowsChanged.emit()
        self.set_status_message(f"Scenario 已删除: {record.name}")

    def _apply_trace_choices(self, result: object) -> None:
        self._trace_choices = tuple(ScenarioTraceChoice.from_record(record) for record in result)
        self.traceChoicesChanged.emit()
        self.set_status_message(f"Trace 选项已加载 {len(self._trace_choices)} 条")

    def _replace_rows(self, records: object) -> None:
        self._rows = tuple(ScenarioRow.from_record(record) for record in records)

    def _set_draft(self, draft: ScenarioDraft | None) -> None:
        self._draft = draft
        self._draft_issues = _draft_issues_for(draft)
        self.draftChanged.emit()
        self.draftIssuesChanged.emit()

    def _set_validation(self, validation: ScenarioValidationDetails | None) -> None:
        self._validation = validation
        self.validationChanged.emit()

    def _set_delete_result(self, result: ScenarioDeleteResultDetails | None) -> None:
        self._delete_result = result
        self.deleteResultChanged.emit()

    def _require_draft_for_edit(self) -> ScenarioDraft:
        if self._draft is None:
            raise RuntimeError("No Scenario draft is loaded.")
        return self._draft

    def _can_edit_draft(self) -> bool:
        if self.busy:
            self.set_status_message("Scenarios 正在执行任务")
            return False
        if self._draft is None:
            self.set_status_message("未加载 Scenario")
            return False
        return True

    def _replace_draft_body(self, body: dict[str, Any], *, status_message: str = "Scenario draft 已修改") -> None:
        draft = self._require_draft_for_edit()
        self._set_draft(
            ScenarioDraft.from_body(
                body,
                scenario_id=draft.scenario_id,
                base_dir=draft.base_dir,
                is_new=draft.is_new,
                dirty=True,
            )
        )
        self._set_validation(None)
        self._set_delete_result(None)
        self.set_status_message(status_message)

    def _set_device_field(self, index: int, field: str, value: object) -> None:
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        devices = _body_list(body, "devices")
        if not _valid_index(devices, index):
            self.set_status_message("Device 不存在")
            return
        devices[int(index)][str(field)] = value
        body["devices"] = devices
        self._replace_draft_body(body)

    def _set_target_field(self, index: int, field: str, value: object) -> None:
        if not self._can_edit_draft():
            return
        draft = self._require_draft_for_edit()
        body = _copy_body(draft.body)
        targets = _body_list(body, "targets")
        if not _valid_index(targets, index):
            self.set_status_message("Target 不存在")
            return
        targets[int(index)][str(field)] = value
        body["targets"] = targets
        self._replace_draft_body(body)

    def _set_action_issue(self, issue: ScenarioDraftIssue, *, status_message: str) -> None:
        self._draft_issues = (*_draft_issues_for(self._draft), issue)
        self.draftIssuesChanged.emit()
        self.set_status_message(status_message)


def _body_mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Scenario body must be a mapping.")
    return dict(value)


def _body_list(body: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = body.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Scenario body field must be a list: {key}")
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"Scenario body field contains a non-object item: {key}")
        rows.append(dict(item))
    return rows


def _valid_index(rows: list[dict[str, Any]], index: int) -> bool:
    return 0 <= int(index) < len(rows)


def _draft_routes(
    route_items: list[dict[str, Any]],
    *,
    sources: tuple[DraftSourceRow, ...],
    targets: tuple[DraftTargetRow, ...],
) -> tuple[DraftRouteRow, ...]:
    sources_by_id = {source.source_id: source for source in sources}
    targets_by_id = {target.target_id: target for target in targets}
    routes: list[DraftRouteRow] = []
    for item in route_items:
        source_id = str(item.get("source", ""))
        target_id = str(item.get("target", ""))
        routes.append(
            DraftRouteRow(
                logical_channel=int(item.get("logical_channel", 0)),
                source_id=source_id,
                target_id=target_id,
                source_label=_source_label(sources_by_id.get(source_id), source_id),
                target_label=_target_label(targets_by_id.get(target_id), target_id),
            )
        )
    return tuple(routes)


def _source_label(source: DraftSourceRow | None, fallback: str) -> str:
    if source is None:
        return fallback
    return f"{source.trace_id} / CH{source.channel} {source.bus}"


def _target_label(target: DraftTargetRow | None, fallback: str) -> str:
    if target is None:
        return fallback
    return f"{target.device_id} / CH{target.physical_channel} {target.bus}"


def _copy_body(body: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(body, ensure_ascii=False))


def _default_scenario_name(trace_name: str) -> str:
    stem = Path(str(trace_name)).stem or "trace"
    return f"replay-{stem}"


def _safe_id(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "-" for character in str(value))
    parts = [part for part in normalized.split("-") if part]
    return "-".join(parts) or "item"


def _resource_ids(body: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("traces", "devices", "sources", "targets"):
        for item in _body_list(body, key):
            value = str(item.get("id", ""))
            if value:
                ids.add(value)
    return ids


def _unique_resource_id(base: str, existing: set[str]) -> str:
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _ensure_trace_resource(body: dict[str, Any], trace: ScenarioTraceChoice) -> None:
    traces = _body_list(body, "traces")
    if all(str(item.get("id", "")) != trace.trace_id for item in traces):
        traces.append({"id": trace.trace_id, "path": trace.trace_id})
    body["traces"] = traces


def _ensure_mock_device(body: dict[str, Any]) -> None:
    devices = _body_list(body, "devices")
    if all(str(item.get("id", "")) != "mock0" for item in devices):
        devices.append({"id": "mock0", "driver": "mock"})
    body["devices"] = devices


def _ensure_source_resource(
    body: dict[str, Any],
    trace: ScenarioTraceChoice,
    source: ScenarioSourceChoice,
) -> str:
    sources = _body_list(body, "sources")
    for item in sources:
        if (
            str(item.get("trace", "")) == trace.trace_id
            and int(item.get("channel", -1)) == source.source_channel
            and str(item.get("bus", "")) == source.bus
        ):
            return str(item.get("id", ""))
    bus_id = _safe_id(source.bus)
    base_id = f"{_safe_id(trace.trace_id)}-ch{source.source_channel}-{bus_id}"
    source_id = _unique_resource_id(base_id, _resource_ids(body))
    sources.append(
        {
            "id": source_id,
            "trace": trace.trace_id,
            "channel": source.source_channel,
            "bus": source.bus,
        }
    )
    body["sources"] = sources
    return source_id


def _ensure_mock_target_resource(
    body: dict[str, Any],
    *,
    bus: str,
    physical_channel: int,
) -> str:
    targets = _body_list(body, "targets")
    for item in targets:
        if (
            str(item.get("device", "")) == "mock0"
            and int(item.get("physical_channel", -1)) == int(physical_channel)
            and str(item.get("bus", "")) == str(bus)
        ):
            return str(item.get("id", ""))
    bus_id = _safe_id(str(bus))
    base_id = f"mock0-ch{int(physical_channel)}-{bus_id}"
    target_id = _unique_resource_id(base_id, _resource_ids(body))
    targets.append(
        {
            "id": target_id,
            "device": "mock0",
            "physical_channel": int(physical_channel),
            "bus": str(bus),
            "nominal_baud": 500000,
            "data_baud": 2000000,
            "resistance_enabled": True,
            "listen_only": False,
            "tx_echo": False,
        }
    )
    body["targets"] = targets
    return target_id


def _unique_target_id(body: dict[str, Any], device_id: str, bus: str, physical_channel: int) -> str:
    base_id = f"{_safe_id(device_id)}-ch{int(physical_channel)}-{_safe_id(bus)}"
    return _unique_resource_id(base_id, _resource_ids(body))


def _next_target_physical_channel(body: dict[str, Any], device_id: str) -> int:
    used = {
        int(item.get("physical_channel", -1))
        for item in _body_list(body, "targets")
        if str(item.get("device", "")) == str(device_id)
    }
    for value in range(256):
        if value not in used:
            return value
    return 255


def _duplicate_values(rows: tuple[object, ...], getter: str) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        value = str(getattr(row, getter))
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _draft_issues_for(draft: ScenarioDraft | None) -> tuple[ScenarioDraftIssue, ...]:
    if draft is None:
        return ()
    issues: list[ScenarioDraftIssue] = []
    if not draft.name.strip():
        issues.append(
            ScenarioDraftIssue(
                section="overview",
                row=None,
                field="name",
                message="Scenario name is required.",
            )
        )
    trace_ids = {row.trace_id for row in draft.traces}
    device_ids = {row.device_id for row in draft.devices}
    sources_by_id = {row.source_id: row for row in draft.sources}
    targets_by_id = {row.target_id: row for row in draft.targets}
    duplicate_device_ids = _duplicate_values(draft.devices, "device_id")
    duplicate_target_ids = _duplicate_values(draft.targets, "target_id")
    for row_index, device in enumerate(draft.devices):
        if not device.device_id:
            issues.append(
                ScenarioDraftIssue(
                    section="devices",
                    row=row_index,
                    field="id",
                    message="Device ID is required.",
                )
            )
        if device.device_id in duplicate_device_ids:
            issues.append(
                ScenarioDraftIssue(
                    section="devices",
                    row=row_index,
                    field="id",
                    message=f"Device ID must be unique: {device.device_id}",
                )
            )
        if not device.driver:
            issues.append(
                ScenarioDraftIssue(
                    section="devices",
                    row=row_index,
                    field="driver",
                    message="Device driver is required.",
                )
            )
    for row_index, target in enumerate(draft.targets):
        if not target.target_id:
            issues.append(
                ScenarioDraftIssue(
                    section="targets",
                    row=row_index,
                    field="id",
                    message="Target ID is required.",
                )
            )
        if target.target_id in duplicate_target_ids:
            issues.append(
                ScenarioDraftIssue(
                    section="targets",
                    row=row_index,
                    field="id",
                    message=f"Target ID must be unique: {target.target_id}",
                )
            )
        if target.bus not in {"CAN", "CANFD"}:
            issues.append(
                ScenarioDraftIssue(
                    section="targets",
                    row=row_index,
                    field="bus",
                    message=f"Target bus must be CAN or CANFD: {target.bus}",
                )
            )
        if target.nominal_baud <= 0:
            issues.append(
                ScenarioDraftIssue(
                    section="targets",
                    row=row_index,
                    field="nominal_baud",
                    message="Target nominal baud must be positive.",
                )
            )
        if target.data_baud <= 0:
            issues.append(
                ScenarioDraftIssue(
                    section="targets",
                    row=row_index,
                    field="data_baud",
                    message="Target data baud must be positive.",
                )
            )
    for row_index, source in enumerate(draft.sources):
        if source.trace_id not in trace_ids:
            issues.append(
                ScenarioDraftIssue(
                    section="sources",
                    row=row_index,
                    field="trace",
                    message=f"Source references unknown trace: {source.trace_id}",
                )
            )
    for row_index, target in enumerate(draft.targets):
        if target.device_id not in device_ids:
            issues.append(
                ScenarioDraftIssue(
                    section="targets",
                    row=row_index,
                    field="device",
                    message=f"Target references unknown device: {target.device_id}",
                )
            )
    if not draft.routes:
        issues.append(
            ScenarioDraftIssue(
                section="routes",
                row=None,
                field="routes",
                message="At least one route is required.",
            )
        )
    logical_channels: dict[int, int] = {}
    for row_index, route in enumerate(draft.routes):
        previous = logical_channels.get(route.logical_channel)
        if previous is not None:
            issues.append(
                ScenarioDraftIssue(
                    section="routes",
                    row=row_index,
                    field="logical_channel",
                    message=(
                        f"Logical channel {route.logical_channel} is already used "
                        f"by route {previous}."
                    ),
                )
            )
        logical_channels[route.logical_channel] = row_index
        source = sources_by_id.get(route.source_id)
        target = targets_by_id.get(route.target_id)
        if source is None:
            issues.append(
                ScenarioDraftIssue(
                    section="routes",
                    row=row_index,
                    field="source",
                    message=f"Route references unknown source: {route.source_id}",
                )
            )
        if target is None:
            issues.append(
                ScenarioDraftIssue(
                    section="routes",
                    row=row_index,
                    field="target",
                    message=f"Route references unknown target: {route.target_id}",
                )
            )
        if source is not None and target is not None and source.bus != target.bus:
            issues.append(
                ScenarioDraftIssue(
                    section="routes",
                    row=row_index,
                    field="target",
                    message=f"Route connects {source.bus} source to {target.bus} target.",
                )
            )
    return tuple(issues)


def _new_scenario_body(
    trace: ScenarioTraceChoice,
    source: ScenarioSourceChoice,
    *,
    name: str,
) -> dict[str, Any]:
    bus = source.bus
    bus_id = _safe_id(bus)
    source_id = f"{_safe_id(trace.trace_id)}-ch{source.source_channel}-{bus_id}"
    target_id = f"mock0-ch0-{bus_id}"
    return {
        "schema_version": 2,
        "name": str(name),
        "traces": [{"id": trace.trace_id, "path": trace.trace_id}],
        "devices": [{"id": "mock0", "driver": "mock"}],
        "sources": [
            {
                "id": source_id,
                "trace": trace.trace_id,
                "channel": source.source_channel,
                "bus": bus,
            }
        ],
        "targets": [
            {
                "id": target_id,
                "device": "mock0",
                "physical_channel": 0,
                "bus": bus,
                "nominal_baud": 500000,
                "data_baud": 2000000,
                "resistance_enabled": True,
                "listen_only": False,
                "tx_echo": False,
            }
        ],
        "routes": [{"logical_channel": 0, "source": source_id, "target": target_id}],
        "timeline": {"loop": False},
    }

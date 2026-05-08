from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Protocol

from PySide6.QtCore import Signal

from replay_tool.planning import ReplayPlan
from replay_tool.ports.project_store import ScenarioRecord
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


@dataclass(frozen=True)
class DraftRouteRow:
    """Draft row for one source-to-target route mapping."""

    logical_channel: int
    source_id: str
    target_id: str
    source_label: str
    target_label: str


@dataclass(frozen=True)
class ScenarioDraft:
    """Read-only UI draft mapped from a saved schema v2 scenario body."""

    scenario_id: str
    name: str
    schema_version: int
    base_dir: str
    traces: tuple[DraftTraceRow, ...]
    devices: tuple[DraftDeviceRow, ...]
    sources: tuple[DraftSourceRow, ...]
    targets: tuple[DraftTargetRow, ...]
    routes: tuple[DraftRouteRow, ...]
    json_text: str
    body: dict[str, Any]

    @classmethod
    def from_record(cls, record: ScenarioRecord) -> "ScenarioDraft":
        """Build a read-only UI draft from a saved scenario record.

        Args:
            record: Saved scenario record from the app layer.

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
            )
            for item in _body_list(body, "targets")
        )
        routes = _draft_routes(_body_list(body, "routes"), sources=sources, targets=targets)
        return cls(
            scenario_id=record.scenario_id,
            name=str(body.get("name", record.name)),
            schema_version=schema_version,
            base_dir=record.base_dir,
            traces=traces,
            devices=devices,
            sources=sources,
            targets=targets,
            routes=routes,
            json_text=json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True),
            body=body,
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
        self._rows: tuple[ScenarioRow, ...] = ()
        self._draft: ScenarioDraft | None = None
        self._validation: ScenarioValidationDetails | None = None
        self._delete_result: ScenarioDeleteResultDetails | None = None

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
                scenario_id=draft.scenario_id,
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

    def _replace_rows(self, records: object) -> None:
        self._rows = tuple(ScenarioRow.from_record(record) for record in records)

    def _set_draft(self, draft: ScenarioDraft | None) -> None:
        self._draft = draft
        self.draftChanged.emit()

    def _set_validation(self, validation: ScenarioValidationDetails | None) -> None:
        self._validation = validation
        self.validationChanged.emit()

    def _set_delete_result(self, result: ScenarioDeleteResultDetails | None) -> None:
        self._delete_result = result
        self.deleteResultChanged.emit()


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

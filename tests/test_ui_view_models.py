from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
import unittest

import tests.bootstrap  # noqa: F401
from tests.bootstrap import ROOT

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication

from replay_tool.app import DeviceEnumerationResult, ReplayApplication, ReplaySessionSummary
from replay_tool.domain import (
    BusType,
    ChannelConfig,
    DeviceCapabilities,
    DeviceConfig,
    DeviceHealth,
    DeviceInfo,
    ReplaySnapshot,
    ReplayState,
)
from replay_tool.planning import PlannedChannel, ReplayPlan
from replay_tool.ports.project_store import ScenarioRecord
from replay_tool.ports.trace_store import (
    DeleteTraceResult,
    TraceInspection,
    TraceMessageSummary,
    TraceRecord,
    TraceSourceSummary,
)
from replay_ui_qt.tasks import TaskRunner
from replay_ui_qt.view_models.base import BaseViewModel
from replay_ui_qt.view_models.devices import DevicesViewModel
from replay_ui_qt.view_models.replay_session import ReplaySessionViewModel
from replay_ui_qt.view_models.scenarios import ScenarioTraceChoice, ScenariosViewModel
from replay_ui_qt.view_models.settings import SettingsViewModel
from replay_ui_qt.view_models.trace_library import TraceLibraryViewModel


class _TraceApp:
    def __init__(
        self,
        records: list[TraceRecord] | None = None,
        error: Exception | None = None,
        release: threading.Event | None = None,
        import_record: TraceRecord | None = None,
        import_error: Exception | None = None,
        inspection: TraceInspection | None = None,
        inspect_error: Exception | None = None,
        rebuild_record: TraceRecord | None = None,
        rebuild_error: Exception | None = None,
        delete_result: DeleteTraceResult | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.release = release
        self.import_record = import_record
        self.import_error = import_error
        self.inspection = inspection
        self.inspect_error = inspect_error
        self.rebuild_record = rebuild_record
        self.rebuild_error = rebuild_error
        self.delete_result = delete_result
        self.delete_error = delete_error
        self.calls = 0
        self.import_paths: list[Path] = []
        self.inspected_ids: list[str] = []
        self.rebuilt_ids: list[str] = []
        self.deleted_ids: list[str] = []

    def list_traces(self) -> list[TraceRecord]:
        self.calls += 1
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return list(self.records)

    def import_trace(self, path: str | Path) -> TraceRecord:
        self.import_paths.append(Path(path))
        if self.import_error is not None:
            raise self.import_error
        if self.import_record is None:
            raise AssertionError("Missing import_record in fake trace app.")
        self.records = [*self.records, self.import_record]
        return self.import_record

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        self.inspected_ids.append(trace_id)
        if self.inspect_error is not None:
            raise self.inspect_error
        if self.inspection is None:
            raise AssertionError("Missing inspection in fake trace app.")
        return self.inspection

    def rebuild_trace_cache(self, trace_id: str) -> TraceRecord:
        self.rebuilt_ids.append(trace_id)
        if self.rebuild_error is not None:
            raise self.rebuild_error
        if self.rebuild_record is None:
            raise AssertionError("Missing rebuild_record in fake trace app.")
        self.records = [
            self.rebuild_record if record.trace_id == trace_id else record
            for record in self.records
        ]
        if all(record.trace_id != trace_id for record in self.records):
            self.records = [*self.records, self.rebuild_record]
        return self.rebuild_record

    def delete_trace(self, trace_id: str) -> DeleteTraceResult:
        self.deleted_ids.append(trace_id)
        if self.delete_error is not None:
            raise self.delete_error
        if self.delete_result is None:
            raise AssertionError("Missing delete_result in fake trace app.")
        self.records = [record for record in self.records if record.trace_id != trace_id]
        return self.delete_result


class _ScenarioApp:
    def __init__(
        self,
        records: list[ScenarioRecord] | None = None,
        error: Exception | None = None,
        release: threading.Event | None = None,
        load_error: Exception | None = None,
        validate_error: Exception | None = None,
        save_error: Exception | None = None,
        delete_error: Exception | None = None,
        validation_plan: ReplayPlan | None = None,
        save_record: ScenarioRecord | None = None,
        delete_record: ScenarioRecord | None = None,
        trace_records: list[TraceRecord] | None = None,
        trace_inspection: TraceInspection | None = None,
        trace_error: Exception | None = None,
        inspect_trace_error: Exception | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.release = release
        self.load_error = load_error
        self.validate_error = validate_error
        self.save_error = save_error
        self.delete_error = delete_error
        self.validation_plan = validation_plan
        self.save_record = save_record
        self.delete_record = delete_record
        self.trace_records = trace_records or []
        self.trace_inspection = trace_inspection
        self.trace_error = trace_error
        self.inspect_trace_error = inspect_trace_error
        self.calls = 0
        self.trace_calls = 0
        self.loaded_ids: list[str] = []
        self.validated_bodies: list[dict[str, object]] = []
        self.validation_base_dirs: list[Path] = []
        self.saved_bodies: list[dict[str, object]] = []
        self.saved_ids: list[str | None] = []
        self.save_base_dirs: list[Path] = []
        self.deleted_ids: list[str] = []
        self.inspected_trace_ids: list[str] = []

    def list_scenarios(self) -> list[ScenarioRecord]:
        self.calls += 1
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return list(self.records)

    def get_scenario(self, scenario_id: str) -> ScenarioRecord:
        self.loaded_ids.append(scenario_id)
        if self.load_error is not None:
            raise self.load_error
        for record in self.records:
            if record.scenario_id == scenario_id:
                return record
        raise KeyError(scenario_id)

    def list_traces(self) -> list[TraceRecord]:
        self.trace_calls += 1
        if self.trace_error is not None:
            raise self.trace_error
        return list(self.trace_records)

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        self.inspected_trace_ids.append(trace_id)
        if self.inspect_trace_error is not None:
            raise self.inspect_trace_error
        if self.trace_inspection is None:
            raise KeyError(trace_id)
        return self.trace_inspection

    def validate_scenario_body(
        self,
        body: dict[str, object],
        *,
        base_dir: str | Path = ".",
    ) -> ReplayPlan:
        self.validated_bodies.append(dict(body))
        self.validation_base_dirs.append(Path(base_dir))
        if self.validate_error is not None:
            raise self.validate_error
        return self.validation_plan or _replay_plan(str(body.get("name", "demo")))

    def save_scenario_body(
        self,
        body: dict[str, object],
        *,
        scenario_id: str | None = None,
        base_dir: str | Path = ".",
    ) -> ScenarioRecord:
        self.saved_bodies.append(dict(body))
        self.saved_ids.append(scenario_id)
        self.save_base_dirs.append(Path(base_dir))
        if self.save_error is not None:
            raise self.save_error
        record = self.save_record or _scenario_record(dict(body), scenario_id=scenario_id or "scenario-1")
        self.records = [record if item.scenario_id == record.scenario_id else item for item in self.records]
        if all(item.scenario_id != record.scenario_id for item in self.records):
            self.records = [*self.records, record]
        return record

    def delete_scenario(self, scenario_id: str) -> ScenarioRecord:
        self.deleted_ids.append(scenario_id)
        if self.delete_error is not None:
            raise self.delete_error
        record = self.delete_record
        if record is None:
            for item in self.records:
                if item.scenario_id == scenario_id:
                    record = item
                    break
        if record is None:
            raise KeyError(scenario_id)
        self.records = [item for item in self.records if item.scenario_id != scenario_id]
        return record


class _FakeReplaySession:
    def __init__(
        self,
        *,
        summary: ReplaySessionSummary | None = None,
        snapshot: ReplaySnapshot | None = None,
    ) -> None:
        self.summary = summary or ReplaySessionSummary(
            name="demo",
            timeline_size=4,
            total_ts_ns=800,
            device_count=1,
            channel_count=1,
            loop=False,
        )
        self.started = True
        self.stopped_by_user = False
        self._snapshot = snapshot or ReplaySnapshot(
            state=ReplayState.RUNNING,
            current_ts_ns=100,
            total_ts_ns=self.summary.total_ts_ns,
            timeline_index=1,
            timeline_size=self.summary.timeline_size,
            sent_frames=1,
        )
        self.paused = False
        self.resumed = False
        self.stopped = False

    def snapshot(self) -> ReplaySnapshot:
        return self._snapshot

    def set_snapshot(self, snapshot: ReplaySnapshot) -> None:
        self._snapshot = snapshot

    def pause(self) -> None:
        self.paused = True
        self._snapshot = ReplaySnapshot(
            state=ReplayState.PAUSED,
            current_ts_ns=self._snapshot.current_ts_ns,
            total_ts_ns=self._snapshot.total_ts_ns,
            timeline_index=self._snapshot.timeline_index,
            timeline_size=self._snapshot.timeline_size,
            sent_frames=self._snapshot.sent_frames,
            skipped_frames=self._snapshot.skipped_frames,
            errors=self._snapshot.errors,
            completed_loops=self._snapshot.completed_loops,
        )

    def resume(self) -> None:
        self.resumed = True
        self._snapshot = ReplaySnapshot(
            state=ReplayState.RUNNING,
            current_ts_ns=self._snapshot.current_ts_ns,
            total_ts_ns=self._snapshot.total_ts_ns,
            timeline_index=self._snapshot.timeline_index,
            timeline_size=self._snapshot.timeline_size,
            sent_frames=self._snapshot.sent_frames,
            skipped_frames=self._snapshot.skipped_frames,
            errors=self._snapshot.errors,
            completed_loops=self._snapshot.completed_loops,
        )

    def stop(self) -> None:
        self.stopped = True
        self.stopped_by_user = True
        self._snapshot = ReplaySnapshot(
            state=ReplayState.STOPPED,
            current_ts_ns=self._snapshot.current_ts_ns,
            total_ts_ns=self._snapshot.total_ts_ns,
            timeline_index=self._snapshot.timeline_index,
            timeline_size=self._snapshot.timeline_size,
            sent_frames=self._snapshot.sent_frames,
            skipped_frames=self._snapshot.skipped_frames,
            errors=self._snapshot.errors,
            completed_loops=self._snapshot.completed_loops,
        )

    def wait(self, timeout: float | None = None) -> bool:
        _ = timeout
        return True


class _ReplayApp:
    def __init__(
        self,
        *,
        session: _FakeReplaySession | None = None,
        error: Exception | None = None,
    ) -> None:
        self.session = session or _FakeReplaySession()
        self.error = error
        self.started_bodies: list[dict[str, object]] = []
        self.base_dirs: list[Path] = []

    def start_replay_session_from_body(
        self,
        body: dict[str, object],
        *,
        base_dir: str | Path = ".",
    ) -> _FakeReplaySession:
        self.started_bodies.append(dict(body))
        self.base_dirs.append(Path(base_dir))
        if self.error is not None:
            raise self.error
        return self.session


class _DevicesApp:
    def __init__(
        self,
        *,
        drivers: tuple[str, ...] = ("mock", "tongxing"),
        result: DeviceEnumerationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.drivers = drivers
        self.result = result or _device_result()
        self.error = error
        self.configs: list[DeviceConfig] = []

    def list_device_drivers(self) -> tuple[str, ...]:
        return self.drivers

    def enumerate_device(self, config: DeviceConfig) -> DeviceEnumerationResult:
        self.configs.append(config)
        if self.error is not None:
            raise self.error
        return self.result


def _scenario_body() -> dict[str, object]:
    return {
        "schema_version": 2,
        "name": "demo",
        "traces": [{"id": "trace1", "path": "sample.asc"}],
        "devices": [{"id": "mock0", "driver": "mock", "device_type": "MOCK", "device_index": 0}],
        "sources": [{"id": "source0", "trace": "trace1", "channel": 0, "bus": "CANFD"}],
        "targets": [{"id": "target0", "device": "mock0", "physical_channel": 0, "bus": "CANFD"}],
        "routes": [{"logical_channel": 0, "source": "source0", "target": "target0"}],
        "timeline": {"loop": False},
    }


def _scenario_body_from_trace(record: TraceRecord, source: TraceSourceSummary) -> dict[str, object]:
    return {
        "schema_version": 2,
        "name": "ui-real-app-mock-replay",
        "traces": [{"id": "trace1", "path": record.trace_id}],
        "devices": [{"id": "mock0", "driver": "mock"}],
        "sources": [
            {
                "id": "source0",
                "trace": "trace1",
                "channel": int(source.source_channel),
                "bus": source.bus.value,
            }
        ],
        "targets": [
            {
                "id": "target0",
                "device": "mock0",
                "physical_channel": 0,
                "bus": source.bus.value,
            }
        ],
        "routes": [{"logical_channel": 0, "source": "source0", "target": "target0"}],
        "timeline": {"loop": False},
    }


def _scenario_record(body: dict[str, object] | None = None, *, scenario_id: str = "scenario-1") -> ScenarioRecord:
    payload = body if body is not None else _scenario_body()
    return ScenarioRecord(
        scenario_id=scenario_id,
        name=str(payload.get("name", "demo")),
        base_dir="C:/data",
        body=payload,
        updated_at="2026-05-08T00:00:00",
        trace_count=1,
        route_count=1,
    )


def _trace_record(trace_id: str = "trace-1", *, name: str = "sample.asc") -> TraceRecord:
    return TraceRecord(
        trace_id=trace_id,
        name=name,
        original_path=name,
        library_path=name,
        cache_path=f"{trace_id}.frames.bin",
        imported_at="2026-05-08T00:00:00",
        event_count=7,
    )


def _trace_inspection(
    record: TraceRecord | None = None,
    sources: tuple[TraceSourceSummary, ...] | None = None,
) -> TraceInspection:
    trace = record or _trace_record()
    return TraceInspection(
        record=trace,
        sources=sources or (TraceSourceSummary(source_channel=0, bus=BusType.CANFD, frame_count=7),),
        messages=(),
    )


def _device_result(*, channel_count: int = 4) -> DeviceEnumerationResult:
    return DeviceEnumerationResult(
        info=DeviceInfo(
            id="mock0",
            driver="mock",
            name="MockBench",
            serial_number="MOCK-001",
            channel_count=channel_count,
        ),
        channels=tuple(range(channel_count)),
        capabilities=DeviceCapabilities(can=True, canfd=True, async_send=True, fifo_read=True),
        health=DeviceHealth(
            online=True,
            detail="Mock online.",
            per_channel={index: True for index in range(channel_count)},
        ),
    )


def _runner() -> TaskRunner:
    return TaskRunner(QThreadPool())


def _replay_plan(name: str = "demo", *, frames: int = 3, total_ns: int = 900) -> ReplayPlan:
    return ReplayPlan(
        name=name,
        frame_sources=(),
        devices=(DeviceConfig(id="mock0", driver="mock"),),
        channels=(
            PlannedChannel(
                logical_channel=0,
                device_id="mock0",
                physical_channel=0,
                config=ChannelConfig(bus=BusType.CANFD),
            ),
        ),
        timeline_size=frames,
        total_ts_ns=total_ns,
    )


def _wait_for(predicate, app: QApplication, timeout_ms: int = 3000) -> None:
    loop = QEventLoop()
    poller = QTimer()
    poller.setInterval(10)
    poller.timeout.connect(lambda: loop.quit() if predicate() else None)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poller.start()
    timeout.start(timeout_ms)
    loop.exec()
    poller.stop()
    app.processEvents()
    if not predicate():
        raise AssertionError("Timed out waiting for async UI state.")


class BaseViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-view-models"])

    def test_command_lifecycle_sets_busy_status_and_error(self) -> None:
        view_model = BaseViewModel()

        self.assertTrue(view_model.begin_command("正在执行"))
        self.assertTrue(view_model.busy)
        self.assertEqual("", view_model.error)
        self.assertEqual("正在执行", view_model.status_message)
        self.assertFalse(view_model.begin_command("重复执行"))

        view_model.complete_command("执行完成")
        self.assertFalse(view_model.busy)
        self.assertEqual("执行完成", view_model.status_message)

        self.assertTrue(view_model.begin_command())
        view_model.fail_command(RuntimeError("boom"), "执行失败")
        self.assertFalse(view_model.busy)
        self.assertEqual("boom", view_model.error)
        self.assertEqual("执行失败", view_model.status_message)


class DevicesViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-devices-view-models"])

    def test_default_config_and_editing_map_to_device_config(self) -> None:
        view_model = DevicesViewModel(_DevicesApp(), _runner())

        self.assertIn("mock", view_model.drivers)
        self.assertEqual("tongxing", view_model.draft.driver)
        self.assertEqual("TSMaster/Windows", view_model.draft.sdk_root)

        view_model.set_driver("mock")
        view_model.set_sdk_root("C:/sdk")
        view_model.set_application("BenchApp")
        view_model.set_device_type("MOCK")
        view_model.set_device_index(3)
        config = view_model.current_config()

        self.assertEqual("device0", config.id)
        self.assertEqual("mock", config.driver)
        self.assertEqual("C:/sdk", config.sdk_root)
        self.assertEqual("BenchApp", config.application)
        self.assertEqual("MOCK", config.device_type)
        self.assertEqual(3, config.device_index)

    def test_enumerate_success_maps_summary_capabilities_and_channels(self) -> None:
        devices_app = _DevicesApp(result=_device_result(channel_count=4))
        view_model = DevicesViewModel(devices_app, _runner())

        view_model.set_driver("mock")
        view_model.enumerate_current_device()
        _wait_for(lambda: not view_model.busy and view_model.summary is not None, self._app)

        self.assertEqual("mock", devices_app.configs[0].driver)
        assert view_model.summary is not None
        self.assertEqual("MockBench", view_model.summary.name)
        self.assertEqual("Online", view_model.summary.health)
        self.assertEqual(4, len(view_model.channels))
        self.assertEqual("Channel Ready", view_model.channels[0].status)
        self.assertEqual(4, len(view_model.capabilities))
        self.assertTrue(view_model.capabilities[1].supported)

    def test_enumerate_failure_reports_error_and_releases_busy(self) -> None:
        view_model = DevicesViewModel(
            _DevicesApp(error=RuntimeError("hardware missing")),
            _runner(),
        )

        view_model.enumerate_current_device()
        _wait_for(lambda: not view_model.busy and bool(view_model.error), self._app)

        self.assertEqual("hardware missing", view_model.error)
        self.assertIsNone(view_model.summary)

    def test_real_application_mock_enumeration_maps_summary_capabilities_and_channels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=tmp)
            view_model = DevicesViewModel(replay_app, _runner())

            view_model.set_driver("mock")
            view_model.enumerate_current_device()
            _wait_for(lambda: not view_model.busy and view_model.summary is not None, self._app)

            assert view_model.summary is not None
            self.assertEqual("mock", view_model.summary.driver)
            self.assertEqual("MockDevice", view_model.summary.name)
            self.assertEqual("Online", view_model.summary.health)
            self.assertEqual(8, view_model.summary.channel_count)
            self.assertEqual(8, len(view_model.channels))
            self.assertEqual("Unknown", view_model.channels[0].status)
            self.assertEqual(("CAN", "CANFD", "Async Send", "FIFO Read"), tuple(row.name for row in view_model.capabilities))
            self.assertTrue(all(row.supported for row in view_model.capabilities))


class SettingsViewModelTests(unittest.TestCase):
    def test_settings_summary_reports_workspace_drivers_and_boundaries(self) -> None:
        view_model = SettingsViewModel(
            _DevicesApp(drivers=("mock", "tongxing")),
            workspace="C:/code/next_replay/.replay_tool",
        )

        self.assertEqual("C:\\code\\next_replay\\.replay_tool", view_model.workspace)
        self.assertEqual("默认浅色工程主题", view_model.theme_name)
        self.assertEqual(("mock", "tongxing"), view_model.driver_names)
        self.assertIn("Drivers: mock, tongxing", view_model.summary_text())
        self.assertIn("offscreen 自动化不能替代", view_model.summary_text())
        self.assertTrue(any(row.feature == "DBC / Signal Override" for row in view_model.unsupported_features))
        self.assertTrue(any(row.item == "ruff" for row in view_model.validation_items))
        self.assertTrue(all(row.state == "未验证" for row in view_model.manual_items))

    def test_settings_uses_placeholder_driver_when_registry_is_empty(self) -> None:
        view_model = SettingsViewModel(_DevicesApp(drivers=()), workspace=".replay_tool")

        self.assertEqual(("未注册",), view_model.driver_names)
        self.assertIn("Drivers: 未注册", view_model.summary_text())


class ReplaySessionViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-replay-view-models"])

    def test_start_records_session_summary_and_running_snapshot(self) -> None:
        session = _FakeReplaySession()
        replay_app = _ReplayApp(session=session)
        view_model = ReplaySessionViewModel(replay_app, _runner(), poll_interval_ms=20)

        accepted = view_model.start_scenario_body(_scenario_body(), base_dir="C:/data")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertTrue(accepted)
        self.assertEqual([Path("C:/data")], replay_app.base_dirs)
        self.assertEqual("demo", replay_app.started_bodies[0]["name"])
        self.assertEqual("demo", view_model.scenario_name)
        self.assertEqual("Running", view_model.display_state)
        self.assertTrue(view_model.active)
        self.assertEqual(1, view_model.sent_frames)
        self.assertEqual(25.0, view_model.progress_percent)
        self.assertTrue(view_model.can_pause)
        self.assertFalse(view_model.can_resume)

    def test_snapshot_polling_maps_completion_and_failure(self) -> None:
        session = _FakeReplaySession()
        view_model = ReplaySessionViewModel(_ReplayApp(session=session), _runner(), poll_interval_ms=20)
        view_model.start_scenario_body(_scenario_body())
        _wait_for(lambda: not view_model.busy, self._app)

        session.set_snapshot(
            ReplaySnapshot(
                state=ReplayState.STOPPED,
                current_ts_ns=800,
                total_ts_ns=800,
                timeline_index=4,
                timeline_size=4,
                sent_frames=4,
            )
        )
        view_model.refresh_snapshot()

        self.assertEqual("Completed", view_model.display_state)
        self.assertFalse(view_model.active)
        self.assertEqual(100.0, view_model.progress_percent)

        session.set_snapshot(
            ReplaySnapshot(
                state=ReplayState.STOPPED,
                timeline_index=2,
                timeline_size=4,
                errors=("boom",),
            )
        )
        view_model.refresh_snapshot()

        self.assertEqual("Failed", view_model.display_state)
        self.assertEqual("boom", view_model.error_text)

    def test_pause_resume_and_stop_delegate_to_session(self) -> None:
        session = _FakeReplaySession()
        view_model = ReplaySessionViewModel(_ReplayApp(session=session), _runner(), poll_interval_ms=20)
        view_model.start_scenario_body(_scenario_body())
        _wait_for(lambda: not view_model.busy, self._app)

        view_model.pause()
        self.assertTrue(session.paused)
        self.assertEqual("Paused", view_model.display_state)
        self.assertTrue(view_model.can_resume)

        view_model.resume()
        self.assertTrue(session.resumed)
        self.assertEqual("Running", view_model.display_state)

        accepted = view_model.stop()
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertTrue(accepted)
        self.assertTrue(session.stopped)
        self.assertTrue(session.stopped_by_user)
        self.assertEqual("Stopped", view_model.display_state)
        self.assertFalse(view_model.active)

    def test_start_failure_reports_error_without_active_session(self) -> None:
        view_model = ReplaySessionViewModel(
            _ReplayApp(error=RuntimeError("compile failed")),
            _runner(),
            poll_interval_ms=20,
        )

        view_model.start_scenario_body(_scenario_body())
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual("compile failed", view_model.error)
        self.assertEqual("Stopped", view_model.display_state)
        self.assertFalse(view_model.active)
        self.assertIsNone(view_model.session)

    def test_real_application_mock_replay_runs_to_completion_and_releases_active_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=tmp)
            record = replay_app.import_trace(ROOT / "examples" / "sample.asc")
            source = replay_app.inspect_trace(record.trace_id).sources[0]
            view_model = ReplaySessionViewModel(replay_app, _runner(), poll_interval_ms=20)

            accepted = view_model.start_scenario_body(
                _scenario_body_from_trace(record, source),
                base_dir=tmp,
            )
            _wait_for(
                lambda: not view_model.busy and view_model.display_state in {"Completed", "Failed"},
                self._app,
            )

            self.assertTrue(accepted)
            self.assertIsNotNone(view_model.session)
            self.assertEqual("Completed", view_model.display_state)
            self.assertFalse(view_model.active)
            self.assertEqual(source.frame_count, view_model.timeline_size)
            self.assertEqual(source.frame_count, view_model.sent_frames)
            self.assertEqual(0, view_model.skipped_frames)
            self.assertEqual("", view_model.error_text)
            self.assertEqual(100.0, view_model.progress_percent)

    def test_real_application_start_failure_reports_error_and_unlocks_editor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=tmp)
            view_model = ReplaySessionViewModel(replay_app, _runner(), poll_interval_ms=20)

            accepted = view_model.start_scenario_body(_scenario_body(), base_dir=tmp)
            _wait_for(lambda: not view_model.busy and bool(view_model.error), self._app)

            self.assertTrue(accepted)
            self.assertIn("sample.asc", view_model.error)
            self.assertEqual("Stopped", view_model.display_state)
            self.assertFalse(view_model.active)
            self.assertIsNone(view_model.session)


class TraceLibraryViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-trace-view-models"])

    def test_refresh_maps_trace_records_to_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "sample.frames.bin"
            cache_path.write_bytes(b"cache")
            record = TraceRecord(
                trace_id="trace-1",
                name="sample.asc",
                original_path=str(Path(tmp) / "sample.asc"),
                library_path=str(Path(tmp) / "library.asc"),
                cache_path=str(cache_path),
                imported_at="2026-05-08T00:00:00",
                event_count=42,
                start_ns=10,
                end_ns=200,
            )

            view_model = TraceLibraryViewModel(_TraceApp([record]), _runner())
            view_model.refresh()
            _wait_for(lambda: not view_model.busy, self._app)

            self.assertEqual("", view_model.error)
            self.assertEqual(1, len(view_model.rows))
            row = view_model.rows[0]
            self.assertEqual("trace-1", row.trace_id)
            self.assertEqual("sample.asc", row.name)
            self.assertEqual(42, row.event_count)
            self.assertEqual("Cache Ready", row.cache_status)
            self.assertIn("Trace Library 已加载 1 条记录", view_model.status_message)

    def test_refresh_reports_missing_cache(self) -> None:
        record = TraceRecord(
            trace_id="trace-2",
            name="missing.asc",
            original_path="missing.asc",
            library_path="library.asc",
            cache_path="missing.frames.bin",
            imported_at="2026-05-08T00:00:00",
        )

        view_model = TraceLibraryViewModel(_TraceApp([record]), _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual("Cache Missing", view_model.rows[0].cache_status)

    def test_refresh_converts_trace_errors_to_error_state(self) -> None:
        view_model = TraceLibraryViewModel(_TraceApp(error=RuntimeError("trace store offline")), _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual((), view_model.rows)
        self.assertEqual("trace store offline", view_model.error)
        self.assertEqual("Trace Library 加载失败", view_model.status_message)
        self.assertFalse(view_model.busy)

    def test_refresh_while_busy_does_not_start_duplicate_trace_task(self) -> None:
        release = threading.Event()
        trace_app = _TraceApp(records=[], release=release)
        view_model = TraceLibraryViewModel(trace_app, _runner())

        view_model.refresh()
        _wait_for(lambda: trace_app.calls == 1 and view_model.busy, self._app)
        view_model.refresh()
        self.assertEqual(1, trace_app.calls)
        self.assertEqual("Trace Library 正在刷新", view_model.status_message)

        release.set()
        _wait_for(lambda: not view_model.busy, self._app)
        self.assertEqual(1, trace_app.calls)

    def test_import_trace_refreshes_rows_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "imported.frames.bin"
            cache_path.write_bytes(b"cache")
            record = TraceRecord(
                trace_id="trace-imported",
                name="imported.asc",
                original_path=str(Path(tmp) / "imported.asc"),
                library_path=str(Path(tmp) / "library.asc"),
                cache_path=str(cache_path),
                imported_at="2026-05-08T00:00:00",
                event_count=7,
            )
            trace_app = _TraceApp(import_record=record)
            view_model = TraceLibraryViewModel(trace_app, _runner())

            view_model.import_trace(Path(tmp) / "imported.asc")
            _wait_for(lambda: not view_model.busy, self._app)

            self.assertEqual([Path(tmp) / "imported.asc"], trace_app.import_paths)
            self.assertEqual(1, trace_app.calls)
            self.assertEqual(1, len(view_model.rows))
            self.assertEqual("trace-imported", view_model.rows[0].trace_id)
            self.assertEqual("Trace 已导入: imported.asc", view_model.status_message)

    def test_import_trace_failure_preserves_existing_rows(self) -> None:
        record = TraceRecord(
            trace_id="trace-1",
            name="sample.asc",
            original_path="sample.asc",
            library_path="library.asc",
            cache_path="missing.frames.bin",
            imported_at="2026-05-08T00:00:00",
        )
        trace_app = _TraceApp(records=[record], import_error=RuntimeError("not asc"))
        view_model = TraceLibraryViewModel(trace_app, _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)

        view_model.import_trace("capture.blf")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(1, len(view_model.rows))
        self.assertEqual("trace-1", view_model.rows[0].trace_id)
        self.assertEqual("not asc", view_model.error)
        self.assertEqual("Trace 导入失败", view_model.status_message)

    def test_inspect_trace_maps_source_and_message_summaries(self) -> None:
        record = TraceRecord(
            trace_id="trace-1",
            name="sample.asc",
            original_path="sample.asc",
            library_path="library.asc",
            cache_path="sample.frames.bin",
            imported_at="2026-05-08T00:00:00",
            event_count=2,
        )
        inspection = TraceInspection(
            record=record,
            sources=(TraceSourceSummary(source_channel=0, bus=BusType.CANFD, frame_count=2),),
            messages=(
                TraceMessageSummary(
                    source_channel=0,
                    bus=BusType.CANFD,
                    frame_count=2,
                    message_ids=(0x18DAF110, 0x18DAF111),
                ),
            ),
        )
        trace_app = _TraceApp(records=[record], inspection=inspection)
        view_model = TraceLibraryViewModel(trace_app, _runner())

        view_model.inspect_trace("trace-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(["trace-1"], trace_app.inspected_ids)
        self.assertIsNotNone(view_model.inspection)
        details = view_model.inspection
        self.assertEqual("trace-1", details.trace_id)
        self.assertEqual("CANFD", details.sources[0].bus)
        self.assertEqual((0x18DAF110, 0x18DAF111), details.messages[0].message_ids)
        self.assertEqual("Trace 已检查: sample.asc", view_model.status_message)

    def test_inspect_trace_failure_preserves_existing_rows(self) -> None:
        record = TraceRecord(
            trace_id="trace-1",
            name="sample.asc",
            original_path="sample.asc",
            library_path="library.asc",
            cache_path="missing.frames.bin",
            imported_at="2026-05-08T00:00:00",
        )
        trace_app = _TraceApp(records=[record], inspect_error=RuntimeError("missing trace"))
        view_model = TraceLibraryViewModel(trace_app, _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)

        view_model.inspect_trace("trace-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(1, len(view_model.rows))
        self.assertIsNone(view_model.inspection)
        self.assertEqual("missing trace", view_model.error)
        self.assertEqual("Trace 检查失败", view_model.status_message)

    def test_rebuild_trace_cache_refreshes_rows_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "rebuilt.frames.bin"
            cache_path.write_bytes(b"cache")
            original = TraceRecord(
                trace_id="trace-1",
                name="sample.asc",
                original_path="sample.asc",
                library_path="library.asc",
                cache_path="missing.frames.bin",
                imported_at="2026-05-08T00:00:00",
                event_count=1,
            )
            rebuilt = TraceRecord(
                trace_id="trace-1",
                name="sample.asc",
                original_path="sample.asc",
                library_path="library.asc",
                cache_path=str(cache_path),
                imported_at="2026-05-08T00:00:00",
                event_count=2,
            )
            trace_app = _TraceApp(records=[original], rebuild_record=rebuilt)
            view_model = TraceLibraryViewModel(trace_app, _runner())

            view_model.rebuild_trace_cache("trace-1")
            _wait_for(lambda: not view_model.busy, self._app)

            self.assertEqual(["trace-1"], trace_app.rebuilt_ids)
            self.assertEqual(1, trace_app.calls)
            self.assertEqual(2, view_model.rows[0].event_count)
            self.assertEqual("Cache Ready", view_model.rows[0].cache_status)
            self.assertEqual("Trace cache 已重建: sample.asc", view_model.status_message)

    def test_rebuild_trace_cache_failure_preserves_rows_and_inspection(self) -> None:
        record = TraceRecord(
            trace_id="trace-1",
            name="sample.asc",
            original_path="sample.asc",
            library_path="library.asc",
            cache_path="missing.frames.bin",
            imported_at="2026-05-08T00:00:00",
        )
        inspection = TraceInspection(
            record=record,
            sources=(TraceSourceSummary(source_channel=0, bus=BusType.CAN, frame_count=1),),
            messages=(TraceMessageSummary(source_channel=0, bus=BusType.CAN, frame_count=1, message_ids=(0x123,)),),
        )
        trace_app = _TraceApp(records=[record], inspection=inspection, rebuild_error=RuntimeError("cache source missing"))
        view_model = TraceLibraryViewModel(trace_app, _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)
        view_model.inspect_trace("trace-1")
        _wait_for(lambda: not view_model.busy, self._app)

        view_model.rebuild_trace_cache("trace-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(1, len(view_model.rows))
        self.assertIsNotNone(view_model.inspection)
        self.assertEqual("cache source missing", view_model.error)
        self.assertEqual("Trace cache 重建失败", view_model.status_message)

    def test_delete_trace_refreshes_rows_and_records_delete_result(self) -> None:
        record = TraceRecord(
            trace_id="trace-1",
            name="sample.asc",
            original_path="sample.asc",
            library_path="library.asc",
            cache_path="missing.frames.bin",
            imported_at="2026-05-08T00:00:00",
        )
        result = DeleteTraceResult(
            trace_id="trace-1",
            name="sample.asc",
            deleted_library_file=True,
            deleted_cache_file=False,
        )
        trace_app = _TraceApp(records=[record], delete_result=result)
        view_model = TraceLibraryViewModel(trace_app, _runner())
        view_model.delete_trace("trace-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(["trace-1"], trace_app.deleted_ids)
        self.assertEqual(1, trace_app.calls)
        self.assertEqual((), view_model.rows)
        self.assertIsNone(view_model.inspection)
        self.assertIsNotNone(view_model.delete_result)
        self.assertTrue(view_model.delete_result.deleted_library_file)
        self.assertFalse(view_model.delete_result.deleted_cache_file)
        self.assertEqual("Trace 已删除: sample.asc", view_model.status_message)

    def test_delete_trace_failure_preserves_rows_and_inspection(self) -> None:
        record = TraceRecord(
            trace_id="trace-1",
            name="sample.asc",
            original_path="sample.asc",
            library_path="library.asc",
            cache_path="missing.frames.bin",
            imported_at="2026-05-08T00:00:00",
        )
        inspection = TraceInspection(
            record=record,
            sources=(TraceSourceSummary(source_channel=0, bus=BusType.CAN, frame_count=1),),
            messages=(TraceMessageSummary(source_channel=0, bus=BusType.CAN, frame_count=1, message_ids=(0x123,)),),
        )
        trace_app = _TraceApp(records=[record], inspection=inspection, delete_error=RuntimeError("delete denied"))
        view_model = TraceLibraryViewModel(trace_app, _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)
        view_model.inspect_trace("trace-1")
        _wait_for(lambda: not view_model.busy, self._app)

        view_model.delete_trace("trace-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(1, len(view_model.rows))
        self.assertIsNotNone(view_model.inspection)
        self.assertIsNone(view_model.delete_result)
        self.assertEqual("delete denied", view_model.error)
        self.assertEqual("Trace 删除失败", view_model.status_message)

    def test_busy_trace_view_model_rejects_trace_commands(self) -> None:
        release = threading.Event()
        trace_app = _TraceApp(records=[], release=release)
        view_model = TraceLibraryViewModel(trace_app, _runner())

        view_model.refresh()
        _wait_for(lambda: trace_app.calls == 1 and view_model.busy, self._app)
        view_model.import_trace("sample.asc")
        view_model.inspect_trace("trace-1")
        view_model.rebuild_trace_cache("trace-1")
        view_model.delete_trace("trace-1")

        self.assertEqual([], trace_app.import_paths)
        self.assertEqual([], trace_app.inspected_ids)
        self.assertEqual([], trace_app.rebuilt_ids)
        self.assertEqual([], trace_app.deleted_ids)
        self.assertEqual("Trace Library 正在执行任务", view_model.status_message)

        release.set()
        _wait_for(lambda: not view_model.busy, self._app)

    def test_real_application_import_and_inspect_trace_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=Path(tmp) / "workspace")
            view_model = TraceLibraryViewModel(replay_app, _runner())

            view_model.import_trace(ROOT / "examples" / "sample.asc")
            _wait_for(lambda: not view_model.busy, self._app)
            self.assertEqual(1, len(view_model.rows))
            trace_id = view_model.rows[0].trace_id

            view_model.inspect_trace(trace_id)
            _wait_for(lambda: not view_model.busy, self._app)

            self.assertIsNotNone(view_model.inspection)
            details = view_model.inspection
            self.assertEqual(trace_id, details.trace_id)
            self.assertGreaterEqual(len(details.sources), 1)
            self.assertGreaterEqual(len(details.messages), 1)

    def test_real_application_rebuild_and_delete_trace_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=Path(tmp) / "workspace")
            view_model = TraceLibraryViewModel(replay_app, _runner())

            view_model.import_trace(ROOT / "examples" / "sample.asc")
            _wait_for(lambda: not view_model.busy, self._app)
            trace_id = view_model.rows[0].trace_id
            cache_path = Path(view_model.rows[0].cache_path)
            library_path = Path(replay_app.inspect_trace(trace_id).record.library_path)
            cache_path.unlink()

            view_model.rebuild_trace_cache(trace_id)
            _wait_for(lambda: not view_model.busy, self._app)
            self.assertTrue(cache_path.exists())
            self.assertEqual("Cache Ready", view_model.rows[0].cache_status)

            view_model.delete_trace(trace_id)
            _wait_for(lambda: not view_model.busy, self._app)

            self.assertEqual((), view_model.rows)
            self.assertIsNotNone(view_model.delete_result)
            self.assertTrue(view_model.delete_result.deleted_library_file)
            self.assertTrue(view_model.delete_result.deleted_cache_file)
            self.assertFalse(library_path.exists())
            self.assertFalse(cache_path.exists())


class ScenariosViewModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-scenario-view-models"])

    def test_refresh_maps_scenario_records_to_rows(self) -> None:
        record = ScenarioRecord(
            scenario_id="scenario-1",
            name="demo",
            base_dir="C:/data",
            updated_at="2026-05-08T00:00:00",
            trace_count=2,
            route_count=4,
        )

        view_model = ScenariosViewModel(_ScenarioApp([record]), _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual("", view_model.error)
        self.assertEqual(1, len(view_model.rows))
        row = view_model.rows[0]
        self.assertEqual("scenario-1", row.scenario_id)
        self.assertEqual("demo", row.name)
        self.assertEqual(2, row.trace_count)
        self.assertEqual(4, row.route_count)
        self.assertEqual("C:/data", row.base_dir)
        self.assertIn("Scenarios 已加载 1 条记录", view_model.status_message)

    def test_refresh_converts_scenario_errors_to_error_state(self) -> None:
        view_model = ScenariosViewModel(_ScenarioApp(error=RuntimeError("project store offline")), _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual((), view_model.rows)
        self.assertEqual("project store offline", view_model.error)
        self.assertEqual("Scenarios 加载失败", view_model.status_message)
        self.assertFalse(view_model.busy)

    def test_refresh_while_busy_does_not_start_duplicate_scenario_task(self) -> None:
        release = threading.Event()
        scenario_app = _ScenarioApp(records=[], release=release)
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.refresh()
        _wait_for(lambda: scenario_app.calls == 1 and view_model.busy, self._app)
        view_model.refresh()
        self.assertEqual(1, scenario_app.calls)
        self.assertEqual("Scenarios 正在刷新", view_model.status_message)

        release.set()
        _wait_for(lambda: not view_model.busy, self._app)
        self.assertEqual(1, scenario_app.calls)

    def test_load_scenario_maps_saved_body_to_draft_rows(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(["scenario-1"], scenario_app.loaded_ids)
        self.assertIsNotNone(view_model.draft)
        draft = view_model.draft
        self.assertEqual("demo", draft.name)
        self.assertEqual(2, draft.schema_version)
        self.assertEqual("trace1", draft.traces[0].trace_id)
        self.assertEqual("mock0", draft.devices[0].device_id)
        self.assertEqual("ReplayTool", draft.devices[0].application)
        self.assertEqual("TSMaster/Windows", draft.devices[0].sdk_root)
        self.assertEqual("source0", draft.sources[0].source_id)
        self.assertEqual("target0", draft.targets[0].target_id)
        self.assertEqual(500000, draft.targets[0].nominal_baud)
        self.assertEqual(2000000, draft.targets[0].data_baud)
        self.assertTrue(draft.targets[0].resistance_enabled)
        self.assertEqual("trace1 / CH0 CANFD", draft.routes[0].source_label)
        self.assertEqual("mock0 / CH0 CANFD", draft.routes[0].target_label)
        self.assertIn('"schema_version": 2', draft.json_text)
        self.assertEqual("Scenario 已加载: demo", view_model.status_message)
        self.assertFalse(draft.is_new)
        self.assertFalse(draft.dirty)

    def test_load_scenario_failure_preserves_rows_and_reports_error(self) -> None:
        record = _scenario_record()
        scenario_app = _ScenarioApp(records=[record], load_error=RuntimeError("scenario missing"))
        view_model = ScenariosViewModel(scenario_app, _runner())
        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertEqual(1, len(view_model.rows))
        self.assertIsNone(view_model.draft)
        self.assertEqual("scenario missing", view_model.error)
        self.assertEqual("Scenario 加载失败", view_model.status_message)

    def test_load_scenario_malformed_body_reports_error_without_crashing(self) -> None:
        bad_record = _scenario_record({"schema_version": 2, "name": "bad", "traces": "not-a-list"})
        scenario_app = _ScenarioApp(records=[bad_record])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy, self._app)

        self.assertIsNone(view_model.draft)
        self.assertIn("Scenario body field must be a list", view_model.error)
        self.assertEqual("Scenario 加载失败", view_model.status_message)

    def test_validate_loaded_scenario_maps_plan_summary(self) -> None:
        plan = _replay_plan("validated", frames=5, total_ns=12345)
        scenario_app = _ScenarioApp(records=[_scenario_record()], validation_plan=plan)
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.validate_loaded_scenario()
        _wait_for(lambda: not view_model.busy and view_model.validation is not None, self._app)

        self.assertEqual(1, len(scenario_app.validated_bodies))
        self.assertEqual(Path("C:/data"), scenario_app.validation_base_dirs[0])
        self.assertEqual("validated", view_model.validation.name)
        self.assertEqual(5, view_model.validation.timeline_size)
        self.assertEqual(1, view_model.validation.device_count)
        self.assertEqual(1, view_model.validation.channel_count)
        self.assertEqual(12345, view_model.validation.total_ts_ns)
        self.assertEqual("Scenario 校验通过: validated", view_model.status_message)

    def test_load_trace_choices_and_create_new_draft_from_trace_source(self) -> None:
        trace = _trace_record("trace-lib-1", name="sample.asc")
        scenario_app = _ScenarioApp(trace_records=[trace], trace_inspection=_trace_inspection(trace))
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_trace_choices()
        _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
        sources = view_model.source_choices_for_trace("trace-lib-1")
        view_model.create_new_scenario_from_trace(view_model.trace_choices[0], sources[0])

        self.assertEqual(1, scenario_app.trace_calls)
        self.assertEqual(["trace-lib-1"], scenario_app.inspected_trace_ids)
        self.assertIsNotNone(view_model.draft)
        draft = view_model.draft
        self.assertTrue(draft.is_new)
        self.assertTrue(draft.dirty)
        self.assertEqual("", draft.scenario_id)
        self.assertEqual("replay-sample", draft.name)
        self.assertEqual("trace-lib-1", draft.traces[0].trace_id)
        self.assertEqual("trace-lib-1", draft.traces[0].path)
        self.assertEqual("trace-lib-1 / CH0 CANFD", draft.routes[0].source_label)
        self.assertEqual("mock0 / CH0 CANFD", draft.routes[0].target_label)
        self.assertEqual("Scenario draft 已创建: replay-sample", view_model.status_message)

    def test_save_new_draft_creates_record_without_scenario_id(self) -> None:
        trace = _trace_record("trace-lib-1", name="sample.asc")
        saved_body = _scenario_body()
        saved_body["name"] = "replay-sample"
        saved_record = _scenario_record(saved_body, scenario_id="generated-id")
        scenario_app = _ScenarioApp(
            trace_records=[trace],
            trace_inspection=_trace_inspection(trace),
            save_record=saved_record,
        )
        view_model = ScenariosViewModel(scenario_app, _runner())
        view_model.create_new_scenario_from_trace(
            ScenarioTraceChoice.from_record(trace),
            view_model.source_choices_for_trace(trace.trace_id)[0],
        )

        view_model.save_loaded_scenario()
        _wait_for(lambda: not view_model.busy and view_model.draft is not None and not view_model.draft.is_new, self._app)

        self.assertEqual([None], scenario_app.saved_ids)
        self.assertEqual(Path("."), scenario_app.save_base_dirs[0])
        self.assertEqual("generated-id", view_model.draft.scenario_id)
        self.assertFalse(view_model.draft.is_new)
        self.assertFalse(view_model.draft.dirty)

    def test_real_application_new_draft_save_and_validate_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            replay_app = ReplayApplication(workspace=Path(tmp) / "workspace")
            trace = replay_app.import_trace(ROOT / "examples" / "sample.asc")
            view_model = ScenariosViewModel(replay_app, _runner())

            view_model.load_trace_choices()
            _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
            sources = view_model.source_choices_for_trace(trace.trace_id)
            view_model.create_new_scenario_from_trace(view_model.trace_choices[0], sources[0])
            view_model.add_route_from_trace(
                view_model.trace_choices[0],
                sources[0],
                logical_channel=1,
                physical_channel=1,
            )
            view_model.rename_loaded_scenario("created-from-ui-draft")
            view_model.save_loaded_scenario()
            _wait_for(lambda: not view_model.busy and view_model.draft is not None and not view_model.draft.is_new, self._app)
            view_model.validate_loaded_scenario()
            _wait_for(lambda: not view_model.busy and view_model.validation is not None, self._app)

            self.assertEqual("created-from-ui-draft", view_model.draft.name)
            self.assertEqual("created-from-ui-draft", view_model.validation.name)
            self.assertEqual(2, view_model.validation.timeline_size)
            self.assertEqual(2, view_model.validation.channel_count)
            self.assertEqual(1, len(view_model.rows))

    def test_editing_loaded_draft_updates_body_marks_dirty_and_clears_validation(self) -> None:
        plan = _replay_plan("validated")
        scenario_app = _ScenarioApp(records=[_scenario_record()], validation_plan=plan)
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.validate_loaded_scenario()
        _wait_for(lambda: not view_model.busy and view_model.validation is not None, self._app)

        view_model.rename_loaded_scenario("edited")
        view_model.set_timeline_loop(True)
        view_model.set_route_logical_channel(0, 3)
        view_model.set_target_physical_channel(0, 2)

        draft = view_model.draft
        self.assertEqual("edited", draft.name)
        self.assertTrue(draft.dirty)
        self.assertFalse(draft.is_new)
        self.assertIsNone(view_model.validation)
        self.assertEqual("edited", draft.body["name"])
        self.assertTrue(draft.body["timeline"]["loop"])
        self.assertEqual(3, draft.body["routes"][0]["logical_channel"])
        self.assertEqual(2, draft.body["targets"][0]["physical_channel"])
        self.assertIn('"name": "edited"', draft.json_text)
        self.assertEqual("mock0 / CH2 CANFD", draft.routes[0].target_label)

    def test_add_route_from_trace_reuses_source_and_creates_mock_target(self) -> None:
        trace = _trace_record("trace-lib-1", name="sample.asc")
        scenario_app = _ScenarioApp(trace_records=[trace], trace_inspection=_trace_inspection(trace))
        view_model = ScenariosViewModel(scenario_app, _runner())
        source = view_model.source_choices_for_trace(trace.trace_id)[0]

        view_model.create_new_scenario_from_trace(ScenarioTraceChoice.from_record(trace), source)
        view_model.add_route_from_trace(
            ScenarioTraceChoice.from_record(trace),
            source,
            logical_channel=1,
            physical_channel=1,
        )

        draft = view_model.draft
        self.assertIsNotNone(draft)
        self.assertEqual(1, len(draft.sources))
        self.assertEqual(2, len(draft.targets))
        self.assertEqual(2, len(draft.routes))
        self.assertEqual("trace-lib-1-ch0-canfd", draft.routes[1].source_id)
        self.assertEqual("mock0-ch1-canfd", draft.routes[1].target_id)
        self.assertEqual(1, draft.body["routes"][1]["logical_channel"])
        self.assertTrue(draft.dirty)
        self.assertEqual((), view_model.draft_issues)
        self.assertEqual("Route 已添加", view_model.status_message)

    def test_device_and_target_edits_update_body_and_json(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.set_device_driver(0, "tongxing")
        view_model.set_device_sdk_root(0, "C:/TSMaster")
        view_model.set_device_application(0, "BenchApp")
        view_model.set_device_type(0, "TC1014")
        view_model.set_device_index(0, 2)
        view_model.set_target_bus(0, "CAN")
        view_model.set_target_nominal_baud(0, 250000)
        view_model.set_target_data_baud(0, 1000000)
        view_model.set_target_resistance_enabled(0, False)
        view_model.set_target_listen_only(0, True)
        view_model.set_target_tx_echo(0, True)

        draft = view_model.draft
        self.assertEqual("tongxing", draft.devices[0].driver)
        self.assertEqual("C:/TSMaster", draft.devices[0].sdk_root)
        self.assertEqual("BenchApp", draft.body["devices"][0]["application"])
        self.assertEqual("TC1014", draft.devices[0].device_type)
        self.assertEqual(2, draft.devices[0].device_index)
        self.assertEqual("CAN", draft.targets[0].bus)
        self.assertEqual(250000, draft.targets[0].nominal_baud)
        self.assertEqual(1000000, draft.body["targets"][0]["data_baud"])
        self.assertFalse(draft.body["targets"][0]["resistance_enabled"])
        self.assertTrue(draft.body["targets"][0]["listen_only"])
        self.assertTrue(draft.body["targets"][0]["tx_echo"])
        self.assertTrue(draft.dirty)
        self.assertIn('"sdk_root": "C:/TSMaster"', draft.json_text)

    def test_add_remove_device_and_target_reference_guards(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.add_device()
        view_model.add_target(device_id="device0", bus="CANFD")

        draft = view_model.draft
        self.assertEqual(2, len(draft.devices))
        self.assertEqual("device0", draft.devices[1].device_id)
        self.assertEqual("tongxing", draft.devices[1].driver)
        self.assertEqual(2, len(draft.targets))
        self.assertEqual("device0-ch0-canfd", draft.targets[1].target_id)

        view_model.remove_device(1)

        self.assertEqual(2, len(view_model.draft.devices))
        self.assertEqual("warning", view_model.draft_issues[-1].severity)
        self.assertFalse(view_model.has_blocking_issues)
        self.assertIn("Device 正被 Target 引用", view_model.status_message)

        view_model.remove_target(1)

        self.assertEqual(1, len(view_model.draft.targets))
        self.assertEqual("Target 已删除: device0-ch0-canfd", view_model.status_message)

        view_model.remove_device(1)

        self.assertEqual(1, len(view_model.draft.devices))
        self.assertEqual("Device 已删除: device0", view_model.status_message)

    def test_add_route_can_use_existing_target_without_creating_mock_target(self) -> None:
        trace = _trace_record("trace-lib-1", name="sample.asc")
        scenario_app = _ScenarioApp(trace_records=[trace], trace_inspection=_trace_inspection(trace))
        view_model = ScenariosViewModel(scenario_app, _runner())
        source = view_model.source_choices_for_trace(trace.trace_id)[0]

        view_model.create_new_scenario_from_trace(ScenarioTraceChoice.from_record(trace), source)
        view_model.add_device()
        view_model.add_target(device_id="device0", bus="CANFD")
        view_model.add_route_from_trace(
            ScenarioTraceChoice.from_record(trace),
            source,
            logical_channel=1,
            target_id="device0-ch0-canfd",
        )

        draft = view_model.draft
        self.assertEqual(2, len(draft.targets))
        self.assertEqual("device0-ch0-canfd", draft.body["routes"][1]["target"])
        self.assertEqual("device0 / CH0 CANFD", draft.routes[1].target_label)
        self.assertEqual((), view_model.draft_issues)

    def test_remove_route_only_removes_route_and_reports_empty_routes_issue(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.remove_route(0)

        draft = view_model.draft
        self.assertEqual(0, len(draft.routes))
        self.assertEqual(1, len(draft.sources))
        self.assertEqual(1, len(draft.targets))
        self.assertTrue(draft.dirty)
        self.assertIn("At least one route", view_model.draft_issues[0].message)
        self.assertEqual("Route 已删除", view_model.status_message)

    def test_route_endpoint_edits_update_body_and_bus_mismatch_issue(self) -> None:
        body = _scenario_body()
        body["targets"] = [
            *body["targets"],
            {"id": "target-can", "device": "mock0", "physical_channel": 1, "bus": "CAN"},
        ]
        scenario_app = _ScenarioApp(records=[_scenario_record(body)])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.set_route_target(0, "target-can")

        draft = view_model.draft
        self.assertEqual("target-can", draft.body["routes"][0]["target"])
        self.assertIn("mock0 / CH1 CAN", draft.routes[0].target_label)
        self.assertEqual("routes[0].target", view_model.draft_issues[0].location)
        self.assertIn("CANFD source to CAN target", view_model.draft_issues[0].message)

        view_model.set_route_target(0, "target0")

        self.assertEqual((), view_model.draft_issues)
        self.assertEqual("target0", view_model.draft.body["routes"][0]["target"])

    def test_duplicate_logical_channel_and_unknown_references_map_to_draft_issues(self) -> None:
        body = _scenario_body()
        body["routes"] = [
            {"logical_channel": 0, "source": "source0", "target": "target0"},
            {"logical_channel": 0, "source": "missing-source", "target": "missing-target"},
        ]
        scenario_app = _ScenarioApp(records=[_scenario_record(body)])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

        locations = [issue.location for issue in view_model.draft_issues]
        messages = "\n".join(issue.message for issue in view_model.draft_issues)
        self.assertIn("routes[1].logical_channel", locations)
        self.assertIn("routes[1].source", locations)
        self.assertIn("routes[1].target", locations)
        self.assertIn("Logical channel 0", messages)
        self.assertIn("unknown source", messages)
        self.assertIn("unknown target", messages)

    def test_validate_loaded_scenario_failure_preserves_rows_and_draft(self) -> None:
        record = _scenario_record()
        scenario_app = _ScenarioApp(records=[record], validate_error=RuntimeError("trace missing"))
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.refresh()
        _wait_for(lambda: not view_model.busy, self._app)
        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.validate_loaded_scenario()
        _wait_for(lambda: not view_model.busy and bool(view_model.error), self._app)

        self.assertEqual(1, len(view_model.rows))
        self.assertIsNotNone(view_model.draft)
        self.assertIsNone(view_model.validation)
        self.assertEqual("trace missing", view_model.error)
        self.assertEqual("Scenario 校验失败", view_model.status_message)

    def test_save_loaded_scenario_refreshes_rows_and_updates_draft(self) -> None:
        saved_body = _scenario_body()
        saved_body["name"] = "saved-again"
        saved_record = _scenario_record(saved_body)
        scenario_app = _ScenarioApp(records=[_scenario_record()], save_record=saved_record)
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.save_loaded_scenario()
        _wait_for(lambda: not view_model.busy and view_model.status_message == "Scenario 已保存: saved-again", self._app)

        self.assertEqual(["scenario-1"], scenario_app.saved_ids)
        self.assertEqual(Path("C:/data"), scenario_app.save_base_dirs[0])
        self.assertEqual(1, scenario_app.calls)
        self.assertEqual("saved-again", view_model.rows[0].name)
        self.assertIsNotNone(view_model.draft)
        self.assertEqual("saved-again", view_model.draft.name)
        self.assertIsNone(view_model.validation)
        self.assertIsNone(view_model.delete_result)

    def test_delete_scenario_refreshes_rows_clears_draft_and_records_result(self) -> None:
        record = _scenario_record()
        scenario_app = _ScenarioApp(records=[record])
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.load_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
        view_model.delete_scenario("scenario-1")
        _wait_for(lambda: not view_model.busy and view_model.delete_result is not None, self._app)

        self.assertEqual(["scenario-1"], scenario_app.deleted_ids)
        self.assertEqual(1, scenario_app.calls)
        self.assertEqual((), view_model.rows)
        self.assertIsNone(view_model.draft)
        self.assertIsNone(view_model.validation)
        self.assertEqual("scenario-1", view_model.delete_result.scenario_id)
        self.assertEqual("demo", view_model.delete_result.name)
        self.assertEqual("Scenario 已删除: demo", view_model.status_message)

    def test_busy_scenario_view_model_rejects_load_command(self) -> None:
        release = threading.Event()
        scenario_app = _ScenarioApp(records=[_scenario_record()], release=release)
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.refresh()
        _wait_for(lambda: scenario_app.calls == 1 and view_model.busy, self._app)
        view_model.load_scenario("scenario-1")
        view_model.validate_loaded_scenario()
        view_model.save_loaded_scenario()
        view_model.delete_scenario("scenario-1")

        self.assertEqual([], scenario_app.loaded_ids)
        self.assertEqual([], scenario_app.validated_bodies)
        self.assertEqual([], scenario_app.saved_bodies)
        self.assertEqual([], scenario_app.deleted_ids)
        self.assertEqual("Scenarios 正在执行任务", view_model.status_message)

        release.set()
        _wait_for(lambda: not view_model.busy, self._app)

    def test_busy_scenario_view_model_rejects_draft_edits(self) -> None:
        release = threading.Event()
        trace = _trace_record("trace-lib-1", name="sample.asc")
        scenario_app = _ScenarioApp(
            records=[],
            release=release,
            trace_records=[trace],
            trace_inspection=_trace_inspection(trace),
        )
        view_model = ScenariosViewModel(scenario_app, _runner())
        source = view_model.source_choices_for_trace(trace.trace_id)[0]
        view_model.create_new_scenario_from_trace(ScenarioTraceChoice.from_record(trace), source)
        original_body = dict(view_model.draft.body)

        view_model.refresh()
        _wait_for(lambda: scenario_app.calls == 1 and view_model.busy, self._app)
        view_model.rename_loaded_scenario("busy-edit")
        view_model.set_route_logical_channel(0, 4)
        view_model.set_route_source(0, "missing-source")
        view_model.set_route_target(0, "missing-target")
        view_model.add_route_from_trace(
            ScenarioTraceChoice.from_record(trace),
            source,
            logical_channel=1,
            physical_channel=1,
        )
        view_model.remove_route(0)

        self.assertEqual(original_body, view_model.draft.body)
        self.assertEqual("Scenarios 正在执行任务", view_model.status_message)

        release.set()
        _wait_for(lambda: not view_model.busy, self._app)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
import unittest

import tests.bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QThreadPool, QTimer
from PySide6.QtWidgets import QApplication

from replay_tool.app import DeviceEnumerationResult, ReplaySessionSummary
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
from replay_ui_qt.view_models.devices import DevicesViewModel
from replay_ui_qt.view_models.replay_session import ReplaySessionViewModel
from replay_ui_qt.view_models.scenarios import ScenarioSourceChoice, ScenarioTraceChoice, ScenariosViewModel
from replay_ui_qt.view_models.trace_library import TraceLibraryViewModel
from replay_ui_qt.views.placeholders import DevicesView, ReplayMonitorView
from replay_ui_qt.views.scenarios_view import ScenariosView
from replay_ui_qt.views.trace_library_view import TraceLibraryView


class _TraceApp:
    def __init__(
        self,
        *,
        records: list[TraceRecord] | None = None,
        error: Exception | None = None,
        release: threading.Event | None = None,
        inspection: TraceInspection | None = None,
        delete_result: DeleteTraceResult | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.release = release
        self.inspection = inspection
        self.delete_result = delete_result
        self.calls = 0

    def list_traces(self) -> list[TraceRecord]:
        self.calls += 1
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return list(self.records)

    def import_trace(self, path: str | Path) -> TraceRecord:
        raise AssertionError(f"Unexpected import in view fake: {path}")

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        if self.inspection is None:
            raise AssertionError(f"Unexpected inspect in view fake: {trace_id}")
        return self.inspection

    def rebuild_trace_cache(self, trace_id: str) -> TraceRecord:
        raise AssertionError(f"Unexpected rebuild in view fake: {trace_id}")

    def delete_trace(self, trace_id: str) -> DeleteTraceResult:
        if self.delete_result is None:
            raise AssertionError(f"Unexpected delete in view fake: {trace_id}")
        self.records = [record for record in self.records if record.trace_id != trace_id]
        return self.delete_result


class _ScenarioApp:
    def __init__(
        self,
        *,
        records: list[ScenarioRecord] | None = None,
        error: Exception | None = None,
        release: threading.Event | None = None,
        validation_plan: ReplayPlan | None = None,
        delete_result: ScenarioRecord | None = None,
        trace_records: list[TraceRecord] | None = None,
        trace_inspection: TraceInspection | None = None,
    ) -> None:
        self.records = records or []
        self.error = error
        self.release = release
        self.validation_plan = validation_plan
        self.delete_result = delete_result
        self.trace_records = trace_records or []
        self.trace_inspection = trace_inspection
        self.calls = 0
        self.trace_calls = 0
        self.loaded_ids: list[str] = []
        self.deleted_ids: list[str] = []

    def list_scenarios(self) -> list[ScenarioRecord]:
        self.calls += 1
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return list(self.records)

    def get_scenario(self, scenario_id: str) -> ScenarioRecord:
        self.loaded_ids.append(scenario_id)
        for record in self.records:
            if record.scenario_id == scenario_id:
                return record
        raise KeyError(scenario_id)

    def list_traces(self) -> list[TraceRecord]:
        self.trace_calls += 1
        return list(self.trace_records)

    def inspect_trace(self, trace_id: str) -> TraceInspection:
        if self.trace_inspection is None:
            raise KeyError(trace_id)
        return self.trace_inspection

    def validate_scenario_body(
        self,
        body: dict[str, object],
        *,
        base_dir: str | Path = ".",
    ) -> ReplayPlan:
        return self.validation_plan or _replay_plan(str(body.get("name", "demo-scenario")))

    def save_scenario_body(
        self,
        body: dict[str, object],
        *,
        scenario_id: str | None = None,
        base_dir: str | Path = ".",
    ) -> ScenarioRecord:
        record = _scenario_record()
        self.records = [record]
        return record

    def delete_scenario(self, scenario_id: str) -> ScenarioRecord:
        self.deleted_ids.append(scenario_id)
        record = self.delete_result
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
            name="demo-scenario",
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
            current_ts_ns=200,
            total_ts_ns=800,
            timeline_index=1,
            timeline_size=4,
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
        )


class _ReplayApp:
    def __init__(self, session: _FakeReplaySession | None = None) -> None:
        self.session = session or _FakeReplaySession()
        self.started_bodies: list[dict[str, object]] = []

    def start_replay_session_from_body(
        self,
        body: dict[str, object],
        *,
        base_dir: str | Path = ".",
    ) -> _FakeReplaySession:
        _ = base_dir
        self.started_bodies.append(dict(body))
        return self.session


class _DevicesApp:
    def __init__(
        self,
        *,
        drivers: tuple[str, ...] = ("mock", "tongxing"),
        result: DeviceEnumerationResult | None = None,
        error: Exception | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.drivers = drivers
        self.result = result or _device_result()
        self.error = error
        self.release = release
        self.configs: list[DeviceConfig] = []

    def list_device_drivers(self) -> tuple[str, ...]:
        return self.drivers

    def enumerate_device(self, config: DeviceConfig) -> DeviceEnumerationResult:
        self.configs.append(config)
        if self.release is not None:
            self.release.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return self.result


def _runner() -> TaskRunner:
    return TaskRunner(QThreadPool())


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
        raise AssertionError("Timed out waiting for async view state.")


def _trace_record(tmp: str, trace_id: str = "trace-1") -> TraceRecord:
    cache_path = Path(tmp) / f"{trace_id}.frames.bin"
    cache_path.write_bytes(b"cache")
    return TraceRecord(
        trace_id=trace_id,
        name="sample.asc",
        original_path=str(Path(tmp) / "sample.asc"),
        library_path=str(Path(tmp) / "library.asc"),
        cache_path=str(cache_path),
        imported_at="2026-05-08T00:00:00",
        event_count=2,
        start_ns=10,
        end_ns=20,
    )


def _inspection(record: TraceRecord) -> TraceInspection:
    return TraceInspection(
        record=record,
        sources=(TraceSourceSummary(source_channel=0, bus=BusType.CANFD, frame_count=2),),
        messages=(
            TraceMessageSummary(
                source_channel=0,
                bus=BusType.CANFD,
                frame_count=2,
                message_ids=(0x18DAF110,),
            ),
        ),
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


def _scenario_body() -> dict[str, object]:
    return {
        "schema_version": 2,
        "name": "demo-scenario",
        "traces": [{"id": "trace1", "path": "sample.asc"}],
        "devices": [{"id": "mock0", "driver": "mock", "device_type": "MOCK", "device_index": 0}],
        "sources": [{"id": "source0", "trace": "trace1", "channel": 0, "bus": "CANFD"}],
        "targets": [{"id": "target0", "device": "mock0", "physical_channel": 0, "bus": "CANFD"}],
        "routes": [{"logical_channel": 0, "source": "source0", "target": "target0"}],
        "timeline": {"loop": False},
    }


def _scenario_record(body: dict[str, object] | None = None) -> ScenarioRecord:
    payload = body if body is not None else _scenario_body()
    return ScenarioRecord(
        scenario_id="scenario-1",
        name=str(payload.get("name", "demo-scenario")),
        base_dir="C:/data",
        body=payload,
        updated_at="2026-05-08T00:00:00",
        trace_count=1,
        route_count=1,
    )


def _replay_plan(name: str = "demo-scenario") -> ReplayPlan:
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
        timeline_size=4,
        total_ts_ns=800,
    )


class DevicesViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-devices-view"])

    def test_fields_are_editable_and_enumeration_result_is_rendered(self) -> None:
        devices_app = _DevicesApp(result=_device_result(channel_count=4))
        view_model = DevicesViewModel(devices_app, _runner())
        view = DevicesView(view_model)
        try:
            self.assertTrue(view.enumerate_enabled())
            self.assertEqual(("Idle", "default"), view.status_badge_state())

            view.set_driver("mock")
            view.edit_sdk_root("C:/sdk")
            view.edit_application("BenchApp")
            view.edit_device_type("MOCK")
            view.edit_device_index(2)
            view.trigger_enumerate()
            _wait_for(lambda: not view_model.busy and view.channel_row_count() == 4, self._app)

            self.assertEqual("mock", devices_app.configs[0].driver)
            self.assertEqual("C:/sdk", devices_app.configs[0].sdk_root)
            self.assertEqual("BenchApp", devices_app.configs[0].application)
            self.assertEqual("MOCK", devices_app.configs[0].device_type)
            self.assertEqual(2, devices_app.configs[0].device_index)
            self.assertIn("MockBench", view.summary_text())
            self.assertIn("Health: Online", view.summary_text())
            self.assertEqual(4, view.capability_row_count())
            self.assertEqual(("Ready", "ready"), view.status_badge_state())
            title, body = view.inspector_snapshot()
            self.assertEqual("Device Enumeration", title)
            self.assertIn("Driver: mock", body)
        finally:
            view.close()
            self._app.processEvents()

    def test_enumerate_busy_disables_fields_and_button(self) -> None:
        release = threading.Event()
        devices_app = _DevicesApp(release=release)
        view_model = DevicesViewModel(devices_app, _runner())
        view = DevicesView(view_model)
        try:
            view.trigger_enumerate()
            _wait_for(
                lambda: not view.enumerate_enabled()
                and view.status_badge_state() == ("Enumerating", "running"),
                self._app,
            )

            release.set()
            _wait_for(lambda: view.enumerate_enabled(), self._app)
        finally:
            release.set()
            view.close()
            self._app.processEvents()

    def test_error_details_button_and_dialog_follow_device_error_state(self) -> None:
        view_model = DevicesViewModel(
            _DevicesApp(error=RuntimeError("hardware missing")),
            _runner(),
        )
        view = DevicesView(view_model)
        try:
            self.assertFalse(view.error_details_enabled())
            view.trigger_enumerate()
            _wait_for(lambda: view.error_details_enabled(), self._app)

            self.assertEqual(("Failed", "failed"), view.status_badge_state())
            dialog = view.create_error_dialog()
            try:
                self.assertIn("Devices 枚举失败", dialog.detail_text())
                self.assertIn("hardware missing", dialog.detail_text())
            finally:
                dialog.close()
        finally:
            view.close()
            self._app.processEvents()


class TraceLibraryViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-trace-view"])

    def test_refresh_button_is_disabled_while_trace_refresh_is_busy(self) -> None:
        release = threading.Event()
        trace_app = _TraceApp(release=release)
        view = TraceLibraryView(TraceLibraryViewModel(trace_app, _runner()))
        try:
            _wait_for(
                lambda: trace_app.calls == 1
                and not view.refresh_enabled()
                and not view.import_enabled()
                and not view.inspect_enabled()
                and not view.rebuild_enabled()
                and not view.delete_enabled()
                and view.status_badge_state() == ("Loading", "running"),
                self._app,
            )

            release.set()
            _wait_for(lambda: view.refresh_enabled(), self._app)
            self.assertEqual(("No records", "disabled"), view.status_badge_state())
        finally:
            release.set()
            view.close()
            self._app.processEvents()

    def test_inspect_button_follows_trace_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _trace_record(tmp)
            view = TraceLibraryView(TraceLibraryViewModel(_TraceApp(records=[record]), _runner()))
            try:
                _wait_for(lambda: view.refresh_enabled(), self._app)
                self.assertTrue(view.import_enabled())
                self.assertFalse(view.inspect_enabled())
                self.assertFalse(view.rebuild_enabled())
                self.assertFalse(view.delete_enabled())

                view.select_row(0)

                self.assertTrue(view.inspect_enabled())
                self.assertTrue(view.rebuild_enabled())
                self.assertTrue(view.delete_enabled())

                dialog = view.create_delete_confirmation_dialog()
                try:
                    self.assertIn("Delete Trace", dialog.text())
                    self.assertIn("sample.asc", dialog.informativeText())
                    self.assertIn("trace-1", dialog.informativeText())
                finally:
                    dialog.close()
            finally:
                view.close()
                self._app.processEvents()

    def test_inspection_details_are_rendered_in_trace_inspector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _trace_record(tmp)
            view_model = TraceLibraryViewModel(_TraceApp(records=[record], inspection=_inspection(record)), _runner())
            view = TraceLibraryView(view_model)
            try:
                _wait_for(lambda: view.refresh_enabled(), self._app)
                view.select_row(0)
                view_model.inspect_trace(record.trace_id)
                _wait_for(lambda: not view_model.busy and view_model.inspection is not None, self._app)

                _title, body = view.inspector_snapshot()
                self.assertIn("Sources:", body)
                self.assertIn("CH0 CANFD frames=2", body)
                self.assertIn("Messages:", body)
                self.assertIn("0x18DAF110", body)
            finally:
                view.close()
                self._app.processEvents()

    def test_delete_result_is_rendered_in_trace_inspector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _trace_record(tmp)
            result = DeleteTraceResult(
                trace_id=record.trace_id,
                name=record.name,
                deleted_library_file=True,
                deleted_cache_file=False,
            )
            view_model = TraceLibraryViewModel(_TraceApp(records=[record], delete_result=result), _runner())
            view = TraceLibraryView(view_model)
            try:
                _wait_for(lambda: view.refresh_enabled(), self._app)
                view.select_row(0)
                view_model.delete_trace(record.trace_id)
                _wait_for(lambda: not view_model.busy and view_model.delete_result is not None, self._app)

                _title, body = view.inspector_snapshot()
                self.assertIn("Trace ID: trace-1", body)
                self.assertIn("Deleted library file: True", body)
                self.assertIn("Deleted cache file: False", body)
            finally:
                view.close()
                self._app.processEvents()

    def test_error_details_button_and_dialog_follow_trace_error_state(self) -> None:
        view = TraceLibraryView(TraceLibraryViewModel(_TraceApp(error=RuntimeError("trace store offline")), _runner()))
        try:
            self.assertFalse(view.error_details_enabled())
            _wait_for(lambda: view.error_details_enabled(), self._app)

            self.assertEqual(("Failed", "failed"), view.status_badge_state())
            dialog = view.create_error_dialog()
            try:
                self.assertIn("Trace Library 操作失败", dialog.detail_text())
                self.assertIn("trace store offline", dialog.detail_text())
            finally:
                dialog.close()
        finally:
            view.close()
            self._app.processEvents()

    def test_toolbar_header_frame_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _trace_record(tmp)
            view = TraceLibraryView(TraceLibraryViewModel(_TraceApp(records=[record]), _runner()))
            try:
                _wait_for(lambda: view.refresh_enabled(), self._app)
                from PySide6.QtWidgets import QFrame
                header = view.findChild(QFrame, "ToolbarHeader")
                self.assertIsNone(header, "Toolbar should be bare QHBoxLayout, not wrapped in ToolbarHeader QFrame")
            finally:
                view.close()
                self._app.processEvents()


class ReplayMonitorViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-replay-monitor-view"])

    def test_monitor_renders_running_snapshot_and_controls(self) -> None:
        session = _FakeReplaySession()
        view_model = ReplaySessionViewModel(_ReplayApp(session), _runner(), poll_interval_ms=20)
        view = ReplayMonitorView(view_model)
        try:
            view_model.start_scenario_body(_scenario_body())
            _wait_for(lambda: not view_model.busy and view.state_text() == "Running", self._app)

            self.assertEqual("Running", view.state_text())
            self.assertEqual(25, view.progress_value())
            self.assertEqual("1/4", view.metric_text("Timeline"))
            self.assertEqual("1", view.metric_text("Sent frames"))
            self.assertTrue(view.pause_enabled())
            self.assertFalse(view.resume_enabled())
            self.assertTrue(view.stop_enabled())

            view_model.pause()
            self.assertEqual("Paused", view.state_text())
            self.assertFalse(view.pause_enabled())
            self.assertTrue(view.resume_enabled())

            dialog = view.create_stop_confirmation_dialog()
            try:
                self.assertIn("Stop Replay", dialog.text())
                self.assertIn("demo-scenario", dialog.informativeText())
            finally:
                dialog.close()
        finally:
            view.close()
            self._app.processEvents()

    def test_monitor_renders_completion_and_error_details(self) -> None:
        session = _FakeReplaySession()
        view_model = ReplaySessionViewModel(_ReplayApp(session), _runner(), poll_interval_ms=20)
        view = ReplayMonitorView(view_model)
        try:
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

            self.assertEqual("Completed", view.state_text())
            self.assertEqual(100, view.progress_value())
            self.assertFalse(view.stop_enabled())

            session.set_snapshot(
                ReplaySnapshot(
                    state=ReplayState.STOPPED,
                    timeline_index=2,
                    timeline_size=4,
                    errors=("runtime failed",),
                )
            )
            view_model.refresh_snapshot()

            self.assertEqual("Failed", view.state_text())
            self.assertTrue(view.error_details_enabled())
            dialog = view.create_error_dialog()
            try:
                self.assertIn("runtime failed", dialog.detail_text())
            finally:
                dialog.close()
        finally:
            view.close()
            self._app.processEvents()


class ScenariosViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication(["test-ui-scenarios-view"])

    def test_refresh_button_is_disabled_while_scenario_refresh_is_busy(self) -> None:
        release = threading.Event()
        scenario_app = _ScenarioApp(release=release)
        view = ScenariosView(ScenariosViewModel(scenario_app, _runner()))
        try:
            _wait_for(
                lambda: scenario_app.calls == 1
                and not view.new_enabled()
                and not view.refresh_enabled()
                and not view.load_enabled()
                and not view.add_route_enabled()
                and not view.remove_route_enabled()
                and view.status_badge_state() == ("Loading", "running"),
                self._app,
            )

            release.set()
            _wait_for(lambda: view.refresh_enabled(), self._app)
            self.assertTrue(view.new_enabled())
            self.assertEqual(("No records", "disabled"), view.status_badge_state())
        finally:
            release.set()
            view.close()
            self._app.processEvents()

    def test_command_buttons_follow_scenario_selection_and_loaded_draft(self) -> None:
        view_model = ScenariosViewModel(_ScenarioApp(records=[_scenario_record()]), _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            self.assertFalse(view.load_enabled())
            self.assertFalse(view.save_enabled())
            self.assertFalse(view.validate_enabled())
            self.assertFalse(view.run_enabled())
            self.assertFalse(view.delete_enabled())
            self.assertTrue(view.new_enabled())

            view.select_row(0)

            self.assertTrue(view.load_enabled())
            self.assertFalse(view.save_enabled())
            self.assertFalse(view.validate_enabled())
            self.assertFalse(view.run_enabled())
            self.assertTrue(view.delete_enabled())

            dialog = view.create_delete_confirmation_dialog()
            try:
                self.assertIn("Delete Scenario", dialog.text())
                self.assertIn("demo-scenario", dialog.informativeText())
                self.assertIn("scenario-1", dialog.informativeText())
            finally:
                dialog.close()

            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            self.assertTrue(view.save_enabled())
            self.assertTrue(view.validate_enabled())
            self.assertTrue(view.run_enabled())
            self.assertTrue(view.delete_enabled())
            self.assertTrue(view.add_route_enabled())
            self.assertTrue(view.remove_route_enabled())
        finally:
            view.close()
            self._app.processEvents()

    def test_run_signal_and_active_replay_lock_editor_commands(self) -> None:
        view_model = ScenariosViewModel(_ScenarioApp(records=[_scenario_record()]), _runner())
        view = ScenariosView(view_model)
        emitted: list[tuple[dict[str, object], str]] = []
        view.runRequested.connect(lambda body, base_dir: emitted.append((dict(body), str(base_dir))))
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            self.assertTrue(view.run_enabled())
            view.trigger_run()

            self.assertEqual(1, len(emitted))
            self.assertEqual("demo-scenario", emitted[0][0]["name"])
            self.assertEqual("C:/data", emitted[0][1])

            view.set_replay_active(True)
            before = view.overview_name_text()

            self.assertFalse(view.save_enabled())
            self.assertFalse(view.validate_enabled())
            self.assertFalse(view.run_enabled())
            self.assertFalse(view.add_route_enabled())
            self.assertFalse(view.remove_route_enabled())
            self.assertFalse(view.add_device_enabled())
            self.assertFalse(view.remove_device_enabled())
            self.assertFalse(view.add_target_enabled())
            self.assertFalse(view.remove_target_enabled())

            view.edit_overview_name("blocked-edit")
            self.assertEqual(before, view.overview_name_text())

            view.set_replay_active(False)
            self.assertTrue(view.run_enabled())
        finally:
            view.close()
            self._app.processEvents()

    def test_new_scenario_switches_to_editor_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = _trace_record(tmp)
            scenario_app = _ScenarioApp(
                trace_records=[trace],
                trace_inspection=_inspection(trace),
            )
            view_model = ScenariosViewModel(scenario_app, _runner())
            view = ScenariosView(view_model)
            try:
                _wait_for(lambda: not view_model.busy, self._app)
                view_model.load_trace_choices()
                _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
                self.assertEqual(0, view.current_page_index())
                view.trigger_new_scenario()
                self.assertEqual(1, view.current_page_index())
            finally:
                view.close()
                self._app.processEvents()

    def test_add_route_button_adds_route_in_editor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = _trace_record(tmp)
            scenario_app = _ScenarioApp(
                trace_records=[trace],
                trace_inspection=_inspection(trace),
            )
            view_model = ScenariosViewModel(scenario_app, _runner())
            view = ScenariosView(view_model)
            try:
                _wait_for(lambda: not view_model.busy, self._app)
                view_model.load_trace_choices()
                _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
                source = view_model.source_choices_for_trace(trace.trace_id)[0]
                view_model.create_new_scenario_from_trace(view_model.trace_choices[0], source)
                view.switch_to_editor()
                self.assertTrue(view.add_route_enabled())
                self.assertIn("trace-1 / CH0 CANFD", view.routes_preview_text())
            finally:
                view.close()
                self._app.processEvents()

    def test_back_button_returns_to_list(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
            view.switch_to_editor()
            self.assertEqual(1, view.current_page_index())
            view.trigger_back_to_list()
            self.assertEqual(0, view.current_page_index())
        finally:
            view.close()
            self._app.processEvents()

    def test_loaded_scenario_draft_is_rendered_in_editor(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            self.assertEqual("demo-scenario", view.overview_name_text())
            self.assertFalse(view.overview_loop_checked())
            self.assertIn("trace1 / CH0 CANFD -> 0 -> mock0 / CH0 CANFD", view.routes_preview_text())
            _title, body = view.inspector_snapshot()
            self.assertIn("Scenario ID: scenario-1", body)
            self.assertIn("Routes: 1", body)
        finally:
            view.close()
            self._app.processEvents()

    def test_overview_and_route_edits_update_editor(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            view.edit_overview_name("edited-scenario")
            view.edit_overview_loop(True)
            view.edit_route_logical_channel(4)
            view.edit_target_physical_channel(2)

            self.assertEqual("edited-scenario", view.overview_name_text())
            self.assertTrue(view.overview_loop_checked())
            self.assertIn("trace1 / CH0 CANFD -> 4 -> mock0 / CH2 CANFD", view.routes_preview_text())
            self.assertTrue(view.run_enabled())
        finally:
            view.close()
            self._app.processEvents()

    def test_device_and_target_editors_update_and_lock_with_replay(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            self.assertTrue(view.add_device_enabled())
            self.assertTrue(view.add_target_enabled())
            view.select_device(0)
            view.edit_device_driver("tongxing")
            view.edit_device_sdk_root("C:/TSMaster")
            view.edit_device_application("BenchApp")
            view.edit_device_type("TC1014")
            view.edit_device_index(3)
            view.select_target(0)
            view.edit_target_bus("CAN")
            view.edit_target_nominal_baud(250000)
            view.edit_target_data_baud(1000000)
            view.edit_target_resistance_enabled(False)
            view.edit_target_listen_only(True)
            view.edit_target_tx_echo(True)

            view.set_replay_active(True)
            self.assertFalse(view.add_device_enabled())
            self.assertFalse(view.remove_device_enabled())
            self.assertFalse(view.add_target_enabled())
            self.assertFalse(view.remove_target_enabled())
        finally:
            view.close()
            self._app.processEvents()

    def test_target_issue_is_shown_near_target_and_route_editors(self) -> None:
        body = _scenario_body()
        body["targets"] = [
            *body["targets"],
            {"id": "target-can", "device": "mock0", "physical_channel": 1, "bus": "CAN"},
        ]
        scenario_app = _ScenarioApp(records=[_scenario_record(body)])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            view.select_route(0)
            view.edit_route_target("target-can")

            self.assertFalse(view.run_enabled())
            self.assertIn("CANFD source to CAN target", view.route_issue_text())
            title, body_text = view.inspector_snapshot()
            self.assertEqual("Scenario Draft Issues", title)
            self.assertIn("routes[0].target", body_text)
        finally:
            view.close()
            self._app.processEvents()

    def test_route_source_target_edits_update_selected_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = _trace_record(tmp, trace_id="trace1")
            scenario_app = _ScenarioApp(
                records=[_scenario_record()],
                trace_records=[trace],
                trace_inspection=_inspection(trace),
            )
            view_model = ScenariosViewModel(scenario_app, _runner())
            view = ScenariosView(view_model)
            try:
                _wait_for(lambda: view.refresh_enabled(), self._app)
                view.select_row(0)
                view_model.load_scenario("scenario-1")
                _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
                view_model.load_trace_choices()
                _wait_for(lambda: not view_model.busy and len(view_model.trace_choices) == 1, self._app)
                source = view_model.source_choices_for_trace(trace.trace_id)[0]
                view_model.add_route_from_trace(
                    view_model.trace_choices[0],
                    source,
                    logical_channel=1,
                    physical_channel=1,
                )

                view.select_route(0)
                view.edit_route_target("mock0-ch1-canfd")
                view.edit_route_logical_channel(5)
                view.edit_route_source("source0")

                self.assertIn("trace1 / CH0 CANFD -> 5 -> mock0 / CH1 CANFD", view.routes_preview_text())
                self.assertTrue(view.remove_route_enabled())
                self.assertTrue(view.run_enabled())
            finally:
                view.close()
                self._app.processEvents()

    def test_draft_issues_are_rendered_in_scenario_inspector(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
            view_model.add_route_from_trace(
                ScenarioTraceChoice("trace1", "sample.asc", 1),
                ScenarioSourceChoice("trace1", 0, "CANFD", 1),
                logical_channel=0,
                physical_channel=1,
            )

            title, body = view.inspector_snapshot()
            self.assertEqual("Scenario Draft Issues", title)
            self.assertIn("routes[1].logical_channel", body)
            self.assertIn("Logical channel 0", body)
        finally:
            view.close()
            self._app.processEvents()

    def test_validation_result_is_rendered_in_scenario_inspector(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()], validation_plan=_replay_plan("compiled-demo"))
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
            view_model.validate_loaded_scenario()
            _wait_for(lambda: not view_model.busy and view_model.validation is not None, self._app)

            title, body = view.inspector_snapshot()
            self.assertEqual("Scenario 校验结果", title)
            self.assertIn("名称: compiled-demo", body)
            self.assertIn("Frames: 4", body)
            self.assertIn("Channels: 1", body)
        finally:
            view.close()
            self._app.processEvents()

    def test_delete_result_is_rendered_in_scenario_inspector(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)
            view_model.delete_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.delete_result is not None, self._app)

            title, body = view.inspector_snapshot()
            self.assertEqual("Scenario 删除结果", title)
            self.assertIn("Scenario ID: scenario-1", body)
            self.assertIn("Routes: 1", body)
            self.assertFalse(view.save_enabled())
            self.assertFalse(view.validate_enabled())
        finally:
            view.close()
            self._app.processEvents()

    def test_error_details_button_and_dialog_follow_scenario_error_state(self) -> None:
        view = ScenariosView(ScenariosViewModel(_ScenarioApp(error=RuntimeError("project store offline")), _runner()))
        try:
            self.assertFalse(view.error_details_enabled())
            _wait_for(lambda: view.error_details_enabled(), self._app)

            self.assertEqual(("Failed", "failed"), view.status_badge_state())
            dialog = view.create_error_dialog()
            try:
                self.assertIn("Scenarios 操作失败", dialog.detail_text())
                self.assertIn("project store offline", dialog.detail_text())
            finally:
                dialog.close()
        finally:
            view.close()
            self._app.processEvents()


    def test_toolbar_header_frame_exists_in_list_view(self) -> None:
        view = ScenariosView(ScenariosViewModel(_ScenarioApp(records=[_scenario_record()]), _runner()))
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            from PySide6.QtWidgets import QFrame

            header = view.findChild(QFrame, "ToolbarHeader")
            self.assertIsNone(header, "Toolbar should be bare QHBoxLayout, not wrapped in ToolbarHeader QFrame")
        finally:
            view.close()
            self._app.processEvents()


if __name__ == "__main__":
    unittest.main()

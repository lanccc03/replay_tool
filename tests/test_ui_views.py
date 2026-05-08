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

from replay_tool.domain import BusType
from replay_tool.ports.project_store import ScenarioRecord
from replay_tool.ports.trace_store import (
    DeleteTraceResult,
    TraceInspection,
    TraceMessageSummary,
    TraceRecord,
    TraceSourceSummary,
)
from replay_ui_qt.tasks import TaskRunner
from replay_ui_qt.view_models.scenarios import ScenariosViewModel
from replay_ui_qt.view_models.trace_library import TraceLibraryViewModel
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
    ) -> None:
        self.records = records or []
        self.error = error
        self.release = release
        self.calls = 0
        self.loaded_ids: list[str] = []

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


def _scenario_record() -> ScenarioRecord:
    return ScenarioRecord(
        scenario_id="scenario-1",
        name="demo-scenario",
        base_dir="C:/data",
        body=_scenario_body(),
        updated_at="2026-05-08T00:00:00",
        trace_count=1,
        route_count=1,
    )


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
                and not view.refresh_enabled()
                and not view.load_enabled()
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

    def test_load_button_follows_scenario_selection_and_edit_actions_stay_disabled(self) -> None:
        view = ScenariosView(ScenariosViewModel(_ScenarioApp(records=[_scenario_record()]), _runner()))
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            self.assertFalse(view.load_enabled())
            self.assertFalse(view.save_enabled())
            self.assertFalse(view.validate_enabled())
            self.assertFalse(view.run_enabled())
            self.assertFalse(view.delete_enabled())

            view.select_row(0)

            self.assertTrue(view.load_enabled())
            self.assertFalse(view.save_enabled())
            self.assertFalse(view.validate_enabled())
            self.assertFalse(view.run_enabled())
            self.assertFalse(view.delete_enabled())
        finally:
            view.close()
            self._app.processEvents()

    def test_loaded_scenario_draft_is_rendered_in_preview_tabs(self) -> None:
        scenario_app = _ScenarioApp(records=[_scenario_record()])
        view_model = ScenariosViewModel(scenario_app, _runner())
        view = ScenariosView(view_model)
        try:
            _wait_for(lambda: view.refresh_enabled(), self._app)
            view.select_row(0)
            view_model.load_scenario("scenario-1")
            _wait_for(lambda: not view_model.busy and view_model.draft is not None, self._app)

            self.assertIn("demo-scenario", view.overview_text())
            self.assertIn("trace1 / CH0 CANFD -> 0 -> mock0 / CH0 CANFD", view.routes_preview_text())
            self.assertIn('"schema_version": 2', view.json_preview_text())
            _title, body = view.inspector_snapshot()
            self.assertIn("Scenario ID: scenario-1", body)
            self.assertIn("Routes: 1", body)
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


if __name__ == "__main__":
    unittest.main()

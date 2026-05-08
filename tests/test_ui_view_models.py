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

from replay_tool.app import ReplayApplication
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
from replay_ui_qt.view_models.base import BaseViewModel
from replay_ui_qt.view_models.scenarios import ScenariosViewModel
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
    ) -> None:
        self.records = records or []
        self.error = error
        self.release = release
        self.load_error = load_error
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
        if self.load_error is not None:
            raise self.load_error
        for record in self.records:
            if record.scenario_id == scenario_id:
                return record
        raise KeyError(scenario_id)


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


def _scenario_record(body: dict[str, object] | None = None) -> ScenarioRecord:
    payload = body if body is not None else _scenario_body()
    return ScenarioRecord(
        scenario_id="scenario-1",
        name=str(payload.get("name", "demo")),
        base_dir="C:/data",
        body=payload,
        updated_at="2026-05-08T00:00:00",
        trace_count=1,
        route_count=1,
    )


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
        self.assertEqual("source0", draft.sources[0].source_id)
        self.assertEqual("target0", draft.targets[0].target_id)
        self.assertEqual("trace1 / CH0 CANFD", draft.routes[0].source_label)
        self.assertEqual("mock0 / CH0 CANFD", draft.routes[0].target_label)
        self.assertIn('"schema_version": 2', draft.json_text)
        self.assertEqual("Scenario 已加载: demo", view_model.status_message)

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

    def test_busy_scenario_view_model_rejects_load_command(self) -> None:
        release = threading.Event()
        scenario_app = _ScenarioApp(records=[_scenario_record()], release=release)
        view_model = ScenariosViewModel(scenario_app, _runner())

        view_model.refresh()
        _wait_for(lambda: scenario_app.calls == 1 and view_model.busy, self._app)
        view_model.load_scenario("scenario-1")

        self.assertEqual([], scenario_app.loaded_ids)
        self.assertEqual("Scenarios 正在执行任务", view_model.status_message)

        release.set()
        _wait_for(lambda: not view_model.busy, self._app)


if __name__ == "__main__":
    unittest.main()

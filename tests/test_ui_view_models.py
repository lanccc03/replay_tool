from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from replay_tool.ports.project_store import ScenarioRecord
from replay_tool.ports.trace_store import TraceRecord
from replay_ui_qt.view_models.base import BaseViewModel
from replay_ui_qt.view_models.scenarios import ScenariosViewModel
from replay_ui_qt.view_models.trace_library import TraceLibraryViewModel


class _TraceApp:
    def __init__(self, records: list[TraceRecord] | None = None, error: Exception | None = None) -> None:
        self.records = records or []
        self.error = error

    def list_traces(self) -> list[TraceRecord]:
        if self.error is not None:
            raise self.error
        return list(self.records)


class _ScenarioApp:
    def __init__(self, records: list[ScenarioRecord] | None = None, error: Exception | None = None) -> None:
        self.records = records or []
        self.error = error

    def list_scenarios(self) -> list[ScenarioRecord]:
        if self.error is not None:
            raise self.error
        return list(self.records)


class BaseViewModelTests(unittest.TestCase):
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

            view_model = TraceLibraryViewModel(_TraceApp([record]))
            view_model.refresh()

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

        view_model = TraceLibraryViewModel(_TraceApp([record]))
        view_model.refresh()

        self.assertEqual("Cache Missing", view_model.rows[0].cache_status)

    def test_refresh_converts_trace_errors_to_error_state(self) -> None:
        view_model = TraceLibraryViewModel(_TraceApp(error=RuntimeError("trace store offline")))
        view_model.refresh()

        self.assertEqual((), view_model.rows)
        self.assertEqual("trace store offline", view_model.error)
        self.assertEqual("Trace Library 加载失败", view_model.status_message)
        self.assertFalse(view_model.busy)


class ScenariosViewModelTests(unittest.TestCase):
    def test_refresh_maps_scenario_records_to_rows(self) -> None:
        record = ScenarioRecord(
            scenario_id="scenario-1",
            name="demo",
            base_dir="C:/data",
            updated_at="2026-05-08T00:00:00",
            trace_count=2,
            route_count=4,
        )

        view_model = ScenariosViewModel(_ScenarioApp([record]))
        view_model.refresh()

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
        view_model = ScenariosViewModel(_ScenarioApp(error=RuntimeError("project store offline")))
        view_model.refresh()

        self.assertEqual((), view_model.rows)
        self.assertEqual("project store offline", view_model.error)
        self.assertEqual("Scenarios 加载失败", view_model.status_message)
        self.assertFalse(view_model.busy)


if __name__ == "__main__":
    unittest.main()

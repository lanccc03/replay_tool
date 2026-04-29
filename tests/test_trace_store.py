from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

from replay_tool.app import ReplayApplication
from replay_tool.domain import BusType
from replay_tool.storage import SqliteTraceStore, read_frame_cache


ROOT = Path(__file__).resolve().parents[1]


class TraceStoreTests(unittest.TestCase):
    def test_import_persists_cache_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteTraceStore(Path(tmp) / "library")

            record = store.import_trace(str(ROOT / "examples" / "sample.asc"))
            listed = store.list_traces()
            inspection = store.inspect_trace(record.trace_id)
            cached_frames = read_frame_cache(record.cache_path)

        self.assertEqual([record.trace_id], [item.trace_id for item in listed])
        self.assertEqual(2, record.event_count)
        self.assertTrue(Path(record.cache_path).name.endswith(".frames.json"))
        self.assertEqual([BusType.CANFD, BusType.CAN], [item.bus for item in cached_frames])
        self.assertEqual((0, BusType.CAN, 1), (inspection.sources[0].source_channel, inspection.sources[0].bus, inspection.sources[0].frame_count))
        self.assertEqual((0, BusType.CANFD, 1), (inspection.sources[1].source_channel, inspection.sources[1].bus, inspection.sources[1].frame_count))
        canfd_summary = next(item for item in inspection.messages if item.bus == BusType.CANFD)
        self.assertEqual((0x18DAF110,), canfd_summary.message_ids)

    def test_application_compiles_scenario_using_imported_trace_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "library"
            app = ReplayApplication(workspace=workspace)
            record = app.import_trace(ROOT / "examples" / "sample.asc")
            scenario_payload = json.loads((ROOT / "examples" / "mock_canfd.json").read_text(encoding="utf-8"))
            scenario_payload["traces"][0]["path"] = record.trace_id
            scenario_path = Path(tmp) / "scenario.json"
            scenario_path.write_text(json.dumps(scenario_payload), encoding="utf-8")

            plan = app.compile_plan(scenario_path)

        self.assertEqual("mock-canfd-demo", plan.name)
        self.assertEqual(1, len(plan.frames))
        self.assertEqual(0x18DAF110, plan.frames[0].message_id)
        self.assertTrue(plan.frames[0].extended)


if __name__ == "__main__":
    unittest.main()

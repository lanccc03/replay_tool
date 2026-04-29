from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

from replay_tool.app import ReplayApplication
from replay_tool.domain import BusType, Frame
from replay_tool.storage import (
    BINARY_CACHE_FORMAT,
    ManagedTraceReader,
    SqliteTraceStore,
    read_binary_frame_cache,
    write_binary_frame_cache,
)


ROOT = Path(__file__).resolve().parents[1]


class TraceStoreTests(unittest.TestCase):
    def test_binary_cache_round_trip_preserves_frame_fields_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "frames.frames.bin"
            frames = [
                Frame(
                    ts_ns=10,
                    bus=BusType.CANFD,
                    channel=0,
                    message_id=0x18DAF110,
                    payload=bytes(range(12)),
                    dlc=0x9,
                    extended=True,
                    remote=False,
                    brs=True,
                    esi=True,
                    direction="Tx",
                    source_file="source.asc",
                ),
                Frame(
                    ts_ns=20,
                    bus=BusType.CAN,
                    channel=1,
                    message_id=0x123,
                    payload=b"\x01\x02",
                    dlc=2,
                    extended=False,
                    remote=True,
                    direction="Rx",
                    source_file="source.asc",
                ),
            ]

            write_binary_frame_cache(cache_path, frames)
            loaded = read_binary_frame_cache(cache_path)
            filtered = read_binary_frame_cache(
                cache_path,
                source_filters={(0, BusType.CANFD)},
                start_ns=0,
                end_ns=20,
            )

        self.assertEqual(frames, loaded)
        self.assertEqual([frames[0]], filtered)

    def test_managed_reader_rejects_json_frame_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "legacy.frames.json"
            cache_path.write_text("[]", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "JSON trace caches are unsupported"):
                ManagedTraceReader().read(str(cache_path))

    def test_import_persists_cache_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteTraceStore(Path(tmp) / "library")

            record = store.import_trace(str(ROOT / "examples" / "sample.asc"))
            listed = store.list_traces()
            inspection = store.inspect_trace(record.trace_id)
            cached_frames = read_binary_frame_cache(record.cache_path)

        self.assertEqual([record.trace_id], [item.trace_id for item in listed])
        self.assertEqual(2, record.event_count)
        self.assertTrue(Path(record.cache_path).name.endswith(".frames.bin"))
        self.assertEqual(BINARY_CACHE_FORMAT, record.metadata["cache_format"])
        self.assertEqual([BusType.CANFD, BusType.CAN], [item.bus for item in cached_frames])
        self.assertEqual((0, BusType.CAN, 1), (inspection.sources[0].source_channel, inspection.sources[0].bus, inspection.sources[0].frame_count))
        self.assertEqual((0, BusType.CANFD, 1), (inspection.sources[1].source_channel, inspection.sources[1].bus, inspection.sources[1].frame_count))
        canfd_summary = next(item for item in inspection.messages if item.bus == BusType.CANFD)
        self.assertEqual((0x18DAF110,), canfd_summary.message_ids)

    def test_load_frames_filters_by_source_and_time_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteTraceStore(Path(tmp) / "library")
            record = store.import_trace(str(ROOT / "examples" / "tongxing_tc1014_four_channel_canfd.asc"))

            window_frames = store.load_frames(
                record.trace_id,
                start_ns=500_000,
                end_ns=1_500_000,
            )
            filtered_frames = store.load_frames(
                record.trace_id,
                source_filters={(2, BusType.CANFD)},
                start_ns=500_000,
                end_ns=1_500_000,
            )

        self.assertEqual([1, 2], [frame.channel for frame in window_frames])
        self.assertEqual([0x18DAF111, 0x18DAF112], [frame.message_id for frame in window_frames])
        self.assertEqual(1, len(filtered_frames))
        self.assertEqual(2, filtered_frames[0].channel)
        self.assertEqual(0x18DAF112, filtered_frames[0].message_id)

    def test_import_rejects_non_asc_trace_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteTraceStore(Path(tmp) / "library")
            blf_path = Path(tmp) / "capture.blf"
            blf_path.write_bytes(b"")

            with self.assertRaisesRegex(ValueError, "Only ASC trace import is supported"):
                store.import_trace(str(blf_path))

    def test_rebuild_cache_recreates_binary_cache_from_library_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteTraceStore(Path(tmp) / "library")
            record = store.import_trace(str(ROOT / "examples" / "sample.asc"))
            cache_path = Path(record.cache_path)
            cache_path.unlink()

            rebuilt = store.rebuild_cache(record.trace_id)
            frames = store.load_frames(record.trace_id)

            self.assertTrue(Path(rebuilt.cache_path).exists())
            self.assertTrue(Path(rebuilt.cache_path).name.endswith(".frames.bin"))
            self.assertEqual(2, len(frames))

    def test_delete_trace_removes_record_and_managed_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteTraceStore(Path(tmp) / "library")
            record = store.import_trace(str(ROOT / "examples" / "sample.asc"))
            library_path = Path(record.library_path)
            cache_path = Path(record.cache_path)

            result = store.delete_trace(record.trace_id)

            self.assertIsNone(store.get_trace(record.trace_id))
            self.assertEqual(record.trace_id, result.trace_id)
            self.assertTrue(result.deleted_library_file)
            self.assertTrue(result.deleted_cache_file)
            self.assertFalse(library_path.exists())
            self.assertFalse(cache_path.exists())

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

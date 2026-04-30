from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import tests.bootstrap  # noqa: F401

from replay_tool.app import ReplayApplication
from replay_tool.domain import BusType, Frame
from replay_tool.storage import (
    AscTraceReader,
    BINARY_CACHE_FORMAT,
    ManagedTraceReader,
    SqliteTraceStore,
    read_binary_frame_cache,
    write_binary_frame_cache,
)


ROOT = Path(__file__).resolve().parents[1]


class SpyAscReader(AscTraceReader):
    def __init__(self) -> None:
        self.iter_called = False
        self.read_called = False

    def read(self, path: str) -> list[Frame]:
        """Fail if import/rebuild falls back to full-list ASC reads.

        Args:
            path: ASC path.

        Returns:
            Never returns; this method should not be called by streaming paths.
        """
        self.read_called = True
        raise AssertionError("Streaming import should not call AscTraceReader.read().")

    def iter(self, path: str):
        """Record streaming reads and delegate to the real parser.

        Args:
            path: ASC path.

        Yields:
            Parsed frames.
        """
        self.iter_called = True
        yield from super().iter(path)


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

    def test_import_and_rebuild_stream_asc_without_reading_full_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_reader = ManagedTraceReader()
            spy_reader = SpyAscReader()
            trace_reader.asc_reader = spy_reader
            store = SqliteTraceStore(Path(tmp) / "library", trace_reader)

            record = store.import_trace(str(ROOT / "examples" / "sample.asc"))
            rebuilt = store.rebuild_cache(record.trace_id)

        self.assertTrue(spy_reader.iter_called)
        self.assertFalse(spy_reader.read_called)
        self.assertEqual(2, rebuilt.event_count)

    def test_import_rejects_out_of_order_asc_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "out_of_order.asc"
            trace_path.write_text(
                "\n".join(
                    [
                        "date Thu Apr 30 00:00:00.000 2026",
                        "base hex timestamps absolute",
                        "0.002000 CANFD 1 Rx 18DAF110 1 0 1 1 00",
                        "0.001000 CANFD 1 Rx 18DAF111 1 0 1 1 01",
                    ]
                ),
                encoding="utf-8",
            )
            store = SqliteTraceStore(Path(tmp) / "library")

            with self.assertRaisesRegex(ValueError, "streaming import requires ordered frames"):
                store.import_trace(str(trace_path))

    def test_import_large_synthetic_asc_builds_cache_summary_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "large.asc"
            lines = [
                "date Thu Apr 30 00:00:00.000 2026",
                "base hex timestamps absolute",
            ]
            for index in range(5000):
                channel = index % 4 + 1
                ts_seconds = index / 1_000_000
                message_id = 0x180 + (index % 8)
                payload = index % 256
                lines.append(f"{ts_seconds:.6f} CANFD {channel} Rx {message_id:X} 1 0 1 1 {payload:02X}")
            trace_path.write_text("\n".join(lines), encoding="utf-8")
            store = SqliteTraceStore(Path(tmp) / "library")

            record = store.import_trace(str(trace_path))
            filtered = store.load_frames(record.trace_id, source_filters={(1, BusType.CANFD)}, start_ns=1_000_000, end_ns=2_000_000)

            connection = sqlite3.connect(store.sqlite_path)
            try:
                index_count = connection.execute(
                    "SELECT COUNT(*) FROM trace_frame_index WHERE trace_id = ?",
                    (record.trace_id,),
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(5000, record.event_count)
        self.assertEqual(0, record.start_ns)
        self.assertEqual(4_999_000, record.end_ns)
        self.assertGreater(index_count, 0)
        self.assertTrue(filtered)
        self.assertTrue(all(frame.channel == 1 for frame in filtered))

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

    def test_load_frames_rebuilds_missing_cache_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SqliteTraceStore(Path(tmp) / "library")
            record = store.import_trace(str(ROOT / "examples" / "sample.asc"))
            connection = sqlite3.connect(store.sqlite_path)
            try:
                connection.execute("DELETE FROM trace_frame_index WHERE trace_id = ?", (record.trace_id,))
                connection.commit()
            finally:
                connection.close()

            frames = store.load_frames(record.trace_id)

            connection = sqlite3.connect(store.sqlite_path)
            try:
                index_count = connection.execute(
                    "SELECT COUNT(*) FROM trace_frame_index WHERE trace_id = ?",
                    (record.trace_id,),
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(2, len(frames))
        self.assertGreater(index_count, 0)

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
        self.assertFalse(hasattr(plan, "frames"))
        self.assertEqual(1, plan.timeline_size)
        self.assertEqual(1, len(plan.frame_sources))
        self.assertEqual(0, plan.frame_sources[0].logical_channel)
        self.assertEqual(record.trace_id, plan.frame_sources[0].library_trace_id)


if __name__ == "__main__":
    unittest.main()

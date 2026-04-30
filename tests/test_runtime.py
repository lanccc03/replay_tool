from __future__ import annotations

from collections.abc import Iterable, Iterator
import time
import unittest

import tests.bootstrap  # noqa: F401

from replay_tool.adapters.mock import MockDevice
from replay_tool.domain import BusType, ChannelConfig, DeviceConfig, Frame, ReplayState
from replay_tool.planning import PlannedChannel, PlannedFrameSource, ReplayPlan
from replay_tool.ports import DeviceRegistry
from replay_tool.runtime import ReplayRuntime


class ManualClock:
    def __init__(self) -> None:
        self.now_ns = 0

    def __call__(self) -> int:
        return self.now_ns

    def advance_sleep(self, seconds: float) -> None:
        self.now_ns += max(int(seconds * 1_000_000_000), 1)


class RecordingDevice(MockDevice):
    def __init__(self, config: DeviceConfig, *, accepted_per_send: int | None = None) -> None:
        super().__init__(config)
        self.accepted_per_send = accepted_per_send
        self.send_batches: list[tuple[Frame, ...]] = []

    def send(self, frames) -> int:
        """Record one batch and report the configured accepted count.

        Args:
            frames: Frames sent by the runtime dispatcher.

        Returns:
            Either the full batch length or the configured partial count.
        """
        self.send_batches.append(tuple(frames))
        if self.accepted_per_send is None:
            return super().send(frames)
        for frame in frames:
            if int(frame.channel) not in self.started_channels:
                raise RuntimeError(f"Recording channel {frame.channel} is not started.")
        self.sent_frames.extend(frames)
        return min(self.accepted_per_send, len(frames))


class InMemoryTraceReader:
    def __init__(self, frames_by_path: dict[str, tuple[Frame, ...]]) -> None:
        self.frames_by_path = frames_by_path

    def read(self, path: str) -> list[Frame]:
        """Read all frames for compatibility with the TraceReader protocol.

        Args:
            path: In-memory trace key.

        Returns:
            Frames matching the key.
        """
        return list(self.iter(path))

    def iter(
        self,
        path: str,
        *,
        source_filters: Iterable[tuple[int, BusType]] | None = None,
        start_ns: int | None = None,
        end_ns: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate in-memory frames with trace reader filters.

        Args:
            path: In-memory trace key.
            source_filters: Optional source channel and bus filters.
            start_ns: Optional inclusive lower timestamp bound.
            end_ns: Optional exclusive upper timestamp bound.

        Yields:
            Matching frames.
        """
        filters = set(source_filters or ())
        for frame in self.frames_by_path[path]:
            if filters and (frame.channel, frame.bus) not in filters:
                continue
            if start_ns is not None and frame.ts_ns < start_ns:
                continue
            if end_ns is not None and frame.ts_ns >= end_ns:
                continue
            yield frame


class RuntimeTests(unittest.TestCase):
    def _make_plan(
        self,
        *,
        loop: bool = False,
        ts_ns: int = 0,
    ) -> tuple[ReplayPlan, list[MockDevice], DeviceRegistry, InMemoryTraceReader]:
        devices: list[MockDevice] = []
        config = DeviceConfig(id="mock0", driver="mock")
        channel_config = ChannelConfig(bus=BusType.CANFD)
        frame = Frame(
            ts_ns=ts_ns,
            bus=BusType.CANFD,
            channel=0,
            message_id=0x123,
            payload=b"\x01\x02",
            dlc=2,
        )
        plan = ReplayPlan(
            name="runtime-demo",
            frame_sources=(
                PlannedFrameSource(
                    trace_id="trace0",
                    source_id="source0",
                    path="trace0",
                    source_channel=0,
                    bus=BusType.CANFD,
                    logical_channel=0,
                    frame_count=1,
                    start_ns=ts_ns,
                    end_ns=ts_ns,
                ),
            ),
            devices=(config,),
            channels=(
                PlannedChannel(
                    logical_channel=0,
                    device_id="mock0",
                    physical_channel=1,
                    config=channel_config,
                ),
            ),
            loop=loop,
            timeline_size=1,
            total_ts_ns=ts_ns,
        )
        registry = DeviceRegistry()
        registry.register("mock", lambda item: devices.append(MockDevice(item)) or devices[-1])
        return plan, devices, registry, InMemoryTraceReader({"trace0": (frame,)})

    def test_runtime_sends_frames_and_closes_device(self) -> None:
        plan, devices, registry, trace_reader = self._make_plan()
        clock = ManualClock()
        runtime = ReplayRuntime(registry, clock=clock, sleeper=clock.advance_sleep, trace_reader=trace_reader)

        runtime.configure(plan)
        runtime.start()
        self.assertTrue(runtime.wait(timeout=2.0))

        snapshot = runtime.snapshot()
        self.assertEqual(ReplayState.STOPPED, snapshot.state)
        self.assertEqual(1, snapshot.sent_frames)
        self.assertFalse(devices[0].opened)
        self.assertEqual(1, devices[0].sent_frames[0].channel)

    def test_pause_resume_rebinds_time_base(self) -> None:
        plan, _devices, registry, trace_reader = self._make_plan(ts_ns=1_000_000_000)
        clock = ManualClock()
        runtime = ReplayRuntime(
            registry,
            clock=clock,
            sleeper=lambda seconds: time.sleep(0.001),
            trace_reader=trace_reader,
        )

        runtime.configure(plan)
        runtime.start()
        runtime.pause()
        self.assertEqual(ReplayState.PAUSED, runtime.snapshot().state)
        clock.now_ns = 1_000_000_000
        runtime.resume()
        clock.now_ns = 2_000_000_000

        self.assertTrue(runtime.wait(timeout=2.0))
        self.assertEqual(1, runtime.snapshot().sent_frames)

    def test_loop_restarts_until_stopped(self) -> None:
        plan, _devices, registry, trace_reader = self._make_plan(loop=True)
        clock = ManualClock()
        runtime = ReplayRuntime(registry, clock=clock, sleeper=clock.advance_sleep, trace_reader=trace_reader)

        runtime.configure(plan)
        runtime.start()
        deadline = time.monotonic() + 2.0
        while runtime.snapshot().completed_loops < 1 and time.monotonic() < deadline:
            time.sleep(0.001)
        runtime.stop()

        self.assertGreaterEqual(runtime.snapshot().completed_loops, 1)

    def test_runtime_batches_frames_in_two_millisecond_window_and_groups_by_device(self) -> None:
        devices: dict[str, RecordingDevice] = {}
        registry = DeviceRegistry()
        registry.register("recording", lambda item: devices.setdefault(item.id, RecordingDevice(item)))
        channel_config = ChannelConfig(bus=BusType.CANFD)
        frames = tuple(
            Frame(
                ts_ns=index * 500_000,
                bus=BusType.CANFD,
                channel=index,
                message_id=0x100 + index,
                payload=bytes([index]),
                dlc=1,
            )
            for index in range(4)
        )
        plan = ReplayPlan(
            name="batch-demo",
            frame_sources=tuple(
                PlannedFrameSource(
                    trace_id="trace0",
                    source_id=f"source{index}",
                    path="trace0",
                    source_channel=index,
                    bus=BusType.CANFD,
                    logical_channel=index,
                    frame_count=1,
                    start_ns=frames[index].ts_ns,
                    end_ns=frames[index].ts_ns,
                )
                for index in range(4)
            ),
            devices=(
                DeviceConfig(id="dev0", driver="recording"),
                DeviceConfig(id="dev1", driver="recording"),
            ),
            channels=(
                PlannedChannel(0, "dev0", 0, channel_config),
                PlannedChannel(1, "dev0", 1, channel_config),
                PlannedChannel(2, "dev1", 0, channel_config),
                PlannedChannel(3, "dev1", 1, channel_config),
            ),
            timeline_size=4,
            total_ts_ns=frames[-1].ts_ns,
        )
        clock = ManualClock()
        runtime = ReplayRuntime(
            registry,
            clock=clock,
            sleeper=clock.advance_sleep,
            trace_reader=InMemoryTraceReader({"trace0": frames}),
        )

        runtime.configure(plan)
        runtime.start()
        self.assertTrue(runtime.wait(timeout=2.0))

        snapshot = runtime.snapshot()
        self.assertEqual(4, snapshot.sent_frames)
        self.assertEqual(0, snapshot.skipped_frames)
        self.assertEqual(4, snapshot.timeline_index)
        self.assertEqual(4, snapshot.timeline_size)
        self.assertEqual(1, len(devices["dev0"].send_batches))
        self.assertEqual(1, len(devices["dev1"].send_batches))
        self.assertEqual([0, 1], [frame.channel for frame in devices["dev0"].send_batches[0]])
        self.assertEqual([0, 1], [frame.channel for frame in devices["dev1"].send_batches[0]])

    def test_runtime_counts_partial_batch_send_as_skipped_remainder(self) -> None:
        devices: list[RecordingDevice] = []
        registry = DeviceRegistry()
        registry.register("recording", lambda item: devices.append(RecordingDevice(item, accepted_per_send=1)) or devices[-1])
        channel_config = ChannelConfig(bus=BusType.CANFD)
        frames = tuple(
            Frame(
                ts_ns=index * 100_000,
                bus=BusType.CANFD,
                channel=index,
                message_id=0x200 + index,
                payload=bytes([index]),
                dlc=1,
            )
            for index in range(3)
        )
        plan = ReplayPlan(
            name="partial-demo",
            frame_sources=tuple(
                PlannedFrameSource(
                    trace_id="trace0",
                    source_id=f"source{index}",
                    path="trace0",
                    source_channel=index,
                    bus=BusType.CANFD,
                    logical_channel=index,
                    frame_count=1,
                    start_ns=frames[index].ts_ns,
                    end_ns=frames[index].ts_ns,
                )
                for index in range(3)
            ),
            devices=(DeviceConfig(id="dev0", driver="recording"),),
            channels=tuple(
                PlannedChannel(index, "dev0", index, channel_config)
                for index in range(3)
            ),
            timeline_size=3,
            total_ts_ns=frames[-1].ts_ns,
        )
        clock = ManualClock()
        runtime = ReplayRuntime(
            registry,
            clock=clock,
            sleeper=clock.advance_sleep,
            trace_reader=InMemoryTraceReader({"trace0": frames}),
        )

        runtime.configure(plan)
        runtime.start()
        self.assertTrue(runtime.wait(timeout=2.0))

        snapshot = runtime.snapshot()
        self.assertEqual(1, snapshot.sent_frames)
        self.assertEqual(2, snapshot.skipped_frames)
        self.assertEqual(1, len(devices[0].send_batches))
        self.assertEqual(3, len(devices[0].send_batches[0]))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import heapq
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from replay_tool.domain import ChannelConfig, DeviceConfig, Frame, ReplayRoute, ReplayScenario, ReplaySource
from replay_tool.ports.trace import TraceReader


@dataclass(frozen=True)
class PlannedChannel:
    logical_channel: int
    device_id: str
    physical_channel: int
    config: ChannelConfig


@dataclass(frozen=True)
class ReplayPlan:
    name: str
    frames: tuple[Frame, ...]
    devices: tuple[DeviceConfig, ...]
    channels: tuple[PlannedChannel, ...]
    loop: bool = False

    @property
    def total_ts_ns(self) -> int:
        """Return the replay plan duration in nanoseconds.

        Returns:
            The timestamp of the final planned frame, or 0 when the plan has no
            frames.
        """
        return self.frames[-1].ts_ns if self.frames else 0

    def channel_for_logical(self, logical_channel: int) -> PlannedChannel:
        """Find the planned target channel for a logical channel number.

        Args:
            logical_channel: Logical replay channel assigned to a frame.

        Returns:
            The matching planned channel route.

        Raises:
            KeyError: If the logical channel is not part of this plan.
        """
        for channel in self.channels:
            if channel.logical_channel == logical_channel:
                return channel
        raise KeyError(logical_channel)


class ReplayPlanner:
    def __init__(self, trace_reader: TraceReader) -> None:
        self.trace_reader = trace_reader

    def compile(self, scenario: ReplayScenario, *, base_dir: str | Path = ".") -> ReplayPlan:
        """Compile a user scenario into an executable replay plan.

        Args:
            scenario: Validated scenario configuration.
            base_dir: Directory used to resolve relative trace paths.

        Returns:
            A ReplayPlan with mapped frames sorted by replay timestamp.

        Raises:
            FileNotFoundError: If a referenced trace path cannot be opened by
                the trace reader.
            ValueError: If a trace reader rejects the trace content.
        """
        base_path = Path(base_dir)
        traces_by_id = {item.id: item for item in scenario.traces}
        sources_by_id = {item.id: item for item in scenario.sources}
        targets_by_id = {item.id: item for item in scenario.targets}
        routes_by_trace: dict[str, list[tuple[ReplayRoute, ReplaySource]]] = {}
        for route in scenario.routes:
            source = sources_by_id[route.source_id]
            routes_by_trace.setdefault(source.trace_id, []).append((route, source))

        frame_groups: list[Sequence[Frame]] = []
        for trace_id, routes in routes_by_trace.items():
            trace = traces_by_id[trace_id]
            trace_path = Path(trace.path)
            if not trace_path.is_absolute():
                trace_path = base_path / trace_path
            trace_frames = self.trace_reader.read(str(trace_path))
            mapped_frames: list[Frame] = []
            for route, source in routes:
                mapped_frames.extend(self._map_frames(trace_frames, route, source))
            mapped_frames.sort(key=lambda item: item.ts_ns)
            frame_groups.append(mapped_frames)

        frames = tuple(heapq.merge(*frame_groups, key=lambda item: item.ts_ns)) if frame_groups else ()
        channels = tuple(
            PlannedChannel(
                logical_channel=route.logical_channel,
                device_id=targets_by_id[route.target_id].device_id,
                physical_channel=targets_by_id[route.target_id].physical_channel,
                config=targets_by_id[route.target_id].config,
            )
            for route in scenario.routes
        )
        return ReplayPlan(
            name=scenario.name,
            frames=frames,
            devices=scenario.devices,
            channels=channels,
            loop=scenario.timeline.loop,
        )

    def _map_frames(self, frames: Sequence[Frame], route: ReplayRoute, source: ReplaySource) -> list[Frame]:
        return [
            frame.clone(channel=route.logical_channel)
            for frame in frames
            if frame.channel == source.channel and frame.bus == source.bus
        ]

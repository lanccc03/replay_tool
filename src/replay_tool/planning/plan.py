from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from replay_tool.domain import BusType, ChannelConfig, DeviceConfig, ReplayRoute, ReplayScenario, ReplaySource
from replay_tool.ports.trace_store import TraceRecord


@dataclass(frozen=True)
class PlannedChannel:
    logical_channel: int
    device_id: str
    physical_channel: int
    config: ChannelConfig


@dataclass(frozen=True)
class PlannedFrameSource:
    trace_id: str
    source_id: str
    path: str
    source_channel: int
    bus: BusType
    logical_channel: int
    library_trace_id: str = ""
    frame_count: int = 0
    start_ns: int = 0
    end_ns: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_channel", int(self.source_channel))
        object.__setattr__(self, "logical_channel", int(self.logical_channel))
        object.__setattr__(self, "frame_count", int(self.frame_count))
        object.__setattr__(self, "start_ns", int(self.start_ns))
        object.__setattr__(self, "end_ns", int(self.end_ns))
        if not isinstance(self.bus, BusType):
            object.__setattr__(self, "bus", BusType(self.bus))


@dataclass(frozen=True)
class ReplayPlan:
    name: str
    frame_sources: tuple[PlannedFrameSource, ...]
    devices: tuple[DeviceConfig, ...]
    channels: tuple[PlannedChannel, ...]
    loop: bool = False
    timeline_size: int = 0
    total_ts_ns: int = 0

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
    def compile(
        self,
        scenario: ReplayScenario,
        *,
        base_dir: str | Path = ".",
        trace_records: dict[str, TraceRecord] | None = None,
    ) -> ReplayPlan:
        """Compile a user scenario into an executable replay plan.

        Args:
            scenario: Validated scenario configuration.
            base_dir: Directory used to resolve relative trace paths.
            trace_records: Optional records keyed by scenario trace ID. When
                present, the planner uses record metadata for timeline counts
                and cache-backed replay source IDs.

        Returns:
            A ReplayPlan with cache-backed planned frame sources.
        """
        base_path = Path(base_dir)
        traces_by_id = {item.id: item for item in scenario.traces}
        sources_by_id = {item.id: item for item in scenario.sources}
        targets_by_id = {item.id: item for item in scenario.targets}
        routes_by_trace: dict[str, list[tuple[ReplayRoute, ReplaySource]]] = {}
        for route in scenario.routes:
            source = sources_by_id[route.source_id]
            routes_by_trace.setdefault(source.trace_id, []).append((route, source))

        records_by_trace = trace_records or {}
        frame_sources: list[PlannedFrameSource] = []
        for trace_id, routes in routes_by_trace.items():
            trace = traces_by_id[trace_id]
            trace_path = Path(trace.path)
            if not trace_path.is_absolute():
                trace_path = base_path / trace_path
            for route, source in routes:
                record = records_by_trace.get(trace_id)
                frame_count, start_ns, end_ns = _source_timing(record, source)
                frame_sources.append(
                    PlannedFrameSource(
                        trace_id=trace_id,
                        source_id=source.id,
                        path=str(trace_path),
                        source_channel=source.channel,
                        bus=source.bus,
                        logical_channel=route.logical_channel,
                        library_trace_id=record.trace_id if record is not None else "",
                        frame_count=frame_count,
                        start_ns=start_ns,
                        end_ns=end_ns,
                    )
                )

        channels = tuple(
            PlannedChannel(
                logical_channel=route.logical_channel,
                device_id=targets_by_id[route.target_id].device_id,
                physical_channel=targets_by_id[route.target_id].physical_channel,
                config=targets_by_id[route.target_id].config,
            )
            for route in scenario.routes
        )
        timeline_size = sum(item.frame_count for item in frame_sources)
        total_ts_ns = max((item.end_ns for item in frame_sources), default=0)
        return ReplayPlan(
            name=scenario.name,
            frame_sources=tuple(frame_sources),
            devices=scenario.devices,
            channels=channels,
            loop=scenario.timeline.loop,
            timeline_size=timeline_size,
            total_ts_ns=total_ts_ns,
        )


def _source_timing(record: TraceRecord | None, source: ReplaySource) -> tuple[int, int, int]:
    if record is None:
        return 0, 0, 0
    source_items = record.metadata.get("source_summaries")
    if isinstance(source_items, list):
        for item in source_items:
            if not isinstance(item, dict):
                continue
            if int(item.get("source_channel", -1)) != source.channel:
                continue
            if BusType(item.get("bus")) != source.bus:
                continue
            return (
                int(item.get("frame_count", 0)),
                int(item.get("start_ns", record.start_ns)),
                int(item.get("end_ns", record.end_ns)),
            )
    return record.event_count, record.start_ns, record.end_ns

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


class BusType(str, Enum):
    CAN = "CAN"
    CANFD = "CANFD"


class ReplayState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


CANFD_PAYLOAD_LENGTHS_BY_DLC = {
    0x0: 0,
    0x1: 1,
    0x2: 2,
    0x3: 3,
    0x4: 4,
    0x5: 5,
    0x6: 6,
    0x7: 7,
    0x8: 8,
    0x9: 12,
    0xA: 16,
    0xB: 20,
    0xC: 24,
    0xD: 32,
    0xE: 48,
    0xF: 64,
}


def canfd_payload_length_to_dlc(payload_length: int) -> int:
    """Convert a CAN FD payload length to the smallest valid DLC.

    Args:
        payload_length: Payload size in bytes.

    Returns:
        The CAN FD data length code that can carry the payload.

    Raises:
        ValueError: If the payload length is negative or exceeds 64 bytes.
    """
    length = int(payload_length)
    if length < 0:
        raise ValueError("CANFD payload length cannot be negative.")
    if length <= 8:
        return length
    for dlc, allowed_length in CANFD_PAYLOAD_LENGTHS_BY_DLC.items():
        if allowed_length >= length:
            return dlc
    raise ValueError(f"CANFD payload length exceeds 64 bytes: {length}")


def canfd_payload_length_from_dlc(dlc: int) -> int:
    """Return the CAN FD payload length represented by a DLC value.

    Args:
        dlc: CAN FD data length code.

    Returns:
        The payload length in bytes for the given DLC.

    Raises:
        KeyError: If the DLC is not one of the CAN FD DLC values.
    """
    return CANFD_PAYLOAD_LENGTHS_BY_DLC[int(dlc)]


@dataclass(frozen=True)
class Frame:
    ts_ns: int
    bus: BusType
    channel: int
    message_id: int
    payload: bytes
    dlc: int
    extended: bool = False
    remote: bool = False
    brs: bool = False
    esi: bool = False
    direction: str = "Rx"
    source_file: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "ts_ns", int(self.ts_ns))
        object.__setattr__(self, "channel", int(self.channel))
        object.__setattr__(self, "message_id", int(self.message_id))
        object.__setattr__(self, "payload", bytes(self.payload))
        object.__setattr__(self, "dlc", int(self.dlc))
        if not isinstance(self.bus, BusType):
            object.__setattr__(self, "bus", BusType(self.bus))

    def clone(self, **updates: Any) -> "Frame":
        """Return a copy of the frame with selected fields replaced.

        Args:
            **updates: Field names and replacement values accepted by
                dataclasses.replace().

        Returns:
            A new immutable Frame instance.
        """
        return replace(self, **updates)


@dataclass(frozen=True)
class ChannelConfig:
    bus: BusType
    nominal_baud: int = 500000
    data_baud: int = 2000000
    resistance_enabled: bool = True
    listen_only: bool = False
    tx_echo: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.bus, BusType):
            object.__setattr__(self, "bus", BusType(self.bus))
        object.__setattr__(self, "nominal_baud", int(self.nominal_baud))
        object.__setattr__(self, "data_baud", int(self.data_baud))


@dataclass(frozen=True)
class TraceConfig:
    id: str
    path: str


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    driver: str
    application: str = "ReplayTool"
    sdk_root: str = "TSMaster/Windows"
    device_type: str = "TC1014"
    device_index: int = 0
    project_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplaySource:
    id: str
    trace_id: str
    channel: int
    bus: BusType

    def __post_init__(self) -> None:
        object.__setattr__(self, "channel", int(self.channel))
        if not isinstance(self.bus, BusType):
            object.__setattr__(self, "bus", BusType(self.bus))


@dataclass(frozen=True)
class ReplayTarget:
    id: str
    device_id: str
    physical_channel: int
    config: ChannelConfig

    def __post_init__(self) -> None:
        object.__setattr__(self, "physical_channel", int(self.physical_channel))


@dataclass(frozen=True)
class ReplayRoute:
    logical_channel: int
    source_id: str
    target_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "logical_channel", int(self.logical_channel))


@dataclass(frozen=True)
class TimelineConfig:
    loop: bool = False
    diagnostics: tuple[dict[str, Any], ...] = ()
    link_actions: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ReplayScenario:
    schema_version: int
    name: str
    traces: tuple[TraceConfig, ...]
    devices: tuple[DeviceConfig, ...]
    sources: tuple[ReplaySource, ...]
    targets: tuple[ReplayTarget, ...]
    routes: tuple[ReplayRoute, ...]
    timeline: TimelineConfig = TimelineConfig()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReplayScenario":
        """Build and validate a replay scenario from a schema v2 mapping.

        Args:
            payload: Parsed scenario JSON payload.

        Returns:
            A validated ReplayScenario instance.

        Raises:
            ValueError: If the schema version is unsupported or references are
                invalid.
            KeyError: If required schema fields are missing.
        """
        if int(payload.get("schema_version", 0)) != 2:
            raise ValueError("Only scenario schema_version=2 is supported.")
        timeline_payload = payload.get("timeline")
        if not isinstance(timeline_payload, dict):
            raise ValueError("Scenario must define timeline settings.")
        traces = tuple(
            TraceConfig(id=str(item["id"]), path=str(item["path"]))
            for item in payload.get("traces", [])
        )
        devices = tuple(
            DeviceConfig(
                id=str(item["id"]),
                driver=str(item["driver"]).lower(),
                application=str(item.get("application", "ReplayTool")),
                sdk_root=str(item.get("sdk_root", "TSMaster/Windows")),
                device_type=str(item.get("device_type", "TC1014")),
                device_index=int(item.get("device_index", 0)),
                project_path=str(item.get("project_path", "")),
                metadata=dict(item.get("metadata", {})),
            )
            for item in payload.get("devices", [])
        )
        sources = tuple(
            ReplaySource(
                id=str(item["id"]),
                trace_id=str(item["trace"]),
                channel=int(item["channel"]),
                bus=BusType(item["bus"]),
            )
            for item in payload.get("sources", [])
        )
        targets = tuple(
            ReplayTarget(
                id=str(item["id"]),
                device_id=str(item["device"]),
                physical_channel=int(item["physical_channel"]),
                config=ChannelConfig(
                    bus=BusType(item["bus"]),
                    nominal_baud=int(item.get("nominal_baud", 500000)),
                    data_baud=int(item.get("data_baud", 2000000)),
                    resistance_enabled=bool(item.get("resistance_enabled", True)),
                    listen_only=bool(item.get("listen_only", False)),
                    tx_echo=bool(item.get("tx_echo", False)),
                ),
            )
            for item in payload.get("targets", [])
        )
        routes = tuple(
            ReplayRoute(
                logical_channel=int(item["logical_channel"]),
                source_id=str(item["source"]),
                target_id=str(item["target"]),
            )
            for item in payload.get("routes", [])
        )
        timeline = TimelineConfig(
            loop=bool(timeline_payload.get("loop", False)),
            diagnostics=tuple(dict(item) for item in timeline_payload.get("diagnostics", [])),
            link_actions=tuple(dict(item) for item in timeline_payload.get("link_actions", [])),
        )
        scenario = cls(
            schema_version=2,
            name=str(payload["name"]),
            traces=traces,
            devices=devices,
            sources=sources,
            targets=targets,
            routes=routes,
            timeline=timeline,
        )
        scenario.validate()
        return scenario

    def validate(self) -> None:
        """Validate required scenario collections and cross references.

        Raises:
            ValueError: If traces, devices, sources, targets, routes, or referenced IDs are
                missing.
        """
        if not self.traces:
            raise ValueError("Scenario must define at least one trace.")
        if not self.devices:
            raise ValueError("Scenario must define at least one device.")
        if not self.sources:
            raise ValueError("Scenario must define at least one source.")
        if not self.targets:
            raise ValueError("Scenario must define at least one target.")
        if not self.routes:
            raise ValueError("Scenario must define at least one route.")
        _validate_ids("trace IDs", [item.id for item in self.traces])
        _validate_ids("device IDs", [item.id for item in self.devices])
        _validate_ids("source IDs", [item.id for item in self.sources])
        _validate_ids("target IDs", [item.id for item in self.targets])
        _validate_ids(
            "scenario resource IDs",
            [item.id for item in self.traces]
            + [item.id for item in self.devices]
            + [item.id for item in self.sources]
            + [item.id for item in self.targets],
        )
        _validate_ids("logical channels", [str(item.logical_channel) for item in self.routes])
        trace_ids = {item.id for item in self.traces}
        device_ids = {item.id for item in self.devices}
        sources_by_id = {item.id: item for item in self.sources}
        targets_by_id = {item.id: item for item in self.targets}
        for source in self.sources:
            if source.trace_id not in trace_ids:
                raise ValueError(f"Source references unknown trace: {source.trace_id}")
        for target in self.targets:
            if target.device_id not in device_ids:
                raise ValueError(f"Target references unknown device: {target.device_id}")
        for route in self.routes:
            source = sources_by_id.get(route.source_id)
            if source is None:
                raise ValueError(f"Route references unknown source: {route.source_id}")
            target = targets_by_id.get(route.target_id)
            if target is None:
                raise ValueError(f"Route references unknown target: {route.target_id}")
            if source.bus != target.config.bus:
                raise ValueError(
                    "Route {logical_channel} connects {source_bus} source to {target_bus} target.".format(
                        logical_channel=route.logical_channel,
                        source_bus=source.bus.value,
                        target_bus=target.config.bus.value,
                    )
                )
        if self.timeline.diagnostics:
            raise ValueError("Scenario timeline diagnostics are not supported yet.")
        if self.timeline.link_actions:
            raise ValueError("Scenario timeline link_actions are not supported yet.")


def _validate_ids(label: str, values: list[str]) -> None:
    missing = [value for value in values if not value]
    if missing:
        raise ValueError(f"Scenario {label} cannot be empty.")
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"Scenario {label} must be unique: {', '.join(duplicates)}")


@dataclass(frozen=True)
class DeviceCapabilities:
    can: bool = False
    canfd: bool = False
    async_send: bool = False
    fifo_read: bool = False


@dataclass(frozen=True)
class DeviceInfo:
    id: str
    driver: str
    name: str
    serial_number: str = ""
    channel_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeviceHealth:
    online: bool
    detail: str = ""
    per_channel: dict[int, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplaySnapshot:
    state: ReplayState = ReplayState.STOPPED
    current_ts_ns: int = 0
    total_ts_ns: int = 0
    timeline_index: int = 0
    timeline_size: int = 0
    sent_frames: int = 0
    skipped_frames: int = 0
    errors: tuple[str, ...] = ()
    completed_loops: int = 0

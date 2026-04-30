from __future__ import annotations

from dataclasses import dataclass

from replay_tool.domain import Frame
from replay_tool.planning import PlannedChannel, ReplayPlan
from replay_tool.ports.device import BusDevice
from replay_tool.ports.registry import DeviceRegistry


@dataclass(frozen=True)
class RoutedFrame:
    """Frame prepared for a physical device endpoint."""

    device_id: str
    device: BusDevice
    channel: PlannedChannel
    frame: Frame


class ReplayDeviceSession:
    """Open devices, start channels, and route logical frames.

    The session owns adapter instances for one configured ReplayPlan. Runtime
    code asks it to translate a frame on a logical channel into a frame on the
    target device's physical channel.
    """

    def __init__(self, registry: DeviceRegistry) -> None:
        self.registry = registry
        self._plan: ReplayPlan | None = None
        self._devices: dict[str, BusDevice] = {}

    def configure(self, plan: ReplayPlan) -> None:
        """Attach a replay plan and clear previous device instances.

        Args:
            plan: Executable replay plan.
        """
        self._plan = plan
        self._devices = {}

    def open_and_start(self) -> None:
        """Open all configured devices and start all planned channels."""
        plan = self._require_plan()
        if self._devices:
            return
        for config in plan.devices:
            device = self.registry.create(config)
            device.open()
            self._devices[config.id] = device
        for channel in plan.channels:
            self._devices[channel.device_id].start_channel(channel.physical_channel, channel.config)

    def route_frame(self, frame: Frame) -> RoutedFrame:
        """Map a logical frame to its physical device endpoint.

        Args:
            frame: Frame whose channel is a logical replay channel.

        Returns:
            Routed frame with device instance and physical channel.

        Raises:
            KeyError: If the frame's logical channel is not planned.
        """
        plan = self._require_plan()
        channel = plan.channel_for_logical(frame.channel)
        device = self._devices[channel.device_id]
        physical = frame.clone(channel=channel.physical_channel)
        return RoutedFrame(
            device_id=channel.device_id,
            device=device,
            channel=channel,
            frame=physical,
        )

    def close(self) -> list[str]:
        """Close all opened devices.

        Returns:
            Cleanup error messages. The session always clears its device table.
        """
        errors: list[str] = []
        for device in self._devices.values():
            try:
                device.close()
            except Exception as exc:  # pragma: no cover - defensive cleanup
                errors.append(str(exc))
        self._devices.clear()
        return errors

    def _require_plan(self) -> ReplayPlan:
        if self._plan is None:
            raise RuntimeError("ReplayDeviceSession is not configured.")
        return self._plan

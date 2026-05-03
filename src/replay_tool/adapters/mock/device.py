from __future__ import annotations

from typing import Sequence

from replay_tool.domain import (
    ChannelConfig,
    DeviceCapabilities,
    DeviceConfig,
    DeviceHealth,
    DeviceInfo,
    Frame,
)


class MockDevice:
    """In-memory BusDevice implementation for tests and local replay."""

    def __init__(self, config: DeviceConfig) -> None:
        self.config = config
        self.opened = False
        self.started_channels: dict[int, ChannelConfig] = {}
        self.sent_frames: list[Frame] = []
        self.rx_frames: list[Frame] = []

    def open(self) -> DeviceInfo:
        """Open the in-memory mock device.

        Returns:
            Device information derived from the mock configuration metadata.
        """
        self.opened = True
        return DeviceInfo(
            id=self.config.id,
            driver="mock",
            name=self.config.metadata.get("name", "MockDevice"),
            channel_count=int(self.config.metadata.get("channel_count", 8)),
        )

    def close(self) -> None:
        """Close the mock device and clear started channels."""
        self.opened = False
        self.started_channels.clear()

    def enumerate_channels(self) -> Sequence[int]:
        """List mock physical channel indexes.

        Returns:
            Channel indexes from 0 up to the configured channel count.
        """
        return tuple(range(int(self.config.metadata.get("channel_count", 8))))

    def start_channel(self, physical_channel: int, config: ChannelConfig) -> None:
        """Mark a mock physical channel as started.

        Args:
            physical_channel: Mock channel index to start.
            config: Bus configuration associated with the channel.
        """
        self.open()
        self.started_channels[int(physical_channel)] = config

    def stop_channel(self, physical_channel: int) -> None:
        """Mark a mock physical channel as stopped.

        Args:
            physical_channel: Mock channel index to stop.
        """
        self.started_channels.pop(int(physical_channel), None)

    def send(self, frames: Sequence[Frame]) -> int:
        """Record frames sent through the mock device.

        Args:
            frames: Frames whose channel field targets a started mock channel.

        Returns:
            Number of frames recorded.

        Raises:
            RuntimeError: If a frame targets a channel that has not been
                started.
        """
        for frame in frames:
            if int(frame.channel) not in self.started_channels:
                raise RuntimeError(f"Mock channel {frame.channel} is not started.")
            self.sent_frames.append(frame)
        return len(frames)

    def read(self, limit: int = 256, timeout_ms: int = 0) -> list[Frame]:
        """Pop queued receive frames from the mock device.

        Args:
            limit: Maximum number of queued frames to return.
            timeout_ms: Ignored by the mock implementation.

        Returns:
            Up to limit frames from the receive queue.
        """
        _ = timeout_ms
        count = min(max(int(limit), 0), len(self.rx_frames))
        result = self.rx_frames[:count]
        del self.rx_frames[:count]
        return result

    def health(self) -> DeviceHealth:
        """Report mock online and channel state.

        Returns:
            Health information based on whether the mock device is open.
        """
        return DeviceHealth(
            online=self.opened,
            detail="Mock online." if self.opened else "Mock closed.",
            per_channel={channel: self.opened for channel in sorted(self.started_channels)},
        )

    def capabilities(self) -> DeviceCapabilities:
        """Report the mock device capability set.

        Returns:
            Capability flags for CAN, CAN FD, async send, and FIFO read.
        """
        return DeviceCapabilities(can=True, canfd=True, async_send=True, fifo_read=True)

from __future__ import annotations

from typing import Protocol, Sequence

from replay_tool.domain import (
    ChannelConfig,
    DeviceCapabilities,
    DeviceHealth,
    DeviceInfo,
    Frame,
)


class BusDevice(Protocol):
    def open(self) -> DeviceInfo:
        """Open the device session.

        Returns:
            Descriptor for the opened device.
        """
        ...

    def close(self) -> None:
        """Close the device session and release adapter resources."""
        ...

    def enumerate_channels(self) -> Sequence[int]:
        """List available physical channels.

        Returns:
            Physical channel indexes supported by the device.
        """
        ...

    def start_channel(self, physical_channel: int, config: ChannelConfig) -> None:
        """Configure and start one physical bus channel.

        Args:
            physical_channel: Device channel index to start.
            config: Bus and bitrate configuration for the channel.
        """
        ...

    def stop_channel(self, physical_channel: int) -> None:
        """Stop one physical bus channel.

        Args:
            physical_channel: Device channel index to stop.
        """
        ...

    def send(self, frames: Sequence[Frame]) -> int:
        """Send frames on already-started physical channels.

        Args:
            frames: Frames whose channel field is a physical channel index.

        Returns:
            Number of frames accepted for transmission.
        """
        ...

    def read(self, limit: int = 256, timeout_ms: int = 0) -> list[Frame]:
        """Read received frames from the device.

        Args:
            limit: Maximum number of frames to return.
            timeout_ms: Maximum time to wait for frames in milliseconds.

        Returns:
            Frames received from physical channels.
        """
        ...

    def health(self) -> DeviceHealth:
        """Report current device health.

        Returns:
            Online status and per-channel state.
        """
        ...

    def capabilities(self) -> DeviceCapabilities:
        """Report static device capabilities.

        Returns:
            Capability flags supported by the adapter.
        """
        ...

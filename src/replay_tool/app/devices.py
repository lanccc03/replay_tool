from __future__ import annotations

from dataclasses import dataclass

from replay_tool.domain import DeviceCapabilities, DeviceHealth, DeviceInfo


@dataclass(frozen=True)
class DeviceEnumerationResult:
    """App-layer result returned after probing one bus device adapter."""

    info: DeviceInfo
    channels: tuple[int, ...]
    capabilities: DeviceCapabilities
    health: DeviceHealth

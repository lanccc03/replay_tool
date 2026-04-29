from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from replay_tool.domain import Frame
from replay_tool.ports.device import BusDevice
from replay_tool.runtime.device_session import ReplayDeviceSession


@dataclass(frozen=True)
class DispatchResult:
    """Counters returned after sending a frame batch."""

    sent_frames: int
    skipped_frames: int


class FrameDispatcher:
    """Group routed frames by device and send them in batches."""

    def __init__(self, session: ReplayDeviceSession) -> None:
        self.session = session

    def dispatch(self, frames: Sequence[Frame]) -> DispatchResult:
        """Send frames grouped by target device.

        Args:
            frames: Logical replay frames due in the current scheduler window.

        Returns:
            Number of frames accepted and skipped across all target devices.
        """
        devices: dict[str, BusDevice] = {}
        grouped: dict[str, list[Frame]] = {}
        for frame in frames:
            routed = self.session.route_frame(frame)
            devices[routed.device_id] = routed.device
            grouped.setdefault(routed.device_id, []).append(routed.frame)

        sent_total = 0
        skipped_total = 0
        for device_id, batch in grouped.items():
            accepted = int(devices[device_id].send(batch) or 0)
            accepted = max(0, min(accepted, len(batch)))
            sent_total += accepted
            skipped_total += len(batch) - accepted
        return DispatchResult(sent_frames=sent_total, skipped_frames=skipped_total)

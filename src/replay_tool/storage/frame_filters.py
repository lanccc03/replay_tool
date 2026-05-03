from __future__ import annotations

from collections.abc import Iterable

from replay_tool.domain import BusType


def normalize_source_filters(
    source_filters: Iterable[tuple[int, BusType]] | None,
) -> set[tuple[int, BusType]] | None:
    """Normalize source-channel filters into a reusable set.

    Args:
        source_filters: Optional `(source_channel, bus)` pairs. Bus values may
            already be BusType instances or values accepted by BusType.

    Returns:
        Normalized `(source_channel, bus)` pairs, or None when no source filter
        should be applied.

    Raises:
        TypeError: If a filter item cannot be unpacked into channel and bus.
        ValueError: If a channel or bus value cannot be normalized.
    """
    if source_filters is None:
        return None
    normalized = {
        (int(channel), bus if isinstance(bus, BusType) else BusType(bus))
        for channel, bus in source_filters
    }
    return normalized or None

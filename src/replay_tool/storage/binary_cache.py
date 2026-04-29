from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
import struct

from replay_tool.domain import BusType, Frame


BINARY_CACHE_FORMAT = "binary-v1"
BINARY_CACHE_SUFFIX = ".frames.bin"
BINARY_CACHE_MAGIC = b"NRPLBIN1"
BINARY_CACHE_VERSION = 1

_FILE_HEADER = struct.Struct("<8sHI")
_RECORD_LENGTH = struct.Struct("<I")
_RECORD_HEADER = struct.Struct("<qBiIHBIII")
_BUS_TYPE_TO_CODE = {
    BusType.CAN: 1,
    BusType.CANFD: 2,
}
_BUS_TYPE_FROM_CODE = {value: key for key, value in _BUS_TYPE_TO_CODE.items()}


def write_binary_frame_cache(path: str | Path, frames: Sequence[Frame]) -> None:
    """Write normalized replay frames to a binary cache file.

    Args:
        path: Destination cache path.
        frames: Frames to serialize in replay order.

    Raises:
        ValueError: If a frame uses an unsupported bus type.
    """
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("wb") as handle:
        handle.write(_FILE_HEADER.pack(BINARY_CACHE_MAGIC, BINARY_CACHE_VERSION, len(frames)))
        for frame in frames:
            handle.write(_encode_record(frame))


def read_binary_frame_cache(
    path: str | Path,
    *,
    source_filters: Iterable[tuple[int, BusType]] | None = None,
    start_ns: int | None = None,
    end_ns: int | None = None,
) -> list[Frame]:
    """Read binary cached frames into memory.

    Args:
        path: Binary cache path.
        source_filters: Optional `(source_channel, bus)` pairs to include.
        start_ns: Optional inclusive lower timestamp bound.
        end_ns: Optional exclusive upper timestamp bound.

    Returns:
        Frames matching the requested filters.
    """
    return list(
        iter_binary_frame_cache(
            path,
            source_filters=source_filters,
            start_ns=start_ns,
            end_ns=end_ns,
        )
    )


def iter_binary_frame_cache(
    path: str | Path,
    *,
    source_filters: Iterable[tuple[int, BusType]] | None = None,
    start_ns: int | None = None,
    end_ns: int | None = None,
) -> Iterator[Frame]:
    """Iterate frames from a binary cache with optional filters.

    Args:
        path: Binary cache path.
        source_filters: Optional `(source_channel, bus)` pairs to include.
        start_ns: Optional inclusive lower timestamp bound.
        end_ns: Optional exclusive upper timestamp bound.

    Yields:
        Frames matching the requested filters.

    Raises:
        ValueError: If the binary cache header or record payload is invalid.
    """
    normalized_filters = _normalize_source_filters(source_filters)
    start_value = int(start_ns) if start_ns is not None else None
    end_value = int(end_ns) if end_ns is not None else None
    cache_path = Path(path)
    with cache_path.open("rb") as handle:
        raw_header = handle.read(_FILE_HEADER.size)
        if len(raw_header) != _FILE_HEADER.size:
            raise ValueError(f"Invalid binary trace cache header: {cache_path}")
        magic, version, record_count = _FILE_HEADER.unpack(raw_header)
        if magic != BINARY_CACHE_MAGIC or int(version) != BINARY_CACHE_VERSION:
            raise ValueError(f"Unsupported binary trace cache format: {cache_path}")
        for _index in range(int(record_count)):
            raw_length = handle.read(_RECORD_LENGTH.size)
            if len(raw_length) != _RECORD_LENGTH.size:
                raise ValueError(f"Truncated binary trace cache record length: {cache_path}")
            record_length = _RECORD_LENGTH.unpack(raw_length)[0]
            raw_record = handle.read(record_length)
            if len(raw_record) != record_length:
                raise ValueError(f"Truncated binary trace cache record: {cache_path}")
            frame = _decode_record(raw_record, cache_path)
            if normalized_filters is not None and (frame.channel, frame.bus) not in normalized_filters:
                continue
            if start_value is not None and frame.ts_ns < start_value:
                continue
            if end_value is not None and frame.ts_ns >= end_value:
                continue
            yield frame


def _encode_record(frame: Frame) -> bytes:
    bus_code = _BUS_TYPE_TO_CODE.get(frame.bus)
    if bus_code is None:
        raise ValueError(f"Unsupported bus type for binary cache: {frame.bus}")
    payload = bytes(frame.payload)
    direction = frame.direction.encode("utf-8")
    source_file = frame.source_file.encode("utf-8")
    flags = (
        (0x01 if frame.extended else 0)
        | (0x02 if frame.remote else 0)
        | (0x04 if frame.brs else 0)
        | (0x08 if frame.esi else 0)
    )
    header = _RECORD_HEADER.pack(
        int(frame.ts_ns),
        int(bus_code),
        int(frame.channel),
        int(frame.message_id) & 0xFFFFFFFF,
        int(frame.dlc),
        int(flags),
        len(payload),
        len(direction),
        len(source_file),
    )
    body = header + payload + direction + source_file
    return _RECORD_LENGTH.pack(len(body)) + body


def _decode_record(raw_record: bytes, cache_path: Path) -> Frame:
    if len(raw_record) < _RECORD_HEADER.size:
        raise ValueError(f"Invalid binary trace cache record: {cache_path}")
    (
        ts_ns,
        bus_code,
        channel,
        message_id,
        dlc,
        flags,
        payload_len,
        direction_len,
        source_len,
    ) = _RECORD_HEADER.unpack_from(raw_record, 0)
    bus = _BUS_TYPE_FROM_CODE.get(int(bus_code))
    if bus is None:
        raise ValueError(f"Unknown binary trace cache bus code {bus_code}: {cache_path}")
    offset = _RECORD_HEADER.size
    expected_size = offset + payload_len + direction_len + source_len
    if len(raw_record) != expected_size:
        raise ValueError(f"Invalid binary trace cache record size: {cache_path}")
    payload = raw_record[offset : offset + payload_len]
    offset += payload_len
    direction = raw_record[offset : offset + direction_len].decode("utf-8")
    offset += direction_len
    source_file = raw_record[offset : offset + source_len].decode("utf-8")
    return Frame(
        ts_ns=int(ts_ns),
        bus=bus,
        channel=int(channel),
        message_id=int(message_id),
        payload=bytes(payload),
        dlc=int(dlc),
        extended=bool(flags & 0x01),
        remote=bool(flags & 0x02),
        brs=bool(flags & 0x04),
        esi=bool(flags & 0x08),
        direction=direction or "Rx",
        source_file=source_file,
    )


def _normalize_source_filters(
    source_filters: Iterable[tuple[int, BusType]] | None,
) -> set[tuple[int, BusType]] | None:
    if source_filters is None:
        return None
    normalized = {
        (int(channel), bus if isinstance(bus, BusType) else BusType(bus))
        for channel, bus in source_filters
    }
    return normalized or None

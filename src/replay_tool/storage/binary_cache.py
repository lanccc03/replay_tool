from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
import struct
from typing import BinaryIO

from replay_tool.domain import BusType, Frame
from replay_tool.storage.frame_filters import normalize_source_filters


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
DEFAULT_INDEX_BLOCK_SIZE = 4096


@dataclass(frozen=True)
class BinaryFrameIndexEntry:
    """Seekable index metadata for a contiguous block of cached frames."""

    block_number: int
    file_offset: int
    start_ns: int
    end_ns: int
    frame_count: int
    sources: tuple[tuple[int, BusType], ...]


class BinaryFrameCacheWriter:
    """Stream frames into a binary cache while collecting block index entries."""

    def __init__(self, path: str | Path, *, block_size: int = DEFAULT_INDEX_BLOCK_SIZE) -> None:
        self.path = Path(path)
        self.tmp_path = self.path.with_name(f"{self.path.name}.tmp")
        self.block_size = max(int(block_size), 1)
        self.index_entries: list[BinaryFrameIndexEntry] = []
        self.frame_count = 0
        self._handle: BinaryIO | None = None
        self._previous_ts_ns: int | None = None
        self._block_number = 0
        self._block_offset = 0
        self._block_start_ns = 0
        self._block_end_ns = 0
        self._block_frame_count = 0
        self._block_sources: set[tuple[int, BusType]] = set()

    def __enter__(self) -> "BinaryFrameCacheWriter":
        """Open the temporary cache and write a placeholder header.

        Returns:
            This writer instance.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.tmp_path.open("wb")
        self._handle.write(_FILE_HEADER.pack(BINARY_CACHE_MAGIC, BINARY_CACHE_VERSION, 0))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Finalize or discard the temporary cache.

        Args:
            exc_type: Exception type supplied by the context manager protocol.
            exc: Exception instance supplied by the context manager protocol.
            tb: Traceback supplied by the context manager protocol.
        """
        handle = self._require_handle()
        if exc_type is None:
            self._finish_block()
            handle.seek(0)
            handle.write(_FILE_HEADER.pack(BINARY_CACHE_MAGIC, BINARY_CACHE_VERSION, self.frame_count))
            handle.close()
            self.tmp_path.replace(self.path)
        else:
            handle.close()
            self.tmp_path.unlink(missing_ok=True)
        self._handle = None

    def write(self, frame: Frame) -> None:
        """Write one frame to the cache.

        Args:
            frame: Normalized frame to append in timestamp order.

        Raises:
            ValueError: If timestamps go backwards or the bus type is unsupported.
        """
        if self._previous_ts_ns is not None and frame.ts_ns < self._previous_ts_ns:
            raise ValueError("Binary cache frames must be ordered by timestamp for streaming replay.")
        handle = self._require_handle()
        if self._block_frame_count >= self.block_size:
            self._finish_block()
        if self._block_frame_count == 0:
            self._block_offset = handle.tell()
            self._block_start_ns = frame.ts_ns
            self._block_sources = set()
        handle.write(_encode_record(frame))
        self.frame_count += 1
        self._previous_ts_ns = frame.ts_ns
        self._block_end_ns = frame.ts_ns
        self._block_frame_count += 1
        self._block_sources.add((frame.channel, frame.bus))

    def _finish_block(self) -> None:
        if self._block_frame_count == 0:
            return
        self.index_entries.append(
            BinaryFrameIndexEntry(
                block_number=self._block_number,
                file_offset=self._block_offset,
                start_ns=self._block_start_ns,
                end_ns=self._block_end_ns,
                frame_count=self._block_frame_count,
                sources=tuple(sorted(self._block_sources, key=lambda item: (item[0], item[1].value))),
            )
        )
        self._block_number += 1
        self._block_frame_count = 0
        self._block_sources = set()

    def _require_handle(self) -> BinaryIO:
        if self._handle is None:
            raise RuntimeError("BinaryFrameCacheWriter is not open.")
        return self._handle


def write_binary_frame_cache(path: str | Path, frames: Iterable[Frame]) -> None:
    """Write normalized replay frames to a binary cache file.

    Args:
        path: Destination cache path.
        frames: Frames to serialize in replay order.

    Raises:
        ValueError: If a frame uses an unsupported bus type or timestamps are
            not ordered.
    """
    with BinaryFrameCacheWriter(path) as writer:
        for frame in frames:
            writer.write(frame)


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
    normalized_filters = normalize_source_filters(source_filters)
    start_value = int(start_ns) if start_ns is not None else None
    end_value = int(end_ns) if end_ns is not None else None
    cache_path = Path(path)
    with cache_path.open("rb") as handle:
        record_count = _read_header(handle, cache_path)
        for _index in range(int(record_count)):
            _offset, frame = _read_record(handle, cache_path)
            if not _matches_filters(frame, normalized_filters, start_value, end_value):
                continue
            yield frame


def iter_binary_frame_cache_blocks(
    path: str | Path,
    blocks: Iterable[BinaryFrameIndexEntry],
    *,
    source_filters: set[tuple[int, BusType]] | None = None,
    start_ns: int | None = None,
    end_ns: int | None = None,
) -> Iterator[Frame]:
    """Iterate selected indexed cache blocks with frame-level filtering.

    Args:
        path: Binary cache path.
        blocks: Index entries to scan.
        source_filters: Optional normalized `(source_channel, bus)` pairs to
            include.
        start_ns: Optional inclusive lower timestamp bound.
        end_ns: Optional exclusive upper timestamp bound.

    Yields:
        Frames matching the requested filters.

    Raises:
        ValueError: If the binary cache header or record payload is invalid.
    """
    selected_blocks = sorted(
        {int(block.block_number): block for block in blocks}.values(),
        key=lambda item: item.file_offset,
    )
    if not selected_blocks:
        return
    start_value = int(start_ns) if start_ns is not None else None
    end_value = int(end_ns) if end_ns is not None else None
    cache_path = Path(path)
    with cache_path.open("rb") as handle:
        _read_header(handle, cache_path)
        for block in selected_blocks:
            handle.seek(int(block.file_offset))
            for _index in range(int(block.frame_count)):
                _offset, frame = _read_record(handle, cache_path)
                if not _matches_filters(frame, source_filters, start_value, end_value):
                    continue
                yield frame


def build_binary_frame_cache_index(
    path: str | Path,
    *,
    block_size: int = DEFAULT_INDEX_BLOCK_SIZE,
) -> list[BinaryFrameIndexEntry]:
    """Build block index entries by scanning an existing binary cache.

    Args:
        path: Binary cache path.
        block_size: Maximum frames per index block.

    Returns:
        Index entries describing seek offsets and timestamp ranges.

    Raises:
        ValueError: If the binary cache header or record payload is invalid.
    """
    entries: list[BinaryFrameIndexEntry] = []
    block_size = max(int(block_size), 1)
    block_number = 0
    block_offset = 0
    block_start_ns = 0
    block_end_ns = 0
    block_frame_count = 0
    block_sources: set[tuple[int, BusType]] = set()
    cache_path = Path(path)
    with cache_path.open("rb") as handle:
        record_count = _read_header(handle, cache_path)
        for _index in range(int(record_count)):
            offset, frame = _read_record(handle, cache_path)
            if block_frame_count >= block_size:
                entries.append(
                    BinaryFrameIndexEntry(
                        block_number=block_number,
                        file_offset=block_offset,
                        start_ns=block_start_ns,
                        end_ns=block_end_ns,
                        frame_count=block_frame_count,
                        sources=tuple(sorted(block_sources, key=lambda item: (item[0], item[1].value))),
                    )
                )
                block_number += 1
                block_frame_count = 0
                block_sources = set()
            if block_frame_count == 0:
                block_offset = offset
                block_start_ns = frame.ts_ns
            block_end_ns = frame.ts_ns
            block_frame_count += 1
            block_sources.add((frame.channel, frame.bus))
        if block_frame_count:
            entries.append(
                BinaryFrameIndexEntry(
                    block_number=block_number,
                    file_offset=block_offset,
                    start_ns=block_start_ns,
                    end_ns=block_end_ns,
                    frame_count=block_frame_count,
                    sources=tuple(sorted(block_sources, key=lambda item: (item[0], item[1].value))),
                )
            )
    return entries


def _read_header(handle: BinaryIO, cache_path: Path) -> int:
    raw_header = handle.read(_FILE_HEADER.size)
    if len(raw_header) != _FILE_HEADER.size:
        raise ValueError(f"Invalid binary trace cache header: {cache_path}")
    magic, version, record_count = _FILE_HEADER.unpack(raw_header)
    if magic != BINARY_CACHE_MAGIC or int(version) != BINARY_CACHE_VERSION:
        raise ValueError(f"Unsupported binary trace cache format: {cache_path}")
    return int(record_count)


def _read_record(handle: BinaryIO, cache_path: Path) -> tuple[int, Frame]:
    offset = handle.tell()
    raw_length = handle.read(_RECORD_LENGTH.size)
    if len(raw_length) != _RECORD_LENGTH.size:
        raise ValueError(f"Truncated binary trace cache record length: {cache_path}")
    record_length = _RECORD_LENGTH.unpack(raw_length)[0]
    raw_record = handle.read(record_length)
    if len(raw_record) != record_length:
        raise ValueError(f"Truncated binary trace cache record: {cache_path}")
    return offset, _decode_record(raw_record, cache_path)


def _matches_filters(
    frame: Frame,
    normalized_filters: set[tuple[int, BusType]] | None,
    start_ns: int | None,
    end_ns: int | None,
) -> bool:
    if normalized_filters is not None and (frame.channel, frame.bus) not in normalized_filters:
        return False
    if start_ns is not None and frame.ts_ns < start_ns:
        return False
    if end_ns is not None and frame.ts_ns >= end_ns:
        return False
    return True


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
